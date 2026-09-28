"""Final fixture isolation and unchanged scripted provider; no native execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_final_probe as probe
import no_cutoff_final_policy as policy
import no_cutoff_custom_probe as measured
from no_cutoff_final_gateway import NoCutoffFinalSession
from scored_gateway import durable_json, private_directory
from test_retry_gateway import Clock


class ProbeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.rt = private_directory(Path(folder.name) / 'runtime')
        self.trial = 'synthetic-nc-final-tools'
        self.record = dict(kind=probe.FIXTURE_KIND, paid_launch_ready=False, live_api_calls=0,
            stage='final', condition='C0-NC', trial_id=self.trial, model_protocol_sha256=policy.SETTINGS.fingerprint())
        durable_json(self.rt / probe.FIXTURE_FILE, self.record)

    def test_only_exact_fixture_stage_and_keys_are_admitted(self):
        self.assertEqual(probe.isolated_fixture(self.rt, self.trial, 'final'), self.record)
        for trial, stage in ((self.trial, 'development'), ('synthetic-nc-tools', 'final'),
                ('customfinal2-c0-nc-01-video-processing', 'final')):
            with self.assertRaises(ValueError): probe.isolated_fixture(self.rt, trial, stage)

    def test_fixture_cannot_substitute_production_qualification_or_registration(self):
        with self.assertRaises(ValueError): policy.require_trial(self.rt, self.trial, 'final')
        with self.assertRaises(FileNotFoundError): policy.require_trial(self.rt, 'customfinal2-c0-nc-01-video-processing', 'final')
        self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())
        self.assertFalse(self.record['paid_launch_ready'])

    def test_tampered_fixture_flags_and_numeric_types_rejected(self):
        for change in ({'paid_launch_ready': True}, {'live_api_calls': False},
                {'live_api_calls': 1}, {'kind': 'paid-proof'}, {'stage': 'development'}, {'extra': True}):
            (self.rt / probe.FIXTURE_FILE).write_text(json.dumps(self.record | change))
            with self.subTest(change=change), self.assertRaises(ValueError):
                probe.isolated_fixture(self.rt, self.trial, 'final')

    def test_final_gateway_session_is_reused_with_only_fake_isolated_admission(self):
        self.assertEqual(probe.FixtureRetrySession.__bases__, (NoCutoffFinalSession,))
        session = object.__new__(probe.FixtureRetrySession)
        session.runtime = self.rt; session.trial_id = self.trial; session.stage = 'final'
        session.client = probe.SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
        with patch.object(probe, 'require_network_isolation') as isolation:
            session.require_session_policy(); session.require_recovery_policy()
            self.assertEqual(isolation.call_count, 2)
        session.client = object()
        with self.assertRaises(ValueError): session.require_session_policy()

    def test_network_failure_precedes_fixture_admission(self):
        session = object.__new__(probe.FixtureRetrySession)
        session.client = probe.SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
        with patch.object(probe, 'require_network_isolation', side_effect=ValueError('external network')), \
                patch.object(probe, 'isolated_fixture') as admit:
            with self.assertRaises(ValueError): session.require_session_policy()
            admit.assert_not_called()

    def test_gateway_uses_final_stage_fake_client_and_loopback_guard(self):
        with patch.object(probe, 'require_network_isolation') as isolation, patch('retry_gateway.serve') as serve:
            probe.gateway_fixture(self.trial, 900)
            isolation.assert_called_once()
            self.assertEqual(serve.call_args.args[2], 'final')
            self.assertIs(serve.call_args.kwargs['client_factory'], measured.SyntheticProvider)
            self.assertIs(serve.call_args.kwargs['session_factory'], probe.FixtureRetrySession)

    def test_measured_provider_and_long_command_job_capture_repair_checks_unchanged(self):
        self.assertIs(probe.SyntheticProvider, measured.SyntheticProvider)
        self.assertEqual(probe.EXPECTED_LOGICAL, measured.EXPECTED_LOGICAL)
        code = Path(probe.__file__).read_text()
        self.assertIn("gateway['network_mode'] = 'none'", code)
        self.assertIn("stage='final', agent_factory=create", code)
        self.assertIn("patch('no_cutoff_final_study.admit_trial'", code)
        self.assertIn("patch('run_no_cutoff_final.run_trial'", code)
        self.assertIn('await dispatch(fixture, block, stop=stop)', code)
        self.assertIn('final_gateway_identity=', code); self.assertIn('final_stage_accounting=', code)
        self.assertNotIn('policy.validate_qualification(', code)
        self.assertNotIn("status='passed', sources_sha256", code)
        for mode in policy.PROBE_MODES:
            self.assertEqual(policy.probe_checks(mode), policy.development.probe_checks(mode)
                | {'final_gateway_identity', 'final_stage_accounting'})

    def test_fixture_and_gateway_import_without_agent_or_evidence_stack(self):
        script = """
import sys
class Block:
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'harbor','deepagents','langgraph','direct_final_evidence',
   'no_cutoff_final_evidence','no_cutoff_final_runtime','no_cutoff_final_study','no_cutoff_evidence_freeze'}:
   raise RuntimeError('Heavy module imported: '+fullname)
sys.meta_path.insert(0,Block())
import no_cutoff_final_gateway, no_cutoff_final_probe
"""
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=Path(__file__).parent,
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
