import copy
import json
from pathlib import Path
import tempfile
import unittest

from extended_token_calibration import token_candidates, save_new


class ExtendedCalibrationTests(unittest.TestCase):
    def test_unapproved_asset_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / '.cache/stage2-tokenizer'
            cache.mkdir(parents=True)
            (cache / 'encoding_dsv4.py').write_bytes(b'not the pinned asset')
            with self.assertRaises(ValueError):
                token_candidates(root, {'messages': []})

    def test_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            save_new(path, {'original': True})
            with self.assertRaises(FileExistsError):
                save_new(path, {'original': False})
            self.assertTrue(json.loads(path.read_text())['original'])

    def test_pinned_local_encoder_preserves_request(self):
        root = Path(__file__).resolve().parents[1]
        if not (root / '.cache/stage2-tokenizer/tokenizer.json').exists():
            self.skipTest('Pinned tokenizer assets not available locally')
        request = {'messages': [{'role': 'user', 'content': 'Reply OK.'}],
                   'tools': [{'type': 'function', 'function': {'name': 'example',
                       'parameters': {'type': 'object', 'properties': {}}}}]}
        original = copy.deepcopy(request)
        candidates = token_candidates(root, request)
        self.assertEqual(request, original)
        self.assertEqual(len(candidates), 8)
        self.assertTrue(all(v['tokens'] > 0 and v['rendered_utf8_bytes'] >= v['tokens']
                            for v in candidates.values()))


if __name__ == '__main__':
    unittest.main()
