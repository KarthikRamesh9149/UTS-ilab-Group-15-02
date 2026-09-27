"""Fake-provider and fixture isolation tests; no Docker or paid calls."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_custom_probe as probe
import no_cutoff_custom_policy as policy
from no_cutoff_capture_backend import encoded_capture_script
from openrouter_transport import TransportError
from scored_gateway import durable_json, private_directory
from test_portable_custom_probe import ProviderFixtureTests
from test_retry_gateway import Clock


class ProbeTests(unittest.TestCase):
    def request(self, contents=()):
        value = ProviderFixtureTests().request()
        value['messages'] = [{'role': 'tool', 'content': content} for content in contents]
        return value

    def test_fake_key_and_absence_of_dynamic_time_advice(self):
        with self.assertRaises(ValueError): probe.SyntheticProvider('not-a-real-key', clock=Clock())
        provider = probe.SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
        with self.assertRaises(AssertionError):
            provider.complete(self.request(['[Task time remaining]']), on_response_headers=lambda _: None)
        with self.assertRaises(TransportError):
            provider.complete(self.request(), on_response_headers=lambda _: None)

    def test_native_script_checks_long_command_jobs_capture_and_repairs(self):
        provider = probe.SyntheticProvider('synthetic-not-a-real-key', clock=Clock()); provider.calls = 10
        def call(contents=()):
            return provider.complete(self.request(contents), on_response_headers=lambda _: None)['choices'][0]['message']['tool_calls']
        args = json.loads(call()[0]['function']['arguments'])
        self.assertIn('sleep 61', args['command']); self.assertNotIn('timeout', args)
        self.assertEqual(len(call(['LONG_COMMAND_OK'])), 8)
        self.assertEqual(len(call([json.dumps({'job_id': str(i)}) for i in range(8)])), 65)
        call([json.dumps({'job_id': str(i)}) for i in range(8, 73)])
        self.assertEqual(len(call(['JOBS_WAITED'])), 73)
        self.assertEqual(json.loads(call([json.dumps({'exit_code': 0})] * 73)[0]['function']['arguments'])['command'], probe.PROCESS_COMMAND)
        self.assertEqual(json.loads(call(['NC_CAPTURE_UNMATCHED'])[0]['function']['arguments'])['command'], probe.LARGE_COMMAND)
        call(['NC_LARGE_COMMAND_OK'])
        for index in range(1, 7):
            call([json.dumps({'status': 'repair_requested', 'terminal': False, 'repair_number': index})])
        final = call([json.dumps({'status': 'repair_requested', 'terminal': False, 'repair_number': 7})])
        self.assertTrue(json.loads(final[0]['function']['arguments'])['checks'])
        self.assertEqual(provider.calls, probe.EXPECTED_LOGICAL + 1)

    def test_failed_observation_cannot_be_counted_as_qualification(self):
        for count, contents in ((11, ['failed']), (15, [json.dumps({'exit_code': 124})] * 73),
                (16, ['NC_CAPTURE_MATCHED']), (17, ['failed-large']),
                (18, [json.dumps({'status': 'repair_exhausted', 'terminal': True})])):
            provider = probe.SyntheticProvider('synthetic-not-a-real-key', clock=Clock()); provider.calls = count
            with self.subTest(count=count), self.assertRaises(AssertionError):
                provider.complete(self.request(contents), on_response_headers=lambda _: None)

    def test_sizeable_encoded_command_runs_without_changed_decoded_content(self):
        # Real harmless local capture; the native fixture later exercises RPC.
        import shlex
        command = probe.LARGE_COMMAND.replace('python3 -c', shlex.quote(sys.executable) + ' -c', 1)
        encoded = encoded_capture_script(command, 5, 64000)
        self.assertGreater(len(encoded), 32768)
        result = subprocess.run([sys.executable, '-c', encoded], capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout)['output'], 'NC_LARGE_COMMAND_OK\n')

    def test_fixture_record_is_separate_and_rejected_by_production(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = private_directory(Path(folder) / '.runtime/stage2')
            trial = 'synthetic-nc-tools'
            value = dict(kind=probe.FIXTURE_KIND, paid_launch_ready=False, live_api_calls=0,
                stage='development', condition='C0-NC', trial_id=trial,
                model_protocol_sha256=policy.SETTINGS.fingerprint())
            durable_json(runtime / probe.FIXTURE_FILE, value)
            self.assertEqual(probe.isolated_fixture(runtime, trial, 'development'), value)
            for bad, stage in ((trial, 'final'), ('customdev4-c0-nc-01-video-processing', 'development')):
                with self.assertRaises(ValueError): probe.isolated_fixture(runtime, bad, stage)
            with self.assertRaises(ValueError): policy.require_trial(runtime, trial, 'development')
            self.assertFalse((runtime / policy.QUALIFICATION).exists())
            self.assertFalse(policy.block_path(runtime).exists())

    def test_fixture_session_cannot_accept_a_real_transport(self):
        session = object.__new__(probe.FixtureRetrySession)
        session.client = object()
        with self.assertRaises(ValueError): session.require_session_policy()

    def test_network_interface_guard_rejects_external_network(self):
        with patch.object(Path, 'iterdir', return_value=iter([Path('lo'), Path('eth0')])):
            with self.assertRaises(ValueError): probe.require_network_isolation()
        with patch.object(Path, 'iterdir', return_value=iter([Path('lo')])):
            probe.require_network_isolation()

    def test_native_fixture_keeps_real_scored_verifier_and_owned_process_matching(self):
        code = Path(probe.__file__).read_text()
        self.assertIn("gateway['network_mode'] = 'none'", code)
        self.assertIn('client_factory=SyntheticProvider', code)
        self.assertIn('session_factory=FixtureRetrySession', code)
        self.assertIn('await execution', code)
        self.assertIn('expected_verifier_result', code)
        self.assertNotIn("status='passed', sources_sha256", code)
        self.assertNotIn('pkill', probe.PROCESS_COMMAND)
        self.assertIn('getppid()', probe.PROCESS_COMMAND)
        self.assertIn('os.kill(p,signal.SIGTERM)', probe.PROCESS_COMMAND)
        self.assertNotIn('uts_nc_owned_capture_match_fixture', encoded_capture_script(probe.PROCESS_COMMAND, 5, 64000))

    def test_gateway_fixture_imports_without_agent_or_host_stack(self):
        script = """
import sys
class Block:
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'harbor','deepagents','langgraph','direct_final_evidence','no_cutoff_custom_runtime','no_cutoff_custom_study'}:
   raise RuntimeError('Heavy module imported: '+fullname)
sys.meta_path.insert(0,Block())
import no_cutoff_custom_probe
"""
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=Path(__file__).parent,
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
