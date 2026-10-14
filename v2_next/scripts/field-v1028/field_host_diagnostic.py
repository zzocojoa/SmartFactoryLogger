"""Short host attribution alongside the unchanged observation collectors.

This development component needs the protected field launcher. The existing
supervisor owns every collector through its job and bounds blocking OS calls.
It never assigns the application or an unrelated host process to that job.
"""
import json
import math
import multiprocessing
from pathlib import Path
import sys
import time

import field_host_sampling as host
import field_http_sampling as http
import field_observation as observation


def collect_host_window(output, *, duration_seconds, origin_ns, stop, interval_seconds=5):
    if (type(duration_seconds) not in (int, float) or not math.isfinite(duration_seconds)
            or not 0 < duration_seconds <= 300 or type(interval_seconds) not in (int, float)
            or not math.isfinite(interval_seconds) or not .05 <= interval_seconds <= 60
            or type(origin_ns) is not int or origin_ns <= 0):
        raise ValueError('Invalid host diagnostic time budget')
    count = math.floor(duration_seconds / interval_seconds) + 1
    if count > 121:
        raise ValueError('Host diagnostic sample budget')
    output = http._prepare_output(output)
    period = round(interval_seconds * 1e9)
    files, intervals = {}, []
    counts = {'captured_slots': 0, 'missed_slots': 0, 'cancelled_slots': 0}
    previous = None
    recording_errors = 0
    for sequence in range(count):
        due = origin_ns + sequence * period
        while not stop.is_set() and time.perf_counter_ns() < due:
            stop.wait(max(0, (due - time.perf_counter_ns()) / 1e9))
        started = time.perf_counter_ns()
        record = {'sequence': sequence, 'due_ns': due, 'started_ns': started,
                  'lateness_ms': (started - due) / 1e6}
        if stop.is_set():
            record['kind'] = 'cancelled'
            counts['cancelled_slots'] += 1
        elif started >= due + period:
            record['kind'] = 'missed'
            counts['missed_slots'] += 1
        else:
            record['kind'] = 'capture'
            record['snapshot'] = snapshot = host.capture_host()
            counts['captured_slots'] += 1
            recording_errors += bool(snapshot['errors'] or snapshot['truncated'])
            if previous is not None:
                intervals.append({'from_sequence': previous[0], 'to_sequence': sequence,
                    'counters': host.compare_host(previous[1], snapshot)})
            previous = (sequence, snapshot)
        name = f'host-{sequence:05d}.json'
        files[name] = observation.write_json(output / name, record)
    files['intervals.json'] = observation.write_json(output / 'intervals.json', intervals)
    result = {'scope': host.SCOPE, 'origin_ns': origin_ns, 'duration_seconds': duration_seconds,
              'interval_seconds': interval_seconds, 'expected_slots': count, **counts,
              'snapshot_errors_or_truncations': recording_errors,
              'partial_intervals': sum(row['counters']['partial'] for row in intervals),
              'recording_status': 'COMPLETE' if counts['captured_slots'] == count and not recording_errors else 'INCOMPLETE',
              'coverage_note': 'COMPLETE refers to scheduled snapshots; inaccessible process counters remain unmeasured.',
              'release_gate': 'HOLD', 'promotion_allowed': False,
              'field_gate': 'NOT_EVALUATED', 'formal_qa_gate': 'HOLD'}
    files['summary.json'] = observation.write_json(output / 'summary.json', result)
    observation.write_json(output / 'manifest.json', {'files': files, 'scope': host.SCOPE,
                                                     'release_gate': 'HOLD', 'promotion_allowed': False})
    return result


def _host_entry(output, duration, origin, external_stop):
    stop = observation.ObservationStop(external_stop)
    code = 1
    try:
        result = collect_host_window(Path(output) / 'host', duration_seconds=duration,
                                     origin_ns=origin, stop=stop)
        code = 0 if result['recording_status'] == 'COMPLETE' else 1
    except Exception as error:
        stop.set()
        observation.write_json(Path(output) / 'host-error.json', {'type': type(error).__name__})
    finally:
        stop.close()
    raise SystemExit(code)


def worker_entry(spec, output, duration_seconds, external_stop, sender):
    """Use with supervise_observation; keep original HTTP/binding failures."""
    output = Path(output)
    stop = observation.ObservationStop(external_stop)
    host_process = None
    code = 1

    def notify(event):
        nonlocal host_process
        if event['phase'] == 'observing':
            if host_process is not None:
                raise ValueError('Duplicate host collector start')
            host_process = multiprocessing.get_context('spawn').Process(target=_host_entry,
                args=(str(output), duration_seconds, event['origin_ns'], external_stop), name='SFL-host-diagnostic')
            host_process.start()
        sender.send_bytes(json.dumps(event).encode())

    try:
        with (output / 'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
                (output / 'worker.stderr.log').open('x', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            result = observation.run_observation(spec, output, duration_seconds, stop, notify)
            result.update(validation_scope=host.SCOPE, formal_qa_gate='HOLD')
            if host_process is not None:
                host_process.join(10)
                result['host_exit_code'] = host_process.exitcode
                if host_process.is_alive():
                    stop.set()
                    raise TimeoutError('Host collector did not finish; supervisor owns cleanup')
                result['host_manifest'] = observation.verify_component_manifest(output / 'host', 125)
                result['host_diagnostic'], _ = observation.read_json(output / 'host/summary.json')
                if host_process.exitcode != 0 or result['host_diagnostic']['recording_status'] != 'COMPLETE':
                    result['observation_status'] = 'FAIL'
            else:
                result['observation_status'] = 'FAIL'
            result['stop_requested'] = stop.is_set()
            fact = observation.write_json(output / 'worker-result.json', result)
            sender.send_bytes(json.dumps({'phase': 'done', 'result': fact}).encode())
            code = 0 if result['observation_status'] == 'PASS' else 1
    finally:
        stop.close()
        sender.close()
        if host_process is not None and not host_process.is_alive():
            host_process.close()
    raise SystemExit(code)
