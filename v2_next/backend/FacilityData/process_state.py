from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Sequence

PROCESS_SEGMENT_FACT_SCHEMA_VERSION = "1.0.0"
PROCESS_STATE_INFERENCE_RULE_VERSION = "process-segment-inference-v1"
RUN_SEGMENTATION_RULE_VERSION = "run-segmentation-inferred-v1"

PROCESS_SEGMENT_FACT_COLUMNS = [
    "process_segment_fact_schema_version",
    "process_segment_id",
    "source_file_id",
    "logger_service_instance_id",
    "sample_seq_start",
    "sample_seq_end",
    "source_row_start",
    "source_row_end",
    "segment_start_at",
    "segment_end_at",
    "sample_count",
    "extruder_process_state_online_basis",
    "extruder_process_state_inferred",
    "inference_confidence",
    "inference_rule_version",
    "inference_reason",
    "run_segment_id_inferred",
    "run_segmentation_confidence",
    "run_segmentation_rule_version",
    "Product_No_operator",
    "Mold_No_operator",
]

ONLINE_PROCESS_STATES = {
    "extruding",
    "stopped",
    "idle_candidate",
    "changeover_candidate",
    "unknown",
}

POSTHOC_PROCESS_STATES = {
    "extruding",
    "billet_change_pause",
    "idle",
    "changeover",
    "unknown",
}

_TRUE_TEXT = {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class _ProcessRow:
    row_number: int
    logger_service_instance_id: str
    sample_seq: int | None
    timestamp: str
    online_state: str
    context: tuple[str, str] | None


@dataclass(frozen=True)
class _ProcessSegment:
    rows: tuple[_ProcessRow, ...]
    logger_service_instance_id: str
    online_state: str
    context: tuple[str, str] | None

    @property
    def start(self) -> _ProcessRow:
        return self.rows[0]

    @property
    def end(self) -> _ProcessRow:
        return self.rows[-1]


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _optional_int(text: str) -> int | None:
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _operator_context(row: Mapping[str, object]) -> tuple[str, str] | None:
    product_no = _text(row, "Product_No_operator")
    mold_no = _text(row, "Mold_No_operator")
    valid_text = _text(row, "operator_metadata_valid").lower()
    valid = valid_text in _TRUE_TEXT if valid_text else bool(product_no and mold_no)
    if not valid or not product_no or not mold_no:
        return None
    return product_no, mold_no


def _normalise_row(row: Mapping[str, object], row_number: int) -> _ProcessRow:
    online_state = _text(row, "extruder_process_state_online") or "unknown"
    if online_state not in ONLINE_PROCESS_STATES:
        online_state = "unknown"
    timestamp = _text(row, "timestamp_utc") or _text(row, "timestamp_local") or _text(row, "Time")
    return _ProcessRow(
        row_number=row_number,
        logger_service_instance_id=_text(row, "logger_service_instance_id"),
        sample_seq=_optional_int(_text(row, "sample_seq")),
        timestamp=timestamp,
        online_state=online_state,
        context=_operator_context(row),
    )


def _same_segment(left: _ProcessRow, right: _ProcessRow) -> bool:
    return (
        left.logger_service_instance_id == right.logger_service_instance_id
        and left.online_state == right.online_state
        and left.context == right.context
    )


def _group_segments(rows: Sequence[_ProcessRow]) -> list[_ProcessSegment]:
    if not rows:
        return []
    segments: list[_ProcessSegment] = []
    current: list[_ProcessRow] = [rows[0]]
    for row in rows[1:]:
        if _same_segment(current[-1], row):
            current.append(row)
            continue
        segments.append(
            _ProcessSegment(
                rows=tuple(current),
                logger_service_instance_id=current[0].logger_service_instance_id,
                online_state=current[0].online_state,
                context=current[0].context,
            )
        )
        current = [row]
    segments.append(
        _ProcessSegment(
            rows=tuple(current),
            logger_service_instance_id=current[0].logger_service_instance_id,
            online_state=current[0].online_state,
            context=current[0].context,
        )
    )
    return segments


def _segment_id(source_file_id: str, segment: _ProcessSegment, state: str) -> str:
    key = "|".join(
        [
            source_file_id,
            segment.logger_service_instance_id,
            str(segment.start.sample_seq or ""),
            str(segment.end.sample_seq or ""),
            str(segment.start.row_number),
            str(segment.end.row_number),
            state,
        ]
    )
    return "ps_" + sha256(key.encode("utf-8")).hexdigest()[:16]


def _run_segment_id(source_file_id: str, logger_service_instance_id: str, context: tuple[str, str] | None) -> str:
    if context is None:
        return ""
    product_no, mold_no = context
    key = "|".join([source_file_id, logger_service_instance_id, product_no, mold_no])
    return "run_" + sha256(key.encode("utf-8")).hexdigest()[:16]


def _infer_state(segments: Sequence[_ProcessSegment], index: int) -> tuple[str, float, str, tuple[str, str] | None]:
    segment = segments[index]
    online_state = segment.online_state
    if online_state == "extruding":
        return "extruding", 1.0, "online_state_extruding", segment.context
    if online_state == "idle_candidate":
        return "idle", 0.65, "online_idle_candidate_promoted_posthoc", segment.context
    if online_state == "changeover_candidate":
        return "changeover", 0.65, "online_changeover_candidate_promoted_posthoc", segment.context
    if online_state == "stopped":
        previous = segments[index - 1] if index > 0 else None
        following = segments[index + 1] if index + 1 < len(segments) else None
        if (
            previous is not None
            and following is not None
            and previous.online_state == "extruding"
            and following.online_state == "extruding"
            and previous.context is not None
            and previous.context == following.context
            and (segment.context is None or segment.context == previous.context)
        ):
            return (
                "billet_change_pause",
                0.7,
                "stopped_between_extruding_segments_with_same_inferred_run_context",
                previous.context,
            )
        return "unknown", 0.35, "stopped_without_same_run_future_context", segment.context
    return "unknown", 0.2, "online_state_unknown_or_invalid", segment.context


def _fmt_confidence(value: float) -> str:
    return f"{max(0.0, min(1.0, value)):.3f}"


def infer_process_segment_facts(
    rows: Sequence[Mapping[str, object]],
    *,
    source_file_id: str,
) -> list[dict[str, str]]:
    """Infer post-hoc process segment facts from realtime v2.3 CSV rows.

    The output is a separate fact table. It intentionally uses future context and must not
    be written back into realtime append-only CSV rows.
    """
    normalised = [_normalise_row(row, index) for index, row in enumerate(rows, start=2)]
    segments = _group_segments(normalised)
    facts: list[dict[str, str]] = []
    for index, segment in enumerate(segments):
        inferred_state, confidence, reason, run_context = _infer_state(segments, index)
        if inferred_state not in POSTHOC_PROCESS_STATES:
            inferred_state = "unknown"
            confidence = 0.0
            reason = "invalid_inferred_state_suppressed"
        product_no, mold_no = run_context or ("", "")
        run_segment_id = _run_segment_id(source_file_id, segment.logger_service_instance_id, run_context)
        run_confidence = "0.650" if run_segment_id else "0.000"
        facts.append(
            {
                "process_segment_fact_schema_version": PROCESS_SEGMENT_FACT_SCHEMA_VERSION,
                "process_segment_id": _segment_id(source_file_id, segment, inferred_state),
                "source_file_id": source_file_id,
                "logger_service_instance_id": segment.logger_service_instance_id,
                "sample_seq_start": str(segment.start.sample_seq or ""),
                "sample_seq_end": str(segment.end.sample_seq or ""),
                "source_row_start": str(segment.start.row_number),
                "source_row_end": str(segment.end.row_number),
                "segment_start_at": segment.start.timestamp,
                "segment_end_at": segment.end.timestamp,
                "sample_count": str(len(segment.rows)),
                "extruder_process_state_online_basis": segment.online_state,
                "extruder_process_state_inferred": inferred_state,
                "inference_confidence": _fmt_confidence(confidence),
                "inference_rule_version": PROCESS_STATE_INFERENCE_RULE_VERSION,
                "inference_reason": reason,
                "run_segment_id_inferred": run_segment_id,
                "run_segmentation_confidence": run_confidence,
                "run_segmentation_rule_version": RUN_SEGMENTATION_RULE_VERSION,
                "Product_No_operator": product_no,
                "Mold_No_operator": mold_no,
            }
        )
    return facts
