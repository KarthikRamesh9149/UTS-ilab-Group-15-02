import os
from pathlib import Path
import tempfile
import unittest

from budget_ledger import Ledger, BudgetExceeded, dollars
from gateway_policy import MODEL
from model_protocol import ModelSettings
from native_setup_gateway import NativeSetupSession
from test_scored_gateway import Client


class NativeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / '.runtime/stage2'
        self.runtime.mkdir(parents=True, mode=0o700)
        ledger = Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        ledger.close()
        os.chmod(self.runtime / 'setup_budget.sqlite', 0o600)
        self.client = Client()
        self.settings = ModelSettings(8192, 1., 'high')

    def tearDown(self): self.temp.cleanup()

    def session(self, name='setup-native-fixture1'):
        return NativeSetupSession(self.root, name, 'a' * 64, self.client, settings=self.settings)

    def request(self):
        return dict(model=MODEL, messages=[{'role': 'user', 'content': 'fixture'}],
                    max_tokens=8192, temperature=1., reasoning={'effort': 'high'})

    def test_shared_setup_spend_survives_session_and_no_scored_ledger(self):
        with self.session() as session:
            session.complete('a' * 64, self.request())
            self.assertEqual(session.ledger.ceiling, dollars('1'))
            self.assertIsNone(session.gateway.trial_estimate)
        with self.session('setup-native-fixture2') as session:
            self.assertEqual(session.ledger.exposure(), dollars('.001'))
        self.assertFalse((self.runtime / 'scored_budget.sqlite').exists())

    def test_missing_existing_ledger_cannot_create_new_allowance(self):
        (self.runtime / 'setup_budget.sqlite').unlink()
        with self.assertRaises(FileNotFoundError): self.session()
        self.assertEqual(self.client.calls, 0)

    def test_prior_setup_spend_is_not_reset(self):
        ledger = Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        ledger.reserve('earlier-setup', 'earlier-probe', '.95', '25', 'setup')
        ledger.settle('earlier-setup', '.95')
        ledger.close()
        with self.session() as session:
            with self.assertRaises(BudgetExceeded): session.complete('a' * 64, self.request())
            self.assertEqual(session.ledger.exposure(), dollars('.95'))
            self.assertEqual(session.budget_stop_sequence, 1)
        self.assertEqual(self.client.calls, 0)

    def test_unknown_outcome_blocks_later_session(self):
        self.client.fail = True
        with self.session() as session:
            with self.assertRaises(Exception): session.complete('a' * 64, self.request())
        with self.assertRaises(BudgetExceeded): self.session('setup-native-fixture2')
        self.assertEqual(self.client.calls, 1)

    def test_finished_session_cannot_replay(self):
        with self.session(): pass
        with self.assertRaises(FileExistsError): self.session()

    def test_settings_drift_rejected_without_generation(self):
        with self.session() as session:
            request = self.request()
            request['temperature'] = 0
            with self.assertRaises(ValueError): session.complete('a' * 64, request)
        self.assertEqual(self.client.calls, 0)
