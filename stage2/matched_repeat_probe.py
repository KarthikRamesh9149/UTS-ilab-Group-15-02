"""Session-owned, fake-only native rehearsal; no CLI or production admission.

The trusted qualifier must call ``probe`` inside its own fresh live handoff
session. It awaits the shared scored lifecycle on that same main-thread task.
No qualification is invented and no production admission function is patched.
Native execution is separate evidence from this module's mocked local tests.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import signal
import stat
import threading
import uuid
import weakref

import matched_repeat_fixture as fixture
import matched_repeat_images as images
import matched_repeat_policy as policy
import matched_repeat_session as session
from matched_repeat_baseline_probe import check_files, regular
from matched_repeat_stream import loads
from matched_repeat_study import _shape
from completion_wait import completion_wait_for
from custom_dispatch_stop import BoundaryStop
from scored_gateway import durable_json, private_directory

TASK = 'lifecycle'
RESOURCE_TASK = 'adaptive-rejection-sampler'
ENTRYPOINT = ['python', '/study/stage2/matched_repeat_fixture.py']
KIND = 'actual_native_matched_baseline_synthetic_provider_not_benchmark_score'
SOURCE_FILES = ('fixtures/lifecycle/task.toml', 'fixtures/lifecycle/instruction.md',
    'fixtures/lifecycle/environment/Dockerfile', 'fixtures/lifecycle/tests/test.sh')
_PERMITS = weakref.WeakKeyDictionary()


class _Permit:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Rehearsal handles cannot be saved or copied')


def _environment():
    # The service has its own credential-free environment. Never inherit a
    # redirected daemon or a real provider credential into this fake route.
    names = ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH',
        'DOCKER_CONFIG', 'COMPOSE_FILE', 'OPENROUTER_API_KEY', 'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY', 'DEEPINFRA_API_TOKEN')
    if any(os.environ.get(name) for name in names):
        raise ValueError('Credential-free local Docker rehearsal environment required')


def _live(permit):
    if not isinstance(permit, _Permit) or permit not in _PERMITS:
        raise ValueError('Use the live synthetic rehearsal scope, not saved metadata')
    state = _PERMITS[permit]
    session._live(state['session'])
    if threading.current_thread() is not threading.main_thread() or session._task() is None:
        raise ValueError('Rehearsals stay on the native service main thread and async task')
    return state


def _read(root, name):
    path = regular(root, name)
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
        raise ValueError('Owned private single-link rehearsal evidence required')
    raw = path.read_bytes()
    return loads(raw), {name: hashlib.sha256(raw).hexdigest()}


def _unscored(root):
    rt = root / '.runtime/stage2'
    for name in (policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE,
            'matched-repeat-dispatch.json', 'matched-repeat-dispatch-result.json',
            'matched-repeat-dispatch-failure.json', 'matched-repeat-image-build-failure.json'):
        path = rt / name
        if path.exists() or path.is_symlink():
            raise ValueError('Rehearsal cannot reuse qualified, dispatched or failed evidence')
    for name in ('scored-trials', 'scored-attempts'):
        path = rt / name
        if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
            raise ValueError('No paid attempts may precede the isolated rehearsal')
    if any(rt.glob('matched-repeat-rehearsal-*-failure.json')):
        raise ValueError('A retained rehearsal failure requires inspection, not another operation')


def _prior(root, harness, mode, source_sha):
    """Retain earlier rehearsal bytes across modes; never resume an uncertainty."""
    files = {}
    for other in policy.PROBE_MODES:
        if other == mode:
            continue
        prefix = 'native-matched-repeat-' + harness + '-' + other + '-'
        directories = list((root / '.runtime/stage2').glob(prefix + '*'))
        relative = '.runtime/stage2/matched-repeat-rehearsal-' + other + '.json'
        path = root / relative
        if not path.exists() and not path.is_symlink():
            if directories:
                raise ValueError('Unowned earlier rehearsal directory requires inspection')
            continue
        intent, bound = _read(root, relative); files.update(bound)
        target = intent.get('runtime_path')
        if (not isinstance(target, str) or not target.startswith('.runtime/stage2/' + prefix)
                or '/' in target.removeprefix('.runtime/stage2/')
                or directories != [root / target]):
            raise ValueError('Exact retained earlier rehearsal identity required')
        evidence, bound = _read(root, target + '/evidence.json'); files.update(bound)
        if (intent.get('kind') != 'one_shot_synthetic_matched_repeat_rehearsal'
                or intent.get('mode') != other or intent.get('harness') != harness
                or intent.get('sources_sha256') != source_sha
                or intent.get('automatic_resume') is not False
                or evidence.get('kind') != KIND or evidence.get('mode') != other
                or evidence.get('harness') != harness or evidence.get('runtime_path') != target
                or evidence.get('status') != 'passed'
                or set(evidence.get('checks', {})) != policy.probe_checks(other)
                or any(v is not True for v in evidence['checks'].values())):
            raise ValueError('Incomplete or failed earlier rehearsal requires inspection')
        image_files = evidence.get('image_evidence_files')
        if (not isinstance(image_files, dict) or set(image_files) != policy.IMAGE_EVIDENCE_FILES
                or evidence.get('image_build_sha256') != intent.get('image_build_sha256')):
            raise ValueError('Earlier rehearsal image producers must still match')
        check_files(root, image_files); files.update(image_files)
        retained = evidence.get('producer_files')
        if not isinstance(retained, dict) or not retained or any(not name.startswith(target + '/') for name in retained):
            raise ValueError('Earlier rehearsal needs its actual retained producer bytes')
        check_files(root, retained); files.update(retained)
    return files


def _owned_clear():
    from scored_trial import docker
    for args in (('ps', '-aq'), ('network', 'ls', '-q'), ('volume', 'ls', '-q')):
        if docker(*args, '--filter', 'name=uts-scored-'):
            raise ValueError('Retained owned resources require inspection before rehearsal')


def _quick(state):
    session._live(state['session']); _environment(); _unscored(state['root'])
    session.handoff._no_stop(state['root'])
    check_files(state['root'], state['files'])
    check_files(state['fixture'], state['fixture_files'])
    for name, sha in state['fixture_files'].items():
        if hashlib.sha256(fixture._private_bytes(state['fixture'] / name)).hexdigest() != sha:
            raise ValueError('Private rehearsal inputs changed')
    record, raw_sha = fixture.read_fixture(state['runtime'], state['record']['trial_id'], 'final')
    if record != state['record'] or raw_sha != state['fixture_sha256']:
        raise ValueError('Synthetic rehearsal input bytes changed')
    if state.get('task') is not None and state.get('task_sha256') != _task_hash(state['task']):
        raise ValueError('Admitted synthetic task configuration changed')


def _task_hash(value):
    return policy.fingerprint(dict(config=value.config.model_dump(mode='json'),
        path=str(value.paths.environment_dir), instruction=value.instruction))


def _next(state):
    _quick(state)
    if state['stop'].requested():
        raise ValueError('Synthetic boundary stop forbids the next dispatch')
    if state['admitted']:
        raise ValueError('Synthetic attempts are single-use and cannot be replayed')


def _task(state):
    from harbor.models.task.task import Task
    value = Task(state['root'] / 'stage2/fixtures/lifecycle')
    row = state['host']['task_inventory'][RESOURCE_TASK]
    # Read only the already authenticated official resource metadata. The
    # instruction and verifier are our harmless source-bound fixture, never
    # a benchmark instruction, solution or verifier.
    value.config.environment.docker_image = row['image_id']
    value.config.environment.cpus = row['cpus']
    value.config.environment.memory_mb = row['memory_mb']
    value.config.environment.storage_mb = row['storage_mb']
    value.config.environment.gpus = row['gpus']
    value.config.environment.build_timeout_sec = row['build_timeout_seconds']
    value.config.agent.timeout_sec = row['agent_timeout_seconds']
    value.config.verifier.timeout_sec = row['verifier_timeout_seconds']
    return value


def _factory(permit):
    from recovery_agents import agent_factory
    state = _live(permit)
    native = agent_factory(state['harness'], state['fixture'])
    # The phase hooks below intentionally contain no Session or Permit. Phase
    # timeout machinery must not receive or move a live admission handle.
    observed, mode, marker, pid = state['observed'], state['mode'], state['stop'].marker, os.getpid()

    def create(**kwargs):
        current = _live(permit); _quick(current)
        task = current['task']
        if (not current['admitted'] or current['constructed'] or _shape(create) != current['shape']
                or Path(kwargs['paths'].trial_dir) != current['runtime'] / 'scored-trials' / current['record']['trial_id']
                or kwargs['agent_timeout_seconds'] != task.config.agent.timeout_sec
                or kwargs['completion_wait_seconds'] != completion_wait_for(task.config.agent.timeout_sec)
                or kwargs['container_api_base'] != 'http://127.0.0.1:8765/v1'):
            raise ValueError('One unchanged native construction for the admitted synthetic task required')
        current['constructed'] = True
        agent = native(**kwargs)
        # These are inherited baseline controls, not benchmark rules. Current
        # full constructor/library parity is independently read by the Session.
        from native_agents import NoRetryTerminus, CompatibleOpenHands
        expected = NoRetryTerminus if current['harness'] == 'terminus-2' else CompatibleOpenHands
        if type(agent) is not expected:
            raise ValueError('Original native baseline class required')
        if current['harness'] == 'terminus-2' and agent._max_episodes != 1000000:
            raise ValueError('Original Terminus turn guard changed')
        if current['harness'] == 'openhands' and agent._get_env('MAX_ITERATIONS') != '1000000':
            raise ValueError('Original OpenHands iteration guard changed')
        observed['baseline_controls_preserved'] = True
        if mode == 'cancel_setup':
            original_setup = agent.setup
            async def setup(environment):
                await original_setup(environment)
                observed['native_setup_finished'] = True
                # Cancel the actual owning task after real native setup and
                # before it can return and permit any model/agent execution.
                owner = asyncio.current_task()
                if owner.cancelling():
                    raise asyncio.CancelledError()
                token = object()
                observed['fixture_cancellation'] = True
                observed['cancel_owner'] = owner; observed['cancel_token'] = token
                owner.cancel(token)
                await asyncio.sleep(0)
            agent.setup = setup
        elif mode == 'boundary_stop':
            original_run = agent.run
            async def run(*args, **kwargs):
                # The handler belongs only to this same service process. It
                # finishes this attempt; it does not cancel the native agent.
                if os.getpid() != pid:
                    raise ValueError('Cannot signal a different rehearsal process')
                durable_json(marker, dict(source='synthetic-rehearsal', automatic_resume=False))
                os.kill(pid, signal.SIGUSR1)
                observed['fixture_signal_sent'] = True
                return await original_run(*args, **kwargs)
            agent.run = run
        return agent

    create.harness = state['harness']
    create.model_protocol_sha256 = policy.MODEL_SHA256
    state['factory'] = create; state['shape'] = _shape(create)
    return create


def admit_trial(permit, root, *, trial_id, task_id, stage, factory, settings,
                gateway_image, guard_image, setup_timeout_seconds):
    """Separate synthetic-only entry, never a paid qualification exception."""
    state = _live(permit)
    _next(state)
    binding = images.qualification_binding(state['session'])
    if binding != state['images']:
        raise ValueError('Actual installed rehearsal image evidence changed')
    if (Path(root) != state['fixture'] or (trial_id, task_id, stage) != (state['record']['trial_id'], TASK, 'final')
            or factory is not state['factory'] or _shape(factory) != state['shape']
            or settings != policy.SETTINGS or gateway_image != binding['gateway_image']
            or guard_image != binding['guard_image'] or type(setup_timeout_seconds) not in (int, float)
            or setup_timeout_seconds != 900):
        raise ValueError('Only the fixed synthetic identity, original factory and verified images are admitted')
    _quick(state)
    state['task'] = _task(state)
    state['task_sha256'] = _task_hash(state['task']); state['admitted'] = True
    return state['fixture_sha256']


def task(permit):
    state = _live(permit); _quick(state)
    if not state['admitted']:
        raise ValueError('Synthetic task is not admitted')
    return state['task']


def compose(permit, **kwargs):
    from production_compose import compose_runtime
    state = _live(permit); _quick(state)
    expected = dict(state_dir=state['runtime'], credential_file=state['fixture'] / '.env',
        token_file=state['runtime'] / 'scored-trials' / state['record']['trial_id'] / 'token',
        gateway_image=state['images']['gateway_image'], guard_image=state['images']['guard_image'],
        trial_id=state['record']['trial_id'], stage='final', uid=0, gid=0,
        completion_wait_seconds=completion_wait_for(state['task'].config.agent.timeout_sec))
    if not state['admitted'] or any(kwargs.get(k) != v for k, v in expected.items()):
        raise ValueError('Synthetic compose belongs to its admitted private runtime')
    kwargs['tokenizer_dir'] = state['root'] / '.cache/stage2-tokenizer'
    value = compose_runtime(**kwargs)
    gateway = value['services']['model-gateway']
    gateway['entrypoint'] = ENTRYPOINT[:]
    gateway['command'] = ['--gateway', '--trial', state['record']['trial_id'],
        '--completion-wait-seconds', str(kwargs['completion_wait_seconds'])]
    gateway.pop('networks')
    gateway['network_mode'] = 'none'
    value['networks'].pop('uts-gateway-egress')
    state['compose'] = deepcopy(value)
    return value


def audit_started(permit, observations):
    """Check actual Docker observations before constructing the native agent."""
    state = _live(permit); _quick(state)
    value = state.get('compose')
    if not state['admitted'] or value is None or set(observations) != set(value['services']):
        raise ValueError('All actual synthetic services must be inspected')
    guard_id = observations['task-network-guard']['Id']
    if observations['main']['Image'] != state['task'].config.environment.docker_image:
        raise ValueError('Started synthetic task image changed')
    volumes = {}
    for name, expected in value['services'].items():
        actual = observations[name]; host = actual['HostConfig']
        status = actual['State']
        if ((name != 'socket-init' and status.get('Running') is not True)
                or (name == 'socket-init' and (status.get('Running') is not False or status.get('ExitCode') != 0))):
            raise ValueError('Actual synthetic services are not in their required lifecycle state')
        namespace = 'container:' + guard_id if name in ('main', 'model-relay') else expected.get('network_mode')
        if namespace is not None and host['NetworkMode'] != namespace:
            raise ValueError('Synthetic service network isolation differs from its fixed compose')
        if name == 'main':
            continue  # Shared audit_task checks official resources and both allowed log mounts.
        if (actual['Image'] != expected['image'] or host.get('Privileged') or host.get('PortBindings')
                or host.get('ReadonlyRootfs') is not True
                or {c.removeprefix('CAP_') for c in host.get('CapDrop') or []} != {'ALL'}
                or {c.removeprefix('CAP_') for c in host.get('CapAdd') or []} != set(expected.get('cap_add', []))
                or not any(v in ('no-new-privileges', 'no-new-privileges:true') for v in host.get('SecurityOpt') or [])
                or host.get('NanoCpus') != int(expected['cpus'] * 1e9)
                or host.get('Memory') != int(expected['mem_limit'].removesuffix('m')) * 1024**2):
            raise ValueError('Actual synthetic service privileges, images or resources changed')
        if name in ('model-gateway', 'model-relay', 'socket-init') and (
                actual['Config']['Entrypoint'] != expected['entrypoint']
                or actual['Config']['Cmd'] != expected['command']):
            raise ValueError('Only the fixed synthetic gateway and relay commands are allowed')
        expected_mounts = expected.get('volumes', [])
        mounts = [m for m in actual['Mounts'] if m['Type'] != 'tmpfs']
        if len(mounts) != len(expected_mounts):
            raise ValueError('Unexpected synthetic service mount')
        for mount in mounts:
            matches = [m for m in expected_mounts if m['target'] == mount['Destination']]
            if len(matches) != 1:
                raise ValueError('Unexpected synthetic mount destination')
            wanted = matches[0]
            if mount['Type'] != wanted['type'] or mount['RW'] != (not wanted.get('read_only', False)):
                raise ValueError('Synthetic mount access changed')
            if mount['Type'] == 'bind' and mount['Source'] != wanted['source']:
                raise ValueError('Synthetic service mounted another host path')
            if mount['Type'] == 'volume':
                volumes.setdefault(wanted['source'], set()).add(mount['Name'])
    if set(volumes) != {'model-socket'} or any(len(v) != 1 for v in volumes.values()):
        raise ValueError('Synthetic socket volume identity differs across services')
    gateway = observations['model-gateway']
    if set(gateway.get('NetworkSettings', {}).get('Networks', {})) - {'none'}:
        raise ValueError('Synthetic gateway has an external network attachment')
    forbidden = {'OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPINFRA_API_TOKEN'}
    if any(v.partition('=')[0] in forbidden and v.partition('=')[2] for v in gateway['Config'].get('Env', [])):
        raise ValueError('Synthetic gateway inherited a provider credential')
    _quick(state)
    state['observed']['fixture_resources_audited'] = True


def _evidence(state, cancelled):
    runtime, record = state['runtime'], state['record']
    name = '.runtime/stage2/scored-trials/' + record['trial_id'] + '/result.json'
    result, result_files = _read(state['fixture'], name)
    started, start_files = _read(state['fixture'], name.replace('result.json', 'started.json'))
    expected = dict(trial_id=record['trial_id'], task_id=TASK, harness=state['harness'], stage='final',
        model_protocol_sha256=policy.MODEL_SHA256, matched_repeat_experiment=policy.EXPERIMENT,
        matched_repeat_fixture=fixture.FIXTURE_KIND, matched_repeat_fixture_sha256=state['fixture_sha256'],
        gateway_image_id=state['images']['gateway_image'], guard_image_id=state['images']['guard_image'])
    if any(value.get(k) != v for value in (result, started) for k, v in expected.items()):
        raise ValueError('Actual synthetic start/result identity does not match this rehearsal')
    if any('matched_repeat_registration_sha256' in v for v in (result, started)):
        raise ValueError('Synthetic results cannot claim a paid registration')
    attempts = runtime / 'scored-attempts' / record['trial_id']
    logical = [loads(regular(state['fixture'], str(p.relative_to(state['fixture']))).read_bytes())
        for p in sorted(attempts.glob('logical-*.json'))]
    is_cancel = state['mode'] == 'cancel_setup'
    expected_logical = 0 if is_cancel else fixture.EXPECTED_LOGICAL[state['harness']]
    expected_requests = 0 if is_cancel else expected_logical + 1
    billing = result.get('billing', {})
    reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
    from credit_only_accounting import summarise
    from local_trace import validate
    trace_dir = runtime / 'scored-trials' / record['trial_id'] / 'traces'
    traces = [validate(_read(state['fixture'], str(p.relative_to(state['fixture'])))[0])
        for p in sorted(trace_dir.glob('*.json'))]
    phases = ['setup', 'cleanup', 'trial'] if is_cancel else ['setup', 'agent', 'verifier', 'cleanup', 'trial']
    trace_ok = (sorted(t['kind'] for t in traces) == sorted(phases + ['generation'] * expected_requests)
        and all(t['trial_id'] == record['trial_id'] and t['task_id'] == TASK
            and t['harness'] == state['harness'] and t['protocol_sha256'] == policy.MODEL_SHA256 for t in traces))
    accepted = len(logical) == expected_logical and all(v.get('accepted_for_agent') is True for v in logical)
    checks = dict(expected_status=result.get('status') == ('interrupted' if is_cancel else 'verified'),
        expected_verifier_result=reward is None if is_cancel else type(reward) in (int, float) and reward == 1,
        model_revoked=result.get('model_revoked') is True,
        all_physical_requests_accounted=billing == summarise(runtime, record['trial_id'])
            and billing.get('requests') == expected_requests and accepted,
        unknown_costs_retained=billing.get('unknown_cost_requests') == expected_requests
            and (billing.get('charged_usd') == '0' if is_cancel else billing.get('charged_usd') is None),
        no_receipt_or_credit_block=billing.get('provider_stop') is None,
        traces_recorded=trace_ok and result.get('trace', {}).get('generations') == expected_requests
            and result.get('trace', {}).get('missing_generation_timings') == 0,
        containers_removed=result.get('containers_removed') is True,
        networks_removed=result.get('networks_removed') is True, volumes_removed=result.get('volumes_removed') is True,
        # probe rechecks these observations before this function, and again
        # after reading evidence. Flags do not replace those actual operations.
        sources_unchanged=True, host_unchanged=True, images_unchanged=True,
        fixture_resources_audited=state['observed'].get('fixture_resources_audited') is True,
        repeat_gateway_identity=True, final_stage_accounting=result.get('accounting_mode') == 'provider-credit-only')
    if is_cancel:
        checks['cancelled_setup_evidence'] = (cancelled and state['observed'].get('native_setup_finished') is True
            and 'setup' in result.get('phase_seconds', {}) and 'agent' not in result.get('phase_seconds', {})
            and 'verifier' not in result.get('phase_seconds', {}) and not logical)
    else:
        checks.update(actual_native_harness_tool_roundtrip=accepted and reward == 1,
            recovered_one_transient=len(list(attempts.glob('*.retry.json'))) == 1,
            baseline_controls_preserved=state['observed'].get('baseline_controls_preserved') is True)
    if state['mode'] == 'boundary_stop':
        checks['cooperative_stop_persisted'] = state['stop'].signalled and state['stop'].requested()
        no_next = False
        try:
            _next(state)
        except ValueError as exc:
            no_next = str(exc) == 'Synthetic boundary stop forbids the next dispatch'
        checks['no_next_dispatch'] = no_next and len(list((runtime / 'scored-trials').iterdir())) == 1
    if set(checks) != policy.probe_checks(state['mode']):
        raise ValueError('Exact native rehearsal check inventory required')
    check_files(state['fixture'], dict(result_files, **start_files))
    producer_files = {}
    paths = [state['fixture'] / name for name in (*state['fixture_files'], *result_files, *start_files)]
    paths += list(trace_dir.glob('*.json')) + list(attempts.glob('*.json'))
    for path in paths:
        # Bind raw private request/response bytes without returning their text.
        relative = str(path.relative_to(state['root']))
        file = regular(state['root'], relative)
        info = file.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Single-link native producer files required')
        producer_files[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
    check_files(state['root'], producer_files)
    return dict(kind=KIND, status='passed' if all(checks.values()) else 'failed', harness=state['harness'],
        mode=state['mode'], live_api_calls=0, paid_launch_ready=False, repeat_execution_qualified=False,
        checks=checks, host_environment=state['host']['host_environment'],
        model_protocol_sha256=policy.MODEL_SHA256, runtime_path=str(state['fixture'].relative_to(state['root'])),
        image_build_sha256=state['images']['image_build_sha256'],
        image_evidence_files=deepcopy(state['images']['image_evidence_files']), producer_files=producer_files)


async def probe(active, mode):
    """One actual synthetic lifecycle, awaited by its owning native service.

    No caller root, factory, task, image, transport or saved receipt is accepted.
    Retained intent, fixture directory or failure prevents automatic replay.
    This function does not build images or create the final qualification.
    """
    state = session._live(active)
    if threading.current_thread() is not threading.main_thread() or session._task() is None:
        raise ValueError('Use the native service main thread and owning async task')
    policy.probe_checks(mode); _environment()
    session.recheck(active)
    root, harness = state['root'], state['harness']
    _unscored(root)
    if any(s['root'] == root for s in _PERMITS.values()):
        raise ValueError('Overlapping or nested synthetic rehearsals are refused')
    runtime = root / '.runtime/stage2'
    intent_path = runtime / ('matched-repeat-rehearsal-' + mode + '.json')
    prefix = 'native-matched-repeat-' + harness + '-' + mode + '-'
    if intent_path.exists() or intent_path.is_symlink() or any(runtime.glob(prefix + '*')):
        raise ValueError('Retained rehearsal intent or attempt forbids automatic replay')
    prior = _prior(root, harness, mode, state['host']['sources_sha256'])
    _owned_clear()
    binding = images.qualification_binding(active)
    for name in SOURCE_FILES:
        if name not in state['host']['sources']:
            raise ValueError('All harmless rehearsal files must be source-bound')
    tokenizer = root / '.cache/stage2-tokenizer'
    if tokenizer.is_symlink() or not tokenizer.is_dir() or tokenizer.resolve() != tokenizer:
        raise ValueError('Existing regular qualified tokenizer directory required')
    record = fixture.fixture_document(harness, mode)
    target = runtime / (prefix + uuid.uuid4().hex)
    intent = dict(kind='one_shot_synthetic_matched_repeat_rehearsal', harness=harness, mode=mode,
        runtime_path=str(target.relative_to(root)), sources_sha256=state['host']['sources_sha256'],
        image_build_sha256=binding['image_build_sha256'], automatic_resume=False, paid_launch_ready=False,
        pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat())
    durable_json(intent_path, intent)
    permit = None
    try:
        target.mkdir(mode=0o700)
        private_directory(target / 'stage2')
        durable_json(target / 'stage2/input_manifest.json', dict(all_task_ids=[TASK], development_ids=[TASK]))
        rt = private_directory(target / '.runtime/stage2')
        durable_json(rt / fixture.FIXTURE_FILE, record)
        with os.fdopen(os.open(target / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(('OPENROUTER_API_KEY=' + fixture.SYNTHETIC_KEY + '\n').encode())
            stream.flush(); os.fsync(stream.fileno())
        inputs = ('stage2/input_manifest.json', '.env', '.runtime/stage2/' + fixture.FIXTURE_FILE)
        fixture_files = {name: hashlib.sha256(regular(target, name).read_bytes()).hexdigest() for name in inputs}
        _, intent_files = _read(root, str(intent_path.relative_to(root)))
        files = {}
        for bindings in (state['files'], binding['image_evidence_files'], intent_files, prior):
            for name, digest in bindings.items():
                if name in files and files[name] != digest:
                    raise ValueError('Rehearsal file bindings disagree')
                files[name] = digest
        permit = _Permit()
        current = dict(session=active, root=root, harness=harness, fixture=target, runtime=rt, record=record,
            mode=mode, fixture_sha256=fixture_files['.runtime/stage2/' + fixture.FIXTURE_FILE],
            fixture_files=fixture_files, files=files, images=binding, host=deepcopy(state['host']),
            admitted=False, constructed=False, observed={})
        _PERMITS[permit] = current
        from scored_trial import run_trial
        with BoundaryStop(rt) as stop:
            current['stop'] = stop
            factory = _factory(permit)
            cancelled = False
            try:
                await run_trial(root=target, trial_id=record['trial_id'], task_id=TASK, stage='final',
                    agent_factory=factory, model_settings=policy.SETTINGS,
                    gateway_image=binding['gateway_image'], guard_image=binding['guard_image'],
                    setup_timeout_seconds=900, accounting_mode='provider-credit-only',
                    matched_repeat_fixture=permit)
            except asyncio.CancelledError as exc:
                # Python 3.12 wait_for retains the owning task. Consume ONLY
                # this fixture's exact cancellation request, after the shared
                # lifecycle has retained its actual revocation/cleanup result.
                # Any additional operator/service cancellation propagates.
                observed = current['observed']; owner = asyncio.current_task()
                if (mode != 'cancel_setup' or not observed.get('fixture_cancellation')
                        or observed.get('cancel_owner') is not owner or owner.cancelling() != 1
                        or len(exc.args) != 1 or exc.args[0] is not observed.get('cancel_token')):
                    raise
                owner.uncancel()
                cancelled = True
            _quick(current); session.recheck(active); _owned_clear()
            if images.qualification_binding(active) != binding:
                raise ValueError('Image evidence changed during the actual rehearsal')
            evidence = _evidence(current, cancelled)
            _quick(current); session.recheck(active)
            check_files(root, evidence['producer_files']); _owned_clear()
            durable_json(target / 'evidence.json', evidence)
            if evidence['status'] != 'passed':
                raise ValueError('Actual synthetic lifecycle failed; retained without replay')
            return evidence
    except BaseException as exc:
        failure_path = runtime / ('matched-repeat-rehearsal-' + mode + '-failure.json')
        if not failure_path.exists() and not failure_path.is_symlink():
            durable_json(failure_path, dict(kind='retained_synthetic_rehearsal_failure', error_type=type(exc).__name__,
                runtime_path=str(target.relative_to(root)), automatic_resume=False, paid_launch_ready=False))
        session.invalidate(active)
        raise
    finally:
        if permit is not None:
            _PERMITS.pop(permit, None)
