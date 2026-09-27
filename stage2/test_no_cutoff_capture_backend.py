"""Predetermined local fixtures only; no original task command or paid call."""
import asyncio
import base64
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
import uuid

from custom_deadline_execution import TaskDeadline
from custom_portable_backend import ContainerCaptureError
from custom_process_capture import capture_script
from no_cutoff_capture_backend import encoded_capture_script, NoCutoffHarborSandbox
from test_retry_gateway import Clock


class EncodedCaptureTests(unittest.TestCase):
    def run_capture(self, command, seconds=2, maximum=64000):
        result = subprocess.run([sys.executable, '-c', encoded_capture_script(command, seconds, maximum)],
            text=True, capture_output=True, check=True, timeout=seconds+7)
        return json.loads(result.stdout)

    def test_decoded_payload_is_exact_unchanged_capture_source(self):
        command = 'printf synthetic-private-service-name'
        script = encoded_capture_script(command, 12.5, 64000)
        encoded = script.split('b64decode(', 1)[1].split(')', 1)[0]
        import ast
        self.assertEqual(base64.b64decode(ast.literal_eval(encoded)).decode(), capture_script(command, 12.5, 64000))
        self.assertNotIn('synthetic-private-service-name', script)

    def test_literal_process_match_reproduced_only_against_owned_parent_pid(self):
        marker = 'uts_synthetic_' + uuid.uuid4().hex
        # This child examines and, only on a literal match, signals its own
        # capture parent. Never use broad pkill/killall against the local host.
        child = ('import os,signal,subprocess; p=os.getppid(); '
            "a=subprocess.check_output(['ps','-p',str(p),'-o','args='],text=True); "
            'matched=' + repr(marker) + ' in a; '
            'os.kill(p,signal.SIGTERM) if matched else None; '
            "print('matched' if matched else 'helper-not-matched')")
        command = 'exec ' + shlex.quote(sys.executable) + ' -c ' + shlex.quote(child)
        original = subprocess.run([sys.executable, '-c', capture_script(command, 2, 64000)],
            text=True, capture_output=True, timeout=9)
        self.assertEqual(original.returncode, -signal.SIGTERM)
        fixed = self.run_capture(command)
        self.assertEqual(fixed['exit_code'], 0)
        self.assertEqual(fixed['output'], 'helper-not-matched\n')

    def test_nonzero_exit_remains_a_tool_observation(self):
        self.assertEqual(self.run_capture('printf fixture; exit 7'),
            dict(output='fixture', exit_code=7, truncated=False))

    def test_unicode_quotes_and_multiline_command_are_preserved(self):
        value = 'fixture "quoted" and single\' quote café\nsecond line'
        result = self.run_capture('printf %s ' + shlex.quote(value))
        self.assertEqual(result, dict(output=value, exit_code=0, truncated=False))

    def test_signal_to_command_itself_remains_visible(self):
        result = self.run_capture('kill -TERM $$')
        self.assertEqual(result['exit_code'], 143)

    def test_official_timeout_is_not_hidden_by_encoding(self):
        before = time.monotonic()
        result = self.run_capture("trap '' TERM; while :; do sleep 1; done", seconds=.1)
        self.assertEqual(result['exit_code'], 124)
        self.assertLess(time.monotonic()-before, 4)

    def test_background_service_survives_shell_then_only_owned_pid_is_cleaned(self):
        result = self.run_capture('sleep 10 & printf "%s" "$!"')
        pid = int(result['output'])
        try:
            self.assertEqual(result['exit_code'], 0)
            self.assertTrue(result['truncated'])
            os.kill(pid, 0)
        finally:
            try: os.kill(pid, signal.SIGKILL)
            except ProcessLookupError: pass

    def test_output_limit_still_drains_and_marks_truncation(self):
        command = shlex.quote(sys.executable) + " -c 'print(\"x\" * 200000)'"
        self.assertEqual(self.run_capture(command, maximum=100),
            dict(output='x'*100, exit_code=0, truncated=True))

    def test_encoding_does_not_accept_invalid_input(self):
        for command, seconds, maximum in ((None,1,1), ('x\x00',1,1), ('x',0,1),
                                         ('x',float('inf'),1), ('x',1,True)):
            with self.assertRaises(ValueError): encoded_capture_script(command, seconds, maximum)


class EncodedBackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock()
        self.deadline = TaskDeadline(deadline_monotonic=7300,
            official_timeout_seconds=7200, monotonic=self.clock.monotonic)
        self.calls = []
        async def execute(command, timeout_sec):
            self.calls.append((command, timeout_sec))
            return SimpleNamespace(return_code=0, stdout='{"output":"fixture","exit_code":0,"truncated":false}')
        self.environment = SimpleNamespace(exec=execute)
        self.backend = NoCutoffHarborSandbox(self.environment, identifier='synthetic', deadline=self.deadline)

    async def test_only_container_rpc_gets_command_with_remaining_time(self):
        self.clock.now += 50
        result = await self.backend.aexecute('printf unique-synthetic-service')
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.calls[0][1], 7160)
        self.assertNotIn('unique-synthetic-service', self.calls[0][0])
        self.assertEqual(shlex.split(self.calls[0][0])[:2], ['python3','-c'])

    async def test_long_and_short_agent_timeouts_stay_optional_and_bounded(self):
        for value, expected in ((4000,4010),(2,12),(10000,7210)):
            await self.backend.aexecute('printf fixture', timeout=value)
            self.assertEqual(self.calls[-1][1], expected)
        self.clock.now += 7200
        before = len(self.calls)
        with self.assertRaises(TimeoutError): await self.backend.aexecute('too-late')
        self.assertEqual(len(self.calls), before)

    async def test_sync_bridge_uses_same_container_encoding(self):
        await asyncio.to_thread(self.backend.execute, 'printf unique-sync-fixture')
        self.assertEqual(self.calls[0][1], 7210)
        self.assertNotIn('unique-sync-fixture', self.calls[0][0])

    async def test_real_capture_failure_propagates_without_replay_or_raw_output(self):
        async def execute(*args, **kwargs):
            self.calls.append(args)
            return SimpleNamespace(return_code=143, stdout='private output')
        self.environment.exec = execute
        with self.assertRaises(ContainerCaptureError) as caught:
            await self.backend.aexecute('fixture')
        self.assertEqual(caught.exception.return_code, 143)
        self.assertNotIn('private', str(caught.exception))
        self.assertEqual(len(self.calls), 1)

    async def test_invalid_result_is_not_fabricated_as_success(self):
        for output in ('bad', '[]', '{}', '{"output":"x","exit_code":true,"truncated":false}'):
            async def execute(*args, **kwargs): return SimpleNamespace(return_code=0, stdout=output)
            self.environment.exec = execute
            with self.assertRaises(ContainerCaptureError): await self.backend.aexecute('fixture')

    async def test_structured_read_window_and_parallel_shell_window_remain_distinct(self):
        started, release = asyncio.Event(), asyncio.Event()
        limits = []
        async def read(backend, *args, **kwargs):
            limits.append(backend._capture_limit.get())
            started.set(); await release.wait()
        with patch('custom_backend.HarborSandbox.aread', new=read):
            task = asyncio.create_task(self.backend.aread('/tmp/synthetic'))
            await started.wait()
            self.assertEqual(self.backend._capture_limit.get(), 64000)
            release.set(); await task
        self.assertEqual(limits, [4*1024**2])


if __name__ == '__main__':
    unittest.main()
