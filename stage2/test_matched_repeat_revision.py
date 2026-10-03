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

    def fixture(self, *, second=False, third=False):
        attempt = revision.THIRD if third else revision.SECOND if second else revision._first()
        count = attempt['source_count']
        commit = attempt['commit']
        sources = {'matched_repeat_policy.py': b'REQUIRED_SOURCE_FILES = frozenset({"matched_repeat_policy.py"})\n'}
        sources.update({f'fixture-{n}.py': b'# synthetic source\n' for n in range(count - 1)})
        hashes = {}
        for name, raw in sources.items():
            hashes['stage2/' + name] = self.record('stage2/' + name, raw)['sha256']
        final = json.dumps(dict(sources={n: h for n, h in ((k[7:], v) for k, v in hashes.items())})).encode()
        for name, raw, key in ((boot.FINAL_INPUT, final, 'FINAL_SHA'), (boot.BASELINE_INPUT, b'{}', 'BASELINE_SHA')):
            hashes[name] = self.record(name, raw)['sha256']
            self.enterContext(patch.object(boot, key, hashes[name]))
        for i in range(9): hashes[f'extra-{i}'] = self.record(f'extra-{i}', b'fixture')['sha256']
        if third:
            name = 'stage2/results/baseline-corrected-20260923/trials.csv'
            hashes[name] = self.record(name, b'synthetic original CSV\n')['sha256']
        self.enterContext(patch.object(revision, 'SOURCES_SHA', boot._fingerprint(
            {name: hashes['stage2/' + name] for name in sources})))
        metadata = {}
        for name, raw in {
                'installation-files.json': json.dumps(dict(files=hashes, runtime=[])).encode(),
                'installation-intent.json': json.dumps(dict(commit=commit)).encode(),
                'installation-result.json': json.dumps(dict(commit=commit, root=str(self.root), paid_launch_ready=False)).encode(),
                'source-commit.txt': (commit + '\n').encode()}.items():
            metadata[name] = self.record(name, raw)
        evidence = {n: self.record(revision.TERMINAL + '/' + n, b'{}\n') for n in attempt['evidence']}
        self.enterContext(patch.object(revision, 'METADATA', metadata))
        self.enterContext(patch.object(revision, 'EVIDENCE', evidence))
        self.enterContext(patch.object(revision, 'TREE', revision._tree(boot)))
        if second or third:
            return dict(attempt, root=self.root, metadata=metadata, evidence=evidence,
                sources_sha=revision.SOURCES_SHA, tree=revision.TREE)

    def test_exact_installed_inputs_terminal_files_and_tree_are_read(self):
        self.fixture(); saved, identities = revision._files(boot)
        self.assertEqual(len(saved), 10); self.assertEqual(len(identities), 430)
        self.assertEqual(revision._files(boot), (saved, identities))

    def test_same_bytes_replaced_terminal_file_refuses(self):
        self.fixture(); path = self.root / revision.TERMINAL / 'failure.json'
        raw = path.read_bytes(); path.rename(path.with_suffix('.retained'))
        save(self.root, revision.TERMINAL + '/failure.json', raw)
        with self.assertRaises(ValueError): revision._files(boot)

    def test_second_attempt_reads_all_435_inputs_and_refuses_replaced_evidence(self):
        attempt = self.fixture(second=True)
        saved, identities = revision._files(boot, attempt)
        self.assertEqual((len(saved), len(identities)), (9, 435))
        self.assertEqual(revision._files(boot, attempt), (saved, identities))
        path = self.root / revision.TERMINAL / 'failure.json'; raw = path.read_bytes()
        path.rename(path.with_suffix('.retained')); save(self.root, revision.TERMINAL + '/failure.json', raw)
        with self.assertRaises(ValueError): revision._files(boot, attempt)

    def test_second_attempt_source_change_refuses(self):
        attempt = self.fixture(second=True)
        (self.root / 'stage2/fixture-422.py').write_bytes(b'# replaced synthetic source\n')
        with self.assertRaises(ValueError): revision._files(boot, attempt)

    def test_second_attempt_cannot_gain_the_previously_missing_csv(self):
        attempt = self.fixture(second=True)
        save(self.root, 'stage2/results/baseline-corrected-20260923/trials.csv', b'synthetic\n')
        with self.assertRaises(ValueError): revision._files(boot, attempt)

    def test_third_attempt_reads_all_436_inputs_including_csv_and_refuses_drift(self):
        attempt = self.fixture(third=True)
        saved, identities = revision._files(boot, attempt)
        self.assertEqual((len(saved), len(identities)), (9, 436))
        self.assertEqual(revision._files(boot, attempt), (saved, identities))
        path = self.root / 'stage2/results/baseline-corrected-20260923/trials.csv'
        path.write_bytes(b'changed CSV\n')
        with self.assertRaises(ValueError): revision._files(boot, attempt)

    def test_third_attempt_replaced_terminal_evidence_refuses(self):
        attempt = self.fixture(third=True)
        path = self.root / revision.TERMINAL / 'failure.json'; raw = path.read_bytes()
        path.rename(path.with_suffix('.retained')); save(self.root, revision.TERMINAL + '/failure.json', raw)
        with self.assertRaises(ValueError): revision._files(boot, attempt)

    def test_third_attempt_source_change_refuses(self):
        attempt = self.fixture(third=True)
        (self.root / 'stage2/fixture-422.py').write_bytes(b'# changed third source\n')
        with self.assertRaises(ValueError): revision._files(boot, attempt)

    def test_native_preservation_rechecks_all_three_attempts_and_refuses_late_drift(self):
        first = revision._first(); attempts = (first, revision.SECOND, revision.THIRD)
        with patch.object(revision.platform, 'system', return_value='Linux'), \
                patch.object(revision.os, 'getuid', return_value=0), \
                patch.object(revision.os, 'getgid', return_value=0), \
                patch.object(revision, '_manager', side_effect=lambda a: {'unit': a['unit']}) as manager, \
                patch.object(revision, '_quiet') as quiet, \
                patch.object(revision, '_files', side_effect=lambda b, a: ({'commit': a['commit']}, {})) as read:
            result = revision.native(boot)
            self.assertEqual([a['root'] for a in result['attempts']], [str(a['root']) for a in attempts])
            self.assertEqual([call.args[1]['root'] for call in read.call_args_list],
                [a['root'] for a in attempts] * 2)
            self.assertEqual((manager.call_count, quiet.call_count), (6, 6))
            self.assertTrue(result['qualification_remains_terminal']); self.assertFalse(result['paid_launch_ready'])
            read.side_effect = [({}, {})] * 5 + [({'late': 'changed'}, {})]
            with self.assertRaises(ValueError): revision.native(boot)

    def test_recorded_second_process_still_live_refuses_before_file_reads(self):
        with patch.object(revision, '_process', return_value=(1, revision.SECOND['processes'][0][1])):
            with self.assertRaisesRegex(ValueError, 'remains live'): revision._quiet(revision.SECOND)

    def test_recorded_third_process_still_live_refuses_before_file_reads(self):
        with patch.object(revision, '_process', return_value=(1, revision.THIRD['processes'][0][1])):
            with self.assertRaisesRegex(ValueError, 'remains live'): revision._quiet(revision.THIRD)

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
    def test_failed_r3_is_preserved_instead_of_reused_for_corrected_execution(self):
        failed = Path('/opt/uts-capstone-matched-repeat-terminus-2-20261003-r3')
        self.assertNotEqual(boot.root_for('terminus-2'), failed)
        self.assertEqual(revision.THIRD_ROOT, failed)
        self.assertEqual(boot.RETIRED_THIRD, failed)
        self.assertEqual(revision.THIRD['source_count'], 424)
        self.assertEqual(revision.THIRD['input_count'], 436)
        self.assertEqual(revision.THIRD['sources_sha'],
            '58d7dfce9baa6ef12ab8a5cc9218443c5c8c2cefa5531e772d37ee58ee9381d7')
        self.assertEqual(revision.THIRD['tree'], dict(entries=18165,
            sha256='894457077e0972b0b156f78f86ce7655381fb026c91c634abf05035bd000d4d9'))
        self.assertEqual(len(revision.THIRD['evidence']), 5)
        self.assertEqual(sum(len(v['files']) for v in revision.LOCAL.values()), 15)
        self.assertEqual(locks.paths(boot.root_for('terminus-2'), 'terminus-2')[57:60],
            tuple(failed / locks.RT / n for n in locks.NAMES))

    def test_failed_r2_is_preserved_instead_of_reused_for_corrected_execution(self):
        failed = Path('/opt/uts-capstone-matched-repeat-terminus-2-20261002-r2')
        self.assertNotEqual(boot.root_for('terminus-2'), failed)
        self.assertEqual(revision.SECOND_ROOT, failed)
        self.assertEqual(boot.RETIRED_SECOND, failed)
        self.assertEqual(revision.SECOND['source_count'], 424)
        self.assertEqual(revision.SECOND['input_count'], 435)
        self.assertEqual(revision.SECOND['sources_sha'],
            '77ba99952a112d6f5e8b85cc334956ed8faac19979963f12a299150730a0cddc')
        self.assertEqual(revision.SECOND['tree'], dict(entries=18164,
            sha256='ca78f3713389834724b0e98f0b7421c319c38d641d1049fcad1b83b9edac4abd'))
        self.assertEqual(len(revision.SECOND['evidence']), 5)
        self.assertEqual(sum(len(v['files']) for v in revision.LOCAL.values()), 15)
        self.assertEqual(locks.paths(boot.root_for('terminus-2'), 'terminus-2')[54:57],
            tuple(failed / locks.RT / n for n in locks.NAMES))

    def test_new_root_states_and_complete_inherited_lock_prefix(self):
        root = boot.root_for('terminus-2')
        self.assertNotEqual(root, revision.ROOT); self.assertEqual(install.ROOT, root)
        self.assertEqual(boot.RETIRED, revision.ROOT)
        self.assertEqual(root, locks.runtime.DEPLOYMENTS['terminus-2'])
        self.assertTrue(install.STATE.endswith('20261003-r4'))
        for operation in ('qualify-repeat', 'run-repeat'):
            self.assertTrue(connection.state_name('terminus-2', operation).endswith('20261003-r4'))
        term = locks.paths(root, 'terminus-2')
        oh = locks.paths(boot.root_for('openhands'), 'openhands')
        self.assertEqual(install._lock_paths(seed, boot), term[:-1])
        self.assertEqual(successor._lock_paths(seed, boot), oh[:-1])
        self.assertEqual(term[51:54], tuple(revision.ROOT / locks.RT / n for n in locks.NAMES))
        self.assertEqual((len(term), len(oh)), (61, 64))


if __name__ == '__main__': unittest.main()
