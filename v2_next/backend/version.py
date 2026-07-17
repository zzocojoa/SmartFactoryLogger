from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

__version__ = "1.0.16"

BUILD_PROVENANCE_FILENAME = "build_provenance.json"
BUILD_PROVENANCE_SCHEMA_VERSION = "1.0.0"
BUILD_PROVENANCE_SOURCE = "clean_git_head"
_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}", re.ASCII)
_GIT_COMMAND_TIMEOUT_SECONDS = 2.0


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


def validate_git_commit(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if _GIT_COMMIT_PATTERN.fullmatch(value) is None:
        return None
    return value


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_clean_git_commit(project_root: Path | None = None) -> str | None:
    repo_root = project_root or _default_project_root()
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
        if status.returncode != 0 or status.stdout.strip():
            return None
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if head.returncode != 0:
        return None
    return validate_git_commit(head.stdout.strip())


def write_build_provenance_file(project_root: Path, destination: Path) -> str:
    commit = resolve_clean_git_commit(project_root)
    if commit is None:
        raise RuntimeError(
            "Build provenance requires a clean Git worktree and a valid 40-character lowercase HEAD SHA."
        )
    payload = {
        "git_commit": commit,
        "schema_version": BUILD_PROVENANCE_SCHEMA_VERSION,
        "source": BUILD_PROVENANCE_SOURCE,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return commit


def verify_build_source_commit(project_root: Path, expected_commit: str) -> str:
    validated_expected = validate_git_commit(expected_commit)
    actual_commit = resolve_clean_git_commit(project_root)
    if validated_expected is None or actual_commit != validated_expected:
        raise RuntimeError("Build source changed after provenance capture; refusing the packaged artifact.")
    return actual_commit


def read_bundled_git_commit(provenance_path: Path | None = None) -> str | None:
    path = provenance_path or Path(__file__).resolve().with_name(BUILD_PROVENANCE_FILENAME)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != BUILD_PROVENANCE_SCHEMA_VERSION:
        return None
    if payload.get("source") != BUILD_PROVENANCE_SOURCE:
        return None
    return validate_git_commit(payload.get("git_commit"))


def resolve_runtime_git_commit(
    *,
    project_root: Path | None = None,
    provenance_path: Path | None = None,
) -> str | None:
    if _resolve_runtime_kind() == "frozen":
        return read_bundled_git_commit(provenance_path)
    return resolve_clean_git_commit(project_root)


def get_runtime_info() -> dict[str, Any]:
    executable_path = _resolve_executable_path()
    return {
        "app_version": __version__,
        "runtime_kind": _resolve_runtime_kind(),
        "executable_path": str(executable_path),
        "executable_mtime": _resolve_executable_mtime(executable_path),
    }
