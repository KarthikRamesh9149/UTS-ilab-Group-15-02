"""Completed recovery audit in the real live locked reporting session.

No source/result mutation, qualification, dispatch, archive recreation or saved
admission. Original 89 outcomes remain separate from these three fresh keys.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

import credit_only_accounting as accounting
import no_cutoff_final_archive as original_archive
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as original_report
import no_cutoff_recovery_files as files
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_qualification as qualification
import no_cutoff_recovery_result as preparation
import no_cutoff_recovery_service as service
import no_cutoff_recovery_session as session
import no_cutoff_recovery_study as study
import run_no_cutoff_recovery as runner

KIND = 'completed_separate_C0_NC_recovery3_audit_v1'
RT = '.runtime/stage2/'
ROW_FIELDS = original_report.ROW_FIELDS | {'original_trial_id', 'original_result_sha256', 'recovery_preparation'}


def _merge(target, more):
    for name, digest in more.items():
        if name in target: policy._same(target[name], digest)
        target[name] = digest


def _json(root, name, bound, identities):
    raw, observed = files.read(root, name)
    _merge(bound, {name: observed['sha256']})
    if name in identities and identities[name] != observed['identity']:
        raise ValueError('Recovery audit producer replaced')
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
    raise ValueError('Corroborated absent recovery evidence appeared')


def row(root, cell, result, limits, bound, identities, directories, directory_ids, absent):
    trial = RT + 'scored-trials/' + cell['trial_id']
    start = _json(root, trial + '/started.json', bound, identities)
    actual = _json(root, trial + '/result.json', bound, identities); policy._same(actual, result)
    if (start.get('status') != 'starting' or start.get('started_utc') != result.get('started_utc')
            or start.get('project') != result.get('project')
            or type(result.get('project')) is not str or not re.fullmatch('uts-scored-[a-f0-9]{12}', result['project'])):
        raise ValueError('Exact retained recovery start identity required')
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
    observed = phase._phase_row(result, events, lifecycle, timings, len(requests), limits)
    billing = accounting.summarise(root / RT, cell['trial_id'])
    policy._same(billing, result.get('billing'))
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
        unknown_cost_requests=billing['unknown_cost_requests'], cleanup_complete=True, model_revoked=True,
        original_trial_id=cell['original_trial_id'], original_result_sha256=cell['original_result_sha256'],
        recovery_preparation=preparation.validate(result.get('recovery_preparation')))
    if not observed['recovery_preparation']['observation_complete']:
        raise ValueError('Incomplete retained preparation cannot silently become complete reporting')
    for name in ('input_tokens', 'output_tokens'):
        values = [c[name] for c in calls if c[name] is not None]
        observed['known_' + name] = sum(values)
        observed[name] = sum(values) if len(values) == len(calls) else None
    if set(observed) != ROW_FIELDS: raise ValueError('Only allowlisted recovery row metadata permitted')
    phase._number(limits['cpus'], positive=True); phase._number(limits['memory_mb'], positive=True)
    original_report._utc(observed['started_utc']); original_report._utc(observed['completed_utc'])
    return observed


def reread(root, data, state):
    files.check(root, data['supporting_files'], state['identities'])
    for name, entries in data['directory_entries'].items():
        path = root / name
        if (files.bootstrap.directories(path, private=True) != state['directory_ids'][name]
                or sorted(p.name for p in path.iterdir()) != entries):
            raise ValueError('Recovery evidence directory identity or inventory changed')
    for name in data['absent_paths']:
        _absent(root, name)


def collect(active):
    """Actual completed native audit, never a standalone saved-report shortcut."""
    live = session._live(active); root = live['root']
    if root != service.ROOT: raise ValueError('Own recovery reporting root required')
    session.recheck(active); study._clear(root)
    verified = qualification.for_dispatch(active)
    ended = service.completed_operation(active, 'run-recovery')
    proof, block = verified['proof'], verified['block']
    bound = dict(verified['files']); identities = dict(verified['identities'])
    _merge(bound, ended['files']); identities = files.extend(root, bound, identities)
    registration = _json(root, RT + policy.REGISTRATION_FILE, bound, identities)
    policy._same(registration, block)
    dispatch = _json(root, RT + runner.RESULT, bound, identities)
    if (dispatch.get('status') != 'complete' or dispatch.get('intended') != 3 or dispatch.get('completed') != 3
            or dispatch.get('stop_markers') or (root / RT / runner.FAILURE).exists()
            or (root / RT / runner.FAILURE).is_symlink()):
        raise ValueError('Only the actual completed unstopped three-cell dispatch can be audited')
    intent = _json(root, RT + runner.INTENT, bound, identities)
    policy._same(dispatch['dispatch_intent_sha256'], bound[RT + runner.INTENT])
    policy._same(intent['registration_sha256'], policy.fingerprint(block))
    complete, partial, retained = study._attempts(root, block)
    if partial or set(complete) != {c['trial_id'] for c in block['cells']}:
        raise ValueError('Exactly all three actual registered outcomes required')
    study._images(root, proof, complete); _merge(bound, retained)
    identities = files.extend(root, bound, identities)
    directories, directory_ids, absent, rows = {}, {}, set(), []
    for cell in block['cells']:
        rows.append(row(root, cell, complete[cell['trial_id']], live['host']['task_inventory'][cell['task_id']],
            bound, identities, directories, directory_ids, absent))
    data = dict(kind=KIND, experiment=policy.EXPERIMENT, collected_utc=datetime.now(timezone.utc).isoformat(),
        original_full89_denominator=89, separate_recovery_denominator=3, original_results_replaced=False,
        recovery_merged_into_original89=False, sources=proof['sources'], sources_sha256=proof['sources_sha256'],
        qualification_sha256=policy.fingerprint(proof), registration=block,
        predecessor=live['predecessor']['predecessor'], rows=rows, aggregate=original_report.aggregate(rows),
        supporting_files=bound, directory_entries=directories, absent_paths=sorted(absent),
        paid_launch_ready=False, completed_recovery_audit=True, off_server_backup_verified=False,
        historical_installed_bytes_attested=False, full_runtime_restore_exercised=False)
    state = dict(identities=files.extend(root, bound, identities), directory_ids=directory_ids)
    # Real observations precede final source/private/history/result rereads.
    runner._owned_resources_clear()
    for result in complete.values(): original_report._resources(result['project'])
    again = qualification.for_dispatch(active); policy._same(again['proof'], proof)
    final_service = service.completed_operation(active, 'run-recovery')
    policy._same(final_service['files'], ended['files'])
    session.recheck(active); study._clear(root)
    policy._same(study._attempts(root, block)[0], complete)
    reread(root, data, state)
    return data, state


def validate(data, manifest, sources):
    """Strict projection schema; not evidence that a collector actually ran."""
    expected_fields = {'kind', 'experiment', 'collected_utc', 'original_full89_denominator',
        'separate_recovery_denominator', 'original_results_replaced', 'recovery_merged_into_original89',
        'sources', 'sources_sha256', 'qualification_sha256', 'registration', 'predecessor', 'rows',
        'aggregate', 'supporting_files', 'directory_entries', 'absent_paths', 'paid_launch_ready',
        'completed_recovery_audit', 'off_server_backup_verified', 'historical_installed_bytes_attested',
        'full_runtime_restore_exercised'}
    if type(data) is not dict or set(data) != expected_fields: raise ValueError('Exact recovery snapshot schema required')
    fixed = dict(kind=KIND, experiment=policy.EXPERIMENT, original_full89_denominator=89,
        separate_recovery_denominator=3, original_results_replaced=False, recovery_merged_into_original89=False,
        paid_launch_ready=False, completed_recovery_audit=True, off_server_backup_verified=False,
        historical_installed_bytes_attested=False, full_runtime_restore_exercised=False,
        sources=sources, sources_sha256=policy.fingerprint(sources))
    for key, value in fixed.items(): policy._same(data[key], value)
    original_report._utc(data['collected_utc']); policy._hash(data['qualification_sha256'])
    plan = policy.plan.schedule(manifest)
    if len(data['rows']) != 3 or len(data['registration']['cells']) != 3:
        raise ValueError('Exactly three separate recovery outcomes required')
    for actual, cell in zip(data['rows'], plan['cells']):
        if set(actual) != ROW_FIELDS: raise ValueError('Only allowlisted recovery row fields permitted')
        for key in ('trial_id', 'task_id', 'original_trial_id', 'original_result_sha256'):
            policy._same(actual[key], cell[key])
        policy._same(actual['harness'], policy.CONDITION)
        if actual['reward'] is not None and (type(actual['reward']) not in (int, float) or actual['reward'] not in (0, 1)):
            raise ValueError('Keep real zero, one and missing outcomes separate')
        policy._hash(actual['result_sha256']); preparation.validate(actual['recovery_preparation'])
        for name, digest in actual['recovery_preparation']['observation']['sources'].items():
            policy._same(sources.get(name), digest)
        original_archive._row({k:v for k,v in actual.items() if k in original_report.ROW_FIELDS},
            dict(agent_timeout_seconds=actual['official_agent_timeout_seconds'],
                verifier_timeout_seconds=actual['official_verifier_timeout_seconds'],
                cpus=actual['official_cpus'],memory_mb=actual['official_memory_mb']),
            original_archive._utc(data['collected_utc']))
        policy._same(data['supporting_files'].get(RT + 'scored-trials/' + cell['trial_id'] + '/result.json'), actual['result_sha256'])
    policy._same(data['aggregate'], original_report.aggregate(data['rows']))
    for name, digest in data['supporting_files'].items(): files.libraries.relative(name); policy._hash(digest)
    for name, digest in sources.items(): policy._same(data['supporting_files'].get('stage2/' + name), digest)
    return data
