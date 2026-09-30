"""Protected recovery evidence IO; no admission from saved records.

JSON has a metadata parser window. Opaque producer files are streamed without
a payload-size limit. Writes are exclusive, private and durable, never updates.
"""
import hashlib
import json
import os
from pathlib import Path

import no_cutoff_recovery_bootstrap as bootstrap
import no_cutoff_recovery_libraries as libraries


def read(root, name):
    root = Path(root)
    libraries.protected(root, name)
    raw, identity = bootstrap.raw(root, name)
    return raw, dict(sha256=hashlib.sha256(raw).hexdigest(), identity=identity)


def private(root, name, identities=None):
    relative = '.runtime/stage2/' + libraries.relative(name)
    raw, item = read(root, relative)
    if identities is not None:
        if relative in identities and identities[relative] != item['identity']:
            raise ValueError('Recovery private identity replaced')
        identities[relative] = item['identity']
    return bootstrap.loads(raw), {relative: hashlib.sha256(raw).hexdigest()}


def capture(root, names):
    """Actual bytes and identities, not just a previously saved hash map."""
    root = Path(root)
    bindings, identities = {}, {}
    for name in sorted(names):
        path = root / libraries.relative(name)
        before = libraries.identity(path.lstat())
        digest = libraries.read(root, name, names[name] if isinstance(names, dict) else None)
        if libraries.identity(path.lstat()) != before:
            raise ValueError('Recovery evidence identity changed during capture')
        bindings[name] = digest; identities[name] = before
    return bindings, identities


def check(root, bindings, identities=None):
    actual, current = capture(root, bindings)
    if actual != bindings or identities is not None and current != identities:
        raise ValueError('Recovery evidence bytes or identity changed')


def extend(root, bindings, identities):
    """Retain earlier file identities while adding newly produced evidence."""
    _, current = capture(root, bindings)
    if any(current.get(name) != value for name, value in identities.items()):
        raise ValueError('Earlier recovery evidence identity replaced')
    identities.update(current)
    return identities


def save(path, value):
    """Serialise before creating anything; refuse existing or partial evidence."""
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode('utf-8')
    before = bootstrap.directories(path.parent, private=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        identity = bootstrap.identity(os.fstat(stream.fileno()))
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(parent)
    finally: os.close(parent)
    observed, actual = bootstrap.raw(path.parent, path.name)
    if observed != raw or actual != identity or bootstrap.directories(path.parent, private=True) != before:
        raise ValueError('Exclusive recovery evidence changed during durable write')
