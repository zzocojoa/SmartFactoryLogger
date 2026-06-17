from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from pathlib import Path
from statistics import mean


REQUIRED_V1_COLUMNS = [
    "Date",
    "Time",
    "Temperature",
    "MainPress",
    "BilletLength",
    "Temp_F",
    "Temp_B",
    "Count",
    "Speed",
    "EndPos",
    "Mold1",
    "Mold2",
    "Mold3",
    "Mold4",
    "Mold5",
    "Mold6",
    "Billet_Temp",
    "At_Pre",
    "At_Temp",
    "DIE_ID",
    "Billet_CycleID",
]

REQUIRED_V2_COLUMNS = [
    "schema_version",
    "sample_seq",
    "timestamp_local",
    "timestamp_utc",
    "ingest_timestamp",
    "captured_at_extruder",
    "captured_at_ls",
    "captured_at_spot",
    *REQUIRED_V1_COLUMNS,
    "MainRamPosition_D0010",
    "ContainerPosition_D0012",
]

REQUIRED_METADATA_FIELDS = {
    "EndPos": "hmi_confirmed_setting_value",
    "MainRamPosition_D0010": "hmi_confirmed_actual_position",
    "ContainerPosition_D0012": "hmi_confirmed_actual_position",
    "ButtLength_HMI_B1880": "hmi_confirmed_separate_field",
}

V1_NAME_RE = re.compile(r"^Factory_Integrated_Log_(\d{8}_\d{6})\.csv$")
V2_NAME_RE = re.compile(r"^Factory_Integrated_Log_v2_(\d{8}_\d{6})\.csv$")
METADATA_NAME_RE = re.compile(r"^Factory_Integrated_Log_v2_(\d{8}_\d{6})\.metadata\.json$")


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows[0], rows[1:]


def _timestamp_suffix(path: Path, pattern: re.Pattern[str]) -> str | None:
    match = pattern.match(path.name)
    if not match:
        return None
    return match.group(1)


def _expand_glob(pattern: str, name_pattern: re.Pattern[str]) -> list[Path]:
    paths = [Path(path) for path in glob.glob(pattern)]
    return sorted(
        [path for path in paths if path.is_file() and _timestamp_suffix(path, name_pattern)],
        key=lambda path: (_timestamp_suffix(path, name_pattern) or "", path.name),
    )


def _index_by_suffix(paths: list[Path], name_pattern: re.Pattern[str]) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in paths:
        suffix = _timestamp_suffix(path, name_pattern)
        if suffix is None:
            continue
        if suffix in indexed:
            raise ValueError(f"duplicate timestamp suffix {suffix}: {indexed[suffix]} and {path}")
        indexed[suffix] = path
    return indexed


def find_metadata_item(metadata: dict, field_name: str) -> dict | None:
    for item in metadata.get("sensor_metadata", []):
        if item.get("field_name") == field_name or item.get("column_name") == field_name:
            return item
    return None


def parse_float_values(rows: list[list[str]], header: list[str], column: str) -> list[float]:
    if column not in header:
        return []
    index = header.index(column)
    values: list[float] = []
    for row in rows:
        if index >= len(row):
            continue
        raw = row[index].strip()
        if not raw:
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def validate_sample_seq(rows: list[list[str]], header: list[str]) -> tuple[bool, str]:
    if "sample_seq" not in header:
        return False, "missing sample_seq"
    index = header.index("sample_seq")
    sequences: list[int] = []
    for row in rows:
        if index >= len(row):
            return False, "row shorter than sample_seq column"
        try:
            sequences.append(int(row[index]))
        except ValueError:
            return False, f"invalid sample_seq value: {row[index]}"
    if not sequences:
        return False, "no v2 data rows"
    monotonic = all(curr > prev for prev, curr in zip(sequences, sequences[1:]))
    if not monotonic:
        return False, "sample_seq is not strictly increasing"
    return True, f"{sequences[0]}..{sequences[-1]}"


def position_summary(rows: list[list[str]], header: list[str], column: str) -> str:
    values = parse_float_values(rows, header, column)
    if not values:
        return "no populated values"
    return (
        f"count={len(values)}, min={min(values):.3f}, max={max(values):.3f}, "
        f"mean={mean(values):.3f}"
    )


def validate(v1_path: Path | None, v2_path: Path, metadata_path: Path) -> int:
    failures: list[str] = []
    warnings: list[str] = []

    v1_header: list[str] = []
    v1_rows: list[list[str]] = []
    if v1_path is not None:
        v1_header, v1_rows = read_csv(v1_path)
    v2_header, v2_rows = read_csv(v2_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))

    if v1_path is not None:
        if v1_header != REQUIRED_V1_COLUMNS:
            failures.append("v1 header does not match canonical 21-column contract")
        if len(v1_header) != 21:
            failures.append(f"v1 column count is {len(v1_header)}, expected 21")

    missing_v2 = [column for column in REQUIRED_V2_COLUMNS if column not in v2_header]
    if missing_v2:
        failures.append(f"v2 header missing columns: {', '.join(missing_v2)}")

    v2_schema = metadata.get("schema_metadata", {}).get("schema_version")
    if v2_schema != "2.1.0":
        failures.append(f"metadata schema_version is {v2_schema!r}, expected '2.1.0'")

    row_delta: int | str = "v1_not_provided"
    if v1_path is not None:
        row_delta = len(v2_rows) - len(v1_rows)
        if row_delta != 0:
            warnings.append(f"row count differs: v1={len(v1_rows)} v2={len(v2_rows)} delta={row_delta}")

    seq_ok, seq_detail = validate_sample_seq(v2_rows, v2_header)
    if not seq_ok:
        failures.append(seq_detail)

    for field_name, expected_status in REQUIRED_METADATA_FIELDS.items():
        item = find_metadata_item(metadata, field_name)
        if item is None:
            failures.append(f"metadata missing sensor field: {field_name}")
            continue
        actual_status = item.get("mapping_status")
        if actual_status != expected_status:
            failures.append(
                f"metadata {field_name}.mapping_status={actual_status!r}, expected {expected_status!r}"
            )

    for column in ("MainRamPosition_D0010", "ContainerPosition_D0012"):
        values = parse_float_values(v2_rows, v2_header, column)
        if not values:
            warnings.append(f"{column} has no populated values. Check position_read_enabled.")

    print("CSV v2 shadow validation")
    print(f"v1_file={v1_path if v1_path is not None else 'not provided'}")
    print(f"v2_file={v2_path}")
    print(f"metadata_file={metadata_path}")
    print(f"v1_rows={len(v1_rows) if v1_path is not None else 'not checked'}")
    print(f"v2_rows={len(v2_rows)}")
    print(f"row_delta={row_delta}")
    print(f"sample_seq={seq_detail}")
    print(f"MainRamPosition_D0010={position_summary(v2_rows, v2_header, 'MainRamPosition_D0010')}")
    print(f"ContainerPosition_D0012={position_summary(v2_rows, v2_header, 'ContainerPosition_D0012')}")

    if warnings:
        print("\nWARNINGS")
        for warning in warnings:
            print(f"- {warning}")
    if failures:
        print("\nFAILURES")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nPASS")
    return 0


def validate_many(
    v1_paths: list[Path],
    v2_paths: list[Path],
    metadata_paths: list[Path],
    require_v1: bool = False,
) -> int:
    failures: list[str] = []
    try:
        v1_by_suffix = _index_by_suffix(v1_paths, V1_NAME_RE) if v1_paths else {}
        v2_by_suffix = _index_by_suffix(v2_paths, V2_NAME_RE)
        metadata_by_suffix = _index_by_suffix(metadata_paths, METADATA_NAME_RE)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1

    if not v2_by_suffix:
        failures.append("no v2 CSV files matched")
    if not metadata_by_suffix:
        failures.append("no v2 metadata files matched")
    if require_v1 and not v1_by_suffix:
        failures.append("no v1 CSV files matched")

    for suffix in sorted(v2_by_suffix):
        if suffix not in metadata_by_suffix:
            failures.append(f"missing metadata for v2 suffix {suffix}")
        if require_v1 and suffix not in v1_by_suffix:
            failures.append(f"missing v1 CSV for v2 suffix {suffix}")

    for suffix in sorted(metadata_by_suffix):
        if suffix not in v2_by_suffix:
            failures.append(f"metadata has no matching v2 CSV for suffix {suffix}")

    if failures:
        print("CSV v2 shadow multi-file validation")
        print(f"v1_files={len(v1_paths)}")
        print(f"v2_files={len(v2_paths)}")
        print(f"metadata_files={len(metadata_paths)}")
        print("\nFAILURES")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("CSV v2 shadow multi-file validation")
    print(f"v1_files={len(v1_paths)}")
    print(f"v2_files={len(v2_paths)}")
    print(f"metadata_files={len(metadata_paths)}")

    status = 0
    for suffix in sorted(v2_by_suffix):
        print(f"\nPAIR {suffix}")
        pair_status = validate(
            v1_by_suffix.get(suffix) if v1_paths else None,
            v2_by_suffix[suffix],
            metadata_by_suffix[suffix],
        )
        if pair_status != 0:
            status = pair_status
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v1/v2 CSV shadow logging outputs.")
    parser.add_argument(
        "--v1",
        type=Path,
        help="v1 Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv file",
    )
    parser.add_argument(
        "--v2",
        type=Path,
        help="v2 Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv file",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        help="Factory_Integrated_Log_v2_*.metadata.json",
    )
    parser.add_argument(
        "--v1-glob",
        help="Glob for v1 Factory_Integrated_Log_YYYYMMDD_HHMMSS.csv files",
    )
    parser.add_argument(
        "--v2-glob",
        help="Glob for v2 Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.csv files",
    )
    parser.add_argument(
        "--metadata-glob",
        help="Glob for v2 Factory_Integrated_Log_v2_YYYYMMDD_HHMMSS.metadata.json files",
    )
    args = parser.parse_args()
    if args.v2_glob or args.metadata_glob or args.v1_glob:
        if not args.v2_glob or not args.metadata_glob:
            parser.error("--v2-glob and --metadata-glob are required for multi-file validation")
        return validate_many(
            _expand_glob(args.v1_glob, V1_NAME_RE) if args.v1_glob else [],
            _expand_glob(args.v2_glob, V2_NAME_RE),
            _expand_glob(args.metadata_glob, METADATA_NAME_RE),
            require_v1=args.v1_glob is not None,
        )

    if args.v2 is None or args.metadata is None:
        parser.error("--v2 and --metadata are required for single-file validation")
    return validate(args.v1, args.v2, args.metadata)


if __name__ == "__main__":
    raise SystemExit(main())
