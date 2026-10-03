"""Actual local exclusive copies/locks; native service facts are mocked."""
import ast
import base64
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_install as install
import matched_repeat_openhands_install as openhands_install
from matched_repeat_baseline_probe import check_files
import matched_repeat_execution_bootstrap as boot
import matched_repeat_locks as locks
import no_cutoff_recovery_install as seed
import no_cutoff_recovery_files as evidence
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save


class InstallTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.old = self.root / 'original'; self.target = self.root / 'baseline'
        self.old.mkdir(mode=0o700)
        for module, name, value in ((install, 'ROOT', self.target), (install, 'ORIGINAL', self.old),
                (seed, 'ORIGINAL', self.old), (evidence.libraries, 'ORIGINAL', self.old)):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.object(seed, '_interpreter', return_value=('synthetic-local-interpreter', 'a' * 64, ())))
        self.paths = tuple(self.old / '.runtime/stage2' / n for n in ('matrix.lock', 'scored.lock', 'gateway.lock'))
        for path in self.paths: save(self.old, path.relative_to(self.old).as_posix(), b'')
        self.enterContext(patch.object(install, '_lock_paths', return_value=self.paths))
        save(self.old, 'stage2/original.py', b'# retained original source\n')
        save(self.old, '.venv/lib/python3.12/site-packages/example.py', b'# local synthetic library\n')
        save(self.old, '.venv/bin/python', b'synthetic-not-an-interpreter\n')
        save(self.old, '.cache/tasks/task/task.toml', b'synthetic task metadata\n')
        save(self.old, '.cache/stage2-tokenizer/cache', b'synthetic tokenizer bytes\n')
        save(self.old, '.runtime/stage2/python-runtime.tar.gz', b'not-a-real-archive\n')
        save(self.old, '.env', b'OPENROUTER_API_KEY=synthetic-not-a-real-credential\n')
        provenance = dict(dataset_path='.cache/tasks', canonical={'file_hashes': [dict(path='task/task.toml',
            sha256=evidence.libraries.read(self.old, '.cache/tasks/task/task.toml'))]})
        self.decoded = {'stage2/current.py': b'# actual current synthetic source\n',
            'stage2/dataset_provenance.json': json.dumps(provenance).encode()}
        self.final = {'python_runtime': {'sha256': evidence.libraries.read(self.old, '.runtime/stage2/python-runtime.tar.gz')}}
        self.value = dict(commit='a' * 40, hashes={n: install._sha(v) for n, v in self.decoded.items()})
        self.enterContext(patch.object(install, '_payload', return_value=(self.decoded, self.final,
            evidence.bootstrap, seed, evidence.libraries, NS())))
        def old(*args, absent):
            if absent and (self.target.exists() or self.target.is_symlink()): raise ValueError('Existing root is terminal')
            path = self.old / 'stage2/original.py'
            return dict(original=(path.read_bytes(), evidence.libraries.identity(path.lstat())))
        self.enterContext(patch.object(install, '_old', side_effect=old))

    def test_actual_exclusive_copy_and_three_locks_original_unchanged(self):
        before = {p.relative_to(self.old).as_posix(): p.read_bytes() for p in self.old.rglob('*') if p.is_file()}
        result = install._install(self.value)
        self.assertEqual(result['precreated_locks'], 3); self.assertEqual(result['harness'], 'terminus-2')
        self.assertFalse(result['paid_launch_ready']); self.assertFalse(result['repeat_execution_qualified'])
        for name, raw in before.items(): self.assertEqual((self.old / name).read_bytes(), raw)
        self.assertEqual((self.target / '.env').read_bytes(), before['.env'])
        for path in self.target.rglob('*'):
            self.assertFalse(path.stat().st_mode & 0o077)
        with self.assertRaises(ValueError): install._install(self.value)
        self.assertEqual(json.loads((self.target / 'installation-result.json').read_bytes()), result)

    def test_existing_partial_root_refuses_without_replacing_anything(self):
        self.target.mkdir(mode=0o700); save(self.target, 'partial.json', b'{}')
        with self.assertRaises(ValueError): install._install(self.value)
        self.assertEqual({p.name for p in self.target.iterdir()}, {'partial.json'})

    def test_same_byte_original_replacement_retains_failure_and_no_success(self):
        original = install._copy; changed = False
        def copy(*args):
            nonlocal changed
            result = original(*args)
            if not changed:
                path = self.old / 'stage2/original.py'; raw = path.read_bytes()
                path.rename(path.with_suffix('.retained')); save(self.old, 'stage2/original.py', raw); changed = True
            return result
        with patch.object(install, '_copy', side_effect=copy), self.assertRaises(ValueError): install._install(self.value)
        self.assertTrue((self.target / 'installation-failure.json').exists())
        self.assertFalse((self.target / 'installation-result.json').exists())

    def test_extra_output_is_preserved_and_cannot_complete(self):
        original = install._copy
        def copy(*args):
            result = original(*args)
            if not (self.target / 'extra').exists(): save(self.target, 'extra', b'preserve me')
            return result
        with patch.object(install, '_copy', side_effect=copy), self.assertRaises(ValueError): install._install(self.value)
        self.assertEqual((self.target / 'extra').read_bytes(), b'preserve me')
        self.assertTrue((self.target / 'installation-failure.json').exists())

    def test_held_or_missing_lock_refuses_before_creation(self):
        with self.paths[0].open('rb') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): install._install(self.value)
        self.assertFalse(self.target.exists())
        self.paths[0].unlink()
        with self.assertRaises(FileNotFoundError): install._install(self.value)
        self.assertFalse(self.target.exists())

    def test_lock_replacement_loss_or_unsafe_mode_refuses(self):
        with self.assertRaisesRegex(ValueError, 'identity changed'), install._locked(seed, evidence.bootstrap) as check:
            path = self.paths[0]; path.rename(path.with_suffix('.retained')); save(self.old, path.relative_to(self.old).as_posix(), b'')
            with self.assertRaises(ValueError): check()
            # Catching a recheck failure does not let the normal exit pass.
        self.paths[0].chmod(0o644)
        with self.assertRaises(ValueError), install._locked(seed, evidence.bootstrap): pass

    def test_symlinked_runtime_input_refuses_without_new_root(self):
        path = self.old / '.cache/stage2-tokenizer/cache'; path.rename(path.with_suffix('.retained')); path.symlink_to('cache.retained')
        with self.assertRaises(ValueError): install._install(self.value)
        self.assertFalse(self.target.exists())

    def test_original_empty_installer_lock_is_private_only_in_new_copy(self):
        save(self.old, '.venv/.lock', b''); path = self.old / '.venv/.lock'; path.chmod(0o666)
        before = evidence.libraries.identity(path.lstat()); install._install(self.value)
        self.assertEqual(evidence.libraries.identity(path.lstat()), before)
        self.assertEqual((self.target / '.venv/.lock').stat().st_mode & 0o777, 0o600)

    def test_original_nonempty_installer_lock_is_not_accepted(self):
        save(self.old, '.venv/.lock', b'not empty'); (self.old / '.venv/.lock').chmod(0o666)
        with self.assertRaises(ValueError): install._install(self.value)
        self.assertFalse(self.target.exists())


class ContractTests(unittest.TestCase):
    def test_both_installers_pin_the_actual_original_audit_csv(self):
        import matched_repeat_original as original
        for installer in (install, openhands_install):
            self.assertEqual(installer.BASELINE_CSV, original.PUBLIC + '/trials.csv')
            self.assertEqual(installer.BASELINE_CSV_SHA, original.policy.BASELINE_CSV_SHA256)
            raw = (Path(install.__file__).parent.parent / installer.BASELINE_CSV).read_bytes()
            self.assertEqual(installer._sha(raw), installer.BASELINE_CSV_SHA)

    def test_exact_real_baseline_ancestor_order_excludes_only_own_uncreated_matrix(self):
        self.assertEqual(install._lock_paths(seed, boot), locks.paths(install.ROOT, 'terminus-2')[:-1])
        self.assertEqual(len(install._lock_paths(seed, boot)), 57)

    def test_only_validated_seed_destination_interpreter_alias_is_rebased(self):
        trees = [dict(links={'alias': dict(target=str(seed.ROOT / '.venv/bin/python3.12'), original='retained'),
            'external': dict(target='/opt/python/python3.12', original='retained'),
            'relative': dict(target='python3.12', original='retained')})]
        with patch.object(seed, '_runtime', return_value=('dataset', deepcopy(trees))):
            _, result = install._runtime(boot, seed, NS(), {})
        self.assertEqual(result[0]['links']['alias']['target'], str(install.ROOT / '.venv/bin/python3.12'))
        self.assertEqual(result[0]['links']['external'], trees[0]['links']['external'])
        self.assertEqual(result[0]['links']['relative'], trees[0]['links']['relative'])

    def test_native_installer_imports_are_stdlib_until_explicit_mac_entries(self):
        tree = ast.parse(Path(install.__file__).read_bytes())
        imports = {n.names[0].name if isinstance(n, ast.Import) else n.module for n in tree.body
            if isinstance(n, (ast.Import, ast.ImportFrom))}
        self.assertFalse(any(n.startswith(('matched_', 'no_cutoff_', 'scored_', 'harbor')) for n in imports))
        self.assertNotIn('shutil', imports)

    def test_payload_rejects_arbitrary_path_kind_revision_and_missing_bytes(self):
        for value in ({}, dict(kind='arbitrary'), dict(kind=install.KIND, commit='short', files={}, hashes={}, native={}, reporter={})):
            with self.assertRaises(ValueError): install._payload(value)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        stage = Path(install.__file__).parent
        self.decoded = {'stage2/' + n: (stage / n).read_bytes() for n in (
            'matched_repeat_execution_bootstrap.py', 'no_cutoff_recovery_install.py',
            'no_cutoff_recovery_libraries.py', 'no_cutoff_final_guard.py')}
        required = {n[7:] for n in self.decoded} | {'matched_repeat_policy.py'}
        self.decoded['stage2/matched_repeat_policy.py'] = ('REQUIRED_SOURCE_FILES = frozenset(' + repr(required) + ')\n').encode()
        self.decoded['stage2/original.py'] = b'# synthetic original source\n'
        self.final = dict(sources={'original.py': install._sha(self.decoded['stage2/original.py'])}, evidence_files={})
        self.decoded[boot.FINAL_INPUT] = json.dumps(self.final).encode()
        self.decoded[boot.BASELINE_INPUT] = b'{"synthetic_baseline":true}'
        self.decoded[install.SNAPSHOT] = b'{"synthetic_original178":true}'
        self.decoded[install.LAUNCH] = b'{"synthetic_launch":true}'
        self.csv = b'harness,task_id,reward\nsynthetic,synthetic,0.0\n'
        self.decoded[install.BASELINE_CSV] = self.csv
        for n in install._public(): self.decoded[n] = b'{"synthetic_public":true}'
        self.enterContext(patch.object(install, 'SNAPSHOT_SHA', install._sha(self.decoded[install.SNAPSHOT])))
        self.enterContext(patch.object(install, 'LAUNCH_SHA', install._sha(self.decoded[install.LAUNCH])))
        self.enterContext(patch.object(install, 'BASELINE_CSV_SHA', install._sha(self.csv)))
        module = install._module
        def load(name, raw):
            value = module(name, raw)
            if name == 'matched_repeat_execution_bootstrap':
                value.FINAL_SHA = install._sha(self.decoded[boot.FINAL_INPUT])
                value.BASELINE_SHA = install._sha(self.decoded[boot.BASELINE_INPUT])
            return value
        self.enterContext(patch.object(install, '_module', side_effect=load))

    def payload(self):
        return dict(kind=install.KIND, commit='a' * 40,
            files={n: base64.b64encode(raw).decode() for n, raw in self.decoded.items()},
            hashes={n: install._sha(raw) for n, raw in self.decoded.items()},
            native={'stage2/original.py': self.final['sources']['original.py'],
                seed.ORIGINAL_QUALIFICATION: install._sha(self.decoded[boot.FINAL_INPUT])},
            reporter={'stage2/synthetic-reporter.py': 'a' * 64})

    def test_actual_bound_stdlib_modules_complete_union_and_exact_raw_inputs(self):
        decoded, final, actual_boot, actual_seed, libraries, guard = install._payload(self.payload())
        self.assertEqual(decoded, self.decoded); self.assertEqual(final, self.final)
        self.assertEqual(actual_boot.RECOVERY, actual_seed.ROOT)
        self.assertEqual(libraries.ORIGINAL, guard.ROOT)

    def test_both_payloads_deliver_the_csv_required_by_the_original_audit(self):
        required = 'stage2/results/baseline-corrected-20260923/trials.csv'
        with patch.object(openhands_install, '_module', side_effect=install._module), \
                patch.object(openhands_install, 'SNAPSHOT_SHA', install.SNAPSHOT_SHA), \
                patch.object(openhands_install, 'LAUNCH_SHA', install.LAUNCH_SHA), \
                patch.object(openhands_install, 'BASELINE_CSV_SHA', install.BASELINE_CSV_SHA):
            for installer in (install, openhands_install):
                with self.subTest(harness=installer.ROOT.name):
                    decoded = installer._payload(self.payload())[0]
                    self.assertIn(required, decoded,
                        'The original audit cannot run without its installed baseline CSV')
                    with tempfile.TemporaryDirectory() as folder:
                        root = Path(folder).resolve()
                        path = root / required
                        path.parent.mkdir(parents=True)
                        path.write_bytes(decoded[required])
                        self.assertEqual(decoded[required], self.csv)
                        check_files(root, {required: install._sha(self.csv)})

    def test_both_payloads_reject_missing_or_altered_required_csv(self):
        with patch.object(openhands_install, '_module', side_effect=install._module), \
                patch.object(openhands_install, 'SNAPSHOT_SHA', install.SNAPSHOT_SHA), \
                patch.object(openhands_install, 'LAUNCH_SHA', install.LAUNCH_SHA), \
                patch.object(openhands_install, 'BASELINE_CSV_SHA', install.BASELINE_CSV_SHA):
            for installer in (install, openhands_install):
                for raw in (None, self.csv + b'altered,synthetic,1.0\n'):
                    with self.subTest(harness=installer.ROOT.name, missing=raw is None):
                        value = self.payload(); name = install.BASELINE_CSV
                        if raw is None:
                            value['files'].pop(name); value['hashes'].pop(name)
                        else:
                            value['files'][name] = base64.b64encode(raw).decode()
                            value['hashes'][name] = install._sha(raw)
                        with self.assertRaises(ValueError): installer._payload(value)

    def test_incomplete_current_inventory_and_extra_file_refuse(self):
        for name in ('stage2/original.py', next(iter(install._public()))):
            value = self.payload(); value['files'].pop(name); value['hashes'].pop(name)
            with self.assertRaises(ValueError): install._payload(value)
        value = self.payload(); value['files']['unrequested'] = base64.b64encode(b'').decode(); value['hashes']['unrequested'] = install._sha(b'')
        with self.assertRaises(ValueError): install._payload(value)

    def test_raw_drift_even_with_consistent_caller_digest_is_not_original_proof(self):
        value = self.payload(); name = boot.FINAL_INPUT; raw = self.decoded[name] + b' '
        value['files'][name] = base64.b64encode(raw).decode(); value['hashes'][name] = install._sha(raw)
        with self.assertRaises(ValueError): install._payload(value)

    def test_incomplete_native_original_sources_and_unsafe_paths_refuse(self):
        value = self.payload(); value['native'].pop('stage2/original.py')
        with self.assertRaises(ValueError): install._payload(value)
        for name in ('../escape', '/absolute', 'stage2//double', 'stage2/./dot'):
            value = self.payload(); value['native'][name] = 'b' * 64
            with self.subTest(name=name), self.assertRaises(ValueError): install._payload(value)


class CompletedUnitTests(unittest.TestCase):
    def setUp(self):
        self.nonce = 'a' * 32; self.unit = 'uts-recovery-qualify-' + self.nonce + '.service'
        self.intent = dict(nonce=self.nonce, unit=self.unit, root=str(boot.RECOVERY),
            operator_commit=boot.RECOVERY_COMMIT, operation='qualify-recovery')
        self.started = dict(native_process=dict(pid=99999999, start_ticks=123), invocation_id='b' * 32)
        self.state = dict(LoadState='loaded', ActiveState='active', SubState='exited', MainPID='0',
            ExecMainPID='99999999', Result='success', ExecMainCode='1', ExecMainStatus='0', InvocationID='b' * 32,
            Restart='no', NRestarts='0', Type='exec', RemainAfterExit='yes', WorkingDirectory=str(boot.RECOVERY))
        self.enterContext(patch.object(boot, 'recovery_finished', return_value={'unit': 'uts-recovery-run-' + 'c' * 32 + '.service'}))
        def read(root, name):
            return json.dumps(self.intent if name.endswith('intent.json') else self.started).encode(), (1,)
        self.enterContext(patch.object(boot, 'raw', side_effect=read))
        self.manager = self.enterContext(patch.object(install.subprocess, 'check_output', side_effect=lambda *a, **k:
            '\n'.join(k + '=' + v for k, v in self.state.items()) + '\n'))
        self.enterContext(patch.object(install.Path, 'read_text', side_effect=FileNotFoundError))

    def test_only_exact_successful_exited_units_allowed_with_two_manager_reads(self):
        self.assertEqual(install._completed_units(boot), {self.unit, 'uts-recovery-run-' + 'c' * 32 + '.service'})
        self.assertEqual(self.manager.call_count, 2)

    def test_unloaded_running_wrong_invocation_restarted_or_failed_unit_refuses(self):
        for key, value in (('LoadState', 'not-found'), ('SubState', 'running'), ('MainPID', '5'),
                ('InvocationID', 'd' * 32), ('NRestarts', '1'), ('ExecMainStatus', '1')):
            old = self.state[key]; self.state[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): install._completed_units(boot)
            self.state[key] = old

    def test_live_pid_or_uncertain_procfs_refuses(self):
        for value in ('malformed', '99999999 (python) S ' + '0 ' * 18 + '123'):
            with patch.object(install.Path, 'read_text', return_value=value), self.assertRaises(ValueError):
                install._completed_units(boot)

    def test_other_root_or_operation_cannot_be_allowlisted(self):
        for key, value in (('root', '/arbitrary'), ('operation', 'inspect'), ('operator_commit', 'd' * 40)):
            old = self.intent[key]; self.intent[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): install._completed_units(boot)
            self.intent[key] = old


if __name__ == '__main__': unittest.main()
