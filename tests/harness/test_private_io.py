"""Exclusive durable records, private directory modes and symlink refusal."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from uts_harness.private_io import durable_json, private_directory
from uts_harness.lifecycle import private_read


class PrivateIOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_directory_is_owned_and_private(self):
        path = private_directory(self.root / 'records')
        info = path.lstat()
        self.assertTrue(stat.S_ISDIR(info.st_mode))
        self.assertEqual(info.st_uid, os.getuid())
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o700)
        self.assertEqual(private_directory(path), path)

    def test_insecure_and_non_directory_targets_are_rejected(self):
        exposed = self.root / 'exposed'
        exposed.mkdir(mode=0o700)
        exposed.chmod(0o755)
        with self.assertRaises(ValueError):
            private_directory(exposed)
        regular = self.root / 'file'
        regular.write_text('unchanged')
        with self.assertRaises(FileExistsError):
            private_directory(regular)
        self.assertEqual(regular.read_text(), 'unchanged')

    def test_directory_symlink_is_not_accepted(self):
        target = private_directory(self.root / 'target')
        link = self.root / 'link'
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            private_directory(link)
        self.assertEqual(list(target.iterdir()), [])

    def test_directory_owner_mismatch_is_rejected(self):
        target = private_directory(self.root / 'target')
        with patch('uts_harness.private_io.os.getuid', return_value=os.getuid() + 1):
            with self.assertRaises(ValueError):
                private_directory(target)

    def test_record_creation_is_private_exclusive_and_fsynced(self):
        target = private_directory(self.root / 'records') / 'result.json'
        with patch('uts_harness.private_io.os.fsync', wraps=os.fsync) as sync:
            durable_json(target, {'result': 'fixture', 'complete': True})
        self.assertEqual(json.loads(target.read_text()), {'result': 'fixture', 'complete': True})
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(sync.call_count, 2)
        before = target.read_bytes()
        with self.assertRaises(FileExistsError):
            durable_json(target, {'result': 'overwritten'})
        self.assertEqual(target.read_bytes(), before)

    def test_record_symlink_does_not_overwrite_target(self):
        original = self.root / 'original.json'
        original.write_text('{"preserved": true}')
        link = self.root / 'result.json'
        link.symlink_to(original)
        with self.assertRaises(FileExistsError):
            durable_json(link, {'preserved': False})
        self.assertEqual(original.read_text(), '{"preserved": true}')
        with self.assertRaises(OSError):
            private_read(link)

    def test_private_read_refuses_exposed_mode_and_nonobject(self):
        target = self.root / 'value.json'
        durable_json(target, {'fixture': True})
        self.assertEqual(private_read(target), {'fixture': True})
        target.chmod(0o644)
        with self.assertRaises(ValueError):
            private_read(target)
        target.chmod(0o600)
        target.write_text('[]')
        with self.assertRaises(ValueError):
            private_read(target)


if __name__ == '__main__':
    unittest.main()
