"""Independent, read-only validation of CSV persistence evidence."""
from collections import Counter
from contextlib import closing
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
from typing import Any, BinaryIO, Sequence

from backend.FacilityData.persistence_payload import csv_parser_field_limit
from backend.FacilityData.persistence_trace import TRACE_SEGMENT_BYTE_LIMIT, TRACE_SEGMENT_RECORD_LIMIT

# The r4 CSV pending-payload contract is 64 MiB; the trace's 1 MiB limit
# is not a CSV row limit. Hash reads retain only one 4 KiB chunk.
CSV_ROW_READ_LIMIT = 64 * 1024**2
CSV_READ_CHUNK_BYTES = 4096
CSV_METADATA_READ_LIMIT = TRACE_SEGMENT_BYTE_LIMIT


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
    location_fields = ("file_device", "file_id", "row_byte_offset", "row_byte_length")
    if (kind == "csv_row_data" and all(type(record.get(key)) is int and record[key] >= 0 for key in location_fields)
            and record["row_byte_length"] > 0):
        database.execute("INSERT INTO row_locations VALUES (?, ?, ?, ?)",
                         (str(record["file_device"]), str(record["file_id"]), str(record["row_byte_offset"]),
                          str(record["row_byte_offset"] + record["row_byte_length"])))
    return {"recorded_csv_processing_failure"} if kind == "csv_processing_failure" else set()


def _csv_location_issues(database: sqlite3.Connection) -> set[str]:
    previous_file: tuple[str, str] | None = None
    last_end = 0
    for device, file_id, first, end in database.execute(
            "SELECT device, file_id, first_byte, end_byte FROM row_locations "
            "ORDER BY device, file_id, length(first_byte), first_byte"):
        current_file = (device, file_id)
        if previous_file == current_file and int(first) < last_end:
            return {"overlapping_csv_row_locations"}
        previous_file, last_end = current_file, int(end)
    return set()


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


def _terminal_output_issues(database: sqlite3.Connection, summary: dict[str, Any]) -> set[str]:
    reported = summary.get("required_sink_outcomes")
    if (not isinstance(reported, dict) or reported.get("contract_version") != "CSV_PERSISTENCE_OUTCOMES_V1"
            or reported.get("coverage") != "TERMINAL_REQUIRED_SINK_COUNTS"):
        return {"missing_or_unsupported_terminal_output_summary"}
    event_fields = ("accepted_event_count", "fully_committed_event_count", "failed_event_count", "outstanding_event_count")
    sink_fields = ("accepted_count", "committed_count", "failed_count", "outstanding_count")
    reported_sinks = reported.get("sinks")
    if (any(type(reported.get(field)) is not int or reported[field] < 0 for field in event_fields)
            or not isinstance(reported_sinks, dict) or set(reported_sinks) != {"csv_v1", "csv_v2"}
            or any(not isinstance(counts, dict) or any(type(counts.get(field)) is not int or counts[field] < 0
                                                     for field in sink_fields) for counts in reported_sinks.values())):
        return {"invalid_terminal_output_counts"}
    events: Counter[str] = Counter()
    sinks: dict[str, Counter[str]] = {sink: Counter() for sink in ("csv_v1", "csv_v2")}
    previous = None
    states: list[str] = []

    def finish_event() -> None:
        if not states:
            return
        events["accepted_event_count"] += 1
        field = ("fully_committed_event_count" if all(state == "committed" for state in states)
                 else "outstanding_event_count" if "outstanding" in states else "failed_event_count")
        events[field] += 1

    rows = database.execute("""SELECT e.sequence, e.sink,
        sum(CASE WHEN r.kind='csv_row_data' THEN 1 ELSE 0 END),
        sum(CASE WHEN r.kind='csv_processing_failure' THEN 1 ELSE 0 END)
        FROM required_outputs AS e LEFT JOIN sink_receipts AS r ON e.sequence=r.sequence AND e.sink=r.sink
        GROUP BY e.sequence, e.sink ORDER BY e.sequence, e.sink""")
    for sequence, sink, committed, failed in rows:
        if previous != sequence:
            finish_event()
            states.clear()
            previous = sequence
        state = "committed" if committed == 1 and failed == 0 else "failed" if failed == 1 and committed == 0 else "outstanding"
        states.append(state)
        sinks[sink]["accepted_count"] += 1
        sinks[sink][f"{state}_count"] += 1
    finish_event()
    if (reported.get("counts_reconciled") is not True
            or any(reported[field] != events[field] for field in event_fields)
            or any(reported_sinks[sink][field] != counts[field] for sink, counts in sinks.items() for field in sink_fields)):
        return {"terminal_output_counts_mismatch"}
    return set()


def _file_signature(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _runtime_closeout_issues(summary: dict[str, Any]) -> tuple[set[str], bool]:
    if "runtime_closeout" not in summary:
        return set(), False  # Legacy aggregate totals do not prove closeout.
    closeout = summary["runtime_closeout"]
    if not isinstance(closeout, dict) or closeout.get("contract_version") != "CSV_SHUTDOWN_STATE_V1":
        return {"unsupported_csv_closeout_contract"}, True
    counts = ("csv_write_failure_count", "processing_failure_count", "pending_event_count",
              "unresolved_file_owner_count", "unclosed_handle_count")
    flags = ("data_closeout_succeeded", "runtime_write_failure_observed")
    if (any(type(closeout.get(key)) is not int or closeout[key] < 0 for key in counts)
            or any(type(closeout.get(key)) is not bool for key in flags)
            or type(summary.get("trace_failure_count")) is not int or summary["trace_failure_count"] < 0
            or any(type(summary.get(key)) is not bool for key in ("trace_incomplete", "trace_boundary_failed"))):
        return {"invalid_csv_closeout_state"}, True
    issues: set[str] = set()
    if not closeout["data_closeout_succeeded"] or closeout["runtime_write_failure_observed"]:
        issues.add("csv_runtime_closeout_failed")
    if closeout["csv_write_failure_count"] or closeout["processing_failure_count"]:
        issues.add("recorded_csv_write_failure")
    if any(closeout[key] for key in ("pending_event_count", "unresolved_file_owner_count", "unclosed_handle_count")):
        issues.add("unresolved_csv_shutdown_state")
    outcomes = summary.get("required_sink_outcomes")
    if not isinstance(outcomes, dict) or closeout["pending_event_count"] != outcomes.get("outstanding_event_count"):
        issues.add("csv_shutdown_pending_count_mismatch")
    if summary["trace_failure_count"] or summary["trace_incomplete"] or summary["trace_boundary_failed"]:
        issues.add("csv_trace_history_incomplete")
    return issues, True


def _index_csv_configuration(database: sqlite3.Connection, record: dict[str, Any], body: str) -> set[str]:
    generation, effective = record.get("config_generation"), record.get("effective_from_producer_seq")
    sinks, destination = record.get("required_sinks"), record.get("admitted_log_dir")
    if (type(generation) is not int or generation < 0 or type(effective) is not int or effective < 1
            or not isinstance(sinks, list) or not sinks
            or any(not isinstance(sink, str) or sink not in {"csv_v1", "csv_v2"} for sink in sinks)
            or len(set(sinks)) != len(sinks) or not isinstance(destination, str) or not Path(destination).is_absolute()):
        return {"invalid_csv_config_activation"}
    database.execute("INSERT INTO csv_configurations VALUES (?, ?, ?)", (str(generation), str(effective), body))
    return set()


def _csv_configuration_issues(database: sqlite3.Connection) -> set[str]:
    issues: set[str] = set()
    if database.execute("SELECT 1 FROM csv_configurations GROUP BY generation HAVING count(*)>1 LIMIT 1").fetchone():
        issues.add("duplicate_csv_config_generation")
    if database.execute("SELECT 1 FROM csv_configurations GROUP BY effective HAVING count(*)>1 LIMIT 1").fetchone():
        issues.add("ambiguous_csv_config_boundary")
    configurations = iter(database.execute(
        "SELECT effective, body FROM csv_configurations ORDER BY length(effective), effective"))
    upcoming = next(configurations, None)
    active: dict[str, Any] | None = None
    for sequence, body in database.execute("SELECT sequence, body FROM csv_contracts ORDER BY length(sequence), sequence"):
        admission = json.loads(body)
        while upcoming is not None and int(upcoming[0]) <= int(sequence):
            next_config = json.loads(upcoming[1])
            if active is not None and next_config["config_generation"] <= active["config_generation"]:
                issues.add("nonmonotonic_csv_config_generations")
            active = next_config
            upcoming = next(configurations, None)
        if active is None:
            issues.add("missing_csv_config_activation")
            continue
        if admission.get("config_generation") != active["config_generation"]:
            issues.add("csv_config_interval_mismatch")
        sinks, destination = admission.get("required_sinks"), admission.get("admitted_log_dir")
        if (not isinstance(sinks, list) or any(not isinstance(sink, str) for sink in sinks)
                or not isinstance(destination, str)):
            issues.add("invalid_csv_config_contract")
            continue
        if (sorted(sinks) != sorted(active["required_sinks"])
                or Path(destination) != Path(active["admitted_log_dir"])
                or any(admission.get(field) != active.get(field)
                       for field in ("csv_v2_schema_version", "csv_v2_column_hash"))):
            issues.add("csv_config_contract_mismatch")
    if upcoming is not None:
        issues.add("unbound_csv_config_activation")
    return issues


def _admitted_csv_contract(database: sqlite3.Connection, record: dict[str, Any]) -> tuple[dict[str, Any] | None, set[str]]:
    sequence = record.get("producer_seq")
    if type(sequence) is not int or sequence < 1:
        return None, {"missing_csv_admission_contract"}
    admissions = database.execute("SELECT body FROM csv_contracts WHERE sequence=? LIMIT 2",
                                  (str(sequence),)).fetchall()
    if not admissions:
        return None, {"missing_csv_admission_contract"}
    if len(admissions) != 1:
        return None, {"ambiguous_csv_admission_contract"}
    return json.loads(admissions[0][0]), set()


def _admitted_destination_issues(contract: dict[str, Any], record: dict[str, Any]) -> set[str]:
    destination, filename = contract.get("admitted_log_dir"), record.get("file_path")
    if (not isinstance(destination, str) or not Path(destination).is_absolute()
            or not isinstance(filename, str) or not Path(filename).is_absolute()):
        return {"invalid_csv_destination_contract"}
    # Compare the frozen configured directory, not the current settings or
    # fallback directory. This lexical check never probes an untrusted path.
    return set() if Path(filename).parent == Path(destination) else {"csv_destination_contract_mismatch"}


class _CsvReadWindow(io.RawIOBase):
    """Feed the text/CSV parser a bounded region without owning the file."""

    def __init__(self, handle: BinaryIO, length: int) -> None:
        self.handle = handle
        self.remaining = length

    def readable(self) -> bool:
        return True

    def readinto(self, target: Any) -> int:
        count = min(len(target), self.remaining, CSV_READ_CHUNK_BYTES)
        if count == 0:
            return 0
        chunk = self.handle.read(count)
        target[:len(chunk)] = chunk
        self.remaining -= len(chunk)
        return len(chunk)


def _read_csv_record(handle: BinaryIO, length: int, *, header: bool = False) -> list[str]:
    # At most one admitted row is decoded, not the entire file. The trace's
    # 1 MiB segment cap must not be applied to legitimate larger CSV fields.
    window = _CsvReadWindow(handle, length)
    with csv_parser_field_limit(CSV_ROW_READ_LIMIT), io.TextIOWrapper(
            io.BufferedReader(window), encoding="utf-8-sig" if header else "utf-8", newline="") as text:
        reader = csv.reader(text, strict=True)
        row = next(reader, None)
        if not row or (not header and next(reader, None) is not None):
            raise ValueError("Expected one nonempty CSV record")
        return row


def _csv_format_issues(record: dict[str, Any], contract: dict[str, Any] | None,
                       columns: list[str], values: list[str]) -> set[str]:
    if contract is None:
        return {"missing_csv_admission_contract"}
    if record.get("sink_id") == "csv_v1":
        expected_columns = contract.get("csv_v1_columns")
        if (not isinstance(expected_columns, list) or not expected_columns
                or any(not isinstance(column, str) for column in expected_columns)):
            return {"invalid_csv_format_contract"}
        return set() if expected_columns == columns else {"csv_header_contract_mismatch"}
    if record.get("sink_id") != "csv_v2":
        return {"invalid_csv_format_contract"}
    expected_hash, schema = contract.get("csv_v2_column_hash"), contract.get("csv_v2_schema_version")
    if (not isinstance(expected_hash, str) or len(expected_hash) != 64
            or any(char not in "0123456789abcdef" for char in expected_hash) or not isinstance(schema, str)):
        return {"invalid_csv_format_contract"}
    if schema not in {"2.3.1", "2.4.2", "2.5.2"}:
        return {"unsupported_csv_schema"}
    # The header contract uses ASCII-escaped JSON, unlike the UTF-8 canonical
    # row-content contract. Recompute it from actual columns, not a row receipt.
    actual_hash = hashlib.sha256(json.dumps(columns, ensure_ascii=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    issues = set() if actual_hash == expected_hash else {"csv_header_contract_mismatch"}
    if columns.count("schema_version") != 1 or values[columns.index("schema_version")] != schema:
        issues.add("csv_schema_version_mismatch")
    return issues


def _csv_output_content_issues(handle: BinaryIO, record: dict[str, Any], contract: dict[str, Any] | None) -> set[str]:
    if record.get("output_contract_version") != "CSV_ROW_CONTENT_V1":
        return {"unsupported_csv_output_contract"}
    expected = record.get("output_payload_hash")
    if (not isinstance(expected, str) or len(expected) != 64
            or any(char not in "0123456789abcdef" for char in expected)):
        return {"invalid_csv_output_hash"}
    try:
        handle.seek(0)
        columns = _read_csv_record(handle, min(record["row_byte_offset"], CSV_ROW_READ_LIMIT), header=True)
        handle.seek(record["row_byte_offset"])
        values = _read_csv_record(handle, record["row_byte_length"])
        if len(columns) != len(values):
            return {"invalid_csv_output_record"}
        content = {"contract_version": "CSV_ROW_CONTENT_V1", "columns": columns, "values": values}
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256()
        for piece in encoder.iterencode(content):
            for start in range(0, len(piece), CSV_READ_CHUNK_BYTES):
                digest.update(piece[start:start + CSV_READ_CHUNK_BYTES].encode("utf-8"))
        issues = _csv_format_issues(record, contract, columns, values)
        if digest.hexdigest() != expected:
            issues.add("csv_output_content_hash_mismatch")
        return issues
    except (UnicodeError, ValueError, csv.Error):
        return {"invalid_csv_output_record"}


def _csv_row_issues(record: dict[str, Any], roots: Sequence[tuple[Path, Path]],
                    contract: dict[str, Any] | None) -> tuple[set[str], set[str]]:
    content_issues: set[str] = set()
    integer_fields = ("row_byte_offset", "row_byte_length", "file_device", "file_id")
    if any(type(record.get(field)) is not int or record[field] < 0 for field in integer_fields):
        return {"invalid_csv_row_location"}, content_issues
    offset, length = record["row_byte_offset"], record["row_byte_length"]
    digest = record.get("output_bytes_sha256")
    if (length < 1 or length > CSV_ROW_READ_LIMIT or not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest) or not isinstance(record.get("file_path"), str)):
        return {"invalid_csv_row_location"}, content_issues
    path = Path(record["file_path"])
    if (not path.is_absolute() or path.suffix.lower() != ".csv"
            or not any(path.is_relative_to(raw) or path.is_relative_to(resolved) for raw, resolved in roots)):
        return {"csv_path_outside_allowed_roots"}, content_issues
    try:
        resolved_path = path.resolve(strict=True)
        if not any(resolved_path.is_relative_to(resolved) for _, resolved in roots):
            return {"csv_path_outside_allowed_roots"}, content_issues
        if not stat.S_ISREG(resolved_path.stat().st_mode):
            return {"csv_path_not_regular_file"}, content_issues
        with resolved_path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if (before.st_dev, before.st_ino) != (record["file_device"], record["file_id"]):
                return {"csv_file_identity_mismatch"}, content_issues
            if offset + length > before.st_size:
                return {"csv_row_truncated"}, content_issues
            handle.seek(offset)
            actual = hashlib.sha256()
            remaining = length
            while remaining:
                chunk = handle.read(min(remaining, CSV_READ_CHUNK_BYTES))
                if not chunk:
                    return {"csv_row_truncated"}, content_issues
                actual.update(chunk)
                remaining -= len(chunk)
            if actual.hexdigest() == digest:
                content_issues.update(_csv_output_content_issues(handle, record, contract))
            after = os.fstat(handle.fileno())
            current = resolved_path.stat()
            if _file_signature(before) != _file_signature(after) or _file_signature(after) != _file_signature(current):
                return {"csv_file_changed_during_validation"}, content_issues
            if actual.hexdigest() != digest:
                return {"csv_row_bytes_mismatch"}, content_issues
    except (OSError, ValueError, OverflowError, RuntimeError):
        return {"csv_data_read_error"}, content_issues
    return set(), content_issues


def _index_csv_file_boundary(database: sqlite3.Connection, record: dict[str, Any], body: str) -> set[str]:
    extent, path = record.get("file_extent_id"), record.get("file_path")
    integer_fields = ("file_device", "file_id", "start_byte", "config_generation")
    if (record.get("contract_version") != "CSV_FILE_EXTENT_V1" or not isinstance(extent, str) or not extent
            or not isinstance(path, str) or not Path(path).is_absolute()
            or record.get("sink_id") not in ("csv_v1", "csv_v2")
            or any(type(record.get(field)) is not int or record[field] < 0 for field in integer_fields)):
        return {"invalid_csv_file_boundary"}
    if record["kind"] == "csv_file_end" and (record.get("closed") is not True
            or type(record.get("end_byte")) is not int or record["end_byte"] < record["start_byte"]):
        return {"invalid_csv_file_boundary"}
    database.execute("INSERT INTO csv_file_boundaries VALUES (?, ?, ?)", (extent, record["kind"], body))
    return set()


def _csv_extent_file_issues(record: dict[str, Any], roots: Sequence[tuple[Path, Path]], *, exact_end: bool = True) -> set[str]:
    path = Path(record["file_path"])
    if (path.suffix.lower() != ".csv"
            or not any(path.is_relative_to(raw) or path.is_relative_to(resolved) for raw, resolved in roots)):
        return {"csv_path_outside_allowed_roots"}
    try:
        resolved_path = path.resolve(strict=True)
        if not any(resolved_path.is_relative_to(resolved) for _, resolved in roots):
            return {"csv_path_outside_allowed_roots"}
        if not stat.S_ISREG(resolved_path.stat().st_mode):
            return {"csv_path_not_regular_file"}
        with resolved_path.open("rb") as handle:
            info = os.fstat(handle.fileno())
            if _file_signature(info) != _file_signature(resolved_path.stat()):
                return {"csv_file_changed_during_validation"}
            if (info.st_dev, info.st_ino) != (record["file_device"], record["file_id"]):
                return {"csv_file_identity_mismatch"}
            if info.st_size < record["end_byte"] or (exact_end and info.st_size != record["end_byte"]):
                return {"csv_file_end_size_mismatch"}
    except (OSError, ValueError, OverflowError, RuntimeError):
        return {"csv_data_read_error"}
    return set()


def _csv_file_extent_issues(database: sqlite3.Connection, roots: Sequence[tuple[Path, Path]]) -> tuple[set[str], int]:
    issues: set[str] = set()
    checked = 0
    if database.execute("SELECT 1 FROM csv_rows AS r LEFT JOIN csv_file_boundaries AS b "
                        "ON r.extent=b.extent WHERE b.extent IS NULL LIMIT 1").fetchone():
        issues.add("missing_csv_file_boundary")
    fields = ("file_path", "file_device", "file_id", "sink_id", "config_generation", "start_byte")
    for (extent,) in database.execute("SELECT DISTINCT extent FROM csv_file_boundaries"):
        # At most two records may define an extent; read one extra to reject
        # ambiguity without loading an unbounded history into memory.
        records = [json.loads(body) for (body,) in database.execute(
            "SELECT body FROM csv_file_boundaries WHERE extent=? LIMIT 3", (extent,))]
        if len(records) != 2 or {record["kind"] for record in records} != {"csv_file_start", "csv_file_end"}:
            issues.add("missing_csv_file_boundary" if len(records) < 2 else "ambiguous_csv_file_boundary")
            continue
        start = next(record for record in records if record["kind"] == "csv_file_start")
        end = next(record for record in records if record["kind"] == "csv_file_end")
        if any(start[field] != end[field] for field in fields):
            issues.add("csv_file_boundary_contract_mismatch")
            continue
        issues.update(_csv_extent_file_issues(end, roots, exact_end=False))
        database.execute("INSERT INTO csv_file_ranges VALUES (?, ?, ?, ?, ?)",
                         (str(end["file_device"]), str(end["file_id"]), str(end["start_byte"]),
                          str(end["end_byte"]), json.dumps(end)))
        next_byte = start["start_byte"]
        for (body,) in database.execute("SELECT body FROM csv_rows WHERE extent=? "
                                        "ORDER BY length(first_byte), first_byte", (extent,)):
            row = json.loads(body)
            if (any(row.get(field) != start[field] for field in fields if field != "start_byte")
                    or type(row.get("row_byte_offset")) is not int or row["row_byte_offset"] < 0
                    or type(row.get("row_byte_length")) is not int or row["row_byte_length"] < 1):
                issues.add("csv_file_extent_row_contract_mismatch")
                continue
            offset, row_end = row["row_byte_offset"], row["row_byte_offset"] + row["row_byte_length"]
            if offset > next_byte:
                issues.add("csv_file_coverage_gap")
            elif offset < next_byte:
                issues.add("csv_file_coverage_overlap")
            if offset < start["start_byte"] or row_end > end["end_byte"]:
                issues.add("csv_row_outside_file_extent")
            next_byte = max(next_byte, row_end)
        if next_byte < end["end_byte"]:
            issues.add("csv_file_coverage_gap")
    # Reopening the same physical file after a configuration transition creates
    # another owner, not another physical file. Every successive owner must begin
    # at the preceding owner's end; only the final end is the current EOF.
    previous_file: tuple[str, str] | None = None
    final_end = 0
    final_record: dict[str, Any] | None = None
    for device, file_id, first, last, body in database.execute(
            "SELECT device, file_id, first_byte, end_byte, body FROM csv_file_ranges "
            "ORDER BY device, file_id, length(first_byte), first_byte, length(end_byte), end_byte"):
        current = (device, file_id)
        if current != previous_file:
            if final_record is not None:
                issues.update(_csv_extent_file_issues(final_record, roots))
            checked += 1
            final_record, final_end = json.loads(body), int(last)
        else:
            if int(first) != final_end:
                issues.add("csv_file_owner_overlap" if int(first) < final_end else "csv_file_owner_gap")
            if int(last) >= final_end:
                final_record, final_end = json.loads(body), int(last)
        previous_file = current
    if final_record is not None:
        issues.update(_csv_extent_file_issues(final_record, roots))
    return issues, checked


def _read_csv_metadata(record: dict[str, Any], roots: Sequence[tuple[Path, Path]],
                       commit: dict[str, Any] | None) -> tuple[str | None, set[str]]:
    path = Path(record["file_path"]).with_suffix(".metadata.json")
    if not any(path.is_relative_to(raw) or path.is_relative_to(resolved) for raw, resolved in roots):
        return None, {"csv_metadata_outside_allowed_roots"}
    try:
        resolved_path = path.resolve(strict=True)
        if not any(resolved_path.is_relative_to(resolved) for _, resolved in roots):
            return None, {"csv_metadata_outside_allowed_roots"}
        if not stat.S_ISREG(resolved_path.stat().st_mode):
            return None, {"csv_metadata_not_regular_file"}
        with resolved_path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            raw = handle.read(CSV_METADATA_READ_LIMIT + 1)
            after = os.fstat(handle.fileno())
            if _file_signature(before) != _file_signature(after) or _file_signature(after) != _file_signature(resolved_path.stat()):
                return None, {"csv_metadata_changed_during_validation"}
        if len(raw) > CSV_METADATA_READ_LIMIT:
            return None, {"csv_metadata_byte_limit"}
        text = raw.decode("utf-8-sig")
        if not isinstance(json.loads(text, object_pairs_hook=_unique_object), dict):
            return None, {"invalid_csv_metadata"}
        issues: set[str] = set()
        if commit is None:
            issues.add("missing_csv_metadata_commit")
        elif (commit["metadata_bytes"] != len(raw) or commit["metadata_sha256"] != hashlib.sha256(raw).hexdigest()
              or commit["file_path"] != record["file_path"] or commit["metadata_path"] != str(path)):
            issues.add("csv_metadata_hash_mismatch")
        return text, issues
    except FileNotFoundError:
        return None, {"csv_metadata_missing"}
    except (UnicodeError, ValueError, RecursionError):
        return None, {"invalid_csv_metadata"}
    except (OSError, RuntimeError):
        return None, {"csv_metadata_read_error"}


def _index_csv_metadata_files(database: sqlite3.Connection, roots: Sequence[tuple[Path, Path]]) -> tuple[set[str], int]:
    issues: set[str] = set()
    checked = 0
    for device, file_id in database.execute("SELECT DISTINCT device, file_id FROM csv_file_ranges"):
        (body,) = database.execute("SELECT body FROM csv_file_ranges WHERE device=? AND file_id=? "
                                   "ORDER BY length(end_byte) DESC, end_byte DESC LIMIT 1", (device, file_id)).fetchone()
        record = json.loads(body)
        if record["sink_id"] != "csv_v2":
            continue
        checked += 1
        committed = database.execute("SELECT body FROM csv_metadata_commits WHERE device=? AND file_id=? "
                                     "ORDER BY length(segment) DESC, segment DESC, ordinal DESC LIMIT 1",
                                     (device, file_id)).fetchone()
        metadata, errors = _read_csv_metadata(record, roots, json.loads(committed[0]) if committed else None)
        issues.update(errors)
        if metadata is not None:
            database.execute("INSERT INTO csv_metadata VALUES (?, ?)", (record["file_extent_id"], metadata))
    return issues, checked


def _index_csv_metadata_commit(database: sqlite3.Connection, record: dict[str, Any],
                               segment: Any, ordinal: int) -> set[str]:
    digest = record.get("metadata_sha256")
    if (record.get("contract_version") != "CSV_METADATA_COMMIT_V1"
            or type(segment) is not int or segment < 1
            or any(type(record.get(key)) is not int or record[key] < 0
                   for key in ("file_device", "file_id", "metadata_bytes"))
            or record["metadata_bytes"] > CSV_METADATA_READ_LIMIT
            or any(not isinstance(record.get(key), str) or not Path(record[key]).is_absolute()
                   for key in ("file_path", "metadata_path"))
            or not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        return {"invalid_csv_metadata_commit"}
    database.execute("INSERT INTO csv_metadata_commits VALUES (?, ?, ?, ?, ?)",
                     (str(record["file_device"]), str(record["file_id"]), str(segment), ordinal, json.dumps(record)))
    return set()


def _csv_metadata_values_issues(metadata: dict[str, Any], contract: dict[str, Any], columns: list[str],
                               values: list[str], filename: str, producer: str) -> set[str]:
    schema, closeout = metadata.get("schema_metadata"), metadata.get("csv_closeout")
    if not isinstance(schema, dict) or not isinstance(closeout, dict):
        return {"invalid_csv_metadata_contract"}
    if len(columns) != len(values) or any(columns.count(key) != 1 for key in ("logger_service_instance_id", "sample_seq")):
        return {"invalid_csv_metadata_row_key"}
    issues: set[str] = set()
    if (schema.get("schema_version") != contract.get("csv_v2_schema_version")
            or schema.get("active_schema_version") != contract.get("csv_v2_schema_version")
            or schema.get("active_column_hash") != contract.get("csv_v2_column_hash")
            or schema.get("v2_columns") != columns):
        issues.add("csv_metadata_schema_mismatch")
    if closeout.get("finalized") is not True or "spot_observation_fact_closeout" in metadata:
        issues.add("csv_metadata_closeout_unfinalized")
    sample = values[columns.index("sample_seq")]
    if not sample.isascii() or not sample.isdecimal() or int(sample) < 1:
        issues.add("invalid_csv_metadata_row_key")
    elif (type(closeout.get("final_persisted_sample_seq")) is not int
          or closeout["final_persisted_sample_seq"] != int(sample)
          or values[columns.index("logger_service_instance_id")] != producer
          or closeout.get("logger_service_instance_id") != producer
          or closeout.get("csv_file_name") != filename
          or not isinstance(closeout.get("persisted_at"), str) or not closeout["persisted_at"]
          or not isinstance(closeout.get("closeout_reason"), str) or not closeout["closeout_reason"]):
        issues.add("csv_metadata_closeout_mismatch")
    return issues


def _csv_metadata_contract_issues(database: sqlite3.Connection, roots: Sequence[tuple[Path, Path]],
                                 producer: Any) -> set[str]:
    issues: set[str] = set()
    for extent, body in database.execute("SELECT extent, body FROM csv_metadata"):
        last_row = database.execute("SELECT body FROM csv_rows WHERE extent=? "
                                    "ORDER BY length(first_byte) DESC, first_byte DESC LIMIT 1", (extent,)).fetchone()
        if last_row is None or not isinstance(producer, str) or not producer:
            issues.add("missing_csv_metadata_row_key")
            continue
        row = json.loads(last_row[0])
        contract, errors = _admitted_csv_contract(database, row)
        issues.update(errors)
        if contract is None:
            continue
        try:
            path = Path(row["file_path"]).resolve(strict=True)
            if not any(path.is_relative_to(resolved) for _, resolved in roots):
                issues.add("csv_path_outside_allowed_roots")
                continue
            with path.open("rb") as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (row["file_device"], row["file_id"]):
                    issues.add("csv_file_identity_mismatch")
                    continue
                columns = _read_csv_record(handle, min(row["row_byte_offset"], CSV_ROW_READ_LIMIT), header=True)
                handle.seek(row["row_byte_offset"])
                values = _read_csv_record(handle, row["row_byte_length"])
                after = os.fstat(handle.fileno())
                if _file_signature(before) != _file_signature(after) or _file_signature(after) != _file_signature(path.stat()):
                    issues.add("csv_file_changed_during_validation")
                    continue
            issues.update(_csv_metadata_values_issues(json.loads(body), contract, columns, values, path.name, producer))
        except (OSError, ValueError, OverflowError, RuntimeError, csv.Error):
            issues.add("csv_metadata_row_read_error")
    return issues


def _validate_csv_trace(paths: Sequence[Path], database: sqlite3.Connection, data_roots: Sequence[Path]) -> dict[str, Any]:
    """Read bounded segments without treating their presence as full data proof."""
    issues: set[str] = set()
    records = 0
    summaries = 0
    unsupported = False
    boundaries: dict[str, list[int]] = {"producer_start": [], "producer_stop": []}
    summary_bounds: tuple[int, int] | None = None
    identities: dict[str, str] = {}
    terminal_summary: dict[str, Any] | None = None
    closeout_issues: set[str] = set()
    closeout_evaluated = False
    byte_issues: set[str] = set()
    content_issues: set[str] = set()
    destination_issues: set[str] = set()
    configuration_issues: set[str] = set()
    file_issues: set[str] = set()
    checked_rows = 0
    roots: list[tuple[Path, Path]] = []
    for root in data_roots:
        try:
            resolved = root.resolve(strict=True)
            if not resolved.is_dir():
                byte_issues.add("invalid_csv_data_root")
            else:
                roots.append((root.absolute(), resolved))
        except (OSError, ValueError, RuntimeError):
            byte_issues.add("invalid_csv_data_root")
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
        for ordinal, line in enumerate(lines[1:]):
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
            if data_roots:
                if record.get("kind") == "csv_admission" and type(record.get("producer_seq")) is int:
                    database.execute("INSERT INTO csv_contracts VALUES (?, ?)",
                                     (str(record["producer_seq"]), line.decode("utf-8")))
                elif record.get("kind") == "csv_row_data":
                    extent, offset = record.get("file_extent_id"), record.get("row_byte_offset")
                    database.execute("INSERT INTO csv_rows VALUES (?, ?, ?)",
                                     (extent if isinstance(extent, str) else None,
                                      str(offset) if type(offset) is int else "", line.decode("utf-8")))
                elif record.get("kind") == "config_activated":
                    configuration_issues.update(_index_csv_configuration(database, record, line.decode("utf-8")))
                elif record.get("kind") in ("csv_file_start", "csv_file_end"):
                    file_issues.update(_index_csv_file_boundary(database, record, line.decode("utf-8")))
                elif record.get("kind") == "csv_metadata_commit":
                    file_issues.update(_index_csv_metadata_commit(database, record, segment_id, ordinal))
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
    # A receipt's segment may precede its admission in the caller's file list.
    # Keep bounded records on disk, then compare each row to its original contract.
    for (body,) in database.execute("SELECT body FROM csv_rows"):
        row = json.loads(body)
        checked_rows += 1
        contract, contract_issues = _admitted_csv_contract(database, row)
        destination_issues.update(contract_issues)
        configuration_issues.update(contract_issues)
        if contract is not None:
            destination_issues.update(_admitted_destination_issues(contract, row))
        row_byte_issues, row_content_issues = _csv_row_issues(row, roots, contract)
        byte_issues.update(row_byte_issues)
        content_issues.update(row_content_issues)
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
        issues.update(_terminal_output_issues(database, terminal_summary))
        closeout_issues, closeout_evaluated = _runtime_closeout_issues(terminal_summary)
        issues.update(closeout_issues)
    issues.update(_required_sink_issues(database))
    issues.update(_csv_location_issues(database))
    configuration_issues.update(_csv_configuration_issues(database))
    extent_issues, checked_files = _csv_file_extent_issues(database, roots)
    file_issues.update(extent_issues)
    metadata_issues: set[str] = set()
    metadata_contract_issues: set[str] = set()
    checked_metadata = 0
    if data_roots and not (byte_issues or file_issues):
        metadata_issues, checked_metadata = _index_csv_metadata_files(database, roots)
        if not content_issues:
            metadata_contract_issues = _csv_metadata_contract_issues(database, roots, identities.get("producer"))
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
    issues.update(byte_issues)
    issues.update(content_issues)
    issues.update(destination_issues)
    issues.update(configuration_issues)
    issues.update(file_issues)
    issues.update(metadata_issues)
    issues.update(metadata_contract_issues)
    metadata_read_issues = metadata_issues - {"csv_metadata_hash_mismatch", "missing_csv_metadata_commit"}
    incomplete = bool(issues - {"missing_trace"})
    if unsupported:
        issues.add("unsupported_trace_schema")
    csv_integrity_issues = set(issues)
    if terminal_summary is not None and type(terminal_summary.get("rejected_count")) is int and terminal_summary["rejected_count"]:
        csv_integrity_issues.add("csv_admissions_rejected")
    csv_integrity_status = "NOT_EVALUATED"
    if paths and csv_integrity_issues:
        csv_integrity_status = "INCOMPLETE"
    elif (paths and data_roots and checked_rows and checked_files and closeout_evaluated and summaries == 1):
        csv_integrity_status = "VERIFIED"
    return {"contract_version": "CSV_PERSISTENCE_VALIDATION_V1",
            "coverage": "CSV_ADMISSION_AND_REQUIRED_SINK_EVIDENCE",
            "csv_integrity_scope": "CSV_CURRENT_PRODUCER_OWNED_RANGES",
            "csv_integrity_status": csv_integrity_status, "csv_integrity_issues": sorted(csv_integrity_issues),
            "status": "INCOMPLETE" if incomplete else "NOT_EVALUATED",
            "issues": sorted(issues), "segment_count": len(paths), "record_count": records,
            "admission_summary_count": summaries, "data_integrity_status": "NOT_EVALUATED",
            "runtime_closeout_status": ("INCOMPLETE" if closeout_issues else "VERIFIED"
                                        if closeout_evaluated and summaries == 1 else "NOT_EVALUATED"),
            "checked_csv_rows": checked_rows,
            "checked_csv_files": checked_files,
            "checked_csv_metadata": checked_metadata,
            "metadata_bytes_status": ("INCOMPLETE" if byte_issues or file_issues or metadata_issues else "VERIFIED"
                                      if checked_metadata else "NOT_EVALUATED"),
            "metadata_read_status": ("INCOMPLETE" if byte_issues or file_issues or metadata_read_issues else "VERIFIED"
                                     if checked_metadata else "NOT_EVALUATED"),
            "metadata_contract_status": ("INCOMPLETE" if byte_issues or file_issues or content_issues
                                         or metadata_issues or metadata_contract_issues else "VERIFIED"
                                         if checked_metadata else "NOT_EVALUATED"),
            "file_extent_status": "INCOMPLETE" if byte_issues or file_issues else "VERIFIED" if checked_files else "NOT_EVALUATED",
            "row_bytes_status": "INCOMPLETE" if byte_issues else "VERIFIED" if checked_rows else "NOT_EVALUATED",
            "destination_status": "INCOMPLETE" if byte_issues or destination_issues else "VERIFIED" if checked_rows else "NOT_EVALUATED",
            "configuration_status": "INCOMPLETE" if configuration_issues else "VERIFIED" if checked_rows else "NOT_EVALUATED",
            "output_content_status": "INCOMPLETE" if byte_issues or content_issues else "VERIFIED" if checked_rows else "NOT_EVALUATED"}


def validate_csv_persistence_trace(paths: Sequence[Path], *, data_roots: Sequence[Path] = ()) -> dict[str, Any]:
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
                database.execute("CREATE TABLE row_locations (device TEXT, file_id TEXT, first_byte TEXT, end_byte TEXT)")
                database.execute("CREATE INDEX row_location_order ON row_locations(device, file_id, length(first_byte), first_byte)")
                database.execute("CREATE TABLE csv_contracts (sequence TEXT, body TEXT)")
                database.execute("CREATE INDEX csv_contract_identity ON csv_contracts(sequence)")
                database.execute("CREATE TABLE csv_rows (extent TEXT, first_byte TEXT, body TEXT)")
                database.execute("CREATE INDEX csv_extent_rows ON csv_rows(extent, length(first_byte), first_byte)")
                database.execute("CREATE TABLE csv_file_boundaries (extent TEXT, kind TEXT, body TEXT)")
                database.execute("CREATE INDEX csv_boundary_extent ON csv_file_boundaries(extent)")
                database.execute("CREATE TABLE csv_file_ranges (device TEXT, file_id TEXT, first_byte TEXT, end_byte TEXT, body TEXT)")
                database.execute("CREATE INDEX csv_file_range_order ON csv_file_ranges(device, file_id, length(first_byte), first_byte)")
                database.execute("CREATE TABLE csv_metadata (extent TEXT PRIMARY KEY, body TEXT)")
                database.execute("CREATE TABLE csv_metadata_commits (device TEXT, file_id TEXT, segment TEXT, ordinal INTEGER, body TEXT)")
                database.execute("CREATE INDEX csv_metadata_commit_order ON csv_metadata_commits"
                                 "(device, file_id, length(segment), segment, ordinal)")
                database.execute("CREATE TABLE csv_configurations (generation TEXT, effective TEXT, body TEXT)")
                database.execute("CREATE INDEX csv_configuration_order ON csv_configurations(length(effective), effective)")
                return _validate_csv_trace(paths, database, data_roots)
    except (OSError, sqlite3.Error):
        return {"contract_version": "CSV_PERSISTENCE_VALIDATION_V1", "coverage": "CSV_ADMISSION_AND_REQUIRED_SINK_EVIDENCE",
                "csv_integrity_scope": "CSV_CURRENT_PRODUCER_OWNED_RANGES", "csv_integrity_status": "INCOMPLETE",
                "csv_integrity_issues": ["validator_workspace_unavailable"],
                "status": "INCOMPLETE", "issues": ["validator_workspace_unavailable"],
                "segment_count": len(paths), "record_count": 0, "admission_summary_count": 0,
                "data_integrity_status": "NOT_EVALUATED", "checked_csv_rows": 0, "row_bytes_status": "NOT_EVALUATED",
                "output_content_status": "NOT_EVALUATED", "destination_status": "NOT_EVALUATED",
                "configuration_status": "NOT_EVALUATED", "checked_csv_files": 0,
                "file_extent_status": "NOT_EVALUATED", "runtime_closeout_status": "NOT_EVALUATED",
                "checked_csv_metadata": 0, "metadata_read_status": "NOT_EVALUATED",
                "metadata_bytes_status": "NOT_EVALUATED",
                "metadata_contract_status": "NOT_EVALUATED"}
