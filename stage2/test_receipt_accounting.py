"""Conservation regressions for active receipts and additive recovery."""
from pathlib import Path
import fcntl
import hashlib
import json
import tempfile
import unittest

from budget_ledger import BudgetExceeded, Ledger, dollars
from collect_deferred_receipts import collect, DIRECTORY as STAGED
from deferred_billing import (_encoded, _write, deferred_audit, extra_exposure_nanodollars,
    register_terminal_deferral, unresolved_liability_nanodollars, validate_deferrals)
from gateway_core import GatewayError
from receipt_accounting import activate, DIRECTORY
from scored_gateway import durable_json, private_directory
import test_collect_deferred_receipts as fixtures


class ActiveReceiptBudgetTests(unittest.TestCase):
    def ledger(self, *, ceiling='1', trial_cap='1', stages=None, estimated=False):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        ledger = Ledger(Path(folder.name) / 'ledger.sqlite', ceiling, trial_cap, stages,
                        allow_estimated_trials=estimated)
        self.addCleanup(ledger.close)
        return ledger

    def test_active_unverified_receipt_keeps_full_hard_exposure(self):
        ledger = self.ledger()
        ledger.reserve('first', 'active', '.1', '12')
        ledger.settle('first', '.001', receipt_pending=True)
        self.assertEqual(ledger.exposure(), dollars('.1'))
        ledger.verify_receipt('first', '.001')
        self.assertEqual(ledger.exposure(), dollars('.001'))

    def test_active_receipt_gap_cannot_cross_stage_cap_before_deferral(self):
        ledger = self.ledger(stages={'final': '.11'})
        ledger.reserve('first', 'active', '.1', '12', 'final')
        ledger.settle('first', '.001', receipt_pending=True)
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('second', 'active', '.1', '12', 'final')
        self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)

    def test_active_receipt_gap_cannot_cross_aggregate_cap(self):
        ledger = self.ledger(ceiling='.15')
        ledger.reserve('first', 'active', '.1', '12')
        ledger.settle('first', '.001', receipt_pending=True)
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('second', 'active', '.1', '12')

    def test_active_receipt_gap_cannot_spend_account_reserve(self):
        ledger = self.ledger()
        ledger.reserve('first', 'active', '.1', '2.15')
        ledger.settle('first', '.001', receipt_pending=True)
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('second', 'active', '.1', '2.15')

    def test_estimated_trial_allowance_stays_separate_from_hard_exposure(self):
        ledger = self.ledger(trial_cap='.023', estimated=True)
        ledger.reserve('first', 'active', '.1', '12', trial_estimate='.01')
        ledger.settle('first', '.001', receipt_pending=True)
        ledger.reserve('second', 'active', '.1', '12', trial_estimate='.01')
        self.assertEqual(ledger.exposure(), dollars('.2'))


class AdditiveReceiptAccountingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CollectionTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.runtime = self.fixture.runtime
        self.request = self.fixture.request
        collect(self.runtime, reader=self.fixture.reader)

    def activate(self, requests=None):
        return activate(self.runtime, kind='scored', request_ids=requests or [self.request])

    def ledger(self):
        ledger = self.fixture.fixture.ledger('scored')
        self.addCleanup(ledger.close)
        return ledger

    def originals(self):
        return {name: value for name, value in self.fixture.originals().items()
                if DIRECTORY not in Path(name).parts}

    def other(self, *, unknown=False):
        fixture = self.fixture.fixture
        trial = 'dev-terminus-2-07-another'
        fixture.client.fail = unknown
        with fixture.session(trial, 'scored') as session:
            if unknown:
                with self.assertRaises(GatewayError):
                    session.complete(fixture.token, fixture.payload)
            else:
                session.complete(fixture.token, fixture.payload)
            request = session.ledger.db.execute('SELECT id FROM requests WHERE trial=?', (trial,)).fetchone()[0]
        fixture.client.fail = False
        result = json.loads(self.fixture.result.read_text()); result['trial_id'] = trial
        path = private_directory(self.runtime / 'scored-trials' / trial) / 'result.json'
        durable_json(path, result)
        entry = register_terminal_deferral(self.runtime, kind='scored', trial_id=trial, result_path=path)
        if not unknown:
            def reader(identifier):
                return self.fixture.receipt | {'id': identifier}
            collect(self.runtime, reader=reader)
        return request, entry

    def test_staging_alone_does_not_reduce_any_hold(self):
        ledger = self.ledger()
        self.assertEqual(ledger.exposure(), dollars('.106496'))
        self.assertEqual(extra_exposure_nanodollars(validate_deferrals(self.runtime)), dollars('.105496'))

    def test_explicit_recovery_changes_only_effective_extra_receipt_hold(self):
        before = self.originals(); ledger = self.ledger()
        result = self.activate()
        self.assertEqual(result['activated_receipts'], 1)
        self.assertEqual(result['hold_reduction_nanodollars'], dollars('.105496'))
        self.assertFalse(result['continuation_authorised'])
        self.assertEqual(self.originals(), before)
        self.assertEqual(ledger.exposure(), dollars('.001'))
        self.assertEqual(ledger.db.execute('SELECT charged,state FROM requests WHERE id=?',
                         (self.request,)).fetchone(), (dollars('.001'), 'settled'))
        self.assertEqual(ledger.db.execute('SELECT state FROM receipt_checks WHERE request_id=?',
                         (self.request,)).fetchone(), ('pending',))
        entries = validate_deferrals(self.runtime)
        self.assertEqual(unresolved_liability_nanodollars(ledger.db, entries), 0)
        self.assertEqual(entries[0]['extra_reserved_nanodollars'], dollars('.105496'))
        view = deferred_audit(entries[0])
        self.assertFalse(view['billing_verified']); self.assertIsNone(view['charged_usd'])
        self.assertEqual(view['retained_liability_nanodollars'], 0)
        self.assertEqual(view['original_retained_liability_nanodollars'], dollars('.105496'))

    def test_repeated_activation_is_idempotent_without_new_records(self):
        self.activate()
        before = {path.name: path.read_bytes() for path in (self.runtime / DIRECTORY).iterdir()}
        result = self.activate()
        self.assertEqual(result['activated_receipts'], 0)
        self.assertEqual(result['already_activated'], 1)
        self.assertEqual(result['hold_reduction_nanodollars'], 0)
        self.assertEqual(before, {path.name: path.read_bytes() for path in (self.runtime / DIRECTORY).iterdir()})

    def test_recovery_never_replays_or_reopens_the_original_trial(self):
        self.activate()
        with self.assertRaises(BudgetExceeded):
            self.ledger().reserve('replacement', self.fixture.trial, '.106496', '12',
                                  'development', trial_estimate='.01')

    def test_unknown_requests_remain_fully_reserved_after_receipt_recovery(self):
        unknown, _ = self.other(unknown=True)
        before = self.originals()
        self.activate()
        ledger = self.ledger(); entries = validate_deferrals(self.runtime)
        self.assertEqual(ledger.exposure(), dollars('.107496'))
        self.assertEqual(unresolved_liability_nanodollars(ledger.db, entries), dollars('.106496'))
        self.assertEqual(self.originals(), before)
        with self.assertRaises(ValueError):
            self.activate([unknown])

    def test_account_reserve_and_original_stage_caps_remain_enforced(self):
        self.other(unknown=True); self.activate()
        ledger = self.ledger()
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('new', 'next', '.1', '2.2', 'development', trial_estimate='.01')
        with self.assertRaises(BudgetExceeded):
            ledger.reserve('large', 'next', '2.7', '12', 'development', trial_estimate='.01')
        self.assertEqual(dict(ledger.db.execute('SELECT name,cap FROM stages')),
                         {'development': dollars('2.760'), 'final': dollars('6.141')})

    def test_active_gap_is_not_double_counted_when_trial_becomes_deferred(self):
        ledger = self.ledger()
        before = ledger.exposure()
        self.assertEqual(before, dollars('.106496'))
        self.activate()
        self.assertEqual(ledger.exposure(), before - dollars('.105496'))

    def test_other_kind_and_unregistered_requests_cannot_be_activated(self):
        for kwargs in ({'kind': 'setup', 'request_ids': [self.request]},
                       {'kind': 'scored', 'request_ids': ['unknown']},
                       {'kind': 'scored', 'request_ids': ['../../outside']}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                activate(self.runtime, **kwargs)
        self.assertFalse((self.runtime / DIRECTORY).exists())

    def test_duplicate_or_unbounded_activation_requests_are_rejected(self):
        for requests in ([], [self.request, self.request], ['x' + str(n) for n in range(65)]):
            with self.subTest(requests=requests), self.assertRaises(ValueError):
                activate(self.runtime, kind='scored', request_ids=requests)

    def test_all_execution_locks_block_activation(self):
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            path = self.runtime / name; path.touch(mode=0o600, exist_ok=True)
            with path.open('r+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    self.activate()
        self.assertFalse((self.runtime / DIRECTORY).exists())

    def test_activation_bytes_cannot_be_changed(self):
        self.activate()
        path = next((self.runtime / DIRECTORY).iterdir())
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'digest changed'):
            validate_deferrals(self.runtime)

    def test_staged_receipt_bytes_remain_bound_after_activation(self):
        self.activate()
        path = next((self.runtime / STAGED).iterdir())
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'receipt bytes changed'):
            validate_deferrals(self.runtime)

    def test_changed_original_result_is_not_hidden_by_recovery(self):
        self.activate()
        self.fixture.result.write_bytes(self.fixture.result.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'changed'):
            validate_deferrals(self.runtime)

    def test_missing_staged_receipt_stops_accounting(self):
        self.activate()
        next((self.runtime / STAGED).iterdir()).unlink()
        with self.assertRaises(OSError):
            validate_deferrals(self.runtime)

    def test_receipt_cannot_appear_in_two_activation_batches(self):
        other, _ = self.other()
        self.activate()
        record_hashes = {}
        for request in (self.request, other):
            path = self.runtime / STAGED / ('scored--' + request + '.json')
            record_hashes[request] = hashlib.sha256(path.read_bytes()).hexdigest()
        batch = {'schema_version': 1, 'kind': 'scored', 'receipts': record_hashes}
        digest = hashlib.sha256(_encoded(batch)).hexdigest()
        _write(self.runtime / DIRECTORY / ('scored--' + digest + '.json'), batch)
        with self.assertRaisesRegex(ValueError, 'twice'):
            validate_deferrals(self.runtime)

    def test_symlinked_activation_folder_is_rejected(self):
        target = self.fixture.fixture.root / 'outside'; target.mkdir(mode=0o700)
        (self.runtime / DIRECTORY).symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.activate()

    def test_shared_readable_activation_folder_is_rejected(self):
        folder = self.runtime / DIRECTORY; folder.mkdir(mode=0o700); folder.chmod(0o755)
        with self.assertRaises(ValueError):
            self.activate()

    def test_collector_remains_no_op_after_explicit_activation(self):
        self.activate(); before = self.originals()
        result = collect(self.runtime, reader=self.fixture.reader)
        self.assertEqual(result['receipt_gets'], 0)
        self.assertEqual(result['already_staged'], 1)
        self.assertEqual(self.originals(), before)


if __name__ == '__main__':
    unittest.main()
