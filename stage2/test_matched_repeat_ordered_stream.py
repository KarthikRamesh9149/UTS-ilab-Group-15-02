"""Actual local pipes and framing; no native audit, archive or model call."""
import io
import os
import threading
import unittest

import matched_repeat_ordered_stream as ordered
import matched_repeat_stream as wire


class OrderedStreamTests(unittest.TestCase):
    def pipe(self):
        read, write = os.pipe()
        incoming = os.fdopen(read, 'rb'); outgoing = os.fdopen(write, 'wb', buffering=0)
        self.addCleanup(incoming.close); self.addCleanup(outgoing.close)
        return incoming, outgoing

    def test_actual_sender_audit_must_finish_before_the_original_reader_is_entered(self):
        incoming, outgoing = self.pipe(); audited = threading.Event(); entered = threading.Event()
        header = {'raw_snapshot':'{"number":1.0,"missing":null}', 'native_qualification':False}
        errors = []
        def sender():
            try:
                self.assertFalse(entered.is_set())
                audited.set()  # Represents completion of the separately mocked audit.
                digest = wire.write_header(outgoing, header)
                wire.commit(outgoing, digest, 'a'*64); outgoing.close()
            except BaseException as error: errors.append(error)
        worker = threading.Thread(target=sender); worker.start()
        stream = ordered.wait_for_sender(incoming)
        self.assertTrue(audited.is_set()); entered.set()
        self.assertEqual(stream.read(0), b'')
        actual, digest = wire.read_header(stream); self.assertEqual(actual, header)
        self.assertEqual(stream.read(), wire.COMMIT+digest+bytes.fromhex('a'*64))
        self.assertEqual(stream.read(1), b'')
        worker.join(2); self.assertFalse(worker.is_alive()); self.assertFalse(errors)

    def test_regular_saved_buffer_never_counts_as_a_live_handoff(self):
        with self.assertRaises(ValueError): ordered.wait_for_sender(io.BytesIO(wire.MAGIC))

    def test_empty_wrong_or_partial_header_still_refuses(self):
        for raw in (b'', b'x', wire.MAGIC[:1]):
            with self.subTest(raw=raw):
                incoming, outgoing = self.pipe(); outgoing.write(raw); outgoing.close()
                with self.assertRaises(ValueError): wire.read_header(ordered.wait_for_sender(incoming))

    def test_exact_prefix_is_returned_only_once_and_underlying_descriptor_is_unchanged(self):
        incoming, outgoing = self.pipe(); outgoing.write(wire.MAGIC); outgoing.close()
        stream = ordered.wait_for_sender(incoming)
        self.assertEqual(stream.fileno(), incoming.fileno())
        self.assertEqual(stream.read(1), wire.MAGIC[:1])
        self.assertEqual(stream.read(), wire.MAGIC[1:])
        incoming.close()
        with self.assertRaises((ValueError, OSError)): stream.read(1)
