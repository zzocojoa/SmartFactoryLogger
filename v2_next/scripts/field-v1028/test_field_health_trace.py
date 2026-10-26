"""Handshake tests with real files/native locks and synthetic coordinator inputs."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch

import field_health_trace as trace
from field_resource_sampling import ProcessIdentity


ROOT = Path(os.environ['SFL_HEALTH_TRACE_TEST_ROOT'])


class TraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir()

    def setUp(self):
        self.root = ROOT/str(len(list(ROOT.iterdir())))
        self.root.mkdir()
        self.channel = self.root/'trace-channel'
        self.channel.mkdir()
        for name in ('payload.json', 'config.json'):
            (self.root/name).write_text('{}')
        self.contract = dict(schema='sfl-health-trace-contract-v1', scope=trace.SCOPE, run_id='b'*32,
            channel_path=str(self.channel), package_sha256='c'*64, backend_pid=101,
            backend_created_filetime=1000, main_pid=100, duration_seconds=6, guard_seconds=30,
            release_gate='HOLD', promotion_allowed=False)
        self.path = self.channel/'contract.json'
        trace.observation.write_json(self.path, self.contract)
        self.spec = trace.TracedHealthCollectionSpec(str(self.root), str(self.root/'payload.json'),
            ProcessIdentity(100, 1.0, os.path.normcase(str(self.root/'smart-factory.exe'))),
            ProcessIdentity(101, 2.0, os.path.normcase(str(self.root/'backend.exe'))), 8000,
            configuration_reference=str(self.root/'config.json'), configuration_reference_sha256='a'*64,
            backend_created_filetime=1000, trace_contract_path=str(self.path),
            trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.evidence = self.root/'evidence'
        self.evidence.mkdir()
        self.handshake = trace.HealthTraceHandshake(self.spec, 6, self.evidence)
        self.stop = threading.Event()

    def test_contract_pin_scope_budget_reuse_and_no_replacement(self):
        for key, value in [('scope', 'FIELD_QA'), ('guard_seconds', 8), ('duration_seconds', True),
                           ('backend_pid', 102), ('backend_created_filetime', 1001), ('promotion_allowed', True)]:
            self.setUp()
            changed = dict(self.contract, **{key: value})
            self.path.write_text(json.dumps(changed))
            spec = replace(self.spec, trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
            with self.subTest(key=key), self.assertRaises(ValueError):
                with trace.HealthTraceHandshake(spec, 6, self.evidence):
                    pass
        self.setUp()
        with self.assertRaises(ValueError):
            with trace.HealthTraceHandshake(replace(self.spec, trace_contract_sha256='0'*64), 6, self.evidence):
                pass
        self.setUp()
        trace.publish(self.channel, 'existing.json', {'value': 1})
        with self.assertRaisesRegex(ValueError, 'trace-channel-already-used'):
            with self.handshake:
                pass
        with self.assertRaisesRegex(ValueError, 'trace-publication-already-exists'):
            trace.publish(self.channel, 'existing.json', {'value': 2})
        self.assertEqual(json.loads((self.channel/'existing.json').read_bytes()), {'value': 1})

    def test_wait_stop_deadline_and_coordinator_failure(self):
        with self.handshake as h:
            with self.assertRaisesRegex(ValueError, 'trace-handshake-deadline'):
                h.wait('missing.json', self.stop, 0)
            self.stop.set()
            with self.assertRaises(InterruptedError):
                h.wait('missing.json', self.stop, 1)
            self.stop.clear()
            trace.publish(self.channel, 'capture-failed.json', dict(schema='sfl-health-trace-failed-v1', **h.common()))
            with self.assertRaisesRegex(ValueError, 'trace-coordinator-failed'):
                h.wait('missing.json', self.stop, 1)

    def test_wait_rejects_different_run_and_boolean_promotion(self):
        with self.handshake as h:
            trace.publish(self.channel, 'wrong.json', dict(h.common(), run_id='d'*32))
            with self.assertRaisesRegex(ValueError, 'trace-handshake-run-binding'):
                h.wait('wrong.json', self.stop, 1)
            trace.publish(self.channel, 'numeric-gate.json', dict(h.common(), promotion_allowed=0))
            with self.assertRaisesRegex(ValueError, 'trace-gate-claim'):
                h.wait('numeric-gate.json', self.stop, 1)

    def coordinator_go(self, handshake):
        directory = self.root/'SmartFactory'/('T'+'d'*12)
        directory.mkdir(parents=True)
        policy = trace.capture_policy(self.spec.outlier_capture, self.spec.cpu_samples, self.spec.concurrent_api,
                                      self.spec.ready_stacks, self.spec.python_frames, self.spec.python_baseline)
        lease = dict(schema=policy['lease_schema'], scope=policy['scope'], run_id=self.contract['run_id'],
            run_path=str(directory), instance='SFLTrace_'+'e'*32, guard_seconds=policy['guard'], capture_seconds=policy['duration'],
            stop_timeout_seconds=60, profile_sha256=policy['profile_sha256'],
            contract_sha256=self.spec.trace_contract_sha256, package_sha256=self.contract['package_sha256'],
            parent_pid=200, parent_created_filetime='2000', release_gate='HOLD', promotion_allowed=False)
        lease_fact = trace.observation.write_json(directory/'lease.json', lease)
        ready = dict(instance=lease['instance'], lease_sha256=lease_fact['sha256'])
        ready_fact = trace.observation.write_json(directory/'ready.json', ready)
        trace.observation.write_json(directory/'start-intent.json', dict(lease_sha256=lease_fact['sha256'],
            manifest_sha256=self.contract['package_sha256'], instance=lease['instance'], observed_before_start='ABSENT',
            guard_pid=300, guard_created_filetime='3000'))
        go = dict(schema='sfl-health-trace-go-v1', **handshake.common(),
            collector_ready_sha256=handshake.ready_fact['sha256'], worker=handshake.worker,
            trace_run_path=str(directory), lease_sha256=lease_fact['sha256'], trace_ready_sha256=ready_fact['sha256'],
            instance=lease['instance'], guard=dict(pid=300, created_filetime='3000'))
        trace.publish(self.channel, 'capture-go.json', go)
        return go, trace.observation.file_fact(self.channel/'capture-go.json')

    def bind(self, handshake, mutation=None):
        def go_wait(name, stop, seconds):
            value, fact = self.coordinator_go(handshake)
            if mutation:
                mutation(value)
            return value, fact
        with patch.object(trace, 'WindowsProcessReader') as reader, patch.object(handshake, 'wait', side_effect=go_wait), \
                patch.object(trace, 'generation_alive') as alive:
            reader.return_value.read.return_value = dict(status='CAPTURED', pid=os.getpid(), created_100ns=1234)
            value = handshake.begin({}, self.stop)
        self.assertEqual(alive.call_count, 2)
        return value

    def test_cpu_contract_and_profile_cannot_be_mixed_with_scheduling_contract(self):
        for cpu in (False, True):
            for wrong_profile in (False, True):
                self.setUp()
                policy = trace.capture_policy(True, cpu)
                self.contract.update(schema=policy['contract_schema'], scope=policy['scope'],
                                     duration_seconds=900, guard_seconds=960)
                self.path.write_text(json.dumps(self.contract))
                self.spec = replace(self.spec, outlier_capture=True, cpu_samples=cpu,
                                    trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())

                def mutate_profile(go):
                    path = Path(go['trace_run_path'])/'lease.json'
                    lease = json.loads(path.read_bytes())
                    lease['profile_sha256'] = trace.PROFILE_SHA256 if cpu else trace.CPU_PROFILE_SHA256
                    path.write_text(json.dumps(lease))
                    go['lease_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()

                with self.subTest(cpu=cpu, wrong_profile=wrong_profile), \
                        trace.HealthTraceHandshake(self.spec, 900, self.evidence) as h:
                    if wrong_profile:
                        with self.assertRaisesRegex(ValueError, 'trace-lease-contract'):
                            self.bind(h, mutate_profile)
                    else:
                        self.assertEqual(self.bind(h)['lease']['profile_sha256'], policy['profile_sha256'])
                        with patch.object(h, 'wait', side_effect=lambda *args: self.stopped(h)):
                            self.assertGreater(h.finish({}, self.stop)['etl']['bytes'], 0)
        for flags in ((False, True), (True, 1), (True, None)):
            with self.assertRaises(ValueError):
                trace.capture_policy(*flags)

    def test_begin_binds_guard_lease_ready_and_native_generation(self):
        with self.handshake as h:
            value = self.bind(h)
            self.assertEqual(value['go']['instance'], value['lease']['instance'])
            ready = json.loads((self.channel/'collector-ready.json').read_bytes())
            self.assertEqual(ready['evidence_directory'], str(self.evidence))
            with self.assertRaises(OSError):
                with self.path.open('w'):
                    pass

    def test_python_contract_profile_and_legacy_scope_cannot_be_mixed(self):
        policy = trace.capture_policy(False, python_frames=True)
        self.assertEqual((policy['duration'], policy['guard'], policy['profile_sha256']),
                         (6, 30, trace.READY_PROFILE_SHA256))
        tool = self.root/'sfl_qpc_reader.exe'
        tool.write_bytes(b'contract-only fixture; never executed')
        self.contract.update(schema=policy['contract_schema'], scope=policy['scope'])
        self.path.write_text(json.dumps(self.contract))
        self.spec = replace(self.spec, python_frames=True, tool=str(tool),
            candidate_commit=trace.binding.CANDIDATE_1030.commit,
            trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'trace-contract-schema'):
            with trace.HealthTraceHandshake(replace(self.spec, python_frames=False, tool=''), 6, self.evidence): pass
        with trace.HealthTraceHandshake(self.spec, 6, self.evidence) as h:
            bound = self.bind(h)
            self.assertEqual(bound['lease']['schema'], policy['lease_schema'])
            with patch.object(h, 'wait', side_effect=lambda *args: self.stopped(h)):
                self.assertGreater(h.finish({}, self.stop)['etl']['bytes'], 0)
        for flags in ((True, False, False, False, True), (False, True, False, False, True),
                      (False, False, True, False, True), (False, False, False, True, True),
                      (False, False, False, False, 1)):
            with self.assertRaises(ValueError): trace.capture_policy(*flags)
        with self.assertRaisesRegex(ValueError, 'trace-python-candidate'):
            replace(self.spec, candidate_commit=trace.binding.CANDIDATE_1029.commit).validate()
        with self.assertRaisesRegex(ValueError, 'trace-unexpected-python-tool'):
            replace(self.spec, python_frames=False).validate()

    def test_concurrent_contract_cannot_be_substituted_for_solo_cpu_contract(self):
        policy = trace.capture_policy(True, True, True)
        self.assertEqual((policy['duration'], policy['guard'], policy['profile_sha256']),
                         (900, 960, trace.CPU_PROFILE_SHA256))
        self.contract.update(schema=policy['contract_schema'], scope=policy['scope'],
                             duration_seconds=900, guard_seconds=960)
        self.path.write_text(json.dumps(self.contract))
        self.spec = replace(self.spec, outlier_capture=True, cpu_samples=True, concurrent_api=True,
                            trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'trace-contract-schema'):
            with trace.HealthTraceHandshake(replace(self.spec, concurrent_api=False), 900, self.evidence):
                pass
        with trace.HealthTraceHandshake(self.spec, 900, self.evidence) as handshake:
            bound = self.bind(handshake)
            self.assertEqual(bound['lease']['schema'], 'sfl-health-cpu-concurrent-lease-v1')
            with patch.object(handshake, 'wait', side_effect=lambda *args: self.stopped(handshake)):
                self.assertGreater(handshake.finish({}, self.stop)['etl']['bytes'], 0)
        for flags in ((False, False, True), (True, False, True), (True, True, 1), (True, True, None)):
            with self.assertRaises(ValueError):
                trace.capture_policy(*flags)

    def test_baseline_policy_keeps_profile_and_limits_but_rejects_mixed_modes(self):
        off = trace.capture_policy(False, python_baseline=True)
        on = trace.capture_policy(False, python_frames=True)
        for key in ('duration', 'guard', 'profile_sha256'):
            self.assertEqual(off[key], on[key])
        self.assertEqual(off['profile_sha256'], trace.READY_PROFILE_SHA256)
        self.assertNotEqual(off['scope'], on['scope'])
        self.assertNotEqual(off['contract_schema'], on['contract_schema'])
        self.assertNotEqual(off['lease_schema'], on['lease_schema'])
        for flags in ((True, False, False, False, False, True), (False, True, False, False, False, True),
                      (False, False, True, False, False, True), (False, False, False, True, False, True),
                      (False, False, False, False, True, True), (False, False, False, False, False, 1)):
            with self.assertRaises(ValueError):
                trace.capture_policy(*flags)

    def test_baseline_binds_its_own_contract_and_rejects_on_or_legacy_contract(self):
        policy = trace.capture_policy(False, python_baseline=True)
        (self.root/'sfl_qpc_reader.exe').write_bytes(b'contract-only fixture; never executed')
        self.contract.update(schema=policy['contract_schema'], scope=policy['scope'])
        self.path.write_text(json.dumps(self.contract))
        self.spec = replace(self.spec, python_baseline=True, tool=str(self.root/'sfl_qpc_reader.exe'),
            candidate_commit=trace.binding.CANDIDATE_1030.commit,
            trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        for alternate in (replace(self.spec, python_baseline=False, python_frames=True),
                          replace(self.spec, python_baseline=False, tool='')):
            with self.assertRaisesRegex(ValueError, 'trace-contract-schema'):
                with trace.HealthTraceHandshake(alternate, 6, self.evidence):
                    pass
        with trace.HealthTraceHandshake(self.spec, 6, self.evidence) as handshake:
            bound = self.bind(handshake)
            self.assertEqual(bound['lease']['profile_sha256'], trace.READY_PROFILE_SHA256)
            with patch.object(handshake, 'wait', side_effect=lambda *args: self.stopped(handshake)):
                self.assertGreater(handshake.finish({}, self.stop)['etl']['bytes'], 0)
        with self.assertRaisesRegex(ValueError, 'trace-python-candidate'):
            replace(self.spec, candidate_commit=trace.binding.CANDIDATE_1029.commit).validate()

    def test_worker_only_starts_python_observer_in_on_condition(self):
        for enabled in (False, True):
            output = self.root/('on' if enabled else 'off')
            output.mkdir()
            spec = replace(self.spec, python_frames=enabled, python_baseline=not enabled,
                           candidate_commit=trace.binding.CANDIDATE_1030.commit,
                           tool=str(self.root/'sfl_qpc_reader.exe'))
            sender = Mock()
            before = sys.stdout, sys.stderr
            with patch.object(trace, 'HealthTraceHandshake') as handshake, \
                    patch.object(trace.python_stream, 'companion') as companion, \
                    patch.object(trace.observation, 'ObservationStop') as stop, \
                    patch.object(trace.collection, 'collect', return_value=dict(collection_status='BOUND_WINDOW_CAPTURED')) as collect:
                try:
                    with self.assertRaises(SystemExit) as ended:
                        trace._worker_entry(spec, output, 6, self.stop, sender)
                finally:
                    sys.stdout, sys.stderr = before
                self.assertEqual(ended.exception.code, 0)
                args, keywords = collect.call_args
                self.assertEqual(args[:3], (spec, output, 6))
                self.assertIs(keywords['_trace'], handshake.return_value.__enter__.return_value)
                self.assertFalse(any(keywords[key] for key in ('_outlier', '_concurrent_api', '_ready_stacks')))
                if enabled:
                    companion.assert_called_once_with(spec, output/'python-stream', stop.return_value, allow_read_gaps=True)
                    self.assertIs(keywords['_python_frames'], companion.return_value.__enter__.return_value)
                else:
                    companion.assert_not_called()
                    self.assertIsNone(keywords['_python_frames'])
                stop.return_value.close.assert_called_once()
                sender.close.assert_called_once()

    def test_ready_contract_rejects_cpu_substitution_and_binds_terminal_trace(self):
        policy = trace.capture_policy(True, False, True, True)
        self.assertEqual((policy['duration'], policy['guard'], policy['profile_sha256']),
                         (900, 960, trace.READY_PROFILE_SHA256))
        self.contract.update(schema=policy['contract_schema'], scope=policy['scope'],
                             duration_seconds=900, guard_seconds=960)
        self.path.write_text(json.dumps(self.contract))
        self.spec = replace(self.spec, outlier_capture=True, concurrent_api=True, ready_stacks=True,
                            trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'trace-contract-schema'):
            with trace.HealthTraceHandshake(replace(self.spec, ready_stacks=False, cpu_samples=True), 900, self.evidence):
                pass
        with trace.HealthTraceHandshake(self.spec, 900, self.evidence) as h:
            bound = self.bind(h)
            self.assertEqual(bound['lease']['profile_sha256'], trace.READY_PROFILE_SHA256)
            with patch.object(h, 'wait', side_effect=lambda *args: self.stopped(h)):
                self.assertGreater(h.finish({}, self.stop)['etl']['bytes'], 0)
        for flags in ((True, True, True, True), (False, False, True, True),
                      (True, False, False, True), (True, False, True, 1), (True, False, True, None)):
            with self.assertRaises(ValueError):
                trace.capture_policy(*flags)

    def test_ready_profile_matches_previously_validated_bytes(self):
        profile = Path(__file__).with_name('profiles')/'SFLReadyThread.wprp'
        self.assertEqual(hashlib.sha256(profile.read_bytes()).hexdigest(), trace.READY_PROFILE_SHA256)

    def test_begin_rejects_changed_ready_worker_or_lease(self):
        for key, value in [('collector_ready_sha256', '0'*64), ('worker', {'pid': 1}),
                           ('lease_sha256', '0'*64), ('trace_ready_sha256', '0'*64), ('instance', 'wrong')]:
            self.setUp()
            with self.subTest(key=key), self.handshake as h, self.assertRaises(ValueError):
                self.bind(h, lambda go: go.update({key: value}))

    def stopped(self, handshake, mutation=None):
        directory = Path(handshake.binding['trace_run_path'])
        raw = b'FAKE_ETL_FOR_CONTRACT_UNIT_TEST_ONLY'
        (directory/'trace.etl').write_bytes(raw)
        etl = trace.observation.file_fact(directory/'trace.etl')
        result = dict(status='CONTROL_FLOW_COMPLETE', lease_sha256=handshake.binding['lease_sha256'],
            instance=handshake.binding['instance'], cleanup_confirmed=True, trace_saved=True,
            cancelled_without_trace=False, reason='controller-requested-stop', errors=[], etl=etl)
        if mutation:
            mutation(result)
        fact = trace.observation.write_json(directory/'result.json', result)
        ended = dict(schema='sfl-health-trace-stopped-v1', **handshake.common(),
            window_sha256=trace.observation.file_fact(self.channel/'capture-complete.json')['sha256'],
            guard_exit=0, trace_result=fact, etl=etl)
        return ended, trace.publish(self.channel, 'capture-stopped.json', ended)

    def test_finish_requires_saved_trace_and_expected_stop_reason(self):
        with self.handshake as h:
            self.bind(h)
            with patch.object(h, 'wait', side_effect=lambda *args: self.stopped(h)):
                result = h.finish({'probe-000.json': {'sha256': 'f'*64, 'bytes': 1}}, self.stop)
            self.assertGreater(result['etl']['bytes'], 0)
        for key, value in [('reason', 'guard-deadline'), ('cleanup_confirmed', False), ('trace_saved', False),
                           ('cancelled_without_trace', True), ('errors', ['failure'])]:
            self.setUp()
            with self.subTest(key=key), self.handshake as h:
                self.bind(h)
                with patch.object(h, 'wait', side_effect=lambda *args: self.stopped(h, lambda r: r.update({key: value}))), \
                        self.assertRaisesRegex(ValueError, 'trace-terminal-status'):
                    h.finish({}, self.stop)

    def test_abort_and_wrong_native_generation_do_not_claim_success(self):
        with self.handshake as h:
            h.abort('ValueError')
            first = (self.channel/'capture-abort.json').read_bytes()
            h.abort('OtherError')
            self.assertEqual(first, (self.channel/'capture-abort.json').read_bytes())
        with patch.object(trace, 'WindowsProcessReader') as reader:
            reader.return_value.read.return_value = dict(status='UNAVAILABLE')
            with self.assertRaisesRegex(ValueError, 'trace-owner-generation-unavailable-or-changed'):
                trace.generation_alive(20, 1000)

    def test_outlier_handshake_binds_separate_contract_and_rejects_legacy_or_mixed_limits(self):
        self.contract.update(schema='sfl-health-outlier-contract-v1', scope=trace.OUTLIER_SCOPE,
                             duration_seconds=900, guard_seconds=960)
        for change in ({}, {'schema': 'sfl-health-trace-contract-v1'}, {'duration_seconds': 6},
                       {'guard_seconds': 30}, {'scope': trace.SCOPE}):
            changed = dict(self.contract, **change)
            self.path.write_text(json.dumps(changed))
            self.spec = replace(self.spec, outlier_capture=True,
                                trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
            if change:
                with self.assertRaises(ValueError):
                    with trace.HealthTraceHandshake(self.spec, 900, self.evidence):
                        pass
            else:
                with trace.HealthTraceHandshake(self.spec, 900, self.evidence) as h:
                    self.assertEqual(h.common()['scope'], trace.OUTLIER_SCOPE)
        self.path.write_text(json.dumps(self.contract))
        self.spec = replace(self.spec, trace_contract_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        with trace.HealthTraceHandshake(self.spec, 900, self.evidence) as h:
            self.bind(h)
            with patch.object(h, 'wait', side_effect=lambda *args: self.stopped(h)):
                result = h.finish({}, self.stop)
            self.assertGreater(result['etl']['bytes'], 0)
        with self.assertRaises(ValueError):
            replace(self.spec, outlier_capture=1).validate()


if __name__ == '__main__':
    unittest.main(verbosity=2)
