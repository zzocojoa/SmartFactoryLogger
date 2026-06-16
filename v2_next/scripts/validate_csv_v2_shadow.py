from __future__ import annotations

import argparse
import csv
import json
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


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows[0], rows[1:]


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


def validate(v1_path: Path, v2_path: Path, metadata_path: Path) -> int:
    failures: list[str] = []
    warnings: list[str] = []

    v1_header, v1_rows = read_csv(v1_path)
    v2_header, v2_rows = read_csv(v2_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))

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
    print(f"v1_file={v1_path}")
    print(f"v2_file={v2_path}")
    print(f"metadata_file={metadata_path}")
    print(f"v1_rows={len(v1_rows)}")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v1/v2 CSV shadow logging outputs.")
    parser.add_argument("--v1", required=True, type=Path, help="Factory_Integrated_Log_*.csv")
    parser.add_argument("--v2", required=True, type=Path, help="Factory_Integrated_Log_v2_*.csv")
    parser.add_argument(
        "--metadata",
        required=True,
        type=Path,
        help="Factory_Integrated_Log_v2_*.metadata.json",
    )
    args = parser.parse_args()
    return validate(args.v1, args.v2, args.metadata)


if __name__ == "__main__":
    raise SystemExit(main())
