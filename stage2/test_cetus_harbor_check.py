import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from cetus_instance_transport import CommandResult
from cetus_harbor_check import check


class PreparedCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_login_node_execution(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            output = Path(tmp) / 'output'
            with self.assertRaises(RuntimeError): await check(output)
            self.assertFalse(output.exists())

    async def scenario(self, root, fail_start=False):
        scratch = root / 'scratch'
        scratch.mkdir()
        calls = []
        async def run(argv, **kwargs):
            calls.append(argv)
            if argv[1] == 'pull':
                Path(argv[2]).write_bytes(b'synthetic SIF placeholder, never executed')
            if argv[1:3] == ['instance', 'start'] and fail_start:
                return CommandResult(255, b'', b'fixture failure')
            return CommandResult(1 if argv[1] == 'exec' else 0, b'', b'')
        transport = AsyncMock()
        transport.exec.return_value = CommandResult(0, b'', b'')
        async def download(source, target):
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target) / 'reward.txt').write_text('1\n')
        transport.download_dir.side_effect = download
        with patch.dict(os.environ, {'PBS_JOBID': '123.hpc-head01'}), \
             patch('cetus_harbor_check.tempfile.mkdtemp', return_value=str(scratch)), \
             patch('cetus_harbor_check.run_process', side_effect=run), \
             patch('cetus_harbor_check.InstanceTransport', return_value=transport):
            result = await check(root / 'output')
        return result, calls

    async def test_prepared_script_lifecycle_with_mocked_apptainer(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = await self.scenario(Path(tmp))
            self.assertTrue(result['complete'])
            self.assertEqual(result['scored_trials'], 0)
            self.assertEqual(result['model_requests'], 0)
            self.assertEqual(result['agent'], 'TrustedFixtureAgent')
            starts = [c for c in calls if c[1:3] == ['instance', 'start']]
            self.assertEqual(len(starts), 1)
            self.assertEqual(starts[0][starts[0].index('--network') + 1], 'none')
            self.assertEqual(len([c for c in calls if c[1:3] == ['instance', 'stop']]), 1)
            self.assertTrue((Path(tmp) / 'output/result.json').is_file())

    async def test_start_failure_still_attempts_cleanup_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, calls = await self.scenario(Path(tmp), fail_start=True)
            self.assertFalse(result['complete'])
            self.assertEqual(result['start_exit'], 255)
            self.assertEqual(len([c for c in calls if c[1:3] == ['instance', 'stop']]), 1)


if __name__ == '__main__':
    unittest.main()
