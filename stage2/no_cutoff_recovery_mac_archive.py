"""Darwin path verifier for the unchanged R6 recovery archive contract.

Only local file protection differs from the frozen Linux reader. The strict
tar/gzip/schema/member/absence checks and three-result denominator are exact.
No writer, extraction, native operation or saved admission is provided.
"""
import gzip
import hashlib
import os
from pathlib import Path
import stat
import tarfile

import mac_operator_files as mac
from no_cutoff_recovery_archive import (KIND, CHUNK, END, MAGIC, _name, _anchors,
    qualification_inputs, validate_inventory, framing, original_archive, report, policy)


def verify(path, data, record, receipt, manifest, sources):
    """Strictly reread the ONE existing private archive; never extract or write."""
    report.validate(data, manifest, sources); validate_inventory(record, data)
    expected = dict(kind=KIND, sha256=receipt.get('sha256'), compressed_bytes=receipt.get('compressed_bytes'),
        files=len(record['files']), bytes=sum(record['sizes'].values()),
        snapshot_sha256=policy.fingerprint(data), inventory_sha256=policy.fingerprint(record))
    policy._same(receipt, expected); policy._hash(receipt['sha256'])
    if type(receipt['compressed_bytes']) is not int or receipt['compressed_bytes'] <= 0:
        raise ValueError('Exact compressed recovery archive size required')
    path = Path(path); parent = mac.directories(path.parent, private=True)
    if path.resolve() != path: raise ValueError('Canonical owned private recovery archive required')
    seen = set(); found_dirs = set(); found_files = set(); metadata = {}
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as handle:
        before = os.fstat(handle.fileno()); mac.acl(path)
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
                                if entry.size > mac.WINDOW: raise ValueError('Metadata parser window exceeded')
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
                or mac.identity(before) != mac.identity(os.fstat(handle.fileno()))
                or mac.identity(before) != mac.identity(path.lstat())
                or mac.directories(path.parent, private=True) != parent):
            raise ValueError('Recovery archive identity, checksum or exact inventory differs')
    _anchors(data, metadata, manifest, sources)
    return dict(receipt, verified_result_files=3, verified_bound_files=len(found_files),
        verified_absent_paths=len(data['absent_paths']), private_archive_not_published=True,
        paid_launch_ready=False, full_runtime_restore_exercised=False)
