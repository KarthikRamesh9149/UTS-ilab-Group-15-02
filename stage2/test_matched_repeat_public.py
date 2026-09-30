"""Pure metadata projection using real synthetic archive verification."""
from copy import deepcopy
import csv
import io
import json

import matched_repeat_public as public
import test_matched_repeat_archive as fixture


class PublicTests(fixture.ArchiveTests):
    def output(self):
        data, _, path, record, _, receipt = self.sample()
        verified = self.verify(path, data, record, receipt)
        return data, verified, public.projection(data, self.f.manifest, self.sources, verified)

    def test_public_projection_keeps_89_original_scores_and_subset_denominators_separate(self):
        data, verified, output = self.output()
        self.assertEqual(output, public.projection(data, self.f.manifest, self.sources, verified))
        self.assertEqual(set(output), set(public.OUTPUTS))
        summary = json.loads(output['summary.json'])
        self.assertEqual(summary['original_scores'], {'terminus-2':52,'openhands':44})
        self.assertFalse(summary['original_results_replaced']); self.assertFalse(summary['best_of_selection'])
        self.assertEqual(summary['aggregate'], data['aggregate'])
        self.assertEqual(summary['development20'], data['development20'])
        self.assertEqual(summary['remaining69'], data['remaining69'])
        self.assertFalse(summary['paid_launch_ready'])
        self.assertEqual(summary['inherited_baseline_turn_guards'], {'terminus-2':1000000,'openhands':1000000})

    def test_public_projection_preserves_unknown_cost_and_unexecuted_phase_nulls(self):
        data, _, output = self.output()
        rows = json.loads(output['trials.json'])['rows']
        self.assertIsNone(rows[-1]['reward']); self.assertIsNone(rows[-1]['agent_seconds'])
        self.assertIsNone(json.loads(output['summary.json'])['aggregate']['total_cost_usd'])
        csv_rows = list(csv.DictReader(io.StringIO(output['trials.csv'].decode())))
        self.assertEqual(csv_rows[-1]['reward'], ''); self.assertEqual(csv_rows[-1]['agent_seconds'], '')
        self.assertEqual(csv_rows[-1]['agent_observation'], 'not_run_setup_failed')
        self.assertEqual(len(rows),89); self.assertEqual(len(csv_rows),89)
        self.assertNotIn('opaque unparsed', ''.join(raw.decode() for raw in output.values()))

    def test_public_projection_refuses_extra_fields_or_wrong_archive_identity(self):
        data, verified, _ = self.output()
        changed = deepcopy(data); changed['rows'][0]['raw_model_exchange'] = 'forbidden'
        with self.assertRaises(ValueError): public.projection(changed, self.f.manifest, self.sources, verified)
        for key, value in (('verified_result_files',88),('paid_launch_ready',True),
                ('files',True),('snapshot_sha256','0'*64),('raw_payload','forbidden')):
            changed = dict(verified); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                public.projection(data, self.f.manifest, self.sources, changed)
