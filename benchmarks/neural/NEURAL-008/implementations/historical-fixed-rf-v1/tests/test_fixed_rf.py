"""Generated controls for the unchanged historical comparator; no RF fits."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / 'fixed_rf.py'
spec = importlib.util.spec_from_file_location('historical_neural008_rf', SOURCE)
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)


def archive(**values):
    stream = io.BytesIO()
    np.savez(stream, **values)
    return stream.getvalue()


def ids(case, count):
    return np.asarray([f'{case}/{i:05d}' for i in range(count)])


class MemoryFile:
    """Only a generated in-memory file fixture, never an authentic data path."""
    def __init__(self, body):
        self.body = body

    def read_bytes(self):
        return self.body


class Controls(unittest.TestCase):
    def test_fit_uses_only_masked_training_rows_for_both_widths(self):
        y = np.array([-1, 0, 2, 4, -1, 1], dtype=np.int8)
        mask = y >= 0
        for width in (15, 21):
            x = np.arange(len(y) * width, dtype=np.float64).reshape(len(y), width)
            recorded = {}
            class Model:
                def fit(self, actual_x, actual_y):
                    recorded['x'], recorded['y'] = actual_x.copy(), actual_y.copy()
            def factory(**parameters):
                recorded['parameters'] = parameters
                return Model()
            with self.subTest(width=width):
                rf.fit_one(factory, x, y, mask)
                np.testing.assert_array_equal(recorded['x'], x[mask])
                np.testing.assert_array_equal(recorded['y'], y[mask])
                self.assertEqual(recorded['parameters'], rf.PARAMETERS)

    def test_wrong_mask_stops_before_factory_or_fit(self):
        called = []
        with self.assertRaisesRegex(ValueError, 'unknown mask'):
            rf.fit_one(lambda **kw: called.append(kw), np.zeros((3, 15)),
                       np.array([-1, 0, 1]), np.array([True, True, True]))
        self.assertEqual(called, [])

    def test_missing_training_classes_keep_fixed_five_class_output(self):
        model = types.SimpleNamespace(classes_=np.array([0, 2, 4]),
                                      predict_proba=lambda x: np.array([[0.2, 0.3, 0.5]]))
        out = rf.probabilities(model, np.zeros((1, 15)))
        np.testing.assert_array_equal(out, [[0.2, 0.0, 0.3, 0.0, 0.5]])

    def test_invalid_probability_outputs_are_not_repaired(self):
        for values in (np.array([[np.nan, 0.0]]), np.array([[0.8, 0.8]]),
                       np.array([[-0.1, 1.1]]), np.ones((2, 2))):
            model = types.SimpleNamespace(classes_=np.array([0, 4]), predict_proba=lambda x: values)
            with self.subTest(values=repr(values)), self.assertRaises(ValueError):
                rf.probabilities(model, np.zeros((1, 15)))

    def test_invalid_classes_are_rejected(self):
        for classes in (np.array([0, 0]), np.array([0, 5]), np.array([0.0, 4.0])):
            model = types.SimpleNamespace(classes_=classes, predict_proba=lambda x: np.array([[0.5, 0.5]]))
            with self.subTest(classes=repr(classes)), self.assertRaises(ValueError):
                rf.probabilities(model, np.zeros((1, 15)))

    def test_complete_ordered_feature_view_required(self):
        case, count = 'development-002', 2670
        value = {'epoch_id': ids(case, count), 'X': np.zeros((count, 15), dtype=np.float64)}
        rf.checked_view(case, count, 15, value)
        value['epoch_id'] = value['epoch_id'][::-1]
        with self.assertRaises(ValueError):
            rf.checked_view(case, count, 15, value)

    def test_extra_archive_member_is_rejected(self):
        body = archive(epoch_id=np.asarray(['train-001/00000']), X=np.zeros((1, 15)),
                       unexpected_target=np.array([4]))
        with self.assertRaisesRegex(ValueError, 'hidden members'):
            rf.arrays(MemoryFile(body), ('epoch_id', 'X'))

    def test_whole_original_roster_main_with_nonfitting_double(self):
        """Exercise actual main orchestration with all8 generated people, no disk data."""
        for width, arm in ((15, 'EEG_clock'), (21, 'EEG_EOG_clock')):
            with self.subTest(arm=arm):
                files, rows, captured, fitted, queried = {}, [], {}, [], []
                for position, (case, count) in enumerate(zip(rf.TRAIN + rf.DEV, rf.COUNTS)):
                    epoch_id = ids(case, count)
                    # Different constants make accidental development fitting visible.
                    x = np.full((count, width), position + 1, dtype=np.float64)
                    body = archive(epoch_id=epoch_id, X=x)
                    name = case + '_features.npz'
                    files[name] = body
                    rows.append({'filename': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
                    if case in rf.TRAIN:
                        stage = np.arange(count, dtype=np.int16) % 5
                        if case == rf.TRAIN[0]:
                            stage[:79] = -1
                        body = archive(epoch_id=epoch_id, stage=stage, score_mask=stage >= 0)
                        name = case + '_labels.npz'
                        files[name] = body
                        rows.append({'filename': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
                manifest = {'arm': arm, 'feature_count': width, 'classes': list(rf.CLASSES),
                            'training': [{'case_id': c, 'epochs': n} for c, n in zip(rf.TRAIN, rf.COUNTS[:6])],
                            'development': [{'case_id': c, 'epochs': n} for c, n in zip(rf.DEV, rf.COUNTS[6:])],
                            'files': rows}
                files['manifest.json'] = json.dumps(manifest).encode()

                class FixturePath:
                    def __init__(self, name):
                        self.name = str(name)
                    def __truediv__(self, name):
                        return FixturePath(str(name))
                    def read_bytes(self):
                        return files[self.name]
                    def read_text(self):
                        return files[self.name].decode()
                    def iterdir(self):
                        return [FixturePath(name) for name in files]

                class NonfittingRF:
                    classes_ = np.arange(5)
                    def __init__(self, **parameters):
                        self.parameters = parameters
                    def fit(self, x, y):
                        fitted.append((x.shape, set(np.unique(x).tolist()), len(y), self.parameters))
                    def predict_proba(self, x):
                        queried.append((x.shape, set(np.unique(x).tolist())))
                        return np.full((len(x), 5), 0.2)

                fake_sklearn = types.ModuleType('sklearn')
                fake_sklearn.__version__ = 'generated-nonfitting-double'
                fake_ensemble = types.ModuleType('sklearn.ensemble')
                fake_ensemble.RandomForestClassifier = NonfittingRF
                def capture_output(path, **arrays):
                    self.assertEqual(path, '/output/predictions.npz')
                    self.assertFalse(captured)
                    captured.update({name: array.copy() for name, array in arrays.items()})
                with patch.object(rf, 'Path', FixturePath), patch.object(rf.np, 'savez', capture_output), \
                     patch.dict(sys.modules, {'sklearn': fake_sklearn, 'sklearn.ensemble': fake_ensemble}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    rf.main()
                self.assertEqual(len(fitted), 1)
                self.assertEqual(fitted[0][:3], ((16211, width), {1., 2., 3., 4., 5., 6.}, 16211))
                self.assertEqual(fitted[0][3], rf.PARAMETERS)
                self.assertEqual(queried, [((2780, width), {7.}), ((2670, width), {8.})])
                self.assertEqual(set(captured), {'class_order', *[case + suffix for case in rf.DEV
                                                                 for suffix in ('__epoch_id', '__probabilities')]})
                for case, count in zip(rf.DEV, rf.COUNTS[6:]):
                    np.testing.assert_array_equal(captured[case + '__epoch_id'], ids(case, count))
                    self.assertEqual(captured[case + '__probabilities'].shape, (count, 5))


if __name__ == '__main__':
    unittest.main(verbosity=2)
