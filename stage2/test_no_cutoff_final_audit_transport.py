"""Local synthetic files/pipes only; SSH and actual native observations mocked."""
import ast
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_final_audit_transport as transport
import no_cutoff_final_reporting as launch
import test_no_cutoff_final_archive as fixtures


def bindings():
    return dict(commit='a'*40, native={}, reporting={'stage2/example.py':'b'*64},
        anchors={}, local={name:'c'*64 for name in transport.SOURCE_FILES})


def program(body, values=None):
    values = values or bindings()
    original = 'import json,sys\nc={"operation":"collect"}\n' + body + '\n' + transport.FOOTER
    with patch.object(launch, '_program', return_value=original):
        return transport._program(values)[0]


def metadata(raw):
    return dict(status='transport_finished', error_type=None, returncode=0,
        elapsed_seconds=1.0, stdout_bytes=len(raw), automatic_resume=False,
        native_state_requires_inspection=False, diagnostics=dict(
            records=[dict(event='started', elapsed_seconds=0.0, pid=7, start_ticks=4),
                dict(event='returned', elapsed_seconds=1.0, stdout_sha256=transport._hash(raw))],
            redacted_stderr_records=0, samples_are_not_passed_checks=True))


class ProgramTests(unittest.TestCase):
    def run_program(self, body, sample=0.02):
        with patch.object(transport, 'SAMPLE_SECONDS', sample):
            source = program(body)
        result = subprocess.run([sys.executable, '-I', '-B', '-'],
            input=source.encode(), capture_output=True, timeout=5)
        sink = transport._Diagnostics(transport._aliases(bindings()))
        with redirect_stderr(io.StringIO()): sink.feed(result.stderr)
        return result, sink.finish()

    def test_original_bootstrap_and_main_are_exactly_preserved(self):
        original = launch._BOOTSTRAP.replace('c=CONFIG', "c={'operation':'collect'}")
        with patch.object(launch, '_program', return_value=original):
            source, sha = transport._program(bindings())
        assignment = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
            and any(isinstance(v, ast.Name) and v.id == '_program' for v in n.targets))
        body = ast.literal_eval(assignment.value)
        self.assertEqual(body, original[:-len(transport.FOOTER)])
        self.assertEqual(sha, transport._hash(original.encode()))
        self.assertEqual(ast.dump(ast.parse(body)), ast.dump(
            ast.Module(body=ast.parse(original).body[:-1], type_ignores=[])))
        self.assertNotIn('setprofile', source)
        self.assertNotIn('settrace', source)

    def test_changed_or_duplicate_outer_footer_refused(self):
        for original in ('def main(): pass\n', transport.FOOTER*2):
            with patch.object(launch, '_program', return_value=original), self.assertRaises(ValueError):
                transport._program(bindings())

    def test_success_retains_float_null_and_one_main_call(self):
        body = 'calls=0\ndef main():\n global calls\n calls+=1\n assert calls==1\n return {"v":1.0,"missing":None}'
        result, diag = self.run_program(body)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'{"missing":null,"v":1.0}\n')
        self.assertEqual([v['event'] for v in diag['records']], ['started','returned'])
        self.assertEqual(diag['records'][-1]['stdout_sha256'], transport._hash(result.stdout))

    def test_private_error_message_is_never_returned(self):
        result, diag = self.run_program('def main():\n raise ValueError("PRIVATE SECRET SOLUTION")')
        self.assertEqual(result.returncode, 1); self.assertEqual(result.stdout, b'')
        self.assertNotIn(b'PRIVATE', result.stderr)
        fault = diag['records'][-1]['exceptions'][0]
        self.assertEqual(fault['type'], 'ValueError')
        self.assertTrue(any(v['source']=='bootstrap' for v in fault['frames']))
        self.assertEqual(set(fault), {'type','frames'})

    def test_nested_error_chain_has_types_and_bound_lines_only(self):
        result, diag = self.run_program('def main():\n try: raise KeyError("PRIVATE ONE")\n except KeyError as exc: raise RuntimeError("PRIVATE TWO") from exc')
        errors = diag['records'][-1]['exceptions']
        self.assertEqual([e['type'] for e in errors], ['RuntimeError','KeyError'])
        self.assertNotIn(b'PRIVATE', result.stderr)

    def test_unknown_exception_class_name_is_redacted(self):
        result, diag = self.run_program('class PRIVATE_ERROR(Exception): pass\ndef main():\n raise PRIVATE_ERROR("PRIVATE")')
        self.assertEqual(diag['records'][-1]['exceptions'][0]['type'], 'OtherError')
        self.assertNotIn(b'PRIVATE', result.stderr)

    def test_systemexit_is_a_failure_not_success(self):
        result, diag = self.run_program('def main():\n raise SystemExit("PRIVATE")')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(diag['records'][-1]['exceptions'][0]['type'], 'SystemExit')
        self.assertNotIn(b'PRIVATE', result.stderr)

    def test_sampling_has_only_source_lines_and_does_not_claim_pass(self):
        result, diag = self.run_program('import time\ndef main():\n time.sleep(0.12)\n return {}')
        self.assertEqual(result.returncode, 0)
        samples = [v for v in diag['records'] if v['event']=='sample']
        self.assertTrue(samples)
        self.assertTrue(all(set(frame)=={'source','line'} for s in samples for frame in s['frames']))
        self.assertTrue(diag['samples_are_not_passed_checks'])

    def test_tampered_bootstrap_never_enters_main(self):
        source = program('def main():\n return {}')
        source = source.replace('def main():', 'def changed():', 1)
        result = subprocess.run([sys.executable,'-I','-B','-'],input=source.encode(),capture_output=True,timeout=5)
        self.assertEqual(result.returncode, 1); self.assertEqual(result.stdout, b'')
        self.assertNotIn(b'"event":"started"', result.stderr)

    def test_collector_error_has_no_default_traceback(self):
        result, _ = self.run_program('def main():\n raise OSError("PRIVATE")')
        self.assertNotIn(b'Traceback', result.stderr)
        self.assertNotIn(b'PRIVATE', result.stderr)


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.sink = transport._Diagnostics({'bound.py':'execution/bound.py'})
        self.enterContext(redirect_stderr(io.StringIO()))

    def feed(self, value):
        self.sink.feed(transport.PREFIX+json.dumps(value).encode()+b'\n')

    def test_fragmented_known_metadata_is_parsed(self):
        raw = transport.PREFIX+b'{"event":"sample","elapsed_seconds":1,"frames":[{"source":"execution/bound.py","line":8}]}\n'
        for byte in raw: self.sink.feed(bytes([byte]))
        self.assertEqual(len(self.sink.records),1)

    def test_raw_exception_output_is_counted_not_retained(self):
        self.sink.feed(b'PRIVATE SECRET\n')
        self.assertEqual(self.sink.finish()['redacted_stderr_records'],1)
        self.assertNotIn('PRIVATE', json.dumps(self.sink.finish()))

    def test_unbound_source_and_extra_fields_are_redacted(self):
        for frames in ([{'source':'PRIVATE/solution.py','line':1}], [{'source':'execution/bound.py','line':1,'locals':'PRIVATE'}]):
            self.feed(dict(event='sample',elapsed_seconds=1,frames=frames))
        self.assertFalse(self.sink.records); self.assertEqual(self.sink.redacted_records,2)

    def test_duplicate_json_keys_refused(self):
        self.sink.feed(transport.PREFIX+b'{"event":"sample","event":"sample","elapsed_seconds":1,"frames":[]}\n')
        self.assertFalse(self.sink.records); self.assertEqual(self.sink.redacted_records,1)

    def test_oversized_unterminated_and_invalid_utf8_are_redacted(self):
        self.sink.feed(b'x'*(transport.LINE_WINDOW+100)+b'\n')
        self.sink.feed(transport.PREFIX+b'\xff\n')
        self.sink.feed(b'PRIVATE')
        self.assertEqual(self.sink.finish()['redacted_stderr_records'],3)
        self.assertFalse(self.sink.partial)

    def test_bool_nan_negative_and_huge_numeric_metadata_rejected(self):
        for value in (True,float('nan'),float('inf'),-1,10**30):
            self.feed(dict(event='sample',elapsed_seconds=value,frames=[]))
        self.assertFalse(self.sink.records)

    def test_unknown_exception_names_or_fields_are_refused(self):
        for error in ({'type':'PRIVATE','frames':[]},{'type':'ValueError','frames':[],'message':'PRIVATE'}):
            self.feed(dict(event='failed',elapsed_seconds=1,exceptions=[error]))
        self.assertFalse(self.sink.records)

    def test_metadata_record_count_is_bounded(self):
        for _ in range(transport.MAX_RECORDS+3):
            self.feed(dict(event='sample',elapsed_seconds=1,frames=[]))
        self.assertEqual(len(self.sink.records), transport.MAX_RECORDS)
        self.assertEqual(self.sink.redacted_records,3)


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(launch,'_command',return_value=[sys.executable,'-I','-B','-']))
        self.enterContext(redirect_stderr(io.StringIO()))

    def test_real_local_pipe_success(self):
        raw, info = transport._exchange(program('def main():\n return {"v":1.0}'),bindings())
        self.assertEqual(raw,b'{"v":1.0}\n'); self.assertEqual(info['returncode'],0)
        self.assertFalse(info['native_state_requires_inspection'])

    def test_real_timeout_is_distinct_and_never_retries(self):
        with patch.object(transport,'TRANSPORT_SECONDS',0.15), patch.object(transport,'SAMPLE_SECONDS',0.03):
            source = program('import time\ndef main():\n time.sleep(3)\n return {}')
            with self.assertRaises(transport.AuditTransportError) as caught:
                transport._exchange(source,bindings())
        self.assertEqual(caught.exception.metadata['status'],'transport_timeout')
        self.assertTrue(caught.exception.metadata['native_state_requires_inspection'])
        self.assertFalse(caught.exception.metadata['automatic_resume'])
        self.assertTrue(caught.exception.metadata['diagnostics']['records'])

    def test_remote_failure_retains_private_safe_trace(self):
        with self.assertRaises(transport.AuditTransportError) as caught:
            transport._exchange(program('def main():\n raise ValueError("PRIVATE")'),bindings())
        info = caught.exception.metadata
        self.assertEqual(info['status'],'ssh_exit')
        self.assertEqual(info['returncode'],1)
        self.assertEqual(info['diagnostics']['records'][-1]['event'],'failed')
        self.assertNotIn('PRIVATE',str(caught.exception)+json.dumps(info))

    def test_send_deadline_failure_is_classified_as_timeout(self):
        with patch.object(transport.receiver,'_send',side_effect=ValueError('PRIVATE')), \
                patch.object(transport.time,'monotonic',side_effect=[0,1801,1801.1]), \
                self.assertRaises(transport.AuditTransportError) as caught:
            transport._exchange('ignored',bindings())
        self.assertEqual(caught.exception.metadata['status'],'transport_timeout')
        self.assertNotIn('PRIVATE',json.dumps(caught.exception.metadata))

    def test_transport_start_failure_is_metadata_only(self):
        with patch.object(transport.subprocess,'Popen',side_effect=OSError('PRIVATE')), self.assertRaises(transport.AuditTransportError) as caught:
            transport._exchange('ignored',bindings())
        self.assertEqual(caught.exception.metadata['status'],'transport_start')
        self.assertNotIn('PRIVATE',json.dumps(caught.exception.metadata))

    def test_stdout_window_is_bounded_without_raw_output_leak(self):
        with patch.object(launch,'WINDOW',16),self.assertRaises(transport.AuditTransportError) as caught:
            transport._exchange(program('def main():\n return {"secret":"PRIVATE"*100}'),bindings())
        self.assertEqual(caught.exception.metadata['status'],'reply_window_exceeded')
        self.assertNotIn('PRIVATE',json.dumps(caught.exception.metadata))

    def test_unknown_stderr_is_redacted_but_does_not_replace_validation(self):
        source=program('import os\ndef main():\n os.write(2,b"PRIVATE WARNING\\n")\n return {}')
        raw, info=transport._exchange(source,bindings())
        self.assertEqual(raw,b'{}\n')
        self.assertEqual(info['diagnostics']['redacted_stderr_records'],1)
        self.assertNotIn('PRIVATE',json.dumps(info))


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        (self.root/'.runtime/netcup').mkdir(parents=True,mode=0o700)
        (self.root/'.runtime').chmod(0o700)
        self.enterContext(patch.object(launch,'REPO',self.root))
        self.bind=bindings(); self.raw=b'{"reporting_source_files":{"stage2/example.py":"'+b'b'*64+b'"},"aggregates":{"full89":{"passed":50,"no_verifier_result":3}}}\n'
        self.info=metadata(self.raw)
        self.enterContext(patch.object(transport,'_prepare',return_value=self.bind))
        self.preflight=self.enterContext(patch.object(launch,'inspect_deployment'))
        self.recheck=self.enterContext(patch.object(launch,'_recheck'))
        self.enterContext(patch.object(transport,'_program',return_value=('source','d'*64)))
        self.exchange=self.enterContext(patch.object(transport,'_exchange',return_value=(self.raw,self.info)))
        self.validate=self.enterContext(patch.object(archive_module(),'validate_snapshot'))
        self.folder=self.root/transport.DESTINATION

    def test_success_is_one_actual_call_and_private_exact_raw_snapshot(self):
        result=transport.collect('a'*40)
        self.assertTrue(result['completed_final_audit_verified'])
        self.assertFalse(result['off_server_backup_verified']); self.assertFalse(result['paid_launch_ready'])
        self.assertEqual(self.exchange.call_count,1); self.assertEqual(self.preflight.call_count,1)
        self.assertEqual((self.folder/'snapshot.json').read_bytes(),self.raw)
        self.assertEqual({p.name for p in self.folder.iterdir()},{'intent.json','diagnostics.json','snapshot.json','result.json'})
        self.assertTrue(all(p.stat().st_mode & 0o077 == 0 for p in self.folder.iterdir()))
        self.validate.assert_called_once()

    def test_completed_or_partial_state_forbids_repetition_before_native_preflight(self):
        self.folder.mkdir(mode=0o700)
        with self.assertRaises(ValueError): transport.collect('a'*40)
        self.preflight.assert_not_called(); self.exchange.assert_not_called()

    def test_success_cannot_be_repeated(self):
        transport.collect('a'*40)
        with self.assertRaises(ValueError): transport.collect('a'*40)
        self.assertEqual(self.exchange.call_count,1)

    def test_symlink_destination_refuses(self):
        self.folder.symlink_to(self.root/'.runtime/netcup',target_is_directory=True)
        with self.assertRaises(ValueError): transport.collect('a'*40)
        self.exchange.assert_not_called()

    def test_preflight_refusal_creates_no_state_or_collect(self):
        self.preflight.side_effect=ValueError('refused')
        with self.assertRaises(ValueError): transport.collect('a'*40)
        self.assertFalse(self.folder.exists()); self.exchange.assert_not_called()

    def test_timeout_failure_is_retained_and_not_repeated(self):
        info=dict(self.info,status='transport_timeout',error_type='TimeoutError',returncode=None)
        self.exchange.side_effect=transport.AuditTransportError(info)
        with self.assertRaises(transport.AuditTransportError): transport.collect('a'*40)
        self.assertEqual({p.name for p in self.folder.iterdir()},{'intent.json','failure.json'})
        failure=json.loads((self.folder/'failure.json').read_bytes())
        self.assertEqual(failure['transport']['status'],'transport_timeout')
        with self.assertRaises(ValueError): transport.collect('a'*40)
        self.assertEqual(self.exchange.call_count,1)

    def test_invalid_snapshot_is_not_saved(self):
        self.validate.side_effect=ValueError('PRIVATE')
        with self.assertRaises(transport.AuditTransportError): transport.collect('a'*40)
        self.assertFalse((self.folder/'snapshot.json').exists())
        self.assertNotIn('PRIVATE',(self.folder/'failure.json').read_text())

    def test_changed_sources_after_transport_refuse_success(self):
        self.recheck.side_effect=[None,None,ValueError('PRIVATE')]
        with self.assertRaises(transport.AuditTransportError): transport.collect('a'*40)
        self.assertFalse((self.folder/'result.json').exists())

    def test_intent_mutation_during_transport_cannot_complete(self):
        def changed(*args):
            (self.folder/'intent.json').write_bytes(b'{}')
            return self.raw,self.info
        self.exchange.side_effect=changed
        with self.assertRaises(transport.AuditTransportError): transport.collect('a'*40)
        self.assertFalse((self.folder/'result.json').exists())

    def test_extra_state_file_during_transport_refuses(self):
        def changed(*args):
            (self.folder/'unexpected').write_bytes(b'PRIVATE')
            return self.raw,self.info
        self.exchange.side_effect=changed
        with self.assertRaises(transport.AuditTransportError): transport.collect('a'*40)
        self.assertFalse((self.folder/'result.json').exists())

    def test_final_source_drift_retains_failure_even_after_result_write(self):
        self.recheck.side_effect=[None,None,None,None,None,ValueError('PRIVATE')]
        with self.assertRaises(transport.AuditTransportError): transport.collect('a'*40)
        self.assertTrue((self.folder/'result.json').exists())
        self.assertTrue((self.folder/'failure.json').exists())

    def test_absent_return_duplicate_start_failed_or_wrong_hash_refuse(self):
        for kind in ('no_return','duplicate_start','failed','wrong_hash'):
            with self.subTest(kind=kind):
                info=deepcopy(self.info); records=info['diagnostics']['records']
                if kind=='no_return': records.pop()
                if kind=='duplicate_start': records.insert(1,deepcopy(records[0]))
                if kind=='failed': records.insert(1,dict(event='failed',elapsed_seconds=0.5,exceptions=[]))
                if kind=='wrong_hash': records[-1]['stdout_sha256']='0'*64
                with self.assertRaises(ValueError): transport._reply(self.raw,info,self.bind)

    def test_wrong_reporting_binding_refuses(self):
        other=dict(self.bind,reporting={})
        with self.assertRaises(ValueError): transport._reply(self.raw,self.info,other)

    def test_transport_error_or_nonzero_exit_cannot_be_saved_as_success(self):
        for key,value in (('status','transport_timeout'),('error_type','TimeoutError'),('returncode',1)):
            info=dict(self.info,**{key:value})
            with self.assertRaises(ValueError): transport._reply(self.raw,info,self.bind)

    def test_unexpected_stdout_is_not_saved(self):
        self.exchange.return_value=(b'PRIVATE\n'+self.raw,self.info)
        with self.assertRaises(transport.AuditTransportError): transport.collect('a'*40)
        self.assertFalse((self.folder/'snapshot.json').exists())
        self.assertNotIn('PRIVATE',(self.folder/'failure.json').read_text())


def archive_module():
    return transport.archive


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.enterContext(patch.object(launch,'REPO',self.root))
        self.enterContext(patch.object(transport,'__file__',str(self.root/transport.SOURCE_FILES[0])))
        self.bind=bindings(); self.bind['reporting']={'stage2/installed.py':transport._hash(b'installed')}
        self.enterContext(patch.object(launch,'_prepare',return_value=self.bind))
        for name in transport.SOURCE_FILES:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'new source')
        self.git=self.enterContext(patch.object(launch,'_git',side_effect=lambda *args:
            b'installed' if args[-1].startswith(transport.INSTALLED_REVISION+':') else b'new source'))

    def test_installed_revision_and_new_committed_sources_bound(self):
        value=transport._prepare('a'*40)
        self.assertTrue(set(transport.SOURCE_FILES)<=set(value['local']))
        self.assertEqual(self.git.call_count,1+len(transport.SOURCE_FILES))

    def test_changed_installed_bundle_refuses(self):
        self.bind['reporting']['stage2/installed.py']='0'*64
        with self.assertRaises(ValueError): transport._prepare('a'*40)

    def test_uncommitted_transport_source_refuses(self):
        (self.root/transport.SOURCE_FILES[0]).write_bytes(b'dirty')
        with self.assertRaises(ValueError): transport._prepare('a'*40)

    def test_new_source_symlink_refuses(self):
        p=self.root/transport.SOURCE_FILES[1];p.unlink();p.symlink_to(self.root/transport.SOURCE_FILES[0])
        with self.assertRaises(ValueError): transport._prepare('a'*40)


class RealSchemaTests(unittest.TestCase):
    def test_actual_amended_validator_retains_three_missing_outcomes(self):
        fixture=fixtures.ArchiveTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        value=fixture.data
        raw=json.dumps(value,separators=(',',':')).encode()+b'\n'
        bind=dict(anchors=fixture.anchors,reporting=value['reporting_source_files'])
        checked=transport._reply(raw,metadata(raw),bind)
        self.assertEqual(checked['aggregates']['full89']['no_verifier_result'],3)
        self.assertIsNone(checked['rows'][0]['agent_seconds'])
        self.assertFalse(checked['paid_launch_ready'])


if __name__ == '__main__':
    unittest.main()
