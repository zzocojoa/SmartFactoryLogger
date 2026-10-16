"""Diagnostic collector contracts and isolated Windows/HTTP regression checks."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

import field_installation_binding as binding
import field_observation as observation
import field_runner as runner
import field_http_sampling as http
from field_host_sampling import WindowsProcessReader
from test_field_http_sampling import local_server
import test_field_observation as fixture

ROOT = Path(os.environ['SFL_TIMING_OBSERVATION_TEST_ROOT'])

# Synthetic server uses real native clocks in two real threads. It exercises
# collector propagation/binding, not installed application performance.
TIMING_SOURCE = '''
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, CLOCK_DIRECTORY)
from health_clock import capture_health_clock
executor=ThreadPoolExecutor(max_workers=1)
def diagnostic_header(probe):
 value=dict(v=2,probe_id=probe,pid=os.getpid(),loop_tid=threading.get_native_id(),
            worker_tid=0,clock='perf_counter_ns',checkpoints={},native={})
 points,native=value['checkpoints'],value['native']
 points['route_enter']=time.perf_counter_ns()
 native['loop_begin']=capture_health_clock()
 points['submitted']=time.perf_counter_ns()
 def work():
  value['worker_tid']=threading.get_native_id()
  points['worker_enter']=time.perf_counter_ns()
  native['worker_begin']=capture_health_clock()
  if mode=='timing-slow': time.sleep(.23)
  for name in ('plc_done','runtime_done','frontend_done','worker_exit'):
   points[name]=time.perf_counter_ns()
  native['worker_end']=capture_health_clock()
 executor.submit(work).result()
 points['route_resume']=time.perf_counter_ns()
 native['loop_end']=capture_health_clock()
 return json.dumps(value,separators=(',',':'))
'''.replace('CLOCK_DIRECTORY', repr(str(Path(__file__).resolve().parents[2]/'backend/Observability')))


class TimingObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir()

    def setUp(self):
        self.folder = ROOT/self._testMethodName
        self.folder.mkdir()

    def request(self):
        data=asdict(observation.TimingObservationSpec('unused','unused',None,None,8000,
            reference_sha256=binding.REFERENCE_SHA_1029, candidate_commit=binding.CANDIDATE_1029.commit,
            backend_created_filetime=123))
        for role in ('main','backend'):
            data[role]=dict(pid=1,created=1.0,exe='unused')
        return dict(schema=runner.SCHEMA,mode='timing-observe',signature_policy='UNSIGNED_INTERNAL',
            candidate_commit=binding.CANDIDATE_1029.commit,duration_seconds=900,spec=data)

    def test_explicit_mode_candidate_native_generation_and_budget(self):
        request=self.request()
        self.assertEqual(runner.validate_request(request),'timing-observe')
        for change in ('ordinary','old-build','boolean-native','missing-native','zero-native','large-native','long-window'):
            bad=deepcopy(request)
            if change=='ordinary':bad['mode']='observe'
            elif change=='old-build':
                bad['candidate_commit']=bad['spec']['candidate_commit']=binding.BUILD
                bad['spec']['reference_sha256']=binding.REFERENCE_SHA
            elif change=='boolean-native':bad['spec']['backend_created_filetime']=True
            elif change=='missing-native':del bad['spec']['backend_created_filetime']
            elif change=='zero-native':bad['spec']['backend_created_filetime']=0
            elif change=='large-native':bad['spec']['backend_created_filetime']=2**64
            else:bad['duration_seconds']=7200
            with self.subTest(change=change),self.assertRaises(ValueError):runner.validate_request(bad)

    def test_progress_records_enqueue_delay_and_does_not_hide_missed_slots(self):
        original=http.queue.Queue.put_nowait
        fired=threading.Event()
        def delayed(queue,item):
            if item[0]=='image' and not fired.is_set():
                fired.set();time.sleep(.3)
            return original(queue,item)
        output=self.folder/'http'
        with local_server() as server,patch.object(http.queue.Queue,'put_nowait',delayed):
            result=http.collect_http_window(server.server_port,output,duration_seconds=1,
                                             diagnostic_timing=True)
        self.assertEqual(result['http_component_status'],'FAIL')
        self.assertGreaterEqual(result['channels']['image']['missed_slots'],1)
        progress=json.loads((output/'progress.json').read_bytes())
        first=progress['channels']['image'][0]
        self.assertGreaterEqual(first['enqueue_return_ns']-first['lock_acquired_ns'],290_000_000)
        self.assertEqual(observation.review_progress(output,result['origin_ns'],1)['status'],
                         'REQUEST_AND_WORKER_PROGRESS_BOUND')
        self.assertEqual(result['persistence']['discarded_records'],0)
        self.assertFalse(result['promotion_allowed'])
        # A mismatched progress timestamp must not silently bind to a raw request.
        progress['channels']['image'][0]['queued_ns']+=1
        (output/'progress.json').write_text(json.dumps(progress),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'timing-progress-request-binding'):
            observation.review_progress(output,result['origin_ns'],1)

    def test_default_mode_has_no_diagnostic_headers_or_progress(self):
        with local_server() as server:
            http.collect_http_window(server.server_port,self.folder/'http',duration_seconds=.3)
        self.assertFalse((self.folder/'http/progress.json').exists())
        health=json.loads((self.folder/'http/health-00000.json').read_bytes())
        self.assertNotIn('health_probe_id',health)

    def run_isolated(self, *, mode='normal', timing=True, wrong_generation=False):
        source=fixture.BACKEND_SOURCE
        if timing:
            source=source.replace('class Handler',TIMING_SOURCE+'\nclass Handler')
            source=source.replace("self.send_response(status);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)",
                "self.send_response(status);self.send_header('Content-Length',str(len(body)))\n"
                "  if self.path=='/health' and self.headers.get('X-SFL-Health-Probe'):\n"
                "   self.send_header('X-SFL-Health-Timing',diagnostic_header(self.headers['X-SFL-Health-Probe']))\n"
                "  self.end_headers();self.wfile.write(body)")
        with patch.object(fixture,'BACKEND_SOURCE',source),fixture.fixture_app(self.folder,mode,
                candidate=binding.CANDIDATE_1029,disabled_low_signal=True) as spec:
            native=WindowsProcessReader().read(spec.backend.pid)
            data=dict(spec.__dict__, backend_created_filetime=native['created_100ns']+int(wrong_generation))
            timed=observation.TimingObservationSpec(**data)
            result=observation.supervise_observation(timed,self.folder/'out',duration_seconds=2.2)
            worker,_=observation.read_json(self.folder/'out/worker-result.json')
            self.assertEqual(result['job_after_cleanup']['active_processes'],0)
            self.assertEqual(worker['scope'],'TIMING_DIAGNOSTIC_NOT_FIELD_PERFORMANCE')
            self.assertEqual(worker['formal_qa_gate'],'HOLD')
            self.assertFalse(worker['promotion_allowed'])
            self.assertEqual(binding.read_process_binding(spec.main,spec.backend,spec.port)['main']['pid'],spec.main.pid)
            return result,worker,timed

    def test_real_owned_collectors_bind_native_timings_and_worker_progress(self):
        result,worker,_=self.run_isolated()
        self.assertEqual(result['supervisor_status'],'PASS',worker)
        timings=worker['review']['diagnostic_timings']
        self.assertEqual(len(timings),2)
        self.assertTrue(all(row['validation']['status']=='REQUEST_AND_NATIVE_CLOCK_BOUND' for row in timings))
        first=json.loads((self.folder/'out/http/health-00000.json').read_bytes())
        second=json.loads((self.folder/'out/http/health-00001.json').read_bytes())
        self.assertNotEqual(first['health_probe_id'],second['health_probe_id'])

    def test_slow_diagnostic_requests_remain_threshold_failures(self):
        result,worker,_=self.run_isolated(mode='timing-slow')
        self.assertEqual(result['supervisor_status'],'FAIL')
        timings=worker['review']['diagnostic_timings']
        self.assertTrue(all(row['validation']['status']=='REQUEST_AND_NATIVE_CLOCK_BOUND' for row in timings))
        self.assertTrue(all(row['request_ms']>200 for row in timings))
        self.assertTrue(all(row['validation']['stages_ns']['plc_done']>=220_000_000 for row in timings))
        self.assertIn('all-health-including-boundaries-failed',worker['review']['issues'])

    def test_missing_header_fails_binding_and_preserves_raw_evidence(self):
        result,worker,_=self.run_isolated(timing=False)
        self.assertEqual(result['supervisor_status'],'FAIL')
        self.assertIn('health-0-timing-not-bound',worker['review']['issues'])
        self.assertTrue((self.folder/'out/http/health-00000.body').is_file())

    def test_wrong_native_generation_prevents_window(self):
        result,worker,_=self.run_isolated(wrong_generation=True)
        self.assertEqual(result['supervisor_status'],'FAIL')
        self.assertFalse((self.folder/'out/http').exists())
        self.assertEqual(worker['errors'][0]['reason'],'timing-observation-native-generation-changed')

    def test_native_required_before_creating_output(self):
        with self.assertRaises(ValueError):
            http.collect_http_window(8000,self.folder/'out',duration_seconds=1,
                                     diagnostic_timing=True,include_native_timing=False)
        self.assertFalse((self.folder/'out').exists())


if __name__=='__main__':
    unittest.main(verbosity=2)
