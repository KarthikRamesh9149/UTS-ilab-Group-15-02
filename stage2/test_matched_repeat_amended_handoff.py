"""Actual amended capture, archive and local pipes; native observations mocked."""
import asyncio
from copy import deepcopy
import io
import fcntl
import json
import os
from pathlib import Path
import pickle
import subprocess
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_amended_handoff as handoff
import matched_repeat_amended_predecessor as operator
import matched_repeat_connection as connection
import matched_repeat_session as session
import matched_repeat_stream as wire
import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch
import test_matched_repeat_amended_predecessor as fixtures
from run_credit_only import hold


class HandoffFixture(fixtures.CaptureFixture):
    def setUp(self):
        super().setUp()
        self.native = report.ROOT
        self.enterContext(patch.object(handoff, '__file__', str(self.repo / 'stage2/matched_repeat_amended_handoff.py')))
        # The local fixture uses one shared checkout for repeat and operator
        # source bytes; native execution/reporting and historical trees are
        # still actual separate bound paths. No native context is claimed.
        for name, value, anchor in ((handoff.policy.BASELINE_FILE, self.f.original, 'ORIGINAL_FILE_SHA256'),
                (handoff.policy.FINAL_FILE, self.f.proof, 'FINAL_FILE_SHA256')):
            raw = producer._json(value); self.save(phase.RT + name, raw)
            self.enterContext(patch.object(handoff.baseline, anchor, export._hash(raw)))
        self.enterContext(patch.object(handoff.baseline, 'FINAL_ROOT', self.native))
        self.inactive = self.enterContext(patch.object(handoff.baseline, 'inactive_ancestors'))
        self.enterContext(patch.dict(handoff.runtime.DEPLOYMENTS, {'terminus-2': self.repo}))
        self.context = self.enterContext(patch.object(handoff, '_context', side_effect=self.context_check))
        self.loaded = self.enterContext(patch.object(handoff.runtime, 'loaded_sources'))
        self.enterContext(patch.object(handoff.runtime, 'sources', side_effect=lambda *a: deepcopy(self.current)))
        self.audit = self.enterContext(patch.object(handoff, '_native_audit', side_effect=lambda _: deepcopy(self.e.fresh)))
        self.no_native = self.enterContext(patch('subprocess.run', side_effect=AssertionError('No actual native calls')))
        self.seed_native_backup()

    def seed_native_backup(self):
        self.f.backup = phase._loads((self.e.folder / 'backup.json').read_bytes())
        for directory in [report.REPORTING, *[p for p in report.REPORTING.rglob('*') if p.is_dir()]]:
            directory.chmod(0o700)
        for path in report.REPORTING.rglob('*'):
            if path.is_file(): path.chmod(0o600)
        records = [dict(kind='one_shot_amended_final_backup_intent', created_utc='2027-01-16T00:00:00+00:00',
            snapshot_sha256=phase.fingerprint(self.f.data), reporting_source_files=self.f.data['reporting_source_files'],
            automatic_resume=False, paid_launch_ready=False),
            dict(kind='native_amended_archive_streamed_not_off_server_proof', receipt=self.f.backup['receipt'],
                automatic_resume=False, off_server_backup_verified=False, paid_launch_ready=False)]
        for name, value in zip(producer.STATE, records):
            path = report.REPORTING / name; path.write_bytes(producer._json(value)); path.chmod(0o600)

    def context_check(self, root, harness):
        handoff._first(harness)
        if Path(root) != self.repo: raise ValueError('Wrong root')
        return self.repo

    def header(self):
        document = self.capture()
        return dict(kind=handoff.TRANSFER_KIND, schema_version=1, harness='terminus-2', operator=document,
            snapshot=(self.e.folder / 'snapshot.json').read_text(), backup=(self.e.folder / 'backup.json').read_text())

    def packet(self, header=None, *, commit=True):
        header = self.header() if header is None else header
        packet = io.BytesIO(); digest = wire.write_header(packet, header)
        raw = self.f.archive.read_bytes()
        wire.copy_archive(io.BytesIO(raw), packet, len(raw), self.f.backup['receipt']['sha256'])
        if commit: wire.commit(packet, digest, self.f.backup['receipt']['sha256'])
        return packet.getvalue()

    def receive(self, packet=None, *, send=False):
        if packet is None and not send: packet = self.packet()
        incoming, outgoing = os.pipe(); errors = []; sent = []
        def produce():
            try:
                with os.fdopen(outgoing, 'wb') as output:
                    if send: sent.append(handoff.send(self.repo, output))
                    else: wire._write(output, packet)
            except BaseException as error: errors.append(error)
        worker = threading.Thread(target=produce, daemon=True); worker.start()
        try:
            with os.fdopen(incoming, 'rb') as stream:
                witness = handoff.authenticate(self.repo, self.f.original, self.f.proof, 'terminus-2', stream)
        finally:
            worker.join(timeout=10); self.assertFalse(worker.is_alive())
        if errors: raise errors[0]
        return witness, sent

    def recheck(self, witness):
        return handoff.recheck(self.repo, self.f.original, self.f.proof, 'terminus-2', witness)


class AmendedHandoffTests(HandoffFixture):
    def test_actual_sender_capture_stream_fresh_audit_and_live_recheck(self):
        raw = self.f.archive.read_bytes()
        with patch.object(archive, 'verify_stream', wraps=archive.verify_stream) as verify:
            witness, sent = self.receive(send=True)
        self.operator_audit.assert_called_once(); self.audit.assert_called_once()
        # The path verifier also uses verify_stream internally: one Mac read
        # of the retained file and one independent native transport read.
        self.assertEqual(verify.call_count, 2)
        record = self.recheck(witness)
        self.assertEqual(record, handoff.describe(witness)); self.assertEqual(record['streamed_backup'], self.f.backup['verification'])
        self.assertEqual(sent[0]['operator_document_sha256'], record['operator_document_sha256'])
        self.assertEqual(record['absent_paths'], self.f.data['absent_paths'])
        self.assertEqual(sum(map(len, record['preserved_result_files'].values())), 182)
        self.assertEqual(self.f.archive.read_bytes(), raw); self.assertFalse(record['paid_launch_ready'])
        self.assertFalse(record['streamed_backup']['completed_final_audit'])
        self.assertFalse(record['streamed_backup']['off_server_location_verified'])
        self.assertIsNone(self.f.data['rows'][0]['reward']); self.assertIsNone(self.f.data['rows'][0]['agent_seconds'])

    def test_old_route_is_unchanged_and_actual_consumers_select_amended_route(self):
        self.assertIs(session.handoff, handoff); self.assertIs(connection.handoff, handoff)
        with patch('matched_repeat_predecessor.capture', side_effect=AssertionError('Old capture forbidden')), \
                patch('matched_repeat_handoff.authenticate', side_effect=AssertionError('Old audit forbidden')), \
                patch.object(wire, 'verify_archive', side_effect=AssertionError('Old stream verifier forbidden')):
            self.receive(send=True)

    def test_actual_amended_witness_is_consumed_by_same_task_locked_session(self):
        packet = self.packet(); incoming, outgoing = os.pipe(); self.locked = False
        common = dict(experiment=handoff.policy.EXPERIMENT, harness='terminus-2', paid_launch_ready=False,
            original_qualification_sha256=phase.fingerprint(self.f.original),
            custom_final_qualification_sha256=phase.fingerprint(self.f.proof))
        source_sha = phase.fingerprint(self.current)
        old = dict(common, kind=session.original_audit.KIND, current_sources_sha256=source_sha)
        library = dict(common, kind=session.baseline.KIND, current_sources_sha256=source_sha)
        host = dict(common, kind=session.runtime.KIND, sources=deepcopy(self.current), sources_sha256=source_sha)
        def authenticate(*args):
            self.assertFalse(self.locked); return deepcopy(old)
        def audit(_):
            self.assertFalse(self.locked); return deepcopy(self.e.fresh)
        def lock(stack, *args):
            hold(stack, self.repo, 'amended-test-session.lock'); self.locked = True
            stack.callback(lambda: setattr(self, 'locked', False))
        def observe(value):
            self.assertTrue(self.locked)
            with (self.repo / 'amended-test-session.lock').open('rb') as competing:
                with self.assertRaises(BlockingIOError): fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return deepcopy(value)
        def produce():
            with os.fdopen(outgoing, 'wb') as output: wire._write(output, packet)
        worker = threading.Thread(target=produce, daemon=True); worker.start()
        self.audit.side_effect = audit
        with patch.object(session, '_context', side_effect=self.context_check), \
                patch.object(session.original_audit, 'authenticate', side_effect=authenticate), \
                patch.object(session.original_audit, 'lock_all', side_effect=lock), \
                patch.object(session.original_audit, 'recheck', side_effect=lambda *a: observe(old)), \
                patch.object(session.baseline, 'inspect', side_effect=lambda *a: observe(library)), \
                patch.object(session.baseline, 'recheck', side_effect=lambda *a: observe(library)), \
                patch.object(session.runtime, 'inspect', side_effect=lambda *a: observe(host)):
            async def consume():
                with os.fdopen(incoming, 'rb') as stream:
                    with session.open_session(self.repo, 'terminus-2', stream) as active:
                        description = session.recheck(active)
                        self.assertEqual(description['predecessor']['kind'], handoff.KIND)
                        self.assertEqual(len(description['predecessor']['absent_paths']), 3)
                        self.assertIs(session._live(active)['task'], asyncio.current_task())
                    with self.assertRaises(ValueError): session.describe(active)
            try: asyncio.run(consume())
            finally:
                worker.join(timeout=10); self.assertFalse(worker.is_alive())
        self.audit.assert_called_once(); self.assertFalse(self.locked)

    def test_regular_file_saved_json_and_constructed_witness_are_not_live(self):
        with self.f.archive.open('rb') as stream, self.assertRaises(ValueError):
            handoff.authenticate(self.repo, self.f.original, self.f.proof, 'terminus-2', stream)
        for value in ({'paid_launch_ready': False}, handoff._Witness(), None):
            with self.assertRaises(ValueError): handoff.describe(value)
        self.audit.assert_not_called()

    def test_missing_commitment_is_refused_before_native_audit(self):
        with self.assertRaises(ValueError): self.receive(self.packet(commit=False))
        self.audit.assert_not_called()

    def test_truncated_archive_and_extra_transfer_bytes_are_refused(self):
        raw = self.packet()
        for changed in (raw[:len(raw)//2], raw + b'extra'):
            with self.subTest(length=len(changed)), self.assertRaises(ValueError): self.receive(changed)
        self.audit.assert_not_called()

    def test_old_envelope_cannot_select_the_amended_reader(self):
        header = self.header(); header['kind'] = 'existing_off_server_custom_final_archive_v1'
        with self.assertRaises(ValueError): self.receive(self.packet(header))
        self.audit.assert_not_called()

    def test_operator_absence_or_historical_map_cannot_be_rewritten(self):
        for key in ('absent_paths', 'preserved_result_files', 'directory_entries'):
            header = self.header(); header['operator'][key] = [] if key == 'absent_paths' else {}
            with self.subTest(key=key), self.assertRaises(ValueError): self.receive(self.packet(header))
        self.audit.assert_not_called()

    def test_new_deadline_after_transfer_refuses_and_invalidates_witness(self):
        witness, _ = self.receive()
        name = self.f.data['absent_paths'][0]; self.save(name, b'{}')
        with self.assertRaises(ValueError): self.recheck(witness)
        (self.repo / name).unlink()
        with self.assertRaises(ValueError): self.recheck(witness)

    def test_changed_historical_outcome_refuses_under_lock_reread(self):
        witness, _ = self.receive()
        root, files = next(iter(self.f.data['preserved_result_files'].items()))
        path = Path(root) / next(iter(files)); path.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.recheck(witness)

    def test_changed_trace_and_new_inventory_entry_refuse_recheck(self):
        witness, _ = self.receive()
        name = next(iter(self.f.data['directory_entries']))
        self.save(name + '/new.json', b'{}')
        with self.assertRaises(ValueError): self.recheck(witness)

    def test_native_backup_failure_or_partial_deployment_refuses_before_audit(self):
        path = report.REPORTING / producer.STATE[2]; path.write_bytes(b'{}'); path.chmod(0o600)
        with self.assertRaises(ValueError): self.receive()
        self.audit.assert_not_called()

    def test_native_backup_result_receipt_mutation_refuses(self):
        path = report.REPORTING / producer.STATE[1]
        value = phase._loads(path.read_bytes()); value['receipt']['sha256'] = '0' * 64
        path.write_bytes(producer._json(value))
        with self.assertRaises(ValueError): self.receive()
        self.audit.assert_not_called()

    def test_actual_service_stop_refuses_before_stream_or_collector(self):
        self.save(phase.RT + 'operator-stop-request.json', b'{}')
        with self.assertRaises(ValueError): self.receive()
        self.audit.assert_not_called()

    def test_active_ancestor_refuses_before_archive_or_collector(self):
        self.inactive.side_effect = ValueError('active ancestor')
        with self.assertRaises(ValueError): self.receive()
        self.audit.assert_not_called()

    def test_fresh_audit_changed_or_older_is_not_equal_evidence(self):
        packet = self.packet()
        stale = deepcopy(self.e.fresh); stale['collected_utc'] = '2027-01-15T00:00:00+00:00'
        self.audit.side_effect = lambda _: stale
        with self.assertRaises(ValueError): self.receive(packet)
        self.audit.assert_called_once()

    def test_mutation_at_last_service_observation_is_caught_by_final_bytes(self):
        witness, _ = self.receive()
        path = self.repo / self.f.data['absent_paths'][0]
        self.inactive.side_effect = lambda: path.write_bytes(b'{}')
        with self.assertRaises(ValueError): self.recheck(witness)

    def test_witness_cannot_cross_process_thread_task_or_be_pickled(self):
        witness, _ = self.receive()
        with self.assertRaises(TypeError): pickle.dumps(witness)
        with patch.object(handoff.os, 'getpid', return_value=-1), self.assertRaises(ValueError): handoff.describe(witness)
        errors = []
        def use():
            try: handoff.describe(witness)
            except ValueError: errors.append(True)
        worker = threading.Thread(target=use); worker.start(); worker.join(timeout=5)
        self.assertEqual(errors, [True])
        async def other():
            with self.assertRaises(ValueError): handoff.describe(witness)
        asyncio.run(other())

    def test_description_is_copied_and_not_a_reusable_witness(self):
        witness, _ = self.receive(); description = handoff.describe(witness)
        description['absent_paths'].clear()
        self.assertTrue(handoff.describe(witness)['absent_paths'])
        with self.assertRaises(ValueError): self.recheck(description)

    def test_sender_withholds_commitment_after_post_stream_source_mutation(self):
        original = wire.copy_archive
        def change(*args):
            original(*args)
            path = self.repo / 'stage2/matched_repeat_amended_predecessor.py'
            path.write_bytes(path.read_bytes() + b'\n')
        with patch.object(wire, 'copy_archive', side_effect=change), \
                patch.object(wire, 'commit', wraps=wire.commit) as commit:
            with self.assertRaises(ValueError): self.receive(send=True)
        self.assertEqual(commit.call_count, 0); self.audit.assert_not_called()

    def test_changed_native_result_during_actual_audit_is_not_hidden(self):
        path = self.repo / phase.RT / 'scored-trials' / self.f.data['rows'][0]['trial_id'] / 'result.json'
        def change(_):
            path.write_bytes(path.read_bytes() + b'\n')
            return deepcopy(self.e.fresh)
        self.audit.side_effect = change
        with self.assertRaises(ValueError): self.receive()

    def test_changed_reporting_source_during_actual_audit_is_not_hidden(self):
        path = report.REPORTING / 'stage2/matched_repeat_amended_handoff.py'
        def change(_):
            path.write_bytes(path.read_bytes() + b'\n')
            return deepcopy(self.e.fresh)
        self.audit.side_effect = change
        with self.assertRaises(ValueError): self.receive()

    def test_copied_qualification_and_public_projection_are_reread(self):
        witness, _ = self.receive()
        path = self.repo / phase.RT / handoff.policy.FINAL_FILE
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(ValueError): self.recheck(witness)

    def test_under_lock_recheck_never_repeats_collector_or_archive_transfer(self):
        witness, _ = self.receive()
        with patch.object(handoff, '_native_audit', side_effect=AssertionError('Recursive collector')), \
                patch.object(archive, 'verify_stream', side_effect=AssertionError('Repeated transfer')), \
                patch.object(report, 'collect', side_effect=AssertionError('Direct collector')):
            self.recheck(witness)

    def test_setup_only_unknown_phase_values_and_raw_float_bytes_survive_transfer(self):
        header = self.header()
        self.assertIn('7200.0', header['snapshot'])
        witness, _ = self.receive(self.packet(header))
        snapshot = phase._loads(handoff._live(witness)['header']['snapshot'])
        self.assertIs(type(snapshot['rows'][0]['official_agent_timeout_seconds']), float)
        self.assertIsNone(snapshot['rows'][0]['agent_seconds'])
        self.assertEqual(snapshot['aggregates']['full89']['phase_durations']['agent']['not_run_attempts'], 3)

    def test_forged_backup_flags_do_not_grant_archive_or_native_authority(self):
        header = self.header(); backup = phase._loads(header['backup'])
        backup['verification']['off_server_location_verified'] = True
        header['backup'] = producer._json(backup).decode()
        document = header['operator']
        document['local_files'][receiver.DESTINATION + '/backup.json'] = export._hash(header['backup'].encode())
        # A self-consistent checksum does not fix the real committed projection.
        with self.assertRaises(ValueError): self.receive(self.packet(header))
        self.audit.assert_not_called()

    def test_wrong_final_marker_digest_cannot_be_accepted(self):
        packet = self.packet(); packet = packet[:-1] + bytes([packet[-1] ^ 1])
        with self.assertRaises(ValueError): self.receive(packet)
        self.audit.assert_not_called()

    def test_native_subprocess_errors_are_sanitised_and_never_retried(self):
        value = handoff._anchors(self.repo, self.f.original, self.f.proof, 'terminus-2', self.header())
        for error in (OSError('PRIVATE-DIAGNOSTIC'), subprocess.TimeoutExpired('private-command', 300)):
            with self.subTest(kind=type(error).__name__), patch('subprocess.run', side_effect=error) as run:
                with self.assertRaises(ValueError) as caught: _NATIVE_AUDIT(value)
                self.assertNotIn('PRIVATE-DIAGNOSTIC', str(caught.exception)); self.assertEqual(run.call_count, 1)

    def test_native_subprocess_uses_actual_reporting_bootstrap_and_exact_environment(self):
        value = handoff._anchors(self.repo, self.f.original, self.f.proof, 'terminus-2', self.header())
        # Call the original implementation retained before fixture patching.
        with patch('subprocess.run', return_value=NS(returncode=0, stdout=producer._json(self.e.fresh), stderr=b'')) as run:
            self.audit.side_effect = None
            result = _NATIVE_AUDIT(value)
        args, kwargs = run.call_args
        self.assertEqual(args[0], [str(report.ROOT / '.venv/bin/python'), '-I', '-B', '-'])
        self.assertEqual(kwargs['env'], report.ENVIRONMENT); self.assertEqual(kwargs['cwd'], report.ROOT)
        self.assertIn(b'value=audit.collect()', kwargs['input'])
        self.assertIn(b"'operation': 'collect'", kwargs['input'])
        self.assertEqual(result, self.e.fresh)

    def test_raw_reader_rejects_fifo_links_public_write_and_private_disclosure(self):
        name = 'test-metadata'; path = self.repo / name
        for mode in ('fifo', 'link', 'public-write'):
            if mode == 'fifo': os.mkfifo(path, 0o600)
            elif mode == 'link': path.symlink_to(self.f.archive)
            else: path.write_bytes(b'{}'); path.chmod(0o666)
            with self.subTest(mode=mode), self.assertRaises(ValueError): handoff._raw(self.repo, name)
            path.unlink()


_NATIVE_AUDIT = handoff._native_audit
