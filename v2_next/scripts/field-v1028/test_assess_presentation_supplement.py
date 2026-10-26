import copy
import unittest

import assess_presentation_supplement as supplement
import assess_presentation_v2 as reader
from test_assess_presentation_v2 import fixture, POLICY, LOGGER

NEW_LOGGER='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


def runtime(policy,logger,stamp):
    processes=[]
    for i in range(5):
        processes.append({'pid':100+i,'is_main':i==0,'native_context':{
            'pid':100+i,'created_utc':'2026-10-26T03:30:00Z','elevated':False,
            'process_handle_retained':True,'user_sid':'test-sid','path':'fixture.exe','session_id':4}})
    return {'computer':'DESKTOP-CIIT7LK','server_changed':False,'sid':'test-sid','observed_utc':stamp,
        'health':{'running':True,'mode':'REAL','app_version':'1.0.32','spot_temperature':{
            'build_git_commit':policy['candidate']['build_commit'],'v2_4_operational':{'logger_service_instance_id':logger}}},
        'config':{'bytes':10,'sha256':'a'*64},'processes':processes}


class SupplementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=reader.load_policy(POLICY,reader.POLICY_SHA)
        cls.base=fixture(cls.policy)

    def setUp(self):
        self.captures,self.bindings,self.screen=copy.deepcopy(self.base)
        capture=copy.deepcopy(self.captures[1]);capture['run_id']='SUPPLEMENT_PC2'
        for p in capture['observation']['dom']['paints']:p['identifier']=capture['run_id']
        capture['before']=capture['after']={'build':self.policy['candidate']['build_commit'],'logger':NEW_LOGGER}
        capture.update(started_utc='2026-10-26T03:40:00Z',ended_utc='2026-10-26T03:56:00Z')
        failed=self.captures[1];failed.pop('observation');failed.pop('after')
        failed.update(status='CAPTURE_INCOMPLETE',preflight={'status':'NOT_READY'})
        self.kw={'original_runtime_before':{'status':'OWNED_LOOPBACK_DEBUG_RUNTIME_READ',
            'computer':'DESKTOP-CIIT7LK','logger':LOGGER,'build':self.policy['candidate']['build_commit'],
            'config_sha256':'a'*64,'utc':'2026-10-26T03:00:00Z'},
            'original_runtime':runtime(self.policy,LOGGER,'2026-10-26T03:25:00Z'),'capture':capture,
            'runtime_before':runtime(self.policy,NEW_LOGGER,'2026-10-26T03:39:50Z'),
            'runtime_after':runtime(self.policy,NEW_LOGGER,'2026-10-26T03:56:15Z'),
            'transport_window':{'clock_scope':'DEVELOPMENT_PC_UTC','before_completed_utc':'2026-10-26T03:39:45Z',
                                'after_started_utc':'2026-10-26T03:56:10Z'},
            'confirmation':{'schema':'sfl-pc2-supplement-screen-confirmation-v1','confirmed_by':'user',
                'user_statement':'fixture only; three displays were visible','run_id':'SUPPLEMENT_PC2',
                'physical_client_map':copy.deepcopy(self.screen['physical_client_map']),
                'all_three_viewing_during_capture':True,'pc2_visible_and_unobscured':True,'white_screen_events':0}}

    def result(self):
        return supplement.assess_supplement(self.captures,self.bindings,self.screen,LOGGER,self.policy,**self.kw)

    def test_compatible_supplement_retains_original_and_separate_generations(self):
        prior=copy.deepcopy((self.captures,self.kw))
        result=self.result();self.assertEqual(result['status'],'PASS',result)
        self.assertEqual(result['original_assessment']['status'],'INCOMPLETE')
        self.assertFalse(result['same_instrumented_window']);self.assertFalse(result['promotion_allowed'])
        self.assertEqual(result['release_gate'],'HOLD')
        self.assertEqual([x['logger'] for x in result['clients']],[LOGGER,NEW_LOGGER,LOGGER])
        self.assertEqual((self.captures,self.kw),prior)

    def test_measured_original_failure_cannot_be_replaced(self):
        self.captures[1]=copy.deepcopy(self.base[0][1])
        self.captures[1]['observation']['dom']['requests'][2]['status']='FAILED'
        result=self.result();self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['original_assessment']['status'],'FAIL')
        self.assertIn('only-unstarted-pc2-may-be-supplemented',result['errors'])

    def test_failed_retained_peer_cannot_be_hidden(self):
        self.screen['white_screen_events']['PC_3']=1
        result=self.result();self.assertEqual(result['status'],'FAIL')
        self.assertIn('retained-clients-must-pass',result['errors'])

    def test_runtime_config_version_generation_and_process_changes_are_rejected(self):
        for kind in ('config','version','logger','process','elevated','old-config'):
            self.setUp();r=self.kw['runtime_after']
            if kind=='config':r['config']['sha256']='b'*64
            elif kind=='version':r['health']['app_version']='1.0.33'
            elif kind=='logger':r['health']['spot_temperature']['v2_4_operational']['logger_service_instance_id']=LOGGER
            elif kind=='process':r['processes'][2]['native_context']['created_utc']='2026-10-26T03:50:00Z'
            elif kind=='elevated':r['processes'][0]['native_context']['elevated']=True
            else:self.kw['original_runtime_before']['config_sha256']='b'*64
            with self.subTest(kind=kind):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_runtime_reads_must_bracket_capture_in_development_clock(self):
        self.kw['transport_window']['before_completed_utc']='2026-10-26T03:41:00Z'
        self.assertIn('runtime-reads-must-bracket-supplement',self.result()['errors'])
        self.setUp();self.kw['transport_window']['after_started_utc']='2026-10-26T03:55:00Z'
        self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_confirmation_must_bind_new_run_and_three_distinct_physical_clients(self):
        for kind in ('missing','old-run','two-displays','mapping','occluded'):
            self.setUp();c=self.kw['confirmation']
            if kind=='missing':self.kw['confirmation']=None
            elif kind=='old-run':c['run_id']=self.captures[1]['run_id']
            elif kind=='two-displays':c['all_three_viewing_during_capture']=False
            elif kind=='mapping':c['physical_client_map']['PC_3']=c['physical_client_map']['PC_2']
            else:c['pc2_visible_and_unobscured']=False
            with self.subTest(kind=kind):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_supplement_still_requires_full_window_focus_and_field_evidence(self):
        for kind in ('short','focus','context','collector'):
            self.setUp();c=self.kw['capture'];d=c['observation']['dom']
            if kind=='short':d['window_end_ms']-=1
            elif kind=='focus':d['states'][50]['focused']=False
            elif kind=='context':c['context']='HEADLESS_FIXTURE'
            else:c['observer_revision_sha256']='0'*64
            with self.subTest(kind=kind):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_positive_error_and_white_screen_remain_failures(self):
        self.kw['capture']['observation']['dom']['requests'][3]['status']='FAILED'
        self.assertEqual(self.result()['status'],'FAIL')

    def with_exception(self):
        capture=self.kw['capture'];dom=capture['observation']['dom'];start=dom['window_start_ms']
        for state in dom['states']:
            if 4000<=state['at']-start<32000:state['focused']=False
        capture['status']='CAPTURE_INCOMPLETE'
        capture['observation']['summary']={'incomplete':['visibility-focus-or-dom-occlusion',
            'not-field-context','independent-window-and-white-screen-evidence-required']}
        self.kw['confirmation'].update(pc2_visible_and_unobscured=False,occlusion_confirmed=True,
                                       occlusion_user_statement='fixture: chat covered the window')
        self.kw['capture_sha256']='b'*64
        self.kw['accepted_exception']={'schema':'sfl-pc2-screen-exception-v1','approved':True,
            'approved_by':'user','user_statement':'fixture explicit acceptance','policy_sha256':reader.POLICY_SHA,
            'run_id':capture['run_id'],'client_id':'PC_2','capture_sha256':'b'*64,
            'scope':'ONE_USER_CONFIRMED_OCCLUSION_ONLY','original_incomplete_preserved':True,
            'focus_interval_relative_ms':[4000,32000]}

    def test_accepted_exception_keeps_raw_and_strict_result_incomplete(self):
        self.with_exception();prior=copy.deepcopy(self.kw)
        with self.assertRaisesRegex(ValueError,'visibility-incomplete'):
            reader.reconstruct(self.kw['capture'],self.bindings[1],NEW_LOGGER,self.policy)
        result=self.result();self.assertEqual(result['status'],'ACCEPTED_WITH_TEST_CONDITION_EXCEPTION',result)
        self.assertEqual(result['clients'][1]['numeric_status'],'PASS')
        self.assertTrue(all(c['policy_id']==self.policy['policy_id'] for c in result['clients']))
        self.assertEqual(result['original_supplement_status'],'CAPTURE_INCOMPLETE')
        self.assertFalse(result['uninterrupted_physical_screen_pass']);self.assertFalse(result['promotion_allowed'])
        self.assertEqual(self.kw,prior)

    def test_exception_requires_exact_approval_capture_policy_and_interval(self):
        for key,value in [('approved',False),('approved_by','agent'),('capture_sha256','c'*64),
                          ('run_id','OTHER'),('policy_sha256','0'*64),('focus_interval_relative_ms',[0,900000]),
                          ('scope','ALL_FUTURE_RUNS'),('original_incomplete_preserved',False)]:
            self.setUp();self.with_exception();self.kw['accepted_exception'][key]=value
            with self.subTest(key=key):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_exception_does_not_accept_other_evidence_defects(self):
        for defect in ('hidden','dom-occluded','missing-focus','second-loss','short','body-mismatch','extra-incomplete','no-confirmation'):
            self.setUp();self.with_exception();c=self.kw['capture'];d=c['observation']['dom']
            if defect=='hidden':d['states'][100]['visible']=False
            elif defect=='dom-occluded':d['states'][100]['dom_occluded']=True
            elif defect=='missing-focus':d['states'][100].pop('focused')
            elif defect=='second-loss':d['states'][1000]['focused']=False
            elif defect=='short':d['window_end_ms']-=1
            elif defect=='body-mismatch':d['loads'][2]['sha256']='d'*64
            elif defect=='extra-incomplete':c['observation']['summary']['incomplete'].append('unknown')
            else:self.kw['confirmation']=None
            with self.subTest(defect=defect):self.assertEqual(self.result()['status'],'INCOMPLETE')

    def test_exception_does_not_hide_request_or_white_screen_failure(self):
        self.with_exception();self.kw['capture']['observation']['dom']['requests'][3]['status']='FAILED'
        self.assertEqual(self.result()['status'],'FAIL')
        self.setUp();self.with_exception();self.kw['confirmation']['white_screen_events']=1
        self.assertEqual(self.result()['status'],'FAIL')
        self.setUp();self.kw['confirmation']['white_screen_events']=1
        self.assertEqual(self.result()['status'],'FAIL')


if __name__=='__main__':unittest.main()
