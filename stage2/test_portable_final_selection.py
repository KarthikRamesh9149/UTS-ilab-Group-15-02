"""Synthetic metadata only. No model calls, SSH or benchmark execution."""
import copy
import json
from pathlib import Path
import unittest

from portable_custom_policy import cells
from portable_final_selection import select


TASKS = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())['development_ids']


def block(condition, passes, parent=None, cost='1', unknown=False):
    from decimal import Decimal
    rows = [dict(cell, reward=int(index < passes), agent_seconds=10.,
        charged_usd=None if unknown else cost, known_charged_usd=cost,
        unknown_cost_requests=int(unknown), requests=200,
        result_sha256=f'{index + 1:064x}')
        for index, cell in enumerate(cells(TASKS, condition, parent))]
    total = str(Decimal(cost) * 20)
    return dict(condition=condition, parent=parent, intended=20, attempted=20,
        passes=passes, failures=20-passes, no_verifier_result=0,
        started_without_result=[], charged_usd=None if unknown else total,
        known_charged_usd=total, unknown_cost_requests=20 if unknown else 0,
        agent_seconds=200.,
        complexity=int(condition == 'C1' or parent == 'C1') + int(condition == 'C2'), rows=rows)


class PortableFinalSelectionTests(unittest.TestCase):
    def setUp(self):
        self.blocks = {'C0': block('C0', 14), 'C1': block('C1', 15),
                       'C2': block('C2', 16, 'C1')}

    def test_best_complete_variant_is_not_a_final_score(self):
        result = select(self.blocks)
        self.assertEqual((result['selected'], result['custom_parent']), ('C2', 'C1'))
        self.assertEqual(result['total_development_attempts'], 60)
        self.assertFalse(result['paid_launch_ready'])
        self.assertFalse(result['full_benchmark_win_claimed'])
        self.assertEqual(result['primary_comparator'], 'terminus-2')

    def test_huge_cost_and_request_counts_are_not_spending_caps(self):
        self.blocks['C2'] = block('C2', 16, 'C1', cost='999999999.123456789')
        for row in self.blocks['C2']['rows']: row['requests'] = 1000000
        self.assertEqual(select(self.blocks)['selected'], 'C2')

    def test_all_unknown_costs_are_allowed(self):
        for name in self.blocks:
            old = self.blocks[name]
            self.blocks[name] = block(name, old['passes'], old['parent'], unknown=True)
        result = select(self.blocks)
        self.assertEqual(result['selected'], 'C2')
        self.assertFalse(result['cost_tiebreak_used'])
        self.assertIsNone(result['summaries']['C2']['charged_usd'])

    def test_unknown_c2_cost_does_not_change_preselected_parent(self):
        self.blocks = {'C0': block('C0', 15, cost='2'), 'C1': block('C1', 15),
                       'C2': block('C2', 15, 'C1', unknown=True)}
        result = select(self.blocks)
        self.assertEqual(result['selected_parent'], 'C1')
        self.assertTrue(result['parent_cost_tiebreak_used'])
        self.assertFalse(result['cost_tiebreak_used'])
        self.assertEqual(result['selected'], 'C0')

    def test_cost_breaks_accuracy_tie_only_when_all_complete(self):
        self.blocks = {'C0': block('C0', 15, cost='2'), 'C1': block('C1', 15),
                       'C2': block('C2', 15, 'C1', cost='0.5')}
        self.assertEqual(select(self.blocks)['selected'], 'C2')

    def test_simple_parent_wins_when_cost_tie_is_unavailable(self):
        self.blocks = {'C0': block('C0', 15, unknown=True), 'C1': block('C1', 15),
                       'C2': block('C2', 14, 'C0')}
        self.assertEqual(select(self.blocks)['selected'], 'C0')

    def test_missing_reward_is_distinct_not_a_verified_failure(self):
        value=self.blocks['C2']; value['rows'][-1]['reward']=None
        value.update(failures=3, no_verifier_result=1)
        result=select(self.blocks)
        self.assertEqual(result['summaries']['C2']['no_verifier_result'],1)
        self.assertEqual(result['summaries']['C2']['failures'],3)

    def test_missing_runtime_is_not_zero(self):
        self.blocks['C2']['agent_seconds']=None
        self.blocks['C2']['rows'][0]['agent_seconds']=None
        self.assertIsNone(select(self.blocks)['summaries']['C2']['agent_seconds'])

    def test_incomplete_or_partial_blocks_rejected(self):
        for mutation in ('drop_block', 'drop_row', 'partial'):
            data=copy.deepcopy(self.blocks)
            if mutation=='drop_block':data.pop('C2')
            elif mutation=='drop_row':data['C2']['rows'].pop()
            else:data['C2']['started_without_result']=['started']
            with self.assertRaises(ValueError):select(data)

    def test_summary_score_or_cost_tampering_rejected(self):
        for key,value in (('passes',20),('known_charged_usd','0'),('agent_seconds',0),
                          ('complexity',0),('charged_usd','999')):
            data=copy.deepcopy(self.blocks);data['C2'][key]=value
            with self.assertRaises(ValueError):select(data)

    def test_wrong_parent_rejected(self):
        self.blocks['C2']=block('C2',16,'C0')
        with self.assertRaises(ValueError):select(self.blocks)

    def test_order_duplicates_and_trial_substitution_rejected(self):
        for mutation in ('order','duplicate','other_trial'):
            data=copy.deepcopy(self.blocks);rows=data['C2']['rows']
            if mutation=='order':rows.reverse()
            elif mutation=='duplicate':rows[1]=rows[0]
            else:rows[0]['trial_id']='customdev2-c0-01-video-processing'
            with self.assertRaises(ValueError):select(data)

    def test_invalid_types_and_nonfinite_values_rejected(self):
        for key,value in (('reward',True),('reward',float('nan')),('agent_seconds',float('inf')),
                          ('requests',True),('known_charged_usd','NaN'),
                          ('charged_usd','-1'),('result_sha256','missing')):
            data=copy.deepcopy(self.blocks);data['C2']['rows'][0][key]=value
            with self.assertRaises(ValueError):select(data)

    def test_unknown_cost_cannot_be_reported_as_complete(self):
        value=self.blocks['C2'];value['rows'][0]['unknown_cost_requests']=1
        with self.assertRaises(ValueError):select(self.blocks)

    def test_selection_does_not_mutate_retained_evidence(self):
        before=copy.deepcopy(self.blocks)
        select(self.blocks)
        self.assertEqual(self.blocks,before)

    def test_missing_metadata_is_rejected_not_inferred(self):
        for key in ('reward', 'charged_usd', 'agent_seconds', 'result_sha256'):
            data = copy.deepcopy(self.blocks)
            data['C2']['rows'][0].pop(key)
            with self.assertRaises(ValueError):
                select(data)

    def test_malformed_summary_or_row_is_rejected(self):
        for data in (None, [], dict(self.blocks, C2=None)):
            with self.assertRaises(ValueError):
                select(data)
        data = copy.deepcopy(self.blocks)
        data['C2']['rows'][0] = None
        with self.assertRaises(ValueError):
            select(data)

    def test_tied_incremental_gain_ablates_completion(self):
        self.assertEqual(select(self.blocks)['diagnostic'], dict(
            kind='ablation', remove='completion', incremental_pass_gain=1,
            condition='C1', parent=None))

    def test_larger_planning_gain_retains_completion_in_ablation(self):
        self.blocks['C0'] = block('C0', 10)
        self.assertEqual(select(self.blocks)['diagnostic'], dict(
            kind='ablation', remove='planning', incremental_pass_gain=5,
            condition='C2', parent='C0'))

    def test_planning_winner_ablates_planning(self):
        self.blocks['C2'] = block('C2', 14, 'C1')
        self.assertEqual(select(self.blocks)['diagnostic'], dict(
            kind='ablation', remove='planning', incremental_pass_gain=1,
            condition='C0', parent=None))

    def test_control_winner_has_only_unchanged_repeat(self):
        self.blocks = {'C0': block('C0', 16), 'C1': block('C1', 15),
                       'C2': block('C2', 14, 'C0')}
        self.assertEqual(select(self.blocks)['diagnostic'], dict(
            kind='unchanged_repeat', condition='C0', parent=None))

    def test_completion_without_planning_ablates_to_control(self):
        self.blocks = {'C0': block('C0', 15), 'C1': block('C1', 14),
                       'C2': block('C2', 16, 'C0')}
        self.assertEqual(select(self.blocks)['diagnostic'], dict(
            kind='ablation', remove='completion', incremental_pass_gain=1,
            condition='C0', parent=None))

    def test_cost_only_selection_does_not_invent_accuracy_gain(self):
        self.blocks = {'C0': block('C0', 15, cost='2'), 'C1': block('C1', 15),
                       'C2': block('C2', 15, 'C1', cost='0.5')}
        result = select(self.blocks)
        self.assertEqual(result['diagnostic'], dict(
            kind='unchanged_repeat', condition='C2', parent='C1'))
        self.assertFalse(result['efficiency_win_claimed'])


if __name__=='__main__':
    unittest.main()
