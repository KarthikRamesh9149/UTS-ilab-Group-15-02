"""Existing protected ancestor locks and input identities for baseline repeats.

This never creates or repairs a lock, runs an audit, or grants dispatch. The
installer must precreate the new root's locks. Shared recovery locks preserve
the actual recovery acquisition order before either baseline's own matrix.
"""
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat

import matched_repeat_runtime as runtime
import no_cutoff_recovery_revision as recovery
import run_deadline_custom as ancestors
from direct_final_evidence import CURRENT as C3_ROOT
from no_cutoff_final_evidence import CURRENT as NC_ROOT

FINAL_ROOT = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
RT = '.runtime/stage2'
NAMES = ('matrix.lock', 'scored.lock', 'gateway.lock')


def paths(root, harness):
    root = Path(root)
    if harness not in runtime.DEPLOYMENTS or root != runtime.DEPLOYMENTS[harness]:
        raise ValueError('Exact distinct baseline repeat lock root required')
    early = (*ancestors.ANCESTORS, ancestors.BASELINE, ancestors.DIAGNOSTIC,
        ancestors.STOPPED_CUSTOM, ancestors.PREVIOUS, ancestors.PRIOR_REHEARSAL)
    values = [base / RT / name for base in early for name in NAMES]
    values.append(recovery.ROOT / RT / 'matrix.lock')
    values.extend(base / RT / name for base in
        (C3_ROOT, NC_ROOT, FINAL_ROOT, recovery.RETIRED, recovery.REJECTED, recovery.REGRESSION_REJECTED,
            recovery.CONNECTION_REJECTED, recovery.SYMLINK_REJECTED) for name in NAMES)
    values.extend(recovery.ROOT / RT / name for name in NAMES[1:])
    if harness == 'openhands':
        values.extend(runtime.DEPLOYMENTS['terminus-2'] / RT / name for name in NAMES)
    values.append(root / RT / 'matrix.lock')
    if len(set(values)) != len(values):
        raise ValueError('Distinct complete baseline ancestor lock chain required')
    return tuple(values)


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
        s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _parents(path):
    return tuple(reversed(path.parents))


def _acl(path):
    if not hasattr(os, 'listxattr') or any(name in
            {'system.posix_acl_access', 'system.posix_acl_default'}
            for name in os.listxattr(path, follow_symlinks=False)):
        raise ValueError('ACL-free protected baseline paths required')


def directories(path, *, private=False):
    answer = []
    for parent in (*_parents(path), path):
        s = parent.lstat(); _acl(parent)
        if (parent.resolve() != parent or not stat.S_ISDIR(s.st_mode)
                or s.st_uid not in {0, os.getuid()} or s.st_gid not in {0, os.getgid()}
                or s.st_mode & 0o7022 or parent == path and private
                and (stat.S_IMODE(s.st_mode) != 0o700
                    or s.st_uid != os.getuid() or s.st_gid != os.getgid())):
            raise ValueError('Protected canonical baseline ancestry required')
        # Exclusive producer writes may change directory mtime and link count.
        answer.append((str(parent), s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid))
    return tuple(answer)


def _regular(path, *, private=False):
    s = path.lstat(); _acl(path)
    if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.getuid()
            or s.st_gid != os.getgid() or s.st_mode & 0o7022
            or private and stat.S_IMODE(s.st_mode) != 0o600):
        raise ValueError('Owned protected single-link baseline file required')
    return identity(s)


def file_identities(root, files):
    """Actually read complete bound bytes and identity, including same-byte swaps."""
    root = Path(root); answer = {}
    if type(files) is not dict or not files:
        raise ValueError('Nonempty actual baseline file bindings required')
    for name, expected in files.items():
        if (type(name) is not str or name.startswith('/')
                or any(part in ('', '.', '..') for part in name.split('/'))
                or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
                or type(expected) is not str or not re.fullmatch('[a-f0-9]{64}', expected)):
            raise ValueError('Exact relative baseline source binding required')
        path = root / name; parents = directories(path.parent)
        private = name.startswith('.runtime/')
        before = _regular(path, private=private)
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            if identity(os.fstat(stream.fileno())) != before:
                raise ValueError('Baseline file replaced before read')
            observed = hashlib.file_digest(stream, 'sha256').hexdigest()
            if identity(os.fstat(stream.fileno())) != before:
                raise ValueError('Baseline file changed while reading')
        if (observed != expected or _regular(path, private=private) != before
                or directories(path.parent) != parents):
            raise ValueError('Baseline source bytes or file ancestry changed')
        answer[name] = (before, parents)
    return answer


def _lock_identity(path):
    return _regular(path, private=True), directories(path.parent, private=True)


class Lease:
    def __init__(self):
        self.handles = []

    def recheck(self):
        for path, handle, recorded in self.handles:
            if (handle.closed or _lock_identity(path) != recorded
                    or identity(os.fstat(handle.fileno())) != recorded[0]):
                raise ValueError('Held baseline lock was replaced, closed or changed')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if identity(os.fstat(fd)) != recorded[0]:
                    raise ValueError('Baseline lock replaced during ownership check')
                try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: pass
                else: raise ValueError('Baseline lock is no longer held')
            finally: os.close(fd)
            if _lock_identity(path) != recorded:
                raise ValueError('Held baseline lock protection changed')


def acquire(stack, root, harness):
    """Caller invalidates its handles before closing stack, even on partial entry."""
    ordered = paths(root, harness)
    recorded = {path: _lock_identity(path) for path in ordered}
    lease = Lease()
    for path in ordered:
        handle = stack.enter_context(os.fdopen(os.open(path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb'))
        if identity(os.fstat(handle.fileno())) != recorded[path][0]:
            raise ValueError('Baseline lock changed before acquisition')
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lease.handles.append((path, handle, recorded[path]))
    lease.recheck()
    return lease
