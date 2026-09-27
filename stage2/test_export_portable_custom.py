"""Synthetic reporting tests. No SSH, paid calls or scored task executions."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from export_portable_custom import (BACKUP, CHECKS, COLLECT, OUTPUT, ROW_FIELDS,
    aggregate, condition_name, expected_archive_hashes, private_backup, program, validate_snapshot, verify_archive)
from portable_custom_policy import POLICY, SETTINGS


class PortableExportTests(unittest.TestCase):
    def setUp(self):
        registration = json.loads((OUTPUT / 'registration-c0.json').read_text())
        proof = json.loads((OUTPUT / 'qualification.json').read_text())
        block = {k: v for k, v in registration.items()
                 if k not in ('kind', 'registration_sha256', 'registration_file_sha256')}
        self.data = dict(condition='C0', registration=block, sources=proof['sources'],
            qualification_sha256=block['qualification_sha256'], model_protocol=SETTINGS.document(), policy=POLICY,
            service=dict(ActiveState='inactive', MainPID='0', ExecMainStatus='0'),
            audit_checks=dict.fromkeys(CHECKS, True), bindings={
                '.runtime/stage2/portable-development-blocks/C0.json': registration['registration_file_sha256'],
                '.runtime/stage2/portable-qualification.json': proof['qualification_file_sha256'],
                '.runtime/stage2/python-runtime.tar.gz': block['python_runtime_sha256']}, rows=[])
        for cell in block['cells']:
            row = {k: 0 for k in ROW_FIELDS}
            row.update(cell, reward=0, status='verified', started_utc='2026-09-26T00:00:00Z',
                completed_utc='2026-09-26T00:01:00Z', agent_error_type='TimeoutError', verifier_error_type='',
                model_requests=2, accepted_model_responses=1, interrupted_requests=1,
                known_cost_usd='0.01', total_cost_usd=None, unknown_cost_requests=1,
                known_input_tokens=10, input_tokens=None, known_output_tokens=5, output_tokens=None,
                cleanup_complete=True, model_revoked=True, result_sha256='a'*64)
            self.data['rows'].append(row)

    def test_complete_retained_zeros_validate(self):
        validate_snapshot(self.data)

    def test_missing_row_rejected(self):
        self.data['rows'].pop()
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_duplicate_row_rejected(self):
        self.data['rows'][1] = self.data['rows'][0]
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_order_change_rejected(self):
        self.data['rows'].reverse()
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_unknown_cost_cannot_be_reported_as_zero(self):
        self.data['rows'][0]['total_cost_usd'] = '0'
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_missing_verifier_remains_separate(self):
        self.data['rows'][0].update(reward=None, status='setup_failed')
        validate_snapshot(self.data)
        result = aggregate(self.data['rows'])
        self.assertEqual((result['failed'], result['no_verifier_result']), (19, 1))

    def test_pass_at_deadline_counts_as_pass(self):
        self.data['rows'][0]['reward'] = 1
        validate_snapshot(self.data)
        result = aggregate(self.data['rows'])
        self.assertEqual((result['passed'], result['passed_despite_agent_timeout']), (1, 1))
        self.assertFalse(result['full_benchmark_win_claimed'])

    def test_call_partition_required(self):
        self.data['rows'][0]['accepted_model_responses'] = 2
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_negative_count_rejected(self):
        self.data['rows'][0]['retry_records'] = -1
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_known_complete_cost_must_match(self):
        row = self.data['rows'][0]
        row.update(unknown_cost_requests=0, total_cost_usd='0.02')
        with self.assertRaises(ValueError): validate_snapshot(self.data)
        row['total_cost_usd'] = '0.01'
        validate_snapshot(self.data)

    def test_nan_cost_and_time_rejected(self):
        for key, value in [('known_cost_usd', 'NaN'), ('agent_seconds', float('nan'))]:
            data = copy.deepcopy(self.data); data['rows'][0][key] = value
            with self.assertRaises(ValueError): validate_snapshot(data)

    def test_raw_text_field_rejected(self):
        self.data['rows'][0]['messages'] = 'private content'
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_exception_text_rejected(self):
        self.data['rows'][0]['agent_error_type'] = 'Error: private command'
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_boolean_score_rejected(self):
        self.data['rows'][0]['reward'] = True
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_cleanup_and_audit_must_be_true(self):
        for key in ('cleanup_complete', 'model_revoked'):
            data = copy.deepcopy(self.data); data['rows'][0][key] = None
            with self.assertRaises(ValueError): validate_snapshot(data)
        self.data['audit_checks'].pop('official_limits')
        with self.assertRaises(ValueError): validate_snapshot(self.data)

    def test_source_runtime_and_registration_bindings_required(self):
        for field in ('sources', 'bindings', 'registration'):
            data = copy.deepcopy(self.data)
            if field == 'sources': data[field]['portable_custom_agent.py'] = '0'*64
            elif field == 'bindings': data[field]['.runtime/stage2/python-runtime.tar.gz'] = '0'*64
            else: data[field]['condition'] = 'C1'
            with self.assertRaises(ValueError): validate_snapshot(data)

    def test_model_policy_and_service_cannot_drift(self):
        for field, key, value in [('model_protocol', 'temperature', 0), ('policy', 'added_cap', 1),
                                  ('service', 'ActiveState', 'active')]:
            data = copy.deepcopy(self.data); data[field][key] = value
            with self.assertRaises(ValueError): validate_snapshot(data)

    def test_unknowns_and_total_preserved(self):
        result = aggregate(self.data['rows'])
        self.assertEqual(result['known_cost_usd'], '0.20')
        self.assertEqual(result['unknown_cost_requests'], 20)
        self.assertIsNone(result['total_cost_usd'])
        self.assertFalse(result['independent_receipts_verified'])

    def test_condition_cannot_be_shell_or_path_input(self):
        for value in ('C3', '../C0', "C0'; exit()"):
            with self.assertRaises(ValueError): condition_name(value)

    def test_remote_programs_compile_without_execution(self):
        for source in (COLLECT, BACKUP):
            compile(program(source, 'C0'), '<offline remote check>', 'exec')

    def test_failed_transfer_retains_private_bytes_and_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch('export_portable_custom.private_dir', return_value=Path(temp)), \
                patch('export_portable_custom.subprocess.run', return_value=SimpleNamespace(
                    returncode=255, stderr=b'synthetic transport failure')):
            with self.assertRaises(RuntimeError): private_backup(self.data)
            self.assertTrue((Path(temp) / 'evidence.tar.gz').exists())
            self.assertEqual((Path(temp) / 'backup-transfer-error.txt').read_bytes(), b'synthetic transport failure')
            self.assertFalse((Path(temp) / 'backup.json').exists())


class PortableArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'evidence.tar.gz'
        self.content = b'synthetic evidence only'
        sha = hashlib.sha256(self.content).hexdigest()
        self.data = dict(bindings={'.runtime/stage2/portable-qualification.json': sha},
            sources={'synthetic.py': sha}, rows=[dict(trial_id='synthetic', result_sha256=sha)])

    def archive(self, *, extra=None, duplicate=False, omit=False):
        names = list(expected_archive_hashes(self.data))
        if omit: names.pop()
        if duplicate: names.append(names[0])
        if extra: names.append(extra)
        with tarfile.open(self.path, 'w:gz') as handle:
            for name in names:
                member = tarfile.TarInfo(name); member.size = len(self.content)
                handle.addfile(member, io.BytesIO(self.content))
        return dict(sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(), files=len(names))

    def test_bound_evidence_verified(self):
        receipt = verify_archive(self.path, self.data, self.archive())
        self.assertEqual(receipt['verified_bound_files'], 3)
        self.assertTrue(receipt['private_archive_not_published'])

    def test_missing_and_duplicate_rejected(self):
        for opts in ({'omit': True}, {'duplicate': True}):
            with self.assertRaises(ValueError): verify_archive(self.path, self.data, self.archive(**opts))

    def test_credentials_and_path_escape_rejected(self):
        for name in ('.env', 'task/token', '../outside', '/outside', 'keys/id_ed25519'):
            with self.assertRaises(ValueError): verify_archive(self.path, self.data, self.archive(extra=name))

    def test_checksum_mismatch_rejected(self):
        receipt = self.archive(); receipt['sha256'] = '0'*64
        with self.assertRaises(ValueError): verify_archive(self.path, self.data, receipt)

    def test_changed_bound_result_rejected(self):
        receipt = self.archive(); self.data['rows'][0]['result_sha256'] = '0'*64
        with self.assertRaises(ValueError): verify_archive(self.path, self.data, receipt)


if __name__ == '__main__':
    unittest.main()
