from pathlib import Path
import tempfile
import unittest
from verify_dataset import compare, git_blob


class DatasetVerificationTests(unittest.TestCase):
    def test_detects_changes_missing_and_extra(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'task').mkdir()
            (root / 'task' / 'same').write_bytes(b'same')
            (root / 'task' / 'changed').write_bytes(b'changed')
            (root / 'task' / 'extra').write_bytes(b'extra')
            tree = {'tree': [{'path': 'tasks/task/' + name, 'type': 'blob',
                              'mode': '100644', 'sha': git_blob(b'same')}
                             for name in ['same', 'changed', 'missing']]}
            result = compare(root, tree, {'task'})
            self.assertEqual(result['differences'], [
                {'path': 'task/changed', 'reason': 'modified'},
                {'path': 'task/missing', 'reason': 'missing'},
                {'path': 'task/extra', 'reason': 'extra'}])

    def test_rejects_truncated_tree(self):
        with self.assertRaises(ValueError):
            compare(Path('/unused'), {'truncated': True}, set())

    def test_does_not_follow_symlink_for_hashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'task').mkdir()
            (root / 'task' / 'link').symlink_to('/nonexistent-sensitive-file')
            tree = {'tree': [{'path': 'tasks/task/link', 'type': 'blob', 'mode': '100644', 'sha': 'unused'}]}
            result = compare(root, tree, {'task'})
            self.assertEqual(result['differences'][0]['reason'], 'unsupported_file_type')
