"""Synthetic reporting and archive checks, no SSH or provider calls."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import export_no_cutoff_custom as export
import no_cutoff_custom_policy as policy
from test_no_cutoff_custom_policy import Fixture


class ExportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); f = Fixture(self, self.root)
        self.enterContext(patch.object(export, 'OUTPUT', self.root))
        self.enterContext(patch.object(export, 'ORIGINAL_FREEZE_SHA256', policy.fingerprint(f.document)))
        registration = dict(f.block, kind='public', registration_sha256=policy.fingerprint(f.block), registration_file_sha256='d' * 64)
        (self.root / 'registration-c0-nc.json').write_text(json.dumps(registration))
        private = dict.fromkeys(('no-cutoff-runtime.json', 'no-cutoff-original-authentication.json', 'no-cutoff-credit-policy.json'), 'b' * 64)
        projection = dict(sources=f.proof['sources'], sources_sha256=f.proof['sources_sha256'],
            qualification_file_sha256='e' * 64, evidence_files=f.proof['evidence_files'], private_file_sha256=private)
        (self.root / 'qualification.json').write_text(json.dumps(projection))
        (self.root / 'lineage.json').write_text(json.dumps(dict(original_candidate_sha256=policy.fingerprint(f.document), candidate_file_sha256='f' * 64)))
        bindings = {'.runtime/stage2/no-cutoff-development-blocks/C0-NC.json': 'd' * 64,
            '.runtime/stage2/no-cutoff-qualification.json': 'e' * 64,
            '.runtime/stage2/no-cutoff-original-candidate.json': 'f' * 64,
            '.runtime/stage2/python-runtime.tar.gz': policy.PYTHON_SHA256,
            **{'.runtime/stage2/' + name: sha for name, sha in private.items()}, **f.proof['evidence_files']}
        self.data = dict(condition='C0-NC', registration=f.block, qualification_sha256=f.block['qualification_sha256'],
            sources=f.proof['sources'], model_protocol=policy.SETTINGS.document(), policy=policy.POLICY,
            service=dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0'),
            audit_checks=dict.fromkeys(export.CHECKS, True), bindings=bindings, rows=[])
        for cell in f.block['cells']:
            row = dict.fromkeys(export.ROW_FIELDS, 0)
            row.update(cell, reward=0, status='verified', started_utc='2026-09-28T00:00:00Z',
                completed_utc='2026-09-28T00:01:00Z', agent_error_type='TimeoutError', verifier_error_type='',
                model_requests=2, accepted_model_responses=1, interrupted_requests=1,
                known_cost_usd='0.01', total_cost_usd=None, unknown_cost_requests=1,
                input_tokens=None, output_tokens=None, cleanup_complete=True, model_revoked=True, result_sha256='a' * 64)
            self.data['rows'].append(row)

    def test_zero_unknown_and_missing_verifier_are_not_inherited_fifteen_passes(self):
        export.validate_snapshot(self.data)
        self.data['rows'][0].update(reward=None, status='setup_failed')
        export.validate_snapshot(self.data)
        result = export.aggregate(self.data['rows'])
        self.assertEqual((result['passed'], result['failed'], result['no_verifier_result']), (0, 19, 1))
        self.assertIsNone(result['total_cost_usd']); self.assertFalse(result['full_benchmark_win_claimed'])

    def test_changed_registration_runtime_or_original_lineage_rejected(self):
        for change in ('duplicate', 'order', 'drop', 'parent', 'binding', 'source', 'active', 'model', 'native-evidence'):
            data = deepcopy(self.data)
            if change == 'duplicate': data['rows'][1] = data['rows'][0]
            elif change == 'order': data['rows'].reverse()
            elif change == 'drop': data['rows'].pop()
            elif change == 'parent': data['registration']['parent'] = 'C3'
            elif change == 'binding': data['bindings']['.runtime/stage2/no-cutoff-original-candidate.json'] = '0' * 64
            elif change == 'source': data['sources']['no_cutoff_custom_agent.py'] = '0' * 64
            elif change == 'active': data['service']['ActiveState'] = 'active'
            elif change == 'native-evidence': data['bindings']['.runtime/stage2/native-no-cutoff-qualification-test/regression.json'] = '0' * 64
            else: data['model_protocol']['temperature'] = 0
            with self.subTest(change=change), self.assertRaises(ValueError): export.validate_snapshot(data)

    def test_private_text_and_false_complete_accounting_rejected(self):
        for change in ({'messages': 'private'}, {'total_cost_usd': '0'}, {'reward': True},
                {'agent_error_type': 'private message'}, {'accepted_model_responses': 3},
                {'cleanup_complete': False}, {'agent_seconds': float('nan')},
                {'started_utc': 'private text'}, {'retry_records': -1}):
            data = deepcopy(self.data); data['rows'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): export.validate_snapshot(data)

    def test_unallowlisted_public_metadata_rejected(self):
        for field in ('service', 'bindings', 'audit_checks'):
            data = deepcopy(self.data); data[field]['private'] = 'do not publish'
            with self.subTest(field=field), self.assertRaises(ValueError): export.validate_snapshot(data)

    def test_read_only_remote_programs_compile_and_use_separate_deployment(self):
        for source in (export.COLLECT, export.BACKUP): compile(export.program(source, 'C0-NC'), '<synthetic>', 'exec')
        self.assertLess(export.COLLECT.index('original.authenticate'), export.COLLECT.index('lock_all(stack,root)'))
        self.assertIn('sources(root,document)', export.COLLECT)
        self.assertIn("names+=list(proof['evidence_files'])", export.BACKUP)
        for bad in ('C0', 'C3', '../C0-NC'):
            with self.assertRaises(ValueError): export.condition_name(bad)

    def test_private_archive_hashes_and_credential_exclusion(self):
        content = b'synthetic'; sha = hashlib.sha256(content).hexdigest()
        data = dict(bindings={'candidate.json': sha}, sources={'fixture.py': sha}, rows=[dict(trial_id='fixture', result_sha256=sha)])
        path = self.root / 'archive.tar.gz'
        for extra in (None, '.env', '../escape'):
            with tarfile.open(path, 'w:gz') as archive:
                for name in [*export.expected_archive_hashes(data), *([extra] if extra else [])]:
                    member = tarfile.TarInfo(name); member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
            receipt = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), files=3 + bool(extra))
            if extra:
                with self.assertRaises(ValueError): export.verify_archive(path, data, receipt)
            else:
                self.assertEqual(export.verify_archive(path, data, receipt)['verified_bound_files'], 3)


if __name__ == '__main__': unittest.main()
