"""Offline tests: synthetic metadata and loopback HTTP only; never SSH."""
import contextlib
import copy
import http.client
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import progress_dashboard as panel


MANIFEST = {'development_ids': [f'task-{i:02}' for i in range(20)],
            'all_task_ids': [f'task-{i:02}' for i in range(89)]}


def record(index=0, harness='terminus-2', stage='development', **changes):
    role = 'custom' if stage == 'final' and harness in ('C0','C1','C2') else harness
    trial = f'{"dev" if stage == "development" else "final"}-{role}-{index:02}-task-{index:02}'
    row = dict(trial_id=trial, directory=trial, task_id=f'task-{index:02}', stage=stage,
               harness=harness, status='verified', reward=0, has_result=True, has_started=True,
               billing_verified=True, budget_stop_count=0)
    row.update(changes)
    return row


def six_records():
    return [record(i, reward=1 if i == 3 else 0, budget_stop_count=1 if i < 3 else 0 if i == 3 else None,
                   billing_verified=i < 4, status='verified' if i < 4 else 'billing_unresolved')
            for i in range(6)]


def remote(records=None):
    return {'observed_at_utc':'2026-09-20T02:00:00Z',
            'service':{'ActiveState':'failed','SubState':'failed'},
            'records':six_records() if records is None else records, 'read_errors':[]}


class CountTests(unittest.TestCase):
    def test_reader_tracks_the_newly_launched_service(self):
        self.assertEqual(panel.SERVICE, 'uts-stage2-qualification-netcupv8.service')
        self.assertIn(panel.SERVICE, panel.REMOTE_READER)
        self.assertNotIn('uts-stage2-qualification-netcupv7.service', panel.REMOTE_READER)

    def test_checkpoint_and_excluded_pilots(self):
        data = panel.summarise(six_records()+[record(trial_id='fixture-old')],MANIFEST)
        self.assertEqual(data['tracks']['initial_terminus'],dict(target=20,attempted=6,
            billing_verified=4,verified=4,passes=1,unknown=2,budget_stops=3))
        self.assertEqual(data['ignored_records'],1)
        self.assertEqual(data['tracks']['final_terminus']['verified'],0)
        self.assertEqual(data['tracks']['final_openhands']['target'],89)

    def test_verified_requires_status_binary_reward_and_billing(self):
        rows=[record(0,status='failed'),record(1,reward=2),record(2,reward=True),
              record(3,reward=float('nan')),record(4,billing_verified=False),record(5,reward=1)]
        data=panel.summarise(rows,MANIFEST)['tracks']['initial_terminus']
        self.assertEqual(data['billing_verified'],5)
        self.assertEqual(data['verified'],1)
        self.assertEqual(data['passes'],1)
        self.assertEqual(data['unknown'],5)

    def test_budget_stop_count_distinguishes_zero_from_unknown(self):
        values=[0,2,None,-1,True,'0']
        rows=panel.summarise([record(i,budget_stop_count=value) for i,value in enumerate(values)],
                             MANIFEST)['initial_trials']
        self.assertEqual([row['budget_stop_count'] for row in rows],[0,2,None,None,None,None])
        duplicate=panel.summarise([record(),record(budget_stop_count=1)],MANIFEST)['initial_trials'][0]
        self.assertIsNone(duplicate['budget_stop_count'])
        self.assertTrue(all(row['billing_verified'] for row in rows))

    def test_no_variant_stitching_and_final_requires_frozen_condition(self):
        rows=[record(0,harness='C0'),record(1,harness='C1'),record(2,harness='C0',stage='final',reward=1)]
        data=panel.summarise(rows,MANIFEST)
        self.assertEqual(data['tracks']['custom_development']['verified'],0)
        self.assertEqual(data['custom_variants']['C0']['verified'],1)
        self.assertEqual(data['custom_variants']['C1']['verified'],1)
        self.assertEqual(data['tracks']['final_custom']['verified'],0)
        selected=panel.summarise(rows,MANIFEST,development_harness='C1',frozen_final_harness='C0')
        self.assertEqual(selected['tracks']['custom_development']['verified'],1)
        self.assertEqual(selected['tracks']['final_custom']['verified'],1)

    def test_duplicate_and_mismatched_cells(self):
        data=panel.summarise([record(),record(reward=1),record(1,stage='wrong')],MANIFEST)
        self.assertEqual(data['tracks']['initial_terminus']['attempted'],1)
        self.assertEqual(data['tracks']['initial_terminus']['verified'],0)
        self.assertEqual(len(data['duplicate_cells']),1)
        self.assertEqual(len(data['rejected_records']),1)

    def test_remote_projection_nested_reward_without_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); trial=root/record()['trial_id'];trial.mkdir()
            raw=dict(record(),verifier_result={'rewards':{'reward':1}},reward=99,
                     billing={'billing_verified':True,'budget_stop_count':0},
                     prompt='PRIVATE TEST PAYLOAD',api_key='PRIVATE TEST KEY')
            (trial/'result.json').write_text(json.dumps(raw))
            output=io.StringIO()
            with patch('pathlib.Path',return_value=root), patch('subprocess.run') as run, contextlib.redirect_stdout(output):
                run.return_value.stdout='ActiveState=failed\nSubState=failed\n'
                exec(panel.REMOTE_READER,{})
            result=json.loads(output.getvalue())
            self.assertEqual(result['records'][0]['reward'],1)
            self.assertNotIn('PRIVATE',output.getvalue())
            self.assertNotIn('prompt',result['records'][0])
            self.assertEqual(panel.summarise(result['records'],MANIFEST)['tracks']['initial_terminus']['passes'],1)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'curated.json'
        self.path.write_bytes((panel.STAGE2/'progress_status.json').read_bytes())
        self.ticks=0; self.calls=0; self.failure=False
        def fetch():
            self.calls+=1
            if self.failure:
                raise subprocess.TimeoutExpired('synthetic',20)
            return remote()
        self.monitor=panel.ProgressMonitor(MANIFEST,self.path,fetcher=fetch,
            clock=lambda:self.ticks,utc_clock=lambda:'2026-09-20T02:00:05Z')

    def test_failure_retains_snapshot_and_throttle_applies(self):
        self.assertTrue(self.monitor.status()['remote']['stale'])
        self.assertTrue(self.monitor.refresh())
        initial=self.monitor.status()['remote']
        self.assertFalse(initial['stale'])
        self.assertEqual(initial['tracks']['initial_terminus']['verified'],4)
        self.assertFalse(self.monitor.refresh())
        self.failure=True;self.ticks=60
        self.assertTrue(self.monitor.refresh())
        failed=self.monitor.status()['remote']
        self.assertTrue(failed['stale'])
        self.assertEqual(failed['tracks'],initial['tracks'])
        self.assertEqual(failed['observed_at_utc'],initial['observed_at_utc'])
        self.ticks=119;self.assertFalse(self.monitor.refresh())
        self.assertEqual(self.calls,2)

    def test_invalid_curated_edit_retains_last_good(self):
        before=self.monitor.status()['engineering']
        self.path.write_text('{}')
        self.assertEqual(self.monitor.status()['engineering'],before)

    def test_bad_metadata_cannot_replace_checkpoint(self):
        self.monitor.fetcher=lambda:remote([record(task_id='wrong')])
        self.monitor.refresh()
        state=self.monitor.status()['remote']
        self.assertTrue(state['stale'])
        self.assertEqual(state['tracks']['initial_terminus']['attempted'],6)


class RouteTests(unittest.TestCase):
    def test_exact_routes_loopback_and_no_remote_poll_per_request(self):
        class StaticMonitor:
            def status(self):
                return {'read_only':True}
        server=panel.create_server(StaticMonitor(),0)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            self.assertEqual(server.server_address[0],'127.0.0.1')
            for path,expected in [('/',200),('/status.json',200),('/stage2/progress_status.json',404),
                                  ('/../.runtime/netcup/id_ed25519',404),('/status.json?x=1',404),
                                  ('/%2e%2e/.env',404)]:
                connection=http.client.HTTPConnection(*server.server_address,timeout=2)
                connection.request('GET',path);response=connection.getresponse();response.read()
                self.assertEqual(response.status,expected,path);connection.close()
            connection=http.client.HTTPConnection(*server.server_address,timeout=2)
            connection.request('GET','/status.json',headers={'Host':'evil.example'})
            response=connection.getresponse();response.read();self.assertEqual(response.status,403);connection.close()
            connection=http.client.HTTPConnection(*server.server_address,timeout=2)
            connection.request('POST','/status.json');response=connection.getresponse();response.read()
            self.assertEqual(response.status,405);connection.close()
        finally:
            server.shutdown();server.server_close();worker.join(2)

    def test_fixed_ssh_safety_and_html_contract(self):
        command=panel.ssh_command()
        for option in ('StrictHostKeyChecking=yes','BatchMode=yes','ConnectTimeout=10','IdentitiesOnly=yes'):
            self.assertIn(option,command)
        self.assertEqual(command[-3:],['root@62.83.32.126','python3','-'])
        page=(panel.STAGE2/'progress_dashboard.html').read_text()
        self.assertNotIn('<script src=',page)
        self.assertNotIn('https://',page)
        self.assertIn('<progress',page)
        self.assertIn('setTimeout(poll,5000)',page)
        self.assertIn('Paid qualification STOPPED',page)
        self.assertNotIn('innerHTML',page)


if __name__ == '__main__':
    unittest.main()
