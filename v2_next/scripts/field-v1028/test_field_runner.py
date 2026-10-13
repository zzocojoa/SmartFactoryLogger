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

    def prepare(self, synthetic=False):
        helper = fixtures.ClosedDataTests()
        helper.folder = self.folder
        folder, data, roles, images = helper.prepare()
        expected, reference, sha = helper.reference(folder, data, roles, synthetic)
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
        with redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main([]),1)
            self.assertEqual(runner.main(['--describe','--request','anything']),1)

    def test_observation_duration_and_reference_are_fixed(self):
        spec={f.name:None for f in runner.fields(runner.observation.ObservationSpec)}
        for role in ('main','backend'):spec[role]={f.name:None for f in runner.fields(runner.ProcessIdentity)}
        spec['reference_sha256']=runner.binding.REFERENCE_SHA
        request=dict(schema=runner.SCHEMA,mode='observe',candidate_commit=runner.binding.BUILD,
                     signature_policy='UNSIGNED_INTERNAL',duration_seconds=900,spec=spec)
        self.assertEqual(runner.validate_request(request),'observe')
        request['duration_seconds']=7200;self.assertEqual(runner.validate_request(request),'observe')
        for value in (420,1,True,7201):
            request['duration_seconds']=value
            with self.assertRaises(ValueError):runner.validate_request(request)
        request['duration_seconds']=900;spec['reference_sha256']='a'*64
        with self.assertRaises(ValueError):runner.validate_request(request)


if __name__ == '__main__':
    unittest.main()
