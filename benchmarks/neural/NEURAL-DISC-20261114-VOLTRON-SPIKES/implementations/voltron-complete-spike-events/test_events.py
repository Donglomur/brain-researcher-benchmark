"""Invented full-cohort controls; no optical traces or electrical truth."""
import copy
import importlib.util
import itertools
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('voltron_scientific_source', Path(__file__).with_name('event_score.py'))
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)


def fixture():
    cells = ['c' + str(i) for i in range(12)]
    mapping = {c: 'a' + str(i % 7) for i, c in enumerate(cells)}
    public = {'schema': 'voltron-complete-events-public/v1', 'task_id': S.TASK,
              'release_manifest_sha256': '1' * 64, 'cells': cells, 'expected_animals': 7, 'movies': {}}
    for i, cell in enumerate(cells):
        public['movies']['m' + str(i)] = {'cell_id': cell, 'fold_id': 'f' + str(i % 7),
            'clock_hz': 4000, 'optical_rate_hz': 400 if i < 6 else 1000,
            'start_tick': 0, 'end_tick': 8000,
            'input_disposition': 'ready', 'optical_valid_intervals': [[0, 8000]],
            'tiles': [{'tile_id': 't' + str(i) + 'a', 'start_tick': 0, 'end_tick': 4000},
                      {'tile_id': 't' + str(i) + 'b', 'start_tick': 4000, 'end_tick': 8000}]}
    reference = {'schema': 'voltron-complete-events-reference/v1', 'task_id': S.TASK,
        'public_sha256': S.identity(public), 'census_evidence_sha256': '2' * 64,
        'mapping_evidence_sha256': '3' * 64, 'cell_to_animal': mapping,
        'outer_folds': {'f' + str(i): {'query_animal': 'a' + str(i),
             'train_cells': [c for c in cells if mapping[c] != 'a' + str(i)]} for i in range(7)},
        'movies': {m: {'valid_intervals': [[0, 8000]], 'spikes': [3990, 6500]} for m in public['movies']}}
    predictions = {'schema': 'voltron-complete-events-predictions/v1', 'task_id': S.TASK,
                   'public_sha256': S.identity(public), 'roles': {}}
    for role in S.ROLES:
        predictions['roles'][role] = {'program_sha256': '4' * 64, 'calibration_sha256': '5' * 64,
           'tiles': {tile['tile_id']: ([3990] if tile['end_tick'] == 4000 else [6500])
                     for m in public['movies'].values() for tile in m['tiles']}}
    return public, predictions, reference


def maximum_bipartite_size(predictions, truth, hz):
    """Independent exhaustive assignment oracle for tiny invented trains."""
    def visit(i, used):
        if i == len(predictions): return 0
        best = visit(i + 1, used)
        for j, target in enumerate(truth):
            if j not in used and abs(predictions[i] - target) * 200 <= hz:
                best = max(best, 1 + visit(i + 1, used | {j}))
        return best
    return visit(0, set())


class Matching(unittest.TestCase):
    def test_exhaustive_maximum_cardinality_1024_pairs(self):
        trains = [tuple(i for i in range(5) if mask & (1 << i)) for mask in range(32)]
        for p in trains:
            for g in trains:
                with self.subTest(pred=p, gold=g):
                    got = S.match_events(p, g, 400)
                    self.assertEqual(got[0], maximum_bipartite_size(p, g, 400))
                    self.assertEqual(got[0] + got[1], len(p))
                    self.assertEqual(got[0] + got[2], len(g))

    def test_exact_five_ms_inclusive_and_one_tick_outside(self):
        self.assertEqual(S.match_events((105,), (100,), 1000)[:3], (1, 0, 0))
        self.assertEqual(S.match_events((106,), (100,), 1000)[:3], (0, 1, 1))
        self.assertEqual(S.match_events((102,), (100,), 400)[:3], (1, 0, 0))
        self.assertEqual(S.match_events((103,), (100,), 400)[:3], (0, 1, 1))

    def test_no_double_credit(self):
        self.assertEqual(S.match_events((99, 100, 101), (100,), 1000)[:3], (1, 2, 0))

    def test_latency_rule_is_not_minimum_latency_claim(self):
        self.assertEqual(S.match_events((0, 100), (90,), 20000), (1, 1, 0, (-90,)))

    def test_invalid_interval_cannot_bridge_match(self):
        public = {'clock_hz': 4000, 'start_tick': 0, 'end_tick': 200,
                  'optical_rate_hz': 1000, 'cell_id': 'invented'}
        gold = {'valid_intervals': ((0, 100), (101, 200)), 'spikes': (110,)}
        row, _ = S.score_movie((90,), gold, public)
        self.assertEqual((row['tp'], row['fp'], row['fn']), (0, 1, 1))
        self.assertEqual(row['valid_duration_fraction'], 199 / 200)


class CompletePanel(unittest.TestCase):
    def setUp(self): self.public, self.pred, self.gold = fixture()

    def grade(self): return S.grade(self.public, self.pred, lambda: self.gold)

    def refuse_before_private(self):
        def forbidden(): self.fail('Private gold opened after invalid panel')
        result = S.grade(self.public, self.pred, forbidden)
        self.assertEqual(result['status'], 'invalid_submission'); self.assertEqual(result['private_reference_loads'], 0)

    def test_complete_twelve_cells_seven_animals_four_roles(self):
        calls = []
        result = S.grade(self.public, self.pred, lambda: (calls.append(1), self.gold)[1])
        self.assertEqual(calls, [1]); self.assertEqual(result['private_reference_loads'], 1)
        for role in S.ROLES:
            rows = result['roles'][role]
            self.assertEqual(len(rows['cells']), 12); self.assertEqual(len(rows['animals']), 7)
            self.assertTrue(all(a['equal_cell_f1'] == 1 for a in rows['animals'].values()))
            self.assertEqual(rows['sampling_rate_strata']['400']['movie_count'], 6)
            self.assertEqual(rows['sampling_rate_strata']['1000']['movie_count'], 6)
        self.assertFalse(result['scientific_qualified'])
        self.assertFalse(result['mapping_and_clock_authenticity_established_by_this_code'])

    def test_cross_tile_match_counted_once(self):
        for role in S.ROLES:
            self.pred['roles'][role]['tiles']['t0a'] = []
            self.pred['roles'][role]['tiles']['t0b'] = [4010, 6500]
        row = self.grade()['roles']['candidate']['movies']['m0']
        self.assertEqual((row['tp'], row['fp'], row['fn']), (2, 0, 0))
        self.assertEqual(row['matched_latency_mean_ms'], 2.5)

    def test_empty_empty_not_perfect(self):
        for row in self.gold['movies'].values(): row['spikes'] = []
        for role in S.ROLES:
            for tile in self.pred['roles'][role]['tiles']: self.pred['roles'][role]['tiles'][tile] = []
        result = self.grade()['roles']['candidate']
        self.assertIsNone(result['cells']['c0']['f1'])
        self.assertEqual(result['cells']['c0']['false_events_per_minute'], 0)
        self.assertIsNone(result['animals']['a0']['equal_cell_f1'])

    def test_no_spike_false_alarm_has_real_burden(self):
        self.gold['movies']['m0']['spikes'] = []
        self.pred['roles']['candidate']['tiles']['t0b'] = []
        row = self.grade()['roles']['candidate']['movies']['m0']
        self.assertEqual(row['f1'], 0); self.assertEqual(row['fp'], 1)
        self.assertEqual(row['false_events_per_minute'], 30)
        self.assertIsNone(row['recall'])

    def test_zero_valid_duration_retained_unscorable(self):
        self.gold['movies']['m0'] = {'valid_intervals': [], 'spikes': []}
        row = self.grade()['roles']['candidate']['movies']['m0']
        self.assertEqual(row['support_disposition'], 'unscorable')
        self.assertEqual(row['predictions_outside_valid_support'], 2)
        self.assertIsNone(row['f1']); self.assertIsNone(row['false_events_per_minute'])

    def test_equal_cell_animal_weighting_not_pooled_events(self):
        # a0 has c0 and c7. c0 is wrong, c7 correct: equal-cell F1 is exactly .5.
        self.pred['roles']['candidate']['tiles']['t0a'] = [3000]
        self.pred['roles']['candidate']['tiles']['t0b'] = [5000]
        row = self.grade()['roles']['candidate']['animals']['a0']
        self.assertEqual(row['equal_cell_f1'], .5); self.assertEqual(row['cell_count'], 2)

    def test_movie_counts_aggregate_before_cell_f1(self):
        row = copy.deepcopy(self.public['movies']['m0'])
        row['tiles'][0]['tile_id'] = 'extra_a'; row['tiles'][1]['tile_id'] = 'extra_b'
        self.public['movies']['extra'] = row
        self.gold['movies']['m0']['spikes'] = [3990]
        self.gold['movies']['extra'] = {'valid_intervals': [[0, 8000]], 'spikes': [1000, 2000, 3000]}
        for role in S.ROLES:
            self.pred['roles'][role]['tiles']['t0b'] = []
            self.pred['roles'][role]['tiles']['extra_a'] = []; self.pred['roles'][role]['tiles']['extra_b'] = []
        self.pred['public_sha256'] = self.gold['public_sha256'] = S.identity(self.public)
        self.assertEqual(self.grade()['roles']['candidate']['cells']['c0']['f1'], .4)

    def test_negative_candidate_baseline_contrast_retained(self):
        for tile, ticks in self.pred['roles']['candidate']['tiles'].items():
            self.pred['roles']['candidate']['tiles'][tile] = [t - 100 for t in ticks]
        row = self.grade()['contrasts']['optical_mad']['candidate_minus_baseline_animal_f1']
        self.assertTrue(all(x == -1 for x in row.values()))

    def test_late_final_role_invalid_no_gold(self):
        self.pred['roles']['metadata_rate']['tiles']['t11b'] = [True]
        self.refuse_before_private()

    def test_missing_final_tile_no_gold(self):
        del self.pred['roles']['metadata_rate']['tiles']['t11b']; self.refuse_before_private()

    def test_missing_comparator_no_gold(self):
        del self.pred['roles']['optical_matched_filter']; self.refuse_before_private()

    def test_duplicate_event_no_gold(self):
        self.pred['roles']['candidate']['tiles']['t0a'] = [3990, 3990]; self.refuse_before_private()

    def test_halo_event_outside_core_no_gold(self):
        self.pred['roles']['candidate']['tiles']['t0a'] = [4000]; self.refuse_before_private()

    def test_reordered_event_no_gold(self):
        self.pred['roles']['candidate']['tiles']['t0a'] = [3000, 2000]; self.refuse_before_private()

    def test_float_tick_no_gold(self):
        self.pred['roles']['candidate']['tiles']['t0a'] = [3990.0]; self.refuse_before_private()

    def test_source_identity_changed_no_gold(self):
        self.pred['public_sha256'] = '0' * 64; self.refuse_before_private()

    def test_query_cell_in_training_rejected(self):
        self.gold['outer_folds']['f0']['train_cells'].append('c0')
        with self.assertRaisesRegex(S.ReferenceError, 'training/query separation'): self.grade()

    def test_shared_animal_different_fold_rejected(self):
        self.public['movies']['m7']['fold_id'] = 'f1'
        self.pred['public_sha256'] = self.gold['public_sha256'] = S.identity(self.public)
        with self.assertRaisesRegex(S.ReferenceError, 'animal fold'): self.grade()

    def test_unresolved_six_title_groups_not_accepted_as_animals(self):
        self.gold['cell_to_animal']['c6'] = 'a0'
        with self.assertRaisesRegex(S.ReferenceError, 'seven resolved'): self.grade()

    def test_private_event_in_ambiguous_interval_rejected(self):
        self.gold['movies']['m0']['valid_intervals'] = [[0, 1000]]
        with self.assertRaisesRegex(S.ReferenceError, 'declared valid'): self.grade()

    def test_adjacent_valid_intervals_do_not_create_fake_boundary(self):
        self.gold['movies']['m0']['valid_intervals'] = [[0, 4000], [4000, 8000]]
        self.pred['roles']['candidate']['tiles']['t0a'] = []
        self.pred['roles']['candidate']['tiles']['t0b'] = [4010, 6500]
        self.assertEqual(self.grade()['roles']['candidate']['movies']['m0']['tp'], 2)

    def test_complete_prediction_snapshot_precedes_callback(self):
        def mutate_candidate():
            self.pred['roles']['candidate']['tiles']['t0a'].clear()
            self.public['movies']['m0']['end_tick'] = 1
            return self.gold
        result = S.grade(self.public, self.pred, mutate_candidate)
        self.assertEqual(result['roles']['candidate']['movies']['m0']['tp'], 2)

    def test_missing_cell_cannot_be_complete_cohort(self):
        del self.public['movies']['m0']
        with self.assertRaises(S.ContractError): self.grade()

    def test_gap_or_overlap_in_cores_rejected(self):
        self.public['movies']['m0']['tiles'][1]['start_tick'] += 1
        with self.assertRaisesRegex(S.ContractError, 'contiguous'): self.grade()

    def test_clock_must_represent_native_frame_grid_exactly(self):
        self.public['movies']['m0']['clock_hz'] = 999
        with self.assertRaisesRegex(S.ContractError, 'clock grid'): self.grade()

    def test_reference_failure_is_operational_not_false_zero_reads(self):
        def unavailable(): raise OSError('invented inaccessible gold')
        with self.assertRaises(OSError): S.grade(self.public, self.pred, unavailable)

    def test_gold_cannot_score_missing_optical_signal(self):
        self.public['movies']['m0']['optical_valid_intervals'] = [[0, 2000]]
        self.pred['public_sha256'] = self.gold['public_sha256'] = S.identity(self.public)
        with self.assertRaisesRegex(S.ReferenceError, 'within optical validity'): self.grade()

    def test_gold_interval_cannot_bridge_optical_gap(self):
        self.public['movies']['m0']['optical_valid_intervals'] = [[0, 4000], [4001, 8000]]
        self.pred['public_sha256'] = self.gold['public_sha256'] = S.identity(self.public)
        with self.assertRaisesRegex(S.ReferenceError, 'within optical validity'): self.grade()

    def test_failed_extraction_stays_in_full_roster(self):
        self.public['movies']['m0']['input_disposition'] = 'optical_extraction_failed'
        self.public['movies']['m0']['optical_valid_intervals'] = []
        self.gold['movies']['m0'] = {'valid_intervals': [], 'spikes': []}
        self.pred['public_sha256'] = self.gold['public_sha256'] = S.identity(self.public)
        rows = self.grade()['roles']['candidate']
        self.assertEqual(len(rows['cells']), 12); self.assertEqual(len(rows['movies']), 12)
        self.assertEqual(rows['movies']['m0']['input_disposition'], 'optical_extraction_failed')
        self.assertEqual(rows['movies']['m0']['support_disposition'], 'unscorable')
        self.assertIsNone(rows['animals']['a0']['equal_cell_f1'])


if __name__ == '__main__': unittest.main(verbosity=2)
