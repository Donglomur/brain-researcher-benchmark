"""Generated endpoint controls; no source recordings, native libraries or model calls."""
import json
import importlib.util
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / 'programme-source/curated-retrospective-design-v1/implementation-v1/program'
sys.path[:0] = [str(HERE), str(ORIGINAL)]
import grade
from contracts import DAY_COUNTS, ENDPOINTS, FAMILIES, PEOPLE, cells
from endpoint_metrics import finite_mean, paired_day_score, person_score
from selection_worker import choose
from contracts import CONFIGS


class Array:
    """Tiny in-memory reader stand-in, exercising the real protected evaluate loop."""
    dtype = SimpleNamespace(str='<f8')

    def __init__(self, values, columns=None):
        self.values = values
        self.shape = (len(values),) if columns is None else (len(values), columns)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            rows, column = key
            return [row[column] for row in self.values[rows]]
        return self.values[key]


class Meter:
    def __init__(self):
        self.reservations = {}

    def reserve(self, key, count):
        self.reservations[key] = self.reservations.get(key, 0) + count

    def tick(self):
        pass


def generated_panel():
    modules = ['core', 'T1', 'D']
    roots = {'packet': '/generated-neural049', 'targets': '/generated-neural049/private',
             'output': '/generated-neural049/candidates', 'reference': '/generated-neural049/references'}
    arrays = {}; days = []; table = {}; candidates = {}; references = {}; selections = {}
    for person, count in zip(PEOPLE, DAY_COUNTS):
        table[person] = []
        for day in range(1, count + 1):
            # Different person/event counts expose incorrect event-pooled macro weighting.
            n = 0 if (person == '01' and day == 1) else int(person) % 3 + 1
            ids = [f'generated-{person}-{day}-{i}' for i in range(n)]
            table[person].append({'day': day, 'ids': ids})
            labels = {}
            for column, endpoint in enumerate(ENDPOINTS):
                path = f'private/{person}-{day}-{endpoint}.npy'
                values = [float(day * (column + 1))] * n
                arrays[str(Path(roots['packet']) / path)] = Array(values)
                labels[endpoint] = {'path': path, 'bytes': 1, 'sha256': '0' * 64,
                                    'shape': [n], 'dtype': '<f8'}
                for view in ('C', 'N', 'NC', 'NC_D'):
                    selections[('r1', endpoint, view, person, day)] = {'strongest': 'B' if day % 2 else 'R'}
                    for family in FAMILIES:
                        prefix = f'{roots["reference"]}/{person}-{day}-{endpoint}-{view}-{family}'
                        raw = [180. if endpoint == 'angle' else -2.] * n
                        projected = [90. if endpoint == 'angle' else 0.] * n
                        arrays[prefix + '-raw'] = Array(raw)
                        arrays[prefix + '-projected'] = Array(projected)
                        key = ('reference_outer_predict', endpoint, view, person, day, day, 'generated', family, 'query')
                        references[key] = {'raw': {'path': prefix + '-raw'},
                                           'projected': {'path': prefix + '-projected'}}
            days.append({'person': person, 'day': day, 'ids': ids, 'labels': labels})
            for cell in cells(modules):
                prefix = f'{roots["output"]}/{person}-{day}-{cell["id"]}'
                arrays[prefix + '-raw'] = Array([[180., -2., -2.] for _ in ids], 3)
                arrays[prefix + '-projected'] = Array([[90., 0., 0.] for _ in ids], 3)
                candidates[(cell['id'], person, day)] = {'ids': ids, 'raw': {'path': prefix + '-raw'},
                                                        'array': {'path': prefix + '-projected'}}
    admitted = {'public_output_admission_complete': True, 'protected_target_bodies_read': False,
                'limits': Meter(), 'table': table, 'packet': {'manifest': {'days': days}},
                'candidate_rows': candidates, 'reference_rows': references, 'selections': selections,
                'producer': {'census': {'source_days': 55, 'people': 12, 'kind': 'generated_control'}}}
    return {'roots': roots, 'modules': modules}, admitted, arrays


def evaluate_generated(a, admitted, arrays):
    # File custody, full reference fitting/selection and bootstrap execution are not claimed by this control.
    with patch.object(grade, 'load', side_effect=lambda desc, roots, limits: arrays[desc['path']]), \
         patch.object(grade, 'verify_selection_values'), \
         patch.object(grade, 'intervals', return_value={'control': 'not_executed'}):
        return grade.evaluate(a, admitted, Meter())


def selection_scores(n=3, sse=10.):
    return {configuration: {'sse': sse, 'n': n} for configuration in CONFIGS}


def predecessor_choose(scores):
    spec = importlib.util.spec_from_file_location('neural049_predecessor_selection', ORIGINAL / 'selection_worker.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.choose(scores)


class SelectionControls(unittest.TestCase):
    def test_division_tie_must_not_replace_minimum_sse_configuration(self):
        scores = selection_scores()
        scores['R00']['sse'] = 1.5000000000000004
        scores['R01']['sse'] = 1.5000000000000002
        self.assertGreater(scores['R00']['sse'], scores['R01']['sse'])
        self.assertEqual(scores['R00']['sse'] / 3, scores['R01']['sse'] / 3)
        self.assertEqual(predecessor_choose(scores)[0]['R'], 'R00')
        self.assertEqual(choose(scores)[0]['R'], 'R01')

    def test_division_tie_must_not_replace_minimum_sse_family(self):
        scores = selection_scores()
        scores['R00']['sse'] = 1.5000000000000004
        scores['B00']['sse'] = 1.5000000000000002
        self.assertEqual(predecessor_choose(scores)[1], 'R')
        self.assertEqual(choose(scores)[1], 'B')

    def test_exact_sse_ties_keep_declared_order(self):
        selected, strongest = choose(selection_scores())
        self.assertEqual(selected, {'R': 'R00', 'B': 'B00', 'T': 'T00'})
        self.assertEqual(strongest, 'R')

    def test_unequal_support_cannot_select_normalized_error(self):
        scores = selection_scores()
        scores['R01'] = {'sse': 1., 'n': 1}
        with self.assertRaisesRegex(ValueError, 'identical complete inner support'):
            choose(scores)

    def test_all_configurations_required(self):
        scores = selection_scores()
        del scores['T07']
        with self.assertRaisesRegex(ValueError, 'all 25 configurations'):
            choose(scores)

    def test_invalid_inner_counts_refused(self):
        for count in (0, -1, True, 3.):
            with self.subTest(count=count), self.assertRaises(ValueError):
                choose(selection_scores(n=count))

    def test_invalid_inner_sse_refused(self):
        for sse in (-1., float('nan'), float('inf'), True, 10 ** 400):
            with self.subTest(sse=repr(sse)), self.assertRaises(ValueError):
                choose(selection_scores(sse=sse))


class EndpointControls(unittest.TestCase):
    def test_folded_angle_is_not_circular_heading(self):
        score = person_score([-89., 89.], [89., -89.])
        self.assertEqual(score['sse'], 2 * 178 ** 2)
        self.assertEqual(score['r2'], -3.)

    def test_projection_and_units(self):
        angle = paired_day_score([0., 90.], [180., -180.], [90., -90.], 'angle')
        self.assertEqual(angle['projection_changed'], 2)
        self.assertEqual(angle['raw']['sse'], 180 ** 2 + 270 ** 2)
        self.assertEqual(angle['projected']['sse'], 90 ** 2 + 180 ** 2)
        for endpoint in ('magnitude', 'speed'):
            value = paired_day_score([1., 2.], [-1., 3.], [0., 3.], endpoint)
            self.assertEqual(value['projection_changed'], 1)
            self.assertEqual(value['raw']['sse'], 5.)
            self.assertEqual(value['projected']['sse'], 2.)

    def test_wrong_projection_or_labels_cannot_be_repaired(self):
        for args in (([91.], [100.], [90.], 'angle'), ([-1.], [0.], [0.], 'magnitude'),
                     ([0.], [180.], [89.], 'angle'), ([0.], [math.inf], [90.], 'angle')):
            with self.assertRaises(ValueError):
                paired_day_score(*args)

    def test_numerical_failures_cannot_emit_nonfinite_r2(self):
        for y, p in (([0., 1e-150], [1e154, 0.]), ([0., 1.], [1e308, 1e308])):
            row = person_score(y, p)
            self.assertEqual(row['status'], 'undefined_numerical_failure')
            self.assertIsNone(row['r2'])
            rows = {person: row for person in PEOPLE}
            self.assertIsNone(grade.macro(rows)['value'])
            json.dumps(rows, allow_nan=False)

    def test_nonzero_underflowed_error_is_not_exact_zero(self):
        row = person_score([0., 1.], [1e-200, 1.])
        self.assertEqual(row['status'], 'undefined_numerical_failure')
        self.assertIsNone(row['sse'])
        self.assertIsNone(row['r2'])
        self.assertIsNone(grade.macro({person: row for person in PEOPLE})['value'])

    def test_nonconstant_tiny_support_is_numerical_failure_not_constant(self):
        row = person_score([-1e-200, 1e-200], [-1e-200, 1e-200])
        self.assertEqual(row['sse'], 0.)
        self.assertIsNone(row['sst'])
        self.assertEqual(row['status'], 'undefined_numerical_failure')
        detail = paired_day_score([0., 1.], [1e-200, 1.], [1e-200, 1.], 'magnitude')
        self.assertEqual(detail['projected']['status'], 'undefined_numerical_failure')

    def test_underflowed_terms_can_sum_to_representable_error(self):
        tiny = 2. ** -538
        row = person_score([0., 0., 0., 0., 1.], [tiny, tiny, tiny, tiny, 1.])
        self.assertEqual(row['sse'], 2. ** -1074)
        self.assertEqual(row['status'], 'defined')
        self.assertEqual(row['n'], 5)

    def test_large_finite_mean_and_constant_support(self):
        self.assertEqual(finite_mean([1e308, 1e308]), 1e308)
        row = person_score([1e308, 1e308], [1e308, 1e308])
        self.assertEqual(row['target_mean'], 1e308)
        self.assertEqual(row['sse'], 0.)
        self.assertEqual(row['status'], 'undefined_constant_person')

    def test_event_pooling_precedes_equal_person_mean(self):
        first = person_score([1., 1., 3., 3.], [0., 0., 0., 0.])
        self.assertEqual(first['r2'], -4.)
        self.assertIsNone(person_score([1., 1.], [0., 0.])['r2'])
        rows = {person: person_score([0., 1.], [0., 1.]) for person in PEOPLE}
        rows['01'] = first
        self.assertAlmostEqual(grade.macro(rows)['value'], 7. / 12.)
        del rows['12']
        with self.assertRaises(ValueError):
            grade.macro(rows)

    def test_full55_evaluate_keeps_raw_projected_and_empty_days(self):
        a, admitted, arrays = generated_panel()
        result = evaluate_generated(a, admitted, arrays)
        self.assertTrue(admitted['protected_target_bodies_read'])
        self.assertEqual(result['primary_prediction_form'], 'projected')
        for column, endpoint in enumerate(ENDPOINTS):
            self.assertEqual(len(result['scores'][endpoint]), 27)
            for model, people in result['day_diagnostics'][endpoint].items():
                self.assertEqual(sum(len(person['days']) for person in people.values()), 55)
                expected_person_r2 = []
                for person, count in zip(PEOPLE, DAY_COUNTS):
                    n = int(person) % 3 + 1
                    y = [float(day * (column + 1)) for day in range(1, count + 1)
                         for _ in range(0 if person == '01' and day == 1 else n)]
                    mean = sum(y) / len(y)
                    self.assertEqual(result['scores'][endpoint][model]['people'][person]['target_mean'], mean)
                    if model != 'train_mean':
                        prediction = 90. if endpoint == 'angle' else 0.
                        expected_person_r2.append(1. - sum((v - prediction) ** 2 for v in y) / sum((v - mean) ** 2 for v in y))
                        self.assertEqual(people[person]['projection_changed'], len(y))
                        self.assertLess(result['raw_scores'][endpoint][model]['people'][person]['r2'],
                                        result['scores'][endpoint][model]['people'][person]['r2'])
                if model != 'train_mean':
                    self.assertAlmostEqual(result['scores'][endpoint][model]['value'], sum(expected_person_r2) / 12.)
            empty = result['day_diagnostics'][endpoint]['F_NC']['01']['days'][0]
            self.assertEqual(empty['n'], 0)
            self.assertIsNone(empty['raw']['r2'])
            self.assertEqual(empty['raw']['status'], 'undefined_empty_day')
        json.dumps(result, allow_nan=False)

    def test_unadmitted_evaluation_reads_no_targets(self):
        a, admitted, arrays = generated_panel()
        admitted['public_output_admission_complete'] = False
        with patch.object(grade, 'load') as reader:
            with self.assertRaises(ValueError):
                grade.evaluate(a, admitted, Meter())
            reader.assert_not_called()

    def test_missing_raw_has_no_projected_fallback(self):
        a, admitted, arrays = generated_panel()
        del admitted['candidate_rows'][('F_C', '01', 1)]['raw']
        with self.assertRaises(KeyError):
            evaluate_generated(a, admitted, arrays)

    def test_changed_raw_projection_relation_fails_evaluation(self):
        a, admitted, arrays = generated_panel()
        desc = admitted['candidate_rows'][('I_NC', '02', 1)]['raw']
        arrays[desc['path']].values[0][0] = 0.
        with self.assertRaisesRegex(ValueError, 'raw/projected prediction relation'):
            evaluate_generated(a, admitted, arrays)


if __name__ == '__main__':
    unittest.main(verbosity=2)
