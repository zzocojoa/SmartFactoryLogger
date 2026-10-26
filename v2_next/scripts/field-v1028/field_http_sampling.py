"""Independent loopback HTTP sampling component; no production launch entrypoint.

The future field orchestrator must bind installed build/session identities and
collect resources, UI, packet and shutdown evidence. This module never grants
field QA or promotion, even when its HTTP observation is complete.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import socket
import threading
import time
from uuid import uuid4

from PIL import Image

import field_native_timing


@dataclass(frozen=True)
class Endpoint:
    name: str
    path: str
    interval_seconds: float
    kind: str
    warning_ms: float | None
    failure_ms: float | None
    max_body_bytes: int


ENDPOINTS = (
    Endpoint('health', '/health', 2.0, 'json', 50, 200, 1024 * 1024),
    Endpoint('data', '/api/data', 6.0, 'json', 100, 500, 8 * 1024 * 1024),
    Endpoint('image', '/api/spot/live_image.jpg', .25, 'jpeg', 500, None, 2 * 1024 * 1024),
)
CONTROL_HEALTH = Endpoint('control_health', '/api/control/health', 5.0, 'json', 50, 200, 1024 * 1024)
SPOT_CONFIG = Endpoint('spot_config', '/api/spot/config', 5.0, 'json', None, None, 8 * 1024 * 1024)


def _validate_endpoint(endpoint):
    reference = next((item for item in (*ENDPOINTS, CONTROL_HEALTH, SPOT_CONFIG) if item.name == endpoint.name), None)
    if reference is None or any(getattr(reference, key) != getattr(endpoint, key)
                                for key in ('path', 'kind', 'warning_ms', 'failure_ms', 'max_body_bytes')):
        raise ValueError('Endpoint contract mismatch')
    if not math.isfinite(endpoint.interval_seconds) or endpoint.interval_seconds <= 0:
        raise ValueError('Positive finite sampling interval required')


class _DeadlineSocket(socket.socket):
    """SocketIO.readinto calls recv_into: refresh remaining total time per read."""
    def __init__(self, deadline_ns):
        super().__init__(socket.AF_INET, socket.SOCK_STREAM)
        self.deadline_ns = deadline_ns

    def _remaining(self):
        remaining = (self.deadline_ns - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            raise TimeoutError('whole-request-deadline')
        self.settimeout(remaining)

    def connect(self, address):
        self._remaining()
        return super().connect(address)

    def sendall(self, data, flags=0):
        self._remaining()
        return super().sendall(data, flags)

    def recv_into(self, buffer, nbytes=0, flags=0):
        self._remaining()
        return super().recv_into(buffer, nbytes, flags)


class _LoopbackConnection(http.client.HTTPConnection):
    def __init__(self, port, deadline_ns):
        super().__init__('127.0.0.1', port)
        self.deadline_ns = deadline_ns

    def connect(self):
        self.sock = _DeadlineSocket(self.deadline_ns)
        self.sock.connect(('127.0.0.1', self.port))


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-finite JSON constant: ' + value)


def _contains_control_token(raw, token):
    # Check ASCII JSON unicode escapes even in partial/invalid JSON. Credentials
    # are lowercase ASCII hex; raw evidence containing that echo is withheld.
    decoded_ascii = re.sub(rb'\\u00([0-9a-f]{2})',
                           lambda match: bytes([int(match.group(1), 16)]), bytes(raw).lower())
    return token.encode('ascii') in decoded_ascii.lower()


def fetch_sample(port, endpoint, *, timeout_seconds=5.0, control_token=None, include_native_timing=True,
                 health_probe_id=None):
    """Preserve full/partial response bytes; elapsed time excludes decoding/I/O."""
    _validate_endpoint(endpoint)
    if health_probe_id is not None and (endpoint.name != 'health' or not isinstance(health_probe_id, str)
            or re.fullmatch('[0-9a-f]{32}', health_probe_id) is None):
        raise ValueError('Health probe requires the health endpoint and a lowercase 32-hex ID')
    if endpoint.name == CONTROL_HEALTH.name:
        if not isinstance(control_token, str) or re.fullmatch('[0-9a-f]{64}', control_token) is None:
            raise ValueError('Control health requires a valid embedded token')
    elif control_token is not None:
        raise ValueError('Control token forbidden for other endpoints')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Loopback port required')
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
        raise ValueError('Timeout must be in (0, 30] seconds')
    if type(include_native_timing) is not bool:
        raise ValueError('Native timing flag must be boolean')
    started = time.perf_counter_ns()
    deadline = started + round(timeout_seconds * 1e9)
    native_begin = field_native_timing.capture() if include_native_timing else None
    result = {'kind': 'request', 'endpoint': endpoint.name, 'path': endpoint.path,
              'started_ns': started, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'status': None, 'headers': [], 'body_complete': False, 'decode_complete': False,
              'timeout': False, 'error_type': None, 'error_reason': None,
              'connect_ms': None, 'send_ms': None, 'headers_wait_ms': None, 'body_ms': None,
              'decode_ms': None, 'timeout_seconds': timeout_seconds}
    connection = _LoopbackConnection(port, deadline)
    if health_probe_id is not None:
        result['health_probe_id'] = health_probe_id
    response = None
    raw = bytearray()
    received = None
    native_end = None
    try:
        connection.connect()
        connected = time.perf_counter_ns()
        result['connect_ms'] = (connected - started) / 1e6
        request_headers = {'Connection': 'close', 'Accept-Encoding': 'identity',
                           'User-Agent': 'SFL-Field-HTTP-Probe/1'}
        if control_token is not None:
            request_headers['X-SFL-Control-Token'] = control_token
        if health_probe_id is not None:
            request_headers['X-SFL-Health-Probe'] = health_probe_id
        connection.request('GET', endpoint.path, headers=request_headers)
        sent = time.perf_counter_ns()
        result['send_ms'] = (sent - connected) / 1e6
        response = connection.getresponse()
        headers_at = time.perf_counter_ns()
        headers = response.getheaders()
        encoded_headers = json.dumps(headers, ensure_ascii=True).encode('utf-8')
        result.update(status=response.status, headers_wait_ms=(headers_at - sent) / 1e6,
                      headers_bytes=len(encoded_headers), headers_sha256=hashlib.sha256(encoded_headers).hexdigest(),
                      headers_truncated=len(encoded_headers) > 65536)
        if result['headers_truncated']:
            raise ValueError('header-byte-budget')
        result['headers'] = headers
        while True:
            if time.perf_counter_ns() >= deadline:
                raise TimeoutError('whole-request-deadline')
            chunk = response.read1(min(65536, endpoint.max_body_bytes + 1 - len(raw)))
            raw.extend(chunk)
            if len(raw) > endpoint.max_body_bytes:
                raise ValueError('body-byte-budget')
            if not chunk:
                if response.length not in (None, 0):
                    raise http.client.IncompleteRead(b'', response.length)
                break
        received = time.perf_counter_ns()
        native_end = field_native_timing.capture() if include_native_timing else None
        result.update(body_complete=True, body_ms=(received - headers_at) / 1e6)
        if received > deadline:
            raise TimeoutError('whole-request-deadline')
        decoding = time.perf_counter_ns()
        try:
            if endpoint.kind == 'json':
                parsed = json.loads(raw, object_pairs_hook=_strict_object, parse_constant=_invalid_constant)
                if not isinstance(parsed, dict):
                    raise ValueError('JSON object required')
            else:
                with Image.open(io.BytesIO(raw)) as picture:
                    if picture.format != 'JPEG' or picture.width * picture.height > 16_777_216:
                        raise ValueError('JPEG format or pixel budget')
                    picture.load()
                    result['image'] = {'width': picture.width, 'height': picture.height}
            result['decode_complete'] = True
        finally:
            result['decode_ms'] = (time.perf_counter_ns() - decoding) / 1e6
    except Exception as error:
        if isinstance(error, http.client.IncompleteRead):
            raw.extend(error.partial)
        reason = str(error)
        result.update(timeout=isinstance(error, TimeoutError), error_type=type(error).__name__,
                      error_reason=reason[:2048], error_reason_truncated=len(reason) > 2048)
    finally:
        response_finished = received if received is not None else time.perf_counter_ns()
        if include_native_timing and native_end is None:
            native_end = field_native_timing.capture()
        if response is not None:
            response.close()
        connection.close()
    result.update(response_finished_ns=response_finished, finished_ns=time.perf_counter_ns(),
                  client_request_and_body_ms=(response_finished - started) / 1e6,
                  body_bytes=len(raw), body_sha256=hashlib.sha256(raw).hexdigest())
    result['native_timing'] = ({'begin': native_begin, 'end': native_end,
                               **field_native_timing.interval(native_begin, native_end)}
                              if include_native_timing else {'status': 'DISABLED'})
    if control_token is not None and (_contains_control_token(raw, control_token)
            or _contains_control_token(json.dumps(result, ensure_ascii=True).encode(), control_token)):
        # A credential echo is never persisted as raw evidence. Fail closed and
        # retain only the timing/status and the fact that content was withheld.
        raw = bytearray()
        result.update(headers=[], headers_bytes=0, headers_sha256=hashlib.sha256(b'').hexdigest(),
                      body_bytes=0, body_sha256=hashlib.sha256(b'').hexdigest(),
                      body_complete=False, decode_complete=False, sensitive_response_withheld=True,
                      error_type='SensitiveResponse', error_reason='control-token-echo-withheld')
    result['request_success'] = (result['status'] == 200 and result['body_complete']
                                 and result['decode_complete'] and result['error_type'] is None)
    return result, bytes(raw)


def summarize_channel(endpoint, records, expected_slots):
    """All attempts, including first failures and timeouts, contribute to timing."""
    _validate_endpoint(endpoint)
    if type(expected_slots) is not int or not 0 < expected_slots <= 50000:
        raise ValueError('Positive bounded slot count required')

    def numeric(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    attempted, covered = [], set()
    missed = cancelled = invalid = 0
    last_sequence = -1
    for record in records:
        if not isinstance(record, dict):
            invalid += 1
            continue
        sequence = record.get('sequence')
        valid = type(sequence) is int and 0 <= sequence < expected_slots
        valid = valid and sequence > last_sequence
        slots = set()
        if type(sequence) is int and 0 <= sequence < expected_slots:
            slots.add(sequence)
            last_sequence = sequence
        kind = record.get('kind')
        if kind == 'request':
            attempted.append(record)
            valid = valid and all(numeric(record.get(key)) for key in ('client_request_and_body_ms', 'start_lateness_ms'))
            valid = valid and all(type(record.get(key)) is bool for key in ('request_success', 'timeout'))
        elif kind == 'missed_slot':
            missed += 1
        elif kind == 'cancelled_remaining':
            remaining = record.get('remaining_slots')
            if slots and type(remaining) is int and remaining > 0 and sequence + remaining == expected_slots:
                slots = set(range(sequence, expected_slots))
                cancelled += remaining
            else:
                valid = False
        else:
            valid = False
            slots.clear()
        if slots & covered:
            valid = False
        covered.update(slots)
        invalid += not valid
    values = sorted(record['client_request_and_body_ms'] for record in attempted if numeric(record.get('client_request_and_body_ms')))

    def percentile(fraction):
        return values[max(0, math.ceil(len(values) * fraction) - 1)] if values else None

    failures = sum(record.get('request_success') is not True for record in attempted)
    threshold_failures = sum(value > endpoint.failure_ms for value in values) if endpoint.failure_ms is not None else None
    complete = len(covered) == expected_slots and missed == cancelled == invalid == 0
    first = attempted[0].get('client_request_and_body_ms') if attempted else None
    status = 'PASS' if complete and attempted and not failures and not threshold_failures else 'FAIL'
    if invalid or len(covered) != expected_slots:
        status = 'NOT_MEASURED'
    return {'expected_slots': expected_slots, 'requests': len(attempted), 'missed_slots': missed,
            'cancelled_slots': cancelled, 'unaccounted_slots': expected_slots - len(covered),
            'invalid_record_count': invalid,
            'schedule_complete': complete, 'request_errors': failures,
            'timeouts': sum(record.get('timeout') is True for record in attempted),
            'first_ms': first if numeric(first) else None,
            'max_ms': values[-1] if values else None, 'p50_ms': percentile(.5),
            'p95_ms': percentile(.95), 'p99_ms': percentile(.99),
            'max_start_lateness_ms': max((record['start_lateness_ms'] for record in attempted if numeric(record.get('start_lateness_ms'))), default=None),
            'warnings': sum(value > endpoint.warning_ms for value in values) if endpoint.warning_ms is not None else None,
            'failure_threshold_ms': endpoint.failure_ms, 'threshold_failures': threshold_failures,
            'http_component_status': status}


def _prepare_output(output):
    output = Path(output)
    if not output.is_absolute() or '..' in output.parts or len(str(output / 'image-00000.json')) > 240:
        raise ValueError('Absolute bounded output path required')
    for path in (output, *output.parents):
        if path.exists() or path.is_symlink():
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('Reparse output path')
    if not output.parent.is_dir():
        raise ValueError('Output parent must exist')
    output.mkdir(exist_ok=False)
    return output


def collect_http_window(port, output, *, duration_seconds, endpoints=ENDPOINTS,
                        timeout_seconds=5.0, stop_event=None, body_byte_budget=4 * 1024**3,
                        origin_ns=None, pending_byte_budget=64 * 1024**2, pending_record_budget=256,
                        include_native_timing=True, diagnostic_timing=False, _record_observer=None,
                        operational_assessment=False):
    """Collect a bounded component window. Caller owns installation/session binding."""
    if type(operational_assessment) is not bool:
        raise ValueError('Operational assessment must be explicit boolean')
    if operational_assessment and tuple(e.name for e in endpoints) != ('health', 'data'):
        raise ValueError('Operational observation uses health/data; images belong to the actual UI')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Loopback port required')
    if not math.isfinite(duration_seconds) or not 0 < duration_seconds <= 7200:
        raise ValueError('Duration must be in (0, 7200] seconds')
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
        raise ValueError('Invalid timeout')
    if type(body_byte_budget) is not int or body_byte_budget <= 0:
        raise ValueError('Positive body byte budget required')
    if type(pending_byte_budget) is not int or not 1 <= pending_byte_budget <= 256 * 1024**2:
        raise ValueError('Pending byte budget must be in [1, 256 MiB]')
    if type(pending_record_budget) is not int or not 1 <= pending_record_budget <= 4096:
        raise ValueError('Pending record budget must be in [1, 4096]')
    if type(include_native_timing) is not bool:
        raise ValueError('Native timing flag must be boolean')
    if type(diagnostic_timing) is not bool or (diagnostic_timing and not include_native_timing):
        raise ValueError('Diagnostic timing requires native timing')
    if _record_observer is not None and not callable(_record_observer):
        raise ValueError('Record observer must be callable')
    endpoints = tuple(endpoints)
    if not endpoints or len({endpoint.name for endpoint in endpoints}) != len(endpoints):
        raise ValueError('Nonempty unique endpoints required')
    for endpoint in endpoints:
        _validate_endpoint(endpoint)
    period = {e.name: round(e.interval_seconds * 1e9) for e in endpoints}
    duration = round(duration_seconds * 1e9)
    if duration <= 0 or any(value <= 0 for value in period.values()):
        raise ValueError('Sub-nanosecond interval or duration')
    counts = {name: (duration + value - 1) // value for name, value in period.items()}
    if sum(counts.values()) > 50000:
        raise ValueError('Sample count budget')
    origin = observation_origin(origin_ns)
    output = _prepare_output(output)
    stop = stop_event if stop_event is not None else threading.Event()
    lock = threading.Lock()
    files, rows, errors = {}, {e.name: [] for e in endpoints}, []
    progress = {e.name: [] for e in endpoints}
    write_timings = []
    body_bytes = 0
    pending = queue.Queue(maxsize=pending_record_budget)
    writer_failed = threading.Event()
    persistence_errors = []
    backlog = {'pending_bytes': 0, 'pending_records': 0, 'peak_pending_bytes': 0,
               'peak_pending_records': 0, 'submitted_records': 0, 'persisted_records': 0,
               'discarded_records': 0, 'byte_budget': pending_byte_budget, 'record_budget': pending_record_budget}

    def write_new(name, data):
        started = time.perf_counter_ns()
        created = False
        try:
            with (output / name).open('xb') as stream:
                created = True
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception as error:
            # Preserve a created partial file as failed evidence, never as a
            # persisted request. Do not claim ownership of a pre-existing file.
            if created:
                raw = (output / name).read_bytes()
                with lock:
                    files[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                                   'failed_write': True, 'expected_bytes': len(data),
                                   'error_type': type(error).__name__}
            raise
        finished = time.perf_counter_ns()
        with lock:
            files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            write_timings.append({'file': name, 'started_ns': started, 'finished_ns': finished,
                                  'file_persistence_ms': (finished - started) / 1e6})

    def write_json(name, record):
        write_new(name, (json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))

    def enqueue(name, record, body):
        record['queued_ns'] = time.perf_counter_ns()
        metadata = (json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        size = len(metadata) + (len(body) if body is not None else 0)
        timing = {'metadata_ready_ns': time.perf_counter_ns()} if diagnostic_timing else None
        with lock:
            if timing is not None:
                timing['lock_acquired_ns'] = time.perf_counter_ns()
            if writer_failed.is_set():
                raise RuntimeError('persistence-worker-failed')
            if backlog['pending_bytes'] + size > pending_byte_budget:
                raise ValueError('pending-byte-budget')
            if backlog['pending_records'] >= pending_record_budget:
                raise ValueError('pending-record-budget')
            pending.put_nowait((name, record, metadata, body, size))
            backlog['pending_bytes'] += size
            backlog['pending_records'] += 1
            backlog['submitted_records'] += 1
            for key in ('bytes', 'records'):
                backlog['peak_pending_' + key] = max(backlog['peak_pending_' + key], backlog['pending_' + key])
        if timing is not None:
            timing['enqueue_return_ns'] = time.perf_counter_ns()
        return timing, metadata

    def persist():
        while True:
            job = pending.get()
            if job is None:
                pending.task_done()
                return
            name, record, metadata, body, size = job
            saved = False
            try:
                if not writer_failed.is_set():
                    if body is not None:
                        write_new(record['body_file'], body)
                    write_new(f'{name}-{record["sequence"]:05d}.json', metadata)
                    rows[name].append(record)
                    saved = True
            except Exception as error:
                persistence_errors.append({'endpoint': name, 'sequence': record['sequence'],
                                           'error_type': type(error).__name__, 'reason': str(error)[:2048]})
                writer_failed.set()
                stop.set()
            finally:
                with lock:
                    backlog['pending_bytes'] -= size
                    backlog['pending_records'] -= 1
                    backlog['persisted_records' if saved else 'discarded_records'] += 1
                pending.task_done()

    # Allow workers to be ready before a shared first slot; no unrecorded HTTP warmup.
    write_json('origin.json', {'origin_ns': origin, 'recorded_utc': datetime.now(timezone.utc).isoformat(),
               'duration_ns': duration, 'period_ns': period, 'expected_slots': counts,
               'persistence_mode': 'BOUNDED_ASYNC_FSYNC_BEFORE_COMPLETION',
               'pending_byte_budget': pending_byte_budget, 'pending_record_budget': pending_record_budget,
               'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'native_timing_enabled': include_native_timing,
               'diagnostic_timing_enabled': diagnostic_timing,
               'scope': 'HTTP_COMPONENT_ONLY', 'field_gate': 'NOT_EVALUATED', 'release_gate': 'HOLD'})

    def worker(endpoint):
        nonlocal body_bytes
        name, step = endpoint.name, period[endpoint.name]
        previous_finished = None
        try:
            for sequence in range(counts[name]):
                target = origin + sequence * step
                turn = dict(sequence=sequence, scheduled_ns=target, loop_entered_ns=time.perf_counter_ns(),
                            previous_finished_ns=previous_finished) if diagnostic_timing else None
                body = None
                if stop.is_set():
                    record = {'kind': 'cancelled_remaining', 'sequence': sequence, 'scheduled_ns': target,
                              'remaining_slots': counts[name] - sequence}
                elif previous_finished is not None and previous_finished >= target:
                    record = {'kind': 'missed_slot', 'sequence': sequence, 'scheduled_ns': target,
                              'reason': 'previous-request-decode-or-enqueue-overrun'}
                elif stop.wait(max(0, (target - time.perf_counter_ns()) / 1e9)):
                    record = {'kind': 'cancelled_remaining', 'sequence': sequence, 'scheduled_ns': target,
                              'remaining_slots': counts[name] - sequence}
                elif time.perf_counter_ns() >= target + step:
                    record = {'kind': 'missed_slot', 'sequence': sequence, 'scheduled_ns': target,
                              'reason': 'scheduler-missed-entire-slot'}
                else:
                    options = {'health_probe_id': uuid4().hex} if diagnostic_timing and name == 'health' else {}
                    record, body = fetch_sample(port, endpoint, timeout_seconds=timeout_seconds,
                                               include_native_timing=include_native_timing, **options)
                    record.update(sequence=sequence, scheduled_ns=target,
                                  start_lateness_ms=(record['started_ns'] - target) / 1e6,
                                  body_file=f'{name}-{sequence:05d}.body')
                    with lock:
                        if body_bytes + len(body) > body_byte_budget:
                            raise ValueError('window-body-byte-budget')
                        body_bytes += len(body)
                enqueued, metadata = enqueue(name, record, body)
                turn_finished = time.perf_counter_ns()
                if record['kind'] == 'request':
                    previous_finished = turn_finished
                if _record_observer is not None:
                    _record_observer(endpoint, metadata, turn_finished)
                if turn is not None:
                    turn.update(kind=record['kind'], queued_ns=record['queued_ns'], **enqueued,
                                worker_turn_finished_ns=time.perf_counter_ns())
                    progress[name].append(turn)
                if record['kind'] == 'cancelled_remaining':
                    break
        except Exception as error:
            with lock:
                errors.append({'endpoint': name, 'error_type': type(error).__name__, 'reason': str(error)})
            stop.set()

    writer = threading.Thread(target=persist, name='field-http-persistence')
    writer.start()
    try:
        with ThreadPoolExecutor(max_workers=len(endpoints), thread_name_prefix='field-http') as executor:
            futures = [executor.submit(worker, endpoint) for endpoint in endpoints]
            for future in futures:
                future.result()
    finally:
        capture_finished = time.perf_counter_ns()
        pending.put(None)
        pending.join()
        writer.join()
    persistence_finished = time.perf_counter_ns()
    # Finish the planned observation interval even when its final request ended early.
    stop.wait(max(0, (origin + duration - time.perf_counter_ns()) / 1e9))
    # Preserve open/write/flush/fsync/close wall time separately from network latency.
    # The trace covers origin and request files, not its own finalization writes.
    observed_writes = list(write_timings)
    write_json('writes.json', {'scope': 'ORIGIN_AND_REQUEST_FILES', 'writes': observed_writes})
    summary = {'scope': 'HTTP_COMPONENT_ONLY', 'origin_ns': origin, 'finished_ns': time.perf_counter_ns(),
               'duration_ns': duration, 'body_bytes': body_bytes, 'worker_errors': errors,
               'capture_finished_ns': capture_finished, 'persistence_finished_ns': persistence_finished,
               'persistence_drain_ms': (persistence_finished - capture_finished) / 1e6,
               'persistence': dict(backlog), 'persistence_errors': persistence_errors,
               'stop_requested': stop.is_set(), 'channels': {
                   e.name: summarize_channel(e, rows[e.name], counts[e.name]) for e in endpoints},
               'file_persistence_max_ms': max((r['file_persistence_ms'] for r in observed_writes), default=None),
               'field_gate': 'NOT_EVALUATED', 'release_gate': 'HOLD', 'promotion_allowed': False}
    requests = [r for channel in rows.values() for r in channel if r['kind'] == 'request']
    linked = sum(r.get('native_timing', {}).get('status') == 'CORRELATABLE_BOUNDARIES' for r in requests)
    summary['native_timing'] = {'enabled': include_native_timing, 'requests': len(requests),
                               'correlatable_requests': linked,
                               'status': ('DISABLED' if not include_native_timing else
                                          'COMPLETE' if requests and linked == len(requests) else 'INCOMPLETE'),
                               'server_or_scheduling_cause_established': False}
    summary['http_component_status'] = 'PASS' if not errors and not persistence_errors and not stop.is_set() and all(
        row['http_component_status'] == 'PASS' for row in summary['channels'].values()) else 'FAIL'
    if operational_assessment:
        from field_operational_assessment import assess_channel, combine
        summary['legacy_http_component_status'] = summary['http_component_status']
        summary['operational_assessment'] = combine({
            e.name: assess_channel(e, rows[e.name], counts[e.name],
                                   legacy_summary=summary['channels'][e.name]) for e in endpoints
        }, collector_errors=bool(errors or persistence_errors or stop.is_set()))
        summary['http_component_status'] = summary['operational_assessment']['collection_status']
        summary['scope'] = 'OPERATIONAL_HTTP_EVIDENCE_NO_SYNTHETIC_IMAGE_REQUESTS'
    if diagnostic_timing:
        write_json('progress.json', dict(schema='sfl-http-worker-progress-v1', channels=progress,
            scope='WALL_CLOCK_BOUNDARIES_NOT_LOCK_OR_SCHEDULER_CAUSATION', release_gate='HOLD', promotion_allowed=False))
    write_json('summary.json', summary)
    write_json('manifest.json', {'schema_version': 'sfl-field-http-component-v1', 'files': dict(files)})
    return summary


def observation_origin(origin_ns=None):
    """Accept a common, future monotonic origin before any output is created."""
    now = time.perf_counter_ns()
    if origin_ns is None:
        return now + 100_000_000
    if type(origin_ns) is not int or not now < origin_ns <= now + 30_000_000_000:
        raise ValueError('Shared origin must be an integer within the next 30 seconds')
    return origin_ns
