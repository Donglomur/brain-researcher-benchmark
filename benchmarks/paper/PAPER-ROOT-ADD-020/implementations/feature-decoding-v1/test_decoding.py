"""Generated software controls only; no measured neural inputs or model fits."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("paper020_feature_decoding", Path(__file__).with_name("decoding.py"))
d = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = d
spec.loader.exec_module(d)


def roster():
    return d.FaceRoster(tuple(f"unfamiliar-{i}" for i in range(1000)),
                        tuple(f"familiar-{i}" for i in range(36)))


def predictions(r, *, omit=None, wrong=None):
    for fold in reversed(range(1000)):
        if fold == omit:
            continue
        query = tuple(reversed((r.unfamiliar[fold],) + r.familiar))
        if fold == wrong:
            query = query[:-1] + (r.unfamiliar[(fold + 1) % 1000],)
        features = tuple((float(fold), float(r.all_faces.index(q)), 1.0) for q in query)
        yield d.FoldPrediction(fold, query, features)


class SourceScheduleTests(unittest.TestCase):
    def setUp(self):
        self.r = roster()

    def test_complete_original_schedule_and_no_query_targets(self):
        responses = {q: [float(i), 10.0] for i, q in enumerate(self.r.all_faces)}
        targets = {q: [float(i), 2.0, 3.0] for i, q in enumerate(self.r.unfamiliar)}
        source = d.FeatureDecodingInput(self.r, responses, targets)
        responses[self.r.unfamiliar[0]][0] = -123.0
        targets[self.r.unfamiliar[0]][0] = -456.0
        with self.assertRaises(TypeError):
            source.responses[self.r.unfamiliar[0]] = (3.0, 4.0)
        coverage = []
        for packet in source.folds():
            coverage.append(packet.held_out_id)
            self.assertEqual(len(packet.training_ids), 999)
            self.assertNotIn(packet.held_out_id, packet.training_ids)
            self.assertFalse(set(packet.training_ids) & set(self.r.familiar))
            self.assertEqual(packet.query_ids, (packet.held_out_id,) + self.r.familiar)
            self.assertEqual(len(packet.query_responses), 37)
            self.assertFalse(hasattr(packet, "query_features"))
            self.assertEqual(packet.query_responses[0][0], packet.fold)
            for identity, feature in zip(packet.training_ids, packet.training_features):
                self.assertEqual(feature[0], int(identity.split("-")[1]))
        self.assertEqual(tuple(coverage), self.r.unfamiliar)

    def test_identity_keyed_assembly_preserves_familiar_folds(self):
        result = d.assemble_predictions(self.r, predictions(self.r), 3)
        self.assertEqual(result.unfamiliar[17], (17.0, 17.0, 1.0))
        self.assertEqual(result.familiar_by_fold[17][4], (17.0, 1004.0, 1.0))
        self.assertEqual(result.familiar_by_fold[999][35], (999.0, 1035.0, 1.0))
        self.assertEqual(len(result.unfamiliar), 1000)
        self.assertEqual(len(result.familiar_by_fold), 1000)

    def test_missing_duplicate_and_misassigned_folds_refuse(self):
        with self.assertRaises(d.DecodingError):
            d.assemble_predictions(self.r, predictions(self.r, omit=7), 3)
        with self.assertRaises(d.DecodingError):
            d.assemble_predictions(self.r, predictions(self.r, wrong=7), 3)
        first = next(predictions(self.r))
        with self.assertRaises(d.DecodingError):
            d.assemble_predictions(self.r, [first, first], 3)

    def test_roster_and_output_values_refuse_silent_repairs(self):
        for unfamiliar in (self.r.unfamiliar[:-1], self.r.unfamiliar[:-1] + (self.r.unfamiliar[0],)):
            with self.assertRaises(d.DecodingError):
                d.FaceRoster(unfamiliar, self.r.familiar)
        first = next(predictions(self.r))
        for value in (float("nan"), float("inf"), True, 10**10000):
            rows = ((value, 1.0, 2.0),) + first.features[1:]
            with self.assertRaises(d.DecodingError):
                d.assemble_predictions(self.r, [d.FoldPrediction(first.fold, first.query_ids, rows)], 3)
        with self.assertRaises(d.DecodingError):
            d.assemble_predictions(self.r, [d.FoldPrediction(first.fold, first.query_ids[:-1], first.features[:-1])], 3)
        with self.assertRaises(d.DecodingError):
            d.assemble_predictions(self.r, [first], 20)

    def test_familiar_target_input_rejected(self):
        responses = {q: (0.0, 1.0) for q in self.r.all_faces}
        all_features = {q: (0.0, 1.0, 2.0) for q in self.r.all_faces}
        with self.assertRaises(d.DecodingError):
            d.FeatureDecodingInput(self.r, responses, all_features)
        del responses[self.r.familiar[0]]
        with self.assertRaises(d.DecodingError):
            d.FeatureDecodingInput(self.r, responses, {q: (0.0, 1.0, 2.0) for q in self.r.unfamiliar})

    def test_vector_correlation_known_independent_controls(self):
        # Centered cosine/Pearson: (-1,0,1) dot (-1,1,0) / (sqrt(2)*sqrt(2)) = 1/2.
        self.assertAlmostEqual(d.feature_correlation([0, 2, 1], [0, 1, 2]).value, 0.5)
        self.assertAlmostEqual(d.feature_correlation([10, 12, 14], [0, 1, 2]).value, 1.0)
        self.assertAlmostEqual(d.feature_correlation([14, 12, 10], [0, 1, 2]).value, -1.0)
        self.assertAlmostEqual(d.feature_correlation([1e308, 0, -1e308], [2, 0, -2]).value, 1.0)
        self.assertEqual(d.feature_correlation([1, 1, 1], [0, 1, 2]).state, "constant_decoded")
        self.assertEqual(d.feature_correlation([1, 2, 3], [0, 0, 0]).state, "constant_actual")
        self.assertIsNone(d.feature_correlation([1, 1, 1], [0, 0, 0]).value)

    def test_complete_scoring_keeps_faces_and_fold_dependence(self):
        actual = {q: (0.0, 1.0, 2.0) for q in self.r.all_faces}
        records = (d.FoldPrediction(i, (q,) + self.r.familiar,
                                   ((0.0, 2.0, 4.0),) + ((4.0, 2.0, 0.0),) * 36)
                   for i, q in enumerate(self.r.unfamiliar))
        result = d.assemble_predictions(self.r, records, 3)
        scores = d.score_feature_correlations(self.r, result, actual)
        self.assertEqual(len(scores.unfamiliar), 1000)
        self.assertTrue(all(math.isclose(s.value, 1.0) for s in scores.unfamiliar))
        self.assertEqual(len(scores.familiar_by_fold), 1000)
        self.assertTrue(all(len(fold) == 36 and all(math.isclose(s.value, -1.0) for s in fold)
                            for fold in scores.familiar_by_fold))
        self.assertFalse(hasattr(scores, "mean"))
        with self.assertRaises(d.DecodingError):
            d.score_feature_correlations(self.r, result, {q: actual[q] for q in self.r.unfamiliar})


if __name__ == "__main__":
    unittest.main(verbosity=2)
