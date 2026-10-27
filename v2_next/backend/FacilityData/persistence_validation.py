"""Independent, read-only validation of CSV persistence evidence."""
import json
from pathlib import Path
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


def validate_csv_persistence_trace(paths: Sequence[Path]) -> dict[str, Any]:
    """Read bounded segments without treating their presence as full data proof."""
    issues: set[str] = set()
    records = 0
    summaries = 0
    unsupported = False
    boundaries: dict[str, list[int]] = {"producer_start": [], "producer_stop": []}
    summary_bounds: tuple[int, int] | None = None
    identities: dict[str, str] = {}
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
        for line in lines[1:]:
            try:
                record = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
                if not isinstance(record, dict):
                    raise ValueError("Invalid trace record")
            except (ValueError, RecursionError):
                issues.add("invalid_trace_record")
                continue
            records += 1
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
                issues.update(_admission_total_issues(record))
                if all(type(record.get(key)) is int for key in ("after_producer_seq", "last_producer_seq")):
                    summary_bounds = record["after_producer_seq"], record["last_producer_seq"]
    if not paths:
        issues.add("missing_trace")
    if paths and not unsupported and summaries == 0:
        issues.add("missing_admission_summary")
    if summaries > 1:
        issues.add("multiple_admission_summaries")
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
            "coverage": "TRACE_PARSE_ADMISSION_TOTALS_AND_PRODUCER_BOUNDARIES",
            "status": "INCOMPLETE" if incomplete else "NOT_EVALUATED",
            "issues": sorted(issues), "segment_count": len(paths), "record_count": records,
            "admission_summary_count": summaries, "data_integrity_status": "NOT_EVALUATED"}
