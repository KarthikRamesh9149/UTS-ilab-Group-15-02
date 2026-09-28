"""Offline repeat planning only; no native qualification or model requests."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import matched_repeat_schedule as repeat
from model_protocol import ModelSettings


class RepeatScheduleTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())
        self.plan = repeat.schedule(self.manifest)

    def test_exact_two_sequential_blocks_and_178_unique_keys(self):
        blocks = self.plan['blocks']
        self.assertEqual([b['harness'] for b in blocks], ['terminus-2', 'openhands'])
        self.assertEqual([len(b['cells']) for b in blocks], [89, 89])
        ids = [c['trial_id'] for b in blocks for c in b['cells']]
        self.assertEqual(len(set(ids)), 178)
        self.assertTrue(all(name.startswith('matchedrepeat1-') for name in ids))
        self.assertEqual(self.plan['total_repeat_attempts'], 178)
        self.assertEqual(self.plan['parallel_trials'], 1)

    def test_both_baselines_cover_exact_same_89_tasks_in_order(self):
        expected = repeat.task_order(self.manifest)
        for block in self.plan['blocks']:
            self.assertEqual([c['task_id'] for c in block['cells']], expected)
            self.assertEqual(set(expected), set(self.manifest['all_task_ids']))
            self.assertEqual(expected[:20], self.manifest['development_ids'])
            for i, cell in enumerate(block['cells'], 1):
                self.assertEqual(cell['trial_id'], f"matchedrepeat1-{block['harness']}-{i:02d}-{cell['task_id']}")
                self.assertEqual(cell['attempt'], 1)
                self.assertEqual(cell['stage'], 'final')
                self.assertEqual(cell['phase'], 'matched-baseline-repeat')

    def test_task_order_matches_unchanged_custom_final_builder(self):
        import no_cutoff_final_policy as final
        # Final task ordering does not depend on a score. This test substitutes
        # only the separate candidate-validation step, not native admission.
        with patch.object(final, 'candidate_execution', return_value={}):
            cells = final.cells({}, self.manifest)
        self.assertEqual(repeat.task_order(self.manifest), [c['task_id'] for c in cells])
        prior_ids = {c['trial_id'] for c in cells}
        for block in self.plan['blocks']:
            self.assertFalse(prior_ids & {c['trial_id'] for c in block['cells']})

    def test_prerequisites_require_custom_first_then_terminus_before_openhands(self):
        self.assertEqual(self.plan['execution_order'], ['custom-final89', 'terminus-2', 'openhands'])
        self.assertEqual(self.plan['blocks'][0]['prerequisite'], 'custom-final89-audited-and-privately-backed-up')
        self.assertEqual(self.plan['blocks'][1]['prerequisite'], 'matched-terminus-2-repeat89-audited-and-privately-backed-up')
        self.assertTrue(self.plan['requires_completed_custom_audit_and_backup'])

    def test_original_comparators_scores_and_baseline_behaviour_remain(self):
        self.assertEqual(self.plan['original_scores'], {'terminus-2': 52, 'openhands': 44})
        self.assertEqual(self.plan['primary_comparator'], 'terminus-2')
        self.assertEqual(self.plan['secondary_comparator'], 'openhands')
        self.assertFalse(self.plan['original_results_replaced'])
        self.assertEqual(self.plan['baseline_agent_behaviour'], 'original-corrected-unchanged')
        from retry_policy import POLICY
        self.assertEqual(self.plan['inherited_baseline_turn_guards'], {
            'terminus-2': POLICY['terminus_default_max_turns'],
            'openhands': POLICY['openhands_max_iterations']})

    def test_uncapped_passive_accounting_does_not_hide_native_turn_guards(self):
        account = self.plan['accounting']
        for name in ('per_task_cap_usd', 'project_cap_usd', 'additional_model_call_cap',
                'additional_physical_request_count_cap', 'retry_count_cap'):
            self.assertIsNone(account[name])
        self.assertEqual(account['reserve_usd'], '0')
        self.assertFalse(account['accounting_blocks_dispatch'])
        self.assertFalse(account['unknown_cost_is_zero'])
        self.assertFalse(account['automatic_top_up'])
        self.assertTrue(account['shared_provider_cooldown'])
        self.assertEqual(set(self.plan['inherited_baseline_turn_guards'].values()), {1000000})

    def test_schedules_do_not_grant_qualification_registration_or_paid_admission(self):
        self.assertEqual(self.plan['kind'], 'matched_baseline_repeat_schedule_not_admission')
        self.assertFalse(self.plan['paid_launch_ready'])
        self.assertFalse(self.plan['full_benchmark_win_claimed'])
        for field in ('requires_native_source_authentication', 'requires_separate_native_qualification',
                'requires_exact_registration'):
            self.assertTrue(self.plan[field])
        self.assertNotIn('qualification_sha256', self.plan)

    def test_no_outcome_input_or_extra_confirmation_diagnostic(self):
        self.assertFalse(self.plan['outcome_dependent_selection'])
        for phase in ('confirmation60', 'diagnostic20'):
            self.assertEqual(self.plan[phase + '_status'], 'deferred_not_run')
        with self.assertRaises(TypeError): repeat.schedule(self.manifest, custom_score=0)

    def test_exact_manifest_refuses_changed_scope_order_or_metadata(self):
        for mutate in (lambda m: m['development_ids'].reverse(),
                lambda m: m['all_task_ids'].pop(), lambda m: m.update(outcomes=[]),
                lambda m: m['outside_development_ids'].append(m['development_ids'][0])):
            altered = deepcopy(self.manifest); mutate(altered)
            with self.assertRaises(ValueError): repeat.schedule(altered)
        for value in (None, [], 'manifest'):
            with self.assertRaises(ValueError): repeat.schedule(value)

    def test_settings_match_pinned_model_and_cannot_drift(self):
        self.assertEqual(self.plan['model_protocol_sha256'], repeat.MODEL_SHA256)
        self.assertEqual(self.plan['model_protocol'], ModelSettings(384000, 1., 'high').document())
        with patch.object(repeat, 'SETTINGS', ModelSettings(64000, 1., 'high')):
            with self.assertRaises(ValueError): repeat.schedule(self.manifest)

    def test_schedule_is_deterministic_and_does_not_mutate_manifest_or_share_state(self):
        before = deepcopy(self.manifest)
        self.assertEqual(repeat.validate_schedule(self.plan, self.manifest), self.plan)
        self.assertEqual(repeat.schedule(self.manifest), self.plan)
        self.assertEqual(before, self.manifest)
        self.plan['blocks'][0]['cells'][0]['task_id'] = 'changed'
        self.assertNotEqual(repeat.schedule(self.manifest), self.plan)
        self.assertNotEqual(self.plan['blocks'][1]['cells'][0]['task_id'], 'changed')

    def test_forged_flags_types_or_priorities_refused(self):
        for changes in ({'paid_launch_ready': True}, {'paid_launch_ready': 0},
                {'parallel_trials': 2}, {'total_repeat_attempts': 179}, {'automatic_task_replay': True},
                {'outcome_dependent_selection': True}, {'extra_variant': 'C4'},
                {'primary_comparator': 'openhands'}, {'original_scores': {'terminus-2': 89, 'openhands': 89}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                repeat.validate_schedule(self.plan | changes, self.manifest)

    def test_missing_duplicate_reordered_or_replayed_cells_refused(self):
        for mutate in (lambda p: p['blocks'].reverse(),
                lambda p: p['blocks'][0]['cells'].pop(),
                lambda p: p['blocks'][0]['cells'].reverse(),
                lambda p: p['blocks'][0]['cells'][0].update(trial_id='corrected1-original-key'),
                lambda p: p['blocks'][0]['cells'][0].update(attempt=2),
                lambda p: p['blocks'][0]['cells'].append(p['blocks'][0]['cells'][0])):
            altered = deepcopy(self.plan); mutate(altered)
            with self.assertRaises(ValueError): repeat.validate_schedule(altered, self.manifest)

    def test_new_request_limits_or_changed_native_guards_refused(self):
        for mutate in (lambda p: p['accounting'].update(additional_model_call_cap=100),
                lambda p: p['accounting'].update(reserve_usd='1'),
                lambda p: p['accounting'].update(unknown_cost_is_zero=True),
                lambda p: p['inherited_baseline_turn_guards'].update(openhands=None)):
            altered = deepcopy(self.plan); mutate(altered)
            with self.assertRaises(ValueError): repeat.validate_schedule(altered, self.manifest)

    def test_import_is_independent_of_native_host_agent_and_paid_clients(self):
        script = '''
import sys
class Block:
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'harbor','deepagents','langgraph','retry_runtime',
   'openrouter_transport','no_cutoff_final_policy','no_cutoff_final_evidence','subprocess'}:
   raise RuntimeError('Heavy or provider module imported: '+fullname)
sys.meta_path.insert(0,Block())
import matched_repeat_schedule
'''
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=Path(__file__).parent,
            text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
