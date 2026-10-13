"""Combine field components in a supervised, read-only observation worker.

Development entry API, not the protected server launcher. UI, packet, device
attestation and shutdown evidence remain gates.
The supervisor owns an unnamed Windows job. Its gated controller spawns only
collector processes; the already running application is never assigned to it.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time

import field_installation_binding as binding
import field_generation_binding as generation_binding
import field_configuration_binding as configuration_binding
import field_shutdown_binding as shutdown_binding
import field_http_sampling as http
import field_resource_sampling as resource
from field_windows_job import CollectorJob


@dataclass(frozen=True)
class ObservationSpec:
    root: str
    reference: str
    main: resource.ProcessIdentity
    backend: resource.ProcessIdentity
    port: int
    reference_sha256: str = binding.REFERENCE_SHA
    extras: dict = field(default_factory=dict)
    configuration_reference: str = ''
    configuration_reference_sha256: str = ''

    def validate(self):
        binding.plain_path(self.root)
        binding.plain_path(self.reference)
        self.main.validate()
        self.backend.validate()
        binding.require(self.main.pid != self.backend.pid and type(self.port) is int
                        and 1 <= self.port <= 65535, 'invalid-process-port')
        binding.require(isinstance(self.reference_sha256, str)
                        and re.fullmatch('[0-9a-f]{64}', self.reference_sha256), 'invalid-reference-hash')
        binding.require(isinstance(self.extras, dict), 'invalid-extra-facts')
        binding.plain_path(self.configuration_reference)
        binding.require(isinstance(self.configuration_reference_sha256, str)
                        and re.fullmatch('[0-9a-f]{64}', self.configuration_reference_sha256),
                        'invalid-configuration-reference-hash')


def write_json(path, value):
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read_json(path, limit=16 * 1024**2):
    path = binding.plain_path(path)
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    binding.require(len(raw) <= limit, 'json-read-budget')
    return binding.strict_json(raw), raw


def file_fact(path):
    with binding.plain_path(path).open('rb') as stream:
        return binding.stream_fact(stream)


class ObservationStop:
    """Bridge cross-process cancellation without sharing OS wait locks per probe.

    Windows semaphore waits can return just before a sub-millisecond deadline.
    Recheck the monotonic deadline; never clamp a negative observed lateness.
    """
    def __init__(self, external):
        self.external = external
        self.local = threading.Event()
        self.closed = threading.Event()
        self.bridge = threading.Thread(target=self._bridge, name='field-stop-bridge', daemon=True)
        self.bridge.start()

    def _bridge(self):
        while not self.closed.wait(.05):
            if self.external.is_set():
                self.local.set()
                return

    def is_set(self):
        return self.local.is_set()

    def set(self):
        self.local.set()
        self.external.set()

    def wait(self, seconds):
        deadline = time.perf_counter() + max(0, seconds)
        while not self.local.is_set():
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return False
            if self.local.wait(remaining):
                return True
        return True

    def close(self):
        self.closed.set()
        self.bridge.join(1)
        binding.require(not self.bridge.is_alive(), 'stop-bridge-did-not-exit')


def collect_process_window(spec, output, duration_seconds, origin_ns, stop):
    output = http._prepare_output(output)
    files, rows = {}, []
    count = math.floor(duration_seconds / 5) + 1
    previous_finished = None
    for sequence in range(count):
        target = origin_ns + sequence * 5_000_000_000
        row = {'sequence': sequence, 'scheduled_ns': target}
        if stop.wait(max(0, (target - time.perf_counter_ns()) / 1e9)):
            row.update(status='CANCELLED', remaining_slots=count - sequence)
        elif (previous_finished is not None and previous_finished >= target) or time.perf_counter_ns() >= target + 5_000_000_000:
            row['status'] = 'MISSED'
            stop.set()
        else:
            row['started_ns'] = time.perf_counter_ns()
            try:
                row['process'] = binding.read_process_binding(spec.main, spec.backend, spec.port)
                row['status'] = 'PASS'
            except Exception as error:
                row.update(status='FAIL', error=resource.error_record(error))
                stop.set()
            row['finished_ns'] = time.perf_counter_ns()
        name = f'process-{sequence:05d}.json'
        files[name] = write_json(output / name, row)
        rows.append(row)
        previous_finished = time.perf_counter_ns()
        if row['status'] != 'PASS':
            break
    stop.wait(max(0, (origin_ns + duration_seconds * 1e9 - time.perf_counter_ns()) / 1e9))
    summary = {'origin_ns': origin_ns, 'expected_slots': count, 'recorded_slots': len(rows),
               'status': 'PASS' if len(rows) == count and all(r['status'] == 'PASS' for r in rows)
                         and not stop.is_set() else 'FAIL',
               'scope': 'FIVE_SECOND_OS_IDENTITY_AND_LISTENER_SAMPLES'}
    files['summary.json'] = write_json(output / 'summary.json', summary)
    write_json(output / 'manifest.json', {'files': files})
    return summary


def verify_component_manifest(folder, max_files):
    manifest, raw = read_json(folder / 'manifest.json')
    specs = manifest.get('files')
    binding.require(isinstance(specs, dict) and 0 < len(specs) <= max_files, 'component-manifest-count')
    # HTTP 120-minute output exceeds the installed-payload tree's 6,000-entry cap.
    actual = set()
    with os.scandir(folder) as entries:
        for entry in entries:
            binding.require(len(actual) < max_files + 1 and entry.is_file(follow_symlinks=False)
                            and not entry.stat(follow_symlinks=False).st_file_attributes & 0x400,
                            'component-entry-budget-or-type')
            actual.add(entry.name)
    binding.require(actual == specs.keys() | {'manifest.json'}, 'component-file-set')
    for name, expected in specs.items():
        binding.entry_name(name)
        binding.require('/' not in name and isinstance(expected, dict)
                        and type(expected.get('bytes')) is int and expected['bytes'] >= 0
                        and isinstance(expected.get('sha256'), str)
                        and not expected.get('failed_write'), 'component-file-fact')
        binding.require(file_fact(folder / name) == expected, 'component-file-hash:' + name)
    return {'files': len(specs), 'manifest_bytes': len(raw),
            'manifest_sha256': hashlib.sha256(raw).hexdigest()}


def review_window(spec, output, origin_ns, duration_seconds, sessions, boundaries):
    """Recompute health/session binding from every durable health body."""
    manifests = {name: verify_component_manifest(output / name, limit) for name, limit in
                 (('http', 100010), ('resources', 5010), ('processes', 1450))}
    summary = {name: read_json(output / name / 'summary.json')[0]
               for name in ('http', 'resources', 'processes')}
    issues, health_records, resource_rows = [], [], 0
    if any(value.get('origin_ns') != origin_ns for value in summary.values()):
        issues.append('origin-mismatch')
    if summary['http']['http_component_status'] != 'PASS':
        issues.append('http-component-failed')
    if (summary['resources']['recording_status'] != 'COMPLETE'
            or summary['resources']['unmeasured_intervals'] != 0
            or (duration_seconds >= 420 and summary['resources']['resource_coverage_status'] != 'SUFFICIENT')):
        issues.append('resource-component-incomplete')
    if summary['processes']['status'] != 'PASS':
        issues.append('process-component-failed')
    for index, boundary in enumerate(boundaries):
        if boundary.get('binding_status') != 'PASS' or boundary.get('sessions') != sessions:
            issues.append(f'boundary-{index}-binding')
        record = boundary.get('health_record')
        if record is not None:
            health_records.append(record)
    for sequence in range(math.ceil(duration_seconds / 2)):
        row, _ = read_json(output / 'http' / f'health-{sequence:05d}.json')
        if row.get('kind') != 'request':
            issues.append(f'health-{sequence}-not-request')
            continue
        raw = (output / 'http' / f'health-{sequence:05d}.body').read_bytes()
        binding.require(len(raw) <= http.ENDPOINTS[0].max_body_bytes, 'health-body-size')
        binding.require(len(raw) == row['body_bytes']
                        and hashlib.sha256(raw).hexdigest() == row['body_sha256'], 'health-body-binding')
        try:
            if not row['request_success'] or binding.runtime_sessions(binding.strict_json(raw), spec.backend) != sessions:
                issues.append(f'health-{sequence}-session')
        except Exception as error:
            issues.append(f'health-{sequence}-{type(error).__name__}')
        health_records.append(row)
    for sequence in range(math.floor(duration_seconds / 5) + 1):
        row, _ = read_json(output / 'resources' / f'resource-{sequence:05d}.json')
        records = row.get('process', {}).get('records', [])
        if not any(p.get('pid') == spec.backend.pid and p.get('created') == spec.backend.created
                   and os.path.normcase(p.get('exe', '')) == spec.backend.exe for p in records):
            issues.append(f'resource-{sequence}-backend-absent')
        resource_rows += 1
    # Both boundary requests are included; the first request is never discarded.
    valid_latency = all(type(r.get('client_request_and_body_ms')) in (int, float)
                        and math.isfinite(r['client_request_and_body_ms'])
                        and 0 <= r['client_request_and_body_ms'] <= 200
                        and r.get('request_success') is True for r in health_records)
    if len(health_records) != math.ceil(duration_seconds / 2) + 2 or not valid_latency:
        issues.append('all-health-including-boundaries-failed')
    return {'status': 'PASS' if not issues else 'FAIL', 'issues': issues, 'manifests': manifests,
            'summary': summary, 'health_requests_including_boundaries': len(health_records),
            'first_health_ms': health_records[0]['client_request_and_body_ms'] if health_records else None,
            'max_health_ms': max((r['client_request_and_body_ms'] for r in health_records), default=None),
            'resource_rows_checked_for_backend': resource_rows}


def _component_entry(name, spec, output, duration, origin, external_stop):
    output = Path(output)
    stop = ObservationStop(external_stop)
    exit_code = 1
    try:
        with (output / f'{name}.stdout.log').open('x', encoding='utf-8') as stdout, \
                (output / f'{name}.stderr.log').open('x', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            if name == 'http':
                result = http.collect_http_window(spec.port, output / name, duration_seconds=duration,
                                                  origin_ns=origin, stop_event=stop)
                passed = result['http_component_status'] == 'PASS'
            elif name == 'resources':
                result = resource.collect_resource_window(spec.main, output / name, duration_seconds=duration,
                                                          origin_ns=origin, stop_event=stop)
                passed = result['recording_status'] == 'COMPLETE'
            elif name == 'processes':
                result = collect_process_window(spec, output / name, duration, origin, stop)
                passed = result['status'] == 'PASS'
            else:
                raise ValueError('Unknown component')
            # Completed failures remain available to the joint reviewer. Do not
            # cancel a simultaneous final resource sample because HTTP failed.
            exit_code = 0 if passed else 1
    except Exception as error:
        stop.set()
        write_json(output / f'{name}-error.json', resource.error_record(error))
    finally:
        stop.close()
    raise SystemExit(exit_code)


def run_observation(spec, output, duration_seconds, stop, notify):
    """Runs in the owned worker; blocking I/O is bounded by its supervisor."""
    output = Path(output)
    result = {'observation_status': 'FAIL', 'field_gate': 'NOT_EVALUATED', 'release_gate': 'HOLD',
              'promotion_allowed': False, 'errors': [], 'worker_pid': os.getpid(),
              'started_utc': datetime.now(timezone.utc).isoformat()}
    try:
        with binding.InstalledPayload(spec.root, spec.reference,
                                      expected_reference_sha256=spec.reference_sha256, extras=spec.extras) as payload, \
                configuration_binding.configuration_reference(spec.configuration_reference,
                    spec.configuration_reference_sha256) as expected_configuration:
            initial = binding.capture_runtime_binding(payload, spec.main, spec.backend, spec.port)
            write_json(output / 'initial.json', initial)
            binding.require(initial['binding_status'] == 'PASS', 'initial-binding-failed')
            sessions = initial['sessions']
            control_initial = generation_binding.capture_generation(payload, spec.main, spec.backend, spec.port)
            write_json(output / 'control-initial.json', control_initial)
            binding.require(control_initial['generation_status'] == 'PASS', 'initial-control-binding-failed')
            configuration_initial = configuration_binding.capture_configuration(
                payload, spec.main, spec.backend, spec.port, sessions, expected_configuration)
            write_json(output / 'configuration-initial.json', configuration_initial)
            binding.require(configuration_initial['configuration_status'] == 'PASS', 'initial-configuration-failed')
            origin = time.perf_counter_ns() + 3_000_000_000
            result['origin_ns'] = origin
            write_json(output / 'observation.json', {'origin_ns': origin, 'duration_seconds': duration_seconds,
                                                   'sessions': sessions, 'spec': asdict(spec)})
            notify({'phase': 'observing', 'origin_ns': origin})
            context = multiprocessing.get_context('spawn')
            jobs = []
            try:
                for name in ('http', 'resources', 'processes'):
                    job = context.Process(target=_component_entry,
                        args=(name, spec, str(output), duration_seconds, origin, stop.external),
                        name='SFL-field-' + name)
                    job.start()
                    jobs.append((name, job))
                while any(job.is_alive() for _, job in jobs):
                    for _, job in jobs:
                        job.join(.05)
                result['component_exits'] = {name: job.exitcode for name, job in jobs}
            except BaseException:
                stop.set()
                raise
            finally:
                for _, job in jobs:
                    if not job.is_alive():
                        job.close()
            notify({'phase': 'finalizing', 'origin_ns': origin})
            final = binding.capture_runtime_binding(payload, spec.main, spec.backend, spec.port,
                                                    expected_sessions=sessions)
            write_json(output / 'final.json', final)
            control_final = generation_binding.capture_generation(payload, spec.main, spec.backend, spec.port,
                expected_identity=control_initial['identity'])
            write_json(output / 'control-final.json', control_final)
            result['control_binding'] = dict(initial=control_initial, final=control_final,
                                             scope='AUTHENTICATED_BOUNDARY_SAMPLES')
            configuration_final = configuration_binding.capture_configuration(
                payload, spec.main, spec.backend, spec.port, sessions, expected_configuration)
            write_json(output / 'configuration-final.json', configuration_final)
            result['configuration_binding'] = dict(initial=configuration_initial, final=configuration_final,
                reference_sha256=spec.configuration_reference_sha256, scope='REPORTED_CONFIGURATION_BOUNDARIES')
            result['closeout'] = payload.recheck()
            result['review'] = review_window(spec, output, origin, duration_seconds, sessions, [initial, final])
            result['shutdown_expectation'] = shutdown_binding.expectation_from_boundary(final, spec.backend)
            result['shutdown_expectation_file'] = write_json(output / 'shutdown-expectation.json',
                                                            result['shutdown_expectation'])
            if (result['review']['status'] == 'PASS' and not stop.is_set()
                    and control_final['generation_status'] == 'PASS'
                    and configuration_final['configuration_status'] == 'PASS'
                    and all(code == 0 for code in result['component_exits'].values())):
                result['observation_status'] = 'PASS'
    except Exception as error:
        result['errors'].append(resource.error_record(error))
        result['observation_status'] = 'FAIL'
        stop.set()
    result.update(stop_requested=stop.is_set(), finished_ns=time.perf_counter_ns())
    result['remaining_gates'] = ['physical_device_and_comparator_verification', 'reference_approval_and_shutdown_attestation',
                                'UI_web_vitals', 'packet_contract', 'normal_application_shutdown_and_final_delta',
                                'all_release_plan_gates']
    return result


def _worker_entry(spec, output, duration_seconds, stop, sender):
    output = Path(output)
    exit_code = 1
    try:
        with (output / 'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
                (output / 'worker.stderr.log').open('x', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            local_stop = ObservationStop(stop)
            try:
                result = run_observation(spec, output, duration_seconds, local_stop,
                                         lambda item: sender.send_bytes(json.dumps(item).encode()))
            finally:
                local_stop.close()
            fact = write_json(output / 'worker-result.json', result)
            sender.send_bytes(json.dumps({'phase': 'done', 'result': fact}).encode())
            exit_code = 0 if result['observation_status'] == 'PASS' else 1
    finally:
        sender.close()
    raise SystemExit(exit_code)


def _gated_entry(gate, target, spec, output, duration, stop, sender):
    if not gate.wait(30):
        raise RuntimeError('Collector job assignment gate expired')
    target(spec, output, duration, stop, sender)


def supervise_observation(spec, output, *, duration_seconds, preparation_timeout=180,
                          finalization_timeout=180, stop_event=None, _worker_target=_worker_entry):
    """Fresh owned collector job per run; no application process control.

    Parent receipt writes still require the future outer protected launcher
    watchdog. Job assignment uses our new child's HANDLE before opening its gate.
    """
    spec.validate()
    binding.require(type(duration_seconds) in (int, float) and math.isfinite(duration_seconds)
                    and 0 < duration_seconds <= 7200, 'invalid-duration')
    for value in (preparation_timeout, finalization_timeout):
        binding.require(type(value) in (int, float) and math.isfinite(value)
                        and 0 < value <= 180, 'invalid-watchdog-budget')
    binding.require(len(str(Path(output) / 'resources' / 'resource-00000.json')) <= 240, 'nested-output-path-budget')
    output = http._prepare_output(output)
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    stop = context.Event()
    gate = context.Event()
    process = context.Process(target=_gated_entry,
        args=(gate, _worker_target, spec, str(output), duration_seconds, stop, sender),
        name='SFL-field-observation-worker')
    receipt = {'supervisor_status': 'FAIL', 'field_gate': 'NOT_EVALUATED', 'release_gate': 'HOLD',
               'promotion_allowed': False, 'events': [], 'errors': [], 'termination_requested': False,
               'started_ns': time.perf_counter_ns(), 'duration_seconds': duration_seconds}
    done = None
    observing = False
    finalizing = False
    deadline = time.perf_counter_ns() + round(preparation_timeout * 1e9)
    started = False
    collector_job = None
    incoming = queue.Queue(maxsize=4)
    reader_finished = threading.Event()

    def read_events():
        try:
            while True:
                event = binding.strict_json(receiver.recv_bytes(65536))
                incoming.put(('event', event), timeout=.2)
        except EOFError:
            pass
        except Exception as error:
            try:
                incoming.put(('error', resource.error_record(error)), timeout=.2)
            except queue.Full:
                pass
        finally:
            reader_finished.set()

    reader = threading.Thread(target=read_events, name='field-worker-event-reader', daemon=True)
    try:
        collector_job = CollectorJob()
        process.start()
        started = True
        receipt['worker_pid'] = process.pid
        collector_job.assign_owned_process(process)
        receipt['job_assignment_before_gate'] = True
        gate.set()
        sender.close()
        reader.start()
        while True:
            now = time.perf_counter_ns()
            if stop_event is not None and stop_event.is_set():
                raise InterruptedError('operator-stop-requested')
            if now > deadline:
                raise TimeoutError('observation-worker-deadline')
            try:
                kind, event = incoming.get(timeout=.05)
            except queue.Empty:
                if not process.is_alive() and reader_finished.is_set():
                    break
            else:
                binding.require(kind == 'event', 'worker-event-read-error:' + str(event))
                receipt['events'].append(event)
                binding.require(len(receipt['events']) <= 3, 'unexpected-worker-events')
                if event.get('phase') == 'observing':
                    origin = event.get('origin_ns')
                    binding.require(not observing and done is None and type(origin) is int
                                    and receipt['started_ns'] <= origin <= now + 30_000_000_000,
                                    'invalid-observation-origin')
                    observing = True
                    deadline = origin + round((duration_seconds + finalization_timeout) * 1e9)
                elif event.get('phase') == 'finalizing':
                    binding.require(observing and not finalizing and done is None
                                    and event.get('origin_ns') == origin, 'unexpected-finalizing')
                    finalizing = True  # Never extends the fixed observation deadline.
                elif event.get('phase') == 'done':
                    binding.require(done is None, 'duplicate-worker-done')
                    done = event.get('result')
                else:
                    raise ValueError('unknown-worker-phase')
        process.join(1)
        receipt['worker_exit_code'] = process.exitcode
        if done is not None:
            binding.require(file_fact(output / 'worker-result.json') == done, 'worker-result-hash')
            result, _ = read_json(output / 'worker-result.json')
            receipt['worker_result'] = done
            binding.require(result['field_gate'] == 'NOT_EVALUATED' and result['release_gate'] == 'HOLD'
                            and result['promotion_allowed'] is False, 'invalid-worker-release-claim')
            if (process.exitcode == 0 and observing and finalizing
                    and result['observation_status'] == 'PASS' and not result['stop_requested']):
                receipt['supervisor_status'] = 'PASS'
        else:
            receipt['errors'].append({'type': 'MissingResult', 'reason': 'Worker exited without a durable result'})
    except Exception as error:
        receipt['errors'].append(resource.error_record(error))
        stop.set()
    finally:
        def cleanup(action):
            try:
                return action()
            except Exception as error:
                receipt['errors'].append(resource.error_record(error))
                receipt['supervisor_status'] = 'FAIL'
                return None

        if started and process.is_alive():
            stop.set()
            process.join(2)
            if process.is_alive():
                receipt['termination_requested'] = True
                if collector_job is not None:
                    cleanup(collector_job.terminate)
                # Also covers a child whose job assignment failed before gate.
                cleanup(process.terminate)
                process.join(10)
            receipt['worker_exit_code'] = process.exitcode
        receipt['worker_still_alive'] = started and process.is_alive()
        if receipt['worker_still_alive'] or receipt['termination_requested'] or receipt['errors']:
            receipt['supervisor_status'] = 'FAIL'
        if collector_job is not None:
            try:
                receipt['job_before_close'] = collector_job.accounting()
                if receipt['job_before_close']['active_processes']:
                    receipt['termination_requested'] = True
                    receipt['supervisor_status'] = 'FAIL'
                    collector_job.terminate()
                    deadline = time.perf_counter() + 10
                    while collector_job.accounting()['active_processes'] and time.perf_counter() < deadline:
                        time.sleep(.05)
                receipt['job_after_cleanup'] = collector_job.accounting()
                binding.require(receipt['job_after_cleanup']['active_processes'] == 0, 'job-children-still-active')
            except Exception as error:
                receipt['errors'].append(resource.error_record(error))
                receipt['supervisor_status'] = 'FAIL'
            finally:
                # KILL_ON_JOB_CLOSE remains the final cleanup if querying or
                # explicitly terminating the owned job failed.
                cleanup(collector_job.close)
        receiver.close()
        sender.close()
        if reader.ident is not None:
            reader.join(.5)
        receipt['event_reader_still_alive'] = reader.is_alive()
        if reader.is_alive():
            receipt['supervisor_status'] = 'FAIL'
        if not receipt['worker_still_alive']:
            process.close()
    receipt['finished_ns'] = time.perf_counter_ns()
    write_json(output / 'supervisor.json', receipt)
    return receipt
