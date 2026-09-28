"""Real local file checks with mocked host/Docker identity, not qualification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import no_cutoff_final_policy as policy
import no_cutoff_final_runtime as runtime
from test_no_cutoff_final_policy import Fixture


class SourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        names = policy.REQUIRED_SOURCE_FILES | {'scored_trial.py', 'local_trace.py',
            'no_cutoff_custom_agent.py', 'no_cutoff_capture_backend.py', 'deadline_final_selection.py'}
        self.actual = {}
        for name in names:
            path = self.root / 'stage2' / name; path.parent.mkdir(parents=True, exist_ok=True)
            raw = ('Synthetic ' + name).encode(); path.write_bytes(raw)
            self.actual[name] = hashlib.sha256(raw).hexdigest()
        self.document = dict(original_candidate=dict(selection_logic_sources={
            'deadline_final_selection.py': self.actual['deadline_final_selection.py']}),
            freeze_logic_sources={'no_cutoff_evidence_freeze.py': self.actual['no_cutoff_evidence_freeze.py']})
        self.execution = dict(sources={name: digest for name, digest in self.actual.items()
            if name not in policy.REQUIRED_SOURCE_FILES})
        self.enterContext(patch.object(policy, 'candidate_execution', return_value=self.execution))

    def test_actual_sources_include_new_admission_and_unchanged_measured_code(self):
        bound = runtime.sources(self.root, self.document)
        self.assertEqual(bound, self.actual)
        self.assertTrue(policy.REQUIRED_SOURCE_FILES <= bound.keys())

    def test_only_two_explicit_orchestration_changes_are_allowed(self):
        for name in ('scored_trial.py', 'local_trace.py'):
            (self.root / 'stage2' / name).write_text('# New orchestration admission')
        changed = policy.source_transition(self.document, runtime.sources(self.root, self.document))
        self.assertEqual(set(changed), {'scored_trial.py', 'local_trace.py'})
        (self.root / 'stage2/no_cutoff_custom_agent.py').write_text('# Unmeasured change')
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)

    def test_both_original_and_revised_freeze_logic_are_immutable(self):
        for name in ('deadline_final_selection.py', 'no_cutoff_evidence_freeze.py'):
            path = self.root / 'stage2' / name; before = path.read_bytes(); path.write_bytes(b'Changed')
            with self.subTest(name=name), self.assertRaises(ValueError): runtime.sources(self.root, self.document)
            path.write_bytes(before)

    def test_missing_or_symlinked_current_source_is_refused(self):
        path = self.root / 'stage2/no_cutoff_final_gateway.py'; path.unlink()
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)
        path.symlink_to(self.root / 'stage2/no_cutoff_final_policy.py')
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)

    def test_loaded_module_and_interpreter_must_be_from_the_final_deployment(self):
        stage = self.root / 'stage2'
        module = SimpleNamespace(__file__=str(stage / 'no_cutoff_final_evidence.py'))
        with patch.object(runtime, '__file__', str(stage / 'no_cutoff_final_runtime.py')), \
                patch.object(sys, 'prefix', str(self.root / '.venv')), \
                patch.dict(sys.modules, {'synthetic_helper': module}, clear=True):
            runtime.loaded_sources(self.root, self.actual)
            module.__file__ = '/other/stage2/no_cutoff_final_evidence.py'
            with self.assertRaises(ValueError): runtime.loaded_sources(self.root, self.actual)
        with self.assertRaises(ValueError): runtime.loaded_sources(self.root, self.actual)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.root = self.f.root
        raw = (Path(__file__).parent / 'input_manifest.json').read_bytes()
        (self.root / 'stage2/input_manifest.json').write_bytes(raw)
        (self.f.runtime / 'python-runtime.tar.gz').write_bytes(b'Synthetic archive')
        self.enterContext(patch.object(runtime, 'DEPLOYMENT', self.root.resolve()))
        self.bound = self.enterContext(patch.object(runtime, 'sources', return_value=self.f.proof['sources']))
        self.enterContext(patch.object(runtime, 'loaded_sources'))
        self.packages = self.enterContext(patch.object(runtime, 'dependencies', return_value=self.f.proof['dependencies']))
        self.bundle = self.enterContext(patch.object(runtime, 'runtime_bundle', return_value=SimpleNamespace(
            validate=lambda: dict(sha256=policy.PYTHON_SHA256))))
        self.host = self.enterContext(patch.object(runtime.host_environment, 'snapshot', return_value=self.f.proof['host_environment']))
        self.dataset = self.enterContext(patch.object(runtime, '_dataset', return_value=(
            self.root / '.cache/tasks', {'synthetic': '1' * 64})))
        self.tasks = {name: dict(docker_image='fixture:' + name, agent_timeout_seconds=12000.0,
            cpus=1, memory_mb=2048, storage_mb=10240, gpus=0) for name in self.f.manifest['all_task_ids']}
        self.configs = self.enterContext(patch.object(runtime, '_task_limits', side_effect=lambda *args: deepcopy(self.tasks)))
        self.original = dict(images=dict.fromkeys(self.tasks, 'sha256:' + '1' * 64),
            agent_deadlines=dict.fromkeys(self.tasks, 12000.0), results_sha256={'synthetic': '2' * 64})
        self.baseline = self.enterContext(patch.object(runtime, '_baseline_images', return_value=self.original))
        self.images = self.enterContext(patch.object(runtime, '_images', side_effect=lambda refs: {
            ref: dict(id=ref if ref.startswith('sha256:') else 'sha256:' + '1' * 64,
                os='linux', architecture='amd64') for ref in refs}))

    def test_all_eighty_nine_task_identities_and_official_limits_without_launch(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        record = runtime.inspect(self.root, self.f.document)
        cells = policy.cells(self.f.document, self.f.manifest)
        self.assertEqual(record['cells'], cells)
        self.assertEqual(list(record['task_inventory']), [c['task_id'] for c in cells])
        self.assertEqual(len(record['task_inventory']), 89)
        self.assertTrue(all(r['agent_timeout_seconds'] == 12000.0 for r in record['task_inventory'].values()))
        self.assertFalse(record['paid_launch_ready'])
        self.assertEqual(record['candidate_sha256'], policy.fingerprint(self.f.document))
        self.assertEqual(record['validation_results_sha256'], policy.fingerprint(self.f.document['result_bindings']))
        self.assertEqual(record['baseline_results_sha256'], self.original['results_sha256'])
        self.baseline.assert_called_once_with(self.root, self.f.manifest)
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob('*')), before)

    def test_current_source_dependencies_host_and_python_archive_cannot_drift(self):
        self.packages.return_value = {}
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        self.packages.return_value = self.f.proof['dependencies']; self.host.return_value = {}
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        self.host.return_value = self.f.proof['host_environment']
        self.bundle.return_value = SimpleNamespace(validate=lambda: dict(sha256='0' * 64))
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        self.bundle.return_value = SimpleNamespace(validate=lambda: dict(sha256=policy.PYTHON_SHA256))
        self.bound.side_effect = [self.f.proof['sources'], {}]
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)

    def test_outside_development_images_and_deadlines_checked_too(self):
        task = self.f.manifest['outside_development_ids'][-1]
        self.original['images'][task] = 'sha256:' + '9' * 64
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        self.original['images'][task] = 'sha256:' + '1' * 64
        self.original['agent_deadlines'][task] = 60.0
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)

    def test_changed_manifest_or_dataset_evidence_refused(self):
        path = self.root / 'stage2/input_manifest.json'; before = path.read_bytes()
        path.write_bytes(before + b' ')
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        path.write_bytes(before); self.dataset.side_effect = ValueError('Changed canonical dataset')
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)

    def test_old_or_different_deployment_not_reused(self):
        with patch.object(runtime, 'DEPLOYMENT', Path('/separate-native-root')):
            with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)

    def test_qualified_identity_is_rechecked_with_producer_files_and_images(self):
        record = runtime.inspect(self.root, self.f.document)
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        with patch.object(runtime, 'verify_native_files') as producer:
            self.assertEqual(runtime.verify_current(self.root, self.f.document, self.f.proof, record), record)
            producer.assert_called_once_with(self.root, self.f.proof)
        self.assertEqual(self.images.call_args.args[0], [self.f.proof['gateway_image'], self.f.proof['guard_image']])

    def test_self_granted_or_stale_identity_is_not_current_qualification(self):
        record = runtime.inspect(self.root, self.f.document)
        with self.assertRaises(ValueError): runtime.verify_current(self.root, self.f.document, self.f.proof, record)
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        changed = dict(record, paid_launch_ready=True)
        with self.assertRaises(ValueError): runtime.verify_current(self.root, self.f.document, self.f.proof, changed)
        with patch.object(runtime, 'verify_native_files'), patch.object(runtime, 'inspect', return_value=changed):
            with self.assertRaises(ValueError): runtime.verify_current(self.root, self.f.document, self.f.proof, record)

    def test_missing_qualified_image_blocks_recheck(self):
        record = runtime.inspect(self.root, self.f.document)
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        with patch.object(runtime, 'verify_native_files'), patch.object(runtime, 'inspect', return_value=record), \
                patch.object(runtime, '_images', return_value={self.f.proof['gateway_image']: {'id': 'sha256:' + '9' * 64}}):
            with self.assertRaises(ValueError): runtime.verify_current(self.root, self.f.document, self.f.proof, record)

    def test_empty_image_response_cannot_pass_final_identity(self):
        record = runtime.inspect(self.root, self.f.document)
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        with patch.object(runtime, 'verify_native_files'), patch.object(runtime, 'inspect', return_value=record), \
                patch.object(runtime, '_images', return_value={}):
            with self.assertRaises(ValueError): runtime.verify_current(self.root, self.f.document, self.f.proof, record)


class ProducerFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.root = self.f.root; self.proof = self.f.proof
        self.write(self.proof['regression_path'] + '/regression.json', self.proof['offline'])
        self.write(self.proof['regression_path'] + '/regression.txt', {'test_output': 'Synthetic only'})
        for case in self.proof['synthetic']:
            self.write(case['runtime_path'] + '/evidence.json', case)
            cancelled = case['mode'] == 'cancel_setup'
            result = dict(stage='final', harness=policy.CONDITION, custom_study=policy.EXPERIMENT,
                trial_id='synthetic-nc-final-' + case['mode'], gateway_image_id=self.proof['gateway_image'],
                status='interrupted' if cancelled else 'verified', model_revoked=True,
                containers_removed=True, networks_removed=True, volumes_removed=True,
                verifier_result=None if cancelled else dict(rewards=dict(reward=1)))
            self.write(case['runtime_path'] + '/.runtime/stage2/scored-trials/synthetic-nc-final-' + case['mode'] + '/result.json', result)

    def write(self, relative, value):
        path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value)); self.proof['evidence_files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_eight_producer_files_and_actual_synthetic_results_are_read(self):
        self.assertEqual(len(self.proof['evidence_files']), 8)
        runtime.verify_native_files(self.root, self.proof)
        policy.validate_qualification(self.f.document, self.f.manifest, self.proof)

    def test_changed_missing_and_symlinked_producer_are_not_flags(self):
        relative = self.proof['synthetic'][0]['runtime_path'] + '/evidence.json'
        path = self.root / relative; before = path.read_bytes(); path.write_bytes(before + b' ')
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)
        path.unlink()
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)
        path.symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)

    def test_hash_consistent_wrong_stage_identity_reward_or_cleanup_rejected(self):
        case = self.proof['synthetic'][0]
        relative = case['runtime_path'] + '/.runtime/stage2/scored-trials/synthetic-nc-final-tools/result.json'
        baseline = json.loads((self.root / relative).read_text())
        for values in ({'stage': 'development'}, {'harness': 'C0'}, {'custom_study': policy.development.EXPERIMENT},
                {'trial_id': 'another-case'}, {'gateway_image_id': 'sha256:' + '0' * 64},
                {'status': 'interrupted'}, {'model_revoked': False}, {'containers_removed': False},
                {'networks_removed': False}, {'volumes_removed': False}, {'verifier_result': None},
                {'verifier_result': {'rewards': {'reward': True}}}):
            self.write(relative, dict(baseline, **values))
            with self.subTest(values=values), self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)

    def test_hash_consistent_regression_and_lifecycle_reports_must_match(self):
        relative = self.proof['regression_path'] + '/regression.json'
        self.write(relative, dict(self.proof['offline'], tests=1))
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)
        self.write(relative, self.proof['offline'])
        case = self.proof['synthetic'][0]
        self.write(case['runtime_path'] + '/evidence.json', dict(case, live_api_calls=1))
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)


if __name__ == '__main__': unittest.main()
