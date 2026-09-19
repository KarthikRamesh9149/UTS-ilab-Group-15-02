from contextlib import contextmanager
from types import SimpleNamespace
import unittest
import subprocess

from task_preparation import COMMAND, SOURCE_REPAIR, SNAPSHOT, refresh_package_metadata


class PreparationTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, code=0, stdout=''):
        calls = []
        class Environment:
            @contextmanager
            def with_default_user(self, user):
                calls.append(('user', user))
                yield
            async def exec(self, command, timeout_sec):
                calls.append((command, timeout_sec))
                return SimpleNamespace(return_code=code, stdout=stdout)
        result = await refresh_package_metadata(Environment())
        return result, calls

    async def test_index_only_root_and_bounded(self):
        result, calls = await self.invoke()
        self.assertEqual(result['status'], 'refreshed')
        self.assertFalse(result['packages_installed'])
        self.assertEqual(calls, [('user', 'root'), (COMMAND, 180)])
        self.assertNotIn(' install ', COMMAND)
        self.assertNotIn(' upgrade', COMMAND)
        self.assertNotIn('/tests', COMMAND)

    async def test_non_debian_skips(self):
        result, _ = await self.invoke(stdout='UTS_PACKAGE_METADATA_NOT_APPLICABLE\n')
        self.assertEqual(result['status'], 'not_applicable')

    async def test_refresh_failure_explicit(self):
        with self.assertRaisesRegex(RuntimeError, 'before agent'):
            await self.invoke(code=100)

    def test_repository_repair_is_exact_idempotent_and_keeps_signatures(self):
        unrelated = 'deb https://deb.debian.org/debian bookworm main\n'
        for options in ['', '[arch=amd64 signed-by=/usr/share/keyrings/debian.gpg] ',
                        '[check-valid-until=yes arch=amd64] ']:
            original = 'deb ' + options + 'http://deb.debian.org/debian-security bullseye-security main contrib\n'
            value = subprocess.check_output(['sed', '-E', SOURCE_REPAIR], input=original + unrelated, text=True)
            self.assertIn(SNAPSHOT + ' bullseye-security main contrib', value)
            self.assertIn('check-valid-until=no', value)
            self.assertIn(unrelated, value)
            if 'signed-by' in original: self.assertIn('signed-by=/usr/share/keyrings/debian.gpg', value)
            self.assertNotIn('trusted=yes', value)
            self.assertEqual(value, subprocess.check_output(['sed', '-E', SOURCE_REPAIR], input=value, text=True))

    def test_other_suite_or_host_and_comments_unchanged(self):
        for line in ['# deb http://deb.debian.org/debian-security bullseye-security main',
                     'deb http://deb.debian.org/debian-security bookworm-security main',
                     'deb http://other.example/debian-security bullseye-security main']:
            value = subprocess.check_output(['sed', '-E', SOURCE_REPAIR], input=line + '\n', text=True)
            self.assertEqual(value, line + '\n')
