from copy import deepcopy
import unittest
from deadline_custom_policy import cells
from deadline_final_selection import select,checked_c3
from test_deadline_custom_policy import parent_fixture
from test_portable_final_selection import block,TASKS


def c3_block(passes=16,unknown=True):
    value=block('C0',passes,unknown=unknown)
    value.update(condition='C3',parent='C0',base_parent=None,complexity=1)
    for row,identity in zip(value['rows'],cells(TASKS)):row.update(identity)
    return value


class SelectionTests(unittest.TestCase):
    def test_best_whole_variant_with_all_eighty_results(self):
        p=parent_fixture();value=select(dict(p['summaries'],C3=c3_block()),p)
        self.assertEqual(value['selected'],'C3');self.assertEqual(value['total_development_attempts'],80)
        self.assertEqual(value['diagnostic']['kind'],'combined_revision_parent_comparison')
        self.assertFalse(value['diagnostic']['causal_single_lever_claim'])
        self.assertFalse(value['cost_tiebreak_used']);self.assertFalse(value['paid_launch_ready'])

    def test_newer_c3_is_not_automatically_promoted(self):
        p=parent_fixture()
        for count in (0,14,15):
            self.assertEqual(select(dict(p['summaries'],C3=c3_block(count)),p)['selected'],'C0')

    def test_missing_cost_never_becomes_zero_or_efficiency_win(self):
        p=parent_fixture();value=select(dict(p['summaries'],C3=c3_block()),p)
        self.assertIsNone(value['summaries']['C3']['charged_usd'])
        self.assertFalse(value['efficiency_win_claimed'])

    def test_incomplete_lineage_and_modified_old_results_rejected(self):
        p=parent_fixture()
        for change in ('partial','parent','base','trial','reward','count','old'):
            values=dict(deepcopy(p['summaries']),C3=c3_block())
            if change=='partial':values['C3']['rows'].pop()
            elif change=='parent':values['C3']['parent']='C1'
            elif change=='base':values['C3']['base_parent']='C0'
            elif change=='trial':values['C3']['rows'][0]['trial_id']='customdev2-c0-01-video-processing'
            elif change=='reward':values['C3']['rows'][0]['reward']=True
            elif change=='count':values['C3']['passes']=20
            else:values['C0']['passes']=20
            with self.subTest(change=change),self.assertRaises(ValueError):select(values,p)


if __name__=='__main__':unittest.main()
