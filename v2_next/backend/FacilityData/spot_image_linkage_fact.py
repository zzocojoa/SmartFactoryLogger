from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


SPOT_IMAGE_LINKAGE_SCHEMA_VERSION = "1.0.0"
SPOT_IMAGE_LINKAGE_RULE_VERSION = "spot-image-linkage-posthoc-v1"
SPOT_IMAGE_LINKAGE_FACT_FILENAME = "spot_image_linkage_fact.csv"
SPOT_IMAGE_LINKAGE_REPORT_FILENAME = "spot_image_linkage_report.json"

SPOT_IMAGE_LINKAGE_FACT_COLUMNS = [
    "spot_image_linkage_schema_version",
    "linkage_rule_version",
    "source_file_id",
    "source_csv_sha256",
    "source_csv_row_number",
    "sample_seq",
    "timestamp_utc",
    "spot_observation_key",
    "linkage_status",
    "unmatched_reason",
    "match_count",
    "matched_spot_image_capture_id",
    "matched_spot_image_path",
    "matched_spot_image_sha256",
    "matched_spot_image_link_status",
    "matched_spot_image_link_age_ms",
    "image_fact_row_number",
    "realtime_spot_image_capture_id_nearest",
    "realtime_pointer_status",
]

SOURCE_CSV_REQUIRED_COLUMNS = [
    "sample_seq",
    "timestamp_utc",
    "spot_observation_key",
    "spot_image_capture_id_nearest",
]

SPOT_IMAGE_FACT_LINKAGE_REQUIRED_COLUMNS = [
    "spot_image_capture_id",
    "spot_image_path",
    "spot_image_sha256",
    "spot_image_link_status",
    "spot_image_link_age_ms",
    "spot_image_linked_observation_key",
]

LINKAGE_STATUSES = {
    "matched",
    "no_observation_key",
    "no_image_fact",
    "ambiguous",
    "invalid_source_row",
}

REALTIME_POINTER_STATUSES = {
    "same_as_posthoc",
    "blank",
    "different",
    "not_applicable",
}


def infer_spot_image_linkage_facts(
    source_rows: Sequence[Mapping[str, object]],
    image_fact_rows: Sequence[Mapping[str, object]],
    *,
    source_csv_sha256: str,
) -> list[dict[str, str]]:
    _require_columns(source_rows, SOURCE_CSV_REQUIRED_COLUMNS, "source CSV")
    _require_columns(image_fact_rows, SPOT_IMAGE_FACT_LINKAGE_REQUIRED_COLUMNS, "spot_image_fact")

    source_file_id = f"sha256:{source_csv_sha256}"
    image_rows_by_observation_key: dict[str, list[tuple[int, Mapping[str, object]]]] = defaultdict(list)
    for row_number, row in enumerate(image_fact_rows, start=2):
        observation_key = _text(row, "spot_image_linked_observation_key")
        if observation_key:
            image_rows_by_observation_key[observation_key].append((row_number, row))

    facts: list[dict[str, str]] = []
    for source_row_number, source_row in enumerate(source_rows, start=2):
        observation_key = _text(source_row, "spot_observation_key")
        realtime_capture_id = _text(source_row, "spot_image_capture_id_nearest")
        matches = image_rows_by_observation_key.get(observation_key, []) if observation_key else []

        fact = {
            "spot_image_linkage_schema_version": SPOT_IMAGE_LINKAGE_SCHEMA_VERSION,
            "linkage_rule_version": SPOT_IMAGE_LINKAGE_RULE_VERSION,
            "source_file_id": source_file_id,
            "source_csv_sha256": source_csv_sha256,
            "source_csv_row_number": str(source_row_number),
            "sample_seq": _text(source_row, "sample_seq"),
            "timestamp_utc": _text(source_row, "timestamp_utc"),
            "spot_observation_key": observation_key,
            "linkage_status": "",
            "unmatched_reason": "",
            "match_count": str(len(matches)),
            "matched_spot_image_capture_id": "",
            "matched_spot_image_path": "",
            "matched_spot_image_sha256": "",
            "matched_spot_image_link_status": "",
            "matched_spot_image_link_age_ms": "",
            "image_fact_row_number": "",
            "realtime_spot_image_capture_id_nearest": realtime_capture_id,
            "realtime_pointer_status": "not_applicable",
        }

        if not fact["sample_seq"] or not fact["timestamp_utc"]:
            fact["linkage_status"] = "invalid_source_row"
            fact["unmatched_reason"] = "source_row_missing_sample_seq_or_timestamp_utc"
        elif not observation_key:
            fact["linkage_status"] = "no_observation_key"
            fact["unmatched_reason"] = "spot_observation_key_blank"
        elif not matches:
            fact["linkage_status"] = "no_image_fact"
            fact["unmatched_reason"] = "no_matching_spot_image_fact"
        elif len(matches) > 1:
            fact["linkage_status"] = "ambiguous"
            fact["unmatched_reason"] = "multiple_spot_image_facts_for_observation_key"
        else:
            image_fact_row_number, image_fact = matches[0]
            matched_capture_id = _text(image_fact, "spot_image_capture_id")
            fact["linkage_status"] = "matched"
            fact["matched_spot_image_capture_id"] = matched_capture_id
            fact["matched_spot_image_path"] = _normalized_relative_path(_text(image_fact, "spot_image_path"))
            fact["matched_spot_image_sha256"] = _text(image_fact, "spot_image_sha256")
            fact["matched_spot_image_link_status"] = _text(image_fact, "spot_image_link_status")
            fact["matched_spot_image_link_age_ms"] = _text(image_fact, "spot_image_link_age_ms")
            fact["image_fact_row_number"] = str(image_fact_row_number)
            if not realtime_capture_id:
                fact["realtime_pointer_status"] = "blank"
            elif realtime_capture_id == matched_capture_id:
                fact["realtime_pointer_status"] = "same_as_posthoc"
            else:
                fact["realtime_pointer_status"] = "different"

        facts.append(fact)
    return facts


def write_spot_image_linkage_fact(
    fact_path: Path,
    facts: Sequence[Mapping[str, str]],
) -> None:
    fact_path.parent.mkdir(parents=True, exist_ok=True)
    with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SPOT_IMAGE_LINKAGE_FACT_COLUMNS)
        writer.writeheader()
        writer.writerows(facts)


def write_spot_image_linkage_artifacts(
    *,
    source_csv_path: Path,
    spot_image_fact_path: Path,
    fact_output_path: Path,
    report_output_path: Path,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    source_rows = _read_csv_dicts(source_csv_path)
    image_fact_rows = _read_csv_dicts(spot_image_fact_path)
    source_csv_sha = _file_sha256(source_csv_path)
    facts = infer_spot_image_linkage_facts(
        source_rows,
        image_fact_rows,
        source_csv_sha256=source_csv_sha,
    )
    write_spot_image_linkage_fact(fact_output_path, facts)
    report = build_spot_image_linkage_report(
        source_csv_path=source_csv_path,
        spot_image_fact_path=spot_image_fact_path,
        linkage_fact_path=fact_output_path,
        facts=facts,
    )
    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    report_output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return facts, report


def build_spot_image_linkage_report(
    *,
    source_csv_path: Path,
    spot_image_fact_path: Path,
    linkage_fact_path: Path,
    facts: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    status_counts = Counter(str(row.get("linkage_status") or "") for row in facts)
    pointer_counts = Counter(str(row.get("realtime_pointer_status") or "") for row in facts)
    source_row_count = _csv_row_count(source_csv_path)
    image_fact_row_count = _csv_row_count(spot_image_fact_path)
    fact_row_count, linkage_fact_sha = _fact_file_stats(linkage_fact_path)
    report: dict[str, Any] = {
        "schema_version": SPOT_IMAGE_LINKAGE_SCHEMA_VERSION,
        "rule_version": SPOT_IMAGE_LINKAGE_RULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifact_kind": "spot_image_linkage_report",
        "source_csv": {
            "file": source_csv_path.name,
            "sha256": _file_sha256(source_csv_path),
            "row_count": source_row_count,
        },
        "spot_image_fact": {
            "file": spot_image_fact_path.name,
            "sha256": _file_sha256(spot_image_fact_path),
            "row_count": image_fact_row_count,
        },
        "linkage_fact": {
            "file": linkage_fact_path.name,
            "sha256": linkage_fact_sha,
            "row_count": fact_row_count,
        },
        "counts": {
            "total_rows": len(facts),
            "matched": status_counts.get("matched", 0),
            "no_observation_key": status_counts.get("no_observation_key", 0),
            "no_image_fact": status_counts.get("no_image_fact", 0),
            "ambiguous": status_counts.get("ambiguous", 0),
            "invalid_source_row": status_counts.get("invalid_source_row", 0),
        },
        "realtime_pointer_comparison": {
            "same_as_posthoc": pointer_counts.get("same_as_posthoc", 0),
            "blank": pointer_counts.get("blank", 0),
            "different": pointer_counts.get("different", 0),
            "not_applicable": pointer_counts.get("not_applicable", 0),
        },
    }
    report["redaction"] = _redaction_flags(report)
    return report


def build_spot_image_linkage_fact_manifest(
    *,
    fact_path: Path,
    report_path: Path,
    source_csv_path: Path,
    spot_image_fact_path: Path,
) -> dict[str, Any]:
    row_count, fact_sha = _fact_file_stats(fact_path)
    report_sha = _file_sha256(report_path) if report_path.exists() else None
    source_csv_sha = _file_sha256(source_csv_path)
    spot_image_fact_sha = _file_sha256(spot_image_fact_path) if spot_image_fact_path.exists() else None
    return {
        "fact_kind": "spot_image_linkage_fact",
        "schema_version": SPOT_IMAGE_LINKAGE_SCHEMA_VERSION,
        "rule_version": SPOT_IMAGE_LINKAGE_RULE_VERSION,
        "fact_path": str(fact_path),
        "report_path": str(report_path),
        "required_columns": list(SPOT_IMAGE_LINKAGE_FACT_COLUMNS),
        "row_count": row_count,
        "sha256": fact_sha,
        "report_sha256": report_sha,
        "source_csv_sha256": source_csv_sha,
        "source_file_id": f"sha256:{source_csv_sha}",
        "spot_image_fact_sha256": spot_image_fact_sha,
    }


def validate_spot_image_linkage_outputs(
    *,
    source_csv_path: Path,
    spot_image_fact_path: Path,
    linkage_fact_path: Path,
    linkage_report_path: Path,
) -> tuple[list[str], dict[str, str]]:
    summary = _new_validation_summary(linkage_fact_path, linkage_report_path)
    failures: list[str] = []
    source_sha = _file_sha256(source_csv_path)
    image_fact_sha = _file_sha256(spot_image_fact_path)

    try:
        source_header, source_rows = _read_csv(source_csv_path)
        image_header, image_rows = _read_csv(spot_image_fact_path)
        fact_header, fact_rows = _read_csv(linkage_fact_path)
    except OSError as exc:
        return [f"spot_image_linkage artifact read failed: {exc.__class__.__name__}"], summary

    summary["spot_image_linkage_fact_actual_row_count"] = str(len(fact_rows))
    summary["spot_image_linkage_fact_actual_sha256"] = _file_sha256(linkage_fact_path)
    summary["spot_image_linkage_source_csv_sha256_match"] = "true"
    summary["spot_image_linkage_spot_image_fact_sha256_match"] = "true"

    source_missing = [column for column in SOURCE_CSV_REQUIRED_COLUMNS if column not in source_header]
    image_missing = [column for column in SPOT_IMAGE_FACT_LINKAGE_REQUIRED_COLUMNS if column not in image_header]
    fact_missing = [column for column in SPOT_IMAGE_LINKAGE_FACT_COLUMNS if column not in fact_header]
    if source_missing:
        failures.append("source CSV header missing columns: " + ", ".join(source_missing))
    if image_missing:
        failures.append("spot_image_fact header missing columns: " + ", ".join(image_missing))
    if fact_missing:
        failures.append("spot_image_linkage_fact header missing columns: " + ", ".join(fact_missing))
    if failures:
        return failures, summary

    for label, header, rows in (
        ("source CSV", source_header, source_rows),
        ("spot_image_fact", image_header, image_rows),
        ("spot_image_linkage_fact", fact_header, fact_rows),
    ):
        for row_number, row in enumerate(rows, start=2):
            if len(row) != len(header):
                failures.append(f"{label} row {row_number} has {len(row)} columns, expected {len(header)}")
    if failures:
        return failures, summary

    row_count_match = len(fact_rows) == len(source_rows)
    summary["spot_image_linkage_fact_row_count_match"] = _bool_text(row_count_match)
    if not row_count_match:
        failures.append(
            f"spot_image_linkage_fact rows={len(fact_rows)}, expected source CSV rows={len(source_rows)}"
        )

    image_rows_by_key: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for row_number, image_row in enumerate(_rows_as_dicts(image_header, image_rows), start=2):
        key = image_row["spot_image_linked_observation_key"].strip()
        if key:
            image_rows_by_key[key].append((row_number, image_row))

    source_dicts = _rows_as_dicts(source_header, source_rows)
    fact_dicts = _rows_as_dicts(fact_header, fact_rows)
    status_counts: Counter[str] = Counter()
    pointer_counts: Counter[str] = Counter()
    for offset, (source_row, fact_row) in enumerate(zip(source_dicts, fact_dicts), start=2):
        failures.extend(
            _validate_linkage_row(
                source_row=source_row,
                fact_row=fact_row,
                source_csv_row_number=offset,
                source_sha=source_sha,
                image_rows_by_key=image_rows_by_key,
            )
        )
        status_counts[fact_row["linkage_status"]] += 1
        pointer_counts[fact_row["realtime_pointer_status"]] += 1

    summary["spot_image_linkage_matched_rows"] = str(status_counts.get("matched", 0))
    summary["spot_image_linkage_ambiguous_rows"] = str(status_counts.get("ambiguous", 0))

    report_failures, report_summary = _validate_linkage_report(
        report_path=linkage_report_path,
        source_csv_path=source_csv_path,
        spot_image_fact_path=spot_image_fact_path,
        linkage_fact_path=linkage_fact_path,
        source_row_count=len(source_rows),
        image_fact_row_count=len(image_rows),
        fact_row_count=len(fact_rows),
        status_counts=status_counts,
        pointer_counts=pointer_counts,
    )
    summary.update(report_summary)
    failures.extend(report_failures)
    return failures, summary


def _validate_linkage_row(
    *,
    source_row: Mapping[str, str],
    fact_row: Mapping[str, str],
    source_csv_row_number: int,
    source_sha: str,
    image_rows_by_key: Mapping[str, list[tuple[int, Mapping[str, str]]]],
) -> list[str]:
    failures: list[str] = []
    row_label = f"spot_image_linkage_fact row {source_csv_row_number}"
    source_file_id = f"sha256:{source_sha}"
    expected_key = source_row["spot_observation_key"].strip()
    matches = image_rows_by_key.get(expected_key, []) if expected_key else []

    expected_values = {
        "spot_image_linkage_schema_version": SPOT_IMAGE_LINKAGE_SCHEMA_VERSION,
        "linkage_rule_version": SPOT_IMAGE_LINKAGE_RULE_VERSION,
        "source_file_id": source_file_id,
        "source_csv_sha256": source_sha,
        "source_csv_row_number": str(source_csv_row_number),
        "sample_seq": source_row["sample_seq"].strip(),
        "timestamp_utc": source_row["timestamp_utc"].strip(),
        "spot_observation_key": expected_key,
        "realtime_spot_image_capture_id_nearest": source_row["spot_image_capture_id_nearest"].strip(),
    }
    for column, expected in expected_values.items():
        if fact_row[column].strip() != expected:
            failures.append(f"{row_label} {column} does not match source CSV")

    status = fact_row["linkage_status"].strip()
    if status not in LINKAGE_STATUSES:
        failures.append(f"{row_label} linkage_status={status!r} is invalid")
        return failures
    pointer_status = fact_row["realtime_pointer_status"].strip()
    if pointer_status not in REALTIME_POINTER_STATUSES:
        failures.append(f"{row_label} realtime_pointer_status={pointer_status!r} is invalid")

    try:
        match_count = int(fact_row["match_count"].strip())
    except ValueError:
        failures.append(f"{row_label} match_count must be an integer")
        match_count = -1
    if match_count != len(matches):
        failures.append(f"{row_label} match_count does not match spot_image_fact")

    if status == "matched":
        if len(matches) != 1:
            failures.append(f"{row_label} matched status requires exactly one spot_image_fact row")
        else:
            image_row_number, image_row = matches[0]
            expected_image_values = {
                "matched_spot_image_capture_id": image_row["spot_image_capture_id"].strip(),
                "matched_spot_image_path": _normalized_relative_path(image_row["spot_image_path"].strip()),
                "matched_spot_image_sha256": image_row["spot_image_sha256"].strip(),
                "matched_spot_image_link_status": image_row["spot_image_link_status"].strip(),
                "matched_spot_image_link_age_ms": image_row["spot_image_link_age_ms"].strip(),
                "image_fact_row_number": str(image_row_number),
            }
            for column, expected in expected_image_values.items():
                if fact_row[column].strip() != expected:
                    failures.append(f"{row_label} {column} does not match spot_image_fact")
            image_path = fact_row["matched_spot_image_path"].strip()
            if _is_unsafe_relative_path(image_path):
                failures.append(f"{row_label} matched_spot_image_path must be a safe relative path")
            if not _is_sha256_text(fact_row["matched_spot_image_sha256"].strip()):
                failures.append(f"{row_label} matched_spot_image_sha256 must be lowercase SHA-256")
            realtime_id = expected_values["realtime_spot_image_capture_id_nearest"]
            expected_pointer = "blank"
            if realtime_id:
                expected_pointer = (
                    "same_as_posthoc"
                    if realtime_id == fact_row["matched_spot_image_capture_id"].strip()
                    else "different"
                )
            if pointer_status != expected_pointer:
                failures.append(f"{row_label} realtime_pointer_status must be {expected_pointer!r}")
    else:
        for column in (
            "matched_spot_image_capture_id",
            "matched_spot_image_path",
            "matched_spot_image_sha256",
            "matched_spot_image_link_status",
            "matched_spot_image_link_age_ms",
            "image_fact_row_number",
        ):
            if fact_row[column].strip():
                failures.append(f"{row_label} {column} must be blank when linkage_status={status!r}")
        if pointer_status != "not_applicable":
            failures.append(f"{row_label} realtime_pointer_status must be 'not_applicable'")
        if not fact_row["unmatched_reason"].strip():
            failures.append(f"{row_label} unmatched_reason must be populated")

    return failures


def _validate_linkage_report(
    *,
    report_path: Path,
    source_csv_path: Path,
    spot_image_fact_path: Path,
    linkage_fact_path: Path,
    source_row_count: int,
    image_fact_row_count: int,
    fact_row_count: int,
    status_counts: Counter[str],
    pointer_counts: Counter[str],
) -> tuple[list[str], dict[str, str]]:
    summary = {
        "spot_image_linkage_report_file": report_path.name,
        "spot_image_linkage_report_sha256_match": "unknown",
        "spot_image_linkage_report_redaction_passed": "unknown",
    }
    if not report_path.exists():
        return ["spot_image_linkage_report path does not exist"], summary
    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ["spot_image_linkage_report JSON could not be read"], summary
    if not isinstance(report, dict):
        return ["spot_image_linkage_report must be a JSON object"], summary

    failures: list[str] = []
    if report.get("schema_version") != SPOT_IMAGE_LINKAGE_SCHEMA_VERSION:
        failures.append("spot_image_linkage_report.schema_version mismatch")
    if report.get("rule_version") != SPOT_IMAGE_LINKAGE_RULE_VERSION:
        failures.append("spot_image_linkage_report.rule_version mismatch")
    _expect_report_item(
        failures,
        report,
        ("source_csv", "file"),
        source_csv_path.name,
    )
    _expect_report_item(failures, report, ("source_csv", "sha256"), _file_sha256(source_csv_path))
    _expect_report_item(failures, report, ("source_csv", "row_count"), source_row_count)
    _expect_report_item(failures, report, ("spot_image_fact", "file"), spot_image_fact_path.name)
    _expect_report_item(failures, report, ("spot_image_fact", "sha256"), _file_sha256(spot_image_fact_path))
    _expect_report_item(failures, report, ("spot_image_fact", "row_count"), image_fact_row_count)
    _expect_report_item(failures, report, ("linkage_fact", "file"), linkage_fact_path.name)
    _expect_report_item(failures, report, ("linkage_fact", "sha256"), _file_sha256(linkage_fact_path))
    _expect_report_item(failures, report, ("linkage_fact", "row_count"), fact_row_count)

    for status in ("matched", "no_observation_key", "no_image_fact", "ambiguous", "invalid_source_row"):
        _expect_report_item(failures, report, ("counts", status), status_counts.get(status, 0))
    _expect_report_item(failures, report, ("counts", "total_rows"), fact_row_count)
    for status in ("same_as_posthoc", "blank", "different", "not_applicable"):
        _expect_report_item(
            failures,
            report,
            ("realtime_pointer_comparison", status),
            pointer_counts.get(status, 0),
        )

    report_sha_matches = _file_sha256(linkage_fact_path) == _nested_text(report, ("linkage_fact", "sha256"))
    summary["spot_image_linkage_report_sha256_match"] = _bool_text(report_sha_matches)
    if not report_sha_matches:
        failures.append("spot_image_linkage_report.linkage_fact.sha256 does not match linkage fact")

    redaction = _redaction_flags(report)
    declared_redaction = report.get("redaction")
    if declared_redaction != redaction:
        failures.append("spot_image_linkage_report.redaction does not match computed redaction flags")
    redaction_passed = not any(redaction.values())
    summary["spot_image_linkage_report_redaction_passed"] = _bool_text(redaction_passed)
    if not redaction_passed:
        failures.append("spot_image_linkage_report contains non-sanitized values")
    return failures, summary


def _expect_report_item(
    failures: list[str],
    report: Mapping[str, Any],
    path: tuple[str, str],
    expected: object,
) -> None:
    value: object = report
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            failures.append("spot_image_linkage_report missing " + ".".join(path))
            return
        value = value[key]
    if value != expected:
        failures.append("spot_image_linkage_report." + ".".join(path) + " mismatch")


def _new_validation_summary(linkage_fact_path: Path, linkage_report_path: Path) -> dict[str, str]:
    return {
        "spot_image_linkage_fact_override_file": linkage_fact_path.name,
        "spot_image_linkage_report_override_file": linkage_report_path.name,
        "spot_image_linkage_fact_actual_row_count": "unknown",
        "spot_image_linkage_fact_row_count_match": "unknown",
        "spot_image_linkage_fact_actual_sha256": "unknown",
        "spot_image_linkage_fact_sha256_match": "unknown",
        "spot_image_linkage_source_csv_sha256_match": "unknown",
        "spot_image_linkage_spot_image_fact_sha256_match": "unknown",
        "spot_image_linkage_report_sha256_match": "unknown",
        "spot_image_linkage_report_redaction_passed": "unknown",
        "spot_image_linkage_matched_rows": "unknown",
        "spot_image_linkage_ambiguous_rows": "unknown",
    }


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        return header, [row for row in reader if row]


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _rows_as_dicts(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[dict[str, str]]:
    return [dict(zip(header, row, strict=False)) for row in rows]


def _require_columns(
    rows: Sequence[Mapping[str, object]],
    required_columns: Sequence[str],
    label: str,
) -> None:
    if not rows:
        return
    available = set(rows[0])
    missing = [column for column in required_columns if column not in available]
    if missing:
        raise ValueError(f"{label} missing columns: {', '.join(missing)}")


def _fact_file_stats(fact_path: Path) -> tuple[int, str | None]:
    if not fact_path.exists() or fact_path.stat().st_size == 0:
        return 0, None
    return _csv_row_count(fact_path), _file_sha256(fact_path)


def _csv_row_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for row in reader if row)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _text(row: Mapping[str, object], key: str) -> str:
    return str(row.get(key) or "").strip()


def _normalized_relative_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def _is_sha256_text(value: str) -> bool:
    text = value.strip()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _is_unsafe_relative_path(value: str) -> bool:
    if not value:
        return True
    path = Path(value)
    if path.is_absolute():
        return True
    return any(part in {"", ".", ".."} for part in path.parts)


def _json_string_values(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _json_string_values(item)
        return
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            yield from _json_string_values(item)


def _redaction_flags(payload: Mapping[str, Any]) -> dict[str, bool]:
    values = list(_json_string_values(payload))
    return {
        "raw_image_included": any(
            value.startswith("data:image/") or value.startswith("/9j/") or value.startswith("iVBOR")
            for value in values
        ),
        "raw_camera_url_included": any("://" in value for value in values),
        "secret_included": any(
            marker in value.lower()
            for value in values
            for marker in ("password=", "password:", "token=", "token:", "secret=", "secret:")
        ),
        "full_internal_path_included": any(
            len(value) >= 3
            and (
                (value[1:3] in (":\\", ":/") and value[0].isalpha())
                or value.startswith("\\\\")
            )
            for value in values
        ),
    }


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _nested_text(payload: Mapping[str, Any], path: tuple[str, str]) -> str:
    value: object = payload
    for key in path:
        if not isinstance(value, Mapping):
            return ""
        value = value.get(key)
    return str(value or "")
