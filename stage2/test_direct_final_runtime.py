"""Final-host file checks with synthetic Docker metadata; no paid calls."""
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import deadline_evidence_freeze as original
import direct_final_policy as policy
import direct_final_runtime as runtime
from test_direct_final_policy import candidate, qualification


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class TemporaryTree(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / '.runtime/stage2').mkdir(parents=True)
        (self.root / 'stage2').mkdir()

    def write(self, name, raw):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return digest(raw)


class SourcesTests(TemporaryTree):
    def setUp(self):
        super().setUp()
        self.document = candidate()
        measured = dict(self.document['candidate']['c3_sources'])
        measured.update({'input_manifest.json': '0' * 64, 'dataset_provenance.json': '0' * 64})
        names = set(measured) | set(self.document['selection_logic_sources']) | policy.REQUIRED_SOURCE_FILES
        actual = {name: self.write('stage2/' + name, b'fixture ' + name.encode()) for name in names}
        self.document['candidate']['c3_sources'] = {name: actual[name] for name in measured}
        self.document['selection_logic_sources'] = {name: actual[name] for name in self.document['selection_logic_sources']}
        self.document['selected_execution'] = original._execution(self.document['candidate'])

    def test_all_current_source_hashes_are_read_from_files(self):
        bound = runtime.sources(self.root, self.document)
        self.assertGreater(len(bound), 25)
        self.assertTrue(policy.REQUIRED_SOURCE_FILES <= set(bound))
        self.assertEqual(bound['custom_model.py'], digest(b'fixture custom_model.py'))

    def test_only_orchestration_delta_can_change(self):
        self.write('stage2/scored_trial.py', b'new explicit admission')
        bound = runtime.sources(self.root, self.document)
        self.assertEqual(set(policy.source_transition(self.document, bound)), {'scored_trial.py'})
        self.write('stage2/custom_model.py', b'changed agent')
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)

    def test_missing_bound_source_and_symlink_rejected(self):
        target = self.root / 'stage2/direct_final_runtime.py'
        saved = target.read_bytes(); target.unlink()
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)
        outside = self.root / 'elsewhere.py'; outside.write_bytes(saved); target.symlink_to(outside)
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)

    def test_dataset_provenance_cannot_be_omitted_from_measured_sources(self):
        self.document['candidate']['c3_sources'].pop('dataset_provenance.json')
        self.document['selected_execution'] = original._execution(self.document['candidate'])
        with self.assertRaises(ValueError): runtime.sources(self.root, self.document)

    def test_older_winner_is_not_relabeled_as_the_c3_finalist(self):
        with self.assertRaises(ValueError): runtime.sources(self.root, candidate(0))

    def test_loaded_helper_must_match_current_tree_and_interpreter(self):
        stage = self.root / 'stage2'
        module = SimpleNamespace(__file__=str(stage / 'direct_final_runtime.py'))
        with patch.object(runtime, '__file__', str(stage / 'direct_final_runtime.py')), \
                patch.object(sys, 'prefix', str(self.root / '.venv')), \
                patch.dict(sys.modules, {'runtime_fixture': module}, clear=True):
            runtime._loaded_sources(self.root, {'direct_final_runtime.py': 'a' * 64})
            module.__file__ = '/different/stage2/direct_final_runtime.py'
            with self.assertRaises(ValueError): runtime._loaded_sources(self.root, {'direct_final_runtime.py': 'a' * 64})
        with self.assertRaises(ValueError): runtime._loaded_sources(self.root, {})


class DatasetTests(TemporaryTree):
    def setUp(self):
        super().setUp()
        self.dataset = self.root / '.cache/tasks'; self.dataset.mkdir(parents=True)
        self.bindings = {'fixture/task.toml': self.write('.cache/tasks/fixture/task.toml', b'version="1.0"'),
            'fixture/instruction.md': self.write('.cache/tasks/fixture/instruction.md', b'private fixture content')}
        self.provenance = dict(dataset_path='.cache/tasks', canonical=dict(
            file_hashes=[dict(path=k, sha256=v) for k, v in self.bindings.items()]))
        self.update()

    def update(self):
        self.bound = {'dataset_provenance.json': self.write('stage2/dataset_provenance.json',
            json.dumps(self.provenance).encode())}

    def test_hash_only_integrity_read_returns_no_task_text(self):
        path, files = runtime._dataset(self.root, self.bound)
        self.assertEqual((path, files), (self.dataset, self.bindings))
        self.assertNotIn('private fixture content', repr(files))

    def test_changed_missing_or_added_dataset_file_rejected(self):
        path = self.dataset / 'fixture/instruction.md'; saved = path.read_bytes()
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError): runtime._dataset(self.root, self.bound)
        path.unlink()
        with self.assertRaises(ValueError): runtime._dataset(self.root, self.bound)
        path.write_bytes(saved); (self.dataset / 'extra').write_text('extra')
        with self.assertRaises(ValueError): runtime._dataset(self.root, self.bound)

    def test_duplicate_inventory_and_escaping_path_rejected(self):
        self.provenance['canonical']['file_hashes'].append(self.provenance['canonical']['file_hashes'][0])
        self.update()
        with self.assertRaises(ValueError): runtime._dataset(self.root, self.bound)
        self.provenance['dataset_path'] = '../outside'; self.update()
        with self.assertRaises(ValueError): runtime._dataset(self.root, self.bound)

    def test_symlinked_dataset_directory_or_file_rejected(self):
        path = self.dataset / 'fixture/instruction.md'; path.unlink()
        path.symlink_to(self.root / 'stage2/dataset_provenance.json')
        with self.assertRaises(ValueError): runtime._dataset(self.root, self.bound)
        path.unlink(); moved = self.dataset.with_name('moved'); self.dataset.rename(moved)
        self.dataset.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError): runtime._dataset(self.root, self.bound)


class TaskLimitTests(TemporaryTree):
    def setUp(self):
        super().setUp()
        self.manifest = dict(all_task_ids=[f'task-{i:02d}' for i in range(89)], tasks=[])
        self.raw = ('version="1.0"\n[metadata]\nprivate_note="not returned"\n'
            '[agent]\ntimeout_sec=12000\n[verifier]\ntimeout_sec=60\n'
            '[environment]\ncpus=1\nmemory_mb=2048\nstorage_mb=10240\ngpus=0\n'
            'docker_image="fixture:tag"\n').encode()
        for task in self.manifest['all_task_ids']:
            sha = self.write(task + '/task.toml', self.raw)
            self.manifest['tasks'].append(dict(task_id=task, task_config_sha256=sha,
                docker_image='fixture:tag', cpus=1, memory_mb=2048, storage_mb=10240, gpus=0, compose_present=False))

    def test_all_eighty_nine_official_configs_and_long_deadline_preserved(self):
        rows = runtime._task_limits(self.root, self.manifest)
        self.assertEqual(len(rows), 89)
        self.assertEqual(rows['task-00']['agent_timeout_seconds'], 12000.0)
        self.assertEqual(rows['task-00']['verifier_timeout_seconds'], 60.0)
        self.assertEqual(rows['task-00']['build_timeout_seconds'], 600.0)
        self.assertNotIn('not returned', repr(rows))

    def test_resource_drift_missing_or_duplicate_task_refused(self):
        for change in ('cpu', 'missing', 'duplicate'):
            manifest = deepcopy(self.manifest)
            if change == 'cpu': manifest['tasks'][0]['cpus'] = 2
            elif change == 'missing': manifest['tasks'].pop()
            else: manifest['tasks'].append(manifest['tasks'][0])
            with self.subTest(change=change), self.assertRaises(ValueError): runtime._task_limits(self.root, manifest)

    def test_changed_config_and_unsupported_network_refused(self):
        self.write('task-00/task.toml', self.raw + b'network_mode="no-network"\n')
        with self.assertRaises(ValueError): runtime._task_limits(self.root, self.manifest)
        self.manifest['tasks'][0]['task_config_sha256'] = digest(self.raw + b'network_mode="no-network"\n')
        with self.assertRaises(ValueError): runtime._task_limits(self.root, self.manifest)


class BaselineImageTests(TemporaryTree):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(runtime, 'BASELINE', self.root))
        self.manifest = dict(all_task_ids=[f'task-{i:02d}' for i in range(89)])
        self.rows = []
        for i, task in enumerate(self.manifest['all_task_ids']):
            for harness in ('terminus-2', 'openhands'):
                name = f'corrected1-final-{harness}-{i:02d}-{task}'
                result = dict(trial_id=name, task_id=task, harness=harness, stage='final',
                    task_image_id='sha256:' + '1' * 64, model_protocol_sha256=policy.SETTINGS.fingerprint(),
                    verifier_result={'reward': 0}, private_note='not returned')
                sha = self.write('.runtime/stage2/scored-trials/' + name + '/result.json', json.dumps(result).encode())
                self.rows.append(dict(trial_id=name, task_id=task, harness=harness,
                    result_sha256=sha, official_agent_timeout_seconds='12000.0'))
        self.update()

    def update(self):
        stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=list(self.rows[0]))
        writer.writeheader(); writer.writerows(self.rows)
        sha = self.write(runtime.BASELINE_CSV, stream.getvalue().encode())
        self.enterContext(patch.object(runtime, 'BASELINE_CSV_SHA256', sha))

    def mutate_result(self, index, **fields):
        row = self.rows[index]
        path = self.root / '.runtime/stage2/scored-trials' / row['trial_id'] / 'result.json'
        result = dict(json.loads(path.read_text()), **fields)
        row['result_sha256'] = self.write(str(path.relative_to(self.root)), json.dumps(result).encode())
        self.update()

    def test_hashes_all_original_results_returns_only_image_and_deadline_metadata(self):
        result = runtime._baseline_images(self.root, self.manifest)
        self.assertEqual(len(result['results_sha256']), 178)
        self.assertEqual(len(result['images']), 89)
        self.assertNotIn('not returned', repr(result))
        self.assertNotIn('reward', repr(result))

    def test_changed_baseline_file_or_csv_blocks(self):
        path = self.root / '.runtime/stage2/scored-trials' / self.rows[0]['trial_id'] / 'result.json'
        path.write_text('{}')
        with self.assertRaises(ValueError): runtime._baseline_images(self.root, self.manifest)
        (self.root / runtime.BASELINE_CSV).write_text('changed')
        with self.assertRaises(ValueError): runtime._baseline_images(self.root, self.manifest)

    def test_missing_or_conflicting_observed_image_is_not_invented(self):
        for value in (None, 'mutable:tag', 'sha256:' + '2' * 64):
            self.mutate_result(1, task_image_id=value)
            with self.subTest(image=value), self.assertRaises(ValueError): runtime._baseline_images(self.root, self.manifest)

    def test_duplicate_baseline_cell_or_result_identity_rejected(self):
        self.rows[1] = deepcopy(self.rows[0]); self.update()
        with self.assertRaises(ValueError): runtime._baseline_images(self.root, self.manifest)

    def test_result_metadata_must_match_immutable_cell_and_protocol(self):
        self.mutate_result(1, harness='C3')
        with self.assertRaises(ValueError): runtime._baseline_images(self.root, self.manifest)

    def test_two_harnesses_must_agree_on_official_time(self):
        self.rows[1]['official_agent_timeout_seconds'] = '60'; self.update()
        with self.assertRaises(ValueError): runtime._baseline_images(self.root, self.manifest)


class DockerMetadataTests(unittest.TestCase):
    def test_inspection_never_starts_or_pulls_an_image(self):
        row = dict(id='sha256:' + '1' * 64, os='linux', architecture='amd64')
        with patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(row))) as command:
            self.assertEqual(runtime._images(['fixture:tag']), {'fixture:tag': row})
        args = command.call_args.args[0]
        self.assertEqual(args[:3], ['docker', 'image', 'inspect'])
        self.assertNotIn('run', args); self.assertNotIn('pull', args)

    def test_missing_wrong_architecture_and_malformed_responses_refused(self):
        for row in ({}, [], dict(id='sha256:' + '1' * 64, os='linux', architecture='arm64')):
            with patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(row))):
                with self.subTest(row=row), self.assertRaises(ValueError): runtime._images(['fixture:tag'])

    def test_command_failure_is_sanitised_and_image_options_rejected(self):
        error = subprocess.CalledProcessError(1, ['docker'], stderr='private fixture text')
        with patch.object(runtime.subprocess, 'run', side_effect=error):
            with self.assertRaisesRegex(ValueError, '^Local Docker image metadata is unavailable$'):
                runtime._images(['fixture:tag'])
        for references in ([], ['--help'], ['bad\nreference']):
            with self.assertRaises(ValueError): runtime._images(references)


class RuntimeIdentityTests(TemporaryTree):
    def setUp(self):
        super().setUp()
        self.document = candidate(); self.proof = qualification(self.document)
        self.manifest = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())
        self.write('stage2/input_manifest.json', (Path(__file__).parent / 'input_manifest.json').read_bytes())
        self.write('.runtime/stage2/python-runtime.tar.gz', b'fixture')
        self.sources = self.enterContext(patch.object(runtime, 'sources', return_value=self.proof['sources']))
        self.enterContext(patch.object(runtime, '_loaded_sources'))
        self.packages = self.enterContext(patch.object(runtime, 'dependencies', return_value=self.proof['dependencies']))
        self.bundle = self.enterContext(patch.object(runtime, 'runtime_bundle', return_value=SimpleNamespace(
            validate=lambda: dict(sha256=policy.PYTHON_SHA256, members=1, unpacked_bytes=1))))
        self.host = self.enterContext(patch.object(runtime.host_environment, 'snapshot', return_value=dict(execution_mode='native_linux_x86_64')))
        self.enterContext(patch.object(runtime, '_dataset', return_value=(self.root / '.cache/tasks', {'fixture': '1' * 64})))
        self.tasks = {t: dict(docker_image='fixture:' + t, agent_timeout_seconds=12000.0)
            for t in self.manifest['all_task_ids']}
        self.enterContext(patch.object(runtime, '_task_limits', side_effect=lambda *args: deepcopy(self.tasks)))
        self.baselines = dict(images={t: 'sha256:' + '1' * 64 for t in self.tasks},
            agent_deadlines=dict.fromkeys(self.tasks, 12000.0), results_sha256={'fixture': '2' * 64})
        self.enterContext(patch.object(runtime, '_baseline_images', return_value=self.baselines))
        self.images = self.enterContext(patch.object(runtime, '_images', side_effect=lambda refs: {
            ref: dict(id=ref if ref.startswith('sha256:') else 'sha256:' + '1' * 64,
                os='linux', architecture='amd64') for ref in refs}))

    def test_current_identity_and_qualified_recheck_are_read_only(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob('*'))
        record = runtime.inspect(self.root, self.document)
        self.assertFalse(record['paid_launch_ready'])
        self.assertEqual(len(record['task_inventory']), 89)
        self.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        self.assertEqual(runtime.verify_current(self.root, self.document, self.proof, record), record)
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob('*')), before)

    def test_dependency_host_and_source_changes_block(self):
        self.packages.return_value = dict(python='0.0.0', packages={})
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.document)
        self.packages.return_value = self.proof['dependencies']; self.host.return_value = {}
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.document)
        self.host.return_value = dict(execution_mode='native_linux_x86_64')
        self.sources.side_effect = [self.proof['sources'], {}]
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.document)

    def test_current_image_or_deadline_drift_from_baselines_blocks(self):
        name = next(iter(self.tasks)); self.baselines['images'][name] = 'sha256:' + '9' * 64
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.document)
        self.baselines['images'][name] = 'sha256:' + '1' * 64
        self.baselines['agent_deadlines'][name] = 60
        with self.assertRaises(ValueError): runtime.inspect(self.root, self.document)

    def test_qualification_cannot_bind_a_different_or_changed_snapshot(self):
        record = runtime.inspect(self.root, self.document)
        with self.assertRaises(ValueError): runtime.verify_current(self.root, self.document, self.proof, record)
        self.proof['runtime_identity_sha256'] = policy.fingerprint(record)
        changed = deepcopy(record); changed['paid_launch_ready'] = True
        with self.assertRaises(ValueError): runtime.verify_current(self.root, self.document, self.proof, changed)
        self.host.return_value = dict(execution_mode='native_linux_x86_64', changed=True)
        with self.assertRaises(ValueError): runtime.verify_current(self.root, self.document, self.proof, record)

    def test_inspection_refuses_the_original_deployment(self):
        with patch.object(runtime, 'ROOTS', {'deadline': self.root}):
            with self.assertRaises(ValueError): runtime.inspect(self.root, self.document)


if __name__ == '__main__':
    unittest.main()
