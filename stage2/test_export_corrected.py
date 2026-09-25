"""Offline exporter regression checks; synthetic metadata, no model requests."""
import copy
import json
import unittest

from export_corrected import OUTPUT, aggregate, validate_snapshot


class CorrectedExportTests(unittest.TestCase):
    def setUp(self):
        self.tasks=[f'task-{i:02}' for i in range(89)]
        hashes=json.loads((OUTPUT/'launch.json').read_text())['hashes']
        self.data={k:hashes[k] for k in ('registration_sha256','qualification_sha256',
                    'provider_check_sha256','model_protocol_sha256')}
        self.data['audit_checks']={'synthetic':True}
        self.data['rows']=[dict(trial_id=f'{h}-{t}',harness=h,task_id=t,reward=0,
            cleanup_complete=True,model_revoked=True,verifier_error_type='',
            unknown_cost_requests=1,total_cost_usd=None,known_cost_usd='0.01',
            accepted_model_responses=1,model_requests=2,agent_error_type='TimeoutError',
            http_429_requests=1,request_outcome_missing=0,transport_error_requests=1,
            retry_records=1,known_input_tokens=10,known_output_tokens=5,
            input_tokens=None,output_tokens=None,agent_seconds=900)
            for h in ('terminus-2','openhands') for t in self.tasks]

    def test_complete_zero_reward_matrix_is_valid(self):
        validate_snapshot(self.data,self.tasks)

    def test_duplicate_cell_rejected(self):
        self.data['rows'][1]=self.data['rows'][0]
        with self.assertRaises(ValueError):validate_snapshot(self.data,self.tasks)

    def test_missing_cell_rejected(self):
        self.data['rows'].pop()
        with self.assertRaises(ValueError):validate_snapshot(self.data,self.tasks)

    def test_missing_reward_rejected(self):
        self.data['rows'][0]['reward']=None
        with self.assertRaises(ValueError):validate_snapshot(self.data,self.tasks)

    def test_unknown_cost_not_reported_as_zero(self):
        self.data['rows'][0]['total_cost_usd']='0'
        with self.assertRaises(ValueError):validate_snapshot(self.data,self.tasks)

    def test_failed_cleanup_rejected(self):
        self.data['rows'][0]['cleanup_complete']=False
        with self.assertRaises(ValueError):validate_snapshot(self.data,self.tasks)

    def test_different_registered_protocol_rejected(self):
        self.data['model_protocol_sha256']='0'*64
        with self.assertRaises(ValueError):validate_snapshot(self.data,self.tasks)

    def test_failed_audit_rejected(self):
        self.data['audit_checks']['synthetic']=False
        with self.assertRaises(ValueError):validate_snapshot(self.data,self.tasks)

    def test_error_on_pass_not_counted_as_failure(self):
        row=copy.deepcopy(self.data['rows'][0]);row['reward']=1
        value=aggregate([row])
        self.assertEqual((value['passed'],value['failed']),(1,0))
        self.assertEqual(value['failed_agent_error_types'],{})
        self.assertEqual(value['failed_timeouts_with_http_429'],0)

    def test_unknown_tokens_and_cost_preserved_in_summary(self):
        value=aggregate(self.data['rows'])
        self.assertEqual(value['known_cost_usd'],'1.78')
        self.assertIsNone(value['total_cost_usd'])
        self.assertIsNone(value['input_tokens'])
        self.assertIsNone(value['output_tokens'])
        self.assertEqual(value['unknown_cost_requests'],178)


if __name__=='__main__':unittest.main()
