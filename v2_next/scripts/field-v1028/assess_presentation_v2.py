"""Reconstruct v2 object lineage under the user's amended three-PC policy.

Read-only component decision. Preparation records stay in the capture; a complete
900-second display interval begins at the first bound presentation, never a later
chosen good interval. Physical display confirmation remains a separate input.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from assess_presentation_capture import (
    ImageRequestFailure, POLICY_SHA as PREVIOUS_POLICY_SHA, read_pinned, records, require,
)
from approved_release_assessment import assess_display, load_policy as load_previous_policy, numeric

COLLECTOR_SHA = 'c793c5da494a26983578b204057e7f0ac68193e6bbb09be1ce6300bfeec4ef6f'
POLICY_SHA = 'd6eadd712409f0a707eb10af0c1d1ae8adf655b2b8e5acca8d29bb41a42eab99'
CONTEXTS = {
    'server': ('sfl-presentation-run-v2', 'FIELD_CONNECTION_NOT_VISUALLY_ATTESTED'),
    'browser': ('sfl-portable-presentation-run-v2', 'FIELD_BROWSER_NOT_VISUALLY_ATTESTED'),
}


def load_policy(path, expected_sha):
    require(expected_sha==POLICY_SHA,'approved-three-client-policy-pin')
    policy=read_pinned(path,expected_sha)
    previous=load_previous_policy(Path(path).with_name('approved_release_policy_20261023.json'),PREVIOUS_POLICY_SHA)
    require(policy.get('schema')==previous['schema'] and policy.get('policy_id')=='c32-three-clients-20261026'
            and policy.get('approval',{}).get('approved') is True
            and policy['approval'].get('user_statement')=='계속 총 3대만 가능, 해당 기준으로 변경'
            and policy.get('previous_policy',{}).get('sha256')==PREVIOUS_POLICY_SHA,'three-client-approval')
    for key in ('candidate','low_signal','operational_criteria','historical_data','rollback'):
        require(policy.get(key)==previous[key],'unapproved-policy-change-'+key)
    contract={**previous['observation_contract'],'physical_clients':3}
    require(policy.get('observation_contract')==contract,'three-client-contract-only')
    return policy


def reconstruct(capture, binding, logger, policy, *, accepted_focus_interval_ms=None):
    role=binding['role'];schema,context=CONTEXTS[role]
    require(capture.get('schema')==schema and capture.get('context')==context,'not-approved-field-capture-context')
    require(capture.get('client_id')==binding['client_id'] and isinstance(capture.get('run_id'),str)
            and re.fullmatch('[A-Za-z0-9_-]{1,80}',capture['run_id']),'client-run-binding')
    require(capture.get('collector_sha256' if role=='server' else 'observer_revision_sha256')==COLLECTOR_SHA,'collector-revision')
    require(capture.get('page_url')==binding['page_url'],'page-binding')
    origin=binding['image_origin']
    if role=='browser':
        require(origin=='http://192.168.0.7:8000' and binding['page_url']==origin+'/dashboard','browser-target')
    else:
        require(urlsplit(binding['page_url']).scheme=='file' and origin in ('http://127.0.0.1:8000','http://localhost:8000'),'server-target')
    # A pre-capture refusal has no after identity. Do not misreport that absence
    # as evidence that the running application actually changed generation.
    if capture.get('status')=='CAPTURE_INCOMPLETE' and 'observation' not in capture:
        if capture.get('preflight',{}).get('status')=='NOT_READY':
            raise ValueError('measurement-not-started:screen-readiness')
        if capture.get('manual_start',{}).get('status') in ('NOT_READY','CANCELLED'):
            raise ValueError('measurement-not-started:manual-preparation')
    identity={'build':policy['candidate']['build_commit'],'logger':logger}
    require(capture.get('before')==identity and capture.get('after')==identity,'runtime-generation')
    raw=capture['observation'];dom=raw['dom']
    require(raw.get('schema')=='sfl-image-presentation-v2' and dom.get('schema')=='sfl-presentation-dom-v2'
            and dom.get('contract_revision')==2,'v2-contract-required')
    require(raw.get('context')==(context if role=='browser' else 'UNSPECIFIED'),'raw-field-context')
    if role=='server':
        require(raw.get('page_url')==binding['page_url'] and raw.get('run_id')==capture['run_id'],'server-page-run')
    require(policy['observation_contract']['image_display_window_seconds']==900,'approved-display-window')
    result=_reconstruct_observation(raw,capture['run_id'],origin,policy,expected_duration_ms=900000,
                                   accepted_focus_interval_ms=accepted_focus_interval_ms)
    expected_status='CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE'
    if accepted_focus_interval_ms is not None:
        expected_status='CAPTURE_INCOMPLETE'
        require(set(raw.get('summary',{}).get('incomplete',[]))=={
            'visibility-focus-or-dom-occlusion','not-field-context',
            'independent-window-and-white-screen-evidence-required'},'unexpected-capture-incompleteness')
    require(capture.get('status')==expected_status
            and not any(capture.get(k) for k in ('error','cleanup_error','disconnect_error')),'capture-incomplete')
    return result


def _reconstruct_observation(raw, run_id, origin, policy, *, expected_duration_ms,
                             accepted_focus_interval_ms=None):
    """Shared raw join; does not attest a field context, runtime, or release."""
    dom=raw['dom']
    require(raw.get('schema')=='sfl-image-presentation-v2' and dom.get('schema')=='sfl-presentation-dom-v2'
            and dom.get('contract_revision')==2,'v2-contract-required')
    responses=records(raw.get('responses'),'responses');requests=records(dom.get('requests'),'requests')
    require(responses==dom.get('responses'),'dom-response-mismatch')
    errors=raw.get('errors');dom_errors=dom.get('errors')
    require(isinstance(errors,list) and isinstance(dom_errors,list),'error-records-required')
    # Positive request errors are failures, even if other measurements are missing.
    if any(r.get('status')=='FAILED' for r in requests) or any(str(x).startswith('image-request-failed') for x in errors+dom_errors):
        raise ImageRequestFailure('image-request-failed')
    for r in responses:
        u=urlsplit(r['url']);require(f'{u.scheme}://{u.netloc}'==origin and u.path=='/api/spot/live_image.jpg','response-target')
        if type(r.get('status')) is int and r['status']!=200:raise ImageRequestFailure('image-http-error')
    require(errors==dom_errors==[],'capture-incomplete')
    require(dom.get('stopped') is True and dom.get('overflow') is False and dom.get('early_stop') is False
            and type(dom.get('pending')) is int and dom['pending']==0,'dom-incomplete')
    start,end,installed=dom['window_start_ms'],dom['window_end_ms'],dom['installed_at_ms']
    require(all(numeric(x) for x in (start,end,installed)) and dom.get('clock')=='PAGE_MONOTONIC_MS'
            and installed<=start and dom.get('readiness_limit_ms')==10000 and start-installed<=10000
            and dom.get('requested_duration_ms')==expected_duration_ms and end-start==expected_duration_ms,'full-monotonic-window-required')
    boundary=dom['boundary'];require(isinstance(boundary,dict) and boundary.get('presentation_time_ms')==start,'boundary-binding')
    by_id={};by_request={};by_url=defaultdict(list);by_paint=defaultdict(list)
    for r in requests:
        require(isinstance(r.get('id'),str) and r['id'] and r['id'] not in by_request
                and numeric(r.get('started_ms')) and r['started_ms']>=installed,'request-identity')
        if r['started_ms']<=end:require(r.get('status')=='RESPONSE' and r.get('response_id')==r['id'],'unfinished-request')
        by_request[r['id']]=r
    for r in responses:
        require(isinstance(r.get('id'),str) and r['id'] and r['id'] not in by_id,'response-identity')
        q=by_request.get(r['id']);require(q is not None and q.get('status')=='RESPONSE'
            and q.get('response_id')==r['id'] and r.get('request_started_ms')==q['started_ms']
            and numeric(r.get('at')) and r['at']>=q['started_ms'],'response-request-binding')
        by_id[r['id']]=r
    for q in requests:
        if q['started_ms']<=end:require(q['id'] in by_id,'missing-response')
    for row in records(dom.get('object_urls'),'object-urls'):
        require(isinstance(row.get('url'),str) and row['url'].startswith('blob:') and numeric(row.get('at')),'object-url')
        by_url[row['url']].append(row)
    for paint in records(dom.get('paints'),'paints'):
        require(paint.get('identifier')==run_id and paint.get('entryType')=='element','paint-provenance')
        by_paint[paint.get('url')].append(paint)
    loads=records(dom.get('loads'),'loads');candidates=[]
    for l in loads:
        require(numeric(l.get('at')),'load-clock')
        if not l.get('error') and l.get('response_id') in by_id:
            for p in by_paint[l.get('url')]:
                if numeric(p.get('presentationTime')) and p['presentationTime']>0:
                    candidates.append(p['presentationTime'])
    require(candidates and min(candidates)==start,'first-bound-presentation-required')
    states=records(dom.get('states'),'states')
    require(states and all(numeric(s.get('at')) for s in states)
            and all(a['at']<=b['at'] for a,b in zip(states,states[1:]))
            and states[0]['at']<=start and states[-1]['at']>=end,'visibility-window-not-covered')
    measured=[s for s in states if start<=s['at']<=end]
    def focus_qualified(state):
        if state.get('focused') is True:return True
        if state.get('focused') is not False or accepted_focus_interval_ms is None:return False
        return accepted_focus_interval_ms[0]<=state['at']-start<accepted_focus_interval_ms[1]
    if accepted_focus_interval_ms is not None:
        require(isinstance(accepted_focus_interval_ms,list) and len(accepted_focus_interval_ms)==2
                and all(numeric(x) for x in accepted_focus_interval_ms)
                and 0<=accepted_focus_interval_ms[0]<accepted_focus_interval_ms[1]<=expected_duration_ms,
                'invalid-accepted-focus-interval')
    require(measured and all(s.get('visible') is True and focus_qualified(s)
            and s.get('dom_occluded') is False and s.get('dom_present') is True for s in measured),'visibility-incomplete')
    stamps=[start,*[s['at'] for s in measured],end]
    # Evidence quality: a gap at least as long as a prohibited display freeze
    # cannot substantiate absence of that freeze. This is not a new latency SLO.
    require(max(b-a for a,b in zip(stamps,stamps[1:]))<policy['operational_criteria']['image_display_gap_failure_ms_inclusive'],
            'state-observation-gap')
    samples=[];last_source=None;last_hash=None;used_response_ids=set();boundary_seen=False
    for l in loads:
        if l['at']>end or (l['at']<start and l.get('url')!=boundary.get('url')):continue
        response=by_id.get(l.get('response_id'));objects=by_url[l.get('url')];paints=by_paint[l.get('url')]
        require(not l.get('error') and response and len(objects)==len(paints)==1,'response-blob-presentation-unbound')
        obj,paint=objects[0],paints[0]
        require(obj.get('response_id')==response['id'] and response['at']<=obj['at']<=l['at'],'object-response-binding')
        require(response.get('consumed') is True and not response.get('error')
                and re.fullmatch('[0-9a-f]{64}',l.get('sha256','')) and l['sha256']==response.get('sha256'),'response-blob-bytes-mismatch')
        source=response.get('captured_at')
        require(isinstance(source,str) and numeric(float(source)) and float(source)>0
                and response['id'] not in used_response_ids,'source-identity')
        stamp=paint.get('presentationTime')
        require(all(numeric(paint.get(k)) for k in ('loadTime','presentationTime','observed_at'))
                and 0<stamp and paint['loadTime']<=stamp<=paint['observed_at'] and stamp>=obj['at'],'presentation-clock')
        used_response_ids.add(response['id'])
        source_number=float(source)
        require(last_source is None or source_number>last_source
                or (source_number==last_source and l['sha256']==last_hash),'source-identity-conflict')
        repeated=source_number==last_source
        last_source,last_hash=source_number,l['sha256']
        if l['url']==boundary.get('url'):
            require(response['id']==boundary.get('response_id') and stamp==start,'boundary-identity');boundary_seen=True
        if stamp>end:continue
        require(stamp>=start,'presentation-before-window')
        # A repeated receipt is not a fresh frame. Its elapsed time remains in
        # the next fresh-frame interval, including the final boundary gap.
        if repeated:continue
        samples.append({'presented_at_ms':stamp,'response_id':response['id'],'presentation_confirmed':True,
            'fresh_frame_identity_confirmed':True,'visible':paint.get('visible'),'occluded':paint.get('dom_occluded')})
    samples.sort(key=lambda s:s['presented_at_ms'])
    require(boundary_seen and len(samples)>=2,'insufficient-presentation-records')
    return samples,start,end


def assess_group(captures, bindings, screen, logger, policy):
    result = {'schema': 'sfl-three-client-presentation-assessment-v2', 'status': 'INCOMPLETE',
              'scope': 'THREE_CLIENT_DISPLAY_COMPONENT_ONLY', 'clients': [], 'errors': [],
              'release_gate': 'HOLD', 'promotion_allowed': False,
              'screen_evidence_kind': 'USER_CONFIRMATION_SEPARATE_FROM_BROWSER_TIMESTAMPS'}
    try:
        require(re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', logger), 'logger-id')
        require(len(captures) == len(bindings) == policy['observation_contract']['physical_clients'], 'three-clients-required')
        ids = [b['client_id'] for b in bindings]
        physical = [b['physical_id'] for b in bindings]
        require(set(ids) == {'PC_1', 'PC_2', 'PC_3'}
                and all(isinstance(v, str) and v.strip() for v in physical) and len(set(physical)) == 3,
                'distinct-physical-clients-required')
        require([b['role'] for b in bindings].count('server') == 1
                and [b['role'] for b in bindings].count('browser') == 2, 'one-server-two-browsers-required')
        run_ids = {b['client_id']: c['run_id'] for b, c in zip(bindings, captures)}
        require(len(set(run_ids.values())) == 3, 'distinct-capture-runs-required')
        require(isinstance(screen, dict) and screen.get('schema') == 'sfl-field-screen-confirmation-v2'
                and screen.get('confirmed_by') == 'user' and isinstance(screen.get('user_statement'), str)
                and bool(screen['user_statement'].strip()) and screen.get('client_run_ids') == run_ids
                and screen.get('physical_client_map') == dict(zip(ids, physical))
                and screen.get('all_clients_visible_during_each_capture') is True
                and screen.get('all_windows_unobscured') is True, 'missing-bound-user-screen-confirmation')
        # Each 900-second monotonic interval ran under three-client viewing load.
        # Browser wall clocks are not assumed synchronized across different PCs.
        for binding, capture in zip(bindings, captures):
            item = {'client_id': binding['client_id'], 'run_id': capture['run_id']}
            try:
                samples, start, end = reconstruct(capture, binding, logger, policy)
                item.update(assess_display(samples, window_start_ms=start, window_end_ms=end,
                    complete=True, white_screen_events=screen['white_screen_events'].get(binding['client_id']), policy=policy))
                item.update(policy_id=policy['policy_id'],frames=len(samples), window_start_ms=start, window_end_ms=end)
            except ImageRequestFailure as error:
                item.update(status='FAIL', failures=[str(error)], promotion_allowed=False)
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                item.update(status='INCOMPLETE', reason=str(error), promotion_allowed=False)
            result['clients'].append(item)
        states = [c['status'] for c in result['clients']]
        result['status'] = 'FAIL' if 'FAIL' in states else 'PASS' if all(s == 'PASS' for s in states) else 'INCOMPLETE'
    except (KeyError, TypeError, ValueError) as error:
        result['errors'].append(str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', required=True)
    parser.add_argument('--index-sha256', required=True)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    policy = load_policy(args.policy, POLICY_SHA)
    index = read_pinned(args.index, args.index_sha256)
    require(index.get('schema') == 'sfl-three-client-capture-index-v2', 'index-schema')
    parent = Path(args.index).resolve().parent
    def read_member(member):
        path = Path(member['path'])
        require(not path.is_absolute() and not path.drive and '..' not in path.parts, 'relative-member-required')
        require((parent / path).resolve().is_relative_to(parent), 'member-path-escape')
        return read_pinned(parent / path, member['sha256'])
    captures = [read_member(b) for b in index['clients']]
    screen = read_member(index['screen_confirmation']) if index.get('screen_confirmation') else None
    result = assess_group(captures, index['clients'], screen, index['logger'], policy)
    result['index_sha256'] = args.index_sha256
    result['policy_sha256'] = POLICY_SHA
    with Path(args.out).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'out': args.out, 'release_gate': 'HOLD'}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
