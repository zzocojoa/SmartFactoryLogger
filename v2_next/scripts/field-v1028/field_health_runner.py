"""Frozen six-second 1.0.29 health/trace collector for the protected launcher.

Inputs must already be archived by the launcher. This child owns only collection
workers; the independent administrator coordinator owns its unique WPR session.
PASS means capture completed, never field performance or release approval.
"""
import argparse
from contextlib import ExitStack
from dataclasses import fields
import json
import multiprocessing
import os
from pathlib import Path
import sys
from uuid import uuid4

import field_health_collection as collection
import field_health_trace as trace
import field_installation_binding as binding
import field_observation as observation
from field_resource_sampling import ProcessIdentity, error_record


SCHEMA = 'sfl-health-diagnostic-request-v1'
PAYLOAD_SHA256 = '658b096408ddb82022c53f9802c1300e6da7ca7cfbd077a60db4efc07935fe69'


def validate_request(value):
    binding.require(isinstance(value, dict) and set(value) == {
        'schema', 'candidate_commit', 'signature_policy', 'duration_seconds', 'spec'}, 'health-request-members')
    binding.require(value['schema'] == SCHEMA
                    and value['candidate_commit'] == binding.CANDIDATE_1029.commit
                    and value['signature_policy'] == 'UNSIGNED_INTERNAL', 'health-request-identity-policy')
    binding.require(type(value['duration_seconds']) is int and value['duration_seconds'] == 6,
                    'health-request-fixed-six-seconds')
    data = value['spec']
    binding.require(isinstance(data, dict) and set(data) == {f.name for f in fields(collection.HealthCollectionSpec)},
                    'health-request-spec-members')
    binding.require(data['reference_sha256'] == PAYLOAD_SHA256
                    and trace.digest(data['configuration_reference_sha256']), 'health-request-reference-pins')
    for role in ('main', 'backend'):
        binding.require(isinstance(data[role], dict)
                        and set(data[role]) == {f.name for f in fields(ProcessIdentity)}, 'health-request-process-fields')
    binding.require(type(data['backend_created_filetime']) is int and 0 < data['backend_created_filetime'] < 2**64,
                    'health-request-native-generation')
    return data


def archived_spec(request, output_root):
    """Only the installed app path remains external; references use archived bytes."""
    data = dict(validate_request(request))
    installed = binding.plain_path(data['root'])
    binding.require(installed != output_root and installed not in output_root.parents
                    and output_root not in installed.parents, 'health-output-installation-boundary')
    data['reference'] = str(output_root/'inputs/candidate-payload.json')
    data['configuration_reference'] = str(output_root/'inputs/configuration.json')
    for role in ('main', 'backend'):
        data[role] = ProcessIdentity(**data[role])
    spec = collection.HealthCollectionSpec(**data)
    spec.validate()
    return spec


def run(output_root, request_sha256, trace_package_sha256):
    binding.require(trace.digest(request_sha256) and trace.digest(trace_package_sha256), 'health-external-pins')
    root = binding.plain_path(output_root)
    binding.require(root.is_dir() and len(str(root/'session/collection/evidence/configuration-initial.json')) <= 240,
                    'health-session-path-budget')
    session = root/'session'
    binding.require(not session.exists(), 'health-session-already-exists')
    session.mkdir()
    result = dict(schema='sfl-field-run-result-v1', mode='health-trace', status='FAIL', errors=[],
        request_sha256=request_sha256, trace_package_sha256=trace_package_sha256,
        frozen=bool(getattr(sys, 'frozen', False)), scope='SIX_SECOND_CAPTURE_NOT_FIELD_PERFORMANCE',
        field_gate='NOT_EVALUATED', trace_quality='NOT_EVALUATED', full_data_gate='NOT_EVALUATED',
        release_gate='HOLD', promotion_allowed=False, installation_performed=False, application_shutdown_performed=False)
    try:
        with ExitStack() as locks:
            archived = {}

            def hold(name, expected, budget):
                stream = locks.enter_context(binding.locked_read(root/'inputs'/name))
                binding.require(0 < os.fstat(stream.fileno()).st_size <= budget, 'health-input-budget:'+name)
                fact = binding.stream_fact(stream)
                binding.require(fact['sha256'] == expected, 'health-archived-input-pin:'+name)
                archived[name] = (stream, fact)
                stream.seek(0)
                return binding.strict_json(stream.read())

            request = hold('request.json', request_sha256, 65536)
            data = validate_request(request)
            hold('candidate-payload.json', PAYLOAD_SHA256, 1024**2)
            hold('configuration.json', data['configuration_reference_sha256'], 1024**2)
            hold('trace/manifest.json', trace_package_sha256, 65536)
            spec = archived_spec(request, root)
            result['archived_inputs'] = {name: fact for name, (_, fact) in archived.items()}
            channel = session/'trace-channel'
            channel.mkdir()
            contract = dict(schema='sfl-health-trace-contract-v1', scope=trace.SCOPE, run_id=uuid4().hex,
                channel_path=str(channel), package_sha256=trace_package_sha256, backend_pid=spec.backend.pid,
                backend_created_filetime=spec.backend_created_filetime, main_pid=spec.main.pid,
                duration_seconds=6, guard_seconds=30, release_gate='HOLD', promotion_allowed=False)
            fact = observation.write_json(channel/'contract.json', contract)
            selected = trace.TracedHealthCollectionSpec(**{f.name: getattr(spec, f.name) for f in fields(spec)},
                trace_contract_path=str(channel/'contract.json'), trace_contract_sha256=fact['sha256'])
            result['phase'] = trace.supervise(selected, session/'collection')
            binding.require(result['phase'].get('release_gate') == 'HOLD'
                            and result['phase'].get('promotion_allowed') is False, 'health-phase-gates')
            for name, (stream, expected) in archived.items():
                binding.require(binding.stream_fact(stream) == expected, 'health-input-closeout:'+name)
            if result['phase']['supervisor_status'] == 'PASS':
                result['status'] = 'PASS'
    except Exception as error:
        result['errors'].append(error_record(error))
    observation.write_json(session/'result.json', result)
    # The coordinator can still publish a terminal channel message. Only the
    # outer launcher seals the complete tree after BOTH writers have exited.
    return dict(status=result['status'], result_path=str(session),
        request_sha256=request_sha256, release_gate='HOLD', promotion_allowed=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe', action='store_true')
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--request-sha256')
    parser.add_argument('--trace-package-sha256')
    args = parser.parse_args(argv)
    try:
        supplied = (args.output_root, args.request_sha256, args.trace_package_sha256)
        if args.describe:
            binding.require(not any(supplied), 'health-describe-with-run-arguments')
            print(json.dumps(dict(schema=SCHEMA, candidate_commit=binding.CANDIDATE_1029.commit,
                frozen=bool(getattr(sys, 'frozen', False)), signature_policy='UNSIGNED_INTERNAL', duration_seconds=6,
                release_gate='HOLD', promotion_allowed=False)))
            return 0
        binding.require(all(supplied), 'health-all-run-arguments-required')
        result = run(args.output_root, args.request_sha256, args.trace_package_sha256)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['status'] == 'PASS' else 1
    except Exception as error:
        print(json.dumps(dict(status='FAIL', error=error_record(error), release_gate='HOLD', promotion_allowed=False)))
        return 1


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
