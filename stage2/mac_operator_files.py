"""Actual Darwin protection and exclusive local evidence IO.

This module has no native operation or benchmark admission. Fixed callers own
their destination. Darwin ACLs are actually read, never inferred from the
Linux-only os.listxattr API or from Unix mode bits alone.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

WINDOW = 64 * 1024 * 1024
OPERATOR_HOME = Path('/Users/karthikramesh')


def _darwin():
    if sys.platform != 'darwin':
        raise ValueError('This reader is only for actual Darwin operator files')


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
        s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _acl(path):
    _darwin()
    before = identity(path.lstat())
    result = subprocess.run(['/bin/ls', '-lde', str(path)], capture_output=True,
        timeout=10, env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
    lines = result.stdout.splitlines()
    entries = tuple(line.strip() for line in lines[1:])
    # The actual macOS home has the standard deny-delete ACL. It grants no
    # access. This exact entry is permitted only on this fixed ancestor, not
    # on evidence, arbitrary directories, or alongside any other ACL entry.
    deny_delete = path == OPERATOR_HOME and entries == (b'0: group:everyone deny delete',)
    if (result.returncode or result.stderr or not lines
            or not lines[0].split(maxsplit=1)
            or not re.fullmatch(rb'[-d][rwxstST-]{9}' + (rb'\+' if deny_delete else rb'@?'),
                lines[0].split(maxsplit=1)[0])
            or entries and not deny_delete
            or identity(path.lstat()) != before):
        raise ValueError('Actual unchanged restrictive Darwin operator ACL required')
    return entries


def acl(path):
    return _acl(Path(path))


def directories(path, *, private=False):
    _darwin()
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute canonical operator directory required')
    result = []
    for current in (*reversed(path.parents), path):
        before = current.lstat()
        # Darwin's actual /Users ancestor is root:admin (gid80). Only root-
        # owned, non-group-writable ancestry gets this Mac system-group rule.
        groups = {0, 80, os.getgid()} if before.st_uid == 0 else {os.getgid()}
        if (current.resolve() != current or not stat.S_ISDIR(before.st_mode)
                or before.st_uid not in {0, os.getuid()} or before.st_gid not in groups
                or before.st_mode & 0o7022 or current == path and private
                and (stat.S_IMODE(before.st_mode) != 0o700
                    or before.st_uid != os.getuid() or before.st_gid != os.getgid())):
            raise ValueError('Protected canonical owned Darwin directory required')
        acl_entries = _acl(current)
        after = current.lstat()
        saved = (str(current), before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_gid)
        if saved != (str(current), after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid):
            raise ValueError('Operator directory identity changed')
        result.append((*saved, acl_entries))
    return tuple(result)


def relative(name):
    if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('Exact normalised operator relative path required')
    return name


@contextmanager
def opened(path, *, private=True):
    """Actual protected regular file; opaque payload reads have no size cap."""
    path = Path(path)
    parents = directories(path.parent, private=private)
    if path.resolve() != path:
        raise ValueError('Canonical operator file required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_uid != os.getuid() or before.st_gid != os.getgid()
                or before.st_mode & 0o7022 or private and stat.S_IMODE(before.st_mode) != 0o600
                or identity(path.lstat()) != identity(before)):
            raise ValueError('Owned single-link protected operator file required')
        _acl(path)
        yield stream, identity(before)
        if (identity(os.fstat(stream.fileno())) != identity(before)
                or identity(path.lstat()) != identity(before)
                or directories(path.parent, private=private) != parents):
            raise ValueError('Operator bytes, ancestry or file identity changed')
        _acl(path)


def raw(root, name, expected=None, *, private=True):
    path = Path(root) / relative(name)
    with opened(path, private=private) as (stream, before):
        if before[6] > WINDOW:
            raise ValueError('Metadata parser window exceeded')
        value = stream.read(WINDOW + 1)
        if len(value) > WINDOW or expected is not None and hashlib.sha256(value).hexdigest() != expected:
            raise ValueError('Exact bounded operator metadata bytes required')
    return value, before


def loads(raw_bytes):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate operator metadata key')
            value[key] = item
        return value
    def constant(_):
        raise ValueError('Nonfinite operator metadata')
    value = json.loads(raw_bytes.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    if type(value) is not dict:
        raise ValueError('Operator metadata object required')
    return value


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_bytes(path, value):
    if type(value) is not bytes:
        raise TypeError('Exact private UTF-8 or payload bytes required')
    path = Path(path)
    parents = directories(path.parent, private=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(value); stream.flush(); os.fsync(stream.fileno())
        created = identity(os.fstat(stream.fileno()))
    sync(path.parent)
    if raw(path.parent, path.name) != (value, created) or directories(path.parent, private=True) != parents:
        raise ValueError('Exclusive durable operator evidence changed')
    return created


def save(path, value):
    # Serialisation precedes exclusive creation, so malformed data leaves no
    # misleading empty operation marker. Existing files are never overwritten.
    raw_bytes = json.dumps(value, sort_keys=True, allow_nan=False).encode('utf-8')
    return write_bytes(path, raw_bytes)
