"""Request/manifest entry contracts and real closed-copy commands on isolated copies."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import field_runner as runner
import test_field_closed_data_qa as fixtures


ROOT = Path(os.environ['SFL_RUNNER_TEST_ROOT'])


class RunnerTests(unittest.TestCase):
    counter = 0

    @classmethod
    def setUpClass(cls):
        ROOT.mkdir()
        package=ROOT/'package';package.mkdir()
        for source in (fixtures.CSV_EXE,fixtures.IMAGE_EXE):shutil.copy2(source,package/source.name)

    def setUp(self):
        type(self).counter += 1
        self.folder = ROOT / f't{self.counter:02d}'
        self.folder.mkdir()

    def prepare(self, synthetic=False, *, disabled_low_signal=False):
        helper = fixtures.ClosedDataTests()
        helper.folder = self.folder
        folder, data, roles, images = helper.prepare()
        expected, reference, sha = helper.reference(folder, data, roles, synthetic,
                                                   disabled_low_signal=disabled_low_signal)
        package = ROOT / 'package'
        output = self.folder / 'output'; output.mkdir()
        request = dict(schema=runner.SCHEMA, mode='closed-data', candidate_commit=runner.binding.BUILD,
            signature_policy='UNSIGNED_INTERNAL',data_root=str(data), roles=roles,
            expected_files={n: fixtures.fact(data/n) for n in roles.values()}, image_files=images,
            shutdown_expectation=expected,configuration_reference=str(reference),
            configuration_reference_sha256=sha,validator_timeout_seconds=120)
        path = self.folder / 'request.json'; fixtures.save(path,request)
        return request,path,output,package

    def invoke(self, path, output, package, sha=None):
        sha = sha or fixtures.fact(path)['sha256']
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = runner.main(['--request',str(path),'--request-sha256',sha,'--output-root',str(output),
                                '--package-root',str(package)])
        text = stream.getvalue()
        (self.folder/'runner.stdout.log').write_text(text,encoding='utf-8')
        fixtures.save(self.folder/'runner-terminal.json',dict(exit_code=code))
        return code,json.loads(text)

    def test_synthetic_closed_copy_pipeline_and_complete_manifest(self):
        request,path,output,package = self.prepare(True)
        code,receipt = self.invoke(path,output,package)
        self.assertEqual(code,0,receipt)
        self.assertEqual(receipt['status'],'PASS')
        self.assertEqual(receipt['release_gate'],'HOLD')
        self.assertFalse(receipt['promotion_allowed'])
        session=output/'session'
        self.assertEqual(fixtures.fact(session/'manifest.json'),receipt['manifest'])
        manifest=json.loads((session/'manifest.json').read_bytes())
        self.assertEqual(set(manifest['files']),runner.qa.image_names(session,session)-{'manifest.json'})
        for name,value in manifest['files'].items():self.assertEqual(fixtures.fact(session/name),value)
        self.assertEqual((session/'request.json').read_bytes(),path.read_bytes())
        self.assertEqual(request['candidate_commit'],runner.binding.BUILD)

    def test_real_archived_attestation_is_not_promoted(self):
        _,path,output,package=self.prepare()
        code,receipt=self.invoke(path,output,package)
        self.assertEqual(code,1)
        self.assertEqual(receipt['status'],'FAIL')
        self.assertFalse((output/'session/closed-data/checks').exists())

    def test_v2_only_pipeline_keeps_v1_comparison_unrequested(self):
        request,path,output,package=self.prepare(True, disabled_low_signal=True)
        data=Path(request['data_root'])
        name=request['roles'].pop('v1')
        (data/name).rename(self.folder/'omitted-v1.csv')
        del request['expected_files'][name]
        metadata_path=data/request['roles']['metadata']
        metadata=json.loads(metadata_path.read_bytes())
        metadata['schema_metadata']['v1_csv_enabled']=False
        fixtures.save(metadata_path,metadata)
        request['expected_files'][metadata_path.name]=fixtures.fact(metadata_path)
        fixtures.save(path,request)
        code,receipt=self.invoke(path,output,package)
        self.assertEqual(code,0,receipt)
        result=json.loads((output/'session/result.json').read_bytes())
        self.assertFalse(result['phase']['csv_inputs']['v1_comparison_requested'])
        self.assertEqual(result['full_data_gate'],'NOT_EVALUATED')
        self.assertEqual(result['physical_device_gate'],'NOT_TESTED')
        self.assertEqual(result['formal_qa_gate'],'HOLD')

    def test_disabled_trial_result_exposes_pending_physical_and_formal_qa(self):
        _,path,output,package=self.prepare(True, disabled_low_signal=True)
        code,receipt=self.invoke(path,output,package)
        self.assertEqual(code,0,receipt)
        result=json.loads((output/'session/result.json').read_bytes())
        self.assertEqual(result['validation_scope'],fixtures.inputs.configuration.DISABLED_SCOPE)
        self.assertEqual(result['physical_device_gate'],'NOT_TESTED')
        self.assertEqual(result['formal_qa_gate'],'HOLD')
        self.assertEqual(receipt['validation_scope'],result['validation_scope'])
        self.assertEqual(receipt['physical_device_gate'],'NOT_TESTED')
        self.assertEqual(receipt['formal_qa_gate'],'HOLD')
        self.assertEqual(result['release_gate'],'HOLD')
        self.assertFalse(result['promotion_allowed'])

    def test_request_hash_mismatch_starts_no_phase(self):
        _,path,output,package=self.prepare()
        with patch.object(runner,'execute_phase') as phase:
            code,_=self.invoke(path,output,package,sha='0'*64)
        self.assertEqual(code,1);phase.assert_not_called()
        self.assertFalse((output/'session/request.json').exists())

    def test_policy_candidate_extra_fields_and_timeout_reject(self):
        request,_,_,_=self.prepare()
        for field,value in (('signature_policy','SIGNED'),('candidate_commit','a'*40),('extra',True),
                            ('validator_timeout_seconds',True),('validator_timeout_seconds',3601)):
            bad=deepcopy(request);bad[field]=value
            with self.assertRaises(ValueError):runner.validate_request(bad)

    def test_duplicate_request_json_is_preserved_and_rejected(self):
        _,path,output,package=self.prepare()
        path.write_bytes(b'{"schema":1,"schema":2}')
        code,_=self.invoke(path,output,package)
        self.assertEqual(code,1)
        self.assertEqual((output/'session/request.json').read_bytes(),path.read_bytes())

    def test_existing_session_never_overwritten(self):
        _,path,output,package=self.prepare()
        (output/'session').mkdir();keep=output/'session/keep.txt';keep.write_bytes(b'keep')
        code,_=self.invoke(path,output,package)
        self.assertEqual(code,1);self.assertEqual(keep.read_bytes(),b'keep')

    def test_phase_release_claim_is_rejected(self):
        _,path,output,package=self.prepare()
        with patch.object(runner,'execute_phase',return_value=({'release_gate':'PASS','promotion_allowed':True},True)):
            code,_=self.invoke(path,output,package)
        self.assertEqual(code,1)

    def test_describe_and_missing_parameters(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(runner.main(['--describe']),0)
        self.assertEqual(json.loads(out.getvalue())['signature_policy'],'UNSIGNED_INTERNAL')
        self.assertEqual(json.loads(out.getvalue())['supported_candidate_commits'],
                         [candidate.commit for candidate in runner.binding.CANDIDATES])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main([]),1)
            self.assertEqual(runner.main(['--describe','--request','anything']),1)

    def test_observation_duration_and_reference_are_fixed(self):
        spec={f.name:None for f in runner.fields(runner.observation.ObservationSpec)}
        for role in ('main','backend'):spec[role]={f.name:None for f in runner.fields(runner.ProcessIdentity)}
        spec['reference_sha256']=runner.binding.REFERENCE_SHA
        spec['candidate_commit']=runner.binding.BUILD
        request=dict(schema=runner.SCHEMA,mode='observe',candidate_commit=runner.binding.BUILD,
                     signature_policy='UNSIGNED_INTERNAL',duration_seconds=900,spec=spec)
        self.assertEqual(runner.validate_request(request),'observe')
        request['duration_seconds']=7200;self.assertEqual(runner.validate_request(request),'observe')
        for value in (420,1,True,7201):
            request['duration_seconds']=value
            with self.assertRaises(ValueError):runner.validate_request(request)
        request['duration_seconds']=900;spec['reference_sha256']='a'*64
        with self.assertRaises(ValueError):runner.validate_request(request)

    def test_candidate_1029_closed_copy_and_mixed_metadata_rejection(self):
        self.check_candidate_closed_copy(runner.binding.CANDIDATE_1029)

    def test_candidate_1030_closed_copy_and_mixed_metadata_rejection(self):
        self.check_candidate_closed_copy(runner.binding.CANDIDATE_1030)

    def test_renderer_fix_1030_closed_copy_rejects_same_version_previous_build(self):
        self.check_candidate_closed_copy(runner.binding.CANDIDATE_1030_RENDERER_FIX)


    def test_final_1030_closed_copy_rejects_same_version_previous_build(self):
        self.check_candidate_closed_copy(runner.binding.CANDIDATE_1030_FINAL)

    def check_candidate_closed_copy(self, candidate):
        request,path,output,package=self.prepare(True, disabled_low_signal=True)
        request['candidate_commit']=candidate.commit
        request['shutdown_expectation']['build_git_commit']=candidate.commit
        reference=Path(request['configuration_reference'])
        config=json.loads(reference.read_bytes())
        config['snapshot']['build_git_commit']=candidate.commit
        fingerprint=fixtures.inputs.configuration.canonical_fingerprint(config['snapshot'])
        for key in ('spot_config_fingerprint_sha256','spot_config_verified_fingerprint_sha256'):
            config['snapshot'][key]=fingerprint
        if config['snapshot']['device_config_readback_status']=='matched':
            config['snapshot']['device_config_fingerprint_sha256']=fingerprint
        fixtures.save(reference,config)
        request['configuration_reference_sha256']=fixtures.fact(reference)['sha256']
        metadata_path=Path(request['data_root'])/request['roles']['metadata']
        metadata=json.loads(metadata_path.read_bytes())
        metadata['schema_metadata']['git_commit']=candidate.commit
        metadata['spot_configuration_snapshot']=config['snapshot']
        fixtures.save(metadata_path,metadata)
        request['expected_files'][metadata_path.name]=fixtures.fact(metadata_path)
        fixtures.save(path,request)
        code,receipt=self.invoke(path,output,package)
        self.assertEqual(code,0,receipt)
        self.assertEqual(receipt['formal_qa_gate'],'HOLD')
        self.assertFalse(receipt['promotion_allowed'])
        mixed=self.folder/'mixed';mixed.mkdir()
        request['shutdown_expectation']['build_git_commit']=(runner.binding.CANDIDATE_1030.commit
            if candidate in (runner.binding.CANDIDATE_1030_FINAL, runner.binding.CANDIDATE_1030_RENDERER_FIX) else runner.binding.CANDIDATE_1029.commit
            if candidate==runner.binding.CANDIDATE_1030 else runner.binding.BUILD)
        fixtures.save(path,request)
        code,receipt=self.invoke(path,mixed,package)
        self.assertEqual(code,1,receipt)
        self.assertFalse((mixed/'session/closed-data/checks').exists())


if __name__ == '__main__':
    unittest.main()
