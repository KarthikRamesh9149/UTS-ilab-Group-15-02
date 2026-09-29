"""Real local streams/private archives; SSH/native context are explicitly mocked."""
import base64
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch

import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as operator
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch
import test_no_cutoff_final_archive as fixtures


class OperatorBackupTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ArchiveTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.commit = 'a' * 40
        for path in self.f.f.reporting.rglob('*'): path.chmod(0o700 if path.is_dir() else 0o600)
        self.enterContext(patch.object(launch, 'REPO', self.root))
        self.enterContext(patch.object(operator, '__file__', str(self.root / 'stage2/no_cutoff_final_backup_operator.py')))
        (self.root / '.runtime').chmod(0o700); (self.root / '.runtime/netcup').mkdir(mode=0o700)
        self.previous = self.root / operator.PREVIOUS_FAILED; self.previous.mkdir(mode=0o700)
        for name in ('intent.json', 'failure.json'):
            producer._save(self.previous, name, {'synthetic_retained_failure': name})
        self.enterContext(patch.object(operator, 'PREVIOUS_FILES', {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.previous.iterdir()}))
        self.bindings = dict(commit=self.commit, reporting=self.f.data['reporting_source_files'], anchors=self.f.anchors)
        self.prepare = self.enterContext(patch.object(launch, '_prepare', return_value=self.bindings))
        self.recheck = self.enterContext(patch.object(launch, '_recheck'))
        self.inspect = self.enterContext(patch.object(launch, 'inspect_deployment'))
        self.program = self.enterContext(patch.object(launch, '_program', return_value='synthetic bootstrap'))
        self.folder = self.root / operator.DESTINATION
        self.raw = self.frame(); self.code = 0; self.children = []
        self.actual_start = operator._start
        self.start = self.enterContext(patch.object(operator, '_start', side_effect=self.child))

    def frame(self, data=None, receipt_change=None, trailer=producer.END):
        data = data or self.f.data; output = io.BytesIO()
        producer._write(output, producer.MAGIC); producer._metadata(output, data)
        receipt = producer._pack(output, data, producer._inventory(data))
        if receipt_change: receipt_change(receipt)
        producer._write(output, struct.pack('!Q', 0)); producer._metadata(output, receipt)
        producer._write(output, trailer)
        return output.getvalue()

    def child(self):
        # Harmless local stdlib child, no network/native/bootstrap execution.
        script = 'import base64,sys;sys.stdin.buffer.read();sys.stdout.buffer.write(base64.b64decode(' + repr(
            base64.b64encode(self.raw).decode()) + '));sys.stdout.buffer.flush();sys.exit(' + str(self.code) + ')'
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.children.append(child); return child

    def test_success_reads_one_existing_archive_before_exclusive_commit(self):
        value = operator.backup(self.commit)
        self.assertTrue(value['off_server_backup_verified']); self.assertFalse(value['paid_launch_ready'])
        self.assertFalse(value['archive_export_and_handoff_integrated']); self.assertEqual(self.start.call_count, 1)
        self.inspect.assert_called_once_with(self.commit)
        self.assertEqual({p.name for p in self.folder.iterdir()}, {'intent.json','snapshot.json','evidence.tar.gz','backup.json'})
        data = phase._loads((self.folder / 'snapshot.json').read_bytes())
        checked = archive.verify_archive(self.folder / 'evidence.tar.gz', data, value['receipt'])
        self.assertEqual(checked, value['verification']); self.assertEqual(checked['verified_absent_paths'], 3)
        self.assertIsNone(data['rows'][0]['agent_seconds'])
        for p in self.folder.iterdir(): self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o700)

    def test_existing_or_partial_local_destination_refuses_before_ssh(self):
        self.folder.mkdir(mode=0o700)
        with self.assertRaises(ValueError): operator.backup(self.commit)
        self.start.assert_not_called(); self.inspect.assert_not_called()

    def test_earlier_failed_backup_must_remain_exact_before_any_native_operation(self):
        (self.previous / 'failure.json').write_bytes(b'changed')
        with self.assertRaises(ValueError): operator.backup(self.commit)
        self.start.assert_not_called(); self.inspect.assert_not_called()

    def test_earlier_archive_or_partial_snapshot_cannot_be_hidden(self):
        (self.previous / 'evidence.tar.gz').write_bytes(b'partial'); (self.previous / 'evidence.tar.gz').chmod(0o600)
        with self.assertRaises(ValueError): operator.backup(self.commit)
        self.start.assert_not_called(); self.inspect.assert_not_called()

    def test_earlier_failure_is_reread_after_transfer(self):
        original = archive.verify_archive
        def verify(*args):
            value = original(*args); (self.previous / 'failure.json').write_bytes(b'changed'); return value
        with patch.object(archive, 'verify_archive', side_effect=verify), self.assertRaises(ValueError): operator.backup(self.commit)
        self.assertFalse((self.folder / 'backup.json').exists()); self.assertTrue((self.folder / 'failure.json').exists())

    def test_success_cannot_be_run_again_or_archive_recreated(self):
        operator.backup(self.commit); raw = (self.folder / 'evidence.tar.gz').read_bytes()
        with self.assertRaises(ValueError): operator.backup(self.commit)
        self.assertEqual((self.folder / 'evidence.tar.gz').read_bytes(), raw); self.assertEqual(self.start.call_count, 1)

    def test_active_or_unknown_native_inspection_prevents_local_intent(self):
        self.inspect.side_effect = ValueError('active')
        with self.assertRaises(ValueError): operator.backup(self.commit)
        self.assertFalse(self.folder.exists()); self.start.assert_not_called()

    def test_wrong_operator_location_refuses_before_ssh(self):
        with patch.object(operator, '__file__', str(self.root / 'elsewhere.py')), self.assertRaises(ValueError):
            operator.backup(self.commit)
        self.inspect.assert_not_called()

    def test_nonprivate_or_symlinked_destination_parent_refuses(self):
        (self.root / '.runtime/netcup').chmod(0o755)
        with self.assertRaises(ValueError): operator.backup(self.commit)
        self.inspect.assert_not_called()

    def test_owned_readable_runtime_parent_remains_unchanged(self):
        (self.root/'.runtime').chmod(0o755)
        operator.backup(self.commit)
        self.assertEqual((self.root/'.runtime').stat().st_mode & 0o777,0o755)

    def test_parent_identity_change_before_receiver_prevents_success(self):
        original=self.child
        def changed():
            (self.root/'.runtime').chmod(0o755)
            return original()
        self.start.side_effect=changed
        with self.assertRaises(ValueError):operator.backup(self.commit)
        self.assertFalse((self.folder/'backup.json').exists())
        self.assertTrue((self.folder/'intent.json').exists())

    def failed(self):
        with self.assertRaisesRegex(ValueError, 'inspect retained'): operator.backup(self.commit)
        self.assertTrue((self.folder / 'intent.json').exists()); self.assertTrue((self.folder / 'failure.json').exists())
        self.assertFalse((self.folder / 'backup.json').exists())
        self.assertFalse(json.loads((self.folder / 'failure.json').read_bytes())['automatic_resume'])
        self.assertEqual(self.start.call_count, 1)
        with self.assertRaises(ValueError): operator.backup(self.commit)

    def test_truncated_stream_retains_partial_evidence_without_retry(self):
        offset = len(producer.MAGIC)
        size = struct.unpack('!Q', self.raw[offset:offset+8])[0]
        self.raw = self.raw[:offset+8+size+8+20]; self.failed()
        self.assertTrue((self.folder / 'snapshot.json').exists())

    def test_missing_final_commitment_is_not_success(self):
        self.raw = self.raw[:-len(producer.END)]; self.failed()

    def test_trailing_data_and_nonzero_process_exit_refuse(self):
        self.raw += b'unexpected'; self.failed()

    def test_process_failure_after_complete_stream_refuses(self):
        self.code = 1; self.failed()

    def test_native_receipt_mismatch_is_not_verified_backup(self):
        self.raw = self.frame(receipt_change=lambda v:v.update(sha256='0'*64)); self.failed()

    def test_wrong_snapshot_reporting_source_refuses_before_archive_write(self):
        data = deepcopy(self.f.data); data['reporting_source_files'][next(iter(data['reporting_source_files']))]='0'*64
        output = io.BytesIO(); producer._write(output, producer.MAGIC); producer._metadata(output, data)
        self.raw=output.getvalue(); self.failed(); self.assertFalse((self.folder / 'evidence.tar.gz').exists())

    def test_invented_zero_for_not_run_phase_is_refused(self):
        data = deepcopy(self.f.data); data['rows'][0]['agent_seconds'] = 0
        output = io.BytesIO(); producer._write(output, producer.MAGIC); producer._metadata(output, data)
        self.raw = output.getvalue(); self.failed()

    def test_local_mutation_after_transfer_withholds_commitment(self):
        def recheck(_):
            if self.folder.exists() and (self.folder/'snapshot.json').exists():
                (self.folder/'snapshot.json').write_bytes(b'changed')
        self.recheck.side_effect = recheck; self.failed()

    def test_full_member_verification_runs_not_only_checksum(self):
        with patch.object(archive, 'verify_archive', side_effect=ValueError('member differs')) as check:
            self.failed()
        check.assert_called_once()

    def test_archive_mutation_after_verification_withholds_commitment(self):
        def changed(_):
            if self.folder.exists() and (self.folder/'evidence.tar.gz').exists():
                with (self.folder/'evidence.tar.gz').open('ab') as stream: stream.write(b'changed')
        self.recheck.side_effect = changed; self.failed()

    def test_snapshot_becoming_nonprivate_withholds_commitment(self):
        def changed(_):
            if self.folder.exists() and (self.folder/'snapshot.json').exists():
                (self.folder/'snapshot.json').chmod(0o644)
        self.recheck.side_effect = changed; self.failed()

    def test_spawn_error_is_private_and_never_retried(self):
        self.start.side_effect = OSError('PRIVATE-KEY-SENTINEL'); self.failed()
        self.assertNotIn('PRIVATE-KEY-SENTINEL', (self.folder/'failure.json').read_text())

    def test_duplicate_json_keys_and_oversized_parser_header_refuse(self):
        raw=b'{"a":1,"a":2}'
        self.raw=producer.MAGIC+struct.pack('!Q',len(raw))+raw; self.failed()

    def test_transport_window_expiry_retains_evidence(self):
        with patch.object(operator, 'TRANSPORT_SECONDS', -1): self.failed()

    def test_source_change_before_launch_prevents_native_operation(self):
        self.recheck.side_effect=ValueError('changed')
        with self.assertRaises(ValueError): operator.backup(self.commit)
        self.start.assert_not_called(); self.assertFalse(self.folder.exists())

    def test_pinned_ssh_only_no_provider_environment_or_raw_stderr(self):
        with patch.object(operator.subprocess, 'Popen') as called:
            self.actual_start()
        self.assertEqual(called.call_args.args[0], launch._command())
        self.assertEqual(called.call_args.kwargs['env'], {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        self.assertEqual(called.call_args.kwargs['stderr'], subprocess.DEVNULL)

    def test_saved_report_callback_or_root_is_not_a_public_entry(self):
        with self.assertRaises(TypeError): operator.backup(self.commit, self.f.data)
        with self.assertRaises(TypeError): operator.backup(self.commit, root=self.root)

    def test_binary_operation_cannot_use_buffered_json_launcher(self):
        with self.assertRaises(ValueError): launch._invoke(self.commit, 'backup')

    def test_snapshot_raw_numeric_bytes_are_not_reserialised(self):
        offset = len(producer.MAGIC); size = struct.unpack('!Q', self.raw[offset:offset+8])[0]
        expected = self.raw[offset+8:offset+8+size]
        operator.backup(self.commit)
        self.assertEqual((self.folder/'snapshot.json').read_bytes(), expected)
        self.assertIn(b'7200.0', expected)


if __name__ == '__main__': unittest.main()
