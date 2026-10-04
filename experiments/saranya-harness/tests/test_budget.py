"""Offline tests for the spending safety stop."""
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from saranya_harness.budget import (DEFAULT_PER_TRIAL_CAP_USD, LEDGER_ENV, OVERALL_CAP_ENV, BudgetGuard,
                                    reservation_for)


class BudgetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / 'ledger.jsonl'

    def tearDown(self):
        self.tmp.cleanup()

    def records(self, kind):
        return [r for r in map(json.loads, self.ledger.read_text().splitlines()) if r['kind'] == kind]

    def test_default_per_trial_cap_is_well_above_c0_maximum(self):
        c0_highest_per_trial_known_cost = Decimal('0.37851930')  # video-processing, c0/trials.csv
        self.assertGreaterEqual(DEFAULT_PER_TRIAL_CAP_USD, 3 * c0_highest_per_trial_known_cost)

    def test_reservation_covers_full_output_allowance(self):
        self.assertGreater(reservation_for(0), Decimal('0.069'))

    def test_per_trial_stop_triggers_and_is_logged(self):
        guard = BudgetGuard(self.ledger, 't1', per_trial_cap_usd=Decimal('0.10'), overall_cap_usd=Decimal('5'))
        _, stop = guard.check(1000)
        self.assertIsNone(stop)
        guard.record(charged_usd=Decimal('0.05'), cost_source='reported')
        with self.assertLogs('saranya_harness.budget', 'WARNING'):
            _, stop = guard.check(1000)
        self.assertEqual(stop.scope, 'per_trial')
        [logged] = self.records('stop')
        self.assertEqual((logged['trial_id'], logged['scope']), ('t1', 'per_trial'))

    def test_overall_cap_is_shared_across_trials(self):
        first = BudgetGuard(self.ledger, 't1', per_trial_cap_usd=Decimal('1'), overall_cap_usd=Decimal('0.15'))
        first.record(charged_usd=Decimal('0.12'), cost_source='reported')
        second = BudgetGuard(self.ledger, 't2', per_trial_cap_usd=Decimal('1'), overall_cap_usd=Decimal('0.15'))
        with self.assertLogs('saranya_harness.budget', 'WARNING'):
            _, stop = second.check(1000)
        self.assertEqual(stop.scope, 'overall')
        self.assertEqual(stop.spent_usd, Decimal('0.12'))

    def test_no_overall_cap_means_no_spending(self):
        with mock.patch.dict('os.environ', {LEDGER_ENV: str(self.ledger)}, clear=True):
            with self.assertRaisesRegex(ValueError, OVERALL_CAP_ENV):
                BudgetGuard.from_environment('t1')

    def test_no_ledger_means_no_spending(self):
        with mock.patch.dict('os.environ', {OVERALL_CAP_ENV: '3'}, clear=True):
            with self.assertRaisesRegex(ValueError, LEDGER_ENV):
                BudgetGuard.from_environment('t1')

    def test_environment_configuration(self):
        with mock.patch.dict('os.environ', {OVERALL_CAP_ENV: '3', LEDGER_ENV: str(self.ledger)}, clear=True):
            guard = BudgetGuard.from_environment('t1')
        self.assertEqual((guard.per_trial_cap, guard.overall_cap), (DEFAULT_PER_TRIAL_CAP_USD, Decimal('3')))


if __name__ == '__main__':
    unittest.main()
