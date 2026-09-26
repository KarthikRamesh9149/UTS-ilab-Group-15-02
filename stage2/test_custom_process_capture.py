"""Real local subprocesses with synthetic commands only; no model calls."""
import asyncio
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from custom_portable_backend import ContainerCaptureError, PortableHarborSandbox
from custom_process_capture import capture_script


class CaptureTests(unittest.TestCase):
    def run_capture(self, command, seconds=2, maximum=64000):
        result = subprocess.run([sys.executable, '-c', capture_script(command, seconds, maximum)],
            text=True, capture_output=True, check=True, timeout=seconds + 7)
        return json.loads(result.stdout)

    def test_output_and_nonzero_exit_are_tool_observations(self):
        self.assertEqual(self.run_capture('printf marker; exit 7'),
            dict(output='marker', exit_code=7, truncated=False))

    def test_large_output_is_drained_but_bounded(self):
        command = shlex.quote(sys.executable) + " -c 'print(\"x\" * 200000)'"
        result = self.run_capture(command, maximum=100)
        self.assertEqual(result, dict(output='x' * 100, exit_code=0, truncated=True))

    def test_foreground_deadline_kills_its_group_and_returns_124(self):
        start = time.monotonic()
        result = self.run_capture("trap '' TERM; while :; do sleep 1; done", seconds=.1)
        self.assertEqual(result['exit_code'], 124)
        self.assertLess(time.monotonic() - start, 4)

    def test_daemon_inheriting_stdout_does_not_hang_finished_shell(self):
        start = time.monotonic()
        result = self.run_capture('sleep 10 & printf "%s" "$!"')
        pid = int(result['output'])
        try:
            self.assertEqual(result['exit_code'], 0)
            self.assertTrue(result['truncated'])
            self.assertLess(time.monotonic() - start, 1.5)
            os.kill(pid, 0)  # The background service was not killed by capture.
        finally:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_pipe_closed_before_process_exit_still_enforces_deadline(self):
        result = self.run_capture('exec 1>&- 2>&-; sleep 5', seconds=.1)
        self.assertEqual(result['exit_code'], 124)

    def test_invalid_inputs_never_execute(self):
        for seconds in (None, True, 0, -1, float('nan'), float('inf'), '1'):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                capture_script('false', seconds, 100)
        for command in (None, 'bad\x00command'):
            with self.assertRaises(ValueError):
                capture_script(command, 1, 100)


class PortableBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_read_budget_does_not_leak_into_parallel_shell_calls(self):
        limits = []
        started, release = asyncio.Event(), asyncio.Event()
        async def read(backend, *args, **kwargs):
            limits.append(backend._capture_limit.get())
            started.set()
            await release.wait()
        backend = PortableHarborSandbox(SimpleNamespace(), identifier='synthetic')
        with patch('custom_backend.HarborSandbox.aread', new=read):
            reading = asyncio.create_task(backend.aread('/tmp/synthetic'))
            await started.wait()
            self.assertEqual(backend._capture_limit.get(), 64000)
            release.set()
            await reading
        self.assertEqual(limits, [4 * 1024**2])
        self.assertEqual(backend._capture_limit.get(), 64000)

    async def test_execution_stays_on_harbor_and_transport_errors_stay_errors(self):
        calls = []
        async def execute(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(return_code=124, stdout='private output must not escape')
        backend = PortableHarborSandbox(SimpleNamespace(exec=execute), identifier='synthetic')
        with self.assertRaises(ContainerCaptureError) as caught:
            await backend.aexecute('synthetic-command', timeout=2)
        self.assertEqual(caught.exception.reason, 'helper_exit')
        self.assertEqual(caught.exception.return_code, 124)
        self.assertNotIn('private', str(caught.exception))
        self.assertEqual(calls[0][1]['timeout_sec'], 12)

    async def test_malformed_capture_is_not_claimed_success(self):
        for output in ('bad', '[]', '{}', '{"output": "x", "exit_code": true, "truncated": false}'):
            async def execute(*args, **kwargs):
                return SimpleNamespace(return_code=0, stdout=output)
            backend = PortableHarborSandbox(SimpleNamespace(exec=execute), identifier='synthetic')
            with self.assertRaises(ContainerCaptureError):
                await backend.aexecute('synthetic')


if __name__ == '__main__':
    unittest.main()
