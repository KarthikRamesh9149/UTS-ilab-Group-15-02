"""Synthetic native facts with real protected files, locks, session and dispatch."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import unittest
from unittest.mock import AsyncMock, patch

import no_cutoff_recovery_files as files
import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_result as retained
import no_cutoff_recovery_session as session
import no_cutoff_recovery_study as study
import run_no_cutoff_recovery as runner
from test_no_cutoff_recovery_setup import Environment
import test_no_cutoff_recovery_session as session_fixtures
from test_no_cutoff_recovery_runtime import save

STAGE = Path(__file__).resolve().parent


class LocalFiles:
    def protect(self, root):
        self.root = root
        self.enterContext(patch.object(files.libraries.os, 'listxattr', return_value=[], create=True))
        self.enterContext(patch.object(files.libraries, '_directory_chain', side_effect=lambda base, path:
            [base, *reversed([p for p in path.parents if p != base and p.is_relative_to(base)])]))
        def directories(path, *, private=False):
            # Only system ancestry outside this actual local fixture is mocked.
            rows = []
            for p in (*[v for v in reversed(path.parents) if v == root or v.is_relative_to(root)], path):
                info = p.lstat()
                if (not stat.S_ISDIR(info.st_mode) or p.resolve() != p or info.st_uid != os.getuid()
                        or info.st_gid != os.getgid() or info.st_mode & 0o7022
                        or p == path and private and stat.S_IMODE(info.st_mode) != 0o700):
                    raise ValueError('Private local fixture ancestry required')
                rows.append((str(p), info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
            return tuple(rows)
        self.enterContext(patch.object(files.bootstrap, 'directories', side_effect=directories))
        # The image module imported this helper directly.
        self.enterContext(patch.object(images, 'directories', side_effect=directories))


class EvidenceTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        import tempfile
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        (self.root / '.runtime').mkdir(mode=0o700)
        (self.root / '.runtime/stage2').mkdir(mode=0o700)

    def test_exclusive_private_durable_preserves_null_and_float(self):
        path = self.root / '.runtime/stage2/value.json'
        value = {'unknown': None, 'measured': 1.0}
        files.save(path, value)
        self.assertEqual(files.private(self.root, 'value.json')[0], value)
        self.assertIs(type(files.private(self.root, 'value.json')[0]['measured']), float)
        with self.assertRaises(FileExistsError): files.save(path, {'overwrite': True})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_identity_replacement_is_not_equal_evidence(self):
        path = self.root / '.runtime/stage2/value.json'; files.save(path, {})
        bound, ids = files.capture(self.root, ['.runtime/stage2/value.json'])
        path.rename(path.with_suffix('.retained'))
        files.save(path, {})
        with self.assertRaises(ValueError): files.check(self.root, bound, ids)

    def test_unsafe_link_hardlink_permissions_and_duplicate_json_refused(self):
        path = self.root / '.runtime/stage2/value.json'; files.save(path, {})
        path.chmod(0o644)
        with self.assertRaises(ValueError): files.private(self.root, 'value.json')
        path.chmod(0o600)
        os.link(path, path.with_suffix('.link'))
        with self.assertRaises(ValueError): files.private(self.root, 'value.json')
        path.with_suffix('.link').unlink()
        path.write_bytes(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError): files.private(self.root, 'value.json')

    def test_invalid_json_does_not_leave_intent(self):
        path = self.root / '.runtime/stage2/value.json'
        for value in ({'x': float('nan')}, {'x': object()}):
            with self.assertRaises((ValueError, TypeError)): files.save(path, value)
            self.assertFalse(path.exists())

    def test_exact_image_context_contains_only_five_new_overlay_sources(self):
        sources = {}
        for name in (*images.COPY_FILES, images.DOCKERFILE):
            raw = (STAGE / name).read_bytes(); save(self.root, 'stage2/' + name, raw)
            sources[name] = hashlib.sha256(raw).hexdigest()
        raw = images._context(self.root, sources)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            self.assertEqual(set(archive.getnames()), set(images.COPY_FILES) | {'Dockerfile'})
            self.assertEqual(archive.extractfile('Dockerfile').read(), images._dockerfile())
        self.assertNotIn('RUN ', images._dockerfile().decode())
        self.assertNotIn('scored_trial.py', images.COPY_FILES)

    def test_image_saved_state_cannot_rebuild(self):
        for name in (images.INTENT, images.RESULT, images.FAILURE, images.CONFIG, policy.REGISTRATION_FILE):
            path = self.root / '.runtime/stage2' / name; path.symlink_to('absent')
            with self.assertRaises(ValueError): images._unstarted(self.root)
            path.unlink()


class StudyFixture(LocalFiles):
    def setUp(self):
        self.q = session_fixtures.SessionTests('runTest')
        # Reuse only synchronous fixture setup, not another async TestCase's
        # runner. Its registered patch/file cleanups must really execute.
        self.q._callCleanup = lambda function, *args, **kwargs: function(*args, **kwargs)
        self.addCleanup(self.q.doCleanups); self.q.setUp()
        self.protect(self.q.root); self.rt = self.root / '.runtime/stage2'
        (self.rt / policy.REGISTRATION_FILE).unlink()  # Synthetic temporary fixture only.
        self.cells = policy.cells(self.q.f.manifest)
        self.q.host['task_inventory'] = {c['task_id']: dict(agent_timeout_seconds=180., image_id='sha256:'+'9'*64)
            for c in self.cells}
        save(self.root, '.runtime/stage2/' + policy.RUNTIME_FILE, json.dumps(self.q.host).encode())
        save(self.root, '.runtime/stage2/synthetic-qualification-producer.json', b'{"test_only":true}')
        self.producers = files.capture(self.root, ['.runtime/stage2/' + policy.RUNTIME_FILE,
            '.runtime/stage2/synthetic-qualification-producer.json'])[0]
        self.proof = dict(gateway_image='sha256:'+'8'*64, guard_image='sha256:'+'7'*64,
            sources=retained.setup._bindings())
        self.block = dict(condition=policy.CONDITION, cells=self.cells, qualification_sha256='1'*64,
            sources_sha256='2'*64, intended=3)
        self.qualified = self.enterContext(patch.object(study, '_qualified', side_effect=self.qualification))

    def qualification(self, active):
        session.recheck(active)
        live = session._live(active)
        bound = dict(live['inputs']['files'], **self.producers)
        files.check(self.root, bound)
        return self.root, deepcopy(self.proof), deepcopy(self.block), bound, files.capture(self.root, bound)[1]

    def open(self): return session.open_session(self.q.stream)

    def args(self, factory, index=0):
        cell = self.cells[index]
        return dict(root=self.root, trial_id=cell['trial_id'], task_id=cell['task_id'], stage='final',
            factory=factory, settings=policy.SETTINGS, gateway_image=self.proof['gateway_image'],
            guard_image=self.proof['guard_image'], setup_timeout_seconds=900)

    async def result(self, block, index, reward=0, *, incomplete=False):
        cell = self.cells[index]; relative = 'scored-trials/' + cell['trial_id'] + '/'
        parent = self.rt / relative; parent.mkdir(parents=True, mode=0o700)
        parent.parent.chmod(0o700)
        observer = retained.RetainedPreparation()
        await observer.prepare(Environment())
        observed = observer.finish()
        if incomplete:
            observed['retention_issues'] = ['late_metadata_unavailable']; observed['observation_complete'] = False
        value = dict(trial_id=cell['trial_id'], task_id=cell['task_id'], harness=policy.CONDITION,
            stage='final', recovery_experiment=policy.EXPERIMENT, recovery_registration_sha256=policy.fingerprint(block),
            model_protocol_sha256=policy.MODEL_SHA256, accounting_mode='provider-credit-only',
            gateway_image_id=self.proof['gateway_image'], guard_image_id=self.proof['guard_image'],
            project='synthetic-test-only', started_utc='2026-09-29T00:00:00Z')
        files.save(parent / 'started.json', value)
        value.update(status='verified', task_image_id='sha256:'+'9'*64,
            model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
            verifier_result=None if reward is None else {'rewards': {'reward': reward}},
            recovery_preparation=observed, billing={'requests': 105, 'unknown_cost_requests': 105, 'charged_usd': None})
        files.save(parent / 'result.json', value)
        return parent / 'result.json'

class StudyTests(StudyFixture, unittest.IsolatedAsyncioTestCase):
    async def test_only_live_session_and_fixed_issued_factory_can_admit(self):
        for fake in (None, {}, session._Session()):
            with self.assertRaises(ValueError): study.register(fake)
        with self.open() as active:
            block = study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                self.assertEqual(factory.harness, policy.CONDITION)
                self.assertEqual(study.admit_trial(**self.args(factory)), policy.fingerprint(block))
                self.assertIsInstance(study.preparation(self.root, self.cells[0]['trial_id']), retained.RetainedPreparation)
                with self.assertRaises(ValueError): study.admit_trial(**self.args(factory))
        with self.assertRaises(ValueError): study.register(active)

    async def test_next_key_requires_actual_result_and_keeps_zero_unknown_and_missing(self):
        with self.open() as active:
            block = study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                for index, reward in enumerate((0, None, 1)):
                    study.admit_trial(**self.args(factory, index))
                    await self.result(block, index, reward)
                complete, partial, bound = study._attempts(self.root, block)
                self.assertEqual(len(complete), 3); self.assertEqual(partial, []); self.assertEqual(len(bound), 6)
                with self.assertRaises(ValueError): study.admit_trial(**self.args(factory))

    async def test_incomplete_observation_blocks_next_and_preserves_started_key(self):
        with self.open() as active:
            block = study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit); study.admit_trial(**self.args(factory))
                path = await self.result(block, 0, incomplete=True); before = path.read_bytes()
                with self.assertRaises(ValueError): study.admit_trial(**self.args(factory, 1))
                self.assertEqual(path.read_bytes(), before)

    async def test_same_byte_qualified_file_replacement_invalidates_scope(self):
        with self.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                path = self.rt / 'synthetic-qualification-producer.json'; raw = path.read_bytes()
                path.rename(path.with_suffix('.retained')); save(self.root, str(path.relative_to(self.root)), raw)
                with self.assertRaises(ValueError): study.agent_factory(permit)

    async def test_child_task_cannot_take_live_permit(self):
        with self.assertRaises(ValueError), self.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                async def child(): return study.agent_factory(permit)
                with self.assertRaises(ValueError): await asyncio.create_task(child())
            with self.assertRaises(ValueError): session.recheck(active)

    async def test_source_producer_drift_blocks_registration(self):
        with self.open() as active:
            (self.rt / 'synthetic-qualification-producer.json').write_bytes(b'changed')
            with self.assertRaises(ValueError): study.register(active)
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())


class DispatchTests(StudyFixture, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        from test_retry_gateway import Clock
        self.enterContext(patch.object(runner, 'Clock', return_value=Clock()))
        self.native = self.enterContext(patch.object(runner, 'docker', return_value=''))
        self.terminal = self.enterContext(patch.object(runner, 'verify_qualification', side_effect=self.qualification))
        self.calls = []
        self.trial = self.enterContext(patch.object(runner, 'run_trial', new_callable=AsyncMock))
        self.trial.side_effect = self.execute
        self.incomplete = False
        self.cancel = False

    async def execute(self, **kwargs):
        index = len(self.calls); factory = kwargs['agent_factory']
        self.assertEqual(kwargs['recovery'], policy.EXPERIMENT)
        self.assertNotIn('matched_repeat', kwargs)
        self.assertEqual(kwargs['setup_timeout_seconds'], 900)
        study.admit_trial(**self.args(factory, index)); self.calls.append(kwargs['trial_id'])
        block = files.private(self.root, policy.REGISTRATION_FILE)[0]
        await self.result(block, index, (0, None, 1)[index], incomplete=self.incomplete)
        if self.cancel: raise asyncio.CancelledError('synthetic local cancellation')
        return {'ignored': 'return values do not prove completion'}

    async def test_exact_three_sequential_and_fresh_session_cannot_restart(self):
        with self.open() as active: value = await runner.run(active)
        self.assertEqual(self.calls, [c['trial_id'] for c in self.cells])
        self.assertEqual((value['completed'], value['passes'], value['failures'], value['missing_verifier_results']), (3,1,1,1))
        self.assertFalse(value['completed_audit_verified']); self.assertFalse(value['recovery_merged_into_original89'])
        with self.open() as active:
            with self.assertRaises(ValueError): await runner.run(active)
        self.assertEqual(len(self.calls), 3)

    async def test_incomplete_result_is_terminal_failure_not_second_dispatch(self):
        self.incomplete = True
        with self.open() as active:
            with self.assertRaises(ValueError): await runner.run(active)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue((self.rt / runner.FAILURE).exists())
        self.assertFalse((self.rt / runner.RESULT).exists())

    async def test_cancellation_does_not_advance_or_report_completion(self):
        self.cancel = True
        with self.open() as active:
            with self.assertRaises(asyncio.CancelledError): await runner.run(active)
        self.assertEqual(len(self.calls), 1); self.assertTrue((self.rt / runner.FAILURE).exists())
