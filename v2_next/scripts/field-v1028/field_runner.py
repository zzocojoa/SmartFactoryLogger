"""Hash-bound entrypoint for field observation and closed-copy checks; never release approval."""
import argparse
from dataclasses import fields
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys

import field_closed_data_qa as qa
import field_csv_inputs as inputs
import field_installation_binding as binding
import field_observation as observation
import field_host_diagnostic as host_diagnostic
from field_resource_sampling import ProcessIdentity, error_record


SCHEMA = 'sfl-field-run-request-v1'
COMMON = {'schema', 'mode', 'candidate_commit', 'signature_policy'}
MODE_FIELDS = {
    'observe': {'spec', 'duration_seconds'},
    'host-diagnostic': {'spec', 'duration_seconds'},
    'closed-data': {'data_root', 'roles', 'expected_files', 'image_files', 'shutdown_expectation',
                    'configuration_reference', 'configuration_reference_sha256', 'validator_timeout_seconds'},
}


def validate_request(value):
    binding.require(isinstance(value, dict) and value.get('schema') == SCHEMA
                    and value.get('candidate_commit') == binding.BUILD
                    and value.get('signature_policy') == 'UNSIGNED_INTERNAL', 'request-identity-policy')
    mode = value.get('mode')
    binding.require(isinstance(mode, str) and mode in MODE_FIELDS
                    and set(value) == COMMON | MODE_FIELDS[mode], 'request-mode-fields')
    if mode in ('observe', 'host-diagnostic'):
        durations = (300,) if mode == 'host-diagnostic' else (900, 7200)
        binding.require(type(value['duration_seconds']) is int and value['duration_seconds'] in durations,
                        'duration-does-not-match-request-mode')
        data = value['spec']
        binding.require(isinstance(data, dict) and set(data) == {f.name for f in fields(observation.ObservationSpec)},
                        'observation-spec-fields')
        binding.require(data['reference_sha256'] == binding.REFERENCE_SHA, 'production-payload-reference-pin')
        for role in ('main', 'backend'):
            binding.require(isinstance(data[role], dict)
                            and set(data[role]) == {f.name for f in fields(ProcessIdentity)}, 'process-identity-fields')
    else:
        timeout = value['validator_timeout_seconds']
        binding.require(type(timeout) is int and 1 <= timeout <= 3600, 'validator-timeout-budget')
        for name in ('roles', 'expected_files', 'image_files', 'shutdown_expectation'):
            binding.require(isinstance(value[name], dict), 'request-object:' + name)
        binding.require(isinstance(value['configuration_reference_sha256'], str)
                        and re.fullmatch('[0-9a-f]{64}', value['configuration_reference_sha256']), 'configuration-pin-format')
    return mode


def execute_phase(request, folder, package):
    mode = validate_request(request)
    if mode in ('observe', 'host-diagnostic'):
        data = dict(request['spec'])
        data['main'] = ProcessIdentity(**data['main'])
        data['backend'] = ProcessIdentity(**data['backend'])
        spec = observation.ObservationSpec(**data)
        spec.validate()
        options = {'_worker_target': host_diagnostic.worker_entry} if mode == 'host-diagnostic' else {}
        result = observation.supervise_observation(spec, folder / 'observation',
                                                   duration_seconds=request['duration_seconds'], **options)
        return result, result['supervisor_status'] == 'PASS'
    bound = inputs.CsvInputs(request['data_root'], folder / 'csv-inputs', request['roles'],
                             request['expected_files'], package / 'validate_csv_v2_shadow.exe')
    result = qa.validate_closed_data(bound, request['image_files'], package / 'validate_spot_image_files.exe',
        folder / 'closed-data', request['shutdown_expectation'], request['configuration_reference'],
        request['configuration_reference_sha256'], timeout=request['validator_timeout_seconds'])
    return result, result['closed_data_status'] == 'PASS'


def run(request_path, request_sha256, output_root, package):
    binding.require(isinstance(request_sha256, str) and re.fullmatch('[0-9a-f]{64}', request_sha256), 'external-request-sha')
    output_root, package = binding.plain_path(output_root), binding.plain_path(package)
    binding.require(output_root.is_dir() and package.is_dir() and output_root != package
                    and package not in output_root.parents, 'output-package-boundary')
    folder = output_root / 'session'
    binding.require(not folder.exists() and len(str(folder / 'closed-data/checks/image-process/LOCALAPPDATA')) <= 240,
                    'new-session-path-budget')
    folder.mkdir()
    result = dict(schema='sfl-field-run-result-v1', status='FAIL', errors=[], request_sha256=request_sha256,
                  frozen=bool(getattr(sys, 'frozen', False)), full_data_gate='NOT_EVALUATED',
                  release_gate='HOLD', promotion_allowed=False, installation_performed=False,
                  application_shutdown_performed=False)
    try:
        with binding.locked_read(request_path) as stream:
            binding.require(os.fstat(stream.fileno()).st_size <= 128 * 1024**2, 'request-size-budget')
            raw = stream.read()
            binding.require(hashlib.sha256(raw).hexdigest() == request_sha256, 'request-sha-mismatch')
            with (folder / 'request.json').open('xb') as copy:
                copy.write(raw); copy.flush(); os.fsync(copy.fileno())
            request = binding.strict_json(raw)
            result['mode'] = validate_request(request)
            input_paths = ([request['spec']['root'], request['spec']['configuration_reference'], request['spec']['reference']]
                           if result['mode'] in ('observe', 'host-diagnostic')
                           else [request['data_root'], request['configuration_reference']])
            for path in input_paths:
                path = binding.plain_path(path)
                binding.require(path != output_root and output_root not in path.parents
                                and path not in output_root.parents, 'output-input-boundary')
            result['phase'], passed = execute_phase(request, folder, package)
            for key in ('validation_scope', 'physical_device_gate', 'formal_qa_gate'):
                if key in result['phase']:
                    result[key] = result['phase'][key]
            binding.require(result['phase'].get('release_gate') == 'HOLD'
                            and result['phase'].get('promotion_allowed') is False, 'phase-release-scope')
            stream.seek(0)
            binding.require(hashlib.sha256(stream.read()).hexdigest() == request_sha256, 'request-closeout-hash')
        if passed: result['status'] = 'PASS'
    except Exception as error:
        result['errors'].append(error_record(error))
    qa.write_json(folder / 'result.json', result)
    facts = {}
    for name in sorted(qa.image_names(folder, folder)):
        with binding.locked_read(folder / name) as stream: facts[name] = inputs.file_fact(stream)
    qa.write_json(folder / 'manifest.json', dict(schema='sfl-field-run-files-v1', files=facts,
                                                release_gate='HOLD', promotion_allowed=False))
    with binding.locked_read(folder / 'manifest.json') as stream: manifest = inputs.file_fact(stream)
    scope = {key: result[key] for key in ('validation_scope', 'physical_device_gate', 'formal_qa_gate') if key in result}
    return dict(status=result['status'], mode=result.get('mode'), result_path=str(folder), manifest=manifest,
                request_sha256=request_sha256, release_gate='HOLD', promotion_allowed=False, **scope)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe', action='store_true')
    parser.add_argument('--request', type=Path)
    parser.add_argument('--request-sha256')
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--package-root', type=Path)
    args = parser.parse_args(argv)
    try:
        supplied = (args.request, args.request_sha256, args.output_root, args.package_root)
        if args.describe:
            binding.require(not any(supplied), 'describe-with-run-arguments')
            print(json.dumps(dict(schema=SCHEMA, modes=list(MODE_FIELDS), candidate_commit=binding.BUILD,
                frozen=bool(getattr(sys, 'frozen', False)), signature_policy='UNSIGNED_INTERNAL',
                release_gate='HOLD', promotion_allowed=False)))
            return 0
        binding.require(all(supplied), 'all-run-arguments-required')
        result = run(args.request, args.request_sha256, args.output_root, args.package_root)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['status'] == 'PASS' else 1
    except Exception as error:
        print(json.dumps(dict(status='FAIL', error=error_record(error), release_gate='HOLD', promotion_allowed=False)))
        return 1


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
