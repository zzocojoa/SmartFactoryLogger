import math
import re
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from typing import Optional, Dict, Any

CSV_INJECTION_PREFIXES = ("=", "+", "-", "@")
PRODUCT_NO_RE = re.compile(r"^\d{1,40}$")
OPERATOR_MOLD_NO_RE = re.compile(r"^\d{1,32}$")


FACTORY_DATA_ENUM_VALUES = {
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
    "spot_device_status_code": {"temperature_under_range", "temperature_over_range"},
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


def _normalize_operator_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value)


def _has_control_character(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


class OperatorMetadataBase(BaseModel):
    product_no: str = ""
    operator_mold_no: str = ""

    @field_validator("product_no", "operator_mold_no", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return _normalize_operator_text(value)

    @field_validator("product_no")
    @classmethod
    def validate_product_no(cls, value: str) -> str:
        if not value.strip():
            return ""
        if _has_control_character(value):
            raise ValueError("product_no must not contain control characters")
        if value[0] in CSV_INJECTION_PREFIXES:
            raise ValueError("product_no must not start with a CSV formula character")
        if not PRODUCT_NO_RE.match(value):
            raise ValueError("product_no must contain digits only")
        return value

    @field_validator("operator_mold_no")
    @classmethod
    def validate_operator_mold_no(cls, value: str) -> str:
        if not value.strip():
            return ""
        if _has_control_character(value):
            raise ValueError("operator_mold_no must not contain control characters")
        if value[0] in CSV_INJECTION_PREFIXES:
            raise ValueError("operator_mold_no must not start with a CSV formula character")
        if not OPERATOR_MOLD_NO_RE.match(value):
            raise ValueError("operator_mold_no must contain digits only")
        return value


class OperatorMetadataUpdate(OperatorMetadataBase):
    @model_validator(mode="after")
    def require_required_fields(self):
        if not self.product_no or not self.operator_mold_no:
            raise ValueError("product_no and operator_mold_no are required")
        return self


class OperatorMetadataHistoryEntry(OperatorMetadataBase):
    updated_at: Optional[str] = None

    @model_validator(mode="after")
    def require_required_fields(self):
        if not self.product_no or not self.operator_mold_no:
            raise ValueError("history product_no and operator_mold_no are required")
        return self


class OperatorMetadata(OperatorMetadataBase):
    valid: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    updated_at: Optional[str] = None
    source: str = "operator_input"
    history: list[OperatorMetadataHistoryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_validity(self):
        missing: list[str] = []
        if not self.product_no:
            missing.append("product_no")
        if not self.operator_mold_no:
            missing.append("operator_mold_no")
        self.missing_fields = missing
        self.valid = not missing
        return self

class FactoryData(BaseModel):
    # System
    Time: str
    Status: str = "Running"
    timestamp_ms: Optional[int] = None
    captured_at_extruder: Optional[float] = None
    captured_at_ls: Optional[float] = None
    captured_at_spot: Optional[float] = None
    extruder_snapshot_error: Optional[str] = None
    ls_snapshot_error: Optional[str] = None
    spot_snapshot_error: Optional[str] = None

    # KPIs
    Speed: Optional[float] = None
    Press: Optional[float] = None
    Count: Optional[int] = None
    EndPos: Optional[float] = None
    MainRamPosition_D0010: Optional[float] = None
    ContainerPosition_D0012: Optional[float] = None
    Billet_Length: Optional[float] = None
    Die_ID: Optional[str] = None
    Billet_Cycle_ID: Optional[str] = None
    Die_ID_derived: Optional[bool] = None
    Billet_Cycle_ID_derived: Optional[bool] = None
    derivation_version: Optional[str] = None
    cycle_confidence: Optional[float] = None
    cycle_state: Optional[str] = None
    Product_No_operator: Optional[str] = None
    Mold_No_operator: Optional[str] = None
    operator_metadata_valid: Optional[bool] = None
    operator_metadata_missing_fields: Optional[list[str]] = None
    operator_metadata_updated_at: Optional[str] = None

    # Temperatures
    Spot: Optional[float] = None
    Temp_F: Optional[float] = None
    Temp_B: Optional[float] = None
    Billet_Temp: Optional[float] = None

    # SPOT temperature shadow diagnostics (v2.3 instrumentation)
    extruder_process_state_online: Optional[str] = None
    process_state_online_rule_version: Optional[str] = None
    spot_target_state_observed_shadow: Optional[str] = None
    spot_target_state_observed_source: Optional[str] = None
    label_validation_state: Optional[str] = None
    temperature_status_shadow: Optional[str] = None
    temperature_status_rule_version: Optional[str] = None
    spot_poll_status: Optional[str] = None
    spot_raw_validity: Optional[str] = None
    spot_cache_status: Optional[str] = None
    spot_source_freshness: Optional[str] = None
    temperature_value_origin: Optional[str] = None
    cache_fallback_allowed: Optional[bool] = None
    spot_service_instance_id: Optional[str] = None
    spot_service_started_at: Optional[str] = None
    spot_poll_seq: Optional[int] = None
    spot_observation_seq: Optional[int] = None
    spot_temperature_observed_c: Optional[float] = None
    spot_temperature_raw: Optional[str] = None
    spot_temperature_raw_truncated: Optional[bool] = None
    spot_raw_payload_hash: Optional[str] = None
    spot_raw_payload_encoding: Optional[str] = None
    spot_http_status_code: Optional[int] = None
    spot_device_status_code: Optional[str] = None
    spot_error_code: Optional[str] = None
    spot_poll_duration_ms: Optional[float] = None
    spot_response_content_length: Optional[int] = None
    spot_last_poll_started_at: Optional[str] = None
    spot_last_poll_completed_at: Optional[str] = None
    spot_last_response_at: Optional[str] = None
    spot_last_valid_value_at: Optional[str] = None
    spot_snapshot_age_ms: Optional[float] = None
    spot_value_age_ms: Optional[float] = None

    # SPOT temperature operational diagnostics (v2.4 candidate contract)
    temperature_output_status: Optional[str] = None
    temperature_unavailable_reason: Optional[str] = None
    temperature_expectedness_candidate: Optional[str] = None
    temperature_under_range_cause_candidate: Optional[str] = None
    temperature_cause_confidence: Optional[float] = None
    temperature_cause_evidence_codes: Optional[str] = None
    spot_effective_age_ms_at_row: Optional[float] = None
    spot_effective_freshness_at_row: Optional[str] = None
    spot_effective_value_age_ms_at_row: Optional[float] = None
    spot_row_age_clock_status: Optional[str] = None
    process_phase_candidate: Optional[str] = None
    process_phase_rule_version: Optional[str] = None
    phase_confirmation_state: Optional[str] = None
    process_segment_id: Optional[str] = None
    changeover_candidate_id: Optional[str] = None
    spot_observation_key: Optional[str] = None
    spot_diagnostic_evidence_codes: Optional[str] = None
    alarmstatus: Optional[str] = None
    signalpc: Optional[float] = None
    low_signal_alarm_enabled: Optional[bool] = None
    low_signal_threshold_pc: Optional[float] = None
    low_signal_comparator: Optional[str] = None
    peak_picker_enabled: Optional[bool] = None
    peak_picker_off_mode: Optional[str] = None
    # Molds
    Mold1: Optional[float] = None
    Mold2: Optional[float] = None
    Mold3: Optional[float] = None
    Mold4: Optional[float] = None
    Mold5: Optional[float] = None
    Mold6: Optional[float] = None

    # Environment
    At_Temp: Optional[float] = None
    At_Pre: Optional[float] = None

    # Computed status (backend-derived)
    Computed: Optional[Dict[str, Any]] = None

    @field_validator(
        "extruder_process_state_online",
        "spot_target_state_observed_shadow",
        "spot_target_state_observed_source",
        "label_validation_state",
        "temperature_status_shadow",
        "spot_poll_status",
        "spot_raw_validity",
        "spot_cache_status",
        "spot_source_freshness",
        "temperature_value_origin",
        "spot_device_status_code",
        "temperature_output_status",
        "temperature_unavailable_reason",
        "temperature_expectedness_candidate",
        "temperature_under_range_cause_candidate",
        "spot_effective_freshness_at_row",
        "spot_row_age_clock_status",
        "process_phase_candidate",
        "phase_confirmation_state",
        mode="before",
    )
    @classmethod
    def validate_shadow_enum(cls, value, info: ValidationInfo):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError(f"{info.field_name} must be one of configured enum values")
        text_value = str(value)
        allowed = FACTORY_DATA_ENUM_VALUES[info.field_name]
        if text_value not in allowed:
            raise ValueError(f"{info.field_name}={text_value!r} is not in {sorted(allowed)!r}")
        return text_value

    @field_validator(
        "spot_poll_seq",
        "spot_observation_seq",
        "spot_http_status_code",
        "spot_response_content_length",
        mode="before",
    )
    @classmethod
    def coerce_non_negative_int(cls, value, info: ValidationInfo):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            val = int(value)
        except Exception:
            return None
        if val < 0:
            return None
        return val

    @model_validator(mode="after")
    def validate_spot_sequence_order(self):
        if (
            self.spot_poll_seq is not None
            and self.spot_observation_seq is not None
            and self.spot_observation_seq > self.spot_poll_seq
        ):
            raise ValueError("spot_observation_seq must be less than or equal to spot_poll_seq")
        return self

    @field_validator(
        "Speed",
        "Press",
        "EndPos",
        "MainRamPosition_D0010",
        "ContainerPosition_D0012",
        "Billet_Length",
        "Temp_F",
        "Temp_B",
        "Billet_Temp",
        "Mold1",
        "Mold2",
        "Mold3",
        "Mold4",
        "Mold5",
        "Mold6",
        "At_Temp",
        "At_Pre",
        "Spot",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def coerce_float(cls, value, info: ValidationInfo):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            val = float(value)
        except Exception:
            return None
        if not math.isfinite(val):
            return None
        name = info.field_name

        if name in {"At_Temp"}:
            if not (-40 <= val <= 100):
                return None
            return val
        if name in {"At_Pre"}:
            if not (0 <= val <= 100):
                return None
            return val
        if name in {"Spot"}:
            if val < 0 or val > 2000:
                return None
            return val
        if name in {"Temp_F", "Temp_B"}:
            if not (0 <= val <= 1000):
                return None
            return val
        if name in {"Billet_Temp", "Mold1", "Mold2", "Mold3", "Mold4", "Mold5", "Mold6"}:
            if not (0 <= val <= 1000):
                return None
            return val
        if val < 0:
            return None
        return val

    @field_validator("Count", mode="before")
    @classmethod
    def coerce_int(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            val = int(value)
        except Exception:
            return None
        if val < 0:
            return None
        return val

class SystemStatus(BaseModel):
    connection: bool
    mode: str  # REAL / MOCK
    message: str


class FactoryDataHistorySample(BaseModel):
    timestamp_ms: int
    data: FactoryData


class FactoryDataHistoryResponse(BaseModel):
    samples: list[FactoryDataHistorySample]
    oldest_timestamp_ms: Optional[int] = None
    newest_timestamp_ms: Optional[int] = None
    history_instance_id: str
    truncated: bool
