"""Validate opt-in health v2 evidence before exposing request/native-clock joins.

Caller supplies independently observed backend generation and its own probe ID.
This does not verify an installed payload, ETW coverage, CPU time or a field gate.
"""
import hashlib
import json
import re

import field_native_timing


POINTS = ('route_enter', 'submitted', 'worker_enter', 'plc_done', 'runtime_done',
          'frontend_done', 'worker_exit', 'route_resume')
ANCHORS = ('loop_begin', 'worker_begin', 'worker_end', 'loop_end')
ANCHOR_KEYS = {'status', 'pid', 'tid', 'process_created_filetime', 'thread_created_filetime',
               'perf_before_ns', 'perf_after_ns', 'qpc_ticks', 'qpc_frequency'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def integer(value, *, upper=2**63, zero=False):
    return type(value) is int and (0 if zero else 1) <= value < upper


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate-json-key')
        result[key] = value
    return result


def invalid_constant(_value):
    raise ValueError('non-finite-json')


def strict_json(raw):
    value = json.loads(raw, object_pairs_hook=strict_object, parse_constant=invalid_constant)
    require(type(value) is dict, 'json-object-required')
    return value


def collector_anchors(native):
    require(type(native) is dict, 'collector-native-missing')
    result = []
    for name in ('begin', 'end'):
        value = native[name]
        require(type(value) is dict and value.get('status') == 'OBSERVED'
                and value.get('schema') == 'sfl-self-thread-clock-v1' and value.get('error') is None,
                'collector-native-unavailable')
        identity, boundary = value['identity'], value['boundary']
        require(type(identity) is dict and set(identity) == {
            'pid', 'native_thread_id', 'process_created_filetime', 'thread_created_filetime'}, 'collector-identity-shape')
        require(type(boundary) is dict and set(boundary) == {
            'perf_before_ns', 'perf_after_ns', 'qpc_ticks', 'qpc_frequency', 'thread_cpu_ns'}, 'collector-clock-shape')
        result.append(dict(status='OBSERVED', pid=identity['pid'], tid=identity['native_thread_id'],
            process_created_filetime=identity['process_created_filetime'],
            thread_created_filetime=identity['thread_created_filetime'],
            **{key: value for key, value in boundary.items() if key != 'thread_cpu_ns'}))
    # Recalculate; a supplied CORRELATABLE_BOUNDARIES flag is not evidence by itself.
    recomputed = field_native_timing.interval(native['begin'], native['end'])
    require(recomputed['status'] == 'CORRELATABLE_BOUNDARIES', 'collector-boundary-join')
    return result


def validate_health_sample(record, raw_body, *, probe_id, backend_pid, backend_created_filetime):
    result = {'status': 'NOT_CORRELATABLE', 'reason': None, 'stages_ns': None,
              'checkpoint_qpc_bounds': None, 'field_gate': 'NOT_EVALUATED',
              'release_gate': 'HOLD', 'promotion_allowed': False}
    try:
        require(type(probe_id) is str and re.fullmatch('[0-9a-f]{32}', probe_id), 'expected-probe-id')
        require(integer(backend_pid, upper=2**32) and integer(backend_created_filetime, upper=2**64),
                'expected-backend-generation')
        require(type(record) is dict and record.get('endpoint') == 'health' and record.get('path') == '/health'
                and record.get('health_probe_id') == probe_id, 'request-probe-binding')
        require(record.get('request_success') is True and type(record.get('status')) is int and record['status'] == 200
                and record.get('body_complete') is True and record.get('decode_complete') is True
                and record.get('error_type') is None and record.get('timeout') is False, 'request-incomplete')
        require(type(raw_body) is bytes and 0 < len(raw_body) <= 1024**2
                and type(record.get('body_bytes')) is int and record['body_bytes'] == len(raw_body)
                and record.get('body_sha256') == hashlib.sha256(raw_body).hexdigest(), 'body-bytes-binding')
        strict_json(raw_body)
        headers = record['headers']
        require(type(headers) is list and len(headers) <= 100 and all(
            type(pair) in (list, tuple) and len(pair) == 2 and all(type(item) is str for item in pair)
            for pair in headers), 'header-list-shape')
        encoded = json.dumps(headers, ensure_ascii=True).encode('utf-8')
        require(len(encoded) <= 65536 and record.get('headers_truncated') is False
                and type(record.get('headers_bytes')) is int and record['headers_bytes'] == len(encoded)
                and record.get('headers_sha256') == hashlib.sha256(encoded).hexdigest(), 'header-bytes-binding')
        matches = [value for name, value in headers if name.lower() == 'x-sfl-health-timing']
        require(len(matches) == 1, 'timing-header-count')
        require(matches[0].isascii() and 0 < len(matches[0]) <= 4096, 'timing-header-budget')
        timing = strict_json(matches[0])
        require(set(timing) == {'v', 'probe_id', 'pid', 'loop_tid', 'worker_tid', 'clock', 'checkpoints', 'native'},
                'timing-schema')
        require(type(timing['v']) is int and timing['v'] == 2 and timing['clock'] == 'perf_counter_ns',
                'timing-version-clock')
        require(timing['probe_id'] == probe_id and integer(timing['pid'], upper=2**32)
                and timing['pid'] == backend_pid, 'timing-request-process')
        require(all(integer(timing[key], upper=2**32) for key in ('loop_tid', 'worker_tid'))
                and timing['loop_tid'] != timing['worker_tid'], 'timing-thread-identities')
        points = timing['checkpoints']
        require(type(points) is dict and set(points) == set(POINTS)
                and all(integer(points[key]) for key in POINTS), 'checkpoint-contract')
        values = [points[key] for key in POINTS]
        require(values == sorted(values), 'checkpoint-order')
        require(all(integer(record.get(key)) for key in ('started_ns', 'response_finished_ns', 'finished_ns')),
                'request-boundary-values')
        require(record['started_ns'] <= values[0] <= values[-1]
                <= record['response_finished_ns'] <= record['finished_ns'], 'request-boundary-order')
        native = timing['native']
        require(type(native) is dict and set(native) == set(ANCHORS), 'backend-native-shape')
        backend = [native[key] for key in ANCHORS]
        collector = collector_anchors(record['native_timing'])
        all_anchors = backend + collector
        for anchor in all_anchors:
            require(type(anchor) is dict and set(anchor) == ANCHOR_KEYS and anchor['status'] == 'OBSERVED',
                    'native-anchor-unavailable')
            require(all(integer(anchor[key], upper=2**32) for key in ('pid', 'tid'))
                    and all(integer(anchor[key], upper=2**64) for key in (
                        'process_created_filetime', 'thread_created_filetime'))
                    and all(integer(anchor[key], zero=True) for key in (
                        'perf_before_ns', 'perf_after_ns', 'qpc_ticks'))
                    and integer(anchor['qpc_frequency']), 'native-anchor-values')
            require(anchor['perf_before_ns'] <= anchor['perf_after_ns'], 'native-anchor-order')
            require(anchor['thread_created_filetime'] >= anchor['process_created_filetime'],
                    'native-thread-created-before-process')
        for key, anchor in zip(ANCHORS, backend):
            require(anchor['pid'] == backend_pid and anchor['process_created_filetime'] == backend_created_filetime
                    and anchor['tid'] == timing['loop_tid' if key.startswith('loop') else 'worker_tid'],
                    'backend-native-generation')
        for left, right in ((backend[0], backend[3]), (backend[1], backend[2])):
            require(left['thread_created_filetime'] == right['thread_created_filetime'], 'thread-generation-changed')
        spans = (
            (backend[0], points['route_enter'], points['submitted']),
            (backend[1], points['worker_enter'], points['plc_done']),
            (backend[2], points['worker_exit'], points['route_resume']),
            (backend[3], points['route_resume'], record['response_finished_ns']),
            (collector[0], record['started_ns'], record['response_finished_ns']),
            (collector[1], record['response_finished_ns'], record['finished_ns']),
        )
        require(all(low <= anchor['perf_before_ns'] <= anchor['perf_after_ns'] <= high
                    for anchor, low, high in spans), 'native-anchor-outside-stage')
        frequency = backend[0]['qpc_frequency']
        require(all(anchor['qpc_frequency'] == frequency for anchor in all_anchors), 'native-frequency-mismatch')
        bounds = []
        for anchor in all_anchors:
            numerator = anchor['qpc_ticks'] * 1_000_000_000
            bounds.append((anchor['perf_before_ns'] - (numerator + frequency - 1) // frequency,
                           anchor['perf_after_ns'] - numerator // frequency))
        lower, upper = max(item[0] for item in bounds), min(item[1] for item in bounds)
        require(lower <= upper, 'cross-process-clock-offset-disjoint')
        ordered = sorted(all_anchors, key=lambda anchor: anchor['perf_before_ns'])
        for left, right in zip(ordered, ordered[1:]):
            if left['perf_after_ns'] <= right['perf_before_ns']:
                require(left['qpc_ticks'] <= right['qpc_ticks'], 'native-qpc-order')
        mapped = {key: [(points[key] - upper) * frequency // 1_000_000_000,
                       ((points[key] - lower) * frequency + 999_999_999) // 1_000_000_000]
                  for key in POINTS}
        require(all(0 <= pair[0] <= pair[1] < 2**63 for pair in mapped.values()), 'mapped-qpc-range')
        result.update(status='REQUEST_AND_NATIVE_CLOCK_BOUND', probe_id=probe_id,
            backend_identity={key: backend[0][key] for key in ('pid', 'process_created_filetime')},
            threads={key: {'tid': anchor['tid'], 'created_filetime': anchor['thread_created_filetime']}
                     for key, anchor in (('loop', backend[0]), ('worker', backend[1]))},
            collector_identity=record['native_timing']['begin']['identity'],
            qpc_frequency=frequency, qpc_offset_lower_ns=lower, qpc_offset_upper_ns=upper,
            checkpoint_qpc_bounds=mapped,
            stages_ns={right: points[right] - points[left] for left, right in zip(POINTS, POINTS[1:])},
            exact_cpu_time='NOT_EVALUATED', etw_coverage='NOT_EVALUATED', latency_cause='UNDETERMINED')
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError) as error:
        result['reason'] = str(error)[:256] if isinstance(error, ValueError) else type(error).__name__
    return result
