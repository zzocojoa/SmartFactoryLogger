"""Explicit candidate propagation through real isolated collectors and closeout."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import field_installation_binding as binding
import field_observation as observation
import field_runner as runner
import field_shutdown_binding as shutdown
from test_field_observation import fixture_app

ROOT = Path(os.environ['SFL_CANDIDATE_OBSERVATION_TEST_ROOT'])


class CandidateObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir()

    def setUp(self):
        self.folder = ROOT/self._testMethodName
        self.folder.mkdir()

    def request(self, candidate):
        spec = observation.ObservationSpec('unused', 'unused', None, None, 8000,
            candidate_commit=candidate.commit,
            reference_sha256=binding.candidate_reference_sha256(candidate))
        data = asdict(spec)
        for role in ('main','backend'):
            data[role] = dict(pid=1,created=1.0,exe='unused')
        return dict(schema=runner.SCHEMA,mode='observe',candidate_commit=candidate.commit,
            signature_policy='UNSIGNED_INTERNAL',duration_seconds=900,spec=data)

    def test_request_accepts_exact_candidates_and_legacy_1028_only(self):
        for candidate in binding.CANDIDATES:
            request=self.request(candidate)
            for seconds in (900,7200):
                request['duration_seconds']=seconds
                self.assertEqual(runner.validate_request(request),'observe')
            del request['spec']['candidate_commit']
            if candidate == binding.CANDIDATE_1028:
                self.assertEqual(runner.validate_request(request),'observe')
            else:
                with self.assertRaisesRegex(ValueError,'candidate-mismatch'):
                    runner.validate_request(request)

    def test_mixed_candidate_reference_and_unsupported_requests_rejected(self):
        request=self.request(binding.CANDIDATE_1029)
        for change in ('commit','spec','reference','unknown','duration','extra'):
            value=deepcopy(request)
            if change=='commit':value['candidate_commit']=binding.BUILD
            elif change=='spec':value['spec']['candidate_commit']=binding.BUILD
            elif change=='reference':value['spec']['reference_sha256']=binding.REFERENCE_SHA
            elif change=='unknown':value['candidate_commit']='f'*40
            elif change=='duration':value['duration_seconds']=True
            else:value['spec']['unexpected']=True
            with self.subTest(change=change), self.assertRaises(ValueError):
                runner.validate_request(value)

    def test_candidate_1029_actual_collectors_and_shutdown_expectation(self):
        self.check_actual_collectors(binding.CANDIDATE_1029)

    def test_candidate_1030_actual_collectors_and_shutdown_expectation(self):
        self.check_actual_collectors(binding.CANDIDATE_1030)

    def test_renderer_fix_1030_actual_collectors(self):
        self.check_actual_collectors(binding.CANDIDATE_1030_RENDERER_FIX)


    def test_final_1030_actual_collectors(self):
        self.check_actual_collectors(binding.CANDIDATE_1030_FINAL)

    def test_renderer_fix_1030_rejects_previous_build_before_http(self):
        with fixture_app(self.folder, candidate=binding.CANDIDATE_1030_RENDERER_FIX) as spec:
            result = observation.supervise_observation(
                replace(spec, candidate_commit=binding.CANDIDATE_1030.commit),
                self.folder/'out', duration_seconds=.5)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            self.assertFalse((self.folder/'out/http').exists())
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)


    def test_final_1030_rejects_previous_build_before_http(self):
        with fixture_app(self.folder, candidate=binding.CANDIDATE_1030_FINAL) as spec:
            result = observation.supervise_observation(
                replace(spec, candidate_commit=binding.CANDIDATE_1030.commit),
                self.folder/'out', duration_seconds=.5)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            self.assertFalse((self.folder/'out/http').exists())
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)

    def check_actual_collectors(self, candidate):
        with fixture_app(self.folder,disabled_low_signal=True,candidate=candidate) as spec:
            output=self.folder/'out'
            result=observation.supervise_observation(spec,output,duration_seconds=6.2)
            self.assertEqual(result['supervisor_status'],'PASS',result)
            worker,_=observation.read_json(output/'worker-result.json')
            self.assertEqual(worker['review']['health_requests_including_boundaries'],6)
            self.assertEqual(worker['review']['resource_rows_checked_for_backend'],2)
            self.assertEqual(worker['shutdown_expectation']['build_git_commit'],candidate.commit)
            shutdown.validate_expectation(worker['shutdown_expectation'],candidate=candidate)
            with self.assertRaisesRegex(ValueError,'shutdown-expectation-build'):
                shutdown.validate_expectation(worker['shutdown_expectation'])
            self.assertEqual(worker['physical_device_gate'],'NOT_TESTED')
            self.assertEqual(worker['formal_qa_gate'],'HOLD')
            self.assertFalse(worker['promotion_allowed'])
            self.assertEqual(result['job_after_cleanup']['active_processes'],0)
            self.assertEqual(binding.read_process_binding(spec.main,spec.backend,spec.port)['main']['pid'],spec.main.pid)

    def test_1030_outer_spec_reference_and_mode_must_agree(self):
        request=self.request(binding.CANDIDATE_1030)
        for mode,seconds in (('observe',900),('observe',7200),('host-diagnostic',300)):
            request.update(mode=mode,duration_seconds=seconds)
            self.assertEqual(runner.validate_request(request),mode)
            for key in ('candidate_commit','reference_sha256'):
                wrong=deepcopy(request)
                wrong['spec'][key]=(binding.CANDIDATE_1029.commit if key=='candidate_commit'
                                    else binding.REFERENCE_SHA_1029)
                with self.subTest(mode=mode,key=key),self.assertRaises(ValueError):
                    runner.validate_request(wrong)

    def test_1030_payload_rejects_previous_candidate_before_http(self):
        with fixture_app(self.folder,candidate=binding.CANDIDATE_1030) as spec:
            result=observation.supervise_observation(replace(spec,candidate_commit=binding.CANDIDATE_1029.commit),
                self.folder/'out',duration_seconds=.5)
            self.assertEqual(result['supervisor_status'],'FAIL')
            self.assertFalse((self.folder/'out/http').exists())
            self.assertEqual(result['job_after_cleanup']['active_processes'],0)

    def test_candidate_1029_payload_does_not_accept_1028_spec(self):
        with fixture_app(self.folder,candidate=binding.CANDIDATE_1029) as spec:
            result=observation.supervise_observation(replace(spec,candidate_commit=binding.BUILD),
                self.folder/'out',duration_seconds=.5)
            self.assertEqual(result['supervisor_status'],'FAIL')
            self.assertFalse((self.folder/'out/http').exists())
            self.assertEqual(result['job_after_cleanup']['active_processes'],0)

    def test_candidate_1029_slow_first_health_remains_failure(self):
        with fixture_app(self.folder,'slow-first',candidate=binding.CANDIDATE_1029) as spec:
            result=observation.supervise_observation(spec,self.folder/'out',duration_seconds=.5)
            self.assertEqual(result['supervisor_status'],'FAIL')
            worker,_=observation.read_json(self.folder/'out/worker-result.json')
            self.assertGreater(worker['review']['first_health_ms'],200)
            self.assertIn('all-health-including-boundaries-failed',worker['review']['issues'])

    def test_operational_request_is_explicit_and_keeps_legacy_request_shape(self):
        request = self.request(binding.CANDIDATE_1030_FINAL)
        request['mode'] = 'operational-observe'
        self.assertEqual(runner.validate_request(request), 'operational-observe')
        request['duration_seconds'] = 1
        with self.assertRaises(ValueError):
            runner.validate_request(request)

    def test_operational_entry_dispatch_does_not_use_legacy_spec(self):
        request = self.request(binding.CANDIDATE_1030_FINAL)
        request['mode'] = 'operational-observe'
        with patch.object(observation.OperationalObservationSpec, 'validate'), \
             patch.object(observation, 'supervise_observation',
                          return_value={'supervisor_status': 'PASS'}) as supervise:
            result, passed = runner.execute_phase(request, self.folder, self.folder)
        self.assertTrue(passed)
        self.assertIsInstance(supervise.call_args.args[0], observation.OperationalObservationSpec)
        self.assertEqual(result['supervisor_status'], 'PASS')

    def test_operational_initial_request_error_still_fails(self):
        with fixture_app(self.folder, 'initial-error', candidate=binding.CANDIDATE_1030_FINAL) as original:
            spec = observation.OperationalObservationSpec(**vars(original))
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=.5)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            self.assertFalse((self.folder / 'out/http').exists())
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)

    def test_operational_entry_receipt_separates_measurement_from_performance(self):
        for passed in (False, True):
            with self.subTest(collection_complete=passed):
                folder = self.folder / str(passed)
                folder.mkdir()
                for name in ('input', 'package', 'output'):
                    (folder / name).mkdir()
                request = self.request(binding.CANDIDATE_1030_FINAL)
                request['mode'] = 'operational-observe'
                request['spec']['root'] = str(folder / 'input')
                for key in ('reference', 'configuration_reference'):
                    path = folder / 'input' / (key + '.json')
                    path.write_text('{}', encoding='utf-8')
                    request['spec'][key] = str(path)
                path = folder / 'request.json'
                path.write_text(json.dumps(request), encoding='utf-8')
                phase = dict(supervisor_status='PASS' if passed else 'FAIL',
                    observation_status='PASS' if passed else 'INCOMPLETE',
                    assessment_policy='operational-evidence-v2',
                    status_scope='COLLECTION_AND_BINDING_ONLY',
                    operational_performance='NOT_EVALUATED',
                    incomplete_evidence=[] if passed else ['http-measurement-incomplete'],
                    release_gate='HOLD', promotion_allowed=False)
                with patch.object(runner, 'execute_phase', return_value=(phase, passed)):
                    receipt = runner.run(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                                         folder / 'output', folder / 'package')
                self.assertEqual(receipt['observation_status'], phase['observation_status'])
                self.assertEqual(receipt['incomplete_evidence'], phase['incomplete_evidence'])
                self.assertEqual(receipt['status_scope'], 'COLLECTION_AND_BINDING_ONLY')
                self.assertEqual(receipt['operational_performance'], 'NOT_EVALUATED')
                self.assertEqual(receipt['release_gate'], 'HOLD')
                self.assertFalse(receipt['promotion_allowed'])

    def test_operational_slow_boundaries_collect_without_product_pass_or_image_load(self):
        for mode in ('slow-first', 'slow-control'):
            folder = self.folder / mode
            folder.mkdir()
            with fixture_app(folder, mode, candidate=binding.CANDIDATE_1030_FINAL) as original:
                spec = observation.OperationalObservationSpec(**vars(original))
                output = folder / 'out'
                result = observation.supervise_observation(spec, output, duration_seconds=2.2)
                self.assertEqual(result['supervisor_status'], 'PASS', result)
                worker, _ = observation.read_json(output / 'worker-result.json')
                self.assertEqual(worker['operational_performance'], 'NOT_EVALUATED')
                self.assertEqual(worker['status_scope'], 'COLLECTION_AND_BINDING_ONLY')
                assessment = worker['review']['operational_assessment']
                self.assertEqual(assessment['collection_status'], 'COMPLETE', assessment)
                self.assertEqual(assessment['display_freshness'], 'NOT_EVALUATED')
                self.assertFalse(list((output / 'http').glob('image-*')))
                if mode == 'slow-first':
                    self.assertGreater(worker['review']['first_health_ms'], 200)
                    self.assertGreaterEqual(assessment['channels']['health_including_boundaries']
                                            ['reference_exceedances'], 1)
                else:
                    control, _ = observation.read_json(output / 'control-initial.json')
                    self.assertTrue(control['over_200ms'])
                self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
                self.assertEqual(worker['release_gate'], 'HOLD')
                self.assertFalse(worker['promotion_allowed'])
                if mode == 'slow-first':
                    self._check_missing_slot_replay(spec, output, worker)

    def _check_missing_slot_replay(self, spec, source, worker):
        """Alter only a disposable test copy to exercise durable missing-slot review."""
        from field_operational_assessment import assess_channel, combine
        target = source.parent / 'synthetic-missing-slot'
        target.mkdir()
        for name in ('http', 'resources', 'processes'):
            shutil.copytree(source / name, target / name)
        missing = target / 'http/health-00001.json'
        missing.write_text(json.dumps(dict(sequence=1, kind='missed_slot')), encoding='utf-8')
        summary_path = target / 'http/summary.json'
        summary, _ = observation.read_json(summary_path)
        assessment = {}
        for endpoint in observation.http.ENDPOINTS[:2]:
            count = 2 if endpoint.name == 'health' else 1
            rows = [observation.read_json(target / 'http' / f'{endpoint.name}-{n:05d}.json')[0]
                    for n in range(count)]
            assessment[endpoint.name] = assess_channel(endpoint, rows, count)
        summary['operational_assessment'] = combine(assessment)
        summary['http_component_status'] = 'INCOMPLETE'
        summary_path.write_text(json.dumps(summary), encoding='utf-8')
        manifest_path = target / 'http/manifest.json'
        manifest, _ = observation.read_json(manifest_path)
        for changed in (missing, summary_path):
            manifest['files'][changed.name] = observation.file_fact(changed)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        initial, _ = observation.read_json(source / 'initial.json')
        final, _ = observation.read_json(source / 'final.json')
        reviewed = observation.review_window(spec, target, worker['origin_ns'], 2.2,
                                             initial['sessions'], [initial, final])
        self.assertEqual(reviewed['status'], 'INCOMPLETE', reviewed)
        channel = reviewed['operational_assessment']['channels']['health_including_boundaries']
        self.assertEqual(channel['missed_slots'], 1)
        self.assertEqual(channel['measurement_status'], 'INCOMPLETE')
        self.assertEqual(channel['request_status'], 'PASS')
        self.assertEqual(reviewed['issues'], [])

        def replace_resource(name, value):
            path = target / 'resources' / name
            path.write_text(json.dumps(value), encoding='utf-8')
            manifest_path = path.parent / 'manifest.json'
            manifest, _ = observation.read_json(manifest_path)
            manifest['files'][name] = observation.file_fact(path)
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

        resource_row, _ = observation.read_json(target / 'resources/resource-00000.json')
        original_process = deepcopy(resource_row['process'])
        resource_row['process']['records'] = []
        resource_row['process']['errors'] = [dict(type='AccessDenied')]
        replace_resource('resource-00000.json', resource_row)
        resource_summary, _ = observation.read_json(target / 'resources/summary.json')
        resource_summary['recording_status'] = 'INCOMPLETE'
        replace_resource('summary.json', resource_summary)
        reviewed = observation.review_window(spec, target, worker['origin_ns'], 2.2,
                                             initial['sessions'], [initial, final])
        self.assertEqual(reviewed['status'], 'INCOMPLETE')
        self.assertEqual(reviewed['issues'], [])
        self.assertIn('resource-0-backend-not-measured', reviewed['incomplete_evidence'])
        resource_row['process']['records'] = original_process['records']
        for row in resource_row['process']['records']:
            if row['pid'] == spec.backend.pid:
                row['created'] += 1
        replace_resource('resource-00000.json', resource_row)
        reviewed = observation.review_window(spec, target, worker['origin_ns'], 2.2,
                                             initial['sessions'], [initial, final])
        self.assertEqual(reviewed['status'], 'FAIL')
        self.assertIn('resource-0-backend-identity-failed', reviewed['issues'])

    def test_operational_changed_identity_still_fails(self):
        with fixture_app(self.folder, 'changed-build', candidate=binding.CANDIDATE_1030_FINAL) as original:
            spec = observation.OperationalObservationSpec(**vars(original))
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=2.2)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            worker, _ = observation.read_json(self.folder / 'out/worker-result.json')
            self.assertIn('health-1-ValueError', worker['review']['issues'])
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)

    def test_candidate_1029_changed_health_build_remains_failure(self):
        with fixture_app(self.folder,'changed-build',candidate=binding.CANDIDATE_1029) as spec:
            result=observation.supervise_observation(spec,self.folder/'out',duration_seconds=2.2)
            self.assertEqual(result['supervisor_status'],'FAIL')
            worker,_=observation.read_json(self.folder/'out/worker-result.json')
            self.assertEqual(worker['observation_status'],'FAIL')
            initial,_=observation.read_json(self.folder/'out/initial.json')
            self.assertEqual(initial['binding_status'],'PASS')
            self.assertIn('health-1-ValueError',worker['review']['issues'])
            self.assertEqual(result['job_after_cleanup']['active_processes'],0)


if __name__ == '__main__':
    unittest.main()
