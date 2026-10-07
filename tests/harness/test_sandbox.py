"""Container backend tests using a local fake Harbor environment."""
import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from uts_harness.sandbox import HarborSandbox
from .fixtures import FakeEnvironment


class BackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = FakeEnvironment()
        self.backend = HarborSandbox(self.env, identifier='fixture')

    async def test_execute_only_calls_environment(self):
        result = await self.backend.aexecute('printf hello; false', timeout=2)
        self.assertEqual(result.output, 'ok')
        self.assertIn('printf hello; false', self.env.calls[0][0])
        self.assertIn('subprocess.Popen', self.env.calls[0][0])
        self.assertEqual(self.env.calls[0][1], 12)

    async def test_sync_bridge_from_worker(self):
        result = await asyncio.to_thread(self.backend.execute, 'pwd')
        self.assertEqual(result.exit_code, 0)

    async def test_sync_on_loop_fails_without_deadlock(self):
        with self.assertRaises(RuntimeError):
            self.backend.execute('pwd')

    async def test_bad_timeouts_rejected(self):
        for value in [True, 0, -1, float('inf'), float('nan'), '1']:
            with self.assertRaises(ValueError):
                await self.backend.aexecute('pwd', timeout=value)
        self.assertEqual(self.env.calls, [])

    async def test_output_truncation_is_explicit(self):
        self.env.output = 'x' * 65000
        result = await self.backend.aexecute('printf x')
        self.assertTrue(result.truncated)
        self.assertEqual(len(result.output), 64000)

    async def test_upload_writes_only_inside_container(self):
        result = await self.backend.aupload_files([('/tmp/a quoted file', b'abc')])
        self.assertIsNone(result[0].error)
        self.assertEqual(self.env.uploads, [])
        self.assertIn('YWJj', self.env.calls[0][0])
        self.assertIn('/tmp/a quoted file', self.env.calls[0][0])

    async def test_upload_chunks_and_empty_file(self):
        await self.backend.aupload_files([('/tmp/a', b'x' * 40000), ('/tmp/empty', b'')])
        self.assertEqual(len(self.env.calls), 4)
        self.assertTrue(all(len(command) < 23000 for command, _ in self.env.calls))

    async def test_download_does_not_open_model_path_on_host(self):
        self.env.output = json.dumps({'data': base64.b64encode(b'remote').decode()})
        self.env.capture = False
        result = await self.backend.adownload_files(['/does/not/exist/on/host'])
        self.assertEqual(result[0].content, b'remote')

    async def test_invalid_paths_and_oversize(self):
        for path in ['relative', '/a\x00b', None]:
            with self.assertRaises(ValueError):
                await self.backend.adownload_files([path])
        result = await self.backend.aupload_files([('/tmp/a', b'x' * (1024 * 1024 + 1))])
        self.assertEqual(result[0].error, 'file_size_limit')
        self.assertEqual(self.env.uploads, [])


if __name__ == '__main__':
    unittest.main()
