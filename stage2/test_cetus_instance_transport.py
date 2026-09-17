import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from cetus_instance_transport import (CommandResult, InstanceTransport, MAX_BYTES,
                                      READ_FILE, WRITE_FILE, container_path, run_process)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def transport(self, runner):
        with patch.dict(os.environ, {'PBS_JOBID': '123.hpc-head01'}):
            return InstanceTransport('uts-harbor-123-fixture', runner=runner)

    async def test_exec_quotes_cwd_and_keeps_environment_inside_container(self):
        runner = AsyncMock(return_value=CommandResult(0, b'ok', b''))
        transport = self.transport(runner)
        result = await transport.exec('printf ok', cwd='/tmp/a; false', env={'FAKE_KEY': 'x; y'})
        argv = runner.call_args.args[0]
        self.assertEqual(argv[:4], ['apptainer', 'exec', '--cleanenv', 'instance://uts-harbor-123-fixture'])
        self.assertIn('FAKE_KEY=x; y', argv)
        self.assertEqual(argv[-1], "cd -- '/tmp/a; false' && printf ok")
        self.assertEqual(result.stdout, b'ok')

    async def test_no_user_fallback(self):
        runner = AsyncMock()
        with self.assertRaises(NotImplementedError):
            await self.transport(runner).exec('true', user='nobody')
        runner.assert_not_called()

    async def test_interruption_poison_prevents_reuse(self):
        for error in (TimeoutError(), asyncio.CancelledError(), ValueError('overflow')):
            runner = AsyncMock(side_effect=error)
            transport = self.transport(runner)
            with self.assertRaises(type(error)):
                await transport.exec('sleep 5')
            with self.assertRaises(RuntimeError):
                await transport.exec('true')
            self.assertEqual(runner.call_count, 1)

    async def test_fixture_file_scripts_roundtrip_binary_without_apptainer(self):
        # Exercise the exact transfer scripts locally on trusted temporary paths.
        # This does not simulate or claim container isolation.
        with tempfile.TemporaryDirectory() as root:
            source, remote, output = [Path(root) / name for name in ('source', 'remote', 'output')]
            source.write_bytes(b'\x00\xffhello\n')
            async def fixture_runner(argv, **kwargs):
                self.assertEqual(argv[4], 'python3')
                return await run_process([sys.executable] + argv[5:], **kwargs)
            transport = self.transport(fixture_runner)
            await transport.upload_file(source, str(remote))
            await transport.download_file(str(remote), output)
            self.assertEqual(output.read_bytes(), source.read_bytes())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(remote.stat().st_mode & 0o777, 0o600)

    async def test_download_rejects_symlink_and_existing_file(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / 'existing'
            file.write_bytes(b'preserve')
            link = Path(root) / 'link'
            link.symlink_to(file)
            runner = AsyncMock()
            for target in (file, link):
                with self.assertRaises(ValueError):
                    await self.transport(runner).download_file('/tmp/result', target)
            runner.assert_not_called()
            self.assertEqual(file.read_bytes(), b'preserve')

    async def test_failed_download_creates_no_output(self):
        runner = AsyncMock(return_value=CommandResult(1, b'partial', b'error'))
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'result'
            with self.assertRaises(RuntimeError):
                await self.transport(runner).download_file('/tmp/file', target)
            self.assertFalse(target.exists())

    async def test_remote_reader_rejects_symlink_and_fifo(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / 'file'
            file.write_bytes(b'fixture')
            link, fifo = Path(root) / 'link', Path(root) / 'fifo'
            link.symlink_to(file)
            os.mkfifo(fifo)
            for path in (link, fifo):
                result = await run_process([sys.executable, '-c', READ_FILE, str(path), str(MAX_BYTES)])
                self.assertNotEqual(result.return_code, 0)

    async def test_process_timeout_and_output_bound(self):
        with self.assertRaises(TimeoutError):
            await run_process([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.1)
        with self.assertRaises(ValueError):
            await asyncio.wait_for(run_process([sys.executable, '-c', 'print("x" * 1000000)'], max_bytes=100), 5)

    async def test_controller_secrets_not_inherited_by_process(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'synthetic', 'APPTAINER_BIND': '/shared'}):
            result = await run_process([sys.executable, '-c',
                'import os; assert "OPENROUTER_API_KEY" not in os.environ; assert "APPTAINER_BIND" not in os.environ'])
        self.assertEqual(result.return_code, 0)

    def test_instance_requires_current_pbs_job(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError): InstanceTransport('uts-harbor-123')
        with patch.dict(os.environ, {'PBS_JOBID': '123.hpc-head01'}):
            for name in ('uts-harbor-124', '--help', 'arbitrary', 'uts-harbor-123;false'):
                with self.assertRaises(ValueError): InstanceTransport(name)

    def test_invalid_container_paths(self):
        for path in ('relative', '/tmp/../shared', '/', '/tmp/a\x00b'):
            with self.assertRaises(ValueError): container_path(path)


if __name__ == '__main__':
    unittest.main()
