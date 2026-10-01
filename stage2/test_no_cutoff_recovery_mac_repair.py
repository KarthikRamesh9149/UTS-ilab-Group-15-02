"""Real protected Mac files/pipes and synthetic archives; no live SSH."""
from copy import deepcopy
import gzip
import hashlib
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

import no_cutoff_recovery_mac_repair as reporting
import no_cutoff_recovery_mac_reporting as failed_reporter
import no_cutoff_recovery_reporting_transport as wire
import test_no_cutoff_recovery_mac_reporting as old
from test_no_cutoff_recovery_runtime import save

old_failed_fixture = old.failed_fixture


def failed_fixture(case, root):
    """Explicit synthetic R5 payloads; real protection and identity algorithms."""
    with patch.object(old,'reporting',failed_reporter):
        old_failed_fixture(root)
    pins = deepcopy(reporting.FAILED_BACKUPS)
    records = {
        'intent.json': dict(automatic_resume=False, commit='32cccab14b72118b43231db6355a2adf7844d270',
            kind='one_shot_off_server_recovery_backup',paid_launch_ready=False,
            started_utc='2026-10-01T08:59:38.864646+00:00'),
        'failure.json': dict(status='failed_or_uncertain_preserve_recovery_backup',
            diagnostic=dict(stage='capture_stream_receive',error_class='ValueError'),
            automatic_resume=False,paid_launch_ready=False),
        'snapshot.json': dict(synthetic_failed_snapshot=True, reward=0.0),
        'inventory.json': dict(synthetic_failed_inventory=True),
    }
    for name,value in records.items():
        raw=json.dumps(value,sort_keys=True).encode();save(root,reporting.R5+'/'+name,raw)
        pins[reporting.R5][name]=hashlib.sha256(raw).hexdigest()
    partial=gzip.compress(b'synthetic incomplete archive only',mtime=0)[:-8]
    name=reporting.R5+'/evidence.tar.gz';save(root,name,partial)
    case.enterContext(patch.object(reporting,'FAILED_BACKUPS',pins))
    case.enterContext(patch.object(reporting,'FAILED_ARCHIVES',{
        name:dict(sha256=hashlib.sha256(partial).hexdigest(),bytes=len(partial))}))


class RepairMacTests(old.MacReportingTests):
    """Reuse unchanged strict IO failure tests against the separate new entry."""
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(old,'reporting',reporting))
        self.enterContext(patch.object(old,'failed_fixture',side_effect=lambda root:failed_fixture(self,root)))

    async def setup_operator(self):
        result=await super().setup_operator()
        self.value['bound']={n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest()
            for n in reporting.repair.SOURCE_NAMES}
        return result

    async def test_actual_pipe_receiver_keeps_exact_committed_archive(self):
        if not self.available():return
        await self.produce();data,_=self.collect();inventory,state=old.native_archive.inventory(data)
        raw=io.BytesIO();output=wire.Writer(raw).start()
        try:
            old.native_archive.framing._write(output,old.native_archive.MAGIC)
            old.native_archive.framing._metadata(output,dict(snapshot=data,inventory=inventory))
            receipt=old.native_archive.pack(output,inventory,state)
            output.flush()
            old.native_archive.framing._write(output,struct.pack('!Q',0))
            old.native_archive.framing._metadata(output,receipt)
            old.native_archive.framing._write(output,old.native_archive.END);output.finish()
        finally:output.close_heartbeat()
        path=self.root/'received';path.mkdir(mode=0o700)
        read,write=os.pipe();errors=[]
        def send():
            try:
                with os.fdopen(write,'wb',buffering=0) as stream:old.native_archive.framing._write(stream,raw.getvalue())
            except BaseException as error:errors.append(type(error).__name__)
        thread=threading.Thread(target=send);thread.start()
        try:
            with os.fdopen(read,'rb',buffering=0) as stream,patch.object(reporting,'_manifest',return_value=self.f.manifest):
                received=reporting._receive(NS(stdout=stream,wait=lambda **kw:0),'backup',
                    {'current_sources':self.sources},path=path)
            self.assertEqual(received[:3],(data,inventory,receipt))
        finally:thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        reporting.archive.verify(path/'evidence.tar.gz',data,inventory,receipt,self.f.manifest,self.sources)

    async def test_preservation_recheck_after_readiness_precedes_original_sender(self):
        if not self.available():return
        await self.setup_operator();real_capture=self.real_capture
        process=NS(stdin=io.BytesIO(),stdout=io.BytesIO(),poll=lambda:0)
        def ready(stream):
            (self.root/reporting.R5/'failure.json').write_bytes(b'{}')
            return reporting.repair.ready(self.bound,'a'*40,'audit',reporting._reporting_sources(self.value))
        with patch.object(reporting,'_prepare',return_value=(self.value,self.bound)),\
                patch.object(reporting,'_command',return_value=['synthetic-no-execution']),\
                patch.object(reporting,'subprocess',NS(Popen=lambda *a,**k:process,
                    PIPE=reporting.subprocess.PIPE,DEVNULL=reporting.subprocess.DEVNULL)),\
                patch.object(reporting.frozen.connection,'read_reply',side_effect=ready),\
                patch.object(reporting.bridge,'send') as send:
            with self.assertRaises(reporting._CaptureFailure) as caught:real_capture('a'*40,'audit')
        self.assertEqual(caught.exception.stage,'before_sender_recheck');send.assert_not_called()

    async def test_failed_partial_archive_change_refuses_before_new_backup(self):
        if not self.available():return
        await self.setup_operator()
        (self.root/reporting.R5/'evidence.tar.gz').write_bytes(b'changed')
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertFalse((self.root/reporting.BACKUP).exists());self.capture.assert_not_called()

    async def test_native_diagnostic_is_preserved_without_raw_payload(self):
        if not self.available():return
        await self.setup_operator()
        self.capture.side_effect=reporting._CaptureFailure('stream_receive',
            wire.NativeFailure(dict(stage='session_exit',error_class='ValueError')))
        with self.assertRaises(reporting._CaptureFailure):reporting.backup('a'*40)
        failure=reporting.boot.loads(reporting.boot.raw(self.root/reporting.BACKUP,'failure.json')[0])
        self.assertEqual(failure['diagnostic']['native'],dict(stage='session_exit',error_class='ValueError'))
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertEqual(self.capture.call_count,1)


class Contracts(unittest.TestCase):
    def test_fixed_new_destinations_and_all_failed_evidence_are_bound(self):
        self.assertEqual(len(reporting.FAILED_BACKUPS),5)
        self.assertEqual(sum(map(len,reporting.FAILED_BACKUPS.values())),12)
        self.assertEqual(reporting.FAILED_ARCHIVES[reporting.R5+'/evidence.tar.gz'],dict(
            sha256='16e7571470740366cd5dc68ab6148b7d14771dc973b4a52f62864c256479b12b',bytes=218947965))
        self.assertEqual(reporting.BACKUP,'.runtime/netcup/custom-no-cutoff-recovery3-reporting-20261002')
        self.assertNotIn(reporting.BACKUP,reporting.FAILED_BACKUPS)
        self.assertEqual(failed_reporter.BACKUP,reporting.R5)
        self.assertEqual(reporting.PUBLIC,failed_reporter.PUBLIC)
        self.assertEqual(reporting.EXPORT,failed_reporter.EXPORT)

    def test_new_command_retains_exact_pinned_route_interpreter_and_keepalives(self):
        import shlex
        fixed=['ssh','-F','/dev/null','-o','StrictHostKeyChecking=yes','root@62.83.32.126','old program']
        sources={n:'b'*64 for n in reporting.repair.SOURCE_NAMES}
        with patch.object(reporting.frozen.connection,'command',return_value=fixed),\
                patch.object(reporting.repair,'program',return_value='new bound code'):
            command=reporting._command({},'a'*40,'backup',sources)
        self.assertEqual(command[:-2],fixed[:-2]+['-o','ServerAliveInterval=30','-o','ServerAliveCountMax=150'])
        self.assertEqual(command[-2],fixed[-2]);remote=shlex.split(command[-1])
        self.assertEqual(remote[-5:],[str(reporting.frozen.boot.ROOT/'.venv/bin/python'),'-I','-B','-c','new bound code'])
        self.assertEqual(remote[:2],['/usr/bin/env','-i'])


if __name__=='__main__':unittest.main()
