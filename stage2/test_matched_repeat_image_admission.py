"""Actual local binding/session/admission code with fake Docker and native readers.

All files and qualification records live in temporary synthetic trees. These
tests never create native proof, contact a provider or exercise a paid trial.
"""
import asyncio
from copy import deepcopy
import hashlib
import json
import threading
import unittest
from unittest.mock import patch

import matched_repeat_images as images
import matched_repeat_policy as policy
import matched_repeat_session as session
import matched_repeat_study as study
import test_matched_repeat_images as fixtures
from test_matched_repeat_policy import qualification

REAL_BINDING = images.qualification_binding
REAL_EXECUTION = session.require_execution


class ImageAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ImageTests('runTest'); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.q = self.f.q; self.root = self.f.root; self.rt = self.f.rt
        # These pre-existing image/admission fixtures mock native prerequisites.
        # The separate composite/session suites retain real witness coverage.
        self.enterContext(patch.object(session, 'require_execution', side_effect=lambda active:
            self.q.under_lock('native-completed-recovery-witness', {'paid_launch_ready': False})))
        # Restore the actual binding/verifier over the older mocked session
        # fixture. Only native prerequisites and the Docker daemon stay mocked.
        self.enterContext(patch.object(images, 'qualification_binding', REAL_BINDING))
        self.q.host['task_inventory'] = {cell['task_id']: dict(agent_timeout_seconds=180.,
            image_id='sha256:' + '9' * 64) for cell in policy.cells(self.q.f.manifest, 'terminus-2')}

    async def prepare(self):
        with self.q.open() as active:
            self.built = images.build(active)
            self.bound = images.qualification_binding(active)
            self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())
            self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())
            # Test-only rehearsal records. Real production qualification must
            # execute the isolated native producers; these are not native proof.
            self.proof = qualification(self.q.f.original, self.q.f.final,
                self.q.f.predecessor, self.q.f.manifest, 'terminus-2')
            self.proof.update(deepcopy(self.bound), sources=deepcopy(self.q.actual),
                sources_sha256=policy.fingerprint(self.q.actual),
                source_transition=deepcopy(self.q.host['source_transition']))
            self.q.f.proof = self.proof
            self.q.proof_files(include_images=False)
        self.f.commands.clear()

    async def verify(self):
        with self.q.open() as active:
            return session.verify_qualification(active)

    def refuse(self, expression=''):
        async def work():
            with self.q.invalidated() as active:
                with self.assertRaisesRegex((ValueError, OSError, RuntimeError), expression):
                    session.verify_qualification(active)
                with self.assertRaises(ValueError): session.describe(active)
        asyncio.run(work())

    def save_proof(self):
        self.q.private(policy.QUALIFICATION_FILE, self.proof)

    def rebind_image(self, record):
        """Tampering inside the temporary negative fixture, never real evidence."""
        sha = self.q.private(images.RESULT, record)
        self.proof['image_evidence_files']['.runtime/stage2/' + images.RESULT] = sha
        self.proof['image_build_sha256'] = policy.fingerprint(record)
        self.save_proof()

    def test_all_ten_producers_and_real_installed_reverification_bind_registration(self):
        asyncio.run(self.prepare())
        async def work():
            with self.q.open() as active:
                checked = session.verify_qualification(active)
                self.assertEqual(checked['image_build_sha256'], self.bound['image_build_sha256'])
                self.assertEqual(checked['image_evidence_files'], self.bound['image_evidence_files'])
                self.assertFalse(checked['paid_launch_ready'])
                block = study.register(active)
                self.assertEqual(block['image_build_sha256'], self.bound['image_build_sha256'])
                self.assertEqual(block['qualification_sha256'], policy.fingerprint(self.proof))
                self.assertEqual(len(self.proof['evidence_files']) + len(self.bound['image_evidence_files']), 10)
                self.assertEqual(self.q.auth.call_count, 2); self.assertEqual(self.q.old_auth.call_count, 2)
                self.assertEqual(self.q.lock.call_count, 2)
        asyncio.run(work())
        self.assertEqual(len(self.f.contexts), 1)
        self.assertEqual(sum(c[0] == 'run' for c in self.f.commands), 2)
        self.assertFalse(any(c[0] == 'build' for c in self.f.commands))
        self.q.process.assert_not_called()

    def test_legacy_inspection_fixture_cannot_register_without_real_recovery_witness(self):
        asyncio.run(self.prepare())
        async def work():
            with patch.object(session, 'require_execution', REAL_EXECUTION), self.q.invalidated() as active:
                with self.assertRaisesRegex(ValueError, 'Actual live recovery successor witness'):
                    study.register(active)
        asyncio.run(work())
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())
        self.assertEqual(self.f.commands, [])

    def test_every_admission_rechecks_images_without_another_handoff_or_build(self):
        asyncio.run(self.prepare())
        async def work():
            with self.q.open() as active:
                block = study.register(active)
                with study.dispatch_permit(active) as permit:
                    factory = study.agent_factory(permit)
                    before = sum(c[0] == 'run' for c in self.f.commands)
                    first = block['cells'][0]
                    self.assertEqual(study.admit_trial(root=self.root, trial_id=first['trial_id'],
                        task_id=first['task_id'], stage='final', factory=factory,
                        settings=policy.SETTINGS, gateway_image=self.proof['gateway_image'],
                        guard_image=self.proof['guard_image'], setup_timeout_seconds=900), policy.fingerprint(block))
                    self.assertGreater(sum(c[0] == 'run' for c in self.f.commands), before)
                self.assertEqual(self.q.auth.call_count, 2); self.assertEqual(self.q.old_auth.call_count, 2)
        asyncio.run(work()); self.assertEqual(len(self.f.contexts), 1)

    def test_missing_image_producers_fail_before_any_installed_image_command(self):
        asyncio.run(self.prepare())
        for name in (images.INTENT, images.RESULT):
            path = self.rt / name; raw = path.read_bytes(); path.unlink()
            with self.subTest(name=name): self.refuse()
            path.write_bytes(raw); path.chmod(0o600)
        self.assertEqual(self.f.commands, [])

    def test_raw_byte_change_is_rejected_even_when_canonical_metadata_is_equal(self):
        asyncio.run(self.prepare())
        for name in (images.INTENT, images.RESULT):
            path = self.rt / name; raw = path.read_bytes(); path.write_bytes(raw + b' ')
            with self.subTest(name=name): self.refuse('input changed')
            path.write_bytes(raw)
        self.assertEqual(self.f.commands, [])

    def test_policy_requires_exact_two_file_bindings_and_canonical_image_result(self):
        asyncio.run(self.prepare())
        for key in ('image_build_sha256', 'image_evidence_files'):
            value = self.proof.pop(key); self.save_proof()
            with self.subTest(key=key): self.refuse()
            self.proof[key] = value
        for files in ({}, {'.runtime/stage2/saved-copy.json': '0' * 64},
                dict(self.bound['image_evidence_files'], **{'.runtime/stage2/../escape': '0' * 64}),
                dict(self.bound['image_evidence_files'], **{'.runtime/stage2/extra.json': '0' * 64})):
            self.proof['image_evidence_files'] = files; self.save_proof()
            with self.subTest(files=files): self.refuse()
        self.assertEqual(self.f.commands, [])

    def test_self_consistent_changed_build_inputs_do_not_replace_live_session(self):
        asyncio.run(self.prepare())
        for key in ('sources_sha256', 'context_sha256', 'original_qualification_sha256',
                'custom_final_qualification_sha256', 'predecessor_authentication_sha256',
                'baseline_behaviour_authentication_sha256', 'runtime_identity_sha256', 'parent_gateway_image'):
            built = deepcopy(self.built)
            built['inputs'][key] = 'sha256:' + 'f' * 64 if key == 'parent_gateway_image' else 'f' * 64
            intent = session.wire.loads((self.rt / images.INTENT).read_bytes())
            intent['inputs'] = deepcopy(built['inputs'])
            intent_sha = self.q.private(images.INTENT, intent)
            built['intent_file_sha256'] = intent_sha
            self.proof['image_evidence_files']['.runtime/stage2/' + images.INTENT] = intent_sha
            self.rebind_image(built)
            with self.subTest(key=key): self.refuse('fresh session')
        self.assertEqual(self.f.commands, [])

    def test_paid_flags_or_wrong_kind_cannot_turn_image_record_into_qualification(self):
        asyncio.run(self.prepare())
        for key, value in (('paid_launch_ready', True), ('repeat_execution_qualified', True),
                ('historical_installed_bytes_attested', True), ('automatic_rebuild', True),
                ('kind', 'native_qualification'), ('live_api_calls', 1), ('live_api_calls', False)):
            built = deepcopy(self.built); built[key] = value; self.rebind_image(built)
            with self.subTest(key=key, value=value): self.refuse('fresh session')

    def test_saved_observation_hash_does_not_replace_actual_installed_bytes(self):
        asyncio.run(self.prepare())
        expected = {n:self.q.actual[n] for n in images.IMAGE_FILES}
        expected['retry_gateway.py'] = 'f' * 64
        self.f.report = dict(installed=expected,
            loaded={n:expected[n + '.py'] for n in ('matched_repeat_gateway', 'matched_repeat_fixture', 'retry_gateway')},
            import_only=True, live_api_calls=0)
        self.refuse('installed source')

    def test_changed_original_base_or_gateway_configuration_is_refused(self):
        asyncio.run(self.prepare())
        self.f.gateway['RootFS']['Layers'][0] = 'sha256:' + 'f' * 64
        self.refuse('original base')

    def test_changed_guard_image_metadata_is_refused(self):
        asyncio.run(self.prepare())
        self.f.guard['Config']['Env'].append('CHANGED=1')
        self.refuse('Actual image')

    def test_qualified_guard_must_match_build_and_all_lifecycle_results(self):
        asyncio.run(self.prepare())
        self.proof['guard_image'] = 'sha256:' + 'f' * 64; self.save_proof()
        self.refuse('original bound build')

    def test_one_lifecycle_cannot_claim_another_guard_with_an_updated_result_hash(self):
        asyncio.run(self.prepare())
        name = next(n for n in self.proof['evidence_files'] if n.endswith('/result.json'))
        value = session.wire.loads((self.root / name).read_bytes()); value['guard_image_id'] = 'sha256:' + 'f' * 64
        raw = json.dumps(value).encode(); (self.root / name).write_bytes(raw)
        self.proof['evidence_files'][name] = hashlib.sha256(raw).hexdigest(); self.save_proof()
        self.refuse('Actual repeat result')

    def test_existing_failure_marker_forbids_qualification_without_rebuild(self):
        asyncio.run(self.prepare()); self.q.private(images.FAILURE, {'exception_type': 'RuntimeError'})
        self.refuse('Retained native qualification failure'); self.assertEqual(self.f.commands, [])

    def test_private_modes_and_symlinked_build_evidence_are_refused(self):
        asyncio.run(self.prepare())
        for name in (images.INTENT, images.RESULT):
            path = self.rt / name; path.chmod(0o644)
            with self.subTest(name=name, kind='mode'): self.refuse('private')
            path.chmod(0o600); saved = path.with_suffix('.saved'); path.rename(saved); path.symlink_to(saved)
            with self.subTest(name=name, kind='symlink'): self.refuse('Symlink')
            path.unlink(); saved.rename(path)
        self.assertEqual(self.f.commands, [])

    def test_source_drift_during_actual_image_verification_invalidates_scope(self):
        asyncio.run(self.prepare()); command = self.f.docker.side_effect
        def changed(root, *args, **kwargs):
            result = command(root, *args, **kwargs)
            if args[0] == 'run': (self.root / 'stage2/matched_repeat_study.py').write_bytes(b'Changed source')
            return result
        self.f.docker.side_effect = changed; self.refuse()

    def test_build_file_drift_during_actual_image_verification_is_refused(self):
        asyncio.run(self.prepare()); command = self.f.docker.side_effect
        def changed(root, *args, **kwargs):
            result = command(root, *args, **kwargs)
            if args[0] == 'run':
                path = self.rt / images.RESULT; path.write_bytes(path.read_bytes() + b' ')
            return result
        self.f.docker.side_effect = changed; self.refuse('input changed')

    def test_change_after_verifier_returns_is_caught_before_binding_is_returned(self):
        asyncio.run(self.prepare()); real = images.verify
        async def work():
            with self.q.invalidated() as active:
                def changed(handle):
                    result = real(handle)
                    self.q.private(images.RESULT, dict(result, completed_utc='changed'))
                    return result
                with patch.object(images, 'verify', side_effect=changed):
                    with self.assertRaisesRegex(ValueError, 'after actual image'): images.qualification_binding(active)
                with self.assertRaises(ValueError): session.describe(active)
        asyncio.run(work())

    def test_final_session_recheck_cannot_hide_a_changed_image_file(self):
        asyncio.run(self.prepare()); real = images.qualification_binding
        async def work():
            with self.q.invalidated() as active:
                def changed(handle):
                    value = real(handle)
                    path = self.rt / images.RESULT; path.write_bytes(path.read_bytes() + b' ')
                    return value
                with patch.object(images, 'qualification_binding', side_effect=changed):
                    with self.assertRaises(ValueError): session.verify_qualification(active)
                with self.assertRaises(ValueError): session.describe(active)
        asyncio.run(work())

    def test_raw_change_after_verifier_returns_cannot_be_rebound_as_producer_bytes(self):
        asyncio.run(self.prepare()); real = images.verify
        async def work():
            with self.q.invalidated() as active:
                def changed(handle):
                    result = real(handle)
                    path = self.rt / images.RESULT; path.write_bytes(path.read_bytes() + b' ')
                    return result
                with patch.object(images, 'verify', side_effect=changed):
                    with self.assertRaisesRegex(ValueError, 'after actual image'): images.qualification_binding(active)
                with self.assertRaises(ValueError): session.describe(active)
        asyncio.run(work())

    def test_duplicate_metadata_keys_refused_even_when_rebound_to_the_same_value(self):
        asyncio.run(self.prepare())
        path = self.rt / images.RESULT
        raw = path.read_bytes().rstrip()[:-1] + b', "live_api_calls": 0}'
        path.write_bytes(raw)
        self.proof['image_evidence_files']['.runtime/stage2/' + images.RESULT] = hashlib.sha256(raw).hexdigest()
        self.save_proof(); self.refuse('Invalid private')

    def test_missing_or_wrong_returned_binding_cannot_grant_admission(self):
        asyncio.run(self.prepare())
        for changed in ({}, dict(self.bound, image_build_sha256='f' * 64)):
            with patch.object(images, 'qualification_binding', return_value=changed):
                with self.subTest(changed=changed): self.refuse('freshly verified actual')

    def test_build_files_stay_bound_after_retained_results_are_read(self):
        asyncio.run(self.prepare())
        async def work():
            with self.q.open() as active:
                block = study.register(active)
                with study.dispatch_permit(active) as permit:
                    factory = study.agent_factory(permit); real = study._attempts
                    def changed(*args, **kwargs):
                        value = real(*args, **kwargs)
                        path = self.rt / images.RESULT; path.write_bytes(path.read_bytes() + b' ')
                        return value
                    cell = block['cells'][0]
                    with patch.object(study, '_attempts', side_effect=changed):
                        with self.assertRaises(ValueError): study.admit_trial(root=self.root,
                            trial_id=cell['trial_id'], task_id=cell['task_id'], stage='final', factory=factory,
                            settings=policy.SETTINGS, gateway_image=self.proof['gateway_image'],
                            guard_image=self.proof['guard_image'], setup_timeout_seconds=900)
        asyncio.run(work())

    def test_dispatch_scope_quick_checks_retain_both_build_files(self):
        asyncio.run(self.prepare())
        async def work():
            with self.q.open() as active:
                study.register(active)
                with study.dispatch_permit(active) as permit:
                    _, state = study._state(permit)
                    self.assertTrue(policy.IMAGE_EVIDENCE_FILES <= state['files'].keys())
                    for name in (images.INTENT, images.RESULT):
                        path = self.rt / name; raw = path.read_bytes(); path.write_bytes(raw + b' ')
                        with self.subTest(name=name), self.assertRaises(ValueError): study._quick(state)
                        path.write_bytes(raw)
        asyncio.run(work())

    def test_changed_registration_image_binding_is_not_reused(self):
        asyncio.run(self.prepare())
        async def work():
            with self.q.open() as active:
                block = study.register(active)
                self.q.private(policy.REGISTRATION_FILE, dict(block, image_build_sha256='f' * 64))
                with self.assertRaisesRegex(ValueError, 'immutable'): study.register(active)
        asyncio.run(work())

    def test_saved_closed_or_child_task_session_cannot_reverify_image_binding(self):
        asyncio.run(self.prepare())
        async def work():
            with self.q.invalidated() as active:
                saved = session.describe(active)
                with self.assertRaises(ValueError): images.qualification_binding(saved)
                async def child():
                    with self.assertRaisesRegex(ValueError, 'async tasks'): images.qualification_binding(active)
                await asyncio.create_task(child())
                with self.assertRaises(ValueError): session.describe(active)
            with self.assertRaises(ValueError): images.qualification_binding(active)
        asyncio.run(work()); self.assertEqual(self.f.commands, [])

    def test_main_thread_and_async_task_remain_required_for_qualification_reverification(self):
        asyncio.run(self.prepare())
        with self.q.invalidated() as active:
            with patch.object(session, '_task', return_value=None), self.assertRaisesRegex(ValueError, 'async tasks'):
                session.verify_qualification(active)
        async def work():
            with self.q.invalidated() as active, patch.object(threading, 'main_thread', return_value=object()):
                with self.assertRaisesRegex(ValueError, 'threads'): session.verify_qualification(active)
        asyncio.run(work()); self.assertEqual(self.f.commands, [])

    def test_active_or_stopped_ancestor_prevents_reverification(self):
        asyncio.run(self.prepare())
        self.q.inactive.side_effect = ValueError('Active custom final')
        with self.assertRaisesRegex(ValueError, 'Active custom final'): asyncio.run(self.verify())
        self.q.inactive.side_effect = None; self.q.private('operator-stop-request.json', {'automatic_resume': False})
        with self.assertRaisesRegex(ValueError, 'Persistent stop'): asyncio.run(self.verify())
        self.assertEqual(self.f.commands, [])


if __name__ == '__main__':
    unittest.main()
