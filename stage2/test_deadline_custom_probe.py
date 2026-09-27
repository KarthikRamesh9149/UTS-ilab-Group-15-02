"""Synthetic provider assertions, no native execution or actual API access."""
import json
from pathlib import Path
import unittest
from deadline_custom_probe import SyntheticProvider,EXPECTED_LOGICAL
from test_portable_custom_probe import ProviderFixtureTests
from test_retry_gateway import Clock
from openrouter_transport import TransportError


class ProbeTests(unittest.TestCase):
    def request(self,contents=()):
        value=ProviderFixtureTests().request()
        value['messages']=[{'role':'system','content':'[Task time remaining]'}]+[
            {'role':'tool','content':c} for c in contents]
        return value

    def test_time_note_and_fake_key_are_required(self):
        with self.assertRaises(ValueError):SyntheticProvider('not-real',clock=Clock())
        provider=SyntheticProvider('synthetic-not-a-real-key',clock=Clock())
        with self.assertRaises(AssertionError):provider.complete(ProviderFixtureTests().request(),on_response_headers=lambda _:None)
        with self.assertRaises(TransportError):provider.complete(self.request(),on_response_headers=lambda _:None)

    def test_long_command_jobs_and_seven_repair_observations(self):
        p=SyntheticProvider('synthetic-not-a-real-key',clock=Clock());p.calls=10
        def call(contents=()):return p.complete(self.request(contents),on_response_headers=lambda _:None)['choices'][0]['message']['tool_calls']
        calls=call();args=json.loads(calls[0]['function']['arguments'])
        self.assertIn('sleep 61',args['command']);self.assertNotIn('timeout',args)
        self.assertEqual(len(call(['LONG_COMMAND_OK'])),8)
        self.assertEqual(len(call([json.dumps({'job_id':str(i)}) for i in range(8)])),65)
        call([json.dumps({'job_id':str(i)}) for i in range(8,73)])
        self.assertEqual(len(call(['JOBS_WAITED'])),73)
        call([json.dumps({'exit_code':0})]*73)
        for i in range(1,7):
            call([json.dumps({'status':'repair_requested','terminal':False,'repair_number':i})])
        last=call([json.dumps({'status':'repair_requested','terminal':False,'repair_number':7})])
        self.assertTrue(json.loads(last[0]['function']['arguments'])['checks'])
        self.assertEqual(p.calls,EXPECTED_LOGICAL+1)

    def test_no_fake_long_command_or_job_success(self):
        for count,contents in ((11,['failed']), (15,[json.dumps({'exit_code':124})]*73),
                               (16,[json.dumps({'status':'repair_exhausted','terminal':True})])):
            p=SyntheticProvider('synthetic-not-a-real-key',clock=Clock());p.calls=count
            with self.assertRaises(AssertionError):p.complete(self.request(contents),on_response_headers=lambda _:None)

    def test_network_isolated_actual_gateway_and_verifier_path(self):
        code=(Path(__file__).parent/'deadline_custom_probe.py').read_text()
        self.assertIn("gateway['network_mode'] = 'none'",code)
        self.assertIn('client_factory=SyntheticProvider',code)
        self.assertIn('await execution',code)
        self.assertIn('expected_verifier_result',code)
        self.assertNotIn('sk-or-',code)


if __name__=='__main__':unittest.main()
