import unittest

from uts_harness.completion_wait import completion_wait_for, validate_completion_wait


class CompletionWaitTests(unittest.TestCase):
    def test_official_timeout_plus_transport_grace(self):
        self.assertEqual(completion_wait_for(900), 960.)
        self.assertEqual(completion_wait_for(120.5), 180.5)

    def test_invalid_values_fail_closed(self):
        for value in (None, True, False, '900', 0, -1, float('nan'), float('inf'),
                      -float('inf'), 10**1000):
            for validate in (validate_completion_wait, completion_wait_for):
                with self.subTest(value=str(value), validate=validate.__name__), self.assertRaises(ValueError):
                    validate(value)
