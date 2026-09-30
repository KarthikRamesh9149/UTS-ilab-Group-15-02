"""Read the existing recovery archive from the actual successor transport.

This mirrors the frozen recovery path verifier's member checks without
changing it, extracting files or creating another archive. It consumes exactly
the declared compressed frame. The owning handoff must verify its commitment,
peer, actual fresh audit and subsequent original-final stream separately.
"""
import gzip
import hashlib
import os
import tarfile

import matched_repeat_stream as wire
import no_cutoff_recovery_archive as archive
import no_cutoff_recovery_policy as policy


def verify_stream(stream, data, record, receipt, manifest, sources):
    """Strict actual bytes only; a verified archive is not a live admission."""
    wire.pipe_only(stream)
    descriptor = os.fstat(stream.fileno())
    descriptor_id = (descriptor.st_dev, descriptor.st_ino, descriptor.st_mode)
    archive.report.validate(data, manifest, sources)
    archive.validate_inventory(record, data)
    expected = dict(kind=archive.KIND, sha256=receipt.get('sha256'),
        compressed_bytes=receipt.get('compressed_bytes'), files=len(record['files']),
        bytes=sum(record['sizes'].values()), snapshot_sha256=policy.fingerprint(data),
        inventory_sha256=policy.fingerprint(record))
    policy._same(receipt, expected); policy._hash(receipt['sha256'])
    if type(receipt['compressed_bytes']) is not int or receipt['compressed_bytes'] <= 0:
        raise ValueError('Exact compressed recovery archive size required')
    seen = set(); found_dirs = set(); found_files = set(); metadata = {}
    compressed_source = archive.original_archive._Compressed(stream, receipt['compressed_bytes'])
    try:
        with gzip.GzipFile(fileobj=compressed_source, mode='rb') as compressed:
            with tarfile.open(fileobj=compressed, mode='r|', tarinfo=archive.original_archive._TarInfo) as payload:
                for entry in payload:
                    name = archive._name(entry.name)
                    if (name in seen or entry.issym() or entry.islnk() or entry.sparse is not None
                            or set(entry.pax_headers) - {'path', 'mtime', 'atime', 'ctime'}):
                        raise ValueError('Unsafe, duplicate or linked recovery archive entry')
                    seen.add(name)
                    if entry.isdir():
                        if name not in record['directories'] or entry.mode != 0o700:
                            raise ValueError('Unexpected archive directory')
                        found_dirs.add(name)
                    elif entry.isfile():
                        if (name not in record['files'] or entry.size != record['sizes'][name]
                                or entry.mode != 0o600):
                            raise ValueError('Unexpected recovery archive payload')
                        with payload.extractfile(entry) as contents:
                            if name in {archive.report.RT + n for n in (
                                    *archive.qualification_inputs(), policy.REGISTRATION_FILE)}:
                                if entry.size > archive.files.bootstrap.WINDOW:
                                    raise ValueError('Metadata parser window exceeded')
                                raw = contents.read(); metadata[name] = raw
                                digest = hashlib.sha256(raw).hexdigest()
                            else:
                                digest = hashlib.file_digest(contents, 'sha256').hexdigest()
                        policy._same(digest, record['files'][name]); found_files.add(name)
                    else:
                        raise ValueError('Special recovery archive entry refused')
                padding = 0
                while tail := payload.fileobj.read(archive.CHUNK):
                    if tail.strip(b'\0'):
                        raise ValueError('Hidden nonpadding data after tar end marker')
                    padding += len(tail)
                if padding < tarfile.BLOCKSIZE:
                    raise ValueError('Complete tar end markers required')
            if compressed.read(archive.CHUNK):
                raise ValueError('Extra decompressed archive payload')
    except (OSError, EOFError, tarfile.TarError):
        raise ValueError('Incomplete or corrupt streamed recovery archive') from None
    after = os.fstat(stream.fileno())
    if (compressed_source.remaining or compressed_source.digest.hexdigest() != receipt['sha256']
            or found_dirs != set(record['directories']) or found_files != set(record['files'])
            or (after.st_dev, after.st_ino, after.st_mode) != descriptor_id):
        raise ValueError('Recovery stream identity, checksum or exact inventory differs')
    archive._anchors(data, metadata, manifest, sources)
    return dict(receipt, verified_result_files=3, verified_bound_files=len(found_files),
        verified_absent_paths=len(data['absent_paths']), private_archive_not_published=True,
        paid_launch_ready=False, full_runtime_restore_exercised=False)
