"""Real synthetic89 archives, pipes and durable writes; native facts mocked."""
import ast
import asyncio
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import struct
import sys
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_reporting as reporting
import matched_repeat_execution_bootstrap as boot
import matched_repeat_execution_service as service
import matched_repeat_session as session
import matched_repeat_archive as archive
import no_cutoff_recovery_files as files
import test_matched_repeat_archive as fixture
from test_no_cutoff_recovery_runtime import save


class ReportingTests(fixture.ArchiveTests):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(boot, 'directories', side_effect=files.bootstrap.directories))
        self.enterContext(patch.object(reporting, 'ROOT', self.root))
        self.live['witness'] = object()
        save(self.root, 'stage2/input_manifest.json',
            (Path(__file__).parent / 'input_manifest.json').read_bytes())

    def test_fixed_mac_backup_then_fresh_audit_export_same_archive_no_replay(self):
        data, _, source, inventory, _, receipt = self.sample(); compressed = source.read_bytes(); calls = []
        netcup = self.root / '.runtime/netcup'; netcup.mkdir(mode=0o700, exist_ok=True)
        public = self.root / reporting.PUBLIC; public.mkdir(parents=True, mode=0o700)
        (public / 'README.md').write_bytes(b'preserved documentation')
        value = {'sources': self.sources, 'bindings': {}}
        identities = files.capture(self.root, self.bound)[1]
        def capture(commit, mode, *, path=None):
            calls.append(mode)
            if mode == 'audit': return dict(data), value, identities
            written = {name: reporting._private_bytes(path / name, raw) for name, raw in {
                'snapshot.json': reporting._json(data), 'inventory.json': reporting._json(inventory),
                'evidence.tar.gz': compressed}.items()}
            return (data, inventory, receipt, written), value, identities
        with patch.object(reporting.handoff.original.launch, 'REPO', self.root), \
                patch.object(reporting.connection, 'prepare', return_value=(value, self.bound)), \
                patch.object(reporting.connection, '_identities', return_value=identities), \
                patch.object(reporting.connection, '_current', side_effect=lambda value: files.check(self.root, self.bound)), \
                patch.object(reporting, '_manifest', return_value=self.f.manifest), \
                patch.object(reporting, '_capture', side_effect=capture):
            result = reporting.backup('a' * 40)
            self.assertEqual(result['archive_sha256'], receipt['sha256']); self.assertEqual(result['completed'], 89)
            path = self.root / reporting.BACKUP / 'evidence.tar.gz'; before = files.bootstrap.identity(path.lstat())
            with self.assertRaises(ValueError): reporting.backup('a' * 40)
            projected = reporting.export('a' * 40)
            self.assertEqual(projected['aggregate']['attempted'], 89)
            with self.assertRaises(ValueError): reporting.export('a' * 40)
            self.assertEqual(files.bootstrap.identity(path.lstat()), before); self.assertEqual(path.read_bytes(), compressed)
        self.assertEqual(calls, ['backup', 'audit']); self.assertEqual((public / 'README.md').read_bytes(), b'preserved documentation')
        summary = json.loads((public / 'summary.json').read_bytes())
        self.assertEqual(summary['original_scores'], {'terminus-2': 52, 'openhands': 44})
        self.assertFalse(summary['repeat_merged_into_original89']); self.assertIsNone(summary['aggregate']['total_cost_usd'])

    def test_real_pipe_receiver_creates_one_strictly_verified_archive(self):
        self.produce(); data, _ = self.collect(); inventory, state = archive.inventory(data)
        wire = io.BytesIO(); archive.framing._write(wire, archive.MAGIC)
        archive.framing._metadata(wire, dict(snapshot=data, inventory=inventory))
        receipt = archive.pack(wire, inventory, state)
        archive.framing._write(wire, struct.pack('!Q', 0)); archive.framing._metadata(wire, receipt)
        archive.framing._write(wire, archive.END)
        path = self.root / 'receiver'; path.mkdir(mode=0o700)
        read, write = os.pipe()
        def send():
            with os.fdopen(write, 'wb', buffering=0) as stream: archive.framing._write(stream, wire.getvalue())
        thread = threading.Thread(target=send); thread.start()
        try:
            with os.fdopen(read, 'rb', buffering=0) as stream, patch.object(reporting, '_manifest', return_value=self.f.manifest):
                received = reporting._receive(NS(stdout=stream, wait=lambda **kw: 0), 'backup', {'sources': self.sources}, path=path)
                self.assertEqual(received[:3], (data, inventory, receipt))
        finally: thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(archive.verify(path / 'evidence.tar.gz', data, inventory, receipt, self.f.manifest, self.sources)['verified_result_files'], 89)

    def native(self, *, fail_exit=False):
        self.produce(); output = io.BytesIO(); read, write = os.pipe(); os.close(write)
        events = []
        @contextmanager
        def open_session(root, harness, stream):
            self.assertEqual((root, harness), (self.root, 'terminus-2'))
            self.assertEqual(boot.loads(output.getvalue()), reporting._ready(self.bound, 'a' * 40, 'backup'))
            events.append('real-entry-would-authenticate-composite'); yield object()
            self.assertFalse(output.getvalue().endswith(archive.END)); events.append('session-exit')
            if fail_exit: raise ValueError('Synthetic final session recheck failure')
        with os.fdopen(read, 'rb', buffering=0) as incoming, \
                patch.object(reporting, '__file__', str(self.root / 'stage2/matched_repeat_reporting.py')), \
                patch.object(boot, 'check', side_effect=lambda harness, bound, *args: files.capture(self.root, bound)[1]), \
                patch.object(service, 'loaded'), patch.object(session, 'open_execution_session', side_effect=open_session), \
                patch.object(session.handoff, '_live', return_value={'header': {'operator': {'operator_commit': 'a' * 40}}}), \
                patch.object(sys, 'stdin', NS(buffer=incoming)), patch.object(sys, '__stdout__', NS(buffer=output)):
            if fail_exit:
                with self.assertRaises(ValueError): asyncio.run(reporting.native(self.bound, 'a' * 40, 'backup'))
            else:
                asyncio.run(reporting.native(self.bound, 'a' * 40, 'backup'))
                with self.assertRaises(ValueError): asyncio.run(reporting.native(self.bound, 'a' * 40, 'backup'))
        return output.getvalue(), events

    def test_actual_native_pack_commit_follows_successful_session_exit(self):
        output, events = self.native()
        self.assertTrue(output.endswith(archive.END)); self.assertEqual(events[-1], 'session-exit')
        self.assertEqual({p.name for p in (self.root / reporting.NATIVE_BACKUP).iterdir()}, {'intent.json', 'result.json'})

    def test_session_exit_failure_withholds_commit_and_retains_failure(self):
        output, _ = self.native(fail_exit=True)
        self.assertFalse(output.endswith(archive.END))
        self.assertTrue((self.root / reporting.NATIVE_BACKUP / 'failure.json').exists())


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.bound = {'stage2/synthetic.py': 'b' * 64}; self.commit = 'a' * 40
        self.value = {'bindings': {}}; self.ids = {'synthetic': ()}
        self.enterContext(patch.object(reporting.connection, 'prepare', return_value=(self.value, self.bound)))
        self.enterContext(patch.object(reporting.connection, '_identities', return_value=self.ids))
        self.enterContext(patch.object(reporting, '_command', return_value=['fixed-synthetic-command']))
        self.enterContext(patch.object(reporting, '_current'))

    def test_composite_sender_waits_for_exact_actual_readiness(self):
        read, write = os.pipe(); pending = threading.Event(); events = []
        process = NS(stdin=io.BytesIO(), stdout=os.fdopen(read, 'rb', buffering=0), poll=lambda: 0)
        original = reporting.connection.read_reply
        def reply(stream): events.append('waiting'); pending.set(); return original(stream)
        def send():
            with os.fdopen(write, 'wb', buffering=0) as stream:
                if pending.wait(5):
                    events.append('ready'); stream.write(service._line(reporting._ready(self.bound, self.commit, 'audit')))
        thread = threading.Thread(target=send); thread.start()
        try:
            with patch.object(reporting.subprocess, 'Popen', return_value=process), \
                    patch.object(reporting.connection, 'read_reply', side_effect=reply), \
                    patch.object(reporting.handoff, 'send', side_effect=lambda stream: events.append('actual-composite-capture')), \
                    patch.object(reporting, '_receive', return_value={'synthetic': True}):
                result, _, _ = reporting._capture(self.commit, 'audit')
        finally: thread.join(5)
        self.assertFalse(thread.is_alive()); self.assertEqual(result, {'synthetic': True})
        self.assertEqual(events, ['waiting', 'ready', 'actual-composite-capture'])

    def test_wrong_readiness_prevents_capture(self):
        for field, value in (('root', '/other'), ('operator_commit', 'c' * 40), ('mode', 'backup'), ('bindings_sha256', 'd' * 64)):
            ready = reporting._ready(self.bound, self.commit, 'audit'); ready[field] = value
            process = NS(stdin=io.BytesIO(), stdout=io.BytesIO(), poll=lambda: 0)
            with self.subTest(field=field), patch.object(reporting.subprocess, 'Popen', return_value=process), \
                    patch.object(reporting.connection, 'read_reply', return_value=ready), \
                    patch.object(reporting.handoff, 'send') as send:
                with self.assertRaises(ValueError): reporting._capture(self.commit, 'audit')
                send.assert_not_called()

    def test_program_uses_bound_same_bootstrap_object_and_fixed_reporting_entry(self):
        raw = Path(boot.__file__).read_bytes(); files = {'stage2/matched_repeat_execution_bootstrap.py': 'b' * 64}
        with patch.object(reporting.handoff.original.launch, '_raw', return_value=raw):
            for mode in ('audit', 'backup'):
                source = reporting._program(files, self.commit, mode); ast.parse(source)
                self.assertIn("b.reporting('terminus-2',", source)
                self.assertIn('sys.modules[b.__name__]=b', source)
        for harness in ('openhands', 'custom', None):
            with self.assertRaises(ValueError): boot.reporting(harness, files, self.commit, 'audit')


if __name__ == '__main__': unittest.main()
