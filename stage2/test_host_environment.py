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
        with patch('host_environment.subprocess.check_output', side_effect=read), \
             patch('host_environment.platform.system', return_value='Darwin'):
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

    def linux(self, client='x86_64', server='x86_64', endpoint='unix:///var/run/docker.sock'):
        info = {'Architecture': server, 'OSType': 'linux', 'KernelVersion': 'fixture-kernel',
                'ServerVersion': 'fixture-version', 'NCPU': 16, 'MemTotal': 32000000000}
        commands = []
        def read(command, **kwargs):
            commands.append(command)
            if command[:2] == ['docker', 'info']: return json.dumps(info)
            if command == ['docker', 'context', 'show']: return 'default'
            if command == ['docker', 'context', 'inspect', 'default']:
                return json.dumps([{'Endpoints': {'docker': {'Host': endpoint}}}])
            raise AssertionError('Unexpected host probe')
        with patch('host_environment.platform.system', return_value='Linux'), \
             patch('host_environment.platform.machine', return_value=client), \
             patch('host_environment.platform.release', return_value='fixture-kernel'), \
             patch('host_environment.subprocess.check_output', side_effect=read):
            value = snapshot()
        self.assertTrue(all(command[0] == 'docker' for command in commands))
        return value

    def test_native_linux_records_identity_without_translator(self):
        value = self.linux()
        self.assertEqual(value['execution_mode'], 'native_linux_x86_64')
        self.assertEqual(value['docker']['NCPU'], 16)
        self.assertNotIn('x86_translation_registration', value)

    def test_linux_arm_or_remote_daemon_not_admitted_as_native(self):
        for options in ({'client': 'aarch64'}, {'server': 'aarch64'}, {'endpoint': 'ssh://fixture'}):
            with self.assertRaises(ValueError): self.linux(**options)

    def test_conflicting_docker_host_override_rejected(self):
        with patch.dict('host_environment.os.environ', {'DOCKER_HOST': 'ssh://fixture'}):
            with self.assertRaises(ValueError): self.linux()
