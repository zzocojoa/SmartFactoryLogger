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
    byte_issues: set[str] = set()
    content_issues: set[str] = set()
    destination_issues: set[str] = set()
    configuration_issues: set[str] = set()
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
            if data_roots:
                if record.get("kind") == "csv_admission" and type(record.get("producer_seq")) is int:
                    database.execute("INSERT INTO csv_contracts VALUES (?, ?)",
                                     (str(record["producer_seq"]), line.decode("utf-8")))
                elif record.get("kind") == "csv_row_data":
                    database.execute("INSERT INTO csv_rows VALUES (?)", (line.decode("utf-8"),))
                elif record.get("kind") == "config_activated":
                    configuration_issues.update(_index_csv_configuration(database, record, line.decode("utf-8")))
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
    issues.update(_required_sink_issues(database))
    issues.update(_csv_location_issues(database))
    configuration_issues.update(_csv_configuration_issues(database))
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
    incomplete = bool(issues - {"missing_trace"})
    if unsupported:
        issues.add("unsupported_trace_schema")
    return {"contract_version": "CSV_PERSISTENCE_VALIDATION_V1",
            "coverage": "CSV_ADMISSION_AND_REQUIRED_SINK_EVIDENCE",
            "status": "INCOMPLETE" if incomplete else "NOT_EVALUATED",
            "issues": sorted(issues), "segment_count": len(paths), "record_count": records,
            "admission_summary_count": summaries, "data_integrity_status": "NOT_EVALUATED",
            "checked_csv_rows": checked_rows,
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
                database.execute("CREATE TABLE csv_rows (body TEXT)")
                database.execute("CREATE TABLE csv_configurations (generation TEXT, effective TEXT, body TEXT)")
                database.execute("CREATE INDEX csv_configuration_order ON csv_configurations(length(effective), effective)")
                return _validate_csv_trace(paths, database, data_roots)
    except (OSError, sqlite3.Error):
        return {"contract_version": "CSV_PERSISTENCE_VALIDATION_V1", "coverage": "CSV_ADMISSION_AND_REQUIRED_SINK_EVIDENCE",
                "status": "INCOMPLETE", "issues": ["validator_workspace_unavailable"],
                "segment_count": len(paths), "record_count": 0, "admission_summary_count": 0,
                "data_integrity_status": "NOT_EVALUATED", "checked_csv_rows": 0, "row_bytes_status": "NOT_EVALUATED",
                "output_content_status": "NOT_EVALUATED", "destination_status": "NOT_EVALUATED",
                "configuration_status": "NOT_EVALUATED"}
