import asyncio
from contextlib import contextmanager
from types import SimpleNamespace as NS
import unittest
from trial_execution import execute_phases


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, *, setup_error=False, agent_error=False, revoke_error=False,
                       verifier_error=False, cleanup_error=False, timeout=False, reward=1,
                       clear_timeout=False):
        events = []
        class Environment:
            @contextmanager
            def with_default_user(self, user):
                events.append('user:' + user)
                yield
            async def empty_dirs(self, paths, chmod):
                events.append('clear-verifier')
                if clear_timeout: await asyncio.sleep(1)
            async def stop(self, delete): events.append('destroy')
        class Agent:
            async def setup(self, env):
                events.append('setup')
                if setup_error: raise RuntimeError('synthetic')
            async def run(self, instruction, env, context):
                events.append('agent')
                if timeout: await asyncio.sleep(1)
                if agent_error: raise RuntimeError('synthetic')
            async def cleanup_after_verification(self):
                events.append('jobs-cleanup')
                if cleanup_error: raise RuntimeError('synthetic')
        class Verifier:
            def __init__(self, *args): events.append('verifier-created')
            async def verify(self):
                events.append('verify')
                if verifier_error: raise RuntimeError('synthetic')
                return NS(model_dump=lambda **kwargs: {'rewards': {'reward': reward}})
        async def revoke():
            events.append('revoke')
            if revoke_error: raise RuntimeError('synthetic')
        task = NS(instruction='synthetic', config=NS(agent=NS(timeout_sec=.01 if timeout else 1, user='agent-user'),
                                                    verifier=NS(timeout_sec=.01 if clear_timeout else 1, user='verifier-user')))
        result = await execute_phases(agent=Agent(), environment=Environment(), task=task,
            paths=None, revoke_model=revoke, setup_timeout_seconds=1, verifier_factory=Verifier)
        return result, events

    async def test_revoke_before_verification_cleanup_after(self):
        result, events = await self.run_case()
        self.assertEqual(result['status'], 'verified')
        self.assertLess(events.index('revoke'), events.index('clear-verifier'))
        self.assertLess(events.index('revoke'), events.index('verifier-created'))
        self.assertLess(events.index('verify'), events.index('jobs-cleanup'))
        self.assertEqual(events[-1], 'destroy')
        self.assertIn('user:verifier-user', events)

    async def test_agent_failure_still_gets_unchanged_verifier(self):
        result, events = await self.run_case(agent_error=True, reward=0)
        self.assertEqual(result['agent_error_type'], 'RuntimeError')
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
        self.assertEqual(events.count('agent'), 1)

    async def test_timeout_is_not_replayed_or_discarded(self):
        result, events = await self.run_case(timeout=True)
        self.assertEqual(result['agent_error_type'], 'TimeoutError')
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(events.count('agent'), 1)

    async def test_setup_failure_skips_verifier_but_cleans_up(self):
        result, events = await self.run_case(setup_error=True)
        self.assertEqual(result['status'], 'setup_failed')
        self.assertNotIn('verify', events)
        self.assertIn('revoke', events)
        self.assertEqual(events[-1], 'destroy')

    async def test_verifier_preparation_is_inside_phase_timeout(self):
        result, events = await self.run_case(clear_timeout=True)
        self.assertEqual(result['status'], 'verifier_failed')
        self.assertEqual(result['verifier_error_type'], 'TimeoutError')
        self.assertNotIn('verifier-created', events)
        self.assertEqual(events[-1], 'destroy')

    async def test_revocation_failure_never_exposes_tests(self):
        result, events = await self.run_case(revoke_error=True)
        self.assertNotIn('verifier-created', events)
        self.assertNotIn('clear-verifier', events)
        self.assertEqual(events[-1], 'destroy')
        self.assertEqual(result['status'], 'cleanup_failed')

    async def test_verifier_failure_and_cleanup_failure_keep_evidence(self):
        result, events = await self.run_case(verifier_error=True, cleanup_error=True)
        self.assertEqual(result['verifier_error_type'], 'RuntimeError')
        self.assertEqual(result['cleanup_errors'], ['agent:RuntimeError'])
        self.assertEqual(events[-1], 'destroy')

    async def test_cancellation_still_revokes_and_destroys(self):
        events, started = [], asyncio.Event()
        class Environment:
            @contextmanager
            def with_default_user(self, user): yield
            async def stop(self, delete): events.append('destroy')
        class Agent:
            async def setup(self, env): pass
            async def run(self, *args):
                started.set()
                await asyncio.Event().wait()
            async def cleanup_after_verification(self): events.append('cleanup')
        async def revoke(): events.append('revoke')
        task = NS(instruction='fixture', config=NS(agent=NS(timeout_sec=10, user=None),
            verifier=NS(timeout_sec=10, user=None)))
        running = asyncio.create_task(execute_phases(agent=Agent(), environment=Environment(),
            task=task, paths=None, revoke_model=revoke, setup_timeout_seconds=1))
        await started.wait()
        running.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await running
        self.assertEqual(events, ['revoke', 'cleanup', 'destroy'])
