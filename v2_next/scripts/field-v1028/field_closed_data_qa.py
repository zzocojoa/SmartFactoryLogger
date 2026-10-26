"""Run pinned CSV/image checks on the same locked closed-copy inputs.

The protected caller authenticates inventory/observation/attestation provenance.
This module neither closes the real app nor approves deployment. Default-stream
locks and output reconciliation do not replace protected parent/output ACLs.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import subprocess
import time

import field_csv_inputs as csv_inputs
import field_installation_binding as binding
from field_resource_sampling import error_record
from field_windows_job import CollectorJob


IMAGE_EXE_SHA = '5601b347637bd0dcb9971839ec93bdc2860ad4594e5ba328acd4e70fa91d5f14'
IMAGE_SOURCE_SHA = '067f2a50f69d44e7665020ebd64898964f215f32cbf7fc2caca72cea1edc79db'
COMMAND_OUTPUT_LIMIT = 128 * 1024**2


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def new_directory(path, input_root):
    path = Path(path)
    binding.require(path.is_absolute() and not path.exists() and path != input_root
                    and input_root not in path.parents, 'new-output-outside-input')
    binding.plain_path(path.parent)
    binding.require(len(str(path)) <= 200, 'output-directory-path-budget')
    path.mkdir()
    return binding.plain_path(path)


def image_names(root, capture):
    pending, names, seen = [binding.plain_path(capture)], set(), 0
    while pending:
        for path in pending.pop().iterdir():
            seen += 1
            binding.require(seen <= 1000000, 'image-tree-entry-budget')
            binding.plain_path(path)
            name = binding.entry_name(path.relative_to(root).as_posix())
            if path.is_dir():
                pending.append(path)
            else:
                binding.require(path.is_file(), 'image-tree-regular-file')
                names.add(name)
    return names


class ImageInputs:
    def __init__(self, bound, expected_files, executable, capture_name='spot_images'):
        self.bound, self.expected = bound, deepcopy(expected_files)
        self.executable, self.capture = Path(executable), bound.root / capture_name
        binding.entry_name(capture_name)
        binding.require('/' not in capture_name, 'direct-capture-directory')
        self.stack, self.held = ExitStack(), {}
        self.receipt = dict(input_binding_status='FAIL', image_file_count=len(self.expected))

    def hold(self, path, expected=None):
        stream = self.stack.enter_context(binding.locked_read(path))
        stat = os.fstat(stream.fileno())
        value = csv_inputs.file_fact(stream)
        binding.require(expected is None or value == expected, 'image-input-fact-mismatch')
        self.held[path] = (stream, (stat.st_dev, stat.st_ino, stat.st_size), value)
        return value

    def __enter__(self):
        try:
            binding.require(self.bound.active, 'csv-input-context-required')
            binding.require(isinstance(self.expected, dict) and len(self.expected) <= 400000, 'image-file-count')
            binding.require(self.capture.is_dir(), 'capture-directory-required')
            folded = set()
            for name, fact in self.expected.items():
                binding.entry_name(name)
                binding.require(name.startswith(self.capture.name + '/') and name.casefold() not in folded,
                                'image-input-name-or-case-collision')
                folded.add(name.casefold())
                binding.require(isinstance(fact, dict) and set(fact) == {'bytes', 'sha256'}
                                and type(fact['bytes']) is int and 0 <= fact['bytes'] <= 2 * 1024**3
                                and isinstance(fact['sha256'], str)
                                and re.fullmatch('[0-9a-f]{64}', fact['sha256']), 'image-input-fact-contract')
                self.hold(self.bound.root / name, fact)
            binding.require(self.hold(self.executable)['sha256'] == IMAGE_EXE_SHA, 'image-executable-pin')
            self.recheck()
            self.receipt.update(input_binding_status='ACTIVE', executable_sha256=IMAGE_EXE_SHA)
            return self
        except BaseException:
            self.stack.close()
            raise

    def recheck(self):
        binding.require(image_names(self.bound.root, self.capture) == self.expected.keys(), 'image-inventory-set')
        for path, (stream, identity, expected) in self.held.items():
            stat = binding.plain_path(path).stat()
            binding.require((stat.st_dev, stat.st_ino, stat.st_size) == identity, 'image-input-identity')
            binding.require(csv_inputs.file_fact(stream) == expected, 'image-input-bytes')

    def __exit__(self, error_type, error, traceback):
        self.receipt['input_binding_status'] = 'FAIL'
        try:
            self.recheck()
        finally:
            self.stack.close()
        if error_type is None:
            self.receipt['input_binding_status'] = 'PASS'


def _command_worker(gate, command, folder):
    if not gate.wait(30):
        raise TimeoutError('command-job-gate')
    folder = Path(folder)
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE') if key in os.environ}
    env['PATH'] = str(Path(env['SYSTEMROOT']) / 'System32') + ';' + env['SYSTEMROOT']
    for key in ('APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP'):
        path = folder / key
        path.mkdir()
        env[key] = str(path)
    with (folder / 'stdout.log').open('xb') as out, (folder / 'stderr.log').open('xb') as err:
        process = subprocess.run(command, cwd=folder, env=env, stdout=out, stderr=err,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        out.flush(); os.fsync(out.fileno())
        err.flush(); os.fsync(err.fileno())
    write_json(folder / 'terminal.json', dict(command=command, exit_code=process.returncode))


def run_command(command, folder, *, timeout=120):
    """Own only a newly created gated worker tree; never select a process by name."""
    binding.require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 3600,
                    'command-timeout-budget')
    folder = Path(folder)
    binding.plain_path(folder.parent)
    binding.require(not folder.exists() and len(str(folder / 'LOCALAPPDATA')) <= 240, 'new-command-folder')
    folder.mkdir()
    context = multiprocessing.get_context('spawn')
    gate = context.Event()
    process = context.Process(target=_command_worker, args=(gate, command, str(folder)))
    receipt = dict(process_status='FAIL', errors=[], termination_requested=False, command=command)
    job, started = None, False
    try:
        job = CollectorJob()
        process.start()
        started = True
        receipt['worker_pid'] = process.pid
        job.assign_owned_process(process)
        gate.set()
        deadline = time.monotonic() + timeout
        while process.is_alive():
            binding.require(time.monotonic() < deadline, 'command-deadline')
            for name in ('stdout.log', 'stderr.log'):
                path = folder / name
                binding.require(not path.exists() or path.stat().st_size <= COMMAND_OUTPUT_LIMIT, 'command-output-budget')
            process.join(.05)
        receipt['worker_exit_code'] = process.exitcode
        binding.require(process.exitcode == 0, 'command-worker-exit')
        receipt['job_before_close'] = job.accounting()
        # A signaled worker and an idle owned job are distinct observations.
        # Preserve the first count; confirm the whole tree within both budgets.
        drain_started = time.monotonic()
        drain = receipt['job_drain'] = dict(budget_seconds=2, observations=[], idle_confirmed=False)
        try:
            while True:
                current = job.accounting()
                now = time.monotonic()
                drain['observations'].append(dict(elapsed_ms=(now-drain_started)*1000, accounting=current))
                binding.require(now < deadline, 'command-deadline')
                if current['active_processes'] == 0:
                    drain['idle_confirmed'] = True
                    break
                for name in ('stdout.log', 'stderr.log'):
                    path = folder / name
                    binding.require(not path.exists() or path.stat().st_size <= COMMAND_OUTPUT_LIMIT,
                                    'command-output-budget')
                binding.require(now < drain_started + 2, 'command-descendants-remain')
                time.sleep(min(.025, max(0, min(deadline, drain_started + 2) - now)))
        finally:
            drain['elapsed_ms'] = (time.monotonic()-drain_started)*1000
        with binding.locked_read(folder / 'terminal.json') as stream:
            binding.require(os.fstat(stream.fileno()).st_size <= 65536, 'command-terminal-budget')
            terminal = binding.strict_json(stream.read())
        binding.require(terminal.get('command') == command and type(terminal.get('exit_code')) is int,
                        'command-terminal-contract')
        receipt['exit_code'] = terminal['exit_code']
        receipt['process_status'] = 'PASS'
    except Exception as error:
        receipt['errors'].append(error_record(error))
    finally:
        try:
            if job is not None:
                if job.accounting()['active_processes']:
                    receipt['termination_requested'] = True
                    job.terminate()
                    deadline = time.monotonic() + 10
                    while job.accounting()['active_processes'] and time.monotonic() < deadline:
                        time.sleep(.05)
                receipt['job_after_cleanup'] = job.accounting()
                binding.require(receipt['job_after_cleanup']['active_processes'] == 0, 'command-job-still-active')
        except Exception as error:
            receipt['errors'].append(error_record(error))
        finally:
            if job is not None:
                try: job.close()
                except Exception as error: receipt['errors'].append(error_record(error))
            if started:
                process.join(10)
                if process.is_alive():
                    receipt['termination_requested'] = True
                    process.terminate()  # Creation handle, also covers failed assignment before gate.
                    process.join(10)
                receipt['worker_still_alive'] = process.is_alive()
                receipt['worker_exit_code'] = process.exitcode
                if not process.is_alive(): process.close()
        if receipt['errors'] or receipt['termination_requested'] or receipt.get('worker_still_alive'):
            receipt['process_status'] = 'FAIL'
    receipt['outputs'] = {}
    receipt['output_read_completion'] = {}
    output_read_deadline = time.monotonic() + 2
    for name in ('stdout.log', 'stderr.log', 'terminal.json'):
        path = folder / name
        if path.exists():
            read_started = time.monotonic()
            completion = receipt['output_read_completion'][name] = dict(sharing_retries=0, writers_closed=False)
            try:
                while True:
                    try:
                        with binding.locked_read(path) as stream:
                            receipt['outputs'][name] = csv_inputs.file_fact(stream)
                        completion['writers_closed'] = True
                        break
                    except OSError as error:
                        if getattr(error, 'winerror', None) not in (32, 33) or time.monotonic() >= output_read_deadline:
                            raise
                        completion['sharing_retries'] += 1
                        time.sleep(min(.025, max(0, output_read_deadline-time.monotonic())))
            except Exception as error:
                receipt['errors'].append(error_record(error))
                receipt['process_status'] = 'FAIL'
                continue
            finally:
                completion['elapsed_ms'] = (time.monotonic()-read_started)*1000
            if name != 'terminal.json' and receipt['outputs'][name]['bytes'] > COMMAND_OUTPUT_LIMIT:
                receipt['errors'].append(dict(type='ValueError', reason='command-final-output-budget'))
                receipt['process_status'] = 'FAIL'
    write_json(folder / 'process-receipt.json', receipt)
    return receipt


def verify_image_outputs(folder, expected, fact_sha):
    """Reconcile the tool's consumed inventories, not just its PASS label."""
    with ExitStack() as stack:
        streams = {name: stack.enter_context(binding.locked_read(folder / name)) for name in
                   ('summary.json', 'inventory-before.jsonl', 'inventory-after.jsonl', 'image-checks.jsonl')}
        facts = {name: csv_inputs.file_fact(stream) for name, stream in streams.items()}
        binding.require(facts['summary.json']['bytes'] <= 1024**2, 'image-summary-budget')
        stream = streams['summary.json']; stream.seek(0)
        summary = binding.strict_json(stream.read())
        binding.require(summary.get('status') == 'PASS' and summary.get('issue_counts') == {}
                        and summary.get('tool_sha256') == IMAGE_SOURCE_SHA
                        and summary.get('fact_sha256_before') == summary.get('fact_sha256_after') == fact_sha
                        and summary.get('full_data_gate') == 'NOT_EVALUATED', 'image-summary-contract')
        for key in ('fact_row_count', 'checked_file_count', 'inventory_file_count'):
            binding.require(type(summary.get(key)) is int and summary[key] == len(expected), 'image-summary-count')
        binding.require(type(summary.get('orphan_file_count')) is int and summary['orphan_file_count'] == 0,
                        'image-orphan-count')
        for name, stream in streams.items():
            if name == 'summary.json': continue
            stream.seek(0); seen = set()
            while raw := stream.readline(1024**2 + 1):
                binding.require(len(raw) <= 1024**2, 'image-record-budget')
                row = binding.strict_json(raw)
                path = row.get('path')
                binding.require(path in expected and path not in seen and row.get('issues') == [],
                                'image-consumer-inventory-set-or-issues')
                seen.add(path)
                if name == 'image-checks.jsonl':
                    actual = row.get('actual', {})
                    binding.require(row.get('status') == actual.get('status') == 'PASS'
                                    and actual.get('issues') == [] and actual.get('sha256') == expected[path]['sha256']
                                    and actual.get('bytes') == expected[path]['bytes'], 'image-consumer-checked-bytes')
                else:
                    identity = row.get('identity')
                    binding.require(isinstance(identity, list) and len(identity) == 4
                                    and identity[0] == expected[path]['bytes']
                                    and row.get('sha256') == expected[path]['sha256'], 'image-consumer-inventory-fact')
            binding.require(seen == expected.keys(), 'image-consumer-inventory-incomplete')
        return dict(summary=summary, files=facts)


def check_bound_data(bound, image_files, image_executable, output, *, timeout=120):
    """Data checks only, for an already active CSV context; not shutdown/field approval."""
    binding.require(bound.active, 'active-csv-context-required')
    output = new_directory(output, bound.root)
    result = dict(data_checks_status='FAIL', field_gate='NOT_EVALUATED', release_gate='HOLD',
                  promotion_allowed=False, errors=[])
    images = ImageInputs(bound, image_files, image_executable)
    try:
        with images:
            result['csv'] = run_command(bound.command(), output / 'csv', timeout=timeout)
            command = [str(images.executable), '--fact', str(bound.paths['image']),
                       '--capture-root', str(images.capture), '--output-dir', str(output / 'images')]
            result['image'] = run_command(command, output / 'image-process', timeout=timeout)
            binding.require(all(result[k]['process_status'] == 'PASS' and result[k].get('exit_code') == 0
                                for k in ('csv', 'image')), 'csv-or-image-consumer-failed')
            result['image_evidence'] = verify_image_outputs(output / 'images', image_files,
                bound.expected[bound.roles['image']]['sha256'])
            bound.recheck()
        result['data_checks_status'] = 'PASS'
    except Exception as error:
        result['errors'].append(error_record(error))
    result['image_inputs'] = images.receipt
    write_json(output / 'data-checks.json', result)
    return result


def validate_closed_data(bound, image_files, image_executable, output, expected_shutdown,
                         configuration_path, configuration_sha256, *, timeout=120, candidate=binding.CANDIDATE_1028):
    """Require shutdown identity/configuration, both validators and clean context closeout."""
    output = new_directory(output, bound.root)
    result = dict(closed_data_status='FAIL', full_data_gate='NOT_EVALUATED', release_gate='HOLD',
                  promotion_allowed=False, errors=[])
    try:
        with csv_inputs.shutdown_csv_inputs(bound, expected_shutdown, configuration_path, configuration_sha256,
                                           candidate=candidate):
            review = bound.receipt['shutdown_review']['configuration_review']
            result.update({key: review[key] for key in
                           ('validation_scope', 'physical_device_gate', 'formal_qa_gate')})
            result['checks'] = check_bound_data(bound, image_files, image_executable, output / 'checks', timeout=timeout)
            binding.require(result['checks']['data_checks_status'] == 'PASS', 'closed-data-checks-failed')
        binding.require(bound.receipt['input_binding_status'] == 'PASS', 'csv-input-closeout-failed')
        result['closed_data_status'] = 'PASS'
    except Exception as error:
        result['errors'].append(error_record(error))
    result['csv_inputs'] = bound.receipt
    write_json(output / 'closed-data.json', result)
    return result
