"""Real private files/locks and mocked native readers; never paid evidence."""
import asyncio
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import pickle
import threading
from unittest.mock import patch

import matched_repeat_session as session
import matched_repeat_policy as policy
from run_credit_only import hold
from test_matched_repeat_runtime import TreeTests
from test_matched_repeat_policy import image_evidence


class SessionTests(TreeTests):
    def setUp(self):
        super().setUp()
        self.root = self.root.resolve()
        self.events = []; self.locked = False; self.witness = object()
        self.enterContext(patch.object(session.platform, 'system', return_value='Linux'))
        self.enterContext(patch.object(session, '__file__', str(self.root / 'stage2/matched_repeat_session.py')))
        self.enterContext(patch.dict(session.runtime.DEPLOYMENTS, {'terminus-2': self.root}))
        self.enterContext(patch.object(session.runtime, 'loaded_sources'))
        for name, value, anchor in ((policy.BASELINE_FILE, self.f.original, 'ORIGINAL_FILE_SHA256'),
                (policy.FINAL_FILE, self.f.final, 'FINAL_FILE_SHA256')):
            sha = self.private(name, value)
            self.enterContext(patch.object(session.baseline, anchor, sha))
        self.inactive = self.enterContext(patch.object(session.baseline, 'inactive_ancestors'))
        final_root = self.root / 'native-final'; (final_root / '.runtime/stage2').mkdir(parents=True)
        self.enterContext(patch.object(session.baseline, 'FINAL_ROOT', final_root))
        common = dict(experiment=policy.EXPERIMENT, harness='terminus-2', paid_launch_ready=False,
            original_qualification_sha256=policy.fingerprint(self.f.original),
            custom_final_qualification_sha256=policy.fingerprint(self.f.final))
        self.pred = dict(common, kind=session.handoff.KIND, current_sources_sha256=policy.fingerprint(self.actual),
            predecessors=deepcopy(self.f.predecessor), streamed_backup=dict(sha256='1' * 64))
        self.old = dict(common, kind=session.original_audit.KIND,
            current_sources_sha256=policy.fingerprint(self.actual), audit_sha256='2' * 64)
        self.library = dict(common, kind=session.baseline.KIND,
            current_sources_sha256=policy.fingerprint(self.actual),
            fixture_current_library_bytes={'module.py': '3' * 64})
        self.host = dict(common, kind=session.runtime.KIND,
            sources=deepcopy(self.actual), sources_sha256=policy.fingerprint(self.actual),
            source_transition=deepcopy(self.f.proof['source_transition']),
            dependencies=deepcopy(self.f.final['dependencies']), python_runtime=deepcopy(self.f.final['python_runtime']),
            host_environment=deepcopy(self.f.final['host_environment']))
        self.auth = self.enterContext(patch.object(session.handoff, 'authenticate', side_effect=self.authenticate))
        self.old_auth = self.enterContext(patch.object(session.original_audit, 'authenticate', side_effect=self.original_auth))
        self.lock = self.enterContext(patch.object(session.original_audit, 'lock_all', side_effect=self.locks))
        self.pred_check = self.enterContext(patch.object(session.handoff, 'recheck', side_effect=self.predecessor_check))
        self.old_check = self.enterContext(patch.object(session.original_audit, 'recheck',
            side_effect=lambda *args: self.under_lock('original-recheck', self.old)))
        self.lib_read = self.enterContext(patch.object(session.baseline, 'inspect',
            side_effect=lambda *args: self.under_lock('library-inspect', self.library)))
        self.lib_check = self.enterContext(patch.object(session.baseline, 'recheck',
            side_effect=lambda *args: self.under_lock('library-recheck', self.library)))
        self.host_read = self.enterContext(patch.object(session.runtime, 'inspect',
            side_effect=lambda *args: self.under_lock('host-inspect', self.host)))
        self.images = self.enterContext(patch.object(session.runtime, '_images',
            side_effect=lambda refs: {ref: dict(id=ref) for ref in refs}))
        self.process = self.enterContext(patch('subprocess.run', side_effect=AssertionError('No native calls in local tests')))
        incoming, outgoing = os.pipe(); os.close(outgoing)
        self.stream = os.fdopen(incoming, 'rb'); self.addCleanup(self.stream.close)
        self.proof_files()
        # This older session fixture has no actual Docker producer. Dedicated
        # image/admission tests restore the real binding and verifier together.
        self.image_binding = self.enterContext(patch('matched_repeat_images.qualification_binding',
            side_effect=lambda active: self.under_lock('image-verification', {
                k: deepcopy(self.f.proof[k]) for k in ('image_build_sha256', 'image_evidence_files',
                    'gateway_image', 'guard_image')})))

    def private(self, name, value):
        relative = '.runtime/stage2/' + name
        sha = self.write(relative, json.dumps(value, sort_keys=True, allow_nan=False).encode())
        (self.root / relative).chmod(0o600)
        return sha

    def authenticate(self, root, original, final, harness, stream):
        self.assertFalse(self.locked); self.events.append('handoff-authenticate')
        self.assertEqual((root, harness, stream), (self.root, 'terminus-2', self.stream))
        self.assertEqual(original, self.f.original); self.assertEqual(final, self.f.final)
        return self.witness

    def original_auth(self, *args):
        self.assertFalse(self.locked); self.events.append('original-authenticate')
        return deepcopy(self.old)

    def locks(self, stack, root, harness):
        self.assertFalse(self.locked); self.events.append('lock-all')
        self.assertEqual((root, harness), (self.root, 'terminus-2'))
        stack.callback(self.unlocked)
        # The complete inherited lock helper has its own integration coverage.
        # Here real competing file locks prove this caller keeps its scope open.
        hold(stack, self.f.runtime, 'matrix.lock')
        for name in ('original-ancestor', 'active-final-ancestor'):
            folder = self.root / name; folder.mkdir(exist_ok=True)
            for lock in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                hold(stack, folder, lock)
        self.locked = True
        stack.callback(self.before_release)

    def before_release(self):
        self.assertFalse(any(state['root'] == self.root for state in session._SESSIONS.values()))
        self.events.append('invalidate-before-unlock')

    def unlocked(self):
        self.locked = False; self.events.append('unlocked')

    def under_lock(self, name, value):
        self.assertTrue(self.locked); self.events.append(name)
        return deepcopy(value)

    def predecessor_check(self, root, original, final, harness, witness):
        self.assertIs(witness, self.witness)
        return self.under_lock('predecessor-recheck', self.pred)

    def open(self, harness='terminus-2', stream=None):
        return session.open_session(self.root, harness, self.stream if stream is None else stream)

    def proof_files(self, *, include_images=True):
        proof = self.f.proof
        if include_images:
            image_evidence(self.root, proof)
        contents = {proof['regression_path'] + '/regression.json': json.dumps(proof['offline']).encode(),
            proof['regression_path'] + '/regression.txt': b'Synthetic local regression output, not native proof\n'}
        for case in proof['synthetic']:
            name = 'synthetic-matched-repeat-terminus-2-' + case['mode']
            cancelled = case['mode'] == 'cancel_setup'
            result = dict(trial_id=name, harness='terminus-2', stage='final',
                matched_repeat_experiment=policy.EXPERIMENT, model_protocol_sha256=policy.MODEL_SHA256,
                gateway_image_id=proof['gateway_image'], guard_image_id=proof['guard_image'],
                status='interrupted' if cancelled else 'verified',
                verifier_result=None if cancelled else {'rewards': {'reward': 1.0}},
                model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True)
            trial = case['runtime_path'] + '/.runtime/stage2/scored-trials/' + name
            supporting = {case['runtime_path'] + '/' + n: b'Local synthetic test fixture only'
                for n in ('stage2/input_manifest.json', '.env', '.runtime/stage2/matched-repeat-isolated-fixture.json')}
            supporting.update({trial + '/started.json': json.dumps(result).encode(),
                trial + '/result.json': json.dumps(result).encode(), trial + '/traces/test.json': b'{}'})
            case.update(paid_launch_ready=False, repeat_execution_qualified=False,
                image_build_sha256=proof['image_build_sha256'], image_evidence_files=deepcopy(proof['image_evidence_files']),
                producer_files={n:self.write(n, raw) for n, raw in supporting.items()})
            for n in supporting: (self.root / n).chmod(0o600)
            contents[case['runtime_path'] + '/evidence.json'] = json.dumps(case).encode()
            contents[trial + '/result.json'] = supporting[trial + '/result.json']
            self.private('matched-repeat-rehearsal-' + case['mode'] + '.json', dict(
                kind='one_shot_synthetic_matched_repeat_rehearsal', harness='terminus-2', mode=case['mode'],
                runtime_path=case['runtime_path'], sources_sha256=self.host['sources_sha256'],
                image_build_sha256=proof['image_build_sha256'], automatic_resume=False, paid_launch_ready=False))
        for name, raw in contents.items():
            proof['evidence_files'][name] = self.write(name, raw); (self.root / name).chmod(0o600)
        proof['baseline_behaviour_authentication_sha256'] = policy.fingerprint(self.library)
        proof['runtime_identity_sha256'] = policy.fingerprint(self.host)
        for name, value in ((policy.PREDECESSOR_FILE, self.f.predecessor),
                (policy.RUNTIME_FILE, self.host), (policy.QUALIFICATION_FILE, proof)):
            self.private(name, value)
        self.completion_files()

    def completion_files(self):
        """Temporary fabricated metadata for mocked native readers, never real proof."""
        proof = self.f.proof
        intent = dict(kind='one_shot_actual_native_repeat_qualification', harness='terminus-2',
            sources_sha256=self.host['sources_sha256'], runtime_identity_sha256=policy.fingerprint(self.host),
            baseline_behaviour_authentication_sha256=policy.fingerprint(self.library),
            predecessor_authentication_sha256=policy.fingerprint(self.pred['predecessors']),
            regression_path=proof['regression_path'], pid=123, started_utc='synthetic-test-only',
            automatic_resume=False, paid_launch_ready=False)
        self.private(policy.QUALIFIER_INTENT_FILE, intent)
        names = {'.runtime/stage2/' + n for n in (policy.POLICY_FILE, policy.MANIFEST_FILE,
            policy.PREDECESSOR_FILE, policy.RUNTIME_FILE, policy.QUALIFICATION_FILE, policy.QUALIFIER_INTENT_FILE)}
        names.update(proof['evidence_files']); names.update(proof['image_evidence_files'])
        for case in proof['synthetic']:
            names.update(case['producer_files'])
            names.add('.runtime/stage2/matched-repeat-rehearsal-' + case['mode'] + '.json')
        files = {n:hashlib.sha256((self.root / n).read_bytes()).hexdigest() for n in names}
        self.private(policy.QUALIFIER_RESULT_FILE, dict(
            kind='actual_native_repeat_qualification_complete_not_dispatch', status='qualified',
            qualification_sha256=policy.fingerprint(proof), offline_tests=proof['offline']['tests'], native_cases=3,
            live_api_calls=0, producer_files=files, completed_utc='synthetic-test-only',
            automatic_resume=False, paid_launch_ready=False))

    def test_actual_authentication_precedes_outer_locks_and_inspection_stays_under_them(self):
        with self.open() as active:
            self.assertEqual(self.events[:3], ['handoff-authenticate', 'original-authenticate', 'lock-all'])
            value = session.describe(active)
            self.assertFalse(value['paid_launch_ready']); self.assertFalse(value['limitations']['repeat_execution_qualified'])
            self.assertEqual(value['predecessor']['predecessors'], self.f.predecessor)
            self.assertFalse(value['limitations']['historical_installed_bytes_attested'])
            self.assertTrue(self.locked)
        self.assertEqual(self.events[-2:], ['invalidate-before-unlock', 'unlocked'])
        self.auth.assert_called_once(); self.old_auth.assert_called_once(); self.lock.assert_called_once()
        self.process.assert_not_called()

    def test_all_ancestor_locks_stay_held_until_session_exit(self):
        with self.open():
            for folder in (self.f.runtime, self.root / 'original-ancestor', self.root / 'active-final-ancestor'):
                with self.subTest(folder=folder), ExitStack() as contender:
                    with self.assertRaises(BlockingIOError): hold(contender, folder, 'matrix.lock')
        with ExitStack() as contender:
            hold(contender, self.f.runtime, 'matrix.lock')

    def test_recheck_does_not_reaudit_retransfer_or_reacquire_locks(self):
        with self.open() as active:
            before = self.lib_check.call_count
            session.recheck(active)
            self.assertEqual(self.lib_check.call_count, before + 1)
            self.auth.assert_called_once(); self.old_auth.assert_called_once(); self.lock.assert_called_once()

    def test_active_ancestor_refused_before_stream_audit_or_locks(self):
        self.inactive.side_effect = ValueError('Active final study')
        with self.assertRaisesRegex(ValueError, 'Active final'):
            with self.open(): self.fail('Must not open')
        self.auth.assert_not_called(); self.old_auth.assert_not_called(); self.lock.assert_not_called()

    def test_actual_stop_files_and_symlinked_stops_refused_before_authentication(self):
        for base in (self.f.runtime, session.baseline.FINAL_ROOT / '.runtime/stage2'):
            for name in ('operator-stop-request.json', 'provider-stop.json'):
                marker = base / name; marker.symlink_to(base / 'absent')
                with self.subTest(base=base, name=name), self.assertRaisesRegex(ValueError, 'Persistent stop'):
                    with self.open(): self.fail('Must not open')
                marker.unlink()
        self.auth.assert_not_called()

    def test_regular_file_or_saved_metadata_cannot_replace_live_pipe(self):
        path = self.f.runtime / policy.QUALIFICATION_FILE
        with path.open('rb') as stream:
            with self.assertRaisesRegex(ValueError, 'pipe'):
                with self.open(stream=stream): self.fail('Must not open')
        self.auth.assert_not_called()

    def test_wrong_host_root_or_module_and_openhands_refused_before_stream(self):
        for target, name, value in ((session.platform, 'system', lambda: 'Darwin'),
                (session, '__file__', '/different/stage2/matched_repeat_session.py')):
            with patch.object(target, name, value), self.assertRaises(ValueError):
                with self.open(): self.fail('Must not open')
        with self.assertRaisesRegex(ValueError, 'OpenHands'):
            with self.open('openhands'): self.fail('Must not open')
        with self.assertRaises(ValueError):
            with session.open_session(self.root / 'wrong', 'terminus-2', self.stream): self.fail('Must not open')
        self.auth.assert_not_called()

    def test_actual_private_anchor_bytes_permissions_and_symlinks_are_checked(self):
        path = self.f.runtime / policy.BASELINE_FILE; raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'Exact private'):
            with self.open(): self.fail('Must not open')
        path.write_bytes(raw); path.chmod(0o644)
        with self.assertRaises(ValueError):
            with self.open(): self.fail('Must not open')
        path.chmod(0o600); path.rename(self.f.runtime / 'moved.json')
        path.symlink_to(self.f.runtime / 'moved.json')
        with self.assertRaises(ValueError):
            with self.open(): self.fail('Must not open')
        self.auth.assert_not_called()

    def test_source_change_between_authentication_and_lock_acquisition_is_refused(self):
        previous = self.old_auth.side_effect
        def changed(*args):
            value = previous(*args)
            (self.root / 'stage2/matched_repeat_session.py').write_bytes(b'Changed source after audit')
            return value
        self.old_auth.side_effect = changed
        with self.assertRaises(ValueError):
            with self.open(): self.fail('Must not open')
        self.lib_read.assert_not_called(); self.assertFalse(self.locked)

    def test_source_or_private_input_change_permanently_invalidates_session(self):
        for path in (self.root / 'stage2/matched_repeat_session.py', self.f.runtime / policy.FINAL_FILE):
            raw = path.read_bytes()
            with self.subTest(path=path), self.open() as active:
                path.write_bytes(raw + b' ')
                with self.assertRaises(ValueError): session.recheck(active)
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'active locked'): session.recheck(active)
            self.assertFalse(self.locked)

    def test_all_four_reader_records_must_agree_on_current_sources_and_identity(self):
        for record in (self.pred, self.old, self.library, self.host):
            for key, changed in (('harness', 'openhands'), ('paid_launch_ready', True),
                    ('sources_sha256' if record is self.host else 'current_sources_sha256', '9' * 64)):
                before = deepcopy(record); record[key] = changed
                with self.subTest(kind=record['kind'], key=key), self.assertRaises(ValueError):
                    with self.open(): self.fail('Must not open')
                record.clear(); record.update(before)

    def test_different_qualification_anchor_in_reader_record_is_refused(self):
        self.library['original_qualification_sha256'] = '9' * 64
        with self.assertRaisesRegex(ValueError, 'qualification anchors'):
            with self.open(): self.fail('Must not open')

    def test_changed_libraries_or_host_fail_closed_during_recheck(self):
        for record in (self.library, self.host):
            with self.subTest(kind=record['kind']), self.open() as active:
                record['changed_after_open'] = True
                with self.assertRaisesRegex(ValueError, 'observation changed'): session.recheck(active)
                record.pop('changed_after_open')
                with self.assertRaisesRegex(ValueError, 'active locked'): session.describe(active)

    def test_result_or_supporting_evidence_recheck_failure_invalidates_session(self):
        for reader in (self.pred_check, self.old_check):
            previous = reader.side_effect
            with self.subTest(reader=reader), self.open() as active:
                reader.side_effect = ValueError('Actual result or supporting inventory drift')
                with self.assertRaisesRegex(ValueError, 'inventory drift'): session.recheck(active)
                reader.side_effect = previous
                with self.assertRaises(ValueError): session.describe(active)

    def test_mutation_during_library_host_inspection_is_caught_by_final_rechecks(self):
        previous = self.host_read.side_effect
        def changed(*args):
            value = previous(*args)
            (self.root / 'stage2/matched_repeat_handoff.py').write_bytes(b'Mutated during long inspection')
            return value
        with self.open() as active:
            self.host_read.side_effect = changed
            with self.assertRaises(ValueError): session.recheck(active)

    def test_description_is_detached_and_cannot_be_used_as_a_session(self):
        with self.open() as active:
            record = session.describe(active)
            record['runtime']['sources'].clear(); record['predecessor']['predecessors']['blocks'].clear()
            self.assertEqual(session.describe(active)['runtime']['sources'], self.actual)
            for invalid in (record, session._Session(), None, {'checks': True}):
                with self.subTest(invalid=type(invalid)), self.assertRaises(ValueError): session.recheck(invalid)

    def test_pickle_deepcopy_closed_session_and_process_reuse_refused(self):
        with self.open() as active:
            for copy in (pickle.dumps, deepcopy):
                with self.assertRaises(TypeError): copy(active)
            with patch.object(session.os, 'getpid', return_value=-1):
                with self.assertRaisesRegex(ValueError, 'cross processes'): session.describe(active)
        with self.assertRaisesRegex(ValueError, 'active locked'): session.describe(active)

    def test_session_cannot_cross_thread_or_allow_overlapping_authentication(self):
        errors = []
        with self.open() as active:
            def other():
                for operation in (lambda: session.describe(active), lambda: self.open().__enter__()):
                    try: operation()
                    except ValueError as error: errors.append(str(error))
            worker = threading.Thread(target=other); worker.start(); worker.join(timeout=5)
            self.assertFalse(worker.is_alive()); self.assertEqual(len(errors), 2)
            session.recheck(active)
            self.auth.assert_called_once()

    def test_async_child_cannot_reuse_parent_session_even_with_inherited_context(self):
        async def work():
            with self.open() as active:
                async def child():
                    with self.assertRaisesRegex(ValueError, 'async tasks'): session.describe(active)
                await asyncio.create_task(child())
                session.recheck(active)
        asyncio.run(work())

    def test_nested_session_fails_before_another_handoff(self):
        with self.open() as active:
            with self.assertRaisesRegex(ValueError, 'nested'):
                with self.open(): self.fail('Must not nest')
            session.recheck(active); self.auth.assert_called_once()

    def test_body_exception_releases_locks_invalidates_and_next_operation_reauthenticates(self):
        with self.assertRaisesRegex(RuntimeError, 'Caller failed'):
            with self.open() as active: raise RuntimeError('Caller failed')
        with self.assertRaises(ValueError): session.describe(active)
        with self.open(): pass
        self.assertEqual(self.auth.call_count, 2); self.assertEqual(self.old_auth.call_count, 2)

    def test_failure_at_each_prerequisite_leaves_no_live_session_or_held_gate(self):
        for reader in (self.auth, self.old_auth, self.lock, self.pred_check, self.old_check,
                self.lib_read, self.host_read, self.lib_check):
            previous = reader.side_effect; reader.side_effect = ValueError('Prerequisite refused')
            with self.subTest(reader=reader), self.assertRaisesRegex(ValueError, 'Prerequisite refused'):
                with self.open(): self.fail('Must not open')
            reader.side_effect = previous
            self.assertFalse(self.locked); self.assertFalse(session._SESSIONS)
            with self.open(): pass

    def test_fresh_operation_never_accepts_the_previous_projection_or_witness(self):
        with self.open() as first: saved = session.describe(first)
        with self.open() as second:
            with self.assertRaises(ValueError): session.recheck(first)
            with self.assertRaises(ValueError): session.recheck(saved)
            self.assertIsNot(first, second)
        self.assertEqual(self.auth.call_count, 2)

    def test_qualification_reads_actual_producers_and_binds_fresh_observations(self):
        before = (self.f.runtime / policy.REGISTRATION_FILE).read_bytes()
        with self.open() as active, patch.object(session.runtime, 'verify_native_files',
                wraps=session.runtime.verify_native_files) as producers:
            result = session.verify_qualification(active)
            producers.assert_called_once()
            self.assertFalse(result['paid_launch_ready'])
            self.assertEqual(result['baseline_behaviour_authentication_sha256'], policy.fingerprint(self.library))
            self.assertEqual(result['runtime_identity_sha256'], policy.fingerprint(self.host))
            self.assertEqual(result['qualification_sha256'], policy.fingerprint(self.f.proof))
            self.assertEqual(len(result['private_files']), 5)
            self.auth.assert_called_once(); self.old_auth.assert_called_once()
        self.assertEqual((self.f.runtime / policy.REGISTRATION_FILE).read_bytes(), before)
        self.process.assert_not_called()

    def test_missing_qualification_does_not_create_or_substitute_a_proof(self):
        path = self.f.runtime / policy.QUALIFICATION_FILE; path.unlink()
        with self.open() as active:
            with self.assertRaises((OSError, ValueError)): session.verify_qualification(active)
            with self.assertRaises(ValueError): session.describe(active)
        self.assertFalse(path.exists())

    def test_saved_predicate_library_or_host_flags_cannot_replace_live_bindings(self):
        original = deepcopy(self.f.proof)
        for key in ('baseline_behaviour_authentication_sha256', 'runtime_identity_sha256', 'harness'):
            proof = deepcopy(original); proof[key] = 'openhands' if key == 'harness' else '9' * 64
            self.private(policy.QUALIFICATION_FILE, proof)
            with self.subTest(key=key), self.open() as active:
                with self.assertRaisesRegex(ValueError, 'actual live'): session.verify_qualification(active)
            self.private(policy.QUALIFICATION_FILE, original)
        for name, value in ((policy.PREDECESSOR_FILE, dict(self.f.predecessor, checks=True)),
                (policy.RUNTIME_FILE, dict(self.host, checks=True))):
            path = self.f.runtime / name; raw = path.read_bytes(); self.private(name, value)
            with self.subTest(name=name), self.open() as active:
                with self.assertRaisesRegex(ValueError, 'actual live'): session.verify_qualification(active)
            path.write_bytes(raw)

    def test_changed_policy_manifest_or_private_permissions_refused(self):
        for name in (policy.POLICY_FILE, policy.MANIFEST_FILE, policy.PREDECESSOR_FILE, policy.RUNTIME_FILE):
            path = self.f.runtime / name; raw = path.read_bytes()
            self.private(name, {'checks': True})
            with self.subTest(name=name), self.open() as active:
                with self.assertRaises(ValueError): session.verify_qualification(active)
            path.write_bytes(raw); path.chmod(0o644)
            with self.subTest(name=name, permissions=True), self.open() as active:
                with self.assertRaises(ValueError): session.verify_qualification(active)
            path.chmod(0o600)

    def test_every_actual_producer_file_must_still_match(self):
        for name in self.f.proof['evidence_files']:
            path = self.root / name; raw = path.read_bytes(); path.write_bytes(raw + b' ')
            with self.subTest(name=name), self.open() as active:
                with self.assertRaisesRegex(ValueError, 'producer bytes'): session.verify_qualification(active)
            path.write_bytes(raw)

    def test_matching_hash_of_wrong_lifecycle_result_is_not_execution_proof(self):
        name = next(name for name in self.f.proof['evidence_files'] if name.endswith('/result.json'))
        value = json.loads((self.root / name).read_text()); value['model_revoked'] = False
        raw = json.dumps(value).encode(); (self.root / name).write_bytes(raw)
        proof = deepcopy(self.f.proof); proof['evidence_files'][name] = hashlib.sha256(raw).hexdigest()
        self.private(policy.QUALIFICATION_FILE, proof)
        with self.open() as active:
            with self.assertRaisesRegex(ValueError, 'Actual repeat result'): session.verify_qualification(active)

    def test_actual_image_and_qualified_source_must_remain_available(self):
        self.images.side_effect = lambda refs: {}
        with self.open() as active:
            with self.assertRaisesRegex(ValueError, 'pinned repeat'): session.verify_qualification(active)

    def test_private_proof_mutation_during_verification_refused_and_not_revivable(self):
        actual = session.runtime.verify_current
        def changed(*args):
            value = actual(*args)
            path = self.f.runtime / policy.QUALIFICATION_FILE; path.write_bytes(path.read_bytes() + b' ')
            return value
        with self.open() as active, patch.object(session.runtime, 'verify_current', side_effect=changed):
            with self.assertRaises(ValueError): session.verify_qualification(active)
            with self.assertRaises(ValueError): session.describe(active)

    def test_producer_mutation_during_last_recheck_is_refused(self):
        previous = self.lib_check.side_effect; calls = 0
        def changed(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                name = next(iter(self.f.proof['evidence_files']))
                (self.root / name).write_bytes(b'Mutated producer after verification')
            return previous(*args)
        with self.open() as active:
            self.lib_check.side_effect = changed
            with self.assertRaises(ValueError): session.verify_qualification(active)


if __name__ == '__main__':
    import unittest
    unittest.main()
