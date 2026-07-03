from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from backend.FacilityData.spot_image_linkage_fact import (
    SPOT_IMAGE_LINKAGE_FACT_FILENAME,
    SPOT_IMAGE_LINKAGE_REPORT_FILENAME,
    build_spot_image_linkage_fact_manifest,
    write_spot_image_linkage_artifacts,
)


def infer_spot_image_linkage_from_csv(
    *,
    input_path: Path,
    spot_image_fact_path: Path,
    fact_output_path: Path,
    report_output_path: Path,
    metadata_path: Path | None = None,
) -> tuple[list[dict[str, str]], dict]:
    facts, report = write_spot_image_linkage_artifacts(
        source_csv_path=input_path,
        spot_image_fact_path=spot_image_fact_path,
        fact_output_path=fact_output_path,
        report_output_path=report_output_path,
    )
    update_spot_image_linkage_fact_manifest(
        metadata_path or input_path.with_suffix(".metadata.json"),
        input_path=input_path,
        spot_image_fact_path=spot_image_fact_path,
        fact_output_path=fact_output_path,
        report_output_path=report_output_path,
    )
    return facts, report


def update_spot_image_linkage_fact_manifest(
    metadata_path: Path,
    *,
    input_path: Path,
    spot_image_fact_path: Path,
    fact_output_path: Path,
    report_output_path: Path,
) -> bool:
    if not metadata_path.exists():
        return False

    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    schema_metadata = metadata.get("schema_metadata")
    if not isinstance(schema_metadata, dict):
        schema_metadata = {}
        metadata["schema_metadata"] = schema_metadata
    manifest_keys = schema_metadata.get("posthoc_fact_manifests")
    if not isinstance(manifest_keys, list):
        manifest_keys = []
        schema_metadata["posthoc_fact_manifests"] = manifest_keys
    if "spot_image_linkage_fact_manifest" not in manifest_keys:
        manifest_keys.append("spot_image_linkage_fact_manifest")

    metadata["spot_image_linkage_fact_manifest"] = build_spot_image_linkage_fact_manifest(
        fact_path=fact_output_path,
        report_path=report_output_path,
        source_csv_path=input_path,
        spot_image_fact_path=spot_image_fact_path,
    )
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create post-hoc SPOT image linkage fact/report without mutating realtime CSV rows."
    )
    parser.add_argument("--input", type=Path, required=True, help="Factory_Integrated_Log_v2*.csv input")
    parser.add_argument("--spot-image-fact", type=Path, required=True, help="spot_image_fact.csv input")
    parser.add_argument(
        "--metadata",
        type=Path,
        help="Optional Factory_Integrated_Log_v2*.metadata.json to update with post-hoc fact manifest",
    )
    parser.add_argument(
        "--fact-output",
        type=Path,
        default=Path(SPOT_IMAGE_LINKAGE_FACT_FILENAME),
        help=f"Output CSV, default {SPOT_IMAGE_LINKAGE_FACT_FILENAME}",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path(SPOT_IMAGE_LINKAGE_REPORT_FILENAME),
        help=f"Output JSON, default {SPOT_IMAGE_LINKAGE_REPORT_FILENAME}",
    )
    args = parser.parse_args()

    facts, report = infer_spot_image_linkage_from_csv(
        input_path=args.input,
        spot_image_fact_path=args.spot_image_fact,
        fact_output_path=args.fact_output,
        report_output_path=args.report_output,
        metadata_path=args.metadata,
    )
    counts = report["counts"]
    print(f"spot_image_linkage_fact_rows={len(facts)}")
    print(f"matched_rows={counts['matched']}")
    print(f"ambiguous_rows={counts['ambiguous']}")
    print(f"fact_output={args.fact_output.name}")
    print(f"report_output={args.report_output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
