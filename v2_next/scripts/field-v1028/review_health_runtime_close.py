"""Review externally pinned first-runtime receipts; never approve field QA.

The capture is limited to the current CSV/config/metadata and held OS processes.
Image/fact joins, worker shutdown receipts and physical attestation remain separate.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import io
import csv
import json
import math
import ntpath
from pathlib import Path
import re

import field_installation_binding as binding
from field_http_sampling import _strict_object, _invalid_constant


BUILD = binding.CANDIDATE_1029.commit
INSTALL = r'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
MAIN = INSTALL + r'\smart-factory.exe'
BACKEND = INSTALL + r'\resources\backend\SmartFactoryBackend.exe'
FILETIME_EPOCH = 116444736000000000
require = binding.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    return json.loads(raw, object_pairs_hook=_strict_object, parse_constant=_invalid_constant)


def utc(value):
    require(type(value) is str, 'utc-text-required')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0, 'utc-required')
    return stamp.timestamp()


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def native_identity(identity):
    require(type(identity) is dict and integer(identity['pid'], 1), 'native-pid')
    ticks = identity['created_filetime']
    require(integer(ticks, FILETIME_EPOCH) and identity['native_handle_retained'] is True, 'native-handle-time')
    unix = (ticks - FILETIME_EPOCH) / 1e7
    require(type(identity['created']) in (int, float) and math.isfinite(identity['created'])
            and abs(identity['created'] - unix) < 1e-5
            and abs(utc(identity['created_at_utc']) - unix) < 1e-5, 'native-time-representations')
    require(type(identity['exe']) is str, 'native-executable-text')
    return identity['pid']


def review_bytes(files, request_sha256, launch_exit):
    require(type(launch_exit) is int and launch_exit == 0, 'launcher-nonzero')
    request = decode(files['request.json'])
    require(sha(files['request.json']) == request_sha256, 'external-request-pin')
    require(request['schema'] == 'sfl-health-runtime-close-request-v1'
            and request['candidate_commit'] == BUILD, 'request-build-schema')
    logger = request['logger_service_instance_id']
    require(type(logger) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', logger), 'logger-id')
    csv_name = request['csv_name']
    require(type(csv_name) is str and re.fullmatch(r'Factory_Integrated_Log_v2_[0-9]{8}_[0-9]{6}\.csv', csv_name), 'csv-name')
    metadata_name = csv_name.replace('.csv', '.metadata.json')
    names = {'request.json', 'health-before.json', 'runtime-before.json', 'process-exits.json',
             'runtime-after.json', 'config.ini', metadata_name, csv_name}
    require(set(files) == names | {'result.json'}, 'result-membership')
    result = decode(files['result.json'])
    require(result['schema'] == 'sfl-health-runtime-close-result-v1'
            and result['status'] == 'CLOSED_RUNTIME_CAPTURED_REQUIRES_REVIEW'
            and result['request_sha256'] == request_sha256 and set(result['files']) == names, 'result-contract')
    for name in names:
        require(result['files'][name] == {'bytes': len(files[name]), 'sha256': sha(files[name])}, 'file-pin:' + name)
    for name in ('configuration_changed', 'application_started', 'forced_termination', 'full_backup_created', 'promotion_allowed'):
        require(result[name] is False, 'unexpected-side-effect:' + name)
    require(result['release_gate'] == 'HOLD' and result['file_content_qa'] == 'NOT_EVALUATED', 'result-scope')
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
        require(ntpath.normcase(item['exe']) == ntpath.normcase(BACKEND if pid == backend else MAIN), 'native-path')
        require(utc(item['created_at_utc']) <= observed, 'creation-after-observation')
    require(utc(native[backend]['created_at_utc']) <= utc(operational['logger_service_started_at']) <= observed,
            'logger-start-outside-process')
    observation = before['observation']
    cim = observation['processes']
    require(type(cim) is list and len(cim) == len(native) and {p['ProcessId'] for p in cim} == set(native), 'cim-membership')
    for item in cim:
        pid = item['ProcessId']
        require(ntpath.normcase(item['ExecutablePath']) == ntpath.normcase(native[pid]['exe']), 'cim-native-path')
        require(item['Name'].casefold() == ('smartfactorybackend.exe' if pid == backend else 'smart-factory.exe'), 'cim-name')
        require(pid == main or item['ParentProcessId'] == main, 'cim-parent')
        stamp = item['CreationDate']
        match = re.fullmatch(r'/Date\((-?\d+)(?:[+-]\d{4})?\)/', stamp) if type(stamp) is str else None
        created = int(match[1]) / 1000 if match else utc(stamp)
        require(abs(created - native[pid]['created']) <= .0011, 'cim-native-creation')
    listeners = observation['listeners']
    require(type(listeners) is list and 1 <= len(listeners) <= 4
            and all(x['LocalPort'] == 8000 and x['OwningProcess'] == backend for x in listeners), 'listener-owner')
    exits = decode(files['process-exits.json'])
    require(type(exits) is list and len(exits) == len(native), 'exit-count')
    seen = set()
    for item in exits:
        pid = native_identity(item['identity'])
        require(pid not in seen and item['identity'] == native.get(pid), 'exit-generation')
        seen.add(pid)
        require(type(item['actual_exit_code']) is int and item['actual_exit_code'] == 0
                and item['forced_termination'] is False, 'process-exit-not-normal-zero')
        require(0 <= utc(item['exit_at_utc']) - observed <= 452, 'exit-outside-observation-window')
    cold = decode(files['runtime-after.json'])
    require(cold['processes'] == [] and cold['listeners'] == [], 'runtime-not-cold')

    metadata = decode(files[metadata_name])
    schema, close = metadata['schema_metadata'], metadata['csv_closeout']
    require(schema['git_commit'] == BUILD and schema['logger_service_instance_id'] == logger, 'metadata-generation')
    require(close['finalized'] is True and close['closeout_reason'] == 'shutdown'
            and close['csv_file_name'] == csv_name and close['logger_service_instance_id'] == logger, 'csv-not-finalized')
    reader = csv.DictReader(io.StringIO(files[csv_name].decode('utf-8-sig'), newline=''))
    header = reader.fieldnames
    required = {'sample_seq', 'logger_service_instance_id', 'temperature_output_status', 'temperature_unavailable_reason'}
    require(header is not None and len(header) == len(set(header)) and required <= set(header), 'csv-header')
    statuses, reasons = Counter(), Counter()
    rows = 0
    for rows, row in enumerate(reader, 1):
        require(None not in row and all(value is not None for value in row.values()), 'csv-row-shape')
        require(row['sample_seq'] == str(rows) and row['logger_service_instance_id'] == logger, 'csv-sequence-generation')
        statuses[row['temperature_output_status']] += 1
        reasons[row['temperature_unavailable_reason']] += 1
    require(rows > 0 and integer(close['final_persisted_sample_seq'], 1)
            and rows == close['final_persisted_sample_seq'], 'csv-final-count')
    require(integer(operational['rows_total']) and operational['rows_total'] <= rows, 'csv-before-count')
    return dict(status='LIMITED_RUNTIME_CLOSE_RECEIPTS_VERIFIED', candidate_commit=BUILD,
                logger_service_instance_id=logger, native_processes=len(native), main_pid=main, backend_pid=backend,
                csv_rows=rows, csv_status_counts=dict(statuses), csv_reason_counts=dict(reasons),
                config_sha256=request['config_sha256'], metadata_sha256=sha(files[metadata_name]),
                configuration_attestation='NOT_EVALUATED', image_fact_and_byte_qa='NOT_EVALUATED',
                worker_shutdown_receipts='NOT_EVALUATED', formal_startup_timing='NOT_EVALUATED',
                physical_boundary='NOT_TESTED', release_gate='HOLD', promotion_allowed=False)


def review(source, result_sha256, request_sha256, launch_exit):
    for pin in (result_sha256, request_sha256):
        require(type(pin) is str and re.fullmatch('[a-f0-9]{64}', pin), 'external-pin-format')
    root = binding.plain_path(source)
    entries = list(root.iterdir())
    require(len(entries) == 9 and all(p.is_file() for p in entries), 'result-directory-membership')
    files = {}
    with ExitStack() as stack:
        for path in entries:
            stream = stack.enter_context(binding.locked_read(path))
            limit = 128 * 1024**2 if path.suffix == '.csv' else 4 * 1024**2
            raw = stream.read(limit + 1)
            require(0 < len(raw) <= limit, 'file-byte-budget')
            files[path.name] = raw
        require(sha(files['result.json']) == result_sha256, 'console-result-pin')
        result = review_bytes(files, request_sha256, launch_exit)
        require(set(p.name for p in root.iterdir()) == set(files), 'result-membership-changed')
        result.update(console_result_sha256=result_sha256, request_sha256=request_sha256,
                      scope='RECOVERED_PINNED_RECEIPTS_CURRENT_CSV_SEQUENCE_ONLY', files_verified=9)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--result-sha256', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--launch-exit', required=True, type=int)
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
