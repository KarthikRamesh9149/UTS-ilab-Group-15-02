"""Separate recovery archive inventory, stream and strict existing-byte reader.

No extraction, original archive recreation, repair, chmod or saved admission.
The caller owns the real live reporting session and pinned transport.
"""
from contextlib import contextmanager
import gzip
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import tarfile

import no_cutoff_final_archive as original_archive
import no_cutoff_final_archive_logs as original_logs
import no_cutoff_final_backup as framing
import no_cutoff_recovery_files as files
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_report as report
import no_cutoff_recovery_service as service

KIND = 'separate_recovery3_private_archive_v1'
MAGIC = b'UTS-C0NC-RECOVERY3-BACKUP-1\n'
END = b'UTS-C0NC-RECOVERY3-BACKUP-END\n'
CHUNK = 64 * 1024


def _name(name):
    value = original_archive._name(name)
    if any(p.startswith('.env.') for p in PurePosixPath(value).parts):
        raise ValueError('Credential/cache exclusions apply to recovery archive')
    return value


def _protection(root, name, trials):
    """Explicit new-root compatibility for extra logs, old reporter unchanged."""
    _name(name)
    if not original_logs.applies(name, trials):
        files.libraries.protected(root, name)
        path = root / name; state = path.lstat()
        if (path.resolve() != path or state.st_uid != os.getuid() or state.st_gid != os.getgid()
                or state.st_mode & 0o7022): raise ValueError('Protected archive source required')
        if stat.S_ISDIR(state.st_mode):
            return files.bootstrap.directories(path, private=name.startswith('.runtime/'))
        return files.bootstrap.directories(path.parent), files.bootstrap.identity(state)
    if root != service.ROOT: raise ValueError('Own fixed recovery log root required')
    saved = list(files.bootstrap.directories(root, private=True))
    current = root; parts = name.split('/')
    for index, part in enumerate(parts, 1):
        current /= part; state = current.lstat(); files.bootstrap.acl(current)
        if (current.resolve() != current or current.is_symlink() or state.st_uid != os.getuid()
                or state.st_gid != os.getgid() or state.st_mode & 0o7000):
            raise ValueError('Owned canonical ACL-free recovery log path required')
        if index <= 4:
            if not stat.S_ISDIR(state.st_mode) or stat.S_IMODE(state.st_mode) != 0o700:
                raise ValueError('Exact private recovery trial boundary required')
        elif stat.S_ISDIR(state.st_mode):
            if stat.S_IMODE(state.st_mode) not in ((0o700, 0o777) if index == 5 else (0o700,)):
                raise ValueError('Only registered agent/verifier roots may be container writable')
        else:
            modes = (0o600,) if parts[4] == 'agent' else (0o600, 0o644, 0o660)
            if (index != len(parts) or not stat.S_ISREG(state.st_mode) or state.st_nlink != 1
                    or stat.S_IMODE(state.st_mode) not in modes):
                raise ValueError('Exact protected extra recovery log file required')
        saved.append((str(current), files.bootstrap.identity(state)))
    return tuple(saved)


@contextmanager
def _open(root, name, trials):
    before = _protection(root, name, trials); path = root / name
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as handle:
        state = os.fstat(handle.fileno())
        if (not stat.S_ISREG(state.st_mode) or state.st_nlink != 1 or state.st_uid != os.getuid()
                or state.st_gid != os.getgid() or not original_logs.applies(name, trials)
                and name.startswith('.runtime/') and stat.S_IMODE(state.st_mode) != 0o600):
            raise ValueError('Regular protected single-link archive source required')
        yield handle, files.bootstrap.identity(state)
        if (files.bootstrap.identity(os.fstat(handle.fileno())) != files.bootstrap.identity(state)
                or files.bootstrap.identity(path.lstat()) != files.bootstrap.identity(state)
                or _protection(root, name, trials) != before):
            raise ValueError('Archive source identity or protection changed')


def inventory(data):
    root = service.ROOT; trials = frozenset(r['trial_id'] for r in data['rows'])
    bound = dict(data['supporting_files']); directories = set(data['directory_entries']); trees = {}; excluded = []
    if any(original_logs.applies(n, trials) for n in bound):
        raise ValueError('Required evidence cannot use extra-log permission compatibility')
    for trial_id in trials:
        pending = [report.RT + 'scored-trials/' + trial_id]
        while pending:
            name = pending.pop(); path = root / name; protection = _protection(root, name, trials)
            state = path.lstat()
            if not stat.S_ISDIR(state.st_mode): raise ValueError('Actual trial directory required')
            children = sorted(p.name for p in path.iterdir())
            trees[name] = dict(entries=children, identity=files.bootstrap.identity(state), protection=protection)
            directories.add(name)
            for child in children:
                full = name + '/' + child
                if child in original_logs.EXCLUDED or child.startswith('.env.'):
                    if full in bound: raise ValueError('Cannot exclude required recovery evidence')
                    excluded.append(full); continue
                _name(full); _protection(root, full, trials); item = (root / full).lstat()
                if stat.S_ISDIR(item.st_mode): pending.append(full)
                elif stat.S_ISREG(item.st_mode): bound.setdefault(full, None)
                else: raise ValueError('Linked/special recovery archive payload refused')
    identities = {}; sizes = {}
    for name, expected in sorted(bound.items()):
        _name(name)
        with _open(root, name, trials) as (handle, identity):
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if expected is not None: policy._same(digest, expected)
        bound[name] = digest; identities[name] = identity; sizes[name] = identity[6]
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != '.')
    if any(n == a or n.startswith(a + '/') for n in set(bound) | directories for a in data['absent_paths']):
        raise ValueError('Recovery archive inventory contradicts corroborated absence')
    result = dict(files=bound, sizes=sizes, directories=sorted(directories), excluded=sorted(excluded),
        absent_paths=data['absent_paths'], snapshot_sha256=policy.fingerprint(data),
        extra_logs_protection=original_logs.contract())
    state = dict(identities=identities, trees=trees, trials=trials)
    recheck(result, state)
    return result, state


def recheck(record, state):
    root = service.ROOT
    for name, expected in record['files'].items():
        with _open(root, name, state['trials']) as (handle, identity):
            if identity != state['identities'][name] or hashlib.file_digest(handle, 'sha256').hexdigest() != expected:
                raise ValueError('Recovery archive inventory file changed')
    for name, item in state['trees'].items():
        path = root / name
        if (sorted(p.name for p in path.iterdir()) != item['entries']
                or files.bootstrap.identity(path.lstat()) != item['identity']
                or _protection(root, name, state['trials']) != item['protection']):
            raise ValueError('Recovery archive trial tree changed')
    for name in record['absent_paths']:
        report._absent(root, name)


def pack(output, record, state):
    framed = framing._Framed(output)
    with gzip.GzipFile(filename='', mode='wb', fileobj=framed, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
            for name in record['directories']:
                entry = tarfile.TarInfo(name); entry.type = tarfile.DIRTYPE; entry.mode = 0o700
                archive.addfile(entry)
            for name, digest in sorted(record['files'].items()):
                with _open(service.ROOT, name, state['trials']) as (handle, identity):
                    if identity != state['identities'][name]: raise ValueError('Archive source replaced before copy')
                    entry = tarfile.TarInfo(name); entry.mode = 0o600; entry.size = record['sizes'][name]
                    reader = framing._Hashed(handle); archive.addfile(entry, reader)
                    if reader.digest.hexdigest() != digest or handle.read(1): raise ValueError('Archive source bytes drifted')
    return dict(kind=KIND, sha256=framed.digest.hexdigest(), compressed_bytes=framed.size,
        files=len(record['files']), bytes=sum(record['sizes'].values()),
        snapshot_sha256=record['snapshot_sha256'], inventory_sha256=policy.fingerprint(record))


def validate_inventory(record, data):
    if set(record) != {'files', 'sizes', 'directories', 'excluded', 'absent_paths', 'snapshot_sha256', 'extra_logs_protection'}:
        raise ValueError('Exact private recovery inventory required')
    policy._same(record['snapshot_sha256'], policy.fingerprint(data))
    policy._same(record['absent_paths'], data['absent_paths'])
    policy._same(record['extra_logs_protection'], original_logs.contract())
    if set(record['files']) != set(record['sizes']) or not record['files']:
        raise ValueError('Exact complete recovery file sizes required')
    for name, digest in record['files'].items():
        _name(name); policy._hash(digest)
        if type(record['sizes'][name]) is not int or record['sizes'][name] < 0: raise ValueError('Actual file size required')
    for name, digest in data['supporting_files'].items(): policy._same(record['files'].get(name), digest)
    trials = {report.RT + 'scored-trials/' + r['trial_id'] for r in data['rows']}
    if any(n not in data['supporting_files'] and not any(n.startswith(t + '/') for t in trials) for n in record['files']):
        raise ValueError('Extra archive files must be below registered trials')
    for key in ('directories', 'excluded', 'absent_paths'):
        if type(record[key]) is not list or record[key] != sorted(set(record[key])): raise ValueError('Exact ordered inventory required')
    for name in record['directories']: _name(name)
    parents = {str(p) for n in record['files'] for p in PurePosixPath(n).parents if str(p) != '.'}
    if not parents <= set(record['directories']) or set(record['directories']) & set(record['files']):
        raise ValueError('Complete archive ancestry required')
    if any(n not in parents and n not in data['directory_entries']
            and not any(n == t or n.startswith(t + '/') for t in trials) for n in record['directories']):
        raise ValueError('Extra empty directories must remain below registered trials')
    if any(n == a or n.startswith(a + '/') for n in set(record['files']) | set(record['directories']) for a in record['absent_paths']):
        raise ValueError('Archive inventory contradicts actual absence')
    for directory, entries in data['directory_entries'].items():
        _name(directory)
        actual = sorted({n[len(directory)+1:].split('/')[0] for n in set(record['files']) | set(record['directories'])
            if n.startswith(directory + '/')})
        if directory not in record['directories'] or actual != entries:
            raise ValueError('Archive differs from exact retained evidence directory inventory')
    for name in record['excluded']:
        if (not any(name.startswith(t + '/') for t in trials)
                or not any(p in original_logs.EXCLUDED or p.startswith('.env.') for p in name.split('/'))):
            raise ValueError('Only credential/cache exclusions under registered trials permitted')


def verify(path, data, record, receipt, manifest, sources):
    """Strictly reread the ONE existing private archive; never extract or write."""
    report.validate(data, manifest, sources); validate_inventory(record, data)
    expected = dict(kind=KIND, sha256=receipt.get('sha256'), compressed_bytes=receipt.get('compressed_bytes'),
        files=len(record['files']), bytes=sum(record['sizes'].values()),
        snapshot_sha256=policy.fingerprint(data), inventory_sha256=policy.fingerprint(record))
    policy._same(receipt, expected); policy._hash(receipt['sha256'])
    if type(receipt['compressed_bytes']) is not int or receipt['compressed_bytes'] <= 0:
        raise ValueError('Exact compressed recovery archive size required')
    path = Path(path); parent = files.bootstrap.directories(path.parent, private=True)
    if path.resolve() != path: raise ValueError('Canonical owned private recovery archive required')
    seen = set(); found_dirs = set(); found_files = set(); metadata = {}
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as handle:
        before = os.fstat(handle.fileno()); files.bootstrap.acl(path)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.getuid()
                or before.st_gid != os.getgid() or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_size != receipt['compressed_bytes']): raise ValueError('Exact protected recovery archive required')
        compressed_source = original_archive._Compressed(handle, before.st_size)
        with gzip.GzipFile(fileobj=compressed_source, mode='rb') as compressed:
            with tarfile.open(fileobj=compressed, mode='r|', tarinfo=original_archive._TarInfo) as archive:
                for entry in archive:
                    name = _name(entry.name)
                    if (name in seen or entry.issym() or entry.islnk() or entry.sparse is not None
                            or set(entry.pax_headers) - {'path', 'mtime', 'atime', 'ctime'}):
                        raise ValueError('Unsafe, duplicate or linked recovery archive entry')
                    seen.add(name)
                    if entry.isdir():
                        if name not in record['directories'] or entry.mode != 0o700: raise ValueError('Unexpected archive directory')
                        found_dirs.add(name)
                    elif entry.isfile():
                        if name not in record['files'] or entry.size != record['sizes'][name] or entry.mode != 0o600:
                            raise ValueError('Unexpected recovery archive payload')
                        with archive.extractfile(entry) as contents:
                            if name in {report.RT + n for n in (*qualification_inputs(), policy.REGISTRATION_FILE)}:
                                if entry.size > files.bootstrap.WINDOW: raise ValueError('Metadata parser window exceeded')
                                raw = contents.read(); metadata[name] = raw; digest = hashlib.sha256(raw).hexdigest()
                            else: digest = hashlib.file_digest(contents, 'sha256').hexdigest()
                        policy._same(digest, record['files'][name]); found_files.add(name)
                    else: raise ValueError('Special recovery archive entry refused')
                padding = 0
                while tail := archive.fileobj.read(CHUNK):
                    if tail.strip(b'\0'): raise ValueError('Hidden nonpadding data after tar end marker')
                    padding += len(tail)
                if padding < tarfile.BLOCKSIZE: raise ValueError('Complete tar end markers required')
            if compressed.read(CHUNK): raise ValueError('Extra decompressed archive payload')
        if (compressed_source.remaining or compressed_source.digest.hexdigest() != receipt['sha256'] or handle.read(1)
                or found_dirs != set(record['directories']) or found_files != set(record['files'])
                or files.bootstrap.identity(before) != files.bootstrap.identity(os.fstat(handle.fileno()))
                or files.bootstrap.identity(before) != files.bootstrap.identity(path.lstat())
                or files.bootstrap.directories(path.parent, private=True) != parent):
            raise ValueError('Recovery archive identity, checksum or exact inventory differs')
    _anchors(data, metadata, manifest, sources)
    return dict(receipt, verified_result_files=3, verified_bound_files=len(found_files),
        verified_absent_paths=len(data['absent_paths']), private_archive_not_published=True,
        paid_launch_ready=False, full_runtime_restore_exercised=False)


def qualification_inputs():
    return (policy.POLICY_FILE, policy.PLAN_FILE, policy.MANIFEST_FILE, policy.ORIGINAL_FILE,
        policy.PREDECESSOR_FILE, policy.RUNTIME_FILE, policy.QUALIFICATION_FILE)


def _anchors(data, raw, manifest, sources):
    documents = {n: files.bootstrap.loads(raw[report.RT + n]) for n in (*qualification_inputs(), policy.REGISTRATION_FILE)}
    policy._same(hashlib.sha256(raw[report.RT + policy.ORIGINAL_FILE]).hexdigest(), policy.ORIGINAL_QUALIFICATION_FILE_SHA256)
    policy._same(hashlib.sha256(raw[report.RT + policy.MANIFEST_FILE]).hexdigest(), policy.INPUT_SHA256)
    policy._same(documents[policy.MANIFEST_FILE], manifest)
    policy._same(documents[policy.POLICY_FILE], policy.POLICY)
    policy.plan.validate_schedule(documents[policy.PLAN_FILE], manifest)
    proof = documents[policy.QUALIFICATION_FILE]; predecessor = documents[policy.PREDECESSOR_FILE]
    policy.validate_qualification(documents[policy.ORIGINAL_FILE], predecessor, manifest, proof)
    block = policy.registration(documents[policy.ORIGINAL_FILE], predecessor, manifest, proof)
    policy._same(documents[policy.REGISTRATION_FILE], block); policy._same(data['registration'], block)
    policy._same(proof['sources'], sources); policy._same(data['qualification_sha256'], policy.fingerprint(proof))
    policy._same(data['predecessor'], predecessor)
    policy._same(proof['runtime_identity_sha256'], policy.fingerprint(documents[policy.RUNTIME_FILE]))
    for row in data['rows']:
        original_archive._row({k:v for k,v in row.items() if k in report.original_report.ROW_FIELDS},
            documents[policy.RUNTIME_FILE]['task_inventory'][row['task_id']],
            original_archive._utc(data['collected_utc']))
    for name, digest in {**proof['evidence_files'], **proof['image_evidence_files']}.items():
        policy._same(data['supporting_files'].get(name), digest)
