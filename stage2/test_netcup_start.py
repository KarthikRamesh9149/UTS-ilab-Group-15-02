import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from netcup.start_qualification import execute, prepare_and_qualify


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

    def test_fresh_sequence_registers_proofs_then_first20_only(self):
        def command_run(command, **kwargs):
            if command[1] == 'stage2/build_admission.py':
                Path(command[command.index('--output') + 1]).write_text('{}')
        self.run.side_effect = command_run
        prepare_and_qualify(self.root, 'testv1', run=self.run,
                            inspect=lambda *args: self.outcome, admit=self.admit)
        commands = [call.args[0] for call in self.run.call_args_list]
        native = [command for command in commands if command[1] == 'stage2/native_live_probe.py']
        self.assertEqual([command[command.index('--harness') + 1] for command in native],
                         ['terminus-2', 'openhands', 'custom'])
        self.assertTrue(all('--execute' in command for command in native))
        self.assertEqual(commands[-1][1], 'stage2/run_qualification.py')
        self.assertNotIn('run_development.py', str(commands))
        self.assertNotIn('run_final.py', str(commands))

    def test_incomplete_references_block_fresh_paid_probes(self):
        self.outcome['status'] = 'qualification_incomplete'
        with self.assertRaises(RuntimeError):
            prepare_and_qualify(self.root, 'testv1', run=self.run,
                                inspect=lambda *args: self.outcome, admit=self.admit)
        commands = [call.args[0][1] for call in self.run.call_args_list]
        self.assertNotIn('stage2/native_live_probe.py', commands)

    def test_existing_probe_or_invalid_label_is_not_replayed(self):
        (self.root / 'stage2/native_live_custom_testv1.json').write_text('{}')
        for label in ('testv1', '../escape', '', 'a' * 33):
            with self.assertRaises(ValueError):
                prepare_and_qualify(self.root, label, run=self.run)
        self.run.assert_not_called()

    def test_failed_probe_prevents_later_probes_and_scoring(self):
        def command_run(command, **kwargs):
            if command[1] == 'stage2/native_live_probe.py':
                raise RuntimeError('retained paid probe failure')
        self.run.side_effect = command_run
        with self.assertRaisesRegex(RuntimeError, 'retained'):
            prepare_and_qualify(self.root, 'testv1', run=self.run,
                                inspect=lambda *args: self.outcome, admit=self.admit)
        commands = [call.args[0][1] for call in self.run.call_args_list]
        self.assertEqual(commands.count('stage2/native_live_probe.py'), 1)
        self.assertNotIn('stage2/build_admission.py', commands)
        self.assertNotIn('stage2/run_qualification.py', commands)
