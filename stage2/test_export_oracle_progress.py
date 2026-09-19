import json
from pathlib import Path
import tempfile
import unittest
from export_oracle_progress import summary


class OracleExportTests(unittest.TestCase):
    def test_full_pass_requires_verified_limits_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stage2').mkdir()
            tasks = ['task-' + str(i) for i in range(20)]
            (root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': tasks}))
            self.assertEqual(summary(root)['status'], 'partial_snapshot')
            for task in tasks:
                folder = root / '.runtime/stage2/oracle-dev20-v2' / task
                folder.mkdir(parents=True)
                value = {'task': task, 'status': 'verified', 'live_api_calls': 0,
                    'runtime_revision': 'explicit-log-mounts-v2', 'time_utc': 'synthetic',
                    'elapsed_seconds': 1, 'cleanup_verified': True, 'resource_limits_verified': True,
                    'task_limits': {}, 'verifier': {'rewards': {'reward': 1}}, 'private_log': 'must-not-export'}
                (folder / 'result.json').write_text(json.dumps(value))
            report = summary(root)
            self.assertEqual(report['status'], 'all_references_passed')
            self.assertNotIn('must-not-export', json.dumps(report))
            native = summary(root, 'netcup')
            self.assertEqual(native['reference_run'], 'netcup')
            self.assertEqual(native['reference_passes_in_snapshot'], 0)
            self.assertEqual(native['source_namespace'], 'oracle-dev20-snapshot-v4')
            self.assertNotIn('original uncollected', json.dumps(native))
            value['cleanup_verified'] = False
            (folder / 'result.json').write_text(json.dumps(value))
            self.assertEqual(summary(root)['status'], 'qualification_incomplete')
            alternate = summary(root, 'rosetta')
            self.assertEqual(alternate['completed_outcomes'], 0)
            self.assertEqual(alternate['source_namespace'], 'oracle-dev20-rosetta-v1')
            self.assertEqual(alternate['reference_passes_in_snapshot'], 0)
            self.assertEqual(len(alternate['pending_tasks']), 20)
            value['cleanup_verified'] = True
            value['verifier']['rewards']['reward'] = 0
            (folder / 'result.json').write_text(json.dumps(value))
            self.assertEqual(summary(root)['reference_passes_in_snapshot'], 19)
            self.assertEqual(summary(root)['status'], 'qualification_incomplete')

    def test_unknown_run_rejected(self):
        with self.assertRaises(ValueError): summary(Path('/unused'), '../escape')
