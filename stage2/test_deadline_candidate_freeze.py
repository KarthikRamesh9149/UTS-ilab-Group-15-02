from copy import deepcopy
import json
from pathlib import Path
import unittest
from deadline_candidate_freeze import freeze,validate_document
from deadline_evaluation_schedule import schedule
from test_deadline_custom_policy import parent_fixture
from test_deadline_final_selection import c3_block


def candidate():
    return freeze(parent_fixture(),c3_block(),registration_sha256='f'*64,
        qualification_sha256='e'*64,sources={'fixture.py':'d'*64},
        dependencies={'python':'3.12.13','packages':{'harbor':'0.22.0'}})


class FreezeTests(unittest.TestCase):
    def test_eighty_bound_results_but_no_paid_admission(self):
        document=candidate();self.assertEqual(len(document['result_bindings']),80)
        self.assertEqual(validate_document(document)['selected'],'C3')
        self.assertFalse(document['paid_launch_ready'])

    def test_changed_evidence_and_false_admission_rejected(self):
        for change in ('hash','source','scope','winner','paid','lineage','unknown'):
            d=candidate()
            if change=='hash':d['result_bindings'].pop(next(iter(d['result_bindings'])))
            elif change=='source':d['c3_sources']={'../secret':'a'*64}
            elif change=='scope':d['development_ids_sha256']='b'*64
            elif change=='winner':d['selection']['selected']='C1'
            elif change=='paid':d['paid_launch_ready']=True
            elif change=='lineage':d['c3_summary']['parent']='C1'
            else:d['extra']='private data'
            with self.subTest(change=change),self.assertRaises(ValueError):validate_document(d)

    def test_exact_fresh_post_development_schedules(self):
        manifest=json.loads((Path(__file__).parent/'input_manifest.json').read_text())
        ids=[]
        for phase,count in (('confirmation',60),('diagnostic',20),('final',89)):
            value=schedule(candidate(),manifest,phase);self.assertEqual(len(value['cells']),count)
            self.assertFalse(value['paid_launch_ready']);self.assertEqual(value['parallel_trials'],1)
            ids.extend(r['trial_id'] for r in value['cells'])
            if phase=='final':
                self.assertEqual({r['task_id'] for r in value['cells']},set(manifest['all_task_ids']))
                self.assertTrue(all(r['harness']=='C3' and r['parent']=='C0' for r in value['cells']))
            else:self.assertEqual({r['task_id'] for r in value['cells']},set(manifest['development_ids']))
        self.assertEqual(len(ids),len(set(ids)))


if __name__=='__main__':unittest.main()
