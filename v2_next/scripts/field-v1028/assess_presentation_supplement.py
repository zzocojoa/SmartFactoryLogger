"""Read-only PC_2 supplement; retain original verdicts and separate generations.

The caller must hash-bind the original index, all captures, runtime reads and the
new user screen confirmation. This component never creates a screen confirmation,
modifies raw data, grants promotion, or asserts simultaneous instrumented windows.
"""
import re
from datetime import datetime

from assess_presentation_v2 import assess_group, reconstruct, POLICY_SHA
from assess_presentation_capture import ImageRequestFailure, require
from approved_release_assessment import assess_display


def utc(value):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(stamp.tzinfo is not None,'timezone-required')
    return stamp


def runtime_identity(record, policy):
    require(record.get('computer')=='DESKTOP-CIIT7LK' and record.get('server_changed') is False,
            'server-runtime-read-required')
    health=record['health'];spot=health['spot_temperature']
    require(health.get('running') is True and health.get('mode')=='REAL'
            and health.get('app_version')=='1.0.32'
            and spot.get('build_git_commit')==policy['candidate']['build_commit'], 'runtime-candidate')
    logger=spot['v2_4_operational']['logger_service_instance_id']
    require(isinstance(logger,str) and re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',logger),
            'runtime-logger')
    config=record['config']
    require(type(config.get('bytes')) is int and config['bytes']>0
            and re.fullmatch('[0-9a-f]{64}',config.get('sha256','')), 'runtime-config')
    processes=record['processes']
    require(len(processes)==5 and len({p['pid'] for p in processes})==5
            and sum(p.get('is_main') is True for p in processes)==1,'runtime-process-set')
    for process in processes:
        native=process['native_context']
        require(native.get('pid')==process['pid'] and native.get('elevated') is False
                and native.get('process_handle_retained') is True
                and native.get('user_sid')==record['sid'], 'runtime-native-context')
    return {'logger':logger,'config':config,'processes':sorted(
        [(p['pid'],p['native_context']['created_utc'],p['native_context']['path'],
          p['native_context']['session_id']) for p in processes])}


def assess_supplement(captures, bindings, screen, original_logger, policy, *,
                      original_runtime_before, original_runtime, capture, runtime_before,
                      runtime_after, transport_window, confirmation, accepted_exception=None,
                      capture_sha256=None):
    result={'schema':'sfl-three-client-presentation-supplement-v1','status':'INCOMPLETE',
            'scope':'PER_CLIENT_900_SECONDS_UNDER_THREE_CLIENT_LOAD',
            'same_instrumented_window':False,'clients':[],'errors':[],
            'release_gate':'HOLD','promotion_allowed':False}
    try:
        original=assess_group(captures,bindings,screen,original_logger,policy)
        result['original_assessment']=original
        if original['status']=='FAIL':result['status']='FAIL'
        require(not original['errors'],'original-binding-incomplete')
        indexed={b['client_id']:(c,b) for c,b in zip(captures,bindings)}
        verdicts={c['client_id']:c for c in original['clients']}
        require(set(verdicts)=={'PC_1','PC_2','PC_3'} and all(verdicts[k]['status']=='PASS' for k in ('PC_1','PC_3')),
                'retained-clients-must-pass')
        failed,binding=indexed['PC_2']
        require(failed.get('status')=='CAPTURE_INCOMPLETE' and 'observation' not in failed
                and failed.get('preflight',{}).get('status')=='NOT_READY',
                'only-unstarted-pc2-may-be-supplemented')
        require(capture.get('run_id') not in {c['run_id'] for c in captures},'new-run-required')
        old=runtime_identity(original_runtime,policy)
        before=runtime_identity(runtime_before,policy);after=runtime_identity(runtime_after,policy)
        require(original_runtime_before.get('status')=='OWNED_LOOPBACK_DEBUG_RUNTIME_READ'
                and original_runtime_before.get('computer')==original_runtime['computer']
                and original_runtime_before.get('logger')==original_logger
                and original_runtime_before.get('build')==policy['candidate']['build_commit']
                and original_runtime_before.get('config_sha256')==old['config']['sha256']
                and utc(original_runtime_before['utc'])<utc(original_runtime['observed_utc']),
                'original-runtime-context')
        require(old['logger']==original_logger and before==after,'runtime-binding-changed')
        require(old['config']==before['config'],'configuration-mismatch')
        before_at=utc(runtime_before['observed_utc']);after_at=utc(runtime_after['observed_utc'])
        require(after_at>before_at,'runtime-read-order')
        # The SSH launcher receipts and PC_2 browser run on the same development
        # PC. Never compare these to wall-clock values from the remote server.
        require(transport_window.get('clock_scope')=='DEVELOPMENT_PC_UTC'
                and utc(transport_window['before_completed_utc'])<=utc(capture['started_utc'])
                <utc(capture['ended_utc'])<=utc(transport_window['after_started_utc']),
                'runtime-reads-must-bracket-supplement')
        accepted_interval=None
        if accepted_exception is not None:
            e=accepted_exception
            require(e.get('schema')=='sfl-pc2-screen-exception-v1' and e.get('approved') is True
                    and e.get('approved_by')=='user' and bool(e.get('user_statement'))
                    and e.get('policy_sha256')==POLICY_SHA
                    and e.get('run_id')==capture['run_id'] and e.get('client_id')=='PC_2'
                    and re.fullmatch('[0-9a-f]{64}',capture_sha256 or '')
                    and e.get('capture_sha256')==capture_sha256
                    and e.get('scope')=='ONE_USER_CONFIRMED_OCCLUSION_ONLY'
                    and e.get('original_incomplete_preserved') is True,
                    'accepted-exception-binding')
            dom=capture['observation']['dom'];start=dom['window_start_ms'];end=dom['window_end_ms']
            intervals=[];loss=None
            for state in dom['states']:
                if not start<=state['at']<=end:continue
                if state.get('focused') is False and loss is None:loss=state['at']-start
                if state.get('focused') is True and loss is not None:
                    intervals.append([loss,state['at']-start]);loss=None
            if loss is not None:intervals.append([loss,end-start])
            accepted_interval=e.get('focus_interval_relative_ms')
            require(len(intervals)==1 and intervals[0]==accepted_interval,'exception-interval-mismatch')
            require(isinstance(confirmation,dict) and confirmation.get('pc2_visible_and_unobscured') is False
                    and confirmation.get('occlusion_confirmed') is True
                    and bool(confirmation.get('occlusion_user_statement')),'exception-screen-confirmation')
            result['accepted_exception']=e
            result['original_supplement_status']=capture['status']
            result['uninterrupted_physical_screen_pass']=False
        require(isinstance(confirmation,dict)
                and confirmation.get('schema')=='sfl-pc2-supplement-screen-confirmation-v1'
                and confirmation.get('confirmed_by')=='user'
                and isinstance(confirmation.get('user_statement'),str)
                and bool(confirmation['user_statement'].strip())
                and confirmation.get('run_id')==capture['run_id']
                and confirmation.get('physical_client_map')==screen['physical_client_map']
                and confirmation.get('all_three_viewing_during_capture') is True
                and (confirmation.get('pc2_visible_and_unobscured') is True or accepted_interval is not None),
                'supplement-screen-confirmation-required')
        samples,start,end=reconstruct(capture,binding,before['logger'],policy,
                                     accepted_focus_interval_ms=accepted_interval)
        decision=assess_display(samples,window_start_ms=start,window_end_ms=end,complete=True,
            white_screen_events=confirmation.get('white_screen_events'),policy=policy)
        decision['policy_id']=policy['policy_id']
        if accepted_interval is not None and decision['status']=='PASS':
            decision={**decision,'numeric_status':'PASS','status':'ACCEPTED_WITH_TEST_CONDITION_EXCEPTION'}
        for client in original['clients']:
            if client['client_id']=='PC_2':
                result['clients'].append({**decision,'client_id':'PC_2','run_id':capture['run_id'],
                    'logger':before['logger'],'frames':len(samples),'window_start_ms':start,'window_end_ms':end})
            else:result['clients'].append({**client,'logger':original_logger})
        result['configuration_sha256']=before['config']['sha256']
        result['original_unstarted_pc2_run_id']=failed['run_id']
        result['status']=decision['status']
    except ImageRequestFailure as error:
        result['status']='FAIL';result['errors'].append(str(error))
    except (KeyError,TypeError,ValueError,OverflowError) as error:
        result['errors'].append(str(error))
    return result
