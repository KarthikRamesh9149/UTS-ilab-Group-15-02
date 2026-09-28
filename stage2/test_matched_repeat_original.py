"""Mocked original native collector with real files/locks, not paid evidence."""
from contextlib import ExitStack
from copy import deepcopy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
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
        self.native = self.root / 'original'; self.native.mkdir()
        self.final_root = self.root / 'final'; (self.final_root / '.runtime/stage2').mkdir(parents=True)
        self.old = self.f.original; self.final = self.f.final
        for name in self.old['sources']:
            raw = ((b'Original ' + name.encode()) if name in policy.INHERITED_BASELINE_DELTAS
                else (self.root / 'stage2' / name).read_bytes())
            self.old['sources'][name] = self.put(self.native, 'stage2/' + name, raw)
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
                (reader.exporter, 'OUTPUT', self.root / reader.PUBLIC), (reader, 'LOCK_ANCESTORS', (self.native,))):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.dict(reader.runtime.DEPLOYMENTS, {'terminus-2': self.root}))
        self.enterContext(patch.object(reader.platform, 'system', return_value='Linux'))
        self.loaded = self.enterContext(patch.object(reader.runtime, 'loaded_sources'))
        self.inactive = self.enterContext(patch.object(reader.baseline, 'inactive_ancestors'))
        self.inherited = self.enterContext(patch.object(reader, 'inherited_locks', side_effect=lambda stack, root:
            hold(stack, root / '.runtime/stage2', 'matrix.lock')))
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

    def test_all_178_results_and_unknown_costs_preserved_without_paid_admission(self):
        value = self.authenticate()
        results = [name for name in value['original_files'] if name.endswith('/result.json')]
        self.assertEqual(len(results), 178)
        self.assertFalse(value['paid_launch_ready'])
        self.assertFalse(value['limitations']['off_server_backup_verified'])
        self.assertFalse(value['limitations']['historical_installed_bytes_attested'])
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
        def drift(stack, root):
            name = next(iter(self.old['sources']))
            self.put(self.native, 'stage2/' + name, b'changed')
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
        with patch.dict(reader.runtime.DEPLOYMENTS, {'openhands': successor}), ExitStack() as stack:
            reader.lock_all(stack, successor, 'openhands')
            for base in (self.root, self.final_root):
                for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                    with self.subTest(base=base, name=name), ExitStack() as contender, self.assertRaises(BlockingIOError):
                        hold(contender, base / '.runtime/stage2', name)

    def test_missing_or_symlinked_ancestor_cannot_create_replacement_lock_tree(self):
        before = sorted(self.root.rglob('*'))
        with patch.object(reader, 'LOCK_ANCESTORS', (self.root / 'missing',)), ExitStack() as stack:
            with self.assertRaises(ValueError): reader.lock_all(stack, self.root, 'terminus-2')
        self.assertEqual(before, sorted(self.root.rglob('*')))
        alias = self.root / 'alias'; alias.symlink_to(self.native)
        with patch.object(reader, 'LOCK_ANCESTORS', (alias,)), ExitStack() as stack:
            with self.assertRaises(ValueError): reader.lock_all(stack, self.root, 'terminus-2')

    def test_wrong_host_or_deployment_context_refused(self):
        with patch.object(reader.platform, 'system', return_value='Darwin'), self.assertRaises(ValueError): self.authenticate()
        with self.assertRaises(ValueError): reader._context(self.native, 'terminus-2')
        with self.assertRaises(ValueError): reader._context(self.root, 'C0-NC')


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
        self.state = self.enterContext(patch('subprocess.check_output',
            return_value='ActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n'))
        self.enterContext(patch.object(reader.exporter, 'COLLECT', 'collector_was_called = True\n'))

    def execute(self, namespace=None):
        namespace = {} if namespace is None else namespace
        exec(reader._native_program(self.bound), namespace)
        return namespace

    def test_guard_runs_before_collector_and_rechecks_after(self):
        self.assertTrue(self.execute()['collector_was_called'])
        self.assertEqual(self.state.call_count, 4)
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


class NativeProcessTests(unittest.TestCase):
    def test_original_interpreter_stdin_credential_free_environment_and_metadata_only(self):
        with (patch('subprocess.run', return_value=NS(returncode=0, stdout='{"rows": []}')) as run,
                patch.dict(os.environ, {'OPENROUTER_API_KEY': 'not-forwarded'})):
            data = reader._native_audit({'stage2/original.py': '1' * 64})
        self.assertEqual(data, {'rows': []})
        args, kw = run.call_args
        self.assertEqual(args[0], [str(reader.baseline.ORIGINAL_ROOT / '.venv/bin/python'), '-I', '-B', '-'])
        self.assertEqual(kw['cwd'], reader.baseline.ORIGINAL_ROOT)
        self.assertNotIn('OPENROUTER_API_KEY', kw['env'])
        self.assertEqual(set(kw['env']), {'PATH', 'LANG', 'LITELLM_LOCAL_MODEL_COST_MAP', 'DO_NOT_TRACK'})
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
