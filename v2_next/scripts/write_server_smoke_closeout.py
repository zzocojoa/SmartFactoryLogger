from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SCRIPT = REPO_ROOT / "scripts" / "validate_csv_v2_shadow.py"
CLOSEOUT_FILENAME = "server_smoke_closeout_sanitized.json"
SPOT_IMAGE_LINK_COLUMNS = (
    "spot_image_capture_id_nearest",
    "spot_image_path_nearest",
    "spot_image_link_status_nearest",
    "spot_image_link_age_ms_nearest",
)
PROCESS_FACTS = (
    (
        "changeover_candidate_resolution_fact",
        "changeover_candidate_resolution_fact.csv",
    ),
    (
        "process_phase_event_fact",
        "process_phase_event_fact.csv",
    ),
)


def _single_file(bundle_path: Path, pattern: str) -> Path:
    matches = sorted(bundle_path.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {pattern} in bundle, found {len(matches)}")
    return matches[0]


def _optional_file(bundle_path: Path, name: str) -> Path | None:
    path = bundle_path / name
    return path if path.exists() else None


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_validator_output(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _validator_verdict(returncode: int, stdout: str) -> str:
    if returncode == 0 and any(line.strip() == "PASS" for line in stdout.splitlines()):
        return "PASS"
    return "FAIL"


def _to_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


def _to_bool(value: str | None) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _required_bool(mapping: Mapping[str, Any], key: str) -> tuple[bool | None, str | None]:
    value = mapping.get(key)
    if not isinstance(value, bool):
        return None, f"image_capture.{key}_missing_or_not_boolean"
    return value, None


def _required_str(mapping: Mapping[str, Any], key: str) -> tuple[str | None, str | None]:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        return None, f"image_capture.{key}_missing_or_not_string"
    return value, None


def _required_int(mapping: Mapping[str, Any], key: str) -> tuple[int | None, str | None]:
    value = mapping.get(key)
    if type(value) is not int:
        return None, f"image_capture.{key}_missing_or_not_integer"
    return value, None


def _load_spot_config(*, api_base: str | None, spot_config_json: Path | None) -> dict[str, Any]:
    if spot_config_json is not None:
        return json.loads(spot_config_json.read_text(encoding="utf-8-sig"))
    if api_base is None:
        raise ValueError("either --api-base or --spot-config-json is required")
    url = api_base.rstrip("/") + "/api/spot/config"
    with urlopen(url, timeout=8) as response:  # noqa: S310 - operator-provided local/backend URL for closeout.
        return json.loads(response.read().decode("utf-8"))


def _json_string_values(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _json_string_values(item)
        return
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            yield from _json_string_values(item)


def _redaction_flags(payload: Mapping[str, Any]) -> dict[str, bool]:
    values = list(_json_string_values(payload))
    return {
        "raw_image_included": any(
            value.startswith("data:image/") or value.startswith("/9j/") or value.startswith("iVBOR")
            for value in values
        ),
        "camera_url_included": any("://" in value for value in values),
        "secret_included": any(
            marker in value.lower()
            for value in values
            for marker in ("password=", "password:", "token=", "token:", "secret=", "secret:")
        ),
        "full_path_included": any(
            len(value) >= 3
            and (
                (value[1:3] in (":\\", ":/") and value[0].isalpha())
                or value.startswith("\\\\")
            )
            for value in values
        ),
    }


def _fact_summary(prefix: str, parsed: Mapping[str, str], fact_path: Path | None) -> dict[str, Any]:
    validation_source = parsed.get(f"{prefix}_validation_source", "not_applicable")
    if validation_source == "not_applicable":
        presence = "not_applicable"
    elif fact_path is not None and fact_path.exists():
        presence = "present"
    else:
        presence = "not_present"
    return {
        "presence": presence,
        "validation_source": validation_source,
        "fact_file": fact_path.name if fact_path is not None else "not_present",
        "row_count": _to_int(parsed.get(f"{prefix}_actual_row_count")),
        "row_count_match": _to_bool(parsed.get(f"{prefix}_row_count_match")),
        "sha256": parsed.get(f"{prefix}_actual_sha256", ""),
        "sha256_match": _to_bool(parsed.get(f"{prefix}_sha256_match")),
        "source_csv_sha256_match": _to_bool(parsed.get(f"{prefix}_source_csv_sha256_match")),
    }


def _validator_args(
    *,
    python_executable: str,
    bundle_path: Path,
    mode: str,
    csv_file: Path,
    metadata_file: Path,
) -> tuple[list[str], list[str], dict[str, Path | None]]:
    spot_observation_fact = _optional_file(bundle_path, "spot_observation_fact.csv")
    spot_image_fact = _optional_file(bundle_path, "spot_image_fact.csv")
    process_fact_paths = {
        prefix: _optional_file(bundle_path, filename)
        for prefix, filename in PROCESS_FACTS
    }

    args = [
        python_executable,
        str(VALIDATOR_SCRIPT),
        "--v2",
        str(csv_file),
        "--metadata",
        str(metadata_file),
    ]
    display = [
        "python scripts\\validate_csv_v2_shadow.py",
        "--v2",
        csv_file.name,
        "--metadata",
        metadata_file.name,
    ]
    if spot_observation_fact is not None:
        args.extend(["--spot-observation-fact", str(spot_observation_fact)])
        display.extend(["--spot-observation-fact", spot_observation_fact.name])
    if mode == "copied" and spot_image_fact is not None:
        args.extend(["--spot-image-fact", str(spot_image_fact)])
        display.extend(["--spot-image-fact", spot_image_fact.name])
    for prefix, fact_path in process_fact_paths.items():
        if mode == "copied" and fact_path is not None:
            option = "--changeover-candidate-resolution-fact"
            if prefix == "process_phase_event_fact":
                option = "--process-phase-event-fact"
            args.extend([option, str(fact_path)])
            display.extend([option, fact_path.name])
    all_paths: dict[str, Path | None] = {
        "spot_observation_fact": spot_observation_fact,
        "spot_image_fact": spot_image_fact,
    }
    all_paths.update(process_fact_paths)
    return args, display, all_paths


def build_closeout(
    *,
    bundle_path: Path,
    mode: str,
    api_base: str | None,
    spot_config_json: Path | None,
    python_executable: str,
) -> tuple[dict[str, Any], int]:
    csv_file = _single_file(bundle_path, "Factory_Integrated_Log_v2*.csv")
    metadata_file = csv_file.with_suffix(".metadata.json")
    if not metadata_file.exists():
        raise ValueError(f"metadata file not found for {csv_file.name}")

    validator_args, validator_display, fact_paths = _validator_args(
        python_executable=python_executable,
        bundle_path=bundle_path,
        mode=mode,
        csv_file=csv_file,
        metadata_file=metadata_file,
    )
    validator = subprocess.run(
        validator_args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    validator_output = validator.stdout + validator.stderr
    parsed = _parse_validator_output(validator_output)
    rows = _read_csv_dicts(csv_file)
    link_rows = [
        row
        for row in rows
        if any(str(row.get(column) or "").strip() for column in SPOT_IMAGE_LINK_COLUMNS)
    ]
    spot_config = _load_spot_config(api_base=api_base, spot_config_json=spot_config_json)
    image_capture = spot_config.get("image_capture") if isinstance(spot_config, dict) else None
    capture_validation_errors: list[str] = []
    if not isinstance(image_capture, dict):
        image_capture = {}
        capture_validation_errors.append("image_capture_missing_or_not_object")
    capture_enabled, capture_enabled_error = _required_bool(image_capture, "enabled")
    capture_mode, capture_mode_error = _required_str(image_capture, "mode")
    capture_failure_count, capture_failure_count_error = _required_int(image_capture, "failure_count")
    capture_validation_errors.extend(
        error
        for error in (capture_enabled_error, capture_mode_error, capture_failure_count_error)
        if error is not None
    )
    if capture_enabled is not False and capture_enabled_error is None:
        capture_validation_errors.append("image_capture.enabled_must_be_false")
    if capture_mode != "off" and capture_mode_error is None:
        capture_validation_errors.append("image_capture.mode_must_be_off")
    if capture_failure_count != 0 and capture_failure_count_error is None:
        capture_validation_errors.append("image_capture.failure_count_must_be_zero")

    expected_source = "override" if mode == "copied" else "metadata_manifest"
    validation_source = parsed.get("spot_image_fact_validation_source", "not_applicable")
    closeout: dict[str, Any] = {
        "artifact_kind": "server_smoke_bundle",
        "validation_mode": mode,
        "bundle_name": bundle_path.name,
        "csv_file": csv_file.name,
        "metadata_file": metadata_file.name,
        "observation_fact_file": fact_paths["spot_observation_fact"].name
        if fact_paths["spot_observation_fact"] is not None
        else "not_present",
        "image_fact_file": fact_paths["spot_image_fact"].name
        if fact_paths["spot_image_fact"] is not None
        else "not_present",
        "validation_source": validation_source,
        "validator_command": validator_display,
        "validator_exit_code": validator.returncode,
        "validator_verdict": _validator_verdict(validator.returncode, validator_output),
        "spot_image_fact_row_count_match": _to_bool(parsed.get("spot_image_fact_row_count_match")),
        "spot_image_fact_sha256_match": _to_bool(parsed.get("spot_image_fact_sha256_match")),
        "v2_rows": _to_int(parsed.get("v2_rows"), len(rows)),
        "realtime_image_link_rows": len(link_rows),
        "realtime_image_link_blank_rows": len(rows) - len(link_rows),
        "capture_enabled": capture_enabled,
        "capture_mode": capture_mode,
        "capture_failure_count": capture_failure_count,
        "capture_validation_errors": capture_validation_errors,
        "process_facts": {
            prefix: _fact_summary(prefix, parsed, fact_paths[prefix])
            for prefix, _filename in PROCESS_FACTS
        },
    }
    closeout["redaction"] = _redaction_flags(closeout)

    if validation_source != expected_source:
        closeout["validator_verdict"] = "FAIL"
        return closeout, 1
    if closeout["validator_exit_code"] != 0:
        return closeout, 1
    if capture_validation_errors:
        closeout["validator_verdict"] = "FAIL"
        return closeout, 1
    if any(closeout["redaction"].values()):
        closeout["validator_verdict"] = "FAIL"
        return closeout, 1
    return closeout, 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Write sanitized NSIS server smoke closeout JSON.")
    parser.add_argument("--bundle", type=Path, required=True, help="Server smoke bundle directory")
    parser.add_argument("--mode", choices=("copied", "freeze"), required=True)
    parser.add_argument("--api-base", help="Backend API base used only to read /api/spot/config")
    parser.add_argument("--spot-config-json", type=Path, help="Offline /api/spot/config JSON response")
    parser.add_argument("--output", type=Path, help=f"Output JSON path, default {CLOSEOUT_FILENAME} in bundle")
    parser.add_argument("--python-executable", default=sys.executable)
    args = parser.parse_args()

    if bool(args.api_base) == bool(args.spot_config_json):
        parser.error("provide exactly one of --api-base or --spot-config-json")
    bundle_path = args.bundle.resolve()
    output_path = args.output or (bundle_path / CLOSEOUT_FILENAME)
    closeout, exit_code = build_closeout(
        bundle_path=bundle_path,
        mode=args.mode,
        api_base=args.api_base,
        spot_config_json=args.spot_config_json,
        python_executable=args.python_executable,
    )
    output_path.write_text(json.dumps(closeout, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"closeout_json={output_path.name}")
    print(f"validator_exit_code={closeout['validator_exit_code']}")
    print(f"validator_verdict={closeout['validator_verdict']}")
    print(f"validation_source={closeout['validation_source']}")
    print(f"capture_enabled={str(closeout['capture_enabled']).lower()}")
    print(f"capture_mode={closeout['capture_mode']}")
    print(f"redaction_passed={str(not any(closeout['redaction'].values())).lower()}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
