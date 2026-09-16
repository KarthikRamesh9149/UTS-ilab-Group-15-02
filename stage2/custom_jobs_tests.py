import asyncio
from types import SimpleNamespace
import unittest
from custom_jobs import ContainerJobs


class HoldingBackend:
    def __init__(self):
        self.environment = self
        self.commands = []
        self.group = '1'

    async def aexecute(self, command, timeout):
        await asyncio.Event().wait()

    async def exec(self, command, timeout_sec):
        self.commands.append(command)
        return SimpleNamespace(return_code=0, stdout=self.group)


class JobTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = HoldingBackend()
        self.jobs = ContainerJobs(self.backend)

    async def asyncTearDown(self):
        tasks = [task for task, _ in self.jobs.jobs.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def test_invalid_command_or_timeout_does_not_start(self):
        for timeout in [0, -1, True, 3601, 1.5]:
            with self.assertRaises(ValueError):
                await self.jobs.start('pwd', timeout)
        for command in ['', ' ', None, '\x00']:
            with self.assertRaises(ValueError):
                await self.jobs.start(command)
        self.assertEqual(self.jobs.jobs, {})

    async def test_no_more_than_four_live_commands(self):
        for _ in range(4):
            await self.jobs.start('sleep 5')
        with self.assertRaises(ValueError):
            await self.jobs.start('fifth')
        self.assertEqual(len(self.jobs.jobs), 4)

    async def test_invalid_group_never_signalled(self):
        identifier = (await self.jobs.start('sleep 5'))['job_id']
        for group in ['1', '0', '-1', '12; touch /tmp/unwanted', '']:
            self.backend.group = group
            with self.assertRaises(RuntimeError):
                await self.jobs.interrupt(identifier)
        self.assertTrue(all(command.startswith('cat ') for command in self.backend.commands))

    async def test_unknown_handle_never_executes(self):
        with self.assertRaises(KeyError):
            self.jobs.poll('unknown')
        with self.assertRaises(KeyError):
            await self.jobs.interrupt('unknown')
        self.assertEqual(self.backend.commands, [])


if __name__ == '__main__':
    unittest.main()
