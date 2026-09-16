from pathlib import Path
import tempfile
import unittest

from budget_ledger import Ledger, BudgetExceeded, dollars
from gateway_core import Gateway, Trial, token_digest
from gateway_policy import MODEL


class EstimatedBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'ledger.sqlite'
        self.ledger = Ledger(self.path, '.20', '.055', {'dev': '.15', 'final': '.05'}, allow_estimated_trials=True)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_small_trial_estimate_keeps_full_global_reservation(self):
        self.ledger.reserve('a', 't', '.104', '25', 'dev', trial_estimate='.01')
        self.assertEqual(self.ledger.exposure(), dollars('.104'))
        self.assertEqual(self.ledger.pending()[0][2], dollars('.104'))
        self.ledger.settle('a', '.003')
        self.assertEqual(self.ledger.exposure(), dollars('.003'))

    def test_hard_stage_and_account_bounds_are_not_estimates(self):
        for stage, credit in [('final', '25'), ('dev', '2.02')]:
            with self.assertRaises(BudgetExceeded):
                self.ledger.reserve('a', 't', '.104', credit, stage, trial_estimate='.001')
        self.assertEqual(self.ledger.exposure(), 0)

    def test_hard_project_bound_remains(self):
        other = Ledger(Path(self.temp.name) / 'small.sqlite', '.10', '.055', allow_estimated_trials=True)
        try:
            with self.assertRaises(BudgetExceeded):
                other.reserve('a', 't', '.104', '25', trial_estimate='.001')
        finally:
            other.close()

    def test_underestimate_persists_charge_and_halt_across_restart(self):
        self.ledger.reserve('a', 't', '.104', '25', 'dev', trial_estimate='.001')
        with self.assertRaises(BudgetExceeded):
            self.ledger.settle('a', '.002')
        self.assertEqual(self.ledger.exposure(), dollars('.002'))
        self.assertEqual(self.ledger.pending(), [])
        other = Ledger(self.path, '.20', '.055', {'dev': '.15', 'final': '.05'}, allow_estimated_trials=True)
        try:
            with self.assertRaises(BudgetExceeded):
                other.reserve('b', 'different', '.104', '25', 'dev', trial_estimate='.001')
        finally:
            other.close()

    def test_trial_spend_uses_settled_actual_costs(self):
        self.ledger.reserve('a', 't', '.104', '25', 'dev', trial_estimate='.05')
        self.ledger.settle('a', '.05')
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('b', 't', '.09', '25', 'dev', trial_estimate='.006')

    def test_invalid_estimates_and_immutable_mode(self):
        for estimate in ['0', '-1', '.105', 'NaN']:
            with self.assertRaises(ValueError):
                self.ledger.reserve('a', 't', '.104', '25', 'dev', trial_estimate=estimate)
        with self.assertRaises(ValueError):
            Ledger(self.path, '.20', '.055', {'dev': '.15', 'final': '.05'})
        strict = Ledger(Path(self.temp.name) / 'strict.sqlite', '.20', '.055')
        try:
            with self.assertRaises(ValueError):
                strict.reserve('a', 't', '.104', '25', trial_estimate='.001')
        finally:
            strict.close()

    def test_gateway_reserves_before_dispatch_and_stops_on_underestimate(self):
        calls = []
        def upstream(request):
            self.assertEqual(self.ledger.exposure(), dollars('.104'))
            calls.append(request)
            return {'id': 'synthetic-estimation', 'model': MODEL, 'usage': {'cost': '.002'}}
        gateway = Gateway(self.ledger, Trial('t', 'dev', token_digest('fixture')), lambda: '25',
            lambda r: '.104', upstream,
            lambda identifier: {'id': identifier, 'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.002'},
            trial_estimate=lambda r: '.001')
        payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'fixture'}], 'max_tokens': 64}
        for _ in range(2):
            with self.assertRaises(BudgetExceeded):
                gateway.complete('fixture', payload)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
