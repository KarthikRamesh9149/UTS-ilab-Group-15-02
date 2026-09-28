"""Real in-memory archive/pipe checks; no native or provider execution."""
import hashlib
import io
import os
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

import export_no_cutoff_final as exporter
import matched_repeat_stream as wire


def archive_bytes(members):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, content, kind in members:
            member = tarfile.TarInfo(name); member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = len(content)
            elif kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                member.linkname = 'elsewhere'
            archive.addfile(member, io.BytesIO(content) if member.isfile() else None)
    return stream.getvalue()


class ShortIO(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 7) if size >= 0 else 7)

    def write(self, raw):
        return super().write(raw[:11])


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.name = '.runtime/stage2/scored-trials/synthetic/result.json'
        self.content = b'{"reward":null,"phase_seconds":1.0}'
        self.members = [(self.name, self.content, tarfile.REGTYPE),
            ('stage2/synthetic.py', b'# source', tarfile.REGTYPE)]
        self.raw = archive_bytes(self.members)
        self.expected = {name: hashlib.sha256(content).hexdigest() for name, content, _ in self.members}
        self.backup = self.receipt(self.raw, self.members)

    def receipt(self, raw, members):
        files = [m for m in members if m[2] == tarfile.REGTYPE]
        return dict(sha256=hashlib.sha256(raw).hexdigest(), files=len(files),
            bytes=sum(len(m[1]) for m in files), excluded=0, compressed_bytes=len(raw),
            verified_result_files=1, verified_bound_files=len(self.expected),
            private_archive_not_published=True, restore_test=exporter.RESTORE_NOTE)

    def packet(self, *, raw=None, backup=None, header=None, stream=None):
        raw = self.raw if raw is None else raw; backup = self.backup if backup is None else backup
        out = stream if stream is not None else io.BytesIO()
        header_digest = wire.write_header(out, header or {'exact': 1.0, 'unknown': None})
        wire.copy_archive(io.BytesIO(raw), out, len(raw), backup['sha256'])
        wire.commit(out, header_digest, backup['sha256'])
        out.seek(0)
        return out

    def verify(self, stream, backup=None):
        header, header_digest = wire.read_header(stream)
        value = wire.verify_archive(stream, self.expected, backup or self.backup,
            exporter.EXCLUDED, exporter.RESTORE_NOTE, 1, header_digest)
        return header, value

    def test_stream_verifier_matches_unchanged_qualified_path_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'archive.tar.gz'; path.write_bytes(self.raw)
            data = dict(bindings=self.expected, sources={}, rows=[dict(trial_id='synthetic',
                result_sha256=self.expected[self.name])])
            receipt = {k: self.backup[k] for k in exporter.RECEIPT_FIELDS}
            expected = exporter.verify_archive(path, data, receipt)
        header, actual = self.verify(self.packet())
        self.assertEqual(actual, expected); self.assertIs(type(header['exact']), float)
        self.assertIsNone(header['unknown'])

    def test_short_reads_and_short_writes_preserve_all_bytes(self):
        packet = self.packet(stream=ShortIO())
        _, actual = self.verify(packet)
        self.assertEqual(actual, self.backup)

    def test_real_pipe_accepted_and_regular_file_or_memory_refused(self):
        incoming, outgoing = os.pipe()
        with os.fdopen(incoming, 'rb') as reader, os.fdopen(outgoing, 'wb') as writer:
            wire.pipe_only(reader); wire.pipe_only(writer)
        with tempfile.TemporaryFile('w+b') as regular:
            with self.assertRaises(ValueError): wire.pipe_only(regular)
        with self.assertRaises(ValueError): wire.pipe_only(io.BytesIO())

    def test_saved_json_is_not_a_live_transfer(self):
        with self.assertRaises(ValueError): wire.read_header(io.BytesIO(b'{"checks":true}'))

    def test_metadata_schema_rejects_duplicate_nonfinite_and_nonobject_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'[]', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): wire.loads(raw)

    def test_metadata_window_checked_before_reading_payload(self):
        for size in (0, wire.METADATA_LIMIT + 1):
            stream = io.BytesIO(wire.MAGIC + struct.pack('!Q', size))
            with self.assertRaises(ValueError): wire.read_header(stream)

    def test_changed_member_rejected_even_with_matching_whole_archive_checksum(self):
        members = [(self.name, b'changed private result', tarfile.REGTYPE), self.members[1]]
        raw = archive_bytes(members); backup = self.receipt(raw, members)
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            self.verify(self.packet(raw=raw, backup=backup), backup)

    def test_unsafe_duplicate_link_device_and_secret_members_refused(self):
        for name, kind in (('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                (self.name, tarfile.REGTYPE), ('link', tarfile.SYMTYPE), ('hard', tarfile.LNKTYPE),
                ('device', tarfile.CHRTYPE), ('dir/.env', tarfile.REGTYPE)):
            members = self.members + [(name, b'secret fixture', kind)]
            raw = archive_bytes(members); backup = self.receipt(raw, members)
            with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                self.verify(self.packet(raw=raw, backup=backup), backup)

    def test_missing_bound_member_or_directory_instead_of_file_refused(self):
        for members in (self.members[1:], [(self.name, b'', tarfile.DIRTYPE), self.members[1]]):
            raw = archive_bytes(members); backup = self.receipt(raw, members)
            with self.assertRaises(ValueError): self.verify(self.packet(raw=raw, backup=backup), backup)

    def test_wrong_counts_and_verification_flags_do_not_override_bytes(self):
        for key, value in (('files', 99), ('bytes', 0), ('verified_bound_files', 0),
                ('verified_result_files', 0), ('private_archive_not_published', False), ('restore_test', 'restored')):
            backup = dict(self.backup, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(self.packet(), backup)

    def test_whole_compressed_checksum_is_required(self):
        backup = dict(self.backup, sha256='0' * 64)
        with self.assertRaises(ValueError): self.verify(self.packet(), backup)

    def test_incomplete_gzip_and_wrong_compressed_length_refused(self):
        for raw in (self.raw[:20], self.raw[:-10], b'not gzip'):
            backup = dict(self.backup, compressed_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                self.verify(self.packet(raw=raw, backup=backup), backup)
        for size in (True, 0, len(self.raw) - 1, len(self.raw) + 1):
            with self.subTest(size=size), self.assertRaises(ValueError):
                self.verify(self.packet(), dict(self.backup, compressed_bytes=size))

    def test_missing_commitment_or_extra_bytes_refused(self):
        raw = self.packet().getvalue()
        for altered in (raw[:-1], raw + b'extra', raw[:-64] + b'X' * 64):
            with self.assertRaises(ValueError): self.verify(io.BytesIO(altered))

    def test_changed_header_digest_refused(self):
        raw = self.packet().getvalue().replace(b'"exact":1.0', b'"exact":2.0')
        with self.assertRaises(ValueError): self.verify(io.BytesIO(raw))

    def test_transfer_does_not_accept_changed_or_extra_source_bytes(self):
        for source in (self.raw + b'extra', self.raw[:-1], b'X' * len(self.raw)):
            with self.assertRaises(ValueError):
                wire.copy_archive(io.BytesIO(source), io.BytesIO(), len(self.raw), self.backup['sha256'])

    def test_no_extract_or_file_write_required_by_verifier(self):
        from unittest.mock import patch
        with (patch('builtins.open', side_effect=AssertionError('No verifier filesystem I/O')),
                patch.object(tarfile.TarFile, 'extract', side_effect=AssertionError('No extraction'))):
            _, value = self.verify(self.packet())
        self.assertEqual(value, self.backup)


if __name__ == '__main__':
    unittest.main()
