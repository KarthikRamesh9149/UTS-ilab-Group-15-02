"""Lightweight C0-NC finalist evidence contract, never paid admission.

The original ranking selected C0. This document preserves that decision and
the separately measured no-cutoff revision; it does not rank individual task
attempts, inherit a score, or authenticate self-supplied JSON as native proof.
"""
import json
import math
from decimal import Decimal, InvalidOperation

import no_cutoff_custom_policy as revision

QUALIFICATION_SHA256 = '945f3d5b19a54df7f435a29aab2b78470033751408735af0b69f21fbccd59fd7'
REGISTRATION_SHA256 = '07b1b21ad676ef2422227257998b96ebf193f1260098018c4e7d58db94f542b4'
RESULTS = 'stage2/results/custom-no-cutoff-20260928'
PRIVATE = '.runtime/netcup/custom-no-cutoff-20260928/qualified'
ORIGINAL = '.runtime/finalisation/four-variant-candidate-freeze.json'
PRIVATE_FILES = (revision.CANDIDATE_FILE, revision.AUTHENTICATION_FILE,
    revision.RUNTIME_FILE, revision.POLICY_FILE, revision.QUALIFICATION)
PUBLIC_FILES = ('qualification.json', 'registration-c0-nc.json', 'credit-policy.json', 'lineage.json')
BASE_ANCHORS = frozenset({ORIGINAL, PRIVATE + '/C0-NC.json'} | {
    RESULTS + '/' + name for name in PUBLIC_FILES} | {
    PRIVATE + '/.runtime/stage2/' + name for name in PRIVATE_FILES})
LOGIC_FILES = frozenset({'no_cutoff_final_candidate.py', 'test_no_cutoff_final_candidate.py',
    'no_cutoff_evidence_freeze.py', 'test_no_cutoff_evidence_freeze.py',
    'export_no_cutoff_custom.py', 'no_cutoff_custom_policy.py',
    'deadline_evidence_freeze.py', 'portable_candidate_freeze.py',
    'scored_gateway.py', 'run_credit_only.py'})
ROW_FIELDS = frozenset({'trial_id', 'task_id', 'harness', 'reward', 'agent_seconds',
    'requests', 'unknown_cost_requests', 'known_charged_usd', 'charged_usd', 'result_sha256'})
FIXED = dict(schema_version=1, kind='original_and_no_cutoff_evidence_bound_finalist',
    selection_basis='original-whole-candidate-ranking-then-required-no-cutoff-validation',
    paid_launch_ready=False, original_score_inherited=False,
    efficiency_win_claimed=False, full_benchmark_win_claimed=False,
    confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run')
VARIABLE = frozenset({'original_candidate', 'revision_qualification', 'revision_registration',
    'validation_summary', 'result_bindings', 'selected_execution',
    'revision_audit_sha256', 'anchor_files', 'freeze_logic_sources'})


def _amount(value):
    if not isinstance(value, str):
        raise ValueError('Recorded cost must remain a decimal string')
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('Invalid recorded cost') from error
    if not amount.is_finite() or amount < 0:
        raise ValueError('Finite nonnegative recorded cost required')
    return amount


def summary(rows, block):
    """Preserve twenty outcomes, including zeros and genuinely missing values."""
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError('All twenty registered revision outcomes are required')
    for row, cell in zip(rows, block['cells'], strict=True):
        if (not isinstance(row, dict) or set(row) != ROW_FIELDS
                or any(row.get(k) != v for k, v in cell.items())):
            raise ValueError('Exact registered revision rows in order required')
        reward = row['reward']
        if reward is not None and (type(reward) not in (int, float) or reward not in (0, 1)):
            raise ValueError('Recorded verifier outcome must be zero, one or missing')
        seconds = row['agent_seconds']
        if seconds is not None and (type(seconds) not in (int, float)
                or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Recorded duration must be finite, nonnegative or missing')
        if any(type(row[k]) is not int or row[k] < 0 for k in ('requests', 'unknown_cost_requests')):
            raise ValueError('Nonnegative request counts required')
        if row['unknown_cost_requests'] > row['requests']:
            raise ValueError('Unknown-cost requests cannot exceed all requests')
        _amount(row['known_charged_usd'])
        expected = None if row['unknown_cost_requests'] else row['known_charged_usd']
        if row['charged_usd'] != expected:
            raise ValueError('Unknown cost cannot become zero or a complete total')
        revision._hash(row['result_sha256'])
    known = str(sum((_amount(row['known_charged_usd']) for row in rows), Decimal(0)))
    return dict(condition=revision.CONDITION, parent='C0', base_parent=None,
        intended=20, attempted=20, started_without_result=[],
        passes=sum(row['reward'] == 1 for row in rows),
        failures=sum(row['reward'] == 0 for row in rows),
        no_verifier_result=sum(row['reward'] is None for row in rows),
        requests=sum(row['requests'] for row in rows), known_charged_usd=known,
        charged_usd=known if all(row['charged_usd'] is not None for row in rows) else None,
        unknown_cost_requests=sum(row['unknown_cost_requests'] for row in rows),
        agent_seconds=sum(row['agent_seconds'] for row in rows)
            if all(row['agent_seconds'] is not None for row in rows) else None,
        original_score_inherited=False, efficiency_win_claimed=False,
        full_benchmark_win_claimed=False, rows=rows)


def execution(proof):
    return dict(harness=revision.CONDITION, parent='C0', base_parent=None,
        candidate_version=revision.CANDIDATE_VERSION,
        original_generation='no_cutoff', sources=proof['sources'],
        sources_sha256=proof['sources_sha256'], dependencies=proof['dependencies'],
        qualification_sha256=revision.fingerprint(proof),
        python_runtime_sha256=revision.PYTHON_SHA256,
        model_protocol_sha256=revision.SETTINGS.fingerprint(),
        execution_contract=revision.execution_contract())


def validate_document(document):
    """Structural validation; the operator/native host must authenticate files."""
    if not isinstance(document, dict) or set(document) != set(FIXED) | VARIABLE:
        raise ValueError('Exact separately measured finalist schema required')
    if revision.fingerprint({k: document[k] for k in FIXED}) != revision.fingerprint(FIXED):
        raise ValueError('A candidate cannot grant paid admission or inherit a score')
    original = document['original_candidate']
    revision.candidate_execution(original)
    proof = revision.validate_qualification(original, document['revision_qualification'])
    block = document['revision_registration']
    if (revision.fingerprint(proof) != QUALIFICATION_SHA256
            or revision.fingerprint(block) != REGISTRATION_SHA256
            or revision.fingerprint(block) != revision.fingerprint(
                revision.registration(original, proof, block.get('development_ids')))):
        raise ValueError('Only the single qualified and registered C0-NC revision is allowed')
    measured = document['validation_summary']
    if (not isinstance(measured, dict) or 'rows' not in measured
            or revision.fingerprint(measured) != revision.fingerprint(summary(measured['rows'], block))):
        raise ValueError('Summary must retain and recompute all revision outcomes')
    results = dict(original['candidate']['result_bindings'])
    revised = {row['trial_id']: row['result_sha256'] for row in measured['rows']}
    if set(results) & set(revised) or len(results) != 80 or len(revised) != 20:
        raise ValueError('Original eighty and revised twenty identities must be distinct')
    results.update(revised)
    if document['result_bindings'] != results:
        raise ValueError('All one hundred original and revised results must be bound')
    if revision.fingerprint(document['selected_execution']) != revision.fingerprint(execution(proof)):
        raise ValueError('Finalist must retain the actually measured revised runtime')
    revision._hash(document['revision_audit_sha256'])
    anchors = BASE_ANCHORS | {PRIVATE + '/' + name for name in proof['evidence_files']}
    for field, keys in (('anchor_files', anchors), ('freeze_logic_sources', LOGIC_FILES)):
        values = document[field]
        if not isinstance(values, dict) or set(values) != keys:
            raise ValueError('Exact qualification, registration, producer and freeze bindings required')
        for value in values.values():
            revision._hash(value)
    revision.source_bindings(document['freeze_logic_sources'])
    return document['selected_execution']


def build(original, proof, block, rows, *, audit_sha256, anchors, logic):
    measured = summary(rows, block)
    document = dict(FIXED, original_candidate=original, revision_qualification=proof,
        revision_registration=block, validation_summary=measured,
        result_bindings=dict(original['candidate']['result_bindings'],
            **{row['trial_id']: row['result_sha256'] for row in rows}),
        selected_execution=execution(proof), revision_audit_sha256=audit_sha256,
        anchor_files=anchors, freeze_logic_sources=logic)
    validate_document(document)
    return json.loads(json.dumps(document, allow_nan=False))
