import unittest
import shlex
from unittest.mock import patch

from completion_wait import completion_wait_for
from native_live_probe import native_setup_command
from production_runtime_probe import synthetic_gateway_command, gateway_fixture
from openhands_agent_probe import relay_command
from docker_gateway_probe import client_fixture, SOCKET, CLIENT_TIMEOUT_SECONDS


class ProbeCompletionWaitTests(unittest.TestCase):
    def test_legacy_socket_fixture_derives_wait_from_unchanged_outer_deadline(self):
        self.assertEqual(CLIENT_TIMEOUT_SECONDS, 120)
        with patch('container_model_relay.make_relay', side_effect=RuntimeError('synthetic stop')) as relay:
            with self.assertRaisesRegex(RuntimeError, 'synthetic stop'):
                client_fixture()
        relay.assert_called_once_with(SOCKET, completion_wait_seconds=180.)

    def test_replacement_gateway_commands_preserve_trusted_wait(self):
        wait = completion_wait_for(180)
        commands = [native_setup_command('synthetic-trial', 'synthetic.json', wait)]
        commands.extend(synthetic_gateway_command(wait, **options) for options in (
            {}, {'native_openhands': True}, {'native_custom': True}))
        commands.append(shlex.split(relay_command(wait)))
        for command in commands:
            self.assertEqual(command.count('--completion-wait-seconds'), 1)
            self.assertEqual(command[command.index('--completion-wait-seconds') + 1], '240.0')

    def test_invalid_configuration_fails_before_gateway_or_provider_creation(self):
        for value in (None, True, 0, -1, float('nan'), float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): native_setup_command('trial', 'config.json', value)
                with self.assertRaises(ValueError): synthetic_gateway_command(value)
                with self.assertRaises(ValueError): gateway_fixture(completion_wait_seconds=value)
                with self.assertRaises(ValueError): relay_command(value)
