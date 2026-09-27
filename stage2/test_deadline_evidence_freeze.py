"""Synthetic evidence authentication; no SSH, Docker or provider execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import deadline_evidence_freeze as freeze
import export_deadline_custom as exporter
from deadline_custom_policy import POLICY, SETTINGS, fingerprint
from scored_gateway import durable_json
from test_deadline_custom_policy import fixture, parent_fixture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvidenceFixture:
    def __init__(self, repo):
        self.repo = repo
        self.output = repo / freeze.RESULTS
        self.output.mkdir(parents=True)
        for name in freeze.LOGIC_FILES:
            (repo / 'stage2' / name).write_text('# Synthetic ' + name + '\n')
        rt, block, original = fixture(repo)
        sources = {'export_deadline_custom.py': digest(repo / 'stage2/export_deadline_custom.py')}
        original.update(sources=sources, sources_sha256=fingerprint(sources),
            dependencies={'python': '3.12.13', 'packages': {'harbor': '0.22.0'}})
        self.private = repo / freeze.PRIVATE_QUALIFICATION
        self.private.parent.mkdir(parents=True, mode=0o700)
        durable_json(self.private, original)
        block.update(sources_sha256=fingerprint(sources), qualification_sha256=fingerprint(original))
        self.registration = dict(block, kind='synthetic_public_registration',
            registration_sha256=fingerprint(block), registration_file_sha256='d' * 64)
        self.proof = dict(sources=sources, sources_sha256=fingerprint(sources),
            dependencies=original['dependencies'], qualification_sha256=fingerprint(original),
            qualification_file_sha256=digest(self.private),
            private_copies_verified={'deadline-credit-policy.json': 'c' * 64})
        self.parent = dict(evidence=parent_fixture(), file_sha256='f' * 64)
        for name, value in zip(freeze.ANCHOR_FILES, (self.proof, self.registration, self.parent, POLICY)):
            (self.output / name).write_text(json.dumps(value))
        self.data = dict(condition='C3', registration=block, qualification_sha256=fingerprint(original),
            sources=sources, model_protocol=SETTINGS.document(), policy=deepcopy(POLICY),
            service=dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0'),
            audit_checks=dict.fromkeys(exporter.CHECKS, True), collected_utc='2026-09-27T00:00:00Z',
            bindings={
                '.runtime/stage2/deadline-development-blocks/C3.json': 'd' * 64,
                '.runtime/stage2/deadline-qualification.json': digest(self.private),
                '.runtime/stage2/deadline-parent-evidence.json': 'f' * 64,
                '.runtime/stage2/deadline-credit-policy.json': 'c' * 64,
                '.runtime/stage2/python-runtime.tar.gz': block['python_runtime_sha256'],
            }, rows=[])
        for index, cell in enumerate(block['cells']):
            row = dict.fromkeys(exporter.ROW_FIELDS, 0)
            row.update(cell, reward=int(index < 16), status='verified',
                started_utc='2026-09-27T00:00:00Z', completed_utc='2026-09-27T00:01:00Z',
                agent_error_type='', verifier_error_type='', model_requests=2,
                accepted_model_responses=1, interrupted_requests=1,
                known_cost_usd='0.01', total_cost_usd=None, unknown_cost_requests=1,
                input_tokens=None, output_tokens=None, cleanup_complete=True, model_revoked=True,
                agent_seconds=10.0, official_agent_timeout_seconds=100.0,
                official_verifier_timeout_seconds=30.0, official_cpus=1, official_memory_mb=2048,
                result_sha256=hashlib.sha256(cell['trial_id'].encode()).hexdigest())
            self.data['rows'].append(row)


class EvidenceFreezeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.fixture = EvidenceFixture(self.repo)
        self.enterContext(patch.object(exporter, 'OUTPUT', self.fixture.output))
        self.reader = self.enterContext(patch.object(freeze, '_read_originals',
            side_effect=lambda: deepcopy(self.fixture.data)))

    def test_all_eighty_results_and_original_runtime_bound(self):
        document = freeze.capture(self.repo)
        self.assertEqual(freeze.validate_document(document)['selected'], 'C3')
        self.assertEqual(len(document['candidate']['result_bindings']), 80)
        self.assertEqual(set(document['anchor_files']), set(freeze.ANCHOR_PATHS))
        execution = document['selected_execution']
        self.assertEqual(execution['candidate_version'], 'stage2-candidate-0.4.1')
        self.assertEqual(execution['sources'], self.fixture.proof['sources'])
        self.assertEqual(execution['parent'], 'C0')
        self.assertFalse(document['paid_launch_ready'])
        self.assertFalse(document['full_benchmark_win_claimed'])

    def test_newer_candidate_does_not_replace_better_original(self):
        self.fixture.data['rows'][15]['reward'] = 0
        document = freeze.capture(self.repo)
        execution = document['selected_execution']
        self.assertEqual(execution['harness'], 'C0')
        self.assertEqual(execution['candidate_version'], 'stage2-candidate-0.3.0')
        self.assertEqual(execution['sources'], self.fixture.parent['evidence']['sources'])
        self.assertIsNone(execution['execution_contract'])
        self.assertIsNone(execution['parent'])

    def test_missing_costs_and_verifier_outcomes_stay_missing(self):
        self.fixture.data['rows'][-1].update(reward=None, status='verifier_failed',
            verifier_error_type='RuntimeError')
        document = freeze.capture(self.repo)
        summary = document['candidate']['c3_summary']
        self.assertEqual((summary['passes'], summary['failures'], summary['no_verifier_result']), (16, 3, 1))
        self.assertIsNone(summary['charged_usd'])
        self.assertEqual(summary['unknown_cost_requests'], 20)
        self.assertFalse(document['candidate']['selection']['cost_tiebreak_used'])

    def test_absent_phase_duration_is_not_fabricated(self):
        self.fixture.data['rows'][-1].update(reward=None, status='setup_failed', agent_seconds=None)
        with self.assertRaises(ValueError):
            freeze.capture(self.repo)

    def test_verify_refreshes_original_files_not_only_document_shape(self):
        document = freeze.capture(self.repo)
        self.fixture.data['collected_utc'] = '2026-09-28T01:00:00+00:00'
        self.assertEqual(freeze.verify(document, self.repo)['selected'], 'C3')
        self.assertEqual(self.reader.call_count, 2)
        self.fixture.data['rows'][0]['result_sha256'] = 'a' * 64
        with self.assertRaises(ValueError):
            freeze.verify(document, self.repo)

    def test_capture_has_no_save_or_mutable_alias(self):
        document = freeze.capture(self.repo)
        document['candidate']['c3_sources']['export_deadline_custom.py'] = '0' * 64
        document['candidate']['parent_evidence']['summaries']['C0']['passes'] = 0
        self.assertNotEqual(self.fixture.proof['sources']['export_deadline_custom.py'], '0' * 64)
        self.assertEqual(self.fixture.parent['evidence']['summaries']['C0']['passes'], 15)
        self.assertFalse((self.repo / '.runtime/finalisation').exists())

    def test_incomplete_active_duplicate_or_unregistered_snapshot_refused(self):
        original = deepcopy(self.fixture.data)
        for change in ('active', 'missing', 'duplicate', 'extra', 'order', 'lineage', 'audit'):
            self.fixture.data = deepcopy(original)
            if change == 'active': self.fixture.data['service']['ActiveState'] = 'active'
            elif change == 'missing': self.fixture.data['rows'].pop()
            elif change == 'duplicate': self.fixture.data['rows'][1] = self.fixture.data['rows'][0]
            elif change == 'extra': self.fixture.data['rows'].append(deepcopy(self.fixture.data['rows'][0]))
            elif change == 'order': self.fixture.data['rows'].reverse()
            elif change == 'lineage': self.fixture.data['registration']['parent'] = 'C1'
            else: self.fixture.data['audit_checks']['cleanup_and_revocation'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                freeze.capture(self.repo)

    def test_private_fields_wrong_byte_binding_and_missing_audit_refused(self):
        original = deepcopy(self.fixture.data)
        for change in ('private', 'row_private', 'policy_bytes', 'extra_binding', 'extra_audit', 'substate', 'timestamp'):
            self.fixture.data = deepcopy(original)
            if change == 'private': self.fixture.data['messages'] = ['must remain private']
            elif change == 'row_private': self.fixture.data['rows'][0]['command'] = 'must remain private'
            elif change == 'policy_bytes': self.fixture.data['bindings']['.runtime/stage2/deadline-credit-policy.json'] = '0' * 64
            elif change == 'extra_binding': self.fixture.data['bindings']['unknown.json'] = '0' * 64
            elif change == 'extra_audit': self.fixture.data['audit_checks']['unregistered'] = True
            elif change == 'substate': self.fixture.data['service']['SubState'] = 'failed'
            else: self.fixture.data['collected_utc'] = '2026-09-27T01:00:00'
            with self.subTest(change=change), self.assertRaises(ValueError):
                freeze.capture(self.repo)

    def test_public_dependencies_must_match_complete_original_qualification(self):
        path = self.fixture.output / 'qualification.json'
        value = deepcopy(self.fixture.proof)
        value['dependencies']['packages']['harbor'] = '0.99.0'
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            freeze.capture(self.repo)
        self.reader.assert_not_called()

    def test_complete_qualification_byte_drift_and_permission_refused(self):
        self.fixture.private.write_text(self.fixture.private.read_text() + ' ')
        with self.assertRaises(ValueError):
            freeze.capture(self.repo)
        self.reader.assert_not_called()
        self.fixture.private.chmod(0o644)
        with self.assertRaises(ValueError):
            freeze.capture(self.repo)

    def test_changed_collector_refused_before_remote_audit(self):
        (self.repo / 'stage2/export_deadline_custom.py').write_text('# changed checks\n')
        with self.assertRaises(ValueError):
            freeze.capture(self.repo)
        self.reader.assert_not_called()

    def test_selection_logic_and_anchors_cannot_change_during_capture(self):
        for relative in ('stage2/' + freeze.LOGIC_FILES[0], freeze.RESULTS + '/credit-policy.json'):
            def mutate():
                path = self.repo / relative
                path.write_text(path.read_text() + ' ')
                return deepcopy(self.fixture.data)
            with patch.object(freeze, '_read_originals', side_effect=mutate), self.assertRaises(ValueError):
                freeze.capture(self.repo)

    def test_changed_logic_or_cost_evidence_refuses_verification(self):
        document = freeze.capture(self.repo)
        self.fixture.data['rows'][0]['known_cost_usd'] = '0.02'
        with self.assertRaises(ValueError):
            freeze.verify(document, self.repo)
        self.fixture.data['rows'][0]['known_cost_usd'] = '0.01'
        (self.repo / 'stage2' / freeze.LOGIC_FILES[0]).write_text('# changed selection\n')
        with self.assertRaises(ValueError):
            freeze.verify(document, self.repo)

    def test_anchor_and_logic_symlinks_refused(self):
        for relative in (freeze.RESULTS + '/parent.json', 'stage2/' + freeze.LOGIC_FILES[0]):
            path = self.repo / relative
            saved = path.with_name(path.name + '.saved')
            path.rename(saved)
            path.symlink_to(saved)
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                freeze.capture(self.repo)
            path.unlink()
            saved.rename(path)
        self.reader.assert_not_called()

    def test_duplicate_json_fields_refused(self):
        path = self.fixture.output / 'credit-policy.json'
        path.write_text('{"project_cap_usd":null,"project_cap_usd":1}')
        with self.assertRaises(ValueError):
            freeze.capture(self.repo)
        self.reader.assert_not_called()

    def test_save_is_private_exclusive_and_idempotent(self):
        document = freeze.save(self.repo)
        path = self.repo / '.runtime/finalisation' / freeze.FREEZE_FILE
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertEqual(freeze.save(self.repo), document)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(freeze.verify(document, self.repo)['selected'], 'C3')

    def test_existing_freeze_not_replaced_after_evidence_changes(self):
        freeze.save(self.repo)
        path = self.repo / '.runtime/finalisation' / freeze.FREEZE_FILE
        before = path.read_bytes()
        self.fixture.data['rows'][0]['result_sha256'] = 'e' * 64
        with self.assertRaises(ValueError):
            freeze.save(self.repo)
        self.assertEqual(path.read_bytes(), before)

    def test_concurrent_saves_and_symlinked_state_refused(self):
        with patch.object(freeze, 'hold', side_effect=BlockingIOError), self.assertRaises(BlockingIOError):
            freeze.save(self.repo)
        self.reader.assert_not_called()
        path = self.repo / '.runtime/finalisation'
        saved = path.with_name('saved-finalisation')
        path.rename(saved)
        path.symlink_to(saved, target_is_directory=True)
        with self.assertRaises(ValueError):
            freeze.save(self.repo)

    def test_document_tampering_cannot_grant_admission(self):
        original = freeze.capture(self.repo)
        for change in ('paid', 'version', 'winner', 'runtime', 'anchor', 'logic', 'hash', 'extra'):
            value = deepcopy(original)
            if change == 'paid': value['paid_launch_ready'] = True
            elif change == 'version': value['schema_version'] = True
            elif change == 'winner': value['candidate']['selection']['selected'] = 'C1'
            elif change == 'runtime': value['selected_execution']['candidate_version'] = 'stage2-candidate-0.3.0'
            elif change == 'anchor': value['anchor_files'].pop(freeze.PRIVATE_QUALIFICATION)
            elif change == 'logic': value['selection_logic_sources'].pop(freeze.LOGIC_FILES[0])
            elif change == 'hash': value['original_audit_sha256'] = 'not-a-sha'
            else: value['requests'] = 'private'
            with self.subTest(change=change), self.assertRaises(ValueError):
                freeze.validate_document(value)


class OriginalReaderTests(unittest.TestCase):
    def test_uses_fixed_read_only_program_and_no_backup_or_paid_runner(self):
        expected = freeze._original_program()
        with patch.object(freeze.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"ok":true}', '')) as run:
            self.assertEqual(freeze._read_originals(), {'ok': True})
        self.assertEqual(run.call_args.kwargs['input'], expected)
        self.assertEqual(run.call_args.args[0], exporter.remote_command())
        self.assertIn(exporter.program(exporter.COLLECT, 'C3'), expected)
        self.assertNotIn('run_trial(', expected)
        self.assertNotIn(exporter.BACKUP, expected)
        compile(expected, '<original-audit>', 'exec')

    def test_persistent_stop_before_or_during_audit_refuses_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / '.runtime/stage2/operator-stop-request.json'
            marker.parent.mkdir(parents=True)
            with patch.object(exporter, 'REMOTE', folder), patch.object(exporter, 'COLLECT', 'pass'):
                exec(freeze._original_program(), {})
                marker.write_text('{}')
                with self.assertRaises(ValueError):
                    exec(freeze._original_program(), {})
                marker.unlink()
            with patch.object(exporter, 'REMOTE', folder), \
                    patch.object(exporter, 'COLLECT', '_candidate_stop.write_text("{}")'):
                with self.assertRaises(ValueError):
                    exec(freeze._original_program(), {})

    def test_failed_remote_audit_is_not_retried_or_leaked(self):
        with patch.object(freeze.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'private diagnostic')) as run:
            with self.assertRaises(RuntimeError) as raised:
                freeze._read_originals()
            self.assertNotIn('private diagnostic', str(raised.exception))
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
