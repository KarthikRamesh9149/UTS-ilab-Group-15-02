import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal
from rerun_budget import NAME, read_profile
from budget_ledger import Ledger, BudgetExceeded


class RepeatBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / '.runtime/stage2' / NAME
        self.path.parent.mkdir(parents=True)
        self.value = dict(experiment='baseline-repeat-20260921', authorised_utc_date='2026-09-21',
                          reserve_usd='1.00', historical_liability_usd='7.774208',
                          starting_balance_usd='11.540139332', ceiling_usd='2.765931332')

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.path.write_text(json.dumps(self.value)); self.path.chmod(0o600)

    def test_absent_preserves_original(self):
        self.assertIsNone(read_profile(self.root))

    def test_exact_funded_profile(self):
        self.write(); self.assertEqual(read_profile(self.root), self.value)

    def test_cannot_ignore_old_liability(self):
        self.value['ceiling_usd'] = '10.540139332'; self.write()
        with self.assertRaises(ValueError): read_profile(self.root)

    def test_reserve_cannot_be_zero(self):
        self.value['reserve_usd'] = '0'; self.write()
        with self.assertRaises(ValueError): read_profile(self.root)

    def test_nonfinite_rejected(self):
        self.value['ceiling_usd'] = 'NaN'; self.write()
        with self.assertRaises(ValueError): read_profile(self.root)

    def test_public_profile_rejected(self):
        self.write(); self.path.chmod(0o644)
        with self.assertRaises(ValueError): read_profile(self.root)

    def test_one_dollar_floor_and_no_small_trial_cap(self):
        with patch('study_budget.ACCOUNT_RESERVE', '1.00'):
            ledger = Ledger(self.root/'new.sqlite', '2.765931332', '2.765931332')
            ledger.reserve('one', 'repeat-a', '.106496', '1.106496')
            ledger.settle('one', '.04')
            ledger.reserve('two', 'repeat-a', '.106496', '1.106496')
            ledger.settle('two', '.04')
            with self.assertRaises(BudgetExceeded):
                ledger.reserve('three', 'repeat-a', '.106496', '1.106495999')

    def test_same_total_ceiling_still_enforced(self):
        with patch('study_budget.ACCOUNT_RESERVE', '1.00'):
            ledger = Ledger(self.root/'new.sqlite', '.15', '.15')
            ledger.reserve('one', 'repeat-a', '.1', '20'); ledger.settle('one', '.1')
            with self.assertRaises(BudgetExceeded): ledger.reserve('two', 'repeat-b', '.1', '20')

    def test_old_liability_subtracted_each_balance_check(self):
        from scored_gateway import ScoredSession
        session = object.__new__(ScoredSession)
        session.runtime = self.path.parent
        session.available_balance = lambda: Decimal('11.540139332')
        with (patch('scored_gateway.require_clear_setup_ledger', return_value=Decimal('0')),
              patch('scored_gateway.HISTORICAL_LIABILITY', '7.774208')):
            self.assertEqual(session.scored_available_balance(), Decimal('3.765931332'))

if __name__ == '__main__': unittest.main()
