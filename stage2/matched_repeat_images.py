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

import matched_repeat_policy as policy
import matched_repeat_session as session
from matched_repeat_baseline_probe import check_files, regular
from scored_gateway import durable_json, private_directory

INTENT = 'matched-repeat-image-build.json'
RESULT = 'matched-repeat-images.json'
FAILURE = 'matched-repeat-image-build-failure.json'
CONFIG = 'matched-repeat-image-docker-config'
DOCKERFILE = 'fixtures/Dockerfile.matched-repeat'
ENTRYPOINT = ['python', '/study/stage2/matched_repeat_gateway.py']
# Complete local static import closure, including lazy legacy helper imports.
# Those inherited helpers are not invoked as financial gates by RetrySession.
IMAGE_FILES = ('budget_ledger.py', 'calibrate_tokenizer.py', 'collect_deferred_receipts.py',
    'completion_wait.py', 'credit_only_gateway.py', 'credit_only_policy.py', 'custom_control.py',
    'deferred_billing.py', 'extended_token_calibration.py', 'gateway_core.py', 'gateway_http.py',
    'gateway_policy.py', 'historical_hold.py', 'matched_repeat_gateway.py', 'matched_repeat_policy.py',
    'matched_repeat_schedule.py', 'model_protocol.py', 'openrouter_transport.py',
    'portable_custom_policy.py', 'rate_limit_candidate.py', 'receipt_accounting.py',
    'receipt_polling.py', 'rerun_budget.py', 'retry_gateway.py', 'retry_policy.py',
    'retry_runtime.py', 'retry_transport.py', 'scored_gateway.py', 'setup_probe.py',
    'study_budget.py', 'trial_estimator.py')
# Overlay only the new lightweight contracts and the two already-disclosed
# shared gateway deltas. All other import helpers remain in the original base
# and must match the newly inventoried/current bytes during actual inspection.
COPY_FILES = ('credit_only_gateway.py', 'retry_gateway.py', 'custom_control.py',
    'portable_custom_policy.py', 'matched_repeat_schedule.py', 'matched_repeat_policy.py',
    'matched_repeat_gateway.py')


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
    contents = {name: regular(root, 'stage2/' + name).read_bytes() for name in names}
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
    private_directory(path)
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
        object_pairs_hook=session.wire._pairs, parse_constant=session.wire._constant)
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
    tag = 'uts-matched-repeat-parent-' + harness + ':sha256-' + parent.removeprefix('sha256:')
    found = _command(root, 'image', 'ls', '--quiet', '--no-trunc', tag).split()
    if found and found != [parent]:
        raise ValueError('Preserve an existing mismatched repeat parent tag')
    if not found:
        _command(root, 'image', 'tag', parent, tag)
    actual = json.loads(_command(root, 'image', 'inspect', tag),
        object_pairs_hook=session.wire._pairs, parse_constant=session.wire._constant)
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
def guard(event, args):
    if (event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn'))
            or event in {'os.system','os.fork','os.forkpty','os.remove','os.rename',
                'os.rmdir','os.mkdir','os.link','os.symlink','os.truncate','os.chmod','os.chown','os.utime'}):
        raise RuntimeError('Gateway import inspection forbids external effects')
    if event == 'open':
        _, mode, flags = args
        if ((isinstance(mode,str) and any(c in mode for c in 'wax+'))
                or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise RuntimeError('Gateway import inspection forbids writes')
read_files()
sys.addaudithook(guard)
sys.path.insert(0, str(base))
import matched_repeat_gateway
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
if 'matched_repeat_gateway' not in loaded or 'retry_gateway' not in loaded:
    raise ValueError('Actual lightweight gateway import required')
print(json.dumps(dict(installed=read_files(), loaded=loaded, import_only=True, live_api_calls=0)))
'''.replace('BASE', repr(base), 1).replace('EXPECTED', repr(expected), 1)


def _observations(root, sources, parent, guard, image):
    old = _inspect(root, parent); firewall = _inspect(root, guard); new = _inspect(root, image)
    if (new['RootFS']['Layers'][:len(old['RootFS']['Layers'])] != old['RootFS']['Layers']
            or len(new['RootFS']['Layers']) != len(old['RootFS']['Layers']) + 1
            or new['Config'] != dict(old['Config'], Entrypoint=ENTRYPOINT)):
        raise ValueError('Gateway changed the qualified original base or configuration')
    name = 'uts-matched-repeat-image-probe-' + image.removeprefix('sha256:')
    retained = ('container', 'ls', '--all', '--quiet', '--filter', 'name=^/' + name + '$')
    if _command(root, *retained).strip():
        raise ValueError('Retained image inspection container requires investigation')
    report = session.wire.loads(_command(root, 'run', '--rm', '--name', name, '--network=none', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--entrypoint', 'python', image,
        '-I', '-B', '-X', 'pycache_prefix=/uts-matched-repeat-absent-bytecode',
        '-c', _probe_script(sources)))
    expected = {name: sources[name] for name in IMAGE_FILES}
    if (not isinstance(report, dict) or set(report) != {'installed', 'loaded', 'import_only', 'live_api_calls'}
            or report['installed'] != expected or report['import_only'] is not True
            or type(report['live_api_calls']) is not int or report['live_api_calls'] != 0
            or not isinstance(report['loaded'], dict)
            or not {'matched_repeat_gateway', 'retry_gateway'}.issubset(report['loaded'])
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
    if session._task() is None or threading.current_thread() is not threading.main_thread():
        raise ValueError('Use the native service main thread and same async task for image preparation')
    sources = state['host']['sources']
    raw = _context(state['root'], sources)
    return state, raw, dict(experiment=policy.EXPERIMENT, harness=state['harness'],
        sources_sha256=policy.fingerprint(sources), context_sha256=hashlib.sha256(raw).hexdigest(),
        original_qualification_sha256=policy.fingerprint(state['original']),
        custom_final_qualification_sha256=policy.fingerprint(state['final']),
        predecessor_authentication_sha256=policy.fingerprint(state['predecessor']['predecessors']),
        baseline_behaviour_authentication_sha256=policy.fingerprint(state['library']),
        runtime_identity_sha256=policy.fingerprint(state['host']),
        parent_gateway_image=_image(state['original']['gateway_image']),
        guard_image=_image(state['original']['guard_image']))


def _unstarted(root):
    rt = root / '.runtime/stage2'
    for name in (INTENT, RESULT, FAILURE, CONFIG, policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE,
            'matched-repeat-dispatch.json', 'matched-repeat-dispatch-result.json', 'matched-repeat-dispatch-failure.json'):
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
    intent = dict(kind='single_matched_repeat_image_build_intent', inputs=inputs,
        started_utc=_utc(), pid=os.getpid(), automatic_rebuild=False, paid_launch_ready=False)
    durable_json(rt / INTENT, intent)
    _, intent_files = session._private(root, INTENT); check_files(root, intent_files)
    image = None
    try:
        _config(root, create=True)
        old = _inspect(root, inputs['parent_gateway_image']); _inspect(root, inputs['guard_image'])
        if old['Config'].get('OnBuild') or old['Config'].get('Volumes'):
            raise ValueError('Qualified gateway must not contain build triggers or implicit volumes')
        tag = _parent_tag(root, inputs['parent_gateway_image'], state['harness'])
        image = _image(_command(root, 'build', '--quiet', '--pull=false', '--network=none',
            '--build-arg', 'PARENT=' + tag, '-', data=context).strip())
        observation = _observations(root, state['host']['sources'], inputs['parent_gateway_image'],
            inputs['guard_image'], image)
        _, current_context, current_inputs = _inputs(active)
        if current_context != context or current_inputs != inputs:
            raise ValueError('Image preparation inputs changed during the build')
        check_files(root, intent_files)
        result = dict(kind='pinned_matched_repeat_gateway_image_not_qualification', inputs=inputs,
            intent_file_sha256=next(iter(intent_files.values())), gateway_image=image,
            observations=observation, completed_utc=_utc(), live_api_calls=0,
            paid_launch_ready=False, repeat_execution_qualified=False,
            historical_installed_bytes_attested=False, automatic_rebuild=False)
        durable_json(rt / RESULT, result)
        return result
    except BaseException as exc:
        session._SESSIONS.pop(active, None)
        durable_json(rt / FAILURE, dict(kind='retained_matched_repeat_image_build_failure',
            exception_type=type(exc).__name__, failed_utc=_utc(), automatic_rebuild=False,
            paid_launch_ready=False, observed_gateway_image=image,
            intent_file_sha256=next(iter(intent_files.values()))))
        raise


def verify(active):
    """Reread existing build evidence and inspect actual images, never rebuild.

    This requires a new real live session for a later operation. It is intended
    for future qualifier integration and is not itself registration/admission.
    """
    try:
        state, _, inputs = _inputs(active)
        root = state['root']; rt = root / '.runtime/stage2'
        if (rt / FAILURE).exists() or (rt / FAILURE).is_symlink():
            raise ValueError('Retained image build failure requires inspection')
        intent, intent_files = session._private(root, INTENT)
        result, result_files = session._private(root, RESULT)
        check_files(root, dict(intent_files, **result_files))
        if (intent.get('kind') != 'single_matched_repeat_image_build_intent'
                or intent.get('inputs') != inputs or intent.get('automatic_rebuild') is not False
                or intent.get('paid_launch_ready') is not False
                or result.get('kind') != 'pinned_matched_repeat_gateway_image_not_qualification'
                or result.get('inputs') != inputs
                or result.get('intent_file_sha256') != next(iter(intent_files.values()))
                or type(result.get('live_api_calls')) is not int or result['live_api_calls'] != 0
                or any(result.get(k) is not False for k in ('paid_launch_ready', 'repeat_execution_qualified',
                    'historical_installed_bytes_attested', 'automatic_rebuild'))):
            raise ValueError('Existing build evidence differs from the fresh session')
        actual = _observations(root, state['host']['sources'], inputs['parent_gateway_image'],
            inputs['guard_image'], _image(result.get('gateway_image')))
        if actual != result.get('observations') or _inputs(active)[2] != inputs:
            raise ValueError('Actual image or prerequisite identity differs from the build')
        check_files(root, dict(intent_files, **result_files))
        return result
    except BaseException:
        session._SESSIONS.pop(active, None)
        raise
