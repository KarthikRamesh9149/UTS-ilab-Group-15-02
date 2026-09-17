from pathlib import Path
import tempfile
import time
from typing import TypedDict
import unittest
from langgraph.graph import StateGraph, START, END
from local_graph_callbacks import LocalGraphCallbacks
from local_observation import DetailObserver
from local_trace import PhaseRecorder, TraceSpool
from local_langfuse import payload


class State(TypedDict):
    value: str


class GraphObservationTests(unittest.TestCase):
    def test_actual_langgraph_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = PhaseRecorder(TraceSpool(tmp), trial_id='graph-fixture', task_id='fixture',
                                     harness='C0', protocol_sha256='a'*64)
            observer = DetailObserver(recorder)
            callback = LocalGraphCallbacks(observer)
            graph = StateGraph(State)
            graph.add_node('fixture', lambda state: {'value': 'PRIVATE_OUTPUT'})
            graph.add_edge(START, 'fixture')
            graph.add_edge('fixture', END)
            start = time.time_ns()
            result = graph.compile().invoke({'value': 'PRIVATE_INPUT'}, config={'callbacks': [callback]})
            recorder(kind='trial', started_ns=start, ended_ns=time.time_ns(), seconds=0.1)
            self.assertEqual(result['value'], 'PRIVATE_OUTPUT')
            self.assertFalse(callback.active)
            self.assertFalse(observer.errors)
            events = recorder.spool.events()
            self.assertTrue(any(e['kind'] == 'graph' for e in events))
            self.assertNotIn('PRIVATE', str(events))
            payload(events)

    def test_actual_graph_error_recorded_without_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder = PhaseRecorder(TraceSpool(tmp), trial_id='graph-error', task_id='fixture',
                                     harness='C0', protocol_sha256='a'*64)
            observer = DetailObserver(recorder)
            callback = LocalGraphCallbacks(observer)
            graph = StateGraph(State)
            def fail(state): raise RuntimeError('PRIVATE_FAILURE')
            graph.add_node('fixture', fail)
            graph.add_edge(START, 'fixture')
            graph.add_edge('fixture', END)
            with self.assertRaises(RuntimeError):
                graph.compile().invoke({'value': 'PRIVATE_INPUT'}, config={'callbacks': [callback]})
            events = recorder.spool.events()
            self.assertTrue(any(e['status'] == 'error' for e in events))
            self.assertNotIn('PRIVATE', str(events))
            self.assertFalse(callback.active)


if __name__ == '__main__':
    unittest.main()
