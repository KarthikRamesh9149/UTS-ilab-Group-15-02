import fcntl
from pathlib import Path
import tempfile
import unittest

from budget_ledger import Ledger, dollars
from gateway_policy import MODEL
from reconcile_pending import reconcile
from scored_gateway import durable_json, private_directory


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.attempt = private_directory(self.runtime / 'native-setup-attempts' / 'fixture')
        self.ledger = Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        self.ledger.reserve('r', 'fixture', '.1', '12', 'setup')
        self.ledger.attach_generation('r', 'g')
        durable_json(self.attempt / '000001.response.json', {'id': 'g', 'model': MODEL, 'usage': {'cost': '.001'}})
        self.calls = []
        self.receipt = {'id': 'g', 'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.001'}

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def generation(self, identifier):
        self.calls.append(identifier)
        return self.receipt

    def test_settles_exact_existing_charge_without_replay_or_score_change(self):
        result = reconcile(self.root, kind='setup', trial_id='fixture', client=self)
        self.assertEqual(self.calls, ['g'])
        self.assertTrue(result['score_unchanged'])
        self.assertEqual(self.ledger.exposure(), dollars('.001'))
        self.assertEqual(self.ledger.pending(), [])
        self.assertTrue((self.attempt / '000001.receipt.json').exists())
        self.assertFalse((self.attempt / 'result.json').exists())

    def test_mismatch_preserves_reservation(self):
        self.receipt['total_cost'] = '.002'
        with self.assertRaises(ValueError):
            reconcile(self.root, kind='setup', trial_id='fixture', client=self)
        self.assertEqual(self.ledger.exposure(), dollars('.1'))
        self.assertFalse((self.attempt / '000001.receipt.json').exists())

    def test_active_runner_blocks_reconciliation(self):
        with (self.runtime / 'scored.lock').open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                reconcile(self.root, kind='setup', trial_id='fixture', client=self)
        self.assertEqual(self.calls, [])

    def test_unknown_generation_never_guesses_or_releases_funds(self):
        self.ledger.db.execute('DELETE FROM generations')
        with self.assertRaises(ValueError):
            reconcile(self.root, kind='setup', trial_id='fixture', client=self)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ledger.exposure(), dollars('.1'))
