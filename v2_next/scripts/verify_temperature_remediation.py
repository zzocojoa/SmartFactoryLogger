"""Read-only full-file baseline and explicitly limited production-module replay.

The input package is private and never copied. Output contains aggregate evidence
and sample-sequence decision differences, not raw temperatures or identifiers.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.temperature_operational import TEMPERATURE_OPERATIONAL_RULE_VERSION

EXPECTED_CSV = "1d368c103e9d269e5dda4dcf0d6d5d67077375dfdeb1a9c7f94c1197f441f965"
EXPECTED_METADATA = "b1bb29c1078c5c7eb253b15d67296f3f175819c1dec6e0237fec6c4f7cfd2202"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dt(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify(package: Path, output: Path):
    source = package / "inputs/Factory_Integrated_Log_v2_20260909_130456.csv"
    metadata_path = source.with_suffix(".metadata.json")
    assert sha(source) == EXPECTED_CSV and sha(metadata_path) == EXPECTED_METADATA
    metadata = read_json(metadata_path)
    supplied = read_json(package / "analysis_summary.json")
    fixtures = {}
    fixture_results = []
    for spec in read_json(package / "fixtures/fixture_manifest.json")["fixtures"]:
        path = package / "fixtures" / spec["name"]
        assert sha(path) == spec["sha256"]
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == spec["logical_rows"]
        assert {r["sample_seq"] for r in rows} == {
            str(seq) for lo, hi in spec["sample_seq_ranges"] for seq in range(lo, hi+1)}
        fixtures.update({row["sample_seq"]: row for row in rows})
        fixture_results.append({"name": spec["name"], "rows": len(rows), "sha256": spec["sha256"]})

    output.mkdir(parents=True, exist_ok=True)
    categories = {key: Counter() for key in supplied["categories"]}
    nonblank, baseline_status, sentinel, violations = Counter(), Counter(), Counter(), Counter()
    polls = defaultdict(set)
    replay_status, transitions, phase_transitions, expectedness_transitions = Counter(), Counter(), Counter(), Counter()
    max_delay, delay_seq = -1, None
    selected, replay_selected = {}, {}
    source_metadata = metadata["spot_temperature_shadow_metadata"]
    threshold_sec = source_metadata["poll_freshness_threshold_sec"]
    ttl_sec = source_metadata["cache_expiry_threshold_sec"]
    service = CSVLoggerService()
    passthrough = [
        "spot_poll_status", "spot_raw_validity", "spot_source_freshness", "spot_cache_status",
        "temperature_value_origin", "spot_device_status_code", "spot_error_code",
        "spot_last_poll_completed_at", "spot_last_valid_value_at", "spot_snapshot_age_ms",
        "spot_value_age_ms", "spot_service_instance_id", "spot_poll_seq", "spot_observation_seq",
        "spot_temperature_observed_c", "extruder_process_state_online", "Count", "Speed",
        "Product_No_operator", "Mold_No_operator", "spot_diagnostic_evidence_codes",
    ]
    diff_columns = ["sample_seq", "old_status", "new_status", "old_effective_age_ms", "new_effective_age_ms",
                    "old_phase", "new_phase", "old_expectedness", "new_expectedness"]
    with source.open(encoding="utf-8-sig", newline="") as stream, \
         (output / "replay_diff.csv").open("w", encoding="utf-8", newline="") as diff_stream, \
         patch("backend.FacilityData.repository.config.SPOT_REFRESH_INTERVAL", threshold_sec / 3):
        reader = csv.reader(stream, strict=True)
        header = next(reader)
        assert len(header) == 109 and header == metadata["schema_metadata"]["v2_columns"]
        assert hashlib.sha256(json.dumps(header, separators=(",", ":")).encode()).hexdigest() == metadata["schema_metadata"]["active_column_hash"]
        diff_writer = csv.DictWriter(diff_stream, fieldnames=diff_columns)
        diff_writer.writeheader()
        for count, values in enumerate(reader, 1):
            assert len(values) == 109
            row = dict(zip(header, values))
            assert row["sample_seq"] == str(count)
            if row["sample_seq"] in fixtures:
                assert row == fixtures.pop(row["sample_seq"])
            for name in categories:
                categories[name][row[name]] += 1
            for name, value in row.items():
                nonblank[name] += int(value != "")
            for name in supplied["numeric"]:
                if row[name]:
                    assert math.isfinite(float(row[name]))
            status = row["temperature_output_status"]
            baseline_status[status] += 1
            if row["spot_temperature_raw"].strip() in {"6553.4", "6553.5"}:
                sentinel[status] += 1
                violations["sentinel_output_leak"] += bool(row["Temperature"])
            violations["nonvalid_output_leak"] += bool(status != "valid" and row["Temperature"])
            violations["quality_mismatch"] += (row["Temperature_quality"], row["Temperature_missing_reason"]) != service._quality_for_temperature_operational_status(status)
            violations["low_count_production"] += bool(row["Count"] and 0 <= float(row["Count"]) <= 2 and row["process_phase_candidate"] == "production_stable")
            violations["startup_key"] += bool(status == "startup_pending" and row["spot_observation_key"])
            if row["spot_poll_seq"] and int(row["spot_poll_seq"]) > 0:
                polls[row["spot_service_instance_id"]].add(int(row["spot_poll_seq"]))
            lag = (dt(row["ingest_timestamp"]) - dt(row["timestamp_utc"])).total_seconds()*1000
            if lag > max_delay:
                max_delay, delay_seq = lag, row["sample_seq"]
            if 15 <= count <= 908:
                assert row["spot_poll_seq"] == "1" and status == "stale" and not row["Temperature"]
            if count == 909:
                assert row["spot_poll_seq"] == "2" and status == "valid"
            if count in (15, 26, 27, 909):
                selected[row["sample_seq"]] = {"old_status": status, "sample_to_ingest_ms": lag,
                    "effective_age_ms": row["spot_effective_age_ms_at_row"]}

            # No invented monotonic endpoint, error flag, PLC usable proof, or fact evidence.
            inputs = {name: row[name] for name in passthrough if row.get(name)}
            inputs.update(Time=row["timestamp_utc"], Status=row.get("Status", ""),
                          spot_cache_expiry_threshold_sec=ttl_sec)
            if row.get("MainPress"):
                inputs["Press"] = row["MainPress"]
            if row.get("cache_fallback_allowed"):
                inputs["cache_fallback_allowed"] = row["cache_fallback_allowed"].lower() == "true"
            data = FactoryData(**inputs)
            phase = service._derive_process_phase_decision(data, dt(row["timestamp_utc"]), count)
            decision = service._derive_temperature_operational_decision(
                data, phase.process_phase_candidate, dt(row["ingest_timestamp"]), None, True)
            new_status = decision.temperature_output_status
            assert new_status != "valid" or (decision.spot_effective_freshness_at_row == "fresh" and decision.spot_row_age_clock_status == "ok")
            assert row["spot_temperature_raw"].strip() not in {"6553.4", "6553.5"} or new_status != "valid"
            replay_status[new_status] += 1
            transitions[f"{status}->{new_status}"] += 1
            phase_transitions[f"{row['process_phase_candidate']}->{phase.process_phase_candidate}"] += 1
            expectedness_transitions[f"{row['temperature_expectedness_candidate']}->{decision.temperature_expectedness_candidate}"] += 1
            diff_writer.writerow(dict(zip(diff_columns, [row["sample_seq"], status, new_status,
                row["spot_effective_age_ms_at_row"], decision.spot_effective_age_ms_at_row,
                row["process_phase_candidate"], phase.process_phase_candidate,
                row["temperature_expectedness_candidate"], decision.temperature_expectedness_candidate])))
            if count in (15, 26, 27, 909):
                replay_selected[str(count)] = {"status": new_status, "age_ms": decision.spot_effective_age_ms_at_row,
                                                "clock_basis": "recorded_ingest_minus_recorded_poll_UTC"}
        physical_lines = reader.line_num

    assert count == 186878 and physical_lines == 373743 and not fixtures
    assert all(dict(values) == supplied["categories"][name] for name, values in categories.items())
    assert {k: v for k, v in nonblank.items() if v} == supplied["column_nonblank_counts"]
    assert not any(violations.values())
    assert sha(source) == EXPECTED_CSV and sha(metadata_path) == EXPECTED_METADATA
    baseline = {"kind": "original_read_only_baseline", "source_name": source.name,
        "source_sha256": EXPECTED_CSV, "metadata_sha256": EXPECTED_METADATA,
        "rows": count, "columns": len(header), "physical_lines": physical_lines,
        "status_counts": dict(baseline_status), "sentinel_status_counts": dict(sentinel),
        "violations": dict(violations), "all_24_categorical_counts_match_package": True,
        "all_nonblank_counts_match_package": True, "sample_seq_continuous": True,
        "max_sample_to_ingest_ms": max_delay, "max_delay_sample_seq": delay_seq,
        "selected_timing": selected, "fixtures": fixture_results,
        "per_service_ranges_without_identifiers": [{"first": min(v), "last": max(v), "distinct": len(v),
            "wide_csv_unobserved_polls": max(v)-min(v)+1-len(v)} for v in polls.values()],
        "actual_fact_verification": "not_verified_missing_original_fact",
        "attestation": {key: metadata["spot_configuration_snapshot"][key] for key in
            ["config_attestation_status", "config_operator_verified", "low_signal_comparator_verified", "diagnostics_collection_mode"]}}
    replay = {"kind": "production_repository_wall_clock_replay", "source_sha256": EXPECTED_CSV,
        "rule_version": TEMPERATURE_OPERATIONAL_RULE_VERSION, "rows": count,
        "threshold_ms_from_metadata": threshold_sec*1000, "ttl_ms_from_metadata": ttl_sec*1000,
        "status_counts": dict(replay_status), "status_transitions": dict(transitions),
        "phase_transitions": dict(phase_transitions), "expectedness_transitions": dict(expectedness_transitions),
        "selected_timing": replay_selected, "limitations": [
            "No recorded monotonic endpoints: this is UTC fallback replay, not reconstructed runtime clocks.",
            "No PLC error/usable/grace proof: phase and dependent expectedness fail closed; actual PLC failure is not established.",
            "No original observation fact: links, fact loss, multi-service behavior cannot be verified from this CSV.",
            "Fact initialization/storage contention is proven only in controlled Event tests, not as the historical delay cause.",
            "Every output row is a replay comparison, not a new source CSV closeout."]}
    save(output / "baseline_report.json", baseline)
    save(output / "replay_report.json", replay)
    print(json.dumps({"baseline_rows": count, "replay_rows": count, "hashes_unchanged": True,
                      "status_transitions": dict(transitions)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    verify(args.package, args.output)
