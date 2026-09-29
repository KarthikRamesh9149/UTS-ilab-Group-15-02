"""Offline fixed recovery planning; no registration or native execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import matched_repeat_schedule as baseline
from model_protocol import ModelSettings
import no_cutoff_recovery_plan as recovery


class RecoveryPlanTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((Path(__file__).parent / 'input_manifest.json').read_bytes())
        self.plan = recovery.schedule(self.manifest)

    def test_only_three_exact_original_tasks_in_original_order(self):
        cells = self.plan['cells']
        self.assertEqual([c['original_ordinal'] for c in cells], [63, 64, 65])
        self.assertEqual([c['task_id'] for c in cells], [t for _, t, _ in recovery.TARGETS])
        self.assertEqual([c['original_result_sha256'] for c in cells], [h for _, _, h in recovery.TARGETS])
        self.assertEqual(self.plan['intended'], 3)
        self.assertEqual(self.plan['parallel_trials'], 1)
        self.assertEqual(self.plan['attempts_per_registered_cell'], 1)

    def test_new_keys_overlap_neither_original89_nor_baseline_repeats(self):
        old = {recovery.original_id(i, task) for i, task in enumerate(baseline.task_order(self.manifest), 1)}
        repeats = {c['trial_id'] for b in baseline.schedule(self.manifest)['blocks'] for c in b['cells']}
        for cell in self.plan['cells']:
            self.assertNotIn(cell['trial_id'], old | repeats)
            self.assertIn(cell['original_trial_id'], old)
            self.assertEqual(cell['trial_id'], 'customrecovery1-c0-nc-' + cell['original_trial_id'].split('customfinal2-c0-nc-')[1])
            self.assertEqual(cell['recovery_attempt'], 1)
            self.assertLessEqual(len(cell['trial_id']), 120)

    def test_original_missing_results_and_separate_denominators_remain(self):
        self.assertEqual(self.plan['original_full89_denominator'], 89)
        self.assertEqual(self.plan['separate_recovery_denominator'], 3)
        for cell in self.plan['cells']:
            self.assertIsNone(cell['original_reward'])
            self.assertEqual(cell['original_outcome'], 'setup_only_missing_verifier')
        for name in ('original_results_replaced', 'recovery_merged_into_original89',
                'best_of_selection', 'success_guaranteed', 'automatic_task_replay'):
            self.assertIs(self.plan[name], False)

    def test_model_tools_and_existing_setup_rules_unchanged(self):
        self.assertEqual(self.plan['model_protocol_sha256'], baseline.MODEL_SHA256)
        self.assertEqual(self.plan['model_protocol'], ModelSettings(384000, 1., 'high').document())
        self.assertEqual(self.plan['agent_prompt_tools_model'], 'original-qualified-C0-NC-unchanged')
        self.assertEqual(self.plan['setup_timeout_seconds'], 900)
        self.assertEqual(self.plan['package_command_timeout_seconds'], 180)
        self.assertEqual(self.plan['setup_preparation'], 'same-original-index-refresh-no-automatic-retry')

    def test_official_resource_and_config_bindings_match_exact_manifest(self):
        tasks = {r['task_id']: r for r in self.manifest['tasks']}
        for cell in self.plan['cells']:
            source = tasks[cell['task_id']]
            self.assertEqual(cell['task_config_sha256'], source['task_config_sha256'])
            self.assertEqual(cell['official_resources'], {k: source[k] for k in ('cpus', 'memory_mb', 'storage_mb', 'gpus')})
        self.assertEqual(self.plan['task_time_and_resources'], 'official-unchanged')

    def test_baseline_schedule_and_order_unchanged(self):
        self.assertEqual(self.plan['baseline_schedule_sha256'],
            'bd26df6c19c88c238d0795423699fa9030a12f4ea925b42667ad75321817a6e1')
        self.assertEqual(self.plan['baseline_order'], ['terminus-2', 'openhands'])
        self.assertIs(self.plan['baseline_schedule_changed'], False)

    def test_plan_never_grants_qualification_or_paid_admission(self):
        for key in ('registered', 'recovery_execution_qualified', 'paid_launch_ready'):
            self.assertIs(self.plan[key], False)
        self.assertIn('not_admission', self.plan['kind'])
        self.assertIn('real-isolated-native-regressions-and-lifecycle-qualification', self.plan['requirements'])
        self.assertIn('fresh-original-audit-and-existing-archive-authentication', self.plan['requirements'])

    def test_no_financial_or_request_cap_unknown_cost_not_zero(self):
        account = self.plan['accounting']
        for key in ('project_cap_usd', 'per_task_cap_usd', 'model_call_cap', 'physical_request_count_cap'):
            self.assertIsNone(account[key])
        for key in ('accounting_blocks_dispatch', 'unknown_cost_is_zero', 'automatic_top_up',
                'automatic_purchase', 'automatic_credit_limit_increase'):
            self.assertIs(account[key], False)
        self.assertIs(account['shared_provider_cooldown'], True)

    def test_unknown_lower_cause_is_not_fabricated(self):
        self.assertEqual(self.plan['lower_level_original_cause'], 'not_retained_not_established')
        self.assertFalse(self.plan['arbitrary_failed_task_selection'])
        with self.assertRaises(TypeError): recovery.schedule(self.manifest, failed_tasks=['x'])

    def test_deterministic_independent_and_nonmutating(self):
        before = deepcopy(self.manifest)
        self.assertEqual(recovery.validate_schedule(self.plan, self.manifest), self.plan)
        self.assertEqual(before, self.manifest)
        self.plan['cells'][0]['official_resources']['cpus'] = 99
        self.assertEqual(recovery.schedule(self.manifest)['cells'][0]['official_resources']['cpus'], 1)

    def test_changed_manifest_or_model_refused(self):
        altered = deepcopy(self.manifest); altered['development_ids'].reverse()
        with self.assertRaises(ValueError): recovery.schedule(altered)
        with patch.object(recovery, 'SETTINGS', ModelSettings(64000, 1., 'high')):
            with self.assertRaises(ValueError): recovery.schedule(self.manifest)

    def test_changed_plan_flags_types_identity_or_order_refused(self):
        for mutate in (lambda p: p.update(paid_launch_ready=True),
                lambda p: p.update(intended=True), lambda p: p['cells'].reverse(),
                lambda p: p['cells'][0].update(trial_id=p['cells'][0]['original_trial_id']),
                lambda p: p.update(recovery_merged_into_original89=True),
                lambda p: p['cells'][0].update(original_reward=0)):
            altered = deepcopy(self.plan); mutate(altered)
            with self.assertRaises(ValueError): recovery.validate_schedule(altered, self.manifest)
        for value in (None, [], 'plan'):
            with self.assertRaises(ValueError): recovery.validate_schedule(value, self.manifest)

    def test_nonapproved_target_or_wrong_original_ordinal_refused(self):
        ordinal, task, sha = recovery.TARGETS[0]
        with patch.object(recovery, 'TARGETS', ((ordinal + 1, task, sha), *recovery.TARGETS[1:])):
            with self.assertRaises(ValueError): recovery.schedule(self.manifest)
