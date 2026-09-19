import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import reference_download_repair as repair


class ReferenceDownloadRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'stage2').mkdir()
        (self.root / 'stage2/dataset_provenance.json').write_text(json.dumps({'dataset_path': 'dataset'}))
        self.task = self.root / 'dataset' / repair.TASK
        (self.task / 'solution').mkdir(parents=True)
        (self.task / 'tests').mkdir()
        (self.task / 'tests/test.sh').write_text('opaque verifier fixture')
        (self.task / 'instruction.md').write_text('opaque instruction fixture')
        self.original = b'unchanged prefix\n' + b'\n'.join(
            (repair.HTTPS + name).encode() for name in repair.FILES) + b'\nunchanged suffix\n'
        (self.task / 'solution/solve.sh').write_bytes(self.original)
        self.digest = hashlib.sha256(self.original).hexdigest()
        self.original_attempt = self.root / '.runtime/stage2' / repair.ORIGINAL_NAMESPACE / repair.TASK
        (self.original_attempt / 'agent').mkdir(parents=True)
        (self.original_attempt / 'result.json').write_text(json.dumps({
            'task': repair.TASK, 'live_api_calls': 0, 'status': 'verified',
            'cleanup_verified': True, 'verifier': {'rewards': {'reward': 0}}}))
        (self.original_attempt / 'agent/exit-code.txt').write_text('8')
        (self.original_attempt / 'agent/oracle.txt').write_text(
            repair.HTTPS + repair.FILES[0] + '\nERROR 403: Forbidden.\n')
        self.patcher = patch.object(repair, 'SOURCE_SHA256', self.digest)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_only_three_exact_urls_change_in_private_copy(self):
        original_files = repair.inventory(self.task)
        copy, record = repair.prepare(self.root)
        self.assertEqual(repair.inventory(self.task), original_files)
        changed = [key for key, value in repair.inventory(copy).items() if value != original_files[key]]
        self.assertEqual(changed, ['solution/solve.sh'])
        self.assertFalse(record['model_environment_changed'])
        self.assertFalse(record['task_instruction_and_verifier_bytes_changed'])
        self.assertFalse(record['canonical_dataset_changed'])
        after = (copy / 'solution/solve.sh').read_bytes()
        self.assertEqual(after.replace(repair.FTP.encode(), repair.HTTPS.encode()), self.original)
        self.assertEqual(repair.validate_copy(self.root), record)
        self.assertEqual(repair.prepare(self.root), (copy, record))

    def test_source_digest_or_url_counts_drift_rejected(self):
        with self.assertRaises(ValueError): repair.amend(self.original + b'x')
        raw = self.original + (repair.HTTPS + repair.FILES[0]).encode()
        with patch.object(repair, 'SOURCE_SHA256', hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(ValueError, 'one occurrence'): repair.amend(raw)

    def test_copy_verifier_mutation_and_symlink_rejected(self):
        copy, _ = repair.prepare(self.root)
        verifier = copy / 'tests/test.sh'
        verifier.write_text('altered')
        with self.assertRaises(ValueError): repair.validate_copy(self.root)
        verifier.unlink()
        verifier.symlink_to(self.task / 'tests/test.sh')
        with self.assertRaises(ValueError): repair.validate_copy(self.root)

    def test_no_override_until_new_result_and_no_reward_cherry_picking(self):
        copy, record = repair.prepare(self.root)
        self.assertIsNone(repair.qualified_override(self.root))
        trial = copy.parent / repair.TASK
        trial.mkdir()
        value = {'reference_amendment': record, 'verifier': {'rewards': {'reward': 0}}}
        (trial / 'result.json').write_text(json.dumps(value))
        self.assertEqual(repair.qualified_override(self.root), value)

    def test_original_failure_evidence_required_and_bound(self):
        repair.prepare(self.root)
        (self.original_attempt / 'agent/exit-code.txt').write_text('0')
        with self.assertRaises(ValueError): repair.validate_copy(self.root)
