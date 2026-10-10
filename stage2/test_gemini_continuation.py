"""Key-free continuation admission and immutable budget extension checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from gemini_baseline_budget import ExtendedBaselineLedger
from gemini_baseline_run import continuation_inputs
from gemini_laptop_policy import atomic_json, BudgetStop, money


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prior = self.root / 'ledger.json'
        atomic_json(self.prior, {'cap_usd': '20', 'requests': [
            dict(sequence=0, trial_id='closed', reserved_usd='1.10', cost_usd='17.808674700', status='settled'),
            dict(sequence=1, trial_id='unknown', reserved_usd='1.10', cost_usd=None, status='reserved')]})
        self.original = self.prior.read_bytes()
        self.auth = dict(prior_ledger_sha256=hashlib.sha256(self.original).hexdigest(),
            additional_cap_usd='30', total_cap_usd='50',
            user_answer='Allow up to US$30 additional, spending as little as possible', completed_attempts=3)

    def ledger(self, auth=None):
        return ExtendedBaselineLedger(self.root / 'new/ledger.json', 100, prior_path=self.prior,
            prior_sha256=self.auth['prior_ledger_sha256'], cells={'new': 'terminus-2'},
            authorization=self.auth if auth is None else auth)

    def test_extension_preserves_all_prior_requests_and_unknown_reserve(self):
        ledger = self.ledger()
        row = ledger.reserve('new', 100)
        ledger.settle(row, '.01')
        self.assertEqual(ledger.known, money('17.818674700'))
        self.assertEqual(ledger.unresolved, money('1.10'))
        self.assertEqual(ledger.data['cap_usd'], '50')
        self.assertEqual(self.prior.read_bytes(), self.original)
        self.assertEqual(ledger.data['requests'][:2], json.loads(self.original)['requests'])

    def test_credit_limit_is_independent_of_authorized_cap(self):
        ledger = self.ledger()
        with self.assertRaises(BudgetStop):
            ledger.reserve('new', '2.19')
        self.assertEqual(len(ledger.data['requests']), 2)

    def test_total_cap_denies_before_reserving(self):
        ledger = self.ledger()
        for _ in range(28):
            ledger.settle(ledger.reserve('new', 100), '1.10')
        with self.assertRaises(BudgetStop):
            ledger.reserve('new', 100)
        self.assertLessEqual(ledger.known + ledger.unresolved, money(50))

    def test_inherited_requests_cannot_be_settled_or_replayed(self):
        ledger = self.ledger()
        with self.assertRaises(ValueError):
            ledger.settle(ledger.data['requests'][1], '0')
        with self.assertRaises(ValueError):
            ledger.reserve('closed', 100)

    def test_cap_change_requires_exact_user_authorization(self):
        bad = copy.deepcopy(self.auth)
        bad['total_cap_usd'] = '80'
        with self.assertRaises(ValueError):
            self.ledger(bad)

    def test_mutated_prefix_is_rejected(self):
        ledger = self.ledger()
        ledger.data['requests'][0]['cost_usd'] = '0'
        with self.assertRaises(ValueError):
            ledger.reserve('new', 100)

    def test_only_unstarted_suffix_is_selected(self):
        cells = [dict(order=i+1, trial_id=f'trial-{i}', task_id=f'task-{i//2}',
            harness='terminus-2' if i%2 == 0 else 'openhands') for i in range(40)]
        rows = [{**cell, 'task_containers_removed': True} for cell in cells[:3]]
        tasks = self.root / 'tasks.json'
        atomic_json(tasks, rows)
        self.auth['completed_tasks_sha256'] = hashlib.sha256(tasks.read_bytes()).hexdigest()
        _, inherited, remaining = continuation_inputs(self.root, self.auth, cells)
        self.assertEqual(inherited, rows)
        self.assertEqual(remaining, cells[3:])
        self.assertEqual(len(remaining), 37)
        cells[0]['task_id'] = 'other'
        with self.assertRaises(ValueError):
            continuation_inputs(self.root, self.auth, cells)


if __name__ == '__main__':
    unittest.main()
