"""Synthetic candidate evidence. No model calls, SSH or native admission."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_candidate_freeze import (
    FIXED, FREEZE_FILE, LOGIC_FILES, capture, save, validate_document, verify,
)
from portable_custom_policy import (
    BLOCKS, POLICY, POLICY_FILE, QUALIFICATION, fingerprint,
)
from scored_gateway import durable_json
from test_portable_final_selection import block


class FreezeFixture:
    """Private temporary fixture; inherited native validation is mocked explicitly."""
    def __init__(self, root):
        self.root = Path(root)
        self.runtime = self.root / '.runtime/stage2'
        self.runtime.mkdir(parents=True, mode=0o700)
        (self.runtime / BLOCKS).mkdir(mode=0o700)
        (self.root / 'stage2').mkdir()
        for name in LOGIC_FILES:
            (self.root / 'stage2' / name).write_text('# Synthetic ' + name + '\n')
        control = self.root / 'stage2/custom_control.py'
        control.write_text('# Synthetic behavior fixture\n')
        sources = {'custom_control.py': hashlib.sha256(control.read_bytes()).hexdigest()}
        self.proof = dict(sources=sources, sources_sha256=fingerprint(sources),
            dependencies={'python': '3.12.13', 'packages': {'harbor': '0.22.0'}})
        durable_json(self.runtime / QUALIFICATION, self.proof)
        durable_json(self.runtime / POLICY_FILE, POLICY)
        self.summaries = {'C0': block('C0', 14, unknown=True),
                          'C1': block('C1', 15), 'C2': block('C2', 16, 'C1')}
        self.completed = {}
        self.registrations = {}
        self.parent = {'parent': 'C1', 'fixture_only': True}
        for condition, value in self.summaries.items():
            registration = dict(condition=condition, parent=value['parent'],
                parent_selection=self.parent if condition == 'C2' else None,
                qualification_sha256=fingerprint(self.proof),
                sources_sha256=self.proof['sources_sha256'])
            self.registrations[condition] = registration
            durable_json(self.runtime / BLOCKS / (condition + '.json'), registration)
            for row in value['rows']:
                result = {key: row[key] for key in ('trial_id', 'task_id', 'harness')}
                result.update(stage='development', model_revoked=True, containers_removed=True,
                    networks_removed=True, volumes_removed=True, status='verified',
                    phase_seconds={'agent': row['agent_seconds']},
                    verifier_result={'rewards': {'reward': row['reward']}})
                path = self.runtime / 'scored-trials' / row['trial_id'] / 'result.json'
                path.parent.mkdir(parents=True, mode=0o700)
                durable_json(path, result)
                row['result_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.completed[row['trial_id']] = result

    def patches(self):
        stack = ExitStack()
        stack.enter_context(patch('portable_candidate_freeze.lock_all'))
        stack.enter_context(patch('portable_candidate_freeze.docker', return_value=''))
        stack.enter_context(patch('portable_candidate_freeze.qualified', return_value=self.proof))
        stack.enter_context(patch('portable_candidate_freeze.audited',
            side_effect=lambda root: (self.completed, [])))
        stack.enter_context(patch('portable_candidate_freeze.require_block',
            side_effect=lambda runtime, condition: self.registrations[condition]))
        stack.enter_context(patch('portable_candidate_freeze.summary',
            side_effect=lambda root, condition: self.summaries[condition]))
        stack.enter_context(patch('portable_candidate_freeze.selected_parent', return_value=self.parent))
        return stack


class CandidateFreezeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fixture = FreezeFixture(self.root)
        self.enterContext(self.fixture.patches())

    def test_all_sixty_results_bound_without_paid_admission(self):
        document = capture(self.root)
        selection = validate_document(document)
        self.assertEqual(selection['selected'], 'C2')
        self.assertEqual(len(document['result_bindings']), 60)
        self.assertEqual(set(document['registration_bindings']), {'C0', 'C1', 'C2'})
        self.assertFalse(document['paid_launch_ready'])
        self.assertEqual(verify(self.root, document), selection)

    def test_unknown_costs_do_not_block_freeze_or_become_zero(self):
        document = capture(self.root)
        self.assertIsNone(document['selection_inputs']['C0']['charged_usd'])
        self.assertEqual(document['selection_inputs']['C0']['unknown_cost_requests'], 20)
        self.assertFalse(document['selection']['cost_tiebreak_used'])

    def test_missing_reward_stays_missing_in_retained_denominator(self):
        value = self.fixture.summaries['C2']
        row = value['rows'][-1]
        row['reward'] = None
        value.update(failures=3, no_verifier_result=1)
        result = self.fixture.completed[row['trial_id']]
        result['verifier_result']['rewards']['reward'] = None
        path = self.fixture.runtime / 'scored-trials' / row['trial_id'] / 'result.json'
        path.write_text(json.dumps(result))
        row['result_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        document = capture(self.root)
        result = document['selection']['summaries']['C2']
        self.assertEqual((result['intended'], result['passes'], result['failures'],
                          result['no_verifier_result']), (20, 16, 3, 1))

    def test_capture_does_not_write_a_freeze_or_return_aliases(self):
        original = deepcopy(FIXED)
        original_sources = deepcopy(self.fixture.proof['sources'])
        document = capture(self.root)
        document['model_protocol']['temperature'] = 0
        document['development_sources']['custom_control.py'] = 'f' * 64
        self.assertEqual(FIXED, original)
        self.assertEqual(self.fixture.proof['sources'], original_sources)
        self.assertFalse((self.fixture.runtime / FREEZE_FILE).exists())

    def test_lock_contention_rejects_before_collecting(self):
        with patch('portable_candidate_freeze.lock_all', side_effect=BlockingIOError), \
                patch('portable_candidate_freeze.qualified') as qualifier:
            with self.assertRaises(BlockingIOError):
                capture(self.root)
            qualifier.assert_not_called()

    def test_active_owned_resources_refuse_freeze(self):
        with patch('portable_candidate_freeze.docker', return_value='owned-container'):
            with self.assertRaises(ValueError):
                capture(self.root)

    def test_persistent_stop_refuses_automatic_progress(self):
        durable_json(self.fixture.runtime / 'operator-stop-request.json', {'automatic_resume': False})
        with self.assertRaises(ValueError):
            save(self.root)
        self.assertFalse((self.fixture.runtime / FREEZE_FILE).exists())

    def test_partial_or_missing_blocks_refused(self):
        with patch('portable_candidate_freeze.audited', return_value=(self.fixture.completed, ['started'])):
            with self.assertRaises(ValueError):
                capture(self.root)
        self.fixture.completed.pop(next(iter(self.fixture.completed)))
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_cleanup_or_revocation_failure_refused(self):
        result = next(iter(self.fixture.completed.values()))
        for key in ('containers_removed', 'networks_removed', 'volumes_removed', 'model_revoked'):
            result[key] = False
            with self.assertRaises(ValueError):
                capture(self.root)
            result[key] = True

    def test_changed_c2_parent_registration_refused(self):
        self.fixture.registrations['C2']['parent_selection'] = {'parent': 'C0'}
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_changed_qualification_or_source_binding_refused(self):
        for key in ('qualification_sha256', 'sources_sha256'):
            previous = self.fixture.registrations['C0'][key]
            self.fixture.registrations['C0'][key] = '0' * 64
            with self.assertRaises(ValueError):
                capture(self.root)
            self.fixture.registrations['C0'][key] = previous

    def test_changed_result_bytes_refused(self):
        name = next(iter(self.fixture.completed))
        path = self.fixture.runtime / 'scored-trials' / name / 'result.json'
        path.write_text(path.read_text() + ' ')
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_summary_reward_cannot_disagree_with_bound_result(self):
        value = self.fixture.summaries['C2']
        value['rows'][-1]['reward'] = 1
        value.update(passes=17, failures=3)
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_summary_runtime_cannot_disagree_with_bound_result(self):
        value = self.fixture.summaries['C2']
        value['rows'][0]['agent_seconds'] = 0.
        value['agent_seconds'] -= 10.
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_registration_file_cannot_disagree_with_loaded_registration(self):
        path = self.fixture.runtime / BLOCKS / 'C0.json'
        value = deepcopy(self.fixture.registrations['C0'])
        value['qualification_sha256'] = '0' * 64
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_changed_development_source_refused(self):
        (self.root / 'stage2/custom_control.py').write_text('# changed behavior\n')
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_runtime_directory_symlink_refused_before_locking(self):
        path = self.fixture.runtime
        path.rename(path.with_name('saved-stage2'))
        path.symlink_to(path.with_name('saved-stage2'), target_is_directory=True)
        with patch('portable_candidate_freeze.lock_all') as locking:
            with self.assertRaises(ValueError):
                capture(self.root)
            locking.assert_not_called()

    def test_changed_policy_refused(self):
        path = self.fixture.runtime / POLICY_FILE
        value = deepcopy(POLICY)
        value['per_task_cap_usd'] = '0.01'
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_source_symlink_refused(self):
        path = self.root / 'stage2' / LOGIC_FILES[0]
        path.unlink()
        path.symlink_to(self.root / 'stage2' / LOGIC_FILES[1])
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_evidence_parent_symlink_refused(self):
        path = self.fixture.runtime / BLOCKS
        path.rename(path.with_name('saved-blocks'))
        path.symlink_to(path.with_name('saved-blocks'), target_is_directory=True)
        with self.assertRaises(ValueError):
            capture(self.root)

    def test_metadata_allowlist_excludes_private_extras(self):
        self.fixture.summaries['C0']['messages'] = ['must not be exported']
        self.fixture.summaries['C0']['rows'][0]['response'] = 'must not be exported'
        document = capture(self.root)
        self.assertNotIn('must not be exported', json.dumps(document))

    def test_save_is_exclusive_and_idempotent(self):
        document = save(self.root)
        path = self.fixture.runtime / FREEZE_FILE
        before = path.read_bytes(), path.stat().st_mtime_ns
        self.assertEqual(save(self.root), document)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_existing_freeze_never_overwritten_after_code_change(self):
        save(self.root)
        path = self.fixture.runtime / FREEZE_FILE
        before = path.read_bytes()
        (self.root / 'stage2' / LOGIC_FILES[0]).write_text('# changed\n')
        with self.assertRaises(ValueError):
            save(self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_verify_rejects_changed_selection_logic(self):
        document = capture(self.root)
        (self.root / 'stage2' / LOGIC_FILES[-1]).write_text('# changed tests\n')
        with self.assertRaises(ValueError):
            verify(self.root, document)

    def test_tampered_document_rejected(self):
        original = capture(self.root)
        mutations = (
            lambda d: d.update(paid_launch_ready=True),
            lambda d: d.update(schema_version=True),
            lambda d: d['model_protocol'].update(temperature=0),
            lambda d: d['selection'].update(selected='C0'),
            lambda d: d['selection_inputs']['C0'].update(passes=20),
            lambda d: d['selection_inputs']['C0']['rows'][0].update(messages=[]),
            lambda d: d.update(development_sources={}),
            lambda d: d['development_sources'].update({'../outside.py': 'a' * 64}),
            lambda d: d['registration_bindings'].pop('C1'),
            lambda d: d['result_bindings'].pop(next(iter(d['result_bindings']))),
            lambda d: d['selection_logic_sources'].pop(LOGIC_FILES[0]),
            lambda d: d.update(qualification_file_sha256='missing'),
            lambda d: d.update(messages=[]),
        )
        for mutate in mutations:
            document = deepcopy(original)
            mutate(document)
            with self.assertRaises(ValueError):
                validate_document(document)


if __name__ == '__main__':
    unittest.main()
