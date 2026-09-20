"""Offline recovery tests: fake receipts, no network, no original ledger mutation."""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import unittest

from collect_deferred_receipts import collect, DIRECTORY
from deferred_billing import register_terminal_deferral, validate_deferrals
from openrouter_transport import TransportError
from scored_gateway import durable_json, private_directory
import test_deferred_billing as fixtures


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DeferredBillingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime = self.fixture.runtime
        self.trial, self.request, self.result, self.entry = self.fixture.register(
            kind='scored', receipt_missing=True)
        self.receipt = self.fixture.client.generation(self.entry['ledger_rows'][0][5])
        self.receipt.update(cancelled=False, is_byok=False,
                            native_tokens_prompt=7, native_tokens_completion=3)
        self.calls = 0

    def reader(self, identifier):
        self.calls += 1
        self.assertEqual(identifier, self.entry['ledger_rows'][0][5])
        return deepcopy(self.receipt)

    def originals(self):
        return {str(path.relative_to(self.runtime)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.runtime.rglob('*') if path.is_file()
                and DIRECTORY not in path.parts and not path.name.endswith('.lock')}

    def test_stages_matching_receipt_without_settling_or_replaying(self):
        before = self.originals()
        result = collect(self.runtime, reader=self.reader)
        self.assertEqual(result['staged'], 1)
        self.assertEqual(result['receipt_gets'], 1)
        self.assertEqual(result['potential_hold_reduction_nanodollars'], 105496000)
        self.assertFalse(result['reservation_released'])
        self.assertFalse(result['continuation_authorised'])
        self.assertEqual(result['generation_calls'], 0)
        self.assertEqual(self.originals(), before)
        self.assertEqual(validate_deferrals(self.runtime)[0], self.entry)
        ledger = self.fixture.ledger('scored')
        try:
            self.assertEqual(ledger.exposure(), 106496000)
        finally:
            ledger.close()
        target = self.runtime / DIRECTORY / ('scored--' + self.request + '.json')
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)

    def test_repeat_revalidates_and_does_not_make_another_get(self):
        collect(self.runtime, reader=self.reader)
        before = self.originals()
        result = collect(self.runtime, reader=self.reader)
        self.assertEqual(self.calls, 1)
        self.assertEqual(result['already_staged'], 1)
        self.assertEqual(result['receipt_gets'], 0)
        self.assertEqual(self.originals(), before)

    def test_unavailable_receipt_does_not_release_or_create_receipt(self):
        before = self.originals()
        def missing(_):
            raise TransportError('unavailable')
        result = collect(self.runtime, reader=missing)
        self.assertEqual(result['unavailable'], 1)
        self.assertEqual(result['potential_hold_reduction_nanodollars'], 0)
        self.assertEqual(list((self.runtime / DIRECTORY).iterdir()), [])
        self.assertEqual(self.originals(), before)

    def test_mismatched_receipts_are_rejected_without_writes(self):
        changes = [{'id': 'different'}, {'model': 'different'}, {'provider_name': 'different'},
                   {'total_cost': '.002'}, {'cancelled': True}, {'cancelled': None},
                   {'is_byok': True}, {'native_tokens_prompt': 8},
                   {'native_tokens_completion': True}, {'total_cost': float('nan')}]
        original = deepcopy(self.receipt)
        before = self.originals()
        for change in changes:
            with self.subTest(change=change):
                self.receipt = original | change
                with self.assertRaises((ValueError, TypeError)):
                    collect(self.runtime, reader=self.reader)
                self.assertEqual(list((self.runtime / DIRECTORY).iterdir()), [])
                self.assertEqual(self.originals(), before)

    def test_existing_staged_record_tampering_is_detected(self):
        collect(self.runtime, reader=self.reader)
        path = next((self.runtime / DIRECTORY).iterdir())
        record = json.loads(path.read_text())
        record['potential_hold_reduction_nanodollars'] += 1
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            collect(self.runtime, reader=self.reader)
        self.assertEqual(self.calls, 1)

    def test_all_execution_owners_block_recovery(self):
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            path = self.runtime / name
            path.touch(mode=0o600, exist_ok=True)
            with path.open('r+') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    collect(self.runtime, reader=self.reader)
        self.assertEqual(self.calls, 0)

    def test_symlinked_recovery_folder_is_rejected(self):
        target = self.fixture.root / 'outside'; target.mkdir(mode=0o700)
        (self.runtime / DIRECTORY).symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            collect(self.runtime, reader=self.reader)
        self.assertEqual(self.calls, 0)

    def test_symlinked_staged_record_is_rejected(self):
        collect(self.runtime, reader=self.reader)
        path = next((self.runtime / DIRECTORY).iterdir())
        target = path.with_name('saved.json'); path.rename(target); path.symlink_to(target)
        with self.assertRaises(OSError):
            collect(self.runtime, reader=self.reader)
        self.assertEqual(self.calls, 1)

    def test_original_ledger_or_result_changes_cannot_be_hidden_by_staging(self):
        collect(self.runtime, reader=self.reader)
        self.result.write_bytes(self.result.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'changed'):
            collect(self.runtime, reader=self.reader)

    def test_collection_is_bounded_and_requires_explicit_inputs(self):
        for value in (0, 65, True, 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                collect(self.runtime, reader=self.reader, maximum_receipts=value)
        with self.assertRaises(ValueError):
            collect(self.runtime, kind='other', reader=self.reader)
        self.assertEqual(self.calls, 0)

    def test_unknown_dispatch_is_not_treated_as_a_settled_response(self):
        self.fixture.register(kind='setup', receipt_missing=False)
        before = self.originals()
        result = collect(self.runtime, kind='setup', reader=self.reader)
        self.assertEqual(result['eligible'], 0)
        self.assertEqual(result['receipt_gets'], 0)
        self.assertEqual(self.originals(), before)

    def test_setup_receipt_uses_the_setup_ledger_without_scored_mutation(self):
        _, _, _, entry = self.fixture.register(kind='setup', receipt_missing=True)
        receipt = self.fixture.client.generation(entry['ledger_rows'][0][5])
        receipt.update(cancelled=False, is_byok=False, native_tokens_prompt=7, native_tokens_completion=3)
        before = self.originals()
        result = collect(self.runtime, kind='setup', reader=lambda identifier: receipt)
        self.assertEqual(result['staged'], 1)
        self.assertEqual(self.originals(), before)

    def test_unexpected_provider_fields_are_not_copied(self):
        self.receipt['prompt'] = 'PRIVATE-CANARY'
        collect(self.runtime, reader=self.reader)
        text = next((self.runtime / DIRECTORY).iterdir()).read_text()
        self.assertNotIn('PRIVATE-CANARY', text)

    def test_shared_readable_recovery_directory_is_refused(self):
        path = self.runtime / DIRECTORY
        path.mkdir(mode=0o700); path.chmod(0o755)
        with self.assertRaises(ValueError):
            collect(self.runtime, reader=self.reader)
        self.assertEqual(self.calls, 0)

    def test_small_batches_advance_past_previously_staged_receipts(self):
        other = 'dev-terminus-2-07-another'
        with self.fixture.session(other, 'scored') as session:
            session.complete(self.fixture.token, self.fixture.payload)
        result = json.loads(self.result.read_text()); result['trial_id'] = other
        path = private_directory(self.runtime / 'scored-trials' / other) / 'result.json'
        durable_json(path, result)
        register_terminal_deferral(self.runtime, kind='scored', trial_id=other, result_path=path)
        def reader(identifier):
            return self.receipt | {'id': identifier}
        first = collect(self.runtime, reader=reader, maximum_receipts=1)
        self.assertEqual((first['staged'], first['unexamined']), (1, 1))
        second = collect(self.runtime, reader=reader, maximum_receipts=1)
        self.assertEqual((second['already_staged'], second['staged'], second['unexamined']), (1, 1, 0))


if __name__ == '__main__':
    unittest.main()
