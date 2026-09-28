"""Local synthetic89 audit tests; all native/service/Docker observations mocked."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import credit_only_accounting as accounting
from credit_only_experiment import coverage
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import test_no_cutoff_final_phase_audit as fixtures


class CompletedAuditTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.PhaseFiles(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.events = []; self.locked = False
        self.reporting = self.root / 'reporting'; self.reporting.mkdir()
        for name in report.REPORTING_FILES:
            path = self.reporting / 'stage2' / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((fixtures.STAGE / name).read_bytes())
        self.enterContext(patch.object(report, 'ROOT', self.root))
        self.enterContext(patch.object(report, 'REPORTING', self.reporting))
        self.enterContext(patch.object(report, '_context'))
        self.service = self.enterContext(patch.object(report, '_service', return_value=dict(
            ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0')))
        self.resources = self.enterContext(patch.object(report, '_resources'))
        self.prepare89()
        self.native = NS(study=NS(read_candidate=Mock(return_value={'synthetic': True}),
            qualified=Mock(side_effect=self.qualified), audited=Mock(side_effect=self.audited)),
            runtime=NS(loaded_sources=Mock(), sources=Mock(side_effect=lambda *a: self.f.proof['sources'])),
            original=NS(authenticate=Mock(side_effect=self.authenticate), recheck=Mock(side_effect=self.recheck)),
            runner=NS(lock_all=Mock(side_effect=self.lock_all)),
            policy=NS(require_block=Mock(side_effect=lambda *a: deepcopy(self.f.block)),
                SETTINGS=NS(document=lambda: {'synthetic': True}), POLICY={'synthetic': True}),
            accounting=accounting, frozen_dataset=Mock(return_value=self.root / 'dataset'),
            Task=Mock(side_effect=lambda *a: NS(config=NS(agent=NS(timeout_sec=7200.0),
                verifier=NS(timeout_sec=900.0), environment=NS(cpus=1, memory_mb=2048)))))
        self.enterContext(patch.object(report, '_native', return_value=self.native))
        self.baseline = self.root / 'baseline'; self.baseline.mkdir()
        self.stopped = self.root / 'stopped'; self.stopped.mkdir()
        self.enterContext(patch.object(report, 'BASELINE', self.baseline))
        self.enterContext(patch.object(report, 'STOPPED', self.stopped))
        historical = {}
        for base, count, filename in ((self.baseline, 178, report.BASELINE_CSV), (self.stopped, 4, report.STOPPED_JSON)):
            rows = []
            for i in range(count):
                name = 'historical-' + str(i)
                path = base / phase.RT / 'scored-trials' / name / 'result.json'
                path.parent.mkdir(parents=True, mode=0o700); path.write_bytes(b'{"private":true}'); path.chmod(0o600)
                rows.append(dict(trial_id=name, result_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            if filename.endswith('.csv'):
                raw = ('trial_id,result_sha256\n' + ''.join(r['trial_id'] + ',' + r['result_sha256'] + '\n' for r in rows)).encode()
                historical[filename] = self.f.write(filename, raw)
            else:
                historical[filename] = self.f.save(filename, {'rows': rows})
        self.enterContext(patch.object(report, 'HISTORICAL_INPUTS', historical))
        self.lockfile = self.root / 'synthetic-ancestor.lock'; self.lockfile.touch(mode=0o600)

    def prepare89(self):
        f = self.f; template = deepcopy(f.result)
        self.ids = [f.trial_id] + ['customfinal2-c0-nc-%02d-synthetic-%02d' % (i, i) for i in range(2, 90)]
        tasks = ['synthetic'] + ['synthetic-%02d' % i for i in range(2, 90)]
        f.host['task_inventory'] = {t: dict(agent_timeout_seconds=7200.0, verifier_timeout_seconds=900.0,
            cpus=1, memory_mb=2048, image_id='sha256:' + '2' * 64) for t in tasks}
        f.proof.update(runtime_identity_sha256=phase.fingerprint(f.host), evidence_files={})
        for i in range(8):
            name = '.runtime/synthetic-producer-%d.json' % i
            f.proof['evidence_files'][name] = f.save(name, {'synthetic': i})
        qualification = phase.fingerprint(f.proof)
        f.block.update(qualification_sha256=qualification,
            cells=[dict(trial_id=name, task_id=task, harness='C0-NC') for name, task in zip(self.ids, tasks)])
        registration = phase.fingerprint(f.block)
        pins = dict(QUALIFICATION=qualification, REGISTRATION=registration,
            QUALIFICATION_FILE=f.save(phase.RT + 'no-cutoff-final-qualification.json', f.proof),
            REGISTRATION_FILE=f.save(phase.RT + 'no-cutoff-final-matrix.json', f.block),
            RUNTIME_FILE=f.save(phase.RT + 'no-cutoff-final-runtime.json', f.host))
        for name, value in pins.items(): self.enterContext(patch.object(phase, name, value))
        inputs = {}
        for name in report.INPUTS:
            path = self.root / phase.RT / name
            inputs[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else f.save(phase.RT + name, {'synthetic': name})
        self.enterContext(patch.object(report, 'INPUTS', inputs))
        for i, (name, task) in enumerate(zip(self.ids, tasks)):
            f.trial_id = name; f.task_id = task; f.trial = phase.RT + 'scored-trials/' + name
            f.accounting = phase.RT + 'scored-attempts/' + name; f.life = phase.RT + 'retry-lifecycle/' + name + '.json'
            f.result = deepcopy(template)
            f.result.update(trial_id=name, task_id=task, custom_registration_sha256=registration,
                project='uts-scored-%012x' % (i + 1))
            f.save(f.trial + '/started.json', {**{k: f.result[k] for k in f.identity}, 'status': 'starting'})
            reward = float(i % 2)
            f.result['verifier_result']['rewards']['reward'] = reward
            f.events = [f.event('trial', 0, 0, 5), f.event('setup', 1, 0, 1), f.event('agent', 2, 1, 3),
                f.event('verifier', 3, 3, 4, reward=reward), f.event('cleanup', 4, 4, 5)]
            f.save(f.life, dict(trial_id=name, model_protocol_sha256=phase.MODEL, boot_id='synthetic',
                deadline_monotonic=7200.0, deadline_utc=fixtures.BASE / 1e9 + 7201))
            f.save(f.accounting + '/started.json', {'trial_id': name})
            f.result['billing'] = accounting.summarise(self.root / phase.RT, name)
            f.flush()
            if i < 3: f.setup_only()

    def authenticate(self, *args):
        self.assertFalse(self.locked); self.events.append('authenticate'); return {'synthetic': True}

    @contextmanager
    def lock(self):
        with self.lockfile.open('rb') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB); self.locked = True
            self.events.append('lock')
            try: yield
            finally: self.locked = False; self.events.append('unlock')

    def lock_all(self, stack, root):
        self.assertEqual(root, self.root); stack.enter_context(self.lock())

    def recheck(self, *args):
        self.assertTrue(self.locked); self.events.append('recheck')
        with self.lockfile.open('rb') as handle:
            with self.assertRaises(BlockingIOError): fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def qualified(self, *args):
        self.assertTrue(self.locked); return deepcopy(self.f.proof)

    def audited(self, *args):
        self.assertTrue(self.locked)
        return coverage(self.root / phase.RT, self.f.block['cells'])

    def result_path(self, index=0):
        return self.root / phase.RT / 'scored-trials' / self.ids[index] / 'result.json'

    def change_result(self, **values):
        path = self.result_path(); data = json.loads(path.read_bytes()); data.update(values)
        path.write_text(json.dumps(data))

    def test_complete89_uses_real_phase_and_accounting_readers_with_native_observations_mocked(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        value = report.collect()
        self.assertEqual(len(value['rows']), 89); self.assertEqual(value['aggregates']['full89']['no_verifier_result'], 3)
        self.assertEqual(value['aggregates']['full89']['passed'], 43); self.assertEqual(value['aggregates']['full89']['failed'], 43)
        self.assertEqual(value['aggregates']['development20']['attempted'], 20)
        self.assertEqual(value['aggregates']['remaining69']['attempted'], 69)
        self.assertEqual([len(v) for v in value['preserved_result_files'].values()], [178, 4])
        self.assertEqual(len(value['absent_paths']), 3)
        self.assertTrue(value['completed_final_audit']); self.assertFalse(value['paid_launch_ready'])
        self.assertFalse(value['off_server_backup_verified']); self.assertFalse(value['archive_export_and_handoff_integrated'])
        self.assertEqual(value['aggregates']['full89']['phase_durations']['agent'], dict(
            measured_attempts=86, not_run_attempts=3, measured_subtotal_seconds=172.0, all_attempts_measured=False))
        self.assertEqual(self.events[:2], ['authenticate', 'lock']); self.assertEqual(self.events[-1], 'unlock')
        self.assertEqual(self.native.study.qualified.call_count, 2)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()})

    def test_active_unknown_or_failed_service_refused_before_lineage_and_locks(self):
        self.service.side_effect = ValueError('inactive required')
        with self.assertRaises(ValueError): report.collect()
        self.native.original.authenticate.assert_not_called(); self.native.runner.lock_all.assert_not_called()

    def test_operator_stop_refused_before_authentication(self):
        self.f.save(phase.RT + 'operator-stop-request.json', {'automatic_resume': False})
        with self.assertRaisesRegex(ValueError, 'Persistent stop'): report.collect()
        self.native.original.authenticate.assert_not_called()

    def test_service_rechecked_after_locks_before_audit(self):
        self.service.side_effect = [self.service.return_value, ValueError('changed')]
        with self.assertRaisesRegex(ValueError, 'changed'): report.collect()
        self.native.study.qualified.assert_not_called(); self.assertFalse(self.locked)

    def test_raw_input_change_rejected_before_authentication(self):
        path = self.root / phase.RT / 'no-cutoff-final-candidate.json'; path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(ValueError): report.collect()
        self.native.original.authenticate.assert_not_called()

    def test_frozen_collector_change_rejected_before_authentication(self):
        (self.root / 'stage2/export_no_cutoff_final.py').write_text('changed')
        with self.assertRaises(ValueError): report.collect()
        self.native.original.authenticate.assert_not_called()

    def test_actual_native_producer_changed_rejected_before_authentication(self):
        (self.root / next(iter(self.f.proof['evidence_files']))).write_text('{}')
        with self.assertRaises(ValueError): report.collect()
        self.native.original.authenticate.assert_not_called()

    def test_input_change_during_authentication_is_detected_under_lock(self):
        def changed(*args):
            (self.root / phase.RT / 'no-cutoff-final-manifest.json').write_text('{}'); return {}
        self.native.original.authenticate.side_effect = changed
        with self.assertRaises(ValueError): report.collect()
        self.native.study.qualified.assert_not_called()

    def test_partial_attempt_refused_without_dispatch_or_replay(self):
        self.result_path().unlink()
        with self.assertRaisesRegex(ValueError, 'coverage'): report.collect()

    def test_unexpected_attempt_refused(self):
        self.f.save(phase.RT + 'scored-trials/unregistered/started.json', {})
        with self.assertRaises(ValueError): report.collect()

    def test_original178_hash_drift_refused(self):
        path = next((self.baseline / phase.RT / 'scored-trials').glob('*/result.json')); path.write_text('{}')
        with self.assertRaises(ValueError): report.collect()

    def test_stopped_four_hash_drift_refused(self):
        path = next((self.stopped / phase.RT / 'scored-trials').glob('*/result.json')); path.write_text('{}')
        with self.assertRaises(ValueError): report.collect()

    def test_rewritten_historical_hash_list_is_not_a_new_anchor(self):
        (self.root / report.STOPPED_JSON).write_text('{"rows":[]}')
        with self.assertRaises(ValueError): report.collect()

    def test_actual_official_task_limits_are_read_and_compared(self):
        self.native.Task.side_effect = lambda *a: NS(config=NS(agent=NS(timeout_sec=60),
            verifier=NS(timeout_sec=900.0), environment=NS(cpus=1, memory_mb=2048)))
        with self.assertRaisesRegex(ValueError, 'official'): report.collect()

    def test_actual_resources_refused_not_deleted(self):
        self.resources.side_effect = ValueError('owned remains')
        with self.assertRaisesRegex(ValueError, 'owned remains'): report.collect()
        self.native.frozen_dataset.assert_not_called()

    def test_cleanup_and_revocation_still_required_for_setup_only(self):
        self.change_result(model_revoked=False)
        with self.assertRaises(ValueError): report.collect()

    def test_missing_executed_deadline_is_not_setup_only(self):
        (self.root / phase.RT / 'retry-lifecycle' / (self.ids[3] + '.json')).unlink()
        with self.assertRaises(ValueError): report.collect()

    def test_new_deadline_after_phase_read_rejected_on_final_reread(self):
        original = report._row
        def changed(*args):
            result = original(*args)
            if result['trial_id'] == self.ids[0]: self.f.save(phase.RT + 'retry-lifecycle/' + self.ids[0] + '.json', {})
            return result
        with patch.object(report, '_row', side_effect=changed), self.assertRaisesRegex(ValueError, 'absent'): report.collect()

    def test_accounting_outcomes_must_match_actual_retained_summary(self):
        data = json.loads(self.result_path().read_bytes()); data['billing']['charged_usd'] = '99'
        self.change_result(billing=data['billing'])
        with self.assertRaisesRegex(ValueError, 'accounting'): report.collect()

    def test_earlier_result_changed_after_row_read_rejected(self):
        original = report._row
        def changed(*args):
            value = original(*args)
            if value['trial_id'] == self.ids[-1]: self.change_result(started_utc='2026-09-28T01:00:00+00:00')
            return value
        with patch.object(report, '_row', side_effect=changed), self.assertRaises(ValueError): report.collect()

    def test_report_bundle_change_rejected(self):
        original = report._row
        def changed(*args):
            value = original(*args)
            if value['trial_id'] == self.ids[-1]: (self.reporting / 'stage2/no_cutoff_final_report.py').write_text('changed')
            return value
        with patch.object(report, '_row', side_effect=changed), self.assertRaisesRegex(ValueError, 'reporting bundle'): report.collect()

    def test_fresh_native_runtime_reverification_cannot_be_replaced_with_saved_success(self):
        self.native.study.qualified.side_effect = [deepcopy(self.f.proof), ValueError('image changed')]
        with self.assertRaisesRegex(ValueError, 'image changed'): report.collect()

    def test_source_reread_at_end_is_required(self):
        self.native.runtime.sources.return_value = {}; self.native.runtime.sources.side_effect = None
        with self.assertRaisesRegex(ValueError, 'sources'): report.collect()

    def test_persistent_stop_appearing_during_audit_refuses_return(self):
        original = self.native.original.recheck.side_effect
        def changed(*args):
            original(*args)
            if self.native.original.recheck.call_count == 2:
                self.f.save(phase.RT + 'operator-stop-request.json', {'automatic_resume': False})
        self.native.original.recheck.side_effect = changed
        with self.assertRaisesRegex(ValueError, 'Persistent stop'): report.collect()

    def test_completion_service_state_is_rechecked_before_return(self):
        self.service.side_effect = [self.service.return_value, self.service.return_value, ValueError('service changed')]
        with self.assertRaisesRegex(ValueError, 'service changed'): report.collect()

    def test_mutation_during_last_native_observation_is_still_reread(self):
        def changed():
            if self.service.call_count == 3:
                self.f.save(phase.RT + 'retry-lifecycle/' + self.ids[0] + '.json', {})
            return self.service.return_value
        self.service.side_effect = changed
        with self.assertRaisesRegex(ValueError, 'absent'): report.collect()

    def test_new_attempt_during_last_native_observation_is_refused(self):
        def changed():
            if self.service.call_count == 3:
                self.f.save(phase.RT + 'scored-trials/unregistered/started.json', {})
            return self.service.return_value
        self.service.side_effect = changed
        with self.assertRaises(ValueError): report.collect()

    def test_actual_original_results_are_reread_after_last_native_observation(self):
        def changed():
            if self.service.call_count == 3:
                path = next((self.baseline / phase.RT / 'scored-trials').glob('*/result.json')); path.write_text('{}')
            return self.service.return_value
        self.service.side_effect = changed
        with self.assertRaises(ValueError): report.collect()

    def test_no_saved_report_root_callback_or_factory_arguments(self):
        for kwargs in ({'root': self.root}, {'proof': {}}, {'callback': lambda: True}, {'factory': object()}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError): report.collect(**kwargs)

    def test_private_symlinked_or_public_result_is_rejected(self):
        self.result_path().chmod(0o644)
        with self.assertRaises(ValueError): report.collect()

    def test_duplicate_json_accounting_metadata_rejected(self):
        name = self.ids[3]
        self.f.write(phase.RT + 'scored-attempts/' + name + '/000001.transport-error.json', b'{"http_status":429,"http_status":200}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'): report.collect()

    def test_unknown_cost_and_missing_generation_timing_retained_without_limit(self):
        # Only synthetic accounting bytes: the raw request sentinel must never
        # become a returned field or a provider operation.
        for i in range(105):
            self.f.write(self.f.accounting + '/%06d.request.json' % i, b'PRIVATE REQUEST SENTINEL')
        self.f.save(self.f.accounting + '/000000.outcome.json', dict(status='ok', accepted_for_agent=True,
            cost_usd='0.25', input_tokens=2, output_tokens=3))
        self.f.save(self.f.accounting + '/000001.transport-error.json', {'http_status': 429})
        self.f.save(self.f.accounting + '/000001.retry.json', {'synthetic': True})
        self.f.result['billing'] = accounting.summarise(self.root / phase.RT, self.f.trial_id); self.f.flush()
        value = report.collect(); row = value['rows'][-1]
        self.assertEqual(row['model_requests'], 105); self.assertEqual(row['accepted_model_responses'], 1)
        self.assertEqual(row['interrupted_requests'], 104); self.assertEqual(row['unknown_cost_requests'], 104)
        self.assertEqual(row['missing_generation_timings'], 105); self.assertEqual(row['http_429_requests'], 1)
        self.assertEqual(row['known_cost_usd'], '0.25'); self.assertIsNone(row['total_cost_usd'])
        self.assertIsNone(value['aggregates']['full89']['total_cost_usd'])
        self.assertNotIn('PRIVATE REQUEST SENTINEL', json.dumps(value))


class ReadOnlyBoundaryTests(unittest.TestCase):
    @contextmanager
    def native_context_fixture(self):
        # Path/platform metadata only; does not execute a native reader.
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            base = Path(folder).resolve(); root = base / 'final'; bundle = base / 'report'
            for directory in (root, bundle): (directory / 'stage2').mkdir(parents=True)
            for obj, key, value in ((report, 'ROOT', root), (report, 'REPORTING', bundle),
                    (report, '__file__', str(bundle / 'stage2/no_cutoff_final_report.py')),
                    (phase, '__file__', str(bundle / 'stage2/no_cutoff_final_phase_audit.py')),
                    (phase.local_trace, '__file__', str(root / 'stage2/local_trace.py')),
                    (report.sys, 'prefix', str(root / '.venv')), (report.sys, 'platform', 'linux'),
                    (report.sys, 'dont_write_bytecode', True), (report.sys, 'flags', NS(isolated=1)),
                    (report.sys, 'pycache_prefix', str(bundle / '.absent-bytecode-cache'))):
                stack.enter_context(patch.object(obj, key, value))
            stack.enter_context(patch.object(report.os, 'getuid', return_value=0))
            stack.enter_context(patch.object(report.Path, 'cwd', return_value=root))
            stack.enter_context(patch.dict(os.environ, report.ENVIRONMENT, clear=True))
            yield bundle

    def test_native_context_requires_separate_bundle_original_interpreter_and_clean_environment(self):
        with self.native_context_fixture(): report._context()

    def test_native_context_rejects_provider_credentials(self):
        with self.native_context_fixture(), patch.dict(os.environ, {'OPENROUTER_API_KEY': 'synthetic'}):
            with self.assertRaisesRegex(ValueError, 'Credential-free'): report._context()

    def test_native_context_rejects_existing_bytecode_prefix(self):
        with self.native_context_fixture() as bundle:
            (bundle / '.absent-bytecode-cache').mkdir()
            with self.assertRaisesRegex(ValueError, 'absent bytecode'): report._context()

    def test_native_context_requires_isolated_interpreter(self):
        with self.native_context_fixture(), patch.object(report.sys, 'flags', NS(isolated=0)):
            with self.assertRaisesRegex(ValueError, 'native interpreter'): report._context()

    def test_local_workspace_cannot_invoke_native_collector(self):
        with patch.object(report, '_service') as service, self.assertRaisesRegex(ValueError, 'native interpreter'):
            report.collect()
        service.assert_not_called()

    def test_service_requires_exact_successful_inactive_state(self):
        for state in ('ActiveState=active\nSubState=running\nMainPID=1\nExecMainStatus=0\n',
                'ActiveState=failed\nSubState=failed\nMainPID=0\nExecMainStatus=1\n', '',
                'ActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\nMainPID=1\n'):
            with patch.object(report, '_command', return_value=state), self.assertRaises(ValueError): report._service()

    def test_docker_commands_only_inspect_exact_owned_resources(self):
        with patch.object(report, '_command', return_value='') as command:
            report._resources('uts-scored-' + 'a' * 12)
        self.assertEqual(len(command.call_args_list), 3)
        self.assertTrue(all('label=com.docker.compose.project=uts-scored-' + 'a' * 12 in c.args[0] for c in command.call_args_list))
        with self.assertRaises(ValueError): report._resources('other-project')

    def test_native_read_command_is_credential_free_and_not_remote_docker(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'must-not-forward', 'DOCKER_HOST': 'tcp://other'}), \
                patch.object(report.subprocess, 'run', return_value=NS(returncode=0, stdout='ok')) as run:
            self.assertEqual(report._command(['systemctl', 'show', report.SERVICE]), 'ok')
        environment = run.call_args.kwargs['env']
        self.assertNotIn('OPENROUTER_API_KEY', environment)
        self.assertEqual(environment['DOCKER_HOST'], 'unix:///var/run/docker.sock')
        self.assertEqual(environment['DOCKER_CONFIG'], '/dev/null')

    def test_native_failure_does_not_return_raw_diagnostics(self):
        with patch.object(report.subprocess, 'run', return_value=NS(returncode=1, stdout='private', stderr='private')):
            with self.assertRaisesRegex(ValueError, 'no automatic retry') as error: report._command(['systemctl'])
        self.assertNotIn('private', str(error.exception))

    def test_aggregate_refuses_invented_zero_for_not_run(self):
        row = dict(reward=None, known_cost_usd='0', unknown_cost_requests=0,
            phase_observation={'setup': 'measured', 'agent': 'not_run_setup_failed', 'verifier': 'not_run_setup_failed'},
            setup_seconds=1.0, agent_seconds=0, verifier_seconds=None)
        for key in ('model_requests', 'accepted_model_responses', 'interrupted_requests', 'error_requests',
                'other_unaccepted_requests', 'http_429_requests', 'transport_error_requests', 'retry_records',
                'known_input_tokens', 'known_output_tokens', 'generation_timings', 'missing_generation_timings'): row[key] = 0
        with self.assertRaisesRegex(ValueError, 'not-run'): report.aggregate([row])
