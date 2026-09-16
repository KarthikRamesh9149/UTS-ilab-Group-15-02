from pathlib import Path
import sqlite3
import tempfile
import unittest

from budget_ledger import BudgetExceeded, Ledger, dollars


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'ledger.sqlite'
        self.ledger = Ledger(self.path, '.10', '.055')

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_exact_money(self):
        self.assertEqual(dollars('.055'), 55_000_000)
        for invalid in ['NaN', 'Infinity', '-1', '.0000000001']:
            with self.assertRaises(ValueError):
                dollars(invalid)

    def test_trial_and_project_caps(self):
        self.ledger.reserve('a', 'trial1', '.055', '25')
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('b', 'trial1', '.001', '25')
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('c', 'trial2', '.055', '25')

    def test_reserve_keeps_account_buffer(self):
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('a', 'trial', '.055', '2.054')

    def test_crash_retains_reservation_and_blocks_duplicate(self):
        self.ledger.reserve('a', 'trial', '.055', '25')
        other = Ledger(self.path, '.10', '.055')
        try:
            self.assertEqual(other.exposure(), dollars('.055'))
            with self.assertRaises((sqlite3.IntegrityError, BudgetExceeded)):
                other.reserve('a', 'trial', '.001', '25')
        finally:
            other.close()

    def test_settlement_and_conflicting_evidence(self):
        self.ledger.reserve('a', 'trial', '.055', '25')
        self.ledger.settle('a', '.01')
        self.ledger.settle('a', '.01')
        self.assertEqual(self.ledger.exposure(), dollars('.01'))
        with self.assertRaises(ValueError):
            self.ledger.settle('a', '.02')

    def test_overcharge_not_silently_accepted(self):
        self.ledger.reserve('a', 'trial', '.01', '25')
        with self.assertRaises(BudgetExceeded):
            self.ledger.settle('a', '.02')
        self.assertEqual(self.ledger.exposure(), dollars('.02'))
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('b', 'other', '.001', '25')

    def test_policy_cannot_be_raised_on_reopen(self):
        with self.assertRaises(ValueError):
            Ledger(self.path, '30', '.055')


if __name__ == '__main__':
    unittest.main()
