"""Local file and mocked host identity tests, not native qualification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import no_cutoff_custom_policy as policy
import no_cutoff_custom_runtime as runtime
from test_no_cutoff_custom_policy import Fixture, document_fixture


class SourceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.document = document_fixture()
        inherited = self.document['candidate']['c3_sources']
        logic = self.document['selection_logic_sources']
        actual = {}
        for name in set(inherited) | set(logic) | policy.REQUIRED_SOURCE_FILES:
            path = self.root / 'stage2' / name; path.parent.mkdir(parents=True, exist_ok=True)
            raw = ('synthetic ' + name).encode(); path.write_bytes(raw)
            actual[name] = hashlib.sha256(raw).hexdigest()
        self.document['candidate']['c3_sources'] = {name: actual[name] for name in inherited}
        self.document['selection_logic_sources'] = {name: actual[name] for name in logic}
        self.enterContext(patch.object(policy, 'ORIGINAL_FREEZE_SHA256', policy.fingerprint(self.document)))

    def test_hashes_actual_new_files_and_reused_sources(self):
        sources = runtime.sources(self.root, self.document)
        self.assertGreater(len(sources), 35)
        self.assertEqual(sources['no_cutoff_custom_agent.py'], hashlib.sha256(b'synthetic no_cutoff_custom_agent.py').hexdigest())

    def test_shared_agent_or_selection_mutation_blocks(self):
        for name in ('custom_model.py', 'custom_deadline_execution.py', 'deadline_final_selection.py'):
            path = self.root / 'stage2' / name; saved = path.read_bytes(); path.write_bytes(b'changed')
            with self.subTest(name=name), self.assertRaises(ValueError): runtime.sources(self.root, self.document)
            path.write_bytes(saved)

    def test_explicit_trace_and_admission_delta_recorded_not_hidden(self):
        for name in ('local_trace.py', 'scored_trial.py'):
            (self.root / 'stage2' / name).write_bytes(b'revision admission')
        changed = policy.source_transition(self.document, runtime.sources(self.root, self.document))
        self.assertEqual(set(changed['orchestration_changes']), {'local_trace.py', 'scored_trial.py'})

    def test_missing_and_symlinked_helper_block(self):
        path = self.root / 'stage2/no_cutoff_custom_gateway.py'
        path.unlink()
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)
        path.symlink_to(self.root / 'stage2/no_cutoff_custom_policy.py')
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)

    def test_own_interpreter_and_loaded_module_locations_required(self):
        stage = self.root / 'stage2'
        module = SimpleNamespace(__file__=str(stage / 'no_cutoff_custom_agent.py'))
        with patch.object(runtime, '__file__', str(stage / 'no_cutoff_custom_runtime.py')), \
                patch.object(sys, 'prefix', str(self.root / '.venv')), \
                patch.dict(sys.modules, {'agent_fixture': module}, clear=True):
            runtime.loaded_sources(self.root, {'no_cutoff_custom_agent.py': '1' * 64})
            module.__file__ = '/other/stage2/no_cutoff_custom_agent.py'
            with self.assertRaises(ValueError): runtime.loaded_sources(self.root, {'no_cutoff_custom_agent.py': '1' * 64})
        with self.assertRaises(ValueError): runtime.loaded_sources(self.root, {})


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.f = Fixture(self, folder.name); self.root = self.f.root
        (self.root / 'stage2').mkdir()
        raw = (Path(__file__).parent / 'input_manifest.json').read_bytes()
        (self.root / 'stage2/input_manifest.json').write_bytes(raw)
        (self.f.rt / 'python-runtime.tar.gz').write_bytes(b'synthetic archive')
        self.manifest = json.loads(raw)
        self.enterContext(patch.object(runtime, 'DEPLOYMENT', self.root.resolve()))
        self.bound = self.enterContext(patch.object(runtime, 'sources', return_value=self.f.proof['sources']))
        self.enterContext(patch.object(runtime, 'loaded_sources'))
        self.packages = self.enterContext(patch.object(runtime, 'dependencies', return_value=self.f.proof['dependencies']))
        self.bundle = self.enterContext(patch.object(runtime, 'runtime_bundle', return_value=SimpleNamespace(
            validate=lambda: dict(sha256=policy.PYTHON_SHA256))))
        self.host = self.enterContext(patch.object(runtime.host_environment, 'snapshot', return_value=self.f.proof['host_environment']))
        self.enterContext(patch.object(runtime, '_dataset', return_value=(self.root / '.cache/tasks', {'fixture': '1' * 64})))
        self.tasks = {name: dict(docker_image='fixture:' + name, agent_timeout_seconds=12000.0)
                      for name in self.manifest['all_task_ids']}
        self.enterContext(patch.object(runtime, '_task_limits', side_effect=lambda *args: deepcopy(self.tasks)))
        self.original = dict(images=dict.fromkeys(self.tasks, 'sha256:' + '1' * 64),
            agent_deadlines=dict.fromkeys(self.tasks, 12000.0), results_sha256={'fixture': '2' * 64})
        self.enterContext(patch.object(runtime, '_baseline_images', return_value=self.original))
        self.images = self.enterContext(patch.object(runtime, '_images', side_effect=lambda refs: {
            ref: dict(id=ref if ref.startswith('sha256:') else 'sha256:' + '1' * 64,
                os='linux', architecture='amd64') for ref in refs}))

    def test_read_only_fixed20_identity_preserves_long_official_time(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        record = runtime.inspect(self.root, self.f.document)
        self.assertEqual(list(record['task_inventory']), self.f.tasks)
        self.assertTrue(all(row['agent_timeout_seconds'] == 12000. for row in record['task_inventory'].values()))
        self.assertFalse(record['paid_launch_ready'])
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        self.assertEqual(runtime.verify_current(self.root, self.f.document, self.f.proof, record), record)
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob('*')), before)

    def test_wrong_host_dependency_and_source_drift_refused(self):
        self.packages.return_value = {}
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        self.packages.return_value = self.f.proof['dependencies']; self.host.return_value = {}
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        self.host.return_value = self.f.proof['host_environment']
        self.bound.side_effect = [self.f.proof['sources'], {}]
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)

    def test_image_or_deadline_drift_and_no_benchmark_replacement(self):
        name = self.f.tasks[0]
        self.original['images'][name] = 'sha256:' + '9' * 64
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)
        self.original['images'][name] = 'sha256:' + '1' * 64
        self.original['agent_deadlines'][name] = 60.
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)

    def test_no_inspection_in_old_deployment(self):
        with patch.object(runtime, 'DEPLOYMENT', Path('/different-native-root')):
            with self.assertRaises(ValueError): runtime.inspect(self.root, self.f.document)

    def test_qualified_record_must_be_actual_current_identity(self):
        record = runtime.inspect(self.root, self.f.document)
        with self.assertRaises(ValueError): runtime.verify_current(self.root, self.f.document, self.f.proof, record)
        self.f.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        record['paid_launch_ready'] = True
        with self.assertRaises(ValueError): runtime.verify_current(self.root, self.f.document, self.f.proof, record)


if __name__ == '__main__':
    unittest.main()
