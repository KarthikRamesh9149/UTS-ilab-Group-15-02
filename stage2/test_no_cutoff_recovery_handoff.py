"""Synthetic original89, real temporary archive/files/pipes; no native or paid execution.

Fixed study pins and the minimal historical qualification fixture are replaced
ONLY in tests. Audit/service/Git observations are mocked. Production validators,
strict archive consumption, source/private-file rereads and live witnesses run.
"""
import asyncio
from copy import copy, deepcopy
import fcntl
import io
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import no_cutoff_recovery_predecessor as operator
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_policy as policy
import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch
import matched_repeat_stream as wire
import test_no_cutoff_final_export as fixtures

STAGE = Path(__file__).resolve().parent
ACTUAL_LOADED = operator.loaded
ACTUAL_CONTEXT = handoff._context
ACTUAL_NO_STOP = handoff._no_stop
ACTUAL_NATIVE_AUDIT = handoff._native_audit


class RecoveryOriginalHandoffTests(unittest.TestCase):
    def setUp(self):
        self.e = fixtures.PublicExportTests(); self.e.setUp(); self.addCleanup(self.e.doCleanups)
        self.root = self.e.root; self.commit = self.e.commit
        self.data = self.e.f.data; self.final = self.e.f.f.f.proof
        self.e.run_export(); self.e.collect.reset_mock()
        self.snapshot_raw = (self.e.folder / 'snapshot.json').read_bytes()
        self.backup_raw = (self.e.folder / 'backup.json').read_bytes()
        self.backup = phase._loads(self.backup_raw)
        self.archive_raw = (self.e.folder / 'evidence.tar.gz').read_bytes()
        for module in (operator, handoff):
            self.enterContext(patch.object(module, '__file__', str(self.root / 'stage2' / (module.__name__ + '.py'))))
        # These two mocked pure gates adapt the existing MINIMAL synthetic
        # qualification. All current source hashes/transitions still run below.
        self.enterContext(patch.object(policy, 'original_final', side_effect=lambda f: f['sources']))
        self.enterContext(patch.object(policy, 'test_modules', return_value=policy.RECOVERY_TEST_MODULES))
        self.enterContext(patch.object(policy, 'cells', return_value=[]))
        tasks = [r['task_id'] for r in self.data['rows']]
        self.enterContext(patch.object(policy.plan, 'task_order', return_value=tasks))
        self.enterContext(patch.object(policy.plan, 'TARGETS', ()))
        pins = dict(ORIGINAL_QUALIFICATION=phase.fingerprint(self.final),
            ORIGINAL_SOURCE_SET=phase.fingerprint(self.final['sources']),
            ORIGINAL_RESULTS_SHA256=phase.fingerprint({r['trial_id']: r['result_sha256'] for r in self.data['rows']}),
            ORIGINAL_QUALIFICATION_FILE_SHA256=phase.QUALIFICATION_FILE,
            SNAPSHOT_SHA256=export._hash(self.snapshot_raw), BACKUP_SHA256=export._hash(self.backup_raw),
            ARCHIVE_SHA256=export._hash(self.archive_raw), AUDIT_SHA256=operator.audit_hash(self.data),
            REPORTER_COMMIT=self.commit,
            PUBLIC_FILES={n: export._hash((self.e.target / n).read_bytes()) for n in export.OUTPUTS})
        for name, value in pins.items(): self.enterContext(patch.object(policy, name, value))
        self.enterContext(patch.object(policy.plan, 'ORIGINAL_REGISTRATION', phase.fingerprint(self.data['registration'])))
        for name in policy.REQUIRED_SOURCE_FILES:
            self.e.save('stage2/' + name, (STAGE / name).read_bytes())
        self.e.save('stage2/input_manifest.json', b'{"synthetic_manifest":true}')
        self.enterContext(patch.object(policy, 'INPUT_SHA256', export._hash(b'{"synthetic_manifest":true}')))
        qualification = self.e.f.anchors[phase.RT + 'no-cutoff-final-qualification.json']
        self.e.save(phase.RT + policy.ORIGINAL_FILE, qualification)
        self.enterContext(patch.object(operator, 'EXPORT_STATE',
            {n: export._hash((self.e.state / n).read_bytes()) for n in ('intent.json', 'result.json')}))
        self.previous = self.enterContext(patch.object(receiver, '_previous_failure'))
        self.loaded = self.enterContext(patch.object(operator, 'loaded', return_value=set()))
        self.context = self.enterContext(patch.object(handoff, '_context', return_value=self.root))
        self.no_stop = self.enterContext(patch.object(handoff, '_no_stop'))
        # Linux POSIX ACL observation is unavailable in this macOS Python.
        # Refusal is tested separately; no production ACL check is bypassed.
        self.enterContext(patch.object(phase.guard.os, 'listxattr', return_value=[], create=True))
        self.native_audit = self.enterContext(patch.object(handoff, '_native_audit',
            side_effect=lambda _: deepcopy(self.e.fresh)))
        self.no_process = self.enterContext(patch.object(handoff.subprocess, 'run',
            side_effect=AssertionError('No real native command is allowed in local handoff tests')))
        native = {'stage2/' + n: h for n, h in self.final['sources'].items()}
        native.update({phase.RT + n: h for n, h in report.INPUTS.items()})
        native.update(self.final['evidence_files']); native.update(report.HISTORICAL_INPUTS)
        native.update(report.dependencies.FILES); native.update(report.guard.REPORTING_LIBRARY_FILES)
        self.e.bindings['native'] = native
        self.git_bytes = {p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in (self.root / 'stage2').rglob('*') if p.is_file()}
        self.e.git.side_effect = lambda op, ref: ((self.commit + '\n').encode()
            if op == 'rev-parse' else self.git_bytes[ref.split(':', 1)[1]])
        self.e.recheck.side_effect = lambda b: [launch._raw(n, h) for n, h in b['local'].items()]
        # The synthetic installed reporter, including its successful producer
        # state, is independent of the transfer and must be actually reread.
        intent = dict(kind='one_shot_amended_final_backup_intent',
            created_utc='2027-01-16T00:00:00+00:00', snapshot_sha256=phase.fingerprint(self.data),
            reporting_source_files=self.data['reporting_source_files'], automatic_resume=False, paid_launch_ready=False)
        result = dict(kind='native_amended_archive_streamed_not_off_server_proof',
            receipt=self.backup['receipt'], automatic_resume=False, off_server_backup_verified=False, paid_launch_ready=False)
        for name, value in zip(producer.STATE, (intent, result)):
            path = report.REPORTING / name; path.write_bytes(producer._json(value)); path.chmod(0o600)
        for path in [report.REPORTING, *report.REPORTING.rglob('*')]:
            path.chmod(0o700 if path.is_dir() else 0o600)
        self.addCleanup(handoff._WITNESSES.clear)

    def captured(self):
        return operator._capture(self.commit)

    def header(self):
        value, document = self.captured()
        return dict(kind=handoff.TRANSFER_KIND, schema_version=1, successor_experiment=policy.EXPERIMENT,
            operator=document, snapshot=self.snapshot_raw.decode(), backup=self.backup_raw.decode())

    def packet(self, header=None, *, archive_raw=None, committed=True, tail=b''):
        header = self.header() if header is None else header
        stream = io.BytesIO(); digest = wire.write_header(stream, header)
        stream.write(self.archive_raw if archive_raw is None else archive_raw)
        if committed: wire.commit(stream, digest, self.backup['receipt']['sha256'])
        return stream.getvalue() + tail

    def pipe(self, data=None, *, sender=None, action=None):
        """Consumer remains in the owning main-thread asyncio task."""
        read, write = os.pipe(); failures = []; sent = []
        def writer():
            try:
                with os.fdopen(write, 'wb', buffering=0) as output:
                    if sender: sent.append(sender(output))
                    else: output.write(data)
            except BrokenPipeError:
                pass  # Expected after a refusing reader closes this test pipe.
            except BaseException as exc:
                failures.append(exc)
        thread = threading.Thread(target=writer); thread.start()
        async def consume():
            with os.fdopen(read, 'rb', buffering=0) as source:
                witness = handoff.authenticate(source)
            if action: return await action(witness)
            return handoff.describe(witness)
        try: result = asyncio.run(consume())
        finally:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), 'Synthetic pipe writer did not finish')
        if failures: raise failures[0]
        return result, sent

    def test_actual_sender_strict_receiver_and_two_independent_audits(self):
        original = {p.name: p.read_bytes() for p in self.e.folder.iterdir()}
        with patch.object(archive, 'verify_archive', wraps=archive.verify_archive) as path_verify, \
                patch.object(archive, 'verify_stream', wraps=archive.verify_stream) as stream_verify:
            result, sent = self.pipe(sender=handoff.send)
        self.e.collect.assert_called_once_with(self.commit); self.native_audit.assert_called_once()
        self.assertEqual(path_verify.call_count, 1)
        # The path verifier itself uses the same strict stream implementation.
        self.assertEqual(stream_verify.call_count, 2)
        self.assertFalse(result['paid_launch_ready']); self.assertFalse(result['recovery_execution_qualified'])
        self.assertFalse(sent[0]['paid_launch_ready'])
        self.assertEqual(result['kind'], handoff.KIND)
        self.assertEqual(len(result['predecessor']['results_sha256']), 89)
        self.assertEqual(sum(len(files) for files in result['preserved_result_files'].values()), 182)
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.e.folder.iterdir()})
        self.no_process.assert_not_called()

    def test_capture_retains_nulls_numeric_types_true_absences_and_current_sources(self):
        value, document = self.captured()
        self.assertIsNone(value['data']['rows'][0]['reward'])
        self.assertIs(type(value['data']['rows'][0]['official_agent_timeout_seconds']), float)
        self.assertEqual(len(document['absent_paths']), 3)
        self.assertEqual(set(document['current_sources']), set(self.final['sources']) | policy.REQUIRED_SOURCE_FILES)
        self.assertFalse(document['paid_launch_ready'])
        self.assertFalse(any(name.startswith('stage2/no_cutoff_recovery_') for name in value['bindings']['local']))
        self.assertIn('stage2/no_cutoff_recovery_handoff.py', document['local_files'])
        self.assertGreaterEqual(self.previous.call_count, 3)

    def test_uncommitted_current_source_refuses_before_audit(self):
        self.git_bytes['stage2/no_cutoff_recovery_handoff.py'] += b'\n'
        with self.assertRaises(ValueError): self.captured()
        self.e.collect.assert_not_called()

    def test_uncommitted_public_result_refuses_before_audit(self):
        self.git_bytes[export.DESTINATION + '/summary.json'] += b'\n'
        with self.assertRaises(ValueError): self.captured()
        self.e.collect.assert_not_called()

    def test_raw_snapshot_drift_cannot_be_saved_flag_shortcut(self):
        with (self.e.folder / 'snapshot.json').open('ab') as stream: stream.write(b' ')
        with self.assertRaises(ValueError): self.captured()
        self.e.collect.assert_not_called()

    def test_old_failed_backup_preservation_is_required_before_audit(self):
        self.previous.side_effect = ValueError('prior failure changed')
        with self.assertRaises(ValueError): self.captured()
        self.e.collect.assert_not_called()

    def test_current_source_drift_during_fresh_audit_refuses(self):
        def changed(_):
            with (self.root / 'stage2/no_cutoff_recovery_handoff.py').open('ab') as stream: stream.write(b' ')
            return deepcopy(self.e.fresh)
        self.e.collect.side_effect = changed
        with self.assertRaises(ValueError): self.captured()

    def test_archive_changed_after_verification_refuses(self):
        original = export._recheck
        def changed(value):
            original(value)
            with (self.e.folder / 'evidence.tar.gz').open('ab') as stream: stream.write(b'x')
        with patch.object(export, '_recheck', side_effect=changed), self.assertRaises(ValueError):
            self.captured()

    def test_final_sender_reread_failure_withholds_commitment(self):
        captured = self.captured()
        calls = 0
        original = operator._recheck
        def checked(value):
            nonlocal calls
            calls += 1
            if calls == 2: raise ValueError('late source mutation')
            original(value)
        read, write = os.pipe(); output = io.BytesIO(); failures = []
        def sender():
            try:
                with os.fdopen(write, 'wb', buffering=0) as destination: handoff.send(destination)
            except ValueError as exc: failures.append(type(exc))
        with patch.object(operator, '_capture', return_value=captured), patch.object(operator, '_recheck', side_effect=checked):
            thread = threading.Thread(target=sender); thread.start()
            with os.fdopen(read, 'rb', buffering=0) as source:
                while chunk := source.read(65536): output.write(chunk)
            thread.join(timeout=10); self.assertFalse(thread.is_alive())
        packet = io.BytesIO(output.getvalue()); _, digest = wire.read_header(packet)
        self.assertEqual(packet.read(), self.archive_raw)
        self.assertEqual(failures, [ValueError])

    def test_wrong_baseline_or_extra_envelope_is_not_recovery(self):
        header = self.header()
        for change in (dict(successor_experiment='matched-repeat-terminus-2'),
                dict(kind='existing_off_server_amended_final_archive_v1'), dict(extra=True),
                dict(schema_version=True)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.pipe(self.packet({**header, **change}))
        self.native_audit.assert_not_called()

    def test_operator_document_extra_or_paid_fields_refuse(self):
        header = self.header()
        for change in (dict(paid_launch_ready=True), dict(harness='terminus-2'), dict(schema_version=True),
                dict(operator_commit='HEAD')):
            modified = deepcopy(header); modified['operator'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): self.pipe(self.packet(modified))
        self.native_audit.assert_not_called()

    def test_changed_exact_raw_metadata_refuses_even_canonical_equivalent(self):
        header = self.header()
        for key in ('snapshot', 'backup'):
            modified = deepcopy(header); modified[key] += ' '
            with self.subTest(key=key), self.assertRaises(ValueError): self.pipe(self.packet(modified))
        self.native_audit.assert_not_called()

    def test_missing_truncated_bad_commit_or_trailing_bytes_refuse_before_native_audit(self):
        header = self.header(); good = self.packet(header)
        cases = (self.packet(header, committed=False), good[:-1], good[:-1] + bytes([good[-1] ^ 1]),
            self.packet(header, tail=b'junk'), good[:len(good) // 2])
        for packet in cases:
            with self.subTest(length=len(packet)), self.assertRaises(ValueError): self.pipe(packet)
        self.native_audit.assert_not_called()

    def test_post_header_stop_refuses_before_archive_authentication_and_native_audit(self):
        packet = self.packet()
        self.no_stop.side_effect = ValueError('synthetic persistent stop')
        with patch.object(archive, 'verify_stream', wraps=archive.verify_stream) as verify, \
                self.assertRaisesRegex(ValueError, 'synthetic persistent stop'):
            self.pipe(packet)
        verify.assert_not_called(); self.native_audit.assert_not_called()
        self.assertFalse(handoff._WITNESSES)

    def test_truncated_header_never_observes_ancestors_or_authenticates_archive(self):
        with patch.object(archive, 'verify_stream', wraps=archive.verify_stream) as verify, \
                self.assertRaises(ValueError):
            self.pipe(b'incomplete transport header')
        self.no_stop.assert_not_called(); verify.assert_not_called()
        self.native_audit.assert_not_called()

    def test_corrupt_archive_refuses_before_native_audit(self):
        raw = bytearray(self.archive_raw); raw[len(raw) // 2] ^= 1
        with self.assertRaises((ValueError, OSError, EOFError)): self.pipe(self.packet(archive_raw=bytes(raw)))
        self.native_audit.assert_not_called()

    def test_current_native_source_mutation_refuses(self):
        packet = self.packet()
        with (self.root / 'stage2/no_cutoff_recovery_handoff.py').open('ab') as stream: stream.write(b' ')
        with self.assertRaises(ValueError): self.pipe(packet)
        self.native_audit.assert_not_called()

    def test_original_qualification_copy_must_be_exact_private_bytes(self):
        packet = self.packet()
        with (self.root / phase.RT / policy.ORIGINAL_FILE).open('ab') as stream: stream.write(b' ')
        with self.assertRaises(ValueError): self.pipe(packet)
        self.native_audit.assert_not_called()

    def test_actual_native_reporter_or_producer_drift_refuses(self):
        packet = self.packet()
        for name in ('stage2/no_cutoff_final_report.py', producer.STATE[0], producer.STATE[1]):
            path = report.REPORTING / name; raw = path.read_bytes()
            if name.startswith('stage2/'):
                changed = raw + b' '
            else:
                changed = producer._json({**phase._loads(raw), 'automatic_resume': True})
            path.write_bytes(changed)
            with self.subTest(name=name), self.assertRaises(ValueError): self.pipe(packet)
            path.write_bytes(raw)
        self.native_audit.assert_not_called()

    def test_native_producer_raw_byte_mutation_after_authentication_latches(self):
        async def action(witness):
            path = report.REPORTING / producer.STATE[0]; raw = path.read_bytes()
            path.write_bytes(raw + b' ')
            with self.assertRaises(ValueError): handoff.recheck(witness)
            path.write_bytes(raw)
            with self.assertRaises(ValueError): handoff.recheck(witness)
        self.pipe(self.packet(), action=action)

    def test_native_reporting_failure_marker_is_not_ignored(self):
        packet = self.packet(); path = report.REPORTING / producer.STATE[2]; path.write_bytes(b'{}'); path.chmod(0o600)
        with self.assertRaises(ValueError): self.pipe(packet)
        self.native_audit.assert_not_called()

    def test_stale_or_different_native_audit_refuses_witness(self):
        packet = self.packet()
        changed = deepcopy(self.e.fresh); changed['rows'][3]['known_input_tokens'] += 1
        stale = deepcopy(self.e.fresh); stale['collected_utc'] = '2027-01-15T23:59:00+00:00'
        for fresh in (changed, stale):
            self.native_audit.side_effect = lambda _, fresh=fresh: deepcopy(fresh)
            with self.subTest(timestamp=fresh['collected_utc']), self.assertRaises(ValueError): self.pipe(packet)
        self.assertFalse(handoff._WITNESSES)

    def test_last_service_observation_followed_by_manifest_reread(self):
        packet = self.packet(); calls = 0
        def changed(_):
            nonlocal calls
            calls += 1
            if calls == 4:
                with (self.root / 'stage2/input_manifest.json').open('ab') as stream: stream.write(b' ')
        self.no_stop.side_effect = changed
        with self.assertRaises(ValueError): self.pipe(packet)
        self.assertEqual(calls, 4); self.assertFalse(handoff._WITNESSES)

    def test_recheck_inside_caller_lock_does_not_audit_transfer_or_lock_recursively(self):
        async def action(witness):
            calls = self.native_audit.call_count
            with (self.root / 'synthetic-ancestor.lock').open('rb') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try: value = handoff.recheck(witness)
                finally: fcntl.flock(lock, fcntl.LOCK_UN)
            self.assertEqual(self.native_audit.call_count, calls)
            value['predecessor']['results_sha256'].clear()
            self.assertEqual(len(handoff.describe(witness)['predecessor']['results_sha256']), 89)
            handoff.invalidate(witness)
            with self.assertRaises(ValueError): handoff.recheck(witness)
            return value
        self.pipe(self.packet(), action=action)

    def test_retained_unstarted_identity_change_latches_the_live_witness(self):
        self.no_stop.return_value = {'retained_identity': {'inode': 1}}
        async def action(witness):
            self.no_stop.return_value = {'retained_identity': {'inode': 2}}
            with self.assertRaises(ValueError): handoff.recheck(witness)
            self.no_stop.return_value = {'retained_identity': {'inode': 1}}
            with self.assertRaises(ValueError): handoff.recheck(witness)
        self.pipe(self.packet(), action=action)

    def test_failed_reread_latches_and_restoration_does_not_revive(self):
        async def action(witness):
            path = self.root / 'stage2/input_manifest.json'; raw = path.read_bytes()
            path.write_bytes(raw + b' ')
            with self.assertRaises(ValueError): handoff.recheck(witness)
            path.write_bytes(raw)
            with self.assertRaises(ValueError): handoff.recheck(witness)
        self.pipe(self.packet(), action=action)

    def test_recheck_detects_new_absence_inventory_and_historical_outcome(self):
        for mode in ('absence', 'inventory', 'history'):
            async def action(witness):
                if mode == 'absence':
                    path = self.root / self.data['absent_paths'][0]; original = None
                elif mode == 'inventory':
                    relative = next(iter(self.data['directory_entries']))
                    path = self.root / relative / 'extra.json'; original = None
                else:
                    base, files = next(iter(self.data['preserved_result_files'].items()))
                    path = Path(base) / next(iter(files)); original = path.read_bytes()
                path.write_bytes(b'{}'); path.chmod(0o600)
                try:
                    with self.assertRaises(ValueError): handoff.recheck(witness)
                finally:
                    if original is None: path.unlink()
                    else: path.write_bytes(original)
            with self.subTest(mode=mode): self.pipe(self.packet(), action=action)

    def test_copied_constructed_or_saved_witness_cannot_substitute(self):
        for fake in ({'paid_launch_ready': False}, handoff._Witness(), None):
            with self.assertRaises(ValueError): handoff.describe(fake)
        async def action(witness):
            for fn in (copy, deepcopy, pickle.dumps):
                with self.assertRaises(TypeError): fn(witness)
            with self.assertRaises(ValueError): handoff.recheck(handoff.describe(witness))
        self.pipe(self.packet(), action=action)

    def test_cross_async_task_misuse_invalidates_owner(self):
        async def action(witness):
            async def other():
                with self.assertRaises(ValueError): handoff.describe(witness)
            await asyncio.create_task(other())
            with self.assertRaises(ValueError): handoff.describe(witness)
        self.pipe(self.packet(), action=action)

    def test_cross_process_or_thread_misuse_invalidates_owner(self):
        for mode in ('process', 'thread'):
            async def action(witness):
                if mode == 'process':
                    with patch.object(handoff.os, 'getpid', return_value=-1), self.assertRaises(ValueError):
                        handoff.describe(witness)
                else:
                    errors = []
                    def other():
                        try: handoff.describe(witness)
                        except ValueError: errors.append(True)
                    worker = threading.Thread(target=other); worker.start(); worker.join(timeout=10)
                    self.assertEqual(errors, [True])
                with self.assertRaises(ValueError): handoff.describe(witness)
            with self.subTest(mode=mode): self.pipe(self.packet(), action=action)

    def test_regular_file_or_saved_bytesio_cannot_be_a_live_transfer(self):
        with self.assertRaises(ValueError): handoff.authenticate(io.BytesIO(self.packet()))
        with (self.e.folder / 'evidence.tar.gz').open('rb') as source, self.assertRaises(ValueError):
            handoff.authenticate(source)
        self.native_audit.assert_not_called()

    def test_raw_reader_refuses_symlink_hardlink_fifo_and_permissions(self):
        # New-root protection, not the special frozen-root permission exception.
        root = self.root / 'new'; root.mkdir(mode=0o700)
        runtime = root / '.runtime/stage2'; runtime.mkdir(parents=True, mode=0o700)
        (root / '.runtime').chmod(0o700)
        path = runtime / 'input.json'
        for mode in ('symlink', 'hardlink', 'fifo', 'public', 'read_only', 'executable', 'group_write_parent'):
            path.write_bytes(b'{}'); path.chmod(0o600)
            extra = runtime / 'extra'
            if mode == 'symlink': path.rename(extra); path.symlink_to(extra)
            if mode == 'hardlink': os.link(path, extra)
            if mode == 'fifo': path.unlink(); os.mkfifo(path, 0o600)
            if mode == 'public': path.chmod(0o644)
            if mode == 'read_only': path.chmod(0o400)
            if mode == 'executable': path.chmod(0o700)
            if mode == 'group_write_parent': runtime.chmod(0o770)
            with self.subTest(mode=mode), self.assertRaises(ValueError): handoff._raw(root, '.runtime/stage2/input.json')
            path.unlink(); runtime.chmod(0o700)
            if extra.exists(): extra.unlink()
        path.write_bytes(b'{}'); path.chmod(0o600)
        self.assertEqual(handoff._raw(root, '.runtime/stage2/input.json'), b'{}')

    def test_raw_reader_rejects_wrong_file_group(self):
        path = self.root / phase.RT / policy.ORIGINAL_FILE
        actual = path.stat()
        wrong = NS(**{name: getattr(actual, name) for name in dir(actual) if name.startswith('st_')})
        wrong.st_gid = -1
        with patch.object(handoff.os, 'fstat', return_value=wrong), self.assertRaises(ValueError):
            handoff._raw(self.root, phase.RT + policy.ORIGINAL_FILE)

    def test_raw_reader_refuses_acl_and_directory_identity_change(self):
        root = self.root / 'new'; root.mkdir(mode=0o700); (root / 'stage2').mkdir(mode=0o700)
        path = root / 'stage2/input.py'; path.write_bytes(b'pass'); path.chmod(0o600)
        with patch.object(phase.guard, '_acl', side_effect=ValueError('ACL')), self.assertRaises(ValueError):
            handoff._raw(root, 'stage2/input.py')
        original = handoff._protection; calls = 0
        def changed(*args):
            nonlocal calls
            calls += 1
            value = original(*args)
            return value if calls == 1 else ('changed',)
        with patch.object(handoff, '_protection', side_effect=changed), self.assertRaises(ValueError):
            handoff._raw(root, 'stage2/input.py')

    def test_native_audit_uses_original_isolated_interpreter_and_exact_environment(self):
        header = self.header(); value = handoff._anchors(self.root, header)
        raw = producer._json(self.e.fresh)
        with patch.object(launch.transport, '_exchange', return_value=(raw, {'synthetic': True})) as exchange, \
                patch.object(launch.transport, '_completed') as completed:
            self.assertEqual(ACTUAL_NATIVE_AUDIT(value), self.e.fresh)
        args, kwargs = exchange.call_args
        self.assertEqual(args[2], [str(report.ROOT / '.venv/bin/python'), '-I', '-B', '-'])
        self.assertEqual(args[3], report.ENVIRONMENT); self.assertEqual(kwargs, {'cwd': report.ROOT})
        self.assertIn('collect()', args[0]); completed.assert_called_once()
        self.no_process.assert_not_called()

    def test_no_stop_uses_actual_manager_check_and_refuses_duplicate_service_state(self):
        (report.BASELINE / '.runtime/stage2').chmod(0o700); report.BASELINE.chmod(0o700)
        good = 'LoadState=loaded\nActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n'
        with patch.object(report.guard, 'service') as manager, patch.object(handoff.revision, 'inspect') as baseline:
            self.no_process.side_effect = None; self.no_process.return_value = NS(stdout=good)
            ACTUAL_NO_STOP(self.root); manager.assert_called_once()
            baseline.side_effect = ValueError('synthetic changed trusted manager record')
            with self.assertRaises(ValueError): ACTUAL_NO_STOP(self.root)
            baseline.side_effect = None
            self.e.save(phase.RT + 'operator-stop-request.json', b'{"automatic_resume":false}')
            with self.assertRaises(ValueError): ACTUAL_NO_STOP(self.root)

    def test_production_context_refuses_local_or_nonasync_scope(self):
        with self.assertRaises(ValueError): ACTUAL_CONTEXT()
        async def checked():
            with patch.object(handoff.platform, 'system', return_value='Darwin'), self.assertRaises(ValueError):
                ACTUAL_CONTEXT()
        asyncio.run(checked())


class RecoveryLoadedSourcesTests(unittest.TestCase):
    def test_exact_anchor_comparison_preserves_bytes_and_numeric_types(self):
        original = dict(anchors={'input': b'{"number":1.0}'}, numeric=1.0)
        operator._same_anchored(deepcopy(original), original)
        for changed in (dict(anchors={'input': b'{"number":1}'}, numeric=1.0),
                dict(anchors=original['anchors'], numeric=1)):
            with self.assertRaises(ValueError): operator._same_anchored(changed, original)

    def test_isolated_import_refuses_writes_network_processes_and_credentials(self):
        program = r'''
import hashlib, os, sys
from pathlib import Path
stage=Path(sys.argv[1]); sys.path.insert(0,str(stage))
sys.pycache_prefix=sys.argv[2]
bound={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.glob('*.py')}
def guard(event,args):
 if event=='open':
  target=args[0]; mode=args[1]; flags=args[2]
  if isinstance(target,(str,bytes)) and Path(os.fsdecode(target)).name=='.env':
   raise AssertionError('credential read')
  if isinstance(mode,str) and any(c in mode for c in 'wax+') or isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
   raise AssertionError('write')
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.exec','os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.chmod','os.chown','os.truncate','os.utime'} or event.startswith('socket.'):
  raise AssertionError('external effect')
sys.addaudithook(guard)
import no_cutoff_recovery_predecessor as operator
import no_cutoff_recovery_handoff as handoff
loaded=operator.loaded(stage.parent,bound)
assert {'no_cutoff_recovery_predecessor.py','no_cutoff_recovery_handoff.py'}<=loaded
assert not handoff._WITNESSES
print('read-only component import passed')
'''
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(STAGE),
                str(Path(temp) / 'absent-cache')], check=True, capture_output=True, text=True,
                env=dict(PATH=os.defpath, PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1',
                    LITELLM_MODE='PRODUCTION', LITELLM_LOCAL_MODEL_COST_MAP='True'))
        self.assertEqual(result.stdout.strip(), 'read-only component import passed')

    def test_actual_loaded_origin_and_bytes_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); stage = root / 'stage2'; stage.mkdir()
            path = stage / 'unique_recovery_origin_check.py'; path.write_bytes(b'pass'); path.chmod(0o600)
            name = path.stem; bound = {path.name: export._hash(path.read_bytes())}
            # Isolate only this inventory for the origin guard test.
            with patch.object(sys, 'modules', {name: NS(__file__=str(path))}):
                self.assertEqual(ACTUAL_LOADED(root, bound), {path.name})
                path.write_bytes(b'pass\n')
                with self.assertRaises(ValueError): ACTUAL_LOADED(root, bound)
            for filename in (str(root / path.name), str(path) + 'c', None):
                with patch.object(sys, 'modules', {name: NS(__file__=filename)}), self.assertRaises(ValueError):
                    ACTUAL_LOADED(root, bound)

    def test_audit_digest_excludes_only_collection_time(self):
        one = dict(collected_utc='a', reward=None, duration=1.0)
        self.assertEqual(operator.audit_hash(one), operator.audit_hash({**one, 'collected_utc': 'b'}))
        for change in (dict(reward=0.0), dict(duration=1), dict(extra=False)):
            self.assertNotEqual(operator.audit_hash(one), operator.audit_hash({**one, **change}))


if __name__ == '__main__':
    unittest.main()
