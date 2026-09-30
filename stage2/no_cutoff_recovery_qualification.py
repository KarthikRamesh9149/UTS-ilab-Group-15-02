"""Read genuine retained recovery producers inside the actual live session.

This does not create qualification. Native regression, image and six lifecycle
producers must have run through the separately bound trusted qualifier first.
No caller-supplied proof, callback, root or saved inspection receipt is accepted.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

import no_cutoff_recovery_files as files
import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_result as retained
import no_cutoff_recovery_session as session
from credit_only_accounting import summarise
from credit_only_experiment import cleanup_complete
from local_trace import validate as validate_trace
import no_cutoff_final_phase_audit as original_phase

INPUTS = (policy.POLICY_FILE, policy.PLAN_FILE, policy.MANIFEST_FILE,
    policy.ORIGINAL_FILE, policy.PREDECESSOR_FILE, policy.RUNTIME_FILE, policy.QUALIFICATION_FILE)
FIXTURE_FILE = 'no-cutoff-recovery-fixture.json'
FIXTURE_KIND = 'isolated_synthetic_C0_NC_recovery_not_paid_registration'


def no_failure(root):
    names = [policy.QUALIFIER_FAILURE_FILE, images.FAILURE]
    names += ['no-cutoff-recovery-rehearsal-' + mode + '-failure.json' for mode in policy.PROBE_MODES]
    for name in names:
        path = root / '.runtime/stage2' / name
        if path.exists() or path.is_symlink():
            raise ValueError('Retained recovery qualification failure forbids admission or automatic repetition')


def inputs(root, identities=None):
    records, bindings = {}, {}
    for name in INPUTS:
        records[name], bound = files.private(root, name, identities); bindings.update(bound)
    policy._same(records[policy.POLICY_FILE], policy.POLICY)
    policy.plan.validate_schedule(records[policy.PLAN_FILE], records[policy.MANIFEST_FILE])
    raw, _ = files.read(root, '.runtime/stage2/' + policy.ORIGINAL_FILE)
    policy._same(hashlib.sha256(raw).hexdigest(), policy.ORIGINAL_QUALIFICATION_FILE_SHA256)
    raw, _ = files.read(root, '.runtime/stage2/' + policy.MANIFEST_FILE)
    policy._same(hashlib.sha256(raw).hexdigest(), policy.INPUT_SHA256)
    return records, bindings


def _json(root, name, identities=None):
    raw, binding = files.read(root, name)
    if identities is not None:
        if name in identities and identities[name] != binding['identity']:
            raise ValueError('Actual producer identity replaced during read')
        identities[name] = binding['identity']
    return session.handoff.phase._loads(raw), {name: binding['sha256']}


def _inventory(root, relative):
    path = root / relative
    files.bootstrap.directories(path, private=True)
    found = []
    for child in sorted(path.iterdir()):
        # This inventory is deliberately all immediate metadata files, not a
        # permissive glob that could ignore a newly introduced producer.
        name = child.relative_to(root).as_posix()
        if not child.name.endswith('.json'):
            raise ValueError('Unexpected native qualification evidence entry')
        files.libraries.read(root, name)
        found.append(name)
    return found


def case_files(root, case, proof, *, pending=False):
    """Real start/result, trace/accounting and exact supporting inventory reads."""
    mode = case['mode']; relative = case['runtime_path']
    read_ids = {}
    def read_json(name): return _json(root, name, read_ids)
    policy.probe_checks(mode)
    import re
    if not re.fullmatch(r'\.runtime/stage2/native-no-cutoff-recovery-' + mode + r'-[a-zA-Z0-9_]+', relative):
        raise ValueError('Exact fixed native case path required')
    trial_id = 'synthetic-nc-recovery-' + mode
    rt = relative + '/.runtime/stage2/'
    trial = rt + 'scored-trials/' + trial_id + '/'
    intent_name = '.runtime/stage2/no-cutoff-recovery-rehearsal-' + mode + '.json'
    intent, bound = read_json(intent_name)
    expected = dict(kind='one_shot_native_recovery_rehearsal', mode=mode,
        experiment=policy.EXPERIMENT, runtime_path=relative,
        sources_sha256=proof['sources_sha256'], image_build_sha256=proof['image_build_sha256'],
        automatic_resume=False, paid_launch_ready=False)
    for key, value in expected.items(): policy._same(intent.get(key), value)
    if type(intent.get('pid')) is not int or intent['pid'] <= 0 or not intent.get('started_utc'):
        raise ValueError('Actual native rehearsal producer identity required')
    if not pending:
        saved, report_files = read_json(relative + '/evidence.json'); bound.update(report_files)
        policy._same(saved, case)
    start, start_files = read_json(trial + 'started.json'); bound.update(start_files)
    result, result_files = read_json(trial + 'result.json'); bound.update(result_files)
    expected = dict(trial_id=trial_id, task_id='lifecycle', stage='final',
        harness=policy.CONDITION, recovery_experiment=policy.EXPERIMENT,
        recovery_fixture=FIXTURE_KIND, model_protocol_sha256=policy.MODEL_SHA256,
        gateway_image_id=proof['gateway_image'], guard_image_id=proof['guard_image'],
        accounting_mode='provider-credit-only')
    for record in (start, result):
        for key, value in expected.items(): policy._same(record.get(key), value)
        if any(key in record for key in ('recovery_registration_sha256', 'custom_study',
                'matched_repeat_experiment', 'accounting_runtime_transition_sha256')):
            raise ValueError('A native recovery rehearsal cannot claim paid or legacy admission')
    for key in ('project', 'started_utc', 'recovery_fixture_sha256'):
        if not start.get(key): raise ValueError('Exact actual rehearsal start binding required')
        policy._same(start[key], result.get(key))
    if result.get('model_revoked') is not True or not cleanup_complete(result):
        raise ValueError('Native rehearsal requires actual revocation and owned cleanup')
    observation = retained.validate(result.get('recovery_preparation'))
    if not observation['observation_complete']:
        raise ValueError('Incomplete setup observation cannot qualify execution')
    policy._same(policy.fingerprint(observation), case['preparation_observation_sha256'])
    inner = observation['observation']
    for name, digest in inner['sources'].items(): policy._same(proof['sources'].get(name), digest)
    outcome = inner['preparation_status'] or inner['infrastructure_category']
    policy._same(outcome, policy.PREPARATION_OUTCOMES[mode])
    trace_names = _inventory(root, trial + 'traces')
    account_names = _inventory(root, rt + 'scored-attempts/' + trial_id)
    support = {relative + '/stage2/input_manifest.json', relative + '/admission.json', rt + FIXTURE_FILE,
        rt + 'synthetic-provider.txt', rt + 'python-runtime.tar.gz',
        rt + 'model-protocol.json',
        trial + 'started.json', trial + 'result.json', trial + 'compose.json',
        *trace_names, *account_names}
    stopped = mode in {'prepare_nonzero', 'prepare_exception', 'cancel_setup'}
    deadline = rt + 'retry-lifecycle/' + trial_id + '.json'
    cooldown = rt + 'provider-cooldown.json'
    if not stopped: support |= {deadline, cooldown}
    else:
        for name in (deadline, cooldown):
            if (root / name).exists() or (root / name).is_symlink():
                raise ValueError('Unexecuted model phase requires actual deadline/cooldown absence')
    if mode == 'boundary_stop': support.add(rt + 'operator-stop-request.json')
    producer, producer_files = read_json(relative + '/producer.json'); bound.update(producer_files)
    fixed = dict(kind='actual_native_recovery_supporting_producers', mode=mode,
        runtime_path=relative, source_sha256=proof['sources_sha256'],
        image_build_sha256=proof['image_build_sha256'], paid_launch_ready=False)
    for key, value in fixed.items(): policy._same(producer.get(key), value)
    if set(producer) != set(fixed) | {'files'} or set(producer['files']) != support:
        raise ValueError('Every actual supporting producer must be retained exactly')
    actual, identities = files.capture(root, producer['files']); bound.update(actual)
    files.extend(root, bound, read_ids)
    from no_cutoff_recovery_fixture import document, SYNTHETIC_KEY
    policy._same(_json(root, rt + FIXTURE_FILE)[0], document(mode))
    policy._same(_json(root, relative + '/stage2/input_manifest.json')[0],
        dict(all_task_ids=['lifecycle'], development_ids=['lifecycle']))
    policy._same(_json(root, rt + 'model-protocol.json')[0], policy.SETTINGS.document())
    if files.read(root, rt + 'synthetic-provider.txt')[0] != ('OPENROUTER_API_KEY=' + SYNTHETIC_KEY + '\n').encode():
        raise ValueError('Exact synthetic credential required')
    policy._same(actual[rt + 'python-runtime.tar.gz'], policy.PYTHON_SHA256)
    host = files.private(root, policy.RUNTIME_FILE)[0]
    official = host['task_inventory']['pytorch-model-recovery']
    admission = _json(root, relative + '/admission.json')[0]
    expected_admission = dict(kind='actual_native_recovery_fixture_admission', resource_task_id='pytorch-model-recovery',
        official=official, task_id='lifecycle', trial_id=trial_id, setup_timeout_seconds=900,
        instruction_sha256=files.libraries.read(root, 'stage2/fixtures/lifecycle/instruction.md'),
        sources_sha256=proof['sources_sha256'], paid_launch_ready=False)
    policy._same(admission, expected_admission)
    policy._same(result.get('task_image_id'), official['image_id'])
    events = [validate_trace(read_json(name)[0]) for name in trace_names]
    if any(Path(name).stem != event['event_id'] for name, event in zip(trace_names, events)):
        raise ValueError('Actual trace filename differs from its event identity')
    if sorted(e['sequence'] for e in events) != list(range(len(events))):
        raise ValueError('Complete native phase/trace sequence required')
    for event in events:
        for key, value in dict(trial_id=trial_id, task_id=expected['task_id'],
                harness=policy.CONDITION, protocol_sha256=policy.MODEL_SHA256).items():
            policy._same(event.get(key), value)
    billing = summarise(root / relative / '.runtime/stage2', trial_id)
    policy._same(result.get('billing'), billing)
    phases = ['setup', 'cleanup', 'trial'] if stopped else ['setup', 'agent', 'verifier', 'cleanup', 'trial']
    policy._same(sorted(e['kind'] for e in events if e['kind'] != 'generation'), sorted(phases))
    if len([e for e in events if e['kind'] == 'generation']) != billing['requests']:
        raise ValueError('All actual physical requests need native timing evidence')
    policy._same(result.get('trace', {}).get('missing_generation_timings'), 0)
    reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
    policy._same(result.get('status'), 'interrupted' if mode == 'cancel_setup' else 'setup_failed' if stopped else 'verified')
    if stopped:
        if (billing['requests'] != 0 or reward is not None or not retained.empty_agent_context(result.get('agent_context'))
                or set(result.get('phase_seconds', {})) != {'setup'}):
            raise ValueError('Failed preparation must not execute agent/model/verifier')
    elif type(reward) not in (int, float) or reward != 1 or billing['requests'] != 3:
        raise ValueError('Genuine native tool/graph/verifier execution required')
    if mode in {'tools', 'boundary_stop'} and len([n for n in account_names if n.endswith('.retry.json')]) != 1:
        raise ValueError('The actual shared transient retry must be retained')
    if billing['unknown_cost_requests'] != billing['requests'] or billing['provider_stop'] is not None:
        raise ValueError('Native synthetic accounting must retain unknown cost and no provider access')
    requests = {n.removesuffix('.request.json') for n in account_names if n.endswith('.request.json')}
    timings = []
    for name in account_names:
        if stopped and not name.endswith('/started.json'):
            raise ValueError('Unexecuted model phase has unexpected accounting evidence')
        if name.endswith('.timing.json'):
            if name.removesuffix('.timing.json') not in requests:
                raise ValueError('Orphaned native model timing')
            timings.append(read_json(name)[0])
    if len(requests) != billing['requests']:
        raise ValueError('Physical request inventory disagrees with accounting')
    lifecycle = None if stopped else read_json(deadline)[0]
    if mode != 'cancel_setup':
        # Reuse the unchanged original semantics for genuinely successful and
        # setup-failed phases. The reader writes nothing and grants no scope.
        original_phase._phase_row(result, events, lifecycle, timings, len(requests), official)
    else:
        phase = {e['kind']: e for e in events}
        trial_event = phase['trial']
        if (phase['setup']['status'] != 'interrupted' or phase['cleanup']['status'] != 'ok'
                or trial_event['status'] != 'interrupted'
                or result.get('verifier_result') is not None or result.get('trace_errors')
                or any(not trial_event['started_ns'] <= e['started_ns'] <= e['ended_ns'] <= trial_event['ended_ns'] for e in events)
                or phase['setup']['ended_ns'] > phase['cleanup']['started_ns']):
            raise ValueError('Actual cancelled setup, revocation and sequential cleanup evidence required')
        for e in events: original_phase._number(e['metrics'].get('duration_seconds'))
        policy._same(result['phase_seconds']['setup'], phase['setup']['metrics']['duration_seconds'])
        expected_trace = dict(status='metadata_spool_not_cloud_export', events=3, generations=0,
            missing_generation_timings=0, unknown_cost_requests=0)
        policy._same(result['trace'], expected_trace)
        policy._same(trial_event['metrics'].get('requests'), 0)
    if mode == 'boundary_stop':
        marker = _json(root, rt + 'operator-stop-request.json')[0]
        if marker.get('automatic_resume') is not False:
            raise ValueError('Actual cooperative boundary stop record required')
    files.check(root, actual, identities)
    if stopped:
        for name in (deadline, cooldown):
            if (root / name).exists() or (root / name).is_symlink():
                raise ValueError('Unexecuted phase evidence appeared during qualification read')
    if _inventory(root, trial + 'traces') != trace_names or _inventory(root, rt + 'scored-attempts/' + trial_id) != account_names:
        raise ValueError('Native producer inventory changed during read')
    files.check(root, bound, read_ids)
    return bound


def verify(active):
    """Fresh runtime/images and real producers, never a saved-admission route."""
    live = session._live(active); root = live['root']
    try:
        session.recheck(active); no_failure(root)
        first_ids = {}
        records, private_files = inputs(root, first_ids)
        proof = records[policy.QUALIFICATION_FILE]
        final = live['inputs']['final']; predecessor = live['predecessor']['predecessor']
        policy._same(records[policy.ORIGINAL_FILE], final)
        policy._same(records[policy.PREDECESSOR_FILE], predecessor)
        policy._same(records[policy.RUNTIME_FILE], live['host'])
        policy.validate_qualification(final, predecessor, records[policy.MANIFEST_FILE], proof)
        policy._same(proof['sources'], live['inputs']['sources'])
        policy._same(proof['runtime_identity_sha256'], policy.fingerprint(live['host']))
        bound = dict(live['inputs']['files'], **private_files)
        bound.update(proof['evidence_files']); bound.update(proof['image_evidence_files'])
        identities = files.extend(root, bound, first_ids)
        actual_images = images.qualification_binding(active)
        policy._same(actual_images, {k: proof[k] for k in
            ('image_build_sha256', 'image_evidence_files', 'gateway_image', 'guard_image')})
        regression = _json(root, proof['regression_path'] + '/regression.json', identities)[0]
        policy._same(regression, proof['offline'])
        producer_files = dict(private_files, **proof['evidence_files'], **proof['image_evidence_files'])
        intent, intent_files = files.private(root, policy.QUALIFIER_INTENT_FILE, identities)
        expected = dict(kind='one_shot_actual_native_recovery_qualification',
            experiment=policy.EXPERIMENT, sources_sha256=proof['sources_sha256'],
            runtime_identity_sha256=proof['runtime_identity_sha256'],
            predecessor_authentication_sha256=policy.fingerprint(predecessor),
            regression_path=proof['regression_path'], automatic_resume=False, paid_launch_ready=False)
        for key, value in expected.items(): policy._same(intent.get(key), value)
        if type(intent.get('pid')) is not int or intent['pid'] <= 0 or not intent.get('started_utc'):
            raise ValueError('Actual native qualification operation required')
        producer_files.update(intent_files)
        for case in proof['synthetic']: producer_files.update(case_files(root, case, proof))
        completion, completion_files = files.private(root, policy.QUALIFIER_RESULT_FILE, identities)
        expected = dict(kind='actual_native_recovery_qualification_complete_not_dispatch',
            status='qualified', qualification_sha256=policy.fingerprint(proof),
            offline_tests=proof['offline']['tests'], native_cases=6, live_api_calls=0,
            producer_files=producer_files, automatic_resume=False, paid_launch_ready=False)
        if set(completion) != set(expected) | {'completed_utc'} or not completion['completed_utc']:
            raise ValueError('Exact actual completed recovery qualification required')
        for key, value in expected.items(): policy._same(completion[key], value)
        bound.update(producer_files); bound.update(completion_files)
        all_identities = files.extend(root, bound, identities)
        session.recheck(active); no_failure(root)
        files.check(root, bound, all_identities)
        block = policy.registration(final, predecessor, records[policy.MANIFEST_FILE], proof)
        return dict(root=root, proof=deepcopy(proof), block=block,
            files=bound, identities=all_identities, paid_launch_ready=False)
    except BaseException:
        session.invalidate(active)
        raise


def for_dispatch(active):
    """Require actual successful detached qualifier exit before paid admission."""
    import no_cutoff_recovery_service as service
    try:
        verified = verify(active)
        finished = service.completed_operation(active, 'qualify-recovery')
        for name, digest in finished['files'].items():
            if name in verified['files']: policy._same(verified['files'][name], digest)
            verified['files'][name] = digest
        for name, identity in finished['identities'].items():
            if name in verified['identities'] and verified['identities'][name] != identity:
                raise ValueError('Qualification service producer identity replaced')
            verified['identities'][name] = identity
        files.check(verified['root'], verified['files'], verified['identities'])
        return verified
    except BaseException:
        session.invalidate(active)
        raise
