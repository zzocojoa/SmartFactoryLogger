"""Native clock joins, identity reuse rejection, and diagnostic failure isolation."""
import copy
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

import field_native_timing as timing
import field_http_sampling as sampling
from test_field_http_sampling import local_server


class NativeTimingTests(unittest.TestCase):
    def pair(self):
        first=timing.capture();time.sleep(.002);last=timing.capture()
        self.assertEqual(first['status'],'OBSERVED',first)
        self.assertEqual(last['status'],'OBSERVED',last)
        return first,last

    def test_native_identity_and_clock_bounds(self):
        first,last=self.pair()
        self.assertEqual(first['identity']['pid'],os.getpid())
        self.assertEqual(first['identity']['native_thread_id'],threading.get_native_id())
        result=timing.interval(first,last)
        self.assertEqual(result['status'],'CORRELATABLE_BOUNDARIES',result)
        self.assertLessEqual(result['qpc_offset_lower_ns'],result['qpc_offset_upper_ns'])
        # This runtime uses system QPC directly; test the observed mapping,
        # without assuming that all historical Python versions have zero offset.
        self.assertLessEqual(result['qpc_offset_lower_ns'],0)
        self.assertGreaterEqual(result['qpc_offset_upper_ns'],0)

    def test_thread_and_process_identities_are_distinct(self):
        main=timing.capture();samples=[]
        child=threading.Thread(target=lambda:samples.append(timing.capture()))
        child.start();child.join(5);self.assertFalse(child.is_alive())
        self.assertEqual(samples[0]['status'],'OBSERVED')
        self.assertEqual(samples[0]['identity']['process_created_filetime'],main['identity']['process_created_filetime'])
        self.assertNotEqual(samples[0]['identity']['native_thread_id'],main['identity']['native_thread_id'])
        self.assertEqual(timing.interval(main,samples[0])['status'],'UNAVAILABLE')
        completed=subprocess.run([sys._base_executable,'-S','-c',
            'import json,field_native_timing as t;print(json.dumps(t.capture()))'],
            cwd=os.path.dirname(timing.__file__),capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(completed.returncode,0,completed.stderr)
        other=json.loads(completed.stdout)
        self.assertEqual(other['status'],'OBSERVED',other)
        self.assertNotEqual(other['identity']['pid'],main['identity']['pid'])
        self.assertEqual(timing.interval(main,other)['status'],'UNAVAILABLE')

    def test_identity_reuse_frequency_and_invalid_fields_cannot_join(self):
        first,last=self.pair()
        for section,key,value in [('identity','process_created_filetime',1),('identity','thread_created_filetime',1),
                ('identity','pid',True),('identity','native_thread_id',0),
                ('boundary','qpc_frequency',1),('boundary','qpc_ticks',-1),
                ('boundary','perf_after_ns',float('nan')),('boundary','thread_cpu_ns',-1)]:
            changed=copy.deepcopy(last);changed[section][key]=value
            self.assertEqual(timing.interval(first,changed)['status'],'UNAVAILABLE',(section,key))
        for malformed in ({},None,{'schema':'wrong'}, {'identity':{}}):
            self.assertEqual(timing.interval(first,malformed)['status'],'UNAVAILABLE')

    def test_inconsistent_clock_and_reverse_order_cannot_join(self):
        first,last=self.pair()
        self.assertEqual(timing.interval(last,first)['status'],'UNAVAILABLE')
        changed=copy.deepcopy(last);changed['boundary']['qpc_ticks']+=changed['boundary']['qpc_frequency']*10
        self.assertEqual(timing.interval(first,changed)['reason'],'clock-offset-intervals-disjoint')
        changed=copy.deepcopy(last);changed['boundary']['thread_cpu_ns']=first['boundary']['thread_cpu_ns']-1
        self.assertEqual(timing.interval(first,changed)['status'],'UNAVAILABLE')

    def test_native_read_failure_retains_http_response_and_threshold_failure(self):
        with patch.object(timing,'_clock',side_effect=OSError('synthetic native read failure')):
            value=timing.capture();self.assertEqual(value['status'],'UNAVAILABLE')
            self.assertIsNone(value['boundary']);self.assertIsNotNone(value['error'])
            with local_server() as server:
                server.modes['/health']='slow'
                record,raw=sampling.fetch_sample(server.server_port,sampling.ENDPOINTS[0])
        self.assertEqual(raw,b'{"ok":true}');self.assertTrue(record['request_success'])
        self.assertEqual(record['native_timing']['status'],'UNAVAILABLE')
        record.update(sequence=0,start_lateness_ms=0)
        self.assertEqual(sampling.summarize_channel(sampling.ENDPOINTS[0],[record],1)['threshold_failures'],1)

    def test_disabled_diagnostic_makes_no_native_reads(self):
        with local_server() as server,patch.object(timing,'capture',side_effect=AssertionError('unexpected native call')):
            record,raw=sampling.fetch_sample(server.server_port,sampling.ENDPOINTS[0],include_native_timing=False)
        self.assertEqual(raw,b'{"ok":true}');self.assertTrue(record['request_success'])
        self.assertEqual(record['native_timing'],{'status':'DISABLED'})

    def test_request_boundaries_cover_network_and_exclude_decode(self):
        with local_server() as server:
            record,_=sampling.fetch_sample(server.server_port,sampling.ENDPOINTS[0])
        native=record['native_timing'];self.assertEqual(native['status'],'CORRELATABLE_BOUNDARIES',native)
        self.assertLessEqual(record['started_ns'],native['begin']['boundary']['perf_before_ns'])
        self.assertLessEqual(native['begin']['boundary']['perf_after_ns'],record['response_finished_ns'])
        self.assertLessEqual(record['response_finished_ns'],native['end']['boundary']['perf_before_ns'])
        self.assertLessEqual(native['end']['boundary']['perf_after_ns'],record['finished_ns'])


if __name__=='__main__':unittest.main(verbosity=2)
