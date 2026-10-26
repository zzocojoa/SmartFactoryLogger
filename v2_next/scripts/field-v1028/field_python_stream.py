"""Pinned, bounded Python reads beside health requests in the owned collector.

Raw memory reads are non-atomic. Interval overlap does not establish latency
cause, CPU duration or GIL contention. No target process is stopped or written.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import field_health_collection as collection
import field_health_timing as timing
import field_installation_binding as binding
import field_native_timing as clock
import field_observation as observation
import field_python_frames as frames
from field_thread_identity import NativeTarget


TOOL_FACT = dict(bytes=7373774, sha256='03c2c8f803baec73f09a4cce57f31afaaec8840c23cc2830f4be584c7f9f6630')
TOOL_NAME = 'sfl_qpc_reader.exe'
CAP = 16 * 1024**2
LINE_CAP = 1024**2
BURSTS = 1
SAMPLES = 350
DURATION = 6


@dataclass(frozen=True)
class PythonHealthSpec(collection.HealthCollectionSpec):
    tool: str = ''

    def validate(self):
        super().validate()
        binding.require(self.candidate == binding.CANDIDATE_1030, 'stream-candidate-required')
        binding.require(binding.plain_path(self.tool).name == TOOL_NAME, 'stream-tool-name')


def tick(value):
    return type(value) is int and 0 <= value < 2**63


def ready_record(value, pid, birth):
    binding.require(set(value) == {'event', 'schema', 'pid', 'created_filetime', 'qpc_frequency',
        'init_begin', 'init_end', 'sample_limit', 'interval_ms', 'nonblocking', 'atomic_snapshot',
        'exact_sample_instant'}, 'stream-ready-members')
    binding.require(value['event'] == 'ready' and value['schema'] == 'sfl-persistent-python-window-v1'
        and type(value['pid']) is int and value['pid'] == pid
        and type(value['created_filetime']) is int and value['created_filetime'] == birth,
        'stream-ready-identity')
    binding.require(type(value['sample_limit']) is int and value['sample_limit'] == SAMPLES
        and type(value['interval_ms']) is int and value['interval_ms'] == 20
        and value['nonblocking'] is True and value['atomic_snapshot'] is False
        and value['exact_sample_instant'] is False, 'stream-ready-policy')
    binding.require(tick(value['qpc_frequency']) and value['qpc_frequency'] > 0
        and tick(value['init_begin']) and tick(value['init_end'])
        and value['init_begin'] <= value['init_end'], 'stream-ready-clock')
    return value


def decode(raw, pid, birth, generations, *, allow_read_gaps=False):
    binding.require(type(allow_read_gaps) is bool, 'stream-gap-policy')
    binding.require(0 < len(raw) <= CAP and raw.endswith(b'\n'), 'stream-output-size-or-truncated')
    lines = raw.splitlines(keepends=True)
    binding.require(len(lines) == SAMPLES+2 and all(0 < len(line) <= LINE_CAP for line in lines),
                    'stream-line-count-or-size')
    rows = [binding.strict_json(line) for line in lines]
    ready = ready_record(rows[0], pid, birth)
    last, samples, read_errors, frame_gaps = ready['init_end'], [], [], []
    for sequence, row in enumerate(rows[1:-1]):
        binding.require(set(row) == {'event', 'sequence', 'qpc_begin', 'qpc_end', 'stacks', 'error'}
            and row['event'] == 'sample' and type(row['sequence']) is int
            and row['sequence'] == sequence, 'stream-sample-sequence')
        binding.require(tick(row['qpc_begin']) and tick(row['qpc_end'])
            and last <= row['qpc_begin'] <= row['qpc_end'], 'stream-sample-clock')
        parsed, frame_gap, error = None, None, row['error']
        if row['error'] is not None:
            binding.require(allow_read_gaps and row['stacks'] is None
                and isinstance(row['error'], str) and 0 < len(row['error']) <= 4096,
                'stream-sample-read-failed')
            read_errors.append(dict(sequence=sequence, qpc_begin=row['qpc_begin'],
                                    qpc_end=row['qpc_end'], error=row['error']))
        else:
            parsed = frames.interpret(json.dumps(row['stacks'], allow_nan=False).encode(), pid, generations,
                                      allow_empty_stacks=allow_read_gaps)
            if parsed.get('empty_stacks'):
                # Retain the whole sample as a gap; other rows do not turn an
                # unavailable stack into a function match or a cause claim.
                error = 'empty-python-stack'
                frame_gap = dict(sequence=sequence, qpc_begin=row['qpc_begin'], qpc_end=row['qpc_end'],
                                 error=error, threads=parsed['empty_stacks'])
                frame_gaps.append(frame_gap)
                parsed = None
        samples.append(dict(sequence=sequence, qpc_begin=row['qpc_begin'], qpc_end=row['qpc_end'],
                            parsed=parsed, error=error, frame_gap=frame_gap))
        last = row['qpc_end']
    finished = rows[-1]
    binding.require(set(finished) == {'event', 'samples', 'errors', 'cancelled', 'release_gate', 'field_gate'}
        and finished['event'] == 'finished' and type(finished['samples']) is int and finished['samples'] == SAMPLES
        and type(finished['errors']) is int and finished['errors'] == len(read_errors) < SAMPLES
        and finished['cancelled'] is False
        and finished['release_gate'] == 'HOLD' and finished['field_gate'] == 'NOT_EVALUATED', 'stream-incomplete')
    binding.require(len(read_errors)+len(frame_gaps) < SAMPLES, 'stream-no-usable-frames')
    return dict(ready=ready, samples=samples, finished=finished, read_errors=read_errors, frame_gaps=frame_gaps)


def reader_outcome(code, stderr, parsed):
    # Exit 1 also covers incomplete/cancelled output. Decode must first prove a
    # complete, uncancelled set with a consistent nonzero read-error count.
    gaps = bool(parsed['read_errors'])
    binding.require((code == 0 and not stderr and not gaps) or
        (code == 1 and gaps and stderr in (b'SFL_READER_ERROR=reader-incomplete\n',
                                          b'SFL_READER_ERROR=reader-incomplete\r\n')),
        'stream-reader-failed')
    return 'CAPTURED_WITH_READ_GAPS' if gaps or parsed['frame_gaps'] else 'CAPTURED'


def capture(spec, output, stop, notify_ready, *, allow_read_gaps=False):
    """Only call in the owned collector Job; the target never joins that Job."""
    output = observation.http._prepare_output(output)
    result = dict(status='FAIL', errors=[], reader_pid=None, reader_exit=None,
                  reader_terminated=False, reader_threads_closed=False, tool=TOOL_FACT)
    child, drains, streams = None, [], {}
    failed = threading.Event()
    drain_errors = []

    def drain(name, pipe):
        kept, first = bytearray(), bytearray()
        seen = 0
        try:
            while chunk := pipe.read1(65536):
                seen += len(chunk)
                kept.extend(chunk[:max(0, CAP-len(kept))])
                if seen > CAP:
                    raise ValueError('stream-output-cap')
                if name == 'stdout' and first is not None:
                    first.extend(chunk)
                    if b'\n' in first:
                        line = bytes(first).split(b'\n', 1)[0]
                        binding.require(len(line)+1 <= LINE_CAP, 'stream-ready-size')
                        ready_record(binding.strict_json(line), spec.backend.pid, spec.backend_created_filetime)
                        notify_ready()
                        first = None
                    else:
                        binding.require(len(first) <= LINE_CAP, 'stream-ready-size')
        except Exception as error:
            drain_errors.append(dict(type=type(error).__name__, reason=str(error) if type(error) is ValueError else 'pipe-read'))
            failed.set()
        finally:
            streams[name] = dict(raw=bytes(kept), seen=seen)
            pipe.close()

    try:
        binding.require(not stop.is_set(), 'stream-stop-before-start')
        with binding.locked_read(spec.tool) as locked, \
                NativeTarget(spec.backend.pid, spec.backend_created_filetime, spec.backend.exe) as target, \
                target.threads() as threads:
            binding.require(binding.stream_fact(locked) == TOOL_FACT, 'stream-tool-pin')
            result.update(target_before=target.recheck(), threads_before=threads.before,
                          threads_unavailable=threads.unavailable, native_begin=clock.capture())
            child = subprocess.Popen([spec.tool, str(spec.backend.pid), str(spec.backend_created_filetime)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW)
            result['reader_pid'] = child.pid
            drains = [threading.Thread(target=drain, args=(name, getattr(child, name)), daemon=True)
                      for name in ('stdout', 'stderr')]
            for thread in drains:
                thread.start()
            deadline = time.monotonic()+9
            while child.poll() is None:
                binding.require(not stop.is_set(), 'stream-stop-requested')
                binding.require(not failed.is_set(), 'stream-pipe-failed')
                binding.require(time.monotonic() < deadline, 'stream-reader-deadline')
                time.sleep(.01)
            result['reader_exit'] = child.returncode
            for thread in drains:
                thread.join(1)
            binding.require(not any(t.is_alive() for t in drains) and not failed.is_set(), 'stream-pipe-failed')
            result.update(native_end=clock.capture(), threads_after=threads.finish(), target_after=target.recheck())
            parsed = decode(streams['stdout']['raw'], spec.backend.pid, spec.backend_created_filetime,
                            result['threads_after'], allow_read_gaps=allow_read_gaps)
            status = reader_outcome(child.returncode, streams['stderr']['raw'], parsed)
            joined = clock.interval(result['native_begin'], result['native_end'])
            binding.require(joined['status'] == 'CORRELATABLE_BOUNDARIES', 'stream-native-clock-unavailable')
            begin, end = (result[name]['boundary'] for name in ('native_begin', 'native_end'))
            binding.require(begin['qpc_frequency'] == end['qpc_frequency'] == parsed['ready']['qpc_frequency']
                and begin['qpc_ticks'] <= parsed['ready']['init_begin']
                and parsed['samples'][-1]['qpc_end'] <= end['qpc_ticks'], 'stream-outside-native-envelope')
            binding.require(binding.stream_fact(locked) == TOOL_FACT, 'stream-tool-closeout-pin')
            result.update(status=status, ready=parsed['ready'], clock_join=joined,
                successful_reads=SAMPLES-len(parsed['read_errors']), failed_reads=len(parsed['read_errors']),
                frame_gap_reads=len(parsed['frame_gaps']),
                usable_reads=SAMPLES-len(parsed['read_errors'])-len(parsed['frame_gaps']),
                read_errors=parsed['read_errors'], frame_gaps=parsed['frame_gaps'],
                read_windows=[dict(sequence=s['sequence'], qpc_begin=s['qpc_begin'], qpc_end=s['qpc_end'],
                                   generation_status=s['parsed']['status'] if s['parsed'] else (
                                       'EMPTY_STACK_GAP' if s['frame_gap'] else 'READ_FAILED'))
                              for s in parsed['samples']])
    except Exception as error:
        result['errors'].append(dict(type=type(error).__name__, reason=str(error)
                                     if type(error) is ValueError else 'stream-capture-failed'))
    finally:
        if child is not None:
            child.stdin.close()  # EOF asks this reader to finish; never controls the target.
            if child.poll() is None:
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    child.kill()  # Our Popen HANDLE only.
                    result['reader_terminated'] = True
                    child.wait(timeout=2)
            result['reader_exit'] = child.returncode
        for thread in drains:
            thread.join(1)
        result['reader_threads_closed'] = not any(t.is_alive() for t in drains)
        binding.require(result['reader_threads_closed'], 'stream-drain-cleanup-failed')
        result['drain_errors'] = drain_errors
        result['streams'] = {}
        for name, data in streams.items():
            with (output/(name+'.bin')).open('xb') as handle:
                handle.write(data['raw'])
            result['streams'][name] = dict(observation.file_fact(output/(name+'.bin')), seen=data['seen'])
        result['stop_requested'] = stop.is_set()
        observation.write_json(output/'result.json', result)
    return result


def observation_coverage(decoded, runs, window):
    """Bound the read schedule around the full observation; samples stay discrete."""
    binding.require(len(decoded) == len(runs) == 1, 'stream-restart-gap')
    binding.require(set(window) == {'origin_ns', 'duration_seconds'}
        and type(window['origin_ns']) is int and window['origin_ns'] >= 0
        and type(window['duration_seconds']) is int and window['duration_seconds'] == DURATION,
        'stream-observation-window')
    run = runs[0][1]
    calibration = clock.interval(run['native_begin'], run['native_end'])
    binding.require(calibration['status'] == 'CORRELATABLE_BOUNDARIES', 'stream-window-clock')
    frequency = decoded[0]['ready']['qpc_frequency']
    binding.require(frequency == run['native_begin']['boundary']['qpc_frequency'], 'stream-window-frequency')
    def mapped(stamp):
        return [(stamp-calibration['qpc_offset_upper_ns'])*frequency//1_000_000_000,
                ((stamp-calibration['qpc_offset_lower_ns'])*frequency+999_999_999)//1_000_000_000]
    begin = mapped(window['origin_ns'])
    end = mapped(window['origin_ns']+DURATION*1_000_000_000)
    samples = decoded[0]['samples']
    first, last = samples[0]['qpc_begin'], samples[-1]['qpc_end']
    binding.require(first <= begin[0] <= begin[1] <= end[0] <= end[1] <= last,
                    'stream-observation-not-spanned')
    return dict(status='READ_SCHEDULE_SPANS_OBSERVATION_WINDOW', **window,
        qpc_frequency=frequency, origin_qpc_bounds=begin, end_qpc_bounds=end,
        first_read_qpc=first, last_read_qpc=last, reader_processes=1,
        max_read_start_gap_ms=max(b['qpc_begin']-a['qpc_begin'] for a,b in zip(samples,samples[1:]))*1000/frequency,
        continuous_frame_coverage=False)


def correlate(spec, runs, probes, *, allow_read_gaps=False, observation_window=None):
    """Revalidate raw inputs; a temporal/generation join is not a cause claim."""
    decoded = []
    for folder, result in runs:
        binding.require(result['status'] == 'CAPTURED' or
            allow_read_gaps and result['status'] == 'CAPTURED_WITH_READ_GAPS', 'stream-run-incomplete')
        with binding.locked_read(folder/'stdout.bin') as handle:
            fact = binding.stream_fact(handle)
            binding.require(all(fact[k] == result['streams']['stdout'][k] for k in fact), 'stream-raw-pin')
            handle.seek(0)
            parsed = decode(handle.read(CAP+1), spec.backend.pid, spec.backend_created_filetime,
                            {int(k): v for k, v in result['threads_after'].items()},
                            allow_read_gaps=allow_read_gaps)
        with binding.locked_read(folder/'stderr.bin') as handle:
            fact = binding.stream_fact(handle)
            binding.require(all(fact[k] == result['streams']['stderr'][k] for k in fact), 'stream-stderr-pin')
            handle.seek(0)
            binding.require(reader_outcome(result['reader_exit'], handle.read(CAP+1), parsed) == result['status'],
                            'stream-result-status')
        decoded.append(parsed)
    rows = []
    for probe in probes:
        binding.require(probe['status'] == 'REQUEST_AND_RUNTIME_BOUND', 'stream-request-not-bound')
        valid = timing.validate_health_sample(probe['health_record'], bytes.fromhex(probe['health_body_hex']),
            probe_id=probe['probe_id'], backend_pid=spec.backend.pid, backend_created_filetime=spec.backend_created_filetime)
        binding.require(valid['status'] == 'REQUEST_AND_NATIVE_CLOCK_BOUND', 'stream-request-clock')
        bounds = valid['checkpoint_qpc_bounds']
        def mapped(value):
            frequency = valid['qpc_frequency']
            return [(value-valid['qpc_offset_upper_ns'])*frequency//1_000_000_000,
                    ((value-valid['qpc_offset_lower_ns'])*frequency+999_999_999)//1_000_000_000]
        client_begin = mapped(probe['health_record']['started_ns'])
        client_end = mapped(probe['health_record']['response_finished_ns'])
        intervals = {'client_request': (client_begin, client_end),
                     'route': (bounds['route_enter'], bounds['route_resume'])}
        intervals.update({right: (bounds[left], bounds[right]) for left, right in zip(timing.POINTS, timing.POINTS[1:])})
        matches, gaps = [], []
        for burst, run in enumerate(decoded):
            binding.require(run['ready']['qpc_frequency'] == valid['qpc_frequency'], 'stream-request-frequency')
            for sample in run['samples']:
                begin, end = sample['qpc_begin'], sample['qpc_end']
                if end < client_begin[0] or begin > client_end[1]:
                    continue
                if sample['parsed'] is None:
                    gaps.append(dict(burst=burst, sequence=sample['sequence'], qpc_begin=begin,
                                     qpc_end=end, error=sample['error'], frame_gap=sample['frame_gap']))
                    continue
                contained = [name for name, (left, right) in intervals.items() if left[1] <= begin <= end <= right[0]]
                roles = []
                for row in sample['parsed']['rows']:
                    for role, identity in valid['threads'].items():
                        if (row['generation_status'] == 'BOUND' and row['os_thread_id'] == identity['tid']
                                and row['created_filetime'] == identity['created_filetime']):
                            roles.append(dict(role=role, tid=identity['tid'], created_filetime=identity['created_filetime'], frames=row['frames']))
                matches.append(dict(burst=burst, sequence=sample['sequence'], qpc_begin=begin, qpc_end=end,
                                    contained_intervals=contained, bound_roles=roles))
        rows.append(dict(probe_id=probe['probe_id'], request_ms=probe['health_record']['client_request_and_body_ms'],
            validation=valid, matches=matches, read_gaps=gaps,
            coverage='READ_GAPS_OVERLAP_REQUEST' if gaps else ('MATCHES_RECORDED' if matches else 'NO_READ_OVERLAP')))
    failures = sum(len(run['read_errors']) for run in decoded)
    frame_gaps = sum(len(run['frame_gaps']) for run in decoded)
    result = dict(schema='sfl-python-http-correlation-v1', requests=rows, atomic_snapshot=False,
        read_quality='READ_GAPS_DETECTED' if failures or frame_gaps else 'NO_READ_ERRORS',
        attempted_reads=SAMPLES*len(decoded), successful_reads=SAMPLES*len(decoded)-failures, failed_reads=failures,
        frame_gap_reads=frame_gaps, usable_reads=SAMPLES*len(decoded)-failures-frame_gaps,
        exact_sample_instant=False, latency_cause='UNDETERMINED', etw_coverage='NOT_EVALUATED',
        field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)
    if observation_window is not None:
        result['observation_window'] = observation_coverage(decoded, runs, observation_window)
    return result


class PythonStream:
    def __init__(self, spec, output, stop, *, allow_read_gaps=False):
        binding.require(type(allow_read_gaps) is bool, 'stream-gap-policy')
        self.allow_read_gaps = allow_read_gaps
        self.spec, self.output, self.stop = spec, Path(output), stop
        self.cancel = threading.Event()
        self.ready = threading.Event()
        self.thread = None
        self.runs, self.errors = [], []

    def is_set(self):
        return self.cancel.is_set() or self.stop.is_set()

    def _run(self):
        try:
            for number in range(BURSTS):
                folder = self.output/f'burst-{number}'
                result = capture(self.spec, folder, self, self.ready.set, allow_read_gaps=self.allow_read_gaps)
                self.runs.append((folder, result))
                binding.require(result['status'] == 'CAPTURED' or self.allow_read_gaps
                    and result['status'] == 'CAPTURED_WITH_READ_GAPS', 'stream-burst-failed')
        except Exception as error:
            self.errors.append(dict(type=type(error).__name__, reason=str(error)
                                   if type(error) is ValueError else 'stream-background-failed'))

    def start(self):
        binding.require(self.thread is None and not self.is_set(), 'stream-already-started-or-stopped')
        observation.http._prepare_output(self.output)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        deadline = time.monotonic()+10
        while not self.ready.wait(.02):
            binding.require(self.thread.is_alive() and not self.is_set() and time.monotonic() < deadline,
                            'stream-ready-unavailable')
        binding.require(not self.errors and not self.is_set(), 'stream-start-failed')
        return dict(tool=TOOL_FACT, bursts=BURSTS, samples_per_burst=SAMPLES, interval_ms=20,
                    observed_ns=time.perf_counter_ns(), exact_sample_instant=False)

    def finish(self, probes, *, origin_ns):
        binding.require(self.thread is not None, 'stream-not-started')
        deadline = time.monotonic()+30
        while self.thread.is_alive():
            binding.require(not self.is_set() and time.monotonic() < deadline, 'stream-finish-deadline-or-stop')
            self.thread.join(.02)
        binding.require(not self.errors and len(self.runs) == BURSTS, 'stream-incomplete')
        joined = correlate(self.spec, self.runs, probes, allow_read_gaps=self.allow_read_gaps,
                           observation_window=dict(origin_ns=origin_ns, duration_seconds=DURATION))
        observation.write_json(self.output/'correlation.json', joined)
        facts = {p.relative_to(self.output).as_posix(): observation.file_fact(p)
                 for p in self.output.rglob('*') if p.is_file()}
        fact = observation.write_json(self.output/'manifest.json', dict(files=facts))
        return dict(status='CAPTURED_WITH_READ_GAPS' if joined['read_quality'] == 'READ_GAPS_DETECTED' else 'CAPTURED',
                    bursts=BURSTS, attempted_reads=SAMPLES, reads=joined['successful_reads'],
                    failed_reads=joined['failed_reads'], read_quality=joined['read_quality'], manifest=fact,
                    frame_gap_reads=joined['frame_gap_reads'], usable_reads=joined['usable_reads'],
                    observation_window=joined['observation_window'],
                    correlation=facts['correlation.json'], latency_cause='UNDETERMINED',
                    etw_coverage='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)

    def abort(self):
        self.cancel.set()
        if self.thread is not None:
            self.thread.join(6)
            binding.require(not self.thread.is_alive(), 'stream-background-cleanup-failed')
        return dict(background_closed=True, errors=list(self.errors), bursts=len(self.runs),
            files={p.relative_to(self.output).as_posix(): observation.file_fact(p)
                   for p in self.output.rglob('*') if p.is_file()})


@contextmanager
def companion(spec, output, stop, *, allow_read_gaps=False):
    stream = PythonStream(spec, output, stop, allow_read_gaps=allow_read_gaps)
    try:
        yield stream
    finally:
        stream.abort()


def worker_entry(spec, output, duration, stop, sender):
    exit_code = 1
    try:
        with (Path(output)/'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
                (Path(output)/'worker.stderr.log').open('x', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            local_stop = observation.ObservationStop(stop)
            try:
                with companion(spec, Path(output)/'python-stream', local_stop) as stream:
                    result = collection.collect(spec, output, duration, local_stop,
                        lambda item: sender.send_bytes(json.dumps(item).encode()), _python_frames=stream)
            finally:
                local_stop.close()
            fact = observation.write_json(Path(output)/'worker-result.json', result)
            sender.send_bytes(json.dumps(dict(phase='done', result=fact)).encode())
            exit_code = 0 if result['collection_status'] == 'BOUND_WINDOW_CAPTURED' else 1
    finally:
        sender.close()
    raise SystemExit(exit_code)
