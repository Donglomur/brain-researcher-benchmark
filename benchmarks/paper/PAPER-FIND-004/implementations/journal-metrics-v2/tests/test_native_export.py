"""Generated native-shaped records only; no source fits, arrays or models."""
import copy
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "journal_native_export", Path(__file__).resolve().parents[1] / "metrics.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture(folds=5, pseudo_id=-1):
    target = [.2, .8] * 125
    universe = set(range(250))
    tests = [[i for i in range(250) if i % folds == fold] for fold in range(folds)]
    trains = [sorted(universe - set(test)) for test in tests]
    fits = [{"target": [[x] for x in target], "predictions_test": [[x] for x in target],
             "scores_test_full": 1., "idxes_train": copy.deepcopy(trains),
             "idxes_test": copy.deepcopy(tests), "pseudo_id": pseudo_id,
             "run_id": run, "n_folds": 999} for run in range(10)]
    return fits, [f"original-trial-{i}" for i in range(250)]


def export(fits, ids, modality="ephys", pseudo_id=-1):
    return m.export_native_draw(fits, ordered_trial_ids=ids,
                               modality=modality, pseudo_id=pseudo_id)


class NativeDrawExport(unittest.TestCase):
    def test_modality_specific_real_and_thousandth_null_roundtrip(self):
        for modality, folds, pseudo in (("ephys", 5, -1), ("wfi", 50, 1000)):
            fits, ids = fixture(folds, pseudo)
            draw = export(fits, ids, modality, pseudo)
            self.assertEqual(draw["pseudo_id"], pseudo)
            self.assertEqual(set(draw["runs"][0]["test_fold"]), set(range(folds)))
            self.assertEqual(m.score_draw(draw, ids, modality)["median_run_r2"], 1.)

    def test_fold_scalar_cannot_masquerade_as_actual_journal_partition(self):
        for modality, actual, advertised in (("ephys", 50, 5), ("wfi", 5, 50)):
            fits, ids = fixture(actual)
            for fit in fits:
                fit["n_folds"] = advertised
            with self.assertRaisesRegex(m.MetricError, "actual native outer fold"):
                export(fits, ids, modality)

    def test_training_leakage_or_duplicate_training_indices_rejected(self):
        for leaked in (True, False):
            fits, ids = fixture()
            fit = fits[0]
            fit["idxes_train"][0].append(
                fit["idxes_test"][0][0] if leaked else fit["idxes_train"][0][0])
            with self.assertRaises(m.MetricError):
                export(fits, ids)

    def test_missing_or_multiply_held_out_trial_rejected(self):
        for missing in (True, False):
            fits, ids = fixture()
            fit = fits[0]
            if missing:
                fit["idxes_test"][4].pop()
            else:
                fit["idxes_test"][4].append(fit["idxes_test"][0][0])
            fit["idxes_train"][4] = sorted(set(range(250)) - set(fit["idxes_test"][4]))
            with self.assertRaises(m.MetricError):
                export(fits, ids)

    def test_balanced_complete_partition_is_required(self):
        fits, ids = fixture()
        fit = fits[0]
        moved = fit["idxes_test"][0].pop()
        fit["idxes_test"][1].append(moved)
        for fold in (0, 1):
            fit["idxes_train"][fold] = sorted(set(range(250)) - set(fit["idxes_test"][fold]))
        with self.assertRaisesRegex(m.MetricError, "balanced"):
            export(fits, ids)

    def test_targets_cannot_change_between_repeats(self):
        fits, ids = fixture()
        fits[1]["target"][0][0] = .3
        with self.assertRaisesRegex(m.MetricError, "target changes"):
            export(fits, ids)

    def test_reported_score_is_checked_against_actual_prediction_arithmetic(self):
        fits, ids = fixture()
        fits[0]["scores_test_full"] = .5
        with self.assertRaisesRegex(m.MetricError, "reported score disagrees"):
            export(fits, ids)
        fits[0]["scores_test_full"] = True
        with self.assertRaisesRegex(m.MetricError, "finite number"):
            export(fits, ids)

    def test_non_scalar_or_nonfinite_native_values_are_not_flattened(self):
        for key, value in (("predictions_test", .2),
                           ("predictions_test", [.2, .8]),
                           ("predictions_test", [float("nan")]),
                           ("target", [1.1])):
            fits, ids = fixture()
            fits[0][key][0] = value
            with self.assertRaises(m.MetricError):
                export(fits, ids)

    def test_exact_ten_unique_runs_and_matching_draw_required(self):
        for change in ("missing", "duplicate", "wrong_draw", "boolean_run"):
            fits, ids = fixture()
            if change == "missing":
                fits.pop()
            elif change == "duplicate":
                fits[9]["run_id"] = 0
            elif change == "wrong_draw":
                fits[9]["pseudo_id"] = 1
            else:
                fits[9]["run_id"] = True
            with self.assertRaises(m.MetricError):
                export(fits, ids)

    def test_original_trial_ids_must_be_explicit_unique_and_complete(self):
        fits, ids = fixture()
        for bad in (ids[:-1], ids[:-1] + [ids[0]], list(range(250))):
            with self.assertRaises(m.MetricError):
                export(fits, bad)

    def test_export_does_not_alias_mutable_native_inputs(self):
        fits, ids = fixture()
        draw = export(fits, ids)
        expected = copy.deepcopy(draw)
        fits[0]["target"][0][0] = .9
        fits[0]["predictions_test"][0][0] = 9.
        fits[0]["idxes_test"][0].clear()
        ids[0] = "changed"
        self.assertEqual(draw, expected)

    def test_numpy_like_trusted_values_and_wrong_modalities(self):
        class Array:
            def __init__(self, values):
                self.values = values
            def tolist(self):
                return self.values

        class Integer:
            def __init__(self, value):
                self.value = value
            def item(self):
                return self.value

        fits, ids = fixture()
        for fit in fits:
            for field in ("target", "predictions_test", "idxes_train", "idxes_test"):
                fit[field] = Array(fit[field])
            fit["run_id"] = Integer(fit["run_id"])
            fit["pseudo_id"] = Integer(fit["pseudo_id"])
        self.assertEqual(len(export(fits, ids)["runs"]), 10)
        for bad in ("unknown", ["ephys"]):
            with self.assertRaisesRegex(m.MetricError, "unsupported modality"):
                export(fits, ids, bad)


if __name__ == "__main__":
    unittest.main()
