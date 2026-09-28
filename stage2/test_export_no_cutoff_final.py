"""Final metadata and real archive checks using synthetic evidence only."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import export_no_cutoff_final as export
import no_cutoff_final_policy as policy
from test_no_cutoff_final_policy import Fixture


class ExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); f = Fixture(self, self.root)
        self.enterContext(patch.object(export, 'OUTPUT', self.root))
        original = policy.fingerprint(f.document['original_candidate'])
        self.enterContext(patch.object(export, 'ORIGINAL_FREEZE_SHA256', original))
        registration = dict(f.block, kind='public', registration_sha256=policy.fingerprint(f.block), registration_file_sha256='d' * 64)
        (self.root / 'registration-c0-nc.json').write_text(json.dumps(registration))
        private = dict.fromkeys((policy.RUNTIME_FILE, policy.AUTHENTICATION_FILE,
            policy.POLICY_FILE, policy.MANIFEST_FILE), 'b' * 64)
        projection = dict(sources=f.proof['sources'], sources_sha256=f.proof['sources_sha256'],
            qualification_file_sha256='e' * 64, evidence_files=f.proof['evidence_files'], private_file_sha256=private)
        (self.root / 'qualification.json').write_text(json.dumps(projection))
        (self.root / 'lineage.json').write_text(json.dumps(dict(original_candidate_sha256=original,
            candidate_sha256=policy.fingerprint(f.document), validation_results_sha256=policy.fingerprint(f.document['result_bindings']),
            candidate_file_sha256='f' * 64)))
        bindings = {'.runtime/stage2/' + policy.REGISTRATION_FILE: 'd' * 64,
            '.runtime/stage2/' + policy.QUALIFICATION_FILE: 'e' * 64,
            '.runtime/stage2/' + policy.CANDIDATE_FILE: 'f' * 64,
            '.runtime/stage2/python-runtime.tar.gz': policy.PYTHON_SHA256,
            **{'.runtime/stage2/' + name: sha for name, sha in private.items()}, **f.proof['evidence_files']}
        self.data = dict(condition='C0-NC', registration=f.block, qualification_sha256=f.block['qualification_sha256'],
            sources=f.proof['sources'], model_protocol=policy.SETTINGS.document(), policy=policy.POLICY,
            collected_utc='2026-09-28T00:02:00Z',
            service=dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0'),
            audit_checks=dict.fromkeys(export.CHECKS, True), bindings=bindings, rows=[])
        for cell in f.block['cells']:
            row = dict.fromkeys(export.ROW_FIELDS, 0)
            row.update({k: cell[k] for k in ('trial_id', 'task_id', 'harness')})
            row.update(reward=0, status='verified', started_utc='2026-09-28T00:00:00Z',
                completed_utc='2026-09-28T00:01:00Z', agent_error_type='TimeoutError', verifier_error_type='',
                model_requests=2, accepted_model_responses=1, interrupted_requests=1,
                known_cost_usd='0.01', total_cost_usd=None, unknown_cost_requests=1,
                input_tokens=None, output_tokens=None, cleanup_complete=True, model_revoked=True, result_sha256='a' * 64)
            self.data['rows'].append(row)

    def test_exact_89_zeros_unknown_and_missing_are_not_inherited_development_scores(self):
        export.validate_snapshot(self.data)
        self.data['rows'][0].update(reward=None, status='setup_failed')
        export.validate_snapshot(self.data); result = export.aggregate(self.data['rows'])
        self.assertEqual((result['passed'], result['failed'], result['no_verifier_result']), (0, 88, 1))
        self.assertIsNone(result['total_cost_usd']); self.assertFalse(result['full_benchmark_win_claimed'])

    def test_changed_final_registration_lineage_sources_and_runtime_rejected(self):
        for change in ('duplicate', 'order', 'drop', 'parent', 'original', 'revision', 'binding',
                'source', 'active', 'model', 'native-evidence', 'manifest'):
            data = deepcopy(self.data)
            if change == 'duplicate': data['rows'][1] = data['rows'][0]
            elif change == 'order': data['rows'].reverse()
            elif change == 'drop': data['rows'].pop()
            elif change == 'parent': data['registration']['parent'] = 'C3'
            elif change == 'original': data['registration']['original_candidate_sha256'] = '0' * 64
            elif change == 'revision': data['registration']['validation_results_sha256'] = '0' * 64
            elif change == 'binding': data['bindings']['.runtime/stage2/' + policy.CANDIDATE_FILE] = '0' * 64
            elif change == 'source': data['sources']['no_cutoff_custom_agent.py'] = '0' * 64
            elif change == 'active': data['service']['ActiveState'] = 'active'
            elif change == 'native-evidence':
                name = next(k for k in data['bindings'] if k.endswith('/regression.json'))
                data['bindings'][name] = '0' * 64
            elif change == 'manifest': data['bindings']['.runtime/stage2/' + policy.MANIFEST_FILE] = '0' * 64
            else: data['model_protocol']['temperature'] = 0
            with self.subTest(change=change), self.assertRaises(ValueError): export.validate_snapshot(data)

    def test_private_text_false_accounting_and_invalid_evidence_rejected(self):
        for change in ({'messages': 'private'}, {'total_cost_usd': '0'}, {'reward': True},
                {'agent_error_type': 'private message'}, {'accepted_model_responses': 3},
                {'cleanup_complete': False}, {'agent_seconds': float('nan')},
                {'started_utc': 'private text'}, {'retry_records': -1}):
            data = deepcopy(self.data); data['rows'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): export.validate_snapshot(data)

    def test_unallowlisted_metadata_and_observation_text_rejected(self):
        for field in ('service', 'bindings', 'audit_checks'):
            data = deepcopy(self.data); data[field]['private'] = 'do not publish'
            with self.subTest(field=field), self.assertRaises(ValueError): export.validate_snapshot(data)
        with self.assertRaises(ValueError): export.validate_snapshot(dict(self.data, raw_exchange='private'))
        with self.assertRaises(ValueError): export.validate_snapshot(dict(self.data, collected_utc='private'))

    def test_native_reader_preflight_and_authentication_before_all_ancestor_locks(self):
        for source in (export.COLLECT, export.BACKUP): compile(export.program(source, 'C0-NC'), '<synthetic>', 'exec')
        self.assertIn('import no_cutoff_final_evidence as original', export.COLLECT)
        self.assertLess(export.COLLECT.index("assert state['ActiveState']=='inactive'"), export.COLLECT.index('original.authenticate'))
        self.assertLess(export.COLLECT.index('original.authenticate'), export.COLLECT.index('lock_all(stack,root)'))
        self.assertIn("report['attempted']==89", export.COLLECT)
        self.assertIn('sources(root,document)', export.COLLECT)
        self.assertIn("names+=list(proof['evidence_files'])", export.BACKUP)
        self.assertIn(policy.MANIFEST_FILE, export.BACKUP); self.assertIn(policy.REGISTRATION_FILE, export.BACKUP)
        self.assertNotIn('no-cutoff-development-blocks', export.COLLECT + export.BACKUP)
        for bad in ('C0', 'C3', '../C0-NC'):
            with self.assertRaises(ValueError): export.condition_name(bad)

    def test_correct_final_interpreter_not_an_appended_second_interpreter(self):
        with patch.object(export, 'ssh_command', return_value=['ssh', 'root@pinned', 'python3', '-']):
            command = export.remote_command()
        self.assertEqual(command[-2:], [export.REMOTE + '/.venv/bin/python', '-'])
        self.assertNotIn('python3', command)

    def test_read_only_failure_does_not_expose_private_stderr(self):
        result = SimpleNamespace(returncode=1, stderr='PRIVATE RAW TEXT', stdout='')
        with patch.object(export, 'remote_command', return_value=['synthetic']), \
                patch.object(export.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError) as caught: export.read_snapshot('C0-NC')
        self.assertNotIn('PRIVATE', str(caught.exception))

    def receipt(self):
        return dict(sha256='0' * 64, files=500, bytes=1000, excluded=1, compressed_bytes=100,
            verified_result_files=89, verified_bound_files=len(export.expected_archive_hashes(self.data)),
            private_archive_not_published=True, restore_test=export.RESTORE_NOTE)

    def test_export_separates_development20_and_outside69_and_preserves_baseline_scores(self):
        backup = self.receipt()
        with patch.object(export, 'verify_archive', return_value=backup) as verify:
            result = export.export(self.data, backup)
        verify.assert_called_once()
        self.assertEqual(result['results']['attempted'], 89)
        self.assertEqual(result['development_subset']['attempted'], 20)
        self.assertEqual(result['outside_development_subset']['attempted'], 69)
        self.assertEqual(result['baseline_comparison']['primary']['passed'], 52)
        self.assertEqual(result['baseline_comparison']['secondary']['passed'], 44)
        self.assertEqual(result['confirmation60_status'], 'deferred_not_run')
        self.assertFalse((self.root / 'c0-nc/evidence.tar.gz').exists())
        self.assertTrue((self.root / 'c0-nc/trials.csv').is_file())

    def test_claimed_backup_flags_cannot_replace_current_archive_verification(self):
        with patch.object(export, 'verify_archive', side_effect=ValueError('not the archived bytes')) as verify:
            with self.assertRaises(ValueError): export.export(self.data, self.receipt())
        verify.assert_called_once(); self.assertFalse((self.root / 'c0-nc').exists())

    def test_backup_cannot_add_private_text_or_claim_only_20_results(self):
        for change in ({'raw': 'private'}, {'verified_result_files': 20}, {'restore_test': 'private text'}):
            with self.assertRaises(ValueError): export.export(self.data, self.receipt() | change)

    def test_private_archive_hashes_and_credential_exclusion(self):
        content = b'synthetic'; sha = hashlib.sha256(content).hexdigest()
        data = dict(bindings={'candidate.json': sha}, sources={'fixture.py': sha}, rows=[dict(trial_id='fixture', result_sha256=sha)])
        path = self.root / 'archive.tar.gz'
        for extra in (None, '.env', '../escape', 'candidate.json'):
            with tarfile.open(path, 'w:gz') as archive:
                for name in [*export.expected_archive_hashes(data), *([extra] if extra else [])]:
                    member = tarfile.TarInfo(name); member.size = len(content); archive.addfile(member, io.BytesIO(content))
            receipt = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), files=3 + bool(extra),
                bytes=(3 + bool(extra)) * len(content), excluded=0)
            if extra:
                with self.assertRaises(ValueError): export.verify_archive(path, data, receipt)
            else:
                self.assertEqual(export.verify_archive(path, data, receipt)['verified_bound_files'], 3)
                for change in ({'private': 'text'}, {'sha256': 'f' * 64}, {'bytes': 0}, {'files': True}):
                    with self.assertRaises(ValueError): export.verify_archive(path, data, receipt | change)


if __name__ == '__main__': unittest.main()
