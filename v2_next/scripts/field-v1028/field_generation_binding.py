"""Authenticated control-health identity of the already validated installed backend.

Only the selected backend's embedded token/generation environment values are used.
No environment, request headers or token are returned or written. Application
control is limited to GET /api/control/health on its verified loopback listener.
"""
from datetime import datetime, timezone
import os
import re
import time

import psutil

import field_http_sampling as http
import field_installation_binding as binding


def control_identity(value, backend, expected_generation):
    binding.require(isinstance(value, dict) and value.get('running') is True, 'control-not-running')
    binding.require(type(value.get('backend_process_id')) is int
                    and value['backend_process_id'] == backend.pid, 'control-process-mismatch')
    generation = value.get('backend_generation_id')
    session = value.get('backend_session_id')
    binding.require(isinstance(generation, str) and re.fullmatch('[0-9a-f]{32}', generation)
                    and generation == expected_generation, 'control-generation-mismatch')
    # Actual app.py uses uuid.uuid4().hex[:12], not a canonical UUID.
    binding.require(isinstance(session, str) and re.fullmatch('[0-9a-f]{12}', session), 'control-session-format')
    started = value.get('started_at')
    binding.require(isinstance(started, str) and len(started) <= 40, 'control-started-format')
    timestamp = datetime.fromisoformat(started.replace('Z', '+00:00'))
    binding.require(timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() == 0
                    and backend.created - 1 <= timestamp.timestamp() <= time.time() + 2, 'control-started-range')
    return dict(backend_process_id=backend.pid, backend_generation_id=generation,
                backend_session_id=session, started_at=started)


def capture_generation(payload, main, backend, port, *, expected_identity=None, enforce_legacy_latency=True):
    binding.require(type(enforce_legacy_latency) is bool, 'control-latency-policy')
    result = dict(generation_status='FAIL', started_ns=time.perf_counter_ns(),
                  observed_at=datetime.now(timezone.utc).isoformat(), errors=[],
                  field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)
    token = None
    try:
        binding.require(payload.active, 'payload-context-not-active')
        binding.require(main.exe == os.path.normcase(str(payload.root / 'smart-factory.exe'))
                        and backend.exe == os.path.normcase(str(payload.root / binding.BACKEND)),
                        'installed-process-path')
        result['process_before'] = binding.read_process_binding(main, backend, port)
        environment = psutil.Process(backend.pid).environ()
        token = environment.get('SFL_CONTROL_TOKEN')
        generation = environment.get('SFL_BACKEND_GENERATION_ID')
        embedded = environment.get('SFL_EMBEDDED_ELECTRON')
        del environment
        binding.require(embedded == '1' and isinstance(token, str) and re.fullmatch('[0-9a-f]{64}', token)
                        and isinstance(generation, str) and re.fullmatch('[0-9a-f]{32}', generation),
                        'embedded-environment-contract')
        result['process_after_environment'] = binding.read_process_binding(main, backend, port)
        binding.require(result['process_after_environment'] == result['process_before'], 'control-process-changed')
        record, raw = http.fetch_sample(port, http.CONTROL_HEALTH, control_token=token)
        result.update(control_record=record, control_body_hex=raw.hex())
        binding.require(record['request_success'], 'control-request-failed')
        result['identity'] = control_identity(binding.strict_json(raw), backend, generation)
        result['process_after'] = binding.read_process_binding(main, backend, port)
        binding.require(result['process_after'] == result['process_before'], 'control-process-changed')
        if expected_identity is not None:
            binding.require(result['identity'] == expected_identity, 'control-session-changed')
        if enforce_legacy_latency:
            binding.require(record['client_request_and_body_ms'] <= 200, 'control-health-latency')
        else:
            result['latency_policy'] = 'DIAGNOSTIC_REFERENCE_ONLY'
            result['over_200ms'] = record['client_request_and_body_ms'] > 200
        result['generation_status'] = 'PASS'
    except Exception as error:
        # Environment/provider exceptions can contain sensitive strings. This
        # boundary intentionally records the type only, never exception text.
        result['errors'].append(dict(type=type(error).__name__, reason='control-binding-failed'))
    finally:
        token = None  # Release this reference; no memory-erasure claim.
    result['finished_ns'] = time.perf_counter_ns()
    return result
