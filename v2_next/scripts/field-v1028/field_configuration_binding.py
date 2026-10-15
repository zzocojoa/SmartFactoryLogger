"""Compare reported runtime configuration with a separately pinned final attestation.

This is read-only evidence binding, not physical device/comparator verification or
approval of a reference. The protected caller must supply the approved reference
hash; a self-consistent JSON document alone cannot establish approval.
"""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import ipaddress
import json
import math
import os
import re
import time

import field_http_sampling as http
import field_installation_binding as binding
from field_resource_sampling import error_record


PROFILE_APPROVAL_SHA = '94873cc2a677ccc79bfbda11f65b736717ff97ed0bf07fc8449254253cf995df'
FIELD_SEQUENCE_APPROVAL_SHA = '6517011d8f51eb4cff560bf83c8dcbb471bd4add99f21cdac59387d3d1c93685'
STRICT_SCOPE = 'VERIFIED_COMPARATOR_CONFIGURATION'
DISABLED_SCOPE = 'DISABLED_LOW_SIGNAL_FIELD_TRIAL'
DISABLED_SCHEMA = 'sfl-field-configuration-disabled-low-signal-v1'
PROFILE = {
    'spot_model_info': 'SPOT+ AL', 'spot_app_mode': 'App1: AL E',
    'spot_range_min_c': 200.0, 'spot_range_max_c': 900.0,
    'spot_analog_4ma_c': 200.0, 'spot_analog_20ma_c': 800.0,
    'low_signal_alarm_enabled': False, 'low_signal_threshold_pc': 2.0,
    'peak_picker_enabled': False, 'limiter_enabled': False, 'averager_enabled': False,
    'modemaster_enabled': False, 'ratio_raw_enabled': False,
    'window_obscuration_pc': 12.0, 'focus_mm': 6071.0,
}
PAYLOAD_KEYS = (
    'spot_config_revision', 'build_git_commit', 'settings_file_sha256', 'spot_ip',
    'spot_model_info', 'spot_app_mode', 'spot_range_min_c', 'spot_range_max_c',
    'spot_analog_4ma_c', 'spot_analog_20ma_c', 'low_signal_alarm_enabled',
    'low_signal_threshold_pc', 'low_signal_comparator', 'low_signal_comparator_configured_verified',
    'peak_picker_enabled', 'limiter_enabled', 'averager_enabled', 'modemaster_enabled',
    'ratio_raw_enabled', 'window_obscuration_pc', 'focus_mm', 'diagnostics_collection_mode',
)
ATTESTATION_KEYS = (
    'low_signal_comparator_verified', 'config_source', 'config_operator_verified_requested',
    'config_operator_verified', 'config_attestation_status', 'spot_config_fingerprint_sha256',
    'spot_config_verified_at', 'spot_config_verified_by', 'spot_config_verified_fingerprint_sha256',
    'device_config_readback_status', 'device_config_fingerprint_sha256',
    'config_drift_detected', 'config_drift_fields', 'spot_ratio_raw_enabled',
)


class ReferenceSnapshot(dict):
    """Scope from a pinned, approved reference; never from runtime JSON fields."""

    def __init__(self, snapshot):
        super().__init__(snapshot)


def scope_fields(reference):
    limited = type(reference) is ReferenceSnapshot
    return dict(validation_scope=DISABLED_SCOPE if limited else STRICT_SCOPE,
                physical_device_gate='NOT_TESTED' if limited else 'NOT_EVALUATED',
                formal_qa_gate='HOLD')


def canonical_fingerprint(snapshot):
    payload = {key: snapshot[key] for key in PAYLOAD_KEYS}
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def utc_timestamp(value):
    binding.require(isinstance(value, str) and 0 < len(value) <= 40, 'configuration-time-format')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    binding.require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0,
                    'configuration-time-not-utc')
    return stamp.timestamp()


def review_snapshot(snapshot, expected=None, *, candidate=binding.CANDIDATE_1028):
    """Return every observed mismatch without coercing strings/bools into numbers."""
    binding.require(type(candidate) is binding.CandidateIdentity, 'candidate-identity-type')
    candidate.validate()
    issues = []
    if not isinstance(snapshot, dict):
        return dict(status='FAIL', issues=['configuration-object-missing'])

    def check(condition, reason):
        if not condition:
            issues.append(reason)

    for key in (*PAYLOAD_KEYS, *ATTESTATION_KEYS, 'config_captured_at'):
        check(key in snapshot, 'missing:' + key)
    for key, value in PROFILE.items():
        actual = snapshot.get(key)
        numeric = type(value) is float
        matches = ((type(actual) in (int, float) and math.isfinite(actual) and actual == value)
                   if numeric else type(actual) is type(value) and actual == value)
        check(matches, 'approved-profile:' + key)
    check(snapshot.get('spot_config_revision') == 'spot-config-provenance-v1', 'revision')
    check(snapshot.get('build_git_commit') == candidate.commit, 'candidate-build')
    for key in ('settings_file_sha256', 'spot_config_fingerprint_sha256', 'spot_config_verified_fingerprint_sha256'):
        check(isinstance(snapshot.get(key), str) and re.fullmatch('[0-9a-f]{64}', snapshot[key]), 'sha256:' + key)
    try:
        ipaddress.IPv4Address(snapshot.get('spot_ip'))
        check(isinstance(snapshot.get('spot_ip'), str), 'spot-ip-text')
    except (ValueError, TypeError):
        issues.append('spot-ip-format')
    check(snapshot.get('low_signal_comparator') in ('lt', 'lte'), 'comparator-unverified')
    check(snapshot.get('diagnostics_collection_mode') == 'async_fact_only', 'diagnostics-mode')
    scope = scope_fields(expected if expected is not None else snapshot)
    comparator_verified = scope['validation_scope'] == STRICT_SCOPE
    for key in ('low_signal_comparator_configured_verified', 'low_signal_comparator_verified'):
        check(snapshot.get(key) is comparator_verified,
              ('not-verified:' if comparator_verified else 'must-remain-unverified:') + key)
    for key in ('config_operator_verified_requested', 'config_operator_verified'):
        check(snapshot.get(key) is True, 'not-verified:' + key)
    check(snapshot.get('spot_ratio_raw_enabled') is snapshot.get('ratio_raw_enabled')
          and type(snapshot.get('spot_ratio_raw_enabled')) is bool, 'ratio-alias')
    check(snapshot.get('config_source') == 'runtime_config_attestation', 'configuration-source')
    check(snapshot.get('config_attestation_status') == 'verified', 'attestation-status')
    check(snapshot.get('config_drift_detected') is False and snapshot.get('config_drift_fields') == [], 'config-drift')
    check(snapshot.get('spot_config_verified_by') == 'USER_SELF', 'operator-identity')
    try:
        verified = utc_timestamp(snapshot.get('spot_config_verified_at'))
        captured = utc_timestamp(snapshot.get('config_captured_at'))
        check(verified <= captured <= time.time() + 2, 'configuration-time-order')
    except (ValueError, OverflowError):
        issues.append('configuration-time-invalid')
    computed = None
    try:
        computed = canonical_fingerprint(snapshot)
        check(snapshot.get('spot_config_fingerprint_sha256') == computed, 'fingerprint-recomputed-mismatch')
        check(snapshot.get('spot_config_verified_fingerprint_sha256') == computed, 'attested-fingerprint-mismatch')
    except (KeyError, TypeError, ValueError):
        issues.append('fingerprint-payload-invalid')
    readback = snapshot.get('device_config_readback_status')
    check(readback in ('matched', 'not_supported'), 'device-readback-blocked')
    if readback == 'matched':
        check(computed is not None and snapshot.get('device_config_fingerprint_sha256') == computed,
              'device-fingerprint-mismatch')
    elif readback == 'not_supported':
        check(snapshot.get('device_config_fingerprint_sha256') == '', 'unsupported-device-fingerprint')
    if expected is not None:
        for key in (*PAYLOAD_KEYS, *ATTESTATION_KEYS):
            check(key in snapshot and key in expected and type(snapshot[key]) is type(expected[key])
                  and snapshot[key] == expected[key], 'pinned-reference:' + key)
    return dict(status='FAIL' if issues else 'PASS', issues=issues, recomputed_fingerprint=computed,
                profile_scope='SOFTWARE_REPRESENTED_APPROVED_FIELDS', **scope)


@contextmanager
def configuration_reference(path, expected_sha256, *, candidate=binding.CANDIDATE_1028):
    """Hold the externally pinned bytes across the observation; never auto-attest."""
    binding.require(isinstance(expected_sha256, str) and re.fullmatch('[0-9a-f]{64}', expected_sha256),
                    'configuration-reference-external-hash')
    with binding.locked_read(path) as stream:
        binding.require(os.fstat(stream.fileno()).st_size <= 32768, 'configuration-reference-budget')
        raw = stream.read(32769)
        binding.require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'configuration-reference-hash')
        value = binding.strict_json(raw)
        binding.require(value.get('schema') in ('sfl-field-configuration-reference-v1', DISABLED_SCHEMA)
                        and value.get('profile_approval_sha256') == PROFILE_APPROVAL_SHA,
                        'configuration-reference-approval-binding')
        snapshot = value.get('snapshot')
        if value['schema'] == DISABLED_SCHEMA:
            binding.require(value.get('field_sequence_approval_sha256') == FIELD_SEQUENCE_APPROVAL_SHA
                            and isinstance(snapshot, dict), 'field-sequence-approval-binding')
            snapshot = ReferenceSnapshot(snapshot)
        binding.require(review_snapshot(snapshot, candidate=candidate)['status'] == 'PASS',
                        'configuration-reference-not-verified')
        yield snapshot
        binding.require(binding.stream_fact(stream) == dict(bytes=len(raw), sha256=expected_sha256),
                        'configuration-reference-changed')


def capture_configuration(payload, main, backend, port, sessions, expected):
    result = dict(configuration_status='FAIL', started_ns=time.perf_counter_ns(),
                  errors=[], field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)
    try:
        result.update(scope_fields(expected))
        binding.require(payload.active, 'payload-context-not-active')
        binding.require(main.exe == os.path.normcase(str(payload.root / 'smart-factory.exe'))
                        and backend.exe == os.path.normcase(str(payload.root / binding.BACKEND)),
                        'installed-process-path')
        binding.require(review_snapshot(expected, candidate=payload.candidate)['status'] == 'PASS',
                        'configuration-expectation-invalid')
        result['process_before'] = binding.read_process_binding(main, backend, port)
        record, raw = http.fetch_sample(port, http.SPOT_CONFIG)
        result.update(configuration_record=record, configuration_body_hex=raw.hex())
        binding.require(record['request_success'], 'configuration-request-failed')
        snapshot = binding.strict_json(raw).get('image')
        result['review'] = review_snapshot(snapshot, expected, candidate=payload.candidate)
        binding.require(isinstance(snapshot, dict)
                        and snapshot.get('spot_service_instance_id') == sessions['spot_service_instance_id'],
                        'configuration-spot-session')
        binding.require(utc_timestamp(snapshot.get('config_captured_at')) >= backend.created - 1,
                        'configuration-predates-backend')
        result['process_after'] = binding.read_process_binding(main, backend, port)
        binding.require(result['process_after'] == result['process_before'], 'configuration-process-changed')
        binding.require(result['review']['status'] == 'PASS', 'configuration-review-failed')
        result['configuration_status'] = 'PASS'
    except Exception as error:
        result['errors'].append(error_record(error))
    result['finished_ns'] = time.perf_counter_ns()
    return result
