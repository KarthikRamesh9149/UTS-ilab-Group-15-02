"""Single-use lifecycle identity and authoritative deadline records."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from uts_harness.lifecycle import activate, deadline_for, deadline_factory
from uts_harness.private_io import durable_json, private_directory
from uts_harness.settings import SETTINGS
from .fixtures import Clock


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.clock = Clock()

    def test_activation_is_single_use_and_deadline_does_not_renew(self):
        activate(self.runtime, 'fixture-trial', 900, SETTINGS, self.clock)
        self.assertEqual(deadline_for(self.runtime, 'fixture-trial', SETTINGS, self.clock), 1000)
        self.clock.now += 100
        self.assertEqual(deadline_for(self.runtime, 'fixture-trial', SETTINGS, self.clock), 1000)
        with self.assertRaises(FileExistsError):
            activate(self.runtime, 'fixture-trial', 900, SETTINGS, self.clock)

    def test_boot_and_protocol_identity_must_match(self):
        activate(self.runtime, 'fixture-trial', 900, SETTINGS, self.clock)
        self.clock.boot_id = 'different-boot'
        with self.assertRaises(ValueError):
            deadline_for(self.runtime, 'fixture-trial', SETTINGS, self.clock)

    async def test_factory_clock_starts_at_run_not_construction(self):
        calls = []
        async def run(*args, **kwargs):
            calls.append(deadline_for(self.runtime, 'fixture-trial', SETTINGS, self.clock))
            return 'fixture-complete'
        def factory(**kwargs):
            return SimpleNamespace(run=run)
        factory.harness = 'C0-NC'
        factory.model_protocol_sha256 = SETTINGS.fingerprint()
        wrapped = deadline_factory(factory, self.root, SETTINGS, clock=self.clock)
        agent = wrapped(paths=SimpleNamespace(trial_dir=Path('fixture-trial')),
            agent_timeout_seconds=900)
        self.assertFalse((self.runtime / 'retry-lifecycle').exists())
        self.assertEqual(await agent.run('fixture'), 'fixture-complete')
        self.assertEqual(calls, [1000])
        with self.assertRaises(FileExistsError):
            await agent.run('no-replay')
        self.assertEqual(calls, [1000])


if __name__ == '__main__':
    unittest.main()
