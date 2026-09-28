"""Local fake-provider checks; no Docker, native rehearsal or paid evidence."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import matched_repeat_fixture as fixture
import matched_repeat_policy as policy
from credit_only_accounting import summarise
from credit_only_gateway import CreditOnlyError, prepare_credit_request
from matched_repeat_gateway import MatchedRepeatSession
from model_protocol import ModelSettings, freeze_protocol
from openrouter_transport import TransportError
from retry_runtime import activate
from scored_gateway import durable_json, private_directory
from test_credit_only_gateway import TOKEN
from test_retry_gateway import Clock, Event, REQUEST


def payload(harness):
    value = deepcopy(REQUEST)
    if harness == 'openhands':
        value['tools'] = [dict(type='function', function=dict(name=name,
            parameters=dict(type='object', properties={}))) for name in ('execute_bash', 'finish')]
    return value


def feedback(harness, request, response, *, confirmation=False):
    value = deepcopy(request)
    value['messages'].append(deepcopy(response['choices'][0]['message']))
    if harness == 'terminus-2':
        content = fixture.OBSERVATION
        if confirmation:
            # Actual installed native formatter, not a rewritten baseline prompt.
            from harbor.agents.terminus_2.terminus_2 import Terminus2
            content = Terminus2._get_completion_confirmation_message(
                SimpleNamespace(_parser_name='json'), content)
        value['messages'].append(dict(role='user', content=content))
    else:
        value['messages'].append(dict(role='tool', tool_call_id=fixture.TOOL_CALL_ID,
            content=fixture.OBSERVATION))
    return value


class FixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.rt = private_directory(self.root / '.runtime/stage2')
        self.network = self.enterContext(patch.object(fixture, 'require_network_isolation'))
        self.provider_network = self.enterContext(patch('openrouter_transport.OpenRouter',
            side_effect=AssertionError('External transport forbidden in local fixture tests')))
        self.clock = Clock()

    def record(self, harness='terminus-2', mode='tools'):
        value = fixture.fixture_document(harness, mode)
        durable_json(self.rt / fixture.FIXTURE_FILE, value)
        freeze_protocol(self.rt, policy.SETTINGS)
        return value

    def provider(self, harness='terminus-2', mode='tools', **overrides):
        arguments = dict(harness=harness, mode=mode, clock=self.clock,
            generation_enabled=True, completion_wait_seconds=900.)
        arguments.update(overrides)
        return fixture.SyntheticProvider(fixture.SYNTHETIC_KEY, **arguments)

    def session(self, harness='terminus-2', mode='tools', *, client=None):
        value = self.record(harness, mode)
        activate(self.rt, value['trial_id'], 900, policy.SETTINGS, self.clock)
        result = fixture.FixtureSession(self.root, value['trial_id'], 'final', TOKEN,
            client if client is not None else self.provider(harness, mode),
            settings=policy.SETTINGS, clock=self.clock)
        result.cancelled = Event(self.clock)
        self.addCleanup(result.close)
        return result

    def start_provider(self, harness='terminus-2'):
        provider = self.provider(harness)
        request = prepare_credit_request(payload(harness), policy.SETTINGS)
        with self.assertRaises(TransportError): provider.complete(request, on_response_headers=lambda _:None)
        response = provider.complete(request, on_response_headers=lambda _:None)
        return provider, request, response

    def test_all_six_fixture_identities_are_separate_and_non_admitting(self):
        ids = set()
        for harness in policy.HARNESSES:
            for mode in policy.PROBE_MODES:
                value = fixture.fixture_document(harness, mode); ids.add(value['trial_id'])
                self.assertFalse(value['paid_launch_ready']); self.assertFalse(value['repeat_execution_qualified'])
                self.assertEqual(value['live_api_calls'], 0)
                self.assertEqual(value['model_protocol_sha256'], policy.SETTINGS.fingerprint())
                self.assertTrue(value['trial_id'].startswith('synthetic-matched-repeat-'))
        self.assertEqual(len(ids), 6)
        for harness, mode in (('C0-NC', 'tools'), ('terminus-2', 'paid'), ('terminus-2', '../tools')):
            with self.assertRaises(ValueError): fixture.fixture_document(harness, mode)

    def test_actual_private_record_and_raw_hash_are_read(self):
        value = self.record(); path = self.rt / fixture.FIXTURE_FILE
        actual, digest = fixture.read_fixture(self.rt, value['trial_id'], 'final')
        self.assertEqual(actual, value)
        self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_wrong_stage_paid_id_and_foreign_harness_are_rejected(self):
        value = self.record()
        for trial, stage in ((value['trial_id'], 'development'), ('matchedrepeat1-terminus-2-01-any', 'final'),
                ('synthetic-matched-repeat-openhands-tools', 'final')):
            with self.assertRaises(ValueError): fixture.read_fixture(self.rt, trial, stage)

    def test_false_proof_extra_fields_and_numeric_type_drift_are_rejected(self):
        value = self.record(); path = self.rt / fixture.FIXTURE_FILE
        for key, replacement in (('paid_launch_ready', True), ('repeat_execution_qualified', True),
                ('live_api_calls', 0.0), ('model_protocol_sha256', '0' * 64), ('qualification', {})):
            path.write_text(json.dumps(dict(value, **{key:replacement})))
            with self.subTest(key=key), self.assertRaises(ValueError):
                fixture.read_fixture(self.rt, value['trial_id'], 'final')

    def test_duplicate_nonfinite_or_nonobject_fixture_is_rejected(self):
        value = self.record(); path = self.rt / fixture.FIXTURE_FILE
        for raw in (b'{"mode":"tools","mode":"tools"}', b'{"value":NaN}', b'[]', b'null'):
            path.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                fixture.read_fixture(self.rt, value['trial_id'], 'final')

    def test_public_or_missing_record_and_public_runtime_are_rejected(self):
        value = self.record(); path = self.rt / fixture.FIXTURE_FILE
        path.chmod(0o644)
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, value['trial_id'], 'final')
        path.chmod(0o600); self.rt.chmod(0o755)
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, value['trial_id'], 'final')
        self.rt.chmod(0o700); path.unlink()
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, value['trial_id'], 'final')

    def test_wrong_owner_and_hardlinked_record_are_rejected(self):
        value = self.record()
        with patch.object(fixture.os, 'getuid', return_value=-1), self.assertRaises(ValueError):
            fixture.read_fixture(self.rt, value['trial_id'], 'final')
        os.link(self.rt / fixture.FIXTURE_FILE, self.rt / 'another-file')
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, value['trial_id'], 'final')

    def test_file_and_parent_symlinks_are_rejected(self):
        value = self.record(); path = self.rt / fixture.FIXTURE_FILE
        other = self.rt / 'other'; path.rename(other); path.symlink_to(other)
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, value['trial_id'], 'final')
        path.unlink(); other.rename(path)
        link = self.root / 'linked'; link.symlink_to(self.rt, target_is_directory=True)
        with self.assertRaises(ValueError): fixture.read_fixture(link, value['trial_id'], 'final')

    def test_oversized_record_is_rejected(self):
        value = self.record(); (self.rt / fixture.FIXTURE_FILE).write_bytes(b' ' * (fixture.MAX_FIXTURE_BYTES + 1))
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, value['trial_id'], 'final')

    def test_production_evidence_cannot_be_mixed_with_a_fixture(self):
        value = self.record()
        for name in fixture.PRODUCTION_FILES:
            path = self.rt / name; path.symlink_to(self.rt / 'absent')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'production repeat evidence'):
                fixture.read_fixture(self.rt, value['trial_id'], 'final')
            path.unlink()

    def test_production_gateway_does_not_accept_the_fixture_document(self):
        value = self.record()
        with self.assertRaises((ValueError, OSError)):
            MatchedRepeatSession(self.root, value['trial_id'], 'final', TOKEN,
                self.provider(), settings=policy.SETTINGS, clock=self.clock)
        self.assertFalse((self.rt / 'scored-attempts').exists())
        self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())

    def test_non_fake_or_subclass_provider_is_refused_before_attempt(self):
        class FakeSubclass(fixture.SyntheticProvider): pass
        client = FakeSubclass(fixture.SYNTHETIC_KEY, harness='terminus-2', mode='tools', clock=self.clock,
            generation_enabled=True, completion_wait_seconds=900)
        with self.assertRaisesRegex(ValueError, 'Exact synthetic provider'): self.session(client=client)
        self.assertFalse((self.rt / 'scored-attempts').exists())

    def test_wrong_provider_identity_or_clock_is_refused(self):
        value = self.record()
        for harness, mode, clock in (('openhands', 'tools', self.clock),
                ('terminus-2', 'boundary_stop', self.clock), ('terminus-2', 'tools', Clock())):
            with self.assertRaisesRegex(ValueError, 'Fixture identity'):
                fixture.FixtureSession(self.root, value['trial_id'], 'final', TOKEN,
                    self.provider(harness, mode, clock=clock), settings=policy.SETTINGS, clock=self.clock)

    def test_external_provider_object_is_refused_without_calling_it(self):
        client = SimpleNamespace(complete=lambda *a, **kw:self.fail('External client called'))
        with self.assertRaisesRegex(ValueError, 'Exact synthetic provider'): self.session(client=client)
        self.assertFalse((self.rt / 'scored-attempts').exists())

    def test_fixture_bytes_are_immutable_even_with_equal_canonical_json(self):
        session = self.session(); path = self.rt / fixture.FIXTURE_FILE
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'private bytes changed'): session.complete(TOKEN, payload('terminus-2'))
        self.assertTrue(session.stopped); self.assertEqual(session.client.calls, 0)
        self.assertFalse(list(session.evidence.glob('*.request.json')))

    def test_fixture_cannot_restart_an_existing_attempt(self):
        session = self.session(); session.close()
        with self.assertRaises(FileExistsError):
            fixture.FixtureSession(self.root, session.trial_id, 'final', TOKEN, self.provider(),
                settings=policy.SETTINGS, clock=self.clock)

    def test_wrong_settings_are_refused_before_attempt(self):
        value = self.record()
        with self.assertRaisesRegex(ValueError, 'frozen model'):
            fixture.FixtureSession(self.root, value['trial_id'], 'final', TOKEN, self.provider(),
                settings=ModelSettings(8192, 1., 'high'), clock=self.clock)

    def test_sentinel_key_only_and_no_generic_transport_options(self):
        arguments = dict(harness='terminus-2', mode='tools', clock=self.clock,
            generation_enabled=True, completion_wait_seconds=900)
        for key in ('not-the-fixture-key', '', None):
            with self.assertRaises(ValueError): fixture.SyntheticProvider(key, **arguments)
        with self.assertRaises(TypeError): fixture.SyntheticProvider(fixture.SYNTHETIC_KEY, **arguments, opener=object())
        with self.assertRaises(ValueError): self.provider(generation_enabled=False)
        self.provider_network.assert_not_called()

    def test_provider_has_no_balance_receipt_or_external_transport_methods(self):
        client = self.provider()
        for name in ('balance', 'key_status', 'metadata', 'generation', 'opener', '_request_url', '_key'):
            self.assertFalse(hasattr(client, name), name)

    def test_one_real_shared_429_and_native_terminus_confirmation(self):
        from harbor.agents.terminus_2.terminus_json_plain_parser import TerminusJSONPlainParser
        session = self.session(); request = payload('terminus-2'); parser = TerminusJSONPlainParser()
        first = session.complete(TOKEN, request)
        parsed = parser.parse_response(first['choices'][0]['message']['content'])
        self.assertFalse(parsed.error); self.assertFalse(parsed.warning); self.assertFalse(parsed.is_task_complete)
        self.assertEqual(parsed.commands[0].keystrokes, fixture.COMMAND + '\n')
        self.assertNotIn(fixture.OBSERVATION, parsed.commands[0].keystrokes)
        request = feedback('terminus-2', request, first)
        second = session.complete(TOKEN, request)
        parsed = parser.parse_response(second['choices'][0]['message']['content'])
        self.assertTrue(parsed.is_task_complete); self.assertEqual(parsed.commands, [])
        third = session.complete(TOKEN, feedback('terminus-2', request, second, confirmation=True))
        self.assertTrue(parser.parse_response(third['choices'][0]['message']['content']).is_task_complete)
        self.assertEqual((session.client.calls, session.client.accepted), (4, 3))
        self.assertEqual(self.clock.now, 101.)
        self.accounting(session, 4, 3)

    def accounting(self, session, physical, logical):
        actual = summarise(self.rt, session.trial_id)
        self.assertEqual(actual['requests'], physical)
        self.assertEqual(actual['unknown_cost_requests'], physical)
        self.assertIsNone(actual['charged_usd']); self.assertIsNone(actual['provider_stop'])
        self.assertEqual(len(list(session.evidence.glob('*.retry.json'))), 1)
        self.assertEqual(len(list(session.evidence.glob('logical-*.json'))), logical)
        self.assertTrue(all(json.loads(p.read_bytes())['accepted_for_agent']
            for p in session.evidence.glob('logical-*.json')))
        self.provider_network.assert_not_called()

    def test_openhands_original_shell_then_finish_wire_contract(self):
        session = self.session('openhands'); request = payload('openhands')
        first = session.complete(TOKEN, request); call = first['choices'][0]['message']['tool_calls'][0]
        self.assertEqual(call['function']['name'], 'execute_bash')
        self.assertEqual(json.loads(call['function']['arguments']), {'command':fixture.COMMAND})
        second = session.complete(TOKEN, feedback('openhands', request, first))
        self.assertEqual(second['choices'][0]['message']['tool_calls'][0]['function']['name'], 'finish')
        self.assertEqual((session.client.calls, session.client.accepted), (3, 2))
        self.accounting(session, 3, 2)

    def test_setup_cancellation_fixture_refuses_any_model_request(self):
        session = self.session(mode='cancel_setup')
        with self.assertRaises(CreditOnlyError): session.complete(TOKEN, payload('terminus-2'))
        self.assertEqual(session.client.calls, 0)
        self.assertTrue(session.client.failed)

    def test_boundary_fixture_scripts_responses_without_sending_signals(self):
        session = self.session(mode='boundary_stop')
        with patch.object(os, 'kill', side_effect=AssertionError('Gateway cannot signal host')):
            session.complete(TOKEN, payload('terminus-2'))
        self.assertEqual(session.client.calls, 2)
        self.assertFalse((self.rt / 'operator-stop-request.json').exists())

    def test_missing_or_echo_only_feedback_cannot_finish(self):
        for role, text in (('user', fixture.COMMAND), ('assistant', fixture.OBSERVATION), ('user', 'missing')):
            provider, request, response = self.start_provider()
            request['messages'].append(dict(role=role, content=text))
            with self.subTest(role=role, text=text), self.assertRaisesRegex(ValueError, 'tool feedback'):
                provider.complete(request, on_response_headers=lambda _:None)
            self.assertTrue(provider.failed); self.assertIsNone(provider.last_failure)
            self.assertEqual(provider.calls, 2)

    def test_wrong_openhands_tool_call_id_is_rejected(self):
        provider, request, response = self.start_provider('openhands')
        request = feedback('openhands', request, response)
        request['messages'][-1]['tool_call_id'] = 'another-command'
        with self.assertRaisesRegex(ValueError, 'tool feedback'):
            provider.complete(request, on_response_headers=lambda _:None)

    def test_no_extra_response_after_finished_dialogue(self):
        provider, request, response = self.start_provider('openhands')
        request = feedback('openhands', request, response)
        provider.complete(request, on_response_headers=lambda _:None)
        with self.assertRaisesRegex(ValueError, 'already completed'):
            provider.complete(request, on_response_headers=lambda _:None)
        self.assertEqual((provider.calls, provider.accepted), (3, 2))
        self.assertTrue(provider.failed); self.assertIsNone(provider.last_failure)

    def test_terminus_must_observe_native_confirmation_not_repeat_feedback(self):
        provider, request, response = self.start_provider()
        request = feedback('terminus-2', request, response)
        provider.complete(request, on_response_headers=lambda _:None)
        with self.assertRaisesRegex(ValueError, 'completion confirmation'):
            provider.complete(request, on_response_headers=lambda _:None)

    def test_changed_retried_payload_and_stale_429_descriptor_are_rejected(self):
        provider = self.provider(); request = prepare_credit_request(payload('terminus-2'), policy.SETTINGS)
        with self.assertRaises(TransportError): provider.complete(request, on_response_headers=lambda _:None)
        request['messages'][-1]['content'] += 'changed'
        with self.assertRaisesRegex(ValueError, 'preserve the rejected request'):
            provider.complete(request, on_response_headers=lambda _:None)
        self.assertIsNone(provider.last_failure); self.assertTrue(provider.failed); self.assertEqual(provider.calls, 1)

    def test_failed_provider_cannot_be_revived_by_restoring_request(self):
        provider = self.provider(); request = prepare_credit_request(payload('terminus-2'), policy.SETTINGS)
        changed = dict(request, max_tokens=1)
        with self.assertRaises(ValueError): provider.complete(changed, on_response_headers=lambda _:None)
        with self.assertRaisesRegex(ValueError, 'fixture state'):
            provider.complete(request, on_response_headers=lambda _:None)
        self.assertEqual(provider.calls, 0)

    def test_model_provider_sampling_or_tools_drift_is_rejected_before_fake_call(self):
        for name, value in (('model', 'different'), ('max_tokens', 8192), ('temperature', 0.),
                ('top_p', .5), ('seed', 42), ('reasoning', {'effort':'low'}), ('provider', {}),
                ('tools', [{'function':{'name':'custom_execute'}}])):
            client = self.provider(); request = prepare_credit_request(payload('terminus-2'), policy.SETTINGS)
            request[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                client.complete(request, on_response_headers=lambda _:None)
            self.assertEqual(client.calls, 0); self.assertIsNone(client.last_failure)

    def test_deadline_cancellation_wrong_token_and_revocation_do_not_call_provider(self):
        session = self.session(); request = payload('terminus-2')
        with self.assertRaises(CreditOnlyError): session.complete('wrong-token', request)
        session.cancelled.set()
        with self.assertRaises(CreditOnlyError): session.complete(TOKEN, request)
        session.cancelled.cancelled = False; self.clock.now += 901
        with self.assertRaises(CreditOnlyError): session.complete(TOKEN, request)
        session.close()
        with self.assertRaises(CreditOnlyError): session.complete(TOKEN, request)
        self.assertEqual(session.client.calls, 0)

    def test_revocation_during_retry_wait_never_resends(self):
        session = self.session(); session.cancelled.wait = lambda _:session.cancelled.set()
        with self.assertRaises(CreditOnlyError): session.complete(TOKEN, payload('terminus-2'))
        self.assertEqual(session.client.calls, 1)

    def test_network_drift_is_rechecked_before_provider_and_each_request(self):
        self.network.side_effect = ValueError('Not isolated')
        with self.assertRaisesRegex(ValueError, 'Not isolated'): self.provider()
        self.network.side_effect = None; session = self.session()
        self.network.side_effect = ValueError('Not isolated')
        with self.assertRaisesRegex(ValueError, 'Not isolated'): session.complete(TOKEN, payload('terminus-2'))
        self.assertEqual(session.client.calls, 0)


class GatewayEntryTests(unittest.TestCase):
    def setUp(self):
        self.network = self.enterContext(patch.object(fixture, 'require_network_isolation'))
        self.document = fixture.fixture_document('terminus-2', 'tools')
        self.read = self.enterContext(patch.object(fixture, 'read_fixture', return_value=(self.document, 'a' * 64)))
        self.credential = self.enterContext(patch.object(fixture, '_private_bytes',
            return_value=('OPENROUTER_API_KEY=' + fixture.SYNTHETIC_KEY + '\n').encode()))
        self.serve = self.enterContext(patch('retry_gateway.serve'))
        self.enterContext(patch.dict(os.environ, {}, clear=True))

    def test_only_fixed_gateway_paths_and_exact_synthetic_factory(self):
        fixture.gateway_fixture(self.document['trial_id'], 900)
        args, kw = self.serve.call_args
        self.assertEqual(args, ('/study', self.document['trial_id'], 'final', '/run/trial-token',
            '/run/openrouter.env', '/socket/private/model.sock'))
        self.assertIs(kw['session_factory'], fixture.FixtureSession)
        client = kw['client_factory'](fixture.SYNTHETIC_KEY, clock=Clock(), generation_enabled=True,
            completion_wait_seconds=900)
        self.assertIs(type(client), fixture.SyntheticProvider)
        self.assertEqual(client.harness, 'terminus-2')
        self.credential.assert_called_once_with(Path('/run/openrouter.env'))

    def test_real_or_extra_credential_data_refuses_server_start(self):
        for raw in (b'OPENROUTER_API_KEY=not-synthetic\n', self.credential.return_value + b'OTHER=value\n'):
            self.credential.return_value = raw
            with self.assertRaisesRegex(ValueError, 'synthetic credential'): fixture.gateway_fixture('fixture', 900)
        self.serve.assert_not_called()

    def test_provider_credentials_in_environment_refuse_server_start(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'do-not-forward'}), self.assertRaises(ValueError):
            fixture.gateway_fixture('fixture', 900)
        self.serve.assert_not_called()

    def test_drift_between_gateway_preflight_and_provider_creation_is_rejected(self):
        fixture.gateway_fixture('fixture', 900)
        self.read.return_value = self.document, 'b' * 64
        with self.assertRaisesRegex(ValueError, 'before provider construction'):
            self.serve.call_args.kwargs['client_factory'](fixture.SYNTHETIC_KEY, clock=Clock(),
                generation_enabled=True, completion_wait_seconds=900)

    def test_network_refusal_precedes_credential_and_fixture_reads(self):
        self.network.side_effect = ValueError('Not isolated')
        with self.assertRaises(ValueError): fixture.gateway_fixture('fixture', 900)
        self.credential.assert_not_called(); self.read.assert_not_called(); self.serve.assert_not_called()


class IsolationTests(unittest.TestCase):
    def test_only_native_linux_loopback_interface_is_accepted(self):
        with patch.object(sys, 'platform', 'linux'), patch.object(Path, 'iterdir', return_value=[Path('lo')]):
            fixture.require_network_isolation()
        for platform, names in (('darwin', ['lo']), ('linux', ['lo', 'eth0']), ('linux', [])):
            with patch.object(sys, 'platform', platform), patch.object(Path, 'iterdir', return_value=list(map(Path, names))):
                with self.assertRaises(ValueError): fixture.require_network_isolation()

    def test_no_host_launcher_cli_and_no_native_stack_import(self):
        path = Path(__file__).with_name('matched_repeat_fixture.py')
        result = subprocess.run([sys.executable, '-B', str(path), '--root', '/unused'],
            capture_output=True, text=True, env={'PATH':'/usr/bin:/bin'})
        self.assertNotEqual(result.returncode, 0)
        code = ('import sys; sys.path.insert(0,' + repr(str(path.parent)) + '); import matched_repeat_fixture; '
            'assert not any(n.split(".")[0] in {"harbor","litellm","openhands","langchain","deepagents"} '
            'for n in sys.modules)')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code],
            capture_output=True, text=True, env={'PATH':'/usr/bin:/bin'})
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
