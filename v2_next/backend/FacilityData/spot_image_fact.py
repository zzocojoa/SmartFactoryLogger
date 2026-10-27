from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import stat
import tempfile
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ContextManager, Generator, Mapping, Optional, TextIO

from backend.FacilityData.spot_observation_fact import build_spot_observation_key
from backend.FacilityData.persistence_payload import PayloadBudgetExceeded, csv_parser_field_limit, csv_record_sizes


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
SPOT_IMAGE_FACT_ROW_BYTE_LIMIT = 1024 * 1024
SPOT_IMAGE_FACT_DIGEST_BUFFER_BYTES = 4096

_MANAGED_IMAGE_EXTENSIONS = {".jpg", ".png", ".gif", ".bmp", ".webp", ".bin"}
_SPOT_IMAGE_FACT_FILE_LOCK = threading.RLock()
# Process-local, bounded manual-recovery latches. Never store arbitrary path
# payloads or forget a known close/tail failure when replacing a writer.
_SPOT_IMAGE_UNCERTAIN_FACT_KEYS: set[bytes] = set()
_SPOT_IMAGE_UNCERTAIN_FACT_KEY_LIMIT = 4096
_SPOT_IMAGE_UNCERTAIN_FACT_KEYS_OVERFLOW = False


def _probe_storage_directory(destination: Path) -> None:
    """Check only two exclusively created files in the actual destination."""
    destination.mkdir(parents=True, exist_ok=True)
    payload = b"SmartFactory storage probe v1\n"
    owned: dict[Path, tuple[int, int]] = {}

    def identity(path: Path) -> tuple[int, int]:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or not info.st_ino:
            raise RuntimeError("storage probe file identity unavailable")
        return info.st_dev, info.st_ino

    try:
        paths: list[Path] = []
        for _ in range(2):
            fd, name = tempfile.mkstemp(prefix=".sfl-storage-probe-", dir=destination)
            path = Path(name)
            with os.fdopen(fd, "wb") as handle:
                info = os.fstat(handle.fileno())
                if not info.st_ino:
                    raise RuntimeError("storage probe handle identity unavailable")
                owned[path] = (info.st_dev, info.st_ino)
                if not paths:
                    if handle.write(payload) != len(payload):
                        raise OSError("storage probe short write")
                    handle.flush()
            paths.append(path)
        source, target = paths
        if any(identity(path) != expected for path, expected in owned.items()):
            raise RuntimeError("storage probe files changed before replace")
        source_identity = owned[source]
        os.replace(source, target)
        del owned[source]
        owned[target] = source_identity
        with target.open("rb") as read_handle:
            info = os.fstat(read_handle.fileno())
            if (info.st_dev, info.st_ino) != source_identity or read_handle.read(len(payload) + 1) != payload:
                raise RuntimeError("storage probe readback mismatch")
        if identity(target) != source_identity:
            raise RuntimeError("storage probe changed after readback")
    finally:
        cleanup_error: OSError | RuntimeError | None = None
        for path, expected in owned.items():
            try:
                if identity(path) != expected:
                    raise RuntimeError("storage probe cleanup identity changed")
                path.unlink()
            except FileNotFoundError:
                continue
            except (OSError, RuntimeError) as exc:
                cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error


def _bounded_fact_rows(handle: TextIO) -> Generator[list[str], None, None]:
    """Bound each logical CSV record, including quoted physical newlines."""
    remaining = SPOT_IMAGE_FACT_ROW_BYTE_LIMIT

    def physical_lines() -> Generator[str, None, None]:
        nonlocal remaining
        while line := handle.readline(remaining + 1):
            size = len(line.encode("utf-8"))
            if size > remaining:
                raise csv.Error("SPOT image fact row exceeds the recovery byte limit")
            remaining -= size
            yield line

    with csv_parser_field_limit(SPOT_IMAGE_FACT_ROW_BYTE_LIMIT):
        for row in csv.reader(physical_lines(), strict=True):
            remaining = SPOT_IMAGE_FACT_ROW_BYTE_LIMIT
            yield row


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
    payload_reservation: Callable[[int, str], ContextManager[None]] | None = field(default=None, repr=False)
    _known_facts_by_capture_id: Optional[dict[str, dict[str, str]]] = field(default=None, init=False, repr=False)
    _latest_recorded_capture_at: Optional[float] = field(default=None, init=False, repr=False)
    _fact_row_count: Optional[int] = field(default=None, init=False, repr=False)
    _fact_digest: Any = field(default_factory=hashlib.sha256, init=False, repr=False)
    _fact_has_content: bool = field(default=False, init=False, repr=False)
    _manifest_state_ready: bool = field(default=True, init=False, repr=False)
    _manifest_tracked_size: int = field(default=0, init=False, repr=False)
    _fact_identity: Optional[tuple[int, int, int, int]] = field(default=None, init=False, repr=False)
    _fact_identity_known: bool = field(default=False, init=False, repr=False)
    _initialization_identity: Optional[tuple[int, int, int, int]] = field(default=None, init=False, repr=False)
    _initialization_identity_observed: bool = field(default=False, init=False, repr=False)
    _historical_fact_mtime: Optional[float] = field(default=None, init=False, repr=False)
    _historical_fact_metadata_readable: bool = field(default=True, init=False, repr=False)
    _fact_append_uncertain: bool = field(default=False, init=False, repr=False)
    _fact_recovery_key: bytes = field(default=b"", init=False, repr=False)
    _retention_scan: Optional[Generator[None, None, None]] = field(default=None, init=False, repr=False)
    _destination_probe_results: tuple[dict[str, Any], ...] = field(default=(), init=False, repr=False)
    _destination_probe_retry_at: Optional[float] = field(default=None, init=False, repr=False)
    _destination_probe_retry_delay: float = field(default=1.0, init=False, repr=False)
    _destination_probe_failure_count: int = field(default=0, init=False, repr=False)
    _destination_probe_generation: int = field(default=0, init=False, repr=False)
    _destination_probe_lock: Any = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._fact_recovery_key = hashlib.sha256(
            os.path.normcase(str(self.fact_path.resolve())).encode("utf-8", errors="surrogatepass")
        ).digest()
        if self._fact_append_is_uncertain():
            self._manifest_state_ready = False
            return
        try:
            self._historical_fact_mtime = self.fact_path.stat().st_mtime
        except FileNotFoundError:
            self._historical_fact_mtime = None
        except OSError:
            # Unknown history must preserve the conservative deduplication path.
            self._historical_fact_metadata_readable = False
        self._initialize_manifest_state()

    @property
    def fact_path(self) -> Path:
        return self.log_path / self.fact_filename

    def probe_storage_destinations(self, *, captured_at: float) -> tuple[dict[str, Any], ...]:
        """Owner-only destination checks, preserving file and directory evidence separately."""
        day = datetime.fromtimestamp(captured_at, timezone.utc)
        image_directory = self.capture_root / day.strftime("%Y") / day.strftime("%m") / day.strftime("%d")
        results = []
        for sink_id, destination in (("image_fact", self.log_path), ("image_jpeg", image_directory)):
            error_type = None
            try:
                reservation = (self.payload_reservation(128, "destination_probe_byte_limit")
                               if self.payload_reservation is not None else nullcontext())
                with reservation:
                    _probe_storage_directory(destination)
            except (OSError, RuntimeError) as exc:
                error_type = type(exc).__name__
            file_error_type = None
            file_scope = "new_capture_directory" if sink_id == "image_jpeg" else "not_checked"
            if sink_id == "image_fact" and error_type is None:
                try:
                    file_scope = self._check_fact_access()
                except (OSError, RuntimeError) as exc:
                    file_error_type = type(exc).__name__
            manual_recovery = sink_id == "image_fact" and self._fact_append_is_uncertain()
            results.append({
                "sink_id": sink_id, "destination_path": str(destination.absolute()),
                "config_generation": self._destination_probe_generation,
                "probe_scope": "directory_only", "probe_status": "blocked" if error_type else "available",
                "probe_error_type": error_type, "probe_checked_monotonic": time.monotonic(),
                "file_check_scope": file_scope, "file_check_error_type": file_error_type,
                "manual_recovery_required": manual_recovery,
                "current_storage_availability": (
                    "blocked" if error_type or file_error_type or manual_recovery else "available"),
            })
        with self._destination_probe_lock:
            previous = {(item["sink_id"], item["destination_path"]): item["current_storage_availability"]
                        for item in self._destination_probe_results}
            if any(item["current_storage_availability"] == "blocked" for item in results):
                self._destination_probe_failure_count += 1
                progress = any(item["current_storage_availability"] == "available"
                               and previous.get((item["sink_id"], item["destination_path"])) == "blocked"
                               for item in results)
                if progress:
                    self._destination_probe_retry_delay = 1.0
                self._destination_probe_retry_at = time.monotonic() + self._destination_probe_retry_delay
                self._destination_probe_retry_delay = min(30.0, self._destination_probe_retry_delay * 2.0)
            else:
                self._destination_probe_retry_at = None
                self._destination_probe_retry_delay = 1.0
            self._destination_probe_results = tuple(results)
        return self.destination_probe_snapshot()

    def _check_fact_access(self) -> str:
        """Check an existing required file without creating, truncating or appending it."""
        with _SPOT_IMAGE_FACT_FILE_LOCK:
            self._assert_fact_unchanged()
            if self._fact_identity is None:
                return "new_fact_path"
            with self.fact_path.open("r+b") as handle:
                opened = os.fstat(handle.fileno())
                identity = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                if identity != self._fact_identity or self._fact_identity_snapshot() != identity:
                    self._mark_fact_append_uncertain()
                    raise RuntimeError("SPOT image fact changed during access verification")
            self._assert_fact_unchanged()
            return "existing_fact_access"

    def destination_probe_snapshot(self) -> tuple[dict[str, Any], ...]:
        """Memory-only copy; access checks do not establish complete historical integrity."""
        with self._destination_probe_lock:
            return tuple(dict(item) for item in self._destination_probe_results)

    def destination_probe_retry_snapshot(self) -> dict[str, Any]:
        with self._destination_probe_lock:
            return {"next_retry_at_monotonic": self._destination_probe_retry_at,
                    "retry_delay_sec": self._destination_probe_retry_delay,
                    "config_generation": self._destination_probe_generation,
                    "failure_count": self._destination_probe_failure_count}

    def bind_destination_probe_generation(self, generation: int) -> None:
        with self._destination_probe_lock:
            if generation == self._destination_probe_generation:
                return
            self._destination_probe_generation = generation
            self._destination_probe_results = ()
            self._destination_probe_retry_at = None
            self._destination_probe_retry_delay = 1.0

    def destination_probe_due(self, *, captured_at: float, now_monotonic: float) -> bool:
        day = datetime.fromtimestamp(captured_at, timezone.utc)
        image_directory = self.capture_root / day.strftime("%Y") / day.strftime("%m") / day.strftime("%d")
        expected = {("image_fact", str(self.log_path.absolute())), ("image_jpeg", str(image_directory.absolute()))}
        with self._destination_probe_lock:
            observed = {(item["sink_id"], item["destination_path"]) for item in self._destination_probe_results}
            return (observed != expected or (
                self._destination_probe_retry_at is not None and now_monotonic >= self._destination_probe_retry_at))

    @property
    def fact_row_count(self) -> int:
        with _SPOT_IMAGE_FACT_FILE_LOCK:
            self._validate_manifest_tracked_size()
            return int(self._fact_row_count or 0)

    @property
    def fact_sha256(self) -> Optional[str]:
        with _SPOT_IMAGE_FACT_FILE_LOCK:
            self._validate_manifest_tracked_size()
            if not self._manifest_state_ready:
                raise RuntimeError("SPOT image fact runtime manifest state is unavailable")
            if not self._fact_has_content:
                return None
            return self._fact_digest.copy().hexdigest()

    def try_manifest_stats(self) -> tuple[int, Optional[str], bool] | None:
        """Read one coherent snapshot without waiting for capture file I/O."""
        if not _SPOT_IMAGE_FACT_FILE_LOCK.acquire(blocking=False):
            return None
        try:
            try:
                self._validate_manifest_tracked_size()
            except OSError:
                self._manifest_state_ready = False
            row_count = int(self._fact_row_count or 0)
            if not self._manifest_state_ready:
                return row_count, None, False
            digest = self._fact_digest.copy().hexdigest() if self._fact_has_content else None
            return row_count, digest, True
        finally:
            _SPOT_IMAGE_FACT_FILE_LOCK.release()

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
        capture_id: Optional[str] = None,
    ) -> dict[str, str]:
        self._assert_fact_unchanged()
        sha256 = hashlib.sha256(image_bytes).hexdigest()
        captured_dt = datetime.fromtimestamp(captured_at, timezone.utc)
        captured_iso = captured_dt.isoformat().replace("+00:00", "Z")
        if capture_id is None:
            # Preserve the historical direct-writer contract. The live HTTP
            # producer supplies its immutable acquisition ID explicitly.
            capture_id = f"spotimg_{captured_dt.strftime('%Y%m%dT%H%M%S%fZ')}_{sha256[:12]}"
        elif not _is_managed_capture_stem(capture_id):
            raise ValueError("Invalid SPOT image capture identity")
        mime, width, height, extension = image_metadata(image_bytes)
        relative_path = self._relative_image_path(captured_dt, capture_id, extension)
        output_path = self.capture_root / captured_dt.strftime("%Y") / captured_dt.strftime("%m") / captured_dt.strftime("%d")
        image_path = output_path / f"{capture_id}{extension}"

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
        if csv_record_sizes(fact[column] for column in SPOT_IMAGE_FACT_COLUMNS)[1] > SPOT_IMAGE_FACT_ROW_BYTE_LIMIT:
            raise PayloadBudgetExceeded("image_fact_row_byte_limit")

        existing_fact = self._cached_fact_for_capture_id(capture_id)
        if existing_fact is None and self._capture_may_already_be_recorded(
            captured_at=captured_at,
            image_path=image_path,
        ):
            existing_fact = self._existing_fact_for_capture_id(capture_id)
        if existing_fact is not None and any(existing_fact.get(key) != fact[key] for key in SPOT_IMAGE_FACT_COLUMNS):
            raise RuntimeError("SPOT image capture identity conflicts with stored fact")

        output_path.mkdir(parents=True, exist_ok=True)
        if not self._reuse_capture_file(image_path, image_bytes):
            tmp_path = image_path.with_suffix(f"{image_path.suffix}.tmp")
            tmp_path.write_bytes(image_bytes)
            tmp_path.replace(image_path)
        if existing_fact is not None:
            return dict(existing_fact)

        self._append_fact(fact)
        self._remember_fact(fact)
        self._latest_recorded_capture_at = max(captured_at, self._latest_recorded_capture_at or captured_at)
        self.written_count += 1
        self._cleanup_retention(time.time())
        return fact

    def _reuse_capture_file(self, path: Path, expected: bytes) -> bool:
        try:
            before = path.lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(before.st_mode) or before.st_size != len(expected):
            raise RuntimeError("SPOT image capture file is uncertain: type or size differs")

        def identity(info: os.stat_result) -> tuple[int, int, int, int]:
            # Windows path stat and handle stat can report different ctime
            # semantics after rename; use the same identity as CSV evidence.
            return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

        with path.open("rb", buffering=0) as handle:
            if identity(os.fstat(handle.fileno())) != identity(before):
                raise RuntimeError("SPOT image capture file is uncertain: identity changed")
            # Verify the existing whole capture without allocating another JPEG.
            size = min(4096, max(1, len(expected)))
            reservation = (self.payload_reservation(size, "capture_verification_byte_limit")
                           if self.payload_reservation is not None else nullcontext())
            with reservation, memoryview(bytearray(size)) as window, memoryview(expected) as source:
                offset = 0
                while offset < len(expected):
                    count = handle.readinto(window[:min(len(window), len(expected) - offset)])
                    if not count or window[:count] != source[offset:offset + count]:
                        raise RuntimeError("SPOT image capture file is uncertain: content differs")
                    offset += count
            if identity(os.fstat(handle.fileno())) != identity(before) or identity(path.lstat()) != identity(before):
                raise RuntimeError("SPOT image capture file is uncertain: changed while verifying")
        return True

    def _capture_may_already_be_recorded(self, *, captured_at: float, image_path: Path) -> bool:
        if image_path.exists():
            return True
        if not self._historical_fact_metadata_readable:
            return True
        return (
            (self._historical_fact_mtime is not None and self._historical_fact_mtime >= captured_at)
            or (self._latest_recorded_capture_at is not None and self._latest_recorded_capture_at >= captured_at)
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

    def _fact_append_is_uncertain(self) -> bool:
        with _SPOT_IMAGE_FACT_FILE_LOCK:
            self._fact_append_uncertain = (
                self._fact_append_uncertain or _SPOT_IMAGE_UNCERTAIN_FACT_KEYS_OVERFLOW
                or self._fact_recovery_key in _SPOT_IMAGE_UNCERTAIN_FACT_KEYS
            )
            return self._fact_append_uncertain

    def _mark_fact_append_uncertain(self) -> None:
        global _SPOT_IMAGE_UNCERTAIN_FACT_KEYS_OVERFLOW
        self._fact_append_uncertain = True
        self._manifest_state_ready = False
        # Called under the file lock. A full latch table blocks further image
        # fact appends; it must not evict an unresolved destination to make room.
        if len(_SPOT_IMAGE_UNCERTAIN_FACT_KEYS) < _SPOT_IMAGE_UNCERTAIN_FACT_KEY_LIMIT:
            _SPOT_IMAGE_UNCERTAIN_FACT_KEYS.add(self._fact_recovery_key)
        elif self._fact_recovery_key not in _SPOT_IMAGE_UNCERTAIN_FACT_KEYS:
            _SPOT_IMAGE_UNCERTAIN_FACT_KEYS_OVERFLOW = True

    def _append_fact(self, fact: Mapping[str, str]) -> None:
        with _SPOT_IMAGE_FACT_FILE_LOCK:
            self._assert_fact_unchanged()
            self.log_path.mkdir(parents=True, exist_ok=True)
            write_header = self._prepare_fact_file_for_append()
            previous_size = self._fact_file_size()
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=SPOT_IMAGE_FACT_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(fact)
            encoding = "utf-8-sig" if write_header and previous_size == 0 else "utf-8"
            payload = buffer.getvalue().encode(encoding)
            expected_size = previous_size + len(payload)
            append_started = False
            try:
                with self.fact_path.open("ab") as handle:
                    opened = os.fstat(handle.fileno())
                    opened_identity = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                    if (
                        (self._fact_identity is not None and opened_identity != self._fact_identity)
                        or (self._fact_identity is None and opened.st_size != 0)
                        or self._fact_identity_snapshot() != opened_identity
                    ):
                        self._mark_fact_append_uncertain()
                        raise RuntimeError("SPOT image fact append is uncertain; manual recovery required")
                    append_started = True
                    if handle.write(payload) != len(payload):
                        raise OSError("SPOT image fact append was truncated")
            except Exception:
                if append_started:
                    # A partial row or failed close cannot be repaired by schema
                    # rollover or by appending the next capture after the tail.
                    self._mark_fact_append_uncertain()
                raise
            try:
                closed_identity = self._fact_identity_snapshot()
                if (
                    closed_identity is None
                    or closed_identity[:2] != opened_identity[:2]
                    or closed_identity[2] != expected_size
                ):
                    self._mark_fact_append_uncertain()
                    raise RuntimeError("SPOT image fact append is uncertain; manual recovery required")
                self._fact_identity = closed_identity
                self._fact_identity_known = True
            except OSError:
                self._fact_identity_known = False
                self._manifest_state_ready = False
                raise
            self._extend_manifest_digest(
                previous_size,
                expected_size=expected_size,
            )
            self._fact_row_count = int(self._fact_row_count or 0) + 1

    def _prepare_fact_file_for_append(self) -> bool:
        if not self.fact_path.exists() or self.fact_path.stat().st_size == 0:
            return True
        try:
            with self.fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                existing_header = next(_bounded_fact_rows(handle), [])
        except (UnicodeError, csv.Error):
            existing_header = []
        if existing_header == SPOT_IMAGE_FACT_COLUMNS:
            return False
        self._mark_fact_append_uncertain()
        raise RuntimeError("SPOT image fact append is uncertain; manual recovery required")

    def _existing_fact_for_capture_id(self, capture_id: str) -> Optional[dict[str, str]]:
        facts_by_id = self._load_known_facts_by_capture_id(capture_id)
        fact = facts_by_id.get(capture_id)
        return dict(fact) if fact is not None else None

    def _cached_fact_for_capture_id(self, capture_id: str) -> Optional[dict[str, str]]:
        if self._known_facts_by_capture_id is None:
            return None
        fact = self._known_facts_by_capture_id.get(capture_id)
        return dict(fact) if fact is not None else None

    def _load_known_facts_by_capture_id(self, requested_id: str) -> dict[str, dict[str, str]]:
        # Scan sequentially, retaining only the requested record. File length
        # must not determine the resident identity-index size.
        facts_by_id: dict[str, dict[str, str]] = {}
        row_count = 0
        if self.fact_path.exists() and self.fact_path.stat().st_size > 0:
            try:
                with self.fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = _bounded_fact_rows(handle)
                    if next(reader, []) != SPOT_IMAGE_FACT_COLUMNS:
                        raise csv.Error("SPOT image fact history has an unsupported header")
                    for values in reader:
                        if len(values) != len(SPOT_IMAGE_FACT_COLUMNS):
                            raise csv.Error("SPOT image fact history contains an incomplete row")
                        row_count += 1
                        row = dict(zip(SPOT_IMAGE_FACT_COLUMNS, values))
                        if row["spot_image_capture_id"] == requested_id:
                            if requested_id in facts_by_id:
                                raise csv.Error("SPOT image fact history duplicates the requested capture")
                            facts_by_id[requested_id] = row
            except (UnicodeError, csv.Error) as exc:
                with _SPOT_IMAGE_FACT_FILE_LOCK:
                    self._mark_fact_append_uncertain()
                raise RuntimeError("SPOT image fact append is uncertain; manual recovery required") from exc
        self._known_facts_by_capture_id = facts_by_id
        if self._fact_row_count is None:
            self._fact_row_count = row_count
        return facts_by_id

    def _load_fact_row_count(self) -> int:
        row_count = 0
        if self.fact_path.exists() and self.fact_path.stat().st_size > 0:
            try:
                with self.fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = _bounded_fact_rows(handle)
                    header = next(reader, [])
                    if header == SPOT_IMAGE_FACT_COLUMNS:
                        for row in reader:
                            if len(row) != len(SPOT_IMAGE_FACT_COLUMNS):
                                raise csv.Error("SPOT image fact history contains an incomplete row")
                            row_count += 1
                    else:
                        raise csv.Error("SPOT image fact history has an unsupported header")
            except OSError:
                row_count = 0
                self._manifest_state_ready = False
                raise
            except (UnicodeError, csv.Error):
                row_count = 0
                with _SPOT_IMAGE_FACT_FILE_LOCK:
                    self._mark_fact_append_uncertain()
        self._fact_row_count = row_count
        return row_count

    def _remember_fact(self, fact: Mapping[str, str]) -> None:
        capture_id = str(fact.get("spot_image_capture_id") or "").strip()
        if not capture_id:
            return
        # Only the most recent row is a fast-path cache. Older retries use the
        # bounded lookup above, including when retention removed their JPEG.
        self._known_facts_by_capture_id = {capture_id: dict(fact)}

    def _initialize_manifest_state(self) -> None:
        self._fact_identity_known = False
        try:
            identity = self._fact_identity_snapshot()
            if self._fact_append_is_uncertain():
                return
            if self._initialization_identity_observed and identity != self._initialization_identity:
                with _SPOT_IMAGE_FACT_FILE_LOCK:
                    self._mark_fact_append_uncertain()
                return
            self._initialization_identity = identity
            self._initialization_identity_observed = True
            if identity is None or identity[2] == 0:
                self._fact_row_count = 0
                self._manifest_tracked_size = 0
                self._fact_identity = identity
                self._fact_identity_known = True
                self._fact_digest = hashlib.sha256()
                self._fact_has_content = False
                self._manifest_state_ready = True
                self._initialization_identity_observed = False
                self._initialization_identity = None
                return
            expected_size = identity[2]
            digest = hashlib.sha256()
            last_byte = self._read_fact_digest(digest, 0, expected_size)
            if last_byte != b"\n":
                with _SPOT_IMAGE_FACT_FILE_LOCK:
                    self._mark_fact_append_uncertain()
                return
            self._fact_digest = digest
            self._fact_has_content = True
            self._load_fact_row_count()
            if self._fact_append_is_uncertain():
                return
            if self._fact_identity_snapshot() != identity:
                with _SPOT_IMAGE_FACT_FILE_LOCK:
                    self._mark_fact_append_uncertain()
                return
            self._manifest_tracked_size = expected_size
            self._fact_identity = identity
            self._fact_identity_known = True
            self._manifest_state_ready = True
            self._initialization_identity_observed = False
            self._initialization_identity = None
        except (OSError, UnicodeError, csv.Error):
            self._manifest_state_ready = False

    def _fact_file_size(self) -> int:
        try:
            return self.fact_path.stat().st_size
        except FileNotFoundError:
            return 0

    def _read_fact_digest(self, digest: Any, offset: int, size: int) -> bytes:
        scratch = min(SPOT_IMAGE_FACT_DIGEST_BUFFER_BYTES, size)
        reservation = (self.payload_reservation(scratch, "fact_digest_byte_limit")
                       if self.payload_reservation is not None else nullcontext())
        last_byte = b""
        with reservation, memoryview(bytearray(scratch)) as window:
            with self.fact_path.open("rb", buffering=0) as handle:
                handle.seek(offset)
                remaining = size
                while remaining:
                    count = handle.readinto(window[:min(len(window), remaining)])
                    if not count:
                        raise OSError("SPOT image fact digest read was truncated")
                    digest.update(window[:count])
                    last_byte = bytes(window[count - 1:count])
                    remaining -= count
        return last_byte

    def _extend_manifest_digest(
        self,
        previous_size: int,
        *,
        expected_size: int,
    ) -> None:
        self._fact_has_content = True
        if not self._manifest_state_ready:
            return
        current_size = self._fact_file_size()
        if (
            previous_size != self._manifest_tracked_size
            or current_size != expected_size
        ):
            self._manifest_state_ready = False
            return
        try:
            self._read_fact_digest(self._fact_digest, previous_size, current_size - previous_size)
            if self._fact_file_size() != current_size:
                self._manifest_state_ready = False
                return
        except (OSError, PayloadBudgetExceeded):
            # The fact row is durable. Preserve row/dedupe state and make the
            # final manifest fail closed rather than writing the same capture twice.
            self._manifest_state_ready = False
            return
        self._manifest_tracked_size = current_size

    def _validate_manifest_tracked_size(self) -> None:
        if self._fact_identity_known and self._fact_identity_snapshot() != self._fact_identity:
            self._mark_fact_append_uncertain()
        if self._fact_append_is_uncertain():
            self._manifest_state_ready = False
        if (
            self._manifest_state_ready
            and self._fact_file_size() != self._manifest_tracked_size
        ):
            self._manifest_state_ready = False

    def _fact_identity_snapshot(self) -> Optional[tuple[int, int, int, int]]:
        try:
            info = self.fact_path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode):
            with _SPOT_IMAGE_FACT_FILE_LOCK:
                self._mark_fact_append_uncertain()
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

    def _assert_fact_unchanged(self) -> None:
        with _SPOT_IMAGE_FACT_FILE_LOCK:
            if not self._fact_identity_known and not self._fact_append_is_uncertain():
                self._initialize_manifest_state()
            self._validate_manifest_tracked_size()
            if self._fact_append_is_uncertain():
                raise RuntimeError("SPOT image fact append is uncertain; manual recovery required")
            if not self._fact_identity_known:
                raise OSError("SPOT image fact identity is unavailable")

    def _cleanup_retention(self, now: float, *, allow_start: bool = True) -> None:
        if self.retention_days <= 0:
            self.close_retention_scan()
            return
        if self._retention_scan is None:
            if not allow_start or now - self.last_cleanup_at < 3600.0:
                return
            self.last_cleanup_at = now
            self._retention_scan = self._retention_steps(now - self.retention_days * 86400.0)
        # Bound work between captures, including directory enumeration. An OS
        # call itself cannot be preempted; this is a cooperative time budget.
        deadline = time.perf_counter() + 0.010
        try:
            for _ in range(256):
                if time.perf_counter() >= deadline:
                    return
                next(self._retention_scan)
        except (StopIteration, OSError):
            self.close_retention_scan()

    def close_retention_scan(self) -> None:
        """Release the scan on its owning capture worker, including on shutdown."""
        scan, self._retention_scan = self._retention_scan, None
        if scan is not None:
            scan.close()

    def _retention_steps(self, cutoff: float) -> Generator[None, None, None]:
        def walk(directory: Path, depth: int) -> Generator[None, None, bool]:
            removed_child = False
            # Path.iterdir/glob can materialize an entire directory. Keep only
            # the current entries and at most four scandir handles instead.
            with os.scandir(directory) as entries:
                for entry in entries:
                    yield
                    if entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                        continue
                    path = Path(entry.path)
                    if depth < 3:
                        component = (4, None, None) if depth == 0 else (2, 1, 12 if depth == 1 else 31)
                        if _is_date_component(entry.name, *component) and entry.is_dir(follow_symlinks=False):
                            child_removed = yield from walk(path, depth + 1)
                            removed_child = removed_child or child_removed
                    elif entry.name.startswith("spotimg_"):
                        if self._is_managed_capture_file(path) and path.stat().st_mtime < cutoff:
                            path.unlink(missing_ok=True)
            removed = False
            # As before, remove month/year only after removing a managed day
            # beneath them. Unrelated empty year/month folders are preserved.
            if depth == 3 or (depth > 0 and removed_child):
                try:
                    directory.rmdir()
                    removed = True
                except OSError:
                    pass
                yield
            return removed

        yield from walk(self.capture_root, 0)

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
    runtime_stats: Optional[Mapping[str, Any]] = None,
    fact_filename: str = SPOT_IMAGE_FACT_FILENAME,
) -> dict[str, Any]:
    fact_path = log_path / fact_filename
    health_data = health or {}
    if runtime_stats is not None:
        if (
            runtime_stats.get("fact_manifest_state_ready") is not True
            or "fact_row_count" not in runtime_stats
            or "fact_sha256" not in runtime_stats
        ):
            raise RuntimeError(
                "SPOT image fact runtime manifest state is unavailable"
            )
        manifest_stats = runtime_stats
        row_count = int(manifest_stats.get("fact_row_count") or 0)
        raw_sha256 = manifest_stats.get("fact_sha256")
        sha256 = str(raw_sha256) if raw_sha256 else None
    else:
        # Offline validators may reconstruct a manifest from a stopped fact file.
        # Production closeout always supplies runtime_stats and must never rescan.
        row_count, sha256 = _fact_file_stats(fact_path)
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
        digest = hashlib.sha256()
        with fact_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        sha256 = digest.hexdigest()
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
        and len(digest) in {12, 32}
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
