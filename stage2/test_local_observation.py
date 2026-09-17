import asyncio
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from local_trace import PhaseRecorder, TraceSpool
from local_observation import DetailObserver


class DetailTests(unittest.TestCase):
    def test_parallel_observations_have_unique_sequence_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = PhaseRecorder(TraceSpool(tmp), trial_id='fixture', task_id='fixture',
                                     harness='C0', protocol_sha256='a'*64)
            observer = DetailObserver(recorder)
            def run(number):
                with observer.operation('tool', {'tool_calls': 1}):
                    pass
            with ThreadPoolExecutor(max_workers=4) as workers:
                list(workers.map(run, range(20)))
            events = recorder.spool.events()
            self.assertEqual(len(events), 20)
            self.assertEqual({e['sequence'] for e in events}, set(range(1, 21)))
            self.assertFalse(observer.errors)

    def test_failure_kind_and_no_exception_text_capture(self):
        for exception, expected in [(TimeoutError('PRIVATE'), 'timeout'),
                                    (asyncio.CancelledError('PRIVATE'), 'interrupted'),
                                    (RuntimeError('PRIVATE'), 'error')]:
            with tempfile.TemporaryDirectory() as tmp:
                recorder = PhaseRecorder(TraceSpool(tmp), trial_id='fixture', task_id='fixture',
                                         harness='C0', protocol_sha256='a'*64)
                with self.assertRaises(type(exception)):
                    with DetailObserver(recorder).operation('generation', {'requests': 1}):
                        raise exception
                events = recorder.spool.events()
                self.assertEqual(events[0]['status'], expected)
                self.assertNotIn('PRIVATE', str(events))


if __name__ == '__main__':
    unittest.main()
