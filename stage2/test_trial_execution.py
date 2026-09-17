import asyncio
from contextlib import contextmanager
from types import SimpleNamespace as NS
import unittest
import tempfile
from local_trace import PhaseRecorder, TraceSpool
from local_langfuse import payload
from trial_execution import execute_phases


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, *, setup_error=False, agent_error=False, revoke_error=False,
                       verifier_error=False, cleanup_error=False, timeout=False, reward=1,
                       clear_timeout=False, phase_observer=None):
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
            paths=None, revoke_model=revoke, setup_timeout_seconds=1, verifier_factory=Verifier,
            phase_observer=phase_observer)
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

    def recorder(self, directory):
        return PhaseRecorder(TraceSpool(directory), trial_id='baseline-openhands-r0-fixture',
                             task_id='fixture', harness='openhands', protocol_sha256='a' * 64)

    async def test_real_lifecycle_writes_exportable_phase_spans(self):
        with tempfile.TemporaryDirectory() as directory:
            observer = self.recorder(directory)
            result, events = await self.run_case(phase_observer=observer, reward=0)
            traces = observer.spool.events()
            self.assertEqual({t['kind'] for t in traces}, {'trial', 'setup', 'agent', 'verifier', 'cleanup'})
            self.assertEqual([t['reward'] for t in traces if t['kind'] == 'verifier'], [0])
            self.assertEqual(len(payload(traces)['resourceSpans'][0]['scopeSpans'][0]['spans']), 5)
            self.assertNotIn('trace_errors', result)
            self.assertLess(events.index('revoke'), events.index('verify'))
            self.assertEqual(events[-1], 'destroy')
            with self.assertRaises(ValueError):
                self.recorder(directory)

    async def test_observer_failure_preserves_score_and_actions(self):
        def broken(**kwargs):
            raise OSError('synthetic disk error')
        plain, plain_events = await self.run_case(reward=0)
        observed, events = await self.run_case(reward=0, phase_observer=broken)
        self.assertEqual(events, plain_events)
        for key in ('status', 'agent_error_type', 'verifier_result', 'cleanup_errors', 'model_revoked'):
            self.assertEqual(observed[key], plain[key])
        self.assertEqual(len(observed['trace_errors']), 5)
        self.assertTrue(all('synthetic disk error' not in e for e in observed['trace_errors']))

    async def test_agent_timeout_and_setup_error_are_distinguished(self):
        for kwargs, phase, status in [({'timeout': True}, 'agent', 'timeout'),
                                      ({'setup_error': True}, 'setup', 'error')]:
            with tempfile.TemporaryDirectory() as directory:
                observer = self.recorder(directory)
                await self.run_case(**kwargs, phase_observer=observer)
                traces = observer.spool.events()
                self.assertEqual(next(t['status'] for t in traces if t['kind'] == phase), status)
                if phase == 'setup':
                    self.assertFalse(any(t['kind'] == 'verifier' for t in traces))
                payload(traces)

    async def test_cleanup_error_is_not_successful_trial_span(self):
        with tempfile.TemporaryDirectory() as directory:
            observer = self.recorder(directory)
            result, events = await self.run_case(cleanup_error=True, phase_observer=observer)
            traces = observer.spool.events()
            self.assertEqual(result['status'], 'cleanup_failed')
            self.assertEqual(next(t['status'] for t in traces if t['kind'] == 'trial'), 'error')
            self.assertEqual(next(t['reward'] for t in traces if t['kind'] == 'verifier'), 1)
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

    async def test_cancellation_records_interrupted_root(self):
        started = asyncio.Event()
        class Environment:
            @contextmanager
            def with_default_user(self, user): yield
            async def stop(self, delete): pass
        class Agent:
            async def setup(self, env): pass
            async def run(self, *args):
                started.set()
                await asyncio.Event().wait()
        async def revoke(): pass
        task = NS(instruction='fixture', config=NS(agent=NS(timeout_sec=10, user=None),
            verifier=NS(timeout_sec=10, user=None)))
        with tempfile.TemporaryDirectory() as directory:
            observer = self.recorder(directory)
            running = asyncio.create_task(execute_phases(agent=Agent(), environment=Environment(),
                task=task, paths=None, revoke_model=revoke, setup_timeout_seconds=1, phase_observer=observer))
            await started.wait()
            running.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await running
            traces = observer.spool.events()
            self.assertEqual(next(t['status'] for t in traces if t['kind'] == 'trial'), 'interrupted')
            self.assertEqual(next(t['status'] for t in traces if t['kind'] == 'agent'), 'interrupted')
            self.assertEqual(next(t['status'] for t in traces if t['kind'] == 'cleanup'), 'ok')
            payload(traces)
