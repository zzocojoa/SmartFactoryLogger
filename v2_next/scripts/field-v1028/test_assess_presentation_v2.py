import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import assess_presentation_v2 as reader
from test_assess_presentation_capture import fixture as old_fixture, LOGGER, POLICY as PREVIOUS_POLICY


POLICY=PREVIOUS_POLICY.with_name('approved_release_policy_20261026_three_pc.json')

def fixture(policy):
    captures, bindings, screen = old_fixture(policy)
    for c,b in zip(captures,bindings):
        c['schema'], c['context'] = reader.CONTEXTS[b['role']]
        c['collector_sha256'] = c['observer_revision_sha256'] = reader.COLLECTOR_SHA
        raw=c['observation'];raw['schema']='sfl-image-presentation-v2'
        raw['context']=c['context'] if b['role']=='browser' else 'UNSPECIFIED'
        dom=raw['dom'];dom.update(schema='sfl-presentation-dom-v2',contract_revision=2,installed_at_ms=0,
            readiness_limit_ms=10000,requested_duration_ms=900000,early_stop=False,
            window_start_ms=500,window_end_ms=900500,object_urls=[],requests=[])
        for r,l,p in zip(dom['responses'],dom['loads'],dom['paints']):
            stamp=p['presentationTime'];r.update(consumed=True,request_started_ms=stamp-100,at=stamp-50)
            r['sha256']='a'*64;l['sha256']='a'*64;l['response_id']=r['id']
            dom['requests'].append({'id':r['id'],'started_ms':r['request_started_ms'],'status':'RESPONSE','response_id':r['id']})
            dom['object_urls'].append({'url':l['url'],'response_id':r['id'],'at':stamp-30})
        first=dom['loads'][0]
        dom['boundary']={'url':first['url'],'response_id':first['response_id'],'presentation_time_ms':500}
        dom['states']=[{'at':t,'visible':True,'focused':True,'dom_occluded':False,'dom_present':True,
                        'load_complete':False,'natural_width':200} for t in range(0,900701,100)]
    captures,bindings=captures[:3],bindings[:3]
    screen['schema']='sfl-field-screen-confirmation-v2'
    screen['all_clients_visible_during_each_capture']=screen.pop('all_four_visible_during_each_capture')
    for key in ['client_run_ids','physical_client_map','white_screen_events']:screen[key].pop('PC_4')
    return captures,bindings,screen


class PresentationV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=reader.load_policy(POLICY,reader.POLICY_SHA)
        cls.base=fixture(cls.policy)

    def setUp(self):
        self.captures,self.bindings,self.screen=copy.deepcopy(self.base)

    def result(self):
        return reader.assess_group(self.captures,self.bindings,self.screen,LOGGER,self.policy)

    def test_identical_bytes_direct_lineage_is_component_pass(self):
        result=self.result();self.assertEqual(result['status'],'PASS',result)
        self.assertEqual(result['release_gate'],'HOLD');self.assertIs(result['promotion_allowed'],False)

    def test_collector_pin_and_cli_input_binding(self):
        source=Path(reader.__file__).with_name('presentation_v2.cjs')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),reader.COLLECTOR_SHA)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/PREVIOUS_POLICY.name).write_bytes(PREVIOUS_POLICY.read_bytes())
            def save(name,value):
                p=root/name;p.write_text(json.dumps(value),encoding='utf-8')
                return {'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            clients=[{**b,**save(b['client_id']+'.json',c)} for b,c in zip(self.bindings,self.captures)]
            index={'schema':'sfl-three-client-capture-index-v2','logger':LOGGER,'clients':clients,
                   'screen_confirmation':save('screen.json',self.screen)}
            pin=save('index.json',index);out=root/'out.json'
            args=[sys.executable,str(Path(reader.__file__)),'--index',str(root/'index.json'),
                  '--index-sha256',pin['sha256'],'--policy',str(POLICY),'--out',str(out)]
            run=subprocess.run(args,text=True,capture_output=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(json.loads(out.read_text())['status'],'PASS')
            original=out.read_bytes()
            retry=subprocess.run(args,text=True,capture_output=True,timeout=30)
            self.assertNotEqual(retry.returncode,0);self.assertEqual(out.read_bytes(),original)
            (root/'PC_2.json').write_text('{}',encoding='utf-8')
            args[-1]=str(root/'bad.json')
            bad=subprocess.run(args,text=True,capture_output=True,timeout=30)
            self.assertNotEqual(bad.returncode,0);self.assertFalse((root/'bad.json').exists())

    def test_no_two_pc_or_same_physical_pc_or_missing_screen_pass(self):
        self.captures.pop();self.assertEqual(self.result()['status'],'INCOMPLETE')
        self.setUp();self.bindings[2]['physical_id']=self.bindings[1]['physical_id']
        self.assertEqual(self.result()['status'],'INCOMPLETE')
        self.setUp();self.screen=None;self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_missing_changed_or_duplicated_lineage_is_incomplete(self):
        cases=[lambda d:d['object_urls'].pop(3), lambda d:d['loads'][3].update(response_id='missing'),
               lambda d:d['responses'][3].update(sha256='b'*64),lambda d:d['responses'].append(d['responses'][3]),
               lambda d:d['paints'][3].pop('presentationTime'), lambda d:d['requests'][3].update(status='PENDING')]
        for f in cases:
            self.setUp();f(self.captures[1]['observation']['dom'])
            with self.subTest(mutation=f):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_loading_does_not_hide_actual_focus_or_visibility_gaps(self):
        self.assertEqual(self.result()['status'],'PASS')
        for key,value in [('visible',False),('focused',False),('dom_present',False),('dom_occluded',True)]:
            self.setUp();self.captures[1]['observation']['dom']['states'][100][key]=value
            with self.subTest(key=key):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_missing_state_interval_or_changed_boundary_never_passes(self):
        for kind in ['gap','start','short','early','contract','origin']:
            self.setUp();dom=self.captures[1]['observation']['dom']
            if kind=='gap':del dom['states'][100:130]
            if kind=='start':dom['window_start_ms']=1000;dom['window_end_ms']=901000
            if kind=='short':dom['window_end_ms']-=1
            if kind=='early':dom['early_stop']=True
            if kind=='contract':dom['contract_revision']=1
            if kind=='origin':dom['responses'][3]['url']='https://example.com/image'
            with self.subTest(kind=kind):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_positive_request_failure_is_failure_even_if_capture_incomplete(self):
        self.captures[1]['status']='CAPTURE_INCOMPLETE'
        self.captures[1]['observation']['dom']['requests'][3]['status']='FAILED'
        self.assertEqual(self.result()['status'],'FAIL')

    def test_preparation_refusal_is_not_reported_as_a_runtime_change(self):
        for key,status,reason in [('preflight','NOT_READY','screen-readiness'),
                                  ('manual_start','CANCELLED','manual-preparation')]:
            self.setUp();capture=self.captures[1]
            capture.pop('observation');capture.pop('after');capture['status']='CAPTURE_INCOMPLETE'
            capture[key]={'status':status}
            result=self.result()
            self.assertEqual(result['status'],'INCOMPLETE')
            self.assertEqual(result['clients'][1]['reason'],'measurement-not-started:'+reason)
        # Measured evidence is still evaluated; a stale preparation marker must
        # never hide a positively observed request failure.
        self.setUp();self.captures[1]['preflight']={'status':'NOT_READY'}
        self.captures[1]['observation']['dom']['requests'][3]['status']='FAILED'
        self.assertEqual(self.result()['status'],'FAIL')

    def test_runtime_revision_context_and_tail_gaps_preserve_policy(self):
        for kind in ['runtime','revision','context','raw-context','regressed-receipt']:
            self.setUp();c=self.captures[1]
            if kind=='runtime':c['after']['logger']='different'
            if kind=='revision':c['observer_revision_sha256']='0'*64
            if kind=='context':c['context']='HEADLESS_FIXTURE'
            if kind=='raw-context':c['observation']['context']='HEADLESS_FIXTURE'
            if kind=='regressed-receipt':c['observation']['responses'][3]['captured_at']=c['observation']['responses'][1]['captured_at']
            with self.subTest(kind=kind):self.assertEqual(self.result()['status'],'INCOMPLETE')
        self.setUp();d=self.captures[1]['observation']['dom'];d['loads']=d['loads'][:-4];d['paints']=d['paints'][:-4]
        self.assertEqual(self.result()['status'],'FAIL')
        self.setUp();self.screen['white_screen_events']['PC_2']=1;self.assertEqual(self.result()['status'],'FAIL')

    def test_repeat_is_not_fresh_and_does_not_hide_stall_or_conflict(self):
        raw=self.captures[1]['observation'];rows=raw['responses']
        rows[3]['captured_at']=rows[2]['captured_at']
        samples,_,_=reader.reconstruct(self.captures[1],self.bindings[1],LOGGER,self.policy)
        self.assertEqual(len(samples),len(rows)-1)
        self.assertEqual(self.result()['status'],'PASS')
        # A long repeat run must retain its entire elapsed gap, not synthesize updates.
        for row in rows[3:10]:row['captured_at']=rows[2]['captured_at']
        result=self.result();self.assertEqual(result['status'],'FAIL')
        self.assertIn('display-gap-exceeded',result['clients'][1]['failures'])
        self.setUp();raw=self.captures[1]['observation'];rows=raw['responses']
        for row in rows[-4:]:row['captured_at']=rows[-5]['captured_at']
        self.assertEqual(self.result()['status'],'FAIL','tail repeat must preserve boundary gap')
        self.setUp();raw=self.captures[1]['observation'];rows=raw['responses']
        rows[3]['captured_at']=rows[2]['captured_at'];rows[3]['sha256']='b'*64;raw['dom']['loads'][3]['sha256']='b'*64
        self.assertEqual(self.result()['status'],'INCOMPLETE','same receipt with different bytes is conflicting')


if __name__=='__main__':unittest.main()
