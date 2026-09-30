"""Actual protected session/locks and handle lifetime; native reads mocked."""
import asyncio
from copy import deepcopy
import os
import threading
import unittest
from unittest.mock import patch

import matched_repeat_recovery_handoff as recovery
import matched_repeat_session as session
import matched_repeat_study as study
import qualify_matched_repeat as qualifier
import test_matched_repeat_session as fixtures


class ExecutionSessionTests(unittest.TestCase):
    def setUp(self):
        self.q = q = fixtures.SessionTests('runTest'); q.setUp(); self.addCleanup(q.doCleanups)
        self.root = q.root; self.events = []; self.witness = None
        self.enterContext(patch.object(recovery, '_task', side_effect=q.task))
        self.record = dict(kind=recovery.KIND, harness='terminus-2', operator_commit='a' * 40,
            recovery_document_sha256='b' * 64, archive_sha256='c' * 64,
            sources_sha256='d' * 64, recovery_result_files={'synthetic-result': 'e' * 64},
            paid_launch_ready=False, full_runtime_restore_exercised=False)
        self.auth = self.enterContext(patch.object(recovery, 'authenticate', side_effect=self.authenticate))
        self.read = self.enterContext(patch.object(recovery, 'recheck', side_effect=self.recheck))
        original = q.authenticate
        def original_auth(*args):
            witness = original(*args)
            session.handoff._WITNESSES[witness]['header'] = {'operator': {'operator_commit': 'a' * 40}}
            self.events.append('actual-original-authentication')
            return witness
        q.auth.side_effect = original_auth
        old_release = q.before_release
        def release():
            self.assertNotIn(self.witness, recovery._WITNESSES)
            self.events.append('both-invalid-before-unlock'); old_release()
        q.before_release = release

    def authenticate(self, root, harness, stream):
        self.assertEqual((root, harness, stream), (self.root, 'terminus-2', self.q.stream))
        self.assertFalse(self.q.locked); self.assertTrue(session._GATE.locked())
        self.events.append('actual-recovery-authentication')
        witness = recovery._Witness(); self.witness = witness
        recovery._WITNESSES[witness] = dict(pid=os.getpid(), thread=threading.get_ident(), task=self.q.task())
        self.addCleanup(recovery.invalidate, witness)
        return witness, stream

    def recheck(self, witness):
        recovery._live(witness)
        self.events.append('recovery-under-lock' if self.q.locked else 'recovery-before-lock')
        return deepcopy(self.record)

    def open(self):
        return session.open_execution_session(self.root, 'terminus-2', self.q.stream)

    def test_actual_execution_entry_consumes_both_handoffs_before_locks(self):
        with self.open() as active:
            self.assertEqual(self.events[:2], ['actual-recovery-authentication', 'actual-original-authentication'])
            self.assertTrue(self.q.locked)
            self.assertEqual(session.require_execution(active), self.record)
            self.assertEqual(session.describe(active)['completed_recovery'], self.record)
            value = session.require_execution(active); value['recovery_result_files'].clear()
            self.assertEqual(len(session.require_execution(active)['recovery_result_files']), 1)
            session.recheck(active)
        self.assertEqual(self.auth.call_count, 1); self.assertEqual(self.q.auth.call_count, 1)
        self.assertIn('both-invalid-before-unlock', self.events)
        with self.assertRaises(ValueError): session.require_execution(active)
        with self.assertRaises(ValueError): recovery._live(self.witness)

    def test_legacy_inspection_or_saved_record_is_not_execution_authority(self):
        with self.assertRaises(ValueError):
            with self.q.open() as active:
                self.assertNotIn('completed_recovery', session.describe(active))
                with self.assertRaises(ValueError): session.require_execution(active)
        self.auth.return_value = (deepcopy(self.record), self.q.stream); self.auth.side_effect = None
        with self.assertRaises(ValueError):
            with self.open(): self.fail('Saved metadata cannot create an execution session')
        self.assertFalse(session._GATE.locked())

    def test_different_commits_refuse_before_lock_and_revoke_recovery(self):
        self.record['operator_commit'] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'same committed revision'):
            with self.open(): self.fail('Different sender revisions cannot mix')
        self.assertFalse(self.q.locked); self.assertFalse(session._GATE.locked())
        self.assertNotIn(self.witness, recovery._WITNESSES)

    def test_final_recovery_drift_invalidates_before_release_and_cannot_restore(self):
        saved = deepcopy(self.record)
        with self.assertRaises(ValueError):
            with self.open() as active:
                self.record['archive_sha256'] = 'f' * 64
                with self.assertRaises(ValueError): session.recheck(active)
                self.record = saved
                with self.assertRaises(ValueError): session.require_execution(active)
        self.assertIn('both-invalid-before-unlock', self.events)

    def test_entry_failure_and_partial_lock_failure_revoke_without_leaking_gate(self):
        self.q.old_auth.side_effect = ValueError('Actual original audit refused')
        with self.assertRaises(ValueError):
            with self.open(): self.fail('Original audit failed')
        self.assertNotIn(self.witness, recovery._WITNESSES); self.assertFalse(session._GATE.locked())
        self.q.old_auth.side_effect = self.q.original_auth
        self.q.lock.side_effect = ValueError('Actual lock contention')
        with self.assertRaises(ValueError):
            with self.open(): self.fail('Lock failed')
        self.assertNotIn(self.witness, recovery._WITNESSES); self.assertFalse(session._GATE.locked())

    def test_exception_cancellation_and_nested_entry_do_not_leave_live_authority(self):
        with self.assertRaises(asyncio.CancelledError):
            with self.open() as active:
                with self.assertRaises(ValueError):
                    with self.open(): self.fail('Nested recovery handoff')
                with self.assertRaises(ValueError):
                    with self.q.open(): self.fail('Nested legacy scope')
                raise asyncio.CancelledError()
        self.assertNotIn(self.witness, recovery._WITNESSES); self.assertFalse(session._GATE.locked())
        with self.assertRaises(ValueError): session.require_execution(active)

    def test_real_task_switch_and_closed_recovery_handle_invalidate_parent_scope(self):
        async def run():
            with self.assertRaises(ValueError):
                with self.open() as active:
                    async def other():
                        with self.assertRaises(ValueError): session.require_execution(active)
                    await asyncio.create_task(other())
                    with self.assertRaises(ValueError): session.require_execution(active)
        asyncio.run(run())
        with self.assertRaises(ValueError):
            with self.open() as active:
                recovery.invalidate(self.witness)
                with self.assertRaises(ValueError): session.require_execution(active)

    def test_normal_exit_performs_actual_final_recovery_recheck(self):
        with self.assertRaises(ValueError):
            with self.open():
                self.read.side_effect = ValueError('Final actual recovery read refused')
        self.assertIn('both-invalid-before-unlock', self.events)
        self.assertFalse(session._GATE.locked())

    def test_real_qualifier_and_registration_reject_legacy_inspection_scope(self):
        with self.assertRaises(ValueError):
            with self.q.open() as active:
                with self.assertRaises(ValueError): study.register(active)
        async def check():
            with self.assertRaises(ValueError):
                with self.q.open() as active:
                    with self.assertRaises(ValueError): await qualifier.qualify(active)
        asyncio.run(check())
        self.auth.assert_not_called()


if __name__ == '__main__': unittest.main()
