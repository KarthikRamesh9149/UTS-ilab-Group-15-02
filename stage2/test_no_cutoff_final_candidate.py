"""Synthetic finalist contracts; no native reads, task execution or paid calls."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_final_candidate as candidate
import no_cutoff_custom_policy as revision
from test_no_cutoff_custom_policy import document_fixture, qualification_fixture
from scored_gateway import durable_json, private_directory


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalistFixture:
    """Explicitly fabricated test data, never installed in a native study."""
    def __init__(self, owner, repo):
        self.repo = repo
        self.output = repo / candidate.RESULTS
        self.output.mkdir(parents=True)
        for name in candidate.LOGIC_FILES:
            (repo / 'stage2' / name).write_text('# Synthetic ' + name + '\n')
        self.original = document_fixture()
        for name in candidate.LOGIC_FILES:
            value = digest(repo / 'stage2' / name)
            if name in self.original['selection_logic_sources']:
                self.original['selection_logic_sources'][name] = value
            if name in self.original['candidate']['c3_sources']:
                self.original['candidate']['c3_sources'][name] = value
        owner.enterContext(patch.object(revision, 'ORIGINAL_FREEZE_SHA256', revision.fingerprint(self.original)))
        self.proof = qualification_fixture(self.original)
        for name in candidate.LOGIC_FILES & self.proof['sources'].keys():
            self.proof['sources'][name] = digest(repo / 'stage2' / name)
        self.proof['sources_sha256'] = revision.fingerprint(self.proof['sources'])
        self.proof['source_transition'] = revision.source_transition(self.original, self.proof['sources'])
        self.tasks = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())['development_ids']
        self.auth = {'synthetic': True}
        self.runtime = {'development_ids': self.tasks}
        self.proof['original_authentication_sha256'] = revision.fingerprint(self.auth)
        self.proof['runtime_identity_sha256'] = revision.fingerprint(self.runtime)
        rt = private_directory(repo / candidate.PRIVATE / '.runtime/stage2')
        for name in self.proof['evidence_files']:
            path = repo / candidate.PRIVATE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic producer bytes: ' + name)
            self.proof['evidence_files'][name] = digest(path)
        self.block = revision.registration(self.original, self.proof, self.tasks)
        owner.enterContext(patch.object(candidate, 'QUALIFICATION_SHA256', revision.fingerprint(self.proof)))
        owner.enterContext(patch.object(candidate, 'REGISTRATION_SHA256', revision.fingerprint(self.block)))
        self.private = rt
        for name, value in {revision.CANDIDATE_FILE:self.original, revision.AUTHENTICATION_FILE:self.auth,
                revision.RUNTIME_FILE:self.runtime, revision.POLICY_FILE:revision.POLICY,
                revision.QUALIFICATION:self.proof}.items():
            durable_json(rt / name, value)
        path = repo / candidate.ORIGINAL; private_directory(path.parent); durable_json(path, self.original)
        durable_json(repo / candidate.PRIVATE / 'C0-NC.json', self.block)
        self.public_proof = dict(self.proof, qualification_sha256=revision.fingerprint(self.proof),
            qualification_file_sha256=digest(rt / revision.QUALIFICATION),
            private_file_sha256={name:digest(rt/name) for name in
                (revision.POLICY_FILE,revision.RUNTIME_FILE,revision.AUTHENTICATION_FILE)})
        self.registration = dict(self.block, kind='synthetic_public',
            registration_sha256=revision.fingerprint(self.block),
            registration_file_sha256=digest(repo / candidate.PRIVATE / 'C0-NC.json'))
        self.lineage = dict(original_candidate_sha256=revision.fingerprint(self.original),
            candidate_file_sha256=digest(rt/revision.CANDIDATE_FILE), original_parent='C0',
            condition=revision.CONDITION, original_score_inherited=False)
        for name, value in zip(candidate.PUBLIC_FILES,
                (self.public_proof,self.registration,revision.POLICY,self.lineage)):
            (self.output/name).write_text(json.dumps(value))
        self.rows = [dict(cell, reward=int(i < 12), agent_seconds=10.0,
            requests=2, unknown_cost_requests=1, known_charged_usd='0.01', charged_usd=None,
            result_sha256=hashlib.sha256(cell['trial_id'].encode()).hexdigest())
            for i,cell in enumerate(self.block['cells'])]

    def build(self):
        names=candidate.BASE_ANCHORS | {candidate.PRIVATE+'/'+name for name in self.proof['evidence_files']}
        return candidate.build(self.original,self.proof,self.block,self.rows,audit_sha256='a'*64,
            anchors={name:digest(self.repo/name) for name in names},
            logic={name:digest(self.repo/'stage2'/name) for name in candidate.LOGIC_FILES})


class CandidateTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.f=FinalistFixture(self,Path(temp.name))

    def test_all_original_and_revised_results_bound_without_inherited_score(self):
        document=self.f.build();selected=candidate.validate_document(document)
        self.assertEqual(len(document['result_bindings']),100)
        self.assertEqual(document['validation_summary']['passes'],12)
        self.assertEqual(document['original_candidate']['candidate']['selection']['selected'],'C0')
        self.assertEqual(selected['harness'],'C0-NC')
        self.assertEqual(selected['candidate_version'],'stage2-candidate-0.5.0')
        self.assertEqual(selected['sources'],self.f.proof['sources'])
        self.assertFalse(document['paid_launch_ready']);self.assertFalse(document['original_score_inherited'])
        self.assertFalse(document['efficiency_win_claimed']);self.assertFalse(document['full_benchmark_win_claimed'])
        self.assertEqual(document['confirmation60_status'],'deferred_not_run')

    def test_zero_score_and_missing_outcomes_are_retained_not_reselected(self):
        for row in self.f.rows:row['reward']=0
        self.f.rows[-1].update(reward=None,agent_seconds=None)
        document=self.f.build();value=document['validation_summary']
        self.assertEqual((value['passes'],value['failures'],value['no_verifier_result']),(0,19,1))
        self.assertIsNone(value['agent_seconds']);self.assertIsNone(value['charged_usd'])
        self.assertEqual(value['known_charged_usd'],'0.20')
        self.assertEqual(value['unknown_cost_requests'],20)
        self.assertEqual(document['selected_execution']['harness'],'C0-NC')

    def test_complete_zero_cost_is_distinct_from_unknown(self):
        for row in self.f.rows:row.update(unknown_cost_requests=0,known_charged_usd='0',charged_usd='0')
        value=self.f.build()['validation_summary']
        self.assertEqual(value['charged_usd'],'0');self.assertEqual(value['unknown_cost_requests'],0)

    def test_no_alias_to_original_sources_or_rows(self):
        document=self.f.build();document['validation_summary']['rows'][0]['reward']=0
        document['revision_qualification']['sources']['no_cutoff_custom_agent.py']='0'*64
        self.assertEqual(self.f.rows[0]['reward'],1)
        self.assertNotEqual(self.f.proof['sources']['no_cutoff_custom_agent.py'],'0'*64)

    def test_incomplete_duplicate_reordered_extra_or_old_cells_refused(self):
        original=deepcopy(self.f.rows)
        for change in ('missing','extra','duplicate','order','old','other-parent'):
            self.f.rows=deepcopy(original)
            if change=='missing':self.f.rows.pop()
            elif change=='extra':self.f.rows.append(deepcopy(self.f.rows[0]))
            elif change=='duplicate':self.f.rows[1]=self.f.rows[0]
            elif change=='order':self.f.rows.reverse()
            elif change=='old':self.f.rows[0]['trial_id']=next(iter(self.f.original['candidate']['result_bindings']))
            else:self.f.rows[0]['harness']='C1-NC'
            with self.subTest(change=change),self.assertRaises(ValueError):self.f.build()

    def test_invalid_or_private_row_values_refused(self):
        original=deepcopy(self.f.rows[0])
        for value in ({'reward':True},{'reward':2},{'reward':float('nan')},{'requests':True},
                {'requests':-1},{'unknown_cost_requests':3},{'known_charged_usd':'NaN'},
                {'known_charged_usd':'-1'},{'known_charged_usd':0.1},{'charged_usd':'0'},
                {'agent_seconds':float('inf')},{'agent_seconds':True},{'result_sha256':'broken'},
                {'messages':['private']}):
            self.f.rows[0]=dict(original,**value)
            with self.subTest(value=value),self.assertRaises(ValueError):self.f.build()

    def test_summary_runtime_score_and_authority_cannot_be_rewritten(self):
        baseline=self.f.build()
        for change in ('paid','schema-bool','score','total','partial','runtime','extra','best-of','missing-original','anchor','logic','audit'):
            doc=deepcopy(baseline)
            if change=='paid':doc['paid_launch_ready']=True
            elif change=='schema-bool':doc['schema_version']=True
            elif change=='score':doc['validation_summary']['passes']=15
            elif change=='total':doc['validation_summary']['charged_usd']='0'
            elif change=='partial':doc['validation_summary']['started_without_result']=['fake']
            elif change=='runtime':doc['selected_execution']['candidate_version']='stage2-candidate-0.3.0'
            elif change=='extra':doc['private_text']='secret'
            elif change=='best-of':doc['result_bindings'][self.f.rows[0]['trial_id']]='b'*64
            elif change=='missing-original':doc['result_bindings'].pop(next(iter(self.f.original['candidate']['result_bindings'])))
            elif change=='anchor':doc['anchor_files'].pop(candidate.ORIGINAL)
            elif change=='logic':doc['freeze_logic_sources'].pop(next(iter(candidate.LOGIC_FILES)))
            else:doc['revision_audit_sha256']='invalid'
            with self.subTest(change=change),self.assertRaises(ValueError):candidate.validate_document(doc)

    def test_changed_qualification_or_registration_not_admitted_by_json_flags(self):
        for key in ('revision_qualification','revision_registration'):
            doc=self.f.build();doc[key]['unregistered_change']=True
            with self.subTest(key=key),self.assertRaises(ValueError):candidate.validate_document(doc)

    def test_lightweight_reader_never_imports_host_or_agent_stack(self):
        path=self.f.repo/'candidate.json';path.write_text(json.dumps(self.f.build()))
        script=r'''
import importlib.abc,json,sys
class RejectHost(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'harbor','deepagents','langgraph','langchain','langchain_core',
    'langchain_openai','no_cutoff_evidence_freeze','export_no_cutoff_custom','direct_final_evidence',
    'direct_final_runtime','deadline_evidence_freeze','portable_candidate_freeze','scored_trial',
    'no_cutoff_custom_runtime','no_cutoff_custom_study','run_no_cutoff_custom'}:
   raise ImportError('Host dependency: '+fullname)
sys.meta_path.insert(0,RejectHost())
import no_cutoff_final_candidate as candidate
document=json.load(open(sys.argv[1]))
candidate.revision.ORIGINAL_FREEZE_SHA256=candidate.revision.fingerprint(document['original_candidate'])
candidate.QUALIFICATION_SHA256=candidate.revision.fingerprint(document['revision_qualification'])
candidate.REGISTRATION_SHA256=candidate.revision.fingerprint(document['revision_registration'])
assert candidate.validate_document(document)['harness']=='C0-NC'
assert document['paid_launch_ready'] is False
'''
        result=subprocess.run([sys.executable,'-B','-c',script,str(path)],capture_output=True,text=True,
            timeout=20,env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent)))
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
