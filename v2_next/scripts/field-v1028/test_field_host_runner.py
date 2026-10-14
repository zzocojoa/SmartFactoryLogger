"""The diagnostic request cannot silently replace formal 15/120 minute runs."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import field_runner as runner
import field_observation as observation
from field_resource_sampling import ProcessIdentity


def request(mode='host-diagnostic', seconds=300):
    spec = observation.ObservationSpec('C:/fixture/app', 'C:/fixture/payload.json',
        ProcessIdentity(10, 1.0, 'C:/fixture/app/main.exe'),
        ProcessIdentity(20, 2.0, 'C:/fixture/app/backend.exe'), 8000,
        configuration_reference='C:/fixture/configuration.json', configuration_reference_sha256='a'*64)
    return {'schema': runner.SCHEMA, 'mode': mode, 'candidate_commit': runner.binding.BUILD,
            'signature_policy': 'UNSIGNED_INTERNAL', 'duration_seconds': seconds, 'spec': asdict(spec)}


class HostRunnerTests(unittest.TestCase):
    def test_diagnostic_is_fixed_to_five_minutes(self):
        self.assertEqual(runner.validate_request(request()), 'host-diagnostic')
        for duration in (True, 0, 299, 301, 900, 7200):
            with self.assertRaises(ValueError): runner.validate_request(request(seconds=duration))

    def test_formal_observation_durations_and_candidate_pins_are_unchanged(self):
        for duration in (900, 7200):
            self.assertEqual(runner.validate_request(request('observe', duration)), 'observe')
        with self.assertRaises(ValueError): runner.validate_request(request('observe', 300))
        original = request()
        for key, value in [('signature_policy', 'SIGNED'), ('candidate_commit', 'b'*40), ('promotion_allowed', True)]:
            invalid = deepcopy(original); invalid[key] = value
            with self.assertRaises(ValueError): runner.validate_request(invalid)
        invalid = deepcopy(original); invalid['spec']['reference_sha256'] = 'b'*64
        with self.assertRaises(ValueError): runner.validate_request(invalid)

    def test_only_diagnostic_selects_host_worker_and_never_overrides_failure(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent)
            (root / 'app').mkdir()
            for name in ('payload.json', 'configuration.json'):
                (root / name).write_text('{}', encoding='utf-8')
            for mode, seconds in [('observe', 900), ('host-diagnostic', 300)]:
                value = request(mode, seconds)
                value['spec'].update(root=str(root / 'app'), reference=str(root / 'payload.json'),
                                     configuration_reference=str(root / 'configuration.json'))
                with patch.object(observation, 'supervise_observation', return_value={'supervisor_status': 'FAIL'}) as run:
                    phase, passed = runner.execute_phase(value, root, root)
                self.assertFalse(passed)
                self.assertEqual(phase['supervisor_status'], 'FAIL')
                self.assertEqual(run.call_args.kwargs['duration_seconds'], seconds)
                self.assertEqual('_worker_target' in run.call_args.kwargs, mode == 'host-diagnostic')


if __name__ == '__main__':
    unittest.main()
