"""Bind one opt-in health request to an externally verified 1.0.29 runtime.

This read-only component neither controls the app nor starts WPR. Its caller
must hold the payload, configuration and authenticated generation boundaries,
own the collector deadline, and preserve raw results for same-run ETW review.
A bound slow request remains evidence; it is never a field-performance PASS.
"""
import os
import re
import time

import field_health_timing as timing
import field_http_sampling as http
import field_installation_binding as binding
from field_host_sampling import WindowsProcessReader


def require_native(value, backend, expected_created):
    binding.require(type(value) is dict and value.get('status') == 'CAPTURED'
                    and type(value.get('pid')) is int and value['pid'] == backend.pid
                    and type(value.get('created_100ns')) is int
                    and value['created_100ns'] == expected_created,
                    'backend-native-generation-changed-or-unavailable')


def capture_health_probe(payload, main, backend, port, *, expected_created_filetime,
                         expected_sessions, probe_id):
    """Return raw HTTP/native facts even when a post-request guard rejects them."""
    result = dict(schema='sfl-bound-health-probe-v1', status='NOT_BOUND',
                  started_ns=time.perf_counter_ns(), errors=[],
                  field_gate='NOT_EVALUATED', etw_coverage='NOT_EVALUATED',
                  release_gate='HOLD', promotion_allowed=False)
    try:
        binding.require(payload.active and payload.candidate == binding.CANDIDATE_1029,
                        'active-health-candidate-required')
        binding.require(type(probe_id) is str and re.fullmatch('[0-9a-f]{32}', probe_id),
                        'diagnostic-probe-id')
        binding.require(type(expected_created_filetime) is int
                        and 0 < expected_created_filetime < 2**64, 'external-native-generation-required')
        binding.require(type(expected_sessions) is dict
                        and set(expected_sessions) == {'spot_service_instance_id', 'logger_service_instance_id'},
                        'external-runtime-sessions-required')
        # This also validates exact process paths against the locked installation.
        binding.require(main.exe == os.path.normcase(str(payload.root / 'smart-factory.exe'))
                        and backend.exe == os.path.normcase(str(payload.root / binding.BACKEND)),
                        'installed-process-path')
        result.update(probe_id=probe_id, expected_backend_created_filetime=expected_created_filetime,
                      expected_sessions=dict(expected_sessions), payload=payload.receipt)
        result['process_before'] = binding.read_process_binding(main, backend, port)
        reader = WindowsProcessReader()
        result['native_before'] = reader.read(backend.pid)
        require_native(result['native_before'], backend, expected_created_filetime)
        record, raw = http.fetch_sample(port, http.ENDPOINTS[0], health_probe_id=probe_id)
        result.update(health_record=record, health_body_hex=raw.hex())
        result['native_after'] = reader.read(backend.pid)
        require_native(result['native_after'], backend, expected_created_filetime)
        result['process_after'] = binding.read_process_binding(main, backend, port)
        binding.require(result['process_before'] == result['process_after'], 'runtime-process-binding-changed')
        result['validation'] = timing.validate_health_sample(record, raw, probe_id=probe_id,
            backend_pid=backend.pid, backend_created_filetime=expected_created_filetime)
        binding.require(result['validation']['status'] == 'REQUEST_AND_NATIVE_CLOCK_BOUND',
                        'health-request-native-clock-not-bound')
        result['sessions'] = binding.runtime_sessions(binding.strict_json(raw), backend,
                                                      candidate=payload.candidate)
        binding.require(result['sessions'] == expected_sessions, 'runtime-service-generation-changed')
        result['status'] = 'REQUEST_AND_RUNTIME_BOUND'
    except Exception as error:
        # No environment or control credentials are accessed by this component.
        result['errors'].append({'type': type(error).__name__,
                                 'reason': str(error) if type(error) is ValueError else 'probe-capture-failed'})
    result['finished_ns'] = time.perf_counter_ns()
    return result
