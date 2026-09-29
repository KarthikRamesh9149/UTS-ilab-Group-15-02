"""Actual synthetic private files/archive; Git/native observations are mocked."""
from copy import deepcopy
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import no_cutoff_recovery_diagnosis as diagnosis
import no_cutoff_recovery_plan as plan
import no_cutoff_final_archive as archive
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_reporting as launch
import test_no_cutoff_final_export as fixtures


class RecoveryDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.PublicExportTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.folder = self.f.folder; self.commit = self.f.commit
        data = self.f.f.data
        self.targets = tuple((i + 1, r['task_id'], r['result_sha256']) for i, r in enumerate(data['rows'][:3]))
        self.enterContext(patch.object(plan, 'TARGETS', self.targets))
        # The existing full89 fixture pins three real infrastructure source
        # files, with synthetic result identities. Never a native attestation.
        sources = {n: h for n, h in data['supporting_file_sha256'].items() if n.startswith('stage2/') and n.endswith('.py')}
        self.sources = dict(list(sources.items())[:3])
        self.enterContext(patch.object(diagnosis, 'EXECUTION_SOURCES', self.sources))
        for row in data['rows'][:3]:
            self.f.f.members[phase.RT + 'scored-trials/' + row['trial_id'] + '/compose.json'] = b'{"synthetic":true}'
        self.f.seed_backup()
        captured = export._read_backup(self.f.bindings)
        public = export._projection(captured)
        for name, raw in public.items(): self.f.save(export.DESTINATION + '/' + name, raw)
        state = {'intent.json': b'{"synthetic":"intent"}', 'result.json': b'{"synthetic":"result"}'}
        for name, raw in state.items(): self.f.save(export.STATE + '/' + name, raw)
        (self.root / export.STATE).chmod(0o700)
        original_git = self.f.git.side_effect
        public_paths = {export.DESTINATION + '/' + n: raw for n, raw in public.items()}
        self.f.git.side_effect = lambda operation, ref: public_paths[ref.split(':', 1)[1]] if ref.split(':', 1)[1] in public_paths else original_git(operation, ref)
        self.enterContext(patch.object(diagnosis, 'PUBLIC_FILES', {n: export._hash(raw) for n, raw in public.items()}))
        self.enterContext(patch.object(diagnosis, 'EXPORT_STATE', {n: export._hash(raw) for n, raw in state.items()}))
        for name, value in (('ARCHIVE_SHA256', captured['backup']['receipt']['sha256']),
                ('SNAPSHOT_SHA256', captured['backup']['snapshot_file_sha256']),
                ('BACKUP_SHA256', captured['hashes'][receiver.DESTINATION + '/backup.json'])):
            self.enterContext(patch.object(diagnosis, name, value))
        diagnosis_raw = {'stage2/' + n: ('synthetic current diagnosis ' + n).encode() for n in diagnosis.SOURCE_FILES}
        for name, raw in diagnosis_raw.items(): self.f.save(name, raw)
        self.bindings = {**self.f.bindings,
            'diagnosis_local': {n: export._hash(raw) for n, raw in diagnosis_raw.items()}}
        self.enterContext(patch.object(diagnosis, '_prepare', return_value=(self.bindings, {'synthetic_plan': True})))
        self.loaded = self.enterContext(patch.object(diagnosis, '_loaded'))
        self.f.collect.side_effect = AssertionError('Diagnosis must not invoke a native collector')
        self.enterContext(patch.object(launch, '_command', side_effect=AssertionError('No SSH')))
        self.enterContext(patch.object(receiver, 'backup', side_effect=AssertionError('No backup')))
        self.capture = captured

    def inspect(self):
        return diagnosis.inspect(self.commit)

    def test_real_archive_read_no_native_call_no_writes_and_unknown_cause(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        with patch.object(archive, 'verify_archive', wraps=archive.verify_archive) as verify:
            result = self.inspect()
        verify.assert_called_once(); self.f.collect.assert_not_called()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})
        self.assertTrue(result['current_archive_verified'])
        for key in ('fresh_native_audit_performed', 'native_operation_performed', 'archive_created',
                'original_evidence_changed', 'paid_launch_ready', 'task_solution_or_model_exchange_parsed'):
            self.assertIs(result[key], False)
        self.assertEqual(result['recovery_attempts_started'], 0)
        self.assertEqual(len(result['original_rows']), 3)
        for row in result['original_rows']:
            self.assertEqual(row['established_failure_stage'], 'prepare_environment_before_return')
            self.assertFalse(row['agent_setup_entered'])
            self.assertFalse(row['lower_level_cause_established'])
            self.assertFalse(row['command_exit_code_retained'])
            self.assertIsNone(row['original_reward'])

    def test_only_six_allowlisted_archive_members_are_parsed(self):
        opened = []; original = tarfile.TarFile.extractfile
        def observe(packed, member):
            opened.append(member.name if hasattr(member, 'name') else member)
            return original(packed, member)
        with patch.object(tarfile.TarFile, 'extractfile', observe):
            selected, _ = diagnosis._selected(self.capture)
        self.assertEqual(set(opened), set(selected))
        self.assertEqual(len(opened), 6)
        self.assertTrue(all(n in self.sources or n.endswith('/result.json') for n in opened))

    def test_original_archive_hash_change_refused(self):
        path = self.folder / 'evidence.tar.gz'; raw = path.read_bytes()
        path.write_bytes(raw + b'x')
        with self.assertRaises(ValueError): self.inspect()

    def test_wrong_archive_snapshot_or_backup_anchor_refused(self):
        for name in ('ARCHIVE_SHA256', 'SNAPSHOT_SHA256', 'BACKUP_SHA256'):
            with patch.object(diagnosis, name, '0' * 64):
                with self.assertRaises(ValueError): self.inspect()

    def test_wrong_original_source_binding_refused(self):
        changed = deepcopy(self.capture)
        changed['data']['supporting_file_sha256'][next(iter(self.sources))] = '0' * 64
        with self.assertRaises(ValueError): diagnosis._selected(changed)

    def test_actual_strict_verifier_failure_is_not_replaced_by_saved_flag(self):
        with patch.object(archive, 'verify_archive', side_effect=ValueError('synthetic refusal')):
            with self.assertRaises(ValueError): self.inspect()

    def test_actual_verification_must_equal_retained_receipt(self):
        with patch.object(archive, 'verify_archive', return_value={'saved_flag': True}):
            with self.assertRaises(ValueError): self.inspect()

    def test_public_bytes_and_current_committed_bytes_both_required(self):
        public = self.root / export.DESTINATION / 'summary.json'
        original = public.read_bytes(); public.write_bytes(original + b' ')
        with self.assertRaises(ValueError): self.inspect()
        public.write_bytes(original)
        git = self.f.git.side_effect
        self.f.git.side_effect = lambda op, ref: b'changed' if ref.endswith('/summary.json') else git(op, ref)
        with self.assertRaises(ValueError): self.inspect()

    def test_extra_public_or_private_state_refuses(self):
        for folder in (self.root / export.DESTINATION, self.root / export.STATE, self.folder):
            path = folder / 'unexpected'; path.write_bytes(b'')
            with self.assertRaises(ValueError): self.inspect()
            path.unlink()  # Only this newly created temporary fixture file.

    def test_private_archive_symlink_and_readable_permissions_refused(self):
        path = self.folder / 'evidence.tar.gz'; path.chmod(0o644)
        with self.assertRaises(ValueError): self.inspect()
        path.chmod(0o600)
        other = self.folder / 'synthetic-original'; path.rename(other); path.symlink_to(other)
        with self.assertRaises(ValueError): self.inspect()

    def test_late_archive_and_public_mutation_refused(self):
        original = diagnosis._rows
        for path in (self.folder / 'evidence.tar.gz', self.root / export.DESTINATION / 'trials.json'):
            before = path.read_bytes()
            def changed(*args):
                result = original(*args); path.write_bytes(before + b' '); return result
            with patch.object(diagnosis, '_rows', side_effect=changed):
                with self.assertRaises(ValueError): self.inspect()
            path.write_bytes(before)

    def test_final_bound_source_recheck_is_required(self):
        self.f.recheck.side_effect = ValueError('synthetic source mutation')
        with self.assertRaises(ValueError): self.inspect()

    def test_current_diagnosis_bindings_are_separate_and_reread_last(self):
        self.assertFalse(set(self.bindings['diagnosis_local']) & set(self.bindings['local']))
        original = diagnosis._rows
        path = self.root / 'stage2/no_cutoff_recovery_plan.py'
        def changed(*args):
            result = original(*args); path.write_bytes(b'changed current plan'); return result
        with patch.object(diagnosis, '_rows', side_effect=changed):
            with self.assertRaises(ValueError): self.inspect()

    def test_late_loaded_module_refusal_prevents_diagnosis(self):
        self.loaded.side_effect = ValueError('synthetic late unbound import')
        with self.assertRaises(ValueError): self.inspect()

    def test_changed_result_presence_phase_error_or_cleanup_refuses(self):
        selected, files = diagnosis._selected(self.capture)
        key = next(n for n in selected if n.endswith('/result.json'))
        for mutate in (lambda r: r.update(environment_preparation={'status': 'refreshed'}),
                lambda r: r.update(environment_preparation=None),
                lambda r: r.update(status='verified'), lambda r: r.update(agent_error_type='TimeoutError'),
                lambda r: r.update(model_revoked=1), lambda r: r.update(containers_removed=False),
                lambda r: r.update(cleanup_errors=['synthetic']),
                lambda r: r['phase_seconds'].update(agent=1.0)):
            values = dict(selected); result = json.loads(values[key]); mutate(result)
            values[key] = json.dumps(result).encode()
            with self.assertRaises(ValueError): diagnosis._rows(self.capture, values, files)

    def test_missing_reward_is_not_zero_and_changed_timing_refuses(self):
        selected, files = diagnosis._selected(self.capture)
        for change in ({'reward': 0.0}, {'model_requests': 1}, {'agent_seconds': 0.0}, {'setup_seconds': 99.0}):
            changed = deepcopy(self.capture); changed['data']['rows'][0].update(change)
            with self.assertRaises(ValueError): diagnosis._rows(changed, selected, files)

    def test_unexpected_log_inventory_needs_separate_inspection(self):
        selected, files = diagnosis._selected(self.capture)
        files[next(iter(files))].add('agent/secret-output.txt')
        with self.assertRaises(ValueError): diagnosis._rows(self.capture, selected, files)

    def test_result_duplicate_json_fields_refused(self):
        selected, files = diagnosis._selected(self.capture)
        key = next(n for n in selected if n.endswith('/result.json'))
        selected[key] = b'{"status":"setup_failed","status":"setup_failed"}'
        with self.assertRaises(ValueError): diagnosis._rows(self.capture, selected, files)

    def test_unknown_fields_are_not_projected(self):
        selected, files = diagnosis._selected(self.capture)
        key = next(n for n in selected if n.endswith('/result.json'))
        result = json.loads(selected[key]); result['untrusted'] = 'SENSITIVE_SENTINEL'
        selected[key] = json.dumps(result).encode()
        output = diagnosis._rows(self.capture, selected, files)
        self.assertNotIn('SENSITIVE_SENTINEL', json.dumps(output))


class DiagnosisPreparationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]; self.commit = 'a' * 40
        self.raw = {'stage2/' + n: (self.root / 'stage2' / n).read_bytes() for n in diagnosis.SOURCE_FILES}
        self.raw[diagnosis.MANIFEST_FILE] = (self.root / diagnosis.MANIFEST_FILE).read_bytes()
        self.enterContext(patch.object(export, '_operator', return_value={
            'local': {}, 'native': {}, 'reporting': {}, 'commit': self.commit}))
        self.loaded = self.enterContext(patch.object(diagnosis, '_loaded'))
        self.enterContext(patch.object(launch, 'REPO', self.root))
        self.enterContext(patch.object(launch, '_raw', side_effect=lambda n, expected=None: self.raw[n]))
        self.git = self.enterContext(patch.object(launch, '_git', side_effect=lambda op, ref: self.raw[ref.split(':', 1)[1]]))

    def test_every_new_source_test_and_protocol_is_bound(self):
        bindings, schedule = diagnosis._prepare(self.commit)
        self.assertEqual(set(bindings['diagnosis_local']), set(self.raw))
        self.assertEqual(bindings['local'], {})
        self.loaded.assert_called_once_with(bindings)
        self.assertEqual(schedule['intended'], 3)
        self.assertFalse(schedule['paid_launch_ready'])

    def test_uncommitted_new_source_refused(self):
        original = self.git.side_effect
        self.git.side_effect = lambda op, ref: b'changed' if ref.endswith('no_cutoff_recovery_plan.py') else original(op, ref)
        with self.assertRaises(ValueError): diagnosis._prepare(self.commit)

    def test_other_module_origin_refused(self):
        with patch.object(diagnosis, '__file__', '/another/no_cutoff_recovery_diagnosis.py'):
            with self.assertRaises(ValueError): diagnosis._prepare(self.commit)

    def test_other_plan_origin_refused(self):
        with patch.object(plan, '__file__', '/another/no_cutoff_recovery_plan.py'):
            with self.assertRaises(ValueError): diagnosis._prepare(self.commit)

    def test_manifest_must_match_current_commit(self):
        original = self.git.side_effect
        self.git.side_effect = lambda op, ref: b'changed' if ref.endswith('input_manifest.json') else original(op, ref)
        with self.assertRaises(ValueError): diagnosis._prepare(self.commit)

    def test_original_model_dependency_cannot_silently_change(self):
        with patch.object(export, '_operator', return_value={'local': {}, 'native': {
                'stage2/model_protocol.py': '0' * 64}, 'reporting': {}, 'commit': self.commit}):
            with self.assertRaises(ValueError): diagnosis._prepare(self.commit)

    def test_no_native_or_archive_writer_entry(self):
        import ast
        tree = ast.parse(Path(diagnosis.__file__).read_text())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        forbidden = {'collect', 'backup', 'deploy', 'extract', 'extractall', 'save', 'Popen', 'run'}
        self.assertFalse([n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr in forbidden])
        self.assertEqual([n.name for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')], ['inspect'])


class LoadedDiagnosisTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); (self.root / 'stage2').mkdir()
        self.source = self.root / 'stage2/recovery_fixture.py'
        self.source.write_bytes(b'# synthetic source\n')
        self.source.chmod(0o600)
        self.enterContext(patch.object(launch, 'REPO', self.root))
        self.bindings = dict(native={}, reporting={}, diagnosis_local={
            'stage2/recovery_fixture.py': diagnosis._hash(self.source.read_bytes())})

    def check(self, modules):
        with patch.object(diagnosis.sys, 'modules', modules):
            return diagnosis._loaded(self.bindings)

    def test_actual_bound_origin_and_bytes_pass(self):
        modules = {'recovery_fixture': SimpleNamespace(__file__=str(self.source))}
        self.assertEqual(self.check(modules), {'stage2/recovery_fixture.py'})

    def test_unbound_module_refused(self):
        self.bindings['diagnosis_local'] = {}
        with self.assertRaises(ValueError): self.check({'alias': SimpleNamespace(__file__=str(self.source))})

    def test_changed_bytes_refused(self):
        self.source.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.check({'recovery_fixture': SimpleNamespace(__file__=str(self.source))})

    def test_other_checkout_or_missing_origin_refused(self):
        for module in (SimpleNamespace(__file__='/other/stage2/recovery_fixture.py'), SimpleNamespace()):
            with self.assertRaises(ValueError): self.check({'recovery_fixture': module})
