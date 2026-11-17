"""Small generated metadata/callback fixtures only; no authentic packet access."""

from copy import deepcopy
from fractions import Fraction
import unittest

from observations import ObservationAdapter, ObservationError, VISIBLE_FIELDS


def cases():
    result = []
    for asset, animal, regions, starts in (
        ('asset-a', 'animal-a', (('MGv', 3), ('MGd', 5)), (-5., -4.25)),
        ('asset-b', 'animal-b', (('SG', 7),), (20., 21.125)),
    ):
        for row, start in enumerate(starts):
            for region, count in regions:
                result.append({
                    'case_id': f'{asset}:{row}:{region}', 'asset_id': asset, 'animal_id': animal,
                    'source_trial_row': row, 'source_trial_id': 100 + row * 7,
                    'trial_start_seconds': start, 'trial_stop_seconds': start + .0001,
                    'region': region, 'source_cluster_count': count,
                })
    return result


class Projection:
    def __init__(self, metadata):
        self.metadata = {case['case_id']: dict(case) for case in metadata}
        self.calls = []
        self.returned = []

    def __call__(self, case_id, *, released_case_id):
        self.calls.append((case_id, released_case_id))
        case = self.metadata[case_id]
        value = {'case': {field: case[field] for field in VISIBLE_FIELDS},
                 'history_rates': [float(Fraction(i * 1000, case['source_cluster_count']))
                                   for i in range(100)]}
        self.returned.append(value)
        return value


class ObservationTests(unittest.TestCase):
    def test_metadata_construction_and_timing_view_never_read_history(self):
        def prohibited(*args, **kwargs):
            raise AssertionError('Timing view accessed history values')
        adapter = ObservationAdapter(list(reversed(cases())), prohibited)
        self.assertEqual(adapter.keys(), (('asset-a', 0), ('asset-a', 1), ('asset-b', 0), ('asset-b', 1)))
        group = adapter.group_cases(('asset-a', 1))
        self.assertEqual([case['region'] for case in group], ['MGd', 'MGv'])
        self.assertTrue(all(set(case) == set(VISIBLE_FIELDS) for case in group))
        observations = adapter.observations('asset-a', 1, view='timing')
        self.assertTrue(all(set(item) == {'case', 'timing'} for item in observations))
        for item in observations:
            self.assertEqual(item['timing']['elapsed_since_first_click_seconds'], .75)
            self.assertEqual(item['timing']['previous_click_interval_seconds'], .75)
            self.assertEqual(set(item['timing']), {'click_duration_seconds',
                             'elapsed_since_first_click_seconds', 'previous_click_interval_seconds'})
            self.assertGreater(item['timing']['click_duration_seconds'], 0.)
        first = adapter.observations('asset-a', 0, view='timing')[0]
        self.assertEqual(first['timing']['elapsed_since_first_click_seconds'], 0.)
        self.assertIsNone(first['timing']['previous_click_interval_seconds'])

    def test_history_reads_only_current_group_and_preserves_exact_codec_rates(self):
        private = cases()
        projection = Projection(private)
        adapter = ObservationAdapter(private, projection)
        self.assertEqual(projection.calls, [])
        result = adapter.observations('asset-a', 1, view='timing_history')
        expected_ids = ['asset-a:1:MGd', 'asset-a:1:MGv']
        self.assertEqual(projection.calls, [(value, value) for value in expected_ids])
        for item, projected in zip(result, projection.returned):
            self.assertEqual(set(item), {'case', 'timing', 'history_rates'})
            self.assertEqual([value.hex() for value in item['history_rates']],
                             [value.hex() for value in projected['history_rates']])
            self.assertIsNot(item['history_rates'], projected['history_rates'])

    def test_returned_values_and_original_metadata_cannot_mutate_later_observations(self):
        private = cases()
        projection = Projection(private)
        adapter = ObservationAdapter(private, projection)
        private[0]['source_cluster_count'] = 999
        metadata = adapter.group_cases(('asset-a', 0))
        metadata[0]['region'] = 'changed'
        first = adapter.observations('asset-a', 0, view='timing')
        first[0]['case']['animal_id'] = 'changed'
        first[0]['timing']['elapsed_since_first_click_seconds'] = 100.
        again = adapter.observations('asset-a', 0, view='timing')
        self.assertEqual(again[0]['case']['region'], 'MGd')
        self.assertEqual(again[0]['case']['animal_id'], 'animal-a')
        self.assertEqual(again[0]['timing']['elapsed_since_first_click_seconds'], 0.)

    def test_missing_history_refuses_without_silent_view_downgrade(self):
        private = cases()
        normal = Projection(private)
        def missing_second(case_id, *, released_case_id):
            if case_id.endswith('MGv'):
                return None
            return normal(case_id, released_case_id=released_case_id)
        adapter = ObservationAdapter(private, missing_second)
        with self.assertRaises(ObservationError):
            adapter.observations('asset-a', 0, view='timing_history')
        def failed_callback(*args, **kwargs):
            raise RuntimeError('history unavailable')
        adapter = ObservationAdapter(private, failed_callback)
        with self.assertRaises(RuntimeError):
            adapter.observations('asset-a', 0, view='timing_history')

    def test_history_identity_and_float_schema_are_strict(self):
        mutations = [
            lambda p: p['case'].__setitem__('source_trial_row', True),
            lambda p: p['case'].__setitem__('source_cluster_count', 99),
            lambda p: p['case'].__setitem__('source_trial_id', 100),
            lambda p: p.__setitem__('response_rates', [0.] * 100),
            lambda p: p['history_rates'].pop(),
            lambda p: p['history_rates'].__setitem__(0, float('nan')),
            lambda p: p['history_rates'].__setitem__(0, float('inf')),
            lambda p: p['history_rates'].__setitem__(0, -1.),
            lambda p: p['history_rates'].__setitem__(0, 0),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                private = cases()
                normal = Projection(private)
                def changed(case_id, *, released_case_id):
                    value = normal(case_id, released_case_id=released_case_id)
                    mutate(value)
                    return value
                adapter = ObservationAdapter(private, changed)
                with self.assertRaises(ObservationError):
                    adapter.observations('asset-a', 1, view='timing_history')

    def test_incomplete_region_or_row_support_is_rejected_without_value_access(self):
        variants = []
        missing_region = cases()
        missing_region.pop(0)
        variants.append(missing_region)
        missing_zero = [case for case in cases() if not (case['asset_id'] == 'asset-a'
                                                        and case['source_trial_row'] == 0)]
        variants.append(missing_zero)
        for metadata in variants:
            with self.subTest(metadata=metadata):
                projection = Projection(metadata)
                with self.assertRaises(ObservationError):
                    ObservationAdapter(metadata, projection)
                self.assertEqual(projection.calls, [])

    def test_metadata_identity_denominator_and_chronology_conflicts_are_rejected(self):
        mutations = [
            lambda m: m.append(deepcopy(m[0])),
            lambda m: m[2].__setitem__('animal_id', 'other-animal'),
            lambda m: m[2].__setitem__('source_cluster_count', 4),
            lambda m: m[0].__setitem__('trial_start_seconds', float('inf')),
            lambda m: m[0].__setitem__('trial_stop_seconds', -5.),
            lambda m: m[0].__setitem__('source_trial_row', False),
            lambda m: m[0].__setitem__('region', ' '),
            lambda m: m[0].__setitem__('trial_start_seconds', -5.1),
            lambda m: [c.update(trial_start_seconds=-6., trial_stop_seconds=-5.9999)
                       for c in m if c['asset_id'] == 'asset-a' and c['source_trial_row'] == 1],
            lambda m: [c.update(source_trial_id=100) for c in m
                       if c['asset_id'] == 'asset-a' and c['source_trial_row'] == 1],
            lambda m: m[0].__setitem__('response_counts', [0] * 100),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                metadata = cases()
                mutate(metadata)
                projection = Projection(metadata)
                with self.assertRaises(ObservationError):
                    ObservationAdapter(metadata, projection)
                self.assertEqual(projection.calls, [])

    def test_invalid_requests_fail_before_callback(self):
        private = cases()
        projection = Projection(private)
        adapter = ObservationAdapter(private, projection)
        for asset, row, view in (('unknown', 0, 'timing_history'),
                                 ('asset-a', 2, 'timing_history'),
                                 ('asset-a', True, 'timing_history'),
                                 ('asset-a', 0, 'history_only')):
            with self.subTest(asset=asset, row=row, view=view):
                with self.assertRaises(ObservationError):
                    adapter.observations(asset, row, view=view)
        self.assertEqual(projection.calls, [])


if __name__ == '__main__':
    unittest.main()
