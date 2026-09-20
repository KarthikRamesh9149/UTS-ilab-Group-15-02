"""Portable synthetic evidence fixtures; production pins are never relaxed.

Only expected content hashes are substituted in the fixture. Ledger identity,
money, original rows, private paths, and all validator decisions stay real.
An additional archive-based read-only check is run separately before release.
"""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import historical_hold as hh
from budget_ledger import Ledger, BudgetExceeded
from model_protocol import ModelSettings, freeze_protocol
from scored_gateway import durable_json, private_directory
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS


class HoldFixture:
    def __init__(self, root, *, registered=True):
        self.root = Path(root)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        setup_path = self.runtime / 'setup_budget.sqlite'
        if not setup_path.exists():
            Ledger(setup_path, '1', '1', {'setup': '1'}).close()
            setup_path.chmod(0o600)
        self.settings = ModelSettings(8192, 1., 'high')
        freeze_protocol(self.runtime, self.settings)
        self.attempt = private_directory(private_directory(self.runtime / 'scored-attempts') / hh.TRIAL_ID)
        hashes = {}
        for name in hh.ATTEMPT_HASHES:
            durable_json(self.attempt / name, {'synthetic_evidence': name})
            hashes[name] = hashlib.sha256((self.attempt / name).read_bytes()).hexdigest()
        output = private_directory(private_directory(self.runtime / 'scored-trials') / hh.TRIAL_ID)
        self.result = output / 'result.json'
        durable_json(self.result, {'trial_id': hh.TRIAL_ID, 'status': 'billing_unresolved',
                                  'billing': {'billing_verified': False}})
        self.patches = ExitStack()
        self.patches.enter_context(patch.object(hh, 'ATTEMPT_HASHES', hashes))
        self.patches.enter_context(patch.object(hh, 'RESULT_SHA256', hashlib.sha256(self.result.read_bytes()).hexdigest()))
        ledger = self.ledger(enabled=False)
        with ledger.transaction():
            ledger.db.execute('INSERT INTO trial_stages VALUES (?,?)', (hh.TRIAL_ID, 'development'))
            for identifier, reserved, charge, state, estimate, generation, receipt_state in hh.ORIGINAL_ROWS:
                ledger.db.execute('INSERT INTO requests VALUES (?,?,?,?,?)',
                                  (identifier, hh.TRIAL_ID, reserved, charge, state))
                ledger.db.execute('INSERT INTO trial_estimates VALUES (?,?)', (identifier, estimate))
                if generation is not None:
                    ledger.db.execute('INSERT INTO generations VALUES (?,?)', (identifier, generation))
                if receipt_state is not None:
                    ledger.db.execute('INSERT INTO receipt_checks VALUES (?,?)', (identifier, receipt_state))
        ledger.close()
        if registered:
            durable_json(self.runtime / hh.SIDECAR, hh.canonical_hold_document())

    def ledger(self, *, enabled=True):
        return Ledger(self.runtime / 'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP,
                      STAGE_CAPS, allow_estimated_trials=True,
                      historical_hold_runtime=self.runtime if enabled else None)

    def close(self):
        self.patches.close()


class HistoricalHoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = HoldFixture(self.temp.name)
        self.runtime = self.fixture.runtime
        self.ledger = self.fixture.ledger()

    def tearDown(self):
        self.ledger.close()
        self.fixture.close()
        self.temp.cleanup()

    def test_exact_hold_keeps_pending_unknown_and_read_only(self):
        database = self.runtime / 'scored_budget.sqlite'
        before = database.read_bytes()
        hold = hh.validate_historical_hold(self.runtime)
        self.assertEqual(database.read_bytes(), before)
        self.assertEqual(hold['reserved_nanodollars'], 106496000)
        self.assertIsNone(hold['charged_nanodollars'])
        self.assertFalse(hold['billing_verified'])
        self.assertEqual(hold['budget_stop_count'], 2)
        self.assertEqual(hold['capacity_budget_stop_count'], 0)
        self.assertEqual(len(self.ledger.pending()), 1)
        self.assertEqual(self.ledger.blocking_pending(), [])

    def test_no_amendment_keeps_old_barrier(self):
        (self.runtime / hh.SIDECAR).unlink()
        self.assertIsNone(hh.validate_historical_hold(self.runtime))
        self.assertEqual(len(self.ledger.blocking_pending()), 1)
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('new', 'new', '.1', '12', 'development', trial_estimate='.01')

    def test_default_ledger_does_not_use_present_amendment(self):
        default = self.fixture.ledger(enabled=False)
        try:
            self.assertEqual(len(default.blocking_pending()), 1)
            with self.assertRaises(BudgetExceeded):
                default.reserve('new', 'new', '.1', '12', 'development', trial_estimate='.01')
        finally:
            default.close()

    def test_tampering_sidecar_result_request_or_inventory_fails(self):
        paths = [self.runtime / hh.SIDECAR, self.fixture.result,
                 self.fixture.attempt / '000003.request.json']
        for path in paths:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(b'{}')
                with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime)
                path.write_bytes(original)
        durable_json(self.fixture.attempt / '000003.receipt.json', {'total_cost': 0})
        with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime)

    def test_private_sidecar_and_regular_evidence_required(self):
        path = self.runtime / hh.SIDECAR
        path.chmod(0o644)
        with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime)
        path.chmod(0o600)
        moved = self.runtime / 'sidecar-copy'
        path.rename(moved)
        path.symlink_to(moved)
        with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime)

    def test_original_rows_estimate_and_generation_cannot_change(self):
        for statement, arguments in [
            ('UPDATE requests SET charged=0 WHERE id=?', (hh.REQUEST_ID,)),
            ('UPDATE trial_estimates SET amount=1 WHERE request_id=?', (hh.REQUEST_ID,)),
            ('INSERT INTO generations VALUES (?,?)', (hh.REQUEST_ID, 'fabricated')),
        ]:
            with self.subTest(statement=statement):
                self.ledger.db.execute('BEGIN IMMEDIATE')
                try:
                    self.ledger.db.execute(statement, arguments)
                    with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime, self.ledger.db)
                finally:
                    self.ledger.db.execute('ROLLBACK')

    def test_second_pending_incident_or_hidden_unverified_receipt_blocks(self):
        for statement in [
            "INSERT INTO requests VALUES ('second','new',1,NULL,'pending')",
            "INSERT INTO incidents VALUES ('unknown',1)",
            "INSERT INTO receipt_checks VALUES ('orphan','pending')",
        ]:
            with self.subTest(statement=statement):
                self.ledger.db.execute('BEGIN IMMEDIATE')
                try:
                    self.ledger.db.execute(statement)
                    with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime, self.ledger.db)
                finally:
                    self.ledger.db.execute('ROLLBACK')

    def test_original_trial_is_forbidden_even_before_new_evidence(self):
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('new', hh.TRIAL_ID, '.1', '12', 'development', trial_estimate='.01')
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 3)

    def test_validator_requires_transaction_on_canonical_connection(self):
        with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime, self.ledger.db)


if __name__ == '__main__':
    unittest.main()
