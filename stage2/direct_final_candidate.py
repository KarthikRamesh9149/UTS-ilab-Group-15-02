"""Lightweight reader for the original four-variant freeze schema.

The gateway does not install the agent or operator's SSH/audit stack. Keep
this structural reader separate from the frozen, operator-side capture code.
Parity tests pin both schemas and recomputed selections; the host still has
to authenticate the original evidence before registering a deployment.
"""
import re

from deadline_custom_contract import CANDIDATE_VERSION, execution_contract
from deadline_custom_policy import source_bindings, dependency_bindings
from deadline_final_selection import select
from portable_custom_policy import (CANDIDATE_VERSION as PORTABLE_VERSION,
    SETTINGS, INPUT_SHA256, DEVELOPMENT_SHA256, PYTHON_SHA256, fingerprint)

MANIFEST_SHA256 = '8bf5271d51eb4306c5fadadf8beee58edd70f595c404223768e39949cca81571'
CANDIDATE_KIND = 'four_variant_candidate_not_execution_admission'
CANDIDATE_FIELDS = {'kind', 'parent_evidence', 'c3_summary', 'c3_registration_sha256',
    'c3_qualification_sha256', 'c3_sources', 'c3_dependencies', 'selection', 'result_bindings',
    'model_protocol_sha256', 'input_manifest_sha256', 'development_ids_sha256',
    'python_runtime_sha256', 'execution_contract', 'paid_launch_ready'}
FIXED = dict(schema_version=1, kind='original_evidence_bound_four_variant_candidate',
    paid_launch_ready=False, full_benchmark_win_claimed=False)
VARIABLE_FIELDS = {'candidate', 'anchor_files', 'selection_logic_sources',
    'original_audit_sha256', 'selected_execution'}
ANCHOR_PATHS = frozenset({
    'stage2/results/custom-deadline-20260927/qualification.json',
    'stage2/results/custom-deadline-20260927/registration-c3.json',
    'stage2/results/custom-deadline-20260927/parent.json',
    'stage2/results/custom-deadline-20260927/credit-policy.json',
    '.runtime/netcup/custom-deadline-20260927/qualified-r2/deadline-qualification.json',
})
LOGIC_FILES = frozenset({
    'deadline_evidence_freeze.py', 'test_deadline_evidence_freeze.py',
    'deadline_candidate_freeze.py', 'test_deadline_candidate_freeze.py',
    'deadline_final_selection.py', 'test_deadline_final_selection.py',
    'deadline_evaluation_schedule.py', 'deadline_custom_policy.py',
    'portable_final_selection.py', 'portable_candidate_freeze.py',
    'export_deadline_custom.py', 'test_export_deadline_custom.py',
    'portable_custom_policy.py', 'retry_policy.py', 'model_protocol.py',
    'gateway_policy.py', 'progress_dashboard.py', 'retry_runtime.py',
    'run_credit_only.py', 'scored_gateway.py',
})


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('SHA256 evidence binding required')


def validate_document(document):
    """Recompute the original ranking without claiming evidence authenticity."""
    if not isinstance(document, dict) or set(document) != set(FIXED) | VARIABLE_FIELDS:
        raise ValueError('Exact evidence-bound candidate schema required')
    if fingerprint({key: document[key] for key in FIXED}) != fingerprint(FIXED):
        raise ValueError('Candidate metadata cannot grant paid admission')
    candidate = document['candidate']
    if (not isinstance(candidate, dict) or set(candidate) != CANDIDATE_FIELDS
            or candidate.get('kind') != CANDIDATE_KIND):
        raise ValueError('Exact four-variant candidate document required')
    parent = candidate['parent_evidence']
    selected = select(dict(parent['summaries'], C3=candidate['c3_summary']), parent)
    expected = dict(selection=selected, model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256, development_ids_sha256=DEVELOPMENT_SHA256,
        python_runtime_sha256=PYTHON_SHA256, execution_contract=execution_contract(),
        paid_launch_ready=False)
    if any(fingerprint(candidate.get(k)) != fingerprint(v) for k, v in expected.items()):
        raise ValueError('Frozen candidate selection or protocol changed')
    for field in ('c3_registration_sha256', 'c3_qualification_sha256'):
        _hash(candidate[field])
    source_bindings(candidate['c3_sources'])
    dependency_bindings(candidate['c3_dependencies'])
    results = dict(parent['results_sha256'], **{
        row['trial_id']: row['result_sha256'] for row in candidate['c3_summary']['rows']})
    if len(results) != 80 or candidate['result_bindings'] != results:
        raise ValueError('All 80 retained results must be bound')
    newer = selected['selected'] == 'C3'
    sources = candidate['c3_sources'] if newer else parent['sources']
    execution = dict(harness=selected['selected'], parent=selected['parent'],
        base_parent=selected['base_parent'],
        candidate_version=CANDIDATE_VERSION if newer else PORTABLE_VERSION,
        original_generation='deadline' if newer else 'portable', sources=sources,
        sources_sha256=fingerprint(sources),
        dependencies=candidate['c3_dependencies'] if newer else parent['dependencies'],
        qualification_sha256=candidate['c3_qualification_sha256'] if newer else parent['qualification_sha256'],
        python_runtime_sha256=candidate['python_runtime_sha256'],
        execution_contract=candidate['execution_contract'] if newer else None)
    if fingerprint(document['selected_execution']) != fingerprint(execution):
        raise ValueError('Selected execution must retain its original whole-variant source')
    for field, keys in (('anchor_files', ANCHOR_PATHS), ('selection_logic_sources', LOGIC_FILES)):
        if not isinstance(document[field], dict) or set(document[field]) != keys:
            raise ValueError('All original anchors and selection code must be bound')
        for value in document[field].values():
            _hash(value)
        if field == 'selection_logic_sources':
            source_bindings(document[field])
    _hash(document['original_audit_sha256'])
    return selected
