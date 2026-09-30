"""Real synthetic three-result archive and pipes; native audit facts mocked."""
from contextlib import contextmanager
from copy import deepcopy
import gzip
import hashlib
import io
import os
import tarfile
import threading
import unittest

import matched_repeat_recovery_archive as stream_archive
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_reporting import ReportingTests


class RecoveryArchiveStreamTests(LocalFiles, unittest.IsolatedAsyncioTestCase):
    setUp = ReportingTests.setUp
    produce = ReportingTests.produce
    collect = ReportingTests.collect
    packed = ReportingTests.packed

    @contextmanager
    def stream(self, raw):
        read, write = os.pipe(); incoming = os.fdopen(read, 'rb')
        outgoing = os.fdopen(write, 'wb', buffering=0); errors = []
        def send():
            try:
                with outgoing: stream_archive.wire._write(outgoing, raw)
            except BrokenPipeError: pass
            except BaseException as error: errors.append(error)
        worker = threading.Thread(target=send); worker.start()
        try: yield incoming
        finally:
            incoming.close(); worker.join(5)
            self.assertFalse(worker.is_alive()); self.assertFalse(errors)

    async def fixture(self):
        await self.produce(); data, _ = self.collect()
        path, record, _, receipt = self.packed(data)
        return path, data, record, receipt

    def verify(self, incoming, data, record, receipt):
        return stream_archive.verify_stream(incoming,data,record,receipt,self.f.manifest,self.sources)

    async def test_real_stream_matches_unchanged_path_verifier_and_leaves_next_frame(self):
        path,data,record,receipt = await self.fixture()
        expected = stream_archive.archive.verify(path,data,record,receipt,self.f.manifest,self.sources)
        tail = b'commit-and-next-original-archive-frame'
        with self.stream(path.read_bytes()+tail) as incoming:
            actual = self.verify(incoming,data,record,receipt)
            self.assertEqual(actual,expected); self.assertEqual(incoming.read(),tail)
            self.assertEqual(actual['verified_result_files'],3)
            self.assertFalse(actual['paid_launch_ready'])

    async def test_saved_buffer_is_not_live_transport(self):
        path,data,record,receipt = await self.fixture()
        with self.assertRaises(ValueError): self.verify(io.BytesIO(path.read_bytes()),data,record,receipt)

    async def test_corruption_and_truncation_refuse(self):
        path,data,record,receipt = await self.fixture(); raw=path.read_bytes()
        for changed in (raw[:-1],bytes([raw[0]^1])+raw[1:]):
            with self.subTest(length=len(changed)), self.stream(changed) as incoming:
                with self.assertRaises(ValueError): self.verify(incoming,data,record,receipt)

    async def test_declared_size_and_hash_cannot_hide_missing_bytes(self):
        path,data,record,receipt = await self.fixture()
        for field,value in (('compressed_bytes',True),('compressed_bytes',receipt['compressed_bytes']+1),
                ('sha256','0'*64)):
            changed=dict(receipt,**{field:value})
            with self.subTest(field=field),self.stream(path.read_bytes()) as incoming:
                with self.assertRaises(ValueError): self.verify(incoming,data,record,changed)

    async def test_duplicate_member_refuses_even_with_updated_compressed_receipt(self):
        path,data,record,receipt = await self.fixture(); target=io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(path.read_bytes()),mode='r:gz') as source:
            members=source.getmembers()
            with tarfile.open(fileobj=target,mode='w:gz') as output:
                for item in members+[members[0]]:
                    output.addfile(item,source.extractfile(item) if item.isfile() else None)
        raw=target.getvalue(); changed=dict(receipt,sha256=hashlib.sha256(raw).hexdigest(),compressed_bytes=len(raw))
        with self.stream(raw) as incoming:
            with self.assertRaises(ValueError): self.verify(incoming,data,record,changed)

    async def test_hidden_tar_payload_refuses_even_with_updated_receipt(self):
        path,data,record,receipt = await self.fixture()
        raw=gzip.compress(gzip.decompress(path.read_bytes())+b'not-padding')
        changed=dict(receipt,sha256=hashlib.sha256(raw).hexdigest(),compressed_bytes=len(raw))
        with self.stream(raw) as incoming:
            with self.assertRaises(ValueError): self.verify(incoming,data,record,changed)

    async def test_missing_outcome_and_source_metadata_cannot_be_replaced_by_receipt(self):
        path,data,record,receipt = await self.fixture()
        for altered in ('row','source'):
            changed=deepcopy(data)
            if altered=='row': changed['rows'].pop()
            else: changed['sources'][next(iter(changed['sources']))]='0'*64
            with self.subTest(altered=altered),self.stream(path.read_bytes()) as incoming:
                with self.assertRaises(ValueError): self.verify(incoming,changed,record,receipt)
