"""Verify pinned running-identity receipts before preparing a field diagnostic.

This proves the captured OS identity, not that the process is still running.
The diagnostic must independently match that generation again at execution.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import ntpath
from pathlib import Path
import re

import field_installation_binding as binding
from review_health_runtime_close import (
    BACKEND, BUILD, MAIN, decode, integer, native_identity, sha, utc,
)


require = binding.require
MEMBERS = {'request.json', 'health-before.json', 'runtime-before.json', 'config.ini'}


def review_bytes(files, request_sha256, launch_exit):
    require(type(launch_exit) is int and launch_exit == 0, 'launcher-nonzero')
    require(set(files) == MEMBERS | {'result.json'}, 'result-membership')
    require(sha(files['request.json']) == request_sha256, 'external-request-pin')
    request = decode(files['request.json'])
    require(request['schema'] == 'sfl-health-runtime-close-request-v1'
            and request['candidate_commit'] == BUILD, 'request-build-schema')
    require(request['physical_boundary'] == 'NOT_TESTED' and request['release_gate'] == 'HOLD'
            and request['promotion_allowed'] is False, 'request-scope')
    logger, csv_name = request['logger_service_instance_id'], request['csv_name']
    require(type(logger) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', logger), 'logger-id')
    require(type(csv_name) is str and re.fullmatch(r'Factory_Integrated_Log_v2_[0-9]{8}_[0-9]{6}\.csv', csv_name), 'csv-name')
    result = decode(files['result.json'])
    require(result['schema'] == 'sfl-health-runtime-identity-result-v1'
            and result['status'] == 'RUNNING_IDENTITY_CAPTURED_REQUIRES_REVIEW'
            and result['request_sha256'] == request_sha256
            and set(result['files']) == MEMBERS, 'result-contract')
    for name in MEMBERS:
        require(result['files'][name] == {'bytes': len(files[name]), 'sha256': sha(files[name])}, 'file-pin:' + name)
    for name in ('configuration_changed', 'application_started', 'application_shutdown_performed',
                 'actual_process_exit_observed', 'full_backup_created', 'promotion_allowed'):
        require(result[name] is False, 'unexpected-side-effect:' + name)
    require(result['field_gate'] == 'NOT_EVALUATED' and result['release_gate'] == 'HOLD', 'result-scope')
    require(sha(files['config.ini']) == request['config_sha256'], 'config-pin')
    health = decode(files['health-before.json'])
    require(health['running'] is True and health['mode'] == 'REAL' and health['app_version'] == '1.0.29'
            and ntpath.normcase(health['executable_path']) == ntpath.normcase(BACKEND), 'health-runtime')
    spot = health['spot_temperature']
    operational = spot['v2_4_operational']
    require(spot['build_git_commit'] == BUILD and operational['logger_service_instance_id'] == logger
            and operational['current_v2_csv_file_name'] == csv_name, 'health-generation')
    before = decode(files['runtime-before.json'])
    observed = utc(before['observed_at_utc'])
    identities = before['processes']
    require(type(identities) is list and 2 <= len(identities) <= 16, 'native-process-count')
    native = {native_identity(item): item for item in identities}
    require(len(native) == len(identities), 'duplicate-native-pid')
    main, backend = before['main_pid'], before['backend_pid']
    require(integer(main, 1) and integer(backend, 1) and main != backend
            and main in native and backend in native, 'main-backend-pids')
    for pid, item in native.items():
        require(pid < 2**32 and item['created_filetime'] < 2**64, 'native-identity-bounds')
        require(ntpath.normcase(item['exe']) == ntpath.normcase(BACKEND if pid == backend else MAIN), 'native-path')
        require(utc(item['created_at_utc']) <= observed, 'creation-after-observation')
    require(utc(native[backend]['created_at_utc']) <= utc(operational['logger_service_started_at']) <= observed,
            'logger-start-outside-process')
    cim = before['observation']['processes']
    require(type(cim) is list and len(cim) == len(native)
            and all(integer(p['ProcessId'], 1) and integer(p['ParentProcessId']) for p in cim)
            and {p['ProcessId'] for p in cim} == set(native), 'cim-membership')
    for item in cim:
        pid = item['ProcessId']
        require(ntpath.normcase(item['ExecutablePath']) == ntpath.normcase(native[pid]['exe']), 'cim-native-path')
        require(item['Name'].casefold() == ('smartfactorybackend.exe' if pid == backend else 'smart-factory.exe'), 'cim-name')
        require(pid == main or item['ParentProcessId'] == main, 'cim-parent')
        stamp = item['CreationDate']
        match = re.fullmatch(r'/Date\((-?\d+)(?:[+-]\d{4})?\)/', stamp) if type(stamp) is str else None
        created = int(match[1]) / 1000 if match else utc(stamp)
        require(abs(created - native[pid]['created']) <= .0011, 'cim-native-creation')
    listeners = before['observation']['listeners']
    require(type(listeners) is list and 1 <= len(listeners) <= 4
            and all(type(x['LocalPort']) is int and type(x['OwningProcess']) is int
                    and x['LocalPort'] == 8000 and x['OwningProcess'] == backend for x in listeners), 'listener-owner')
    return dict(status='CAPTURED_NATIVE_RUNTIME_IDENTITY_VERIFIED', candidate_commit=BUILD,
                observed_at_utc=before['observed_at_utc'], logger_service_instance_id=logger, csv_name=csv_name,
                config_sha256=request['config_sha256'], main=native[main], backend=native[backend],
                native_processes=len(native), current_liveness='REQUIRES_EXECUTION_TIME_RECHECK',
                configuration_attestation='NOT_EVALUATED', actual_process_exit_observed=False,
                file_content_qa='NOT_EVALUATED', physical_boundary='NOT_TESTED',
                field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)


def review(source, result_sha256, request_sha256, launch_exit):
    for pin in (result_sha256, request_sha256):
        require(type(pin) is str and re.fullmatch('[a-f0-9]{64}', pin), 'external-pin-format')
    root = binding.plain_path(source)
    entries = list(root.iterdir())
    require({p.name for p in entries} == MEMBERS | {'result.json'}
            and all(p.is_file() for p in entries), 'result-directory-membership')
    files = {}
    with ExitStack() as stack:
        for path in entries:
            stream = stack.enter_context(binding.locked_read(path))
            raw = stream.read(4 * 1024**2 + 1)
            require(0 < len(raw) <= 4 * 1024**2, 'file-byte-budget')
            files[path.name] = raw
        require(sha(files['result.json']) == result_sha256, 'console-result-pin')
        result = review_bytes(files, request_sha256, launch_exit)
        require({p.name for p in root.iterdir()} == set(files), 'result-membership-changed')
        result.update(console_result_sha256=result_sha256, request_sha256=request_sha256,
                      scope='RECOVERED_PINNED_CAPTURED_IDENTITY_NOT_LIVE_FIELD_QA', files_verified=5)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--result-sha256', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--launch-exit', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).absolute()
    require(not output.is_relative_to(Path(args.source).absolute()), 'output-must-be-outside-evidence')
    try:
        result = review(args.source, args.result_sha256, args.request_sha256, args.launch_exit)
        code = 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as error:
        result = dict(status='HOLD', error_type=type(error).__name__, reason=str(error),
                      release_gate='HOLD', promotion_allowed=False)
        code = 1
    result['reviewed_at_utc'] = datetime.now(timezone.utc).isoformat()
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
