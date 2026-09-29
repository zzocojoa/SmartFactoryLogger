"""Create-only shutdown observations, independent of legacy closeout decisions.

Hashes detect copy corruption; they are not signatures or process-exit proof.
Only a matching begin/final pair belongs to an attempt. A final observation
never authorizes installation and never amends an earlier failed observation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
from typing import Any, Callable
from uuid import uuid4


def _reject_redirected_path(path: Path) -> None:
    # Check lexically before resolve() could hide a symlink/junction. These are
    # app-owned paths, not request parameters. This is not hostile-admin defense.
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise OSError("redirected shutdown evidence path")


def _publish(path: Path, data: bytes) -> None:
    """Flush before publishing without replacing any prior file.

    A failed attempt leaves its pending/partial files for diagnosis. Hard-link
    publication is supported by NTFS; unsupported filesystems fail closed.
    This does not promise durability through power loss of directory metadata.
    """
    pending = path.with_name(path.name + ".pending")
    _reject_redirected_path(pending)
    with pending.open("xb") as handle:
        if handle.write(data) != len(data):
            raise OSError("short shutdown evidence write")
        handle.flush()
        os.fsync(handle.fileno())
    _reject_redirected_path(path)
    os.link(pending, path)  # atomic no-clobber publication
    pending.unlink()


def read_receipt(path: Path) -> dict[str, Any]:
    path = path.absolute()
    sidecar = path.with_name(path.name + ".sha256")
    _reject_redirected_path(path)
    _reject_redirected_path(sidecar)
    data = path.read_bytes()
    digest = sidecar.read_text(encoding="ascii").strip()
    if digest != hashlib.sha256(data).hexdigest():
        raise ValueError("shutdown evidence hash mismatch")
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("shutdown evidence object required")
    return payload


def preserve_receipt(path: Path, payload: dict[str, Any]) -> str:
    path = path.absolute()
    _reject_redirected_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_redirected_path(path)
    data = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    _publish(path, data)
    _publish(path.with_name(path.name + ".sha256"), (digest + "\n").encode("ascii"))
    if read_receipt(path) != payload:
        raise ValueError("shutdown evidence readback mismatch")
    return digest


class ShutdownEvidenceAttempt:
    """One caller's before/final observation; no worker or exit decisions here."""

    def __init__(self, root: Path, *, entrypoint: str, identity: dict[str, Any], image: dict[str, Any]):
        if entrypoint not in {"control", "lifespan"}:
            raise ValueError("unsupported shutdown entrypoint")
        self.attempt_id = uuid4().hex
        self.root = root
        self._common = {
            "schema_version": 1,
            "attempt_id": self.attempt_id,
            "entrypoint": entrypoint,
            "identity": deepcopy(identity),
            "image_shutdown_id": image.get("shutdown_id"),
            "process_exit_observed": False,
            "installation_clearance": False,
        }
        self._before = self._payload("begin", image)
        self._lock = threading.RLock()
        self._io_thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "attempt_id": self.attempt_id, "before_verified": False,
            "final_verified": False, "receipt_verified": False,
            "error_phase": None, "error_type": None,
        }

    def invalidate(self, phase: str, error_type: str) -> None:
        with self._lock:
            if self._status["error_phase"] is None:
                self._status["error_phase"] = phase
                self._status["error_type"] = error_type
            self._status["receipt_verified"] = False

    def _start_io(self, phase: str, operation: Callable[[], bool]) -> bool:
        with self._lock:
            if self._io_thread is not None and self._io_thread.is_alive():
                self.invalidate(phase, "PreviousEvidenceWriterPending")
                return False
            def run() -> None:
                try:
                    operation()
                except Exception as exc:
                    self.invalidate(phase, type(exc).__name__)
            try:
                self._io_thread = threading.Thread(
                    target=run, name=f"shutdown-evidence-{phase}-{self._common['entrypoint']}", daemon=True,
                )
                self._io_thread.start()
            except Exception as exc:
                self.invalidate(phase, type(exc).__name__)
                return False
            return True

    def start_begin(self) -> bool:
        return self._start_io("begin", self.begin)

    def start_finish(self, *, image: dict[str, Any], stages: dict[str, Any], stage_exit_code: int) -> bool:
        return self._start_io("final", lambda: self.finish(
            image=image, stages=stages, stage_exit_code=stage_exit_code,
        ))

    def _path(self, phase: str) -> Path:
        return self.root / f"{self.attempt_id}.{phase}.json"

    def _payload(self, phase: str, image: dict[str, Any]) -> dict[str, Any]:
        return {**deepcopy(self._common), "phase": phase,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "image_capture": deepcopy(image)}

    def _write(self, phase: str, payload: dict[str, Any]) -> bool:
        try:
            digest = preserve_receipt(self._path(phase), payload)
        except Exception as exc:
            # No exception text, path, control token or device URL in the API.
            self.invalidate(phase, type(exc).__name__)
            return False
        with self._lock:
            self._status[f"{phase}_sha256"] = digest
        return True

    def begin(self) -> bool:
        verified = self._write("begin", self._before)
        with self._lock:
            self._status["before_verified"] = verified
        return verified

    def finish(self, *, image: dict[str, Any], stages: dict[str, Any], stage_exit_code: int) -> bool:
        payload = self._payload("final", image)
        status = self.status()
        payload.update({
            "begin_sha256": status.get("begin_sha256"),
            "before_verified": status["before_verified"],
            "stages": deepcopy(stages),
            # Observed before process exit. Even a verified receipt is not an
            # assertion that os._exit was reached or all OS processes exited.
            "stage_exit_code": stage_exit_code,
        })
        try:
            before = read_receipt(self._path("begin"))
            if before != self._before or image.get("shutdown_id") != self._common["image_shutdown_id"]:
                raise ValueError("shutdown attempt binding mismatch")
        except Exception as exc:
            self.invalidate("binding", type(exc).__name__)
            payload["before_verified"] = False
        verified = self._write("final", payload)
        with self._lock:
            self._status["final_verified"] = verified
            self._status["receipt_verified"] = (
                verified and self._status["before_verified"] and self._status["error_phase"] is None
            )
            return bool(self._status["receipt_verified"])

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {**deepcopy(self._status),
                    "writer_alive": self._io_thread is not None and self._io_thread.is_alive()}
