from __future__ import annotations

import argparse
import csv
import hashlib
import glob
import json
import math
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from backend.FacilityData.changeover_candidate_resolution_fact import (
    CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
    CHANGEOVER_CANDIDATE_RESOLUTION_RULE_VERSION,
    CHANGEOVER_CANDIDATE_RESOLUTION_SCHEMA_VERSION,
    PROCESS_PHASE_EVENT_FACT_COLUMNS,
    PROCESS_PHASE_EVENT_RULE_VERSION,
    PROCESS_PHASE_EVENT_SCHEMA_VERSION,
)
from backend.FacilityData.spot_image_linkage_fact import (
    SPOT_IMAGE_LINKAGE_FACT_COLUMNS,
    SPOT_IMAGE_LINKAGE_RULE_VERSION,
    SPOT_IMAGE_LINKAGE_SCHEMA_VERSION,
    validate_spot_image_linkage_outputs,
)
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_COLUMNS,
    SPOT_OBSERVATION_FACT_FILENAME,
    SPOT_OBSERVATION_FACT_SCHEMA_VERSION,
    build_spot_observation_fact_manifest,
)


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

CSV_SCHEMA_VERSION_V2_1 = "2.1.0"
CSV_SCHEMA_VERSION_V2_2 = "2.2.0"
CSV_SCHEMA_VERSION_V2_3 = "2.3.0"
CSV_SCHEMA_VERSION_V2_4 = "2.4.0"
SUPPORTED_CSV_SCHEMA_VERSIONS = {
    CSV_SCHEMA_VERSION_V2_1,
    CSV_SCHEMA_VERSION_V2_2,
    CSV_SCHEMA_VERSION_V2_3,
    CSV_SCHEMA_VERSION_V2_4,
}
SPOT_IMAGE_FACT_REQUIRED_COLUMNS = [
    "spot_image_capture_id",
    "spot_image_path",
    "spot_image_sha256",
    "spot_image_size_bytes",
    "spot_image_mime",
    "spot_image_link_age_ms",
    "spot_image_link_status",
    "spot_image_linked_observation_key",
]
SPOT_IMAGE_LINK_STATUSES = {
    "fresh",
    "stale",
    "missing_observation",
    "unlinked_observation",
    "unknown_age",
    "clock_anomaly",
}
HEX_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
EXPECTED_SPOT_INVALID_SENTINEL_VALUES = {"6553.4", "6553.5"}
EXPECTED_SPOT_INVALID_SENTINEL_MEANINGS = {
    "6553.4": "under_range",
    "6553.5": "over_range",
}
EXPECTED_SPOT_INVALID_SENTINEL_DEVICE_STATUS_CODES = {
    "6553.4": "temperature_under_range",
    "6553.5": "temperature_over_range",
}
EXPECTED_SPOT_SENTINEL_PROVENANCE = {
    "document_title": "SPOT+ Family REST API User Guide",
    "document_issue": "2",
    "repository_relative_path": "docs/reference/ametek_land_spot.pdf",
    "document_sha256": "c8d315fafd796075545558afcca894e0f1855fc3ba6ebc2f875e95ca1d39bf22",
    "page_numbers": [7],
    "verification_method": "local_pdf_text_extraction_pypdf",
}
FALLBACK_ROW_TIME_FRESHNESS_THRESHOLD_MS = 9000.0
CURRENT_SERVER_PROMOTION_SPOT_CONFIGURATION_PROFILE = {
    "spot_model_info": "SPOT+ AL",
    "spot_app_mode": "App1: AL E",
    "spot_range_min_c": 200.0,
    "spot_range_max_c": 900.0,
    "spot_analog_4ma_c": 200.0,
    "spot_analog_20ma_c": 800.0,
    "low_signal_alarm_enabled": False,
    "low_signal_threshold_pc": 2.0,
    "low_signal_comparator": "lt",
    "low_signal_comparator_verified": False,
    "peak_picker_enabled": False,
    "window_obscuration_pc": 12.0,
    "focus_mm": 6071,
    "config_operator_verified": True,
}
REQUIRED_V2_BASE_COLUMNS = [
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

OPERATOR_METADATA_V2_COLUMNS = [
    "Product_No_operator",
    "Mold_No_operator",
    "operator_metadata_valid",
    "operator_metadata_missing_fields",
    "operator_metadata_updated_at",
]

SPOT_SHADOW_ENUM_VALUES = {
    "extruder_process_state_online": {
        "extruding",
        "stopped",
        "idle_candidate",
        "changeover_candidate",
        "unknown",
    },
    "spot_target_state_observed_shadow": {"present", "absent", "unknown"},
    "spot_target_state_observed_source": {"verified_device_code", "valid_temperature", "unknown"},
    "label_validation_state": {"shadow", "validated", "deprecated"},
    "temperature_status_shadow": {
        "ok",
        "no_target",
        "startup_pending",
        "source_error",
        "invalid_value",
        "stale",
        "unknown_missing",
    },
    "spot_poll_status": {
        "success",
        "timeout",
        "connection_error",
        "http_error",
        "config_missing",
        "not_attempted",
    },
    "spot_raw_validity": {
        "valid_temperature",
        "verified_no_target",
        "empty_body",
        "parse_error",
        "invalid_sentinel",
        "out_of_range",
        "not_received",
        "not_evaluated",
    },
    "spot_cache_status": {
        "fresh",
        "reused",
        "expired",
        "empty",
        "invalidated",
        "available_not_used",
    },
    "spot_source_freshness": {"fresh", "stale", "unknown"},
    "temperature_value_origin": {"current_observation", "cached_observation", "none"},
}

SPOT_TEMPERATURE_SHADOW_COLUMNS = [
    "logger_service_instance_id",
    "logger_service_started_at",
    "extruder_process_state_online",
    "process_state_online_rule_version",
    "spot_target_state_observed_shadow",
    "spot_target_state_observed_source",
    "label_validation_state",
    "temperature_status_shadow",
    "temperature_status_rule_version",
    "spot_poll_status",
    "spot_raw_validity",
    "spot_cache_status",
    "spot_source_freshness",
    "temperature_value_origin",
    "cache_fallback_allowed",
    "spot_service_instance_id",
    "spot_service_started_at",
    "spot_poll_seq",
    "spot_observation_seq",
    "spot_temperature_observed_c",
    "spot_temperature_raw",
    "spot_temperature_raw_truncated",
    "spot_raw_payload_hash",
    "spot_raw_payload_encoding",
    "spot_http_status_code",
    "spot_device_status_code",
    "spot_error_code",
    "spot_poll_duration_ms",
    "spot_response_content_length",
    "spot_last_poll_started_at",
    "spot_last_poll_completed_at",
    "spot_last_response_at",
    "spot_last_valid_value_at",
    "spot_snapshot_age_ms",
    "spot_value_age_ms",
]

V2_4_OPERATIONAL_COLUMNS = [
    "temperature_output_status",
    "temperature_unavailable_reason",
    "temperature_expectedness_candidate",
    "temperature_under_range_cause_candidate",
    "temperature_cause_confidence",
    "temperature_cause_evidence_codes",
    "spot_effective_age_ms_at_row",
    "spot_effective_freshness_at_row",
    "spot_effective_value_age_ms_at_row",
    "spot_row_age_clock_status",
    "process_phase_candidate",
    "process_phase_rule_version",
    "phase_confirmation_state",
    "process_segment_id",
    "changeover_candidate_id",
    "spot_observation_key",
    "spot_image_capture_id_nearest",
    "spot_image_path_nearest",
    "spot_image_link_status_nearest",
    "spot_image_link_age_ms_nearest",
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
    *OPERATOR_METADATA_V2_COLUMNS,
    *REQUIRED_V1_COLUMNS,
    "MainRamPosition_D0010",
    "ContainerPosition_D0012",
]

REQUIRED_V2_COLUMNS_BY_SCHEMA = {
    CSV_SCHEMA_VERSION_V2_1: REQUIRED_V2_BASE_COLUMNS,
    CSV_SCHEMA_VERSION_V2_2: REQUIRED_V2_COLUMNS,
    CSV_SCHEMA_VERSION_V2_3: [*REQUIRED_V2_COLUMNS, *SPOT_TEMPERATURE_SHADOW_COLUMNS],
    CSV_SCHEMA_VERSION_V2_4: [*REQUIRED_V2_COLUMNS, *SPOT_TEMPERATURE_SHADOW_COLUMNS, *V2_4_OPERATIONAL_COLUMNS],
}

BASE_REQUIRED_METADATA_FIELDS = {
    "EndPos": "hmi_confirmed_setting_value",
    "MainRamPosition_D0010": "hmi_confirmed_actual_position",
    "ContainerPosition_D0012": "hmi_confirmed_actual_position",
    "ButtLength_HMI_B1880": "hmi_confirmed_separate_field",
}

OPERATOR_METADATA_FIELDS = {
    "product_no": "operator_entered_required",
    "operator_mold_no": "operator_entered_required",
}

REQUIRED_METADATA_FIELDS_BY_SCHEMA = {
    CSV_SCHEMA_VERSION_V2_1: BASE_REQUIRED_METADATA_FIELDS,
    CSV_SCHEMA_VERSION_V2_2: {
        **BASE_REQUIRED_METADATA_FIELDS,
        **OPERATOR_METADATA_FIELDS,
    },
    CSV_SCHEMA_VERSION_V2_3: {
        **BASE_REQUIRED_METADATA_FIELDS,
        **OPERATOR_METADATA_FIELDS,
    },
    CSV_SCHEMA_VERSION_V2_4: {
        **BASE_REQUIRED_METADATA_FIELDS,
        **OPERATOR_METADATA_FIELDS,
    },
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


def validate_shadow_enum_values(rows: list[list[str]], header: list[str]) -> list[str]:
    failures: list[str] = []
    for column, allowed in SPOT_SHADOW_ENUM_VALUES.items():
        if column not in header:
            continue
        index = header.index(column)
        for row_number, row in enumerate(rows, start=2):
            if index >= len(row):
                failures.append(f"row {row_number} shorter than {column} column")
                continue
            value = row[index].strip()
            if not value:
                continue
            if value not in allowed:
                failures.append(f"row {row_number} {column}={value!r} not in {sorted(allowed)!r}")
    return failures


def validate_spot_sequence_values(rows: list[list[str]], header: list[str]) -> list[str]:
    failures: list[str] = []
    if "spot_poll_seq" not in header or "spot_observation_seq" not in header:
        return failures
    poll_index = header.index("spot_poll_seq")
    observation_index = header.index("spot_observation_seq")
    for row_number, row in enumerate(rows, start=2):
        if poll_index >= len(row) or observation_index >= len(row):
            failures.append(f"row {row_number} shorter than spot sequence columns")
            continue
        raw_poll = row[poll_index].strip()
        raw_observation = row[observation_index].strip()
        if not raw_poll and not raw_observation:
            continue
        try:
            poll_seq = int(raw_poll)
            observation_seq = int(raw_observation)
        except ValueError:
            failures.append(f"row {row_number} has non-integer spot sequence values")
            continue
        if poll_seq < 0 or observation_seq < 0:
            failures.append(f"row {row_number} has negative spot sequence values")
        if observation_seq > poll_seq:
            failures.append(f"row {row_number} spot_observation_seq exceeds spot_poll_seq")
    return failures


def _parse_finite_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _parse_utc_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _metadata_row_time_freshness_threshold_ms(metadata: dict) -> float:
    shadow_metadata = metadata.get("spot_temperature_shadow_metadata")
    if isinstance(shadow_metadata, dict):
        threshold_sec = _parse_finite_float(shadow_metadata.get("poll_freshness_threshold_sec"))
        if threshold_sec is not None and threshold_sec >= 0:
            return threshold_sec * 1000.0
    return FALLBACK_ROW_TIME_FRESHNESS_THRESHOLD_MS


def _parse_json_string_list(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item)]


def validate_temperature_value_origin_invariants(rows: list[list[str]], header: list[str]) -> list[str]:
    required_columns = [
        "Temperature",
        "temperature_value_origin",
        "spot_temperature_observed_c",
        "spot_last_valid_value_at",
    ]
    missing_columns = [column for column in required_columns if column not in header]
    if missing_columns:
        return ["v2 header missing temperature origin invariant columns: " + ", ".join(missing_columns)]

    failures: list[str] = []
    temperature_index = header.index("Temperature")
    origin_index = header.index("temperature_value_origin")
    observed_index = header.index("spot_temperature_observed_c")
    last_valid_index = header.index("spot_last_valid_value_at")
    cache_index = header.index("spot_cache_status") if "spot_cache_status" in header else None
    freshness_index = header.index("spot_source_freshness") if "spot_source_freshness" in header else None
    output_status_index = header.index("temperature_output_status") if "temperature_output_status" in header else None
    raw_validity_index = header.index("spot_raw_validity") if "spot_raw_validity" in header else None
    row_freshness_index = (
        header.index("spot_effective_freshness_at_row")
        if "spot_effective_freshness_at_row" in header
        else None
    )

    for row_number, row in enumerate(rows, start=2):
        if max(temperature_index, origin_index, observed_index, last_valid_index) >= len(row):
            failures.append(f"row {row_number} shorter than temperature origin invariant columns")
            continue

        temperature = row[temperature_index].strip()
        origin = row[origin_index].strip()
        observed = row[observed_index].strip()
        last_valid_at = row[last_valid_index].strip()
        cache_status = row[cache_index].strip() if cache_index is not None and cache_index < len(row) else ""
        freshness = row[freshness_index].strip() if freshness_index is not None and freshness_index < len(row) else ""
        raw_validity = (
            row[raw_validity_index].strip()
            if raw_validity_index is not None and raw_validity_index < len(row)
            else ""
        )
        output_status = (
            row[output_status_index].strip()
            if output_status_index is not None and output_status_index < len(row)
            else ""
        )
        row_freshness = (
            row[row_freshness_index].strip()
            if row_freshness_index is not None and row_freshness_index < len(row)
            else ""
        )

        if not origin:
            continue

        if origin == "current_observation":
            temperature_value = _parse_finite_float(temperature)
            observed_value = _parse_finite_float(observed)
            if temperature_value is None:
                failures.append(f"row {row_number} current_observation requires finite Temperature")
            if observed_value is None:
                failures.append(f"row {row_number} current_observation requires finite spot_temperature_observed_c")
            if temperature_value is not None and observed_value is not None:
                if abs(temperature_value - observed_value) > 1e-6:
                    failures.append(
                        f"row {row_number} current_observation Temperature must equal spot_temperature_observed_c"
                    )
            if not last_valid_at:
                failures.append(f"row {row_number} current_observation requires spot_last_valid_value_at")
        elif origin == "cached_observation":
            if _parse_finite_float(temperature) is None:
                failures.append(f"row {row_number} cached_observation requires finite Temperature")
            if observed and _parse_finite_float(observed) is None:
                failures.append(f"row {row_number} populated spot_temperature_observed_c must be finite")
            if not last_valid_at:
                failures.append(f"row {row_number} cached_observation requires spot_last_valid_value_at")
        elif origin == "none":
            if temperature:
                failures.append(f"row {row_number} origin none requires blank Temperature")
            if observed:
                observed_value = _parse_finite_float(observed)
                if observed_value is None:
                    failures.append(f"row {row_number} populated spot_temperature_observed_c must be finite")
                elif not _origin_none_allows_populated_observed(
                    cache_status=cache_status,
                    freshness=freshness,
                    row_freshness=row_freshness,
                    output_status=output_status,
                    raw_validity=raw_validity,
                ):
                    failures.append(
                        f"row {row_number} origin none permits populated spot_temperature_observed_c "
                        "only for stale diagnostic rows"
                    )

    return failures


def _origin_none_allows_populated_observed(
    *,
    cache_status: str,
    freshness: str,
    row_freshness: str,
    output_status: str,
    raw_validity: str,
) -> bool:
    if output_status not in {"", "stale"}:
        return False
    if freshness != "stale" and row_freshness != "stale":
        return False
    if cache_status == "available_not_used":
        return True
    if cache_status == "expired" and raw_validity == "valid_temperature":
        return True
    return row_freshness == "stale" and cache_status == "fresh" and raw_validity == "valid_temperature"

def _parse_decimal_value(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _expected_device_status_for_sentinel_raw(raw_value: str) -> str | None:
    parsed = _parse_decimal_value(raw_value.strip())
    if parsed is None or not parsed.is_finite():
        return None
    for sentinel_value, device_status in EXPECTED_SPOT_INVALID_SENTINEL_DEVICE_STATUS_CODES.items():
        if parsed == Decimal(sentinel_value):
            return device_status
    return None


def validate_spot_invalid_sentinel_invariants(rows: list[list[str]], header: list[str]) -> list[str]:
    required_columns = [
        "Temperature",
        "spot_poll_status",
        "spot_raw_validity",
        "spot_temperature_raw",
        "spot_device_status_code",
        "spot_error_code",
        "cache_fallback_allowed",
        "temperature_status_shadow",
        "spot_target_state_observed_shadow",
        "temperature_value_origin",
    ]
    missing_columns = [column for column in required_columns if column not in header]
    if missing_columns:
        return ["v2 header missing invalid sentinel invariant columns: " + ", ".join(missing_columns)]

    indices = {column: header.index(column) for column in required_columns}
    source_freshness_index = header.index("spot_source_freshness") if "spot_source_freshness" in header else None
    cache_status_index = header.index("spot_cache_status") if "spot_cache_status" in header else None
    failures: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        if max(indices.values()) >= len(row):
            failures.append(f"row {row_number} shorter than invalid sentinel invariant columns")
            continue
        if row[indices["spot_raw_validity"]].strip() != "invalid_sentinel":
            continue

        raw_value = row[indices["spot_temperature_raw"]]
        expected_device_status = _expected_device_status_for_sentinel_raw(raw_value)
        if expected_device_status is None:
            failures.append(f"row {row_number} invalid_sentinel raw value is not documented 6553.4/6553.5 sentinel")
            continue

        source_freshness = (
            row[source_freshness_index].strip()
            if source_freshness_index is not None and source_freshness_index < len(row)
            else ""
        )
        cache_status = (
            row[cache_status_index].strip()
            if cache_status_index is not None and cache_status_index < len(row)
            else ""
        )
        if source_freshness == "stale":
            expected_temperature_status = "stale" if cache_status == "expired" else "unknown_missing"
        else:
            expected_temperature_status = "invalid_value"

        expected_values = {
            "spot_poll_status": "success",
            "spot_device_status_code": expected_device_status,
            "spot_error_code": "",
            "cache_fallback_allowed": "false",
            "temperature_status_shadow": expected_temperature_status,
            "spot_target_state_observed_shadow": "unknown",
            "temperature_value_origin": "none",
            "Temperature": "",
        }
        for column, expected in expected_values.items():
            actual = row[indices[column]].strip()
            comparable_actual = actual.lower() if column == "cache_fallback_allowed" else actual
            if comparable_actual != expected:
                failures.append(f"row {row_number} {column}={actual!r}, expected {expected!r}")
    return failures


V2_4_OPERATIONAL_ENUM_VALUES = {
    "temperature_output_status": {
        "valid",
        "under_range",
        "over_range",
        "stale",
        "source_error",
        "startup_pending",
        "unknown",
    },
    "temperature_unavailable_reason": {
        "under_range",
        "over_range",
        "stale_observation",
        "timeout",
        "connection_error",
        "http_error",
        "parse_error",
        "empty_body",
        "config_missing",
        "numeric_out_of_range",
        "not_attempted",
        "startup_pending",
        "unknown_freshness",
        "unknown",
    },
    "temperature_expectedness_candidate": {"expected_candidate", "unexpected_candidate", "unknown"},
    "temperature_under_range_cause_candidate": {
        "peak_picker_reset_candidate",
        "target_out_of_fov_candidate",
        "alignment_change_candidate",
        "low_signal_candidate",
        "below_measurement_range_candidate",
        "unknown",
    },
    "spot_effective_freshness_at_row": {"fresh", "stale", "unknown"},
    "spot_row_age_clock_status": {"ok", "clock_anomaly", "unknown"},
    "process_phase_candidate": {
        "production_stable",
        "setup_candidate",
        "pre_changeover_hold_candidate",
        "stopped_after_production_candidate",
        "possible_pre_changeover_hold",
        "die_change_candidate",
        "setup_alignment_candidate",
        "changeover_candidate",
        "production_stabilizing",
        "idle_candidate",
        "unknown",
    },
    "phase_confirmation_state": {"realtime_candidate", "unknown"},
    "spot_image_link_status_nearest": SPOT_IMAGE_LINK_STATUSES,
}


def validate_v2_4_operational_invariants(
    rows: list[list[str]],
    header: list[str],
    *,
    row_time_freshness_threshold_ms: float = FALLBACK_ROW_TIME_FRESHNESS_THRESHOLD_MS,
) -> list[str]:
    required_columns = [
        "timestamp_utc",
        "Temperature",
        "spot_poll_status",
        "spot_poll_seq",
        "spot_raw_validity",
        "spot_source_freshness",
        "spot_device_status_code",
        "spot_last_poll_completed_at",
        "spot_effective_freshness_at_row",
        "spot_row_age_clock_status",
        "temperature_status_shadow",
        "temperature_output_status",
        "temperature_unavailable_reason",
        "temperature_under_range_cause_candidate",
        "temperature_cause_confidence",
        "temperature_cause_evidence_codes",
        "process_phase_candidate",
        "spot_observation_key",
        "spot_image_capture_id_nearest",
        "spot_image_path_nearest",
        "spot_image_link_status_nearest",
        "spot_image_link_age_ms_nearest",
    ]
    missing_columns = [column for column in required_columns if column not in header]
    if missing_columns:
        return ["v2.4 header missing operational invariant columns: " + ", ".join(missing_columns)]

    failures: list[str] = []
    indices = {column: header.index(column) for column in required_columns}
    for column, allowed in V2_4_OPERATIONAL_ENUM_VALUES.items():
        if column not in header:
            failures.append(f"v2.4 header missing enum column: {column}")
            continue
        index = header.index(column)
        for row_number, row in enumerate(rows, start=2):
            if index >= len(row):
                failures.append(f"row {row_number} shorter than {column} column")
                continue
            value = row[index].strip()
            if value and value not in allowed:
                failures.append(f"row {row_number} {column}={value!r} not in {sorted(allowed)!r}")

    for row_number, row in enumerate(rows, start=2):
        if max(indices.values()) >= len(row):
            failures.append(f"row {row_number} shorter than v2.4 operational columns")
            continue
        temperature = row[indices["Temperature"]].strip()
        timestamp_utc = row[indices["timestamp_utc"]].strip()
        poll_status = row[indices["spot_poll_status"]].strip()
        raw_poll_seq = row[indices["spot_poll_seq"]].strip()
        raw_validity = row[indices["spot_raw_validity"]].strip()
        source_freshness = row[indices["spot_source_freshness"]].strip()
        device_status = row[indices["spot_device_status_code"]].strip()
        poll_completed_at = row[indices["spot_last_poll_completed_at"]].strip()
        row_freshness = row[indices["spot_effective_freshness_at_row"]].strip()
        clock_status = row[indices["spot_row_age_clock_status"]].strip()
        shadow_status = row[indices["temperature_status_shadow"]].strip()
        output_status = row[indices["temperature_output_status"]].strip()
        unavailable_reason = row[indices["temperature_unavailable_reason"]].strip()
        cause = row[indices["temperature_under_range_cause_candidate"]].strip()
        confidence = row[indices["temperature_cause_confidence"]].strip()
        evidence_codes = _parse_json_string_list(row[indices["temperature_cause_evidence_codes"]].strip())
        spot_observation_key = row[indices["spot_observation_key"]].strip()
        image_capture_id = row[indices["spot_image_capture_id_nearest"]].strip()
        image_path = row[indices["spot_image_path_nearest"]].strip()
        image_link_status = row[indices["spot_image_link_status_nearest"]].strip()
        image_link_age = row[indices["spot_image_link_age_ms_nearest"]].strip()

        if output_status and output_status != "valid" and temperature:
            failures.append(f"row {row_number} non-valid temperature_output_status requires blank Temperature")
        row_timestamp = _parse_utc_timestamp(timestamp_utc)
        poll_timestamp = _parse_utc_timestamp(poll_completed_at)
        if not timestamp_utc or row_timestamp is None:
            failures.append(f"row {row_number} timestamp_utc must be a parseable UTC timestamp")
        if poll_completed_at and poll_timestamp is None:
            failures.append(f"row {row_number} spot_last_poll_completed_at must be a parseable UTC timestamp when populated")
        poll_seq: int | None = None
        if raw_poll_seq:
            try:
                poll_seq = int(raw_poll_seq)
            except ValueError:
                failures.append(f"row {row_number} spot_poll_seq must be an integer when populated")
        if spot_observation_key:
            if poll_seq is None or poll_seq <= 0:
                failures.append(f"row {row_number} nonblank spot_observation_key requires positive spot_poll_seq")
            if poll_status == "not_attempted":
                failures.append(f"row {row_number} not_attempted poll requires blank spot_observation_key")
            if not poll_completed_at:
                failures.append(f"row {row_number} missing spot_last_poll_completed_at requires blank spot_observation_key")
            if output_status == "startup_pending":
                failures.append(f"row {row_number} startup_pending row requires blank spot_observation_key")
            if shadow_status == "startup_pending":
                failures.append(
                    f"row {row_number} startup_pending shadow status requires blank spot_observation_key"
                )
        if row_timestamp is not None and poll_timestamp is not None:
            actual_age_ms = (row_timestamp - poll_timestamp).total_seconds() * 1000.0
            if actual_age_ms < 0:
                if clock_status != "clock_anomaly":
                    failures.append(
                        f"row {row_number} negative timestamp row age requires spot_row_age_clock_status=clock_anomaly"
                    )
                if row_freshness != "unknown":
                    failures.append(
                        f"row {row_number} negative timestamp row age requires spot_effective_freshness_at_row=unknown"
                    )
                if output_status != "unknown" or unavailable_reason != "unknown_freshness":
                    failures.append(
                        f"row {row_number} negative timestamp row age requires "
                        "temperature_output_status=unknown and temperature_unavailable_reason=unknown_freshness"
                    )
            elif actual_age_ms > row_time_freshness_threshold_ms:
                if row_freshness != "stale":
                    failures.append(
                        f"row {row_number} timestamp row age {actual_age_ms:.3f}ms exceeds "
                        f"{row_time_freshness_threshold_ms:.3f}ms but "
                        f"spot_effective_freshness_at_row={row_freshness!r}"
                    )
                if output_status != "stale":
                    failures.append(
                        f"row {row_number} timestamp row age {actual_age_ms:.3f}ms exceeds "
                        f"{row_time_freshness_threshold_ms:.3f}ms but temperature_output_status={output_status!r}"
                    )
        if row_freshness == "stale" or source_freshness == "stale":
            if output_status != "stale":
                failures.append(f"row {row_number} stale freshness requires temperature_output_status=stale")
            if unavailable_reason != "stale_observation":
                failures.append(f"row {row_number} stale freshness requires temperature_unavailable_reason=stale_observation")
        if raw_validity == "invalid_sentinel" and row_freshness != "stale" and source_freshness != "stale":
            expected_status = {
                "temperature_under_range": "under_range",
                "temperature_over_range": "over_range",
            }.get(device_status)
            if expected_status is None:
                failures.append(f"row {row_number} invalid_sentinel has unsupported spot_device_status_code={device_status!r}")
            elif output_status != expected_status:
                failures.append(f"row {row_number} invalid_sentinel output status {output_status!r}, expected {expected_status!r}")
        if cause == "low_signal_candidate" and not ({"alarm_low_signal", "signal_below_threshold"} & set(evidence_codes)):
            failures.append(f"row {row_number} low_signal_candidate requires alarm_low_signal or signal_below_threshold evidence")
        if cause == "peak_picker_reset_candidate" and "peak_picker_off_mode_reset_configured" not in evidence_codes:
            failures.append(f"row {row_number} peak_picker_reset_candidate requires peak_picker_off_mode_reset_configured evidence")
        if cause == "below_measurement_range_candidate" and not {
            "measurement_range_configured",
            "detector_below_measurement_range",
        }.issubset(set(evidence_codes)):
            failures.append(f"row {row_number} below_measurement_range_candidate requires measurement range and detector evidence")
        if confidence:
            parsed_confidence = _parse_finite_float(confidence)
            if parsed_confidence is None or not 0.0 <= parsed_confidence <= 1.0:
                failures.append(f"row {row_number} temperature_cause_confidence must be 0.0..1.0")
        if any((image_capture_id, image_path, image_link_status, image_link_age)):
            if not image_capture_id:
                failures.append(f"row {row_number} image link requires spot_image_capture_id_nearest")
            if not image_path:
                failures.append(f"row {row_number} image link requires spot_image_path_nearest")
            elif _is_unsafe_relative_path(image_path):
                failures.append(f"row {row_number} spot_image_path_nearest must be a safe relative path")
            if not image_link_status:
                failures.append(f"row {row_number} image link requires spot_image_link_status_nearest")
            if image_link_status == "fresh" and not spot_observation_key:
                failures.append(f"row {row_number} fresh image link requires spot_observation_key")
            if image_link_age and _parse_finite_float(image_link_age) is None:
                failures.append(f"row {row_number} spot_image_link_age_ms_nearest must be finite when populated")
    return failures


def validate_current_server_promotion_profile(snapshot: dict) -> list[str]:
    failures: list[str] = []
    for key, expected in CURRENT_SERVER_PROMOTION_SPOT_CONFIGURATION_PROFILE.items():
        actual = snapshot.get(key)
        if isinstance(expected, float):
            parsed = _parse_finite_float(actual)
            if parsed is None or abs(parsed - expected) > 1e-9:
                failures.append(f"current server promotion profile spot_configuration_snapshot.{key} must be {expected!r}")
        elif actual != expected:
            failures.append(f"current server promotion profile spot_configuration_snapshot.{key} must be {expected!r}")
    return failures


def validate_spot_configuration_snapshot(
    metadata: dict,
    rows: list[list[str]],
    header: list[str],
    *,
    require_current_server_promotion_profile: bool = False,
) -> list[str]:
    failures: list[str] = []
    snapshot = metadata.get("spot_configuration_snapshot")
    if not isinstance(snapshot, dict):
        return ["metadata missing spot_configuration_snapshot block"]

    threshold = _parse_finite_float(snapshot.get("low_signal_threshold_pc"))
    if threshold is None or not 0.0 <= threshold <= 100.0:
        failures.append("spot_configuration_snapshot.low_signal_threshold_pc must be 0.0..100.0")
    comparator = str(snapshot.get("low_signal_comparator") or "").strip().lower()
    if comparator not in {"lt", "lte", "unknown"}:
        failures.append("spot_configuration_snapshot.low_signal_comparator must be lt/lte/unknown")
    if not isinstance(snapshot.get("low_signal_alarm_enabled"), bool):
        failures.append("spot_configuration_snapshot.low_signal_alarm_enabled must be boolean")
    if not isinstance(snapshot.get("low_signal_comparator_verified"), bool):
        failures.append("spot_configuration_snapshot.low_signal_comparator_verified must be boolean")
    for key in (
        "peak_picker_enabled",
        "limiter_enabled",
        "averager_enabled",
        "modemaster_enabled",
        "spot_ratio_raw_enabled",
        "config_operator_verified",
    ):
        if key in snapshot and not isinstance(snapshot.get(key), bool):
            failures.append(f"spot_configuration_snapshot.{key} must be boolean")
    for key in (
        "spot_range_min_c",
        "spot_range_max_c",
        "spot_analog_4ma_c",
        "spot_analog_20ma_c",
        "window_obscuration_pc",
        "focus_mm",
    ):
        if key in snapshot and _parse_finite_float(snapshot.get(key)) is None:
            failures.append(f"spot_configuration_snapshot.{key} must be finite")
    range_min = _parse_finite_float(snapshot.get("spot_range_min_c"))
    range_max = _parse_finite_float(snapshot.get("spot_range_max_c"))
    if range_min is not None and range_max is not None and range_min > range_max:
        failures.append("spot_configuration_snapshot.spot_range_min_c must be <= spot_range_max_c")
    obscuration = _parse_finite_float(snapshot.get("window_obscuration_pc"))
    if obscuration is not None and not 0.0 <= obscuration <= 100.0:
        failures.append("spot_configuration_snapshot.window_obscuration_pc must be 0.0..100.0")

    if snapshot.get("low_signal_alarm_enabled") is False and "temperature_cause_evidence_codes" in header:
        evidence_index = header.index("temperature_cause_evidence_codes")
        for row_number, row in enumerate(rows, start=2):
            if evidence_index >= len(row):
                continue
            evidence_codes = _parse_json_string_list(row[evidence_index].strip())
            if "signal_below_threshold" in evidence_codes:
                failures.append(f"row {row_number} signal_below_threshold evidence is forbidden when low signal alarm is disabled")
    if snapshot.get("peak_picker_enabled") is False and "temperature_under_range_cause_candidate" in header:
        cause_index = header.index("temperature_under_range_cause_candidate")
        for row_number, row in enumerate(rows, start=2):
            if cause_index < len(row) and row[cause_index].strip() == "peak_picker_reset_candidate":
                failures.append(f"row {row_number} peak_picker_reset_candidate is forbidden when Peak Picker is disabled")
    if require_current_server_promotion_profile:
        failures.extend(validate_current_server_promotion_profile(snapshot))
    return failures

def _parse_bool_text(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return None


def _parse_alarmstatus_byte(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = int(text, 0)
    except ValueError:
        return None
    if parsed < 0 or parsed > 255:
        return None
    return parsed


def validate_spot_observation_fact_invariants(fact_path: Path) -> list[str]:
    header, rows = read_csv(fact_path)
    required_columns = [
        "alarmstatus",
        "spot_diagnostic_evidence_codes",
        "low_signal_alarm_enabled",
        "low_signal_threshold_pc",
        "low_signal_comparator",
        "peak_picker_enabled",
    ]
    missing_columns = [column for column in required_columns if column not in header]
    if missing_columns:
        return ["spot_observation_fact header missing columns: " + ", ".join(missing_columns)]

    failures: list[str] = []
    indices = {column: header.index(column) for column in required_columns}
    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            failures.append(
                f"spot_observation_fact row {row_number} has {len(row)} columns, expected {len(header)}"
            )
            continue
        evidence_codes = _parse_json_string_list(row[indices["spot_diagnostic_evidence_codes"]].strip())
        alarmstatus = _parse_alarmstatus_byte(row[indices["alarmstatus"]])
        if alarmstatus is not None and (alarmstatus & 0x10) and "alarm_low_signal" not in evidence_codes:
            failures.append(
                f"spot_observation_fact row {row_number} alarmstatus bit4 requires alarm_low_signal evidence"
            )
        threshold = row[indices["low_signal_threshold_pc"]].strip()
        if threshold:
            parsed_threshold = _parse_finite_float(threshold)
            if parsed_threshold is None or not 0.0 <= parsed_threshold <= 100.0:
                failures.append(f"spot_observation_fact row {row_number} low_signal_threshold_pc must be 0.0..100.0")
        comparator = row[indices["low_signal_comparator"]].strip().lower()
        if comparator and comparator not in {"lt", "lte", "unknown"}:
            failures.append(f"spot_observation_fact row {row_number} low_signal_comparator must be lt/lte/unknown")
        low_signal_alarm_enabled = _parse_bool_text(row[indices["low_signal_alarm_enabled"]])
        if row[indices["low_signal_alarm_enabled"]].strip() and low_signal_alarm_enabled is None:
            failures.append(f"spot_observation_fact row {row_number} low_signal_alarm_enabled must be true/false")
        if low_signal_alarm_enabled is False and "signal_below_threshold" in evidence_codes:
            failures.append(
                f"spot_observation_fact row {row_number} signal_below_threshold is forbidden when low signal alarm is disabled"
            )
        peak_picker_enabled = _parse_bool_text(row[indices["peak_picker_enabled"]])
        if peak_picker_enabled is False and "peak_picker_off_mode_reset_configured" in evidence_codes:
            failures.append(
                f"spot_observation_fact row {row_number} peak_picker evidence is forbidden when Peak Picker is disabled"
            )
    return failures


def _new_spot_observation_fact_summary(spot_observation_fact_path: Path | None) -> dict[str, str]:
    override_file = spot_observation_fact_path.name if spot_observation_fact_path is not None else "not provided"
    return {
        "spot_observation_fact_validation_source": "not_applicable",
        "spot_observation_fact_override_provided": _bool_text(spot_observation_fact_path is not None),
        "spot_observation_fact_manifest_fact_file": "",
        "spot_observation_fact_override_file": override_file,
        "spot_observation_fact_verified_file": "not available",
        "spot_observation_fact_manifest_row_count": "unknown",
        "spot_observation_fact_actual_row_count": "unknown",
        "spot_observation_fact_row_count_match": "unknown",
        "spot_observation_fact_manifest_distinct_observation_key_count": "unknown",
        "spot_observation_fact_actual_distinct_observation_key_count": "unknown",
        "spot_observation_fact_distinct_observation_key_count_match": "unknown",
        "spot_observation_fact_manifest_first_poll_seq": "unknown",
        "spot_observation_fact_actual_first_poll_seq": "unknown",
        "spot_observation_fact_first_poll_seq_match": "unknown",
        "spot_observation_fact_manifest_last_poll_seq": "unknown",
        "spot_observation_fact_actual_last_poll_seq": "unknown",
        "spot_observation_fact_last_poll_seq_match": "unknown",
        "spot_observation_fact_manifest_poll_seq_gap_count": "unknown",
        "spot_observation_fact_actual_poll_seq_gap_count": "unknown",
        "spot_observation_fact_poll_seq_gap_count_match": "unknown",
        "spot_observation_fact_manifest_sha256": "unknown",
        "spot_observation_fact_actual_sha256": "unknown",
        "spot_observation_fact_sha256_match": "unknown",
        "spot_observation_fact_write_failure_count": "unknown",
        "spot_observation_fact_spool_pending_count": "unknown",
        "spot_observation_fact_realtime_rows_with_observation_key": "unknown",
        "spot_observation_fact_linked_rows": "unknown",
        "spot_observation_fact_missing_fact_key_rows": "unknown",
        "spot_observation_fact_link_coverage_pct": "unknown",
        "spot_observation_fact_diagnostic_source_mismatch_count": "unknown",
    }


def validate_spot_observation_fact_manifest(
    metadata: dict,
    metadata_path: Path,
    v2_header: Sequence[str],
    v2_rows: Sequence[Sequence[str]],
    spot_observation_fact_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    summary = _new_spot_observation_fact_summary(spot_observation_fact_path)
    summary["spot_observation_fact_validation_source"] = (
        "override" if spot_observation_fact_path is not None else "metadata_manifest"
    )
    manifest = metadata.get("spot_observation_fact_manifest")
    if not isinstance(manifest, dict):
        return ["metadata missing spot_observation_fact_manifest block"], summary

    failures: list[str] = []
    if manifest.get("enabled") is not True:
        failures.append("spot_observation_fact_manifest.enabled must be true")
    if manifest.get("schema_version") != SPOT_OBSERVATION_FACT_SCHEMA_VERSION:
        failures.append(
            f"spot_observation_fact_manifest.schema_version must be {SPOT_OBSERVATION_FACT_SCHEMA_VERSION}"
        )

    fact_path_text = str(
        manifest.get("path")
        or manifest.get("fact_path")
        or SPOT_OBSERVATION_FACT_FILENAME
    ).strip()
    summary["spot_observation_fact_manifest_fact_file"] = _path_basename_text(fact_path_text)
    if not fact_path_text:
        failures.append("spot_observation_fact_manifest.path must be populated")
    if fact_path_text and _is_unsafe_relative_path(fact_path_text):
        failures.append("spot_observation_fact_manifest.path must be a safe relative path")
    fact_path = (
        spot_observation_fact_path
        if spot_observation_fact_path is not None
        else (metadata_path.parent / fact_path_text)
    )
    summary["spot_observation_fact_verified_file"] = fact_path.name
    if not fact_path.exists():
        failures.append("spot_observation_fact.csv is required but was not found")
        return failures, summary

    required_columns = manifest.get("required_columns")
    if required_columns is not None and list(required_columns) != SPOT_OBSERVATION_FACT_COLUMNS:
        failures.append("spot_observation_fact_manifest.required_columns does not match contract")

    realtime_row_dicts = _row_dicts(v2_header, v2_rows)
    actual_manifest = build_spot_observation_fact_manifest(
        fact_path=fact_path,
        enabled=True,
        write_failure_count=0,
        spool_pending_count=0,
        realtime_rows=realtime_row_dicts,
        path=SPOT_OBSERVATION_FACT_FILENAME,
    )

    scalar_checks = [
        ("row_count", "row_count", True),
        ("distinct_observation_key_count", "distinct_observation_key_count", True),
        ("first_poll_seq", "first_poll_seq", False),
        ("last_poll_seq", "last_poll_seq", False),
        ("poll_seq_gap_count", "poll_seq_gap_count", False),
        ("sha256", "sha256", True),
    ]
    for manifest_key, summary_suffix, required in scalar_checks:
        manifest_value = manifest.get(manifest_key)
        actual_value = actual_manifest.get(manifest_key)
        summary[f"spot_observation_fact_manifest_{summary_suffix}"] = _summary_value(manifest_value)
        summary[f"spot_observation_fact_actual_{summary_suffix}"] = _summary_value(actual_value)
        match_key = f"spot_observation_fact_{summary_suffix}_match"
        value_matches = manifest_value == actual_value
        summary[match_key] = _bool_text(value_matches)
        if required and manifest_value in (None, ""):
            failures.append(f"spot_observation_fact_manifest.{manifest_key} must be populated")
        if manifest_value != actual_value:
            failures.append(
                f"spot_observation_fact_manifest.{manifest_key}={manifest_value!r}, actual={actual_value!r}"
            )

    row_count = _parse_non_negative_int(manifest.get("row_count"))
    if row_count is None or row_count <= 0:
        failures.append("spot_observation_fact_manifest.row_count must be greater than 0")
    if not _is_sha256_text(str(manifest.get("sha256") or "")):
        failures.append("spot_observation_fact_manifest.sha256 must be populated with lowercase SHA-256")

    write_failure_count = _parse_non_negative_int(manifest.get("write_failure_count"))
    spool_pending_count = _parse_non_negative_int(manifest.get("spool_pending_count"))
    summary["spot_observation_fact_write_failure_count"] = _summary_value(manifest.get("write_failure_count"))
    summary["spot_observation_fact_spool_pending_count"] = _summary_value(manifest.get("spool_pending_count"))
    if write_failure_count != 0:
        failures.append("spot_observation_fact_manifest.write_failure_count must be 0")
    if spool_pending_count != 0:
        failures.append("spot_observation_fact_manifest.spool_pending_count must be 0")

    failures.extend(_compare_nested_counts(manifest, actual_manifest, "link_coverage", summary))
    failures.extend(_compare_nested_counts(manifest, actual_manifest, "diagnostic_field_coverage", summary))
    actual_link_coverage = actual_manifest.get("link_coverage", {})
    if actual_link_coverage.get("missing_fact_key_rows") != 0:
        failures.append("spot_observation_fact_manifest.link_coverage.missing_fact_key_rows must be 0")
    if actual_link_coverage.get("coverage_pct") != 100.0:
        failures.append("spot_observation_fact_manifest.link_coverage.coverage_pct must be 100.0")

    try:
        fact_header, fact_rows = read_csv(fact_path)
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        return [*failures, f"spot_observation_fact CSV read failed: {exc.__class__.__name__}"], summary

    missing_columns = [column for column in SPOT_OBSERVATION_FACT_COLUMNS if column not in fact_header]
    if missing_columns:
        return [*failures, "spot_observation_fact header missing columns: " + ", ".join(missing_columns)], summary
    failures.extend(validate_spot_observation_fact_invariants(fact_path))

    fact_row_dicts = _row_dicts(fact_header, fact_rows)
    fact_by_key: dict[str, dict[str, str]] = {}
    duplicate_key_count = 0
    for fact in fact_row_dicts:
        key = fact.get("spot_observation_key", "").strip()
        if not key:
            continue
        if key in fact_by_key:
            duplicate_key_count += 1
            continue
        fact_by_key[key] = fact
    if duplicate_key_count:
        failures.append(f"spot_observation_fact has duplicate spot_observation_key rows: {duplicate_key_count}")

    source_mismatch_count = 0
    for row_number, row in enumerate(realtime_row_dicts, start=2):
        key = row.get("spot_observation_key", "").strip()
        if not key:
            continue
        fact = fact_by_key.get(key)
        if fact is None:
            failures.append(f"row {row_number} spot_observation_key has no matching spot_observation_fact row")
            continue
        evidence_codes = _parse_json_string_list(row.get("temperature_cause_evidence_codes", "").strip())
        missing_sources = _missing_diagnostic_sources_for_evidence(evidence_codes, fact)
        if missing_sources:
            source_mismatch_count += 1
            failures.append(
                f"row {row_number} evidence requires spot_observation_fact fields: {', '.join(missing_sources)}"
            )
    summary["spot_observation_fact_diagnostic_source_mismatch_count"] = str(source_mismatch_count)
    return failures, summary


def _row_dicts(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[dict[str, str]]:
    row_dicts: list[dict[str, str]] = []
    for row in rows:
        row_dicts.append({column: row[index] if index < len(row) else "" for index, column in enumerate(header)})
    return row_dicts


def _summary_value(value: object) -> str:
    if value is None:
        return "null"
    return str(value)


def _compare_nested_counts(
    manifest: dict,
    actual_manifest: dict,
    key: str,
    summary: dict[str, str],
) -> list[str]:
    failures: list[str] = []
    manifest_section = manifest.get(key)
    actual_section = actual_manifest.get(key)
    if not isinstance(manifest_section, dict) or not isinstance(actual_section, dict):
        failures.append(f"spot_observation_fact_manifest.{key} must be an object")
        return failures
    for nested_key, actual_value in actual_section.items():
        manifest_value = manifest_section.get(nested_key)
        summary_key = f"spot_observation_fact_{nested_key}"
        if key == "link_coverage" and nested_key == "coverage_pct":
            summary_key = "spot_observation_fact_link_coverage_pct"
        if key == "diagnostic_field_coverage":
            summary_key = f"spot_observation_fact_diagnostic_{nested_key}"
        summary[summary_key] = _summary_value(actual_value)
        if manifest_value != actual_value:
            failures.append(
                f"spot_observation_fact_manifest.{key}.{nested_key}={manifest_value!r}, actual={actual_value!r}"
            )
    return failures


def _missing_diagnostic_sources_for_evidence(evidence_codes: Sequence[str], fact: dict[str, str]) -> list[str]:
    required: list[str] = []
    code_set = set(evidence_codes)
    if "alarm_low_signal" in code_set:
        required.append("alarmstatus")
    if code_set.intersection(
        {
            "signal_below_threshold",
            "signal_below_configured_threshold_alarm_disabled",
            "signal_at_or_above_configured_threshold",
        }
    ):
        required.extend(["signalpc", "low_signal_threshold_pc", "low_signal_comparator"])
    if "peak_picker_off_mode_reset_configured" in code_set:
        required.extend(["peak_picker_enabled", "peak_picker_off_mode"])
    missing = [field for field in required if not fact.get(field, "").strip()]
    if code_set.intersection({"actuator_scanning", "actuator_position_changed"}):
        if not fact.get("actuator_scan_state", "").strip() and not fact.get("actuator_position", "").strip():
            missing.append("actuator_scan_state or actuator_position")
    return missing


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _path_basename_text(value: str) -> str:
    normalized = value.replace("\\", "/").rstrip("/")
    if not normalized:
        return ""
    return normalized.rsplit("/", 1)[-1]


def _path_display(path: Path | None) -> str:
    return path.name if path is not None else "not provided"


def _new_spot_image_fact_summary(
    spot_image_fact_path: Path | None,
    spot_image_fact_final_manifest_path: Path | None = None,
) -> dict[str, str]:
    override_file = spot_image_fact_path.name if spot_image_fact_path is not None else "not provided"
    final_manifest_file = (
        spot_image_fact_final_manifest_path.name
        if spot_image_fact_final_manifest_path is not None
        else "not provided"
    )
    return {
        "spot_image_fact_validation_source": "not_applicable",
        "spot_image_fact_override_provided": _bool_text(spot_image_fact_path is not None),
        "spot_image_fact_final_manifest_provided": _bool_text(spot_image_fact_final_manifest_path is not None),
        "spot_image_fact_final_manifest_file": final_manifest_file,
        "spot_image_fact_manifest_fact_file": "",
        "spot_image_fact_override_file": override_file,
        "spot_image_fact_verified_file": "not available",
        "spot_image_fact_manifest_row_count": "unknown",
        "spot_image_fact_actual_row_count": "unknown",
        "spot_image_fact_row_count_match": "unknown",
        "spot_image_fact_manifest_sha256": "unknown",
        "spot_image_fact_actual_sha256": "unknown",
        "spot_image_fact_sha256_match": "unknown",
    }


def validate_spot_image_fact_manifest(
    metadata: dict,
    metadata_path: Path,
    spot_image_fact_path: Path | None = None,
    spot_image_fact_final_manifest_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    summary = _new_spot_image_fact_summary(spot_image_fact_path, spot_image_fact_final_manifest_path)
    manifest_label = "spot_image_fact_manifest"
    strict_manifest_stats = spot_image_fact_path is None
    if spot_image_fact_final_manifest_path is not None:
        summary["spot_image_fact_validation_source"] = "final_manifest"
        manifest_label = "spot_image_fact_final_manifest"
        strict_manifest_stats = True
        if not spot_image_fact_final_manifest_path.exists():
            return ["spot_image_fact final manifest path does not exist"], summary
        try:
            final_payload = json.loads(spot_image_fact_final_manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return ["spot_image_fact final manifest JSON could not be read"], summary
        if isinstance(final_payload, dict) and isinstance(final_payload.get("spot_image_fact_manifest"), dict):
            manifest = final_payload.get("spot_image_fact_manifest")
        else:
            manifest = final_payload
    else:
        manifest = metadata.get("spot_image_fact_manifest")
        summary["spot_image_fact_validation_source"] = (
            "override" if spot_image_fact_path is not None else "metadata_manifest"
        )
    if not isinstance(manifest, dict):
        if spot_image_fact_final_manifest_path is not None:
            return ["spot_image_fact final manifest must be a JSON object"], summary
        return ["metadata missing spot_image_fact_manifest block"], summary

    failures: list[str] = []
    enabled = manifest.get("enabled")
    if not isinstance(enabled, bool):
        failures.append(f"{manifest_label}.enabled must be boolean")
    mode = str(manifest.get("mode") or "")
    if mode not in {"off", "event", "interval", "all"}:
        failures.append(f"{manifest_label}.mode must be off/event/interval/all")

    fact_path_text = str(manifest.get("fact_path") or "").strip()
    capture_root_text = str(manifest.get("capture_root") or "").strip()
    summary["spot_image_fact_manifest_fact_file"] = _path_basename_text(fact_path_text)
    if not fact_path_text:
        failures.append(f"{manifest_label}.fact_path must be populated")
    if not capture_root_text:
        failures.append(f"{manifest_label}.capture_root must be populated")

    row_count = _parse_non_negative_int(manifest.get("row_count"))
    if row_count is None:
        failures.append(f"{manifest_label}.row_count must be a non-negative integer")
        row_count = 0
    summary["spot_image_fact_manifest_row_count"] = str(row_count)

    for key in ("written", "dropped", "failure"):
        value = manifest.get(key)
        if value is not None and _parse_non_negative_int(value) is None:
            failures.append(f"{manifest_label}.{key} must be null or a non-negative integer")

    manifest_sha = manifest.get("sha256")
    if manifest_sha is not None and not _is_sha256_text(str(manifest_sha)):
        failures.append(f"{manifest_label}.sha256 must be null or lowercase SHA-256")
    summary["spot_image_fact_manifest_sha256"] = str(manifest_sha or "")

    if not fact_path_text and spot_image_fact_path is None:
        return failures, summary

    fact_path = spot_image_fact_path if spot_image_fact_path is not None else Path(fact_path_text)
    summary["spot_image_fact_verified_file"] = fact_path.name
    if not fact_path.exists():
        if spot_image_fact_path is not None:
            failures.append("spot_image_fact override path does not exist")
        elif row_count > 0 or manifest_sha:
            failures.append(f"{manifest_label}.fact_path does not exist despite non-empty manifest stats")
        return failures, summary

    try:
        fact_hash = hashlib.sha256(fact_path.read_bytes()).hexdigest()
    except OSError:
        failures.append("spot_image_fact could not be read")
        return failures, summary
    summary["spot_image_fact_actual_sha256"] = fact_hash
    sha_matches = bool(manifest_sha and fact_hash == manifest_sha)
    summary["spot_image_fact_sha256_match"] = _bool_text(sha_matches)
    if manifest_sha and fact_hash != manifest_sha and strict_manifest_stats:
        failures.append(f"{manifest_label}.sha256 does not match fact file")

    try:
        header, rows = read_csv(fact_path)
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        failures.append(f"spot_image_fact CSV read failed: {exc.__class__.__name__}")
        return failures, summary

    summary["spot_image_fact_actual_row_count"] = str(len(rows))
    row_count_matches = len(rows) == row_count
    summary["spot_image_fact_row_count_match"] = _bool_text(row_count_matches)
    if not row_count_matches and strict_manifest_stats:
        failures.append(f"{manifest_label}.row_count={row_count}, actual spot_image_fact rows={len(rows)}")
    missing_columns = [column for column in SPOT_IMAGE_FACT_REQUIRED_COLUMNS if column not in header]
    if missing_columns and rows:
        failures.append("spot_image_fact header missing columns: " + ", ".join(missing_columns))
        return failures, summary

    if rows:
        indices = {column: header.index(column) for column in SPOT_IMAGE_FACT_REQUIRED_COLUMNS}
        fact_parent = fact_path.parent.resolve()
        for row_number, row in enumerate(rows, start=2):
            if len(row) != len(header):
                failures.append(f"spot_image_fact row {row_number} has {len(row)} columns, expected {len(header)}")
                continue
            row_sha = row[indices["spot_image_sha256"]].strip()
            if not _is_sha256_text(row_sha):
                failures.append(f"spot_image_fact row {row_number} spot_image_sha256 must be lowercase SHA-256")
            link_status = row[indices["spot_image_link_status"]].strip()
            if link_status not in SPOT_IMAGE_LINK_STATUSES:
                failures.append(f"spot_image_fact row {row_number} spot_image_link_status={link_status!r} is invalid")
            linked_key = row[indices["spot_image_linked_observation_key"]].strip()
            if link_status == "fresh" and ":" not in linked_key:
                failures.append(f"spot_image_fact row {row_number} fresh link requires spot_image_linked_observation_key")
            image_path = row[indices["spot_image_path"]].strip()
            if _is_unsafe_relative_path(image_path):
                failures.append(f"spot_image_fact row {row_number} spot_image_path must be a safe relative path")
                continue
            resolved_image_path = (fact_parent / image_path).resolve()
            if not _is_within_directory(resolved_image_path, fact_parent):
                failures.append(f"spot_image_fact row {row_number} spot_image_path escapes the log directory")

    return failures, summary


def _new_process_phase_fact_summary(summary_prefix: str, fact_path: Path | None) -> dict[str, str]:
    override_file = fact_path.name if fact_path is not None else "not provided"
    return {
        f"{summary_prefix}_validation_source": "not_applicable",
        f"{summary_prefix}_override_provided": _bool_text(fact_path is not None),
        f"{summary_prefix}_manifest_fact_file": "",
        f"{summary_prefix}_override_file": override_file,
        f"{summary_prefix}_verified_file": "not available",
        f"{summary_prefix}_manifest_row_count": "unknown",
        f"{summary_prefix}_actual_row_count": "unknown",
        f"{summary_prefix}_row_count_match": "unknown",
        f"{summary_prefix}_manifest_sha256": "unknown",
        f"{summary_prefix}_actual_sha256": "unknown",
        f"{summary_prefix}_sha256_match": "unknown",
        f"{summary_prefix}_manifest_source_csv_sha256": "unknown",
        f"{summary_prefix}_actual_source_csv_sha256": "unknown",
        f"{summary_prefix}_source_csv_sha256_match": "unknown",
    }


def _posthoc_fact_manifest_required(metadata: dict, manifest_key: str) -> bool:
    schema_metadata = metadata.get("schema_metadata")
    if not isinstance(schema_metadata, dict):
        return False
    manifest_keys = schema_metadata.get("posthoc_fact_manifests")
    return isinstance(manifest_keys, list) and manifest_key in manifest_keys


def validate_process_phase_fact_manifest(
    metadata: dict,
    metadata_path: Path,
    v2_path: Path,
    *,
    manifest_key: str,
    summary_prefix: str,
    fact_kind: str,
    required_columns: Sequence[str],
    schema_field: str,
    expected_schema_version: str,
    rule_field: str,
    expected_rule_version: str,
    fact_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    manifest = metadata.get(manifest_key)
    summary = _new_process_phase_fact_summary(summary_prefix, fact_path)
    summary[f"{summary_prefix}_validation_source"] = "override" if fact_path is not None else "metadata_manifest"
    if not isinstance(manifest, dict):
        if _posthoc_fact_manifest_required(metadata, manifest_key) or fact_path is not None:
            return [f"metadata missing {manifest_key} block"], summary
        summary[f"{summary_prefix}_validation_source"] = "not_applicable"
        return [], summary

    failures: list[str] = []
    if manifest.get("fact_kind") != fact_kind:
        failures.append(f"{manifest_key}.fact_kind must be {fact_kind!r}")
    if manifest.get("schema_version") != expected_schema_version:
        failures.append(f"{manifest_key}.schema_version must be {expected_schema_version!r}")
    if manifest.get("rule_version") != expected_rule_version:
        failures.append(f"{manifest_key}.rule_version must be {expected_rule_version!r}")

    fact_path_text = str(manifest.get("fact_path") or "").strip()
    summary[f"{summary_prefix}_manifest_fact_file"] = _path_basename_text(fact_path_text)
    if not fact_path_text:
        failures.append(f"{manifest_key}.fact_path must be populated")

    manifest_columns = manifest.get("required_columns")
    if manifest_columns != list(required_columns):
        failures.append(f"{manifest_key}.required_columns must match canonical fact columns")

    row_count = _parse_non_negative_int(manifest.get("row_count"))
    if row_count is None:
        failures.append(f"{manifest_key}.row_count must be a non-negative integer")
        row_count = 0
    summary[f"{summary_prefix}_manifest_row_count"] = str(row_count)

    manifest_sha = manifest.get("sha256")
    if manifest_sha is not None and not _is_sha256_text(str(manifest_sha)):
        failures.append(f"{manifest_key}.sha256 must be null or lowercase SHA-256")
    manifest_sha_text = str(manifest_sha or "")
    summary[f"{summary_prefix}_manifest_sha256"] = manifest_sha_text

    actual_source_csv_sha256 = hashlib.sha256(v2_path.read_bytes()).hexdigest()
    summary[f"{summary_prefix}_actual_source_csv_sha256"] = actual_source_csv_sha256
    manifest_source_sha = manifest.get("source_csv_sha256")
    if manifest_source_sha is not None and not _is_sha256_text(str(manifest_source_sha)):
        failures.append(f"{manifest_key}.source_csv_sha256 must be null or lowercase SHA-256")
    manifest_source_sha_text = str(manifest_source_sha or "")
    summary[f"{summary_prefix}_manifest_source_csv_sha256"] = manifest_source_sha_text
    if manifest_source_sha:
        source_sha_matches = manifest_source_sha == actual_source_csv_sha256
        summary[f"{summary_prefix}_source_csv_sha256_match"] = _bool_text(source_sha_matches)
        if not source_sha_matches:
            failures.append(f"{manifest_key}.source_csv_sha256 does not match v2 CSV")

    source_file_id = manifest.get("source_file_id")
    expected_source_file_id = f"sha256:{actual_source_csv_sha256}"
    if source_file_id is not None and source_file_id != expected_source_file_id:
        failures.append(f"{manifest_key}.source_file_id does not match v2 CSV SHA-256")

    if not fact_path_text and fact_path is None:
        return failures, summary

    selected_fact_path = fact_path if fact_path is not None else Path(fact_path_text)
    summary[f"{summary_prefix}_verified_file"] = selected_fact_path.name
    if not selected_fact_path.exists():
        if fact_path is not None:
            failures.append(f"{summary_prefix} override path does not exist")
        elif row_count > 0 or manifest_sha:
            failures.append(f"{manifest_key}.fact_path does not exist despite non-empty manifest stats")
        return failures, summary

    try:
        fact_hash = hashlib.sha256(selected_fact_path.read_bytes()).hexdigest()
    except OSError:
        failures.append(f"{summary_prefix} could not be read")
        return failures, summary
    summary[f"{summary_prefix}_actual_sha256"] = fact_hash
    sha_matches = bool(manifest_sha and fact_hash == manifest_sha)
    summary[f"{summary_prefix}_sha256_match"] = _bool_text(sha_matches)
    if manifest_sha and fact_hash != manifest_sha and fact_path is None:
        failures.append(f"{manifest_key}.sha256 does not match fact file")

    try:
        header, rows = read_csv(selected_fact_path)
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        failures.append(f"{summary_prefix} CSV read failed: {exc.__class__.__name__}")
        return failures, summary

    summary[f"{summary_prefix}_actual_row_count"] = str(len(rows))
    row_count_matches = len(rows) == row_count
    summary[f"{summary_prefix}_row_count_match"] = _bool_text(row_count_matches)
    if not row_count_matches and fact_path is None:
        failures.append(f"{manifest_key}.row_count={row_count}, actual {summary_prefix} rows={len(rows)}")

    missing_columns = [column for column in required_columns if column not in header]
    if missing_columns:
        failures.append(f"{summary_prefix} header missing columns: " + ", ".join(missing_columns))
        return failures, summary

    indices = {column: header.index(column) for column in required_columns}
    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            failures.append(f"{summary_prefix} row {row_number} has {len(row)} columns, expected {len(header)}")
            continue
        if row[indices[schema_field]].strip() != expected_schema_version:
            failures.append(f"{summary_prefix} row {row_number} {schema_field} must be {expected_schema_version!r}")
        if row[indices[rule_field]].strip() != expected_rule_version:
            failures.append(f"{summary_prefix} row {row_number} {rule_field} must be {expected_rule_version!r}")
        if row[indices["source_file_id"]].strip() != expected_source_file_id:
            failures.append(f"{summary_prefix} row {row_number} source_file_id does not match v2 CSV SHA-256")

    if rows and not manifest_source_sha:
        failures.append(f"{manifest_key}.source_csv_sha256 must be populated when fact rows exist")
    if rows and source_file_id is None:
        failures.append(f"{manifest_key}.source_file_id must be populated when fact rows exist")

    return failures, summary


def validate_changeover_candidate_resolution_fact_manifest(
    metadata: dict,
    metadata_path: Path,
    v2_path: Path,
    fact_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    return validate_process_phase_fact_manifest(
        metadata,
        metadata_path,
        v2_path,
        manifest_key="changeover_candidate_resolution_fact_manifest",
        summary_prefix="changeover_candidate_resolution_fact",
        fact_kind="changeover_candidate_resolution_fact",
        required_columns=CHANGEOVER_CANDIDATE_RESOLUTION_FACT_COLUMNS,
        schema_field="candidate_resolution_schema_version",
        expected_schema_version=CHANGEOVER_CANDIDATE_RESOLUTION_SCHEMA_VERSION,
        rule_field="resolution_rule_version",
        expected_rule_version=CHANGEOVER_CANDIDATE_RESOLUTION_RULE_VERSION,
        fact_path=fact_path,
    )


def validate_process_phase_event_fact_manifest(
    metadata: dict,
    metadata_path: Path,
    v2_path: Path,
    fact_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    return validate_process_phase_fact_manifest(
        metadata,
        metadata_path,
        v2_path,
        manifest_key="process_phase_event_fact_manifest",
        summary_prefix="process_phase_event_fact",
        fact_kind="process_phase_event_fact",
        required_columns=PROCESS_PHASE_EVENT_FACT_COLUMNS,
        schema_field="process_phase_event_schema_version",
        expected_schema_version=PROCESS_PHASE_EVENT_SCHEMA_VERSION,
        rule_field="confirmation_rule_version",
        expected_rule_version=PROCESS_PHASE_EVENT_RULE_VERSION,
        fact_path=fact_path,
    )


def _new_spot_image_linkage_summary(
    linkage_fact_path: Path | None,
    linkage_report_path: Path | None,
) -> dict[str, str]:
    return {
        "spot_image_linkage_fact_validation_source": "not_applicable",
        "spot_image_linkage_fact_override_provided": _bool_text(linkage_fact_path is not None),
        "spot_image_linkage_report_override_provided": _bool_text(linkage_report_path is not None),
        "spot_image_linkage_fact_manifest_fact_file": "",
        "spot_image_linkage_fact_manifest_report_file": "",
        "spot_image_linkage_fact_override_file": linkage_fact_path.name
        if linkage_fact_path is not None
        else "not provided",
        "spot_image_linkage_report_override_file": linkage_report_path.name
        if linkage_report_path is not None
        else "not provided",
        "spot_image_linkage_fact_verified_file": "not available",
        "spot_image_linkage_report_verified_file": "not available",
        "spot_image_linkage_fact_manifest_row_count": "unknown",
        "spot_image_linkage_fact_actual_row_count": "unknown",
        "spot_image_linkage_fact_row_count_match": "unknown",
        "spot_image_linkage_fact_manifest_sha256": "unknown",
        "spot_image_linkage_fact_actual_sha256": "unknown",
        "spot_image_linkage_fact_sha256_match": "unknown",
        "spot_image_linkage_manifest_source_csv_sha256": "unknown",
        "spot_image_linkage_source_csv_sha256_match": "unknown",
        "spot_image_linkage_manifest_spot_image_fact_sha256": "unknown",
        "spot_image_linkage_spot_image_fact_sha256_match": "unknown",
        "spot_image_linkage_report_sha256_match": "unknown",
        "spot_image_linkage_report_redaction_passed": "unknown",
        "spot_image_linkage_matched_rows": "unknown",
        "spot_image_linkage_ambiguous_rows": "unknown",
    }


def validate_spot_image_linkage_fact_manifest(
    metadata: dict,
    metadata_path: Path,
    v2_path: Path,
    *,
    spot_image_fact_path: Path | None = None,
    linkage_fact_path: Path | None = None,
    linkage_report_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    summary = _new_spot_image_linkage_summary(linkage_fact_path, linkage_report_path)
    manifest_key = "spot_image_linkage_fact_manifest"
    manifest = metadata.get(manifest_key)
    override_provided = linkage_fact_path is not None or linkage_report_path is not None
    if not isinstance(manifest, dict):
        if _posthoc_fact_manifest_required(metadata, manifest_key) or override_provided:
            if linkage_fact_path is None or linkage_report_path is None:
                return ["spot_image_linkage fact/report override must be provided together"], summary
        else:
            return [], summary
    else:
        summary["spot_image_linkage_fact_validation_source"] = (
            "override" if override_provided else "metadata_manifest"
        )

    failures: list[str] = []
    if isinstance(manifest, dict):
        if manifest.get("fact_kind") != "spot_image_linkage_fact":
            failures.append(f"{manifest_key}.fact_kind must be 'spot_image_linkage_fact'")
        if manifest.get("schema_version") != SPOT_IMAGE_LINKAGE_SCHEMA_VERSION:
            failures.append(f"{manifest_key}.schema_version must be {SPOT_IMAGE_LINKAGE_SCHEMA_VERSION!r}")
        if manifest.get("rule_version") != SPOT_IMAGE_LINKAGE_RULE_VERSION:
            failures.append(f"{manifest_key}.rule_version must be {SPOT_IMAGE_LINKAGE_RULE_VERSION!r}")
        if manifest.get("required_columns") != list(SPOT_IMAGE_LINKAGE_FACT_COLUMNS):
            failures.append(f"{manifest_key}.required_columns must match canonical fact columns")

        fact_path_text = str(manifest.get("fact_path") or "").strip()
        report_path_text = str(manifest.get("report_path") or "").strip()
        summary["spot_image_linkage_fact_manifest_fact_file"] = _path_basename_text(fact_path_text)
        summary["spot_image_linkage_fact_manifest_report_file"] = _path_basename_text(report_path_text)
        if not fact_path_text:
            failures.append(f"{manifest_key}.fact_path must be populated")
        if not report_path_text:
            failures.append(f"{manifest_key}.report_path must be populated")

        row_count = _parse_non_negative_int(manifest.get("row_count"))
        if row_count is None:
            failures.append(f"{manifest_key}.row_count must be a non-negative integer")
            row_count = 0
        summary["spot_image_linkage_fact_manifest_row_count"] = str(row_count)

        manifest_sha = manifest.get("sha256")
        if manifest_sha is not None and not _is_sha256_text(str(manifest_sha)):
            failures.append(f"{manifest_key}.sha256 must be null or lowercase SHA-256")
        summary["spot_image_linkage_fact_manifest_sha256"] = str(manifest_sha or "")

        source_sha = manifest.get("source_csv_sha256")
        if source_sha is not None and not _is_sha256_text(str(source_sha)):
            failures.append(f"{manifest_key}.source_csv_sha256 must be null or lowercase SHA-256")
        summary["spot_image_linkage_manifest_source_csv_sha256"] = str(source_sha or "")

        image_fact_sha = manifest.get("spot_image_fact_sha256")
        if image_fact_sha is not None and not _is_sha256_text(str(image_fact_sha)):
            failures.append(f"{manifest_key}.spot_image_fact_sha256 must be null or lowercase SHA-256")
        summary["spot_image_linkage_manifest_spot_image_fact_sha256"] = str(image_fact_sha or "")

    if linkage_fact_path is None and isinstance(manifest, dict):
        linkage_fact_path = Path(str(manifest.get("fact_path") or ""))
    if linkage_report_path is None and isinstance(manifest, dict):
        linkage_report_path = Path(str(manifest.get("report_path") or ""))

    if linkage_fact_path is None and linkage_report_path is None:
        return failures, summary
    if linkage_fact_path is None or linkage_report_path is None:
        failures.append("spot_image_linkage fact/report override must be provided together")
        return failures, summary

    summary["spot_image_linkage_fact_validation_source"] = (
        "override" if override_provided else "metadata_manifest"
    )
    summary["spot_image_linkage_fact_verified_file"] = linkage_fact_path.name
    summary["spot_image_linkage_report_verified_file"] = linkage_report_path.name
    if not linkage_fact_path.exists():
        failures.append("spot_image_linkage_fact path does not exist")
        return failures, summary
    if not linkage_report_path.exists():
        failures.append("spot_image_linkage_report path does not exist")
        return failures, summary

    selected_spot_image_fact_path = spot_image_fact_path or _spot_image_fact_path_from_metadata(metadata)
    if selected_spot_image_fact_path is None or not selected_spot_image_fact_path.exists():
        failures.append("spot_image_linkage requires a readable spot_image_fact.csv")
        return failures, summary

    output_failures, output_summary = validate_spot_image_linkage_outputs(
        source_csv_path=v2_path,
        spot_image_fact_path=selected_spot_image_fact_path,
        linkage_fact_path=linkage_fact_path,
        linkage_report_path=linkage_report_path,
    )
    summary.update(output_summary)
    failures.extend(output_failures)

    if isinstance(manifest, dict):
        manifest_row_count = summary["spot_image_linkage_fact_manifest_row_count"]
        row_count_matches = manifest_row_count == summary["spot_image_linkage_fact_actual_row_count"]
        summary["spot_image_linkage_fact_row_count_match"] = _bool_text(row_count_matches)
        if not row_count_matches and not override_provided:
            failures.append(
                f"{manifest_key}.row_count={manifest_row_count}, actual "
                f"spot_image_linkage_fact rows={summary['spot_image_linkage_fact_actual_row_count']}"
            )

        manifest_sha = summary["spot_image_linkage_fact_manifest_sha256"]
        actual_sha = summary["spot_image_linkage_fact_actual_sha256"]
        sha_matches = bool(manifest_sha and manifest_sha == actual_sha)
        summary["spot_image_linkage_fact_sha256_match"] = _bool_text(sha_matches)
        if manifest_sha and not sha_matches and not override_provided:
            failures.append(f"{manifest_key}.sha256 does not match linkage fact file")

        actual_source_sha = hashlib.sha256(v2_path.read_bytes()).hexdigest()
        source_sha = summary["spot_image_linkage_manifest_source_csv_sha256"]
        source_sha_matches = bool(source_sha and source_sha == actual_source_sha)
        summary["spot_image_linkage_source_csv_sha256_match"] = _bool_text(source_sha_matches)
        if source_sha and not source_sha_matches:
            failures.append(f"{manifest_key}.source_csv_sha256 does not match v2 CSV")

        actual_image_fact_sha = hashlib.sha256(selected_spot_image_fact_path.read_bytes()).hexdigest()
        image_fact_sha = summary["spot_image_linkage_manifest_spot_image_fact_sha256"]
        image_fact_sha_matches = bool(image_fact_sha and image_fact_sha == actual_image_fact_sha)
        summary["spot_image_linkage_spot_image_fact_sha256_match"] = _bool_text(image_fact_sha_matches)
        if image_fact_sha and not image_fact_sha_matches:
            failures.append(f"{manifest_key}.spot_image_fact_sha256 does not match spot_image_fact")

    return failures, summary


def _spot_image_fact_path_from_metadata(metadata: dict) -> Path | None:
    manifest = metadata.get("spot_image_fact_manifest")
    if not isinstance(manifest, dict):
        return None
    fact_path_text = str(manifest.get("fact_path") or "").strip()
    return Path(fact_path_text) if fact_path_text else None


def _parse_non_negative_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _is_sha256_text(value: str) -> bool:
    return bool(HEX_SHA256_RE.fullmatch(value.strip()))


def _is_unsafe_relative_path(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    normalized = text.replace("\\", "/")
    first_segment = normalized.split("/", 1)[0]
    if ":" in first_segment:
        return True
    if normalized.startswith("/"):
        return True
    return any(part in {"", ".", ".."} for part in normalized.split("/"))


def _is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


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


def validate(
    v1_path: Path | None,
    v2_path: Path,
    metadata_path: Path,
    spot_observation_fact_path: Path | None = None,
    require_current_server_promotion_profile: bool = False,
    spot_image_fact_path: Path | None = None,
    spot_image_fact_final_manifest_path: Path | None = None,
    changeover_candidate_resolution_fact_path: Path | None = None,
    process_phase_event_fact_path: Path | None = None,
    spot_image_linkage_fact_path: Path | None = None,
    spot_image_linkage_report_path: Path | None = None,
) -> int:
    failures: list[str] = []
    warnings: list[str] = []
    spot_observation_fact_summary = _new_spot_observation_fact_summary(spot_observation_fact_path)
    spot_image_fact_summary = _new_spot_image_fact_summary(
        spot_image_fact_path,
        spot_image_fact_final_manifest_path,
    )
    changeover_fact_summary = _new_process_phase_fact_summary(
        "changeover_candidate_resolution_fact",
        changeover_candidate_resolution_fact_path,
    )
    process_phase_fact_summary = _new_process_phase_fact_summary(
        "process_phase_event_fact",
        process_phase_event_fact_path,
    )
    spot_image_linkage_summary = _new_spot_image_linkage_summary(
        spot_image_linkage_fact_path,
        spot_image_linkage_report_path,
    )

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

    v2_schema = metadata.get("schema_metadata", {}).get("schema_version")
    if v2_schema not in SUPPORTED_CSV_SCHEMA_VERSIONS:
        failures.append(
            f"metadata schema_version is {v2_schema!r}, expected one of "
            f"{', '.join(sorted(SUPPORTED_CSV_SCHEMA_VERSIONS))}"
        )

    required_v2_columns = REQUIRED_V2_COLUMNS_BY_SCHEMA.get(v2_schema, REQUIRED_V2_COLUMNS)
    missing_v2 = [column for column in required_v2_columns if column not in v2_header]
    if missing_v2:
        failures.append(f"v2 header missing columns: {', '.join(missing_v2)}")

    if v2_schema in {CSV_SCHEMA_VERSION_V2_2, CSV_SCHEMA_VERSION_V2_3, CSV_SCHEMA_VERSION_V2_4}:
        operator_metadata_version = metadata.get("schema_metadata", {}).get("operator_metadata_version")
        if operator_metadata_version != "1.0.0":
            failures.append(
                f"metadata operator_metadata_version is {operator_metadata_version!r}, expected '1.0.0'"
            )

        operator_metadata = metadata.get("operator_metadata")
        if not isinstance(operator_metadata, dict):
            failures.append("metadata missing operator_metadata block")
        else:
            required_fields = operator_metadata.get("required_fields")
            if required_fields != ["product_no", "operator_mold_no"]:
                failures.append(f"operator_metadata.required_fields={required_fields!r}")

    if v2_schema in {CSV_SCHEMA_VERSION_V2_3, CSV_SCHEMA_VERSION_V2_4}:
        schema_metadata = metadata.get("schema_metadata", {})
        if schema_metadata.get("row_unique_key") != ["logger_service_instance_id", "sample_seq"]:
            failures.append("schema_metadata.row_unique_key must be ['logger_service_instance_id', 'sample_seq']")
        spot_key_scope = str(schema_metadata.get("spot_observation_key_scope") or "")
        if "not realtime CSV rows" not in spot_key_scope:
            failures.append("schema_metadata.spot_observation_key_scope must limit SPOT sequence uniqueness to spot_observation_fact")

        failures.extend(validate_shadow_enum_values(v2_rows, v2_header))
        failures.extend(validate_spot_sequence_values(v2_rows, v2_header))
        failures.extend(validate_temperature_value_origin_invariants(v2_rows, v2_header))
        failures.extend(validate_spot_invalid_sentinel_invariants(v2_rows, v2_header))
        if v2_schema == CSV_SCHEMA_VERSION_V2_4:
            failures.extend(
                validate_v2_4_operational_invariants(
                    v2_rows,
                    v2_header,
                    row_time_freshness_threshold_ms=_metadata_row_time_freshness_threshold_ms(metadata),
                )
            )
            failures.extend(
                validate_spot_configuration_snapshot(
                    metadata,
                    v2_rows,
                    v2_header,
                    require_current_server_promotion_profile=require_current_server_promotion_profile,
                )
            )
            spot_observation_fact_failures, spot_observation_fact_summary = (
                validate_spot_observation_fact_manifest(
                    metadata,
                    metadata_path,
                    v2_header,
                    v2_rows,
                    spot_observation_fact_path=spot_observation_fact_path,
                )
            )
            spot_image_fact_failures, spot_image_fact_summary = validate_spot_image_fact_manifest(
                metadata,
                metadata_path,
                spot_image_fact_path=spot_image_fact_path,
                spot_image_fact_final_manifest_path=spot_image_fact_final_manifest_path,
            )
            failures.extend(spot_observation_fact_failures)
            failures.extend(spot_image_fact_failures)
            changeover_fact_failures, changeover_fact_summary = (
                validate_changeover_candidate_resolution_fact_manifest(
                    metadata,
                    metadata_path,
                    v2_path,
                    fact_path=changeover_candidate_resolution_fact_path,
                )
            )
            process_phase_fact_failures, process_phase_fact_summary = validate_process_phase_event_fact_manifest(
                metadata,
                metadata_path,
                v2_path,
                fact_path=process_phase_event_fact_path,
            )
            spot_image_linkage_failures, spot_image_linkage_summary = (
                validate_spot_image_linkage_fact_manifest(
                    metadata,
                    metadata_path,
                    v2_path,
                    spot_image_fact_path=spot_image_fact_path,
                    linkage_fact_path=spot_image_linkage_fact_path,
                    linkage_report_path=spot_image_linkage_report_path,
                )
            )
            failures.extend(changeover_fact_failures)
            failures.extend(process_phase_fact_failures)
            failures.extend(spot_image_linkage_failures)

        shadow_metadata = metadata.get("spot_temperature_shadow_metadata")
        if not isinstance(shadow_metadata, dict):
            failures.append("metadata missing spot_temperature_shadow_metadata block")
        else:
            shadow_columns = shadow_metadata.get("shadow_columns")
            if not isinstance(shadow_columns, list):
                failures.append("spot_temperature_shadow_metadata.shadow_columns is missing or not a list")
            else:
                missing_shadow_columns = [
                    column for column in SPOT_TEMPERATURE_SHADOW_COLUMNS if column not in shadow_columns
                ]
                if missing_shadow_columns:
                    failures.append(
                        "spot_temperature_shadow_metadata.shadow_columns missing: "
                        + ", ".join(missing_shadow_columns)
                    )
            sentinel_map = shadow_metadata.get("sentinel_map")
            if not isinstance(sentinel_map, dict):
                failures.append("spot_temperature_shadow_metadata.sentinel_map is missing or not a dict")
            else:
                if sentinel_map.get("server_pc_verified") is not False:
                    failures.append("sentinel_map.server_pc_verified must be false during shadow validation")
                invalid_sentinel_values = set(sentinel_map.get("invalid_sentinel_values") or [])
                missing_invalid_sentinels = EXPECTED_SPOT_INVALID_SENTINEL_VALUES - invalid_sentinel_values
                if missing_invalid_sentinels:
                    failures.append(
                        "sentinel_map.invalid_sentinel_values missing documented values: "
                        + ", ".join(sorted(missing_invalid_sentinels))
                    )
                invalid_sentinel_meanings = sentinel_map.get("invalid_sentinel_meanings")
                if invalid_sentinel_meanings != EXPECTED_SPOT_INVALID_SENTINEL_MEANINGS:
                    failures.append(
                        "sentinel_map.invalid_sentinel_meanings must map 6553.4=under_range and 6553.5=over_range"
                    )
                documented_sentinels = sentinel_map.get("documented_temperature_sentinels")
                if documented_sentinels != {"under_range": "6553.4", "over_range": "6553.5"}:
                    failures.append("sentinel_map.documented_temperature_sentinels must match AMETEK REST API values")
                for key, expected_value in EXPECTED_SPOT_SENTINEL_PROVENANCE.items():
                    if sentinel_map.get(key) != expected_value:
                        failures.append(f"sentinel_map.{key} must be {expected_value!r}")
                if not str(sentinel_map.get("verified_at") or "").strip():
                    failures.append("sentinel_map.verified_at must record the verification date")
                if sentinel_map.get("pdf_verified") is not True:
                    failures.append("sentinel_map.pdf_verified must be true for documented AMETEK sentinel values")
                if sentinel_map.get("verified_no_target_values") not in ([], ()):
                    failures.append("sentinel_map.verified_no_target_values must remain empty until no-target is server-verified")
            policy = str(shadow_metadata.get("v2_3_policy") or "")
            if "v2.4.0" not in policy:
                failures.append("spot_temperature_shadow_metadata.v2_3_policy must mention v2.4.0+ operational fields")

    row_delta: int | str = "v1_not_provided"
    if v1_path is not None:
        row_delta = len(v2_rows) - len(v1_rows)
        if row_delta != 0:
            warnings.append(f"row count differs: v1={len(v1_rows)} v2={len(v2_rows)} delta={row_delta}")

    seq_ok, seq_detail = validate_sample_seq(v2_rows, v2_header)
    if not seq_ok:
        failures.append(seq_detail)

    required_metadata_fields = REQUIRED_METADATA_FIELDS_BY_SCHEMA.get(v2_schema, REQUIRED_METADATA_FIELDS_BY_SCHEMA[CSV_SCHEMA_VERSION_V2_2])
    for field_name, expected_status in required_metadata_fields.items():
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
    print(f"v1_file={_path_display(v1_path)}")
    print(f"v2_file={_path_display(v2_path)}")
    print(f"metadata_file={_path_display(metadata_path)}")
    print(f"spot_observation_fact_file={_path_display(spot_observation_fact_path)}")
    for key in (
        "spot_observation_fact_validation_source",
        "spot_observation_fact_override_provided",
        "spot_observation_fact_manifest_fact_file",
        "spot_observation_fact_override_file",
        "spot_observation_fact_verified_file",
        "spot_observation_fact_manifest_row_count",
        "spot_observation_fact_actual_row_count",
        "spot_observation_fact_row_count_match",
        "spot_observation_fact_manifest_distinct_observation_key_count",
        "spot_observation_fact_actual_distinct_observation_key_count",
        "spot_observation_fact_distinct_observation_key_count_match",
        "spot_observation_fact_manifest_first_poll_seq",
        "spot_observation_fact_actual_first_poll_seq",
        "spot_observation_fact_first_poll_seq_match",
        "spot_observation_fact_manifest_last_poll_seq",
        "spot_observation_fact_actual_last_poll_seq",
        "spot_observation_fact_last_poll_seq_match",
        "spot_observation_fact_manifest_poll_seq_gap_count",
        "spot_observation_fact_actual_poll_seq_gap_count",
        "spot_observation_fact_poll_seq_gap_count_match",
        "spot_observation_fact_manifest_sha256",
        "spot_observation_fact_actual_sha256",
        "spot_observation_fact_sha256_match",
        "spot_observation_fact_write_failure_count",
        "spot_observation_fact_spool_pending_count",
        "spot_observation_fact_realtime_rows_with_observation_key",
        "spot_observation_fact_linked_rows",
        "spot_observation_fact_missing_fact_key_rows",
        "spot_observation_fact_link_coverage_pct",
        "spot_observation_fact_diagnostic_source_mismatch_count",
    ):
        print(f"{key}={spot_observation_fact_summary.get(key, 'unknown')}")
    for key in (
        "spot_image_fact_validation_source",
        "spot_image_fact_override_provided",
        "spot_image_fact_final_manifest_provided",
        "spot_image_fact_final_manifest_file",
        "spot_image_fact_manifest_fact_file",
        "spot_image_fact_override_file",
        "spot_image_fact_verified_file",
        "spot_image_fact_manifest_row_count",
        "spot_image_fact_actual_row_count",
        "spot_image_fact_row_count_match",
        "spot_image_fact_manifest_sha256",
        "spot_image_fact_actual_sha256",
        "spot_image_fact_sha256_match",
    ):
        print(f"{key}={spot_image_fact_summary[key]}")
    for summary in (changeover_fact_summary, process_phase_fact_summary):
        for key in (
            "validation_source",
            "override_provided",
            "manifest_fact_file",
            "override_file",
            "verified_file",
            "manifest_row_count",
            "actual_row_count",
            "row_count_match",
            "manifest_sha256",
            "actual_sha256",
            "sha256_match",
            "manifest_source_csv_sha256",
            "actual_source_csv_sha256",
            "source_csv_sha256_match",
        ):
            matching_key = next(summary_key for summary_key in summary if summary_key.endswith(f"_{key}"))
            print(f"{matching_key}={summary[matching_key]}")
    for key in (
        "spot_image_linkage_fact_validation_source",
        "spot_image_linkage_fact_override_provided",
        "spot_image_linkage_report_override_provided",
        "spot_image_linkage_fact_manifest_fact_file",
        "spot_image_linkage_fact_manifest_report_file",
        "spot_image_linkage_fact_override_file",
        "spot_image_linkage_report_override_file",
        "spot_image_linkage_fact_verified_file",
        "spot_image_linkage_report_verified_file",
        "spot_image_linkage_fact_manifest_row_count",
        "spot_image_linkage_fact_actual_row_count",
        "spot_image_linkage_fact_row_count_match",
        "spot_image_linkage_fact_manifest_sha256",
        "spot_image_linkage_fact_actual_sha256",
        "spot_image_linkage_fact_sha256_match",
        "spot_image_linkage_manifest_source_csv_sha256",
        "spot_image_linkage_source_csv_sha256_match",
        "spot_image_linkage_manifest_spot_image_fact_sha256",
        "spot_image_linkage_spot_image_fact_sha256_match",
        "spot_image_linkage_report_sha256_match",
        "spot_image_linkage_report_redaction_passed",
        "spot_image_linkage_matched_rows",
        "spot_image_linkage_ambiguous_rows",
    ):
        print(f"{key}={spot_image_linkage_summary[key]}")
    print(f"current_server_promotion_profile_required={require_current_server_promotion_profile}")
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
    require_current_server_promotion_profile: bool = False,
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
            require_current_server_promotion_profile=require_current_server_promotion_profile,
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
        "--spot-observation-fact",
        type=Path,
        help="Optional spot_observation_fact.csv for SPOT diagnostic invariant validation",
    )
    parser.add_argument(
        "--spot-image-fact",
        type=Path,
        help=(
            "Optional portable spot_image_fact.csv override. The file is validated directly "
            "and metadata row/hash match is reported without requiring the original manifest path."
        ),
    )
    parser.add_argument(
        "--spot-image-fact-final-manifest",
        type=Path,
        help=(
            "Optional spot_image_fact_manifest.final.json. When provided, its row count and SHA-256 "
            "must strictly match the verified fact file, even with --spot-image-fact."
        ),
    )
    parser.add_argument(
        "--changeover-candidate-resolution-fact",
        type=Path,
        help=(
            "Optional portable changeover_candidate_resolution_fact.csv override. The file is validated directly "
            "and metadata row/hash match is reported without requiring the original manifest path."
        ),
    )
    parser.add_argument(
        "--process-phase-event-fact",
        type=Path,
        help=(
            "Optional portable process_phase_event_fact.csv override. The file is validated directly "
            "and metadata row/hash match is reported without requiring the original manifest path."
        ),
    )
    parser.add_argument(
        "--spot-image-linkage-fact",
        type=Path,
        help=(
            "Optional portable spot_image_linkage_fact.csv override. Must be paired with "
            "--spot-image-linkage-report."
        ),
    )
    parser.add_argument(
        "--spot-image-linkage-report",
        type=Path,
        help=(
            "Optional portable spot_image_linkage_report.json override. Must be paired with "
            "--spot-image-linkage-fact."
        ),
    )
    parser.add_argument(
        "--require-current-server-promotion-profile",
        action="store_true",
        help="Also require the known current server SPOT promotion profile values, not only generic schema/range invariants",
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
            require_current_server_promotion_profile=args.require_current_server_promotion_profile,
        )

    if args.v2 is None or args.metadata is None:
        parser.error("--v2 and --metadata are required for single-file validation")
    return validate(
        args.v1,
        args.v2,
        args.metadata,
        args.spot_observation_fact,
        require_current_server_promotion_profile=args.require_current_server_promotion_profile,
        spot_image_fact_path=args.spot_image_fact,
        spot_image_fact_final_manifest_path=args.spot_image_fact_final_manifest,
        changeover_candidate_resolution_fact_path=args.changeover_candidate_resolution_fact,
        process_phase_event_fact_path=args.process_phase_event_fact,
        spot_image_linkage_fact_path=args.spot_image_linkage_fact,
        spot_image_linkage_report_path=args.spot_image_linkage_report,
    )


if __name__ == "__main__":
    raise SystemExit(main())
