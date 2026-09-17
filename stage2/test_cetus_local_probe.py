import unittest
from cetus_local_probe import check_gpu_allocation, tool_ok, SHARDS


class ProbeTests(unittest.TestCase):
    def test_capacity_and_allocation(self):
        rows = [['0', 'L40', 'id0', '46068', '45000'], ['1', 'L40', 'id1', '46068', '45000']]
        check_gpu_allocation({'Resource_List': {'ngpus': 2}}, rows)
        for count, inventory in [(1, rows), (2, rows[:1]), (2, rows + rows)]:
            with self.assertRaises(RuntimeError):
                check_gpu_allocation({'Resource_List': {'ngpus': count}}, inventory)
        rows[0][4] = '1000'
        with self.assertRaises(RuntimeError):
            check_gpu_allocation({'Resource_List': {'ngpus': 2}}, rows)

    def test_tool_validation(self):
        response = {'choices': [{'message': {'tool_calls': [{'function': {
            'name': 'add_numbers', 'arguments': '{"a":2,"b":3}'}}]}}]}
        self.assertTrue(tool_ok(response))
        response['choices'][0]['message']['tool_calls'][0]['function']['name'] = 'shell'
        self.assertFalse(tool_ok(response))

    def test_manifest(self):
        self.assertEqual(len(SHARDS), 4)
        self.assertEqual(sum(size for size, _ in SHARDS), 48410992032)
        self.assertTrue(all(len(digest) == 64 for _, digest in SHARDS))


if __name__ == '__main__':
    unittest.main()
