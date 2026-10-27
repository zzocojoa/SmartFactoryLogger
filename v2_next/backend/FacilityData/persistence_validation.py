"""Independent, read-only validation of CSV persistence evidence."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Sequence

from backend.FacilityData.persistence_trace import TRACE_SEGMENT_BYTE_LIMIT, TRACE_SEGMENT_RECORD_LIMIT


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence field")
        result[key] = value
    return result


def _admission_total_issues(summary: dict[str, Any]) -> set[str]:
    fields = ("produced_count", "accounted_count", "unaccounted_count", "accepted_count",
              "excluded_count", "rejected_count", "after_producer_seq", "last_producer_seq")
    if any(type(summary.get(field)) is not int or summary[field] < 0 for field in fields):
        return {"invalid_admission_totals"}
    issues: set[str] = set()
    if (summary["accepted_count"] + summary["excluded_count"] + summary["rejected_count"]
            != summary["accounted_count"]
            or summary["accounted_count"] + summary["unaccounted_count"] != summary["produced_count"]
            or summary["last_producer_seq"] - summary["after_producer_seq"] != summary["produced_count"]):
        issues.add("admission_totals_mismatch")
    if summary["unaccounted_count"]:
        issues.add("unaccounted_producer_ids")
    counts = summary.get("outcome_counts")
    allowed = {"ACCEPTED", "DISABLED", "REJECTED_FULL", "REJECTED_LIMIT", "REJECTED_UNAVAILABLE",
               "REJECTED_CLOSED", "INVALID"}
    if (not isinstance(counts, dict) or any(key not in allowed or type(value) is not int or value < 0
                                          for key, value in counts.items())):
        issues.add("invalid_admission_status_counts")
    elif (sum(counts.values()) != summary["accounted_count"]
          or counts.get("ACCEPTED", 0) != summary["accepted_count"]
          or counts.get("DISABLED", 0) != summary["excluded_count"]):
        issues.add("admission_status_totals_mismatch")
    if summary.get("details_incomplete") is True:
        issues.add("reported_admission_detail_loss")
    return issues


def _index_admission(database: sqlite3.Connection, record: dict[str, Any], producer: Any) -> set[str]:
    kind = record.get("kind")
    if not isinstance(kind, str) or kind not in {"csv_admission", "admission_exclusion_range", "admission_rejection_range"}:
        return set()
    status = record.get("status")
    if kind == "csv_admission":
        first = last = record.get("producer_seq")
        allowed = {"ACCEPTED"}
        contract = "CSV_ADMISSION_EVENT_V1"
        if record.get("producer_instance_id") != producer:
            return {"admission_producer_identity_mismatch"}
    else:
        first, last = record.get("first_producer_seq"), record.get("last_producer_seq")
        excluded = kind == "admission_exclusion_range"
        allowed = {"DISABLED"} if excluded else {"REJECTED_FULL", "REJECTED_LIMIT", "REJECTED_UNAVAILABLE",
                                               "REJECTED_CLOSED", "INVALID"}
        contract = "CSV_ADMISSION_EXCLUSIONS_V1" if excluded else "CSV_ADMISSION_REJECTIONS_V1"
    if (type(first) is not int or type(last) is not int or first < 1 or last < first
            or not isinstance(status, str) or status not in allowed or record.get("contract_version") != contract):
        return {"invalid_admission_identity"}
    # Decimal text avoids a narrowing conversion to SQLite's signed 64-bit integers.
    # Ranges stay ranges: an excluded interval is never expanded into per-ID objects.
    database.execute("INSERT INTO outcomes VALUES (?, ?, ?)", (str(first), str(last), status))
    return set()


def _admission_identity_issues(database: sqlite3.Connection, summary: dict[str, Any]) -> set[str]:
    after, final = summary.get("after_producer_seq"), summary.get("last_producer_seq")
    if type(after) is not int or type(final) is not int or after < 0 or final < after:
        return set()  # The summary/boundary checks report invalid bounds independently.
    issues: set[str] = set()
    counts: Counter[str] = Counter()
    next_sequence = after + 1
    for first_text, last_text, status in database.execute(
            "SELECT first_seq, last_seq, status FROM outcomes ORDER BY length(first_seq), first_seq"):
        first, last = int(first_text), int(last_text)
        if first <= after or last > final:
            issues.add("admission_identity_outside_producer_bounds")
        if first < next_sequence:
            issues.add("overlapping_admission_identities")
        elif first > next_sequence:
            issues.add("missing_admission_identities")
        next_sequence = max(next_sequence, last + 1)
        counts[status] += last - first + 1
    if next_sequence < final + 1:
        issues.add("missing_admission_identities")
    reported = summary.get("outcome_counts")
    if isinstance(reported, dict) and any(counts[key] != reported.get(key, 0) for key in counts.keys() | reported.keys()):
        issues.add("admission_identity_totals_mismatch")
    return issues


def _index_sink_record(database: sqlite3.Connection, record: dict[str, Any], producer: Any) -> set[str]:
    kind = record.get("kind")
    if not isinstance(kind, str) or kind not in {"csv_admission", "csv_row_data", "csv_processing_failure"}:
        return set()
    sequence, generation, digest = record.get("producer_seq"), record.get("config_generation"), record.get("source_payload_hash")
    if (type(sequence) is not int or sequence < 1 or type(generation) is not int or generation < 0
            or not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)):
        return {"invalid_sink_record_identity"}
    if kind != "csv_row_data" and record.get("producer_instance_id") != producer:
        return {"output_producer_identity_mismatch"}
    sinks = record.get("required_sinks") if kind == "csv_admission" else [record.get("sink_id")]
    if (not isinstance(sinks, list) or not sinks
            or any(not isinstance(sink, str) or sink not in {"csv_v1", "csv_v2"} for sink in sinks)
            or len(set(sinks)) != len(sinks)):
        return {"invalid_required_sink_contract"}
    if kind == "csv_row_data" and (type(record.get("record_version")) is not int or record["record_version"] != 1):
        return {"unsupported_csv_row_evidence"}
    if kind == "csv_processing_failure" and (record.get("contract_version") != "CSV_PROCESSING_FAILURE_V1"
                                             or record.get("status") != "FAILED"
                                             or not isinstance(record.get("reason"), str) or not record["reason"]):
        return {"invalid_processing_failure_evidence"}
    for sink in sinks:
        values = (str(sequence), sink, digest, str(generation))
        if kind == "csv_admission":
            database.execute("INSERT INTO required_outputs VALUES (?, ?, ?, ?)", values)
        else:
            database.execute("INSERT INTO sink_receipts VALUES (?, ?, ?, ?, ?)", (*values, kind))
    return {"recorded_csv_processing_failure"} if kind == "csv_processing_failure" else set()


def _required_sink_issues(database: sqlite3.Connection) -> set[str]:
    checks = {
        "missing_required_sink_evidence": """SELECT 1 FROM required_outputs AS e LEFT JOIN sink_receipts AS r
            ON e.sequence=r.sequence AND e.sink=r.sink WHERE r.sequence IS NULL LIMIT 1""",
        "unadmitted_sink_evidence": """SELECT 1 FROM sink_receipts AS r LEFT JOIN required_outputs AS e
            ON e.sequence=r.sequence AND e.sink=r.sink WHERE e.sequence IS NULL LIMIT 1""",
        "sink_evidence_contract_mismatch": """SELECT 1 FROM required_outputs AS e JOIN sink_receipts AS r
            ON e.sequence=r.sequence AND e.sink=r.sink
            WHERE e.source_hash!=r.source_hash OR e.generation!=r.generation LIMIT 1""",
        "multiple_sink_outcomes": "SELECT 1 FROM sink_receipts GROUP BY sequence, sink HAVING count(*)>1 LIMIT 1",
    }
    return {issue for issue, query in checks.items() if database.execute(query).fetchone() is not None}


def _validate_csv_trace(paths: Sequence[Path], database: sqlite3.Connection) -> dict[str, Any]:
    """Read bounded segments without treating their presence as full data proof."""
    issues: set[str] = set()
    records = 0
    summaries = 0
    unsupported = False
    boundaries: dict[str, list[int]] = {"producer_start": [], "producer_stop": []}
    summary_bounds: tuple[int, int] | None = None
    identities: dict[str, str] = {}
    terminal_summary: dict[str, Any] | None = None
    for path in paths:
        try:
            with path.open("rb") as handle:
                raw = handle.read(TRACE_SEGMENT_BYTE_LIMIT + 1)
        except OSError:
            issues.add("trace_read_error")
            continue
        if len(raw) > TRACE_SEGMENT_BYTE_LIMIT:
            issues.add("segment_byte_limit")
            continue
        lines = raw.splitlines()
        if not lines or not raw.endswith(b"\n"):
            issues.add("incomplete_segment")
            continue
        if len(lines) - 1 > TRACE_SEGMENT_RECORD_LIMIT:
            issues.add("segment_record_limit")
            continue
        try:
            header = json.loads(lines[0].decode("utf-8"), object_pairs_hook=_unique_object)
            if not isinstance(header, dict):
                raise ValueError("Invalid trace header")
            if type(header.get("schema_version")) is not int or header["schema_version"] != 1:
                unsupported = True
                continue
        except (ValueError, RecursionError):
            issues.add("invalid_segment_header")
            continue
        for identity in ("producer", "writer"):
            value = header.get(f"{identity}_instance_id")
            if not isinstance(value, str) or not value:
                issues.add("invalid_segment_identity")
            elif identity in identities and value != identities[identity]:
                issues.add(f"mixed_{identity}_identity")
            else:
                identities[identity] = value
        segment_id = header.get("segment_id")
        if type(segment_id) is not int or segment_id < 1:
            issues.add("invalid_trace_segment_id")
        else:
            try:
                database.execute("INSERT INTO segments VALUES (?)", (str(segment_id),))
            except sqlite3.IntegrityError:
                issues.add("duplicate_trace_segment_id")
        for line in lines[1:]:
            try:
                record = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
                if not isinstance(record, dict):
                    raise ValueError("Invalid trace record")
            except (ValueError, RecursionError):
                issues.add("invalid_trace_record")
                continue
            records += 1
            issues.update(_index_admission(database, record, header.get("producer_instance_id")))
            issues.update(_index_sink_record(database, record, header.get("producer_instance_id")))
            kind = record.get("kind")
            if isinstance(kind, str) and kind in boundaries:
                field = "after_producer_seq" if kind == "producer_start" else "final_producer_seq"
                value = record.get(field)
                if type(value) is not int or value < 0:
                    issues.add("invalid_producer_boundary")
                elif len(boundaries[kind]) < 2:
                    boundaries[kind].append(value)
            if record.get("kind") == "admission_summary":
                summaries += 1
                terminal_summary = record
                issues.update(_admission_total_issues(record))
                if all(type(record.get(key)) is int for key in ("after_producer_seq", "last_producer_seq")):
                    summary_bounds = record["after_producer_seq"], record["last_producer_seq"]
    if not paths:
        issues.add("missing_trace")
    if paths and not unsupported and summaries == 0:
        issues.add("missing_admission_summary")
    if summaries > 1:
        issues.add("multiple_admission_summaries")
    segment_total = database.execute("SELECT count(*) FROM segments").fetchone()[0]
    if segment_total:
        largest = database.execute(
            "SELECT segment_id FROM segments ORDER BY length(segment_id) DESC, segment_id DESC LIMIT 1").fetchone()[0]
        if int(largest) != segment_total:
            issues.add("noncontiguous_trace_segments")
    if terminal_summary is not None:
        issues.update(_admission_identity_issues(database, terminal_summary))
    issues.update(_required_sink_issues(database))
    if paths and not unsupported:
        for kind, values in boundaries.items():
            if not values:
                issues.add(f"missing_{kind}")
            elif len(values) > 1:
                issues.add(f"multiple_{kind}")
        if all(len(values) == 1 for values in boundaries.values()):
            observed = boundaries["producer_start"][0], boundaries["producer_stop"][0]
            if observed[1] < observed[0] or (summary_bounds is not None and observed != summary_bounds):
                issues.add("producer_boundary_mismatch")
    incomplete = bool(issues - {"missing_trace"})
    if unsupported:
        issues.add("unsupported_trace_schema")
    return {"contract_version": "CSV_PERSISTENCE_VALIDATION_V1",
            "coverage": "CSV_ADMISSION_AND_REQUIRED_SINK_EVIDENCE",
            "status": "INCOMPLETE" if incomplete else "NOT_EVALUATED",
            "issues": sorted(issues), "segment_count": len(paths), "record_count": records,
            "admission_summary_count": summaries, "data_integrity_status": "NOT_EVALUATED"}


def validate_csv_persistence_trace(paths: Sequence[Path]) -> dict[str, Any]:
    """Validate evidence without rewriting it or retaining all outcome IDs in RAM."""
    try:
        with tempfile.TemporaryDirectory(prefix="sfl-evidence-") as workspace:
            with closing(sqlite3.connect(str(Path(workspace) / "admissions.sqlite"))) as database:
                database.execute("PRAGMA cache_size=-1024")
                database.execute("PRAGMA temp_store=FILE")
                database.execute("CREATE TABLE outcomes (first_seq TEXT, last_seq TEXT, status TEXT)")
                database.execute("CREATE INDEX outcome_order ON outcomes(length(first_seq), first_seq)")
                database.execute("CREATE TABLE segments (segment_id TEXT PRIMARY KEY)")
                database.execute("CREATE TABLE required_outputs (sequence TEXT, sink TEXT, source_hash TEXT, generation TEXT)")
                database.execute("CREATE INDEX required_output_identity ON required_outputs(sequence, sink)")
                database.execute("CREATE TABLE sink_receipts (sequence TEXT, sink TEXT, source_hash TEXT, generation TEXT, kind TEXT)")
                database.execute("CREATE INDEX sink_receipt_identity ON sink_receipts(sequence, sink)")
                return _validate_csv_trace(paths, database)
    except (OSError, sqlite3.Error):
        return {"contract_version": "CSV_PERSISTENCE_VALIDATION_V1", "coverage": "CSV_ADMISSION_AND_REQUIRED_SINK_EVIDENCE",
                "status": "INCOMPLETE", "issues": ["validator_workspace_unavailable"],
                "segment_count": len(paths), "record_count": 0, "admission_summary_count": 0,
                "data_integrity_status": "NOT_EVALUATED"}
