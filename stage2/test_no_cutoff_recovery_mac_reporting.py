"""Actual Mac IO and synthetic three-result archives; native facts are mocked."""
import ast
import asyncio
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import mac_operator_files as mac
import no_cutoff_recovery_archive as native_archive
import no_cutoff_recovery_mac_archive as archive
import no_cutoff_recovery_mac_reporting as reporting
import no_cutoff_recovery_mac_bridge as bridge
import no_cutoff_recovery_reporting as original
import test_no_cutoff_recovery_reporting as fixture
from test_no_cutoff_recovery_execution import LocalFiles


class ContractTests(unittest.TestCase):
    def test_same_archive_algorithm_only_local_protection_changes(self):
        expected=inspect.getsource(native_archive.verify).replace('files.bootstrap.','mac.')
        actual=inspect.getsource(archive.verify)
        self.assertEqual(ast.dump(ast.parse(actual)),ast.dump(ast.parse(expected)))
        self.assertIs(archive._anchors,native_archive._anchors)
        self.assertIs(archive.validate_inventory,native_archive.validate_inventory)

    def test_fixed_native_commands_projection_and_destinations_unchanged(self):
        self.assertIs(reporting._command,original._command)
        self.assertIs(reporting._ready,original._ready)
        self.assertIs(reporting.projection,original.projection)
        for name in ('BACKUP','EXPORT','PUBLIC','OUTPUTS','AUDIT_MAGIC'):
            self.assertEqual(getattr(reporting,name),getattr(original,name))
        self.assertIsNot(reporting.backup,original.backup)
        self.assertIn('bridge.send(value, process.stdin)',inspect.getsource(reporting._capture))

    def test_amendment_does_not_change_frozen_native_inventory(self):
        self.assertTrue(set(bridge.EXTRAS).isdisjoint(fixture.policy.REQUIRED_SOURCE_FILES))


class MacReportingTests(LocalFiles,unittest.IsolatedAsyncioTestCase):
    produce=fixture.ReportingTests.produce
    collect=fixture.ReportingTests.collect
    packed=fixture.ReportingTests.packed

    def setUp(self):
        factory=tempfile.TemporaryDirectory
        with patch.object(fixture.tempfile,'TemporaryDirectory',side_effect=lambda:factory(
                prefix='.uts-mac-report-',dir=Path.home() if sys.platform=='darwin' else None)):
            fixture.ReportingTests.setUp(self)

    def available(self):
        if sys.platform=='darwin':return True
        with self.assertRaises(ValueError):mac.directories(self.root,private=True)
        return False

    async def archive_fixture(self):
        await self.produce(); data,_=self.collect(); path,inventory,_,receipt=self.packed(data)
        return data,path,inventory,receipt

    async def test_actual_darwin_archive_read_retains_three_and_nulls(self):
        if not self.available():return
        data,path,inventory,receipt=await self.archive_fixture()
        with patch.object(mac,'_acl',wraps=mac._acl) as acl:
            verified=archive.verify(path,data,inventory,receipt,self.f.manifest,self.sources)
        self.assertGreater(acl.call_count,1)
        self.assertEqual(verified['verified_result_files'],3)
        self.assertEqual(verified['verified_absent_paths'],1)
        self.assertFalse(verified['paid_launch_ready'])
        self.assertIsNone(data['rows'][2]['reward'])

    async def test_actual_darwin_corruption_and_truncation_refused(self):
        if not self.available():return
        data,path,inventory,receipt=await self.archive_fixture(); raw=path.read_bytes()
        path.write_bytes(raw[:-1])
        with self.assertRaises(ValueError):archive.verify(path,data,inventory,receipt,self.f.manifest,self.sources)
        path.write_bytes(bytes([raw[0]^1])+raw[1:])
        with self.assertRaises((ValueError,OSError)):archive.verify(path,data,inventory,receipt,self.f.manifest,self.sources)

    async def test_same_archive_permissions_links_and_parent_checks(self):
        if not self.available():return
        data,path,inventory,receipt=await self.archive_fixture()
        path.chmod(0o644)
        with self.assertRaises(ValueError):archive.verify(path,data,inventory,receipt,self.f.manifest,self.sources)
        path.chmod(0o600);os.link(path,path.parent/'hardlink')
        with self.assertRaises(ValueError):archive.verify(path,data,inventory,receipt,self.f.manifest,self.sources)

    async def test_actual_pipe_receiver_keeps_exact_committed_archive(self):
        if not self.available():return
        await self.produce();data,_=self.collect();inventory,state=native_archive.inventory(data)
        wire=io.BytesIO();native_archive.framing._write(wire,native_archive.MAGIC)
        native_archive.framing._metadata(wire,dict(snapshot=data,inventory=inventory))
        receipt=native_archive.pack(wire,inventory,state)
        native_archive.framing._write(wire,struct.pack('!Q',0));native_archive.framing._metadata(wire,receipt)
        native_archive.framing._write(wire,native_archive.END)
        path=self.root/'received';path.mkdir(mode=0o700)
        read,write=os.pipe();errors=[]
        def sender():
            try:
                with os.fdopen(write,'wb',buffering=0) as stream:native_archive.framing._write(stream,wire.getvalue())
            except BaseException as error:errors.append(type(error).__name__)
        thread=threading.Thread(target=sender);thread.start()
        try:
            with os.fdopen(read,'rb',buffering=0) as stream,patch.object(reporting,'_manifest',return_value=self.f.manifest):
                received=reporting._receive(NS(stdout=stream,wait=lambda **kw:0),'backup',
                    {'current_sources':self.sources},path=path)
            self.assertEqual(received[:3],(data,inventory,receipt))
        finally:thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        archive.verify(path/'evidence.tar.gz',data,inventory,receipt,self.f.manifest,self.sources)

    async def setup_operator(self):
        data,source,inventory,receipt=await self.archive_fixture()
        compressed=source.read_bytes();self.calls=[]
        (self.root/'.runtime/netcup').mkdir(mode=0o700)
        self.public=self.root/reporting.PUBLIC;self.public.mkdir(parents=True,mode=0o700)
        (self.public/'README.md').write_bytes(b'existing documentation')
        self.value={'current_sources':self.sources,'local_identities':{}}
        def capture(commit,mode,*,path=None):
            self.calls.append(mode)
            if mode=='audit':return dict(data),self.value,{}
            written={n:reporting._private_bytes(path/n,raw) for n,raw in {
                'snapshot.json':reporting._json(data),'inventory.json':reporting._json(inventory),
                'evidence.tar.gz':compressed}.items()}
            return (data,inventory,receipt,written),self.value,{}
        self.enterContext(patch.object(reporting.handoff.launch,'REPO',self.root))
        self.enterContext(patch.object(bridge,'prepare',return_value=(self.value,self.bound)))
        self.current=self.enterContext(patch.object(bridge,'current'))
        self.enterContext(patch.object(reporting,'_manifest',return_value=self.f.manifest))
        self.capture=self.enterContext(patch.object(reporting,'_capture',side_effect=capture))
        return data,receipt

    async def test_real_mac_one_backup_and_export_no_recreation(self):
        if not self.available():return
        data,receipt=await self.setup_operator()
        verified=reporting.backup('a'*40);self.assertEqual(verified['archive_sha256'],receipt['sha256'])
        path=self.root/reporting.BACKUP/'evidence.tar.gz';before=mac.identity(path.stat())
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        exported=reporting.export('a'*40)
        self.assertEqual(exported['aggregate']['attempted'],3)
        with self.assertRaises(ValueError):reporting.export('a'*40)
        self.assertEqual(mac.identity(path.stat()),before)
        self.assertEqual(self.calls,['backup','audit'])
        self.assertEqual((self.public/'README.md').read_bytes(),b'existing documentation')
        self.assertEqual(set(p.name for p in path.parent.iterdir()),
            {'intent.json','snapshot.json','inventory.json','evidence.tar.gz','backup.json'})
        output=json.loads((self.public/'summary.json').read_bytes())
        self.assertEqual(output['original_full89_denominator'],89)
        self.assertEqual(output['separate_recovery_denominator'],3)
        self.assertFalse(output['recovery_merged_into_original89'])
        rows=json.loads((self.public/'trials.json').read_bytes())['rows'];self.assertIsNone(rows[2]['reward'])

    async def test_failure_stays_private_terminal_and_unreplayed(self):
        if not self.available():return
        await self.setup_operator();self.capture.side_effect=ValueError('not published arbitrary diagnostics')
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        path=self.root/reporting.BACKUP
        self.assertEqual({p.name for p in path.iterdir()},{'intent.json','failure.json'})
        self.assertNotIn(b'arbitrary',mac.raw(path,'failure.json')[0])
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertEqual(self.capture.call_count,1)

    async def test_same_byte_archive_replacement_before_completion_refused(self):
        if not self.available():return
        await self.setup_operator();changed=False
        def replace(value):
            nonlocal changed
            if not changed:
                changed=True;path=self.root/reporting.BACKUP/'evidence.tar.gz';raw=path.read_bytes()
                path.rename(path.parent/'original-retained')
                reporting._private_bytes(path,raw)
        self.current.side_effect=replace
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertFalse((self.root/reporting.BACKUP/'backup.json').exists())
        self.assertTrue((self.root/reporting.BACKUP/'failure.json').exists())

    async def test_retained_backup_missing_file_or_wrong_identity_refused(self):
        if not self.available():return
        await self.setup_operator();reporting.backup('a'*40)
        path=self.root/reporting.BACKUP/'backup.json';raw=path.read_bytes()
        data=json.loads(raw);data['receipt']['files']+=1
        path.write_bytes(json.dumps(data).encode())
        with self.assertRaises(ValueError):reporting._read_backup(self.value)


if __name__=='__main__':unittest.main()
