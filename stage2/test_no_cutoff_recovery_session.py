"""Local protected files and real locks; native observations are mocked.

Synthetic live witnesses are test-only. No retained archive, native service,
Docker operation, genuine qualification or paid model is used by these tests.
"""
import asyncio
from contextlib import ExitStack
from copy import copy, deepcopy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import no_cutoff_recovery_session as session
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_runtime as runtime
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_libraries as libraries
from test_no_cutoff_recovery_policy import Fixture
from test_no_cutoff_recovery_runtime import save, sha


class LocalTree:
    def mock(self, obj, name, *args, **kwargs):
        p = patch.object(obj, name, *args, **kwargs)
        value = p.start(); self.addCleanup(p.stop)
        return value

    def tree(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        # Handoff protection also binds root.parent during each read. Give it
        # an owned stable parent, not the shared system temporary directory.
        self.root = Path(tmp.name).resolve() / 'deployment'
        self.root.mkdir(mode=0o700)
        self.mock(libraries.os, 'listxattr', return_value=[], create=True)
        self.mock(libraries, '_directory_chain', side_effect=lambda root, path:
            [root, *reversed([p for p in path.parents if p != root and p.is_relative_to(root)])])
        # Mock only system ancestry unavailable on macOS; every local fixture
        # directory and file retains actual identity/mode/link/ACL checks.
        self.mock(session, '_lock_parents', side_effect=lambda path:
            tuple(p for p in reversed(path.parents) if p == self.root or p.is_relative_to(self.root)))

    def lock_files(self):
        self.paths = tuple(save(self.root, folder + '/.runtime/stage2/' + name, b'')
            for folder in ('ancestor', 'recovery', 'original-final')
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'))
        self.mock(session, '_lock_paths', return_value=self.paths)

    def is_locked(self, path):
        with path.open('rb') as stream:
            try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return True
            return False


class LockTests(LocalTree, unittest.TestCase):
    def setUp(self):
        self.tree(); self.lock_files(); self.witness = handoff._Witness()
        handoff._WITNESSES[self.witness] = {'fixture': True}
        self.addCleanup(handoff.invalidate, self.witness)

    def test_all_real_locks_remain_held_and_release_after_invalidation(self):
        with session._locked(self.root, self.witness) as locks:
            self.assertTrue(all(self.is_locked(p) for p in self.paths))
            locks.recheck()
            self.assertIn(self.witness, handoff._WITNESSES)
        self.assertNotIn(self.witness, handoff._WITNESSES)
        self.assertFalse(any(self.is_locked(p) for p in self.paths))

    def test_partial_contention_invalidates_before_releasing_acquired_descriptors(self):
        opened = session.os.fdopen; witness = self.witness; owner = self
        class ObservedClose:
            def __init__(self, *args): self.stream = opened(*args)
            def __enter__(self): return self.stream
            def __exit__(self, *args):
                owner.assertNotIn(witness, handoff._WITNESSES)
                self.stream.close()
        with self.paths[3].open('rb') as other:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(session.os, 'fdopen', ObservedClose), self.assertRaises(BlockingIOError):
                with session._locked(self.root, witness): self.fail('Contended entry must refuse')
            self.assertFalse(any(self.is_locked(p) for p in self.paths[:3]))

    def test_missing_lock_is_not_created(self):
        self.paths[0].unlink()
        with self.assertRaises(FileNotFoundError):
            with session._locked(self.root, self.witness): self.fail('Missing lock accepted')
        self.assertFalse(self.paths[0].exists())

    def test_permission_acl_link_hardlink_and_fifo_refuse(self):
        path = self.paths[0]
        for kind in ('mode', 'acl', 'link', 'hardlink', 'fifo'):
            with self.subTest(kind=kind):
                path.unlink(); save(self.root, str(path.relative_to(self.root)), b'')
                if kind == 'mode': path.chmod(0o644)
                elif kind == 'acl': libraries.os.listxattr.return_value = ['system.posix_acl_access']
                elif kind == 'link': path.unlink(); path.symlink_to(self.paths[1])
                elif kind == 'hardlink': path.unlink(); os.link(self.paths[1], path)
                elif kind == 'fifo': path.unlink(); os.mkfifo(path, 0o600)
                with self.assertRaises(ValueError): session._lock_identity(path)
                libraries.os.listxattr.return_value = []

    def test_lock_parent_permission_change_refuses(self):
        self.paths[0].parent.chmod(0o755)
        with self.assertRaises(ValueError): session._lock_identity(self.paths[0])

    def test_same_byte_path_replacement_under_lock_refuses(self):
        with session._locked(self.root, self.witness) as locks:
            self.paths[0].unlink(); save(self.root, str(self.paths[0].relative_to(self.root)), b'')
            with self.assertRaises(ValueError): locks.recheck()

    def test_closed_descriptor_refuses(self):
        with session._locked(self.root, self.witness) as locks:
            locks.handles[0][1].close()
            with self.assertRaises(ValueError): locks.recheck()

    def test_explicitly_lost_lock_refuses_without_reacquiring_it(self):
        with session._locked(self.root, self.witness) as locks:
            fcntl.flock(locks.handles[0][1], fcntl.LOCK_UN)
            with self.assertRaises(ValueError): locks.recheck()
            self.assertFalse(self.is_locked(self.paths[0]))

    def test_future_exclusive_directory_writes_do_not_change_lock_identity(self):
        with session._locked(self.root, self.witness) as locks:
            save(self.root, 'ancestor/.runtime/stage2/new-producer/result.json')
            locks.recheck()


class SessionTests(LocalTree, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tree(); self.lock_files()
        self.f = Fixture(self, self.root)
        self.f.final['runtime_identity_sha256'] = '8' * 64
        raw = json.dumps(self.f.final).encode()
        self.mock(policy, 'ORIGINAL_QUALIFICATION', policy.fingerprint(self.f.final))
        self.mock(policy, 'ORIGINAL_QUALIFICATION_FILE_SHA256', sha(raw))
        save(self.root, handoff.phase.RT + policy.ORIGINAL_FILE, raw)
        save(self.root, 'stage2/input_manifest.json', self.f.manifest_raw)
        source = save(self.root, 'stage2/no_cutoff_recovery_session.py', b'local synthetic source')
        self.source = source; self.bound = {source.name: sha(source.read_bytes())}
        self.mock(handoff.operator, 'sources', return_value=self.bound)
        self.mock(handoff.operator, 'loaded')
        self.mock(session, '_context', return_value=self.root)
        self.stops = self.mock(handoff, '_no_stop')
        self.original = session._inputs(self.root)
        self.pred = dict(kind=handoff.KIND, experiment=policy.EXPERIMENT, paid_launch_ready=False,
            current_sources_sha256=policy.fingerprint(self.bound), predecessor=deepcopy(self.f.predecessor),
            copied_files=self.original['files'])
        self.host = dict(kind=runtime.KIND, experiment=policy.EXPERIMENT, condition=policy.CONDITION,
            paid_launch_ready=False, original_qualification_sha256=policy.ORIGINAL_QUALIFICATION,
            original_runtime_sha256=self.f.final['runtime_identity_sha256'], plan_sha256=policy.PLAN_SHA256,
            predecessor_sha256=policy.fingerprint(self.pred['predecessor']), sources=self.bound,
            sources_sha256=policy.fingerprint(self.bound), library_parity={'synthetic': 'same'})
        self.events = []; self.witness = None
        self.auth = self.mock(handoff, 'authenticate', side_effect=self.authenticate)
        self.inspect = self.mock(runtime, 'inspect', side_effect=self.inspect_host)
        self.reread = self.mock(runtime, 'recheck', side_effect=self.recheck_host)
        self.native = self.mock(handoff, '_native_audit', side_effect=AssertionError('No native operation in test'))
        incoming, outgoing = os.pipe(); os.close(outgoing)
        self.stream = os.fdopen(incoming, 'rb'); self.addCleanup(self.stream.close)

    def authenticate(self, stream):
        self.assertIs(stream, self.stream)
        self.assertFalse(any(self.is_locked(p) for p in self.paths)); self.events.append('authenticate')
        self.witness = handoff._Witness()
        handoff._WITNESSES[self.witness] = dict(pid=os.getpid(), thread=threading.get_ident(),
            task=handoff._task(), root=self.root, record=deepcopy(self.pred))
        return self.witness

    def inspect_host(self, witness):
        handoff._live(witness)
        self.assertTrue(all(self.is_locked(p) for p in self.paths)); self.events.append('host-read')
        return deepcopy(self.host)

    def recheck_host(self, witness, recorded):
        current = self.inspect_host(witness); policy._same(current, recorded)
        return current

    def assert_dead(self, active):
        self.assertNotIn(active, session._SESSIONS)
        self.assertNotIn(self.witness, handoff._WITNESSES)
        with self.assertRaises(ValueError): session.describe(active)

    async def test_fresh_auth_before_locks_runtime_under_locks_and_exit_recheck(self):
        with session.open_session(self.stream) as active:
            record = session.describe(active)
            self.assertFalse(record['paid_launch_ready'])
            self.assertFalse(record['limitations']['recovery_execution_qualified'])
            self.assertEqual(record['condition'], 'C0-NC')
            self.assertEqual(session.recheck(active), record)
            self.assertEqual(self.auth.call_count, 1)
            self.assertEqual(self.events[0], 'authenticate')
        self.assertEqual(self.reread.call_count, 2)
        self.assert_dead(active); self.assertFalse(any(self.is_locked(p) for p in self.paths))
        self.native.assert_not_called()

    async def test_description_is_deep_copy_not_authority(self):
        with session.open_session(self.stream) as active:
            record = session.describe(active); record['runtime']['sources'].clear()
            self.assertTrue(session.describe(active)['runtime']['sources'])
            for value in (record, session._Session(), None, {'paid_launch_ready': True}):
                with self.subTest(value=type(value).__name__), self.assertRaises(ValueError): session.recheck(value)
            for operation in (copy, deepcopy, pickle.dumps):
                with self.assertRaises(TypeError): operation(active)

    async def test_nested_entry_refuses_without_second_auth_or_invalidating_owner(self):
        with session.open_session(self.stream) as active:
            with self.assertRaises(ValueError):
                with session.open_session(self.stream): self.fail('Nested session accepted')
            session.recheck(active); self.assertEqual(self.auth.call_count, 1)

    async def test_regular_saved_stream_refuses_before_auth(self):
        with self.assertRaises(ValueError):
            with session.open_session(io.BytesIO(b'saved')): self.fail('Saved input accepted')
        self.auth.assert_not_called()

    async def test_stop_refuses_before_authentication(self):
        self.stops.side_effect = ValueError('persistent stop')
        with self.assertRaises(ValueError):
            with session.open_session(self.stream): self.fail('Stopped entry accepted')
        self.auth.assert_not_called()

    async def test_authentication_failure_releases_gate_without_host_execution(self):
        self.auth.side_effect = ValueError('uncommitted transfer')
        with self.assertRaises(ValueError):
            with session.open_session(self.stream): self.fail('Bad handoff accepted')
        self.assertTrue(session._GATE.acquire(blocking=False)); session._GATE.release()
        self.inspect.assert_not_called()

    async def test_entry_runtime_failure_invalidates_before_unlock(self):
        original = handoff.invalidate
        def invalidate(w):
            if w is self.witness and w in handoff._WITNESSES:
                self.assertTrue(all(self.is_locked(p) for p in self.paths))
            original(w)
        self.mock(handoff, 'invalidate', side_effect=invalidate)
        self.inspect.side_effect = ValueError('native mismatch')
        with self.assertRaises(ValueError):
            with session.open_session(self.stream): self.fail('Runtime refusal accepted')
        self.assertNotIn(self.witness, handoff._WITNESSES)

    async def test_input_drift_during_authentication_refuses_before_host(self):
        original = self.auth.side_effect
        def changed(stream):
            value = original(stream); self.source.write_bytes(b'changed'); return value
        self.auth.side_effect = changed
        with self.assertRaises(ValueError):
            with session.open_session(self.stream): self.fail('Changed source accepted')
        self.inspect.assert_not_called(); self.assertNotIn(self.witness, handoff._WITNESSES)

    async def test_source_drift_latches_both_handles_even_after_byte_restoration(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                raw = self.source.read_bytes(); self.source.write_bytes(b'changed')
                with self.assertRaises(ValueError): session.recheck(active)
                self.source.write_bytes(raw)
                self.assert_dead(active)
                self.assertTrue(all(self.is_locked(p) for p in self.paths))

    async def test_same_byte_source_replacement_latches_identity(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                raw = self.source.read_bytes(); self.source.unlink()
                save(self.root, 'stage2/no_cutoff_recovery_session.py', raw)
                session.recheck(active)
        self.assert_dead(active)

    async def test_private_whitespace_mode_and_source_link_refuse_before_auth(self):
        path = self.root / handoff.phase.RT / policy.ORIGINAL_FILE
        raw = path.read_bytes(); path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            with session.open_session(self.stream): self.fail('Changed original bytes accepted')
        path.write_bytes(raw); path.chmod(0o640)
        with self.assertRaises(ValueError):
            with session.open_session(self.stream): self.fail('Readable private anchor accepted')
        path.chmod(0o600); self.source.unlink(); self.source.symlink_to(path)
        with self.assertRaises((ValueError, OSError)):
            with session.open_session(self.stream): self.fail('Linked source accepted')
        self.auth.assert_not_called()

    async def test_runtime_library_drift_refuses_exit_and_both_handles_die(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                self.host['library_parity']['synthetic'] = 'changed'
        self.assert_dead(active)

    async def test_incoherent_reader_identity_cannot_open_scope(self):
        self.host['condition'] = 'terminus-2'
        with self.assertRaises(ValueError):
            with session.open_session(self.stream): self.fail('Wrong harness accepted')
        self.assertNotIn(self.witness, handoff._WITNESSES)

    async def test_late_mutation_after_host_recheck_is_not_hidden(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                def changed(w, recorded):
                    value = self.recheck_host(w, recorded); self.source.write_bytes(b'late'); return value
                self.reread.side_effect = changed
                session.recheck(active)
        self.assert_dead(active)

    async def test_caller_exception_and_cancellation_invalidate_before_release(self):
        for error in (RuntimeError('synthetic'), asyncio.CancelledError()):
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                with session.open_session(self.stream) as active:
                    raise error
            self.assert_dead(active); self.assertFalse(any(self.is_locked(p) for p in self.paths))

    async def test_real_async_task_cancellation_releases_locks_and_invalidates(self):
        entered = asyncio.Event(); active = None
        async def consume():
            nonlocal active
            with session.open_session(self.stream) as active:
                entered.set(); await asyncio.Future()
        worker = asyncio.create_task(consume())
        await entered.wait(); worker.cancel()
        with self.assertRaises(asyncio.CancelledError): await worker
        self.assert_dead(active); self.assertFalse(any(self.is_locked(p) for p in self.paths))

    async def test_cancelled_runtime_recheck_latches_both_handles(self):
        with self.assertRaises(asyncio.CancelledError):
            with session.open_session(self.stream) as active:
                self.reread.side_effect = asyncio.CancelledError()
                session.recheck(active)
        self.assert_dead(active)

    async def test_wrong_pid_latches_owner_even_after_restore(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                with patch.object(session.os, 'getpid', return_value=os.getpid() + 1):
                    with self.assertRaises(ValueError): session.describe(active)
                self.assert_dead(active)

    async def test_other_async_task_invalidates_original_owner(self):
        async def moved(active):
            with self.assertRaises(ValueError): session.describe(active)
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                await asyncio.create_task(moved(active)); self.assert_dead(active)

    async def test_other_thread_invalidates_original_owner(self):
        def moved(active):
            try: session.describe(active)
            except ValueError: return True
            return False
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                self.assertTrue(await asyncio.to_thread(moved, active)); self.assert_dead(active)

    async def test_revoked_handoff_cannot_leave_a_live_session(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                handoff.invalidate(self.witness); session.describe(active)
        self.assert_dead(active)

    async def test_lost_lock_invalidates_session_without_reacquisition(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.stream) as active:
                handle = session._SESSIONS[active]['locks'].handles[0][1]
                fcntl.flock(handle, fcntl.LOCK_UN); session.describe(active)
        self.assert_dead(active)

    async def test_new_context_requires_new_authentication_not_old_handle(self):
        with session.open_session(self.stream) as first: first_witness = self.witness
        with session.open_session(self.stream) as second:
            self.assertEqual(self.auth.call_count, 2); self.assertIsNot(first, second)
            self.assertIsNot(first_witness, self.witness)
            with self.assertRaises(ValueError): session.recheck(first)
        # This is not permission to replay any started key. There is no paid
        # registration/dispatch entry in this prerequisite component.
        self.assertFalse(hasattr(session, 'dispatch_permit'))
        self.assertFalse(hasattr(session, 'verify_qualification'))


class ContractTests(unittest.TestCase):
    def test_actual_lock_chain_matches_unchanged_inherited_helper_plus_final(self):
        import run_no_cutoff_final as final
        import run_no_cutoff_custom as nc
        paths = []
        def hold(stack, runtime_path, name): paths.append(runtime_path / name)
        with patch.object(session.ancestors, 'hold', side_effect=hold), \
                patch.object(nc, 'hold', side_effect=hold), patch.object(final, 'hold', side_effect=hold):
            final.lock_all(ExitStack(), handoff.ROOT)
        paths.extend(handoff.report.ROOT / handoff.phase.RT / n
            for n in ('matrix.lock', 'scored.lock', 'gateway.lock'))
        paths.extend(base / handoff.phase.RT / n
            for base in (handoff.revision.RETIRED, handoff.revision.REJECTED)
            for n in ('matrix.lock', 'scored.lock', 'gateway.lock'))
        self.assertEqual(session._lock_paths(handoff.ROOT), tuple(paths))
        self.assertEqual(len(paths), 40)
        self.assertEqual(sum(p.parent == handoff.ROOT / handoff.phase.RT for p in paths), 1)

    def test_full_system_ancestry_is_included(self):
        path = Path('/opt/example/.runtime/stage2/matrix.lock')
        self.assertEqual(session._lock_parents(path), tuple(reversed(path.parents)))

    def test_actual_context_refuses_local_interpreter_without_effects(self):
        with self.assertRaises(ValueError): session._context()

    def test_import_credential_free_child_has_no_external_effects(self):
        root = Path(__file__).resolve().parents[1]
        code = '''import sys, os, json
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'stage2'))
import no_cutoff_recovery_libraries as guard
guard._ENVIRONMENT=dict(os.environ);sys.addaudithook(guard.no_effects)
import no_cutoff_recovery_session as s
if guard._VIOLATION: raise ValueError('Forbidden import effect')
print(json.dumps(dict(kind=s.KIND,sessions=len(s._SESSIONS),paid_launch_ready=False)))
'''
        environment = libraries.environment(root)
        # The local test venv is .tools/stage2-custom, not a native .venv.
        environment['TIKTOKEN_CACHE_DIR'] = str(Path(sys.prefix) /
            'lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers')
        result = subprocess.run([sys.executable, '-I', '-B', '-'], input=code, cwd=root,
            env=environment, capture_output=True, text=True, check=True, timeout=90)
        self.assertEqual(json.loads(result.stdout), dict(kind=session.KIND, sessions=0, paid_launch_ready=False))


if __name__ == '__main__': unittest.main()
