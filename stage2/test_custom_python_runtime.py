import hashlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import tarfile
import unittest

from custom_python_runtime import PythonBundle, PythonFallbackEnvironment, prepare_python


class BundleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'python.tar.gz'

    def bundle(self, extra=()):
        with tarfile.open(self.path, 'w:gz') as archive:
            member = tarfile.TarInfo('python/bin/python3')
            member.size, member.mode = 7, 0o755
            archive.addfile(member, io.BytesIO(b'fixture'))
            for member in extra:
                archive.addfile(member)
        return PythonBundle(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_hash_and_distribution_are_bound(self):
        bundle = self.bundle()
        self.assertEqual(bundle.validate()['unpacked_bytes'], 7)
        with self.assertRaises(ValueError):
            PythonBundle(self.path, '0' * 64).validate()

    def test_path_traversal_duplicates_and_links_are_rejected(self):
        for name, kind, target in [('../bad', tarfile.DIRTYPE, ''),
                ('python/../bad', tarfile.DIRTYPE, ''), ('/tmp/bad', tarfile.DIRTYPE, ''),
                ('python/bin/python3', tarfile.DIRTYPE, ''),
                ('python/bad', tarfile.SYMTYPE, '../../outside'),
                ('python/bad', tarfile.SYMTYPE, '/etc/passwd'),
                ('python/bad', tarfile.LNKTYPE, 'python/bin/python3'),
                ('python/bad', tarfile.FIFOTYPE, '')]:
            member = tarfile.TarInfo(name)
            member.type, member.linkname = kind, target
            with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                self.bundle([member]).validate()

    def test_internal_file_symlink_is_allowed_but_symlink_parent_is_not(self):
        member = tarfile.TarInfo('python/bin/alias')
        member.type, member.linkname = tarfile.SYMTYPE, 'python3'
        self.assertEqual(self.bundle([member]).validate()['members'], 2)
        child = tarfile.TarInfo('python/bin/alias/file')
        with self.assertRaises(ValueError):
            self.bundle([member, child]).validate()

    async def test_bootstrap_does_not_install_packages_or_replace_task_python(self):
        calls, uploads = [], []
        results = ['', '/tmp/uts-python-Fixture123\n', 'runtime-ready\n', 'backend-ready\n', 'ok']
        async def execute(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(return_code=0, stdout=results.pop(0))
        async def upload(source, target):
            uploads.append((source, target))
        env = SimpleNamespace(exec=execute, upload_file=upload)
        wrapped, proof = await prepare_python(env, self.bundle())
        self.assertEqual(proof['network_downloads'], 0)
        self.assertTrue(proof['task_python_preserved'])
        await wrapped.exec('printf ok', timeout_sec=1, cwd='/app')
        self.assertTrue(calls[-1][0].startswith('export PATH="$PATH":/tmp/uts-python-Fixture123/python/bin; '))
        self.assertEqual(calls[-1][1], dict(timeout_sec=1, cwd='/app'))
        self.assertEqual(uploads[0][1], '/tmp/uts-python-Fixture123/bundle.tar.gz')
        self.assertFalse(any('apt' in command or 'pip' in command or 'curl' in command for command, _ in calls))

    async def test_unexpected_container_path_never_receives_host_upload(self):
        async def execute(command, **kwargs):
            return SimpleNamespace(return_code=0, stdout='/somewhere/else')
        env = SimpleNamespace(exec=execute)
        with self.assertRaises(RuntimeError):
            await prepare_python(env, self.bundle())
        with self.assertRaises(ValueError):
            PythonFallbackEnvironment(env, '/usr/bin')


if __name__ == '__main__':
    unittest.main()
