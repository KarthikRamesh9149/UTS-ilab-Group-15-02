import unittest
from unittest.mock import patch
from cetus_apptainer_qualification import limits_verified, FLAGS, trial


class CapabilityTests(unittest.TestCase):
    def test_v2_finite_limits(self):
        limits = {'memory.max': '536870912', 'cpu.max': '100000 100000', 'pids.max': '64'}
        self.assertTrue(limits_verified({'files': limits}))
        for key, value in [('memory.max', 'max'), ('cpu.max', 'max 100000'), ('pids.max', 'max'),
                           ('memory.max', '1073741824'), ('cpu.max', '200000 100000')]:
            changed = dict(limits, **{key: value})
            self.assertFalse(limits_verified({'files': changed}))

    def test_v1_limits_and_missing_data(self):
        self.assertTrue(limits_verified({'files': {'memory.limit_in_bytes': '536870912',
            'cpu.cfs_quota_us': '50000', 'cpu.cfs_period_us': '100000', 'pids.max': '32'}}))
        self.assertFalse(limits_verified({}))
        self.assertFalse(limits_verified({'files': {'memory.max': None}}))

    def test_no_network_fallback(self):
        self.assertEqual(FLAGS[FLAGS.index('--network') + 1], 'none')
        self.assertIn('--containall', FLAGS)
        self.assertIn('home,tmp,bind-paths,hostfs,cwd,sys', FLAGS)

    def test_start_failure_still_attempts_cleanup(self):
        with patch('cetus_apptainer_qualification.command', return_value={'exit_code': 255, 'stdout': '', 'stderr': 'denied'}) as run:
            with patch('cetus_apptainer_qualification.instance_pid', return_value=None):
                result = trial('/fixture.sif', 'uts-caps-test', fakeroot=True, enforce=True)
        self.assertFalse(result['complete'])
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[1][0][0][:3], ['apptainer', 'instance', 'stop'])


if __name__ == '__main__':
    unittest.main()
