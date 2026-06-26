from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import re
from decimal import Decimal, InvalidOperation
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
EXPECTED_SPOT_CONFIGURATION_SNAPSHOT = {
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
        output_status = (
            row[output_status_index].strip()
            if output_status_index is not None and output_status_index < len(row)
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
                elif not (
                    cache_status == "available_not_used"
                    and freshness == "stale"
                    and (not output_status or output_status == "stale")
                ):
                    failures.append(
                        f"row {row_number} origin none permits populated spot_temperature_observed_c "
                        "only for stale available_not_used rows"
                    )

    return failures


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

        expected_values = {
            "spot_poll_status": "success",
            "spot_device_status_code": expected_device_status,
            "spot_error_code": "",
            "cache_fallback_allowed": "false",
            "temperature_status_shadow": "invalid_value",
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
        "die_change_candidate",
        "setup_alignment_candidate",
        "changeover_candidate",
        "production_stabilizing",
        "idle_candidate",
        "unknown",
    },
    "phase_confirmation_state": {"realtime_candidate", "unknown"},
}


def validate_v2_4_operational_invariants(rows: list[list[str]], header: list[str]) -> list[str]:
    required_columns = [
        "Temperature",
        "spot_raw_validity",
        "spot_device_status_code",
        "spot_effective_freshness_at_row",
        "temperature_output_status",
        "temperature_unavailable_reason",
        "temperature_under_range_cause_candidate",
        "temperature_cause_confidence",
        "temperature_cause_evidence_codes",
        "process_phase_candidate",
        "spot_observation_key",
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
        raw_validity = row[indices["spot_raw_validity"]].strip()
        device_status = row[indices["spot_device_status_code"]].strip()
        row_freshness = row[indices["spot_effective_freshness_at_row"]].strip()
        output_status = row[indices["temperature_output_status"]].strip()
        unavailable_reason = row[indices["temperature_unavailable_reason"]].strip()
        cause = row[indices["temperature_under_range_cause_candidate"]].strip()
        confidence = row[indices["temperature_cause_confidence"]].strip()
        evidence_codes = _parse_json_string_list(row[indices["temperature_cause_evidence_codes"]].strip())

        if output_status and output_status != "valid" and temperature:
            failures.append(f"row {row_number} non-valid temperature_output_status requires blank Temperature")
        if row_freshness == "stale":
            if output_status != "stale":
                failures.append(f"row {row_number} stale freshness requires temperature_output_status=stale")
            if unavailable_reason != "stale_observation":
                failures.append(f"row {row_number} stale freshness requires temperature_unavailable_reason=stale_observation")
        if raw_validity == "invalid_sentinel" and row_freshness != "stale":
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
    return failures


def validate_spot_configuration_snapshot(metadata: dict, rows: list[list[str]], header: list[str]) -> list[str]:
    failures: list[str] = []
    snapshot = metadata.get("spot_configuration_snapshot")
    if not isinstance(snapshot, dict):
        return ["metadata missing spot_configuration_snapshot block"]

    for key, expected in EXPECTED_SPOT_CONFIGURATION_SNAPSHOT.items():
        actual = snapshot.get(key)
        if isinstance(expected, float):
            parsed = _parse_finite_float(actual)
            if parsed is None or abs(parsed - expected) > 1e-9:
                failures.append(f"spot_configuration_snapshot.{key} must be {expected!r}")
        elif actual != expected:
            failures.append(f"spot_configuration_snapshot.{key} must be {expected!r}")

    threshold = _parse_finite_float(snapshot.get("low_signal_threshold_pc"))
    if threshold is None or not 0.0 <= threshold <= 100.0:
        failures.append("spot_configuration_snapshot.low_signal_threshold_pc must be 0.0..100.0")
    comparator = str(snapshot.get("low_signal_comparator") or "").strip().lower()
    if comparator not in {"lt", "lte", "unknown"}:
        failures.append("spot_configuration_snapshot.low_signal_comparator must be lt/lte/unknown")
    if not isinstance(snapshot.get("low_signal_alarm_enabled"), bool):
        failures.append("spot_configuration_snapshot.low_signal_alarm_enabled must be boolean")

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
    return failures


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
            failures.extend(validate_v2_4_operational_invariants(v2_rows, v2_header))
            failures.extend(validate_spot_configuration_snapshot(metadata, v2_rows, v2_header))

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
