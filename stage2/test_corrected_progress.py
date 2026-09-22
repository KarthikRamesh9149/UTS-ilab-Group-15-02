import copy
import json
from pathlib import Path
import unittest
from corrected_progress import summarise, Monitor, REMOTE, SERVICE


class ProgressTests(unittest.TestCase):
    def row(self, h='terminus-2', **kwargs):
        task = sorted(json.loads(Path(__file__).with_name('input_manifest.json').read_text())['all_task_ids'])[0]
        return dict(trial_id=f'corrected1-final-{h}-00-{task}', task_id=task, harness=h,
                    completed=True, reward=1, cleanup_complete=True, **kwargs)
    def raw(self, rows):
        return dict(rows=rows, observed_at_utc='2026-09-22T22:00:00Z', service={'ActiveState':'active','SubState':'running'})
    def test_score_does_not_require_cost_receipt(self):
        d = summarise(self.raw([self.row()]))
        self.assertEqual(d['conditions']['terminus-2']['passed'], 1)
        self.assertEqual(d['completed'], 1)
    def test_missing_and_false_rewards_are_not_failures(self):
        for reward in (None, True, 2):
            row=self.row();row['reward']=reward
            d=summarise(self.raw([row]))['conditions']['terminus-2']
            self.assertEqual((d['failed'],d['no_score']),(0,1))
    def test_duplicate_and_other_experiment_rejected(self):
        row=self.row()
        with self.assertRaises(ValueError): summarise(self.raw([row,row]))
        row['trial_id']=row['trial_id'].removeprefix('corrected1-')
        with self.assertRaises(ValueError): summarise(self.raw([row]))
    def test_running_is_not_completed(self):
        row=self.row();row['completed']=False;row['reward']=None
        d=summarise(self.raw([row]))
        self.assertEqual(d['completed'],0)
        self.assertEqual(len(d['active']),1)
    def test_failure_retains_last_snapshot(self):
        expected=summarise(self.raw([self.row()]))
        monitor=Monitor(lambda:expected);monitor.refresh()
        def fail(): raise OSError('offline')
        monitor.fetcher=fail;monitor.refresh()
        d=monitor.status()
        self.assertEqual(d['snapshot'],expected)
        self.assertTrue(d['stale'])
    def test_reader_is_metadata_only(self):
        self.assertIn(SERVICE,REMOTE)
        for forbidden in ('.env','request.json','response.json','load_key','OpenRouter'):
            self.assertNotIn(forbidden,REMOTE)
        html=Path(__file__).with_name('corrected_progress.html').read_text()
        self.assertNotIn('innerHTML',html)
        self.assertIn('setTimeout(poll,5000)',html)


if __name__=='__main__': unittest.main()
