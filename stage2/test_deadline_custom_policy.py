"""C3 gate and recovery fixtures. No live network or benchmark execution."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadline_custom_policy import *
from deadline_custom_gateway import DeadlineRetrySession
from credit_only_accounting import summarise
from credit_only_gateway import PassiveSession, CreditOnlyError
from retry_gateway import RetrySession
from retry_runtime import activate
from scored_gateway import private_directory,durable_json
from test_portable_final_selection import block,TASKS
from test_retry_gateway import Clock,Event,Flaky,REQUEST
from test_credit_only_gateway import TOKEN,Client


def parent_fixture():
    summaries=dict(C0=block('C0',15,unknown=True),C1=block('C1',14),C2=block('C2',14,'C0'))
    selection=select(summaries);sources={'fixture.py':'a'*64}
    return dict(kind='audited_portable_parent_for_c3',summaries=summaries,selection=selection,
        results_sha256={r['trial_id']:r['result_sha256'] for s in summaries.values() for r in s['rows']},
        qualification_sha256='b'*64,qualification_file_sha256='c'*64,sources=sources,
        sources_sha256=fingerprint(sources),dependencies={'python':'3.12.13','packages':{'harbor':'0.22.0'}},
        registration_bindings={c:dict(canonical_sha256='d'*64,file_sha256='e'*64) for c in summaries})


def fixture(root):
    rt=private_directory(Path(root)/'.runtime/stage2');parent=parent_fixture()
    durable_json(rt/POLICY_FILE,POLICY);durable_json(rt/PARENT_FILE,parent)
    proof=dict(experiment=EXPERIMENT,status='passed',candidate_version=CANDIDATE_VERSION,
        sources_sha256='a'*64,policy_sha256=fingerprint(POLICY),model_protocol_sha256=SETTINGS.fingerprint(),
        parent_evidence_sha256=fingerprint(parent),execution_contract=execution_contract(),
        python_runtime={'sha256':PYTHON_SHA256})
    durable_json(rt/QUALIFICATION,proof)
    value=dict(experiment=EXPERIMENT,stage='development',condition='C3',parent='C0',base_parent=None,
        candidate_version=CANDIDATE_VERSION,python_runtime_sha256=PYTHON_SHA256,
        policy_sha256=fingerprint(POLICY),model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256,primary_comparator='terminus-2',secondary_comparator='openhands',
        parent_evidence_sha256=fingerprint(parent),execution_contract=execution_contract(),
        development_ids=TASKS,cells=cells(TASKS),sources_sha256='a'*64,qualification_sha256=fingerprint(proof))
    private_directory(block_path(rt).parent);durable_json(block_path(rt),value)
    return rt,value,proof


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.rt,self.block,self.proof=fixture(self.root)
        self.trial=self.block['cells'][0]['trial_id']

    def test_fresh_exact_twenty_only(self):
        self.assertEqual(require_trial(self.rt,self.trial,'development'),self.block)
        self.assertEqual(len({r['trial_id'] for r in cells(TASKS)}),20)
        for tasks in (TASKS[::-1],TASKS[:-1],TASKS[:-1]+['held-out']):
            with self.assertRaises(ValueError):cells(tasks)
        for trial,stage in ((self.trial,'final'),('customdev2-c0-01-video-processing','development'),
                            ('customdev3-c3-01-other','development'),('../escape','development')):
            with self.assertRaises(ValueError):require_trial(self.rt,trial,stage)

    def test_old_gate_cannot_admit_new_candidate(self):
        from portable_custom_policy import require_trial as old
        with self.assertRaises((ValueError,OSError)):old(self.rt,self.trial,'development')
        for cls in (PassiveSession,RetrySession):
            with self.assertRaises(ValueError):
                cls(self.root,'legacy','development',TOKEN,Client(),settings=SETTINGS,clock=Clock()) \
                    if cls is RetrySession else cls(self.root,'legacy','development',TOKEN,Client(),settings=SETTINGS)

    def test_no_financial_or_call_cap(self):
        for field in ('model_call_cap','physical_request_count_cap','per_task_cap_usd','project_cap_usd',
                      'stage_cap_usd','provider_max_price'):
            self.assertIsNone(require_policy(self.rt)[field])
        self.assertEqual(POLICY['reserve_usd'],'0');self.assertFalse(POLICY['automatic_top_up'])
        for field in ('completion_repair_count_cap','background_active_count_cap','background_lifetime_count_cap'):
            self.assertIsNone(POLICY['execution_contract'][field])

    def test_policy_parent_or_registration_drift_rejected(self):
        path=block_path(self.rt)
        for key,value in (('parent','C1'),('base_parent','C1'),('candidate_version','stage2-candidate-0.3.0'),
                          ('primary_comparator','openhands'),('cells',self.block['cells'][:-1]),
                          ('qualification_sha256','b'*64),('parent_evidence_sha256','c'*64)):
            path.write_text(json.dumps(self.block|{key:value}))
            with self.subTest(key=key),self.assertRaises(ValueError):require_trial(self.rt,self.trial,'development')
        path.write_text(json.dumps(self.block))
        (self.rt/POLICY_FILE).write_text(json.dumps(POLICY|{'model_call_cap':100}))
        with self.assertRaises(ValueError):require_policy(self.rt)

    def test_incomplete_or_tampered_parent_rejected(self):
        for mutate in ('drop','partial','hash','score','source','winner'):
            parent=parent_fixture()
            if mutate=='drop':parent['summaries'].pop('C2')
            elif mutate=='partial':parent['summaries']['C2']['rows'].pop()
            elif mutate=='hash':parent['results_sha256'].pop(next(iter(parent['results_sha256'])))
            elif mutate=='score':parent['summaries']['C0']['passes']=20
            elif mutate=='source':parent['sources']={}
            else:parent['selection']['selected']='C1'
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):parent_selection(parent)

    def test_private_files_and_registry_symlinks_rejected(self):
        path=self.rt/POLICY_FILE;path.chmod(0o644)
        with self.assertRaises(ValueError):require_policy(self.rt)
        path.chmod(0o600);saved=self.rt/'saved.json';path.rename(saved);path.symlink_to(saved)
        with self.assertRaises(OSError):require_policy(self.rt)

    def test_parent_rejects_private_fields_and_invalid_dependency_evidence(self):
        for change in ('extra','row','summary','source_path','python','package'):
            parent=parent_fixture()
            if change=='extra':parent['private_text']='not allowed'
            elif change=='row':parent['summaries']['C0']['rows'][0]['command']='not allowed'
            elif change=='summary':parent['summaries']['C0']['full_benchmark_win_claimed']=True
            elif change=='source_path':
                parent['sources']={'../escape':'f'*64};parent['sources_sha256']=fingerprint(parent['sources'])
            elif change=='python':parent['dependencies']['python']=None
            else:parent['dependencies']['packages']={'bad name':'private content'}
            with self.subTest(change=change),self.assertRaises(ValueError):parent_selection(parent)


class GatewayTests(PolicyTests):
    def session(self,failures=(),timeout=10000):
        clock=Clock();activate(self.rt,self.trial,timeout,SETTINGS,clock)
        session=DeadlineRetrySession(self.root,self.trial,'development',TOKEN,Flaky(clock,failures),
            settings=SETTINGS,clock=clock);session.cancelled=Event(clock)
        return session

    def test_more_than_one_hundred_calls_without_financial_gate(self):
        with patch('budget_ledger.Ledger.reserve',side_effect=AssertionError('No reservation')),self.session() as s:
            s.client.response.pop('usage')
            for _ in range(105):s.complete(TOKEN,REQUEST)
            evidence=summarise(self.rt,self.trial)
            self.assertEqual(evidence['requests'],105);self.assertEqual(evidence['unknown_cost_requests'],105)
            self.assertIsNone(evidence['charged_usd'])

    def test_shared_transient_retry_has_no_count_cap(self):
        with self.session([(429,['0'])]*105) as s:
            s.complete(TOKEN,REQUEST)
            self.assertEqual(len(s.client.calls),106)

    def test_registration_change_inside_attempt_stops(self):
        with self.session() as s:
            s.complete(TOKEN,REQUEST)
            block_path(self.rt).write_text(json.dumps(self.block|{'parent':'C1'}))
            with self.assertRaises(ValueError):s.complete(TOKEN,REQUEST)

    def test_actual_credit_stop_is_retained(self):
        with self.session([(402,[])]) as s:
            with self.assertRaises(CreditOnlyError):s.complete(TOKEN,REQUEST)
            self.assertEqual(len(s.client.calls),1)


if __name__=='__main__':unittest.main()
