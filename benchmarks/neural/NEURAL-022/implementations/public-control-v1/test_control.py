"""Generated software controls only; no authentic input or fitting workload."""
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('public_control', Path(__file__).with_name('control.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
import held_scorer
import numpy as np


class PublicControl(unittest.TestCase):
    def setUp(self):
        self.training = {
            'ids': np.array([f'{i + 1:024x}' for i in range(141)], dtype='<U24'),
            'counts': np.ones((141, 390), dtype='<i8'),
            'velocity': np.array([[i % 8 + i // 8, -2 * (i % 8) + 3 * (i // 8)]
                                  for i in range(141)], dtype='<f8'),
            'directions': np.array([(i % 8) * 45 for i in range(141)], dtype='<i8'),
        }
        self.rows = []
        for mode, counts in [('passive', [5] * 8), ('active', [7] * 4 + [6] * 4)]:
            for direction, n in zip(c.DIRECTIONS, counts):
                for _ in range(n):
                    self.rows.append({'id': f'{len(self.rows) + 1001:024x}',
                                      'mode': mode, 'direction': direction})
        self.public = {'schema': 'neural022_public_cases_v1', 'cases': self.rows}
        self.query = {'ids': np.array([r['id'] for r in self.rows], dtype='<U24'),
                      'counts': np.ones((92, 390), dtype='<i8'),
                      'directions': np.array([r['direction'] for r in self.rows], dtype='<i8'),
                      'modes': np.array([r['mode'] for r in self.rows], dtype='<U7')}
        self.training_raw = c.io.encoded_npz(self.training)
        self.query_raw = c.io.encoded_npz(self.query)

    def model(self, control='active_direction'):
        return c.fit(self.training_raw, control)

    def test_direction_arithmetic_independent_of_query_mode(self):
        result = c.predict(self.model(), self.query_raw, self.public)
        self.assertEqual(len(result['predictions']), 92)
        for row, context in zip(result['predictions'], self.rows):
            direction = context['direction'] // 45
            n = 18 if direction < 5 else 17
            expected = [direction + (n - 1) / 2, -2 * direction + 3 * (n - 1) / 2]
            np.testing.assert_allclose(row['velocity'], expected, rtol=0, atol=1e-13)

    def test_weighted_training_mean_and_zero(self):
        # 17 complete direction cycles followed by directions 0..4 at rank17.
        expected = [(17 * 28 + 8 * 136 + 10 + 5 * 17) / 141,
                    (-2 * (17 * 28 + 10) + 3 * (8 * 136 + 5 * 17)) / 141]
        for control in ('active_mean', 'zero'):
            result = c.predict(self.model(control), self.query_raw, self.public)
            for row in result['predictions']:
                np.testing.assert_allclose(row['velocity'], expected if control == 'active_mean' else [0, 0],
                                           rtol=0, atol=1e-13)

    def test_neural_counts_do_not_change_direction_control(self):
        model = self.model()
        result = c.predict(model, self.query_raw, self.public)
        self.query['counts'][:] = np.arange(390)
        self.assertEqual(c.predict(model, c.io.encoded_npz(self.query), self.public), result)
        self.training['counts'][:] = 0
        changed = c.fit(c.io.encoded_npz(self.training), 'active_direction')
        self.assertEqual(changed['parameters'], model['parameters'])
        self.assertNotEqual(changed['training'], model['training'])

    def test_existing_scorer_compatibility(self):
        raw = c.io.encoded_json(c.predict(self.model('zero'), self.query_raw, self.public))
        private = {'ids': [r['id'] for r in self.rows], 'velocity': [[1., -2.]] * 92,
                   'references': {m: [[0., 0.]] * 92 for m in c.candidate.METHODS}}
        expected = {'losses': {mode: {m: 5. for m in c.candidate.METHODS}
                               for mode in ('passive', 'active')},
                    'primary_active_minus_passive_neural_loss': 0.}
        result = c.candidate.evaluate(raw, self.public, lambda: private, held_scorer.score, expected)
        self.assertEqual(result['status'], 'scored_exposed_transfer_candidate')
        self.assertEqual(result['primary_score'], 5.)
        self.assertEqual(len(result['direction_strata']), 16)

    def test_target_or_source_coordinate_members_rejected(self):
        for key in ('velocity', 'source_rows', 'passive_training'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.predict(self.model(), c.io.encoded_npz(dict(self.query, **{key: np.zeros(92)})), self.public)
        with self.assertRaises(ValueError):
            c.fit(c.io.encoded_npz(dict(self.training, source_rows=np.arange(141))), 'active_mean')

    def test_identity_context_and_coverage_counterexamples(self):
        for field, index, value in [('ids', 91, self.query['ids'][0]),
                                    ('ids', 91, self.training['ids'][0]),
                                    ('directions', 91, 0), ('modes', 91, 'passive')]:
            query = {k: v.copy() for k, v in self.query.items()}
            query[field][index] = value
            public = copy.deepcopy(self.public)
            if field == 'ids' and value == self.training['ids'][0]:
                public['cases'][91]['id'] = str(value)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                c.predict(self.model(), c.io.encoded_npz(query), public)
        public = copy.deepcopy(self.public)
        public['cases'].reverse()
        with self.assertRaises(ValueError):
            c.predict(self.model(), self.query_raw, public)
        public = copy.deepcopy(self.public)
        for row in public['cases']:
            if row['direction'] == 315:
                row['direction'] = 0
        with self.assertRaises(ValueError):
            c.predict(self.model(), self.query_raw, public)

    def test_complete_numeric_observations_required(self):
        for key, value in [('counts', self.query['counts'].astype('<f8')),
                           ('counts', self.query['counts'][:, :-1]),
                           ('counts', -self.query['counts'])]:
            with self.subTest(shape=value.shape, dtype=value.dtype), self.assertRaises(ValueError):
                c.predict(self.model(), c.io.encoded_npz(dict(self.query, **{key: value})), self.public)
        for field, value in [('velocity', np.full((141, 2), np.nan)),
                             ('directions', np.zeros(141, dtype='<i8')),
                             ('counts', -self.training['counts'])]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                c.fit(c.io.encoded_npz(dict(self.training, **{field: value})), 'active_mean')

    def test_frozen_boolean_parameters_or_extra_fields_rejected(self):
        frozen = self.model()
        frozen['parameters']['templates'][0][0] = True
        with self.assertRaises(ValueError):
            c.predict(frozen, self.query_raw, self.public)
        frozen = self.model('zero')
        frozen['parameters']['target'] = [0., 0.]
        with self.assertRaises(ValueError):
            c.predict(frozen, self.query_raw, self.public)

    def test_finite_mean_does_not_overflow_due_to_sum(self):
        self.training['velocity'][:] = [1e308, -1e308]
        frozen = c.fit(c.io.encoded_npz(self.training), 'active_mean')
        np.testing.assert_allclose(frozen['parameters']['mean'], [1e308, -1e308], rtol=1e-14)

    def test_fit_then_predict_cli_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            training = root / 'training.npz'; training.write_bytes(self.training_raw)
            query = root / 'queries.npz'; query.write_bytes(self.query_raw)
            cases = root / 'cases.json'; cases.write_bytes(c.io.encoded_json(self.public))
            frozen = root / 'frozen.json'; output = root / 'predictions.json'
            with redirect_stdout(io.StringIO()):
                self.assertEqual(c.main(['fit', '--control', 'active_direction', '--training', str(training),
                                         '--training-sha256', c.io.pin(self.training_raw)['sha256'],
                                         '--out', str(frozen)]), 0)
                args = ['predict', '--out', str(output)]
                for name, path in [('frozen', frozen), ('queries', query), ('cases', cases)]:
                    args += ['--' + name, str(path), '--' + name + '-sha256', c.io.pin(path.read_bytes())['sha256']]
                self.assertEqual(c.main(args), 0)
                self.assertEqual(len(json.loads(output.read_bytes())['predictions']), 92)
                with self.assertRaises(FileExistsError):
                    c.main(args)

    def test_bad_freeze_hash_prevents_query_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            frozen = Path(directory).resolve() / 'frozen.json'
            frozen.write_bytes(c.io.encoded_json(self.model()))
            reads = []
            original = c.capture
            def capture(*args):
                reads.append(args[0])
                return original(*args)
            with patch.object(c, 'capture', side_effect=capture), self.assertRaises(ValueError):
                c.main(['predict', '--frozen', str(frozen), '--frozen-sha256', '0' * 64,
                        '--queries', '/missing-query', '--queries-sha256', '0' * 64,
                        '--cases', '/missing-cases', '--cases-sha256', '0' * 64,
                        '--out', '/unused-output'])
            self.assertEqual(reads, [frozen])

    def test_public_file_pin_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / 'training.npz'; path.write_bytes(self.training_raw)
            with self.assertRaises(ValueError):
                c.capture(path, '0' * 64, 600000)
            alias = root / 'alias.npz'; alias.symlink_to(path)
            with self.assertRaises(ValueError):
                c.capture(alias, c.io.pin(self.training_raw)['sha256'], 600000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
