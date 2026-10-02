"""Protected local preservation fixtures; manager/procfs facts are mocked."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_revision as revision
import matched_repeat_execution_bootstrap as boot
import matched_repeat_execution_connection as connection
import matched_repeat_install as install
import matched_repeat_openhands_install as successor
import matched_repeat_locks as locks
import no_cutoff_recovery_install as seed
import no_cutoff_recovery_files as files
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save


class PreservationTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.enterContext(patch.object(boot, 'directories', side_effect=files.bootstrap.directories))
        self.enterContext(patch.object(revision, 'ROOT', self.root))

    def record(self, name, raw):
        path = save(self.root, name, raw)
        return revision._record(raw, boot.identity(path.lstat()))

    def fixture(self):
        sources = {'matched_repeat_policy.py': b'REQUIRED_SOURCE_FILES = frozenset({"matched_repeat_policy.py"})\n'}
        sources.update({f'fixture-{n}.py': b'# synthetic source\n' for n in range(418)})
        hashes = {}
        for name, raw in sources.items():
            hashes['stage2/' + name] = self.record('stage2/' + name, raw)['sha256']
        final = json.dumps(dict(sources={n: h for n, h in ((k[7:], v) for k, v in hashes.items())})).encode()
        for name, raw, key in ((boot.FINAL_INPUT, final, 'FINAL_SHA'), (boot.BASELINE_INPUT, b'{}', 'BASELINE_SHA')):
            hashes[name] = self.record(name, raw)['sha256']
            self.enterContext(patch.object(boot, key, hashes[name]))
        for i in range(9): hashes[f'extra-{i}'] = self.record(f'extra-{i}', b'fixture')['sha256']
        self.enterContext(patch.object(revision, 'SOURCES_SHA', boot._fingerprint(
            {n[7:]: h for n, h in hashes.items() if n.startswith('stage2/')})))
        metadata = {}
        for name, raw in {
                'installation-files.json': json.dumps(dict(files=hashes, runtime=[])).encode(),
                'installation-intent.json': json.dumps(dict(commit=revision.COMMIT)).encode(),
                'installation-result.json': json.dumps(dict(commit=revision.COMMIT, root=str(self.root), paid_launch_ready=False)).encode(),
                'source-commit.txt': (revision.COMMIT + '\n').encode()}.items():
            metadata[name] = self.record(name, raw)
        evidence = {n: self.record(revision.TERMINAL + '/' + n, b'{}\n') for n in revision.EVIDENCE}
        self.enterContext(patch.object(revision, 'METADATA', metadata))
        self.enterContext(patch.object(revision, 'EVIDENCE', evidence))
        self.enterContext(patch.object(revision, 'TREE', revision._tree(boot)))

    def test_exact_installed_inputs_terminal_files_and_tree_are_read(self):
        self.fixture(); saved, identities = revision._files(boot)
        self.assertEqual(len(saved), 10); self.assertEqual(len(identities), 430)
        self.assertEqual(revision._files(boot), (saved, identities))

    def test_same_bytes_replaced_terminal_file_refuses(self):
        self.fixture(); path = self.root / revision.TERMINAL / 'failure.json'
        raw = path.read_bytes(); path.rename(path.with_suffix('.retained'))
        save(self.root, revision.TERMINAL + '/failure.json', raw)
        with self.assertRaises(ValueError): revision._files(boot)

    def test_any_new_stop_execution_or_extra_tree_entry_refuses(self):
        for name in (*revision.ABSENT, 'unexpected-file'):
            with self.subTest(name=name):
                self.fixture()
                path = save(self.root, revision.RT + name, b'preserve')
                with self.assertRaises(ValueError): revision._files(boot)
                path.unlink()  # Only this disposable synthetic test fixture.

    def test_byte_change_unsafe_mode_and_link_refuse(self):
        self.fixture(); path = self.root / 'stage2/fixture-0.py'
        path.write_bytes(b'# different synthetic source\n')
        with self.assertRaises(ValueError): revision._files(boot)
        path.chmod(0o666)
        with self.assertRaises(ValueError): revision._tree(boot)

    def test_local_records_require_exact_inventory_hashes_and_decimal_identity(self):
        folder = '.runtime/netcup/retired-synthetic'; path = self.root / folder
        expected = self.record(folder + '/failure.json', b'{}')
        pinned = {folder: dict(files={'failure.json': expected},
            directory_identity=[str(v) for v in boot.identity(path.lstat())])}
        mac = NS(raw=boot.raw, identity=boot.identity, directories=boot.directories)
        with patch.object(revision, 'LOCAL', pinned):
            self.assertFalse(revision.local(self.root, mac)['paid_launch_ready'])
            save(self.root, folder + '/result.json', b'{}')
            with self.assertRaises(ValueError): revision.local(self.root, mac)

    def test_manager_requires_exact_retained_failure_not_an_exited_success(self):
        fields = dict(LoadState='loaded', ActiveState='failed', SubState='failed', MainPID='0',
            ExecMainPID='1970801', Result='exit-code', ExecMainCode='1', ExecMainStatus='1',
            InvocationID=revision.INVOCATION, Restart='no', NRestarts='0', Type='exec',
            RemainAfterExit='yes', WorkingDirectory=str(self.root), ControlPID='0', ControlGroup='')
        with patch.object(revision.subprocess, 'check_output') as command:
            command.return_value = '\n'.join(k+'='+v for k,v in fields.items())
            self.assertEqual(revision._manager(), fields)
            for key in ('InvocationID', 'ActiveState', 'MainPID', 'ControlGroup', 'ExecMainStatus'):
                command.return_value = '\n'.join(k+'='+('changed' if k==key else v) for k,v in fields.items())
                with self.subTest(key=key), self.assertRaises(ValueError): revision._manager()


class BindingTests(unittest.TestCase):
    def test_new_root_states_and_complete_inherited_lock_prefix(self):
        root = boot.root_for('terminus-2')
        self.assertNotEqual(root, revision.ROOT); self.assertEqual(install.ROOT, root)
        self.assertEqual(boot.RETIRED, revision.ROOT)
        self.assertEqual(root, locks.runtime.DEPLOYMENTS['terminus-2'])
        self.assertTrue(install.STATE.endswith('20261002-r2'))
        for operation in ('qualify-repeat', 'run-repeat'):
            self.assertTrue(connection.state_name('terminus-2', operation).endswith('20261002-r2'))
        term = locks.paths(root, 'terminus-2')
        oh = locks.paths(boot.root_for('openhands'), 'openhands')
        self.assertEqual(install._lock_paths(seed, boot), term[:-1])
        self.assertEqual(successor._lock_paths(seed, boot), oh[:-1])
        self.assertEqual(term[51:54], tuple(revision.ROOT / locks.RT / n for n in locks.NAMES))
        self.assertEqual((len(term), len(oh)), (55, 58))


if __name__ == '__main__': unittest.main()
