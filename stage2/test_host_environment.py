import json
import unittest
from unittest.mock import patch

from host_environment import snapshot


class HostEnvironmentTests(unittest.TestCase):
    def inspect(self, registration='rosetta\nenabled\ninterpreter /fixture/rosetta', missing=False):
        info = {'Architecture': 'aarch64', 'OSType': 'linux', 'KernelVersion': 'fixture',
                'ServerVersion': 'fixture', 'NCPU': 4, 'MemTotal': 1000}
        if missing: del info['MemTotal']
        def read(command, **kwargs):
            if command[:2] == ['docker', 'info']: return json.dumps(info)
            if command[0] == 'colima': return registration
            return 'fixture'
        with patch('host_environment.subprocess.check_output', side_effect=read):
            return snapshot()

    def test_identity_records_translation_and_resources(self):
        value = self.inspect()
        self.assertEqual(value['docker']['NCPU'], 4)
        self.assertIn('rosetta', value['x86_translation_registration'])

    def test_unknown_or_disabled_translation_rejected(self):
        for registration in ['', 'rosetta\ndisabled\ninterpreter /fixture/rosetta']:
            with self.assertRaises(ValueError): self.inspect(registration)

    def test_missing_resources_rejected(self):
        with self.assertRaises(ValueError): self.inspect(missing=True)
