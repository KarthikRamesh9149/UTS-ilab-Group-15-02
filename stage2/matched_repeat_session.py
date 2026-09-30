"""Locked native prerequisite session, not a transport or paid dispatch scope.

The actual Mac sender and pinned SSH service integration must feed the live
archive pipe to this same process. Both collectors run BEFORE the outer locks;
only real file/library/runtime rechecks run UNDER them. No saved document or
caller-supplied authentication callback can open a session. Every operation
needs a new live handoff. OpenHands additionally consumes its actual completed
Terminus witness. Opening/rechecking prerequisites starts no study or rehearsal.
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
import sys
import threading
import weakref

import matched_repeat_baseline as baseline
import matched_repeat_amended_handoff as handoff
import matched_repeat_original as original_audit
import matched_repeat_policy as policy
import matched_repeat_runtime as runtime
import matched_repeat_locks as locks
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
    policy._harness(harness)
    root = Path(root)
    if (platform.system() != 'Linux' or root != runtime.DEPLOYMENTS[harness]
            or not root.is_dir() or root.is_symlink() or root.resolve() != root
            or Path(__file__).absolute() != root / 'stage2/matched_repeat_session.py'
            or Path(sys.executable).absolute() != root / '.venv/bin/python'
            or threading.current_thread() is not threading.main_thread()):
        raise ValueError('Use this separate native repeat deployment for the locked session')
    locks.directories(root, private=True)
    locks.directories(root / '.runtime/stage2', private=True)
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


def _invalidate_witness(witness):
    # The archived handoff module is immutable. Its current owning session
    # revokes the real in-memory entry without changing that old reader.
    if type(witness) is handoff._Witness:
        handoff._WITNESSES.pop(witness, None)
    else:
        import matched_repeat_openhands_handoff as successor
        successor.invalidate(witness)


def invalidate(session):
    """Revoke every live handle now; the owning context keeps locks until exit."""
    if type(session) is _Session:
        state = _SESSIONS.pop(session, None)
        if state is not None:
            _invalidate_witness(state['witness'])
            if state.get('recovery_witness') is not None:
                import matched_repeat_recovery_handoff as recovery
                recovery.invalidate(state['recovery_witness'])
            if state.get('terminus_witness') is not None:
                import matched_repeat_terminus_handoff as terminus
                terminus.invalidate(state['terminus_witness'])


def _live(session):
    if not isinstance(session, _Session) or session not in _SESSIONS:
        raise ValueError('An active locked native session is required, not saved metadata')
    state = _SESSIONS[session]
    try:
        if (state['pid'] != os.getpid() or state['thread'] != threading.get_ident()
                or state['task'] is None or state['task'] is not _task()
                or threading.current_thread() is not threading.main_thread()):
            raise ValueError('Locked sessions cannot cross processes, threads or async tasks')
        state.get('handoff', handoff)._live(state['witness'])
        if state.get('recovery_witness') is not None:
            import matched_repeat_recovery_handoff as recovery
            recovery._live(state['recovery_witness'])
        if state.get('terminus_witness') is not None:
            import matched_repeat_terminus_handoff as terminus
            terminus._live(state['terminus_witness'])
        state['locks'].recheck()
        return state
    except BaseException:
        invalidate(session)
        raise


def _coherent(state, predecessor, original, library, host):
    source_sha = policy.fingerprint(host['sources'])
    expected = dict(experiment=policy.EXPERIMENT, harness=state['harness'], paid_launch_ready=False)
    for record, kind in ((predecessor, state.get('handoff', handoff).KIND), (original, original_audit.KIND),
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
    result = dict(kind=KIND, experiment=policy.EXPERIMENT, harness=state['harness'],
        inputs=state['files'], predecessor=state['predecessor'], original_audit=state['original_record'],
        baseline=state['library'], runtime=state['host'], limitations=LIMITATIONS,
        paid_launch_ready=False)
    if state.get('recovery_witness') is not None:
        result['completed_recovery'] = state['recovery_record']
    if state.get('terminus_witness') is not None:
        result['completed_terminus'] = state['terminus_record']
    return deepcopy(result)


def operator_commit(active):
    state = _live(active)
    return state.get('handoff', handoff)._live(state['witness'])['header']['operator']['operator_commit']


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
        if locks.file_identities(root, files) != state['identities']:
            raise ValueError('Locked session source or private file identity changed')
        reader = state.get('handoff', handoff)
        predecessor = reader.recheck(root, original, final, harness, state['witness'])
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
        reader.recheck(root, original, final, harness, state['witness'])
        if state.get('recovery_witness') is not None:
            import matched_repeat_recovery_handoff as recovery
            if recovery.recheck(state['recovery_witness']) != state['recovery_record']:
                raise ValueError('Actual completed recovery changed under baseline locks')
        if state.get('terminus_witness') is not None:
            import matched_repeat_terminus_handoff as terminus
            if terminus.recheck(state['terminus_witness']) != state['terminus_record']:
                raise ValueError('Actual completed Terminus changed under OpenHands locks')
        check_files(root, state['files'])
        if locks.file_identities(root, files) != state['identities']:
            raise ValueError('Late baseline source or private file identity change')
        runtime.loaded_sources(root, host['sources'])
        return describe(session)
    except BaseException:
        invalidate(session)
        raise


@contextmanager
def _opened(root, harness, stream, recovery_witness=None, terminus_witness=None):
    """Internal owning entry; public callers never supply a witness or flag."""
    if not _GATE.locked():
        raise ValueError('Actual owning prerequisite entry required')
    session = witness = None
    reader = handoff
    if harness == 'openhands':
        import matched_repeat_openhands_handoff as reader
        import matched_repeat_terminus_handoff as terminus
        terminus._live(terminus_witness)
    elif terminus_witness is not None:
        raise ValueError('Terminus witness belongs only to the real OpenHands successor')
    try:
        root = _context(root, harness)
        if _task() is None:
            raise ValueError('An actual owning async task is required for a baseline session')
        handoff._no_stop(root); wire.pipe_only(stream)
        original, final, files = _inputs(root)
        identities = locks.file_identities(root, files)
        witness = (reader.authenticate(root, original, final, harness, stream) if terminus_witness is None else
            reader.authenticate(root, original, final, harness, stream, terminus_witness))
        if recovery_witness is not None:
            import matched_repeat_recovery_handoff as recovery
            recovered = recovery.recheck(recovery_witness)
            if recovered['operator_commit'] != reader._live(witness)['header']['operator']['operator_commit']:
                raise ValueError('Both actual composite captures must use the same committed revision')
        original_record = original_audit.authenticate(root, original, final, harness)
        with ExitStack() as stack:
            try:
                lease = locks.acquire(stack, root, harness)
                handoff._no_stop(root); check_files(root, files)
                if locks.file_identities(root, files) != identities:
                    raise ValueError('Baseline input identity changed during authentication or locking')
                predecessor = reader.recheck(root, original, final, harness, witness)
                original_record = original_audit.recheck(root, original, final, harness, original_record)
                library = baseline.inspect(root, original, final, harness)
                host = runtime.inspect(root, original, final, harness)
                state = dict(pid=os.getpid(), thread=threading.get_ident(), task=_task(), root=root,
                    harness=harness, original=deepcopy(original), final=deepcopy(final), files=deepcopy(files),
                    witness=witness, predecessor=deepcopy(predecessor), original_record=deepcopy(original_record),
                    library=deepcopy(library), host=deepcopy(host), locks=lease, identities=identities, handoff=reader)
                _coherent(state, predecessor, original_record, library, host)
                if recovery_witness is not None:
                    state.update(recovery_witness=recovery_witness,
                        recovery_record=recovery.recheck(recovery_witness))
                if terminus_witness is not None:
                    state.update(terminus_witness=terminus_witness, terminus_record=terminus.recheck(terminus_witness))
                session = _Session(); _SESSIONS[session] = state
                recheck(session)
                yield session
                # A caught earlier failure cannot turn context exit into success.
                recheck(session)
            finally:
                # Also covers partial acquisition and pre-session entry failures.
                invalidate(session); _invalidate_witness(witness)
                if recovery_witness is not None:
                    recovery.invalidate(recovery_witness)
                if terminus_witness is not None:
                    terminus.invalidate(terminus_witness)
    finally:
        invalidate(session); _invalidate_witness(witness)


@contextmanager
def open_session(root, harness, stream):
    """Legacy inspection scope, not the new recovery-bound execution entry."""
    handoff._first(harness)
    if not _GATE.acquire(blocking=False):
        raise ValueError('Overlapping or nested native prerequisite sessions are refused')
    try:
        with _opened(root, harness, stream) as active:
            yield active
    finally:
        _GATE.release()


@contextmanager
def open_execution_session(root, harness, stream):
    """All required real archives and original audit, then all ancestor locks.

    The recovery subframe is consumed here before the unchanged original
    reader. Its EOF is withheld until the actual final composite commitment.
    No saved record, witness, factory or caller callback is accepted.
    """
    if not _GATE.acquire(blocking=False):
        raise ValueError('Overlapping or nested native prerequisite sessions are refused')
    witness = recovery = earlier = terminus = None
    try:
        import matched_repeat_recovery_handoff as recovery
        root = _context(root, harness)
        if harness == 'openhands':
            import matched_repeat_terminus_handoff as terminus
            earlier, witness, original_stream = terminus.authenticate(root, harness, stream)
        else:
            witness, original_stream = recovery.authenticate(root, harness, stream)
        with _opened(root, harness, original_stream, witness, earlier) as active:
            yield active
    finally:
        if recovery is not None:
            recovery.invalidate(witness)
        if terminus is not None:
            terminus.invalidate(earlier)
        _GATE.release()


def require_execution(active):
    """Actual same-session recovery witness, never a saved prerequisite flag."""
    state = _live(active)
    try:
        import matched_repeat_recovery_handoff as recovery
        witness = state.get('recovery_witness')
        record = recovery.recheck(witness)
        if record != state.get('recovery_record'):
            raise ValueError('Exact live completed-recovery execution scope required')
        if state['harness'] == 'openhands':
            import matched_repeat_terminus_handoff as terminus
            prior = terminus.recheck(state.get('terminus_witness'))
            if prior != state.get('terminus_record') or prior['operator_commit'] != record['operator_commit']:
                raise ValueError('Exact real completed-Terminus witness required for OpenHands execution')
        return deepcopy(record)
    except BaseException:
        invalidate(active)
        raise


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
        invalidate(session)
        raise
