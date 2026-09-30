"""Completed baseline-repeat audit in a real same-task locked session.

Original 52/89 and 44/89 outcomes and custom/recovery outcomes remain separate.
No saved receipt, caller factory, score floor, mutation or replay is accepted.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

import credit_only_accounting as accounting
import matched_repeat_completion as completion
import matched_repeat_policy as policy
import matched_repeat_phase as baseline_phase
import matched_repeat_runtime as runtime
import matched_repeat_session as session
import matched_repeat_study as study
import no_cutoff_final_archive as original_archive
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as original_report
import no_cutoff_recovery_files as files
import run_matched_repeat as runner
from no_cutoff_final_archive import _same as same

KIND = 'completed_separate_matched_baseline_repeat89_audit_v1'
RT = '.runtime/stage2/'
ROW_FIELDS = original_report.ROW_FIELDS


def _merge(target, more):
    for name, digest in more.items():
        if name in target: same(target[name], digest)
        target[name] = digest


def _json(root, name, bound, identities):
    raw, observed = files.read(root, name)
    _merge(bound, {name: observed['sha256']})
    if name in identities and identities[name] != observed['identity']:
        raise ValueError('Baseline audit producer replaced')
    identities[name] = observed['identity']
    return files.bootstrap.loads(raw)


def _inventory(root, name, directories, directory_ids, absent, *, optional=False):
    path = root / files.libraries.relative(name)
    if not path.exists() and not path.is_symlink() and optional:
        # Protect the actual parent too, including genuinely absent leaf paths.
        _absent(root, name)
        absent.add(name); return []
    directory_ids[name] = files.bootstrap.directories(path, private=True)
    children = sorted(p.name for p in path.iterdir())
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+\.json', child) for child in children):
        raise ValueError('Exact retained JSON evidence inventory required')
    directories[name] = children
    return [name + '/' + child for child in children]


def _absent(root, name):
    current = root
    for part in files.libraries.relative(name).split('/'):
        next_path = current / part
        files.bootstrap.directories(current, private=True)
        if not next_path.exists() and not next_path.is_symlink(): return
        current = next_path
    raise ValueError('Corroborated absent baseline evidence appeared')


def row(root, cell, result, limits, bound, identities, directories, directory_ids, absent):
    trial = RT + 'scored-trials/' + cell['trial_id']
    start = _json(root, trial + '/started.json', bound, identities)
    actual = _json(root, trial + '/result.json', bound, identities); same(actual, result)
    if (start.get('status') != 'starting' or start.get('started_utc') != result.get('started_utc')
            or start.get('project') != result.get('project')
            or type(result.get('project')) is not str or not re.fullmatch('uts-scored-[a-f0-9]{12}', result['project'])):
        raise ValueError('Exact retained baseline start identity required')
    events = []
    for name in _inventory(root, trial + '/traces', directories, directory_ids, absent):
        event = _json(root, name, bound, identities)
        if Path(name).stem != event.get('event_id'): raise ValueError('Trace filename identity differs')
        events.append(event)
    account = _inventory(root, RT + 'scored-attempts/' + cell['trial_id'],
        directories, directory_ids, absent, optional=True)
    actual_files, actual_ids = files.capture(root, account)
    _merge(bound, actual_files); identities.update(actual_ids)
    requests = {n.removesuffix('.request.json') for n in account if n.endswith('.request.json')}
    timings = []; statuses = Counter()
    for name in account:
        if name.endswith('/provider-stop.json'):
            raise ValueError('Persistent provider stop requires separate inspection')
        if result.get('status') == 'setup_failed' and not name.endswith('/started.json'):
            raise ValueError('Unexecuted agent cannot have model accounting artifacts')
        if name.endswith('.timing.json'):
            if name.removesuffix('.timing.json') not in requests: raise ValueError('Orphaned model timing')
            timings.append(_json(root, name, bound, identities))
        elif name.endswith(('.outcome.json', '.transport-error.json', '.retry.json')):
            metadata = _json(root, name, bound, identities)
            if name.endswith('.transport-error.json'): statuses[str(metadata.get('http_status'))] += 1
    deadline = RT + 'retry-lifecycle/' + cell['trial_id'] + '.json'
    if (root / deadline).exists() or (root / deadline).is_symlink():
        lifecycle = _json(root, deadline, bound, identities)
    else:
        _absent(root, deadline)
        lifecycle = None; absent.add(deadline)
    observed = baseline_phase.read(result, events, lifecycle, timings, len(requests), limits)
    billing = accounting.summarise(root / RT, cell['trial_id'])
    same(billing, result.get('billing'))
    calls = accounting.call_records(root / RT / 'scored-attempts' / cell['trial_id'])
    if len(calls) != len(requests) or billing.get('provider_stop') is not None:
        raise ValueError('Fresh passive request accounting differs from retained result')
    accepted = sum(c.get('accepted_for_agent') is True for c in calls)
    interrupted = sum(c.get('accepted_for_agent') is not True and c.get('status') == 'interrupted' for c in calls)
    errors = sum(c.get('accepted_for_agent') is not True and c.get('status') == 'error' for c in calls)
    observed.update(result_sha256=bound[trial + '/result.json'], started_utc=result['started_utc'],
        official_cpus=limits['cpus'], official_memory_mb=limits['memory_mb'],
        accepted_model_responses=accepted, interrupted_requests=interrupted, error_requests=errors,
        other_unaccepted_requests=len(calls)-accepted-interrupted-errors,
        http_429_requests=statuses.get('429', 0), transport_error_requests=sum(statuses.values()),
        retry_records=sum(n.endswith('.retry.json') for n in account),
        known_cost_usd=billing['known_charged_usd'], total_cost_usd=billing['charged_usd'],
        unknown_cost_requests=billing['unknown_cost_requests'], cleanup_complete=True, model_revoked=True)
    for name in ('input_tokens', 'output_tokens'):
        values = [c[name] for c in calls if c[name] is not None]
        observed['known_' + name] = sum(values)
        observed[name] = sum(values) if len(values) == len(calls) else None
    if set(observed) != ROW_FIELDS: raise ValueError('Only allowlisted baseline row metadata permitted')
    phase._number(limits['cpus'], positive=True); phase._number(limits['memory_mb'], positive=True)
    original_report._utc(observed['started_utc']); original_report._utc(observed['completed_utc'])
    return observed


def reread(root, data, state):
    files.check(root, data['supporting_files'], state['identities'])
    for name, entries in data['directory_entries'].items():
        path = root / name
        if (files.bootstrap.directories(path, private=True) != state['directory_ids'][name]
                or sorted(p.name for p in path.iterdir()) != entries):
            raise ValueError('Baseline evidence directory identity or inventory changed')
    for name in data['absent_paths']:
        _absent(root, name)


def collect(active):
    """Fresh native reads under the actual live session, never a saved audit."""
    live = session._live(active); root = live['root']; harness = live['harness']
    if (root != runtime.DEPLOYMENTS[harness]
            or Path(__file__).absolute() != root / 'stage2/matched_repeat_report.py'):
        raise ValueError('Own fixed baseline reporting root required')
    session.recheck(active); study._clear(root)
    qualified_root, proof, block, bound = study._qualified(active)
    if root != qualified_root: raise ValueError('Qualified baseline root changed')
    bound = dict(bound); identities = files.capture(root, bound)[1]
    qualification_end = completion.read(active, 'qualify-repeat')
    ended = completion.read(active, 'run-repeat')
    for observed in (qualification_end, ended):
        _merge(bound, observed['files'])
        for name, identity in observed['identities'].items():
            if name in identities and identities[name] != identity:
                raise ValueError('Baseline producer identity changed')
            identities[name] = identity
    registration = _json(root, RT + policy.REGISTRATION_FILE, bound, identities)
    same(registration, block)
    dispatch = _json(root, RT + runner.RESULT, bound, identities)
    if (dispatch.get('status') != 'complete' or dispatch.get('intended') != 89
            or dispatch.get('completed') != 89 or dispatch.get('stop_markers')
            or (root / RT / runner.FAILURE).exists() or (root / RT / runner.FAILURE).is_symlink()):
        raise ValueError('Exactly the actual completed unstopped baseline89 is required')
    intent = _json(root, RT + runner.INTENT, bound, identities)
    same(dispatch['dispatch_intent_sha256'], bound[RT + runner.INTENT])
    same(intent['registration_sha256'], policy.fingerprint(block))
    complete, partial, retained = study._attempts(root, block)
    if partial or set(complete) != {c['trial_id'] for c in block['cells']}:
        raise ValueError('All 89 actual registered baseline outcomes required')
    study._images(root, proof, complete); _merge(bound, retained)
    identities = files.extend(root, bound, identities)
    directories, directory_ids, absent, rows = {}, {}, set(), []
    for cell in block['cells']:
        rows.append(row(root, cell, complete[cell['trial_id']], live['host']['task_inventory'][cell['task_id']],
            bound, identities, directories, directory_ids, absent))
    data = dict(kind=KIND, experiment=policy.EXPERIMENT, harness=harness,
        collected_utc=datetime.now(timezone.utc).isoformat(), intended=89,
        original_scores={'terminus-2': 52, 'openhands': 44}, original_results_replaced=False,
        sources=proof['sources'], sources_sha256=proof['sources_sha256'],
        qualification_sha256=policy.fingerprint(proof), registration=block,
        predecessors=live['predecessor']['predecessors'],
        original_audit_sha256=policy.fingerprint(live['original_record']),
        rows=rows, aggregate=original_report.aggregate(rows),
        development20=original_report.aggregate(rows[:20]), remaining69=original_report.aggregate(rows[20:]),
        supporting_files=bound, directory_entries=directories, absent_paths=sorted(absent),
        paid_launch_ready=False, completed_repeat_audit=True, off_server_backup_verified=False,
        historical_installed_bytes_attested=False, full_runtime_restore_exercised=False)
    state = dict(identities=files.extend(root, bound, identities), directory_ids=directory_ids)
    runner._owned_resources_clear()
    for result in complete.values(): original_report._resources(result['project'])
    again_root, again_proof, again_block, _ = study._qualified(active)
    if again_root != root: raise ValueError('Late baseline root changed')
    same(again_proof, proof); same(again_block, block)
    for operation, observed in (('qualify-repeat', qualification_end), ('run-repeat', ended)):
        same(completion.read(active, operation), observed)
    session.recheck(active); study._clear(root)
    same(study._attempts(root, block)[0], complete)
    reread(root, data, state)
    return data, state


def validate(data, manifest, sources):
    """Strict allowlisted projection, not evidence that a collector ran."""
    fields = {'kind', 'experiment', 'harness', 'collected_utc', 'intended', 'original_scores',
        'original_results_replaced', 'sources', 'sources_sha256', 'qualification_sha256',
        'registration', 'predecessors', 'original_audit_sha256', 'rows', 'aggregate',
        'development20', 'remaining69', 'supporting_files', 'directory_entries', 'absent_paths',
        'paid_launch_ready', 'completed_repeat_audit', 'off_server_backup_verified',
        'historical_installed_bytes_attested', 'full_runtime_restore_exercised'}
    if type(data) is not dict or set(data) != fields:
        raise ValueError('Exact baseline completed snapshot schema required')
    harness = data['harness']; policy._harness(harness)
    fixed = dict(kind=KIND, experiment=policy.EXPERIMENT, intended=89,
        original_scores={'terminus-2': 52, 'openhands': 44}, original_results_replaced=False,
        paid_launch_ready=False, completed_repeat_audit=True, off_server_backup_verified=False,
        historical_installed_bytes_attested=False, full_runtime_restore_exercised=False,
        sources=sources, sources_sha256=policy.fingerprint(sources))
    for key, value in fixed.items(): same(data[key], value)
    original_report._utc(data['collected_utc'])
    for name in ('qualification_sha256', 'original_audit_sha256'): policy._hash(data[name])
    policy.validate_predecessors(data['predecessors'], manifest, harness)
    expected = policy.cells(manifest, harness)
    block = data['registration']
    if (type(block) is not dict or block.get('harness') != harness or block.get('intended') != 89
            or block.get('experiment') != policy.EXPERIMENT or block.get('original_results_replaced') is not False):
        raise ValueError('Separate matched baseline registration required')
    same(block['cells'], expected); same(block['qualification_sha256'], data['qualification_sha256'])
    same(block['sources_sha256'], data['sources_sha256'])
    if type(data['rows']) is not list or len(data['rows']) != 89:
        raise ValueError('Exactly all 89 separate baseline outcomes required')
    collected = original_archive._utc(data['collected_utc'])
    for actual, cell in zip(data['rows'], expected):
        if type(actual) is not dict or set(actual) != ROW_FIELDS:
            raise ValueError('Only allowlisted baseline row fields permitted')
        for key in ('trial_id', 'task_id', 'harness'): same(actual[key], cell[key])
        policy._hash(actual['result_sha256'])
        original_archive._row(actual,
            dict(agent_timeout_seconds=actual['official_agent_timeout_seconds'],
                verifier_timeout_seconds=actual['official_verifier_timeout_seconds'],
                cpus=actual['official_cpus'], memory_mb=actual['official_memory_mb']), collected)
        same(data['supporting_files'].get(RT + 'scored-trials/' + cell['trial_id'] + '/result.json'),
            actual['result_sha256'])
    for key, values in (('aggregate', data['rows']), ('development20', data['rows'][:20]),
            ('remaining69', data['rows'][20:])):
        same(data[key], original_report.aggregate(values))
    original_archive._inventories(data['directory_entries'], data['absent_paths'])
    for name, digest in data['supporting_files'].items():
        files.libraries.relative(name); policy._hash(digest)
    for name, digest in sources.items(): same(data['supporting_files'].get('stage2/' + name), digest)
    if any(n == a or n.startswith(a + '/') for n in data['supporting_files'] for a in data['absent_paths']):
        raise ValueError('Baseline supporting evidence contradicts actual absence')
    return data
