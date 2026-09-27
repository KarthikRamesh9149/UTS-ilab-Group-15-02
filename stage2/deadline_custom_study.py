"""Separately qualified C3 development: exact fixed20 and whole-parent lineage."""
from decimal import Decimal
from pathlib import Path
import math
import re

from deadline_custom_policy import (EXPERIMENT,POLICY,QUALIFICATION,BLOCKS,PARENT_FILE,
    SETTINGS,CANDIDATE_VERSION,PYTHON_SHA256,fingerprint,cells,require_policy,require_block,
    require_trial,block_path,parent_selection,execution_contract)
from deadline_custom_parent import verify_parent
from portable_custom_study import (sources as previous_sources,dependencies,image_compatibility,
    PROBE_CHECKS as BASE_CHECKS,TOOL_CHECKS as BASE_TOOL_CHECKS)
from portable_custom_agent import runtime_bundle
from corrected_custom_scope import inspect
from credit_only_accounting import summarise as billing_summary
from credit_only_experiment import coverage,cleanup_complete,digest
from retry_runtime import private_read
from scored_gateway import durable_json,private_directory

DEPLOYMENT=Path('/opt/uts-capstone-custom-deadline-20260927')
ADDED=('deadline_custom_contract.py','custom_deadline_guidance.py','custom_deadline_execution.py',
    'deadline_custom_agent.py','deadline_custom_policy.py','deadline_custom_gateway.py',
    'deadline_custom_parent.py','deadline_custom_study.py','run_deadline_custom.py',
    'deadline_custom_probe.py','qualify_deadline_custom.py','export_deadline_custom.py',
    'deadline_final_selection.py','deadline_candidate_freeze.py','deadline_evaluation_schedule.py',
    'portable_final_selection.py','portable_candidate_freeze.py','portable_evaluation_schedule.py',
    'test_portable_final_selection.py',
    'test_custom_deadline_guidance.py','test_custom_deadline_execution.py','test_deadline_custom_agent.py',
    'test_deadline_custom_policy.py','test_deadline_custom_study.py','test_deadline_custom_probe.py',
    'test_deadline_final_selection.py','test_deadline_candidate_freeze.py','test_export_deadline_custom.py',
    'fixtures/Dockerfile.custom-deadline')
TEST_MODULES=('test_deadline_custom_policy','test_deadline_custom_study','test_deadline_custom_probe',
    'test_deadline_final_selection','test_deadline_candidate_freeze','test_export_deadline_custom',
    'test_custom_deadline_guidance','test_custom_deadline_execution','test_deadline_custom_agent',
    'test_retry_gateway','test_credit_only_gateway','test_scored_trial','test_trial_execution',
    'test_custom_text_transport','test_custom_python_runtime','test_custom_process_capture',
    'test_custom_dispatch_stop','custom_runner_tests','custom_backend_tests','custom_jobs_tests')
PROBE_MODES=('tools','cancel_setup','boundary_stop')


def probe_checks(mode):
    if mode not in PROBE_MODES: raise ValueError('Unknown C3 fixture mode')
    extra={'deadline_context_observed','more_than_two_repairs','no_command_count_quota',
           'command_passed_sixty_seconds'}
    return BASE_CHECKS | ({'cancelled_setup_evidence'} if mode=='cancel_setup' else BASE_TOOL_CHECKS|extra) | (
        {'cooperative_stop_persisted','no_next_dispatch'} if mode=='boundary_stop' else set())


def sources(root):
    return dict(previous_sources(root),**{n:digest(Path(root)/'stage2'/n) for n in ADDED})


def identity(root):
    root=Path(root);bound=sources(root);scope=inspect(root)
    parent=private_read(root/'.runtime/stage2'/PARENT_FILE);selection=parent_selection(parent)
    return dict(experiment=EXPERIMENT,policy_sha256=fingerprint(POLICY),candidate_version=CANDIDATE_VERSION,
        python_runtime=runtime_bundle(root).validate(),model_protocol_sha256=SETTINGS.fingerprint(),
        sources=bound,sources_sha256=fingerprint(bound),dependencies=dependencies(),matched_scope=scope,
        image_compatibility=image_compatibility(root,scope),parent_evidence_sha256=fingerprint(parent),
        parent=selection['selected'],base_parent=selection['custom_parent'],execution_contract=execution_contract())


def qualified(root):
    import host_environment
    from scored_trial import docker
    root=Path(root);rt=root/'.runtime/stage2';require_policy(rt)
    proof=private_read(rt/QUALIFICATION);current=identity(root)
    if (proof.get('status')!='passed' or type(proof.get('live_api_calls')) is not int
            or proof['live_api_calls']!=0 or any(proof.get(k)!=v for k,v in current.items())
            or proof.get('host_environment')!=host_environment.snapshot()
            or type(proof.get('setup_timeout_seconds')) is not int or proof['setup_timeout_seconds']!=900):
        raise ValueError('Current source-bound native C3 qualification required')
    offline=proof.get('offline',{})
    if (offline.get('modules')!=list(TEST_MODULES) or offline.get('passed') is not True
            or type(offline.get('tests')) is not int or offline['tests']<=0
            or any(type(offline.get(k)) is not int or offline[k]!=0 for k in ('skipped','errors','failures'))):
        raise ValueError('Native C3 offline checks incomplete')
    native=proof.get('synthetic',[])
    if (len(native)!=len(PROBE_MODES) or [v.get('mode') for v in native]!=list(PROBE_MODES)
            or any(v.get('condition')!='C3' or v.get('parent')!=current['parent']
                   or v.get('base_parent')!=current['base_parent'] or v.get('status')!='passed'
                   or type(v.get('live_api_calls')) is not int or v['live_api_calls']!=0
                   or set(v.get('checks',{}))!=probe_checks(v['mode'])
                   or any(x is not True for x in v['checks'].values()) for v in native)):
        raise ValueError('Complete native C3 lifecycle evidence required')
    for field in ('gateway_image','guard_image'):
        image=proof.get(field)
        if not isinstance(image,str) or not re.fullmatch(r'sha256:[a-f0-9]{64}',image):
            raise ValueError('Pinned image required')
        if docker('image','inspect',image,'--format','{{.Id}}')!=image:
            raise ValueError('Qualified image unavailable')
    if proof.get('image_sources_match') is not True: raise ValueError('Gateway source mismatch')
    return proof


def audited(root):
    rt=Path(root)/'.runtime/stage2';folder=rt/BLOCKS
    if folder.is_symlink(): raise ValueError('Unsafe registry')
    names=sorted(p.name for p in folder.iterdir()) if folder.exists() else []
    if names not in ([],['C3.json']): raise ValueError('Unexpected C3 registration')
    block=require_block(rt) if names else None
    complete,partial=coverage(rt,block['cells'] if block else [])
    for name,result in complete.items():
        require_trial(rt,name,'development')
        if (result.get('stage')!='development' or result.get('custom_study')!=EXPERIMENT
                or result.get('harness')!='C3' or result.get('model_revoked') is not True
                or result.get('custom_registration_sha256')!=fingerprint(block)
                or result.get('model_protocol_sha256')!=SETTINGS.fingerprint()
                or result.get('accounting_mode')!='provider-credit-only'):
            raise ValueError('C3 result identity or revocation differs from registration')
        if not cleanup_complete(result):
            raise ValueError('Retained C3 outcome requires completed cleanup')
        metadata=(result.get('agent_context') or {}).get('metadata',{})
        if metadata:
            expected=dict(custom_version=CANDIDATE_VERSION,custom_condition='C3',
                custom_parent=block['parent'],custom_base_parent=block['base_parent'],
                custom_execution_contract=execution_contract())
            if any(fingerprint(metadata.get(k))!=fingerprint(v) for k,v in expected.items()):
                raise ValueError('Actual C3 execution differs from its registered contract')
    return complete,partial


def summary(root):
    rt=Path(root)/'.runtime/stage2';block=require_block(rt);complete,partial=audited(root);rows=[]
    for cell in block['cells']:
        name=cell['trial_id']
        if name not in complete: continue
        result=complete[name];bill=billing_summary(rt,name)
        reward=((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        if reward is not None and (type(reward) not in (int,float) or reward not in (0,1)):
            raise ValueError('Invalid verifier result')
        seconds=result.get('phase_seconds',{}).get('agent')
        if seconds is not None and (type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0):
            raise ValueError('Invalid observed runtime')
        rows.append(dict(cell,reward=reward,agent_seconds=seconds,
            result_sha256=digest(rt/'scored-trials'/name/'result.json'),
            **{k:bill[k] for k in ('requests','unknown_cost_requests','known_charged_usd','charged_usd')}))
    known=sum((Decimal(r['known_charged_usd']) for r in rows),Decimal(0))
    elapsed=[r['agent_seconds'] for r in rows]
    parent=private_read(rt/PARENT_FILE)['selection']['summaries'][block['parent']]
    return dict(condition='C3',parent=block['parent'],base_parent=block['base_parent'],intended=20,
        attempted=len(rows),passes=sum(r['reward']==1 for r in rows),failures=sum(r['reward']==0 for r in rows),
        no_verifier_result=sum(r['reward'] is None for r in rows),started_without_result=partial,
        known_charged_usd=str(known),charged_usd=str(known) if len(rows)==20 and all(r['charged_usd'] is not None for r in rows) else None,
        unknown_cost_requests=sum(r['unknown_cost_requests'] for r in rows),
        agent_seconds=sum(elapsed) if len(rows)==20 and None not in elapsed else None,complexity=parent['complexity']+1,
        rows=rows,efficiency_win_claimed=False,full_benchmark_win_claimed=False)


def register(root):
    root=Path(root);rt=root/'.runtime/stage2';parent=verify_parent(rt);proof=qualified(root)
    complete,partial=audited(root)
    if partial: raise ValueError('Started attempt retained; no replay')
    scope=proof['matched_scope']
    block=dict(experiment=EXPERIMENT,stage='development',condition='C3',parent=proof['parent'],
        base_parent=proof['base_parent'],candidate_version=CANDIDATE_VERSION,python_runtime_sha256=PYTHON_SHA256,
        policy_sha256=fingerprint(POLICY),sources_sha256=proof['sources_sha256'],
        qualification_sha256=fingerprint(proof),model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=scope['input_manifest_sha256'],development_ids=scope['development_ids'],
        primary_comparator='terminus-2',secondary_comparator='openhands',
        parent_evidence_sha256=fingerprint(parent),execution_contract=execution_contract(),
        cells=cells(scope['development_ids']))
    path=block_path(rt);private_directory(path.parent)
    if path.exists() or path.is_symlink():
        if fingerprint(private_read(path))!=fingerprint(block): raise ValueError('Immutable C3 registration changed')
    else: durable_json(path,block)
    require_block(rt)
    return block


def admit_trial(root,*,trial_id,task_id,stage,factory,settings,gateway_image,guard_image):
    proof=qualified(root);block=require_trial(Path(root)/'.runtime/stage2',trial_id,stage)
    cell=next(c for c in block['cells'] if c['trial_id']==trial_id)
    if (cell['task_id']!=task_id or getattr(factory,'harness',None)!='C3'
            or getattr(factory,'custom_parent',None)!=block['parent']
            or getattr(factory,'custom_base_parent',None)!=block['base_parent']
            or getattr(factory,'custom_version',None)!=CANDIDATE_VERSION
            or getattr(factory,'python_runtime_sha256',None)!=PYTHON_SHA256
            or settings!=SETTINGS or gateway_image!=proof['gateway_image'] or guard_image!=proof['guard_image']
            or fingerprint(proof)!=block['qualification_sha256']):
        raise ValueError('C3 factory/task/runtime differs from qualified registration')
    return fingerprint(block)
