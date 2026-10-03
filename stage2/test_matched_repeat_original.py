"""Mocked original native collector with real files/locks, not paid evidence."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_original as reader
import matched_repeat_policy as policy
from run_credit_only import hold
from test_matched_repeat_runtime import TreeTests


class AuditTests(TreeTests):
    def setUp(self):
        super().setUp()
        self.root = self.root.resolve()
        self.native = self.root / 'original'; self.native.mkdir(mode=0o700)
        self.final_root = self.root / 'final'; (self.final_root / '.runtime/stage2').mkdir(parents=True)
        self.old = self.f.original; self.final = self.f.final
        for name in self.old['sources']:
            raw = ((b'Original ' + name.encode()) if name in policy.INHERITED_BASELINE_DELTAS
                else (self.root / 'stage2' / name).read_bytes())
            self.old['sources'][name] = self.put(self.native, 'stage2/' + name, raw)
        for name in reader.CURRENT_COLLECTOR_IMPORTS:
            self.put(self.native, 'stage2/' + name, (self.root / 'stage2' / name).read_bytes())
        self.old.update(gateway_image='sha256:' + 'a' * 64, guard_image='sha256:' + 'b' * 64,
            evidence_folder='qualification-fixture', evidence_sha256={})
        for name in ('offline.json', 'image.json', 'synthetic.json'):
            self.old['evidence_sha256'][name] = self.put(self.native,
                '.runtime/stage2/qualification-fixture/' + name, b'{"synthetic":true}')
        old_raw = json.dumps(self.old).encode(); final_raw = json.dumps(self.final).encode()
        old_sha = self.put(self.root, '.runtime/stage2/' + policy.BASELINE_FILE, old_raw)
        self.put(self.native, '.runtime/stage2/corrected-qualification.json', old_raw)
        final_sha = self.put(self.root, '.runtime/stage2/' + policy.FINAL_FILE, final_raw)
        registration = self.put(self.native, '.runtime/stage2/corrected-matrix.json', b'{"fixture":true}')
        provider = self.put(self.native, '.runtime/stage2/provider-check.json', b'{"fixture":true}')
        self.data = dict(experiment='baseline-corrected-credit-only-20260923',
            collected_utc='2026-09-25T12:00:00Z', sources_sha256=self.old['sources'],
            model_protocol=policy.SETTINGS.document(), model_protocol_sha256=policy.MODEL_SHA256,
            qualification_sha256=old_sha, registration_sha256=registration, provider_check_sha256=provider,
            gateway_image=self.old['gateway_image'], guard_image=self.old['guard_image'],
            audit_checks={'synthetic_local_test': True}, rows=[],
            service=dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0'))
        for index, task in enumerate(self.f.manifest['all_task_ids']):
            for harness in ('terminus-2', 'openhands'):
                name = 'original-' + harness + '-' + task
                result_sha = self.put(self.native, '.runtime/stage2/scored-trials/' + name + '/result.json',
                    json.dumps(dict(trial_id=name, reward=index % 2)).encode())
                self.put(self.native, '.runtime/stage2/scored-trials/' + name + '/traces/root.json', b'{"fixture":true}')
                self.put(self.native, '.runtime/stage2/scored-attempts/' + name + '/0001.request.json', b'{"private":"not-returned"}')
                self.put(self.native, '.runtime/stage2/scored-attempts/' + name + '/0001.outcome.json', b'{"cost_usd":null}')
                self.data['rows'].append(dict(trial_id=name, task_id=task, harness=harness, reward=index % 2,
                    agent_error_type='', verifier_error_type='', cleanup_complete=True, model_revoked=True,
                    unknown_cost_requests=1, total_cost_usd=None, known_cost_usd='0',
                    accepted_model_responses=1, model_requests=2, agent_seconds=7200.0, result_sha256=result_sha))
        snapshot_sha = self.put(self.root, reader.SNAPSHOT, json.dumps(self.data).encode())
        launch_sha = self.put(self.root, reader.PUBLIC + '/launch.json', json.dumps(dict(hashes={
            key: self.data[key] for key in ('registration_sha256', 'qualification_sha256',
                'provider_check_sha256', 'model_protocol_sha256')})).encode())
        stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=list(self.data['rows'][0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(sorted(self.data['rows'], key=lambda r: (r['task_id'], r['harness'])))
        csv_sha = self.put(self.root, reader.PUBLIC + '/trials.csv', stream.getvalue().encode())
        for name in ('corrected-policy.json', 'credit-only-policy.json', 'model-protocol.json'):
            self.put(self.native, '.runtime/stage2/' + name, b'{"fixture":true}')
        for module, name, value in ((policy, 'ORIGINAL_QUALIFICATION_SHA256', policy.fingerprint(self.old)),
                (policy, 'BASELINE_CSV_SHA256', csv_sha),
                (reader.baseline, 'ORIGINAL_ROOT', self.native), (reader.baseline, 'FINAL_ROOT', self.final_root),
                (reader.baseline, 'ORIGINAL_FILE_SHA256', old_sha), (reader.baseline, 'FINAL_FILE_SHA256', final_sha),
                (reader, 'SNAPSHOT_SHA256', snapshot_sha), (reader, 'LAUNCH_SHA256', launch_sha),
                (reader, 'COLLECTOR_SHA256', self.actual['export_corrected.py']),
                (reader, '__file__', str(self.root / 'stage2/matched_repeat_original.py')),
                (reader.exporter, '__file__', str(self.root / 'stage2/export_corrected.py')),
                (reader.exporter, 'OUTPUT', self.root / reader.PUBLIC)):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.dict(reader.runtime.DEPLOYMENTS, {'terminus-2': self.root}))
        self.enterContext(patch.object(reader.platform, 'system', return_value='Linux'))
        self.loaded = self.enterContext(patch.object(reader.runtime, 'loaded_sources'))
        self.inactive = self.enterContext(patch.object(reader.baseline, 'inactive_ancestors'))
        self.enterContext(patch.object(reader.locks.os, 'listxattr', return_value=[], create=True))
        self.enterContext(patch.object(reader.locks, '_parents', side_effect=lambda path:
            tuple(p for p in reversed(path.parents) if p == self.root or p.is_relative_to(self.root))))
        self.lock_paths = tuple(base / '.runtime/stage2' / name
            for base in (self.native, self.final_root, self.root) for name in reader.locks.NAMES)
        for path in self.lock_paths:
            path.parent.chmod(0o700); path.write_bytes(b''); path.chmod(0o600)
        self.lock_order = self.enterContext(patch.object(reader.locks, 'paths', return_value=self.lock_paths))
        self.acquire = reader.locks.acquire
        self.inherited = self.enterContext(patch.object(reader.locks, 'acquire', wraps=self.acquire))
        self.audit = self.enterContext(patch.object(reader, '_native_audit', side_effect=lambda files: deepcopy(self.data)))
        self.process = self.enterContext(patch('subprocess.run', side_effect=AssertionError('No native calls in local tests')))

    @staticmethod
    def put(root, name, raw):
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(0o600)
        return hashlib.sha256(raw).hexdigest()

    def anchors(self):
        return reader._anchors(self.root, self.old, self.final, 'terminus-2')

    def authenticate(self):
        return reader.authenticate(self.root, self.old, self.final, 'terminus-2')

    def recheck(self, record):
        return reader.recheck(self.root, self.old, self.final, 'terminus-2', record)

    @contextmanager
    def legacy_source_metadata(self, owner=(501, 50), extra_paths=()):
        # The actual native source enclosure is root-owned 0700, while its
        # stage2 tree retains 501:50 ownership. Only uid/gid are synthetic:
        # bytes, descriptors, modes, identities, locks and readers stay real.
        paths = {self.native / 'stage2', *(self.native / 'stage2').rglob('*'), *extra_paths}
        lstat = Path.lstat; fstat = os.fstat
        identities = {(lstat(path).st_dev, lstat(path).st_ino) for path in paths}
        def observed(value):
            if (value.st_dev, value.st_ino) not in identities:
                return value
            fields = {key: getattr(value, key) for key in dir(value) if key.startswith('st_')}
            fields.update(st_uid=owner[0], st_gid=owner[1])
            return NS(**fields)
        with (patch.object(Path, 'lstat', lambda path: observed(lstat(path))),
                patch.object(os, 'fstat', lambda fd: observed(fstat(fd)))):
            yield

    def test_enclosed_legacy_sources_reach_real_reader_without_weakening_generic_guard(self):
        sources = {name: value for name, value in self.anchors()['original'].items()
            if name.startswith('stage2/')}
        with self.legacy_source_metadata():
            with self.assertRaises(ValueError):
                reader.locks.file_identities(self.native, sources)
            value = self.authenticate()
            self.assertFalse(value['paid_launch_ready'])
            self.audit.assert_called_once()
            self.assertEqual(self.recheck(value), value)

    def test_original_source_enclosure_must_be_private_before_collector(self):
        self.native.chmod(0o755)
        with self.assertRaises(ValueError): self.authenticate()
        self.audit.assert_not_called()

    def test_original_source_enclosure_is_rechecked_after_collector(self):
        def weaken(files):
            self.native.chmod(0o755)
            return deepcopy(self.data)
        self.audit.side_effect = weaken
        with self.assertRaises(ValueError): self.authenticate()
        self.audit.assert_called_once()

    def test_under_lock_recheck_refuses_weakened_original_source_enclosure(self):
        value = self.authenticate(); self.audit.reset_mock()
        self.native.chmod(0o755)
        with self.assertRaises(ValueError): self.recheck(value)
        self.audit.assert_not_called()

    def test_under_lock_recheck_refuses_same_byte_original_source_replacement(self):
        value = self.authenticate(); self.audit.reset_mock()
        path = self.native / 'stage2/native_agents.py'; raw = path.read_bytes()
        actual = reader._check
        def replace(*args):
            actual(*args)
            path.rename(path.with_name('retained-source.py'))
            path.write_bytes(raw); path.chmod(0o600)
        with patch.object(reader, '_check', side_effect=replace):
            with self.assertRaisesRegex(ValueError, 'identity changed'): self.recheck(value)
        self.audit.assert_not_called()

    def test_legacy_allowance_does_not_include_private_evidence_or_enclosing_root(self):
        evidence = self.native / '.runtime/stage2/corrected-matrix.json'
        for extra in (evidence, self.native):
            with self.subTest(category='evidence' if extra == evidence else 'root'):
                with self.legacy_source_metadata(extra_paths=(extra,)):
                    with self.assertRaises(ValueError): self.authenticate()
        self.audit.assert_not_called()

    def test_unobserved_source_owner_pair_is_not_allowed(self):
        for owner in ((777, 50), (501, 777), (0, 50)):
            with self.subTest(owner=owner), self.legacy_source_metadata(owner):
                with self.assertRaises(ValueError): self.authenticate()
        self.audit.assert_not_called()

    def test_legacy_source_same_byte_replacement_during_collector_is_refused(self):
        path = self.native / 'stage2/native_agents.py'; raw = path.read_bytes()
        def replace(files):
            moved = path.with_name('retained-original.py'); path.rename(moved)
            path.write_bytes(raw); path.chmod(0o600)
            return deepcopy(self.data)
        self.audit.side_effect = replace
        with self.legacy_source_metadata(), self.assertRaisesRegex(ValueError, 'identity changed'):
            self.authenticate()
        self.audit.assert_called_once()

    def test_legacy_source_writable_ancestry_and_file_are_refused(self):
        for path in (self.native / 'stage2', self.native / 'stage2/native_agents.py'):
            mode = path.stat().st_mode & 0o777
            path.chmod(mode | 0o020)
            with self.subTest(directory=path.is_dir()), self.legacy_source_metadata():
                with self.assertRaises(ValueError): self.authenticate()
            path.chmod(mode)
        self.audit.assert_not_called()

    def test_all_178_results_and_unknown_costs_preserved_without_paid_admission(self):
        value = self.authenticate()
        results = [name for name in value['original_files'] if name.endswith('/result.json')]
        self.assertEqual(len(results), 178)
        self.assertFalse(value['paid_launch_ready'])
        self.assertFalse(value['limitations']['off_server_backup_verified'])
        self.assertFalse(value['limitations']['historical_installed_bytes_attested'])
        self.assertEqual(set(value['current_collector_import_files']),
            {'stage2/' + name for name in reader.CURRENT_COLLECTOR_IMPORTS})
        self.audit.assert_called_once()
        self.assertNotIn('not-returned', json.dumps(value))
        self.assertNotIn('rows', value)

    def test_recheck_rereads_actual_files_without_collector_or_recursive_locks(self):
        value = self.authenticate(); self.audit.reset_mock(); self.inherited.reset_mock()
        self.assertEqual(self.recheck(value), value)
        self.audit.assert_not_called(); self.inherited.assert_not_called()
        name = next(iter(value['support_files']))
        self.put(self.native, name, b'changed')
        with self.assertRaises(ValueError): self.recheck(value)

    def test_active_ancestor_refused_before_locks_and_collector(self):
        self.inactive.side_effect = ValueError('active ancestor')
        with self.assertRaisesRegex(ValueError, 'active'): self.authenticate()
        self.inherited.assert_not_called(); self.audit.assert_not_called()

    def test_drift_during_lock_acquisition_refused_before_collector(self):
        def drift(stack, root, harness):
            lease = self.acquire(stack, root, harness)
            name = next(iter(self.old['sources']))
            self.put(self.native, 'stage2/' + name, b'changed')
            return lease
        self.inherited.side_effect = drift
        with self.assertRaises(ValueError): self.authenticate()
        self.audit.assert_not_called()

    def test_original_source_qualification_producer_and_result_drift_refused(self):
        bound = self.anchors()['original']
        for name in ('stage2/native_agents.py', '.runtime/stage2/corrected-qualification.json',
                '.runtime/stage2/qualification-fixture/synthetic.json',
                next(n for n in bound if n.endswith('/result.json'))):
            path = self.native / name; raw = path.read_bytes(); path.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaises(ValueError): self.authenticate()
            path.write_bytes(raw)
        self.audit.assert_not_called()

    def test_current_extra_imports_are_reread_without_expanding_original_proof(self):
        names = set(self.old['sources'])
        self.authenticate()
        self.assertEqual(set(self.old['sources']), names)
        self.audit.reset_mock()
        for name in reader.CURRENT_COLLECTOR_IMPORTS:
            path = self.native / 'stage2' / name; raw = path.read_bytes()
            path.write_bytes(b'Current helper changed')
            with self.subTest(name=name), self.assertRaises(ValueError): self.authenticate()
            path.write_bytes(raw)
        self.audit.assert_not_called()

    def test_snapshot_csv_launch_and_copied_anchor_byte_changes_refused(self):
        for name in (reader.SNAPSHOT, reader.PUBLIC + '/trials.csv', reader.PUBLIC + '/launch.json',
                '.runtime/stage2/' + policy.BASELINE_FILE, '.runtime/stage2/' + policy.FINAL_FILE):
            path = self.root / name; raw = path.read_bytes(); path.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaises(ValueError): self.authenticate()
            path.write_bytes(raw)
        self.audit.assert_not_called()

    def test_unchanged_original_collector_required_even_when_inventory_is_updated(self):
        self.put(self.root, 'stage2/export_corrected.py', b'new callback')
        with self.assertRaisesRegex(ValueError, 'unchanged original collector'): self.authenticate()
        self.audit.assert_not_called()

    def test_supplied_anchor_must_equal_exact_private_bytes(self):
        with patch.object(reader.policy, 'source_transition'), patch.object(reader.policy, 'anchors',
                return_value=self.final['sources']):
            altered = deepcopy(self.old); altered['unapproved'] = True
            with self.assertRaisesRegex(ValueError, 'actual copied'): reader._anchors(self.root, altered, self.final, 'terminus-2')

    def test_real_csv_crosscheck_rejects_reordered_or_omitted_outcome(self):
        data = deepcopy(self.data); data['rows'][0]['reward'] = 1
        checksum = self.put(self.root, reader.SNAPSHOT, json.dumps(data).encode())
        with patch.object(reader, 'SNAPSHOT_SHA256', checksum), self.assertRaisesRegex(ValueError, '178 original'):
            self.anchors()

    def test_fresh_audit_requires_all_metadata_equal_except_collection_time(self):
        def value(files):
            data = deepcopy(self.data); data['collected_utc'] = '2026-10-01T00:00:00Z'; return data
        self.audit.side_effect = value
        self.authenticate()
        for key, replacement in (('reward', 1), ('agent_seconds', 0), ('known_cost_usd', '99')):
            data = deepcopy(self.data); data['rows'][0][key] = replacement
            self.audit.side_effect = lambda files, data=data: data
            with self.subTest(key=key), self.assertRaises(ValueError): self.authenticate()

    def test_zero_unknown_or_missing_outcomes_are_never_rewritten(self):
        for key, value in (('reward', None), ('unknown_cost_requests', 0), ('total_cost_usd', '0')):
            data = deepcopy(self.data); data['rows'][0][key] = value
            self.audit.side_effect = lambda files, data=data: data
            with self.subTest(key=key), self.assertRaises(ValueError): self.authenticate()
        self.assertIsNone(self.data['rows'][0]['total_cost_usd'])
        self.assertEqual(self.data['rows'][0]['reward'], 0)

    def test_source_and_support_mutation_during_audit_rejected(self):
        for root, name in ((self.root, 'stage2/matched_repeat_original.py'),
                (self.native, '.runtime/stage2/scored-trials/' + self.data['rows'][0]['trial_id'] + '/traces/root.json')):
            path = root / name; raw = path.read_bytes()
            def mutate(files):
                path.write_bytes(b'changed'); return deepcopy(self.data)
            self.audit.side_effect = mutate
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'changed'): self.authenticate()
            path.write_bytes(raw)

    def test_new_support_file_and_provider_stop_during_audit_rejected(self):
        base = '.runtime/stage2/scored-attempts/' + self.data['rows'][0]['trial_id'] + '/'
        for filename in ('0002.outcome.json', 'provider-stop.json'):
            def mutate(files):
                self.put(self.native, base + filename, b'{}'); return deepcopy(self.data)
            self.audit.side_effect = mutate
            with self.subTest(filename=filename), self.assertRaises(ValueError): self.authenticate()
            (self.native / (base + filename)).unlink()

    def test_final_manager_observation_cannot_hide_late_support_changes(self):
        anchors = self.anchors()
        support = reader._support_files(self.native, self.data)
        name = next(iter(support)); calls = []
        def mutate_on_final_observation():
            calls.append(1)
            if len(calls) == 2:
                self.put(self.native, name, b'Late changed bytes')
        self.inactive.side_effect = mutate_on_final_observation
        with self.assertRaisesRegex(ValueError, 'final service check'):
            reader._check(self.root, anchors, support)

    def test_support_inventory_covers_trace_requests_errors_retries_and_lifecycle(self):
        row = self.data['rows'][0]; base = '.runtime/stage2/scored-attempts/' + row['trial_id'] + '/'
        names = [base + suffix for suffix in ('0001.transport-error.json', '0001.retry.json')]
        names.append('.runtime/stage2/retry-lifecycle/' + row['trial_id'] + '.json')
        for name in names: self.put(self.native, name, b'{}')
        support = reader._support_files(self.native, self.data)
        self.assertTrue(set(names) <= set(support))
        self.assertIn(base + '0001.request.json', support)

    def test_missing_timeout_lifecycle_remains_error_not_invented_zero(self):
        data = deepcopy(self.data); data['rows'][0]['agent_error_type'] = 'TimeoutError'
        with self.assertRaises(FileNotFoundError): reader._support_files(self.native, data)

    def test_private_evidence_and_symlinked_support_paths_are_refused(self):
        path = self.root / reader.SNAPSHOT; path.chmod(0o644)
        with self.assertRaises(ValueError): self.authenticate()
        path.chmod(0o600)
        name = self.data['rows'][0]['trial_id']
        traces = self.native / '.runtime/stage2/scored-trials' / name / 'traces'
        moved = traces.with_name('moved'); traces.rename(moved); traces.symlink_to(moved)
        with self.assertRaisesRegex(ValueError, 'metadata directories'): self.authenticate()

    def test_fabricated_or_altered_record_is_not_an_under_lock_recheck(self):
        value = self.authenticate()
        for record in ({'checks': True}, dict(value, paid_launch_ready=True),
                dict(value, audit_sha256='f' * 64), dict(value, support_files={})):
            with self.subTest(record=list(record)), self.assertRaises(ValueError): self.recheck(record)

    def test_final_ancestor_lock_really_prevents_audit_and_releases_afterward(self):
        with ExitStack() as stack:
            hold(stack, self.final_root / '.runtime/stage2', 'gateway.lock')
            with self.assertRaises(BlockingIOError): self.authenticate()
        self.audit.assert_not_called()
        self.authenticate()

    def test_lock_extension_includes_final_and_completed_terminus_for_openhands(self):
        successor = self.root / 'openhands'; (successor / '.runtime/stage2').mkdir(parents=True)
        own = successor / '.runtime/stage2/matrix.lock'
        own.parent.chmod(0o700); own.write_bytes(b''); own.chmod(0o600)
        self.lock_order.return_value = (*self.lock_paths, own)
        with patch.dict(reader.runtime.DEPLOYMENTS, {'openhands': successor}), ExitStack() as stack:
            reader.lock_all(stack, successor, 'openhands')
            for base in (self.root, self.final_root):
                for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                    with self.subTest(base=base, name=name), ExitStack() as contender, self.assertRaises(BlockingIOError):
                        hold(contender, base / '.runtime/stage2', name)

    def test_missing_or_symlinked_ancestor_cannot_create_replacement_lock_tree(self):
        before = sorted(self.root.rglob('*'))
        self.lock_order.return_value = (self.root / 'missing/.runtime/stage2/matrix.lock',)
        with ExitStack() as stack:
            with self.assertRaises((ValueError, FileNotFoundError)): reader.lock_all(stack, self.root, 'terminus-2')
        self.assertEqual(before, sorted(self.root.rglob('*')))
        alias = self.root / 'alias'; alias.symlink_to(self.native)
        self.lock_order.return_value = (alias / '.runtime/stage2/matrix.lock',)
        with ExitStack() as stack:
            with self.assertRaises(ValueError): reader.lock_all(stack, self.root, 'terminus-2')

    def test_replaced_held_lock_after_collector_prevents_success(self):
        def changed(files):
            path = self.lock_paths[0]; path.unlink(); path.write_bytes(b''); path.chmod(0o600)
            return deepcopy(self.data)
        self.audit.side_effect = changed
        with self.assertRaisesRegex(ValueError, 'lock was replaced'): self.authenticate()

    def test_same_byte_original_result_replacement_after_collector_refuses(self):
        name = self.data['rows'][0]['trial_id']
        path = self.native / '.runtime/stage2/scored-trials' / name / 'result.json'
        raw = path.read_bytes()
        def changed(files):
            path.unlink(); path.write_bytes(raw); path.chmod(0o600)
            return deepcopy(self.data)
        self.audit.side_effect = changed
        with self.assertRaisesRegex(ValueError, 'identity changed'): self.authenticate()

    def test_wrong_host_or_deployment_context_refused(self):
        with patch.object(reader.platform, 'system', return_value='Darwin'), self.assertRaises(ValueError): self.authenticate()
        with self.assertRaises(ValueError): reader._context(self.native, 'terminus-2')
        with self.assertRaises(ValueError): reader._context(self.root, 'C0-NC')


class OriginalSourceIdentityTests(unittest.TestCase):
    """Real bytes/descriptors with explicitly synthetic native uid/gid and ACLs."""
    legacy_source_metadata = AuditTests.legacy_source_metadata

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.native = self.root / 'original'; self.native.mkdir(mode=0o700)
        self.name = 'stage2/nested/source.py'
        self.files = {self.name: AuditTests.put(self.native, self.name, b'# retained source\n')}
        self.path = self.native / self.name
        self.enterContext(patch.object(reader.baseline, 'ORIGINAL_ROOT', self.native))
        self.acl = self.enterContext(patch.object(reader.locks.os, 'listxattr', return_value=[], create=True))
        self.enterContext(patch.object(reader.locks, '_parents', side_effect=lambda path:
            tuple(p for p in reversed(path.parents) if p == self.root or p.is_relative_to(self.root))))

    def read(self, files=None):
        return reader._original_file_identities(self.files if files is None else files)

    def test_actual_file_bytes_and_nine_field_identity_are_retained(self):
        before = self.path.read_bytes(), reader.locks.identity(self.path.lstat())
        for legacy in (False, True):
            with self.subTest(legacy=legacy), ExitStack() as stack:
                if legacy: stack.enter_context(self.legacy_source_metadata())
                value = self.read()[self.name]
                self.assertEqual(len(value[0]), 9)
                self.assertEqual(value[0], reader.locks.identity(self.path.lstat()))
                self.assertEqual(value[1][-1][0], str(self.path.parent))
        self.assertEqual((self.path.read_bytes(), reader.locks.identity(self.path.lstat())), before)

    def test_symlinked_file_directory_and_hardlink_are_refused(self):
        original = self.path.with_name('retained.py'); self.path.rename(original)
        self.path.symlink_to(original)
        with self.assertRaises(ValueError): self.read()
        self.path.unlink(); os.link(original, self.path)
        with self.assertRaises(ValueError): self.read()
        self.path.unlink(); original.rename(self.path)
        directory = self.path.parent; moved = directory.with_name('retained-directory')
        directory.rename(moved); directory.symlink_to(moved)
        with self.assertRaises(ValueError): self.read()

    def test_original_root_alias_is_not_a_private_enclosure(self):
        alias = self.root / 'alias'; alias.symlink_to(self.native)
        with patch.object(reader.baseline, 'ORIGINAL_ROOT', alias), self.assertRaises(ValueError): self.read()

    def test_source_acl_and_unsafe_permission_modes_are_refused(self):
        for target in (self.native, self.path.parent, self.path):
            for attribute in ('system.posix_acl_access', 'system.posix_acl_default'):
                self.acl.side_effect = lambda path, **kw: [attribute] if path == target else []
                with self.subTest(acl=attribute, directory=target.is_dir()), self.assertRaises(ValueError):
                    self.read()
        self.acl.side_effect = None
        for mode in (0o664, 0o666, 0o4644, 0o1644):
            self.path.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.read()
        self.path.chmod(0o600)

    def test_unbound_bytes_and_malformed_or_out_of_scope_names_are_refused(self):
        cases = ({}, {self.name: 'f' * 64}, {self.name: 'invalid'},
            {'../source.py': 'f' * 64}, {'/stage2/source.py': 'f' * 64},
            {'stage2/../source.py': 'f' * 64}, {'stage2//source.py': 'f' * 64},
            {'elsewhere/source.py': 'f' * 64})
        for files in cases:
            with self.subTest(names=tuple(files)), self.assertRaises(ValueError): self.read(files)

    def test_same_byte_replacement_before_open_is_refused(self):
        actual = os.open; raw = self.path.read_bytes()
        def replace(path, flags, *args, **kwargs):
            if Path(path) == self.path:
                self.path.rename(self.path.with_name('retained.py'))
                self.path.write_bytes(raw); self.path.chmod(0o600)
            return actual(path, flags, *args, **kwargs)
        with patch.object(reader.os, 'open', side_effect=replace), self.assertRaisesRegex(ValueError, 'before read'):
            self.read()

    def test_changed_open_file_is_refused_after_digest(self):
        actual = hashlib.file_digest
        def mutate(stream, algorithm):
            result = actual(stream, algorithm)
            self.path.write_bytes(b'# changed source\n')
            return result
        with patch.object(reader.hashlib, 'file_digest', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'while reading'): self.read()

    def test_same_byte_parent_replacement_after_digest_is_refused(self):
        actual = hashlib.file_digest; raw = self.path.read_bytes()
        def replace(stream, algorithm):
            result = actual(stream, algorithm)
            parent = self.path.parent; parent.rename(parent.with_name('retained'))
            parent.mkdir(); self.path.write_bytes(raw); self.path.chmod(0o600)
            return result
        with patch.object(reader.hashlib, 'file_digest', side_effect=replace):
            with self.assertRaisesRegex(ValueError, 'ancestry changed'): self.read()

    def test_private_metadata_keeps_the_strict_existing_reader(self):
        name = '.runtime/stage2/result.json'
        files = dict(self.files, **{name: AuditTests.put(self.native, name, b'{}')})
        self.read(files)
        path = self.native / name
        with self.legacy_source_metadata(extra_paths=(path,)), self.assertRaises(ValueError): self.read(files)
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.read(files)


class NativeProgramTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.enterContext(patch.object(reader.baseline, 'ORIGINAL_ROOT', self.root))
        self.enterContext(patch.object(reader.baseline, 'FINAL_ROOT', self.root))
        self.bound = {'stage2/original.py': AuditTests.put(self.root, 'stage2/original.py', b'# Original source')}
        self.enterContext(patch.object(sys, 'prefix', str(self.root / '.venv')))
        self.enterContext(patch.object(sys, 'flags', NS(isolated=True)))
        self.enterContext(patch.object(sys, 'dont_write_bytecode', True))
        self.enterContext(patch.object(sys, 'pycache_prefix', None))
        self.enterContext(patch.object(sys, 'path', list(sys.path)))
        self.hooks = []
        self.enterContext(patch.object(sys, 'addaudithook', side_effect=self.hooks.append))
        self.enterContext(patch.dict(os.environ, reader._native_environment(), clear=True))
        self.state = self.enterContext(patch('subprocess.check_output',
            return_value='ActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n'))
        self.enterContext(patch.object(reader.exporter, 'COLLECT', 'collector_was_called = True\n'))

    def execute(self, namespace=None):
        namespace = {} if namespace is None else namespace
        exec(reader._native_program(self.bound), namespace)
        return namespace

    def test_guard_runs_before_collector_and_rechecks_after(self):
        self.assertTrue(self.execute()['collector_was_called'])
        self.assertEqual(self.state.call_count, 6)
        self.assertEqual(len(self.hooks), 1)
        self.assertFalse((self.root / '.runtime/unused-original-audit-bytecode').exists())

    def test_active_service_prevents_any_collector_project_import(self):
        self.state.return_value = 'ActiveState=active\nSubState=running\nMainPID=12\nExecMainStatus=0\n'
        ns = {}
        with self.assertRaisesRegex(ValueError, 'Inactive'): self.execute(ns)
        self.assertNotIn('collector_was_called', ns)

    def test_stop_or_source_drift_prevents_collector(self):
        marker = self.root / '.runtime/stage2/operator-stop-request.json'
        marker.parent.mkdir(parents=True); marker.write_text('{}')
        ns = {}
        with self.assertRaisesRegex(ValueError, 'stop'): self.execute(ns)
        self.assertNotIn('collector_was_called', ns)
        marker.unlink(); (self.root / 'stage2/original.py').write_text('# Changed')
        with self.assertRaisesRegex(ValueError, 'changed'): self.execute(ns)
        self.assertNotIn('collector_was_called', ns)

    def test_mutation_after_collector_is_not_accepted(self):
        code = "collector_was_called = True\n(_original_root/'stage2/original.py').write_text('# Changed')\n"
        with patch.object(reader.exporter, 'COLLECT', code), self.assertRaisesRegex(ValueError, 'changed'):
            self.execute()

    def test_private_permissions_symlinks_and_existing_cache_are_refused(self):
        path = self.root / '.runtime/stage2/private.json'
        self.bound = {'.runtime/stage2/private.json': AuditTests.put(self.root, '.runtime/stage2/private.json', b'{}')}
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'Private'): self.execute()
        path.chmod(0o600); path.rename(path.with_name('real.json')); path.symlink_to(path.with_name('real.json'))
        with self.assertRaisesRegex(ValueError, 'Symlinked'): self.execute()
        path.unlink(); path.write_text('{}'); path.chmod(0o600)
        (self.root / '.runtime/unused-original-audit-bytecode').mkdir()
        with self.assertRaisesRegex(ValueError, 'cache prefix'): self.execute()

    def test_nonisolated_or_wrong_interpreter_and_unsafe_bindings_refused(self):
        with patch.object(sys, 'prefix', '/another/.venv'), self.assertRaises(ValueError): self.execute()
        with patch.object(sys, 'flags', NS(isolated=False)), self.assertRaises(ValueError): self.execute()
        for files in ({}, {'../other': '1' * 64}, {'source.py': 'not-hash'}):
            with self.subTest(files=files), self.assertRaises(ValueError): reader._native_program(files)

    def test_symlinked_original_virtualenv_is_not_its_own_interpreter(self):
        target = self.root / 'other-venv'; target.mkdir()
        (self.root / '.venv').symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'original isolated interpreter'): self.execute()

    def test_unexpected_environment_is_not_cleared_or_accepted(self):
        ns = {}
        with patch.dict(os.environ, {'UNEXPECTED_VALUE': 'private'}), self.assertRaisesRegex(ValueError, 'environment'):
            self.execute(ns)
        self.assertNotIn('collector_was_called', ns)
        self.state.assert_not_called()

    def test_credential_read_refusal_latches_even_if_library_catches_it(self):
        ns = self.execute()
        for filename in ('.env', '.env.production', '.jwt_secret', 'id_ed25519', 'id_rsa'):
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, 'credential'):
                ns['_original_event']('open', (str(self.root / filename), 'r', os.O_RDONLY))
        self.assertTrue(ns['_original_violation'])
        with self.assertRaisesRegex(ValueError, 'environment'): ns['_original_check']()

    def test_import_socket_probe_is_denied_before_creation_without_latching(self):
        ns = self.execute(); ns['_original_importing'] = True
        with self.assertRaises(RuntimeError): ns['_original_event']('socket.__new__', ())
        self.assertEqual(ns['_original_socket_refusals'], 1)
        self.assertFalse(ns['_original_violation'])
        ns['_original_importing'] = False
        ns['_original_environment_check']()
        with self.assertRaises(ValueError): ns['_original_event']('socket.__new__', ())
        self.assertTrue(ns['_original_violation'])

    def test_environment_mutation_and_write_network_process_refusals_latch(self):
        cases = (('os.putenv', (b'UNEXPECTED', b'not-retained')),
            ('os.unsetenv', (b'LANG',)),
            ('open', (str(self.root / 'new-output'), 'w', os.O_WRONLY | os.O_CREAT)),
            ('socket.connect', (None, ('192.0.2.1', 1))),
            ('subprocess.Popen', ('docker', ['docker', 'run', 'unapproved'], None, None)))
        for event, args in cases:
            ns = self.execute()
            with self.subTest(event=event), self.assertRaises(ValueError): ns['_original_event'](event, args)
            self.assertTrue(ns['_original_violation'])
            with self.assertRaises(ValueError): ns['_original_environment_check']()

    def test_read_only_collector_commands_are_forbidden_during_import(self):
        ns = self.execute()
        args = ('docker', ['docker', 'ps', '-q', '--filter', 'name=uts-scored-'], None, None)
        ns['_original_event']('subprocess.Popen', args)
        ns['_original_importing'] = True
        with self.assertRaises(ValueError): ns['_original_event']('subprocess.Popen', args)
        self.assertTrue(ns['_original_violation'])

    def test_loaded_project_source_must_belong_to_exact_original_bindings(self):
        ns = self.execute()
        for name, path in (('original', self.root / 'elsewhere/original.py'),
                ('unbound', self.root / 'stage2/unbound.py')):
            with patch.dict(sys.modules, {name: NS(__file__=str(path))}), self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'collector'): ns['_original_loaded']()


class NativeProcessTests(unittest.TestCase):
    def isolated_fixture(self, module_source):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / '.venv').mkdir()
            digest = AuditTests.put(root, 'stage2/original.py', module_source)
            with (patch.object(reader.baseline, 'ORIGINAL_ROOT', root),
                    patch.object(reader.baseline, 'FINAL_ROOT', root),
                    patch.object(reader.exporter, 'COLLECT', 'import original\nprint("synthetic-complete")\n')):
                environment = reader._native_environment()
                # This Mac runtime adds its own CoreFoundation encoding at
                # startup. Bind that actual local fixture value explicitly;
                # the production Linux environment remains exact and unchanged.
                if sys.platform == 'darwin' and '__CF_USER_TEXT_ENCODING' in os.environ:
                    environment['__CF_USER_TEXT_ENCODING'] = os.environ['__CF_USER_TEXT_ENCODING']
                with patch.object(reader, '_native_environment', return_value=environment):
                    program = reader._native_program({'stage2/original.py': digest})
            # Only the historical host/interpreter identity observations are
            # synthetic. Imports and the audit hook execute in a real isolated
            # credential-free child; no native collector or daemon is called.
            prefix = ('import sys,subprocess\nsys.prefix=' + repr(str(root / '.venv')) + '\n'
                'subprocess.check_output=lambda *a,**k: '
                + repr('ActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n') + '\n')
            process = subprocess.run([sys.executable, '-I', '-B', '-'], input=prefix + program,
                text=True, capture_output=True, env=environment, cwd=root, timeout=30)
            self.assertFalse((root / 'blocked-output').exists())
            return process

    def test_actual_isolated_child_imports_bound_source_without_effects(self):
        process = self.isolated_fixture(b'import json\nvalue=json.loads("{}")\n')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, 'synthetic-complete\n')

    def test_actual_child_caught_credential_read_still_prevents_collector(self):
        source = b'try:\n open(".env","r")\nexcept ValueError:\n pass\n'
        process = self.isolated_fixture(source)
        self.assertNotEqual(process.returncode, 0)
        self.assertNotIn('synthetic-complete', process.stdout)

    def test_actual_child_caught_socket_probe_creates_no_socket(self):
        source = (b'import socket\ntry:\n socket.socket()\n'
            b'except RuntimeError:\n pass\nelse:\n raise AssertionError("Socket unexpectedly created")\n')
        process = self.isolated_fixture(source)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_actual_child_caught_write_still_prevents_collector(self):
        source = b'try:\n open("blocked-output","w")\nexcept ValueError:\n pass\n'
        process = self.isolated_fixture(source)
        self.assertNotEqual(process.returncode, 0)
        self.assertNotIn('synthetic-complete', process.stdout)

    def test_original_interpreter_stdin_credential_free_environment_and_metadata_only(self):
        with (patch('subprocess.run', return_value=NS(returncode=0, stdout='{"rows": []}')) as run,
                patch.dict(os.environ, {'OPENROUTER_API_KEY': 'not-forwarded'})):
            data = reader._native_audit({'stage2/original.py': '1' * 64})
        self.assertEqual(data, {'rows': []})
        args, kw = run.call_args
        self.assertEqual(args[0], [str(reader.baseline.ORIGINAL_ROOT / '.venv/bin/python'), '-I', '-B', '-'])
        self.assertEqual(kw['cwd'], reader.baseline.ORIGINAL_ROOT)
        self.assertNotIn('OPENROUTER_API_KEY', kw['env'])
        self.assertEqual(kw['env'], reader._native_environment())
        self.assertEqual(kw['env']['PYTHON_DOTENV_DISABLED'], '1')
        self.assertEqual(kw['env']['LITELLM_MODE'], 'PRODUCTION')
        self.assertEqual(kw['env']['DOCKER_HOST'], 'unix:///var/run/docker.sock')
        self.assertEqual(kw['env']['DOCKER_CONFIG'], '/dev/null')
        self.assertIn(reader.exporter.COLLECT, kw['input'])

    def test_process_failures_and_malformed_metadata_are_sanitised(self):
        for value in (NS(returncode=1, stdout='', stderr='private failure'),
                NS(returncode=0, stdout='private failure')):
            with patch('subprocess.run', return_value=value), self.assertRaises(ValueError) as caught:
                reader._native_audit({'source.py': '1' * 64})
            self.assertNotIn('private failure', str(caught.exception))
        for error in (OSError('private failure'), subprocess.TimeoutExpired('private', 1)):
            with patch('subprocess.run', side_effect=error), self.assertRaises(ValueError) as caught:
                reader._native_audit({'source.py': '1' * 64})
            self.assertNotIn('private failure', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
