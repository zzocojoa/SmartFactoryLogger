"""Read-only decisions under the user's 2026-10-23 C32 release scope.

Callers bind immutable inputs and runtime identities before using these component
results. No component result grants release promotion or rewrites old verdicts.
"""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

POLICY_ID = 'c32-disabled-low-signal-20261023'


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate policy key')
        value[key] = item
    return value


def load_policy(path, expected_sha256):
    data = Path(path).read_bytes()
    if len(data) > 65536 or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('Policy bytes/hash mismatch')
    policy = json.loads(data.decode('utf-8-sig'), object_pairs_hook=_object)
    if (policy.get('schema') != 'sfl-approved-release-policy-v1'
            or policy.get('policy_id') != POLICY_ID
            or policy.get('approval', {}).get('approved') is not True
            or policy.get('candidate', {}).get('build_commit')
            != 'cd46692ac9c551080c57d8168fa9ea5abd530206'):
        raise ValueError('Unsupported/unapproved policy')
    criteria = policy['operational_criteria']
    if criteria.get('percentile_method') != 'nearest_rank':
        raise ValueError('Unsupported percentile method')
    for key, value in criteria.items():
        if key != 'percentile_method' and not numeric(value):
            raise ValueError('Invalid criterion: ' + key)
    return policy


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def percentile(values, fraction):
    if not values or not 0 < fraction <= 1 or any(not numeric(v) for v in values):
        raise ValueError('Finite nonempty measurements required')
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


def assess_http(endpoint, records, expected_slots, policy, *, boundary_records=None):
    from field_operational_assessment import assess_channel
    summary = assess_channel(endpoint, records, expected_slots)
    key = {'health': 'health_latency_p99_ms_inclusive',
           'data': 'data_latency_p99_ms_inclusive'}[endpoint.name]
    limit = policy['operational_criteria'][key]
    failures = []
    if summary['request_status'] == 'FAIL':
        failures.append('request-error-or-timeout')
    complete = (summary['measurement_status'] == 'COMPLETE'
                and summary['request_status'] == 'PASS' and expected_slots > 0)
    boundaries = [] if boundary_records is None else boundary_records
    boundary_valid = isinstance(boundaries, list) and (boundary_records is None or len(boundaries) == 2)
    previous_end = None
    for row in boundaries if isinstance(boundaries, list) else []:
        if not isinstance(row, dict):
            boundary_valid = False
            continue
        if row.get('request_success') is False or row.get('timeout') is True or row.get('error_type'):
            failures.append('boundary-request-error-or-timeout')
        start, response, end = [row.get(k) for k in ('started_ns', 'response_finished_ns', 'finished_ns')]
        latency = row.get('client_request_and_body_ms')
        valid = (row.get('kind') == 'request' and row.get('endpoint') == endpoint.name
                 and row.get('path') == endpoint.path and row.get('status') == 200
                 and row.get('request_success') is True and row.get('timeout') is False
                 and row.get('body_complete') is True and row.get('decode_complete') is True
                 and all(type(v) is int and v > 0 for v in (start, response, end))
                 and start <= response <= end and numeric(latency)
                 and math.isclose(latency, (response-start)/1e6, rel_tol=1e-9, abs_tol=1e-6))
        boundary_valid = boundary_valid and valid
        if valid and previous_end is not None and start < previous_end:
            boundary_valid = False
        previous_end = end if valid else None
    if boundary_records is not None and boundary_valid:
        boundary_valid = complete and bool(records) and (boundaries[0]['finished_ns'] <= records[0]['started_ns']
                                           and records[-1]['finished_ns'] <= boundaries[1]['started_ns'])
    complete = complete and boundary_valid
    p99 = None
    if complete:
        p99 = percentile([r['client_request_and_body_ms'] for r in [*records, *boundaries]], .99)
        if p99 > limit:
            failures.append('p99-latency-exceeded')
    return {'status': 'FAIL' if failures else 'PASS' if complete else 'INCOMPLETE',
            'scope': endpoint.name + '_HTTP_ONLY', 'policy_id': POLICY_ID,
            'p99_ms': p99, 'limit_ms_inclusive': limit,
            'boundary_count': len(boundaries) if isinstance(boundaries, list) else 0,
            'boundaries_valid': boundary_valid,
            'failures': failures, 'legacy_and_measurement': summary,
            'promotion_allowed': False}


def assess_temperature(rows, service_id, policy):
    """All receipt states count, including sentinel; CSV repetitions do not."""
    times, errors, sequence = [], [], 0
    invalid = False
    for row in rows:
        try:
            seq = int(row['spot_poll_seq'])
            if row['spot_service_instance_id'] != service_id or seq != sequence + 1:
                invalid = True
            sequence = seq
            value = datetime.fromisoformat(row['spot_last_poll_completed_at'].replace('Z', '+00:00'))
            if value.tzinfo is None:
                invalid = True
            if times and value < times[-1]:
                invalid = True
            times.append(value)
            if row['spot_poll_status'] != 'success':
                errors.append(seq)
        except (KeyError, TypeError, ValueError):
            invalid = True
    if invalid or len(times) < 2:
        return {'status': 'INCOMPLETE', 'reason': 'receipt-clock-sequence-or-identity',
                'promotion_allowed': False}
    gaps = [(b - a).total_seconds() * 1000 for a, b in zip(times, times[1:])]
    criteria = policy['operational_criteria']
    p99, maximum = percentile(gaps, .99), max(gaps)
    failures = []
    if p99 > criteria['temperature_receipt_interval_p99_ms_inclusive']:
        failures.append('receipt-p99-exceeded')
    if maximum >= criteria['temperature_receipt_gap_failure_ms_inclusive']:
        failures.append('receipt-gap-exceeded')
    if errors:
        failures.append('poll-error')
    return {'status': 'FAIL' if failures else 'PASS', 'policy_id': POLICY_ID,
            'scope': 'RECEIPT_CADENCE_ONLY', 'service_id': service_id,
            'receipts': len(times), 'intervals': len(gaps), 'p99_ms': p99,
            'max_ms': maximum, 'failures': failures, 'poll_error_sequences': errors,
            'physical_sample_completeness': 'NOT_EVALUATED',
            'learning_suitability': 'NOT_EVALUATED', 'promotion_allowed': False}


def assess_display(samples, *, window_start_ms, window_end_ms,
                   complete, white_screen_events, policy):
    """Accept only correlated presentation records, never DOM load/RAF alone.

    A collector must provide compositor evidence for the visible image paired
    with its response identity. The implementation of that proof is separate.
    """
    valid = (complete is True and type(white_screen_events) is int
             and white_screen_events >= 0 and numeric(window_start_ms)
             and numeric(window_end_ms) and window_end_ms > window_start_ms
             and isinstance(samples, list) and len(samples) >= 2)
    stamps, ids = [], set()
    for sample in samples if isinstance(samples, list) else []:
        if not isinstance(sample, dict):
            valid = False
            continue
        stamp, frame_id = sample.get('presented_at_ms'), sample.get('response_id')
        valid = (valid and sample.get('presentation_confirmed') is True
                 and sample.get('visible') is True and sample.get('occluded') is False
                 and sample.get('fresh_frame_identity_confirmed') is True
                 and numeric(stamp) and isinstance(frame_id, str) and bool(frame_id)
                 and frame_id not in ids)
        if numeric(stamp):
            valid = valid and window_start_ms <= stamp <= window_end_ms
            valid = valid and (not stamps or stamp > stamps[-1])
            stamps.append(stamp)
        if isinstance(frame_id, str):
            ids.add(frame_id)
    if not valid:
        return {'status': 'INCOMPLETE', 'reason': 'missing-complete-correlated-presentation',
                'promotion_allowed': False}
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    boundary_gaps = [stamps[0] - window_start_ms, window_end_ms - stamps[-1]]
    criteria = policy['operational_criteria']
    p95, p99, maximum = percentile(gaps, .95), percentile(gaps, .99), max(gaps + boundary_gaps)
    failures = []
    if p95 > criteria['image_display_interval_p95_ms_inclusive']:
        failures.append('display-p95-exceeded')
    if p99 > criteria['image_display_interval_p99_ms_inclusive']:
        failures.append('display-p99-exceeded')
    if maximum >= criteria['image_display_gap_failure_ms_inclusive']:
        failures.append('display-gap-exceeded')
    if white_screen_events > criteria['white_screen_events_max']:
        failures.append('white-screen')
    return {'status': 'FAIL' if failures else 'PASS', 'scope': 'ONE_CLIENT_DISPLAY_WINDOW_ONLY',
            'policy_id': POLICY_ID, 'p95_ms': p95, 'p99_ms': p99, 'max_gap_ms': maximum,
            'boundary_gaps_ms': boundary_gaps, 'failures': failures, 'promotion_allowed': False}


def assess_rollback(record, policy):
    approved = policy['rollback']
    valid = all(record.get(k) == approved[k] for k in ('build_commit', 'installer_sha256',
                                                      'request_path', 'http_status', 'reason'))
    valid = valid and record.get('normal_ui_close_requested') is True
    valid = valid and record.get('forced_exit') is False and record.get('data_validation_passed') is True
    exits = record.get('native_exit_codes')
    valid = valid and isinstance(exits, list) and bool(exits)
    valid = valid and all(type(x) is int and x == 0 for x in (exits or []))
    valid = valid and type(record.get('pending_writes')) is int and record['pending_writes'] == 0
    valid = valid and type(record.get('storage_failures')) is int and record['storage_failures'] == 0
    start, error, end = [record.get(k) for k in ('close_requested_at', 'error_at', 'exit_at')]
    valid = valid and all(numeric(v) for v in (start, error, end))
    valid = valid and start <= error <= end
    return {'disposition': 'ACCEPTED_KNOWN_LIMITATION' if valid else 'NOT_ACCEPTED',
            'legacy_verdict_preserved': True, 'promotion_allowed': False}
