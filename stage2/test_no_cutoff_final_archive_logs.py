"""Real temporary protection/hash/tar checks, never native backup evidence."""
from copy import deepcopy
import gzip
import io
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_final_archive_logs as logs
import no_cutoff_final_backup as backup
import no_cutoff_final_guard as guard
import no_cutoff_final_report as report
import test_no_cutoff_final_backup as fixtures


class LogProtectionTests(unittest.TestCase):
    def setUp(self):
        if not hasattr(os, 'listxattr'):
            self.enterContext(patch.object(os, 'listxattr', return_value=[], create=True))
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve(); self.parent.chmod(0o700)
        self.root = self.parent / 'native'; self.root.mkdir(mode=0o700)
        self.trial = 'customfinal2-c0-nc-01-synthetic'; self.trials = frozenset({self.trial})
        self.prefix = '.runtime/stage2/scored-trials/' + self.trial
        current = self.root
        for part in self.prefix.split('/'):
            current /= part; current.mkdir(mode=0o700)
        for family in ('agent', 'verifier'):
            path = current / family; path.mkdir(mode=0o700); path.chmod(0o777)
        for obj, key, value in ((guard, 'ROOT', self.root), (guard, 'OWNER', os.getuid()),
                (guard, 'GROUP', os.getgid()), (report, 'ROOT', self.root)):
            self.enterContext(patch.object(obj, key, value))

    def file(self, family='verifier', mode=0o644, name='output.log'):
        relative = self.prefix + '/' + family + '/' + name
        path = self.root / relative; path.write_bytes(b'PRIVATE-LOG-SENTINEL'); path.chmod(mode)
        return relative, path

    def check(self, name):
        return logs.protection(self.root, name, self.trials)

    def data(self):
        return dict(rows=[dict(trial_id=self.trial)], supporting_file_sha256={},
            reporting_source_files={}, directory_entries={}, absent_paths=[])

    def test_observed_modes_are_read_without_modification(self):
        for family, modes in (('agent', (0o600,)), ('verifier', (0o600, 0o644, 0o660))):
            for mode in modes:
                with self.subTest(family=family, mode=mode):
                    name, path = self.file(family, mode)
                    before = self.check(name)
                    sha, identity = backup._digest(self.root, name, log_trials=self.trials)
                    self.assertEqual(self.check(name), before)
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
                    self.assertEqual(len(sha), 64); self.assertEqual(identity, guard.identity(path.stat()))

    def test_only_registered_agent_verifier_paths_qualify(self):
        for name in (self.prefix + '/result.json', self.prefix + '/traces/a.json',
                self.prefix.replace(self.trial, 'another') + '/agent/output.log',
                self.prefix + '/verifier-other/output.log'):
            with self.subTest(name=name):
                self.assertFalse(logs.applies(name, self.trials))
                with self.assertRaises(ValueError): self.check(name)

    def test_another_root_is_refused(self):
        name, _ = self.file()
        with self.assertRaises(ValueError): logs.protection(self.parent, name, self.trials)

    def test_traversal_noncanonical_and_credential_names_refuse(self):
        for tail in ('../output', 'a//b', './output', '.env', '.env.local', 'id_rsa', 'token'):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                self.check(self.prefix + '/verifier/' + tail)

    def test_all_private_boundary_modes_remain_exact(self):
        name, _ = self.file()
        current = self.root
        paths = [current]
        for part in self.prefix.split('/'):
            current /= part; paths.append(current)
        for path in paths:
            for mode in (0o755, 0o770, 0o777):
                with self.subTest(path=path.name, mode=mode):
                    path.chmod(mode)
                    try:
                        with self.assertRaises(ValueError): self.check(name)
                    finally: path.chmod(0o700)

    def test_writable_execution_parent_refuses(self):
        name, _ = self.file(); self.parent.chmod(0o770)
        with self.assertRaises(ValueError): self.check(name)

    def test_wrong_owner_or_group_refuses(self):
        name, _ = self.file()
        for field in ('OWNER', 'GROUP'):
            with patch.object(guard, field, getattr(guard, field) + 1), self.assertRaises(ValueError): self.check(name)

    def test_access_or_default_acl_refuses(self):
        name, _ = self.file()
        for value in ('system.posix_acl_access', 'system.posix_acl_default'):
            with patch.object(os, 'listxattr', return_value=[value]), self.assertRaises(ValueError): self.check(name)

    def test_log_root_modes_are_narrow(self):
        name, path = self.file()
        for mode in (0o700, 0o777):
            path.parent.chmod(mode); self.check(name)
        for mode in (0o755, 0o775, 0o1777, 0o2777):
            path.parent.chmod(mode)
            with self.assertRaises(ValueError): self.check(name)

    def test_nested_log_directories_stay_private(self):
        nested = self.root / self.prefix / 'verifier/nested'; nested.mkdir(mode=0o700)
        name, _ = self.file(name='nested/output.log'); self.check(name)
        for mode in (0o755, 0o777):
            nested.chmod(mode)
            with self.assertRaises(ValueError): self.check(name)

    def test_agent_file_permissions_are_not_relaxed(self):
        name, _ = self.file('agent', 0o644)
        with self.assertRaises(ValueError): self.check(name)

    def test_verifier_world_write_execute_or_special_bits_refuse(self):
        for mode in (0o664, 0o666, 0o755, 0o1600, 0o2600, 0o4600):
            name, _ = self.file(mode=mode)
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.check(name)

    def test_symlink_file_and_ancestor_refuse(self):
        name, path = self.file(); path.unlink(); path.symlink_to(self.parent / 'elsewhere')
        with self.assertRaises(ValueError): self.check(name)
        path.unlink(); path.parent.rmdir(); path.parent.symlink_to(self.root / self.prefix / 'agent')
        with self.assertRaises(ValueError): self.check(name)

    def test_hardlink_and_fifo_refuse(self):
        name, path = self.file(); other = path.with_name('linked'); os.link(path, other)
        with self.assertRaises(ValueError): self.check(name)
        other.unlink(); path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError): self.check(name)

    def test_file_cannot_replace_log_root(self):
        path = self.root / self.prefix / 'agent'; path.rmdir(); path.write_bytes(b'x'); path.chmod(0o600)
        with self.assertRaises(ValueError): self.check(self.prefix + '/agent')

    def test_root_change_during_open_refuses(self):
        name, _ = self.file()
        with self.assertRaises(ValueError):
            with backup._open(self.root, name, log_trials=self.trials) as (stream, _):
                stream.read(); self.root.chmod(0o755)

    def test_file_change_during_open_refuses(self):
        name, path = self.file()
        with self.assertRaises(ValueError):
            with backup._open(self.root, name, log_trials=self.trials) as (stream, _):
                stream.read(); path.write_bytes(b'changed')

    def test_scope_omission_keeps_original_strict_reader(self):
        name, _ = self.file()
        with self.assertRaises(ValueError): backup._digest(self.root, name)

    def test_required_evidence_cannot_be_relabelled_as_logs(self):
        name, _ = self.file(); data = self.data(); data['supporting_file_sha256'][name] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Required evidence'): backup._inventory(data)
        data = self.data(); data['directory_entries'][self.prefix + '/agent'] = []
        with self.assertRaisesRegex(ValueError, 'Required evidence'): backup._inventory(data)

    def test_source_is_preserved_and_archive_members_are_private(self):
        name, path = self.file(); self.file('agent', 0o600)
        before = self.check(name); data = self.data(); inventory = backup._inventory(data)
        output = io.BytesIO(); backup._pack(output, data, inventory)
        # Remove the producer's size framing in this synthetic local stream.
        import struct
        framed = io.BytesIO(output.getvalue()); compressed = bytearray()
        while header := framed.read(8): compressed.extend(framed.read(struct.unpack('!Q', header)[0]))
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(compressed)), mode='r:') as tar:
            for member in tar:
                self.assertEqual(member.mode, 0o700 if member.isdir() else 0o600)
        self.assertEqual(before, self.check(name)); self.assertEqual(path.read_bytes(), b'PRIVATE-LOG-SENTINEL')

    def test_inventory_detects_directory_identity_change(self):
        self.file(); original = backup._digest; changed = False
        def digest(*args, **kwargs):
            nonlocal changed
            value = original(*args, **kwargs)
            if not changed:
                changed = True; (self.root / self.prefix / 'agent/new').mkdir(mode=0o700)
            return value
        with patch.object(backup, '_digest', side_effect=digest), self.assertRaises(ValueError): backup._inventory(self.data())

    def test_pack_refuses_changed_log_after_inventory(self):
        name, path = self.file(); data = self.data(); inventory = backup._inventory(data)
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError): backup._pack(io.BytesIO(), data, inventory)

    def test_contract_disclaims_historical_proof_and_permission_mutation(self):
        value = logs.contract()
        self.assertFalse(value['historical_payload_bytes_attested'])
        self.assertFalse(value['source_permissions_modified']); self.assertTrue(value['required_evidence_permissions_unchanged'])


class IntegratedLogArchiveTests(unittest.TestCase):
    def setUp(self):
        if not hasattr(os, 'listxattr'):
            self.enterContext(patch.object(os, 'listxattr', return_value=[], create=True))
        # Supply a real private parent on Linux and macOS; no host permission edit.
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        parent = Path(temporary.name).resolve(); parent.chmod(0o700)
        original = tempfile.TemporaryDirectory
        self.f = fixtures.BackupTests()
        with patch.object(tempfile, 'TemporaryDirectory', side_effect=lambda: original(dir=parent)):
            self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        for name in ('', '.runtime', '.runtime/stage2', '.runtime/stage2/scored-trials'):
            (self.root / name).chmod(0o700)
        for trial in self.f.f.f.ids:
            (self.root / '.runtime/stage2/scored-trials' / trial).chmod(0o700)
        for obj, key, value in ((guard, 'ROOT', self.root), (guard, 'OWNER', os.getuid()), (guard, 'GROUP', os.getgid())):
            self.enterContext(patch.object(obj, key, value))
        self.name = self.f.f.f.ids[0]
        self.relative = '.runtime/stage2/scored-trials/' + self.name + '/verifier'
        self.folder = self.root / self.relative; self.folder.mkdir(mode=0o700); self.folder.chmod(0o777)
        self.path = self.folder / 'private-output.log'; self.path.write_bytes(b'PRIVATE-INTEGRATION-SENTINEL'); self.path.chmod(0o660)

    def test_actual_producer_and_strict_archive_verifier_accept_protected_extra_logs(self):
        backup.stream(); data, raw, receipt = self.f.decode()
        value = backup.archive.verify_stream(io.BytesIO(raw), data, receipt)
        self.assertEqual(value['verified_result_files'], 89)
        self.assertEqual(data['archive_log_permissions'], logs.contract())
        self.assertNotIn('PRIVATE-INTEGRATION-SENTINEL', str(data) + str(value))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o660)

    def test_late_log_mutation_prevents_native_commitment(self):
        original = backup._pack
        def pack(*args):
            value = original(*args); self.path.write_bytes(b'changed'); return value
        with patch.object(backup, '_pack', side_effect=pack), self.assertRaises(ValueError): backup.stream()
        self.assertFalse(self.f.output.getvalue().endswith(backup.END))

    def test_required_trace_permissions_still_refuse(self):
        trace = next((self.root / '.runtime/stage2/scored-trials' / self.name / 'traces').iterdir())
        trace.chmod(0o644)
        with self.assertRaises(ValueError): backup.stream()

    def test_archive_schema_refuses_weakened_log_contract(self):
        data = deepcopy(self.f.f.data); data['archive_log_permissions']['required_evidence_permissions_unchanged'] = False
        with self.assertRaises(ValueError): backup.archive.validate_snapshot(data, self.f.f.anchors)
