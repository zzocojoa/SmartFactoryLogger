"""Bounded read-only candidate diagnostic collection, not a field QA entrypoint.

The existing supervisor owns only a gated collector process. Neither this module
nor its worker controls the application or WPR. A protected outer launcher and
same-run ETW handshake/coverage review are still required for field use.
"""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sys
import time
from uuid import uuid4

import field_configuration_binding as configuration
from field_concurrent_api_load import ConcurrentApiLoad
import field_generation_binding as generation
import field_health_diagnostic as diagnostic
import field_installation_binding as binding
import field_observation as observation
from field_host_sampling import WindowsProcessReader


HEALTH_CANDIDATES = diagnostic.HEALTH_CANDIDATES


@dataclass(frozen=True)
class HealthCollectionSpec(observation.ObservationSpec):
    candidate_commit: str = binding.CANDIDATE_1029.commit
    backend_created_filetime: int = 0

    def validate(self):
        super().validate()
        binding.require(self.candidate in HEALTH_CANDIDATES, 'diagnostic-candidate-required')
        binding.require(type(self.backend_created_filetime) is int
                        and 0 < self.backend_created_filetime < 2**64,
                        'external-backend-native-generation-required')


def validate_duration(duration):
    binding.require(type(duration) in (int, float) and math.isfinite(duration)
                    and 0 < duration <= 30, 'diagnostic-duration-budget')


def collect(spec, output, duration, stop, notify, *, _trace=None, _outlier=False, _concurrent_api=False):
    """Run only inside the owned worker; the supervisor bounds blocking calls."""
    spec.validate()
    if _outlier:
        binding.require(type(_outlier) is bool and type(duration) is int and duration == 900
                        and _trace is not None, 'outlier-fixed-bounded-trace-required')
    else:
        validate_duration(duration)
    binding.require(type(_concurrent_api) is bool and (not _concurrent_api or _outlier),
                    'concurrent-api-requires-bounded-outlier-trace')
    folder = observation.http._prepare_output(Path(output) / 'evidence')
    files = {}
    result = dict(schema='sfl-health-collection-v1', collection_status='INCOMPLETE',
                  observation_status='FAIL', errors=[], samples=[],
                  field_gate='NOT_EVALUATED', etw_coverage='NOT_EVALUATED',
                  release_gate='HOLD', promotion_allowed=False,
                  started_ns=time.perf_counter_ns(), duration_seconds=duration,
                  scope='READ_ONLY_BOUND_REQUESTS_NOT_FIELD_PERFORMANCE')
    if _outlier:
        result.update(scope='OUTLIER_CAPTURE_NOT_FIELD_PERFORMANCE', trigger_status='NOT_EVALUATED',
                      trigger_threshold_ms=200, trigger=None)
    if _concurrent_api:
        result.update(scope='CPU_CONCURRENT_CAPTURE_NOT_FIELD_PERFORMANCE', concurrent_api=True)
    companion = None
    companion_finished = False

    def finish_companion():
        nonlocal companion_finished
        # finish owns its bounded cleanup even if result publication raises.
        companion_finished = True
        receipt = companion.finish()
        save('concurrent-api-closeout.json', receipt)
        binding.require(receipt['load_status'] == 'CAPTURE_COMPLETE', 'concurrent-api-capture-incomplete')

    def save(name, value):
        files[name] = observation.write_json(folder / name, value)

    def require_running():
        binding.require(not stop.is_set(), 'diagnostic-stop-requested')

    try:
        require_running()
        with binding.InstalledPayload(spec.root, spec.reference,
                expected_reference_sha256=spec.reference_sha256, extras=spec.extras,
                candidate=spec.candidate) as payload, \
                configuration.configuration_reference(spec.configuration_reference,
                    spec.configuration_reference_sha256, candidate=spec.candidate) as expected:
            result.update(configuration.scope_fields(expected))
            native = WindowsProcessReader().read(spec.backend.pid)
            save('native-initial.json', native)
            diagnostic.require_native(native, spec.backend, spec.backend_created_filetime)
            initial = binding.capture_runtime_binding(payload, spec.main, spec.backend, spec.port)
            save('runtime-initial.json', initial)
            binding.require(initial['binding_status'] == 'PASS', 'initial-runtime-binding')
            sessions = initial['sessions']
            initial_control = generation.capture_generation(payload, spec.main, spec.backend, spec.port)
            save('control-initial.json', initial_control)
            binding.require(initial_control['generation_status'] == 'PASS', 'initial-control-binding')
            initial_configuration = configuration.capture_configuration(
                payload, spec.main, spec.backend, spec.port, sessions, expected)
            save('configuration-initial.json', initial_configuration)
            binding.require(initial_configuration['configuration_status'] == 'PASS', 'initial-configuration-binding')
            require_running()
            if _trace is not None:
                save('trace-binding.json', _trace.begin(dict(files), stop))
            origin = time.perf_counter_ns() + (3_000_000_000 if _concurrent_api else 250_000_000)
            if _concurrent_api:
                companion = ConcurrentApiLoad(spec.port, Path(output)/'concurrent-api',
                    duration_seconds=duration, origin_ns=origin)
                save('concurrent-api-started.json', dict(origin_ns=origin,
                    started=observation.file_fact(Path(output)/'concurrent-api/started.json')))
            expected_slots = math.ceil(duration / 2)
            result.update(origin_ns=origin, expected_slots=expected_slots, sessions=sessions)
            save('collection.json', dict(spec=asdict(spec), origin_ns=origin,
                duration_seconds=duration, interval_seconds=2, expected_slots=expected_slots,
                scope=result['scope']))
            notify(dict(phase='observing', origin_ns=origin))
            previous_finish = None
            for index in range(expected_slots):
                target = origin + index * 2_000_000_000
                if stop.wait(max(0, (target - time.perf_counter_ns()) / 1e9)):
                    raise InterruptedError('diagnostic-stop-requested')
                binding.require(previous_finish is None or previous_finish < target, 'diagnostic-slot-overrun')
                binding.require(time.perf_counter_ns() < target + 2_000_000_000, 'diagnostic-slot-missed')
                sample = diagnostic.capture_health_probe(payload, spec.main, spec.backend, spec.port,
                    expected_created_filetime=spec.backend_created_filetime,
                    expected_sessions=sessions, probe_id=uuid4().hex)
                sample.update(sequence=index, scheduled_ns=target)
                name = f'probe-{index:03d}.json'
                save(name, sample)
                result['samples'].append(dict(file=name, status=sample['status'], probe_id=sample.get('probe_id')))
                binding.require(sample['status'] == 'REQUEST_AND_RUNTIME_BOUND', 'diagnostic-request-not-bound')
                previous_finish = time.perf_counter_ns()
                if _outlier and sample['health_record']['client_request_and_body_ms'] > 200:
                    result.update(trigger_status='OUTLIER_CAPTURED_REQUIRES_CORRELATION',
                        trigger=dict(sequence=index, file=name, probe_id=sample['probe_id'],
                            client_request_and_body_ms=sample['health_record']['client_request_and_body_ms'],
                            response_finished_ns=sample['health_record']['response_finished_ns'],
                            decision_ns=previous_finish))
                    break
            triggered = _outlier and result['trigger'] is not None
            if companion is not None and triggered:
                companion.request_stop()
            if not triggered and stop.wait(max(0, (origin + round(duration * 1e9) - time.perf_counter_ns()) / 1e9)):
                raise InterruptedError('diagnostic-stop-requested')
            if _outlier:
                if not triggered:
                    result['trigger_status'] = 'NO_OUTLIER_OBSERVED'
                save('trigger.json', dict(status=result['trigger_status'], threshold_ms=200,
                    trigger=result['trigger'], probes=len(result['samples']), expected_slots=expected_slots,
                    origin_ns=origin, finished_ns=time.perf_counter_ns(),
                    release_gate='HOLD', promotion_allowed=False))
            notify(dict(phase='finalizing', origin_ns=origin))
            if _trace is not None:
                save('trace-completion.json', _trace.finish(dict(files), stop))
            if companion is not None:
                finish_companion()
            final_control = generation.capture_generation(payload, spec.main, spec.backend, spec.port,
                expected_identity=initial_control['identity'])
            save('control-final.json', final_control)
            binding.require(final_control['generation_status'] == 'PASS', 'final-control-binding')
            final_configuration = configuration.capture_configuration(
                payload, spec.main, spec.backend, spec.port, sessions, expected)
            save('configuration-final.json', final_configuration)
            binding.require(final_configuration['configuration_status'] == 'PASS', 'final-configuration-binding')
            final = binding.capture_runtime_binding(payload, spec.main, spec.backend, spec.port,
                                                    expected_sessions=sessions)
            save('runtime-final.json', final)
            binding.require(final['binding_status'] == 'PASS', 'final-runtime-binding')
            native = WindowsProcessReader().read(spec.backend.pid)
            save('native-final.json', native)
            diagnostic.require_native(native, spec.backend, spec.backend_created_filetime)
            save('payload-closeout.json', payload.recheck())
        require_running()  # Includes successful reference/context closeout above.
        result['collection_status'] = 'BOUND_WINDOW_CAPTURED'
        # Existing owned-worker IPC field: PASS means collector completion only.
        result['observation_status'] = 'PASS'
    except Exception as error:
        if companion is not None and not companion_finished:
            try:
                companion.request_stop()
            except Exception as stop_error:
                result['errors'].append(dict(type=type(stop_error).__name__, reason='concurrent-api-stop-failed'))
        if _trace is not None:
            try:
                _trace.abort(type(error).__name__)
            except Exception as publication_error:
                result['errors'].append(dict(type=type(publication_error).__name__, reason='trace-abort-publication-failed'))
        if companion is not None and not companion_finished:
            try:
                finish_companion()
            except Exception as close_error:
                result['errors'].append(dict(type=type(close_error).__name__, reason='concurrent-api-closeout-failed'))
        result['errors'].append(dict(type=type(error).__name__,
            reason=str(error) if type(error) in (ValueError, InterruptedError) else 'diagnostic-collection-failed'))
        stop.set()
    result.update(stop_requested=stop.is_set(), finished_ns=time.perf_counter_ns())
    save('summary.json', result)
    observation.write_json(folder / 'manifest.json', dict(files=files))
    result['evidence_manifest'] = observation.verify_component_manifest(folder, 512 if _outlier else 32)
    return result


def _worker_entry(spec, output, duration, stop, sender):
    exit_code = 1
    try:
        with (Path(output) / 'worker.stdout.log').open('x', encoding='utf-8') as stdout, \
                (Path(output) / 'worker.stderr.log').open('x', encoding='utf-8') as stderr:
            sys.stdout, sys.stderr = stdout, stderr
            local_stop = observation.ObservationStop(stop)
            try:
                result = collect(spec, output, duration, local_stop,
                                 lambda item: sender.send_bytes(json.dumps(item).encode()))
            finally:
                local_stop.close()
            fact = observation.write_json(Path(output) / 'worker-result.json', result)
            sender.send_bytes(json.dumps(dict(phase='done', result=fact)).encode())
            exit_code = 0 if result['collection_status'] == 'BOUND_WINDOW_CAPTURED' else 1
    finally:
        sender.close()
    raise SystemExit(exit_code)


def supervise(spec, output, *, duration_seconds=6, preparation_timeout=180,
              finalization_timeout=180, stop_event=None):
    binding.require(type(spec) is HealthCollectionSpec, 'diagnostic-spec-type')
    spec.validate()
    validate_duration(duration_seconds)
    return observation.supervise_observation(spec, output, duration_seconds=duration_seconds,
        preparation_timeout=preparation_timeout, finalization_timeout=finalization_timeout,
        stop_event=stop_event, _worker_target=_worker_entry)
