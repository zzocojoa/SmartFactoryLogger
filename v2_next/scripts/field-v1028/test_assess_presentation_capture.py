import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import assess_presentation_capture as reader

POLICY = Path(__file__).resolve().parents[2] / 'docs/V2/05_운영_배포/approved_release_policy_20261023.json'
LOGGER = '11111111-2222-3333-4444-555555555555'


def fixture(policy):
    captures, bindings = [], []
    for n in range(1, 5):
        cid, run = f'PC_{n}', f'SYNTHETIC_ONLY_{n}'
        role = 'server' if n == 1 else 'browser'
        origin = 'http://127.0.0.1:8000' if n == 1 else 'http://192.168.0.7:8000'
        page = 'file:///test-only/index.html' if n == 1 else origin + '/dashboard'
        binding = {'client_id': cid, 'physical_id': f'SYNTHETIC_COMPUTER_{n}',
                   'role': role, 'page_url': page, 'image_origin': origin}
        schema, context = reader.CONTEXTS[role]
        capture = {'schema': schema, 'context': context, 'client_id': cid, 'run_id': run,
                   'page_url': page, 'collector_sha256': reader.COLLECTOR_SHA,
                   'observer_revision_sha256': reader.COLLECTOR_SHA,
                   'status': 'CAPTURE_COMPLETE_REQUIRES_SCREEN_EVIDENCE',
                   'before': {'build': policy['candidate']['build_commit'], 'logger': LOGGER},
                   'after': {'build': policy['candidate']['build_commit'], 'logger': LOGGER}}
        dom = {'loads': [], 'paints': [], 'responses': [], 'states': [], 'errors': [],
               'stopped': True, 'overflow': False, 'pending': 0, 'clock': 'PAGE_MONOTONIC_MS',
               'window_start_ms': 0, 'window_end_ms': 900000}
        network = []
        for i in range(1, 1801):
            stamp = i * 500
            digest = hashlib.sha256(str(i).encode()).hexdigest()
            url, blob = origin + f'/api/spot/live_image.jpg?i={i}', f'blob:{origin}/{run}_{i}'
            response = {'id': str(i), 'url': url, 'sha256': digest, 'status': 200,
                        'captured_at': str(1700000000 + i / 2)}
            dom['responses'].append(response)
            network.append({k: response[k] for k in ('url', 'status', 'captured_at')})
            dom['loads'].append({'url': blob, 'at': stamp - 1, 'sha256': digest})
            dom['paints'].append({'url': blob, 'identifier': run, 'entryType': 'element',
                                 'loadTime': stamp - 10, 'presentationTime': stamp,
                                 'observed_at': stamp + 1, 'visible': True, 'dom_occluded': False})
        dom['states'] = [{'at': t, 'visible': True, 'focused': True, 'dom_occluded': False,
                          'image_present': True} for t in (0, 100000, 900000, 902000)]
        capture['observation'] = {'schema': 'sfl-image-presentation-v1',
            'context': context if role == 'browser' else 'UNSPECIFIED',
            'run_id': run, 'page_url': page, 'dom': dom, 'responses': dom['responses'],
            'network_responses': network, 'errors': [], 'summary': {'status': 'IGNORE_UNTRUSTED_SUMMARY'}}
        captures.append(capture)
        bindings.append(binding)
    screen = {'schema': 'sfl-field-screen-confirmation-v1', 'confirmed_by': 'user',
              'user_statement': 'SYNTHETIC TEST DATA ONLY. This is not a field confirmation.',
              'all_four_visible_during_each_capture': True, 'all_windows_unobscured': True,
              'client_run_ids': {c['client_id']: c['run_id'] for c in captures},
              'physical_client_map': {b['client_id']: b['physical_id'] for b in bindings},
              'white_screen_events': {c['client_id']: 0 for c in captures}}
    return captures, bindings, screen


class PresentationCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = reader.load_policy(POLICY, reader.POLICY_SHA)
        cls.original = fixture(cls.policy)

    def setUp(self):
        self.captures, self.bindings, self.screen = copy.deepcopy(self.original)

    def result(self):
        return reader.assess_group(self.captures, self.bindings, self.screen, LOGGER, self.policy)

    def test_four_complete_distinct_clients_only_component_pass(self):
        result = self.result()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual([c['p95_ms'] for c in result['clients']], [500] * 4)
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertIs(result['promotion_allowed'], False)

    def test_missing_or_unbound_screen_confirmation_cannot_pass(self):
        for key in ('schema', 'user_statement', 'client_run_ids', 'physical_client_map',
                    'all_four_visible_during_each_capture', 'all_windows_unobscured'):
            self.screen = copy.deepcopy(self.original[2]); self.screen.pop(key)
            with self.subTest(key=key):
                self.assertEqual(self.result()['status'], 'INCOMPLETE')
        self.screen = None
        self.assertEqual(self.result()['status'], 'INCOMPLETE')

    def test_same_pc_four_times_or_stale_capture_is_not_four_pc_evidence(self):
        self.bindings[3]['physical_id'] = self.bindings[2]['physical_id']
        self.assertEqual(self.result()['status'], 'INCOMPLETE')
        self.bindings = copy.deepcopy(self.original[1])
        self.captures[3]['run_id'] = self.captures[2]['run_id']
        self.assertEqual(self.result()['status'], 'INCOMPLETE')
        self.captures.pop()
        self.assertEqual(self.result()['status'], 'INCOMPLETE')

    def test_fixture_context_wrong_build_and_cleanup_errors_are_rejected(self):
        mutations = [('context', 'HEADLESS_FIXTURE'), ('observer_revision_sha256', '0' * 64),
                     ('cleanup_error', 'not restored'), ('status', 'CAPTURE_INCOMPLETE')]
        for key, value in mutations:
            self.captures = copy.deepcopy(self.original[0]); self.captures[1][key] = value
            with self.subTest(key=key): self.assertEqual(self.result()['status'], 'INCOMPLETE')
        self.captures = copy.deepcopy(self.original[0])
        self.captures[1]['after']['logger'] = 'different'
        self.assertEqual(self.result()['status'], 'INCOMPLETE')

    def test_forged_summary_does_not_replace_raw_presentation(self):
        self.captures[1]['observation']['summary'] = {'status': 'PASS', 'samples': []}
        del self.captures[1]['observation']['dom']['paints'][8]['presentationTime']
        self.assertEqual(self.result()['status'], 'INCOMPLETE')

    def test_bound_http_error_is_failure_even_when_capture_is_incomplete(self):
        self.captures[1]['status'] = 'CAPTURE_INCOMPLETE'
        self.captures[1]['observation']['network_responses'][3]['status'] = 503
        result = self.result()
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['clients'][1]['failures'], ['image-http-error'])
        self.captures = copy.deepcopy(self.original[0])
        self.captures[1]['observation']['errors'].append('image-request-failed')
        self.assertEqual(self.result()['status'], 'FAIL')

    def test_changing_only_top_context_does_not_convert_fixture_to_field(self):
        self.captures[1]['observation']['context'] = 'HEADLESS_FIXTURE'
        self.assertEqual(self.result()['status'], 'INCOMPLETE')

    def test_missing_raw_headers_and_ambiguous_body_cannot_pass(self):
        raw = self.captures[1]['observation']
        raw['network_responses'].pop(3)
        self.assertEqual(self.result()['status'], 'INCOMPLETE')
        self.captures = copy.deepcopy(self.original[0]); raw = self.captures[1]['observation']
        raw['responses'][3]['sha256'] = raw['responses'][4]['sha256']
        self.assertEqual(self.result()['status'], 'INCOMPLETE')

    def test_partial_window_empty_visibility_or_lost_focus_cannot_pass(self):
        for mutation in ('duration', 'empty', 'hidden', 'missing_end', 'overflow'):
            self.captures = copy.deepcopy(self.original[0]); dom = self.captures[1]['observation']['dom']
            if mutation == 'duration': dom['window_end_ms'] = 899999
            if mutation == 'empty': dom['states'] = []
            if mutation == 'hidden': dom['states'][1]['focused'] = False
            if mutation == 'missing_end': dom['states'] = dom['states'][:2]
            if mutation == 'overflow': dom['overflow'] = True
            with self.subTest(mutation=mutation): self.assertEqual(self.result()['status'], 'INCOMPLETE')

    def test_two_second_tail_gap_and_white_screen_are_failures(self):
        dom = self.captures[2]['observation']['dom']
        dom['loads'] = dom['loads'][:-4]; dom['paints'] = dom['paints'][:-4]
        result = self.result()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('display-gap-exceeded', result['clients'][2]['failures'])
        self.captures = copy.deepcopy(self.original[0]); self.screen['white_screen_events']['PC_3'] = 1
        self.assertEqual(self.result()['status'], 'FAIL')

    def test_strict_json_and_hash_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'raw.json'
            for text in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    reader.read_pinned(path, hashlib.sha256(path.read_bytes()).hexdigest())
            path.write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError): reader.read_pinned(path, '0' * 64)

    def test_cli_reads_exact_members_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def save(name, value):
                path = root / name; path.write_text(json.dumps(value), encoding='utf-8')
                return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            clients = [{**b, **save(f'{b["client_id"]}.json', c)} for b, c in zip(self.bindings, self.captures)]
            index = {'schema': 'sfl-four-client-capture-index-v1', 'logger': LOGGER,
                     'clients': clients, 'screen_confirmation': save('screen.json', self.screen)}
            pin = save('index.json', index); out = root / 'assessment.json'
            args = [sys.executable, str(Path(reader.__file__)), '--index', str(root / pin['path']),
                    '--index-sha256', pin['sha256'], '--policy', str(POLICY), '--out', str(out)]
            run = subprocess.run(args, text=True, capture_output=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(out.read_text())['status'], 'PASS')
            original = out.read_bytes()
            retry = subprocess.run(args, text=True, capture_output=True, timeout=20)
            self.assertNotEqual(retry.returncode, 0)
            self.assertEqual(out.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
