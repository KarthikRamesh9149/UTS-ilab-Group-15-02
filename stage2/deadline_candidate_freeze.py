"""Pure four-variant freeze document; qualification/admission stays separate."""
from deadline_custom_policy import fingerprint, parent_selection, execution_contract, dependency_bindings
from deadline_final_selection import select
from portable_candidate_freeze import _source_map, _hash
from portable_custom_policy import SETTINGS, INPUT_SHA256, DEVELOPMENT_SHA256, PYTHON_SHA256

KIND='four_variant_candidate_not_execution_admission'
FIELDS={'kind','parent_evidence','c3_summary','c3_registration_sha256','c3_qualification_sha256',
    'c3_sources','c3_dependencies','selection','result_bindings','model_protocol_sha256',
    'input_manifest_sha256','development_ids_sha256','python_runtime_sha256','execution_contract',
    'paid_launch_ready'}


def freeze(parent,c3,*,registration_sha256,qualification_sha256,sources,dependencies):
    document=dict(kind=KIND,parent_evidence=parent,c3_summary=c3,
        c3_registration_sha256=registration_sha256,c3_qualification_sha256=qualification_sha256,
        c3_sources=sources,c3_dependencies=dependencies,
        selection=select(dict(parent['summaries'],C3=c3),parent),
        result_bindings=dict(parent['results_sha256'],**{r['trial_id']:r['result_sha256'] for r in c3['rows']}),
        model_protocol_sha256=SETTINGS.fingerprint(),input_manifest_sha256=INPUT_SHA256,
        development_ids_sha256=DEVELOPMENT_SHA256,python_runtime_sha256=PYTHON_SHA256,
        execution_contract=execution_contract(),paid_launch_ready=False)
    validate_document(document)
    import json
    return json.loads(json.dumps(document,allow_nan=False))


def validate_document(document):
    if not isinstance(document,dict) or set(document)!=FIELDS or document.get('kind')!=KIND:
        raise ValueError('Exact four-variant candidate document required')
    parent=document['parent_evidence'];parent_selection(parent)
    selected=select(dict(parent['summaries'],C3=document['c3_summary']),parent)
    fixed=dict(selection=selected,model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256,development_ids_sha256=DEVELOPMENT_SHA256,
        python_runtime_sha256=PYTHON_SHA256,execution_contract=execution_contract(),paid_launch_ready=False)
    if any(fingerprint(document.get(k))!=fingerprint(v) for k,v in fixed.items()):
        raise ValueError('Frozen candidate selection or protocol changed')
    for field in ('c3_registration_sha256','c3_qualification_sha256'): _hash(document[field])
    _source_map(document['c3_sources'])
    dependency_bindings(document['c3_dependencies'])
    expected=dict(parent['results_sha256'],**{r['trial_id']:r['result_sha256'] for r in document['c3_summary']['rows']})
    if len(expected)!=80 or document['result_bindings']!=expected:
        raise ValueError('All 80 retained results must be bound')
    return selected
