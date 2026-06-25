from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Sequence


CHANGEOVER_CANDIDATE_RESOLUTION_SCHEMA_VERSION = "1.0.0"
CHANGEOVER_CANDIDATE_RESOLUTION_RULE_VERSION = "changeover-candidate-resolution-v1"
PROCESS_PHASE_EVENT_SCHEMA_VERSION = "1.0.0"
PROCESS_PHASE_EVENT_RULE_VERSION = "process-phase-event-v1"

CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS = [
    "candidate_resolution_schema_version",
    "changeover_candidate_id",
    "confirmation_outcome",
    "resolved_at",
    "resolution_rule_version",
    "source_file_id",
    "logger_service_instance_id",
    "sample_seq_start",
    "sample_seq_end",
    "merged_into_changeover_event_id",
    "split_event_count",
    "split_changeover_event_ids",
    "resolution_reason",
    "resolution_confidence",
]

PROCESS_PHASE_EVENT_FACT_COLUMNS = [
    "process_phase_event_schema_version",
    "changeover_event_id",
    "source_changeover_candidate_id",
    "source_file_id",
    "logger_service_instance_id",
    "sample_seq_start",
    "sample_seq_end",
    "phase_start_at",
    "phase_end_at",
    "process_phase_confirmed",
    "temperature_expectedness_confirmed",
    "phase_confirmation_state",
    "confirmation_rule_version",
    "confirmation_reason",
    "confirmation_confidence",
]

_CANDIDATE_TO_CONFIRMED = {
    "setup_candidate": "setup",
    "setup_alignment_candidate": "setup_alignment",
    "pre_changeover_hold_candidate": "pre_changeover_hold",
    "die_change_candidate": "die_change",
    "changeover_candidate": "changeover",
    "production_stable": "production_stable",
    "idle_candidate": "idle",
    "unknown": "unknown",
}


@dataclass(frozen=True)
class _CandidateRows:
    candidate_id: str
    rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class _CandidateSegment:
    base_candidate_id: str
    rows: tuple[Mapping[str, object], ...]


def infer_changeover_candidate_resolution_facts(
    rows: Sequence[Mapping[str, object]],
    *,
    source_file_id: str,
) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    for candidate in _group_candidate_rows(rows):
        start = candidate.rows[0]
        end = candidate.rows[-1]
        phase = _text(start, "process_phase_candidate") or "unknown"
        outcome = "confirmed" if phase != "unknown" else "rejected"
        confidence = "0.650" if outcome == "confirmed" else "0.350"
        facts.append(
            {
                "candidate_resolution_schema_version": CHANGEOVER_CANDIDATE_RESOLUTION_SCHEMA_VERSION,
                "changeover_candidate_id": candidate.candidate_id,
                "confirmation_outcome": outcome,
                "resolved_at": _text(end, "timestamp_utc") or _text(end, "timestamp_local"),
                "resolution_rule_version": CHANGEOVER_CANDIDATE_RESOLUTION_RULE_VERSION,
                "source_file_id": source_file_id,
                "logger_service_instance_id": _text(start, "logger_service_instance_id"),
                "sample_seq_start": _text(start, "sample_seq"),
                "sample_seq_end": _text(end, "sample_seq"),
                "merged_into_changeover_event_id": "",
                "split_event_count": "0",
                "split_changeover_event_ids": "[]",
                "resolution_reason": f"realtime_{phase}_terminal",
                "resolution_confidence": confidence,
            }
        )
    return facts


def infer_process_phase_event_facts(
    rows: Sequence[Mapping[str, object]],
    *,
    source_file_id: str,
) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    for candidate in _group_candidate_rows(rows):
        start = candidate.rows[0]
        end = candidate.rows[-1]
        phase_candidate = _text(start, "process_phase_candidate") or "unknown"
        confirmed_phase = _CANDIDATE_TO_CONFIRMED.get(phase_candidate, "unknown")
        event_id = _event_id(source_file_id, candidate.candidate_id, confirmed_phase)
        expectedness = _confirmed_expectedness(candidate.rows)
        facts.append(
            {
                "process_phase_event_schema_version": PROCESS_PHASE_EVENT_SCHEMA_VERSION,
                "changeover_event_id": event_id,
                "source_changeover_candidate_id": candidate.candidate_id,
                "source_file_id": source_file_id,
                "logger_service_instance_id": _text(start, "logger_service_instance_id"),
                "sample_seq_start": _text(start, "sample_seq"),
                "sample_seq_end": _text(end, "sample_seq"),
                "phase_start_at": _text(start, "timestamp_utc") or _text(start, "timestamp_local"),
                "phase_end_at": _text(end, "timestamp_utc") or _text(end, "timestamp_local"),
                "process_phase_confirmed": confirmed_phase,
                "temperature_expectedness_confirmed": expectedness,
                "phase_confirmation_state": "posthoc_confirmed" if confirmed_phase != "unknown" else "posthoc_rejected",
                "confirmation_rule_version": PROCESS_PHASE_EVENT_RULE_VERSION,
                "confirmation_reason": f"{phase_candidate}_mapped_posthoc",
                "confirmation_confidence": "0.650" if confirmed_phase != "unknown" else "0.350",
            }
        )
    return facts


def _group_candidate_rows(rows: Sequence[Mapping[str, object]]) -> list[_CandidateRows]:
    segments = _contiguous_candidate_segments(rows)
    duplicate_counts = Counter(segment.base_candidate_id for segment in segments)
    occurrence_counts: Counter[str] = Counter()
    grouped: list[_CandidateRows] = []
    for segment in segments:
        occurrence_counts[segment.base_candidate_id] += 1
        grouped.append(
            _CandidateRows(
                candidate_id=_occurrence_candidate_id(
                    segment,
                    duplicate_counts[segment.base_candidate_id],
                    occurrence_counts[segment.base_candidate_id],
                ),
                rows=segment.rows,
            )
        )
    return grouped


def _contiguous_candidate_segments(rows: Sequence[Mapping[str, object]]) -> list[_CandidateSegment]:
    segments: list[_CandidateSegment] = []
    current_id = ""
    current_rows: list[Mapping[str, object]] = []

    for row in rows:
        candidate_id = _text(row, "changeover_candidate_id")
        if not candidate_id:
            _append_segment(segments, current_id, current_rows)
            current_id = ""
            current_rows = []
            continue
        if current_rows and (candidate_id != current_id or not _sample_seq_is_contiguous(current_rows[-1], row)):
            _append_segment(segments, current_id, current_rows)
            current_rows = []
        current_id = candidate_id
        current_rows.append(row)
    _append_segment(segments, current_id, current_rows)
    return segments


def _append_segment(
    segments: list[_CandidateSegment],
    candidate_id: str,
    rows: list[Mapping[str, object]],
) -> None:
    if candidate_id and rows:
        segments.append(_CandidateSegment(base_candidate_id=candidate_id, rows=tuple(rows)))


def _occurrence_candidate_id(segment: _CandidateSegment, duplicate_count: int, occurrence_index: int) -> str:
    if duplicate_count <= 1:
        return segment.base_candidate_id
    start_seq = _text(segment.rows[0], "sample_seq") or f"occ_{occurrence_index}"
    return f"{segment.base_candidate_id}__seq_{start_seq}"


def _sample_seq_is_contiguous(previous: Mapping[str, object], current: Mapping[str, object]) -> bool:
    previous_seq = _to_int(_text(previous, "sample_seq"))
    current_seq = _to_int(_text(current, "sample_seq"))
    if previous_seq is None or current_seq is None:
        return True
    return current_seq == previous_seq + 1


def _confirmed_expectedness(rows: Sequence[Mapping[str, object]]) -> str:
    values = {_text(row, "temperature_expectedness_candidate") for row in rows}
    if "unexpected_candidate" in values:
        return "unexpected"
    if "expected_candidate" in values:
        return "expected"
    return "indeterminate"


def _event_id(source_file_id: str, candidate_id: str, phase: str) -> str:
    key = "|".join([source_file_id, candidate_id, phase])
    return "phase_" + sha256(key.encode("utf-8")).hexdigest()[:16]


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    text = str(value).strip()
    if key.endswith("_ids") and not text:
        return json.dumps([])
    return text


def _to_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
