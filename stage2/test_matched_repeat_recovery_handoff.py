"""Actual synthetic recovery archives/native files and local transport pipes.

Native manager/process/Docker observations and the original-final second frame
are mocked here; the unchanged original reader has its own full archive tests.
These are not completed recovery outcomes or native successor qualification.
"""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import matched_repeat_recovery_handoff as handoff
import test_matched_repeat_recovery_operator as operator_tests
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save


class RecoverySuccessorHandoffTests(LocalFiles, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        operator_tests.RecoveryOperatorTests.setUp(self)
        # The receiver side is a Linux fixture, independently of the actual
        # Mac sender-side ACL checks exercised by the retained reader.
        self.enterContext(patch.object(handoff.bootstrap, 'directories',
            side_effect=handoff.operator.recovery.boot.directories))
    produce = operator_tests.RecoveryOperatorTests.produce
    collect = operator_tests.RecoveryOperatorTests.collect
    packed = operator_tests.RecoveryOperatorTests.packed
    retained = operator_tests.RecoveryOperatorTests.retained

    async def fixture(self):
        data, backup = await self.retained()
        recovery = handoff.operator.recovery
        self.enterContext(patch.object(handoff.bootstrap, 'RECOVERY', self.root))
        self.enterContext(patch.object(handoff.bootstrap, 'RECOVERY_SOURCES_SHA', recovery.policy.fingerprint(self.sources)))
        bound = {'stage2/' + n: h for n, h in self.sources.items()}
        self.native_bound = bound
        self.enterContext(patch.object(handoff.bootstrap, '_recovery_files', return_value=bound))
        self.finished = self.enterContext(patch.object(handoff.bootstrap, 'recovery_finished'))
        self.enterContext(patch.object(handoff, '_context', return_value=self.root))
        self.enterContext(patch.object(handoff, '_inputs', return_value=({}, {})))
        self.check = self.enterContext(patch.object(handoff.bootstrap, 'check', return_value={}))
        value = handoff.operator._retained({'commit': 'a' * 40}, self.sources)
        document = dict(kind=handoff.operator.KIND, operator_commit='a' * 40,
            recovery_root=str(self.root), recovery_sources_sha256=recovery.policy.fingerprint(self.sources),
            fresh_audit=deepcopy(data), retained={n: v[0].decode() for n, v in value['records'].items()},
            archive_sha256=backup['receipt']['sha256'], paid_launch_ready=False)
        inventory = recovery.boot.loads(document['retained'][recovery.BACKUP + '/inventory.json'].encode())
        for name, record in (('intent.json', dict(kind='one_shot_separate_recovery_backup', commit='a' * 40,
                sources_sha256=recovery.policy.fingerprint(bound), automatic_resume=False,
                started_utc=data['collected_utc'], paid_launch_ready=False)),
                ('result.json', dict(backup['receipt'], automatic_resume=False, paid_launch_ready=False))):
            save(self.root, recovery.NATIVE_BACKUP + '/' + name, json.dumps(record).encode())
        archive = (self.root / recovery.BACKUP / 'evidence.tar.gz').read_bytes()
        self.resources.reset_mock()  # Exclude the fixture's earlier synthetic completed audit.
        return data, backup, inventory, document, archive

    def frames(self, document, archive):
        header = dict(kind=handoff.TRANSFER, schema_version=1, harness='terminus-2', operator=document)
        out = io.BytesIO(); digest = handoff.wire.write_header(out, header)
        handoff.wire._write(out, archive); handoff.wire.commit(out, digest, document['archive_sha256'])
        first = out.getvalue()
        # Only wire semantics of this second frame are tested here. It is NOT
        # passed off as an actual original-final archive or original witness.
        second = io.BytesIO(); payload = b'explicit synthetic original-frame bytes'
        archive_sha = hashlib.sha256(payload).hexdigest(); original_document = {'test_only': True, 'number': 1.0}
        original_sha = handoff.operator.recovery.policy.fingerprint(original_document)
        digest = handoff.wire.write_header(second, dict(operator=original_document,
            backup=json.dumps({'receipt': {'compressed_bytes': len(payload), 'sha256': archive_sha}})))
        handoff.wire._write(second, payload); handoff.wire.commit(second, digest, archive_sha)
        footer = handoff.composite.END + bytes.fromhex(handoff.operator.recovery.policy.fingerprint(document))
        footer += bytes.fromhex(original_sha) + bytes.fromhex(archive_sha)
        return first, second.getvalue(), footer

    @contextmanager
    def pipe(self, raw):
        r, w = os.pipe(); errors = []
        def send():
            try:
                with os.fdopen(w, 'wb', buffering=0) as stream: handoff.wire._write(stream, raw)
            except BrokenPipeError: pass
            except BaseException as error: errors.append(error)
        thread = threading.Thread(target=send); thread.start()
        try:
            with os.fdopen(r, 'rb', buffering=0) as stream: yield stream
        finally:
            thread.join(5); self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])

    def authenticate(self, document, archive, *, footer=True):
        first, second, end = self.frames(document, archive)
        with self.pipe(first + second + (end if footer else b'')) as incoming:
            witness, frame = handoff.authenticate(self.root, 'terminus-2', incoming)
            self.addCleanup(handoff.invalidate, witness)
            self.assertEqual(handoff.wire._exact(frame, len(second)), second)
            self.assertEqual(frame.read(1), b'')
        return witness

    async def test_real_recovery_archive_and_actual_native_inventory_are_consumed(self):
        data, backup, inventory, document, archive = await self.fixture()
        witness = self.authenticate(document, archive)
        record = handoff.recheck(witness)
        self.assertEqual(record['archive_sha256'], backup['receipt']['sha256'])
        self.assertEqual(len(record['recovery_result_files']), 3)
        self.assertFalse(record['paid_launch_ready']); self.assertFalse(record['full_runtime_restore_exercised'])
        self.finished.assert_called_once()
        self.assertEqual(self.resources.call_count, 3)
        self.assertIsNone(data['rows'][2]['reward'])
        record['recovery_result_files'].clear()
        self.assertEqual(len(handoff.recheck(witness)['recovery_result_files']), 3)

    async def test_native_observation_occurs_after_original_post_audit_header(self):
        _, _, _, document, archive = await self.fixture()
        real_frame = handoff.composite.original_frame; ordered = []
        def frame(*args):
            value = real_frame(*args); ordered.append('actual_original_header'); return value
        self.finished.side_effect = lambda: ordered.append('actual_native_observation')
        with patch.object(handoff.composite, 'original_frame', side_effect=frame):
            self.authenticate(document, archive)
        self.assertEqual(ordered, ['actual_original_header', 'actual_native_observation'])

    async def test_uncommitted_outer_sender_never_exposes_original_eof(self):
        _, _, _, document, archive = await self.fixture()
        with self.assertRaises(ValueError): self.authenticate(document, archive, footer=False)

    async def test_actual_producer_missing_failure_receipt_or_identity_drift_refuses(self):
        _, backup, _, document, archive = await self.fixture()
        recovery = handoff.operator.recovery
        path = self.root / recovery.NATIVE_BACKUP / 'result.json'; raw = path.read_bytes()
        path.unlink()
        with self.assertRaises(ValueError): handoff._backup_producer(document, backup)
        save(self.root, recovery.NATIVE_BACKUP + '/result.json', raw)
        failure = recovery.NATIVE_BACKUP + '/failure.json'; save(self.root, failure, b'{}')
        with self.assertRaises(ValueError): handoff._backup_producer(document, backup)
        (self.root / failure).unlink()
        before = handoff._backup_producer(document, backup)
        path.rename(path.with_suffix('.saved')); save(self.root, recovery.NATIVE_BACKUP + '/result.json', raw)
        path.with_suffix('.saved').unlink()
        self.assertNotEqual(handoff._backup_producer(document, backup), before)
        save(self.root, recovery.NATIVE_BACKUP + '/result.json', b'{}')
        with self.assertRaises(ValueError): self.authenticate(document, archive)

    async def test_actual_result_drift_and_restoration_permanently_invalidate(self):
        data, _, _, document, archive = await self.fixture(); witness = self.authenticate(document, archive)
        name = handoff.operator.recovery.report.RT + 'scored-trials/' + data['rows'][0]['trial_id'] + '/result.json'
        path = self.root / name; raw = path.read_bytes(); path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError): handoff.recheck(witness)
        path.write_bytes(raw)
        with self.assertRaises(ValueError): handoff.recheck(witness)

    async def test_same_byte_producer_replacement_and_extra_trial_file_invalidate(self):
        data, _, _, document, archive = await self.fixture()
        witness = self.authenticate(document, archive)
        relative = handoff.operator.recovery.NATIVE_BACKUP + '/result.json'; path = self.root / relative
        raw = path.read_bytes(); saved = path.with_suffix('.saved'); path.rename(saved); save(self.root, relative, raw); saved.unlink()
        with self.assertRaises(ValueError): handoff.recheck(witness)
        witness = self.authenticate(document, archive)
        trial = handoff.operator.recovery.report.RT + 'scored-trials/' + data['rows'][0]['trial_id']
        save(self.root, trial + '/extra-unregistered-file.txt', b'changed')
        with self.assertRaises(ValueError): handoff.recheck(witness)

    async def test_actual_late_source_change_and_new_absent_file_refuse(self):
        data, _, _, document, archive = await self.fixture()
        witness = self.authenticate(document, archive)
        with patch.object(handoff.bootstrap, '_recovery_files', return_value={}):
            with self.assertRaises(ValueError): handoff.recheck(witness)
        witness = self.authenticate(document, archive)
        self.assertTrue(data['absent_paths']); save(self.root, data['absent_paths'][0], b'{}')
        with self.assertRaises(ValueError): handoff.recheck(witness)

    async def test_constructed_copied_cross_task_and_cross_thread_handles_refuse(self):
        _, _, _, document, archive = await self.fixture(); witness = self.authenticate(document, archive)
        with self.assertRaises(ValueError): handoff.recheck(handoff._Witness())
        with self.assertRaises(TypeError): copy.copy(witness)
        async def another():
            with self.assertRaises(ValueError): handoff.recheck(witness)
        await asyncio.create_task(another())
        with self.assertRaises(ValueError): handoff.recheck(witness)
        witness = self.authenticate(document, archive); errors = []
        def check():
            try: handoff.recheck(witness)
            except ValueError: errors.append(True)
        thread = threading.Thread(target=check); thread.start(); thread.join(5)
        self.assertEqual(errors, [True])
        with self.assertRaises(ValueError): handoff.recheck(witness)

    async def test_changed_metadata_receipt_raw_publication_and_stale_audit_refuse(self):
        _, _, _, document, archive = await self.fixture(); recovery = handoff.operator.recovery
        for mode in ('receipt', 'public', 'stale', 'float_type', 'extra'):
            changed = deepcopy(document)
            if mode == 'receipt': changed['archive_sha256'] = '0' * 64
            elif mode == 'public': changed['retained'][recovery.PUBLIC + '/trials.json'] += ' '
            elif mode == 'stale': changed['fresh_audit']['collected_utc'] = '2000-01-01T00:00:00Z'
            elif mode == 'float_type': changed['fresh_audit']['rows'][0]['reward'] = True
            else: changed['saved_admission'] = True
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.authenticate(changed, archive)

    async def test_native_read_errors_and_cancellation_do_not_return_witness(self):
        _, _, _, document, archive = await self.fixture()
        for error in (ValueError('native check refused'), asyncio.CancelledError()):
            self.finished.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                self.authenticate(document, archive)


if __name__ == '__main__': unittest.main()
