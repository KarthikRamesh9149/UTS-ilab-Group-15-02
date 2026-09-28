"""Mocked native/old-anchor readers, real revised anchor files; no paid calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import direct_final_evidence as original
import export_no_cutoff_custom as exporter
import no_cutoff_custom_policy as revision
import no_cutoff_evidence_freeze as freeze
import no_cutoff_final_candidate as candidate
import no_cutoff_final_evidence as evidence
from test_no_cutoff_evidence_freeze import snapshot
from test_no_cutoff_final_candidate import FinalistFixture


def original_anchors(document):
    """Synthetic predecessor projections; not a native authentication record."""
    value = document['candidate']
    return {'qualification.json': dict(sources=value['c3_sources'], dependencies=value['c3_dependencies'],
        qualification_sha256=value['c3_qualification_sha256'], qualification_file_sha256='a' * 64,
        private_copies_verified={'deadline-credit-policy.json': 'b' * 64}),
        'registration-c3.json': dict(registration_sha256=value['c3_registration_sha256'],
            registration_file_sha256='c' * 64),
        'parent.json': dict(evidence=value['parent_evidence'], file_sha256='d' * 64)}


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'final'; self.root.mkdir()
        self.f = FinalistFixture(self, self.root)
        self.data = snapshot(self.f)
        self.document = self.f.build()
        self.document['revision_audit_sha256'] = revision.fingerprint(
            {k: v for k, v in self.data.items() if k != 'collected_utc'})
        self.enterContext(patch.object(exporter, 'OUTPUT', self.f.output))
        self.enterContext(patch.object(exporter, 'ORIGINAL_FREEZE_SHA256', revision.fingerprint(self.f.original)))
        self.anchors = self.enterContext(patch.object(original.original, '_anchors',
            return_value=original_anchors(self.f.original)))
        # Predecessor anchor validation has its own unchanged test module.
        # This fixture keeps one extra real file to exercise its composition
        # with the new revised-finalist anchor set and both integrity passes.
        path = self.root / 'stage2/synthetic-original-selection.py'; path.write_text('# Test only\n')
        self.extra = {'stage2/synthetic-original-selection.py': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.old_operator = self.enterContext(patch.object(original, '_operator_files', return_value=self.extra))
        self.native = self.enterContext(patch.object(evidence, '_native_audit', side_effect=lambda files: deepcopy(self.data)))
        self.original_files = self.enterContext(patch.object(original, '_check_originals'))
        self.roots = {'portable': self.base / 'portable', 'deadline': self.base / 'deadline'}
        self.enterContext(patch.object(original, 'ROOTS', self.roots))
        self.current = self.base / 'revision'
        self.enterContext(patch.object(evidence, 'CURRENT', self.current))
        self.real_check_files = original._check_files
        self.file_check = self.enterContext(patch.object(original, '_check_files', side_effect=self.check_files))

    def check_files(self, root, files):
        if Path(root) != self.current:
            self.real_check_files(root, files)

    def test_fresh_collector_binds_all_hundred_results_and_actual_revision(self):
        record = evidence.authenticate(self.root, self.document)
        self.native.assert_called_once_with(record['revision_files'])
        self.assertEqual(self.original_files.call_count, 2)
        self.assertEqual(record['kind'], evidence.KIND)
        self.assertEqual(record['candidate_sha256'], revision.fingerprint(self.document))
        self.assertEqual(record['original_candidate_sha256'], revision.fingerprint(self.f.original))
        self.assertFalse(record['paid_launch_ready'])
        # Native producer results are evidence, not additional benchmark cells.
        prefix = '.runtime/stage2/scored-trials/'
        counts = {name: sum(p.startswith(prefix) for p in bindings)
            for name, bindings in record['original_files'].items()}
        self.assertEqual(counts, {'portable': 60, 'deadline': 20})
        self.assertEqual(sum(p.startswith(prefix) for p in record['revision_files']), 20)
        for row in self.document['validation_summary']['rows']:
            self.assertEqual(record['revision_files'][prefix + row['trial_id'] + '/result.json'], row['result_sha256'])
        selected = evidence.recheck(self.root, self.document, record)
        self.assertEqual(selected['harness'], 'C0-NC')
        self.assertEqual(selected['candidate_version'], 'stage2-candidate-0.5.0')
        self.assertEqual(self.document['validation_summary']['passes'], 12)
        self.assertEqual(self.document['original_candidate']['candidate']['selection']['selected'], 'C0')
        self.native.assert_called_once()  # Under-lock recheck never reacquires collector locks.

    def test_every_revised_source_input_producer_and_runtime_is_bound(self):
        record = evidence.authenticate(self.root, self.document)
        files = record['revision_files']
        for name, digest in self.f.proof['sources'].items():
            self.assertEqual(files['stage2/' + name], digest)
        for name, digest in self.f.proof['evidence_files'].items():
            self.assertEqual(files[name], digest)
        for name in candidate.PRIVATE_FILES:
            self.assertEqual(files['.runtime/stage2/' + name],
                self.document['anchor_files'][candidate.PRIVATE + '/.runtime/stage2/' + name])
        self.assertEqual(files['.runtime/stage2/no-cutoff-development-blocks/C0-NC.json'],
            self.f.registration['registration_file_sha256'])
        self.assertEqual(files['.runtime/stage2/python-runtime.tar.gz'], revision.PYTHON_SHA256)
        self.assertEqual({k: record['operator_files'][k] for k in self.extra}, self.extra)
        self.old_operator.assert_called_once_with(self.f.original)
        self.anchors.assert_called_once_with(self.root)

    def test_native_files_checked_before_and_after_actual_reader(self):
        order = []
        def files(root, bindings):
            order.append('revision' if Path(root) == self.current else 'operator')
            self.check_files(root, bindings)
        self.file_check.side_effect = files
        self.original_files.side_effect = lambda value: order.append('original')
        self.native.side_effect = lambda value: (order.append('audit'), deepcopy(self.data))[1]
        evidence.authenticate(self.root, self.document)
        self.assertEqual(order, ['operator', 'original', 'revision', 'audit', 'operator', 'original', 'revision'])

    def test_mutated_original_or_revision_refused_before_native_code_execution(self):
        for source in ('original', 'revision'):
            if source == 'original': self.original_files.side_effect = ValueError('changed original source')
            else:
                self.original_files.side_effect = None
                def changed(root, files):
                    if Path(root) == self.current: raise ValueError('changed revision or result')
                    self.check_files(root, files)
                self.file_check.side_effect = changed
            with self.subTest(source=source), self.assertRaises(ValueError):
                evidence.authenticate(self.root, self.document)
        self.native.assert_not_called()

    def test_mutated_native_evidence_during_audit_rejected(self):
        for source in ('original', 'revision'):
            self.original_files.side_effect = None
            self.file_check.side_effect = self.check_files
            def mutate(files):
                if source == 'original': self.original_files.side_effect = ValueError('changed during audit')
                else:
                    def changed(root, bindings):
                        if Path(root) == self.current: raise ValueError('changed during audit')
                        self.check_files(root, bindings)
                    self.file_check.side_effect = changed
                return deepcopy(self.data)
            self.native.side_effect = mutate
            with self.subTest(source=source), self.assertRaises(ValueError):
                evidence.authenticate(self.root, self.document)
        self.assertEqual(self.native.call_count, 2)

    def test_local_anchor_or_freeze_code_drift_refused_before_native_audit(self):
        for relative in (candidate.RESULTS + '/qualification.json',
                candidate.PRIVATE + '/C0-NC.json', candidate.ORIGINAL,
                'stage2/no_cutoff_evidence_freeze.py', next(iter(self.extra))):
            path = self.root / relative; before = path.read_bytes(); path.write_bytes(before + b' ')
            with self.subTest(path=relative), self.assertRaises(ValueError):
                evidence.authenticate(self.root, self.document)
            path.write_bytes(before)
        self.native.assert_not_called()

    def test_operator_source_drift_during_audit_is_not_accepted(self):
        def mutate(files):
            (self.root / 'stage2/no_cutoff_evidence_freeze.py').write_text('# Changed during reader')
            return deepcopy(self.data)
        self.native.side_effect = mutate
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)

    def test_fresh_rows_and_audit_must_match_not_just_passed_flags(self):
        for change in ('reward', 'duration', 'requests', 'result', 'active', 'partial', 'revocation',
                'cleanup', 'qualification', 'source', 'binding', 'private', 'private-row', 'missing-phase'):
            data = deepcopy(self.data)
            if change == 'reward': data['rows'][0]['reward'] = 0
            elif change == 'duration': data['rows'][0]['agent_seconds'] += 1
            elif change == 'requests':
                data['rows'][0]['model_requests'] += 1; data['rows'][0]['other_unaccepted_requests'] += 1
            elif change == 'result': data['rows'][0]['result_sha256'] = '0' * 64
            elif change == 'active': data['service']['ActiveState'] = 'active'
            elif change == 'partial': data['rows'].pop()
            elif change == 'revocation': data['rows'][0]['model_revoked'] = False
            elif change == 'cleanup': data['audit_checks']['cleanup_and_revocation'] = False
            elif change == 'qualification': data['qualification_sha256'] = '0' * 64
            elif change == 'source': data['sources']['no_cutoff_custom_agent.py'] = '0' * 64
            elif change == 'binding': data['bindings']['.runtime/stage2/no-cutoff-runtime.json'] = '0' * 64
            elif change == 'private': data['raw_response'] = 'Not allowed'
            elif change == 'private-row': data['rows'][0]['command'] = 'Not allowed'
            else: data['rows'][0]['agent_seconds'] = None
            self.native.side_effect = lambda files: data
            with self.subTest(change=change), self.assertRaises(ValueError):
                evidence.authenticate(self.root, self.document)

    def test_observation_timestamp_can_change_but_no_evidence_can(self):
        self.data['collected_utc'] = '2026-09-28T01:00:00+00:00'
        record = evidence.authenticate(self.root, self.document)
        self.assertEqual(record['revision_audit_sha256'], self.document['revision_audit_sha256'])
        self.assertIsNone(self.document['validation_summary']['charged_usd'])
        self.assertEqual(self.document['validation_summary']['unknown_cost_requests'], 20)

    def test_zero_score_missing_verifier_and_unknown_cost_do_not_trigger_reselection(self):
        for row in self.data['rows']: row['reward'] = 0
        self.data['rows'][-1].update(reward=None, status='verifier_failed', verifier_error_type='RuntimeError')
        with patch.object(freeze, '_read_revision', return_value=self.data):
            document = freeze.capture(self.root)
        record = evidence.authenticate(self.root, document)
        self.assertEqual(evidence.recheck(self.root, document, record)['harness'], 'C0-NC')
        self.assertEqual(document['validation_summary']['passes'], 0)
        self.assertEqual(document['validation_summary']['failures'], 19)
        self.assertEqual(document['validation_summary']['no_verifier_result'], 1)
        self.assertIsNone(document['validation_summary']['charged_usd'])

    def test_under_lock_recheck_requires_exact_record_but_does_not_repeat_audit(self):
        record = evidence.authenticate(self.root, self.document)
        for field in record:
            altered = deepcopy(record)
            altered[field] = True if field == 'paid_launch_ready' else {} if isinstance(altered[field], dict) else 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.recheck(self.root, self.document, altered)
        for altered in (None, {}, dict(record, trusted=True)):
            with self.subTest(record=altered), self.assertRaises(ValueError):
                evidence.recheck(self.root, self.document, altered)
        self.native.assert_called_once()

    def test_under_lock_recheck_rejects_current_revision_file_drift(self):
        record = evidence.authenticate(self.root, self.document)
        def changed(root, files):
            if Path(root) == self.current: raise ValueError('Changed native result')
            self.check_files(root, files)
        self.file_check.side_effect = changed
        with self.assertRaises(ValueError): evidence.recheck(self.root, self.document, record)
        self.native.assert_called_once()

    def test_stop_in_any_original_revision_or_final_root_refuses_progression(self):
        record = evidence.authenticate(self.root, self.document)
        roots = dict(self.roots, revision=self.current, final=self.root)
        for name, root in roots.items():
            marker = root / '.runtime/stage2/operator-stop-request.json'; marker.parent.mkdir(parents=True, exist_ok=True)
            for dangling in (False, True):
                if dangling: marker.symlink_to(root / 'missing')
                else: marker.write_text('{}')
                with self.subTest(root=name, dangling=dangling), self.assertRaises(ValueError):
                    evidence.authenticate(self.root, self.document)
                with self.subTest(root=name, dangling=dangling, recheck=True), self.assertRaises(ValueError):
                    evidence.recheck(self.root, self.document, record)
                marker.unlink()
        self.native.assert_called_once()

    def test_stop_arriving_during_audit_is_honoured(self):
        def stop(files):
            marker = self.current / '.runtime/stage2/operator-stop-request.json'
            marker.parent.mkdir(parents=True); marker.write_text('{}')
            return deepcopy(self.data)
        self.native.side_effect = stop
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)

    def test_no_completed_root_can_be_reused(self):
        record = evidence.authenticate(self.root, self.document)
        for root in (*self.roots.values(), self.current):
            with self.subTest(root=root), self.assertRaises(ValueError): evidence.authenticate(root, self.document)
            with self.subTest(root=root, recheck=True), self.assertRaises(ValueError): evidence.recheck(root, self.document, record)
        self.native.assert_called_once()

    def test_anchor_lineage_and_original_projection_are_rechecked(self):
        altered = original_anchors(self.f.original)
        altered['qualification.json']['sources'] = dict(altered['qualification.json']['sources'], changed='0' * 64)
        self.anchors.return_value = altered
        with self.assertRaises(ValueError): evidence.authenticate(self.root, self.document)
        self.native.assert_not_called()

    def test_conflicting_old_and_revised_operator_bindings_are_not_overwritten(self):
        self.old_operator.return_value = {candidate.ORIGINAL: '0' * 64}
        with self.assertRaisesRegex(ValueError, 'disagree'): evidence.authenticate(self.root, self.document)
        self.native.assert_not_called()

    def test_does_not_create_files_or_modify_candidate_and_record_has_no_aliases(self):
        before = deepcopy(self.document)
        paths = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*'))
        record = evidence.authenticate(self.root, self.document)
        record['revision_files'].clear(); record['original_files']['portable'].clear()
        self.assertEqual(self.document, before)
        self.assertEqual(sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*')), paths)


class NativeReaderTests(unittest.TestCase):
    def test_local_original_interpreter_unchanged_collector_and_result_preflight(self):
        bindings = {'stage2/source.py': 'a' * 64,
            '.runtime/stage2/scored-trials/synthetic/result.json': 'b' * 64}
        with patch.object(evidence.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}', '')) as run:
            self.assertEqual(evidence._native_audit(bindings), {})
        args, kwargs = run.call_args
        self.assertEqual(args[0][:3], [str(evidence.CURRENT / '.venv/bin/python'), '-B', '-c'])
        program = args[0][3]; compile(program, '<synthetic-host-reader>', 'exec')
        self.assertEqual(program, freeze._revision_program(bindings))
        self.assertIn(exporter.program(exporter.COLLECT, revision.CONDITION), program)
        self.assertLess(program.index('_finalist_state'), program.index('original.authenticate'))
        self.assertLess(program.index('_finalist_check_files()\n'), program.index('original.authenticate'))
        self.assertIn('.runtime/stage2/scored-trials/synthetic/result.json', program)
        self.assertEqual(kwargs['cwd'], evidence.CURRENT)
        self.assertEqual(kwargs['env']['PYTHONPATH'], str(evidence.CURRENT / 'stage2'))
        self.assertEqual(kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertNotIn('PYTHONHOME', kwargs['env'])
        self.assertNotIn('run_trial(', program); self.assertNotIn(exporter.BACKUP, program)

    def test_failed_or_malformed_native_output_is_not_exposed_or_retried(self):
        for code, stdout in ((1, 'Private output'), (0, 'Private output')):
            with patch.object(evidence.subprocess, 'run', return_value=subprocess.CompletedProcess(
                    [], code, stdout, 'Private error')) as run:
                with self.assertRaises(ValueError) as error: evidence._native_audit({'source.py': 'a' * 64})
            self.assertNotIn('Private', str(error.exception)); self.assertEqual(run.call_count, 1)

    def test_timeout_and_missing_interpreter_are_sanitized_without_retry(self):
        for failure in (OSError('Private path'), subprocess.TimeoutExpired(
                ['Private command'], 180, output='Private output', stderr='Private error')):
            with patch.object(evidence.subprocess, 'run', side_effect=failure) as run:
                with self.assertRaises(ValueError) as error: evidence._native_audit({'source.py': 'a' * 64})
            self.assertNotIn('Private', str(error.exception)); self.assertEqual(run.call_count, 1)

    def test_preflight_rejects_active_revision_without_executing_collector(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(exporter, 'REMOTE', folder), patch.object(exporter, 'COLLECT', 'audit_ran=True'), \
                    patch('subprocess.check_output', return_value='ActiveState=active\nMainPID=42\nExecMainStatus=0'):
                scope = {}
                with self.assertRaises(ValueError): exec(freeze._revision_program({'source.py': 'a' * 64}), scope)
                self.assertNotIn('audit_ran', scope)

    def test_preflight_checks_known_result_bytes_not_only_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); path = root / '.runtime/stage2/scored-trials/synthetic/result.json'
            path.parent.mkdir(parents=True); path.write_text('{}')
            bindings = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()}
            with patch.object(exporter, 'REMOTE', folder), patch.object(exporter, 'COLLECT', 'audit_ran=True'), \
                    patch('subprocess.check_output', return_value='ActiveState=inactive\nMainPID=0\nExecMainStatus=0'):
                scope = {}; exec(freeze._revision_program(bindings), scope); self.assertTrue(scope['audit_ran'])
                path.write_text('{"changed":true}'); scope = {}
                with self.assertRaises(ValueError): exec(freeze._revision_program(bindings), scope)
                self.assertNotIn('audit_ran', scope)
                path.unlink(); path.symlink_to(root / 'missing'); scope = {}
                with self.assertRaises(ValueError): exec(freeze._revision_program(bindings), scope)
                self.assertNotIn('audit_ran', scope)


if __name__ == '__main__': unittest.main()
