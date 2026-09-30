"""Real local pipes; no native service, provider or historical archive access."""
import hashlib
import io
import json
import os
import struct
import threading
import unittest

import matched_repeat_composite_stream as composite
import matched_repeat_stream as wire


class CompositeStreamTests(unittest.TestCase):
    def setUp(self):
        self.payload = b'unchanged original archive frame'
        self.archive_sha = hashlib.sha256(self.payload).hexdigest()
        self.document = {'nullable': None, 'sampling': 1.0, 'text': '\u03bb'}
        self.document_sha = hashlib.sha256(json.dumps(self.document, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.recovery_sha = 'a' * 64
        self.header = {'operator': self.document, 'snapshot': '{"nullable":null,"sampling":1.0}',
            'backup': json.dumps({'receipt': {'compressed_bytes': len(self.payload),
                'sha256': self.archive_sha}})}
        stream = io.BytesIO()
        digest = wire.write_header(stream, self.header)
        wire._write(stream, self.payload)
        wire.commit(stream, digest, self.archive_sha)
        self.original = stream.getvalue()
        self.footer = (composite.END + bytes.fromhex(self.recovery_sha)
            + bytes.fromhex(self.document_sha) + bytes.fromhex(self.archive_sha))
        self.sent = dict(kind='amended_off_server_predecessor_bytes_sent_not_admission',
            operator_document_sha256=self.document_sha, archive_sha256=self.archive_sha,
            paid_launch_ready=False)

    def pipe(self, raw, callback):
        read_fd, write_fd = os.pipe()
        errors = []
        def write():
            try:
                with os.fdopen(write_fd, 'wb', buffering=0) as stream:
                    wire._write(stream, raw)
            except BrokenPipeError:
                pass  # The negative-test reader intentionally refuses early.
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=write)
        thread.start()
        try:
            with os.fdopen(read_fd, 'rb', buffering=0) as stream:
                return callback(stream)
        finally:
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])

    def consume(self, stream):
        frame = composite.original_frame(stream, self.recovery_sha)
        wire.pipe_only(frame)
        self.assertEqual(frame.read(0), b'')
        raw = wire._exact(frame, len(self.original))
        self.assertEqual(raw, self.original)
        self.assertEqual(frame.read(1), b'')
        self.assertEqual(frame.read(1), b'')
        return raw

    def test_exact_original_raw_bytes_nulls_floats_and_eof_are_preserved(self):
        self.assertEqual(self.pipe(self.original + self.footer, self.consume), self.original)

    def test_original_eof_waits_for_real_outer_commit_and_transport_eof(self):
        r, w = os.pipe()
        before_footer = threading.Event()
        read_started = threading.Event()
        released = threading.Event()
        errors = []
        def write():
            try:
                with os.fdopen(w, 'wb', buffering=0) as outgoing:
                    wire._write(outgoing, self.original)
                    self.assertTrue(before_footer.wait(5))
                    self.assertTrue(read_started.wait(5))
                    composite.finish(outgoing, self.recovery_sha, self.sent)
                    released.set()
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=write)
        thread.start()
        try:
            with os.fdopen(r, 'rb', buffering=0) as incoming:
                frame = composite.original_frame(incoming, self.recovery_sha)
                self.assertEqual(wire._exact(frame, len(self.original)), self.original)
                self.assertFalse(released.is_set())
                before_footer.set(); read_started.set()
                self.assertEqual(frame.read(1), b'')
                self.assertTrue(released.is_set())
        finally:
            before_footer.set(); read_started.set(); thread.join(5)
            self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])

    def test_missing_changed_truncated_or_extra_final_commit_refuses_eof(self):
        for tail in (b'', self.footer[:-1], self.footer[:-1] + b'X', self.footer + b'extra'):
            with self.subTest(tail=len(tail)), self.assertRaises(ValueError):
                self.pipe(self.original + tail, self.consume)

    def test_all_three_bound_hashes_are_required(self):
        for offset in (len(composite.END), len(composite.END) + 32, len(composite.END) + 64):
            tail = bytearray(self.footer); tail[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.pipe(self.original + bytes(tail), self.consume)

    def test_truncated_original_body_cannot_be_completed_by_footer(self):
        with self.assertRaises(ValueError):
            self.pipe(self.original[:-1] + self.footer,
                lambda s: wire._exact(composite.original_frame(s, self.recovery_sha),
                    len(self.original) + 1))

    def test_saved_regular_buffer_cannot_replace_actual_pipe(self):
        with self.assertRaises(ValueError):
            composite.original_frame(io.BytesIO(self.original + self.footer), self.recovery_sha)
        with self.assertRaises(ValueError):
            composite.finish(io.BytesIO(), self.recovery_sha, self.sent)

    def test_invalid_headers_and_size_types_refuse(self):
        raw_headers = [b'{}', b'{"operator":{},"operator":{},"backup":"{}"}',
            json.dumps(dict(self.header, backup='{"receipt":null}')).encode(),
            json.dumps(dict(self.header, backup='{"receipt":{"compressed_bytes":true}}')).encode(),
            json.dumps(dict(self.header, backup='{"receipt":{"compressed_bytes":0}}')).encode()]
        for raw in raw_headers:
            framed = wire.MAGIC + struct.pack('!Q', len(raw)) + raw
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.pipe(framed, lambda s: composite.original_frame(s, self.recovery_sha))
        for prefix in (b'wrong', wire.MAGIC + struct.pack('!Q', 0),
                wire.MAGIC + struct.pack('!Q', wire.METADATA_LIMIT + 1)):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                self.pipe(prefix, lambda s: composite.original_frame(s, self.recovery_sha))

    def test_sender_requires_exact_real_original_completion_shape(self):
        for value in (dict(self.sent, paid_launch_ready=True), dict(self.sent, extra=True),
                dict(self.sent, kind='saved'), dict(self.sent, archive_sha256='x'), None):
            r, w = os.pipe()
            try:
                with os.fdopen(w, 'wb', buffering=0) as stream, self.assertRaises(ValueError):
                    composite.finish(stream, self.recovery_sha, value)
            finally:
                os.close(r)

    def test_closed_descriptor_and_invalid_read_size_refuse(self):
        def check(stream):
            frame = composite.original_frame(stream, self.recovery_sha)
            with self.assertRaises(ValueError): frame.read(True)
            stream.close()
            with self.assertRaises(ValueError): frame.read(1)
        self.pipe(self.original + self.footer, check)


if __name__ == '__main__':
    unittest.main()
