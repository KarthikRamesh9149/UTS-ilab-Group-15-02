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


class HoldFixtureV2(HoldFixture):
    """Synthetic immutable two-hold registry, with verified known receipts."""
    def __init__(self, root, *, registered=True):
        super().__init__(root, registered=False)
        self.second_attempt = private_directory(self.runtime / 'scored-attempts' / hh.SECOND_TRIAL_ID)
        hashes = {}
        for name in hh.SECOND_ATTEMPT_HASHES:
            durable_json(self.second_attempt / name, {'synthetic_second_evidence': name})
            hashes[name] = hashlib.sha256((self.second_attempt / name).read_bytes()).hexdigest()
        self.patches.enter_context(patch.object(hh, 'SECOND_ATTEMPT_HASHES', hashes))
        folder = private_directory(self.runtime / 'scored-trials' / hh.SECOND_TRIAL_ID)
        self.second_result = folder / 'result.json'
        self.results = {hh.TRIAL_ID: self.result, hh.SECOND_TRIAL_ID: self.second_result}
        self.attempts = {hh.TRIAL_ID: self.attempt, hh.SECOND_TRIAL_ID: self.second_attempt}
        for trial, task, constant in ((hh.TRIAL_ID, 'video-processing', 'RESULT_SHA256'),
                                      (hh.SECOND_TRIAL_ID, 'reshard-c4-data', 'SECOND_RESULT_SHA256')):
            value = {'trial_id': trial, 'task_id': task, 'stage': 'development', 'harness': 'terminus-2',
                     'model_protocol_sha256': self.settings.fingerprint(), 'status': 'billing_unresolved',
                     'billing': {'billing_verified': False}, 'verifier_result': {'rewards': {'reward': 0}},
                     'agent_error_type': 'APIError', 'model_revoked': True, 'containers_removed': True,
                     'networks_removed': True, 'volumes_removed': True}
            path = self.results[trial]
            if path.exists():
                path.write_text(json.dumps(value, sort_keys=True))
            else:
                durable_json(path, value)
            self.patches.enter_context(patch.object(hh, constant, hashlib.sha256(path.read_bytes()).hexdigest()))
        ledger = self.ledger(enabled=False)
        with ledger.transaction():
            ledger.db.execute('INSERT INTO trial_stages VALUES (?,?)', (hh.SECOND_TRIAL_ID, 'development'))
            for identifier, reserved, charge, state, estimate, generation, receipt_state in hh.SECOND_ORIGINAL_ROWS:
                ledger.db.execute('INSERT INTO requests VALUES (?,?,?,?,?)',
                                  (identifier, hh.SECOND_TRIAL_ID, reserved, charge, state))
                ledger.db.execute('INSERT INTO trial_estimates VALUES (?,?)', (identifier, estimate))
                if generation is not None:
                    ledger.db.execute('INSERT INTO generations VALUES (?,?)', (identifier, generation))
                if receipt_state is not None:
                    ledger.db.execute('INSERT INTO receipt_checks VALUES (?,?)', (identifier, receipt_state))
        ledger.close()
        durable_json(self.runtime / hh.SIDECAR, hh.canonical_hold_document())
        self.patches.enter_context(patch.object(hh, 'PRIOR_SIDECAR_SHA256',
            hashlib.sha256((self.runtime / hh.SIDECAR).read_bytes()).hexdigest()))
        if registered:
            durable_json(self.runtime / hh.SIDECAR_V2, hh.canonical_v2_document())


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


class TwoHistoricalHoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = HoldFixtureV2(self.temp.name)
        self.runtime = self.fixture.runtime
        self.ledger = self.fixture.ledger()

    def tearDown(self):
        self.ledger.close()
        self.fixture.close()
        self.temp.cleanup()

    def test_two_exact_unknowns_are_preserved_and_read_only(self):
        paths = [self.runtime / 'scored_budget.sqlite', self.runtime / hh.SIDECAR, *self.fixture.results.values()]
        before = [path.read_bytes() for path in paths]
        registry = hh.validate_historical_hold(self.runtime)
        self.assertEqual(registry['schema_version'], 2)
        self.assertEqual(registry['reserved_nanodollars'], 212992000)
        self.assertFalse(registry['billing_verified'])
        self.assertIsNone(registry['charged_nanodollars'])
        self.assertFalse(registry['original_qualification_gate_satisfied'])
        self.assertEqual({entry['request_id'] for entry in hh.hold_entries(registry)},
                         {hh.REQUEST_ID, hh.SECOND_REQUEST_ID})
        for trial in self.fixture.results:
            entry = hh.hold_for_trial(registry, trial)
            self.assertIsNone(entry['charged_nanodollars'])
            self.assertFalse(entry['billing_verified'])
            self.assertEqual(entry['reserved_nanodollars'], 106496000)
            self.assertEqual(entry['sidecar_sha256'], registry['sidecar_sha256'])
        second = hh.hold_for_trial(registry, hh.SECOND_TRIAL_ID)
        self.assertEqual((second['budget_stop_count'], second['capacity_budget_stop_count']), (0, 0))
        self.assertEqual(second['budget_stop_classification'], 'no_budget_stop')
        self.assertEqual(len(self.ledger.pending()), 2)
        self.assertEqual(self.ledger.blocking_pending(), [])
        self.assertEqual(before, [path.read_bytes() for path in paths])

    def test_prior_amendment_bytes_required_and_v1_does_not_authorize_second(self):
        prior = self.runtime / hh.SIDECAR
        original = prior.read_bytes()
        prior.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'Original historical hold amendment'):
            hh.validate_historical_hold(self.runtime)
        prior.write_bytes(original)
        (self.runtime / hh.SIDECAR_V2).unlink()
        with self.assertRaisesRegex(ValueError, 'Another unresolved'):
            hh.validate_historical_hold(self.runtime)
        self.assertEqual(prior.read_bytes(), original)

    def test_either_evidence_result_or_known_receipt_tamper_blocks(self):
        paths = [*self.fixture.results.values(), self.fixture.attempt / '000003.request.json',
                 self.fixture.second_attempt / '000006.request.json',
                 self.fixture.second_attempt / '000005.receipt.json']
        for path in paths:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(b'{}')
                with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime)
                path.write_bytes(original)
        durable_json(self.fixture.second_attempt / '000006.response.json', {'invented': True})
        with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime)

    def test_third_unknown_incident_and_unverified_known_receipts_block(self):
        for statement in (
            "INSERT INTO requests VALUES ('third','new',106496000,NULL,'pending')",
            "INSERT INTO incidents VALUES ('unknown',1)",
            "INSERT INTO receipt_checks VALUES ('orphan','pending')",
            "UPDATE receipt_checks SET state='pending' WHERE request_id='7648c6c2-a378-4dc3-8f7e-45929c96d7d9'",
        ):
            with self.subTest(statement=statement):
                self.ledger.db.execute('BEGIN IMMEDIATE')
                try:
                    self.ledger.db.execute(statement)
                    with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime, self.ledger.db)
                finally:
                    self.ledger.db.execute('ROLLBACK')

    def test_both_historical_trials_reject_replay(self):
        for trial in self.fixture.results:
            with self.assertRaises(BudgetExceeded):
                self.ledger.reserve('replay', trial, '.1', '25', 'development', trial_estimate='.01')
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 9)

    def test_second_original_ledger_facts_cannot_be_corrected_by_the_hold(self):
        for statement in (
            "UPDATE requests SET charged=0 WHERE id='" + hh.SECOND_REQUEST_ID + "'",
            "UPDATE trial_estimates SET amount=1 WHERE request_id='" + hh.SECOND_REQUEST_ID + "'",
            "INSERT INTO generations VALUES ('" + hh.SECOND_REQUEST_ID + "','fabricated')",
            "UPDATE requests SET charged=1 WHERE id='7648c6c2-a378-4dc3-8f7e-45929c96d7d9'",
        ):
            self.ledger.db.execute('BEGIN IMMEDIATE')
            try:
                self.ledger.db.execute(statement)
                with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime, self.ledger.db)
            finally:
                self.ledger.db.execute('ROLLBACK')

    def test_registry_cannot_authorize_a_third_hold_or_higher_limit(self):
        path = self.runtime / hh.SIDECAR_V2
        original = path.read_bytes()
        for change in ({'reserved_nanodollars': 0}, {'aggregate_cap_nanodollars': 9_000_000_000},
                       {'holds': hh.canonical_v2_document()['holds'] * 2},
                       {'additional_unknown_hold_authorized': True}, {'billing_verified': True}):
            with self.subTest(change=change):
                path.write_text(json.dumps(dict(hh.canonical_v2_document(), **change)))
                with self.assertRaises(ValueError): hh.validate_historical_hold(self.runtime)
                path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
