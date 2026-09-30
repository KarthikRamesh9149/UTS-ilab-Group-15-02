"""Real synthetic89 result/trace/accounting files; native facts mocked."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import credit_only_accounting as accounting
from local_trace import observation
import matched_repeat_completion as completion
import matched_repeat_policy as policy
import matched_repeat_report as report
import matched_repeat_session as session
import matched_repeat_study as study
import no_cutoff_recovery_files as files
import run_matched_repeat as runner
from test_matched_repeat_policy import Fixture
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save

BASE = int(datetime.fromisoformat('2026-09-29T01:00:00+00:00').timestamp()) * 1_000_000_000
STAGE = Path(__file__).resolve().parent


class ReportTests(LocalFiles, unittest.TestCase):
    harness = 'terminus-2'

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.f = Fixture(self, self.root, self.harness); self.rt = self.f.runtime
        self.cells = self.f.block['cells']; self.proof = deepcopy(self.f.proof)
        self.sources = {'fixture.py': hashlib.sha256(b'# synthetic source only\n').hexdigest()}
        save(self.root, 'stage2/fixture.py', b'# synthetic source only\n')
        self.proof.update(sources=self.sources, sources_sha256=policy.fingerprint(self.sources))
        self.block = dict(self.f.block, sources_sha256=self.proof['sources_sha256'],
            qualification_sha256=policy.fingerprint(self.proof))
        self.host = dict(task_inventory={c['task_id']: dict(agent_timeout_seconds=180.0,
            verifier_timeout_seconds=30.0, cpus=1, memory_mb=2048, image_id='sha256:'+'9'*64) for c in self.cells})
        self.write(policy.RUNTIME_FILE, self.host); self.write(policy.REGISTRATION_FILE, self.block)
        self.bound = files.capture(self.root, ['stage2/fixture.py', report.RT+policy.REGISTRATION_FILE,
            report.RT+policy.RUNTIME_FILE])[0]
        self.live = dict(root=self.root, harness=self.harness, host=self.host, files=self.bound,
            predecessor={'predecessors': self.f.predecessor}, original_record={'synthetic_original_audit': True})
        self.enterContext(patch.dict(report.runtime.DEPLOYMENTS, {self.harness: self.root}))
        self.enterContext(patch.object(report, '__file__', str(self.root/'stage2/matched_repeat_report.py')))
        self.enterContext(patch.object(session, '_live', return_value=self.live))
        self.rechecks = self.enterContext(patch.object(session, 'recheck'))
        self.enterContext(patch.object(study, '_clear'))
        self.qualified = self.enterContext(patch.object(study, '_qualified', side_effect=lambda active:
            (self.root, deepcopy(self.proof), deepcopy(self.block), self.bound.copy())))
        self.ended = self.enterContext(patch.object(completion, 'read', return_value={'files': {}, 'identities': {}}))
        self.enterContext(patch.object(runner, '_owned_resources_clear'))
        self.resources = self.enterContext(patch.object(report.original_report, '_resources'))

    def write(self, name, value):
        return save(self.root, report.RT+name, json.dumps(value).encode())

    def produce(self, *, setup_only=False, requests=0):
        for index,cell in enumerate(self.cells):
            reward = None if setup_only or index == 88 else index % 2
            name = cell['trial_id']; trial = report.RT+'scored-trials/'+name
            start = dict(trial_id=name, task_id=cell['task_id'], harness=self.harness, stage='final',
                matched_repeat_experiment=policy.EXPERIMENT, matched_repeat_registration_sha256=policy.fingerprint(self.block),
                model_protocol_sha256=policy.MODEL_SHA256, accounting_mode='provider-credit-only',
                gateway_image_id=self.proof['gateway_image'], guard_image_id=self.proof['guard_image'],
                project='uts-scored-'+format(index+1,'012x'), started_utc='2026-09-29T00:00:00Z', status='starting')
            save(self.root, trial+'/started.json', json.dumps(start).encode())
            save(self.root, trial+'/compose.json', b'{}')
            count = requests if index == 0 and reward is not None else 0
            account = report.RT+'scored-attempts/'+name
            save(self.root, account+'/started.json', b'{}')
            for request in range(count):
                save(self.root, account+f'/{request:06d}.request.json', b'opaque unparsed model exchange')
            billing = accounting.summarise(self.rt, name)
            result = dict(start, status='setup_failed' if reward is None else 'verified',
                task_image_id=self.host['task_inventory'][cell['task_id']]['image_id'],
                agent_error_type='RuntimeError' if reward is None else None, verifier_error_type=None,
                verifier_result=None if reward is None else {'rewards': {'reward': reward}},
                phase_seconds={'setup': 1.0} if reward is None else {'setup': 1.0, 'agent': 2.0, 'verifier': 1.0},
                model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
                cleanup_errors=[], billing=billing)
            specs = [('trial',0,0,2,'error',None),('setup',1,0,1,'error',None),('cleanup',2,1,2,'ok',None)] if reward is None else [
                ('trial',0,0,5,'ok',None),('setup',1,0,1,'ok',None),('agent',2,1,3,'ok',None),
                ('verifier',3,3,4,'ok',reward),('cleanup',4,4,5,'ok',None)]
            for kind,sequence,begin,end,status,score in specs:
                event = observation(trial_id=name, task_id=cell['task_id'], harness=self.harness,
                    protocol_sha256=policy.MODEL_SHA256, kind=kind, sequence=sequence,
                    started_ns=BASE+index*10_000_000_000+begin*1_000_000_000,
                    ended_ns=BASE+index*10_000_000_000+end*1_000_000_000, status=status, reward=score,
                    metrics={'duration_seconds': float(end-begin), **({'requests': count} if kind=='trial' else {})})
                save(self.root, trial+'/traces/'+event['event_id']+'.json', json.dumps(event).encode())
            result['trace'] = dict(status='metadata_spool_not_cloud_export', events=len(specs), generations=0,
                missing_generation_timings=count, unknown_cost_requests=count)
            save(self.root, trial+'/result.json', json.dumps(result).encode())
            if reward is not None:
                self.write('retry-lifecycle/'+name+'.json', dict(trial_id=name,
                    model_protocol_sha256=policy.MODEL_SHA256, boot_id='synthetic-only', deadline_monotonic=180.0,
                    deadline_utc=BASE/1e9+index*10+1+180.0))
        self.write(runner.INTENT, dict(registration_sha256=policy.fingerprint(self.block)))
        self.write(runner.RESULT, dict(status='complete', intended=89, completed=89, stop_markers=[],
            dispatch_intent_sha256=files.capture(self.root, [report.RT+runner.INTENT])[0][report.RT+runner.INTENT]))

    def collect(self): return report.collect(object())

    def test_actual_eighty_nine_phase_and_accounting_reads_keep_zero_missing_and_unknown(self):
        self.produce(requests=105); data,state = self.collect()
        self.assertEqual((data['aggregate']['passed'],data['aggregate']['failed'],data['aggregate']['no_verifier_result']),(44,44,1))
        self.assertEqual(data['aggregate']['unknown_cost_requests'],105); self.assertIsNone(data['aggregate']['total_cost_usd'])
        self.assertEqual(data['development20']['passed'],10); self.assertEqual(data['remaining69']['passed'],34)
        self.assertIsNone(data['rows'][-1]['agent_seconds']); self.assertEqual(len(data['absent_paths']),1)
        self.assertEqual(data['original_scores'],{'terminus-2':52,'openhands':44})
        report.validate(data,self.f.manifest,self.sources); report.reread(self.root,data,state)
        self.assertEqual(self.ended.call_count,4); self.assertGreaterEqual(self.rechecks.call_count,2)
        self.assertNotIn('opaque', json.dumps(data))

    def test_all_setup_only_failures_have_real_absence_not_invented_deadlines(self):
        self.produce(setup_only=True); data,_ = self.collect()
        self.assertEqual(data['aggregate']['no_verifier_result'],89)
        self.assertFalse((self.rt/'retry-lifecycle').exists())
        report.validate(data,self.f.manifest,self.sources)

    def test_native_completion_failure_never_becomes_a_saved_completed_audit(self):
        self.ended.side_effect=ValueError('Actual service has not ended')
        with self.assertRaisesRegex(ValueError,'service'): self.collect()

    def test_missing_result_or_partial_prefix_refuses(self):
        self.produce()
        (self.rt/'scored-trials'/self.cells[17]['trial_id']/'result.json').unlink()
        with self.assertRaises(ValueError): self.collect()

    def test_foreign_custom_trace_identity_cannot_be_used_for_a_baseline(self):
        self.produce()
        folder=self.rt/'scored-trials'/self.cells[0]['trial_id']/'traces'
        path=next(folder.iterdir()); value=json.loads(path.read_bytes()); value['harness']='C0-NC'
        save(self.root,path.relative_to(self.root).as_posix(),json.dumps(value).encode())
        with self.assertRaisesRegex(ValueError,'Trace identity'): self.collect()

    def test_final_native_observation_is_followed_by_actual_file_identity_rereads(self):
        self.produce(); path=self.rt/'scored-trials'/self.cells[0]['trial_id']/'result.json'
        def replace(project):
            if not getattr(replace,'done',False):
                raw=path.read_bytes(); path.rename(path.with_suffix('.retained'))
                save(self.root,path.relative_to(self.root).as_posix(),raw); replace.done=True
        self.resources.side_effect=replace
        with self.assertRaises(ValueError): self.collect()

    def test_wrong_registered_image_cleanup_or_lifecycle_evidence_refuses(self):
        self.produce(); path=self.rt/'scored-trials'/self.cells[0]['trial_id']/'result.json'
        saved=path.read_bytes()
        for key,value in (('task_image_id','sha256:'+'f'*64),('model_revoked',False),('phase_seconds',{'setup':1.0})):
            with self.subTest(key=key):
                altered=json.loads(saved); altered[key]=value; path.write_bytes(json.dumps(altered).encode())
                with self.assertRaises(ValueError): self.collect()
            path.write_bytes(saved)

    def test_validate_rejects_dropped_reordered_merged_or_extra_outcome_fields(self):
        self.produce(); data,_=self.collect()
        for change in ('drop','order','original','harness','payload','absence','count'):
            value=deepcopy(data)
            if change=='drop': value['rows'].pop()
            elif change=='order': value['rows'][0],value['rows'][1]=value['rows'][1],value['rows'][0]
            elif change=='original': value['original_results_replaced']=True
            elif change=='harness': value['rows'][0]['harness']='C0-NC'
            elif change=='payload': value['rows'][0]['raw_output']='private'
            elif change=='absence': value['absent_paths']=[next(iter(value['supporting_files']))]
            else: value['rows'][0]['model_requests']=999
            with self.subTest(change=change), self.assertRaises(ValueError): report.validate(value,self.f.manifest,self.sources)

    def test_late_source_replacement_and_new_deadline_refuse_reread(self):
        self.produce(); data,state=self.collect()
        name=data['absent_paths'][0]; save(self.root,name,b'{}')
        with self.assertRaises(ValueError): report.reread(self.root,data,state)
        (self.root/name).unlink()
        path=self.root/'stage2'/next(iter(self.sources)); raw=path.read_bytes(); path.rename(path.with_suffix('.old')); path.write_bytes(raw)
        with self.assertRaises(ValueError): report.reread(self.root,data,state)

    def test_separate_phase_reader_supports_actual_openhands_identity_and_rejects_custom(self):
        self.produce(); cell=self.cells[0]; trial=report.RT+'scored-trials/'+cell['trial_id']
        result=json.loads((self.root/trial/'result.json').read_bytes())
        events=[json.loads(p.read_bytes()) for p in (self.root/trial/'traces').iterdir()]
        lifecycle=json.loads((self.rt/'retry-lifecycle'/ (cell['trial_id']+'.json')).read_bytes())
        limits=self.host['task_inventory'][cell['task_id']]
        for harness in ('terminus-2','openhands'):
            altered=deepcopy(result); altered['harness']=harness
            changed=deepcopy(events)
            for event in changed: event['harness']=harness
            self.assertEqual(report.baseline_phase.read(altered,changed,lifecycle,[],0,limits)['harness'],harness)
        result['harness']='C0-NC'
        with self.assertRaises(ValueError): report.baseline_phase.read(result,events,lifecycle,[],0,limits)

    def test_no_cli_writer_or_dispatch_entry(self):
        import ast
        source=ast.parse((STAGE/'matched_repeat_report.py').read_bytes())
        functions={node.name for node in source.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
        self.assertFalse(functions & {'main','register','run','qualify','save','backup','export'})
        with patch.object(session,'_live',side_effect=ValueError('No live session')):
            with self.assertRaises(ValueError): report.collect({})
