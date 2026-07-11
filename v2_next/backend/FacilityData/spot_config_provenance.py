from __future__ import annotations

import configparser
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from backend.version import validate_git_commit


SPOT_CONFIG_REVISION = "spot-config-provenance-v1"
DEVICE_CONFIG_READBACK_STATUSES = frozenset(
    {"matched", "mismatch", "partial", "not_supported", "not_attempted", "error"}
)
CONFIG_ATTESTATION_STATUSES = frozenset(
    {
        "verified",
        "not_requested",
        "invalid_metadata",
        "fingerprint_mismatch",
        "device_readback_blocked",
    }
)
CONFIG_DRIFT_FIELDS = frozenset(
    {
        "config_attestation_metadata",
        "build_git_commit",
        "spot_config_fingerprint_sha256",
        "device_config_readback_status",
    }
)
_BLOCKING_READBACK_STATUSES = frozenset({"mismatch", "partial", "not_attempted", "error"})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", re.ASCII)
_OPERATOR_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)
_SENSITIVE_CONFIG_KEY_PARTS = (
    "api_key",
    "apikey",
    "auth_header",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)
_ATTESTATION_CONFIG_KEYS = frozenset(
    {
        ("spot", "config_operator_verified"),
        ("spot", "config_verified_at"),
        ("spot", "config_verified_by"),
        ("spot", "config_verified_fingerprint_sha256"),
    }
)


def validate_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if _SHA256_PATTERN.fullmatch(normalized) is None:
        return None
    return normalized


def compute_settings_file_sha256(path: Path | str | None) -> str:
    """Hash canonical settings while excluding the attestation fields themselves.

    Excluding attestation keys prevents a circular fingerprint: writing the approved
    fingerprint into config.ini must not alter the value being approved.
    """
    if path is None:
        return ""
    config_path = Path(path)
    try:
        raw = config_path.read_bytes()
    except OSError:
        return ""

    text: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return ""

    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read_string(text)
    except configparser.Error:
        return ""

    canonical: dict[str, dict[str, str]] = {}
    for section in sorted(parser.sections(), key=str.casefold):
        normalized_section = section.strip().casefold()
        values: dict[str, str] = {}
        for key, value in sorted(parser.items(section, raw=True), key=lambda item: item[0].casefold()):
            normalized_key = key.strip().casefold()
            if (normalized_section, normalized_key) in _ATTESTATION_CONFIG_KEYS:
                continue
            if any(part in normalized_key for part in _SENSITIVE_CONFIG_KEY_PARTS):
                continue
            values[normalized_key] = str(value).strip()
        canonical[normalized_section] = values
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_spot_config_fingerprint_payload(
    config_source: object,
    *,
    runtime_git_commit: str | None,
    settings_file_sha256: str,
) -> dict[str, Any]:
    return {
        "spot_config_revision": SPOT_CONFIG_REVISION,
        "build_git_commit": validate_git_commit(runtime_git_commit) or "",
        "settings_file_sha256": validate_sha256(settings_file_sha256) or "",
        "spot_ip": _text_attr(config_source, "SPOT_IP"),
        "spot_model_info": _text_attr(config_source, "SPOT_MODEL_INFO"),
        "spot_app_mode": _text_attr(config_source, "SPOT_APP_MODE"),
        "spot_range_min_c": _finite_float_attr(config_source, "SPOT_RANGE_MIN_C"),
        "spot_range_max_c": _finite_float_attr(config_source, "SPOT_RANGE_MAX_C"),
        "spot_analog_4ma_c": _finite_float_attr(config_source, "SPOT_ANALOG_4MA_C"),
        "spot_analog_20ma_c": _finite_float_attr(config_source, "SPOT_ANALOG_20MA_C"),
        "low_signal_alarm_enabled": _bool_attr(config_source, "SPOT_LOW_SIGNAL_ALARM_ENABLED"),
        "low_signal_threshold_pc": _finite_float_attr(config_source, "SPOT_LOW_SIGNAL_THRESHOLD_PC"),
        "low_signal_comparator": _text_attr(config_source, "SPOT_LOW_SIGNAL_COMPARATOR").lower(),
        "low_signal_comparator_configured_verified": _bool_attr(
            config_source, "SPOT_LOW_SIGNAL_COMPARATOR_VERIFIED"
        ),
        "peak_picker_enabled": _bool_attr(config_source, "SPOT_PEAK_PICKER_ENABLED"),
        "limiter_enabled": _bool_attr(config_source, "SPOT_LIMITER_ENABLED"),
        "averager_enabled": _bool_attr(config_source, "SPOT_AVERAGER_ENABLED"),
        "modemaster_enabled": _bool_attr(config_source, "SPOT_MODEMASTER_ENABLED"),
        "ratio_raw_enabled": _bool_attr(config_source, "SPOT_RATIO_RAW_ENABLED"),
        "window_obscuration_pc": _finite_float_attr(config_source, "SPOT_WINDOW_OBSCURATION_PC"),
        "focus_mm": _finite_float_attr(config_source, "SPOT_FOCUS_MM"),
        "diagnostics_collection_mode": _text_attr(
            config_source, "SPOT_DIAGNOSTICS_COLLECTION_MODE", "async_fact_only"
        ),
    }


def compute_spot_config_fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_spot_configuration_snapshot(
    config_source: object,
    *,
    runtime_git_commit: str | None,
    captured_at: str | None = None,
    device_readback_status: str = "not_supported",
    device_fingerprint_sha256: str | None = None,
) -> dict[str, Any]:
    settings_hash = compute_settings_file_sha256(getattr(config_source, "CONFIG_PATH", None))
    fingerprint_payload = build_spot_config_fingerprint_payload(
        config_source,
        runtime_git_commit=runtime_git_commit,
        settings_file_sha256=settings_hash,
    )
    fingerprint = compute_spot_config_fingerprint(fingerprint_payload)
    requested = _bool_attr(config_source, "SPOT_CONFIG_OPERATOR_VERIFIED")
    verified_at = _valid_utc_timestamp(_text_attr(config_source, "SPOT_CONFIG_VERIFIED_AT"))
    verified_by = _valid_operator_id(_text_attr(config_source, "SPOT_CONFIG_VERIFIED_BY"))
    verified_fingerprint = validate_sha256(
        getattr(config_source, "SPOT_CONFIG_VERIFIED_FINGERPRINT_SHA256", None)
    )
    readback_status = str(device_readback_status or "not_attempted").strip().lower()
    if readback_status not in DEVICE_CONFIG_READBACK_STATUSES:
        readback_status = "error"
    device_fingerprint = validate_sha256(device_fingerprint_sha256)
    if readback_status == "matched":
        if device_fingerprint is None:
            readback_status = "partial"
        elif not hmac.compare_digest(device_fingerprint, fingerprint):
            readback_status = "mismatch"

    fingerprint_matches = bool(
        verified_fingerprint and hmac.compare_digest(verified_fingerprint, fingerprint)
    )
    build_commit_valid = bool(fingerprint_payload["build_git_commit"])
    attestation_metadata_valid = bool(
        verified_at and verified_by and verified_fingerprint and build_commit_valid
    )
    readback_allows_verification = readback_status not in _BLOCKING_READBACK_STATUSES
    effective_verified = bool(
        requested
        and attestation_metadata_valid
        and fingerprint_matches
        and readback_allows_verification
    )

    drift_fields: list[str] = []
    if requested and not (verified_at and verified_by and verified_fingerprint):
        drift_fields.append("config_attestation_metadata")
    if requested and not build_commit_valid:
        drift_fields.append("build_git_commit")
    elif requested and verified_fingerprint and not fingerprint_matches:
        drift_fields.append("spot_config_fingerprint_sha256")
    if readback_status in _BLOCKING_READBACK_STATUSES:
        drift_fields.append("device_config_readback_status")

    if effective_verified:
        attestation_status = "verified"
    elif not requested:
        attestation_status = "not_requested"
    elif not attestation_metadata_valid:
        attestation_status = "invalid_metadata"
    elif not fingerprint_matches:
        attestation_status = "fingerprint_mismatch"
    else:
        attestation_status = "device_readback_blocked"

    snapshot = dict(fingerprint_payload)
    snapshot.update(
        {
            "low_signal_comparator_verified": bool(
                fingerprint_payload["low_signal_comparator_configured_verified"]
                and effective_verified
            ),
            "low_signal_config_source": _text_attr(config_source, "SPOT_LOW_SIGNAL_CONFIG_SOURCE"),
            "config_source": "runtime_config_attestation",
            "config_captured_at": captured_at or _utc_now_iso(),
            "config_operator_verified_requested": requested,
            "config_operator_verified": effective_verified,
            "config_attestation_status": attestation_status,
            "spot_config_fingerprint_sha256": fingerprint,
            "spot_config_verified_at": verified_at,
            "spot_config_verified_by": verified_by,
            "spot_config_verified_fingerprint_sha256": verified_fingerprint or "",
            "device_config_readback_status": readback_status,
            "device_config_fingerprint_sha256": device_fingerprint or "",
            "config_drift_detected": bool(drift_fields),
            "config_drift_fields": drift_fields,
            "spot_ratio_raw_enabled": fingerprint_payload["ratio_raw_enabled"],
        }
    )
    return snapshot


def _text_attr(config_source: object, name: str, default: str = "") -> str:
    return str(getattr(config_source, name, default) or default).strip()


def _bool_attr(config_source: object, name: str) -> bool:
    return bool(getattr(config_source, name, False))


def _finite_float_attr(config_source: object, name: str) -> float | None:
    value = getattr(config_source, name, None)
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _valid_utc_timestamp(value: str) -> str:
    if not value:
        return ""
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return ""
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        return ""
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_operator_id(value: str) -> str:
    if _OPERATOR_ID_PATTERN.fullmatch(value) is None:
        return ""
    return value


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
