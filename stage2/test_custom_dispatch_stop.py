import asyncio
from contextlib import contextmanager
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from custom_dispatch_stop import BoundaryStop
from corrected_custom_policy import fingerprint
from run_corrected_custom import dispatch
from test_corrected_custom_study import fixture
from test_retry_gateway import Clock
from trial_execution import execute_phases


class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_marker_stops_before_audit_or_paid_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, block, _ = fixture(root)
            (runtime / 'operator-stop-request.json').touch()
            with patch('run_corrected_custom.audited') as audit, patch('run_corrected_custom.run_trial') as run:
                with patch('builtins.print'):
                    await dispatch(root, block)
                audit.assert_not_called()
                run.assert_not_called()

    async def test_signal_during_attempt_waits_for_result_and_prevents_next_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, block, proof = fixture(root)
            block['cells'] = block['cells'][:2]
            proof |= dict(gateway_image='image', guard_image='guard', setup_timeout_seconds=900)
            block['qualification_sha256'] = fingerprint(proof)
            complete, events = {}, []
            stop = BoundaryStop(runtime)
            async def execute(**kwargs):
                events.append('start')
                stop._receive(signal.SIGUSR1, None)
                await asyncio.sleep(.01)
                events.append('verified_and_cleaned')
                value = dict(status='verified', model_revoked=True,
                    containers_removed=True, networks_removed=True, volumes_removed=True)
                complete[kwargs['trial_id']] = value
                return value
            with patch('run_corrected_custom.audited', side_effect=lambda _: (complete.copy(), [])), \
                 patch('run_corrected_custom.qualified', return_value=proof), \
                 patch('run_corrected_custom.pending_stops', return_value=[]), \
                 patch('run_corrected_custom.Clock', Clock), \
                 patch('run_corrected_custom.summary', return_value={'attempted': 1}), \
                 patch('run_corrected_custom.run_trial', side_effect=execute) as run, patch('builtins.print'):
                await dispatch(root, block, stop=stop)
                run.assert_awaited_once()
            self.assertEqual(events, ['start', 'verified_and_cleaned'])
            self.assertEqual(len(complete), 1)

    def test_signal_handler_is_restored_and_does_not_cancel_active_task(self):
        before = signal.getsignal(signal.SIGUSR1)
        with tempfile.TemporaryDirectory() as directory:
            with BoundaryStop(directory) as stop:
                signal.raise_signal(signal.SIGUSR1)
                self.assertTrue(stop.requested())
            self.assertEqual(signal.getsignal(signal.SIGUSR1), before)
            self.assertTrue(BoundaryStop(directory).requested())
            self.assertEqual((Path(directory) / 'operator-stop-request.json').stat().st_mode & 0o777, 0o600)
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'operator-stop-request.json').symlink_to('/tmp/nonexistent-stop-target')
            with self.assertRaises(ValueError):
                BoundaryStop(directory).requested()


class CancelEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_setup_retains_actual_cleanup_and_revocation_evidence(self):
        for revoke_fails in (False, True):
            started, evidence, events = asyncio.Event(), {}, []
            class Environment:
                @contextmanager
                def with_default_user(self, user):
                    yield
                async def stop(self, delete):
                    events.append('destroyed')
            class Agent:
                async def setup(self, env):
                    started.set()
                    await asyncio.Event().wait()
            async def revoke():
                if revoke_fails:
                    raise RuntimeError('synthetic failure')
                events.append('revoked')
            task = NS(instruction='synthetic', config=NS(agent=NS(timeout_sec=10, user=None),
                verifier=NS(timeout_sec=10, user=None)))
            running = asyncio.create_task(execute_phases(agent=Agent(), environment=Environment(),
                task=task, paths=None, revoke_model=revoke, setup_timeout_seconds=10,
                retained_result=evidence))
            await started.wait()
            running.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await running
            self.assertEqual(evidence['model_revoked'], not revoke_fails)
            self.assertIn('setup', evidence['phase_seconds'])
            self.assertIsNone(evidence['verifier_result'])
            self.assertIn('destroyed', events)
            self.assertEqual(evidence['cleanup_errors'], ['revocation:RuntimeError'] if revoke_fails else [])


if __name__ == '__main__':
    unittest.main()
