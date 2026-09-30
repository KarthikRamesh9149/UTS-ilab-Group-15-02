"""Recovery-only locked prerequisites, not qualification or scored admission.

The future pinned SSH service must consume this context in its owning native
main-thread async task. A fresh actual original audit and same-archive handoff
precede every ancestor lock. No saved witness, root, factory or callback input
is accepted. This component neither writes evidence nor starts an attempt.
"""
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import stat
import sys
import threading
import weakref

import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_runtime as runtime
import run_deadline_custom as ancestors
from direct_final_evidence import CURRENT as C3_ROOT
from no_cutoff_final_evidence import CURRENT as NC_ROOT

KIND = 'locked_recovery_prerequisites_not_scored_admission'
LIMITATIONS = dict(paid_launch_ready=False, recovery_execution_qualified=False,
    historical_installed_bytes_attested=False, full_runtime_restore_exercised=False,
    transport='actual-pinned-SSH-service-integration-required',
    off_server_archive='freshly-read-at-handoff-not-continuously-attested',
    qualification_registration_and_scored_dispatch='separate-required-integration')
_SESSIONS = weakref.WeakKeyDictionary()
_GATE = threading.Lock()


class _Session:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Recovery sessions cannot be copied or saved')


def _context():
    root = handoff._context()
    if (root != handoff.ROOT or Path(__file__).absolute() != root / 'stage2/no_cutoff_recovery_session.py'
            or Path(sys.executable).absolute() != root / '.venv/bin/python'):
        raise ValueError('Own fixed recovery service interpreter and source required')
    # Includes every ancestor above /opt, not just the final parent directory.
    runtime.libraries.protected(root, 'stage2/no_cutoff_recovery_session.py')
    return root


def _inputs(root):
    raw = handoff._raw(root, handoff.phase.RT + policy.ORIGINAL_FILE,
        policy.ORIGINAL_QUALIFICATION_FILE_SHA256)
    final = handoff.phase._loads(raw); policy.original_final(final)
    bound = handoff.operator.sources(root, final)
    files = {'stage2/' + n: h for n, h in bound.items()}
    files[handoff.phase.RT + policy.ORIGINAL_FILE] = policy.ORIGINAL_QUALIFICATION_FILE_SHA256
    files['stage2/input_manifest.json'] = policy.INPUT_SHA256
    identities = {}
    for name, digest in files.items():
        path = root / name; before = runtime.libraries.identity(path.lstat())
        runtime.libraries.read(root, name, digest)
        if runtime.libraries.identity(path.lstat()) != before:
            raise ValueError('Recovery source/private identity changed during read')
        identities[name] = before
    manifest = handoff.phase._loads(handoff._raw(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    policy.cells(manifest); handoff.operator.loaded(root, bound)
    return dict(final=final, sources=bound, files=files, identities=identities)


def _lock_paths(root):
    # Exact inherited run_no_cutoff_final.lock_all order, then original final's
    # three locks. Only the new root's matrix is held here; scored/gateway locks
    # belong to the future actual per-attempt lifecycle. No old helper changes.
    early = (*ancestors.ANCESTORS, ancestors.BASELINE, ancestors.DIAGNOSTIC,
        ancestors.STOPPED_CUSTOM, ancestors.PREVIOUS, ancestors.PRIOR_REHEARSAL)
    paths = [base / handoff.phase.RT / n for base in early
        for n in ('matrix.lock', 'scored.lock', 'gateway.lock')]
    paths.append(root / handoff.phase.RT / 'matrix.lock')
    paths.extend(base / handoff.phase.RT / n for base in (C3_ROOT, NC_ROOT, handoff.report.ROOT)
        for n in ('matrix.lock', 'scored.lock', 'gateway.lock'))
    paths.extend(handoff.revision.RETIRED / handoff.phase.RT / n
        for n in ('matrix.lock', 'scored.lock', 'gateway.lock'))
    if len(set(paths)) != len(paths): raise ValueError('Distinct complete recovery lock chain required')
    return tuple(paths)


def _lock_parents(path):
    return tuple(reversed(path.parents))


def _lock_identity(path):
    """Existing lock files only: never create, replace, chmod or write one."""
    parents = []
    for parent in _lock_parents(path):
        s = parent.lstat()
        if (parent.resolve() != parent or not stat.S_ISDIR(s.st_mode)
                or s.st_uid != os.getuid() or s.st_gid != os.getgid() or s.st_mode & 0o7022
                or parent == path.parent and stat.S_IMODE(s.st_mode) != 0o700):
            raise ValueError('Protected canonical ancestor lock directory required')
        runtime.libraries.acl(parent)
        # Future exclusive evidence writes may change directory mtime/nlink;
        # directory identity, ownership, mode and ACL protection may not change.
        parents.append((str(parent), s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid))
    s = path.lstat(); runtime.libraries.acl(path)
    if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.getuid()
            or s.st_gid != os.getgid() or stat.S_IMODE(s.st_mode) != 0o600):
        raise ValueError('Existing private single-link ancestor lock required')
    return runtime.libraries.identity(s), tuple(parents)


class _Locks:
    def __init__(self): self.handles = []

    def recheck(self):
        for path, handle, recorded in self.handles:
            if (handle.closed or _lock_identity(path) != recorded
                    or runtime.libraries.identity(os.fstat(handle.fileno())) != recorded[0]):
                raise ValueError('Held ancestor lock identity changed or closed')
            # A second open-file description must conflict. This does not unlock
            # or reacquire our held descriptor, and never waits for another job.
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if runtime.libraries.identity(os.fstat(fd)) != recorded[0]:
                    raise ValueError('Ancestor lock replaced during ownership check')
                try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: pass
                else: raise ValueError('Ancestor lock is no longer held')
            finally: os.close(fd)
            if _lock_identity(path) != recorded:
                raise ValueError('Ancestor lock protection changed')


@contextmanager
def _locked(root, witness):
    paths = _lock_paths(root)
    recorded = {p: _lock_identity(p) for p in paths}
    lease = _Locks()
    with ExitStack() as stack:
        try:
            for path in paths:
                handle = stack.enter_context(os.fdopen(os.open(path,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb'))
                if runtime.libraries.identity(os.fstat(handle.fileno())) != recorded[path][0]:
                    raise ValueError('Ancestor lock changed before acquisition')
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lease.handles.append((path, handle, recorded[path]))
            lease.recheck()
            yield lease
        finally:
            # Covers failure during partial acquisition, before the caller's
            # context body exists, as well as normal/exceptional context exit.
            handoff.invalidate(witness)


def invalidate(session):
    """Revoke both handles immediately; context exit alone releases locks."""
    if type(session) is _Session:
        state = _SESSIONS.pop(session, None)
        if state is not None: handoff.invalidate(state['witness'])


def _live(session):
    if type(session) is not _Session or session not in _SESSIONS:
        raise ValueError('Actual live locked recovery session required, not saved metadata')
    state = _SESSIONS[session]
    try:
        if (state['pid'] != os.getpid() or state['thread'] != threading.get_ident()
                or state['task'] is not handoff._task() or state['task'] is None
                or threading.current_thread() is not threading.main_thread()):
            raise ValueError('Recovery sessions cannot cross processes, threads or async tasks')
        handoff._live(state['witness']); state['locks'].recheck()
        return state
    except BaseException:
        invalidate(session)
        raise


def _coherent(inputs, predecessor, host):
    policy._same(predecessor['kind'], handoff.KIND)
    policy._same(host['kind'], runtime.KIND)
    for value in (predecessor, host):
        policy._same(value['experiment'], policy.EXPERIMENT)
        policy._same(value['paid_launch_ready'], False)
    policy._same(host['condition'], policy.CONDITION)
    policy._same(host['original_qualification_sha256'], policy.fingerprint(inputs['final']))
    policy._same(host['original_runtime_sha256'], inputs['final']['runtime_identity_sha256'])
    policy._same(host['plan_sha256'], policy.PLAN_SHA256)
    policy._same(host['predecessor_sha256'], policy.fingerprint(predecessor['predecessor']))
    policy._same(host['sources'], inputs['sources'])
    source_sha = policy.fingerprint(inputs['sources'])
    policy._same(host['sources_sha256'], source_sha)
    policy._same(predecessor['current_sources_sha256'], source_sha)
    for name, digest in inputs['files'].items():
        policy._same(predecessor['copied_files'].get(name), digest)


def describe(session):
    """Non-admitting deep copy; never a fresh observation or saved handle."""
    state = _live(session)
    return deepcopy(dict(kind=KIND, experiment=policy.EXPERIMENT, condition=policy.CONDITION,
        files=state['inputs']['files'], predecessor=state['predecessor'], runtime=state['host'],
        limitations=LIMITATIONS, paid_launch_ready=False))


def recheck(session):
    """Real under-lock host/library/evidence reads, no audit/transfer/new lock."""
    state = _live(session)
    try:
        root = _context()
        if root != state['root'] or _inputs(root) != state['inputs']:
            raise ValueError('Recovery input bytes or identities changed')
        host = runtime.recheck(state['witness'], state['host'])
        predecessor = handoff.describe(state['witness'])
        _coherent(state['inputs'], predecessor, host)
        policy._same(predecessor, state['predecessor'])
        # Runtime's last service/host/image observation is already followed by
        # its real historical/library/dataset rereads. No such observation follows.
        if _inputs(root) != state['inputs']:
            raise ValueError('Late recovery source/private identity drift')
        return describe(session)
    except BaseException:
        invalidate(session)
        raise


@contextmanager
def open_session(stream):
    """Actual fresh handoff BEFORE full locks; both handles die BEFORE unlock."""
    if not _GATE.acquire(blocking=False):
        raise ValueError('Nested or overlapping recovery sessions are refused')
    session = witness = None
    try:
        root = _context(); handoff.wire.pipe_only(stream); handoff._no_stop(root)
        inputs = _inputs(root)
        witness = handoff.authenticate(stream)
        try:
            with _locked(root, witness) as locks:
                try:
                    if _inputs(root) != inputs:
                        raise ValueError('Recovery inputs changed while authenticating or locking')
                    host = runtime.inspect(witness)
                    predecessor = handoff.describe(witness)
                    _coherent(inputs, predecessor, host)
                    if _inputs(root) != inputs:
                        raise ValueError('Recovery inputs changed during host inspection')
                    session = _Session()
                    _SESSIONS[session] = dict(pid=os.getpid(), thread=threading.get_ident(),
                        task=handoff._task(), root=root, inputs=deepcopy(inputs), witness=witness,
                        predecessor=deepcopy(predecessor), host=deepcopy(host), locks=locks)
                    _live(session)
                    yield session
                    recheck(session)
                finally:
                    invalidate(session); handoff.invalidate(witness)
        finally:
            # Also covers a partial/nonblocking lock acquisition failure.
            handoff.invalidate(witness)
    finally:
        invalidate(session)
        _GATE.release()
