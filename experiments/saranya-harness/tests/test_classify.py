"""Offline tests for infrastructure classification and job summaries."""
import json
from pathlib import Path
import tempfile
import unittest

from saranya_harness.classify import classify_trial, scan_network, scan_output
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
        self.assertEqual(classify(reward=None, exception_type='RuntimeError',
                                  network_signals=['no such host']), 'infrastructure')
        self.assertEqual(classify(network_signals=["Could not resolve '"]), 'infrastructure')

    def test_network_signatures(self):
        self.assertEqual(scan_network("E: Failed to fetch ... Could not resolve 'deb.debian.org'"),
                         ["Could not resolve '"])
        self.assertEqual(scan_network('dial tcp: lookup registry-1.docker.io: no such host'), ['no such host'])
        self.assertEqual(scan_network('All 6 tests passed'), [])


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

    def test_oracle_logs_and_verifier_network_are_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / 'job'
            trials = {
                # Built-in agents record no metadata: the Rosetta crash is only in agent/oracle.txt.
                'rosetta': ('terminal-bench/install-windows-3.11', 'agent', 'oracle.txt',
                            'rosetta error: Unimplemented syscall number 282'),
                # The solution succeeded but the verifier could not download its tools.
                'offline': ('terminal-bench/openssl-selfsigned-cert', 'verifier', 'test-stdout.txt',
                            "E: Failed to fetch x  Could not resolve 'deb.debian.org'"),
            }
            for name, (task, folder, filename, text) in trials.items():
                (job / name / folder).mkdir(parents=True)
                (job / name / folder / filename).write_text(text)
                (job / name / 'result.json').write_text(json.dumps(
                    {'task_name': task, 'trial_name': name, 'verifier_result': {'rewards': {'reward': 0.0}}}))
            output = Path(tmp) / 'out.csv'
            counts = summarise(job, output, host='linux-x86_64')
            self.assertEqual(dict(counts), {'infrastructure': 2})
            text = output.read_text()
            self.assertIn('host translation signature', text)
            self.assertIn('host network failure', text)


if __name__ == '__main__':
    unittest.main()
