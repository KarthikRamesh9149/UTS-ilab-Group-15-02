"""Actual local private bytes/flocks; native ancestry is explicitly mocked."""
from contextlib import ExitStack
import ast
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import matched_repeat_locks as locks


class LockTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / 'deployment'
        self.root.mkdir(mode=0o700)
        self.enterContext(patch.object(locks.os, 'listxattr', return_value=[], create=True))
        self.enterContext(patch.object(locks, '_parents', side_effect=lambda path:
            tuple(p for p in reversed(path.parents) if p == self.root or p.is_relative_to(self.root))))
        self.paths = tuple(self.write(folder + '/.runtime/stage2/' + name, b'')
            for folder in ('original', 'recovery', 'repeat') for name in locks.NAMES)
        self.enterContext(patch.object(locks, 'paths', return_value=self.paths))

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(0o600)
        return path

    def held(self, path):
        with path.open('rb') as stream:
            try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return True
        return False

    def test_all_precreated_locks_are_held_and_released(self):
        with ExitStack() as stack:
            lease = locks.acquire(stack, self.root, 'terminus-2')
            self.assertTrue(all(self.held(p) for p in self.paths))
            lease.recheck()
        self.assertFalse(any(self.held(p) for p in self.paths))

    def test_contention_is_nonblocking_and_partial_locks_release(self):
        with self.paths[4].open('rb') as other:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError), ExitStack() as stack:
                locks.acquire(stack, self.root, 'terminus-2')
            self.assertFalse(any(self.held(p) for p in self.paths[:4]))

    def test_missing_lock_is_never_created(self):
        self.paths[0].unlink()
        with self.assertRaises(FileNotFoundError), ExitStack() as stack:
            locks.acquire(stack, self.root, 'terminus-2')
        self.assertFalse(self.paths[0].exists())

    def test_mode_acl_symlink_hardlink_fifo_and_wrong_group_refuse(self):
        path = self.paths[0]
        for mode in ('mode', 'acl', 'symlink', 'hardlink', 'fifo', 'group'):
            with self.subTest(mode=mode), ExitStack() as stack:
                path.unlink(); self.write(path.relative_to(self.root).as_posix(), b'')
                if mode == 'mode': path.chmod(0o644)
                elif mode == 'acl': stack.enter_context(patch.object(locks.os, 'listxattr', return_value=['system.posix_acl_access']))
                elif mode == 'symlink': path.unlink(); path.symlink_to(self.paths[1])
                elif mode == 'hardlink': path.unlink(); os.link(self.paths[1], path)
                elif mode == 'fifo': path.unlink(); os.mkfifo(path, 0o600)
                elif mode == 'group': stack.enter_context(patch.object(locks.os, 'getgid', return_value=-1))
                with self.assertRaises(ValueError): locks._lock_identity(path)

    def test_nonprivate_runtime_parent_refuses(self):
        self.paths[0].parent.chmod(0o755)
        with self.assertRaises(ValueError): locks._lock_identity(self.paths[0])

    def test_closed_replaced_or_unlocked_handle_refuses(self):
        for mode in ('closed', 'replaced', 'unlocked'):
            with self.subTest(mode=mode), ExitStack() as stack:
                lease = locks.acquire(stack, self.root, 'terminus-2')
                path, handle, _ = lease.handles[0]
                if mode == 'closed': handle.close()
                elif mode == 'replaced': path.unlink(); self.write(path.relative_to(self.root).as_posix(), b'')
                else: fcntl.flock(handle, fcntl.LOCK_UN)
                with self.assertRaises(ValueError): lease.recheck()

    def test_new_private_evidence_does_not_change_directory_identity(self):
        with ExitStack() as stack:
            lease = locks.acquire(stack, self.root, 'terminus-2')
            self.write('recovery/.runtime/stage2/new-producer/evidence.json', b'{}')
            lease.recheck()

    def test_input_bytes_and_same_byte_file_replacement_are_distinct(self):
        path = self.write('stage2/synthetic.py', b'bound bytes')
        files = {'stage2/synthetic.py': hashlib.sha256(path.read_bytes()).hexdigest()}
        first = locks.file_identities(self.root, files)
        path.unlink(); self.write('stage2/synthetic.py', b'bound bytes')
        self.assertNotEqual(locks.file_identities(self.root, files), first)
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError): locks.file_identities(self.root, files)

    def test_private_input_modes_links_and_path_escape_refuse(self):
        path = self.write('.runtime/stage2/input.json', b'{}')
        files = {'.runtime/stage2/input.json': hashlib.sha256(b'{}').hexdigest()}
        locks.file_identities(self.root, files)
        path.chmod(0o644)
        with self.assertRaises(ValueError): locks.file_identities(self.root, files)
        path.chmod(0o600); os.link(path, path.with_name('alias.json'))
        with self.assertRaises(ValueError): locks.file_identities(self.root, files)
        for name in ('../escape', '/absolute', 'stage2//file', 'stage2/./file'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                locks.file_identities(self.root, {name: 'a' * 64})

    def test_directory_replacement_and_acl_refuse(self):
        path = self.write('stage2/source.py', b'bound')
        files = {'stage2/source.py': hashlib.sha256(b'bound').hexdigest()}
        first = locks.file_identities(self.root, files)
        path.parent.rename(self.root / 'old-stage2')
        self.write('stage2/source.py', b'bound')
        self.assertNotEqual(locks.file_identities(self.root, files), first)
        with patch.object(locks.os, 'listxattr', return_value=['system.posix_acl_default']):
            with self.assertRaises(ValueError): locks.file_identities(self.root, files)


class OrderTests(unittest.TestCase):
    def test_actual_recovery_order_is_prefix_and_baselines_remain_sequential(self):
        # Inspect only the committed function's path plan, never open a recovery
        # session, native root, lock, collector or private archive.
        source = Path(__file__).parent / 'no_cutoff_recovery_session.py'
        tree = ast.parse(source.read_bytes())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name == '_lock_paths')
        namespace = dict(ancestors=locks.ancestors, C3_ROOT=locks.C3_ROOT, NC_ROOT=locks.NC_ROOT,
            handoff=SimpleNamespace(phase=SimpleNamespace(RT=locks.RT + '/'),
                report=SimpleNamespace(ROOT=locks.FINAL_ROOT), revision=locks.recovery))
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        original = namespace['_lock_paths'](locks.recovery.ROOT)
        terminus = locks.paths(locks.runtime.DEPLOYMENTS['terminus-2'], 'terminus-2')
        openhands = locks.paths(locks.runtime.DEPLOYMENTS['openhands'], 'openhands')
        self.assertEqual(len(original), 49)
        self.assertEqual(terminus[:49], original)
        self.assertEqual((len(terminus), len(openhands)), (52, 55))
        self.assertEqual(openhands[:52], terminus)
        self.assertEqual(terminus[-1], locks.runtime.DEPLOYMENTS['terminus-2'] / locks.RT / 'matrix.lock')
        self.assertEqual(openhands[-1], locks.runtime.DEPLOYMENTS['openhands'] / locks.RT / 'matrix.lock')

    def test_arbitrary_root_and_harness_refuse(self):
        for root, harness in ((Path('/arbitrary'), 'terminus-2'), (Path('/arbitrary'), 'custom')):
            with self.subTest(harness=harness), self.assertRaises(ValueError): locks.paths(root, harness)

    def test_full_real_system_ancestry_is_the_default(self):
        path = locks.recovery.ROOT / locks.RT
        self.assertEqual(locks._parents(path), tuple(reversed(path.parents)))


if __name__ == '__main__':
    unittest.main()
