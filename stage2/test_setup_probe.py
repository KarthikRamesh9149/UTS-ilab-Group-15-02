from decimal import Decimal
import unittest
from setup_probe import full_context_bound, validate_metadata, CONTEXT
from gateway_policy import MODEL, ENDPOINT


class SetupTests(unittest.TestCase):
    def metadata(self):
        return {'data':{'id':MODEL, 'endpoints':[{'tag':ENDPOINT,'quantization':'fp8',
            'context_length':CONTEXT,'pricing':{'prompt':'0.00000006','completion':'0.00000018'}}]}}

    def test_full_context_bound_includes_all_input(self):
        self.assertEqual(full_context_bound({'max_tokens':64}), Decimal('.1048704'))

    def test_metadata_accepts_only_frozen_configuration(self):
        validate_metadata(self.metadata())
        for field, value in [('quantization','fp16'),('context_length',CONTEXT*2),('tag','other')]:
            data=self.metadata()
            data['data']['endpoints'][0][field]=value
            with self.assertRaises(ValueError): validate_metadata(data)

    def test_price_and_extra_billing_fail_closed(self):
        for field,value in [('prompt','.01'),('request','.01')]:
            data=self.metadata()
            data['data']['endpoints'][0]['pricing'][field]=value
            with self.assertRaises(ValueError): validate_metadata(data)
