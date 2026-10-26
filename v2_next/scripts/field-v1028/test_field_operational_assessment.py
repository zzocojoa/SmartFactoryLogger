import pytest

from field_http_sampling import ENDPOINTS, summarize_channel
from field_operational_assessment import assess_channel, combine


def request(sequence, ms, **changes):
    start = 1_000_000_000 + sequence * 2_000_000_000
    return dict(sequence=sequence, kind='request', started_ns=start,
                finished_ns=start + round(ms * 1e6), client_request_and_body_ms=ms,
                start_lateness_ms=0, request_success=True, timeout=False, **changes)


@pytest.mark.parametrize('endpoint,latency', [(ENDPOINTS[0], 425), (ENDPOINTS[1], 700)])
def test_slow_success_is_diagnostic_not_operational_failure(endpoint, latency):
    rows = [request(0, latency)]
    old = summarize_channel(endpoint, rows, 1)
    new = assess_channel(endpoint, rows, 1)
    assert old['http_component_status'] == 'FAIL'
    assert new['measurement_status'] == 'COMPLETE' and new['request_status'] == 'PASS'
    assert new['reference_exceedances'] == 1
    assert new['operational_performance'] == 'NOT_EVALUATED'
    assert combine({'endpoint': new})['collection_status'] == 'COMPLETE'
    assert new['release_gate'] == 'HOLD' and not new['promotion_allowed']


def test_missed_synthetic_image_slots_are_not_saved_image_loss():
    rows = [request(0, 50), {'sequence': 1, 'kind': 'missed_slot'}]
    value = assess_channel(ENDPOINTS[2], rows, 2)
    assert value['measurement_status'] == 'INCOMPLETE'
    assert value['request_status'] == 'PASS'
    assert value['stored_data_integrity'] == value['display_freshness'] == 'NOT_EVALUATED'
    assert combine({'image': value})['collection_status'] == 'INCOMPLETE'


def test_error_remains_failure_even_with_incomplete_measurement():
    row = request(0, 5000)
    row.update(timeout=True, request_success=False)
    value = assess_channel(ENDPOINTS[0], [row], 2)
    assert value['request_status'] == 'FAIL'
    assert value['measurement_status'] == 'INCOMPLETE'
    assert combine({'health': value})['collection_status'] == 'FAIL'


def test_exceedance_spans_are_not_claimed_as_continuous_outages():
    rows = [request(0, 250), request(1, 300), {'sequence': 2, 'kind': 'missed_slot'},
            request(3, 250), request(4, 20)]
    value = assess_channel(ENDPOINTS[0], rows, 5)
    assert value['longest_consecutive_exceedances'] == 2
    assert value['longest_exceedance_sample_span_ms'] == 2300
    assert not value['span_is_continuous_outage_duration']
    assert value['reference_exceedances'] == 3


@pytest.mark.parametrize('change', ['duplicate', 'nan', 'clock', 'backwards', 'bool', 'unaccounted'])
def test_incomplete_or_malformed_measurements_cannot_pass(change):
    rows = [request(0, 20), request(1, 20)]
    if change == 'duplicate':
        rows[1]['sequence'] = 0
    elif change == 'nan':
        rows[1]['client_request_and_body_ms'] = float('nan')
    elif change == 'clock':
        rows[1]['finished_ns'] = 0
    elif change == 'backwards':
        rows[1]['started_ns'] = 1
    elif change == 'bool':
        rows[1]['started_ns'] = True
    else:
        rows.pop()
    assert assess_channel(ENDPOINTS[0], rows, 2)['measurement_status'] == 'INCOMPLETE'


def test_threshold_equality_and_missing_channel_remain_explicit():
    value = assess_channel(ENDPOINTS[0], [request(0, 200)], 1)
    assert value['reference_exceedances'] == 0
    assert combine({})['collection_status'] == 'INCOMPLETE'
    assert combine({'health': value})['display_freshness'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('rows', [
    [request(0, 250), request(2, 300)],
    [request(0, 250), None, request(2, 300)],
    [request(0, 250), dict(sequence=1, kind='missed_slot'), request(2, 300)],
])
def test_missing_evidence_breaks_latency_streak_and_success_gap(rows):
    value = assess_channel(ENDPOINTS[0], rows, 3)
    assert value['measurement_status'] == 'INCOMPLETE'
    assert value['longest_consecutive_exceedances'] == 1
    assert value['longest_exceedance_sample_span_ms'] == 300
    assert value['max_observed_success_gap_ms'] is None


def test_cancelled_remaining_is_incomplete():
    value = assess_channel(ENDPOINTS[0], [
        request(0, 20), dict(kind='cancelled_remaining', sequence=1, remaining_slots=2)], 3)
    assert value['cancelled_slots'] == 2
    assert value['measurement_status'] == 'INCOMPLETE'


def test_no_threshold_does_not_invent_one():
    endpoint = ENDPOINTS[2]
    assert assess_channel(endpoint, [request(0, 900)], 1)['reference_exceedances'] is None


def test_last_attempt_is_explicit_and_not_replaced_by_previous_good_latency():
    rows = [request(0, 250), request(1, 300)]
    value = assess_channel(ENDPOINTS[0], rows, 2)
    assert value['last_ms'] == 300
    rows[-1]['client_request_and_body_ms'] = float('nan')
    assert assess_channel(ENDPOINTS[0], rows, 2)['last_ms'] is None


@pytest.mark.parametrize('change', ['overlap', 'response-before-start',
                                    'response-after-finish', 'latency-mismatch'])
def test_request_clock_consistency_is_required(change):
    rows = [request(0, 250), request(1, 300)]
    rows[1]['response_finished_ns'] = rows[1]['finished_ns']
    if change == 'overlap':
        rows[1]['started_ns'] = rows[0]['finished_ns'] - 1
        rows[1]['client_request_and_body_ms'] = (
            rows[1]['response_finished_ns'] - rows[1]['started_ns']) / 1e6
    elif change == 'response-before-start':
        rows[1]['response_finished_ns'] = rows[1]['started_ns'] - 1
    elif change == 'response-after-finish':
        rows[1]['response_finished_ns'] += 1
    else:
        rows[1]['client_request_and_body_ms'] += 100
    value = assess_channel(ENDPOINTS[0], rows, 2)
    assert value['measurement_status'] == 'INCOMPLETE'
    assert value['invalid_clock_records'] == 1
    assert value['longest_consecutive_exceedances'] == 1


def test_decode_duration_is_not_mistaken_for_response_duration():
    row = request(0, 250)
    row['response_finished_ns'] = row['finished_ns']
    row['finished_ns'] += 50_000_000
    assert assess_channel(ENDPOINTS[0], [row], 1)['measurement_status'] == 'COMPLETE'


@pytest.mark.parametrize('case,expected', [
    ('valid', 'PASS'), ('unreadable', 'INCOMPLETE'), ('empty', 'INCOMPLETE'),
    ('missing-with-read-error', 'INCOMPLETE'), ('missing-complete', 'FAIL'),
    ('changed-with-read-error', 'FAIL'),
])
def test_resource_read_failure_is_distinct_from_observed_identity_failure(case, expected):
    from field_observation import resource_backend_status
    from field_resource_sampling import ProcessIdentity
    backend = ProcessIdentity(10, 1.0, 'backend.exe')
    row = dict(process=dict(records=[dict(pid=10, created=1.0, exe='backend.exe')], errors=[]))
    if case in ('unreadable', 'empty'):
        row['process']['records'] = []
    if case.startswith('missing'):
        row['process']['records'] = [dict(pid=20, created=1.0, exe='other.exe')]
    if case == 'unreadable' or 'read-error' in case:
        row['process']['errors'] = [dict(type='AccessDenied')]
    if case.startswith('changed'):
        row['process']['records'][0]['created'] = 2.0
    assert resource_backend_status(row, backend) == expected


def test_new_collector_marks_cancelled_evidence_incomplete_without_image_requests(tmp_path):
    import threading
    from field_http_sampling import collect_http_window
    from test_field_http_sampling import local_server
    stopped = threading.Event()
    stopped.set()
    with local_server() as server:
        value = collect_http_window(server.server_port, tmp_path / 'cancelled',
            duration_seconds=.1, endpoints=ENDPOINTS[:2], stop_event=stopped,
            operational_assessment=True)
    assert value['operational_assessment']['measurement_status'] == 'INCOMPLETE'
    assert value['operational_assessment']['request_status'] == 'NOT_EVALUATED'
    assert value['operational_assessment']['operational_performance'] == 'NOT_EVALUATED'
    assert not list((tmp_path / 'cancelled').glob('image-*'))


def test_new_collector_rejects_synthetic_image_channel_before_output(tmp_path):
    from field_http_sampling import collect_http_window
    with pytest.raises(ValueError, match='actual UI'):
        collect_http_window(8000, tmp_path / 'invalid', duration_seconds=.1,
                            operational_assessment=True)
    assert not (tmp_path / 'invalid').exists()
