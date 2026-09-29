"""Real synthetic89 files/tar bytes/locks; native observations remain mocked."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import no_cutoff_final_archive as archive
import no_cutoff_final_backup as backup
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import test_no_cutoff_final_archive as fixtures


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ArchiveTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.reporting = self.f.f.reporting
        for path in self.reporting.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)
        self.reporting.chmod(0o700)
        self.enterContext(patch.object(backup, '__file__', str(self.reporting / 'stage2/no_cutoff_final_backup.py')))
        self.output = io.BytesIO(); self.enterContext(patch.object(backup, '_output', return_value=self.output))
        original = report.collect
        def collect():
            value = original(); value['collected_utc'] = '2027-01-16T00:00:00+00:00'; return value
        self.collect = self.enterContext(patch.object(report, 'collect', side_effect=collect))

    def decode(self, raw=None):
        source = io.BytesIO(self.output.getvalue() if raw is None else raw)
        self.assertEqual(source.read(len(backup.MAGIC)), backup.MAGIC)
        def metadata(): return phase._loads(source.read(struct.unpack('!Q', source.read(8))[0]))
        data = metadata(); chunks = []
        while size := struct.unpack('!Q', source.read(8))[0]:
            self.assertLessEqual(size, backup.CHUNK); chunks.append(source.read(size))
        receipt = metadata(); self.assertEqual(source.read(), backup.END)
        return data, b''.join(chunks), receipt

    def write(self, name, raw=b'private log'):
        return self.f.f.f.write(name, raw)

    def test_one_actual_audit_then_locked_stream_preserves_all_absences(self):
        before = {n: (self.root / n).read_bytes() for n in self.f.data['supporting_file_sha256']}
        backup.stream(); data, raw, receipt = self.decode()
        value = archive.verify_stream(io.BytesIO(raw), data, receipt)
        self.assertEqual(value['verified_result_files'], 89); self.assertEqual(value['verified_absent_paths'], 3)
        self.assertEqual(data['aggregates']['full89']['no_verifier_result'], 3)
        self.assertIsNone(data['rows'][0]['agent_seconds']); self.assertFalse(value['paid_launch_ready'])
        self.collect.assert_called_once_with()
        self.assertFalse(self.f.f.locked); self.assertEqual(self.f.f.events[-1], 'unlock')
        self.assertEqual(before, {n: (self.root / n).read_bytes() for n in before})
        self.assertTrue((self.reporting / backup.STATE[0]).is_file())
        self.assertTrue((self.reporting / backup.STATE[1]).is_file())
        self.assertFalse((self.reporting / backup.STATE[2]).exists())

    def test_second_stream_refused_without_audit_or_new_bytes(self):
        backup.stream(); raw = self.output.getvalue()
        with self.assertRaises(ValueError): backup.stream()
        self.collect.assert_called_once_with(); self.assertEqual(self.output.getvalue(), raw)

    def test_any_retained_native_state_forbids_repetition(self):
        for name in backup.STATE:
            with self.subTest(name=name):
                path = self.reporting / name; path.write_bytes(b'{}'); path.chmod(0o600)
                with self.assertRaises(ValueError): backup.stream()
                path.unlink()
        self.collect.assert_not_called(); self.assertFalse(self.output.getvalue())

    def test_native_context_or_wrong_source_location_refuses(self):
        with patch.object(report, '_context', side_effect=ValueError('native context')):
            with self.assertRaises(ValueError): backup.stream()
        with patch.object(backup, '__file__', str(self.root / 'stage2/no_cutoff_final_backup.py')):
            with self.assertRaises(ValueError): backup.stream()
        self.collect.assert_not_called()

    def test_active_service_refuses_before_any_collector_or_intent(self):
        self.f.f.service.side_effect = ValueError('active')
        with self.assertRaises(ValueError): backup.stream()
        self.collect.assert_not_called(); self.assertFalse((self.reporting / backup.STATE[0]).exists())

    def test_persistent_stop_refuses_without_native_audit(self):
        self.write(phase.RT + 'operator-stop-request.json', b'{"automatic_resume":false}')
        with self.assertRaises(ValueError): backup.stream()
        self.collect.assert_not_called()

    def test_stream_error_retains_intent_and_type_only_failure(self):
        with patch.object(backup, '_pack', side_effect=RuntimeError('SECRET-RAW')):
            with self.assertRaises(RuntimeError): backup.stream()
        failure = json.loads((self.reporting / backup.STATE[2]).read_bytes())
        self.assertEqual(failure['error_type'], 'RuntimeError'); self.assertFalse(failure['automatic_resume'])
        self.assertNotIn('SECRET-RAW', json.dumps(failure)); self.assertFalse(self.output.getvalue().endswith(backup.END))
        with self.assertRaises(ValueError): backup.stream()

    def test_cancellation_retains_failure_and_releases_real_locks(self):
        with patch.object(backup, '_pack', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): backup.stream()
        self.assertFalse(self.f.f.locked); self.assertTrue((self.reporting / backup.STATE[2]).exists())

    def test_last_native_observation_mutation_prevents_commitment(self):
        original = backup._pack
        def packed(*args):
            value = original(*args)
            output = self.f.f.service.return_value
            def changed():
                (self.root / self.f.data['absent_paths'][0]).write_bytes(b'{}')
                return output
            self.f.f.service.side_effect = changed
            return value
        with patch.object(backup, '_pack', side_effect=packed), self.assertRaises(ValueError): backup.stream()
        self.assertFalse(self.output.getvalue().endswith(backup.END))
        self.assertTrue((self.reporting / backup.STATE[2]).exists())

    def test_final_historical_result_mutation_is_not_ignored(self):
        original = backup._pack
        def packed(*args):
            value = original(*args)
            name = next(iter(self.f.data['preserved_result_files'][str(report.BASELINE)]))
            (report.BASELINE / name).write_bytes(b'changed')
            return value
        with patch.object(backup, '_pack', side_effect=packed), self.assertRaises(ValueError): backup.stream()
        self.assertFalse(self.output.getvalue().endswith(backup.END))

    def test_caught_environment_refusal_after_stream_prevents_receipt(self):
        original = backup._pack
        def packed(*args):
            value = original(*args)
            report._context.side_effect = ValueError('latched environment refusal')
            return value
        with patch.object(backup, '_pack', side_effect=packed), self.assertRaises(ValueError): backup.stream()
        self.assertFalse(self.output.getvalue().endswith(backup.END))
        self.assertTrue((self.reporting / backup.STATE[2]).exists())

    def test_new_private_log_after_stream_is_detected(self):
        original = backup._pack
        def packed(*args):
            value = original(*args); self.write(phase.RT + 'scored-trials/' + self.f.f.ids[0] + '/extra.log'); return value
        with patch.object(backup, '_pack', side_effect=packed), self.assertRaises(ValueError): backup.stream()

    def test_private_logs_are_archived_but_never_returned_in_metadata(self):
        self.write(phase.RT + 'scored-trials/' + self.f.f.ids[0] + '/private.log', b'PRIVATE-EXCHANGE-SENTINEL')
        backup.stream(); data, raw, receipt = self.decode()
        value = archive.verify_stream(io.BytesIO(raw), data, receipt)
        self.assertNotIn('PRIVATE-EXCHANGE-SENTINEL', json.dumps(data) + json.dumps(value))
        self.assertEqual(receipt['files'], value['verified_bound_files'] + 1)

    def test_credentials_are_excluded_without_reading_or_returning_them(self):
        name = phase.RT + 'scored-trials/' + self.f.f.ids[0] + '/token'
        self.write(name, b'CREDENTIAL-SENTINEL')
        inventory = backup._inventory(self.f.data)
        self.assertNotIn(name, inventory[0]); self.assertEqual(inventory[3], 1)
        raw = io.BytesIO(); receipt = backup._pack(raw, self.f.data, inventory)
        self.assertNotIn(b'CREDENTIAL-SENTINEL', raw.getvalue()); self.assertEqual(receipt['excluded'], 1)

    def test_exclusion_cannot_drop_a_required_file(self):
        data = deepcopy(self.f.data); name = phase.RT + 'scored-trials/' + self.f.f.ids[0] + '/token'
        data['supporting_file_sha256'][name] = self.write(name)
        with self.assertRaises(ValueError): backup._inventory(data)

    def test_unsafe_symlink_fifo_or_hardlinked_log_refuses(self):
        base = self.root / phase.RT / 'scored-trials' / self.f.f.ids[0]
        path = base / 'extra.log'; path.symlink_to(base / 'result.json')
        with self.assertRaises(ValueError): backup._inventory(self.f.data)
        path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError): backup._inventory(self.f.data)
        path.unlink(); os.link(base / 'result.json', path)
        with self.assertRaises(ValueError): backup._inventory(self.f.data)

    def test_source_replacement_between_inventory_and_pack_refuses(self):
        inventory = backup._inventory(self.f.data)
        name = next(iter(inventory[0])); base, relative, _, _ = inventory[0][name]
        p = base / relative; raw = p.read_bytes(); mode = p.stat().st_mode & 0o777
        p.unlink(); p.write_bytes(raw); p.chmod(mode)
        with self.assertRaises(ValueError): backup._pack(io.BytesIO(), self.f.data, inventory)

    def test_public_permissions_and_fifo_direct_read_refuse_without_wait(self):
        name = phase.RT + 'scored-trials/' + self.f.f.ids[0] + '/extra.log'
        self.write(name); path = self.root / name; path.chmod(0o644)
        with self.assertRaises(ValueError): backup._digest(self.root, name)
        path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError): backup._digest(self.root, name)

    def test_final_marker_failure_retains_both_result_and_failure_not_success(self):
        original = backup._write
        def write(output, raw):
            if raw == backup.END: raise BrokenPipeError('private')
            return original(output, raw)
        with patch.object(backup, '_write', side_effect=write), self.assertRaises(BrokenPipeError): backup.stream()
        self.assertTrue((self.reporting / backup.STATE[1]).exists()); self.assertTrue((self.reporting / backup.STATE[2]).exists())
        self.assertFalse(self.output.getvalue().endswith(backup.END))

    def test_short_writes_are_completed_and_invalid_writes_refused(self):
        class Short(io.BytesIO):
            def write(self, raw): return super().write(raw[:3])
        output = Short(); backup._write(output, b'12345678'); self.assertEqual(output.getvalue(), b'12345678')
        with patch.object(output, 'write', return_value=0), self.assertRaises(ValueError): backup._write(output, b'x')

    def test_no_caller_root_saved_proof_or_cli(self):
        with self.assertRaises(TypeError): backup.stream(self.f.data)
        with self.assertRaises(TypeError): backup.stream(root=self.root)


if __name__ == '__main__': unittest.main()
