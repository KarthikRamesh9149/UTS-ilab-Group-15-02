"""Real local scopes/files with mocked native execution, not benchmark evidence."""
import asyncio
from contextlib import ExitStack
import json
import os
import signal
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

import matched_repeat_policy as policy
import matched_repeat_session as session
import matched_repeat_study as study
import run_matched_repeat as runner
import test_matched_repeat_study as fixtures
from retry_runtime import Cooldown
from run_credit_only import hold


class Clock:
    boot_id = 'synthetic-local-boot'
    def __init__(self): self.now = 100.
    def monotonic(self): return self.now
    def wall(self): return self.now + 100000.


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f = fixtures.StudyFixture('runTest'); self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.q = self.f.q; self.root = self.f.root; self.rt = self.f.rt
        self.clock = Clock(); self.enterContext(patch.object(runner, 'Clock', return_value=self.clock))
        self.docker = self.enterContext(patch.object(runner, 'docker', return_value=''))
        self.run_trial = self.enterContext(patch.object(runner, 'run_trial', new_callable=AsyncMock))
        self.run_trial.side_effect = self.trial
        self.ids = []; self.rewards = {}; self.after = None; self.factories = []
        self.task = None

    def read(self, name): return json.loads((self.rt / name).read_bytes())

    async def trial(self, **kwargs):
        self.assertTrue(self.q.locked)
        self.assertIs(asyncio.current_task(), self.task)
        self.assertEqual(kwargs['accounting_mode'], 'provider-credit-only')
        self.assertEqual(kwargs['matched_repeat'], policy.EXPERIMENT)
        self.assertEqual(kwargs['stage'], 'final'); self.assertEqual(kwargs['setup_timeout_seconds'], 900)
        self.assertEqual(kwargs['model_settings'], policy.SETTINGS)
        index = len(self.ids); cell = self.f.cells[index]
        self.assertEqual((kwargs['trial_id'], kwargs['task_id']), (cell['trial_id'], cell['task_id']))
        self.assertTrue((self.rt / runner.INTENT).exists())
        for directory in (self.rt, self.root / 'original-ancestor', self.root / 'active-final-ancestor'):
            with ExitStack() as contender, self.assertRaises(BlockingIOError): hold(contender, directory, 'matrix.lock')
        factory = kwargs['agent_factory']; self.factories.append(factory)
        study.admit_trial(**self.f.args(factory, index))
        if index == 0:
            # Construct the actual original baseline with a dummy key, never
            # setup/run or any provider request. Native phases remain mocked.
            path = self.f.partial(index)
            agent = factory(paths=NS(trial_dir=path, agent_dir=path / 'agent'),
                host_api_base='http://127.0.0.1:1/v1', container_api_base='http://127.0.0.1:1/v1',
                trial_token='synthetic-not-a-provider-key', agent_timeout_seconds=180.,
                completion_wait_seconds=240.)
            self.assertEqual(agent._max_episodes, 1000000)
        self.ids.append(cell['trial_id'])
        self.f.result(self.read(policy.REGISTRATION_FILE), index, self.rewards.get(index, 0.))
        if self.after is not None: await self.after(index)
        return {'ignored': 'return values are not retained evidence'}

    async def dispatch(self, active):
        self.task = asyncio.current_task()
        return await runner.run(active)

    async def test_saved_empty_closed_or_description_session_never_dispatches(self):
        for value in (None, {}, session._Session(), {'paid_launch_ready': True}):
            with self.assertRaises(ValueError): await self.dispatch(value)
        with self.q.open() as active:
            with self.assertRaises(ValueError): await self.dispatch(session.describe(active))
        with self.assertRaises(ValueError): await self.dispatch(active)
        self.run_trial.assert_not_awaited(); self.docker.assert_not_called()
        self.assertFalse((self.rt / runner.INTENT).exists())

    async def test_full_fixed89_retains_zeros_missing_unknowns_and_separate_splits(self):
        self.rewards = {0: 1., 19: None, 20: 1., 88: None}
        with self.q.open() as active: result = await self.dispatch(active)
        self.assertEqual(self.ids, [cell['trial_id'] for cell in self.f.cells])
        self.assertEqual((result['completed'], result['passes'], result['failures'],
            result['missing_verifier_results']), (89, 2, 85, 2))
        self.assertEqual(result['development20'], dict(intended=20, completed=20, passes=1,
            failures=18, missing_verifier_results=1))
        self.assertEqual(result['remaining69'], dict(intended=69, completed=69, passes=1,
            failures=67, missing_verifier_results=1))
        self.assertEqual(result['status'], 'complete'); self.assertFalse(result['completed_audit_verified'])
        self.assertFalse(result['paid_launch_ready']); self.assertFalse(result['off_server_backup_verified'])
        self.assertEqual(len(result['retained_files']), 178)
        self.assertEqual(self.read(runner.RESULT), result)
        self.assertTrue(all(factory is self.factories[0] for factory in self.factories))
        for name in (runner.INTENT, runner.RESULT):
            self.assertEqual((self.rt / name).stat().st_mode & 0o777, 0o600)
        for name in self.ids:
            bill = self.read('scored-trials/' + name + '/result.json')['billing']
            self.assertIsNone(bill['charged_usd']); self.assertEqual(bill['requests'], 105)
        self.q.auth.assert_called_once(); self.q.old_auth.assert_called_once(); self.q.lock.assert_called_once()
        self.q.process.assert_not_called(); self.assertEqual(self.docker.call_count, 6)
        self.assertIsNone(study._CURRENT.get())

    async def test_all89_failure_results_do_not_create_score_floor_or_retry(self):
        with self.q.open() as active: result = await self.dispatch(active)
        self.assertEqual((result['completed'], result['passes'], result['failures']), (89, 0, 89))
        self.assertEqual(len(set(self.ids)), 89)

    async def test_exception_with_actual_clean_retained_outcome_advances_without_replay(self):
        async def after(index):
            if index == 0: raise RuntimeError('private synthetic text must not be copied')
        self.after = after; self.rewards[0] = None
        with self.q.open() as active: result = await self.dispatch(active)
        self.assertEqual(result['completed'], 89); self.assertEqual(result['missing_verifier_results'], 1)
        self.assertEqual(result['retained_exception_types'], {self.ids[0]: 'RuntimeError'})
        self.assertNotIn('private synthetic', (self.rt / runner.RESULT).read_text())

    async def test_exception_without_result_is_terminal_and_same_session_cannot_retry(self):
        self.run_trial.side_effect = RuntimeError('not a retained result')
        with self.q.open() as active:
            with self.assertRaises(ValueError): await self.dispatch(active)
            with self.assertRaisesRegex(ValueError, 'fresh authenticated'): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1)
        failure = self.read(runner.FAILURE)
        self.assertFalse(failure['automatic_resume']); self.assertEqual(failure['previously_checked_completed'], 0)
        self.assertFalse((self.rt / runner.RESULT).exists()); self.assertIsNone(study._CURRENT.get())

    async def test_partial_attempt_is_not_replayed_or_counted_complete(self):
        async def partial(**kwargs):
            study.admit_trial(**self.f.args(kwargs['agent_factory']))
            self.f.partial(); raise RuntimeError('synthetic interrupted task')
        self.run_trial.side_effect = partial
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'durably retained'): await self.dispatch(active)
        self.assertEqual(self.read(runner.FAILURE)['previously_checked_completed'], 0)
        self.assertEqual(self.run_trial.await_count, 1)

    async def test_fake_return_or_saved_result_without_real_admission_cannot_advance(self):
        async def fake(**kwargs):
            self.f.result(self.read(policy.REGISTRATION_FILE))
            return {'status': 'complete', 'paid_launch_ready': True}
        self.run_trial.side_effect = fake
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'real scored admission'): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1)

    async def test_old_completed_prefix_cannot_automatically_resume(self):
        with self.q.open() as active:
            block = study.register(active); self.f.result(block)
            with self.assertRaisesRegex(ValueError, 'dispatched prefix'): await self.dispatch(active)
        self.run_trial.assert_not_awaited(); self.assertFalse((self.rt / runner.INTENT).exists())

    async def test_retained_intent_or_terminal_metadata_blocks_even_a_new_session(self):
        for name in (runner.INTENT, runner.RESULT, runner.FAILURE):
            self.q.private(name, {'synthetic': True})
            with self.q.open() as active:
                with self.assertRaisesRegex(ValueError, 'automatic restart'): await self.dispatch(active)
            (self.rt / name).unlink()  # Remove only this test fixture.
        self.run_trial.assert_not_awaited()

    async def test_dangling_intent_symlink_blocks_without_following_or_overwriting(self):
        path = self.rt / runner.INTENT; path.symlink_to(self.rt / 'absent')
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'automatic restart'): await self.dispatch(active)
        self.assertTrue(path.is_symlink()); self.assertFalse((self.rt / 'absent').exists())

    async def test_new_session_does_not_restart_a_failed_dispatch(self):
        self.run_trial.side_effect = ValueError('synthetic failure')
        with self.q.open() as active:
            with self.assertRaises(ValueError): await self.dispatch(active)
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'automatic restart'): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1)

    async def test_changed_qualified_producer_refused_before_intent_or_native_work(self):
        with self.q.open() as active:
            path = self.root / next(iter(self.q.f.proof['evidence_files']))
            path.write_bytes(b'changed test producer')
            with self.assertRaises(ValueError): await self.dispatch(active)
        self.run_trial.assert_not_awaited(); self.docker.assert_not_called()
        self.assertFalse((self.rt / runner.INTENT).exists())

    async def test_leftover_owned_resources_refuse_before_launch_intent(self):
        self.docker.return_value = 'retained-owned-container'
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'owned scored resources'): await self.dispatch(active)
        self.run_trial.assert_not_awaited(); self.assertFalse((self.rt / runner.INTENT).exists())

    async def test_retained_cleanup_failure_halts_without_replay(self):
        async def after(index):
            self.f.result(self.read(policy.REGISTRATION_FILE), index, 0., containers_removed=False)
        self.after = after
        with self.q.open() as active:
            with self.assertRaises(ValueError): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1); self.assertFalse((self.rt / runner.RESULT).exists())

    async def test_missing_revocation_halts_without_replay(self):
        async def after(index):
            self.f.result(self.read(policy.REGISTRATION_FILE), index, 0., model_revoked=False)
        self.after = after
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'revocation'): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1)

    async def test_source_mutation_during_task_halts_after_retaining_original_result(self):
        async def after(index): (self.root / 'stage2/run_matched_repeat.py').write_bytes(b'changed fixture source')
        self.after = after
        with self.q.open() as active:
            with self.assertRaises(ValueError): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1)
        self.assertTrue((self.rt / 'scored-trials' / self.ids[0] / 'result.json').is_file())

    async def test_prior_result_mutation_in_next_task_halts(self):
        async def after(index):
            if index == 1:
                path = self.rt / 'scored-trials' / self.ids[0] / 'result.json'
                path.write_bytes(path.read_bytes() + b' ')
        self.after = after
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'Previously retained'): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 2)
        self.assertEqual(self.read(runner.FAILURE)['previously_checked_completed'], 1)

    async def test_unexpected_second_result_cannot_skip_next_admission(self):
        async def after(index): self.f.result(self.read(policy.REGISTRATION_FILE), index + 1)
        self.after = after
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'dispatched prefix'): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1)

    async def test_operator_marker_before_signal_finishes_current_then_stops(self):
        previous = signal.getsignal(signal.SIGUSR1)
        async def after(index):
            self.q.private('operator-stop-request.json', {'automatic_resume': False, 'source': 'test-operator'})
            os.kill(os.getpid(), signal.SIGUSR1)
        self.after = after
        with self.q.open() as active: result = await self.dispatch(active)
        self.assertEqual((result['status'], result['completed']), ('stopped', 1))
        self.assertEqual(self.run_trial.await_count, 1)
        self.assertEqual(signal.getsignal(signal.SIGUSR1), previous)
        self.assertEqual(self.read('operator-stop-request.json')['source'], 'test-operator')
        self.assertFalse(result['automatic_resume'])

    async def test_unpersisted_signal_is_retained_at_last_boundary_even_after89(self):
        async def after(index):
            if index == 88: os.kill(os.getpid(), signal.SIGUSR1)
        self.after = after
        with self.q.open() as active: result = await self.dispatch(active)
        self.assertEqual((result['status'], result['completed']), ('stopped', 89))
        self.assertEqual(self.read('operator-stop-request.json'), dict(source='SIGUSR1', automatic_resume=False))
        self.assertFalse(result['completed_audit_verified'])

    async def test_root_provider_stop_retains_failure_but_never_advances(self):
        async def after(index): self.q.private('provider-stop.json', {'reason': 'synthetic-authentication-stop'})
        self.after = after; self.rewards[0] = None
        with self.q.open() as active: result = await self.dispatch(active)
        self.assertEqual((result['status'], result['completed'], result['missing_verifier_results']), ('stopped', 1, 1))
        self.assertEqual(self.run_trial.await_count, 1)

    async def test_attempt_provider_stop_is_not_acknowledged_or_bypassed_by_observation(self):
        async def after(index):
            folder = self.f.partial(index, 'scored-attempts')
            self.q.private(str(folder.relative_to(self.rt)) + '/provider-stop.json', {'reason': 'synthetic-credit-stop'})
        self.after = after
        with self.q.open() as active:
            result = await self.dispatch(active)
            with self.assertRaisesRegex(ValueError, 'provider stop'): study.register(active)
        self.assertEqual(result['status'], 'stopped'); self.assertEqual(self.run_trial.await_count, 1)
        self.assertEqual(len(result['stop_files']), 1)

    async def test_unsafe_stop_marker_fails_closed_instead_of_claiming_safe_stop(self):
        async def after(index): (self.rt / 'provider-stop.json').symlink_to(self.rt / 'absent')
        self.after = after
        with self.q.open() as active:
            with self.assertRaises(ValueError): await self.dispatch(active)
        self.assertFalse((self.rt / runner.RESULT).exists()); self.assertTrue((self.rt / runner.FAILURE).exists())

    async def test_real_shared_cooldown_is_awaited_without_shortening_task_deadline(self):
        Cooldown(self.rt, self.clock).update(102.5, 3); waits = []
        async def sleep(seconds):
            self.assertFalse(self.ids); self.assertTrue(self.q.locked)
            waits.append(seconds); self.clock.now += seconds
        with patch.object(runner.asyncio, 'sleep', side_effect=sleep), self.q.open() as active:
            result = await self.dispatch(active)
        self.assertEqual(waits, [1., 1., .5]); self.assertEqual(result['completed'], 89)

    async def test_operator_stop_during_cooldown_does_not_start_first_task(self):
        Cooldown(self.rt, self.clock).update(200., 3)
        async def sleep(seconds):
            self.q.private('operator-stop-request.json', {'automatic_resume': False})
        with patch.object(runner.asyncio, 'sleep', side_effect=sleep), self.q.open() as active:
            result = await self.dispatch(active)
        self.assertEqual((result['status'], result['completed']), ('stopped', 0))
        self.run_trial.assert_not_awaited()

    async def test_cross_process_child_task_and_thread_handles_never_launch(self):
        with self.q.open() as active:
            with patch.object(session.os, 'getpid', return_value=os.getpid() + 1):
                with self.assertRaises(ValueError): await self.dispatch(active)
            with self.assertRaisesRegex(ValueError, 'async tasks'):
                await asyncio.create_task(runner.run(active))
            with self.assertRaises(ValueError): await asyncio.to_thread(lambda: asyncio.run(runner.run(active)))
        self.run_trial.assert_not_awaited(); self.assertFalse((self.rt / runner.INTENT).exists())

    async def test_cancellation_is_failure_not_completion_or_automatic_next_key(self):
        async def after(index): raise asyncio.CancelledError()
        self.after = after
        with self.q.open() as active:
            with self.assertRaises(asyncio.CancelledError): await self.dispatch(active)
        self.assertEqual(self.read(runner.FAILURE)['error_type'], 'CancelledError')
        self.assertEqual(self.run_trial.await_count, 1); self.assertFalse((self.rt / runner.RESULT).exists())
        self.assertIsNone(study._CURRENT.get())

    async def test_intent_mutation_during_task_prevents_completion(self):
        async def after(index):
            path = self.rt / runner.INTENT; path.write_bytes(path.read_bytes() + b' ')
        self.after = after
        with self.q.open() as active:
            with self.assertRaises(ValueError): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1); self.assertFalse((self.rt / runner.RESULT).exists())

    async def test_terminal_owned_resource_check_can_refuse_claimed_cleanup(self):
        async def after(index):
            self.q.private('operator-stop-request.json', {'automatic_resume': False})
            self.docker.return_value = 'unexpected-retained-owned-resource'
        self.after = after
        with self.q.open() as active:
            with self.assertRaisesRegex(ValueError, 'owned scored resources'): await self.dispatch(active)
        self.assertEqual(self.run_trial.await_count, 1)
        self.assertFalse((self.rt / runner.RESULT).exists())

    async def test_stop_observation_never_relaxes_next_cell_admission(self):
        with self.q.open() as active:
            block = study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                study.admit_trial(**self.f.args(factory)); self.f.result(block)
                folder = self.f.partial(0, 'scored-attempts')
                self.q.private(str(folder.relative_to(self.rt)) + '/provider-stop.json', {'reason': 'synthetic-stop'})
                metadata = runner._checkpoint(permit, {self.f.cells[0]['trial_id']})
                self.assertEqual(metadata['completed'], 1)
                with self.assertRaisesRegex(ValueError, 'provider stop'):
                    study.admit_trial(**self.f.args(factory, 1))

    def test_runner_and_tests_are_in_future_frozen_native_inventory(self):
        self.assertTrue({'run_matched_repeat.py', 'test_run_matched_repeat.py'} <= policy.REQUIRED_SOURCE_FILES)
        self.assertIn('test_run_matched_repeat', policy.TEST_MODULES)
