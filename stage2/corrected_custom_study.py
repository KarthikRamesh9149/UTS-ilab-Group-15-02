"""Fixed-dev20 registration, qualification and passive-cost candidate selection.

No task instructions, tests, solutions or held-out trajectories are read here.
Missing verifier output and unknown money are kept distinct from zero.
"""
from decimal import Decimal
from importlib.metadata import version
import math
from pathlib import Path
import platform
import re

from corrected_custom_policy import (EXPERIMENT, POLICY, QUALIFICATION, BLOCKS,
    SETTINGS, require_policy, require_block, require_trial, block_path, cells, fingerprint)
from corrected_custom_scope import inspect
from credit_only_accounting import summarise as billing_summary
from credit_only_experiment import coverage, cleanup_complete, digest
from retry_experiment import sources as inherited_sources
from retry_runtime import private_read
from scored_gateway import durable_json, private_directory

DEPLOYMENT = Path('/opt/uts-capstone-custom-development-20260926')
ADDED = ('corrected_custom_agent.py', 'corrected_custom_scope.py',
    'corrected_custom_policy.py', 'corrected_custom_gateway.py', 'corrected_custom_study.py',
    'run_corrected_custom.py', 'corrected_custom_probe.py', 'qualify_corrected_custom.py',
    'test_corrected_custom_agent.py', 'test_corrected_custom_scope.py',
    'test_corrected_custom_policy.py', 'test_corrected_custom_study.py',
    'fixtures/Dockerfile.custom-corrected', 'fixtures/lifecycle/task.toml',
    'fixtures/lifecycle/instruction.md', 'fixtures/lifecycle/environment/Dockerfile',
    'fixtures/lifecycle/tests/test.sh')
TEST_MODULES = ('test_corrected_custom_agent', 'test_corrected_custom_scope',
    'test_corrected_custom_policy', 'test_corrected_custom_study',
    'test_retry_gateway', 'test_credit_only_gateway', 'test_scored_trial',
    'custom_runner_tests', 'custom_backend_tests', 'custom_jobs_tests')
PROBE_CASES = (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1'))
PROBE_CHECKS = {'verifier_reward_one', 'model_revoked', 'clean_status',
    'actual_custom_tool_roundtrip', 'recovered_one_transient',
    'all_physical_requests_accounted', 'unknown_costs_retained', 'no_receipt_or_credit_block',
    'traces_recorded', 'containers_removed', 'networks_removed', 'volumes_removed',
    'sources_unchanged', 'host_unchanged', 'images_unchanged', 'official_resources_audited'}


def sources(root):
    root = Path(root)
    return dict(inherited_sources(root), **{n: digest(root / 'stage2' / n) for n in ADDED})


def dependencies():
    return dict(python=platform.python_version(), packages={name: version(name) for name in (
        'harbor', 'deepagents', 'langgraph', 'langchain', 'langchain-core',
        'langchain-openai', 'openai', 'httpx')})


def identity(root):
    bound = sources(root)
    return dict(experiment=EXPERIMENT, policy_sha256=fingerprint(POLICY),
        model_protocol_sha256=SETTINGS.fingerprint(), sources=bound,
        sources_sha256=fingerprint(bound), dependencies=dependencies(), matched_scope=inspect(root))


def qualified(root):
    import host_environment
    from scored_trial import docker
    root = Path(root)
    runtime = root / '.runtime/stage2'
    require_policy(runtime)
    proof = private_read(runtime / QUALIFICATION)
    current = identity(root)
    if (proof.get('status') != 'passed' or type(proof.get('live_api_calls')) is not int
            or proof['live_api_calls'] != 0 or any(proof.get(k) != v for k, v in current.items())
            or proof.get('host_environment') != host_environment.snapshot()):
        raise ValueError('Current source-bound native custom qualification required')
    if type(proof.get('setup_timeout_seconds')) is not int or proof['setup_timeout_seconds'] != 900:
        raise ValueError('Preserve the corrected baseline setup allowance')
    offline = proof.get('offline', {})
    if (offline.get('modules') != list(TEST_MODULES) or offline.get('passed') is not True
            or type(offline.get('tests')) is not int or offline['tests'] <= 0
            or offline.get('skipped') != 0 or offline.get('errors') != 0 or offline.get('failures') != 0):
        raise ValueError('Required custom offline test evidence missing')
    native = proof.get('synthetic', [])
    if (len(native) != len(PROBE_CASES)
            or [(c.get('condition'), c.get('parent')) for c in native] != list(PROBE_CASES)
            or any(c.get('status') != 'passed' or c.get('live_api_calls') != 0
                   or set(c.get('checks', {})) != PROBE_CHECKS
                   or not all(v is True for v in c['checks'].values()) for c in native)):
        raise ValueError('All actual custom variants need native synthetic qualification')
    for field in ('gateway_image', 'guard_image'):
        image = proof.get(field)
        if not isinstance(image, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            raise ValueError('Pinned image ID required')
        if docker('image', 'inspect', image, '--format', '{{.Id}}') != image:
            raise ValueError('Qualified image unavailable')
    if proof.get('image_sources_match') is not True:
        raise ValueError('Gateway image source qualification required')
    return proof


def all_cells(runtime):
    folder = Path(runtime) / BLOCKS
    if folder.is_symlink():
        raise ValueError('Unsafe registration directory')
    names = sorted(p.name for p in folder.iterdir()) if folder.exists() else []
    if any(n not in {'C0.json', 'C1.json', 'C2.json'} for n in names):
        raise ValueError('Unexpected custom block')
    return [cell for n in names for cell in require_block(runtime, n[:-5])['cells']]


def audited(root):
    runtime = Path(root) / '.runtime/stage2'
    completed, partial = coverage(runtime, all_cells(runtime))
    for name, result in completed.items():
        block = require_trial(runtime, name, 'development')
        if (result.get('stage') != 'development' or result.get('model_revoked') is not True
                or result.get('model_protocol_sha256') != SETTINGS.fingerprint()
                or result.get('custom_registration_sha256') != fingerprint(block)
                or result.get('accounting_mode') != POLICY['accounting_mode']):
            raise ValueError('Custom result protocol/revocation/registration mismatch')
    return completed, partial


def summary(root, condition):
    runtime = Path(root) / '.runtime/stage2'
    block = require_block(runtime, condition)
    complete, partial = audited(root)
    rows, costs = [], []
    for cell in block['cells']:
        name = cell['trial_id']
        result = complete.get(name)
        if result is None:
            continue
        reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        if reward is not None and (type(reward) not in (int, float) or reward not in (0, 1)):
            raise ValueError('Invalid verifier reward')
        # Recompute cost from immutable physical request metadata, never trust
        # an older capped/reserved result or treat missing billing as free.
        billing = billing_summary(runtime, name)
        seconds = result.get('phase_seconds', {}).get('agent')
        if seconds is not None and (type(seconds) not in (int, float)
                or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Invalid observed runtime')
        metadata = (result.get('agent_context') or {}).get('metadata', {})
        if metadata and (metadata.get('custom_condition') != condition
                or metadata.get('custom_parent') != block['parent']):
            raise ValueError('Actual custom condition differs from registration')
        row = dict(cell, reward=reward, agent_seconds=seconds,
            result_sha256=digest(runtime / 'scored-trials' / name / 'result.json'),
            charged_usd=billing['charged_usd'], known_charged_usd=billing['known_charged_usd'],
            unknown_cost_requests=billing['unknown_cost_requests'], requests=billing['requests'])
        rows.append(row)
        costs.append(Decimal(row['charged_usd']) if row['charged_usd'] is not None else None)
    missing = sum(r['reward'] is None for r in rows)
    return dict(condition=condition, parent=block['parent'], intended=20, attempted=len(rows),
        passes=sum(r['reward'] == 1 for r in rows), failures=sum(r['reward'] == 0 for r in rows),
        no_verifier_result=missing, started_without_result=[n for n in partial if n in {c['trial_id'] for c in block['cells']}],
        charged_usd=str(sum(costs, Decimal(0))) if len(rows) == 20 and None not in costs else None,
        known_charged_usd=str(sum((Decimal(r['known_charged_usd']) for r in rows), Decimal(0))),
        unknown_cost_requests=sum(r['unknown_cost_requests'] for r in rows),
        agent_seconds=sum(r['agent_seconds'] for r in rows) if len(rows) == 20 and all(r['agent_seconds'] is not None for r in rows) else None,
        complexity=int(condition == 'C1' or block['parent'] == 'C1') + int(condition == 'C2'),
        rows=rows, efficiency_win_claimed=False, full_benchmark_win_claimed=False)


def selected_parent(root):
    rows = {condition: summary(root, condition) for condition in ('C0', 'C1')}
    if any(r['attempted'] != 20 or r['started_without_result'] for r in rows.values()):
        raise ValueError('Both complete 20-task parent blocks are required')
    # A missing score is not labelled a verifier failure. It earns no pass in
    # the all-intended denominator; the separate missing count remains visible.
    use_cost = all(r['charged_usd'] is not None for r in rows.values())
    def key(condition):
        r = rows[condition]
        return (-r['passes'], *((Decimal(r['charged_usd']),) if use_cost else ()),
            r['complexity'], r['agent_seconds'] if r['agent_seconds'] is not None else math.inf, condition)
    return dict(parent=min(rows, key=key), cost_tiebreak_used=use_cost,
        summaries={c: {k: v for k, v in r.items() if k != 'rows'} for c, r in rows.items()},
        results_sha256={row['trial_id']: row['result_sha256'] for r in rows.values() for row in r['rows']})


def register(root, condition):
    root = Path(root)
    proof = qualified(root)
    runtime = root / '.runtime/stage2'
    if condition not in {'C0', 'C1', 'C2'}:
        raise ValueError('Unknown custom condition')
    completed, partial = audited(root)
    if partial:
        raise ValueError('Started custom attempt retained; inspect before continuing')
    parent_selection = selected_parent(root) if condition == 'C2' else None
    if condition == 'C1' and summary(root, 'C0')['attempted'] != 20:
        raise ValueError('Finish the registered C0 block before C1')
    parent = parent_selection['parent'] if parent_selection else None
    scope = proof['matched_scope']
    value = dict(experiment=EXPERIMENT, stage='development', condition=condition, parent=parent,
        policy_sha256=fingerprint(POLICY), sources_sha256=proof['sources_sha256'],
        qualification_sha256=fingerprint(proof), model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=scope['input_manifest_sha256'], development_ids=scope['development_ids'],
        primary_comparator=scope['primary_comparator'], secondary_comparator=scope['secondary_comparator'],
        cells=cells(scope['development_ids'], condition, parent), parent_selection=parent_selection)
    path = block_path(runtime, condition)
    private_directory(path.parent)
    if path.exists() or path.is_symlink():
        if private_read(path) != value:
            raise ValueError('Immutable custom block changed')
    else:
        durable_json(path, value)
    return value


def admit_trial(root, *, trial_id, task_id, stage, factory, settings, gateway_image, guard_image):
    proof = qualified(root)
    block = require_trial(Path(root) / '.runtime/stage2', trial_id, stage)
    cell = next(c for c in block['cells'] if c['trial_id'] == trial_id)
    if (cell['task_id'] != task_id or cell['harness'] != getattr(factory, 'harness', None)
            or getattr(factory, 'custom_parent', None) != block['parent']
            or getattr(factory, 'custom_version', None) != 'stage2-candidate-0.2.0'
            or settings != SETTINGS or gateway_image != proof['gateway_image']
            or guard_image != proof['guard_image'] or block['qualification_sha256'] != fingerprint(proof)):
        raise ValueError('Scored custom trial differs from its qualified registration')
    return fingerprint(block)
