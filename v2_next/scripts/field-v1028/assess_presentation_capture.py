"""Join pinned C32 display captures; never infer field evidence from a fixture.

Index and screen confirmation are separate, hash-bound inputs. A confirmation
must describe actual user/field observations; this module never creates one.
Component PASS does not authorize release or change the rollback baseline.
"""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from approved_release_assessment import assess_display, load_policy, numeric

COLLECTOR_SHA = '947b976bec81b00bbf836fa24e233e40cfb0116ae9eb5eceacf532c6bc214bcc'
POLICY_SHA = '81122c28d6d5300c9f9c9eae5961e3661c9f775edc09e16ab108a5593bab5324'
CONTEXTS = {
    'browser': ('sfl-portable-presentation-run-v1', 'FIELD_BROWSER_NOT_VISUALLY_ATTESTED'),
    'server': ('sfl-presentation-run-v1', 'FIELD_CONNECTION_NOT_VISUALLY_ATTESTED'),
}


class ImageRequestFailure(ValueError):
    """A bound capture contains a positively observed request failure."""


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate-json-key')
        result[key] = value
    return result


def read_pinned(path, expected_sha):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'ordinary-input-file-required')
    require(path.stat().st_size <= 32 * 1024 * 1024, 'input-too-large')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == expected_sha, 'input-hash-mismatch')
    return json.loads(data.decode('utf-8-sig'), object_pairs_hook=strict_object,
                      parse_constant=lambda value: require(False, 'nonfinite-json-number'))


def records(value, label):
    require(isinstance(value, list) and len(value) <= 12000
            and all(isinstance(row, dict) for row in value), 'invalid-' + label)
    return value


def reconstruct(capture, binding, logger, policy):
    """Recompute joins from raw bytes/paint records; ignore supplied summaries."""
    role = binding['role']
    schema, context = CONTEXTS[role]
    require(capture.get('schema') == schema and capture.get('context') == context,
            'not-approved-field-capture-context')
    require(capture.get('client_id') == binding['client_id'], 'client-binding')
    require(isinstance(capture.get('run_id'), str) and capture['run_id'], 'missing-run-id')
    revision = capture.get('observer_revision_sha256' if role == 'browser' else 'collector_sha256')
    require(revision == COLLECTOR_SHA, 'collector-revision')
    require(capture.get('page_url', binding['page_url']) == binding['page_url'], 'page-binding')
    origin = binding['image_origin']
    if role == 'browser':
        require(binding['page_url'] == 'http://192.168.0.7:8000/dashboard'
                and origin == 'http://192.168.0.7:8000', 'browser-target')
    else:
        require(urlsplit(binding['page_url']).scheme == 'file'
                and origin in ('http://127.0.0.1:8000', 'http://localhost:8000'), 'server-target')
    identity = {'build': policy['candidate']['build_commit'], 'logger': logger}
    require(capture.get('before') == identity and capture.get('after') == identity, 'runtime-generation')
    raw = capture['observation']
    require(raw.get('schema') == 'sfl-image-presentation-v1', 'raw-schema')
    require(raw.get('context') == (context if role == 'browser' else 'UNSPECIFIED'), 'raw-field-context')
    if role == 'server':
        require(raw.get('page_url') == binding['page_url'] and raw.get('run_id') == capture['run_id'], 'server-page-run')
    network = records(raw.get('network_responses'), 'network')
    for row in network:
        u = urlsplit(row['url'])
        require(f'{u.scheme}://{u.netloc}' == origin and u.path == '/api/spot/live_image.jpg', 'network-target')
        if type(row.get('status')) is int and row['status'] != 200:
            raise ImageRequestFailure('image-http-error')
    require(isinstance(raw.get('errors'), list), 'raw-errors-missing')
    if 'image-request-failed' in raw['errors']:
        raise ImageRequestFailure('image-request-failed')
    require(raw['errors'] == [], 'raw-errors')
    require(capture.get('status') == 'CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE'
            and not any(capture.get(k) for k in ('error', 'cleanup_error', 'disconnect_error')), 'capture-incomplete')
    dom = raw['dom']
    require(dom.get('stopped') is True and dom.get('overflow') is False
            and type(dom.get('pending')) is int and dom['pending'] == 0 and dom.get('errors') == [], 'dom-incomplete')
    start, end = dom['window_start_ms'], dom['window_end_ms']
    require(numeric(start) and numeric(end) and dom.get('clock') == 'PAGE_MONOTONIC_MS'
            and abs((end - start) - policy['observation_contract']['image_display_window_seconds'] * 1000) < .001,
            'full-monotonic-window-required')
    responses = records(raw.get('responses'), 'responses')
    require(responses == dom.get('responses'), 'dom-response-mismatch')
    require(network and all(type(row.get('status')) is int and row['status'] == 200 for row in network), 'image-request-error-or-missing')
    by_hash, by_url, header_keys = defaultdict(list), defaultdict(list), defaultdict(int)
    for row in network:
        header_keys[(row.get('url'), row.get('status'), row.get('captured_at'))] += 1
    for row in responses:
        u = urlsplit(row['url'])
        require(f'{u.scheme}://{u.netloc}' == origin and u.path == '/api/spot/live_image.jpg'
                and not row.get('error') and re.fullmatch('[0-9a-f]{64}', row.get('sha256', ''))
                and header_keys[(row['url'], row['status'], row.get('captured_at'))] == 1, 'unbound-response')
        by_hash[row['sha256']].append(row)
    for paint in records(dom.get('paints'), 'paints'):
        require(paint.get('identifier') == capture['run_id'] and paint.get('entryType') == 'element', 'paint-provenance')
        by_url[paint.get('url')].append(paint)
    states = records(dom.get('states'), 'states')
    require(states and all(numeric(s.get('at')) for s in states), 'missing-visibility-records')
    require(all(s.get('visible') is True and s.get('focused') is True
                and s.get('dom_occluded') is False and s.get('image_present') is True
                for s in states if start <= s['at'] <= end), 'visibility-incomplete')
    samples, source_ids = [], set()
    for load in records(dom.get('loads'), 'loads'):
        require(numeric(load.get('at')), 'load-clock')
        if not start <= load['at'] <= end:
            continue
        require(not load.get('error') and len(by_hash[load.get('sha256')]) == 1
                and len(by_url[load.get('url')]) == 1, 'ambiguous-or-missing-presentation')
        response, paint = by_hash[load['sha256']][0], by_url[load['url']][0]
        source_id = response.get('captured_at')
        require(isinstance(source_id, str) and numeric(float(source_id)) and float(source_id) > 0
                and source_id not in source_ids, 'source-identity')
        source_ids.add(source_id)
        stamp = paint.get('presentationTime')
        require(all(numeric(paint.get(k)) for k in ('loadTime', 'presentationTime', 'observed_at'))
                and 0 < stamp and paint['loadTime'] <= stamp <= paint['observed_at'], 'presentation-clock')
        if stamp > end:
            continue  # Keep tail evidence in the original; not in the measured window.
        require(stamp >= start, 'presentation-before-window')
        samples.append({'presented_at_ms': stamp, 'response_id': response.get('id'),
                        'presentation_confirmed': True, 'fresh_frame_identity_confirmed': True,
                        'visible': paint.get('visible'), 'occluded': paint.get('dom_occluded')})
    samples.sort(key=lambda row: row['presented_at_ms'])
    require(len(samples) >= 2 and states[0]['at'] <= samples[0]['presented_at_ms']
            and states[-1]['at'] >= end, 'visibility-window-not-covered')
    return samples, start, end


def assess_group(captures, bindings, screen, logger, policy):
    result = {'schema': 'sfl-four-client-presentation-assessment-v1', 'status': 'INCOMPLETE',
              'scope': 'FOUR_CLIENT_DISPLAY_COMPONENT_ONLY', 'clients': [], 'errors': [],
              'release_gate': 'HOLD', 'promotion_allowed': False,
              'screen_evidence_kind': 'USER_CONFIRMATION_SEPARATE_FROM_BROWSER_TIMESTAMPS'}
    try:
        require(re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', logger), 'logger-id')
        require(len(captures) == len(bindings) == policy['observation_contract']['physical_clients'], 'four-clients-required')
        ids = [b['client_id'] for b in bindings]
        physical = [b['physical_id'] for b in bindings]
        require(set(ids) == {'PC_1', 'PC_2', 'PC_3', 'PC_4'}
                and all(isinstance(v, str) and v.strip() for v in physical) and len(set(physical)) == 4,
                'distinct-physical-clients-required')
        require([b['role'] for b in bindings].count('server') == 1
                and [b['role'] for b in bindings].count('browser') == 3, 'one-server-three-browsers-required')
        run_ids = {b['client_id']: c['run_id'] for b, c in zip(bindings, captures)}
        require(len(set(run_ids.values())) == 4, 'distinct-capture-runs-required')
        require(isinstance(screen, dict) and screen.get('schema') == 'sfl-field-screen-confirmation-v1'
                and screen.get('confirmed_by') == 'user' and isinstance(screen.get('user_statement'), str)
                and bool(screen['user_statement'].strip()) and screen.get('client_run_ids') == run_ids
                and screen.get('physical_client_map') == dict(zip(ids, physical))
                and screen.get('all_four_visible_during_each_capture') is True
                and screen.get('all_windows_unobscured') is True, 'missing-bound-user-screen-confirmation')
        # Each 900-second monotonic interval ran under four-client viewing load.
        # Browser wall clocks are not assumed synchronized across different PCs.
        for binding, capture in zip(bindings, captures):
            item = {'client_id': binding['client_id'], 'run_id': capture['run_id']}
            try:
                samples, start, end = reconstruct(capture, binding, logger, policy)
                item.update(assess_display(samples, window_start_ms=start, window_end_ms=end,
                    complete=True, white_screen_events=screen['white_screen_events'].get(binding['client_id']), policy=policy))
                item.update(frames=len(samples), window_start_ms=start, window_end_ms=end)
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
    require(index.get('schema') == 'sfl-four-client-capture-index-v1', 'index-schema')
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
