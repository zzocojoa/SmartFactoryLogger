from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Mapping, Sequence


CHANGEOVER_CANDIDATE_RESOLUTION_SCHEMA_VERSION = "1.0.0"
CHANGEOVER_CANDIDATE_RESOLUTION_RULE_VERSION = "changeover-candidate-resolution-v1"
PROCESS_PHASE_EVENT_SCHEMA_VERSION = "1.0.0"
PROCESS_PHASE_EVENT_RULE_VERSION = "process-phase-event-v1"
_PRE_CHANGEOVER_EVIDENCE_WINDOW = timedelta(seconds=300)
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
    "production_stabilizing": "production_stabilizing",
    "unknown": "unknown",
}

_PHASE_CONFIRMATION_PRECEDENCE = (
    "production_stabilizing",
    "setup_alignment_candidate",
    "die_change_candidate",
    "changeover_candidate",
    "setup_candidate",
    "pre_changeover_hold_candidate",
)

@dataclass(frozen=True)
class _CandidateRows:
    candidate_id: str
    rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class _PhaseConfirmation:
    confirmed_phase: str
    reason: str


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
        confirmation = _confirm_candidate_phase(phase, candidate.rows, rows)
        outcome = "confirmed" if confirmation.confirmed_phase != "unknown" else "rejected"
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
                "resolution_reason": confirmation.reason,
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
        confirmation = _confirm_candidate_phase(phase_candidate, candidate.rows, rows)
        confirmed_phase = confirmation.confirmed_phase
        event_id = _event_id(source_file_id, candidate.candidate_id, confirmed_phase)
        expectedness = _confirmed_expectedness(candidate.rows) if confirmed_phase != "unknown" else "indeterminate"
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
                "confirmation_reason": confirmation.reason,
                "confirmation_confidence": "0.650" if confirmed_phase != "unknown" else "0.350",
            }
        )
    return facts


def _group_candidate_rows(rows: Sequence[Mapping[str, object]]) -> list[_CandidateRows]:
    rows_by_candidate: dict[str, list[Mapping[str, object]]] = {}
    candidate_order: list[str] = []
    for row in rows:
        candidate_id = _text(row, "changeover_candidate_id")
        if not candidate_id:
            continue
        if candidate_id not in rows_by_candidate:
            rows_by_candidate[candidate_id] = []
            candidate_order.append(candidate_id)
        rows_by_candidate[candidate_id].append(row)
    return [
        _CandidateRows(candidate_id=candidate_id, rows=tuple(rows_by_candidate[candidate_id]))
        for candidate_id in candidate_order
    ]

def _confirm_candidate_phase(
    phase_candidate: str,
    candidate_rows: Sequence[Mapping[str, object]],
    all_rows: Sequence[Mapping[str, object]],
) -> _PhaseConfirmation:
    representative_phase = _representative_candidate_phase(phase_candidate, candidate_rows)
    confirmed_phase = _CANDIDATE_TO_CONFIRMED.get(representative_phase, "unknown")
    if representative_phase != "pre_changeover_hold_candidate":
        return _PhaseConfirmation(
            confirmed_phase=confirmed_phase,
            reason=f"{representative_phase}_mapped_posthoc",
        )
    evidence = _pre_changeover_future_evidence(candidate_rows, all_rows)
    if evidence:
        return _PhaseConfirmation(
            confirmed_phase=confirmed_phase,
            reason=f"pre_changeover_hold_candidate_confirmed_by_{evidence}",
        )
    return _PhaseConfirmation(
        confirmed_phase="unknown",
        reason="pre_changeover_hold_candidate_without_future_evidence",
    )


def _representative_candidate_phase(
    fallback_phase: str,
    candidate_rows: Sequence[Mapping[str, object]],
) -> str:
    phases = {_text(row, "process_phase_candidate") for row in candidate_rows}
    for phase in _PHASE_CONFIRMATION_PRECEDENCE:
        if phase in phases:
            return phase
    return fallback_phase or "unknown"


def _pre_changeover_future_evidence(
    candidate_rows: Sequence[Mapping[str, object]],
    all_rows: Sequence[Mapping[str, object]],
) -> str:
    if not candidate_rows:
        return ""
    start = candidate_rows[0]
    end = candidate_rows[-1]
    end_seq = _to_int(_text(end, "sample_seq"))
    end_time = _parse_timestamp(end)
    if end_seq is None or end_time is None:
        return ""
    start_count = _to_int(_text(start, "Count"))
    start_product = _text(start, "Product_No_operator")
    start_mold = _text(start, "Mold_No_operator")
    for row in all_rows:
        row_seq = _to_int(_text(row, "sample_seq"))
        if row_seq is None or row_seq <= end_seq:
            continue
        row_time = _parse_timestamp(row)
        if row_time is None:
            continue
        if row_time - end_time > _PRE_CHANGEOVER_EVIDENCE_WINDOW:
            break
        count = _to_int(_text(row, "Count"))
        if start_count is not None and start_count > 2 and count == 0:
            return "future_count_reset_to_0"
        product = _text(row, "Product_No_operator")
        mold = _text(row, "Mold_No_operator")
        if (
            start_product
            and start_mold
            and product
            and mold
            and (product, mold) != (start_product, start_mold)
        ):
            return "future_operator_context_changed"
        phase = _text(row, "process_phase_candidate")
        if phase in {"die_change_candidate", "changeover_candidate"}:
            return "future_die_change_marker"
    return ""


def _parse_timestamp(row: Mapping[str, object]) -> datetime | None:
    raw = _text(row, "timestamp_utc") or _text(row, "timestamp_local")
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


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
