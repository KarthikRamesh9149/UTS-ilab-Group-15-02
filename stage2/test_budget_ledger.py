from pathlib import Path
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import historical_hold as hh
from budget_ledger import BudgetExceeded, Ledger, dollars
from test_historical_hold import HoldFixture


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

    def test_stage_budget_protects_final_allocation(self):
        ledger = Ledger(Path(self.temp.name) / 'stages.sqlite', '.10', '.055',
                        {'development': '.04', 'final': '.06'})
        try:
            ledger.reserve('a', 'dev1', '.04', '25', 'development')
            ledger.settle('a', '.04')
            with self.assertRaises(BudgetExceeded):
                ledger.reserve('b', 'dev2', '.001', '25', 'development')
            ledger.reserve('c', 'final1', '.055', '25', 'final')
            ledger.settle('c', '.055')
            with self.assertRaises(ValueError):
                ledger.reserve('d', 'dev1', '.001', '25', 'final')
        finally:
            ledger.close()

    def test_concurrent_reservations_admit_only_one(self):
        barrier = Barrier(2)
        def attempt(identifier):
            ledger = Ledger(self.path, '.10', '.055')
            try:
                barrier.wait(timeout=5)
                ledger.reserve(identifier, identifier, '.01', '25')
                return True
            except BudgetExceeded:
                return False
            finally:
                ledger.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt, ['a', 'b'])), [False, True])

    def test_settled_duplicate_id_is_not_dispatched_twice(self):
        self.ledger.reserve('a', 'trial', '.01', '25')
        self.ledger.settle('a', '.001')
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.reserve('a', 'trial', '.01', '25')

    def test_overcharge_halt_survives_restart(self):
        self.ledger.reserve('a', 'trial', '.01', '25')
        with self.assertRaises(BudgetExceeded):
            self.ledger.settle('a', '.02')
        other = Ledger(self.path, '.10', '.055')
        try:
            with self.assertRaises(BudgetExceeded):
                other.reserve('b', 'other', '.001', '25')
        finally:
            other.close()


class HistoricalHoldBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = HoldFixture(self.temp.name)
        self.ledger = self.fixture.ledger()
        self.original_exposure = hh.SETTLED_NANODOLLARS + hh.RESERVED_NANODOLLARS

    def tearDown(self):
        self.ledger.close()
        self.fixture.close()
        self.temp.cleanup()

    def original_rows(self):
        return self.ledger.db.execute('''
            SELECT r.id,r.reserved,r.charged,r.state,e.amount,g.generation_id,c.state
            FROM requests r LEFT JOIN trial_estimates e ON e.request_id=r.id
            LEFT JOIN generations g ON g.request_id=r.id
            LEFT JOIN receipt_checks c ON c.request_id=r.id
            WHERE r.trial=? ORDER BY r.id''', (hh.TRIAL_ID,)).fetchall()

    def seed_settled(self, identifier, nanodollars, *, stage=None, trial=None):
        """Synthetic prior spending isolates caps without changing policy or history."""
        trial = trial or identifier
        with self.ledger.transaction():
            self.ledger.db.execute('INSERT INTO requests VALUES (?,?,?,?,?)',
                                   (identifier, trial, nanodollars, nanodollars, 'settled'))
            if stage is not None:
                self.ledger.db.execute('INSERT OR IGNORE INTO trial_stages VALUES (?,?)',
                                       (trial, stage))

    def assert_request_absent(self, identifier):
        self.assertIsNone(self.ledger.db.execute(
            'SELECT id FROM requests WHERE id=?', (identifier,)).fetchone())
        self.assertIsNone(self.ledger.db.execute(
            'SELECT amount FROM trial_estimates WHERE request_id=?', (identifier,)).fetchone())

    def test_account_floor_counts_full_hold_and_new_reservation_exactly(self):
        self.assertEqual(self.ledger.exposure(), self.original_exposure)
        self.assertEqual(self.ledger.blocking_pending(), [])
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('short', 'fresh', '.1', '2.206495999',
                                'development', trial_estimate='.01')
        self.assert_request_absent('short')
        self.assertIsNone(self.ledger.db.execute(
            'SELECT stage FROM trial_stages WHERE trial=?', ('fresh',)).fetchone())
        self.ledger.reserve('exact', 'fresh', '.1', '2.206496000',
                            'development', trial_estimate='.01')
        self.assertEqual(self.ledger.exposure(), self.original_exposure + dollars('.1'))
        self.assertEqual(sum(row[2] for row in self.ledger.pending()), dollars('.206496'))
        self.assertEqual(self.original_rows(), sorted(hh.ORIGINAL_ROWS))

    def test_development_cap_counts_settled_hold_and_full_new_reservation(self):
        cap = dollars('2.760')
        fill = cap - self.original_exposure - dollars('.1')
        self.seed_settled('development-fill', fill, stage='development')
        self.seed_settled('one-nanodollar', 1, stage='development')
        with self.assertRaisesRegex(BudgetExceeded, 'Stage allocation exhausted'):
            self.ledger.reserve('over-stage', 'fresh', '.1', '25',
                                'development', trial_estimate='.01')
        self.assert_request_absent('over-stage')
        with self.ledger.transaction():
            self.ledger.db.execute('DELETE FROM requests WHERE id=?', ('one-nanodollar',))
        self.ledger.reserve('exact-stage', 'fresh', '.1', '25',
                            'development', trial_estimate='.01')
        self.assertEqual(self.ledger.exposure(), cap)
        self.assertEqual(self.original_rows(), sorted(hh.ORIGINAL_ROWS))

    def test_aggregate_cap_counts_settled_hold_and_full_new_reservation(self):
        cap = dollars('8.901')
        # An unallocated synthetic settled row isolates the aggregate check:
        # the real stage allocations sum to the aggregate cap exactly.
        self.seed_settled('aggregate-fill', cap - self.original_exposure - dollars('.1'))
        self.seed_settled('one-nanodollar', 1)
        with self.assertRaisesRegex(BudgetExceeded, 'Reservation refused before dispatch'):
            self.ledger.reserve('over-aggregate', 'fresh', '.1', '25',
                                'development', trial_estimate='.01')
        self.assert_request_absent('over-aggregate')
        with self.ledger.transaction():
            self.ledger.db.execute('DELETE FROM requests WHERE id=?', ('one-nanodollar',))
        self.ledger.reserve('exact-aggregate', 'fresh', '.1', '25',
                            'development', trial_estimate='.01')
        self.assertEqual(self.ledger.exposure(), cap)
        self.assertEqual(self.original_rows(), sorted(hh.ORIGINAL_ROWS))

    def test_new_trial_estimate_cap_still_blocks_above_023(self):
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('too-large-estimate', 'fresh', '.1', '25',
                                'development', trial_estimate='.023000001')
        self.assert_request_absent('too-large-estimate')
        self.ledger.reserve('exact-estimate', 'fresh', '.1', '25',
                            'development', trial_estimate='.023')
        self.assertEqual(self.ledger.exposure('fresh'), dollars('.1'))
        self.assertEqual(self.ledger.db.execute(
            'SELECT amount FROM trial_estimates WHERE request_id=?',
            ('exact-estimate',)).fetchone(), (dollars('.023'),))

    def test_new_trial_cap_counts_its_prior_settled_charges(self):
        self.seed_settled('prior-new-charge', dollars('.013'),
                          stage='development', trial='fresh')
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('over-trial', 'fresh', '.1', '25',
                                'development', trial_estimate='.010000001')
        self.assert_request_absent('over-trial')
        self.ledger.reserve('exact-trial', 'fresh', '.1', '25',
                            'development', trial_estimate='.01')
        self.assertEqual(self.ledger.exposure('fresh'), dollars('.113'))

    def test_two_connections_admit_only_one_new_request_beside_hold(self):
        barrier = Barrier(2)

        def attempt(identifier):
            ledger = self.fixture.ledger()
            try:
                barrier.wait(timeout=5)
                ledger.reserve(identifier, identifier, '.1', '25',
                               'development', trial_estimate='.01')
                return identifier, True
            except BudgetExceeded:
                return identifier, False
            finally:
                ledger.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = dict(pool.map(attempt, ('new-a', 'new-b')))
        self.assertEqual(sorted(outcomes.values()), [False, True])
        winner = next(identifier for identifier, accepted in outcomes.items() if accepted)
        loser = next(identifier for identifier, accepted in outcomes.items() if not accepted)
        self.assertEqual({row[0] for row in self.ledger.pending()}, {hh.REQUEST_ID, winner})
        self.assertEqual(self.ledger.exposure(), self.original_exposure + dollars('.1'))
        self.assert_request_absent(loser)
        self.assertEqual(self.original_rows(), sorted(hh.ORIGINAL_ROWS))
        with self.assertRaises(BudgetExceeded):
            self.ledger.blocking_pending()
        self.ledger.settle(winner, '.01')
        self.assertEqual(self.ledger.blocking_pending(), [])
        self.assertEqual(self.ledger.pending(), [(hh.REQUEST_ID, hh.TRIAL_ID,
                                                 hh.RESERVED_NANODOLLARS, None)])

    def test_historical_rows_and_unknown_pending_survive_new_work_and_restart(self):
        before = self.original_rows()
        self.ledger.reserve('new', 'fresh', '.1', '25',
                            'development', trial_estimate='.01')
        self.ledger.settle('new', '.01')
        self.ledger.close()
        self.ledger = self.fixture.ledger()
        self.assertEqual(self.original_rows(), before)
        self.assertEqual(self.original_rows(), sorted(hh.ORIGINAL_ROWS))
        self.assertEqual(self.ledger.pending(), [(hh.REQUEST_ID, hh.TRIAL_ID,
                                                 hh.RESERVED_NANODOLLARS, None)])
        self.assertEqual(self.ledger.blocking_pending(), [])
        self.assertEqual(self.ledger.exposure(), self.original_exposure + dollars('.01'))
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('old-trial-replay', hh.TRIAL_ID, '.1', '25',
                                'development', trial_estimate='.01')
        self.assert_request_absent('old-trial-replay')
        self.assertEqual(self.original_rows(), before)

    def test_sidecar_and_evidence_tamper_is_rechecked_inside_reservation(self):
        for path in (self.fixture.runtime / hh.SIDECAR,
                     self.fixture.attempt / '000003.request.json', self.fixture.result):
            with self.subTest(path=path.name):
                self.assertEqual(self.ledger.blocking_pending(), [])
                original = path.read_bytes()
                statements = []
                try:
                    path.write_bytes(b'{}')
                    self.ledger.db.set_trace_callback(statements.append)
                    with self.assertRaisesRegex(BudgetExceeded, 'Historical hold validation failed'):
                        self.ledger.reserve('tampered', 'fresh', '.1', '25',
                                            'development', trial_estimate='.01')
                finally:
                    self.ledger.db.set_trace_callback(None)
                    path.write_bytes(original)
                self.assertEqual(statements[0], 'BEGIN IMMEDIATE')
                self.assertEqual(statements[-1], 'ROLLBACK')
                self.assertFalse(self.ledger.db.in_transaction)
                self.assert_request_absent('tampered')
                self.assertEqual(self.ledger.exposure(), self.original_exposure)
                self.assertEqual(self.original_rows(), sorted(hh.ORIGINAL_ROWS))
                self.assertEqual(self.ledger.blocking_pending(), [])


if __name__ == '__main__':
    unittest.main()
