from __future__ import annotations

import argparse
import csv
import sys
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from backend.FacilityData.process_state import PROCESS_SEGMENT_FACT_COLUMNS, infer_process_segment_facts


def source_file_id_for_path(path: Path) -> str:
    digest = sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def infer_process_segments_from_csv(input_path: Path, output_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    facts = infer_process_segment_facts(rows, source_file_id=source_file_id_for_path(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROCESS_SEGMENT_FACT_COLUMNS)
        writer.writeheader()
        writer.writerows(facts)
    return facts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a separate post-hoc process_segment_fact CSV from realtime Factory CSV v2.3 rows."
    )
    parser.add_argument("--input", type=Path, required=True, help="Factory_Integrated_Log_v2*.csv input")
    parser.add_argument("--output", type=Path, required=True, help="process_segment_fact CSV output")
    args = parser.parse_args()
    facts = infer_process_segments_from_csv(args.input, args.output)
    print(f"process_segment_fact_rows={len(facts)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
