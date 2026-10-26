"""Operational evidence v2: collection, request health and fitness are distinct.

No factory latency budget is inferred. Legacy summaries remain reproducible.
This module never grants release approval or infers device/sample loss from HTTP.
"""
import math

POLICY = 'operational-evidence-v2'


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def assess_channel(endpoint, records, expected_slots, *, legacy_summary=None):
    # Local import keeps the legacy sampler usable without a circular import.
    from field_http_sampling import summarize_channel
    legacy = legacy_summary if legacy_summary is not None else summarize_channel(
        endpoint, records, expected_slots)
    run = longest = 0
    run_start = None
    longest_span_ms = 0
    previous_success = None
    max_success_gap_ms = None
    invalid_clock = 0
    previous_finish = None
    previous_sequence = None
    last_ms = None
    for row in records:
        if not isinstance(row, dict):
            run, run_start, previous_success, previous_sequence = 0, None, None, None
            continue
        sequence = row.get('sequence')
        if (type(sequence) is not int or previous_sequence is None
                or sequence != previous_sequence + 1):
            run, run_start, previous_success = 0, None, None
        previous_sequence = sequence if type(sequence) is int else None
        if row.get('kind') != 'request':
            run, run_start, previous_success = 0, None, None
            continue
        start, finish = row.get('started_ns'), row.get('finished_ns')
        valid_clock = (type(start) is int and type(finish) is int and 0 < start <= finish
                       and (previous_finish is None or start >= previous_finish))
        latency = row.get('client_request_and_body_ms')
        last_ms = latency if numeric(latency) else None
        if 'response_finished_ns' in row:
            response_end = row['response_finished_ns']
            valid_clock = (valid_clock and type(response_end) is int
                           and start <= response_end <= finish and numeric(latency)
                           and math.isclose(latency, (response_end - start) / 1e6,
                                            rel_tol=1e-9, abs_tol=1e-6))
        invalid_clock += not valid_clock
        previous_finish = finish if valid_clock else previous_finish
        success = row.get('request_success') is True and row.get('timeout') is False
        over = (success and numeric(latency) and endpoint.failure_ms is not None
                and latency > endpoint.failure_ms and valid_clock)
        if over:
            run += 1
            run_start = start if run_start is None else run_start
            longest = max(longest, run)
            longest_span_ms = max(longest_span_ms, (finish - run_start) / 1e6)
        else:
            run, run_start = 0, None
        if success and valid_clock:
            if previous_success is not None:
                gap = (finish - previous_success) / 1e6
                max_success_gap_ms = max(max_success_gap_ms or 0, gap)
            previous_success = finish
        elif not valid_clock:
            previous_success = None
    complete = legacy['schedule_complete'] and invalid_clock == 0
    errors = legacy['request_errors'] or legacy['timeouts']
    return {
        'policy': POLICY,
        'measurement_status': 'COMPLETE' if complete else 'INCOMPLETE',
        'request_status': 'FAIL' if errors else 'PASS' if legacy['requests'] else 'NOT_EVALUATED',
        'expected_slots': expected_slots, 'requests': legacy['requests'],
        'missed_slots': legacy['missed_slots'], 'cancelled_slots': legacy['cancelled_slots'],
        'unaccounted_slots': legacy['unaccounted_slots'],
        'invalid_record_count': legacy['invalid_record_count'],
        'invalid_clock_records': invalid_clock,
        'request_errors': legacy['request_errors'], 'timeouts': legacy['timeouts'],
        'diagnostic_reference_ms': endpoint.failure_ms,
        'reference_exceedances': legacy['threshold_failures'],
        'first_ms': legacy['first_ms'], 'last_ms': last_ms, 'max_ms': legacy['max_ms'],
        'p50_ms': legacy['p50_ms'], 'p95_ms': legacy['p95_ms'], 'p99_ms': legacy['p99_ms'],
        'longest_consecutive_exceedances': longest,
        'longest_exceedance_sample_span_ms': longest_span_ms,
        'max_observed_success_gap_ms': max_success_gap_ms,
        'span_is_continuous_outage_duration': False,
        'operational_performance': 'NOT_EVALUATED',
        'operational_budget': None,
        'display_freshness': 'NOT_EVALUATED',
        'stored_data_integrity': 'NOT_EVALUATED',
        'device_sample_completeness': 'NOT_EVALUATED',
        'legacy_status': legacy['http_component_status'],
        'release_gate': 'HOLD', 'promotion_allowed': False,
    }


def combine(channels, *, collector_errors=False):
    values = list(channels.values())
    incomplete = not values or any(v['measurement_status'] != 'COMPLETE' for v in values)
    failed = collector_errors or any(v['request_status'] == 'FAIL' for v in values)
    return {
        'policy': POLICY, 'channels': channels,
        'collection_status': 'FAIL' if failed else 'INCOMPLETE' if incomplete else 'COMPLETE',
        'measurement_status': 'INCOMPLETE' if collector_errors or incomplete else 'COMPLETE',
        'request_status': 'FAIL' if any(v['request_status'] == 'FAIL' for v in values)
                          else 'PASS' if values and all(v['request_status'] == 'PASS' for v in values)
                          else 'NOT_EVALUATED',
        'operational_performance': 'NOT_EVALUATED',
        'display_freshness': 'NOT_EVALUATED', 'stored_data_integrity': 'NOT_EVALUATED',
        'device_sample_completeness': 'NOT_EVALUATED',
        'remaining_evidence': ['operator_ui_observation', 'approved_process_timing_requirements',
                               'closed_fact_csv_image_reconciliation'],
        'release_gate': 'HOLD', 'promotion_allowed': False,
    }
