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
import shlex
import signal
import stat
import threading
import uuid
import weakref

import no_cutoff_recovery_fixture as fixture
import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_session as session
import no_cutoff_recovery_files as evidence
import no_cutoff_recovery_qualification as qualification
from no_cutoff_recovery_result import RetainedPreparation
check_files = evidence.check
from matched_repeat_stream import loads
from no_cutoff_recovery_study import _shape
from completion_wait import completion_wait_for
from custom_dispatch_stop import BoundaryStop
from no_cutoff_recovery_files import save as durable_json
from scored_gateway import private_directory

TASK = 'lifecycle'
RESOURCE_TASK = 'pytorch-model-recovery'
ENTRYPOINT = ['python', '/study/stage2/no_cutoff_recovery_fixture.py']
KIND = 'actual_native_recovery_synthetic_provider_not_benchmark_score'
SOURCE_FILES = ('fixtures/lifecycle/task.toml', 'fixtures/lifecycle/instruction.md',
    'fixtures/lifecycle/environment/Dockerfile', 'fixtures/lifecycle/tests/test.sh')
_PERMITS = weakref.WeakKeyDictionary()

# These fault-injection inputs affect only each freshly created synthetic
# container. The paid task environment and its original preparation are never
# changed. No package is downloaded, installed or repaired by this fixture.
CONTROL = '/tmp/uts-recovery-qualification'


class _ControlledEnvironment:
    def __init__(self, environment, mode, observed):
        self.environment, self.mode, self.observed = environment, mode, observed

    def with_default_user(self, user):
        return self.environment.with_default_user(user)

    async def exec(self, command, *, timeout_sec):
        from task_preparation import COMMAND as ORIGINAL_COMMAND
        if command != ORIGINAL_COMMAND or timeout_sec != 180:
            raise ValueError('The actual original preparation command and window are required')
        self.observed['original_preparation_command'] = True
        path = CONTROL + '/bin' + ('' if self.mode == 'prepare_not_applicable' else ':/usr/bin:/bin')
        if self.mode != 'cancel_setup':
            result = await self.environment.exec(command, timeout_sec=timeout_sec, env={'PATH': path})
            if self.mode == 'prepare_exception':
                # Explicit integration fault injection AFTER real container
                # execution, not an invented historical/native transport cause.
                if result.return_code != 0: raise ValueError('The native exception fixture precondition failed')
                raise RuntimeError('Source-bound synthetic preparation exception')
            return result
        operation = asyncio.create_task(self.environment.exec(command, timeout_sec=timeout_sec, env={'PATH': path}))
        try:
            # Observe the owned command's real marker before cancelling this
            # setup task. This fixture wait is not a benchmark time allowance.
            async with asyncio.timeout(60):
                while True:
                    if operation.done(): raise ValueError('Cancellation fixture command ended before observation')
                    marker = await self.environment.exec('test -f ' + CONTROL + '/started', timeout_sec=5)
                    if marker.return_code == 0: break
                    await asyncio.sleep(.1)
            owner = asyncio.current_task()
            if owner.cancelling(): raise asyncio.CancelledError()
            token = object()
            self.observed.update(fixture_cancellation=True, cancel_owner=owner, cancel_token=token)
            owner.cancel(token)
            return await operation
        finally:
            if not operation.done(): operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)


class _Preparation(RetainedPreparation):
    def __init__(self, mode, observed):
        super().__init__(); self.mode, self.observed = mode, observed

    async def prepare(self, environment):
        self._owner()
        if self._used: raise ValueError('Synthetic preparation cannot be repeated')
        script = '#!/bin/sh\n'
        if self.mode == 'cancel_setup': script += 'touch ' + CONTROL + '/started\nexec /bin/sleep 300\n'
        elif self.mode == 'prepare_nonzero': script += "printf 'SYNTHETIC_NONZERO\\n' >&2\nexit 42\n"
        else: script += "printf 'SYNTHETIC_REFRESHED\\n'\nexit 0\n"
        # A new private directory is exclusive, so even fixture preconditions
        # cannot silently repeat. PATH, not a system binary, selects the stub.
        command = ('test -f /etc/debian_version && umask 077 && mkdir ' + CONTROL
            + ' && mkdir ' + CONTROL + '/bin && ln -s /bin/bash ' + CONTROL + '/bin/bash')
        if self.mode != 'prepare_not_applicable':
            command += ' && printf %s ' + shlex.quote(script) + ' > ' + CONTROL + '/bin/apt-get && chmod 700 ' + CONTROL + '/bin/apt-get'
        with environment.with_default_user('root'):
            created = await environment.exec(command, timeout_sec=60)
        if created.return_code != 0:
            raise ValueError('Synthetic native preparation precondition failed')
        return await super().prepare(_ControlledEnvironment(environment, self.mode, self.observed))


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
    if threading.current_thread() is not threading.main_thread() or session.handoff._task() is None:
        raise ValueError('Rehearsals stay on the native service main thread and async task')
    return state


def _read(root, name):
    raw, captured = evidence.read(root, name)
    return loads(raw), {name: captured['sha256']}


def _unscored(root):
    rt = root / '.runtime/stage2'
    for name in (policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE,
            'no-cutoff-recovery-dispatch.json', 'no-cutoff-recovery-dispatch-result.json',
            'no-cutoff-recovery-dispatch-failure.json', 'no-cutoff-recovery-image-build-failure.json'):
        path = rt / name
        if path.exists() or path.is_symlink():
            raise ValueError('Rehearsal cannot reuse qualified, dispatched or failed evidence')
    for name in ('scored-trials', 'scored-attempts'):
        path = rt / name
        if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
            raise ValueError('No paid attempts may precede the isolated rehearsal')
    if any(rt.glob('no-cutoff-recovery-rehearsal-*-failure.json')):
        raise ValueError('A retained rehearsal failure requires inspection, not another operation')


def _prior(root, mode, state, binding):
    retained = {}
    for other in policy.PROBE_MODES:
        if other == mode: continue
        path = root / '.runtime/stage2' / ('no-cutoff-recovery-rehearsal-' + other + '.json')
        prefix = 'native-no-cutoff-recovery-' + other + '-'
        directories = list((root / '.runtime/stage2').glob(prefix + '*'))
        if not path.exists() and not path.is_symlink():
            if directories: raise ValueError('Unowned native rehearsal directory requires inspection')
            continue
        intent, _ = _read(root, str(path.relative_to(root)))
        relative = intent.get('runtime_path')
        if type(relative) is not str or directories != [root / relative]:
            raise ValueError('Exact earlier rehearsal identity required')
        case, _ = _read(root, relative + '/evidence.json')
        proof = dict(binding, sources=state['host']['sources'], sources_sha256=state['host']['sources_sha256'])
        retained.update(qualification.case_files(root, case, proof))
    return retained


def _owned_clear():
    from scored_trial import docker
    for args in (('ps', '-aq'), ('network', 'ls', '-q'), ('volume', 'ls', '-q')):
        if docker(*args, '--filter', 'name=uts-scored-'):
            raise ValueError('Retained owned resources require inspection before rehearsal')


def _quick(state):
    session._live(state['session']); _environment(); _unscored(state['root'])
    session.handoff._no_stop(state['root'])
    check_files(state['root'], state['files'], state['identities'])
    check_files(state['fixture'], state['fixture_files'], state['fixture_identities'])
    for name, sha in state['fixture_files'].items():
        if name != '.runtime/stage2/python-runtime.tar.gz' and hashlib.sha256(fixture.private_bytes(state['fixture'] / name)).hexdigest() != sha:
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
    from no_cutoff_custom_agent import agent_factory
    state = _live(permit)
    native = agent_factory(state['fixture'], 'C0')
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
        from no_cutoff_custom_agent import NoCutoffCustomHarborAgent
        if (type(agent) is not NoCutoffCustomHarborAgent or agent.condition.name != 'C0'
                or agent.condition.parent is not None or agent.version() != policy.CANDIDATE_VERSION):
            raise ValueError('Original qualified C0-NC class and controls required')
        observed['original_C0_NC_controls'] = True
        if mode == 'boundary_stop':
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

    create.harness = policy.CONDITION
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
    state['preparation'] = _Preparation(state['mode'], state['observed'])
    durable_json(state['fixture'] / 'admission.json', dict(kind='actual_native_recovery_fixture_admission',
        resource_task_id=RESOURCE_TASK, official=state['host']['task_inventory'][RESOURCE_TASK],
        task_id=TASK, trial_id=trial_id, setup_timeout_seconds=900,
        instruction_sha256=hashlib.sha256(state['task'].instruction.encode()).hexdigest(),
        sources_sha256=state['host']['sources_sha256'], paid_launch_ready=False))
    state['fixture_files'].update(evidence.capture(state['fixture'], ['admission.json'])[0])
    evidence.extend(state['fixture'], state['fixture_files'], state['fixture_identities'])
    return state['fixture_sha256']


def task(permit):
    state = _live(permit); _quick(state)
    if not state['admitted']:
        raise ValueError('Synthetic task is not admitted')
    return state['task']


def preparation(permit, root, trial_id):
    state = _live(permit); _quick(state)
    if Path(root) != state['fixture'] or trial_id != state['record']['trial_id'] or not state['admitted']:
        raise ValueError('Only this admitted synthetic trial owns its preparation')
    return state['preparation']


def require_task_image(permit, root, task_id, actual_image):
    state = _live(permit); _quick(state)
    if (Path(root) != state['fixture'] or task_id != TASK
            or actual_image != state['task'].config.environment.docker_image):
        raise ValueError('Actual synthetic task image changed')


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
    kwargs['credential_file'] = state['runtime'] / 'synthetic-provider.txt'
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
    root = state['root']; relative = state['fixture'].relative_to(root).as_posix()
    mode = state['mode']; trial_id = state['record']['trial_id']
    trial = relative + '/.runtime/stage2/scored-trials/' + trial_id
    result, _ = _read(root, trial + '/result.json')
    from no_cutoff_recovery_result import validate
    observation = validate(result.get('recovery_preparation'))
    if not observation['observation_complete']:
        raise ValueError('Actual native preparation observation is incomplete')
    if (not state['observed'].get('fixture_resources_audited') or not state['observed'].get('original_C0_NC_controls')
            or not state['observed'].get('original_preparation_command')):
        raise ValueError('Actual native resource and original constructor observations required')
    if mode == 'cancel_setup' and not cancelled:
        raise ValueError('The actual setup cancellation was not observed')
    if mode == 'boundary_stop':
        if not state['observed'].get('fixture_signal_sent') or not state['stop'].requested():
            raise ValueError('Actual cooperative boundary signal must be retained')
        try: _next(state)
        except ValueError as exc:
            if str(exc) != 'Synthetic boundary stop forbids the next dispatch': raise
        else: raise ValueError('The next synthetic dispatch was not refused')
    case = dict(kind=KIND, mode=mode, condition=policy.CONDITION, status='passed',
        live_api_calls=0, preparation_outcome=policy.PREPARATION_OUTCOMES[mode],
        checks=dict.fromkeys(sorted(policy.probe_checks(mode)), True),
        runtime_path=relative, preparation_observation_sha256=policy.fingerprint(observation))
    trace_names = qualification._inventory(root, trial + '/traces')
    account_names = qualification._inventory(root, relative + '/.runtime/stage2/scored-attempts/' + trial_id)
    support = {relative + '/' + name for name in state['fixture_files']}
    support |= {trial + '/' + n for n in ('started.json', 'result.json', 'compose.json')}
    support |= {*trace_names, *account_names}
    support.add(relative + '/.runtime/stage2/model-protocol.json')
    if mode not in fixture.NO_MODEL:
        support |= {relative + '/.runtime/stage2/retry-lifecycle/' + trial_id + '.json',
            relative + '/.runtime/stage2/provider-cooldown.json'}
    if mode == 'boundary_stop': support.add(relative + '/.runtime/stage2/operator-stop-request.json')
    bindings, identities = evidence.capture(root, support)
    durable_json(state['fixture'] / 'producer.json', dict(kind='actual_native_recovery_supporting_producers',
        mode=mode, runtime_path=relative, source_sha256=state['host']['sources_sha256'],
        image_build_sha256=state['images']['image_build_sha256'], files=bindings, paid_launch_ready=False))
    proof = dict(state['images'], sources=state['host']['sources'], sources_sha256=state['host']['sources_sha256'])
    qualification.case_files(root, case, proof, pending=True)
    evidence.check(root, bindings, identities)
    return case, dict(bindings, **_read(root, relative + '/producer.json')[1])


async def probe(active, mode):
    """One actual synthetic lifecycle, awaited by its owning native service.

    No caller root, factory, task, image, transport or saved receipt is accepted.
    Retained intent, fixture directory or failure prevents automatic replay.
    This function does not build images or create the final qualification.
    """
    state = session._live(active)
    if threading.current_thread() is not threading.main_thread() or session.handoff._task() is None:
        raise ValueError('Use the native service main thread and owning async task')
    policy.probe_checks(mode); _environment()
    session.recheck(active)
    root, harness = state['root'], policy.CONDITION
    _unscored(root)
    if any(s['root'] == root for s in _PERMITS.values()):
        raise ValueError('Overlapping or nested synthetic rehearsals are refused')
    runtime = root / '.runtime/stage2'
    intent_path = runtime / ('no-cutoff-recovery-rehearsal-' + mode + '.json')
    prefix = 'native-no-cutoff-recovery-' + mode + '-'
    if intent_path.exists() or intent_path.is_symlink() or any(runtime.glob(prefix + '*')):
        raise ValueError('Retained rehearsal intent or attempt forbids automatic replay')
    _owned_clear()
    binding = images.qualification_binding(active)
    prior = _prior(root, mode, state, binding)
    for name in SOURCE_FILES:
        if name not in state['host']['sources']:
            raise ValueError('All harmless rehearsal files must be source-bound')
    tokenizer = root / '.cache/stage2-tokenizer'
    if tokenizer.is_symlink() or not tokenizer.is_dir() or tokenizer.resolve() != tokenizer:
        raise ValueError('Existing regular qualified tokenizer directory required')
    record = fixture.document(mode)
    target = runtime / (prefix + uuid.uuid4().hex)
    intent = dict(kind='one_shot_native_recovery_rehearsal', experiment=policy.EXPERIMENT, mode=mode,
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
        credential = rt / 'synthetic-provider.txt'
        raw = ('OPENROUTER_API_KEY=' + fixture.SYNTHETIC_KEY + '\n').encode()
        with os.fdopen(os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        from portable_custom_agent import runtime_bundle
        bundle = runtime_bundle(root); bundle.validate()
        evidence.libraries.read(root, '.runtime/stage2/python-runtime.tar.gz', policy.PYTHON_SHA256)
        destination = rt / 'python-runtime.tar.gz'
        with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
            with bundle.path.open('rb') as source:
                while chunk := source.read(1024 * 1024): output.write(chunk)
            output.flush(); os.fsync(output.fileno())
        evidence.libraries.read(root, '.runtime/stage2/python-runtime.tar.gz', policy.PYTHON_SHA256)
        evidence.libraries.read(target, '.runtime/stage2/python-runtime.tar.gz', policy.PYTHON_SHA256)
        inputs = ('stage2/input_manifest.json', '.runtime/stage2/synthetic-provider.txt',
            '.runtime/stage2/python-runtime.tar.gz', '.runtime/stage2/' + fixture.FIXTURE_FILE)
        fixture_files = evidence.capture(target, inputs)[0]
        _, intent_files = _read(root, str(intent_path.relative_to(root)))
        files = {}
        for bindings in (state['inputs']['files'], binding['image_evidence_files'], intent_files, prior):
            for name, digest in bindings.items():
                if name in files and files[name] != digest:
                    raise ValueError('Rehearsal file bindings disagree')
                files[name] = digest
        permit = _Permit()
        current = dict(session=active, root=root, harness=harness, fixture=target, runtime=rt, record=record,
            mode=mode, fixture_sha256=fixture_files['.runtime/stage2/' + fixture.FIXTURE_FILE],
            fixture_files=fixture_files, files=files, images=binding, host=deepcopy(state['host']),
            identities=evidence.capture(root, files)[1], fixture_identities=evidence.capture(target, fixture_files)[1],
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
                    recovery_fixture=permit)
            except asyncio.CancelledError as exc:
                # Python 3.12 wait_for retains the owning task. Consume ONLY
                # this fixture's exact cancellation request, after the shared
                # lifecycle has retained its actual revocation/cleanup result.
                # Any additional operator/service cancellation propagates.
                observed = current['observed']; owner = asyncio.current_task()
                origin = observed.get('cancel_owner')
                if (mode != 'cancel_setup' or not observed.get('fixture_cancellation')
                        or len(exc.args) != 1 or exc.args[0] is not observed.get('cancel_token')
                        or origin is None or origin.cancelling() != 1
                        or (origin is not owner and (owner.cancelling() or not origin.done()))):
                    raise
                if origin is owner: owner.uncancel()
                cancelled = True
            _quick(current); session.recheck(active); _owned_clear()
            if images.qualification_binding(active) != binding:
                raise ValueError('Image evidence changed during the actual rehearsal')
            case, producer_files = _evidence(current, cancelled)
            producer_identities = evidence.capture(root, producer_files)[1]
            _owned_clear(); _quick(current); session.recheck(active)
            check_files(root, producer_files, producer_identities)
            durable_json(target / 'evidence.json', case)
            if case['status'] != 'passed':
                raise ValueError('Actual synthetic lifecycle failed; retained without replay')
            return case
    except BaseException as exc:
        failure_path = runtime / ('no-cutoff-recovery-rehearsal-' + mode + '-failure.json')
        if not failure_path.exists() and not failure_path.is_symlink():
            name = type(exc).__name__
            if name not in {'ValueError', 'RuntimeError', 'OSError', 'FileExistsError',
                    'FileNotFoundError', 'PermissionError', 'TimeoutError', 'CancelledError',
                    'KeyboardInterrupt', 'SystemExit'}: name = 'OtherException'
            durable_json(failure_path, dict(kind='retained_synthetic_rehearsal_failure', error_type=name,
                runtime_path=str(target.relative_to(root)), automatic_resume=False, paid_launch_ready=False))
        session.invalidate(active)
        raise
    finally:
        if permit is not None:
            _PERMITS.pop(permit, None)
