from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from backend.FacilityData.spot_observation_fact import build_spot_observation_key


SPOT_IMAGE_FACT_COLUMNS = [
    "spot_image_capture_id",
    "spot_image_captured_at",
    "spot_image_source_url_hash",
    "spot_image_path",
    "spot_image_sha256",
    "spot_image_size_bytes",
    "spot_image_mime",
    "spot_image_width",
    "spot_image_height",
    "spot_image_status",
    "spot_image_source",
    "spot_image_age_ms",
    "spot_image_linked_observation_key",
    "spot_service_instance_id",
    "spot_poll_seq_nearest",
    "sample_seq_nearest",
    "timestamp_utc_nearest",
    "temperature_output_status_nearest",
    "temperature_unavailable_reason_nearest",
    "temperature_under_range_cause_candidate_nearest",
    "process_phase_candidate_nearest",
    "signalpc_nearest",
    "alarmstatus_nearest",
    "d1temperature_nearest",
    "d2temperature_nearest",
    "e1out_nearest",
    "e2out_nearest",
    "actuator_position_nearest",
    "focus_mm",
    "low_signal_threshold_pc",
    "peak_picker_enabled",
]


@dataclass
class SpotImageCaptureWriter:
    log_path: Path
    capture_root: Path
    retention_days: int = 7
    fact_filename: str = "spot_image_fact.csv"
    failure_count: int = 0
    written_count: int = 0
    last_cleanup_at: float = 0.0

    @property
    def fact_path(self) -> Path:
        return self.log_path / self.fact_filename

    def write_capture(
        self,
        *,
        image_bytes: bytes,
        captured_at: float,
        source_url: str,
        source: str,
        image_age_ms: Optional[float],
        observation_snapshot: Optional[Mapping[str, Any]],
    ) -> dict[str, str]:
        sha256 = hashlib.sha256(image_bytes).hexdigest()
        captured_dt = datetime.fromtimestamp(captured_at, timezone.utc)
        captured_iso = captured_dt.isoformat().replace("+00:00", "Z")
        sha12 = sha256[:12]
        capture_id = f"spotimg_{captured_dt.strftime('%Y%m%dT%H%M%S%fZ')}_{sha12}"
        mime, width, height, extension = image_metadata(image_bytes)
        relative_path = self._relative_image_path(captured_dt, capture_id, extension)
        output_path = self.capture_root / captured_dt.strftime("%Y") / captured_dt.strftime("%m") / captured_dt.strftime("%d")
        output_path.mkdir(parents=True, exist_ok=True)
        image_path = output_path / f"{capture_id}{extension}"
        tmp_path = image_path.with_suffix(f"{image_path.suffix}.tmp")
        tmp_path.write_bytes(image_bytes)
        tmp_path.replace(image_path)

        fact = build_spot_image_fact(
            capture_id=capture_id,
            captured_iso=captured_iso,
            source_url=source_url,
            relative_path=relative_path.as_posix(),
            sha256=sha256,
            size_bytes=len(image_bytes),
            mime=mime,
            width=width,
            height=height,
            source=source,
            image_age_ms=image_age_ms,
            observation_snapshot=observation_snapshot,
        )
        self._append_fact(fact)
        self.written_count += 1
        self._cleanup_retention(time.time())
        return fact

    def _relative_image_path(self, captured_dt: datetime, capture_id: str, extension: str) -> Path:
        try:
            base_path = self.capture_root.resolve().relative_to(self.log_path.resolve())
        except ValueError:
            base_path = Path(self.capture_root.name or "spot_images")
        return (
            base_path
            / captured_dt.strftime("%Y")
            / captured_dt.strftime("%m")
            / captured_dt.strftime("%d")
            / f"{capture_id}{extension}"
        )

    def _append_fact(self, fact: Mapping[str, str]) -> None:
        self.log_path.mkdir(parents=True, exist_ok=True)
        write_header = self._prepare_fact_file_for_append()
        with self.fact_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SPOT_IMAGE_FACT_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(fact)

    def _prepare_fact_file_for_append(self) -> bool:
        if not self.fact_path.exists() or self.fact_path.stat().st_size == 0:
            return True
        try:
            with self.fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                existing_header = next(csv.reader(handle), [])
        except (OSError, UnicodeError, csv.Error):
            existing_header = []
        if existing_header == SPOT_IMAGE_FACT_COLUMNS:
            return False
        archive_path = self.fact_path.with_name(
            f"{self.fact_path.stem}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.schema-mismatch.csv"
        )
        self.fact_path.rename(archive_path)
        return True

    def _cleanup_retention(self, now: float) -> None:
        if self.retention_days <= 0 or now - self.last_cleanup_at < 3600.0:
            return
        self.last_cleanup_at = now
        cutoff = now - (self.retention_days * 86400.0)
        try:
            for path in self.capture_root.rglob("*"):
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            for path in sorted((p for p in self.capture_root.rglob("*") if p.is_dir()), reverse=True):
                try:
                    path.rmdir()
                except OSError:
                    continue
        except OSError:
            return


def build_spot_image_fact(
    *,
    capture_id: str,
    captured_iso: str,
    source_url: str,
    relative_path: str,
    sha256: str,
    size_bytes: int,
    mime: str,
    width: Optional[int],
    height: Optional[int],
    source: str,
    image_age_ms: Optional[float],
    observation_snapshot: Optional[Mapping[str, Any]],
) -> dict[str, str]:
    snapshot = observation_snapshot or {}
    return {
        "spot_image_capture_id": capture_id,
        "spot_image_captured_at": captured_iso,
        "spot_image_source_url_hash": hashlib.sha256(source_url.encode("utf-8", errors="replace")).hexdigest(),
        "spot_image_path": relative_path,
        "spot_image_sha256": sha256,
        "spot_image_size_bytes": str(size_bytes),
        "spot_image_mime": mime,
        "spot_image_width": _text(width),
        "spot_image_height": _text(height),
        "spot_image_status": "captured",
        "spot_image_source": source,
        "spot_image_age_ms": _format_optional_float(image_age_ms),
        "spot_image_linked_observation_key": build_spot_observation_key(snapshot),
        "spot_service_instance_id": _text(snapshot.get("spot_service_instance_id")),
        "spot_poll_seq_nearest": _text(snapshot.get("spot_poll_seq")),
        "sample_seq_nearest": _text(snapshot.get("sample_seq")),
        "timestamp_utc_nearest": _text(snapshot.get("spot_last_poll_completed_at")),
        "temperature_output_status_nearest": _temperature_output_status(snapshot),
        "temperature_unavailable_reason_nearest": _temperature_unavailable_reason(snapshot),
        "temperature_under_range_cause_candidate_nearest": _under_range_cause_candidate(snapshot),
        "process_phase_candidate_nearest": _text(snapshot.get("process_phase_candidate")),
        "signalpc_nearest": _text(snapshot.get("signalpc")),
        "alarmstatus_nearest": _text(snapshot.get("alarmstatus")),
        "d1temperature_nearest": _text(snapshot.get("d1temperature")),
        "d2temperature_nearest": _text(snapshot.get("d2temperature")),
        "e1out_nearest": _text(snapshot.get("e1out")),
        "e2out_nearest": _text(snapshot.get("e2out")),
        "actuator_position_nearest": _text(snapshot.get("actuator_position")),
        "focus_mm": _text(snapshot.get("focus_mm")),
        "low_signal_threshold_pc": _text(snapshot.get("low_signal_threshold_pc")),
        "peak_picker_enabled": _text(snapshot.get("peak_picker_enabled")),
    }


def image_metadata(image_bytes: bytes) -> tuple[str, Optional[int], Optional[int], str]:
    if image_bytes.startswith(b"\xff\xd8") and image_bytes.endswith(b"\xff\xd9"):
        width, height = _jpeg_size(image_bytes)
        return "image/jpeg", width, height, ".jpg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = _png_size(image_bytes)
        return "image/png", width, height, ".png"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        width, height = _little_endian_size(image_bytes, 6)
        return "image/gif", width, height, ".gif"
    if image_bytes.startswith(b"BM"):
        width, height = _bmp_size(image_bytes)
        return "image/bmp", width, height, ".bmp"
    if len(image_bytes) >= 12 and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp", None, None, ".webp"
    return "application/octet-stream", None, None, ".bin"


def _png_size(image_bytes: bytes) -> tuple[Optional[int], Optional[int]]:
    if len(image_bytes) < 24:
        return None, None
    return int.from_bytes(image_bytes[16:20], "big"), int.from_bytes(image_bytes[20:24], "big")


def _little_endian_size(image_bytes: bytes, offset: int) -> tuple[Optional[int], Optional[int]]:
    if len(image_bytes) < offset + 4:
        return None, None
    return int.from_bytes(image_bytes[offset : offset + 2], "little"), int.from_bytes(
        image_bytes[offset + 2 : offset + 4],
        "little",
    )


def _bmp_size(image_bytes: bytes) -> tuple[Optional[int], Optional[int]]:
    if len(image_bytes) < 26:
        return None, None
    width = int.from_bytes(image_bytes[18:22], "little", signed=True)
    height = int.from_bytes(image_bytes[22:26], "little", signed=True)
    return abs(width), abs(height)


def _jpeg_size(image_bytes: bytes) -> tuple[Optional[int], Optional[int]]:
    index = 2
    while index + 9 < len(image_bytes):
        if image_bytes[index] != 0xFF:
            index += 1
            continue
        marker = image_bytes[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(image_bytes):
            return None, None
        segment_length = int.from_bytes(image_bytes[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(image_bytes):
            return None, None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(image_bytes[index + 3 : index + 5], "big")
            width = int.from_bytes(image_bytes[index + 5 : index + 7], "big")
            return width, height
        index += segment_length
    return None, None


def _temperature_output_status(snapshot: Mapping[str, Any]) -> str:
    explicit = _text(snapshot.get("temperature_output_status"))
    if explicit:
        return explicit
    device_status = _text(snapshot.get("spot_device_status_code"))
    if device_status == "temperature_under_range":
        return "under_range"
    if device_status == "temperature_over_range":
        return "over_range"
    raw_validity = _text(snapshot.get("spot_raw_validity"))
    if raw_validity == "valid_temperature":
        return "valid"
    poll_status = _text(snapshot.get("spot_poll_status"))
    if poll_status in {"timeout", "connection_error", "http_error", "config_missing"}:
        return "source_error"
    if raw_validity in {"not_received", "not_evaluated"}:
        return "unknown"
    return raw_validity


def _temperature_unavailable_reason(snapshot: Mapping[str, Any]) -> str:
    explicit = _text(snapshot.get("temperature_unavailable_reason"))
    if explicit:
        return explicit
    output_status = _temperature_output_status(snapshot)
    if output_status == "valid":
        return ""
    if output_status in {"under_range", "over_range", "source_error"}:
        return output_status
    return _text(snapshot.get("spot_error_code")) or output_status


def _under_range_cause_candidate(snapshot: Mapping[str, Any]) -> str:
    explicit = _text(snapshot.get("temperature_under_range_cause_candidate"))
    if explicit:
        return explicit
    evidence = set(_parse_evidence_codes(snapshot.get("spot_diagnostic_evidence_codes")))
    if "target_out_of_fov_evidence" in evidence:
        return "target_out_of_fov_candidate"
    if "actuator_scanning" in evidence or "actuator_position_changed" in evidence:
        return "alignment_change_candidate"
    if "signal_below_threshold" in evidence or "alarm_low_signal" in evidence:
        return "low_signal_candidate"
    if "detector_below_measurement_range" in evidence:
        return "below_measurement_range_candidate"
    if _temperature_output_status(snapshot) == "under_range":
        return "unknown"
    return ""


def _parse_evidence_codes(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return ()
            if isinstance(parsed, list):
                return tuple(str(item) for item in parsed)
        return tuple(part for part in stripped.replace(";", ",").split(",") if part)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return ()


def _format_optional_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value):.3f}"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
