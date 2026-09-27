"""Mocked native audit, real temporary-file integrity; no SSH or paid calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import export_no_cutoff_custom as exporter
import no_cutoff_evidence_freeze as freeze
import no_cutoff_final_candidate as candidate
import no_cutoff_custom_policy as revision
from test_no_cutoff_final_candidate import FinalistFixture


def snapshot(fixture):
    proof=fixture.proof;rt=fixture.private
    data=dict(condition=revision.CONDITION,registration=fixture.block,
        qualification_sha256=revision.fingerprint(proof),sources=proof['sources'],
        model_protocol=revision.SETTINGS.document(),policy=revision.POLICY,
        service=dict(ActiveState='inactive',SubState='dead',MainPID='0',ExecMainStatus='0'),
        audit_checks=dict.fromkeys(exporter.CHECKS,True),collected_utc='2026-09-28T00:00:00Z',
        bindings={'.runtime/stage2/'+name:freeze._digest(fixture.repo,
            candidate.PRIVATE+'/.runtime/stage2/'+name) for name in candidate.PRIVATE_FILES},rows=[])
    data['bindings'].update(proof['evidence_files'])
    data['bindings']['.runtime/stage2/no-cutoff-development-blocks/C0-NC.json']=fixture.registration['registration_file_sha256']
    data['bindings']['.runtime/stage2/python-runtime.tar.gz']=revision.PYTHON_SHA256
    for original in fixture.rows:
        row=dict.fromkeys(exporter.ROW_FIELDS,0)
        row.update({k:original[k] for k in ('trial_id','task_id','harness','reward','agent_seconds','result_sha256')})
        row.update(status='verified',started_utc='2026-09-28T00:00:00Z',completed_utc='2026-09-28T00:01:00Z',
            agent_error_type='',verifier_error_type='',model_requests=2,accepted_model_responses=1,
            interrupted_requests=1,unknown_cost_requests=1,known_cost_usd='0.01',total_cost_usd=None,
            input_tokens=None,output_tokens=None,cleanup_complete=True,model_revoked=True,
            official_agent_timeout_seconds=100.0,official_verifier_timeout_seconds=30.0,
            official_cpus=1,official_memory_mb=2048)
        data['rows'].append(row)
    return data


class FreezeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.repo=Path(temp.name);self.f=FinalistFixture(self,self.repo)
        self.data=snapshot(self.f)
        self.enterContext(patch.object(exporter,'OUTPUT',self.f.output))
        self.enterContext(patch.object(exporter,'ORIGINAL_FREEZE_SHA256',revision.fingerprint(self.f.original)))
        self.reader=self.enterContext(patch.object(freeze,'_read_revision',side_effect=lambda bindings:deepcopy(self.data)))

    def test_capture_binds_hundred_results_and_revised_runtime_without_paid_authority(self):
        doc=freeze.capture(self.repo)
        self.assertEqual(len(doc['result_bindings']),100)
        self.assertEqual(doc['validation_summary']['passes'],12)
        self.assertEqual(doc['selected_execution']['candidate_version'],'stage2-candidate-0.5.0')
        self.assertFalse(doc['paid_launch_ready']);self.assertFalse(doc['original_score_inherited'])
        self.assertEqual(doc['revision_qualification'],self.f.proof)
        self.assertEqual(doc['anchor_files'].keys(),candidate.BASE_ANCHORS | {
            candidate.PRIVATE+'/'+name for name in self.f.proof['evidence_files']})
        self.assertFalse((self.repo/'.runtime/finalisation'/freeze.FREEZE_FILE).exists())
        native=self.reader.call_args.args[0]
        self.assertTrue(all(native['stage2/'+name]==digest for name,digest in self.f.proof['sources'].items()))
        self.assertEqual(native['.runtime/stage2/python-runtime.tar.gz'],revision.PYTHON_SHA256)
        self.assertEqual(native['.runtime/stage2/no-cutoff-development-blocks/C0-NC.json'],
            self.f.registration['registration_file_sha256'])

    def test_missing_verifier_and_unknown_cost_stay_missing(self):
        self.data['rows'][-1].update(reward=None,status='verifier_failed',verifier_error_type='RuntimeError')
        value=freeze.capture(self.repo)['validation_summary']
        self.assertEqual((value['passes'],value['failures'],value['no_verifier_result']),(12,7,1))
        self.assertEqual(value['unknown_cost_requests'],20);self.assertIsNone(value['charged_usd'])

    def test_missing_phase_duration_is_not_fabricated(self):
        self.data['rows'][-1]['agent_seconds']=None
        with self.assertRaises(ValueError):freeze.capture(self.repo)

    def test_fresh_verification_ignores_only_observation_time(self):
        doc=freeze.capture(self.repo);self.data['collected_utc']='2026-09-28T02:00:00+00:00'
        self.assertEqual(freeze.verify(doc,self.repo)['harness'],'C0-NC')
        self.assertEqual(self.reader.call_count,2)
        self.data['rows'][0]['result_sha256']='a'*64
        with self.assertRaises(ValueError):freeze.verify(doc,self.repo)

    def test_active_incomplete_duplicate_extra_or_wrong_order_refused(self):
        baseline=deepcopy(self.data)
        for change in ('active','missing','duplicate','extra','order','no-revocation','no-cleanup','audit'):
            self.data=deepcopy(baseline)
            if change=='active':self.data['service']['ActiveState']='active'
            elif change=='missing':self.data['rows'].pop()
            elif change=='duplicate':self.data['rows'][1]=self.data['rows'][0]
            elif change=='extra':self.data['rows'].append(deepcopy(self.data['rows'][0]))
            elif change=='order':self.data['rows'].reverse()
            elif change=='no-revocation':self.data['rows'][0]['model_revoked']=False
            elif change=='no-cleanup':self.data['rows'][0]['cleanup_complete']=False
            else:self.data['audit_checks']['official_limits']=False
            with self.subTest(change=change),self.assertRaises(ValueError):freeze.capture(self.repo)

    def test_private_fields_or_unbound_evidence_refused(self):
        baseline=deepcopy(self.data)
        for change in ('private','row-private','binding','extra-binding','extra-audit','substate','timestamp'):
            self.data=deepcopy(baseline)
            if change=='private':self.data['requests']=['private']
            elif change=='row-private':self.data['rows'][0]['command']='private'
            elif change=='binding':self.data['bindings']['.runtime/stage2/no-cutoff-runtime.json']='0'*64
            elif change=='extra-binding':self.data['bindings']['.runtime/stage2/other.json']='0'*64
            elif change=='extra-audit':self.data['audit_checks']['new']=True
            elif change=='substate':self.data['service']['SubState']='failed'
            else:self.data['collected_utc']='2026-09-28T01:00:00'
            with self.subTest(change=change),self.assertRaises(ValueError):freeze.capture(self.repo)

    def test_changed_full_qualification_bytes_or_projection_rejected_before_audit(self):
        for target in (self.f.private/revision.QUALIFICATION,self.f.output/'qualification.json'):
            before=target.read_bytes()
            if target.name==revision.QUALIFICATION:target.write_bytes(before+b' ')
            else:
                value=json.loads(before);value['dependencies']['packages']['harbor']='0.99.0';target.write_text(json.dumps(value))
            with self.subTest(target=target),self.assertRaises(ValueError):freeze.capture(self.repo)
            target.write_bytes(before)
        self.reader.assert_not_called()

    def test_policy_runtime_auth_and_producer_bytes_rechecked(self):
        paths=[self.f.private/name for name in (revision.POLICY_FILE,revision.RUNTIME_FILE,revision.AUTHENTICATION_FILE)]
        paths.append(self.repo/candidate.PRIVATE/next(iter(self.f.proof['evidence_files'])))
        for path in paths:
            before=path.read_bytes();path.write_bytes(before+b' ')
            with self.subTest(path=path),self.assertRaises(ValueError):freeze.capture(self.repo)
            path.write_bytes(before)
        self.reader.assert_not_called()

    def test_changed_original_or_registration_or_lineage_refused(self):
        for path in (self.repo/candidate.ORIGINAL,self.repo/candidate.PRIVATE/'C0-NC.json',self.f.output/'lineage.json'):
            before=path.read_bytes();value=json.loads(before)
            if path.name=='lineage.json':value['original_score_inherited']=True
            elif path.name=='C0-NC.json':value['condition']='C0'
            else:value['selected_execution']['harness']='C1'
            path.write_text(json.dumps(value))
            with self.subTest(path=path),self.assertRaises(ValueError):freeze.capture(self.repo)
            path.write_bytes(before)
        self.reader.assert_not_called()

    def test_changed_qualified_collector_rejected_before_remote_execution(self):
        (self.repo/'stage2/export_no_cutoff_custom.py').write_text('# different audit\n')
        with self.assertRaises(ValueError):freeze.capture(self.repo)
        self.reader.assert_not_called()

    def test_mutations_during_capture_or_later_verification_rejected(self):
        for relative in (candidate.RESULTS+'/credit-policy.json','stage2/no_cutoff_final_candidate.py'):
            path=self.repo/relative;before=path.read_bytes()
            def mutate(bindings):
                path.write_bytes(before+b' ');return deepcopy(self.data)
            with patch.object(freeze,'_read_revision',side_effect=mutate),self.assertRaises(ValueError):freeze.capture(self.repo)
            path.write_bytes(before)
        doc=freeze.capture(self.repo)
        (self.repo/'stage2/no_cutoff_evidence_freeze.py').write_text('# changed new capture code')
        with self.assertRaises(ValueError):freeze.verify(doc,self.repo)

    def test_symlink_anchor_logic_and_private_evidence_rejected(self):
        names=[candidate.RESULTS+'/lineage.json','stage2/no_cutoff_final_candidate.py',
            candidate.PRIVATE+'/'+next(iter(self.f.proof['evidence_files']))]
        for name in names:
            path=self.repo/name;saved=path.with_name(path.name+'.saved');path.rename(saved);path.symlink_to(saved)
            with self.subTest(name=name),self.assertRaises(ValueError):freeze.capture(self.repo)
            path.unlink();saved.rename(path)

    def test_duplicate_json_fields_and_insecure_private_file_refused(self):
        path=self.f.output/'credit-policy.json';before=path.read_bytes()
        path.write_text('{"project_cap_usd":null,"project_cap_usd":1}')
        with self.assertRaises(ValueError):freeze.capture(self.repo)
        path.write_bytes(before)
        (self.f.private/revision.QUALIFICATION).chmod(0o644)
        with self.assertRaises(ValueError):freeze.capture(self.repo)
        self.reader.assert_not_called()

    def test_private_save_is_exclusive_idempotent_and_never_replaces_different_evidence(self):
        doc=freeze.save(self.repo);path=self.repo/'.runtime/finalisation'/freeze.FREEZE_FILE
        before=(path.read_bytes(),path.stat().st_mtime_ns)
        self.assertEqual(freeze.save(self.repo),doc)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.data['rows'][0]['result_sha256']='e'*64
        with self.assertRaises(ValueError):freeze.save(self.repo)
        self.assertEqual(path.read_bytes(),before[0])

    def test_concurrent_save_and_symlinked_state_refused(self):
        with patch.object(freeze,'hold',side_effect=BlockingIOError),self.assertRaises(BlockingIOError):freeze.save(self.repo)
        self.reader.assert_not_called()
        path=self.repo/'.runtime/finalisation';other=self.repo/'.runtime/finalisation-saved'
        path.rename(other);path.symlink_to(other,target_is_directory=True)
        with self.assertRaises(ValueError):freeze.save(self.repo)


class NativeReaderTests(unittest.TestCase):
    def test_program_uses_unchanged_collector_and_guards_active_run_before_locks(self):
        bindings={'stage2/fixture.py':'a'*64}
        program=freeze._revision_program(bindings);compile(program,'<synthetic-native-reader>','exec')
        self.assertIn(exporter.program(exporter.COLLECT,revision.CONDITION),program)
        self.assertLess(program.index('_finalist_state'),program.index('original.authenticate'))
        self.assertLess(program.index('_finalist_check_files()\n'),program.index('original.authenticate'))
        self.assertNotIn('run_trial(',program);self.assertNotIn(exporter.BACKUP,program)
        with patch.object(freeze.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'{"ok":true}','')) as run:
            self.assertEqual(freeze._read_revision(bindings),{'ok':True})
        self.assertEqual(run.call_args.args[0],exporter.remote_command())
        self.assertEqual(run.call_args.kwargs['input'],program)

    def test_active_service_and_operator_stop_before_or_during_audit_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'.runtime/stage2/operator-stop-request.json';marker.parent.mkdir(parents=True)
            source=Path(folder)/'source.py';source.write_text('# Synthetic source')
            bindings={'source.py':hashlib.sha256(source.read_bytes()).hexdigest()}
            with patch.object(exporter,'REMOTE',folder),patch.object(exporter,'COLLECT','audit_ran=True'):
                for state in ('ActiveState=active\nMainPID=123\nExecMainStatus=0',
                              'ActiveState=inactive\nMainPID=0\nExecMainStatus=1'):
                    scope={}
                    with patch('subprocess.check_output',return_value=state),self.assertRaises(ValueError):
                        exec(freeze._revision_program(bindings),scope)
                    self.assertNotIn('audit_ran',scope)
                state='ActiveState=inactive\nMainPID=0\nExecMainStatus=0'
                with patch('subprocess.check_output',return_value=state):
                    scope={};exec(freeze._revision_program(bindings),scope);self.assertTrue(scope['audit_ran'])
                    marker.write_text('{}')
                    with self.assertRaises(ValueError):exec(freeze._revision_program(bindings),{})
                    marker.unlink()
                    with patch.object(exporter,'COLLECT','_finalist_stop.write_text("{}")'),self.assertRaises(ValueError):
                        exec(freeze._revision_program(bindings),{})

    def test_changed_or_symlinked_native_files_rejected_before_collector(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.py';source.write_text('# Synthetic source')
            bindings={'source.py':hashlib.sha256(source.read_bytes()).hexdigest()}
            with patch.object(exporter,'REMOTE',folder),patch.object(exporter,'COLLECT','audit_ran=True'), \
                    patch('subprocess.check_output',return_value='ActiveState=inactive\nMainPID=0\nExecMainStatus=0'):
                program=freeze._revision_program(bindings)
                source.write_text('# Changed source');scope={}
                with self.assertRaises(ValueError):exec(program,scope)
                self.assertNotIn('audit_ran',scope)
                source.unlink();source.symlink_to(Path(folder)/'missing');scope={}
                with self.assertRaises(ValueError):exec(program,scope)
                self.assertNotIn('audit_ran',scope)

    def test_native_mutation_during_collector_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.py';source.write_text('# Synthetic source')
            bindings={'source.py':hashlib.sha256(source.read_bytes()).hexdigest()}
            changed='(_finalist_root/"source.py").write_text("# Changed during collector")'
            with patch.object(exporter,'REMOTE',folder),patch.object(exporter,'COLLECT',changed), \
                    patch('subprocess.check_output',return_value='ActiveState=inactive\nMainPID=0\nExecMainStatus=0'):
                with self.assertRaises(ValueError):exec(freeze._revision_program(bindings),{})

    def test_unsafe_or_missing_native_bindings_refused(self):
        for values in ({},{'/escape':'a'*64},{'../escape':'a'*64},{'a//b':'a'*64},{'a':'invalid'}):
            with self.subTest(values=values),self.assertRaises(ValueError):freeze._revision_program(values)

    def test_failed_or_malformed_remote_output_not_retried_or_exposed(self):
        for code,out in ((1,''),(0,'private raw text')):
            with patch.object(freeze.subprocess,'run',return_value=subprocess.CompletedProcess([],code,out,'private diagnostics')) as run:
                with self.assertRaises(RuntimeError) as error:freeze._read_revision({'source.py':'a'*64})
            self.assertNotIn('private',str(error.exception));self.assertEqual(run.call_count,1)

    def test_timeout_or_process_failure_diagnostics_not_exposed(self):
        for issue in (OSError('private details'),subprocess.TimeoutExpired(['private'],180,output='private')):
            with patch.object(freeze.subprocess,'run',side_effect=issue) as run:
                with self.assertRaises(RuntimeError) as error:freeze._read_revision({'source.py':'a'*64})
            self.assertNotIn('private',str(error.exception));self.assertEqual(run.call_count,1)


if __name__=='__main__':unittest.main()
