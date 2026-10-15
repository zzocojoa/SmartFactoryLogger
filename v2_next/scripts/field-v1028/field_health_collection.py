"""Bounded read-only 1.0.29 diagnostic collection, not a field QA entrypoint.

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
import field_generation_binding as generation
import field_health_diagnostic as diagnostic
import field_installation_binding as binding
import field_observation as observation
from field_host_sampling import WindowsProcessReader


@dataclass(frozen=True)
class HealthCollectionSpec(observation.ObservationSpec):
    backend_created_filetime: int = 0

    def validate(self):
        super().validate()
        binding.require(type(self.backend_created_filetime) is int
                        and 0 < self.backend_created_filetime < 2**64,
                        'external-backend-native-generation-required')


def validate_duration(duration):
    binding.require(type(duration) in (int, float) and math.isfinite(duration)
                    and 0 < duration <= 30, 'diagnostic-duration-budget')


def collect(spec, output, duration, stop, notify):
    """Run only inside the owned worker; the supervisor bounds blocking calls."""
    spec.validate()
    validate_duration(duration)
    folder = observation.http._prepare_output(Path(output) / 'evidence')
    files = {}
    result = dict(schema='sfl-health-collection-v1', collection_status='INCOMPLETE',
                  observation_status='FAIL', errors=[], samples=[],
                  field_gate='NOT_EVALUATED', etw_coverage='NOT_EVALUATED',
                  release_gate='HOLD', promotion_allowed=False,
                  started_ns=time.perf_counter_ns(), duration_seconds=duration,
                  scope='READ_ONLY_BOUND_REQUESTS_NOT_FIELD_PERFORMANCE')

    def save(name, value):
        files[name] = observation.write_json(folder / name, value)

    def require_running():
        binding.require(not stop.is_set(), 'diagnostic-stop-requested')

    try:
        require_running()
        with binding.InstalledPayload(spec.root, spec.reference,
                expected_reference_sha256=spec.reference_sha256, extras=spec.extras,
                candidate=binding.CANDIDATE_1029) as payload, \
                configuration.configuration_reference(spec.configuration_reference,
                    spec.configuration_reference_sha256, candidate=binding.CANDIDATE_1029) as expected:
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
            origin = time.perf_counter_ns() + 250_000_000
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
            if stop.wait(max(0, (origin + round(duration * 1e9) - time.perf_counter_ns()) / 1e9)):
                raise InterruptedError('diagnostic-stop-requested')
            notify(dict(phase='finalizing', origin_ns=origin))
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
        result['errors'].append(dict(type=type(error).__name__,
            reason=str(error) if type(error) in (ValueError, InterruptedError) else 'diagnostic-collection-failed'))
        stop.set()
    result.update(stop_requested=stop.is_set(), finished_ns=time.perf_counter_ns())
    save('summary.json', result)
    observation.write_json(folder / 'manifest.json', dict(files=files))
    result['evidence_manifest'] = observation.verify_component_manifest(folder, 32)
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
