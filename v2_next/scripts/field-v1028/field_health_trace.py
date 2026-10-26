"""File handshake for a bounded health capture and an independent WPR owner.

Local integration API only. The outer administrator coordinator is separate from
the owned collector job; this consumer never launches WPR or controls the app.
File/ETL provenance and scheduling coverage remain separate verification steps.
"""
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import time

import field_health_collection as collection
import field_installation_binding as binding
import field_observation as observation
import field_python_stream as python_stream
from field_host_sampling import WindowsProcessReader


PROFILE_SHA256 = '603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486'
CPU_PROFILE_SHA256 = '3ad310b110ead5c2867b9632ff96ec71e0381a030bac7f7ec91bddf5f5c94fee'
READY_PROFILE_SHA256 = '03220768bee3245513b2ec4d9eeac2affd7ddffcd2c786f6a658146bdd8e2478'
SCOPE = 'LOCAL_INSTALLED_HEALTH_TRACE_DIAGNOSTIC'
OUTLIER_SCOPE = 'LOCAL_HEALTH_OUTLIER_TRACE_DIAGNOSTIC'
CPU_OUTLIER_SCOPE = 'LOCAL_HEALTH_CPU_OUTLIER_TRACE_DIAGNOSTIC'
CPU_CONCURRENT_SCOPE = 'LOCAL_HEALTH_CPU_CONCURRENT_TRACE_DIAGNOSTIC'
READY_CONCURRENT_SCOPE = 'LOCAL_HEALTH_READY_CONCURRENT_TRACE_DIAGNOSTIC'
PYTHON_SCOPE = 'LOCAL_PYTHON_HEALTH_TRACE_DIAGNOSTIC'
PYTHON_BASELINE_SCOPE = 'LOCAL_PYTHON_HEALTH_BASELINE_TRACE_DIAGNOSTIC'


def capture_policy(outlier, cpu_samples=False, concurrent_api=False, ready_stacks=False, python_frames=False,
                   python_baseline=False):
    binding.require(type(outlier) is bool, 'trace-outlier-mode-type')
    binding.require(type(python_baseline) is bool and (not python_baseline or
                    not any((outlier, cpu_samples, concurrent_api, ready_stacks, python_frames))),
                    'trace-python-baseline-fixed-mode')
    binding.require(type(python_frames) is bool and (not python_frames or
                    not any((outlier, cpu_samples, concurrent_api, ready_stacks))), 'trace-python-fixed-mode')
    binding.require(type(cpu_samples) is bool and (not cpu_samples or outlier), 'trace-cpu-outlier-mode')
    binding.require(type(ready_stacks) is bool
                    and (not ready_stacks or (outlier and concurrent_api and not cpu_samples)),
                    'trace-ready-concurrent-mode')
    binding.require(type(concurrent_api) is bool and (not concurrent_api or cpu_samples or ready_stacks),
                    'trace-concurrent-api-mode')
    if python_baseline:
        return dict(scope=PYTHON_BASELINE_SCOPE, contract_schema='sfl-python-health-baseline-contract-v1',
                    lease_schema='sfl-python-health-baseline-lease-v1', duration=6, guard=30,
                    profile_sha256=READY_PROFILE_SHA256)
    if python_frames:
        return dict(scope=PYTHON_SCOPE, contract_schema='sfl-python-health-trace-contract-v1',
                    lease_schema='sfl-python-health-trace-lease-v1', duration=6, guard=30,
                    profile_sha256=READY_PROFILE_SHA256)
    if ready_stacks:
        return dict(scope=READY_CONCURRENT_SCOPE, contract_schema='sfl-health-ready-concurrent-contract-v1',
                    lease_schema='sfl-health-ready-concurrent-lease-v1', duration=900, guard=960,
                    profile_sha256=READY_PROFILE_SHA256)
    if concurrent_api:
        return dict(scope=CPU_CONCURRENT_SCOPE, contract_schema='sfl-health-cpu-concurrent-contract-v1',
                    lease_schema='sfl-health-cpu-concurrent-lease-v1', duration=900, guard=960,
                    profile_sha256=CPU_PROFILE_SHA256)
    if cpu_samples:
        return dict(scope=CPU_OUTLIER_SCOPE, contract_schema='sfl-health-cpu-outlier-contract-v1',
                    lease_schema='sfl-health-cpu-outlier-lease-v1', duration=900, guard=960,
                    profile_sha256=CPU_PROFILE_SHA256)
    return dict(scope=OUTLIER_SCOPE if outlier else SCOPE,
                contract_schema='sfl-health-outlier-contract-v1' if outlier else 'sfl-health-trace-contract-v1',
                lease_schema='sfl-health-outlier-lease-v1' if outlier else 'sfl-health-trace-lease-v1',
                duration=900 if outlier else 6, guard=960 if outlier else 30, profile_sha256=PROFILE_SHA256)


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def read_locked(path, expected=None):
    with binding.locked_read(path) as stream:
        fact = binding.stream_fact(stream)
        binding.require(0 < fact['bytes'] <= 65536, 'trace-json-budget')
        if expected is not None:
            binding.require(digest(expected) and fact['sha256'] == expected, 'trace-json-pin')
        stream.seek(0)
        return binding.strict_json(stream.read()), fact


def publish(folder, name, value):
    temporary, target = folder / (name+'.writing'), folder / name
    binding.require(not target.exists() and not temporary.exists(), 'trace-publication-already-exists')
    fact = observation.write_json(temporary, value)
    # Windows rename fails if the destination exists; no replacement operation.
    temporary.rename(target)
    return fact


def gates(value):
    binding.require(value['release_gate'] == 'HOLD' and value['promotion_allowed'] is False, 'trace-gate-claim')


def generation_alive(pid, created):
    binding.require(type(pid) is int and 0 < pid < 2**32 and type(created) is int and 0 < created < 2**64,
                    'trace-native-generation-values')
    native = WindowsProcessReader().read(pid)
    binding.require(native.get('status') == 'CAPTURED' and native.get('pid') == pid
                    and native.get('created_100ns') == created, 'trace-owner-generation-unavailable-or-changed')
    return native


@dataclass(frozen=True)
class TracedHealthCollectionSpec(collection.HealthCollectionSpec):
    trace_contract_path: str = ''
    trace_contract_sha256: str = ''
    outlier_capture: bool = False
    cpu_samples: bool = False
    concurrent_api: bool = False
    ready_stacks: bool = False
    python_frames: bool = False
    tool: str = ''
    python_baseline: bool = False

    def validate(self):
        super().validate()
        binding.plain_path(self.trace_contract_path)
        binding.require(digest(self.trace_contract_sha256), 'trace-contract-sha256')
        capture_policy(self.outlier_capture, self.cpu_samples, self.concurrent_api, self.ready_stacks,
                       self.python_frames, self.python_baseline)
        if self.python_frames or self.python_baseline:
            binding.require(self.candidate == binding.CANDIDATE_1030, 'trace-python-candidate')
            binding.require(binding.plain_path(self.tool).name == python_stream.TOOL_NAME, 'trace-python-tool')
        else:
            binding.require(self.tool == '', 'trace-unexpected-python-tool')


class HealthTraceHandshake:
    def __init__(self, spec, duration, evidence_directory):
        spec.validate()
        self.policy = capture_policy(spec.outlier_capture, spec.cpu_samples, spec.concurrent_api, spec.ready_stacks,
                                     spec.python_frames, spec.python_baseline)
        binding.require(duration == self.policy['duration'] and type(duration) in (int, float),
                        'trace-capture-fixed-duration')
        self.spec = spec
        self.path = binding.plain_path(spec.trace_contract_path)
        self.folder = self.path.parent
        self.evidence_directory = Path(evidence_directory)
        binding.require(self.path.name == 'contract.json' and self.folder.name == 'trace-channel', 'trace-channel-path')
        self.held = ExitStack()
        self.contract = None
        self.binding = None
        self.ready_fact = None
        self.worker = None

    def __enter__(self):
        try:
            stream = self.held.enter_context(binding.locked_read(self.path))
            fact = binding.stream_fact(stream)
            binding.require(0 < fact['bytes'] <= 65536 and fact['sha256'] == self.spec.trace_contract_sha256,
                            'trace-contract-pin')
            stream.seek(0)
            c = self.contract = binding.strict_json(stream.read())
            binding.require(set(c) == {'schema', 'scope', 'run_id', 'channel_path', 'package_sha256',
                'backend_pid', 'backend_created_filetime', 'main_pid', 'duration_seconds', 'guard_seconds',
                'release_gate', 'promotion_allowed'}, 'trace-contract-members')
            binding.require(c['schema'] == self.policy['contract_schema'] and c['scope'] == self.policy['scope'],
                            'trace-contract-schema')
            binding.require(isinstance(c['run_id'], str) and re.fullmatch('[0-9a-f]{32}', c['run_id']), 'trace-run-id')
            binding.require(binding.plain_path(c['channel_path']) == self.folder and digest(c['package_sha256']),
                            'trace-contract-path-package')
            binding.require(type(c['duration_seconds']) is int and c['duration_seconds'] == self.policy['duration']
                            and type(c['guard_seconds']) is int and c['guard_seconds'] == self.policy['guard'],
                            'trace-contract-budget')
            binding.require(type(c['main_pid']) is int and c['main_pid'] == self.spec.main.pid
                            and type(c['backend_pid']) is int and c['backend_pid'] == self.spec.backend.pid
                            and type(c['backend_created_filetime']) is int
                            and c['backend_created_filetime'] == self.spec.backend_created_filetime, 'trace-contract-app-generation')
            gates(c)
            binding.require({p.name for p in self.folder.iterdir()} == {'contract.json'}, 'trace-channel-already-used')
            return self
        except Exception:
            self.held.close()
            raise

    def __exit__(self, *args):
        self.held.close()

    def common(self):
        return dict(run_id=self.contract['run_id'], contract_sha256=self.spec.trace_contract_sha256,
                    scope=self.policy['scope'], release_gate='HOLD', promotion_allowed=False)

    def wait(self, name, stop, seconds):
        deadline = time.perf_counter() + seconds
        path = self.folder / name
        while not path.exists():
            failure = self.folder / 'capture-failed.json'
            if failure.exists():
                failed, _ = read_locked(failure)
                binding.require(failed['schema'] == 'sfl-health-trace-failed-v1'
                                and all(failed[k] == v for k, v in self.common().items()), 'trace-failure-run-binding')
                gates(failed)
                raise ValueError('trace-coordinator-failed')
            binding.require(time.perf_counter() < deadline, 'trace-handshake-deadline:'+name)
            if stop.wait(.025):
                raise InterruptedError('trace-handshake-stop-requested')
        value, fact = read_locked(path)
        binding.require(all(value[k] == v for k, v in self.common().items()), 'trace-handshake-run-binding')
        gates(value)
        return value, fact

    def begin(self, evidence_files, stop):
        native = WindowsProcessReader().read(os.getpid())
        binding.require(native.get('status') == 'CAPTURED', 'trace-worker-native-unavailable')
        self.worker = dict(pid=os.getpid(), created_filetime=native['created_100ns'])
        self.ready_fact = publish(self.folder, 'collector-ready.json', dict(schema='sfl-health-trace-collector-ready-v1',
            **self.common(), worker=self.worker, initial_files=evidence_files, evidence_directory=str(self.evidence_directory),
            payload_reference_sha256=self.spec.reference_sha256,
            configuration_reference_sha256=self.spec.configuration_reference_sha256))
        go, go_fact = self.wait('capture-go.json', stop, 60)
        binding.require(go['schema'] == 'sfl-health-trace-go-v1' and go['collector_ready_sha256'] == self.ready_fact['sha256']
                        and go['worker'] == self.worker, 'trace-go-collector-binding')
        directory = binding.plain_path(go['trace_run_path'])
        binding.require(re.fullmatch('T[0-9a-f]{12}', directory.name) and directory.parent.name == 'SmartFactory',
                        'trace-run-path')
        lease, lease_fact = read_locked(directory/'lease.json', go['lease_sha256'])
        binding.require(lease['schema'] == self.policy['lease_schema'] and lease['scope'] == self.policy['scope'],
                        'trace-lease-schema')
        gates(lease)
        binding.require(lease['contract_sha256'] == self.spec.trace_contract_sha256
                        and lease['package_sha256'] == self.contract['package_sha256']
                        and lease['run_id'] == self.contract['run_id'] and lease['run_path'] == str(directory)
                        and lease['guard_seconds'] == self.policy['guard']
                        and lease['capture_seconds'] == self.policy['duration']
                        and lease['stop_timeout_seconds'] == 60
                        and lease['profile_sha256'] == self.policy['profile_sha256'],
                        'trace-lease-contract')
        binding.require(all(type(lease[k]) is int for k in ('guard_seconds', 'capture_seconds', 'stop_timeout_seconds', 'parent_pid')),
                        'trace-lease-number-types')
        binding.require(re.fullmatch('SFLTrace_[0-9a-f]{32}', lease['instance'])
                        and go['instance'] == lease['instance'], 'trace-instance-binding')
        ready, ready_fact = read_locked(directory/'ready.json', go['trace_ready_sha256'])
        binding.require(ready['instance'] == lease['instance'] and ready['lease_sha256'] == lease_fact['sha256'],
                        'trace-ready-binding')
        generation_alive(lease['parent_pid'], int(lease['parent_created_filetime']))
        generation_alive(go['guard']['pid'], int(go['guard']['created_filetime']))
        intent, _ = read_locked(directory/'start-intent.json')
        binding.require(intent['lease_sha256'] == lease_fact['sha256']
                        and intent['manifest_sha256'] == self.contract['package_sha256']
                        and intent['instance'] == lease['instance'] and intent['observed_before_start'] == 'ABSENT'
                        and intent['guard_pid'] == go['guard']['pid']
                        and intent['guard_created_filetime'] == go['guard']['created_filetime'], 'trace-guard-start-intent')
        binding.require(not any((directory/name).exists() for name in ('result.json', 'stop-request.json')), 'trace-already-terminal')
        self.binding = go
        return dict(go=go, go_fact=go_fact, lease=lease, lease_fact=lease_fact, ready=ready, ready_fact=ready_fact)

    def finish(self, evidence_files, stop):
        binding.require(self.binding is not None, 'trace-not-bound')
        window_fact = publish(self.folder, 'capture-complete.json', dict(schema='sfl-health-trace-window-v1',
            **self.common(), worker=self.worker, collector_ready_sha256=self.ready_fact['sha256'],
            evidence_files=evidence_files, finished_ns=time.perf_counter_ns()))
        ended, ended_fact = self.wait('capture-stopped.json', stop, 145)
        binding.require(ended['schema'] == 'sfl-health-trace-stopped-v1'
                        and ended['window_sha256'] == window_fact['sha256']
                        and type(ended['guard_exit']) is int and ended['guard_exit'] == 0,
                        'trace-completion-binding')
        directory = Path(self.binding['trace_run_path'])
        result, result_fact = read_locked(directory/'result.json', ended['trace_result']['sha256'])
        binding.require(result_fact == ended['trace_result'] and result['status'] == 'CONTROL_FLOW_COMPLETE'
                        and result['lease_sha256'] == self.binding['lease_sha256']
                        and result['instance'] == self.binding['instance'] and result['cleanup_confirmed'] is True
                        and result['trace_saved'] is True and result['cancelled_without_trace'] is False
                        and result['reason'] == 'controller-requested-stop' and result['errors'] == [],
                        'trace-terminal-status')
        with binding.locked_read(directory/'trace.etl') as stream:
            binding.require(0 < os.fstat(stream.fileno()).st_size <= 256*1024**2, 'trace-etl-budget')
            etl = binding.stream_fact(stream)
        binding.require(etl == ended['etl'] and all(etl[k] == result['etl'][k] for k in ('bytes', 'sha256')),
                        'trace-etl-pin')
        return dict(window_fact=window_fact, ended=ended, ended_fact=ended_fact, trace_result=result_fact, etl=etl)

    def abort(self, error_type):
        if self.contract is not None and not (self.folder/'capture-abort.json').exists():
            publish(self.folder, 'capture-abort.json', dict(schema='sfl-health-trace-abort-v1',
                **self.common(), error_type=error_type, worker=self.worker))


def _worker_entry(spec, output, duration, stop, sender):
    exit_code = 1
    try:
        with (Path(output)/'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
                (Path(output)/'worker.stderr.log').open('x', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            local_stop = observation.ObservationStop(stop)
            try:
                with HealthTraceHandshake(spec, duration, Path(output)/'evidence') as trace, \
                (python_stream.companion(spec, Path(output)/'python-stream', local_stop, allow_read_gaps=True)
                         if spec.python_frames else nullcontext(None)) as frames:
                    result = collection.collect(spec, output, duration, local_stop,
                        lambda item: sender.send_bytes(json.dumps(item).encode()), _trace=trace,
                        _outlier=spec.outlier_capture, _concurrent_api=spec.concurrent_api,
                        _ready_stacks=spec.ready_stacks, _python_frames=frames)
            finally:
                local_stop.close()
            fact = observation.write_json(Path(output)/'worker-result.json', result)
            sender.send_bytes(json.dumps(dict(phase='done', result=fact)).encode())
            exit_code = 0 if result['collection_status'] == 'BOUND_WINDOW_CAPTURED' else 1
    finally:
        sender.close()
    raise SystemExit(exit_code)


def supervise(spec, output, *, stop_event=None):
    binding.require(type(spec) is TracedHealthCollectionSpec, 'traced-diagnostic-spec-type')
    spec.validate()
    return observation.supervise_observation(spec, output,
        duration_seconds=capture_policy(spec.outlier_capture, spec.cpu_samples, spec.concurrent_api,
                                        spec.ready_stacks, spec.python_frames, spec.python_baseline)['duration'],
        preparation_timeout=180, finalization_timeout=180, stop_event=stop_event, _worker_target=_worker_entry)
