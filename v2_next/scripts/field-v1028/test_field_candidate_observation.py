"""Explicit candidate propagation through real isolated collectors and closeout."""
from copy import deepcopy
from dataclasses import asdict, replace
import os
from pathlib import Path
import unittest

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
            reference_sha256=binding.REFERENCE_SHA if candidate == binding.CANDIDATE_1028 else binding.REFERENCE_SHA_1029)
        data = asdict(spec)
        for role in ('main','backend'):
            data[role] = dict(pid=1,created=1.0,exe='unused')
        return dict(schema=runner.SCHEMA,mode='observe',candidate_commit=candidate.commit,
            signature_policy='UNSIGNED_INTERNAL',duration_seconds=900,spec=data)

    def test_request_accepts_exact_candidates_and_legacy_1028_only(self):
        for candidate in (binding.CANDIDATE_1028,binding.CANDIDATE_1029):
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
        with fixture_app(self.folder,disabled_low_signal=True,candidate=binding.CANDIDATE_1029) as spec:
            output=self.folder/'out'
            result=observation.supervise_observation(spec,output,duration_seconds=6.2)
            self.assertEqual(result['supervisor_status'],'PASS',result)
            worker,_=observation.read_json(output/'worker-result.json')
            self.assertEqual(worker['review']['health_requests_including_boundaries'],6)
            self.assertEqual(worker['review']['resource_rows_checked_for_backend'],2)
            self.assertEqual(worker['shutdown_expectation']['build_git_commit'],binding.CANDIDATE_1029.commit)
            shutdown.validate_expectation(worker['shutdown_expectation'],candidate=binding.CANDIDATE_1029)
            with self.assertRaisesRegex(ValueError,'shutdown-expectation-build'):
                shutdown.validate_expectation(worker['shutdown_expectation'])
            self.assertEqual(worker['physical_device_gate'],'NOT_TESTED')
            self.assertEqual(worker['formal_qa_gate'],'HOLD')
            self.assertFalse(worker['promotion_allowed'])
            self.assertEqual(result['job_after_cleanup']['active_processes'],0)
            self.assertEqual(binding.read_process_binding(spec.main,spec.backend,spec.port)['main']['pid'],spec.main.pid)

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
