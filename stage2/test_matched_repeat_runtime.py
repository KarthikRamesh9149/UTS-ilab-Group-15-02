"""Real local files with fake host/Docker responses, not native qualification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import matched_repeat_policy as policy
import matched_repeat_runtime as runtime
from test_matched_repeat_policy import Fixture, predecessors, qualification


class TreeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.f = Fixture(self, self.root)
        names = set(self.f.final['sources']) | {'input_manifest.json', 'dataset_provenance.json'}
        actual = {name: self.write('stage2/' + name, ('Synthetic file ' + name).encode())
            for name in names | policy.REQUIRED_SOURCE_FILES}
        actual['input_manifest.json'] = self.write('stage2/input_manifest.json',
            (Path(__file__).parent / 'input_manifest.json').read_bytes())
        self.f.final['sources'] = {name: actual[name] for name in names}
        self.f.original['sources'] = {name: ('1' * 64 if name in policy.INHERITED_BASELINE_DELTAS
            else actual[name]) for name in self.f.original['sources']}
        self.f.final['sources_sha256'] = policy.fingerprint(self.f.final['sources'])
        for key, value in (('ORIGINAL_QUALIFICATION_SHA256', policy.fingerprint(self.f.original)),
                ('CUSTOM_FINAL_QUALIFICATION_SHA256', policy.fingerprint(self.f.final)),
                ('CUSTOM_FINAL_SOURCES_SHA256', self.f.final['sources_sha256'])):
            self.enterContext(patch.object(policy, key, value))
        self.f.predecessor = predecessors(self.f.manifest, 'terminus-2')
        self.f.proof = qualification(self.f.original, self.f.final, self.f.predecessor,
            self.f.manifest, 'terminus-2')
        self.f.proof.update(sources=actual, sources_sha256=policy.fingerprint(actual),
            source_transition=policy.source_transition(self.f.original, self.f.final, actual))
        self.actual = actual

    def write(self, relative, raw):
        path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()


class SourceTests(TreeTests):
    def read(self):
        return runtime.sources(self.root, self.f.original, self.f.final)

    def test_real_source_files_and_every_native_regression_module_are_bound(self):
        self.assertEqual(self.read(), self.actual)
        self.assertTrue(policy.REQUIRED_SOURCE_FILES <= self.actual.keys())
        self.assertTrue({name + '.py' for name in policy.TEST_MODULES} <= self.actual.keys())

    def test_original_factories_locks_retry_and_model_cannot_change(self):
        for name in policy.BASELINE_BEHAVIOUR_FILES:
            path = self.root / 'stage2' / name; raw = path.read_bytes(); path.write_bytes(b'Changed')
            with self.subTest(name=name), self.assertRaises(ValueError): self.read()
            path.write_bytes(raw)

    def test_only_explicit_orchestration_deltas_are_allowed(self):
        for name in policy.ORCHESTRATION_FILES:
            self.write('stage2/' + name, b'Explicit repeat admission or trace delta')
        bound = self.read()
        transition = policy.source_transition(self.f.original, self.f.final, bound)
        self.assertEqual(set(transition['orchestration_changes']), set(policy.ORCHESTRATION_FILES))
        self.write('stage2/no_cutoff_final_policy.py', b'Changing an older policy is forbidden')
        with self.assertRaises(ValueError): self.read()

    def test_missing_symlinked_file_and_symlinked_source_directory_refused(self):
        path = self.root / 'stage2/matched_repeat_runtime.py'; raw = path.read_bytes(); path.unlink()
        with self.assertRaises(ValueError): self.read()
        path.symlink_to(self.root / 'stage2/matched_repeat_policy.py')
        with self.assertRaises(ValueError): self.read()
        path.unlink(); path.write_bytes(raw)
        stage = self.root / 'stage2'; stage.rename(self.root / 'moved-stage')
        stage.symlink_to(self.root / 'moved-stage', target_is_directory=True)
        with self.assertRaises(ValueError): self.read()

    def test_omitted_dataset_binding_is_not_an_acceptable_source_map(self):
        altered = dict(self.actual); altered.pop('dataset_provenance.json')
        with patch.object(policy, 'anchors', return_value=altered), patch.object(policy, 'source_transition'):
            with self.assertRaises(ValueError): self.read()

    def test_wrong_original_or_final_anchor_is_refused(self):
        for old, final in (({}, self.f.final), (self.f.original, {})):
            with self.assertRaises(ValueError): runtime.sources(self.root, old, final)

    def test_loaded_sources_require_own_interpreter_and_current_tree(self):
        stage = self.root / 'stage2'
        module = SimpleNamespace(__file__=str(stage / 'native_agents.py'))
        with patch.object(runtime, '__file__', str(stage / 'matched_repeat_runtime.py')), \
                patch.object(sys, 'prefix', str(self.root / '.venv')), \
                patch.dict(sys.modules, {'synthetic_module': module}, clear=True):
            runtime.loaded_sources(self.root, self.actual)
            module.__file__ = '/original/stage2/native_agents.py'
            with self.assertRaises(ValueError): runtime.loaded_sources(self.root, self.actual)
        with self.assertRaises(ValueError): runtime.loaded_sources(self.root, self.actual)

    def test_symlinked_loaded_module_or_virtualenv_is_refused(self):
        stage = self.root / 'stage2'; alias = self.root / 'alias'; alias.mkdir()
        path = alias / 'native_agents.py'; path.symlink_to(stage / path.name)
        module = SimpleNamespace(__file__=str(path))
        with patch.object(runtime, '__file__', str(stage / 'matched_repeat_runtime.py')), \
                patch.object(sys, 'prefix', str(self.root / '.venv')), \
                patch.dict(sys.modules, {'synthetic_module': module}, clear=True):
            with self.assertRaises(ValueError): runtime.loaded_sources(self.root, self.actual)
            module.__file__ = str(stage / path.name)
            (self.root / 'other-venv').mkdir(); (self.root / '.venv').symlink_to(self.root / 'other-venv')
            with self.assertRaises(ValueError): runtime.loaded_sources(self.root, self.actual)


class RuntimeTests(TreeTests):
    def setUp(self):
        super().setUp()
        self.write('.runtime/stage2/python-runtime.tar.gz', b'Synthetic runtime archive')
        self.enterContext(patch.dict(runtime.DEPLOYMENTS, {'terminus-2': self.root.resolve()}))
        self.enterContext(patch.object(runtime, 'loaded_sources'))
        self.packages = self.enterContext(patch.object(runtime, 'dependencies',
            return_value=deepcopy(self.f.final['dependencies'])))
        self.bundle = self.enterContext(patch.object(runtime, 'runtime_bundle', return_value=SimpleNamespace(
            validate=lambda: deepcopy(self.f.final['python_runtime']))))
        self.host = self.enterContext(patch.object(runtime.host_environment, 'snapshot',
            return_value=deepcopy(self.f.final['host_environment'])))
        self.dataset = self.enterContext(patch.object(runtime, '_dataset', return_value=(
            self.root / '.cache/tasks', {'fixture-file': '1' * 64})))
        self.tasks = {task: dict(docker_image='fixture:' + task, agent_timeout_seconds=12000.0,
            cpus=1, memory_mb=2048, storage_mb=10240, gpus=0) for task in self.f.manifest['all_task_ids']}
        self.configs = self.enterContext(patch.object(runtime, '_task_limits',
            side_effect=lambda *args: deepcopy(self.tasks)))
        self.baseline_data = dict(images=dict.fromkeys(self.tasks, 'sha256:' + '1' * 64),
            agent_deadlines=dict.fromkeys(self.tasks, 12000.0),
            results_sha256=dict.fromkeys(['original-' + str(i) for i in range(178)], '2' * 64))
        self.baselines = self.enterContext(patch.object(runtime, '_baseline_images', return_value=self.baseline_data))
        self.images = self.enterContext(patch.object(runtime, '_images', side_effect=lambda refs: {
            ref: dict(id=ref if ref.startswith('sha256:') else 'sha256:' + '1' * 64,
                os='linux', architecture='amd64') for ref in refs}))
        # Neither identity nor recheck may recursively invoke an audit/SSH or
        # start containers. All legitimate host/Docker reads are mocked above.
        self.process = self.enterContext(patch('subprocess.run', side_effect=AssertionError('Unexpected subprocess')))

    def read(self, harness='terminus-2'):
        return runtime.inspect(self.root, self.f.original, self.f.final, harness)

    def verify(self, recorded):
        return runtime.verify_current(self.root, self.f.original, self.f.final,
            self.f.predecessor, self.f.proof, recorded)

    def test_exact_schedule_all_task_limits_and_178_baseline_bindings_without_writes(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        record = self.read()
        cells = policy.cells(self.f.manifest, 'terminus-2')
        self.assertEqual(record['cells'], cells)
        self.assertEqual(list(record['task_inventory']), [c['task_id'] for c in cells])
        self.assertEqual(len(record['task_inventory']), 89)
        self.assertTrue(all(v['agent_timeout_seconds'] == 12000.0 for v in record['task_inventory'].values()))
        self.assertEqual(len(record['baseline_results_sha256']), 178)
        self.assertEqual(record['sources'], self.actual)
        self.assertEqual(record['source_transition']['orchestration_changes'], {})
        self.assertEqual(record['original_qualification_sha256'], policy.fingerprint(self.f.original))
        self.assertEqual(record['custom_final_qualification_sha256'], policy.fingerprint(self.f.final))
        self.assertEqual(record['kind'], runtime.KIND); self.assertFalse(record['paid_launch_ready'])
        self.assertNotIn('baseline_behaviour_authentication_sha256', record)
        self.assertNotIn('predecessor_authentication_sha256', record)
        self.assertNotIn('passes', record)
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob('*')), before)
        self.process.assert_not_called()

    def test_other_baseline_identity_is_distinct_and_not_successor_admission(self):
        first = self.read()
        with patch.dict(runtime.DEPLOYMENTS, {'openhands': self.root.resolve()}):
            second = self.read('openhands')
        self.assertEqual([c['task_id'] for c in first['cells']], [c['task_id'] for c in second['cells']])
        self.assertFalse({c['trial_id'] for c in first['cells']} & {c['trial_id'] for c in second['cells']})
        self.assertFalse(second['paid_launch_ready'])
        self.assertEqual(second['harness'], 'openhands')

    def test_previous_different_and_other_harness_roots_refused(self):
        with patch.dict(runtime.DEPLOYMENTS, {'terminus-2': Path('/separate-new-repeat')}):
            with self.assertRaises(ValueError): self.read()
        with self.assertRaises(ValueError): self.read('openhands')
        with self.assertRaises(ValueError): self.read('C0-NC')

    def test_current_dependency_versions_must_match_final_anchor(self):
        self.packages.return_value['python'] = '3.12.999'
        with self.assertRaises(ValueError): self.read()

    def test_host_must_match_whole_native_final_identity_not_only_execution_flag(self):
        for value in ({}, {'execution_mode': 'native_linux_x86_64', 'docker_context': 'different'}):
            self.host.return_value = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.read()

    def test_archive_identity_must_match_and_real_file_must_exist(self):
        self.bundle.return_value = SimpleNamespace(validate=lambda: {'sha256': '0' * 64})
        with self.assertRaises(ValueError): self.read()
        self.bundle.return_value = SimpleNamespace(validate=lambda: dict(self.f.final['python_runtime'], files=1))
        with self.assertRaises(ValueError): self.read()
        self.bundle.return_value = SimpleNamespace(validate=lambda: deepcopy(self.f.final['python_runtime']))
        (self.f.runtime / 'python-runtime.tar.gz').unlink()
        with self.assertRaises(ValueError): self.read()

    def test_changed_manifest_and_canonical_dataset_refused(self):
        path = self.root / 'stage2/input_manifest.json'; before = path.read_bytes(); path.write_bytes(before + b' ')
        with self.assertRaises(ValueError): self.read()
        path.write_bytes(before); self.dataset.side_effect = ValueError('Changed canonical bytes')
        with self.assertRaises(ValueError): self.read()

    def test_outside_development_image_and_deadline_checked(self):
        task = self.f.manifest['outside_development_ids'][-1]
        self.baseline_data['images'][task] = 'sha256:' + '9' * 64
        with self.assertRaises(ValueError): self.read()
        self.baseline_data['images'][task] = 'sha256:' + '1' * 64
        self.baseline_data['agent_deadlines'][task] = 60.0
        with self.assertRaises(ValueError): self.read()

    def test_empty_task_image_response_and_missing_baseline_evidence_refused(self):
        self.images.side_effect = None; self.images.return_value = {}
        with self.assertRaises(ValueError): self.read()
        self.baselines.side_effect = ValueError('Missing original metadata')
        with self.assertRaises(ValueError): self.read()

    def test_sources_rechecked_after_metadata_reads(self):
        self.configs.side_effect = lambda *args: (self.write('stage2/matched_repeat_runtime.py', b'Changed'),
            deepcopy(self.tasks))[1]
        with self.assertRaises(ValueError): self.read()

    def test_real_qualification_identity_producers_and_pinned_images_required_by_recheck(self):
        record = self.read(); self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        with patch.object(runtime, 'verify_native_files') as producers:
            self.assertEqual(self.verify(record), record)
            producers.assert_called_once_with(self.root, self.f.original, self.f.final,
                self.f.predecessor, self.f.manifest, self.f.proof)
        self.assertEqual(self.images.call_args.args[0], [self.f.proof['gateway_image'], self.f.proof['guard_image']])
        self.process.assert_not_called()

    def test_missing_producer_cannot_be_replaced_by_true_flags(self):
        record = self.read(); self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        with self.assertRaises(ValueError): self.verify(record)

    def test_self_granted_changed_harness_or_stale_identity_refused(self):
        record = self.read()
        with self.assertRaises(ValueError): self.verify(record)
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        for values in ({'paid_launch_ready': True}, {'harness': 'openhands'}, {'sources': {}}):
            with self.subTest(values=values), self.assertRaises(ValueError): self.verify(dict(record, **values))

    def test_self_consistent_saved_snapshot_does_not_replace_current_reads(self):
        recorded = dict(self.read(), dataset_files_sha256='f' * 64)
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(recorded)
        with patch.object(runtime, 'verify_native_files'):
            with self.assertRaises(ValueError): self.verify(recorded)

    def test_missing_or_wrong_pinned_gateway_and_guard_image_refused(self):
        record = self.read(); self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        refs = [self.f.proof['gateway_image'], self.f.proof['guard_image']]
        for response in ({}, {refs[0]: {'id': refs[0]}}, dict.fromkeys(refs, {'id': 'sha256:' + '0' * 64})):
            with patch.object(runtime, 'verify_native_files'), patch.object(runtime, 'inspect', return_value=record), \
                    patch.object(runtime, '_images', return_value=response):
                with self.subTest(response=response), self.assertRaises(ValueError): self.verify(record)


class ProducerTests(TreeTests):
    def setUp(self):
        super().setUp()
        self.proof = self.f.proof
        self.producer(self.proof['regression_path'] + '/regression.json', self.proof['offline'])
        self.producer(self.proof['regression_path'] + '/regression.txt', {'output': 'Synthetic local fixture only'})
        for case in self.proof['synthetic']:
            self.producer(case['runtime_path'] + '/evidence.json', case)
            cancelled = case['mode'] == 'cancel_setup'
            trial_id = 'synthetic-matched-repeat-terminus-2-' + case['mode']
            result = dict(stage='final', harness='terminus-2', matched_repeat_experiment=policy.EXPERIMENT,
                trial_id=trial_id, gateway_image_id=self.proof['gateway_image'],
                model_protocol_sha256=policy.MODEL_SHA256,
                status='interrupted' if cancelled else 'verified', model_revoked=True,
                containers_removed=True, networks_removed=True, volumes_removed=True,
                verifier_result=None if cancelled else dict(rewards=dict(reward=1)))
            self.producer(case['runtime_path'] + '/.runtime/stage2/scored-trials/' + trial_id + '/result.json', result)

    def producer(self, name, value):
        self.proof['evidence_files'][name] = self.write(name, json.dumps(value).encode())

    def verify(self):
        runtime.verify_native_files(self.root, self.f.original, self.f.final,
            self.f.predecessor, self.f.manifest, self.proof)

    def result_path(self, mode='tools'):
        case = next(c for c in self.proof['synthetic'] if c['mode'] == mode)
        return case['runtime_path'] + '/.runtime/stage2/scored-trials/synthetic-matched-repeat-terminus-2-' + mode + '/result.json'

    def test_eight_files_and_actual_result_fields_read(self):
        self.assertEqual(len(self.proof['evidence_files']), 8)
        self.verify()

    def test_all_files_required_not_just_producer_flags(self):
        for relative in self.proof['evidence_files']:
            path = self.root / relative; raw = path.read_bytes(); path.unlink()
            with self.subTest(relative=relative), self.assertRaises(ValueError): self.verify()
            path.write_bytes(raw)

    def test_missing_or_symlinked_producer_refused_even_if_hash_matches(self):
        relative = self.proof['synthetic'][0]['runtime_path'] + '/evidence.json'
        path = self.root / relative; saved = path.with_suffix('.saved'); path.rename(saved); path.symlink_to(saved)
        with self.assertRaises(ValueError): self.verify()

    def test_mutated_regression_text_or_reports_refused(self):
        for relative in self.proof['evidence_files']:
            path = self.root / relative; raw = path.read_bytes(); path.write_bytes(raw + b' ')
            with self.subTest(relative=relative), self.assertRaises(ValueError): self.verify()
            path.write_bytes(raw)

    def test_report_contents_must_equal_proof_even_with_updated_file_hash(self):
        name = self.proof['regression_path'] + '/regression.json'
        self.producer(name, dict(self.proof['offline'], tests=1))
        with self.assertRaises(ValueError): self.verify()
        self.producer(name, self.proof['offline'])
        case = self.proof['synthetic'][0]
        self.producer(case['runtime_path'] + '/evidence.json', dict(case, live_api_calls=1))
        with self.assertRaises(ValueError): self.verify()

    def test_exact_result_identity_verifier_revocation_and_cleanup_not_hashes_alone(self):
        name = self.result_path(); baseline = json.loads((self.root / name).read_text())
        for values in ({'trial_id': 'different'}, {'stage': 'development'}, {'harness': 'openhands'},
                {'matched_repeat_experiment': policy.CUSTOM_FINAL_EXPERIMENT},
                {'model_protocol_sha256': '0' * 64}, {'gateway_image_id': 'sha256:' + '0' * 64},
                {'status': 'interrupted'}, {'model_revoked': False}, {'containers_removed': False},
                {'networks_removed': False}, {'volumes_removed': False}, {'verifier_result': None},
                {'verifier_result': {'rewards': {'reward': True}}},
                {'verifier_result': {'rewards': {'reward': 0.0}}}):
            self.producer(name, dict(baseline, **values))
            with self.subTest(values=values), self.assertRaises(ValueError): self.verify()

    def test_cancelled_setup_must_remain_interrupted_without_verifier_reward(self):
        name = self.result_path('cancel_setup'); baseline = json.loads((self.root / name).read_text())
        for values in ({'status': 'verified'}, {'verifier_result': {'rewards': {'reward': 1.0}}}):
            self.producer(name, dict(baseline, **values))
            with self.subTest(values=values), self.assertRaises(ValueError): self.verify()

    def test_self_consistent_but_incomplete_qualification_cannot_skip_a_case(self):
        self.proof['synthetic'].pop()
        with self.assertRaises(ValueError): self.verify()


if __name__ == '__main__': unittest.main()
