"""Local lifecycle/files/locks with mocked native readers, Docker and regression.

These temporary synthetic fixtures are not native qualification or paid evidence.
No production proof is fabricated on any deployment and no provider is called.
"""
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, AsyncMock

import qualify_matched_repeat as qualifier
import matched_repeat_policy as policy
import matched_repeat_session as session
import matched_repeat_study as study
from scored_gateway import durable_json
from test_matched_repeat_policy import image_evidence
import test_matched_repeat_probe as fixtures

REAL_VERIFY = session.verify_qualification
REAL_REGRESSION = qualifier._regression


class QualifierTests(unittest.TestCase):
    def setUp(self):
        self.p = p = fixtures.ProbeTests('runTest'); p.setUp(); self.addCleanup(p.doCleanups)
        self.q = p.q; self.root = p.root; self.rt = p.rt.resolve(); self.steps = []
        # Remove only fabricated setup records in this fresh TemporaryDirectory.
        # The production qualifier never removes earlier evidence or retries it.
        for path in self.rt.glob('native-matched-repeat-*-qualification-*'):
            shutil.rmtree(path)
        for name in (policy.POLICY_FILE, policy.MANIFEST_FILE, policy.PREDECESSOR_FILE, policy.RUNTIME_FILE,
                qualifier.INTENT, qualifier.RESULT, qualifier.images.INTENT, qualifier.images.RESULT):
            (self.rt / name).unlink()
        self.enterContext(patch.object(session, 'verify_qualification', REAL_VERIFY))
        self.builder = self.enterContext(patch.object(qualifier.images, 'build', side_effect=self.build))
        self.regression = self.enterContext(patch.object(qualifier, '_regression', side_effect=self.regress))
        self.original_probe = qualifier.probe.probe
        self.probes = self.enterContext(patch.object(qualifier.probe, 'probe', side_effect=self.rehearse))

    def build(self, active):
        self.assertTrue(self.q.locked); self.assertIs(session._task(), session._live(active)['task'])
        self.steps.append('build')
        image_evidence(self.root, self.q.f.proof)
        return {'this_return_is_not_evidence': True}

    async def regress(self, active, folder, files):
        self.assertTrue(self.q.locked); self.assertIs(session._task(), session._live(active)['task'])
        self.steps.append('regression')
        durable_json(folder / 'regression.json', dict(tests=1, passed=True, skipped=0,
            errors=0, failures=0, modules=list(policy.TEST_MODULES)))
        path = folder / 'regression.txt'; path.write_bytes(b'Local mocked regression only\n'); path.chmod(0o600)
        return {'this_return_is_not_evidence': True}

    async def rehearse(self, active, mode):
        self.steps.append(mode)
        await self.original_probe(active, mode)
        return {'this_return_is_not_evidence': True}

    async def execute(self, after=None):
        with self.q.open() as active:
            result = await qualifier.qualify(active)
            if after: await after(active, result)
            return result

    def read(self, name): return json.loads((self.rt / name).read_bytes())

    def refuse(self, expression=''):
        async def work():
            with self.q.open() as active:
                with self.assertRaisesRegex((ValueError, OSError, RuntimeError, AssertionError), expression):
                    await qualifier.qualify(active)
        asyncio.run(work())

    def assert_failure(self, kind='ValueError'):
        value = self.read(qualifier.FAILURE)
        self.assertEqual(value['exception_type'], kind)
        self.assertIs(value['automatic_resume'], False)
        self.assertIs(value['paid_launch_ready'], False)
        self.assertNotIn('error', value)
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())

    def test_real_scoped_orchestration_reuses_native_lifecycle_with_mocked_host(self):
        result = asyncio.run(self.execute())
        self.assertEqual(self.steps, ['build', 'regression', *policy.PROBE_MODES])
        self.assertEqual(result['status'], 'qualified'); self.assertFalse(result['paid_launch_ready'])
        proof = self.read(policy.QUALIFICATION_FILE)
        self.assertEqual(len(proof['evidence_files']), 8)
        self.assertEqual(len(proof['image_evidence_files']), 2)
        self.assertEqual(len(proof['synthetic']), 3)
        self.assertEqual(proof['offline']['tests'], 1)
        self.assertEqual(proof['inherited_baseline_turn_guards'], policy.POLICY['inherited_baseline_turn_guards'])
        self.assertGreater(len(result['producer_files']), 30)
        self.assertEqual((self.rt / policy.MANIFEST_FILE).read_bytes(), (self.root / 'stage2/input_manifest.json').read_bytes())
        self.assertEqual(self.q.auth.call_count, 1); self.assertEqual(self.q.old_auth.call_count, 1)
        self.assertEqual(self.q.lock.call_count, 1); self.q.process.assert_not_called()
        self.assertEqual(self.p.events.count('native-run'), 2)
        self.assertEqual(self.p.events.count('native-setup'), 3)
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())
        self.assertFalse((self.rt / 'scored-trials').exists())

    def test_completion_is_freshly_reread_and_includes_all_supporting_bytes(self):
        async def after(active, result):
            checked = session.verify_qualification(active)
            self.assertEqual(set(checked['qualification_operation_files']),
                set(result['producer_files']) | {'.runtime/stage2/' + qualifier.RESULT})
            self.assertEqual(len(checked['private_files']), 5)
            self.assertFalse(checked['paid_launch_ready'])
        asyncio.run(self.execute(after))

    def test_saved_or_closed_sessions_and_missing_task_are_refused(self):
        for value in ({}, object(), session._Session()):
            with self.assertRaises(ValueError): asyncio.run(qualifier.qualify(value))
        with self.q.open() as active: pass
        with self.assertRaises(ValueError): asyncio.run(qualifier.qualify(active))
        with self.q.open() as active:
            with self.assertRaises(ValueError): asyncio.run(qualifier.qualify(active))
        self.builder.assert_not_called()

    def test_child_async_task_cannot_consume_parent_session(self):
        async def work():
            with self.q.open() as active:
                with self.assertRaisesRegex(ValueError, 'async tasks'):
                    await asyncio.create_task(qualifier.qualify(active))
        asyncio.run(work()); self.builder.assert_not_called()

    def test_thread_and_process_identity_are_not_transferable(self):
        async def work():
            with self.q.open() as active:
                errors = []
                def child():
                    try: asyncio.run(qualifier.qualify(active))
                    except ValueError as exc: errors.append(str(exc))
                thread = threading.Thread(target=child); thread.start(); thread.join()
                self.assertEqual(len(errors), 1)
                with patch.object(session.os, 'getpid', return_value=os.getpid() + 1):
                    with self.assertRaises(ValueError): await qualifier.qualify(active)
        asyncio.run(work()); self.builder.assert_not_called()

    def test_earlier_intent_failure_result_or_partial_directory_prevents_start(self):
        for name in (qualifier.INTENT, qualifier.RESULT, qualifier.FAILURE,
                qualifier.images.INTENT, qualifier.images.RESULT, qualifier.images.FAILURE,
                policy.QUALIFICATION_FILE, 'matched-repeat-rehearsal-tools.json'):
            path = self.rt / name; path.symlink_to(self.rt / 'absent')
            with self.subTest(name=name): self.refuse()
            path.unlink()
        folder = self.rt / 'native-matched-repeat-terminus-2-tools-interrupted'; folder.mkdir()
        self.refuse('Earlier'); self.builder.assert_not_called()

    def test_paid_attempts_and_operator_stop_prevent_any_operation(self):
        folder = self.rt / 'scored-trials' / 'started-key'; folder.mkdir(parents=True)
        self.refuse('paid attempts'); shutil.rmtree(folder.parent)
        durable_json(self.rt / 'operator-stop-request.json', dict(automatic_resume=False))
        with self.assertRaisesRegex(ValueError, 'Persistent stop'): asyncio.run(self.execute())
        self.builder.assert_not_called()

    def test_existing_changed_or_nonexact_manifest_is_not_overwritten(self):
        original = (self.root / 'stage2/input_manifest.json').read_bytes()
        path = self.rt / policy.MANIFEST_FILE; path.write_bytes(original + b' '); path.chmod(0o600)
        self.refuse('Exact manifest bytes'); self.assertEqual(path.read_bytes(), original + b' ')
        self.assert_failure(); self.builder.assert_not_called()

    def test_existing_wrong_policy_is_not_overwritten(self):
        durable_json(self.rt / policy.POLICY_FILE, {'changed': True})
        self.refuse('Existing qualification input'); self.assert_failure()
        self.assertEqual(self.read(policy.POLICY_FILE), {'changed': True})

    def test_real_credentials_or_redirected_docker_are_refused_before_intent(self):
        for name in ('OPENROUTER_API_KEY', 'DOCKER_HOST'):
            with patch.dict(os.environ, {name:'test-forbidden'}): self.refuse('Credential-free')
        self.assertFalse((self.rt / qualifier.INTENT).exists()); self.builder.assert_not_called()

    def test_builder_failure_retained_with_exception_type_only(self):
        self.builder.side_effect = RuntimeError('private diagnostic must not be published')
        self.refuse('private diagnostic'); self.assert_failure('RuntimeError')
        self.assertNotIn('private diagnostic', (self.rt / qualifier.FAILURE).read_text())
        self.regression.assert_not_called(); self.probes.assert_not_called()

    def test_regression_return_cannot_replace_missing_actual_files(self):
        self.regression.side_effect = None; self.regression.return_value = {'passed':True}
        self.refuse(); self.assert_failure('FileNotFoundError'); self.probes.assert_not_called()

    def test_skipped_or_failed_regression_blocks_all_rehearsals(self):
        async def bad(active, folder, files):
            await self.regress(active, folder, files)
            value = json.loads((folder / 'regression.json').read_bytes()); value['skipped'] = 1
            (folder / 'regression.json').write_text(json.dumps(value))
        self.regression.side_effect = bad
        self.refuse('complete native regression'); self.assert_failure(); self.probes.assert_not_called()

    def test_raw_input_change_across_regression_is_caught(self):
        async def bad(active, folder, files):
            await self.regress(active, folder, files)
            path = self.rt / policy.POLICY_FILE; path.write_bytes(path.read_bytes() + b' ')
        self.regression.side_effect = bad
        self.refuse('input changed'); self.assert_failure(); self.probes.assert_not_called()

    def test_source_change_during_operation_invalidates_session(self):
        async def bad(active, folder, files):
            await self.regress(active, folder, files)
            (self.root / 'stage2/matched_repeat_session.py').write_bytes(b'changed')
        self.regression.side_effect = bad
        self.refuse(); self.assert_failure(); self.probes.assert_not_called()

    def test_cancellation_is_retained_not_a_completed_qualification(self):
        self.regression.side_effect = asyncio.CancelledError('external-cancel')
        with self.assertRaises(asyncio.CancelledError): asyncio.run(self.execute())
        self.assert_failure('CancelledError'); self.probes.assert_not_called()
        self.assertFalse((self.rt / qualifier.RESULT).exists())

    def test_probe_return_without_actual_evidence_never_qualifies(self):
        self.probes.side_effect = None; self.probes.return_value = {'status':'passed'}
        self.refuse(); self.assert_failure('FileNotFoundError')
        self.assertEqual(self.probes.call_count, 1)

    def test_failed_real_probe_retains_earlier_mode_and_never_runs_next(self):
        async def bad(active, mode):
            if mode == 'cancel_setup': raise RuntimeError('fixture failure')
            await self.rehearse(active, mode)
        self.probes.side_effect = bad
        self.refuse('fixture failure'); self.assert_failure('RuntimeError')
        self.assertTrue((self.rt / 'matched-repeat-rehearsal-tools.json').exists())
        self.assertFalse((self.rt / 'matched-repeat-rehearsal-boundary_stop.json').exists())

    def test_supporting_trace_mutation_refused_before_next_mode(self):
        async def bad(active, mode):
            await self.rehearse(active, mode)
            intent = self.read('matched-repeat-rehearsal-' + mode + '.json')
            path = next((self.root / intent['runtime_path']).rglob('traces/*.json'))
            path.write_bytes(path.read_bytes() + b' ')
        self.probes.side_effect = bad
        self.refuse('supporting producer bytes'); self.assert_failure()
        self.assertEqual(self.probes.call_count, 1)

    def test_false_rehearsal_check_refused_before_next_mode(self):
        async def bad(active, mode):
            await self.rehearse(active, mode)
            intent = self.read('matched-repeat-rehearsal-' + mode + '.json')
            path = self.root / intent['runtime_path'] / 'evidence.json'
            value = json.loads(path.read_bytes()); value['checks']['model_revoked'] = False
            path.write_text(json.dumps(value))
        self.probes.side_effect = bad
        self.refuse('rehearsal report'); self.assert_failure(); self.assertEqual(self.probes.call_count, 1)

    def test_failure_after_proof_and_result_save_blocks_later_sessions(self):
        with patch.object(session, 'verify_qualification', side_effect=ValueError('final recheck failed')):
            self.refuse('final recheck failed')
        self.assertTrue((self.rt / policy.QUALIFICATION_FILE).exists())
        self.assertTrue((self.rt / qualifier.RESULT).exists()); self.assert_failure()
        async def check():
            with self.q.open() as active:
                with self.assertRaisesRegex(ValueError, 'Retained native qualification failure'):
                    REAL_VERIFY(active)
        asyncio.run(check())

    def test_successful_operation_cannot_run_again_even_with_fresh_session(self):
        asyncio.run(self.execute()); self.refuse()
        self.assertEqual(self.builder.call_count, 1)
        self.assertEqual(self.probes.call_count, 3)

    def test_missing_completion_is_not_paid_qualification(self):
        asyncio.run(self.execute()); (self.rt / qualifier.RESULT).unlink()
        async def check():
            with self.q.open() as active:
                with self.assertRaises((OSError, ValueError)): REAL_VERIFY(active)
        asyncio.run(check())

    def test_completion_files_privacy_symlinks_and_duplicate_fields(self):
        asyncio.run(self.execute()); path = self.rt / qualifier.RESULT; raw = path.read_bytes()
        async def check():
            with self.q.open() as active:
                with self.assertRaises((ValueError, OSError)): REAL_VERIFY(active)
        path.chmod(0o644); asyncio.run(check()); path.chmod(0o600)
        path.write_bytes(b'{"status":1,"status":2}'); asyncio.run(check())
        path.unlink(); path.symlink_to(self.rt / 'absent'); asyncio.run(check())
        path.unlink(); path.write_bytes(raw); path.chmod(0o600)

    def test_raw_support_changes_after_completion_invalidate_later_admission(self):
        result = asyncio.run(self.execute())
        name = next(n for n in result['producer_files'] if '/traces/' in n)
        path = self.root / name; path.write_bytes(path.read_bytes() + b' ')
        async def check():
            with self.q.open() as active:
                with self.assertRaisesRegex(ValueError, 'supporting producer bytes'): REAL_VERIFY(active)
        asyncio.run(check())

    def test_terminal_failure_marker_is_checked_by_paid_quick_gate(self):
        asyncio.run(self.execute())
        (self.rt / qualifier.FAILURE).symlink_to(self.rt / 'absent')
        with self.assertRaisesRegex(ValueError, 'Retained native qualification failure'): study._clear(self.root)

    def test_child_command_is_fixed_isolated_and_credential_free(self):
        observed = {}
        async def spawn(*args, **kwargs):
            observed.update(args=args, kwargs=kwargs)
            class Process:
                returncode = 0; pid = 999999
                async def communicate(inner, raw):
                    observed['payload'] = json.loads(raw)
                    folder = self.root / observed['payload']['folder']
                    durable_json(folder / 'regression.json', {'actual_child_record': True})
            return Process()
        async def work():
            with self.q.open() as active:
                folder = self.rt / 'native-matched-repeat-terminus-2-qualification-command'; folder.mkdir()
                files = {'.runtime/stage2/' + policy.BASELINE_FILE: session.baseline.ORIGINAL_FILE_SHA256}
                with patch.object(asyncio, 'create_subprocess_exec', side_effect=spawn):
                    value = await REAL_REGRESSION(active, folder, files)
                self.assertEqual(value, {'actual_child_record':True})
        asyncio.run(work())
        self.assertEqual(observed['args'], (str(self.root / '.venv/bin/python'), '-I', '-B', '-c', qualifier.BOOTSTRAP))
        self.assertTrue(observed['kwargs']['start_new_session']); self.assertTrue(observed['kwargs']['close_fds'])
        self.assertEqual(set(observed['kwargs']['env']), {'PATH', 'LANG', 'LC_ALL', 'LITELLM_LOCAL_MODEL_COST_MAP'})
        self.assertNotIn('session', observed['payload'])
        self.assertEqual(observed['payload']['modules'], list(policy.TEST_MODULES))

    def test_child_cancellation_signals_only_owned_regression_process_group(self):
        child = SimpleNamespace(pid=999999, returncode=None, communicate=AsyncMock(side_effect=asyncio.CancelledError()),
            wait=AsyncMock(return_value=-15))
        async def work():
            with self.q.open() as active:
                folder = self.rt / 'native-matched-repeat-terminus-2-qualification-child'; folder.mkdir()
                files = {'.runtime/stage2/' + policy.BASELINE_FILE: session.baseline.ORIGINAL_FILE_SHA256}
                with patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=child)), \
                        patch.object(os, 'killpg') as kill:
                    with self.assertRaises(asyncio.CancelledError): await REAL_REGRESSION(active, folder, files)
                    kill.assert_called_once_with(999999, signal.SIGTERM)
        asyncio.run(work())

    def test_cancel_during_child_creation_waits_for_owned_child_then_cleans_it(self):
        child = SimpleNamespace(pid=999998, returncode=None, communicate=AsyncMock(), wait=AsyncMock(return_value=-15))
        async def work():
            with self.q.open() as active:
                owner = asyncio.current_task()
                async def spawn(*args, **kwargs):
                    owner.cancel('during-owned-spawn')
                    await asyncio.sleep(0)
                    return child
                folder = self.rt / 'native-matched-repeat-terminus-2-qualification-spawn'; folder.mkdir()
                files = {'.runtime/stage2/' + policy.BASELINE_FILE: session.baseline.ORIGINAL_FILE_SHA256}
                with patch.object(asyncio, 'create_subprocess_exec', side_effect=spawn), patch.object(os, 'killpg') as kill:
                    with self.assertRaises(asyncio.CancelledError): await REAL_REGRESSION(active, folder, files)
                    owner.uncancel()
                    kill.assert_called_once_with(999998, signal.SIGTERM)
                    child.communicate.assert_not_called()
        asyncio.run(work())

    def test_regression_stop_escalates_only_its_owned_child_after_cleanup_window(self):
        child = SimpleNamespace(pid=999997, returncode=None, wait=AsyncMock(side_effect=[asyncio.TimeoutError(), -9]))
        with patch.object(os, 'killpg') as kill:
            asyncio.run(qualifier._stop_regression(child))
        self.assertEqual([c.args for c in kill.call_args_list], [(999997, signal.SIGTERM), (999997, signal.SIGKILL)])

    def test_changed_completion_raw_bytes_after_image_return_are_rechecked(self):
        asyncio.run(self.execute())
        real = qualifier.verify_completion
        def change(active, proof):
            files = real(active, proof)
            path = self.rt / qualifier.RESULT; path.write_bytes(path.read_bytes() + b' ')
            return files
        async def work():
            with self.q.open() as active, patch.object(qualifier, 'verify_completion', side_effect=change):
                with self.assertRaisesRegex(ValueError, 'input changed'): REAL_VERIFY(active)
        asyncio.run(work())


class RegressionGuardTests(unittest.TestCase):
    def bootstrap(self, mutate=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); stage = root / 'stage2'; stage.mkdir()
            folder = root / '.runtime/stage2/native-matched-repeat-terminus-2-qualification-test'
            folder.mkdir(parents=True)
            # A tiny harmless local module proves the pre-import boundary only.
            # This is not the actual qualifier and cannot emit native proof.
            raw = b'def regression_worker(payload): print("local-bootstrap-test-only")\n'
            path = stage / 'qualify_matched_repeat.py'; path.write_bytes(raw)
            payload = dict(root=str(root), folder=str(folder.relative_to(root)),
                files={'stage2/qualify_matched_repeat.py':hashlib.sha256(raw).hexdigest()}, modules=[])
            if mutate: mutate(root, folder, payload)
            prefix = 'import sys;sys.platform="linux";sys.prefix=' + repr(str(root / '.venv')) + '\n'
            return subprocess.run([sys.executable, '-I', '-B', '-c', prefix + qualifier.BOOTSTRAP],
                input=json.dumps(payload), capture_output=True, text=True,
                env={'PATH':'/usr/bin:/bin'}, timeout=10)

    def test_actual_local_subprocess_bootstrap_requires_bound_bytes_before_import(self):
        value = self.bootstrap()
        self.assertEqual(value.returncode, 0, value.stderr)
        self.assertEqual(value.stdout.strip(), 'local-bootstrap-test-only')

    def test_bootstrap_source_drift_symlinks_unsafe_paths_and_cache_fail_closed(self):
        def link(root, folder, payload):
            path = root / 'stage2/qualify_matched_repeat.py'; path.rename(path.with_suffix('.saved'))
            path.symlink_to(path.with_suffix('.saved'))
        def cache(root, folder, payload): (folder / 'absent-bytecode-cache').symlink_to(root / 'absent')
        for mutate in (lambda r,f,p: p['files'].update({'stage2/qualify_matched_repeat.py':'0' * 64}), link, cache,
                lambda r,f,p: p.update(folder='../outside'),
                lambda r,f,p: p['files'].update({'stage2//qualify_matched_repeat.py':'0' * 64})):
            with self.subTest(mutate=mutate):
                value = self.bootstrap(mutate)
                self.assertNotEqual(value.returncode, 0)
                self.assertNotIn('local-bootstrap-test-only', value.stdout)

    def test_bootstrap_denies_external_network_during_project_import(self):
        def attempt(root, folder, payload):
            raw = b'import socket\nsocket.create_connection(("192.0.2.1",443))\n'
            (root / 'stage2/qualify_matched_repeat.py').write_bytes(raw)
            payload['files']['stage2/qualify_matched_repeat.py'] = hashlib.sha256(raw).hexdigest()
        value = self.bootstrap(attempt)
        self.assertNotEqual(value.returncode, 0)
        self.assertIn('only local synthetic network peers', value.stderr)

    def worker(self, suite):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); folder = root / '.runtime/stage2/native-matched-repeat-test'; folder.mkdir(parents=True)
            path = root / 'input'; path.write_bytes(b'actual bound input')
            module = root / 'stage2/qualify_matched_repeat.py'; module.parent.mkdir()
            module.write_bytes(b'Temporary synthetic source binding only')
            payload = dict(root=str(root), folder=str(folder.relative_to(root)),
                files={'input':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'stage2/qualify_matched_repeat.py':hashlib.sha256(module.read_bytes()).hexdigest()},
                modules=list(policy.TEST_MODULES))
            with patch.object(sys, 'platform', 'linux'), patch.object(sys, 'prefix', str(root / '.venv')), \
                    patch.object(sys, 'dont_write_bytecode', True), patch.object(sys, 'addaudithook') as hook, \
                    patch.object(sys, 'stdout', io.StringIO()), patch.object(qualifier.probe, '_environment'), \
                    patch.object(qualifier, '__file__', str(root / 'stage2/qualify_matched_repeat.py')), \
                    patch.object(unittest.defaultTestLoader, 'loadTestsFromNames', return_value=suite):
                error = None
                try: qualifier.regression_worker(payload)
                except ValueError as exc: error = exc
                hook.assert_called_once_with(qualifier._network_guard)
            report = json.loads((folder / 'regression.json').read_bytes())
            return report, error

    def test_worker_retains_actual_passing_test_count_not_a_saved_report(self):
        report, error = self.worker(unittest.TestSuite([unittest.FunctionTestCase(lambda: None)]))
        self.assertIsNone(error); self.assertEqual(report['tests'], 1); self.assertTrue(report['passed'])
        self.assertEqual(report['modules'], list(policy.TEST_MODULES))

    def test_worker_retains_failures_skips_and_empty_suite_without_qualifying(self):
        def fail(): raise AssertionError('synthetic failure')
        def skip(): raise unittest.SkipTest('synthetic skip')
        for suite in (unittest.TestSuite([unittest.FunctionTestCase(fail)]),
                unittest.TestSuite([unittest.FunctionTestCase(skip)]), unittest.TestSuite()):
            report, error = self.worker(suite)
            self.assertIsInstance(error, ValueError)
            self.assertTrue(report['failures'] or report['skipped'] or report['tests'] == 0)

    def test_loopback_and_unix_allowed_external_peers_refused(self):
        for event, args in (('socket.connect', (None, ('127.0.0.1', 99))),
                ('socket.connect', (None, ('::1', 99))), ('socket.connect', (None, '/tmp/owned.sock')),
                ('socket.getaddrinfo', ('localhost', 99)), ('socket.sendto', (None, b'data', ('127.0.0.1', 99)))):
            qualifier._network_guard(event, args)
        for event, args in (('socket.connect', (None, ('1.1.1.1', 443))),
                ('socket.getaddrinfo', ('model-provider.invalid', 443)),
                ('socket.sendto', (None, b'data', ('192.0.2.1', 99)))):
            with self.assertRaises(PermissionError): qualifier._network_guard(event, args)

    def test_worker_rejects_non_native_or_other_interpreter_before_regression(self):
        with self.assertRaises(ValueError):
            qualifier.regression_worker(dict(root='/opt/not-this-deployment', folder='missing'))

    def test_inventory_binds_qualifier_and_fixed_test_module(self):
        self.assertIn('qualify_matched_repeat.py', policy.REQUIRED_SOURCE_FILES)
        self.assertIn('test_qualify_matched_repeat.py', policy.REQUIRED_SOURCE_FILES)
        self.assertIn('test_qualify_matched_repeat', policy.TEST_MODULES)

    def test_loaded_project_imports_require_bound_unchanged_actual_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); stage = root / 'stage2'; stage.mkdir()
            path = stage / 'fixture.py'; path.write_bytes(b'local fixture source')
            files = {'stage2/fixture.py':hashlib.sha256(path.read_bytes()).hexdigest()}
            module = SimpleNamespace(__file__=str(path))
            with patch.dict(sys.modules, {'synthetic_fixture':module}, clear=True):
                qualifier._loaded(root, files)
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'input changed'): qualifier._loaded(root, files)
                module.__file__ = str(stage / 'unbound.py')
                with self.assertRaisesRegex(ValueError, 'source-bound'): qualifier._loaded(root, files)
                module.__file__ = str(root / 'elsewhere/fixture.py')
                with self.assertRaisesRegex(ValueError, 'another deployment'): qualifier._loaded(root, files)


if __name__ == '__main__': unittest.main()
