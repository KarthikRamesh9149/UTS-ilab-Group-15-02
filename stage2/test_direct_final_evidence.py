"""Original-native authentication fixtures, with no SSH, Docker or model calls."""
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import deadline_evidence_freeze as original
import direct_final_evidence as evidence
import export_deadline_custom as exporter
from portable_custom_policy import fingerprint
from test_deadline_evidence_freeze import EvidenceFixture


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.root = self.base / 'final'; self.root.mkdir()
        self.fixture = EvidenceFixture(self.root)
        self.enterContext(patch.object(exporter, 'OUTPUT', self.fixture.output))
        self.enterContext(patch.object(original, '_read_originals',
            side_effect=lambda: deepcopy(self.fixture.data)))
        self.document = original.capture(self.root)
        self.native = self.enterContext(patch.object(evidence, '_native_audit',
            side_effect=lambda: deepcopy(self.fixture.data)))
        self.files = self.enterContext(patch.object(evidence, '_check_originals'))
        self.roots = {'portable': self.base / 'old-portable', 'deadline': self.base / 'old-deadline'}
        self.enterContext(patch.object(evidence, 'ROOTS', self.roots))

    def test_fresh_original_audit_and_both_file_checks_required(self):
        record = evidence.authenticate(self.root, self.document)
        self.native.assert_called_once_with()
        self.assertEqual(self.files.call_count, 2)
        self.assertEqual(record['candidate_sha256'], fingerprint(self.document))
        self.assertEqual(record['original_audit_sha256'], self.document['original_audit_sha256'])
        self.assertFalse(record['paid_launch_ready'])
        counts = {generation: sum(name.endswith('/result.json') for name in files)
            for generation, files in record['original_files'].items()}
        self.assertEqual(counts, {'portable': 60, 'deadline': 20})
        self.assertEqual(evidence.recheck(self.root, self.document, record)['selected'], 'C3')
        self.native.assert_called_once()  # Recheck never takes collector locks again.

    def test_c0_winner_retains_its_original_source_generation(self):
        self.fixture.data['rows'][15]['reward'] = 0
        document = original.capture(self.root)
        record = evidence.authenticate(self.root, document)
        self.assertEqual(evidence.recheck(self.root, document, record)['selected'], 'C0')
        self.assertEqual(document['selected_execution']['original_generation'], 'portable')

    def test_every_original_source_qualification_registration_and_result_is_bound(self):
        record = evidence.authenticate(self.root, self.document)
        parent = self.document['candidate']['parent_evidence']
        portable = record['original_files']['portable']; deadline = record['original_files']['deadline']
        self.assertEqual(portable['.runtime/stage2/portable-qualification.json'], parent['qualification_file_sha256'])
        for condition in ('C0', 'C1', 'C2'):
            self.assertEqual(portable[f'.runtime/stage2/portable-development-blocks/{condition}.json'],
                parent['registration_bindings'][condition]['file_sha256'])
        self.assertEqual(deadline['.runtime/stage2/deadline-qualification.json'],
            self.fixture.proof['qualification_file_sha256'])
        for generation in ('portable', 'deadline'):
            self.assertEqual(record['original_files'][generation]['.runtime/stage2/python-runtime.tar.gz'],
                evidence.PYTHON_SHA256)
        self.assertTrue(all('token' not in name and not name.endswith('.env')
            for files in record['original_files'].values() for name in files))

    def test_changed_original_code_blocks_before_executing_original_interpreter(self):
        self.files.side_effect = ValueError('changed')
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)
        self.native.assert_not_called()

    def test_original_files_are_rechecked_after_native_audit(self):
        self.files.side_effect = [None, ValueError('changed during audit')]
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)
        self.native.assert_called_once()

    def test_operator_anchor_or_selection_code_drift_blocks_before_native_audit(self):
        for relative in (original.ANCHOR_PATHS[0], 'stage2/deadline_final_selection.py'):
            path = self.root / relative; before = path.read_bytes()
            path.write_bytes(before + b' ')
            with self.subTest(path=relative), self.assertRaises(ValueError):
                evidence.authenticate(self.root, self.document)
            self.native.assert_not_called()
            path.write_bytes(before)

    def test_current_native_audit_not_just_boolean_checks_must_match(self):
        for change in ('reward', 'runtime', 'requests', 'service', 'partial', 'checks', 'qualification'):
            data = deepcopy(self.fixture.data)
            if change == 'reward': data['rows'][0]['reward'] = 0
            elif change == 'runtime': data['rows'][0]['agent_seconds'] += 1
            elif change == 'requests': data['rows'][0]['model_requests'] += 1
            elif change == 'service': data['service']['ActiveState'] = 'active'
            elif change == 'partial': data['rows'].pop()
            elif change == 'checks': data['audit_checks']['cleanup_and_revocation'] = False
            else: data['qualification_sha256'] = '7' * 64
            self.native.side_effect = lambda: data
            with self.subTest(change=change), self.assertRaises(ValueError):
                evidence.authenticate(self.root, self.document)

    def test_collected_timestamp_is_observation_not_candidate_identity(self):
        self.fixture.data['collected_utc'] = '2026-09-28T01:00:00Z'
        record = evidence.authenticate(self.root, self.document)
        self.assertEqual(record['candidate_sha256'], fingerprint(self.document))

    def test_source_projection_cannot_replace_original_qualified_source(self):
        document = deepcopy(self.document)
        document['candidate']['c3_sources']['export_deadline_custom.py'] = '9' * 64
        document['selected_execution'] = original._execution(document['candidate'])
        with self.assertRaises(ValueError): evidence.authenticate(self.root, document)
        self.native.assert_not_called()

    def test_operator_source_mutation_during_audit_rejected(self):
        def audit():
            (self.root / 'stage2/deadline_evidence_freeze.py').write_text('# changed')
            return deepcopy(self.fixture.data)
        self.native.side_effect = audit
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)

    def test_native_audit_error_and_unexpected_private_metadata_not_forwarded(self):
        self.native.side_effect = ValueError('synthetic native audit failed')
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)
        data = dict(deepcopy(self.fixture.data), raw_messages=['not allowed'])
        self.native.side_effect = lambda: data
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)

    def test_recheck_binds_all_fields_without_self_granted_paid_admission(self):
        record = evidence.authenticate(self.root, self.document)
        for field in record:
            changed = deepcopy(record)
            if field == 'paid_launch_ready': changed[field] = True
            elif isinstance(changed[field], dict): changed[field] = {}
            else: changed[field] = 'mutated'
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.recheck(self.root, self.document, changed)
        with self.assertRaises(ValueError):
            evidence.recheck(self.root, self.document, dict(record, trusted=True))

    def test_operator_stop_in_either_original_generation_prevents_progression(self):
        record = evidence.authenticate(self.root, self.document)
        for name, root in self.roots.items():
            marker = root / '.runtime/stage2/operator-stop-request.json'
            marker.parent.mkdir(parents=True); marker.write_text('{}')
            with self.subTest(generation=name), self.assertRaises(ValueError):
                evidence.recheck(self.root, self.document, record)
            with self.subTest(generation=name, authenticate=True), self.assertRaises(ValueError):
                evidence.authenticate(self.root, self.document)
            marker.unlink()
            marker.symlink_to(root / 'missing')
            with self.subTest(generation=name, dangling=True), self.assertRaises(ValueError):
                evidence.recheck(self.root, self.document, record)
            marker.unlink()

    def test_no_new_files_created_or_candidate_modified(self):
        before = deepcopy(self.document)
        paths = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob('*'))
        evidence.authenticate(self.root, self.document)
        self.assertEqual(self.document, before)
        self.assertEqual(sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob('*')), paths)

    def test_cannot_authenticate_inside_original_study(self):
        self.roots['deadline'] = self.root
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)
        self.native.assert_not_called()


class FileAndProcessTests(unittest.TestCase):
    def test_file_bindings_reject_drift_missing_and_symlinked_components(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); nested = root / 'files'; nested.mkdir()
            path = nested / 'result.json'; path.write_text('synthetic')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            evidence._check_files(root, {'files/result.json': digest})
            path.write_text('changed')
            with self.assertRaises(ValueError): evidence._check_files(root, {'files/result.json': digest})
            path.unlink()
            with self.assertRaises(ValueError): evidence._check_files(root, {'files/result.json': digest})
            path.symlink_to(root / 'missing')
            with self.assertRaises(ValueError): evidence._check_files(root, {'files/result.json': digest})
            path.unlink(); path.write_text('synthetic')
            nested.rename(root / 'moved'); nested.symlink_to(root / 'moved')
            with self.assertRaises(ValueError): evidence._check_files(root, {'files/result.json': digest})
            alias = root / 'root-alias'; alias.symlink_to(root)
            with self.assertRaises(ValueError): evidence._check_files(alias, {'files/result.json': digest})
            for value in (None, {}, {'../outside': digest}, {'files/result.json': 'bad'}):
                with self.subTest(value=value), self.assertRaises(ValueError): evidence._check_files(root, value)

    def test_both_original_deployments_are_checked_not_caller_paths(self):
        bindings = {'portable': {'a.py': 'a' * 64}, 'deadline': {'b.py': 'b' * 64}}
        with patch.object(evidence, '_check_files') as check:
            evidence._check_originals(bindings)
            self.assertEqual(check.call_args_list[0].args, (evidence.ROOTS['portable'], bindings['portable']))
            self.assertEqual(check.call_args_list[1].args, (evidence.ROOTS['deadline'], bindings['deadline']))
            for invalid in ({}, {'deadline': bindings['deadline']}, dict(bindings, extra={})):
                with self.assertRaises(ValueError): evidence._check_originals(invalid)

    def test_native_reader_uses_original_interpreter_and_collector_not_ssh(self):
        with patch.object(evidence.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='{}')) as run:
            self.assertEqual(evidence._native_audit(), {})
            args, kwargs = run.call_args
            self.assertEqual(args[0][:3], [str(evidence.CURRENT / '.venv/bin/python'), '-B', '-c'])
            self.assertEqual(args[0][3], original._original_program())
            self.assertEqual(kwargs['cwd'], evidence.CURRENT)
            self.assertEqual(kwargs['env']['PYTHONPATH'], str(evidence.CURRENT / 'stage2'))
            self.assertEqual(kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertNotIn('PYTHONHOME', kwargs['env'])
            self.assertIn('lock_all(stack,root)', args[0][3])

    def test_failed_native_reader_does_not_echo_private_stdout_or_stderr(self):
        for code, stdout in ((1, 'private output'), (0, 'private output')):
            with patch.object(evidence.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=code, stdout=stdout, stderr='private error')):
                with self.assertRaises(ValueError) as error: evidence._native_audit()
                self.assertNotIn('private output', str(error.exception))
                self.assertNotIn('private error', str(error.exception))

    def test_missing_interpreter_and_timeout_do_not_echo_private_process_output(self):
        for failure in (OSError('private path'), subprocess.TimeoutExpired(
                ['private command'], 120, output='private output', stderr='private error')):
            with patch.object(evidence.subprocess, 'run', side_effect=failure):
                with self.assertRaises(ValueError) as error: evidence._native_audit()
                self.assertNotIn('private', str(error.exception))


if __name__ == '__main__':
    unittest.main()
