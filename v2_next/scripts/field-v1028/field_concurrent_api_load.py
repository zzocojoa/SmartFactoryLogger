"""Owned data/image request companion for a future explicit CPU diagnostic mode.

No production entrypoint calls this component yet. The caller must bind the app,
share an origin with its health probes, stop WPR before waiting for this child's
disk drain, and always call finish. Capture completion is not performance PASS.
"""
import math
import multiprocessing
from pathlib import Path
import sys
import time

import field_http_sampling as http
import field_installation_binding as binding
import field_observation as observation
from field_windows_job import CollectorJob


ENDPOINTS = tuple(endpoint for endpoint in http.ENDPOINTS if endpoint.name in ('data', 'image'))
BODY_BUDGET = 128 * 1024**2
FILE_BUDGET = 7510


def _worker(gate, ready, stop, port, output, duration, origin):
    if not gate.wait(30):
        raise RuntimeError('companion-job-gate-expired')
    output = Path(output)
    result = dict(load_status='FAIL', errors=[], scope='DATA_IMAGE_COMPANION_ONLY',
                  field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)
    code = 1
    with (output/'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
            (output/'worker.stderr.log').open('x', encoding='utf-8') as stderr:
        sys.stdout, sys.stderr = stdout, stderr
        try:
            local_stop = observation.ObservationStop(stop)
            try:
                ready.set()
                summary = http.collect_http_window(port, output/'requests', duration_seconds=duration,
                    endpoints=ENDPOINTS, timeout_seconds=5, stop_event=local_stop, origin_ns=origin,
                    body_byte_budget=BODY_BUDGET)
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
        result.update(stop_observed=stop.is_set(), finished_ns=time.perf_counter_ns())
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
        try:
            self.job = CollectorJob()
            self.process = context.Process(target=_worker,
                args=(self.gate, self.ready, self.stop, port, str(self.output), duration_seconds, origin_ns),
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
            raise

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
            record['load_status'] = 'CAPTURE_COMPLETE'
            record['http_component_status'] = value['http_summary']['http_component_status']
            record['channels'] = value['http_summary']['channels']
        except Exception as error:
            record['errors'].append(dict(type=type(error).__name__, reason=str(error)))
        finally:
            if self.job is not None:
                self.job.close()
                self.job = None
            if self.process is not None and not self.process.is_alive():
                self.process.close()
            record['finished_ns'] = time.perf_counter_ns()
        observation.write_json(self.output/'closeout.json', record)
        self.receipt = record
        return record
