"""Fixed three-snapshot Python frame diagnostic inside the existing owned job.

This module never controls the target application. The protected outer launcher
remains required; completion is not performance QA or release approval.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import field_configuration_binding as configuration
import field_generation_binding as generation
import field_installation_binding as binding
import field_native_timing as clock
import field_observation as observation
from field_thread_identity import NativeTarget


TOOL_FACT = dict(bytes=4815360, sha256='6e83ab095f40453742d01a2719a178f308534015da519ec0659d2584139dc995')
DURATION = 6
CAP = 1024**2
SCOPE = 'THREE_NONBLOCKING_PYTHON_SNAPSHOTS_NOT_PERFORMANCE_QA'


@dataclass(frozen=True)
class PythonFrameSpec(observation.TimingObservationSpec):
    tool: str = ''

    def validate(self):
        super().validate()
        binding.require(self.candidate == binding.CANDIDATE_1030, 'frame-candidate-required')
        path = binding.plain_path(self.tool)
        binding.require(path.name == 'py-spy.exe', 'frame-tool-name')


def interpret(raw, pid, generations, *, allow_empty_stacks=False):
    binding.require(type(allow_empty_stacks) is bool, 'frame-empty-stack-policy')
    # The shared decoder enforces unique object keys/finite JSON but requires
    # an object root. Wrap only for decoding this tool's documented array root.
    document = binding.strict_json(b'{"stacks":' + raw + b'}')
    binding.require(set(document) == {'stacks'}, 'frame-json-root')
    rows = document['stacks']
    binding.require(isinstance(rows, list) and 0 < len(rows) <= 512, 'frame-thread-count')
    ids, native_ids, interpreted, empty_stacks = set(), set(), [], []
    for row in rows:
        binding.require(isinstance(row, dict) and set(row) == {
            'pid', 'thread_id', 'thread_name', 'os_thread_id', 'active', 'owns_gil', 'frames', 'process_info'},
            'frame-thread-members')
        binding.require(type(row['pid']) is int and row['pid'] == pid and row['process_info'] is None,
                        'frame-process-mismatch')
        tid = row['os_thread_id']
        binding.require((tid is None or type(tid) is int and 0 < tid < 2**32)
                        and type(row['thread_id']) is int and 0 < row['thread_id'] < 2**64,
                        'frame-thread-id')
        binding.require(row['thread_id'] not in ids, 'frame-duplicate-thread')
        ids.add(row['thread_id'])
        if tid is not None:
            binding.require(tid not in native_ids, 'frame-duplicate-native-thread')
            native_ids.add(tid)
        binding.require(row['thread_name'] is None or isinstance(row['thread_name'], str)
                        and len(row['thread_name']) <= 4096, 'frame-thread-name')
        binding.require(type(row['active']) is bool and type(row['owns_gil']) is bool, 'frame-thread-flags')
        frames = row['frames']
        binding.require(isinstance(frames, list) and len(frames) <= 512
                        and (frames or allow_empty_stacks), 'frame-stack-budget')
        if not frames:
            empty_stacks.append(dict(thread_id=row['thread_id'], os_thread_id=tid))
        for frame in frames:
            binding.require(isinstance(frame, dict) and set(frame) == {
                'name', 'filename', 'module', 'short_filename', 'line', 'locals', 'is_entry', 'is_shim_entry'},
                'frame-members')
            binding.require(frame['locals'] is None, 'frame-locals-forbidden')
            for key in ('name', 'filename', 'short_filename'):
                binding.require(isinstance(frame[key], str) and len(frame[key]) <= 8192, 'frame-string-budget')
            binding.require(frame['module'] is None or isinstance(frame['module'], str)
                            and len(frame['module']) <= 8192, 'frame-module-budget')
            binding.require(type(frame['line']) is int and 0 <= frame['line'] < 2**31
                            and type(frame['is_entry']) is bool and type(frame['is_shim_entry']) is bool,
                            'frame-line-or-flags')
        native = generations.get(tid)
        stable = native is not None and native['stable'] is True
        interpreted.append(dict(**row, generation_status='BOUND' if stable else 'UNBOUND',
            created_filetime=native['created_filetime'] if stable else None))
    result = dict(status='GENERATIONS_BOUND' if not empty_stacks and all(
                    r['generation_status'] == 'BOUND' for r in interpreted) else 'PARTIAL',
                rows=interpreted, atomic_snapshot=False,
                native_threads_without_python_frames=sorted(set(generations) - {
                    r['os_thread_id'] for r in rows if r['os_thread_id'] and r['frames']}))
    if allow_empty_stacks:
        result['empty_stacks'] = empty_stacks
    return result


def capture(target, tool, output, stop):
    output = observation.http._prepare_output(output)
    result = dict(status='FAIL', errors=[], started_ns=time.perf_counter_ns(), output_cap=CAP,
                  field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False,
                  read_window=dict(status='UNAVAILABLE', reason='reader-not-completed',
                                   scope='READER_ENVELOPE_ONLY', sample_instant_available=False))
    child, readers = None, []
    overflow = threading.Event()
    streams, errors = {}, []

    def drain(name, stream):
        kept = bytearray()
        seen = 0
        try:
            while chunk := stream.read(65536):
                seen += len(chunk)
                kept.extend(chunk[:max(0, CAP - len(kept))])
                if seen > CAP:
                    overflow.set()
            streams[name] = dict(raw=bytes(kept), seen=seen)
        except BaseException as error:
            errors.append(type(error).__name__)
            overflow.set()
        finally:
            stream.close()

    try:
        binding.require(not stop.is_set(), 'frame-stop-before-start')
        tool = binding.plain_path(tool)
        binding.require(tool.name == 'py-spy.exe', 'frame-tool-name')
        with binding.locked_read(tool) as locked, target.threads() as threads:
            binding.require(binding.stream_fact(locked) == TOOL_FACT, 'frame-tool-pin')
            result['target_before'] = target.recheck()
            result['threads_before'] = threads.before
            result['threads_unavailable'] = threads.unavailable
            args = [str(tool), 'dump', '--pid', str(target.pid), '--json', '--full-filenames', '--nonblocking']
            result['argv'] = args
            result['read_started_ns'] = time.perf_counter_ns()
            result['native_begin'] = clock.capture()
            child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            result['reader_pid'] = child.pid
            readers = [threading.Thread(target=drain, args=(name, getattr(child, name)), daemon=True)
                       for name in ('stdout', 'stderr')]
            for reader in readers:
                reader.start()
            deadline = time.monotonic() + 2
            while child.poll() is None:
                binding.require(not stop.is_set(), 'frame-stop-requested')
                binding.require(not overflow.is_set(), 'frame-output-limit')
                binding.require(time.monotonic() < deadline, 'frame-reader-timeout')
                time.sleep(.01)
            result['reader_exit'] = child.returncode
            for reader in readers:
                reader.join(1)
            binding.require(not any(r.is_alive() for r in readers) and not errors, 'frame-reader-drain-failed')
            result['read_finished_ns'] = time.perf_counter_ns()
            result['native_end'] = clock.capture()
            binding.require(not overflow.is_set(), 'frame-output-limit')
            binding.require(child.returncode == 0 and not streams['stderr']['raw'], 'frame-reader-failed')
            result['threads_after'] = after = threads.finish()
            result['target_after'] = target.recheck()
            parsed = interpret(streams['stdout']['raw'], target.pid, after)
            result['parsed'] = parsed
            binding.require(binding.stream_fact(locked) == TOOL_FACT, 'frame-tool-closeout-pin')
            result['status'] = 'CAPTURED' if parsed['status'] == 'GENERATIONS_BOUND' else 'PARTIAL'
            joined = clock.interval(result['native_begin'], result['native_end'])
            result['clock_join'] = joined
            if joined['status'] == 'CORRELATABLE_BOUNDARIES':
                begin, end = (result[name]['boundary'] for name in ('native_begin', 'native_end'))
                result['read_window'] = dict(status='BOUNDED', reason=None,
                    scope='READER_ENVELOPE_ONLY', sample_instant_available=False,
                    qpc_begin=begin['qpc_ticks'], qpc_end=end['qpc_ticks'],
                    qpc_frequency=begin['qpc_frequency'])
            else:
                result['read_window']['reason'] = joined['reason']
    except Exception as error:
        result['errors'].append(dict(type=type(error).__name__, reason=str(error)
                                    if type(error) is ValueError else 'frame-snapshot-failed'))
    finally:
        if child is not None and child.poll() is None:
            child.kill()  # Only our own reader HANDLE; never the target.
            child.wait(timeout=2)
            result['reader_terminated'] = True
        for reader in readers:
            reader.join(1)
        result['reader_threads_closed'] = not any(r.is_alive() for r in readers)
        if not result['reader_threads_closed']:
            result['status'] = 'FAIL'
        result['streams'] = {}
        for name, record in streams.items():
            with (output/(name+'.bin')).open('xb') as stream:
                stream.write(record['raw'])
            result['streams'][name] = dict(fact=observation.file_fact(output/(name+'.bin')), seen_bytes=record['seen'])
        result['finished_ns'] = time.perf_counter_ns()
        observation.write_json(output/'result.json', result)
    return result


def collect(spec, output, duration, stop, notify):
    spec.validate()
    binding.require(type(duration) is int and duration == DURATION, 'frame-fixed-duration')
    output = observation.http._prepare_output(Path(output)/'frames')
    result = dict(observation_status='FAIL', validation_scope=SCOPE, errors=[], samples=[],
                  field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)

    def save(name, value):
        observation.write_json(output/name, value)
        return value

    try:
        binding.require(not stop.is_set(), 'frame-stop-before-binding')
        with binding.InstalledPayload(spec.root, spec.reference, expected_reference_sha256=spec.reference_sha256,
                extras=spec.extras, candidate=spec.candidate) as payload, \
                configuration.configuration_reference(spec.configuration_reference,
                    spec.configuration_reference_sha256, candidate=spec.candidate) as expected, \
                NativeTarget(spec.backend.pid, spec.backend_created_filetime, spec.backend.exe) as target:
            runtime = save('runtime-initial.json', binding.capture_runtime_binding(payload, spec.main, spec.backend, spec.port))
            binding.require(runtime['binding_status'] == 'PASS', 'frame-runtime-binding')
            sessions = runtime['sessions']
            control = save('control-initial.json', generation.capture_generation(payload, spec.main, spec.backend, spec.port))
            binding.require(control['generation_status'] == 'PASS', 'frame-control-binding')
            config = save('configuration-initial.json', configuration.capture_configuration(
                payload, spec.main, spec.backend, spec.port, sessions, expected))
            binding.require(config['configuration_status'] == 'PASS', 'frame-configuration-binding')
            origin = time.perf_counter_ns()
            notify(dict(phase='observing', origin_ns=origin))
            for sequence in range(3):
                due = origin + sequence * 2_000_000_000
                binding.require(not stop.wait(max(0, (due-time.perf_counter_ns())/1e9)), 'frame-stop-requested')
                binding.require(time.perf_counter_ns() < due + 2_000_000_000, 'frame-slot-missed')
                sample = capture(target, spec.tool, output/f'sample-{sequence}', stop)
                result['samples'].append(dict(sequence=sequence, status=sample['status'],
                    read_window_status=sample['read_window']['status']))
                binding.require(sample['status'] in ('CAPTURED', 'PARTIAL'), 'frame-sample-failed')
            notify(dict(phase='finalizing', origin_ns=origin))
            final = save('runtime-final.json', binding.capture_runtime_binding(payload, spec.main, spec.backend, spec.port))
            binding.require(final['binding_status'] == 'PASS' and final['sessions'] == sessions, 'frame-runtime-closeout')
            final_control = save('control-final.json', generation.capture_generation(
                payload, spec.main, spec.backend, spec.port, expected_identity=control['identity']))
            binding.require(final_control['generation_status'] == 'PASS', 'frame-control-closeout')
            final_config = save('configuration-final.json', configuration.capture_configuration(
                payload, spec.main, spec.backend, spec.port, sessions, expected))
            binding.require(final_config['configuration_status'] == 'PASS', 'frame-configuration-closeout')
            save('target-final.json', target.recheck())
            save('payload-final.json', payload.recheck())
        binding.require(not stop.is_set(), 'frame-stop-before-closeout')
        result['observation_status'] = 'PASS'
        result['sample_coverage'] = 'PARTIAL' if any(s['status'] == 'PARTIAL' for s in result['samples']) else 'GENERATIONS_BOUND'
        result['clock_coverage'] = 'BOUNDED' if all(s['read_window_status'] == 'BOUNDED'
            for s in result['samples']) else 'UNAVAILABLE_OR_PARTIAL'
    except Exception as error:
        result['errors'].append(dict(type=type(error).__name__, reason=str(error)
                                    if type(error) is ValueError else 'frame-collection-failed'))
    result['stop_requested'] = stop.is_set()
    save('summary.json', result)
    return result


def worker_entry(spec, output, duration, stop, sender):
    exit_code = 1
    try:
        with (Path(output)/'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
                (Path(output)/'worker.stderr.log').open('x', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            local_stop = observation.ObservationStop(stop)
            try:
                result = collect(spec, output, duration, local_stop,
                                 lambda item: sender.send_bytes(json.dumps(item).encode()))
            finally:
                local_stop.close()
            fact = observation.write_json(Path(output)/'worker-result.json', result)
            sender.send_bytes(json.dumps(dict(phase='done', result=fact)).encode())
            exit_code = 0 if result['observation_status'] == 'PASS' else 1
    finally:
        sender.close()
    raise SystemExit(exit_code)
