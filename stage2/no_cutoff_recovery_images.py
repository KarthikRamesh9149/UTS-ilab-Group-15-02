"""One-shot, session-bound gateway build; not qualification or paid admission.

Only the future trusted native service may call build inside its fresh live
session. No root/receipt/parent/callback can be supplied instead. The original
qualified gateway supplies all base layers; the guard image is never rebuilt.
No old deployment or image tag is replaced and no image is automatically removed.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import threading

import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_session as session
from no_cutoff_recovery_files import check as check_files, private, read, save
from no_cutoff_recovery_bootstrap import directories

INTENT = policy.IMAGE_INTENT_FILE
RESULT = policy.IMAGE_RESULT_FILE
FAILURE = 'no-cutoff-recovery-image-build-failure.json'
CONFIG = 'no-cutoff-recovery-image-docker-config'
DOCKERFILE = 'fixtures/Dockerfile.no-cutoff-recovery'
ENTRYPOINT = ['python', '/study/stage2/no_cutoff_recovery_gateway.py']
# Complete local static import closure, including lazy legacy helper imports.
# Those inherited helpers are not invoked as financial gates by RetrySession.
IMAGE_FILES = ('budget_ledger.py', 'calibrate_tokenizer.py', 'collect_deferred_receipts.py',
    'completion_wait.py', 'credit_only_gateway.py', 'credit_only_policy.py', 'custom_control.py',
    'deferred_billing.py', 'deadline_custom_contract.py', 'extended_token_calibration.py', 'gateway_core.py', 'gateway_http.py',
    'gateway_policy.py', 'historical_hold.py', 'no_cutoff_recovery_gateway.py', 'no_cutoff_recovery_policy.py',
    'no_cutoff_recovery_plan.py', 'matched_repeat_schedule.py', 'no_cutoff_custom_contract.py',
    'model_protocol.py', 'openrouter_transport.py', 'portable_custom_policy.py', 'rate_limit_candidate.py',
    'receipt_accounting.py', 'receipt_polling.py', 'rerun_budget.py', 'retry_gateway.py', 'retry_policy.py',
    'retry_runtime.py', 'retry_transport.py', 'scored_gateway.py', 'setup_probe.py', 'study_budget.py',
    'trial_estimator.py', 'no_cutoff_recovery_fixture.py')
# The parent is the original C0-NC final gateway. No inherited helper is changed.
COPY_FILES = ('no_cutoff_recovery_gateway.py', 'no_cutoff_recovery_policy.py',
    'no_cutoff_recovery_plan.py', 'matched_repeat_schedule.py', 'no_cutoff_recovery_fixture.py')


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _image(value):
    if not isinstance(value, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', value):
        raise ValueError('Exact qualified image ID required')
    return value


def _dockerfile():
    # No RUN, download, broad COPY, secret, package change or task-container edit.
    return ('ARG PARENT\nFROM ${PARENT}\nCOPY ' + ' '.join(COPY_FILES)
        + ' /study/stage2/\nENTRYPOINT ' + json.dumps(ENTRYPOINT) + '\n').encode()


def _context(root, sources):
    names = (*COPY_FILES, DOCKERFILE)
    bindings = {'stage2/' + name: sources[name] for name in names}
    check_files(root, bindings)
    contents = {name: read(root, 'stage2/' + name)[0] for name in names}
    if contents[DOCKERFILE] != _dockerfile():
        raise ValueError('Only the fixed allowlisted gateway Dockerfile is supported')
    if any(hashlib.sha256(raw).hexdigest() != sources[name] for name, raw in contents.items()):
        raise ValueError('Build context changed while reading source bytes')
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(contents.items()):
            member = tarfile.TarInfo('Dockerfile' if name == DOCKERFILE else name)
            member.size = len(raw); member.mode = 0o644; member.mtime = 0
            archive.addfile(member, io.BytesIO(raw))
    check_files(root, bindings)
    return buffer.getvalue()


def _config(root, *, create=False):
    path = root / '.runtime/stage2' / CONFIG
    if path.is_symlink() or path.resolve() != path:
        raise ValueError('Regular empty private Docker configuration required')
    if create:
        path.mkdir(mode=0o700)  # Exclusive; no user registry credentials copied.
    if not path.is_dir():
        raise ValueError('Existing empty Docker configuration required')
    directories(path, private=True)
    if any(path.iterdir()):
        raise ValueError('Docker configuration must remain empty and credential-free')
    return path


def _command(root, *args, data=None):
    config = _config(root)
    # Pin the local daemon, ignore client environment/configuration, and avoid
    # buildx/plugin/frontend downloads. Native legacy-builder support must be
    # exercised during the real qualification, not inferred from local tests.
    result = subprocess.run(['/usr/bin/docker', '--config', str(config),
        '--host=unix:///var/run/docker.sock', *args], input=data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'DOCKER_BUILDKIT': '0'})
    _config(root)
    if result.returncode:
        # Neither raw daemon diagnostics nor inherited environment is published.
        raise RuntimeError('Pinned local Docker command failed')
    return result.stdout.decode('utf-8')


def _inspect(root, reference):
    values = json.loads(_command(root, 'image', 'inspect', reference),
        object_pairs_hook=session.handoff.wire._pairs, parse_constant=session.handoff.wire._constant)
    if not isinstance(values, list) or len(values) != 1:
        raise ValueError('One exact local image inspection required')
    value = values[0]
    if (not isinstance(value, dict) or value.get('Id') != _image(reference)
            or value.get('Os') != 'linux' or value.get('Architecture') != 'amd64'
            or not isinstance(value.get('Config'), dict)
            or value.get('RootFS', {}).get('Type') != 'layers'
            or not value['RootFS'].get('Layers')):
        raise ValueError('Pinned native Linux image identity is unavailable')
    for layer in value['RootFS']['Layers']:
        _image(layer)
    return {key: value[key] for key in ('Id', 'Os', 'Architecture', 'RootFS', 'Config')}


def _parent_tag(root, parent, harness):
    tag = 'uts-no-cutoff-recovery-parent-' + harness + ':sha256-' + parent.removeprefix('sha256:')
    found = _command(root, 'image', 'ls', '--quiet', '--no-trunc', tag).split()
    if found and found != [parent]:
        raise ValueError('Preserve an existing mismatched repeat parent tag')
    if not found:
        _command(root, 'image', 'tag', parent, tag)
    actual = json.loads(_command(root, 'image', 'inspect', tag),
        object_pairs_hook=session.handoff.wire._pairs, parse_constant=session.handoff.wire._constant)
    if not isinstance(actual, list) or len(actual) != 1 or actual[0].get('Id') != parent:
        raise ValueError('Repeat parent tag does not resolve to the qualified original image')
    return tag


def _probe_script(sources, base='/study/stage2'):
    # This code runs in an isolated, read-only, network-less gateway container.
    # The audit hook is defence in depth, not an OS sandbox. No gateway session,
    # baseline factory, tool, container, model call or provider probe is created.
    expected = {name: sources[name] for name in IMAGE_FILES}
    return '''import hashlib,json,os,pathlib,sys
base = pathlib.Path(BASE)
expected = EXPECTED
if base.resolve() != base or any(p.is_symlink() for p in (base, *base.parents)):
    raise ValueError('Regular installed gateway directory required')
if not sys.flags.isolated or not sys.dont_write_bytecode or not sys.pycache_prefix:
    raise ValueError('Isolated uncached gateway interpreter required')
if pathlib.Path(sys.pycache_prefix).exists():
    raise ValueError('Absent gateway bytecode prefix required')
def read_files():
    answer = {}
    for name in expected:
        path = base / name
        if path.is_symlink() or not path.is_file() or path.resolve() != path:
            raise ValueError('Regular installed gateway source required')
        answer[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if answer != expected:
        raise ValueError('Installed gateway bytes differ from the frozen context')
    return answer
violation = False
environment = dict(os.environ)
def refuse():
    global violation
    violation = True
    raise RuntimeError('Gateway import inspection refuses external effects')
def guard(event, args):
    if (event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn'))
            or event in {'os.system','os.fork','os.forkpty','os.remove','os.rename',
                'os.rmdir','os.mkdir','os.link','os.symlink','os.truncate','os.chmod','os.chown','os.utime'}):
        refuse()
    if event in {'os.putenv', 'os.unsetenv'}: refuse()
    if event == 'open':
        path, mode, flags = args
        name = pathlib.Path(os.fsdecode(path)).name if isinstance(path,(str,bytes,os.PathLike)) else ''
        if ((isinstance(mode,str) and any(c in mode for c in 'wax+'))
                or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)
                or name == '.env' or name.startswith('.env.') or name in {'.jwt_secret','id_ed25519','id_rsa'}):
            refuse()
read_files()
sys.addaudithook(guard)
sys.path.insert(0, str(base))
import no_cutoff_recovery_gateway
import no_cutoff_recovery_fixture
if violation or dict(os.environ) != environment:
    raise ValueError('Caught import effects or environment changes cannot qualify an image')
loaded = {}
for name, module in list(sys.modules.items()):
    path = getattr(module, '__file__', None)
    if name.split('.')[0] in {'harbor','litellm','deepagents','langgraph','langchain',
            'langchain_core','langchain_openai','openhands'}:
        raise ValueError('Gateway unexpectedly imported the native harness stack')
    if path and pathlib.Path(path).parent == base and name + '.py' not in expected:
        raise ValueError('Gateway imported an unbound project module')
    if name + '.py' in expected:
        if path is None or pathlib.Path(path) != base / (name + '.py'):
            raise ValueError('Gateway module loaded from another source tree')
        loaded[name] = expected[name + '.py']
if not {'no_cutoff_recovery_gateway', 'no_cutoff_recovery_fixture', 'retry_gateway'}.issubset(loaded):
    raise ValueError('Actual lightweight gateway import required')
print(json.dumps(dict(installed=read_files(), loaded=loaded, import_only=True, live_api_calls=0)))
'''.replace('BASE', repr(base), 1).replace('EXPECTED', repr(expected), 1)


def _observations(root, sources, parent, guard, image):
    old = _inspect(root, parent); firewall = _inspect(root, guard); new = _inspect(root, image)
    if (new['RootFS']['Layers'][:len(old['RootFS']['Layers'])] != old['RootFS']['Layers']
            or len(new['RootFS']['Layers']) != len(old['RootFS']['Layers']) + 1
            or new['Config'] != dict(old['Config'], Entrypoint=ENTRYPOINT)):
        raise ValueError('Gateway changed the qualified original base or configuration')
    name = 'uts-no-cutoff-recovery-image-probe-' + image.removeprefix('sha256:')
    retained = ('container', 'ls', '--all', '--quiet', '--filter', 'name=^/' + name + '$')
    if _command(root, *retained).strip():
        raise ValueError('Retained image inspection container requires investigation')
    report = session.handoff.wire.loads(_command(root, 'run', '--rm', '--name', name, '--network=none', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--entrypoint', 'python', image,
        '-I', '-B', '-X', 'pycache_prefix=/uts-no-cutoff-recovery-absent-bytecode',
        '-c', _probe_script(sources)))
    expected = {name: sources[name] for name in IMAGE_FILES}
    if (not isinstance(report, dict) or set(report) != {'installed', 'loaded', 'import_only', 'live_api_calls'}
            or report['installed'] != expected or report['import_only'] is not True
            or type(report['live_api_calls']) is not int or report['live_api_calls'] != 0
            or not isinstance(report['loaded'], dict)
            or not {'no_cutoff_recovery_gateway', 'no_cutoff_recovery_fixture', 'retry_gateway'}.issubset(report['loaded'])
            or any(name + '.py' not in expected or sha != expected[name + '.py']
                for name, sha in report['loaded'].items())):
        raise ValueError('Actual installed source and lean import observation required')
    if _command(root, *retained).strip():
        raise ValueError('Owned image inspection container was not removed')
    if (_inspect(root, parent) != old or _inspect(root, guard) != firewall or _inspect(root, image) != new):
        raise ValueError('Pinned image identity changed during inspection')
    return dict(parent_metadata_sha256=policy.fingerprint(old), guard_metadata_sha256=policy.fingerprint(firewall),
        gateway_metadata_sha256=policy.fingerprint(new), installed_sources=expected,
        lean_import_sha256=policy.fingerprint(report))


def _inputs(active):
    session.recheck(active)
    state = session._live(active)
    if session.handoff._task() is None or threading.current_thread() is not threading.main_thread():
        raise ValueError('Use the native service main thread and same async task for image preparation')
    sources = state['host']['sources']
    raw = _context(state['root'], sources)
    final = state['inputs']['final']
    return state, raw, dict(experiment=policy.EXPERIMENT, condition=policy.CONDITION,
        sources_sha256=policy.fingerprint(sources), context_sha256=hashlib.sha256(raw).hexdigest(),
        original_qualification_sha256=policy.fingerprint(final), plan_sha256=policy.PLAN_SHA256,
        predecessor_authentication_sha256=policy.fingerprint(state['predecessor']['predecessor']),
        runtime_identity_sha256=policy.fingerprint(state['host']),
        parent_gateway_image=_image(final['gateway_image']),
        guard_image=_image(final['guard_image']))



def _unstarted(root):
    rt = root / '.runtime/stage2'
    for name in (INTENT, RESULT, FAILURE, CONFIG, policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE,
            'no-cutoff-recovery-dispatch.json', 'no-cutoff-recovery-dispatch-result.json', 'no-cutoff-recovery-dispatch-failure.json'):
        path = rt / name
        if path.exists() or path.is_symlink():
            raise ValueError('Retained image/qualification/dispatch evidence forbids an automatic rebuild')
    for name in ('scored-trials', 'scored-attempts'):
        path = rt / name
        if path.is_symlink() or path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError('Cannot prepare images over earlier attempts')


def build(active):
    """Build once, with actual prerequisites under held ancestor locks.

    The trusted service/qualifier must call this directly within open_session;
    it cannot transfer a prepared handle to a subprocess or another async task.
    Failure retains private evidence and forbids automatic rebuild/retry.
    """
    state, context, inputs = _inputs(active)
    root = state['root']; rt = root / '.runtime/stage2'
    _unstarted(root)
    intent = dict(kind='single_no_cutoff_recovery_image_build_intent', inputs=inputs,
        started_utc=_utc(), pid=os.getpid(), automatic_rebuild=False, paid_launch_ready=False)
    save(rt / INTENT, intent)
    identities = {}
    _, intent_files = private(root, INTENT, identities); check_files(root, intent_files, identities)
    image = None
    try:
        _config(root, create=True)
        old = _inspect(root, inputs['parent_gateway_image']); _inspect(root, inputs['guard_image'])
        if old['Config'].get('OnBuild') or old['Config'].get('Volumes'):
            raise ValueError('Qualified gateway must not contain build triggers or implicit volumes')
        tag = _parent_tag(root, inputs['parent_gateway_image'], policy.CONDITION.lower())
        image = _image(_command(root, 'build', '--quiet', '--pull=false', '--network=none',
            '--build-arg', 'PARENT=' + tag, '-', data=context).strip())
        observation = _observations(root, state['host']['sources'], inputs['parent_gateway_image'],
            inputs['guard_image'], image)
        _, current_context, current_inputs = _inputs(active)
        if current_context != context or current_inputs != inputs:
            raise ValueError('Image preparation inputs changed during the build')
        check_files(root, intent_files, identities)
        result = dict(kind='pinned_no_cutoff_recovery_gateway_image_not_qualification', inputs=inputs,
            intent_file_sha256=next(iter(intent_files.values())), gateway_image=image,
            observations=observation, completed_utc=_utc(), live_api_calls=0,
            paid_launch_ready=False, recovery_execution_qualified=False,
            historical_installed_bytes_attested=False, automatic_rebuild=False)
        save(rt / RESULT, result)
        return result
    except BaseException as exc:
        session.invalidate(active)
        save(rt / FAILURE, dict(kind='retained_no_cutoff_recovery_image_build_failure',
            exception_type=type(exc).__name__ if type(exc) in (ValueError, RuntimeError, OSError,
                TimeoutError, KeyboardInterrupt, SystemExit) else 'OtherException',
            failed_utc=_utc(), automatic_rebuild=False,
            paid_launch_ready=False, observed_gateway_image=image,
            intent_file_sha256=next(iter(intent_files.values()))))
        raise


def verify(active):
    """Reread existing build evidence and inspect actual images, never rebuild.

    This requires a new real live session for a later operation. It is intended
    for qualification/admission rechecks and is not itself registration/admission.
    """
    try:
        state, _, inputs = _inputs(active)
        root = state['root']; rt = root / '.runtime/stage2'
        if (rt / FAILURE).exists() or (rt / FAILURE).is_symlink():
            raise ValueError('Retained image build failure requires inspection')
        identities = {}
        intent, intent_files = private(root, INTENT, identities)
        result, result_files = private(root, RESULT, identities)
        check_files(root, dict(intent_files, **result_files), identities)
        if (intent.get('kind') != 'single_no_cutoff_recovery_image_build_intent'
                or intent.get('inputs') != inputs or intent.get('automatic_rebuild') is not False
                or intent.get('paid_launch_ready') is not False
                or result.get('kind') != 'pinned_no_cutoff_recovery_gateway_image_not_qualification'
                or result.get('inputs') != inputs
                or result.get('intent_file_sha256') != next(iter(intent_files.values()))
                or type(result.get('live_api_calls')) is not int or result['live_api_calls'] != 0
                or any(result.get(k) is not False for k in ('paid_launch_ready', 'recovery_execution_qualified',
                    'historical_installed_bytes_attested', 'automatic_rebuild'))):
            raise ValueError('Existing build evidence differs from the fresh session')
        actual = _observations(root, state['host']['sources'], inputs['parent_gateway_image'],
            inputs['guard_image'], _image(result.get('gateway_image')))
        if actual != result.get('observations') or _inputs(active)[2] != inputs:
            raise ValueError('Actual image or prerequisite identity differs from the build')
        check_files(root, dict(intent_files, **result_files), identities)
        return result
    except BaseException:
        if isinstance(active, session._Session):
            session.invalidate(active)
        raise


def qualification_binding(active):
    """Reverify real installed images and bind the retained build producer bytes.

    A future qualifier must call this after the actual build and rehearsals;
    admission calls it again in its own fresh same-task locked session. No
    caller-selected image, proof, saved record or build shortcut is accepted.
    This produces only a non-admitting binding, never a qualification.
    """
    try:
        root = session._live(active)['root']
        identities = {}
        _, before_intent = private(root, INTENT, identities)
        _, before_result = private(root, RESULT, identities)
        before = dict(before_intent, **before_result)
        check_files(root, before, identities)
        observed = verify(active)
        intent, intent_files = private(root, INTENT, identities)
        result, result_files = private(root, RESULT, identities)
        files = dict(intent_files, **result_files)
        if (files != before or policy.fingerprint(result) != policy.fingerprint(observed)
                or result['intent_file_sha256'] != next(iter(intent_files.values()))
                or intent['inputs'] != result['inputs']):
            raise ValueError('Image producer bytes changed after actual image verification')
        session.recheck(active)
        check_files(root, files, identities)
        return dict(image_build_sha256=policy.fingerprint(result), image_evidence_files=files,
            gateway_image=result['gateway_image'], guard_image=result['inputs']['guard_image'])
    except BaseException:
        if isinstance(active, session._Session):
            session.invalidate(active)
        raise
