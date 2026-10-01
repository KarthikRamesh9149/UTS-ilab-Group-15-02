"""Real pipes and synthetic archive/state tests; native host facts are mocked."""
from contextlib import contextmanager
import gzip
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import zlib

import no_cutoff_recovery_reporting_repair as repair
import no_cutoff_recovery_reporting_transport as wire
import no_cutoff_recovery_reporting as frozen
import test_no_cutoff_recovery_reporting as fixture
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save


def failed_native_fixture(case, root):
    records = {'intent.json': {'synthetic_failed_intent': True},
        'result.json': {'synthetic_pre_exit_receipt': True},
        'failure.json': dict(status='failed_or_uncertain_preserve_evidence',
            automatic_resume=False, paid_launch_ready=False)}
    pins = {}
    for name, value in records.items():
        raw = json.dumps(value, sort_keys=True).encode()
        save(root, repair.FAILED_NATIVE+'/'+name, raw)
        pins[name] = hashlib.sha256(raw).hexdigest()
    case.enterContext(patch.object(repair, 'FAILED_NATIVE_FILES', pins))
    return pins


class TransportTests(unittest.TestCase):
    @contextmanager
    def pipe(self, send):
        read, write = os.pipe(); errors = []
        def sender():
            try:
                with os.fdopen(write, 'wb', buffering=0) as stream: send(stream)
            except BrokenPipeError: pass
            except BaseException as error: errors.append(type(error).__name__)
        thread = threading.Thread(target=sender); thread.start()
        try:
            with os.fdopen(read, 'rb', buffering=0) as stream: yield stream
        finally:
            thread.join(5); self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])

    def test_real_pipe_heartbeats_extend_idle_window_but_never_mean_completion(self):
        def send(stream):
            output = wire.Writer(stream).start()
            try:
                time.sleep(0.35)
                output.write(b'actual payload'); output.finish()
            finally: output.close_heartbeat()
        with patch.object(wire, 'IDLE_SECONDS', 0.18), patch.object(wire, 'HEARTBEAT_SECONDS', 0.03), self.pipe(send) as stream:
            reader = wire.Reader(stream)
            self.assertEqual(reader.exact(14), b'actual payload'); reader.finish()
            self.assertEqual(stream.read(), b'')

    def test_unresponsive_real_pipe_times_out_without_signalling_sender(self):
        def send(stream):
            stream.write(wire.MAGIC); time.sleep(0.1)
        with patch.object(wire, 'IDLE_SECONDS', 0.03), self.pipe(send) as stream:
            with self.assertRaises(TimeoutError): wire.Reader(stream).exact(1)

    def test_real_buffered_gzip_trailer_is_visible_before_final_audit_or_finish(self):
        sink = io.BytesIO(); buffered = io.BufferedWriter(sink)
        output = wire.Writer(buffered).start()
        try:
            framed = frozen.archive.framing._Framed(output)
            with gzip.GzipFile(fileobj=framed, mode='wb', mtime=0) as compressed:
                compressed.write(b'unchanged actual packer framing' * 1000)
            raw = sink.getvalue(); self.assertTrue(raw.startswith(wire.MAGIC))
            packets = io.BytesIO(raw[len(wire.MAGIC):]); inner = bytearray()
            while header := packets.read(5):
                tag, count = header[:1], struct.unpack('!I', header[1:])[0]
                value = packets.read(count)
                if tag == b'D': inner.extend(value)
                else: self.assertEqual(tag, b'H')
            frames = io.BytesIO(inner); payload = bytearray()
            while header := frames.read(8): payload.extend(frames.read(struct.unpack('!Q', header)[0]))
            decoded = zlib.decompressobj(31); decoded.decompress(payload)
            self.assertTrue(decoded.eof); self.assertFalse(decoded.unused_data)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), framed.digest.hexdigest())
            self.assertFalse(output.finished)
        finally: output.close_heartbeat()

    def test_failures_are_bounded_and_cannot_be_completion(self):
        def send(stream):
            output = wire.Writer(stream).start()
            output.fail(wire.diagnostic('session_exit', ValueError('private task or model text')))
        with self.pipe(send) as stream:
            with self.assertRaises(wire.NativeFailure) as caught: wire.Reader(stream).exact(1)
        self.assertEqual(caught.exception.diagnostic, dict(stage='session_exit', error_class='ValueError'))
        self.assertNotIn('private', str(caught.exception))
        self.assertEqual(wire.diagnostic('audit', type('SecretType', (Exception,), {})())['error_class'], 'OtherError')

    def test_truncation_early_finish_oversize_duplicate_and_extra_frames_refuse(self):
        def frame(tag, raw=b''): return tag+struct.pack('!I', len(raw))+raw
        cases = [b'', frame(b'E'), b'D'+struct.pack('!I', wire.CHUNK+1), frame(b'X'),
            frame(b'F', b'{"stage":"audit","stage":"audit","error_class":"ValueError"}'),
            frame(b'F', b'{"stage":"audit","error_class":"ValueError","message":"secret"}')]
        for raw in cases:
            with self.subTest(raw=raw[:8]), self.pipe(lambda s:s.write(wire.MAGIC+raw)) as stream:
                with self.assertRaises((ValueError, EOFError)): wire.Reader(stream).exact(1)
        with self.pipe(lambda s:s.write(wire.MAGIC+frame(b'D', b'ab')+frame(b'E'))) as stream:
            reader=wire.Reader(stream); self.assertEqual(reader.exact(1), b'a')
            with self.assertRaises(ValueError): reader.finish()

    def test_writer_partial_write_zero_and_restart_refuse(self):
        with self.assertRaises(BrokenPipeError): wire.Writer(NS(write=lambda raw:0,flush=lambda:None)).start()
        out=wire.Writer(io.BytesIO()).start();out.finish()
        with self.assertRaises(ValueError):out.start()
        with self.assertRaises(BrokenPipeError):out.write(b'after')


class NativeRepairTests(LocalFiles, unittest.IsolatedAsyncioTestCase):
    setUp = fixture.ReportingTests.setUp
    produce = fixture.ReportingTests.produce
    collect = fixture.ReportingTests.collect
    packed = fixture.ReportingTests.packed

    async def setup_native(self, exit_error=False):
        await self.produce()
        failed_native_fixture(self, self.root)
        self.preserved = repair.preserved_native()
        self.payloads = {n: (Path(__file__).parent/n).read_bytes() for n in repair.SOURCE_NAMES}
        self.reporting_sources = {n:hashlib.sha256(v).hexdigest() for n,v in self.payloads.items()}
        self.output = io.BytesIO(); read, write = os.pipe(); os.close(write)
        incoming = self.enterContext(os.fdopen(read,'rb',buffering=0))
        self.enterContext(patch.object(repair, 'WIRE', wire, create=True))
        self.enterContext(patch.object(repair, 'no_other_processes'))
        self.enterContext(patch.object(frozen.boot, 'check', side_effect=lambda bound,*args:fixture.files.capture(self.root,bound)[1]))
        self.enterContext(patch.object(frozen.service, 'loaded'))
        self.enterContext(patch.object(frozen.handoff, '_live', return_value={'header':{'operator':{'operator_commit':'a'*40}}}))
        self.enterContext(patch.object(sys, 'stdin', NS(buffer=incoming)))
        self.enterContext(patch.object(sys, '__stdout__', NS(buffer=self.output)))
        @contextmanager
        def session(stream):
            yield object()
            self.assertFalse((self.root/repair.NATIVE_BACKUP/'result.json').exists())
            if exit_error: raise ValueError('private final check failure')
        self.enterContext(patch.object(frozen.session, 'open_session', side_effect=session))

    async def test_fresh_audits_normal_exit_then_new_result_old_failure_unchanged(self):
        await self.setup_native()
        with patch.object(frozen.report, 'collect', wraps=frozen.report.collect) as collect:
            await repair.native(self.bound, 'a'*40, 'backup', self.reporting_sources, self.payloads)
        self.assertEqual(collect.call_count, 2)
        receipt=frozen.boot.loads(frozen.boot.raw(self.root,repair.NATIVE_BACKUP+'/result.json')[0])
        receipt={n:v for n,v in receipt.items() if n not in ('automatic_resume','paid_launch_ready')}
        repair.retained_native(self.bound,'a'*40,self.reporting_sources,receipt)
        self.assertEqual(repair.preserved_native(),self.preserved)
        self.assertTrue(self.output.getvalue().endswith(b'E'+bytes(4)))
        with self.assertRaises(ValueError):
            await repair.native(self.bound,'a'*40,'backup',self.reporting_sources,self.payloads)

    async def test_actual_session_exit_failure_has_no_success_result_or_commit(self):
        await self.setup_native(exit_error=True)
        with self.assertRaises(ValueError):
            await repair.native(self.bound,'a'*40,'backup',self.reporting_sources,self.payloads)
        folder=self.root/repair.NATIVE_BACKUP
        self.assertEqual({p.name for p in folder.iterdir()},{'intent.json','failure.json'})
        failure=frozen.boot.loads(frozen.boot.raw(folder,'failure.json')[0])
        self.assertEqual(failure['diagnostic'],dict(stage='session_exit',error_class='ValueError'))
        self.assertEqual(repair.preserved_native(),self.preserved)

    async def test_late_source_drift_and_partial_native_state_are_terminal(self):
        await self.setup_native()
        self.payloads[repair.SOURCE_NAMES[0]] += b'\n# drift\n'
        with self.assertRaises(ValueError):
            await repair.native(self.bound,'a'*40,'backup',self.reporting_sources,self.payloads)
        self.assertFalse((self.root/repair.NATIVE_BACKUP/'result.json').exists())
        with self.assertRaises(ValueError):
            await repair.native(self.bound,'a'*40,'backup',self.reporting_sources,self.payloads)

    async def test_old_native_failure_missing_or_same_byte_replacement_detected(self):
        await self.setup_native()
        path=self.root/repair.FAILED_NATIVE/'failure.json'; raw=path.read_bytes()
        path.rename(path.parent/'extra.json')
        with self.assertRaises(ValueError): repair.preserved_native()
        path.parent.joinpath('extra.json').unlink(); save(self.root,repair.FAILED_NATIVE+'/failure.json',raw)
        self.assertNotEqual(repair.preserved_native(),self.preserved)

    async def test_readonly_inspection_checks_actual_status_without_session_or_archive(self):
        await self.setup_native()
        counts=dict(intended=3,completed=3,passed=0,failed=3,missing_verifier=0,active_tasks=[])
        with patch.object(frozen.service,'operation_status',return_value=dict(counts=counts,
                status='service_exited_successfully_not_completed_study_audit',observed_utc='2026-10-01T00:00:00Z')) as status,\
                patch.object(frozen.session,'open_session') as session,\
                patch.object(frozen.report,'collect') as collect,patch.object(frozen.archive,'pack') as pack:
            result=repair.inspect_native(self.bound,'a'*40,self.reporting_sources,{})
        self.assertEqual(result['counts'],counts);self.assertTrue(result['new_producer_absent'])
        self.assertFalse((self.root/repair.NATIVE_BACKUP).exists())
        status.assert_called_once();session.assert_not_called();collect.assert_not_called();pack.assert_not_called()


class BindingTests(unittest.TestCase):
    def test_generated_entry_binds_both_inline_sources_and_real_bootstrap(self):
        root=Path(__file__).parent
        names=(*repair.SOURCE_NAMES,'no_cutoff_recovery_bootstrap.py')
        raw={'stage2/'+n:(root/n).read_bytes() for n in names}
        sources={n:hashlib.sha256(raw['stage2/'+n]).hexdigest() for n in repair.SOURCE_NAMES}
        files={'stage2/no_cutoff_recovery_bootstrap.py':hashlib.sha256(raw['stage2/no_cutoff_recovery_bootstrap.py']).hexdigest()}
        with patch.object(frozen.handoff.launch,'_raw',side_effect=lambda n,h:raw[n]):
            code=repair.program(files,'a'*40,'backup',sources)
            inspection=repair.program(files,'a'*40,'inspect',sources)
        compile(code,'<synthetic-command>','exec')
        compile(inspection,'<synthetic-inspection>','exec')
        self.assertIn('hashlib.sha256(v).hexdigest()==sources[n]',code)
        self.assertNotIn('sys.modules.pop',code)
        self.assertIn('source_bound_reporting_recovery',code)
        self.assertIn("boot.ancestors(files)",inspect.getsource(repair.entry))
        self.assertIn(".absent-bytecode-cache",inspect.getsource(repair.entry))
        self.assertNotEqual(repair.NATIVE_BACKUP,frozen.NATIVE_BACKUP)
        for invalid in ({},dict(sources,extra='a'*64)):
            with self.assertRaises(ValueError):repair.program(files,'a'*40,'backup',invalid)

    def test_wrong_entry_source_is_rejected_before_bootstrap_effects(self):
        raw={n:b'not the actual entry' for n in repair.SOURCE_NAMES}
        sources={n:hashlib.sha256(v).hexdigest() for n,v in raw.items()}
        with patch.object(frozen.boot,'check') as check,self.assertRaises(ValueError):
            repair.entry({},'a'*40,'backup',sources,raw)
        check.assert_not_called()


if __name__ == '__main__': unittest.main()
