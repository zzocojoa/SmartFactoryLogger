"""Read-only checks of copied SPOT image bytes; separate from CSV schema validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
import warnings
from collections import Counter
from contextlib import closing
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, ImageFile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_identity(path: Path) -> tuple[int, int, int, int]:
    info = path.stat()
    return info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino


def inspect_image_file(path: Path, expected_sha256: str, expected_size: int) -> dict[str, Any]:
    issues: list[str] = []
    result: dict[str, Any] = {"status": "FAIL", "issues": issues}
    try:
        before = _file_identity(path)
        result["bytes"] = before[0]
        result["sha256"] = sha256_file(path)
        if result["sha256"] != expected_sha256:
            issues.append("sha256_mismatch")
        if result["bytes"] != expected_size:
            issues.append("size_mismatch")
        if ImageFile.LOAD_TRUNCATED_IMAGES:
            issues.append("decoder_allows_truncation")
        else:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(path) as image:
                        result.update(width=image.width, height=image.height, mime=Image.MIME.get(image.format))
                        frame_count = 0
                        while True:
                            image.load()
                            frame_count += 1
                            try:
                                image.seek(frame_count)
                            except EOFError:
                                break
                        result["decoded_frames"] = frame_count
                    with Image.open(path) as image:
                        image.verify()
            except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                issues.append("decode_failed")
        if _file_identity(path) != before:
            issues.append("changed_during_read")
    except OSError as error:
        issues.append("missing_file" if isinstance(error, FileNotFoundError) else "file_read_failed")
    result["status"] = "FAIL" if issues else "PASS"
    return result


def _reject_links(path: Path) -> None:
    for component in (path, *path.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("symlink_or_reparse_point")


def _image_path(text: str, log_root: Path, capture_root: Path) -> Path:
    portable = text.replace("\\", "/")
    parts = PurePosixPath(portable)
    if not portable or parts.is_absolute() or ".." in parts.parts or ":" in portable or "\x00" in portable:
        raise ValueError("unsafe_image_path")
    candidate = log_root.joinpath(*parts.parts)
    if not candidate.is_relative_to(capture_root):
        raise ValueError("image_outside_capture_root")
    return candidate


def _path_key(relative: str) -> str:
    return os.path.normcase(relative).replace("\\", "/")


def _inventory(root: Path, log_root: Path):
    """Yield every entry that cannot be traversed and every regular file; never follow links."""
    for path in sorted(root.iterdir()):
        relative = path.relative_to(log_root).as_posix()
        try:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                yield {"path": relative, "issues": ["symlink_or_reparse_point"]}
            elif path.is_dir():
                yield from _inventory(path, log_root)
            elif path.is_file():
                before = _file_identity(path)
                digest = sha256_file(path)
                issues = [] if before == _file_identity(path) else ["changed_during_read"]
                yield {"path": relative, "identity": before, "sha256": digest, "issues": issues}
            else:
                yield {"path": relative, "issues": ["unsupported_file_type"]}
        except OSError:
            yield {"path": relative, "issues": ["inventory_read_failed"]}


def audit_image_files(fact_path: Path, capture_root: Path, output_dir: Path) -> dict[str, Any]:
    """Audit a copied image subtree and its fact. Does not establish a server-wide snapshot."""
    fact_path, capture_root, output_dir = (path.absolute() for path in (fact_path, capture_root, output_dir))
    _reject_links(fact_path)
    _reject_links(capture_root)
    _reject_links(output_dir.parent)
    log_root = fact_path.parent
    if not capture_root.is_relative_to(log_root) or capture_root == log_root:
        raise ValueError("capture_root_must_be_a_log_subdirectory")
    if output_dir.is_relative_to(log_root):
        raise ValueError("output_must_be_outside_input_copy")
    if not fact_path.is_file() or not capture_root.is_dir():
        raise ValueError("fact_file_and_capture_directory_required")
    output_dir.mkdir()  # Exclusive creation: earlier evidence is never overwritten.
    issue_counts: Counter[str] = Counter()
    summary: dict[str, Any] = {
        "scope": "copied_image_subtree_and_selected_fact",
        "full_data_gate": "NOT_EVALUATED",
        "status": "FAIL",
        "fact_row_count": 0,
        "checked_file_count": 0,
        "orphan_file_count": 0,
        "inventory_file_count": 0,
        "fact_sha256_before": sha256_file(fact_path),
        "tool_sha256": sha256_file(Path(__file__)),
    }
    fact_identity = _file_identity(fact_path)
    with tempfile.TemporaryDirectory(dir=output_dir) as index_dir, closing(sqlite3.connect(Path(index_dir) / "index.sqlite")) as db:
        db.execute("CREATE TABLE inventory (path TEXT PRIMARY KEY, record TEXT, seen_after INTEGER DEFAULT 0)")
        db.execute("CREATE TABLE refs (capture_id TEXT PRIMARY KEY, path TEXT UNIQUE)")
        db.execute("CREATE TABLE checked (path TEXT PRIMARY KEY)")
        with (output_dir / "inventory-before.jsonl").open("x", encoding="utf-8") as inventory_file:
            for item in _inventory(capture_root, log_root):
                encoded = json.dumps(item, ensure_ascii=False)
                inventory_file.write(encoded + "\n")
                db.execute("INSERT INTO inventory (path, record) VALUES (?, ?)", (_path_key(item["path"]), encoded))
                issue_counts.update(item["issues"])
                if "sha256" in item:
                    summary["inventory_file_count"] += 1
        with (output_dir / "image-checks.jsonl").open("x", encoding="utf-8") as checks:
            def record(result: dict[str, Any]) -> None:
                issue_counts.update(result["issues"])
                checks.write(json.dumps(result, ensure_ascii=False) + "\n")

            with fact_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, strict=True)
                required = {"spot_image_capture_id", "spot_image_path", "spot_image_sha256", "spot_image_size_bytes"}
                header = reader.fieldnames or []
                if not required.issubset(header) or len(set(header)) != len(header):
                    record({"issues": ["invalid_fact_header"]})
                else:
                    try:
                        for row_number, row in enumerate(reader, start=2):
                            summary["fact_row_count"] += 1
                            result: dict[str, Any] = {"row": row_number, "issues": []}
                            try:
                                if None in row or any(value is None for value in row.values()):
                                    raise ValueError("invalid_fact_row_width")
                                capture_id = row["spot_image_capture_id"].strip()
                                expected_sha = row["spot_image_sha256"].strip()
                                size_text = row["spot_image_size_bytes"].strip()
                                if not capture_id or not re.fullmatch("[0-9a-f]{64}", expected_sha) or not re.fullmatch("0|[1-9][0-9]*", size_text):
                                    raise ValueError("invalid_fact_identity_hash_or_size")
                                path = _image_path(row["spot_image_path"].strip(), log_root, capture_root)
                                relative = path.relative_to(log_root).as_posix()
                                path_key = _path_key(relative)
                                result.update(path=relative, capture_id=capture_id)
                                try:
                                    db.execute("INSERT INTO refs VALUES (?, ?)", (capture_id, path_key))
                                except sqlite3.IntegrityError:
                                    result["issues"].append("duplicate_capture_id_or_path")
                                _reject_links(path)
                                inspected = inspect_image_file(path, expected_sha, int(size_text))
                                result["actual"] = inspected
                                result["issues"].extend(inspected["issues"])
                                db.execute("INSERT OR IGNORE INTO checked VALUES (?)", (path_key,))
                                for field, actual in (("spot_image_width", "width"), ("spot_image_height", "height"), ("spot_image_mime", "mime")):
                                    expected = row.get(field, "").strip()
                                    if expected and str(inspected.get(actual)) != expected:
                                        result["issues"].append(actual + "_mismatch")
                                baseline = db.execute("SELECT record FROM inventory WHERE path=?", (path_key,)).fetchone()
                                if baseline is None or json.loads(baseline[0]).get("sha256") != inspected.get("sha256"):
                                    result["issues"].append("not_matching_initial_inventory")
                            except FileNotFoundError:
                                result["issues"].append("missing_file")
                            except (OSError, ValueError) as error:
                                result["issues"].append(str(error) if isinstance(error, ValueError) else "file_read_failed")
                            result["status"] = "FAIL" if result["issues"] else "PASS"
                            record(result)
                    except (csv.Error, UnicodeError):
                        record({"issues": ["fact_parse_failed"]})
            for path_key, encoded in db.execute("SELECT path, record FROM inventory WHERE path NOT IN (SELECT path FROM refs)"):
                item = json.loads(encoded)
                relative = item["path"]
                result = {"path": relative, "issues": ["orphan_file"]}
                summary["orphan_file_count"] += 1
                if "sha256" in item:
                    inspected = inspect_image_file(log_root / relative, item["sha256"], item["identity"][0])
                    result["actual"] = inspected
                    result["issues"].extend(inspected["issues"])
                    db.execute("INSERT OR IGNORE INTO checked VALUES (?)", (path_key,))
                record(result)
        summary["checked_file_count"] = db.execute("SELECT count(*) FROM checked").fetchone()[0]
        with (output_dir / "inventory-after.jsonl").open("x", encoding="utf-8") as inventory_file:
            for item in _inventory(capture_root, log_root):
                encoded = json.dumps(item, ensure_ascii=False)
                inventory_file.write(encoded + "\n")
                path_key = _path_key(item["path"])
                prior = db.execute("SELECT record FROM inventory WHERE path=?", (path_key,)).fetchone()
                if prior is None or json.loads(prior[0]) != json.loads(encoded):
                    issue_counts.update(["inventory_changed"])
                db.execute("UPDATE inventory SET seen_after=1 WHERE path=?", (path_key,))
            missing = db.execute("SELECT count(*) FROM inventory WHERE seen_after=0").fetchone()[0]
            issue_counts.update({"inventory_removed": missing})
    summary["fact_sha256_after"] = sha256_file(fact_path)
    if summary["fact_sha256_before"] != summary["fact_sha256_after"] or fact_identity != _file_identity(fact_path):
        issue_counts.update(["fact_changed"])
    summary["issue_counts"] = {name: count for name, count in sorted(issue_counts.items()) if count}
    summary["status"] = "FAIL" if summary["issue_counts"] else "PASS"
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fact", required=True, type=Path)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit_image_files(args.fact, args.capture_root, args.output_dir)
    except (OSError, ValueError, csv.Error, UnicodeError) as error:
        print(json.dumps({"status": "FAIL", "error_type": type(error).__name__, "full_data_gate": "NOT_EVALUATED"}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
