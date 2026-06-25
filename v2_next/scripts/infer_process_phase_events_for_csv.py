from __future__ import annotations

import argparse
import csv
import sys
from hashlib import sha256
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from backend import config
from backend.FacilityData.changeover_candidate_resolution_fact import (
    CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
    PROCESS_PHASE_EVENT_FACT_COLUMNS,
    infer_changeover_candidate_resolution_facts,
    infer_process_phase_event_facts,
)


PROCESS_PHASE_EVENT_FACT_FLAG = "PROCESS_PHASE_EVENT_FACT_ENABLED"


class ProcessPhaseEventFactDisabledError(RuntimeError):
    pass


def source_file_id_for_path(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def process_phase_event_fact_enabled() -> bool:
    return bool(getattr(config, PROCESS_PHASE_EVENT_FACT_FLAG, False))


def infer_process_phase_events_from_csv(
    input_path: Path,
    resolution_output_path: Path,
    event_output_path: Path,
    *,
    enabled: Optional[bool] = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    effective_enabled = process_phase_event_fact_enabled() if enabled is None else enabled
    if not effective_enabled:
        raise ProcessPhaseEventFactDisabledError(
            f"{PROCESS_PHASE_EVENT_FACT_FLAG}=false; process phase event fact generation is disabled."
        )

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    source_file_id = source_file_id_for_path(input_path)
    resolution_facts = infer_changeover_candidate_resolution_facts(rows, source_file_id=source_file_id)
    event_facts = infer_process_phase_event_facts(rows, source_file_id=source_file_id)
    resolution_output_path.parent.mkdir(parents=True, exist_ok=True)
    event_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolution_output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS)
        writer.writeheader()
        writer.writerows(resolution_facts)
    with event_output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROCESS_PHASE_EVENT_FACT_COLUMNS)
        writer.writeheader()
        writer.writerows(event_facts)
    return resolution_facts, event_facts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create post-hoc v2.4 process phase event facts without mutating source CSV rows."
    )
    parser.add_argument("--input", type=Path, required=True, help="Factory_Integrated_Log_v2*.csv input")
    parser.add_argument(
        "--resolution-output",
        type=Path,
        required=True,
        help="changeover_candidate_resolution_fact CSV output",
    )
    parser.add_argument("--event-output", type=Path, required=True, help="process_phase_event_fact CSV output")
    args = parser.parse_args()
    try:
        resolution_facts, event_facts = infer_process_phase_events_from_csv(
            args.input,
            args.resolution_output,
            args.event_output,
        )
    except ProcessPhaseEventFactDisabledError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"changeover_candidate_resolution_fact_rows={len(resolution_facts)}")
    print(f"process_phase_event_fact_rows={len(event_facts)}")
    print(f"resolution_output={args.resolution_output}")
    print(f"event_output={args.event_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
