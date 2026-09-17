import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from cetus_directory_transfer import pack, unpack
from cetus_instance_transport import InstanceTransport, MAX_BYTES, run_process


class DirectoryTests(unittest.IsolatedAsyncioTestCase):
    def tree(self, root):
        root.mkdir()
        (root / 'empty').mkdir()
        (root / 'nested').mkdir()
        (root / 'nested' / 'binary').write_bytes(b'\x00\xff\n')
        (root / 'test.sh').write_text('#!/bin/sh\nexit 0\n')
        (root / 'test.sh').chmod(0o755)

    async def test_actual_scripts_roundtrip_without_container(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            self.tree(root / 'source')
            async def runner(argv, **kwargs):
                return await run_process([sys.executable] + argv[5:], **kwargs)
            with patch.dict(os.environ, {'PBS_JOBID': '123.hpc-head01'}):
                transport = InstanceTransport('uts-harbor-123', runner=runner)
            await transport.upload_dir(root / 'source', str(root / 'remote'))
            await transport.download_dir(str(root / 'remote'), root / 'output')
            self.assertEqual((root / 'output/nested/binary').read_bytes(), b'\x00\xff\n')
            self.assertTrue((root / 'output/empty').is_dir())
            self.assertEqual((root / 'remote/test.sh').stat().st_mode & 0o777, 0o755)
            self.assertEqual((root / 'output/test.sh').stat().st_mode & 0o777, 0o700)

    def archive(self, specs):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w') as archive:
            for name, kind in specs:
                entry = tarfile.TarInfo(name)
                entry.type = kind
                entry.linkname = '/outside'
                archive.addfile(entry)
        return output.getvalue()

    def test_unsafe_archive_rejected_before_writes(self):
        cases = [[('../outside', tarfile.REGTYPE)], [('/absolute', tarfile.REGTYPE)],
                 [('link', tarfile.SYMTYPE)], [('hard', tarfile.LNKTYPE)],
                 [('device', tarfile.CHRTYPE)], [('fifo', tarfile.FIFOTYPE)],
                 [('same', tarfile.REGTYPE), ('same', tarfile.REGTYPE)],
                 [('parent', tarfile.REGTYPE), ('parent/file', tarfile.REGTYPE)],
                 [('.', tarfile.DIRTYPE)]]
        with tempfile.TemporaryDirectory() as base:
            destination = Path(base) / 'out'
            for specs in cases:
                with self.subTest(specs=specs), self.assertRaises(ValueError):
                    unpack(self.archive(specs), destination, MAX_BYTES)
                self.assertFalse(destination.exists())

    def test_symlink_source_rejected(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            self.tree(root / 'source')
            (root / 'source/link').symlink_to(root / 'source/test.sh')
            with self.assertRaises(ValueError): pack(root / 'source', MAX_BYTES)

    def test_existing_destination_preserved(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            self.tree(root / 'source')
            self.tree(root / 'output')
            data = pack(root / 'source', MAX_BYTES)
            with self.assertRaises(ValueError): unpack(data, root / 'output', MAX_BYTES)
            self.assertEqual((root / 'output/nested/binary').read_bytes(), b'\x00\xff\n')

    def test_size_and_entry_limits(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            self.tree(root / 'source')
            with self.assertRaises(ValueError): pack(root / 'source', 100)
            with patch('cetus_directory_transfer.MAX_ENTRIES', 1):
                with self.assertRaises(ValueError): pack(root / 'source', MAX_BYTES)
                with self.assertRaises(ValueError):
                    unpack(self.archive([('a', tarfile.REGTYPE), ('b', tarfile.REGTYPE)]), root / 'out', MAX_BYTES)
            with self.assertRaises(ValueError): unpack(b'x' * 101, root / 'out', 100)

    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            (root / 'real').mkdir()
            (root / 'link').symlink_to(root / 'real')
            with self.assertRaises(ValueError):
                unpack(self.archive([('a', tarfile.REGTYPE)]), root / 'link', MAX_BYTES)
            self.assertEqual(list((root / 'real').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
