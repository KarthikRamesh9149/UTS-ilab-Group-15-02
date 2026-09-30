"""Local files/procfs/journal fixtures; no native observation or paid calls."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import no_cutoff_recovery_revision as revision
import no_cutoff_recovery_bootstrap as bootstrap
import no_cutoff_recovery_install as install
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_libraries as libraries
import no_cutoff_recovery_plan as plan
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save


class ManagerTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.baseline = self.root / 'baseline'; self.retired = self.root / 'retired'
        self.proc = self.root / 'proc'; self.cgroup = self.root / 'cgroup'
        save(self.baseline, '.runtime/stage2/matrix.lock', b'')
        self.retired.mkdir(mode=0o700); self.cgroup.mkdir(mode=0o700)
        save(self.proc, '1/comm', b'systemd\n'); save(self.proc, '1/cgroup', b'0::/\n')
        save(self.proc, 'sys/kernel/random/boot_id', revision.BOOT.encode())
        for key, value in dict(BASELINE=self.baseline, RETIRED=self.retired, PROC=self.proc,
                CGROUP=self.cgroup, OWNER=os.getuid(), GROUP=os.getgid()).items():
            self.enterContext(patch.object(revision, key, value))
        self.enterContext(patch.object(revision.sys, 'platform', 'linux'))
        self.rows = []
        events = []
        for index, (event, when, _) in enumerate(revision.EVENTS):
            text = revision.SERVICE + ': Deactivated successfully.' if index == 2 else 'synthetic manager event ' + str(index)
            events.append((event, when, revision._sha(text.encode())))
            self.rows.append(dict(_PID='1', _UID='0', _COMM='systemd', _BOOT_ID=revision.BOOT,
                SYSLOG_IDENTIFIER='systemd', UNIT=revision.SERVICE, INVOCATION_ID=revision.INVOCATION,
                MESSAGE_ID=event, __REALTIME_TIMESTAMP=when, MESSAGE=text))
        self.rows[0]['JOB_TYPE'] = 'start'
        self.rows[1].update(JOB_TYPE='start', JOB_RESULT='done')
        self.enterContext(patch.object(revision, 'EVENTS', tuple(events)))
        self.state = 'LoadState=not-found\nActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n'
        self.command = self.enterContext(patch.object(revision, '_command', side_effect=self.response))

    def response(self, args):
        if args[0] == 'systemctl': return self.state
        return '\n'.join(json.dumps(row) for row in self.rows)

    def test_unloaded_defaults_need_all_actual_manager_and_procfs_reads(self):
        self.assertEqual(revision.baseline()[revision.SERVICE]['LoadState'], 'not-found')
        self.assertEqual(sum(c.args[0][0] == 'journalctl' for c in self.command.call_args_list), 1)
        self.assertEqual(sum(c.args[0][0] == 'systemctl' for c in self.command.call_args_list), 4)

    def test_missing_extra_or_failed_journal_refuses_default_success_fields(self):
        original = deepcopy(self.rows)
        for rows in ([], original[:-1], original + [original[-1]], list(reversed(original))):
            with self.subTest(count=len(rows)):
                self.rows = rows
                with self.assertRaises(ValueError): revision.baseline()
        self.rows = original; self.rows[2]['MESSAGE'] = 'failed'
        with self.assertRaises(ValueError): revision.baseline()

    def test_each_trusted_identity_timestamp_invocation_and_message_is_required(self):
        for key in ('_PID', '_UID', '_COMM', '_BOOT_ID', 'SYSLOG_IDENTIFIER', 'UNIT',
                'INVOCATION_ID', 'MESSAGE_ID', '__REALTIME_TIMESTAMP', 'MESSAGE'):
            old = self.rows[2][key]; self.rows[2][key] = 'changed'
            with self.subTest(key=key), self.assertRaises(ValueError): revision.baseline()
            self.rows[2][key] = old

    def test_duplicate_state_and_nonzero_exit_or_active_process_refuse(self):
        for state in (self.state + 'MainPID=0\n', self.state.replace('MainPID=0', 'MainPID=12'),
                self.state.replace('ExecMainStatus=0', 'ExecMainStatus=1'),
                self.state.replace('ActiveState=inactive', 'ActiveState=active')):
            self.state = state
            with self.assertRaises(ValueError): revision.baseline()

    def test_current_boot_and_real_manager_required(self):
        save(self.proc, 'sys/kernel/random/boot_id', b'wrong-boot')
        with self.assertRaises(ValueError): revision.baseline()
        save(self.proc, 'sys/kernel/random/boot_id', revision.BOOT.encode())
        save(self.proc, '1/comm', b'not-systemd')
        with self.assertRaises(ValueError): revision.baseline()

    def test_existing_cgroup_or_process_under_either_old_root_refuses(self):
        (self.cgroup / revision.SERVICE).mkdir()
        with self.assertRaises(ValueError): revision.baseline()
        (self.cgroup / revision.SERVICE).rmdir()
        save(self.proc, '123/cgroup', b'0::/\n')
        for root in (self.baseline, self.retired):
            path = self.proc / '123/cwd'; path.symlink_to(root)
            with self.assertRaises(ValueError): revision.baseline()
            path.unlink()
        save(self.proc, '123/cgroup', ('0::/system.slice/' + revision.SERVICE + '\n').encode())
        with self.assertRaises(ValueError): revision.baseline()

    def test_stop_and_unsafe_runtime_permissions_refuse(self):
        p = self.baseline / '.runtime/stage2/operator-stop-request.json'
        save(self.baseline, '.runtime/stage2/operator-stop-request.json', b'{}')
        with self.assertRaises(ValueError): revision.baseline()
        p.unlink(); p.parent.chmod(0o777)
        with self.assertRaises(ValueError): revision.baseline()

    def test_late_manager_state_change_refuses(self):
        calls = 0
        def changed(args):
            nonlocal calls
            if args[0] == 'systemctl':
                calls += 1
                return self.state.replace('MainPID=0', 'MainPID=12') if calls == 4 else self.state
            return self.response(args)
        self.command.side_effect = changed
        with self.assertRaises(ValueError): revision.baseline()


class RetainedTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.enterContext(patch.object(revision, 'RETIRED', self.root))
        self.enterContext(patch.object(revision, 'OWNER', os.getuid()))
        self.enterContext(patch.object(revision, 'GROUP', os.getgid()))
        sources = {}
        for i in range(321):
            name = 'stage2/source_' + str(i) + '.py'; raw = ('synthetic source ' + str(i)).encode()
            save(self.root, name, raw); sources[name] = revision._sha(raw)
        save(self.root, '.venv/bin/real-python', b'not a real interpreter')
        (self.root / '.venv/bin/python').symlink_to('real-python')
        save(self.root, '.env', b'synthetic credential bytes must never be read')
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            save(self.root, '.runtime/stage2/' + name, b'')
        inventory = dict(files=sources, runtime=[dict(files={
            '.venv/bin/real-python': revision._sha(b'not a real interpreter'), '.env': 'a' * 64},
            links={'.venv/bin/python': 'real-python'}, directories=['.venv', '.venv/bin'])])
        records = {'installation-intent.json': b'{}', 'installation-files.json': json.dumps(inventory).encode(),
            'installation-result.json': b'{}', 'source-commit.txt': (revision.COMMIT + '\n').encode()}
        for name, raw in records.items(): save(self.root, name, raw)
        self.enterContext(patch.object(revision, 'RECORDS', {n: revision._sha(v) for n, v in records.items()}))
        self.enterContext(patch.object(revision, 'SOURCE_MAP',
            revision._sha(json.dumps(sources, sort_keys=True, allow_nan=False).encode())))

    def test_complete_exact_unused_tree_is_read_without_credentials(self):
        real = os.open
        def checked(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)) and Path(path).name == '.env':
                self.fail('Retired credential payload was opened')
            return real(path, *args, **kwargs)
        with patch.object(os, 'open', side_effect=checked):
            first = revision.retained(); self.assertEqual(revision.retained(), first)
        self.assertEqual(len(first['files']), 331)

    def test_new_attempt_or_operation_marker_is_never_an_unused_tree(self):
        for name in ('.runtime/stage2/no-cutoff-recovery-qualify-connection/intent.json',
                '.runtime/stage2/scored-trials/fresh-key/started.json',
                'installation-failure.json'):
            save(self.root, name, b'{}')
            with self.assertRaises(ValueError): revision.retained()
            # Each extra retained directory alone still correctly refuses.

    def test_pinned_runtime_inventory_allows_literal_exclamation_filename(self):
        name = '.venv/share/installed!asset.bin'
        save(self.root, name, b'synthetic installed runtime asset')
        path = self.root / 'installation-files.json'
        inventory = json.loads(path.read_bytes())
        inventory['runtime'][0]['files'][name] = revision._sha(b'synthetic installed runtime asset')
        inventory['runtime'][0]['directories'].append('.venv/share')
        raw = json.dumps(inventory).encode(); save(self.root, path.name, raw)
        revision.RECORDS[path.name] = revision._sha(raw)
        first = revision.retained()
        self.assertIn(name, first['files'])
        self.assertEqual(revision.retained(), first)
        (self.root / name).chmod(0o666)
        with self.assertRaises(ValueError): revision.retained()

    def test_source_content_same_byte_identity_and_manifest_changes_refuse(self):
        first = revision.retained(); p = self.root / 'stage2/source_0.py'
        p.write_bytes(b'changed')
        with self.assertRaises(ValueError): revision.retained()
        p.write_bytes(b'synthetic source 0')
        self.assertNotEqual(revision.retained(), first)
        p = self.root / 'installation-files.json'; p.write_bytes(p.read_bytes() + b' ')
        with self.assertRaises(ValueError): revision.retained()

    def test_symlink_hardlink_group_write_and_acl_refuse(self):
        p = self.root / 'stage2/source_0.py'; p.chmod(0o666)
        with self.assertRaises(ValueError): revision.retained()
        p.chmod(0o600); alias = self.root / 'alias'; os.link(p, alias)
        with self.assertRaises(ValueError): revision.retained()
        alias.unlink(); p.rename(alias); p.symlink_to(alias)
        with self.assertRaises((ValueError, OSError)): revision.retained()

    def test_late_inventory_drift_and_changed_interpreter_alias_refuse(self):
        p = self.root / '.venv/bin/python'; p.unlink(); p.symlink_to('other-python')
        with self.assertRaises(ValueError): revision.retained()

    def test_recheck_rejects_same_byte_replacement_between_observations(self):
        real = revision.retained; calls = 0
        def replace():
            nonlocal calls
            calls += 1
            if calls == 2:
                p = self.root / 'stage2/source_0.py'; q = self.root / 'old-source'
                p.rename(q); save(self.root, 'stage2/source_0.py', q.read_bytes()); q.unlink()
            return real()
        with patch.object(revision, 'baseline', return_value={'actual_synthetic': True}), \
                patch.object(revision, 'rejected', return_value={'retained_failure': True}), \
                patch.object(revision, 'retained', side_effect=replace), self.assertRaises(ValueError):
            revision.inspect()


class ContractTests(unittest.TestCase):
    def test_relative_paths_allow_literal_exclamation_not_traversal_or_shell_syntax(self):
        self.assertEqual(revision._relative('.venv/share/asset!name'), '.venv/share/asset!name')
        for name in ('/absolute!', '../parent!', 'nested/../parent!', 'nested//empty!',
                'nested/./dot!', 'nested\\backslash!', 'bad\x00name!', 'bad\nname!',
                'bad;name!', 'bad$name!', 'bad name!', ''):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError): revision._relative(name)

    def test_bootstrap_consumes_exact_bound_revision_reader_before_service_work(self):
        original = ('from pathlib import Path\nROOT=Path(' + repr(str(bootstrap.ORIGINAL)) +
            ')\ndef service(): return None\n').encode()
        amended = ('from pathlib import Path\nROOT=Path(' + repr(str(bootstrap.ROOT)) +
            ')\ndef inspect(): raise ValueError("synthetic revision refusal")\n').encode()
        names = {'stage2/no_cutoff_final_guard.py': original, 'stage2/no_cutoff_recovery_revision.py': amended}
        bindings = {n: revision._sha(v) for n, v in names.items()}
        def read(root, name, digest):
            self.assertEqual(root, bootstrap.ROOT); self.assertEqual(digest, bindings[name])
            return names[name], ()
        with patch.object(bootstrap, 'raw', side_effect=read) as actual, self.assertRaisesRegex(ValueError, 'synthetic revision refusal'):
            bootstrap.ancestors(bindings)
        self.assertEqual(actual.call_count, 2)

    def test_fixed_plan_root_is_retained_and_corrected_consumers_agree(self):
        self.assertEqual(Path(plan.ROOT), revision.RETIRED)
        self.assertNotEqual(revision.ROOT, revision.RETIRED)
        self.assertEqual({bootstrap.ROOT, install.ROOT, handoff.ROOT, libraries.RECOVERY}, {revision.ROOT})

    def test_command_uses_fixed_credential_free_environment_and_refuses_failure(self):
        with patch.object(revision.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='metadata')) as run:
            self.assertEqual(revision._command(['systemctl', 'show', revision.SERVICE]), 'metadata')
        self.assertEqual(run.call_args.kwargs['env'], revision.ENV)
        with patch.object(revision.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='')):
            with self.assertRaises(ValueError): revision._command(['systemctl', 'show', revision.SERVICE])

    def test_saved_or_partial_proof_has_no_inspection_shortcut(self):
        with patch.object(revision, 'baseline', return_value={}) as live, \
                patch.object(revision, 'rejected', return_value={'retained_failure': True}), \
                patch.object(revision, 'retained', side_effect=[{'identity': 1}, {'identity': 2}]), \
                self.assertRaises(ValueError):
            revision.inspect()
        self.assertEqual(live.call_count, 2)
        with self.assertRaises(TypeError): revision.inspect({'passed': True})


class RejectedTests(unittest.TestCase):
    def setUp(self):
        fixture = RetainedTests('runTest')
        fixture._callCleanup = lambda function, *args, **kwargs: function(*args, **kwargs)
        self.addCleanup(fixture.doCleanups); fixture.setUp()
        self.root = fixture.root
        inventory = json.loads((self.root / 'installation-files.json').read_bytes())
        for i in range(321, 324):
            name = 'stage2/source_' + str(i) + '.py'; raw = ('synthetic source ' + str(i)).encode()
            save(self.root, name, raw); inventory['files'][name] = revision._sha(raw)
        raw = json.dumps(inventory).encode(); save(self.root, 'installation-files.json', raw)
        records = dict(revision.RECORDS, **{'installation-files.json': revision._sha(raw)})
        extra = {'.runtime/stage2/retained-failure.json': b'{"error_type":"ValueError"}',
            '.runtime/stage2/connection/service.log': b'private synthetic infrastructure metadata'}
        for name, raw in extra.items(): save(self.root, name, raw)
        (self.root / '.runtime/stage2/empty-producer').mkdir(mode=0o700)
        (self.root / '.runtime/stage2/no-cutoff-recovery-image-docker-config').mkdir(mode=0o700)
        self.enterContext(patch.object(revision, 'REJECTED', self.root))
        self.enterContext(patch.object(revision, 'REJECTED_RECORDS', records))
        self.enterContext(patch.object(revision, 'REJECTED_SOURCE_MAP',
            revision._sha(json.dumps(inventory['files'], sort_keys=True, allow_nan=False).encode())))
        self.enterContext(patch.object(revision, 'REJECTED_FILES', {n: revision._sha(v) for n, v in extra.items()}))
        self.enterContext(patch.object(revision, 'REJECTED_DIRECTORIES',
            ('.runtime/stage2/empty-producer', '.runtime/stage2/connection',
             '.runtime/stage2/no-cutoff-recovery-image-docker-config')))
        self.manager = dict(LoadState='loaded', ActiveState='failed', SubState='failed', MainPID='0',
            InvocationID=revision.REJECTED_INVOCATION, Result='exit-code', ExecMainCode='1',
            ExecMainStatus='1', ExecMainPID='1226555', NRestarts='0', Restart='no', Type='exec',
            RemainAfterExit='yes', WorkingDirectory=str(self.root))

    def tree(self):
        return revision._retained_tree(self.root, revision.REJECTED_RECORDS, 324,
            revision.REJECTED_SOURCE_MAP, revision.REJECTED_FILES, revision.REJECTED_DIRECTORIES)

    def test_exact_failure_tree_preserves_empty_directories_and_never_reads_credentials(self):
        actual = os.open
        def safe(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)) and Path(path).name == '.env':
                self.fail('Retired credential must stay unopened')
            return actual(path, *args, **kwargs)
        with patch.object(os, 'open', side_effect=safe):
            first = self.tree(); self.assertEqual(self.tree(), first)
        self.assertIn('.runtime/stage2/empty-producer', first['directories'])

    def test_missing_changed_or_extra_failure_evidence_refuses(self):
        path = self.root / '.runtime/stage2/retained-failure.json'
        raw = path.read_bytes(); path.write_bytes(b'{}')
        with self.assertRaises(ValueError): self.tree()
        path.write_bytes(raw)
        save(self.root, '.runtime/stage2/scored-trials/unapproved/started.json', b'{}')
        with self.assertRaises(ValueError): self.tree()

    def test_same_byte_replacement_changes_the_retained_identity(self):
        first = self.tree(); path = self.root / '.runtime/stage2/retained-failure.json'
        raw = path.read_bytes(); other = path.with_suffix('.old')
        path.rename(other); save(self.root, '.runtime/stage2/retained-failure.json', raw); other.unlink()
        self.assertNotEqual(self.tree(), first)

    def test_failure_evidence_remains_private_and_single_link(self):
        path = self.root / '.runtime/stage2/retained-failure.json'; path.chmod(0o644)
        with self.assertRaises(ValueError): self.tree()
        path.chmod(0o600); os.link(path, self.root / 'linked-evidence')
        with self.assertRaises(ValueError): self.tree()

    def test_exact_failed_invocation_not_default_dead_metadata_is_required(self):
        raw = '\n'.join(k + '=' + v for k, v in self.manager.items())
        with patch.object(revision, '_command', return_value=raw):
            self.assertEqual(revision._rejected_manager(), self.manager)
        for key, value in (('LoadState', 'not-found'), ('MainPID', '12'), ('NRestarts', '1'),
                ('InvocationID', 'a' * 32), ('ExecMainStatus', '0'), ('WorkingDirectory', '/other')):
            with self.subTest(key=key), patch.object(revision, '_command',
                    return_value='\n'.join(k + '=' + v for k, v in dict(self.manager, **{key: value}).items())):
                with self.assertRaises(ValueError): revision._rejected_manager()

    def test_actual_failed_process_or_unit_membership_refuses(self):
        proc = self.root / 'synthetic-proc'; proc.mkdir()
        with patch.object(revision, 'PROC', proc):
            revision._rejected_processes()
            save(proc, '123/cgroup', b'0::/system.slice/unrelated.service\n')
            (proc / '123/cwd').symlink_to(self.root)
            with self.assertRaises(ValueError): revision._rejected_processes()
            (proc / '123/cwd').unlink()
            save(proc, '123/cgroup', ('0::/system.slice/' + revision.REJECTED_UNIT + '\n').encode())
            with self.assertRaises(ValueError): revision._rejected_processes()

    def test_retained_image_is_inspected_not_rebuilt(self):
        image = dict(Id='sha256:' + 'a' * 64, Os='linux', Architecture='amd64',
            RootFS={'Type': 'layers', 'Layers': ['sha256:' + 'b' * 64]}, Config={'Entrypoint': ['python']})
        expected = revision._sha(json.dumps(image, sort_keys=True, allow_nan=False).encode())
        with patch.object(revision, 'REJECTED_IMAGES', {image['Id']: expected}), \
                patch.object(revision, '_command', return_value=json.dumps([image])) as command:
            self.assertEqual(revision._rejected_images(), {image['Id']: expected})
            args = command.call_args.args[0]
            self.assertEqual(args[-3:], ['image', 'inspect', image['Id']])
            image['Config']['Entrypoint'] = ['sh']
            command.return_value = json.dumps([image])
            with self.assertRaises(ValueError): revision._rejected_images()

    def test_last_native_observation_precedes_real_failed_tree_reads(self):
        order = []
        with patch.object(revision, '_rejected_manager', side_effect=lambda: order.append('manager') or self.manager), \
                patch.object(revision, '_rejected_processes', side_effect=lambda: order.append('process')), \
                patch.object(revision, '_rejected_images', side_effect=lambda: order.append('images') or {}), \
                patch.object(revision, '_retained_tree', side_effect=lambda *args: order.append('actual_tree') or {'files': {}}):
            self.assertFalse(revision.rejected()['qualification_passed'])
        self.assertEqual(order, ['manager', 'process', 'images', 'process', 'manager', 'actual_tree'])

    def test_complete_inspection_rejects_late_failed_evidence_replacement(self):
        with patch.object(revision, 'baseline', return_value={}), \
                patch.object(revision, 'retained', return_value={}), \
                patch.object(revision, 'rejected', side_effect=[{'identity': 1}, {'identity': 2}]):
            with self.assertRaises(ValueError): revision.inspect()


class OperatorPreservationTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        import no_cutoff_recovery_predecessor as operator
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.enterContext(patch.object(operator.launch, 'REPO', self.root))
        self.states = {
            '.runtime/netcup/retained-installation': {'intent.json': revision._sha(b'{}'), 'result.json': revision._sha(b'{}')},
            '.runtime/netcup/retained-refusal': {'intent.json': revision._sha(b'{}'), 'failure.json': revision._sha(b'{}')}}
        for name, leaves in self.states.items():
            for leaf in leaves: save(self.root, name + '/' + leaf, b'{}')
        self.enterContext(patch.object(revision, 'OPERATOR_STATES', self.states))

    def test_exact_both_states_are_reread_and_same_byte_replacement_is_detectable(self):
        first = install._retained_operator_states()
        name = next(iter(self.states)); p = self.root / name / 'intent.json'
        p.rename(p.with_suffix('.retained')); save(self.root, name + '/intent.json', b'{}')
        with self.assertRaises(ValueError): install._retained_operator_states()
        p.with_suffix('.retained').unlink()
        self.assertNotEqual(install._retained_operator_states(), first)

    def test_bytes_private_mode_and_extra_receiver_cannot_be_hidden(self):
        name = list(self.states)[1]; p = self.root / name / 'failure.json'
        p.write_bytes(b'{ }')
        with self.assertRaises(ValueError): install._retained_operator_states()
        p.write_bytes(b'{}'); p.chmod(0o644)
        with self.assertRaises(ValueError): install._retained_operator_states()
        p.chmod(0o600); save(self.root, name + '/receiver.json', b'{}')
        with self.assertRaises(ValueError): install._retained_operator_states()

    def test_replaced_file_during_read_is_rejected(self):
        import no_cutoff_recovery_predecessor as operator
        original = operator.launch._raw; replaced = False
        def read(name, digest=None):
            nonlocal replaced
            raw = original(name, digest)
            if not replaced:
                p = self.root / name; q = p.with_suffix('.retained')
                p.rename(q); save(self.root, name, raw); q.unlink(); replaced = True
            return raw
        with patch.object(operator.launch, '_raw', side_effect=read), self.assertRaises(ValueError):
            install._retained_operator_states()
