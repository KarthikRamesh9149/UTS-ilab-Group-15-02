"""Real owned pipes/socket pairs; no native admission or model calls."""
import os
import queue
import socket
import struct
import threading
import time
import unittest
from unittest import mock

import matched_repeat_execution_transport as transport
import matched_repeat_composite_stream as composite
import matched_repeat_stream as wire
import test_matched_repeat_composite_stream as composite_tests


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.patches = [mock.patch.object(transport, 'IDLE_SECONDS', 1),
            mock.patch.object(transport, 'HEARTBEAT_SECONDS', .05)]
        for patch in self.patches: patch.start()
        self.addCleanup(lambda: [patch.stop() for patch in reversed(self.patches)])

    def pair(self):
        left, right = socket.socketpair()
        outgoing = left.makefile('wb', buffering=0)
        incoming = right.makefile('rb', buffering=0)
        left.close(); right.close()
        for item in (outgoing, incoming): self.addCleanup(item.close)
        return outgoing, incoming

    def test_real_pipe_audits_longer_than_idle_window_and_exact_payload(self):
        read_fd, write_fd = os.pipe()
        outgoing = os.fdopen(write_fd, 'wb', buffering=0)
        incoming = os.fdopen(read_fd, 'rb', buffering=0)
        self.addCleanup(outgoing.close); self.addCleanup(incoming.close)
        observed = []; errors = []; payload = bytes(range(256)) * 2048
        def receive():
            try:
                reader = transport.Reader(incoming)
                observed.append(reader.fileno() == incoming.fileno())
                result = bytearray()
                while raw := reader.read(7919): result.extend(raw)
                observed.append(bytes(result)); observed.append(reader.read(1))
            except BaseException as error: errors.append(type(error).__name__)
        worker = threading.Thread(target=receive); worker.start()
        with transport.Writer(outgoing) as writer:
            self.assertEqual(writer.fileno(), outgoing.fileno())
            time.sleep(2.2)  # The synthetic audit stays on this owning thread.
            self.assertEqual(writer.write(payload), len(payload))
            writer.flush(); time.sleep(2.2)
            writer.finish()
            with self.assertRaises(ValueError): writer.write(b'late')
        outgoing.close(); worker.join(2)
        self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])
        self.assertEqual(observed, [True, payload, b''])
        self.assertFalse(writer.thread.is_alive())

    def test_silent_sender_expires(self):
        outgoing, incoming = self.pair()
        outgoing.write(transport.MAGIC)
        with self.assertRaises(TimeoutError): transport.Reader(incoming).read(1)

    def test_failed_sender_never_emits_completion_and_thread_ends(self):
        outgoing, incoming = self.pair()
        with self.assertRaisesRegex(RuntimeError, 'sender'):
            with transport.Writer(outgoing) as writer:
                writer.write(b'partial'); raise RuntimeError('sender')
        self.assertFalse(writer.thread.is_alive())
        # Close the underlying socket as well to give the reader genuine EOF.
        outgoing.close()
        reader = transport.Reader(incoming)
        self.assertEqual(reader.read(7), b'partial')
        with self.assertRaises((ValueError, TimeoutError)): reader.read(1)

    def test_malformed_truncated_and_extra_transport_refuse(self):
        header = lambda kind, size: kind + struct.pack('!I', size)
        cases = [b'wrong', transport.MAGIC, transport.MAGIC + b'D',
            transport.MAGIC + header(b'H', 1) + b'x',
            transport.MAGIC + header(b'D', 0),
            transport.MAGIC + header(b'D', transport.CHUNK + 1),
            transport.MAGIC + header(b'X', 0),
            transport.MAGIC + header(b'E', 1),
            transport.MAGIC + header(b'E', 0) + b'extra']
        for raw in cases:
            with self.subTest(raw=raw):
                read_fd, write_fd = os.pipe()
                with os.fdopen(read_fd, 'rb', buffering=0) as incoming:
                    os.write(write_fd, raw); os.close(write_fd)
                    with self.assertRaises(ValueError): transport.Reader(incoming).read(1)

    def test_completion_needs_real_eof_and_does_not_accept_a_heartbeat(self):
        outgoing, incoming = self.pair()
        outgoing.write(transport.MAGIC + b'H\0\0\0\0' + b'E\0\0\0\0')
        with self.assertRaises(TimeoutError): transport.Reader(incoming).read(1)

    def test_broken_pipe_and_blocked_writer_are_bounded(self):
        read_fd, write_fd = os.pipe(); os.close(read_fd)
        with os.fdopen(write_fd, 'wb', buffering=0) as outgoing:
            with self.assertRaises(BrokenPipeError):
                with transport.Writer(outgoing): pass
        read_fd, write_fd = os.pipe()
        with os.fdopen(write_fd, 'wb', buffering=0) as outgoing:
            try:
                with self.assertRaises(TimeoutError):
                    with transport.Writer(outgoing) as writer:
                        writer.write(b'x' * (transport.CHUNK * 8))
                self.assertFalse(writer.thread.is_alive())
                self.assertTrue(os.get_blocking(outgoing.fileno()))
            finally: os.close(read_fd)

    def test_heartbeat_thread_cannot_write_payload_or_finish(self):
        outgoing, _ = self.pair(); errors = []
        with transport.Writer(outgoing) as writer:
            def misuse():
                for call in (lambda: writer.write(b'forged'), writer.finish):
                    try: call()
                    except ValueError: errors.append(True)
            worker = threading.Thread(target=misuse); worker.start(); worker.join(1)
            self.assertEqual(errors, [True, True]); writer.finish()

    def test_coalesced_readiness_does_not_discard_reverse_prefix(self):
        read_fd, write_fd = os.pipe()
        reply = b'{"ready":true}\n'
        os.write(write_fd, reply + transport.MAGIC + b'D' + struct.pack('!I', len(reply))
            + reply + b'E\0\0\0\0'); os.close(write_fd)
        with os.fdopen(read_fd, 'rb', buffering=0) as stream:
            self.assertEqual(transport.ready_line(stream, 128), reply)
            self.assertEqual(transport.reply_bytes(transport.Reader(stream), 128), reply)

    def test_duplex_backpressure_and_native_validation_longer_than_idle(self):
        in_read, in_write = os.pipe(); out_read, out_write = os.pipe()
        mac_send = os.fdopen(in_write, 'wb', buffering=0)
        relay_read = os.fdopen(in_read, 'rb', buffering=0)
        mac_read = os.fdopen(out_read, 'rb', buffering=0)
        relay_send = os.fdopen(out_write, 'wb', buffering=0)
        peer, native = socket.socketpair(); peer.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        for value in (mac_send, relay_read, mac_read, relay_send, peer, native): self.addCleanup(value.close)
        payload = b'p' * (transport.CHUNK * 16); errors = []; received = []
        def forwarding():
            try: transport.relay(relay_read, relay_send, peer)
            except BaseException as error: errors.append(('relay', type(error).__name__))
            finally: relay_send.close()
        def service():
            try:
                with native.makefile('rb', buffering=0) as source, native.makefile('wb', buffering=0) as destination:
                    with transport.Writer(destination) as writer:
                        reader = transport.Reader(source)
                        result = bytearray(reader.read(1)); time.sleep(2.2)
                        while raw := reader.read(transport.CHUNK): result.extend(raw)
                        received.append(bytes(result)); time.sleep(2.2)
                        ack = transport.Acknowledgement(writer, native)
                        ack.sendall(b'{"accepted":true}\n'); ack.shutdown(socket.SHUT_WR)
            except BaseException as error: errors.append(('service', type(error).__name__))
        workers = [threading.Thread(target=forwarding), threading.Thread(target=service)]
        for worker in workers: worker.start()
        with transport.ReplyReceiver(mac_read, 128) as receiver:
            with transport.Writer(mac_send, peer=receiver) as writer:
                time.sleep(2.2); writer.write(payload); writer.finish()
            mac_send.close()
            self.assertEqual(receiver.wait(), b'{"accepted":true}\n')
        for worker in workers: worker.join(2); self.assertFalse(worker.is_alive())
        self.assertEqual(errors, []); self.assertEqual(received, [payload])
        self.assertFalse(receiver.thread.is_alive()); self.assertFalse(writer.thread.is_alive())

    def test_reply_reader_is_bounded_and_cancelled_on_sender_failure(self):
        outgoing, incoming = self.pair()
        with transport.ReplyReceiver(incoming, 8) as receiver:
            with transport.Writer(outgoing) as writer:
                writer.write(b'123456789'); writer.finish()
            outgoing.close()
            with self.assertRaises(ValueError): receiver.wait()
        self.assertFalse(receiver.thread.is_alive())
        outgoing, incoming = self.pair()
        with transport.ReplyReceiver(incoming, 8) as receiver: pass
        self.assertFalse(receiver.thread.is_alive())

    def test_outer_completion_cannot_replace_actual_inner_composite_commitment(self):
        fixture = composite_tests.CompositeStreamTests(); fixture.setUp()
        for complete in (True, False):
            with self.subTest(inner_complete=complete):
                read_fd, write_fd = os.pipe(); errors = []
                def send():
                    try:
                        with os.fdopen(write_fd, 'wb', buffering=0) as outgoing:
                            with transport.Writer(outgoing) as writer:
                                wire._write(writer, fixture.original)
                                if complete:
                                    composite.finish(writer, fixture.recovery_sha, fixture.sent)
                                writer.finish()
                    except BaseException as error: errors.append(type(error).__name__)
                worker = threading.Thread(target=send); worker.start()
                try:
                    with os.fdopen(read_fd, 'rb', buffering=0) as incoming:
                        frame = composite.original_frame(transport.Reader(incoming), fixture.recovery_sha)
                        self.assertEqual(wire._exact(frame, len(fixture.original)), fixture.original)
                        if complete: self.assertEqual(frame.read(1), b'')
                        else:
                            with self.assertRaises(ValueError): frame.read(1)
                finally:
                    worker.join(2)
                    self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])

    def test_reporting_stream_is_bounded_preserves_bytes_and_survives_slow_producer(self):
        outgoing, incoming = self.pair(); payload = bytes(range(256)) * 4096; errors = []
        def produce():
            try:
                with transport.Writer(outgoing) as writer:
                    time.sleep(2.2); writer.write(payload); time.sleep(2.2); writer.finish()
            except BaseException as error: errors.append(type(error).__name__)
            finally: outgoing.close()
        worker = threading.Thread(target=produce); worker.start()
        with transport.StreamReceiver(incoming) as receiver:
            self.assertEqual(receiver.pending.maxsize, 2)
            self.assertEqual(receiver.fileno(), incoming.fileno())
            actual = bytearray()
            while raw := receiver.read(7919): actual.extend(raw)
            self.assertEqual(bytes(actual), payload)
            self.assertEqual(receiver.read(1), b'')
        worker.join(2); self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])
        self.assertFalse(receiver.thread.is_alive())

    def test_reporting_stream_requires_completion_and_owner_and_cancels_cleanly(self):
        outgoing, incoming = self.pair(); errors = []
        with transport.StreamReceiver(incoming) as receiver:
            def misuse():
                try: receiver.read(1)
                except ValueError: errors.append('owner-refused')
            worker = threading.Thread(target=misuse); worker.start(); worker.join(2)
            self.assertEqual(errors, ['owner-refused'])
            outgoing.write(transport.MAGIC + b'D\0\0\0\1x'); outgoing.close()
            self.assertEqual(receiver.read(1), b'x')
            with self.assertRaises(ValueError): receiver.read(1)
        self.assertFalse(receiver.thread.is_alive())
        outgoing, incoming = self.pair()
        with transport.StreamReceiver(incoming) as receiver: pass
        self.assertFalse(receiver.thread.is_alive())

    def test_final_queued_data_cannot_race_with_completion_and_be_hidden(self):
        _, incoming = self.pair(); receiver = transport.StreamReceiver(incoming)
        # Deterministically reproduce a queue timeout immediately before the
        # producer queues its final bytes and marks itself done. No native work.
        receiver.entered = True; original = receiver.pending.get; calls = []
        def race(*args, **kwargs):
            if not calls:
                calls.append(True); receiver.pending.put_nowait(b'extra'); receiver.done.set()
                raise queue.Empty
            return original(*args, **kwargs)
        with mock.patch.object(receiver.pending, 'get', side_effect=race):
            self.assertEqual(receiver.read(5), b'extra')
            self.assertEqual(receiver.read(1), b'')


if __name__ == '__main__': unittest.main()
