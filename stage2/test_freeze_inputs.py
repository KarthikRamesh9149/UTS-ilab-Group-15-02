import unittest
from unittest.mock import patch
from pathlib import Path
import json
import tempfile
from freeze_inputs import build, select_dev, dataset_path


class InputTests(unittest.TestCase):
    def test_canonical_provenance_path_is_preferred(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'stage2').mkdir()
            (root / 'stage2/dataset_provenance.json').write_text(json.dumps({'dataset_path': '.cache/canonical/tasks'}))
            with patch('freeze_inputs.ROOT', root):
                self.assertEqual(dataset_path(), root / '.cache/canonical/tasks')

    def test_order_independent(self):
        ids = [str(i) for i in range(89)]
        self.assertEqual(select_dev(ids), select_dev(list(reversed(ids))))

    def test_rejects_incomplete_or_duplicate_dataset(self):
        for ids in [['x'] * 89, [str(i) for i in range(88)]]:
            with self.assertRaises(ValueError):
                select_dev(ids)

    def test_real_inventory(self):
        data = build()
        self.assertEqual(len(data['tasks']), 89)
        self.assertEqual(len(data['development_ids']), 20)
        self.assertEqual(len(data['outside_development_ids']), 69)
        self.assertFalse(set(data['development_ids']) & set(data['outside_development_ids']))


if __name__ == '__main__':
    unittest.main()
