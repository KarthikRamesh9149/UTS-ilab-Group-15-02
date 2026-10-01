"""Offline tests for infrastructure classification and job summaries."""
import json
from pathlib import Path
import tempfile
import unittest

from saranya_harness.classify import classify_trial, scan_output
from saranya_harness.summarize import summarise


def classify(**overrides):
    values = dict(task_id='mailman', reward=0.0, exception_type=None, infrastructure_signals=[], host='mac')
    values.update(overrides)
    return classify_trial(**values)[0]


class ClassifyTest(unittest.TestCase):
    def test_rosetta_signatures(self):
        self.assertEqual(len(scan_output('rosetta error: Unimplemented syscall number 282')), 2)
        self.assertEqual(scan_output('bash: ./tool: cannot execute binary file: Exec format error'), [])
        self.assertEqual(scan_output(None), [])

    def test_categories(self):
        self.assertEqual(classify(reward=1.0, infrastructure_signals=['rosetta error']), 'passed')
        self.assertEqual(classify(task_id='qemu-startup'), 'infrastructure')
        self.assertEqual(classify(task_id='qemu-startup', host='linux-x86_64'), 'model_failure')
        self.assertEqual(classify(task_id='build-pov-ray'), 'model_failure')
        self.assertEqual(classify(infrastructure_signals=['rosetta error']), 'infrastructure')
        self.assertEqual(classify(reward=None, exception_type='EnvironmentStartTimeoutError'), 'infrastructure')
        self.assertEqual(classify(exception_type='AgentTimeoutError'), 'model_failure')
        self.assertEqual(classify(stop_reason='budget_per_trial'), 'budget_stop')
        self.assertEqual(classify(stop_reason='budget_overall'), 'budget_stop')
        self.assertEqual(classify(stop_reason='no_spending_approval'), 'not_attempted')
        self.assertEqual(classify(stop_reason='no_spending_approval', task_id='qemu-startup'), 'not_attempted')
        self.assertEqual(classify(exception_type='VerifierTimeoutError'), 'infrastructure_review')
        self.assertEqual(classify(reward=None, exception_type='RuntimeError'), 'infrastructure_review')


class SummariseTest(unittest.TestCase):
    def test_job_directory_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / 'job'
            trials = {
                'a': {'task_name': 'terminal-bench/mailman', 'trial_name': 'a',
                      'verifier_result': {'rewards': {'reward': 1.0}},
                      'agent_result': {'n_input_tokens': 10, 'metadata': {'host': 'mac', 'model_calls': 2}}},
                'b': {'task_name': 'terminal-bench/qemu-startup', 'trial_name': 'b',
                      'verifier_result': {'rewards': {'reward': 0.0}},
                      'agent_result': {'metadata': {'host': 'mac'}}},
                'c': {'task_name': 'terminal-bench/regex-chess', 'trial_name': 'c',
                      'verifier_result': {'rewards': {'reward': 0.0}},
                      'exception_info': {'exception_type': 'AgentTimeoutError'},
                      'agent_result': {'metadata': {'host': 'mac', 'stop_reason': None}},
                      'agent_execution': {'started_at': '2026-10-01T00:00:00+00:00',
                                          'finished_at': '2026-10-01T00:15:00+00:00'}},
            }
            for name, result in trials.items():
                (job / name).mkdir(parents=True)
                (job / name / 'result.json').write_text(json.dumps(result))
            (job / 'result.json').write_text(json.dumps({'job': 'summary'}))
            output = Path(tmp) / 'out.csv'
            counts = summarise(job, output)
            self.assertEqual(dict(counts), {'passed': 1, 'infrastructure': 1, 'model_failure': 1})
            self.assertIn('900.0', output.read_text())


if __name__ == '__main__':
    unittest.main()
