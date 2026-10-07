import unittest
from uts_harness.control import Condition, CompletionControl, PLAN_PROMPT, CHECK_PROMPT


class ControlTests(unittest.TestCase):
    def test_variants_change_only_registered_prompt_additions(self):
        self.assertEqual(Condition('C1').prompt, Condition('C0').prompt + '\n\n' + PLAN_PROMPT)
        for parent in ['C0', 'C1']:
            self.assertEqual(Condition('C2', parent).prompt, Condition(parent).prompt + '\n\n' + CHECK_PROMPT)

    def test_parent_must_be_explicit(self):
        for name, parent in [('C2', None), ('C2', 'C2'), ('C0', 'C1'), ('other', None)]:
            with self.assertRaises(ValueError):
                Condition(name, parent)

    def test_equal_repair_allowance_and_no_fourth_attempt(self):
        for condition in [Condition('C0'), Condition('C1'), Condition('C2', 'C0'), Condition('C2', 'C1')]:
            control = CompletionControl(condition)
            self.assertEqual(control.incomplete('missing')['repair_number'], 1)
            self.assertEqual(control.incomplete('missing')['repair_number'], 2)
            self.assertEqual(control.incomplete('missing')['status'], 'repair_exhausted')
            self.assertEqual(control.complete('later')['status'], 'repair_exhausted')
            self.assertEqual(len(control.events), 3)

    def test_complete_is_not_verified_success(self):
        control = CompletionControl(Condition('C0'))
        result = control.complete('Done')
        self.assertIsNone(result['benchmark_success'])
        self.assertEqual(result['status'], 'agent_reported_complete')

    def test_c2_rejects_missing_empty_or_false_observations(self):
        for checks in [None, [], [{}], [{'criterion': 'x', 'observation': 'seen', 'satisfied': False}],
                       [{'criterion': 'x', 'observation': '', 'satisfied': True}],
                       [{'criterion': 'x', 'observation': 'seen', 'satisfied': 1}]]:
            control = CompletionControl(Condition('C2', 'C0'))
            self.assertEqual(control.complete('Done', checks)['status'], 'repair_requested')

    def test_legitimate_no_edit_completion(self):
        control = CompletionControl(Condition('C2', 'C1'))
        result = control.complete('Already correct', [{'criterion': 'Service healthy',
            'observation': 'Health response was 200 with expected body', 'satisfied': True}],
            no_edit_reason='Requested configuration was already present')
        self.assertEqual(result['status'], 'agent_reported_complete')
        self.assertEqual(control.repairs_used, 0)

    def test_state_is_per_trial_and_abandon_is_terminal(self):
        a, b = CompletionControl(Condition('C0')), CompletionControl(Condition('C0'))
        a.incomplete('x')
        self.assertEqual(b.repairs_used, 0)
        a.abandon('Cannot resolve')
        self.assertEqual(a.complete('Done')['status'], 'agent_reported_incomplete')


if __name__ == '__main__':
    unittest.main()
