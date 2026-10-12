"""Synthetic admission checks; no API credentials or benchmark scores."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from gemini_baseline_run import run
from gemini_same_cap import SameCapBaselineLedger, suffix_inputs, validate_resume_review
from gemini_laptop_policy import atomic_json, BudgetStop, money, SNAPSHOT


class SameCapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prior_path = self.root / 'ledger.json'
        self.grant = dict(total_cap_usd='50', additional_cap_usd='30',
            user_answer='Allow up to US$30 additional, spending as little as possible')
        self.prior = dict(cap_usd='50', authorization=self.grant, requests=[
            dict(sequence=0, trial_id='closed', reserved_usd='1.10', cost_usd='.30', status='settled'),
            dict(sequence=1, trial_id='old-unknown', reserved_usd='1.10', cost_usd=None, status='reserved'),
            dict(sequence=2, trial_id='new-unknown', reserved_usd='1.10', cost_usd=None, status='reserved')])
        atomic_json(self.prior_path, self.prior)
        self.raw = self.prior_path.read_bytes()
        self.cells = [dict(order=i+1, trial_id=f'trial-{i}', task_id=f'task-{i//2}',
            harness='terminus-2' if i%2 == 0 else 'openhands') for i in range(40)]
        rows = [{**c, 'task_containers_removed': True, 'model_revoked': True,
                 'cleanup_errors': [], 'trace_errors': []} for c in self.cells[:18]]
        atomic_json(self.root / 'tasks.json', rows)
        self.manifest = dict(scope='preparation_only_not_a_paid_run_authorization',
            prior_ledger_sha256=hashlib.sha256(self.raw).hexdigest(),
            completed_tasks_sha256=hashlib.sha256((self.root/'tasks.json').read_bytes()).hexdigest(),
            inherited_cap_usd='50', proposed_total_cap_usd='50', additional_allowance_usd='0',
            inherited_physical_requests=3, inherited_known_usd='.30',
            inherited_unresolved_reserved_usd='2.20', remaining_conservative_usd='47.50',
            completed_attempts=18, remaining_cells=self.cells[18:], closed_attempt_replays=0)

    def ledger(self, manifest=None, cells=None):
        return SameCapBaselineLedger(self.root/'suffix/ledger.json', 100,
            prior_path=self.prior_path, prior_sha256=self.manifest['prior_ledger_sha256'],
            cells={'new': 'terminus-2'} if cells is None else cells,
            manifest=self.manifest if manifest is None else manifest)

    def test_both_unknown_reserves_and_existing_grant_preserved(self):
        ledger = self.ledger()
        ledger.settle(ledger.reserve('new', 100), '.02')
        self.assertEqual(ledger.known, money('.32'))
        self.assertEqual(ledger.unresolved, money('2.20'))
        self.assertEqual(ledger.data['authorization'], self.grant)
        self.assertEqual(ledger.data['cap_usd'], '50')
        self.assertEqual(ledger.data['requests'][:3], self.prior['requests'])
        self.assertEqual(self.prior_path.read_bytes(), self.raw)

    def test_lower_live_credit_stops_before_reservation(self):
        ledger = self.ledger()
        with self.assertRaises(BudgetStop):
            ledger.reserve('new', '3.29')
        self.assertEqual(len(ledger.data['requests']), 3)

    def test_total_allowance_does_not_reset(self):
        ledger = self.ledger()
        for _ in range(43):
            ledger.settle(ledger.reserve('new', 100), '1.10')
        with self.assertRaises(BudgetStop):
            ledger.reserve('new', 100)
        self.assertLessEqual(ledger.known + ledger.unresolved, money('50'))

    def test_cannot_release_inherited_unknown(self):
        ledger = self.ledger()
        with self.assertRaises(ValueError):
            ledger.settle(ledger.data['requests'][2], '0')

    def test_cannot_register_closed_trial(self):
        with self.assertRaises(ValueError):
            self.ledger(cells={'closed': 'terminus-2'})

    def test_cannot_grant_more_money(self):
        for field, value in [('proposed_total_cap_usd','80'), ('additional_allowance_usd','30')]:
            changed = copy.deepcopy(self.manifest)
            changed[field] = value
            with self.assertRaises(ValueError):
                self.ledger(changed)

    def test_missing_reserve_rejected(self):
        changed = copy.deepcopy(self.manifest)
        changed['inherited_unresolved_reserved_usd'] = '1.10'
        with self.assertRaises(ValueError):
            self.ledger(changed)

    def test_changed_prefix_or_authorization_rejected(self):
        ledger = self.ledger()
        ledger.data['requests'][0]['cost_usd'] = '0'
        with self.assertRaises(ValueError):
            ledger.reserve('new', 100)
        ledger.data = copy.deepcopy(self.prior)
        ledger.data['authorization']['total_cap_usd'] = '80'
        with self.assertRaises(ValueError):
            ledger.reserve('new', 100)

    def test_prior_hash_mismatch_rejected(self):
        changed = copy.deepcopy(self.manifest)
        changed['prior_ledger_sha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.ledger(changed)

    def test_reopened_suffix_preserves_prefix(self):
        ledger = self.ledger()
        ledger.settle(ledger.reserve('new', 100), '.01')
        reopened = self.ledger()
        self.assertEqual(reopened.known, money('.31'))
        self.assertEqual(reopened.unresolved, money('2.20'))

    def test_only_exact_twenty_two_suffix_admitted(self):
        _, rows, suffix = suffix_inputs(self.root, self.manifest, self.cells)
        self.assertEqual(len(rows), 18)
        self.assertEqual(suffix, self.cells[18:])
        self.assertEqual(len(suffix), 22)

    def test_reordered_or_replayed_suffix_rejected(self):
        changed = copy.deepcopy(self.manifest)
        changed['remaining_cells'] = list(reversed(changed['remaining_cells']))
        with self.assertRaises(ValueError):
            suffix_inputs(self.root, changed, self.cells)
        changed = copy.deepcopy(self.manifest)
        changed['closed_attempt_replays'] = 1
        with self.assertRaises(ValueError):
            suffix_inputs(self.root, changed, self.cells)

    def test_mutated_outcomes_hash_rejected(self):
        atomic_json(self.root/'tasks.json', [])
        with self.assertRaises(ValueError):
            suffix_inputs(self.root, self.manifest, self.cells)

    def test_failed_cleanup_rejected_even_with_matching_hash(self):
        path = self.root/'tasks.json'
        rows = json.loads(path.read_text())
        rows[-1]['task_containers_removed'] = False
        atomic_json(path, rows)
        self.manifest['completed_tasks_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            suffix_inputs(self.root, self.manifest, self.cells)

    def test_preparation_flag_cannot_start_paid_work(self):
        args = SimpleNamespace(same_cap_manifest=Path('manifest.json'), qualify=False,
            continuation_root=Path('closed'), authorization=None)
        with self.assertRaisesRegex(ValueError, 'key-free qualification'):
            asyncio.run(run(args))

    def test_resume_review_preserves_cap_and_binds_exact_evidence(self):
        review = dict(scope='continue_unstarted_native_suffix',user_message='continue the gemini one',
            total_cap_usd='50',additional_allowance_usd='0',manifest_sha256='a'*64,
            prior_ledger_sha256=self.manifest['prior_ledger_sha256'],
            completed_tasks_sha256=self.manifest['completed_tasks_sha256'],
            upstream_model=SNAPSHOT,preserve_unresolved_reserves=True,replays=0)
        self.assertEqual(validate_resume_review(review,self.manifest,'a'*64),review)
        for field,value in [('total_cap_usd','80'),('additional_allowance_usd','30'),
                            ('upstream_model','google/gemini-3.8-flash'),
                            ('preserve_unresolved_reserves',False),('manifest_sha256','b'*64)]:
            bad=copy.deepcopy(review);bad[field]=value
            with self.assertRaises(ValueError): validate_resume_review(bad,self.manifest,'a'*64)


if __name__ == '__main__':
    unittest.main()
