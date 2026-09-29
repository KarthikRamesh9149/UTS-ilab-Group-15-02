"""Locked native prerequisite session, not a transport or paid dispatch scope.

The actual Mac sender and pinned SSH service integration must feed the live
archive pipe to this same process. Both collectors run BEFORE the outer locks;
only real file/library/runtime rechecks run UNDER them. No saved document or
caller-supplied authentication callback can open a session. Every operation
needs a new live handoff. OpenHands remains closed until its second predecessor
reader exists. Opening/rechecking prerequisites starts no study or rehearsal.
Qualification verification also runs the source-bound, network-less image
inspection container; it starts no benchmark task or model call.
"""
import asyncio
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import platform
import threading
import weakref

import matched_repeat_baseline as baseline
import matched_repeat_amended_handoff as handoff
import matched_repeat_original as original_audit
import matched_repeat_policy as policy
import matched_repeat_runtime as runtime
import matched_repeat_stream as wire
from matched_repeat_baseline_probe import check_files, regular

KIND = 'locked_matched_repeat_prerequisites_not_dispatch'
LIMITATIONS = dict(paid_launch_ready=False, historical_installed_bytes_attested=False,
    repeat_execution_qualified=False, transport='separate-pinned-authenticated-SSH-integration-required',
    off_server_archive='freshly-read-at-handoff-not-continuously-attested',
    registration_and_scored_dispatch='separate-required-integration', full_runtime_restore=False)
_SESSIONS = weakref.WeakKeyDictionary()
_GATE = threading.Lock()


class _Session:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Locked native sessions cannot be saved or copied')


def _task():
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


def _context(root, harness):
    handoff._first(harness)
    root = Path(root)
    if (platform.system() != 'Linux' or root != runtime.DEPLOYMENTS[harness]
            or not root.is_dir() or root.is_symlink() or root.resolve() != root
            or Path(__file__).resolve() != root / 'stage2/matched_repeat_session.py'):
        raise ValueError('Use this separate native repeat deployment for the locked session')
    return root


def _private(root, name):
    relative = '.runtime/stage2/' + name
    raw = regular(root, relative).read_bytes()
    return wire.loads(raw), {relative: hashlib.sha256(raw).hexdigest()}


def _inputs(root):
    original, old_file = _private(root, policy.BASELINE_FILE)
    final, final_file = _private(root, policy.FINAL_FILE)
    if (next(iter(old_file.values())) != baseline.ORIGINAL_FILE_SHA256
            or next(iter(final_file.values())) != baseline.FINAL_FILE_SHA256):
        raise ValueError('Exact private original and final qualification bytes required')
    policy.anchors(original, final)
    sources = runtime.sources(root, original, final)
    runtime.loaded_sources(root, sources)
    files = dict(old_file, **final_file)
    files.update({'stage2/' + name: sha for name, sha in sources.items()})
    check_files(root, files)
    return original, final, files


def _live(session):
    if not isinstance(session, _Session) or session not in _SESSIONS:
        raise ValueError('An active locked native session is required, not saved metadata')
    state = _SESSIONS[session]
    if (state['pid'] != os.getpid() or state['thread'] != threading.get_ident()
            or state['task'] is not _task()):
        raise ValueError('Locked sessions cannot cross processes, threads or async tasks')
    return state


def _coherent(state, predecessor, original, library, host):
    source_sha = policy.fingerprint(host['sources'])
    expected = dict(experiment=policy.EXPERIMENT, harness=state['harness'], paid_launch_ready=False)
    for record, kind in ((predecessor, handoff.KIND), (original, original_audit.KIND),
            (library, baseline.KIND), (host, runtime.KIND)):
        if (record.get('kind') != kind or any(policy.fingerprint(record.get(k)) != policy.fingerprint(v)
                for k, v in expected.items())):
            raise ValueError('All fresh prerequisite readers must identify this same repeat')
        if record.get('sources_sha256' if kind == runtime.KIND else 'current_sources_sha256') != source_sha:
            raise ValueError('Fresh prerequisite readers disagree on the repeat source')
    for record in (original, library, host):
        if (record.get('original_qualification_sha256') != policy.fingerprint(state['original'])
                or record.get('custom_final_qualification_sha256') != policy.fingerprint(state['final'])):
            raise ValueError('Fresh prerequisite readers disagree on the qualification anchors')
    if {'stage2/' + name: sha for name, sha in host['sources'].items()} != {
            name: sha for name, sha in state['files'].items() if name.startswith('stage2/')}:
        raise ValueError('Fresh host identity differs from the actual session inputs')


def describe(session):
    """Deep-copied metadata only; there is no inverse or saved-session route."""
    state = _live(session)
    return deepcopy(dict(kind=KIND, experiment=policy.EXPERIMENT, harness=state['harness'],
        inputs=state['files'], predecessor=state['predecessor'], original_audit=state['original_record'],
        baseline=state['library'], runtime=state['host'], limitations=LIMITATIONS,
        paid_launch_ready=False))


def recheck(session):
    """Actual under-lock rereads, without another collector/archive/lock call.

    A failed recheck permanently invalidates this session. Restoring a changed
    file cannot revive it; leave the context and perform a fresh handoff.
    """
    state = _live(session)
    try:
        root, harness = state['root'], state['harness']
        _context(root, harness); handoff._no_stop(root)
        original, final, files = _inputs(root)
        if files != state['files']:
            raise ValueError('Locked session source or input bytes changed')
        predecessor = handoff.recheck(root, original, final, harness, state['witness'])
        original_record = original_audit.recheck(root, original, final, harness, state['original_record'])
        library = baseline.recheck(root, original, final, harness, state['library'])
        host = runtime.inspect(root, original, final, harness)
        _coherent(state, predecessor, original_record, library, host)
        for name, value in (('predecessor', predecessor), ('original_record', original_record),
                ('library', library), ('host', host)):
            if policy.fingerprint(value) != policy.fingerprint(state[name]):
                raise ValueError('Current prerequisite observation changed within the locked session')
        # The potentially longer library/host reads cannot hide source, result
        # or supporting-inventory changes occurring after the first rechecks.
        handoff._no_stop(root)
        original_audit.recheck(root, original, final, harness, state['original_record'])
        handoff.recheck(root, original, final, harness, state['witness'])
        check_files(root, state['files'])
        return describe(session)
    except BaseException:
        _SESSIONS.pop(session, None)
        raise


@contextmanager
def open_session(root, harness, stream):
    """Fresh live handoff and original audit, then all inherited outer locks.

    No witness or record parameter is accepted. A future service must call this
    in the process that consumes the preparation/dispatch scope, not hand a
    serialised projection to a different process. The outer locks stay held
    through the caller's context and are released on every exception path.
    """
    if not _GATE.acquire(blocking=False):
        raise ValueError('Overlapping or nested native prerequisite sessions are refused')
    session = None
    try:
        root = _context(root, harness)
        handoff._no_stop(root); wire.pipe_only(stream)
        original, final, files = _inputs(root)
        witness = handoff.authenticate(root, original, final, harness, stream)
        original_record = original_audit.authenticate(root, original, final, harness)
        with ExitStack() as stack:
            original_audit.lock_all(stack, root, harness)
            handoff._no_stop(root); check_files(root, files)
            predecessor = handoff.recheck(root, original, final, harness, witness)
            original_record = original_audit.recheck(root, original, final, harness, original_record)
            library = baseline.inspect(root, original, final, harness)
            host = runtime.inspect(root, original, final, harness)
            state = dict(pid=os.getpid(), thread=threading.get_ident(), task=_task(), root=root,
                harness=harness, original=deepcopy(original), final=deepcopy(final), files=deepcopy(files),
                witness=witness, predecessor=deepcopy(predecessor), original_record=deepcopy(original_record),
                library=deepcopy(library), host=deepcopy(host))
            _coherent(state, predecessor, original_record, library, host)
            session = _Session(); _SESSIONS[session] = state
            try:
                recheck(session)
                yield session
            finally:
                # Invalidate before ExitStack releases any ancestor lock.
                _SESSIONS.pop(session, None)
    finally:
        if session is not None:
            _SESSIONS.pop(session, None)
        _GATE.release()


def _qualification_inputs(root):
    records, files = {}, {}
    for name in (policy.POLICY_FILE, policy.MANIFEST_FILE, policy.PREDECESSOR_FILE,
            policy.RUNTIME_FILE, policy.QUALIFICATION_FILE):
        records[name], bindings = _private(root, name)
        files.update(bindings)
    raw = regular(root, 'stage2/input_manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != policy.INPUT_SHA256:
        raise ValueError('Exact source-bound full89 manifest required')
    if (policy.fingerprint(records[policy.POLICY_FILE]) != policy.fingerprint(policy.POLICY)
            or policy.fingerprint(records[policy.MANIFEST_FILE]) != policy.fingerprint(wire.loads(raw))):
        raise ValueError('Exact repeat policy and unchanged private manifest required')
    return records, files


def verify_qualification(session):
    """Bind actual private qualification/producers to this live locked session.

    This does not run a qualifier, register a block or issue a paid permit. The
    actual native fixture and trusted producer workflow remain mandatory.
    Copied qualification flags cannot replace the freshly performed readers.
    """
    state = _live(session)
    try:
        recheck(session)
        root = state['root']
        from qualify_matched_repeat import verify_completion, no_failure
        no_failure(root)
        records, files = _qualification_inputs(root)
        proof = records[policy.QUALIFICATION_FILE]
        predecessors = state['predecessor']['predecessors']
        if (policy.fingerprint(records[policy.PREDECESSOR_FILE]) != policy.fingerprint(predecessors)
                or policy.fingerprint(records[policy.RUNTIME_FILE]) != policy.fingerprint(state['host'])
                or proof.get('harness') != state['harness']
                or proof.get('baseline_behaviour_authentication_sha256') != policy.fingerprint(state['library'])
                or proof.get('runtime_identity_sha256') != policy.fingerprint(state['host'])):
            raise ValueError('Qualification must bind actual live predecessor, library and host observations')
        runtime.verify_current(root, state['original'], state['final'], predecessors, proof, state['host'])
        # A saved image report is not installed-byte evidence. Reuse the real
        # source-bound builder's verifier inside this same live locked task,
        # without rebuilding, recursive audits, transfers or lock acquisition.
        from matched_repeat_images import qualification_binding
        images = qualification_binding(session)
        expected_images = {k: proof.get(k) for k in ('image_build_sha256', 'image_evidence_files',
            'gateway_image', 'guard_image')}
        if policy.fingerprint(images) != policy.fingerprint(expected_images):
            raise ValueError('Qualification must bind freshly verified actual image-build evidence')
        operation_files = verify_completion(session, proof)
        recheck(session)
        check_files(root, files); check_files(root, proof['evidence_files'])
        check_files(root, proof['image_evidence_files'])
        check_files(root, operation_files); no_failure(root)
        return dict(kind='live_bound_repeat_qualification_not_dispatch', harness=state['harness'],
            qualification_sha256=policy.fingerprint(proof), private_files=files,
            predecessor_authentication_sha256=policy.fingerprint(predecessors),
            original_audit_sha256=policy.fingerprint(state['original_record']),
            baseline_behaviour_authentication_sha256=policy.fingerprint(state['library']),
            runtime_identity_sha256=policy.fingerprint(state['host']),
            image_build_sha256=images['image_build_sha256'],
            qualification_operation_files=operation_files,
            image_evidence_files=images['image_evidence_files'], paid_launch_ready=False)
    except BaseException:
        _SESSIONS.pop(session, None)
        raise
