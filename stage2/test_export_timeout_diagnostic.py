"""Offline reporting tests; no SSH, model calls or benchmark executions."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from export_timeout_diagnostic import (BACKUP, CHECKS, COLLECT, HASH_KEYS, OUTPUT,
    aggregate, api_observation, expected_archive_hashes, validate_snapshot, verify_archive)


class DiagnosticExportTests(unittest.TestCase):
    def setUp(self):
        launch = json.loads((OUTPUT / 'launch.json').read_text())
        self.expected = [dict(trial_id=f'{h}-{i}', task_id=f'task-{i}', harness=h,
            original_trial_id=f'original-{h}-{i}', original_result_sha256='a'*64,
            original_http_429_requests=2) for h, n in [('terminus-2', 11), ('openhands', 19)]
            for i in range(n)]
        self.data = {k: launch[k] for k in HASH_KEYS}
        self.data['audit_checks'] = dict.fromkeys(CHECKS, True)
        self.data['rows'] = [dict(c, reward=0, original_reward=0, original_agent_error_type='TimeoutError',
            agent_error_type='TimeoutError', verifier_error_type='', cleanup_complete=True,
            model_revoked=True, model_requests=2, accepted_model_responses=1,
            interrupted_model_requests=1, error_outcome_requests=0, other_unaccepted_requests=0,
            http_429_requests=0, transport_error_requests=0, retry_records=0,
            missing_call_outcomes=0, no_recorded_api_errors=False,
            interrupted_last_call_at_deadline=True, known_cost_usd='0.01', total_cost_usd=None,
            unknown_cost_requests=1, known_input_tokens=10, known_output_tokens=5,
            input_tokens=None, output_tokens=None) for c in self.expected]

    def test_registered_failures_remain_valid(self):
        validate_snapshot(self.data, self.expected)

    def test_duplicate_cell_rejected(self):
        self.data['rows'][1] = self.data['rows'][0]
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_missing_cell_rejected(self):
        self.data['rows'].pop()
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_parent_binding_cannot_change(self):
        self.data['rows'][0]['original_result_sha256'] = 'b'*64
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_protocol_cannot_change(self):
        self.data['model_protocol_sha256'] = '0'*64
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_missing_verifier_not_failure_score(self):
        self.data['rows'][0]['reward'] = None
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_missing_cleanup_and_audit_rejected(self):
        for mutation in ('cleanup', 'audit'):
            data = copy.deepcopy(self.data)
            if mutation == 'cleanup':
                data['rows'][0]['model_revoked'] = False
            else:
                data['audit_checks'].pop('official_deadlines_unchanged')
            with self.assertRaises(ValueError):
                validate_snapshot(data, self.expected)

    def test_unknown_cost_not_zero(self):
        self.data['rows'][0]['total_cost_usd'] = '0'
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_physical_request_accounting(self):
        self.data['rows'][0]['accepted_model_responses'] = 2
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_interrupted_call_not_strict_clean(self):
        self.data['rows'][0]['no_recorded_api_errors'] = True
        with self.assertRaises(ValueError):
            validate_snapshot(self.data, self.expected)

    def test_deadline_interruption_not_provider_error(self):
        self.assertEqual(api_observation(self.data['rows'][0]), 'last_request_interrupted_at_task_deadline')

    def test_generic_error_does_not_invent_origin(self):
        row = dict(self.data['rows'][0], error_outcome_requests=1, interrupted_model_requests=0,
                   interrupted_last_call_at_deadline=False)
        self.assertEqual(api_observation(row), 'request_error_origin_unestablished')

    def test_recorded_provider_errors_have_separate_categories(self):
        row = dict(self.data['rows'][0], transport_error_requests=1)
        self.assertEqual(api_observation(row), 'recorded_other_transport_error')
        row['http_429_requests'] = 1
        self.assertEqual(api_observation(row), 'recorded_http_429')

    def test_pass_at_timeout_is_not_discarded_or_added_to_original(self):
        row = dict(self.data['rows'][0], reward=1)
        value = aggregate([row])
        self.assertEqual((value['passed'], value['failed'], value['passed_despite_agent_timeout']), (1, 0, 1))
        self.assertEqual(value['passed_all_responses_accepted'], 0)
        self.assertIsNone(value['causal_additional_original_passes'])
        self.assertFalse(value['original_scores_replaced'])

    def test_complete_accepted_calls_can_still_fail(self):
        row = dict(self.data['rows'][0], accepted_model_responses=2, interrupted_model_requests=0,
                   interrupted_last_call_at_deadline=False, no_recorded_api_errors=True)
        self.assertEqual(api_observation(row), 'all_responses_accepted_no_recorded_api_error')
        self.assertEqual(aggregate([row])['failed_all_responses_accepted'], 1)

    def test_unknown_costs_and_tokens_preserved(self):
        value = aggregate(self.data['rows'])
        self.assertEqual(value['known_cost_usd'], '0.30')
        self.assertEqual(value['unknown_cost_requests'], 30)
        self.assertIsNone(value['total_cost_usd'])
        self.assertIsNone(value['input_tokens'])
        self.assertIsNone(value['output_tokens'])

    def test_remote_programs_compile_without_execution(self):
        compile(COLLECT, '<read-only collector>', 'exec')
        compile(BACKUP, '<read-only backup>', 'exec')


class DiagnosticArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'evidence.tar.gz'
        self.contents = b'synthetic evidence only'
        digest = hashlib.sha256(self.contents).hexdigest()
        self.data = dict(rows=[dict(trial_id='synthetic', result_sha256=digest)],
                         sources_sha256={'synthetic.py': digest},
                         registration_sha256=digest, qualification_sha256=digest)

    def archive(self, *, extra=None, omit=False, duplicate=False):
        names = list(expected_archive_hashes(self.data))
        if omit:
            names.pop()
        if duplicate:
            names.append(names[0])
        if extra:
            names.append(extra)
        with tarfile.open(self.path, 'w:gz') as archive:
            for name in names:
                info = tarfile.TarInfo(name)
                info.size = len(self.contents)
                archive.addfile(info, io.BytesIO(self.contents))
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        return dict(sha256=digest, files=len(names))

    def test_result_sources_and_bindings_verified(self):
        receipt = verify_archive(self.path, self.data, self.archive())
        self.assertEqual(receipt['verified_result_files'], 1)
        self.assertEqual(receipt['verified_bound_files'], 4)
        self.assertTrue(receipt['private_archive_not_published'])

    def test_credential_or_traversal_member_rejected(self):
        for extra in ('stage2/.env', '../outside', 'token'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                verify_archive(self.path, self.data, self.archive(extra=extra))

    def test_missing_or_duplicated_bound_member_rejected(self):
        for args in ({'omit': True}, {'duplicate': True}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                verify_archive(self.path, self.data, self.archive(**args))

    def test_source_stream_checksum_must_match(self):
        receipt = self.archive()
        receipt['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            verify_archive(self.path, self.data, receipt)


if __name__ == '__main__':
    unittest.main()
