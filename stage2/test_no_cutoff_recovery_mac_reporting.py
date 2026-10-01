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


def failed_fixture(root):
    """Exact allowlisted failed-attempt metadata in owned synthetic trees."""
    for folder, files in reporting.FAILED_BACKUPS.items():
        path = root / folder; path.mkdir(parents=True, mode=0o700)
        first = folder == reporting.FAILED_BACKUP
        records = {
            'intent.json': dict(automatic_resume=False,
                commit='42613a88ded7e80c157f1686851dc91b2f7bc4f7' if first else '0af784affcb2908b3cd9a54a882bc8afda5ee934',
                kind='one_shot_off_server_recovery_backup', paid_launch_ready=False,
                started_utc='2026-09-30T23:06:17.968027+00:00' if first else '2026-10-01T01:31:38.883400+00:00'),
            'failure.json': dict(automatic_resume=False, paid_launch_ready=False,
                status='failed_or_uncertain_preserve_recovery_backup'),
        }
        if folder.endswith('-r3'):
            records['intent.json'].update(commit='4cfaac53039242ff5a53fbc2bd2fa125cd57e7d4',
                started_utc='2026-10-01T03:11:20.813805+00:00')
            records['failure.json']['diagnostic'] = dict(
                stage='capture_original_sender', error_class='ValueError')
        for name, value in records.items():
            raw = json.dumps(value, sort_keys=True).encode()
            assert hashlib.sha256(raw).hexdigest() == files[name]
            from test_no_cutoff_recovery_runtime import save
            save(root, folder+'/'+name, raw)


class ContractTests(unittest.TestCase):
    def test_capture_prepare_failure_retains_only_fixed_stage_and_class(self):
        with patch.object(reporting, '_prepare', side_effect=ValueError('private arbitrary payload')), \
                patch.object(reporting.subprocess, 'Popen') as popen:
            with self.assertRaises(reporting._CaptureFailure) as caught:
                reporting._capture('a'*40, 'backup')
        self.assertEqual((caught.exception.stage,caught.exception.error_class),('prepare','ValueError'))
        self.assertNotIn('private',str(caught.exception));popen.assert_not_called()

    def test_diagnostic_unknown_names_are_not_exported(self):
        error=type('PrivateArbitraryPayload', (Exception,), {})('raw private text')
        self.assertEqual(reporting._error_class(error),'OtherError')
        with self.assertRaises(ValueError):reporting._CaptureFailure('untrusted stage',error)

    def test_sender_metadata_is_bounded_and_propagated_without_exception_payload(self):
        record=dict(stage='original_audit_archive',error_class='ValueError',transport=None)
        error=bridge._SenderFailure(record,1)
        failure=reporting._CaptureFailure('original_sender',error)
        self.assertEqual(failure.sender,dict(record,returncode=1))
        error.diagnostic['message']='private arbitrary payload'
        self.assertNotIn('message',failure.sender)
        with self.assertRaises(ValueError):reporting._CaptureFailure('original_sender',error)

    def test_same_archive_algorithm_only_local_protection_changes(self):
        expected=inspect.getsource(native_archive.verify).replace('files.bootstrap.','mac.')
        actual=inspect.getsource(archive.verify)
        self.assertEqual(ast.dump(ast.parse(actual)),ast.dump(ast.parse(expected)))
        self.assertIs(archive._anchors,native_archive._anchors)
        self.assertIs(archive.validate_inventory,native_archive.validate_inventory)

    def test_fixed_native_commands_projection_and_exclusive_amended_destination(self):
        self.assertIs(reporting._command,original._command)
        self.assertIs(reporting._ready,original._ready)
        self.assertIs(reporting.projection,original.projection)
        for name in ('EXPORT','PUBLIC','OUTPUTS','AUDIT_MAGIC'):
            self.assertEqual(getattr(reporting,name),getattr(original,name))
        self.assertEqual(reporting.FAILED_BACKUP, original.BACKUP)
        self.assertEqual(reporting.BACKUP, '.runtime/netcup/custom-no-cutoff-recovery3-20261001-r4')
        self.assertNotIn(reporting.BACKUP, reporting.FAILED_BACKUPS)
        self.assertNotEqual(reporting.BACKUP, original.BACKUP)
        self.assertIsNot(reporting.backup,original.backup)
        self.assertIn('bridge.send(value, process.stdin)',inspect.getsource(reporting._capture))

    def test_all_three_terminal_attempts_are_pinned_separately(self):
        self.assertEqual(set(reporting.FAILED_BACKUPS), {
            reporting.FAILED_BACKUP,
            '.runtime/netcup/custom-no-cutoff-recovery3-20261001-r2',
            '.runtime/netcup/custom-no-cutoff-recovery3-20261001-r3',
        })
        self.assertEqual(reporting.FAILED_BACKUPS[
            '.runtime/netcup/custom-no-cutoff-recovery3-20261001-r3'], {
            'intent.json': '68f1518d63b2a204b14f4a5edaf33033cbd429407d60c190711e2a7ba20f63f3',
            'failure.json': 'b2d691a45c3dea8ef638bdc465b7e05553c24755fc4130dd1c3e9ec5fb3692f0',
        })

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
        failed_fixture(self.root)
        self.value['failed_backup'] = reporting._failed_backup()
        self.enterContext(patch.object(bridge,'prepare',return_value=(self.value,self.bound)))
        self.current=self.enterContext(patch.object(bridge,'current'))
        self.enterContext(patch.object(reporting,'_manifest',return_value=self.f.manifest))
        self.real_capture=reporting._capture
        self.capture=self.enterContext(patch.object(reporting,'_capture',side_effect=capture))
        return data,receipt

    async def test_real_mac_one_backup_and_export_no_recreation(self):
        if not self.available():return
        data,receipt=await self.setup_operator()
        failed = reporting._failed_backup()
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
        self.assertEqual(reporting._failed_backup(), failed)

    async def test_failure_stays_private_terminal_and_unreplayed(self):
        if not self.available():return
        await self.setup_operator();self.capture.side_effect=ValueError('not published arbitrary diagnostics')
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        path=self.root/reporting.BACKUP
        self.assertEqual({p.name for p in path.iterdir()},{'intent.json','failure.json'})
        self.assertNotIn(b'arbitrary',mac.raw(path,'failure.json')[0])
        self.assertEqual(mac.loads(mac.raw(path,'failure.json')[0])['diagnostic'],
            dict(stage='capture',error_class='ValueError'))
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertEqual(self.capture.call_count,1)

    async def test_real_private_failure_retains_only_validated_inner_sender_categories(self):
        if not self.available():return
        await self.setup_operator()
        record=dict(stage='original_audit_archive',error_class='ValueError',transport=None)
        self.capture.side_effect=reporting._CaptureFailure('original_sender',bridge._SenderFailure(record,1))
        with self.assertRaises(reporting._CaptureFailure):reporting.backup('a'*40)
        path=self.root/reporting.BACKUP
        failure=mac.loads(mac.raw(path,'failure.json')[0])
        self.assertEqual(failure['diagnostic']['sender'],dict(record,returncode=1))
        self.assertEqual({p.name for p in path.iterdir()},{'intent.json','failure.json'})
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertEqual(self.capture.call_count,1)

    async def test_same_byte_archive_replacement_before_completion_refused(self):
        if not self.available():return
        await self.setup_operator();changed=False
        def replace(value):
            nonlocal changed
            path=self.root/reporting.BACKUP/'evidence.tar.gz'
            if not changed and path.exists():
                changed=True;raw=path.read_bytes()
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

    async def test_failed_attempt_change_refuses_before_new_destination_or_capture(self):
        if not self.available():return
        await self.setup_operator()
        path=self.root/reporting.FAILED_BACKUP/'failure.json'
        path.write_bytes(b'{}')
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertFalse((self.root/reporting.BACKUP).exists())
        self.assertEqual(self.capture.call_count,0)

    async def test_later_failed_attempt_changes_also_block_before_creation(self):
        if not self.available():return
        await self.setup_operator()
        for index,folder in enumerate(n for n in reporting.FAILED_BACKUPS if n!=reporting.FAILED_BACKUP):
            path=self.root/folder/'intent.json';raw=path.read_bytes()
            for replacement in (b'{}',raw):
                with self.subTest(folder=folder,same_bytes=replacement==raw):
                    if replacement==raw:
                        path.write_bytes(raw)
                        self.value['failed_backup']=reporting._failed_backup()
                        path.rename(self.root/('preserved-later-intent-'+str(index)))
                        mac.write_bytes(path,raw)
                        with self.assertRaises(ValueError):reporting._current(self.value,{})
                    else:
                        path.write_bytes(replacement)
                        with self.assertRaises(ValueError):reporting.backup('a'*40)
                    self.assertFalse((self.root/reporting.BACKUP).exists())
                    self.assertEqual(self.capture.call_count,0)
            self.value['failed_backup']=reporting._failed_backup()

    async def test_failed_attempt_extra_missing_link_or_permissions_refuse(self):
        if not self.available():return
        await self.setup_operator();path=self.root/reporting.FAILED_BACKUP
        intent=path/'intent.json';raw=intent.read_bytes()
        for mode in ('extra','missing','symlink','hardlink','mode'):
            with self.subTest(mode=mode):
                if mode=='extra':mac.write_bytes(path/'evidence.tar.gz',b'not an archive')
                elif mode=='missing':intent.unlink()
                elif mode=='symlink':intent.unlink();intent.symlink_to(path/'failure.json')
                elif mode=='hardlink':os.link(intent,self.root/'extra-link')
                else:intent.chmod(0o644)
                with self.assertRaises((ValueError,OSError)):reporting.backup('a'*40)
                self.assertFalse((self.root/reporting.BACKUP).exists())
                if mode=='extra':(path/'evidence.tar.gz').unlink()
                elif mode in ('missing','symlink'):
                    if intent.is_symlink():intent.unlink()
                    mac.write_bytes(intent,raw)
                elif mode=='hardlink':(self.root/'extra-link').unlink()
                else:intent.chmod(0o600)
        self.assertEqual(self.capture.call_count,0)

    async def test_same_byte_failed_attempt_replacement_latches_before_completion(self):
        if not self.available():return
        await self.setup_operator();original_capture=self.capture.side_effect
        def capture(*args,**kwargs):
            result=original_capture(*args,**kwargs)
            path=self.root/reporting.FAILED_BACKUP/'intent.json';raw=path.read_bytes()
            path.rename(self.root/'preserved-first-intent')
            mac.write_bytes(path,raw)
            return result
        self.capture.side_effect=capture
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertFalse((self.root/reporting.BACKUP/'backup.json').exists())
        self.assertTrue((self.root/reporting.BACKUP/'failure.json').exists())
        with self.assertRaises(ValueError):reporting.backup('a'*40)
        self.assertEqual(self.capture.call_count,1)

    async def test_late_failed_attempt_change_refuses_export_and_successor_archive(self):
        if not self.available():return
        await self.setup_operator();reporting.backup('a'*40)
        original_capture=self.capture.side_effect
        def capture(*args,**kwargs):
            result=original_capture(*args,**kwargs)
            (self.root/reporting.FAILED_BACKUP/'failure.json').write_bytes(b'{}')
            return result
        self.capture.side_effect=capture
        with self.assertRaises(ValueError):reporting.export('a'*40)
        self.assertFalse((self.root/reporting.EXPORT/'result.json').exists())
        self.assertFalse((self.public/'summary.json').exists())
        with self.assertRaises(ValueError):reporting._read_backup(self.value)

    async def test_preservation_recheck_after_readiness_precedes_original_sender(self):
        if not self.available():return
        await self.setup_operator()
        # Call the real capture body, not the fixture's native-audit stand-in.
        real_capture = self.real_capture
        process=NS(stdin=io.BytesIO(),stdout=io.BytesIO(),poll=lambda:0)
        def ready(stream):
            (self.root/reporting.FAILED_BACKUP/'failure.json').write_bytes(b'{}')
            return reporting._ready(self.bound, 'a'*40, 'audit')
        with patch.object(reporting, '_prepare', return_value=(self.value,self.bound)), \
                patch.object(reporting, '_command', return_value=['synthetic-no-execution']), \
                patch.object(reporting, 'subprocess', NS(Popen=lambda *a,**k:process,
                    PIPE=reporting.subprocess.PIPE, DEVNULL=reporting.subprocess.DEVNULL)), \
                patch.object(reporting.frozen.connection, 'read_reply', side_effect=ready), \
                patch.object(bridge, 'send') as send:
            with self.assertRaises(reporting._CaptureFailure) as caught:real_capture('a'*40,'audit')
        self.assertEqual(caught.exception.stage,'before_sender_recheck')
        send.assert_not_called()


if __name__=='__main__':unittest.main()
