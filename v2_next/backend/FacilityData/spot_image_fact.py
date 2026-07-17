from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import dataclass, field
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
    "spot_image_link_age_ms",
    "spot_image_link_status",
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
SPOT_IMAGE_FACT_FILENAME = "spot_image_fact.csv"
SPOT_IMAGE_FACT_FINAL_MANIFEST_FILENAME = "spot_image_fact_manifest.final.json"

_MANAGED_IMAGE_EXTENSIONS = {".jpg", ".png", ".gif", ".bmp", ".webp", ".bin"}


@dataclass
class SpotImageCaptureWriter:
    log_path: Path
    capture_root: Path
    retention_days: int = 7
    fact_filename: str = SPOT_IMAGE_FACT_FILENAME
    link_stale_threshold_ms: float = 9000.0
    failure_count: int = 0
    written_count: int = 0
    last_cleanup_at: float = field(default_factory=time.time)
    _known_facts_by_capture_id: Optional[dict[str, dict[str, str]]] = field(default=None, init=False, repr=False)
    _known_facts_complete: bool = field(default=False, init=False, repr=False)
    _fact_row_count: Optional[int] = field(default=None, init=False, repr=False)
    _historical_fact_mtime: Optional[float] = field(default=None, init=False, repr=False)
    _historical_fact_metadata_readable: bool = field(default=True, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self._historical_fact_mtime = self.fact_path.stat().st_mtime
        except FileNotFoundError:
            self._historical_fact_mtime = None
        except OSError:
            # Unknown history must preserve the conservative deduplication path.
            self._historical_fact_metadata_readable = False

    @property
    def fact_path(self) -> Path:
        return self.log_path / self.fact_filename

    @property
    def fact_row_count(self) -> int:
        if self._fact_row_count is None:
            self._load_fact_row_count()
        return int(self._fact_row_count or 0)

    def write_capture(
        self,
        *,
        image_bytes: bytes,
        captured_at: float,
        source_url: str,
        source: str,
        image_age_ms: Optional[float],
        link_checked_at: Optional[float],
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

        existing_fact = self._cached_fact_for_capture_id(capture_id)
        if existing_fact is None and self._capture_may_already_be_recorded(
            captured_at=captured_at,
            image_path=image_path,
        ):
            existing_fact = self._existing_fact_for_capture_id(capture_id)
        if existing_fact is not None:
            if not image_path.exists():
                tmp_path = image_path.with_suffix(f"{image_path.suffix}.tmp")
                tmp_path.write_bytes(image_bytes)
                tmp_path.replace(image_path)
            return dict(existing_fact)

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
            link_checked_at=link_checked_at,
            link_stale_threshold_ms=self.link_stale_threshold_ms,
            observation_snapshot=observation_snapshot,
        )
        self._append_fact(fact)
        self._remember_fact(fact)
        self.written_count += 1
        self._cleanup_retention(time.time())
        return fact

    def _capture_may_already_be_recorded(self, *, captured_at: float, image_path: Path) -> bool:
        if image_path.exists():
            return True
        if not self._historical_fact_metadata_readable:
            return True
        return (
            self._historical_fact_mtime is not None
            and self._historical_fact_mtime >= captured_at
        )

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
        self._known_facts_by_capture_id = {}
        self._known_facts_complete = True
        self._fact_row_count = 0
        return True

    def _existing_fact_for_capture_id(self, capture_id: str) -> Optional[dict[str, str]]:
        facts_by_id = self._load_known_facts_by_capture_id()
        fact = facts_by_id.get(capture_id)
        return dict(fact) if fact is not None else None

    def _cached_fact_for_capture_id(self, capture_id: str) -> Optional[dict[str, str]]:
        if self._known_facts_by_capture_id is None:
            return None
        fact = self._known_facts_by_capture_id.get(capture_id)
        return dict(fact) if fact is not None else None

    def _load_known_facts_by_capture_id(self) -> dict[str, dict[str, str]]:
        if self._known_facts_complete and self._known_facts_by_capture_id is not None:
            return self._known_facts_by_capture_id
        facts_by_id: dict[str, dict[str, str]] = {}
        row_count = 0
        if self.fact_path.exists() and self.fact_path.stat().st_size > 0:
            try:
                with self.fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    if reader.fieldnames == SPOT_IMAGE_FACT_COLUMNS:
                        for row in reader:
                            if row:
                                row_count += 1
                            capture_id = str(row.get("spot_image_capture_id") or "").strip()
                            if capture_id:
                                facts_by_id[capture_id] = dict(row)
            except (OSError, UnicodeError, csv.Error):
                facts_by_id = {}
                row_count = 0
        self._known_facts_by_capture_id = facts_by_id
        self._known_facts_complete = True
        self._fact_row_count = row_count
        return facts_by_id

    def _load_fact_row_count(self) -> int:
        row_count = 0
        if self.fact_path.exists() and self.fact_path.stat().st_size > 0:
            try:
                with self.fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.reader(handle)
                    header = next(reader, [])
                    if header == SPOT_IMAGE_FACT_COLUMNS:
                        row_count = sum(1 for row in reader if row)
            except (OSError, UnicodeError, csv.Error):
                row_count = 0
        self._fact_row_count = row_count
        return row_count

    def _remember_fact(self, fact: Mapping[str, str]) -> None:
        capture_id = str(fact.get("spot_image_capture_id") or "").strip()
        if not capture_id:
            return
        if self._known_facts_by_capture_id is None:
            self._known_facts_by_capture_id = {}
        facts_by_id = self._known_facts_by_capture_id
        was_known = capture_id in facts_by_id
        facts_by_id[capture_id] = dict(fact)
        if not was_known and self._fact_row_count is not None:
            self._fact_row_count += 1

    def _cleanup_retention(self, now: float) -> None:
        if self.retention_days <= 0 or now - self.last_cleanup_at < 3600.0:
            return
        self.last_cleanup_at = now
        cutoff = now - (self.retention_days * 86400.0)
        try:
            for day_dir in self._iter_managed_day_dirs():
                for path in day_dir.glob("spotimg_*"):
                    if self._is_managed_capture_file(path) and path.stat().st_mtime < cutoff:
                        path.unlink(missing_ok=True)
            self._cleanup_empty_managed_dirs()
        except OSError:
            return

    def _iter_managed_day_dirs(self) -> tuple[Path, ...]:
        if not self.capture_root.exists() or not self.capture_root.is_dir():
            return ()
        day_dirs: list[Path] = []
        for year_dir in self.capture_root.iterdir():
            if not year_dir.is_dir() or not _is_date_component(year_dir.name, 4):
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or not _is_date_component(month_dir.name, 2, 1, 12):
                    continue
                for day_dir in month_dir.iterdir():
                    if day_dir.is_dir() and _is_date_component(day_dir.name, 2, 1, 31):
                        day_dirs.append(day_dir)
        return tuple(day_dirs)

    def _is_managed_capture_file(self, path: Path) -> bool:
        if not path.is_file() or not _is_managed_capture_stem(path.stem):
            return False
        if path.suffix.lower() not in _MANAGED_IMAGE_EXTENSIONS:
            return False
        try:
            relative = path.relative_to(self.capture_root)
        except ValueError:
            return False
        parts = relative.parts
        return (
            len(parts) == 4
            and _is_date_component(parts[0], 4)
            and _is_date_component(parts[1], 2, 1, 12)
            and _is_date_component(parts[2], 2, 1, 31)
        )

    def _cleanup_empty_managed_dirs(self) -> None:
        for day_dir in sorted(self._iter_managed_day_dirs(), reverse=True):
            try:
                day_dir.rmdir()
            except OSError:
                continue
            month_dir = day_dir.parent
            year_dir = month_dir.parent
            for path in (month_dir, year_dir):
                try:
                    path.rmdir()
                except OSError:
                    break


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
    link_checked_at: Optional[float],
    observation_snapshot: Optional[Mapping[str, Any]],
    link_stale_threshold_ms: float = 9000.0,
) -> dict[str, str]:
    snapshot = observation_snapshot or {}
    linked_observation_key = build_spot_observation_key(snapshot)
    link_age_ms, link_status = _derive_link_age_and_status(
        snapshot=snapshot,
        link_checked_at=link_checked_at,
        linked_observation_key=linked_observation_key,
        stale_threshold_ms=link_stale_threshold_ms,
    )
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
        "spot_image_link_age_ms": _format_optional_float(link_age_ms),
        "spot_image_link_status": link_status,
        "spot_image_linked_observation_key": linked_observation_key,
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


def build_spot_image_fact_manifest(
    *,
    log_path: Path,
    capture_root: Path,
    enabled: bool,
    mode: str,
    health: Optional[Mapping[str, Any]] = None,
    fact_filename: str = SPOT_IMAGE_FACT_FILENAME,
) -> dict[str, Any]:
    fact_path = log_path / fact_filename
    row_count, sha256 = _fact_file_stats(fact_path)
    health_data = health or {}
    return {
        "enabled": bool(enabled),
        "mode": str(mode or "off"),
        "fact_path": str(fact_path),
        "capture_root": str(capture_root),
        "row_count": row_count,
        "sha256": sha256,
        "written": _optional_int(health_data.get("written_count")),
        "dropped": _optional_int(health_data.get("dropped_count")),
        "failure": _optional_int(health_data.get("failure_count")),
        "last_write_at": health_data.get("last_write_at"),
    }


def _derive_link_age_and_status(
    *,
    snapshot: Mapping[str, Any],
    link_checked_at: Optional[float],
    linked_observation_key: str,
    stale_threshold_ms: float,
) -> tuple[Optional[float], str]:
    if not snapshot:
        return None, "missing_observation"
    if not linked_observation_key:
        return None, "unlinked_observation"
    completed_at_epoch = _snapshot_completed_at_epoch(snapshot)
    if completed_at_epoch is None or link_checked_at is None:
        return None, "unknown_age"
    age_ms = (float(link_checked_at) - completed_at_epoch) * 1000.0
    if age_ms < 0:
        return age_ms, "clock_anomaly"
    if age_ms > stale_threshold_ms:
        return age_ms, "stale"
    return age_ms, "fresh"


def _snapshot_completed_at_epoch(snapshot: Mapping[str, Any]) -> Optional[float]:
    epoch_value = snapshot.get("_spot_last_poll_completed_at_epoch")
    try:
        if epoch_value is not None:
            return float(epoch_value)
    except (TypeError, ValueError):
        pass
    text = _text(snapshot.get("spot_last_poll_completed_at"))
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def _fact_file_stats(fact_path: Path) -> tuple[int, Optional[str]]:
    if not fact_path.exists() or fact_path.stat().st_size == 0:
        return 0, None
    row_count = 0
    try:
        with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            row_count = sum(1 for row in reader if row)
    except (OSError, UnicodeError, csv.Error):
        row_count = 0
    try:
        sha256 = hashlib.sha256(fact_path.read_bytes()).hexdigest()
    except OSError:
        sha256 = None
    return row_count, sha256


def image_metadata(image_bytes: bytes) -> tuple[str, Optional[int], Optional[int], str]:
    if image_bytes.startswith(b"\xff\xd8") and image_bytes.endswith(b"\xff\xd9"):
        width, height = _jpeg_size(image_bytes)
        return "image/jpeg", width, height, ".jpg"
    return "application/octet-stream", None, None, ".bin"


def _is_date_component(value: str, width: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> bool:
    if len(value) != width or not value.isdigit():
        return False
    number = int(value)
    if minimum is not None and number < minimum:
        return False
    if maximum is not None and number > maximum:
        return False
    return True


def _is_managed_capture_stem(stem: str) -> bool:
    parts = stem.split("_")
    if len(parts) != 3 or parts[0] != "spotimg":
        return False
    timestamp, digest = parts[1], parts[2]
    timestamp_digits = timestamp[:8] + timestamp[9:21]
    return (
        len(timestamp) == 22
        and timestamp[8] == "T"
        and timestamp[21] == "Z"
        and timestamp_digits.isdigit()
        and len(digest) == 12
        and all(char in "0123456789abcdef" for char in digest.lower())
    )


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
        return explicit if explicit in {"low_signal_candidate", "unknown"} else "unknown"
    if _temperature_output_status(snapshot) == "under_range":
        return "unknown"
    return ""

def _format_optional_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value):.3f}"


def _optional_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
