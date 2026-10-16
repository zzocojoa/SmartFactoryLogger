"""Owned data/image request companion for explicit CPU diagnostic collection.

The caller must bind the app,
share an origin with its health probes, stop WPR before waiting for this child's
disk drain, and always call finish. Capture completion is not performance PASS.
"""
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import sys
import threading
import time

import field_http_sampling as http
import field_installation_binding as binding
import field_observation as observation
from field_windows_job import CollectorJob


ENDPOINTS = tuple(endpoint for endpoint in http.ENDPOINTS if endpoint.name in ('data', 'image'))
BODY_BUDGET = 128 * 1024**2
FILE_BUDGET = 7510
NOTICE_LIMIT = 4096


def _trigger_reason(endpoint, row, decision_ns):
    if row['kind'] == 'missed_slot':
        return 'missed-slot'
    if row['kind'] == 'request':
        if row['request_success'] is not True:
            return 'request-error'
        if endpoint.failure_ms is not None and row['client_request_and_body_ms'] > endpoint.failure_ms:
            return 'request-threshold-exceeded'
        if decision_ns >= row['scheduled_ns'] + round(endpoint.interval_seconds * 1e9):
            return 'request-period-overrun'
    return None


class _FirstAnomaly:
    """One small message, with no queue feeder or per-request disk operation."""

    def __init__(self, sender):
        self.sender = sender
        self.notice = None
        self.lock = threading.Lock()

    def __call__(self, endpoint, metadata, decision_ns):
        with self.lock:
            if self.notice is not None:
                return
            row = binding.strict_json(metadata)
            reason = _trigger_reason(endpoint, row, decision_ns)
            if reason is None:
                return
            notice = dict(schema='sfl-concurrent-http-trigger-v1', endpoint=endpoint.name,
                sequence=row['sequence'], kind=row['kind'], scheduled_ns=row['scheduled_ns'],
                period_ns=round(endpoint.interval_seconds * 1e9), decision_ns=decision_ns, reason=reason,
                record_file=f'requests/{endpoint.name}-{row["sequence"]:05d}.json',
                record_sha256=hashlib.sha256(metadata).hexdigest())
            raw = json.dumps(notice, allow_nan=False).encode('utf-8')
            binding.require(len(raw) <= NOTICE_LIMIT, 'companion-notice-budget')
            self.sender.send_bytes(raw)
            self.notice = notice


def _validate_notice(notice, origin, duration):
    keys = {'schema', 'endpoint', 'sequence', 'kind', 'scheduled_ns', 'period_ns',
            'decision_ns', 'reason', 'record_file', 'record_sha256'}
    binding.require(type(notice) is dict and set(notice) == keys, 'companion-notice-fields')
    endpoint = next((item for item in ENDPOINTS if item.name == notice['endpoint']), None)
    binding.require(endpoint is not None and notice['schema'] == 'sfl-concurrent-http-trigger-v1',
                    'companion-notice-schema')
    step = round(endpoint.interval_seconds * 1e9)
    count = (round(duration * 1e9) + step - 1) // step
    binding.require(all(type(notice[key]) is int for key in ('sequence', 'scheduled_ns', 'period_ns', 'decision_ns'))
                    and 0 <= notice['sequence'] < count and notice['period_ns'] == step
                    and notice['scheduled_ns'] == origin + notice['sequence'] * step
                    and notice['scheduled_ns'] <= notice['decision_ns'] <= time.perf_counter_ns(),
                    'companion-notice-timing')
    binding.require(notice['record_file'] == f'requests/{endpoint.name}-{notice["sequence"]:05d}.json'
                    and type(notice['record_sha256']) is str and len(notice['record_sha256']) == 64
                    and all(char in '0123456789abcdef' for char in notice['record_sha256']),
                    'companion-notice-record')
    binding.require((notice['kind'] == 'missed_slot' and notice['reason'] == 'missed-slot')
                    or (notice['kind'] == 'request' and notice['reason'] in (
                        'request-error', 'request-threshold-exceeded', 'request-period-overrun')),
                    'companion-notice-reason')
    return endpoint


def _worker(gate, ready, stop, port, output, duration, origin, trigger_sender=None):
    if not gate.wait(30):
        raise RuntimeError('companion-job-gate-expired')
    output = Path(output)
    result = dict(load_status='FAIL', errors=[], scope='DATA_IMAGE_COMPANION_ONLY',
                  field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)
    code = 1
    anomaly = _FirstAnomaly(trigger_sender) if trigger_sender is not None else None
    with (output/'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
            (output/'worker.stderr.log').open('x', encoding='utf-8') as stderr:
        sys.stdout, sys.stderr = stdout, stderr
        try:
            local_stop = observation.ObservationStop(stop)
            try:
                ready.set()
                summary = http.collect_http_window(port, output/'requests', duration_seconds=duration,
                    endpoints=ENDPOINTS, timeout_seconds=5, stop_event=local_stop, origin_ns=origin,
                    body_byte_budget=BODY_BUDGET, _record_observer=anomaly)
            finally:
                local_stop.close()
            result['http_summary'] = summary
            result['manifest'] = observation.verify_component_manifest(output/'requests', FILE_BUDGET)
            persistence = summary['persistence']
            binding.require(not summary['worker_errors'] and not summary['persistence_errors']
                and persistence['pending_bytes'] == persistence['pending_records'] == persistence['discarded_records'] == 0
                and persistence['submitted_records'] == persistence['persisted_records'], 'companion-capture-or-persistence-failed')
            result['load_status'] = 'CAPTURE_COMPLETE'
            code = 0
        except Exception as error:
            result['errors'].append(dict(type=type(error).__name__, reason=str(error)))
        finally:
            if trigger_sender is not None:
                trigger_sender.close()
        result.update(stop_observed=stop.is_set(), finished_ns=time.perf_counter_ns(),
                      trigger=anomaly.notice if anomaly is not None else None)
        observation.write_json(output/'worker-result.json', result)
    raise SystemExit(code)


class ConcurrentApiLoad:
    """Own a gated child by its native multiprocessing handle and Windows Job."""

    def __init__(self, port, output, *, duration_seconds, origin_ns):
        binding.require(type(port) is int and 1 <= port <= 65535, 'companion-loopback-port')
        binding.require(type(duration_seconds) in (int, float) and math.isfinite(duration_seconds)
                        and 0 < duration_seconds <= 900, 'companion-duration')
        http.observation_origin(origin_ns)
        self.output = http._prepare_output(output)
        binding.require(len(str(self.output/'requests/image-00000.body')) <= 240, 'companion-path-budget')
        context = multiprocessing.get_context('spawn')
        self.stop = context.Event()
        self.gate = context.Event()
        self.ready = context.Event()
        self.job = None
        self.process = None
        self.receipt = None
        self.stop_requested_ns = None
        self.origin_ns = origin_ns
        self.duration_seconds = duration_seconds
        self.trigger = None
        self.receiver, sender = context.Pipe(duplex=False)
        try:
            self.job = CollectorJob()
            self.process = context.Process(target=_worker,
                args=(self.gate, self.ready, self.stop, port, str(self.output), duration_seconds, origin_ns, sender),
                name='SFL-data-image-companion')
            self.process.start()
            self.job.assign_owned_process(self.process)
            self.gate.set()
            deadline = min(origin_ns, time.perf_counter_ns() + 10_000_000_000)
            while not self.ready.wait(.02):
                binding.require(self.process.is_alive(), 'companion-exited-before-ready')
                binding.require(time.perf_counter_ns() < deadline, 'companion-ready-deadline')
            binding.require(time.perf_counter_ns() < origin_ns, 'companion-not-ready-before-origin')
            observation.write_json(self.output/'started.json', dict(pid=self.process.pid,
                origin_ns=origin_ns, duration_seconds=duration_seconds, ready_observed_ns=time.perf_counter_ns(),
                job_assignment_before_gate=True, body_byte_budget=BODY_BUDGET,
                endpoint_periods={endpoint.name: endpoint.interval_seconds for endpoint in ENDPOINTS},
                scope='DATA_IMAGE_COMPANION_ONLY', release_gate='HOLD', promotion_allowed=False))
        except BaseException:
            if self.process is not None and self.process.pid is not None:
                self.finish(request_stop=True, _join_seconds=2)
            elif self.job is not None:
                self.job.close()
            if self.receiver is not None:
                self.receiver.close()
                self.receiver = None
            raise
        finally:
            sender.close()

    def poll_trigger(self):
        """Observe, without disk I/O; the retained record is verified after drain."""
        if self.receiver is not None:
            try:
                raw = self.receiver.recv_bytes(NOTICE_LIMIT) if self.receiver.poll() else None
            except (EOFError, OSError) as error:
                # Windows can report ERROR_BROKEN_PIPE from poll, not EOFError
                # from recv, after the child's single writer closes normally.
                if not isinstance(error, EOFError) and getattr(error, 'winerror', None) != 109:
                    raise
                self.receiver.close()
                self.receiver = None
                raw = None
            if raw is not None:
                binding.require(self.trigger is None, 'companion-duplicate-notice')
                notice = binding.strict_json(raw)
                _validate_notice(notice, self.origin_ns, self.duration_seconds)
                self.trigger = notice
        if self.receipt is None:
            binding.require(self.process.exitcode in (None, 0), 'companion-exited-during-observation')
        return dict(self.trigger) if self.trigger is not None else None

    def verify_trigger(self, value):
        self.poll_trigger()
        # A second queued message must fail, including after an earlier poll.
        self.poll_trigger()
        binding.require(value['trigger'] == self.trigger, 'companion-notice-result-mismatch')
        if self.trigger is not None:
            notice = self.trigger
            endpoint = _validate_notice(notice, self.origin_ns, self.duration_seconds)
            row, raw = observation.read_json(self.output/notice['record_file'])
            binding.require(hashlib.sha256(raw).hexdigest() == notice['record_sha256'], 'companion-notice-record-hash')
            binding.require(all(row[key] == notice[key] for key in ('sequence', 'kind', 'scheduled_ns'))
                            and row['queued_ns'] <= notice['decision_ns']
                            and _trigger_reason(endpoint, row, notice['decision_ns']) == notice['reason'],
                            'companion-notice-record-mismatch')

    def request_stop(self):
        if self.stop_requested_ns is None:
            self.stop_requested_ns = time.perf_counter_ns()
        self.stop.set()

    def finish(self, *, request_stop=False, _join_seconds=30):
        """Drain for at most 30 seconds, then fail and terminate only our job.

        Shorter private budgets support real timeout regression checks; callers
        cannot extend the production bound. Repeated finish returns its receipt.
        """
        binding.require(type(_join_seconds) in (int, float) and math.isfinite(_join_seconds)
                        and 0 < _join_seconds <= 30, 'companion-close-budget')
        if self.receipt is not None:
            return self.receipt
        if request_stop:
            self.request_stop()
        record = dict(load_status='FAIL', errors=[], worker_pid=self.process.pid,
                      forced_termination=False, stop_requested_ns=self.stop_requested_ns,
                      scope='DATA_IMAGE_COMPANION_LIFECYCLE_ONLY', field_gate='NOT_EVALUATED',
                      release_gate='HOLD', promotion_allowed=False)
        try:
            self.process.join(_join_seconds)
            if self.process.is_alive():
                record['forced_termination'] = True
                self.job.terminate()
                self.process.join(5)
                # Covers failure to assign the suspended-at-gate child to its job.
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(5)
            record['worker_still_alive'] = self.process.is_alive()
            record['worker_exit_code'] = self.process.exitcode
            record['job_after_cleanup'] = self.job.accounting()
            binding.require(not record['worker_still_alive']
                            and record['job_after_cleanup']['active_processes'] == 0, 'companion-cleanup-unconfirmed')
            binding.require(not record['forced_termination'] and self.process.exitcode == 0, 'companion-worker-incomplete')
            value, _ = observation.read_json(self.output/'worker-result.json')
            record['worker_result'] = observation.file_fact(self.output/'worker-result.json')
            binding.require(value['load_status'] == 'CAPTURE_COMPLETE' and not value['errors'], 'companion-result-incomplete')
            binding.require(not value['stop_observed'] or self.stop_requested_ns is not None, 'companion-unrequested-stop')
            binding.require(value['release_gate'] == 'HOLD' and value['promotion_allowed'] is False
                            and value['field_gate'] == 'NOT_EVALUATED', 'companion-invalid-gates')
            record['manifest'] = observation.verify_component_manifest(self.output/'requests', FILE_BUDGET)
            binding.require(record['manifest'] == value['manifest'], 'companion-manifest-changed')
            self.verify_trigger(value)
            record['trigger'] = self.trigger
            record['load_status'] = 'CAPTURE_COMPLETE'
            record['http_component_status'] = value['http_summary']['http_component_status']
            record['channels'] = value['http_summary']['channels']
        except Exception as error:
            record['errors'].append(dict(type=type(error).__name__, reason=str(error)))
        finally:
            if self.receiver is not None:
                self.receiver.close()
                self.receiver = None
            if self.job is not None:
                self.job.close()
                self.job = None
            if self.process is not None and not self.process.is_alive():
                self.process.close()
            record['finished_ns'] = time.perf_counter_ns()
        observation.write_json(self.output/'closeout.json', record)
        self.receipt = record
        return record
