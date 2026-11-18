import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fig3c_profiles", ROOT / "fig3c_profiles.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def row(model="train0_test1", sizes=None):
    sizes = sizes or [1] * 10
    support = "after" if model == "train0_test1" else "before"
    folds = [{"sample_ids": [f"{support}-{f}-{i}" for i in range(size)],
              "actual": [0.0] * size, "predicted": [0.0] * size}
             for f, size in enumerate(sizes)]
    shuffles = []
    for repeat in range(100):
        shuffled = copy.deepcopy(folds)
        for fold in shuffled:
            fold["predicted"] = [0.0 if repeat % 2 == 0 else math.pi] * len(fold["actual"])
        shuffles.append(shuffled)
    return {"animal": "GCAMP3", "day": 3, "cell_type": "rr", "model": model,
            "folds": folds, "shuffles": shuffles}


def panel():
    templates = {model: row(model) for model in m.MODELS}
    rows = []
    for animal in m.ANIMALS:
        for day in m.DAYS:
            for cell_type in m.CELL_TYPES:
                for model in m.MODELS:
                    item = dict(templates[model], animal=animal, day=day, cell_type=cell_type)
                    rows.append(item)
    return {"schema": m.SCHEMA, "source_commit": m.COMMIT,
            "preparation_sha256": "a" * 64, "fold_receipt_sha256": "b" * 64,
            "rows": rows}


class Fig3cTests(unittest.TestCase):
    def test_left_closed_right_open_and_missing_predictions(self):
        values = [-math.pi, m.EDGES[1], math.pi, None, 0.0]
        predicted = [-math.pi, m.EDGES[1], math.pi, 0.0, None]
        out = m.fold_profile(values, predicted)
        self.assertEqual(out["occupancy"][0:2], [1, 1])
        self.assertEqual(out["means"][0:2], [1.0, 1.0])
        self.assertEqual(out["occupancy"][22], 1)
        self.assertEqual(out["valid_predictions"][22], 0)
        self.assertTrue(math.isnan(out["means"][22]))
        self.assertEqual(out["missing_actual"], 1)
        self.assertEqual(out["excluded_positive_pi"], 1)

    def test_position_binning_uses_actual_not_prediction(self):
        out = m.fold_profile([0.0], [math.pi])
        self.assertEqual(out["occupancy"][22], 1)
        self.assertEqual(out["means"][22], -1.0)
        self.assertEqual(sum(out["occupancy"]), 1)

    def test_equal_fold_weighting_not_sample_pooling(self):
        data = row(sizes=[2] * 9 + [1])
        for index, fold in enumerate(data["folds"]):
            fold["predicted"] = [0.0 if index == 0 else math.pi] * len(fold["actual"])
        out = m.profile_row(data)
        self.assertAlmostEqual(out["real_mean_cosine"][22]["value"], -0.8)
        self.assertNotAlmostEqual(out["real_mean_cosine"][22]["value"], -15 / 19)
        self.assertEqual(out["real_valid_fold_counts"][22], 10)

    def test_repeat_population_sd_and_nan_bins(self):
        out = m.profile_row(row())
        self.assertEqual(out["shuffle_mean_cosine"][22], {"value": 0.0, "state": "finite"})
        self.assertEqual(out["shuffle_population_sd"][22], {"value": 1.0, "state": "finite"})
        self.assertEqual(out["zscore"][22], {"value": 1.0, "state": "finite"})
        self.assertEqual(out["zscore"][0], {"value": None, "state": "nan"})
        self.assertEqual(out["shuffle_valid_repeat_counts"][22], 100)

    def test_nanmean_retains_empty_fold_counts(self):
        data = row()
        for fold in data["folds"][1:]:
            fold["predicted"] = [None]
        out = m.profile_row(data)
        self.assertEqual(out["real_valid_fold_counts"][22], 1)
        self.assertEqual(out["real_mean_cosine"][22]["value"], 1.0)
        self.assertEqual(out["real_fold_occupancy"][9][22], 1)
        self.assertEqual(out["real_fold_valid_predictions"][9][22], 0)

    def test_zero_variance_preserves_infinity_and_zero_over_zero(self):
        data = row()
        data["shuffles"] = [copy.deepcopy(data["shuffles"][1]) for _ in range(100)]
        out = m.profile_row(data)
        self.assertEqual(out["zscore"][22]["state"], "positive_infinity")
        for fold in data["folds"]:
            fold["predicted"] = [math.pi]
        self.assertEqual(m.profile_row(data)["zscore"][22]["state"], "nan")
        data = row()
        for fold in data["folds"]:
            fold["predicted"] = [math.pi]
        data["shuffles"] = [copy.deepcopy(data["shuffles"][0]) for _ in range(100)]
        self.assertEqual(m.profile_row(data)["zscore"][22]["state"], "negative_infinity")

    def test_source_sem_uses_total_axis_not_number_finite(self):
        result = m.cohort_statistics([0.0, 2.0] + [None] * 9)
        self.assertEqual(result["mean"]["value"], 1.0)
        self.assertAlmostEqual(result["sem"]["value"], 1 / math.sqrt(10))
        self.assertEqual(result["finite_mice"], 2)
        self.assertEqual(result["total_mice"], 11)

    def test_source_infinity_is_not_dropped_like_nan(self):
        result = m.cohort_statistics([math.inf] + [None] * 10)
        self.assertEqual(result["mean"]["state"], "positive_infinity")
        self.assertEqual(result["sem"]["state"], "nan")
        self.assertEqual(result["non_nan_mice"], 1)
        self.assertEqual(result["finite_mice"], 0)
        both = m.cohort_statistics([math.inf, -math.inf] + [0.0] * 9)
        self.assertEqual(both["mean"]["state"], "nan")

    def test_shuffle_target_or_order_change_rejects(self):
        data = row()
        data["shuffles"][0][0]["actual"] = [0.1]
        with self.assertRaisesRegex(m.InputError, "shuffle changed"):
            m.profile_row(data)
        data = row()
        data["shuffles"][0][0]["sample_ids"] = ["not-the-source-observation"]
        with self.assertRaisesRegex(m.InputError, "shuffle changed"):
            m.profile_row(data)

    def test_duplicate_fold_support_and_missing_repeats_reject(self):
        data = row()
        data["folds"][1]["sample_ids"] = data["folds"][0]["sample_ids"]
        with self.assertRaisesRegex(m.InputError, "duplicate sample"):
            m.profile_row(data)
        data = row()
        data["shuffles"].pop()
        with self.assertRaisesRegex(m.InputError, "all100"):
            m.profile_row(data)

    def test_wrong_source_fold_size_order_rejects(self):
        data = row(sizes=[1] + [2] * 9)
        with self.assertRaisesRegex(m.InputError, "array_split"):
            m.profile_row(data)

    def test_invalid_angle_bool_infinity_and_unexpected_field_reject(self):
        for bad in (True, math.inf, -math.inf, 4.0, "0"):
            with self.subTest(bad=bad), self.assertRaises(m.InputError):
                m.fold_profile([bad], [0.0])
        data = row()
        data["candidate_score"] = 1
        with self.assertRaises(m.InputError):
            m.profile_row(data)

    def test_complete_condition_membership_fails_before_arithmetic(self):
        data = panel()
        data["rows"][-1] = data["rows"][0]
        with self.assertRaisesRegex(m.InputError, "duplicate or missing"):
            m.score_panel(data)
        data["rows"].pop()
        with self.assertRaisesRegex(m.InputError, "all11mice"):
            m.score_panel(data)

    def test_full_generated_cohort_and_source_export(self):
        # Complete declared roster, with deliberately tiny generated support.
        # This exercises full composition, not authentic recordings or fitting.
        result = m.score_panel(panel())
        self.assertEqual(len(result["rows"]), 462)
        self.assertEqual(len(result["cohort_profiles"]), 42)
        self.assertEqual(len(result["figure3c_source_export"]), 66)
        self.assertEqual({x["switch"] for x in result["figure3c_source_export"]}, {1, 7})
        self.assertEqual({x["model"] for x in result["figure3c_source_export"]}, {"train0_test1"})
        self.assertEqual(result["cohort_profiles"][0]["bins"][22]["mean"]["value"], 1.0)
        self.assertEqual(result["cohort_profiles"][0]["bins"][22]["sem"]["value"], 0.0)
        self.assertIsNone(result["paper_win"])
        self.assertEqual(result["scientific_readiness"], "unknown")

    def test_json_reader_rejects_duplicate_and_nonfinite_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for body in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(body)
                with self.assertRaises(m.InputError):
                    m.read_json(path)
        # Tagged nonfinite output remains strict JSON.
        json.dumps([m.tagged(math.nan), m.tagged(math.inf)], allow_nan=False)


if __name__ == "__main__":
    unittest.main()
