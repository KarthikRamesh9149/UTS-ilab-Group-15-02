"""Exact C3 development admission. No financial or request-count gate."""
from pathlib import Path, PurePosixPath
import re

from deadline_custom_contract import CANDIDATE_VERSION, execution_contract
from portable_custom_policy import (POLICY as PREDECESSOR_POLICY, SETTINGS,
    DEVELOPMENT_SHA256, INPUT_SHA256, PYTHON_SHA256, fingerprint)
from portable_final_selection import select
from retry_runtime import private_read

EXPERIMENT = 'custom-deadline-development-20260927'
POLICY_FILE = 'deadline-credit-policy.json'
QUALIFICATION = 'deadline-qualification.json'
PARENT_FILE = 'deadline-parent-evidence.json'
BLOCKS = 'deadline-development-blocks'
POLICY = dict(PREDECESSOR_POLICY, experiment=EXPERIMENT,
    candidate_version=CANDIDATE_VERSION, predecessor=PREDECESSOR_POLICY['experiment'],
    authorised_date='2026-09-27', authority='explicit-user-c3-uncapped-deadline-execution',
    execution_contract=execution_contract(),
    design='combined-deadline-context-and-execution-policy-not-single-lever-ablation')
PARENT_FIELDS={'kind','summaries','selection','results_sha256','qualification_sha256',
    'qualification_file_sha256','sources','sources_sha256','dependencies','registration_bindings'}
SUMMARY_FIELDS={'condition','parent','intended','attempted','passes','failures','no_verifier_result',
    'started_without_result','charged_usd','known_charged_usd','unknown_cost_requests',
    'agent_seconds','complexity','rows'}
ROW_FIELDS={'trial_id','task_id','harness','reward','agent_seconds','result_sha256',
    'charged_usd','known_charged_usd','unknown_cost_requests','requests'}


def source_bindings(value):
    if not isinstance(value,dict) or not value:
        raise ValueError('Nonempty source bindings required')
    for name,sha in value.items():
        path=PurePosixPath(name) if isinstance(name,str) else None
        if (path is None or path.is_absolute() or '..' in path.parts or str(path)!=name
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',name)
                or not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{64}',sha)):
            raise ValueError('Relative source name and SHA256 required')


def dependency_bindings(value):
    if (not isinstance(value,dict) or set(value)!={'python','packages'}
            or not isinstance(value['python'],str) or not re.fullmatch(r'\d+\.\d+\.\d+',value['python'])
            or not isinstance(value['packages'],dict) or not value['packages']
            or any(not isinstance(n,str) or not re.fullmatch('[a-z0-9-]+',n)
                   or not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9.+_-]+',v)
                   for n,v in value['packages'].items())):
        raise ValueError('Exact installed dependency versions required')


def summary_fields(summary, *, c3=False):
    required=SUMMARY_FIELDS|({'base_parent'} if c3 else set())
    optional={'efficiency_win_claimed','full_benchmark_win_claimed'}
    if (not isinstance(summary,dict) or not required.issubset(summary)
            or not set(summary).issubset(required|optional)
            or any(summary[k] is not False for k in optional if k in summary)
            or not isinstance(summary['rows'],list)
            or any(not isinstance(row,dict) or set(row)!=ROW_FIELDS for row in summary['rows'])):
        raise ValueError('Only allowlisted outcome metadata may enter selection')


def require_policy(runtime):
    value = private_read(Path(runtime) / POLICY_FILE)
    if fingerprint(value) != fingerprint(POLICY):
        raise ValueError('Exact C3 uncapped policy required')
    return value


def cells(development):
    if (not isinstance(development, list) or len(development) != 20
            or fingerprint(development) != DEVELOPMENT_SHA256):
        raise ValueError('Original fixed development split and order required')
    return [dict(trial_id=f'customdev3-c3-{i:02d}-{task}', task_id=task, harness='C3')
            for i, task in enumerate(development, 1)]


def parent_selection(document):
    if (not isinstance(document, dict) or set(document)!=PARENT_FIELDS
            or document.get('kind') != 'audited_portable_parent_for_c3'):
        raise ValueError('Audited C0/C1/C2 parent evidence required')
    if not isinstance(document['summaries'],dict) or set(document['summaries'])!={'C0','C1','C2'}:
        raise ValueError('All three complete predecessor summaries required')
    for summary in document['summaries'].values(): summary_fields(summary)
    source_bindings(document['sources']);dependency_bindings(document['dependencies'])
    selected = select(document.get('summaries'))
    if fingerprint(document.get('selection')) != fingerprint(selected):
        raise ValueError('C3 parent differs from the preselected complete-block ranking')
    expected = {k:v for row in selected['summaries'].values()
                for k,v in row['results_sha256'].items()}
    if len(expected) != 60 or document.get('results_sha256') != expected:
        raise ValueError('All 60 retained predecessor results must be bound')
    for field in ('qualification_sha256', 'qualification_file_sha256', 'sources_sha256'):
        if not isinstance(document.get(field), str) or not re.fullmatch('[a-f0-9]{64}', document[field]):
            raise ValueError('Predecessor qualification and source binding required')
    if (not isinstance(document.get('sources'), dict)
            or fingerprint(document['sources']) != document['sources_sha256']
            or set(document.get('registration_bindings', {})) != {'C0','C1','C2'}):
        raise ValueError('Exact predecessor source and registration bindings required')
    for binding in document['registration_bindings'].values():
        if (not isinstance(binding, dict) or set(binding) != {'canonical_sha256','file_sha256'}
                or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in binding.values())):
            raise ValueError('Invalid predecessor registration binding')
    return selected


def block_path(runtime):
    if (Path(runtime) / BLOCKS).is_symlink():
        raise ValueError('Unsafe C3 registration directory')
    return Path(runtime) / BLOCKS / 'C3.json'


def require_block(runtime):
    runtime=Path(runtime)
    require_policy(runtime)
    value=private_read(block_path(runtime))
    parent=private_read(runtime / PARENT_FILE)
    selection=parent_selection(parent)
    fixed=dict(experiment=EXPERIMENT, stage='development', condition='C3',
        parent=selection['selected'], base_parent=selection['custom_parent'],
        candidate_version=CANDIDATE_VERSION, python_runtime_sha256=PYTHON_SHA256,
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256, primary_comparator='terminus-2',
        secondary_comparator='openhands', parent_evidence_sha256=fingerprint(parent),
        execution_contract=execution_contract())
    if any(fingerprint(value.get(k)) != fingerprint(v) for k,v in fixed.items()):
        raise ValueError('C3 registration, parent, model or authority changed')
    if value.get('cells') != cells(value.get('development_ids')):
        raise ValueError('Exactly one new C3 attempt per original development task required')
    for field in ('qualification_sha256','sources_sha256'):
        if not isinstance(value.get(field),str) or not re.fullmatch('[a-f0-9]{64}',value[field]):
            raise ValueError('C3 qualification/source binding required')
    return value


def require_trial(runtime, trial_id, stage):
    if (stage != 'development' or not isinstance(trial_id,str) or len(trial_id)>120
            or not re.fullmatch(r'customdev3-c3-\d{2}-[a-z0-9][a-z0-9_.-]*',trial_id)):
        raise ValueError('Registered C3 development attempt required')
    block=require_block(runtime)
    if not any(c['trial_id']==trial_id for c in block['cells']):
        raise ValueError('Unregistered C3 cell')
    proof=private_read(Path(runtime) / QUALIFICATION)
    expected=dict(experiment=EXPERIMENT, status='passed', candidate_version=CANDIDATE_VERSION,
        sources_sha256=block['sources_sha256'], policy_sha256=fingerprint(POLICY),
        model_protocol_sha256=SETTINGS.fingerprint(), parent_evidence_sha256=block['parent_evidence_sha256'],
        execution_contract=execution_contract())
    if (fingerprint(proof)!=block['qualification_sha256']
            or any(fingerprint(proof.get(k))!=fingerprint(v) for k,v in expected.items())
            or proof.get('python_runtime',{}).get('sha256')!=PYTHON_SHA256):
        raise ValueError('C3 qualification changed after registration')
    return block
