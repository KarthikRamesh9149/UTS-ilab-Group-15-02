"""Private predecessor archive framing; no files, extraction or paid admission.

The archive is the existing off-server backup, not a newly made archive. Both
ends hash the compressed bytes, and the receiver reads every bound tar member.
The final marker is sent only after the operator's post-transfer file recheck.
The metadata limit is a transport/parser bound, never a benchmark task limit.
"""
import gzip
import hashlib
import json
import os
from pathlib import PurePosixPath
import stat
import struct
import tarfile

MAGIC = b'UTS-MATCHED-PREDECESSOR-V1\n'
COMMIT = b'UTS-MATCHED-PREDECESSOR-COMMIT-V1\n'
METADATA_LIMIT = 64 * 1024 * 1024
CHUNK = 64 * 1024


def pipe_only(stream):
    """Check descriptor type, not peer identity; the caller authenticates SSH.

    No archive pathname, regular file or terminal may masquerade as a pipe.
    """
    try:
        mode = os.fstat(stream.fileno()).st_mode
    except (AttributeError, OSError, ValueError):
        raise ValueError('A live operator transport pipe is required') from None
    if not (stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)):
        raise ValueError('A live operator transport pipe is required')


def _exact(stream, size):
    pieces = []
    while size:
        piece = stream.read(min(size, CHUNK))
        if not isinstance(piece, bytes) or not piece or len(piece) > size:
            raise ValueError('Incomplete private predecessor transfer')
        pieces.append(piece); size -= len(piece)
    return b''.join(pieces)


def _write(stream, raw):
    pending = memoryview(raw)
    while pending:
        count = stream.write(pending)
        if type(count) is not int or count <= 0 or count > len(pending):
            raise ValueError('Private predecessor transport did not accept bytes')
        pending = pending[count:]


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate predecessor metadata key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Non-finite predecessor metadata value')


def loads(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, TypeError, ValueError):
        raise ValueError('Invalid private predecessor metadata') from None
    if not isinstance(value, dict):
        raise ValueError('Object predecessor metadata required')
    return value


def write_header(stream, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > METADATA_LIMIT:
        raise ValueError('Predecessor metadata exceeds the transport parser window')
    _write(stream, MAGIC + struct.pack('!Q', len(raw)) + raw)
    return hashlib.sha256(raw).digest()


def read_header(stream):
    if _exact(stream, len(MAGIC)) != MAGIC:
        raise ValueError('Exact live predecessor transfer format required')
    size = struct.unpack('!Q', _exact(stream, 8))[0]
    if not 0 < size <= METADATA_LIMIT:
        raise ValueError('Invalid predecessor metadata transport length')
    raw = _exact(stream, size)
    return loads(raw), hashlib.sha256(raw).digest()


def copy_archive(source, destination, size, expected_sha256):
    """One bounded-buffer read of existing bytes, not archive creation."""
    if type(size) is not int or size <= 0:
        raise ValueError('Exact compressed archive length required')
    digest = hashlib.sha256(); remaining = size
    while remaining:
        raw = _exact(source, min(CHUNK, remaining))
        digest.update(raw); _write(destination, raw); remaining -= len(raw)
    if source.read(1) or digest.hexdigest() != expected_sha256:
        raise ValueError('Existing off-server archive changed during transfer')


def commit(stream, header_digest, archive_sha256):
    _write(stream, COMMIT + header_digest + bytes.fromhex(archive_sha256))
    stream.flush()


class _Compressed:
    def __init__(self, stream, size):
        self.stream, self.remaining = stream, size
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        if not self.remaining:
            return b''
        count = min(self.remaining, CHUNK, size if size >= 0 else CHUNK)
        if count == 0:
            return b''
        raw = _exact(self.stream, count)
        self.remaining -= len(raw); self.digest.update(raw)
        return raw


def verify_archive(stream, expected, backup, excluded, restore_note, result_count, header_digest):
    """Streaming equivalent of the frozen verifier, with no extraction/write.

    The caller independently validates the snapshot and exact receipt schema.
    Only paths/hashes/counts are returned; no private archive contents escape.
    """
    size = backup.get('compressed_bytes')
    if type(size) is not int or size <= 0:
        raise ValueError('Exact nonempty compressed archive length required')
    source = _Compressed(stream, size)
    names, seen = set(), set()
    files = unpacked = 0
    try:
        with gzip.GzipFile(fileobj=source, mode='rb') as compressed:
            with tarfile.open(fileobj=compressed, mode='r|') as archive:
                for member in archive:
                    parts = PurePosixPath(member.name).parts
                    if (member.name.startswith('/') or '..' in parts or member.name in names
                            or member.issym() or member.islnk() or any(p in excluded for p in parts)
                            or not (member.isfile() or member.isdir())):
                        raise ValueError('Unsafe, duplicate or credential-bearing archive member')
                    names.add(member.name)
                    if member.isfile():
                        files += 1; unpacked += member.size
                        with archive.extractfile(member) as contents:
                            digest = hashlib.file_digest(contents, 'sha256').hexdigest()
                        if member.name in expected:
                            if digest != expected[member.name]:
                                raise ValueError('Streamed archived evidence binding changed')
                            seen.add(member.name)
                    elif member.name in expected:
                        raise ValueError('Bound archived evidence is not a regular file')
            # Read through the gzip trailer, including any buffered bytes.
            while compressed.read(CHUNK):
                pass
    except (OSError, EOFError, tarfile.TarError):
        raise ValueError('Invalid or incomplete compressed predecessor archive') from None
    if (source.remaining or source.digest.hexdigest() != backup['sha256']
            or seen != set(expected) or files != backup['files'] or unpacked != backup['bytes']):
        raise ValueError('Streamed archive differs from the verified complete backup')
    trailer = COMMIT + header_digest + bytes.fromhex(backup['sha256'])
    if _exact(stream, len(trailer)) != trailer or stream.read(1):
        raise ValueError('Missing operator post-transfer commitment or extra transfer bytes')
    verified = dict(sha256=backup['sha256'], files=files, bytes=unpacked, excluded=backup['excluded'],
        compressed_bytes=size, verified_result_files=result_count, verified_bound_files=len(seen),
        private_archive_not_published=True, restore_test=restore_note)
    if verified != backup:
        raise ValueError('Streamed archive receipt differs from the retained backup record')
    return verified
