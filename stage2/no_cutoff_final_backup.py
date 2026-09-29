"""One-shot native amended archive stream; no saved proof or paid admission.

Only the separately source-bound reporting bootstrap may invoke stream().
Native state is retained outside the frozen execution root. No archive is
stored on the server, no evidence is changed, and failures are never retried.
"""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import sys
import tarfile

import no_cutoff_final_archive as archive
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report

MAGIC = b'UTS-C0NC-ABSENCE-BACKUP-1\n'
END = b'UTS-C0NC-ABSENCE-BACKUP-END\n'
STATE = ('.backup-intent.json', '.backup-result.json', '.backup-failure.json')
CHUNK = archive.CHUNK


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _identity(s):
    return phase.guard.identity(s)


@contextmanager
def _open(root, name):
    protection = phase.guard.protected_path(root, name)
    path = phase._path(root, name)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as handle:
        before = os.fstat(handle.fileno())
        # Only the fixed execution/historical source trees may contain public
        # sources. Reporting state and every Mac-side output stay private.
        private = root not in (report.ROOT, report.BASELINE, report.STOPPED) or name.startswith('.runtime/')
        phase.guard.protected_file(root, name, before, private=private)
        yield handle, before
        if (_identity(before) != _identity(os.fstat(handle.fileno())) or _identity(before) != _identity(path.lstat())
                or protection != phase.guard.protected_path(root, name)):
            raise ValueError('Backup source changed while reading')


def _digest(root, name, expected=None):
    with _open(root, name) as (handle, before):
        sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    if expected is not None and sha != expected:
        raise ValueError('Actual backup source differs from audit binding')
    return sha, _identity(before)


def _save(root, name, value):
    path = phase._path(root, name)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as handle:
        handle.write(_json(value)); handle.flush(); os.fsync(handle.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _unused():
    for name in STATE:
        if phase._path(report.REPORTING, name).exists():
            raise ValueError('Retained backup operation forbids automatic repetition')


def _recheck(data):
    for name, sha in data['supporting_file_sha256'].items(): _digest(report.ROOT, name, sha)
    for name, sha in data['reporting_source_files'].items(): _digest(report.REPORTING, name, sha)
    for name, entries in data['directory_entries'].items():
        path = phase._path(report.ROOT, name)
        if not path.is_dir() or sorted(p.name for p in path.iterdir()) != entries:
            raise ValueError('Actual evidence inventory changed across backup')
    for name in data['absent_paths']:
        if phase._path(report.ROOT, name).exists():
            raise ValueError('Corroborated absent evidence appeared across backup')
    if set(data['preserved_result_files']) != {str(report.BASELINE), str(report.STOPPED)}:
        raise ValueError('Fixed historical roots required')
    for root, files in data['preserved_result_files'].items():
        for name, sha in files.items(): _digest(Path(root), name, sha)


def _inventory(data):
    """Bind original required bytes plus private logs, without parsing exchanges."""
    files = {n: (report.ROOT, n, h) for n, h in data['supporting_file_sha256'].items()}
    files.update({'reporting/' + n: (report.REPORTING, n, h) for n, h in data['reporting_source_files'].items()})
    directories = set(data['directory_entries']); trees = {}; excluded = 0
    for row in data['rows']:
        trial = phase.RT + 'scored-trials/' + row['trial_id']
        pending = [trial]
        while pending:
            name = pending.pop(); path = phase._path(report.ROOT, name); state = path.stat()
            if not stat.S_ISDIR(state.st_mode) or state.st_uid != os.getuid() or state.st_mode & 0o022:
                raise ValueError('Owned protected private trial directory required')
            children = sorted(p.name for p in path.iterdir()); trees[name] = children; directories.add(name)
            for child in children:
                full = name + '/' + child
                if child in archive.EXCLUDED:
                    if full in files or full in data['directory_entries']:
                        raise ValueError('Exclusion cannot remove required evidence')
                    excluded += 1; continue
                archive._name(full); item = phase._path(report.ROOT, full); info = item.lstat()
                if stat.S_ISDIR(info.st_mode): pending.append(full)
                elif stat.S_ISREG(info.st_mode): files.setdefault(full, (report.ROOT, full, None))
                else: raise ValueError('Links and special private backup files are refused')
    for name in files:
        archive._name(name)
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != '.')
    bound = {}
    for name, (root, source, expected) in sorted(files.items()):
        sha, identity = _digest(root, source, expected)
        bound[name] = (root, source, sha, identity)
    if any(n == a or n.startswith(a + '/') for n in set(bound) | directories for a in data['absent_paths']):
        raise ValueError('Inventory contradicts proven absence')
    return bound, sorted(directories), trees, excluded


def _observations(native, data, document, authenticated):
    native.original.recheck(report.ROOT, document, authenticated)
    proof = native.study.qualified(report.ROOT)
    archive._same(phase.fingerprint(proof), data['qualification_sha256'])
    archive._same(native.policy.require_block(report.ROOT / phase.RT), data['registration'])
    complete = report._coverage(native, data['registration'])
    report._resources()
    for result in complete.values(): report._resources(result['project'])
    native.runtime.loaded_sources(report.ROOT, data['sources'])
    report._stops(); archive._same(report._service(), data['service'])
    # These file/inventory/absence reads follow the final native observation.
    archive._same(report._coverage(native, data['registration']), complete)
    native.original.recheck(report.ROOT, document, authenticated)
    _recheck(data)
    report._context()  # Only the original-interpreter producer, not generic handoff rereads.
    report._loaded({'sources': data['sources']}, data['reporting_source_files'])


def _write(output, raw):
    view = memoryview(raw)
    while view:
        count = output.write(view)
        if type(count) is not int or count <= 0 or count > len(view):
            raise ValueError('Incomplete private backup stream write')
        view = view[count:]


def _metadata(output, value):
    raw = _json(value)
    if len(raw) > archive.ANCHOR_WINDOW: raise ValueError('Metadata parser window exceeded')
    _write(output, struct.pack('!Q', len(raw))); _write(output, raw)


class _Framed:
    def __init__(self, output):
        self.output = output; self.digest = hashlib.sha256(); self.size = 0

    def write(self, raw):
        for offset in range(0, len(raw), CHUNK):
            part = raw[offset:offset + CHUNK]
            _write(self.output, struct.pack('!Q', len(part))); _write(self.output, part)
            self.digest.update(part); self.size += len(part)
        return len(raw)

    def flush(self): self.output.flush()


class _Hashed:
    def __init__(self, handle): self.handle = handle; self.digest = hashlib.sha256()
    def read(self, size=-1):
        raw = self.handle.read(size); self.digest.update(raw); return raw


def _pack(output, data, inventory):
    files, directories, _, excluded = inventory
    framed = _Framed(output); size = 0
    with gzip.GzipFile(filename='', mode='wb', fileobj=framed, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as tar:
            for name in directories:
                member = tarfile.TarInfo(name); member.type = tarfile.DIRTYPE; member.mode = 0o700
                tar.addfile(member)
            for name, (root, source, sha, identity) in files.items():
                with _open(root, source) as (handle, state):
                    if _identity(state) != identity: raise ValueError('Source replaced before archiving')
                    member = tarfile.TarInfo(name); member.mode = 0o600; member.size = state.st_size
                    reader = _Hashed(handle); tar.addfile(member, reader)
                    if reader.digest.hexdigest() != sha or handle.read(1):
                        raise ValueError('Streamed source differs from pre-archive bytes')
                    size += state.st_size
    return dict(kind=archive.KIND, sha256=framed.digest.hexdigest(), compressed_bytes=framed.size,
        files=len(files), bytes=size, excluded=excluded, snapshot_sha256=phase.fingerprint(data),
        reporting_sources_sha256=phase.fingerprint(data['reporting_source_files']),
        absent_paths_sha256=phase.fingerprint(data['absent_paths']))


def _output():
    return sys.__stdout__.buffer


def stream():
    """Actual completed audit, ancestor locks and ONE stdout archive. No args."""
    report._context()
    if Path(__file__).resolve() != report.REPORTING / 'stage2/no_cutoff_final_backup.py':
        raise ValueError('Use the separately source-bound native archive producer')
    report._service(); report._stops(); _unused()
    data = report.collect()
    anchors = {}
    for name, sha in archive.anchor_hashes().items():
        with _open(report.ROOT, name) as (handle, state):
            if state.st_size > archive.ANCHOR_WINDOW: raise ValueError('Metadata parser window exceeded')
            anchors[name] = handle.read()
        if hashlib.sha256(anchors[name]).hexdigest() != sha:
            raise ValueError('Original anchor changed before backup validation')
    archive.validate_snapshot(data, anchors)
    native = report._native(); document = native.study.read_candidate(report.ROOT)
    # Both audits take their own locks; neither runs recursively under ours.
    report._service(); report._stops()
    authenticated = native.original.authenticate(report.ROOT, document)
    with ExitStack() as stack:
        native.runner.lock_all(stack, report.ROOT)
        _unused(); _observations(native, data, document, authenticated)
        inventory = _inventory(data)
        intent = dict(kind='one_shot_amended_final_backup_intent', created_utc=datetime.now(timezone.utc).isoformat(),
            snapshot_sha256=phase.fingerprint(data), reporting_source_files=data['reporting_source_files'],
            automatic_resume=False, paid_launch_ready=False)
        _save(report.REPORTING, STATE[0], intent)
        intent_sha, _ = _digest(report.REPORTING, STATE[0])
        try:
            output = _output(); _write(output, MAGIC); _metadata(output, data)
            receipt = _pack(output, data, inventory)
            _observations(native, data, document, authenticated)
            if _inventory(data) != inventory: raise ValueError('Backup tree changed across streaming')
            _digest(report.REPORTING, STATE[0], intent_sha)
            for name in STATE[1:]:
                if phase._path(report.REPORTING, name).exists(): raise ValueError('Backup state appeared during streaming')
            archive._receipt(data, receipt)
            report._context()
            _save(report.REPORTING, STATE[1], dict(kind='native_amended_archive_streamed_not_off_server_proof',
                receipt=receipt, automatic_resume=False, off_server_backup_verified=False, paid_launch_ready=False))
            # This terminal receipt/marker is emitted only after all rereads.
            _write(output, struct.pack('!Q', 0)); _metadata(output, receipt); _write(output, END); output.flush()
        except BaseException as error:
            _save(report.REPORTING, STATE[2], dict(kind='amended_backup_failed_inspection_required',
                error_type=type(error).__name__, automatic_resume=False, paid_launch_ready=False))
            raise
