from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

__version__ = "1.0.1"


def _resolve_executable_path() -> Path:
    return Path(sys.executable).resolve()


def _resolve_runtime_kind() -> str:
    if getattr(sys, "frozen", False):
        return "frozen"
    return "dev"


def _resolve_executable_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return None


def get_runtime_info() -> dict[str, Any]:
    executable_path = _resolve_executable_path()
    return {
        "app_version": __version__,
        "runtime_kind": _resolve_runtime_kind(),
        "executable_path": str(executable_path),
        "executable_mtime": _resolve_executable_mtime(executable_path),
    }
