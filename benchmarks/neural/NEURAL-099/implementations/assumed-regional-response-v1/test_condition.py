"""Generated scientific boundary checks; no source neural arrays are opened."""
from copy import deepcopy
import unittest

from condition import (ChronologicalQuery, declared_folds, prepare_asset,
                       project, score_selected, selected_protocol, validate_protocol)


def support():
    return {'asset_id': 'asset-generated', 'source_subject_id': 'source-animal',
            'source_trial_rows': 2,
            'regions': [{'region': 'MGv', 'cluster_ids': [10, 11], 'cluster_count': 2},
                        {'region': 'SG', 'cluster_ids': [12], 'cluster_count': 1}]}


def trials():
    return [{'source_trial_id': 101, 'start_seconds': 1.0, 'stop_seconds': 1.0001},
            {'source_trial_id': 109, 'start_seconds': 1.5, 'stop_seconds': 1.5001}]


def spikes():
    return {10: [.9, .999, 1., 1.001, 1.099999, 1.1, 1.4, 1.499, 1.5, 1.599999, 1.6],
            11: [1., 1.05], 12: []}


def prepared(**changes):
    args = {'animal_id': 'animal-generated', 'protocol': selected_protocol(),
            'trials': trials(), 'spikes_by_cluster': spikes()}
    args.update(changes)
    return prepare_asset(support(), **args)


class ConditionTests(unittest.TestCase):
    def test_timing_inspection_rows_join_without_replacing_source_identifiers(self):
        from inspect_clicks import validate_trial_rows
        checked = validate_trial_rows([-1, 109], [1., 1.5], [1.0001, 1.5001], expected_rows=2)
        rows = [{'source_trial_id': row['source_trial_id'], 'start_seconds': row['start_time'],
                 'stop_seconds': row['stop_time']} for row in checked['rows']]
        packet = prepared(trials=rows)
        self.assertEqual([row['source_trial_id'] for row in packet['private_source_trial_provenance']],
                         [-1, -1, 109, 109])
        self.assertEqual([row['source_trial_row'] for row in packet['cases']], [0, 0, 1, 1])

    def test_selected_score_wrapper_preserves_nominal_units_and_5ms_average(self):
        case = prepared()['cases'][0]
        gold = [{'case': case, 'counts': [2] + [0]*99}]
        result = score_selected([case], [{'case_id': case['case_id'], 'rates': [0.]*100}], gold)
        self.assertEqual(result['bins_per_case'], 100)
        self.assertEqual(result['native_resolution']['animal_macro_mse'], {'value': 10000., 'state': 'finite'})
        self.assertEqual(result['native_resolution']['animal_macro_mae'], {'value': 10., 'state': 'finite'})
        self.assertEqual(result['coarsened_resolution']['bins_per_case'], 20)
        self.assertEqual(result['coarsened_resolution']['animal_macro_mse'], {'value': 2000., 'state': 'finite'})

    def test_half_open_counts_denominators_and_source_row_provenance(self):
        packet = prepared()
        self.assertEqual(len(packet['cases']), 4)
        gold = packet['private_gold'][0]
        self.assertEqual(gold['case']['source_cluster_count'], 2)
        self.assertEqual(gold['counts'][0], 2)
        self.assertEqual(gold['counts'][1], 1)
        self.assertEqual(gold['counts'][50], 1)
        self.assertEqual(gold['counts'][99], 1)
        self.assertEqual(sum(gold['counts']), 5)
        self.assertEqual(sum(packet['private_gold'][1]['counts']), 0)
        self.assertEqual(packet['permitted_observations'][0]['history_rates'][0], 500)
        self.assertEqual(packet['permitted_observations'][0]['history_rates'][99], 500)
        self.assertEqual([row['source_trial_id'] for row in packet['private_source_trial_provenance']],
                         [101, 101, 109, 109])
        self.assertFalse(packet['verified_physiological_coverage'])
        self.assertFalse(packet['source_authentication_performed_by_this_function'])

    def test_known_gap_rejects_instead_of_zero_filling(self):
        full = {key: [[.9, 1.6]] for key in spikes()}
        self.assertTrue(prepared(known_observation_intervals=full)['known_observation_intervals_checked'])
        full[11] = [[.9, 1.03], [1.04, 1.6]]
        with self.assertRaisesRegex(ValueError, 'gap intersects'):
            prepared(known_observation_intervals=full)

    def test_missing_intervals_are_explicit_assumption_not_automatic_exclusion(self):
        packet = prepared()
        self.assertFalse(packet['known_observation_intervals_checked'])
        self.assertIn('explicit benchmark assumption', packet['observation_assumption'])

    def test_negative_reference_times_not_arbitrary_recording_bounds(self):
        shifted_trials = trials()
        for row in shifted_trials:
            row['start_seconds'] -= 1
            row['stop_seconds'] -= 1
        shifted_spikes = {key: [value-1 for value in values] for key, values in spikes().items()}
        packet = prepared(trials=shifted_trials, spikes_by_cluster=shifted_spikes)
        self.assertEqual(len(packet['cases']), 4)
        self.assertFalse(packet['verified_physiological_coverage'])

    def test_cross_trial_history_cannot_disclose_scored_responses(self):
        rows = trials()
        rows[1] = {'source_trial_id': 109, 'start_seconds': 1.15, 'stop_seconds': 1.1501}
        with self.assertRaisesRegex(ValueError, 'histories intersect'):
            prepared(trials=rows)

    def test_all_rows_and_exact_eligible_clusters_required(self):
        with self.assertRaisesRegex(ValueError, 'All declared'):
            prepared(trials=trials()[:1])
        changed = spikes()
        changed[999] = []
        with self.assertRaisesRegex(ValueError, 'exactly the eligible'):
            prepared(spikes_by_cluster=changed)
        changed = support()
        changed['regions'][0]['cluster_count'] = 0
        with self.assertRaises(ValueError):
            prepare_asset(changed, animal_id='a', protocol=selected_protocol(),
                          trials=trials(), spikes_by_cluster=spikes())

    def test_projection_has_matched_content_and_no_private_fields(self):
        observation = prepared()['permitted_observations'][0]
        timing = project(observation, view='timing')
        history = project(observation, view='timing_history')
        self.assertEqual(timing, {key: value for key, value in history.items() if key != 'history_rates'})
        self.assertNotIn('counts', repr(history))
        self.assertNotIn('source_start_seconds', repr(history))
        contaminated = deepcopy(observation)
        contaminated['timing']['target'] = [42]
        with self.assertRaisesRegex(ValueError, 'Exact permitted timing'):
            project(contaminated, view='timing')
        contaminated = deepcopy(observation)
        contaminated['case']['target'] = [42]
        with self.assertRaises(ValueError):
            project(contaminated, view='timing_history')

    def test_chronological_predictions_lock_before_next_history(self):
        records = prepared()['permitted_observations']
        cursor = ChronologicalQuery(records, view='timing_history',
                                    edges_seconds=[i/1000 for i in range(101)])
        first = cursor.current()
        self.assertEqual({row['case']['source_trial_row'] for row in first}, {0})
        first[0]['history_rates'][0] = -100
        self.assertEqual(cursor.current()[0]['history_rates'][0], 500)
        predictions = [{'case_id': row['case']['case_id'], 'rates': [0.]*100} for row in cursor.current()]
        with self.assertRaises(ValueError):
            cursor.commit(predictions[:1])
        self.assertEqual(cursor.current()[0]['case']['source_trial_row'], 0)
        with self.assertRaisesRegex(ValueError, 'until all trials lock'):
            cursor.locked_predictions()
        self.assertFalse(cursor.commit(predictions)['complete'])
        second = cursor.current()
        self.assertEqual({row['case']['source_trial_row'] for row in second}, {1})
        self.assertTrue(cursor.commit([{'case_id': row['case']['case_id'], 'rates': [0.]*100}
                                       for row in second])['complete'])
        self.assertIsNone(cursor.current())
        self.assertEqual(len(cursor.locked_predictions()), 4)
        with self.assertRaises(ValueError):
            cursor.commit([])

    def test_reverse_rows_and_duplicate_regions_do_not_make_sequential_queries(self):
        records = prepared()['permitted_observations']
        with self.assertRaises(ValueError):
            ChronologicalQuery(records[2:] + records[:2], view='timing',
                               edges_seconds=[i/1000 for i in range(101)])
        with self.assertRaises(ValueError):
            ChronologicalQuery(records + records[:1], view='timing',
                               edges_seconds=[i/1000 for i in range(101)])

    def test_animal_state_reset_and_multisession_chronology_are_not_assumed(self):
        first = prepared()['permitted_observations']
        other = deepcopy(first)
        for row in other:
            row['case']['case_id'] = 'other-' + row['case']['case_id']
            row['case']['asset_id'] = 'other-asset'
            row['case']['animal_id'] = 'other-animal'
        with self.assertRaisesRegex(ValueError, 'fresh query state'):
            ChronologicalQuery(first + other, view='timing', edges_seconds=[i/1000 for i in range(101)])
        for row in other:
            row['case']['animal_id'] = 'animal-generated'
        with self.assertRaisesRegex(ValueError, 'separately qualified source schedule'):
            ChronologicalQuery(first + other, view='timing', edges_seconds=[i/1000 for i in range(101)])

    def test_alias_groups_stay_together_and_are_queried_once(self):
        subjects = ['s1', 'alias-s1', 's2', 's3', 's4', 's5', 's6']
        mapping = {subject: subject for subject in subjects}
        mapping['alias-s1'] = 's1'
        review = {'source_to_animal': mapping, 'evidence': ['generated identity fixture'],
                  'status': 'declared_source_identity_only'}
        result = declared_folds(subjects, biological_identity_review=review)
        queried = [animal for fold in result['folds'] for animal in fold['query_animals']]
        self.assertEqual(sorted(queried), ['s1', 's2', 's3', 's4', 's5', 's6'])
        for fold in result['folds']:
            query, val, train = map(set, (fold['query_animals'], fold['validation_animals'],
                                         fold['initial_train_animals']))
            self.assertFalse(query & val or query & train or val & train)
            self.assertEqual(set(fold['final_refit_animals']), val | train)
        self.assertFalse(result['biological_independence_verified'])
        reversed_result = declared_folds(list(reversed(subjects)), biological_identity_review=review)
        self.assertEqual(result['folds'], reversed_result['folds'])

    def test_protocol_cannot_silently_change_endpoint_or_qualification(self):
        changed = selected_protocol()
        changed['response_edges_microseconds'][0] = 5000
        with self.assertRaises(ValueError):
            validate_protocol(changed)
        records = prepared()['permitted_observations']
        with self.assertRaisesRegex(ValueError, '100 one-millisecond'):
            ChronologicalQuery(records, view='timing', edges_seconds=[0., .1])
        with self.assertRaisesRegex(ValueError, '100 one-millisecond'):
            ChronologicalQuery(records, view='timing', edges_seconds=[i/2000 for i in range(101)])
        changed = selected_protocol()
        changed['response_edges_microseconds'][0] = False
        with self.assertRaises(ValueError):
            validate_protocol(changed)
        changed = selected_protocol()
        changed['actual_timing_qualified'] = True
        with self.assertRaises(ValueError):
            validate_protocol(changed)


if __name__ == '__main__':
    unittest.main()
