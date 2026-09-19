import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from netcup.start_qualification import execute


class NativeSequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'stage2').mkdir()
        self.admission = self.root / 'stage2/admission.json'
        self.admission.write_text('{}')
        self.run = Mock()
        self.admit = Mock()
        self.outcome = {'status': 'all_references_passed', 'results': [
            {'task': task, 'reward': 1, 'cleanup_verified': True} for task in
            ('qemu-startup', 'install-windows-3.11', 'adaptive-rejection-sampler')]}

    def launch(self):
        execute(self.root, self.admission, run=self.run,
                admit=self.admit, inspect=lambda *args: self.outcome)

    def test_reference_success_required_before_single_qualification_block(self):
        self.launch()
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(len(commands), 6)
        self.assertEqual(commands[-1][1], 'stage2/run_qualification.py')
        self.assertNotIn('run_final.py', str(commands))
        self.assertEqual(self.admit.call_count, 2)

    def test_zero_reference_stops_without_scored_dispatch(self):
        self.outcome['results'][0]['reward'] = 0
        with self.assertRaises(RuntimeError): self.launch()
        self.assertEqual(self.run.call_count, 1)

    def test_remaining_reference_failure_prevents_spending(self):
        self.outcome['status'] = 'qualification_incomplete'
        with self.assertRaises(RuntimeError): self.launch()
        self.assertEqual(self.run.call_count, 5)

    def test_invalid_admission_never_runs_anything(self):
        self.admit.side_effect = ValueError('stale')
        with self.assertRaises(ValueError): self.launch()
        self.run.assert_not_called()
