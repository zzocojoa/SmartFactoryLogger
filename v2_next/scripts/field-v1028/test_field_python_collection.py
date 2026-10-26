"""Real loopback/installed-file fixture and actual py-spy under the owned job."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import threading
import unittest

import field_python_frames as frames
from field_host_sampling import WindowsProcessReader
from test_field_observation import fixture_app

ROOT = Path(os.environ['SFL_PYTHON_COLLECTION_TEST_ROOT'])
TOOL = Path(os.environ['SFL_PYTHON_FRAMES_FIXTURE_ROOT'])/'py-spy.exe'


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def check(self, mode='normal', *, cancel=False, wrong_generation=False):
        folder=ROOT/self._testMethodName;folder.mkdir()
        with fixture_app(folder, mode, disabled_low_signal=True, candidate=frames.binding.CANDIDATE_1030) as base:
            original=WindowsProcessReader().read(base.backend.pid)
            self.assertEqual(original['status'],'CAPTURED')
            spec=frames.PythonFrameSpec(**asdict(base), backend_created_filetime=original['created_100ns']+int(wrong_generation),tool=str(TOOL))
            # Restore nested immutable identities after dataclass serialization.
            spec=frames.PythonFrameSpec(**dict(spec.__dict__, main=base.main,backend=base.backend))
            stop=threading.Event();timer=threading.Timer(.8,stop.set) if cancel else None
            if timer:timer.start()
            try:
                result=frames.observation.supervise_observation(spec,folder/'out',duration_seconds=6,
                    preparation_timeout=30,finalization_timeout=20,stop_event=stop,_worker_target=frames.worker_entry)
            finally:
                if timer:timer.cancel();timer.join(2)
            self.assertFalse(result['worker_still_alive'])
            self.assertFalse(result['event_reader_still_alive'])
            self.assertEqual(result['job_after_cleanup']['active_processes'],0)
            self.assertEqual(result['release_gate'],'HOLD')
            self.assertFalse(result['promotion_allowed'])
            after=WindowsProcessReader().read(base.backend.pid)
            self.assertEqual(after['status'],'CAPTURED')
            self.assertEqual(after['created_100ns'],original['created_100ns'])
            worker=json.loads((folder/'out/worker-result.json').read_bytes())
        exit_record=json.loads((folder/'fixture-exit.json').read_bytes())
        self.assertEqual(exit_record['exit_code'],0)
        return folder,result,worker

    def test_three_snapshots_keep_runtime_and_configuration_binding(self):
        folder,result,worker=self.check()
        self.assertEqual(result['supervisor_status'],'PASS',result['errors'])
        self.assertEqual(worker['observation_status'],'PASS',worker['errors'])
        self.assertEqual(len(worker['samples']),3)
        for sample in worker['samples']:
            self.assertIn(sample['status'],('CAPTURED','PARTIAL'))
            observed=json.loads((folder/f"out/frames/sample-{sample['sequence']}/result.json").read_bytes())
            self.assertEqual(observed['reader_exit'],0)
            self.assertTrue(any(Path(frame['filename']).name=='backend.py'
                for thread in observed['parsed']['rows'] for frame in thread['frames']))

    def test_changed_configuration_does_not_promote_capture(self):
        _,result,worker=self.check('configuration-changed')
        self.assertEqual(result['supervisor_status'],'FAIL')
        self.assertEqual(worker['observation_status'],'FAIL')
        self.assertTrue(any(e['reason']=='frame-configuration-closeout' for e in worker['errors']))

    def test_cancelled_collection_preserves_target_and_fails(self):
        _,result,worker=self.check(cancel=True)
        self.assertEqual(result['supervisor_status'],'FAIL')
        self.assertTrue(worker['stop_requested'])

    def test_wrong_generation_never_starts_reader(self):
        folder,result,worker=self.check(wrong_generation=True)
        self.assertEqual(result['supervisor_status'],'FAIL')
        self.assertEqual(worker['samples'],[])
        self.assertFalse(list((folder/'out/frames').glob('sample-*')))


if __name__=='__main__':unittest.main()
