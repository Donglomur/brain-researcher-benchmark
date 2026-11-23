"""Generated full-grid identity controls; no authentic data, fits or files."""
import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "journal_pairing_receipts", Path(__file__).resolve().parents[1] / "metrics.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def metadata():
    return {
        "modality": "ephys", "subject": "mouse", "eid": "session",
        "region": "VISp", "predictor": "neural", "n_features": 5,
        "trial_ids": [f"trial-{i}" for i in range(250)],
        "target_model": "optBay", "target": "pLeft",
        "input_manifest_sha256": "1" * 64,
        "target_generator_sha256": "2" * 64,
    }


def draws(meta, *, reverse=False, prediction_error=0., changed_target=False,
          changed_folds=False):
    target = [.2, .8] * 125
    prediction = [x + prediction_error for x in target]
    folds = [i % 5 for i in range(250)]
    order = [-1, *range(1, 1001)]
    if reverse:
        order.reverse()
    for draw_id in order:
        actual_target = target
        actual_folds = folds
        if changed_target and draw_id == 1000:
            actual_target = list(target)
            actual_target[0] = .3
        if changed_folds and draw_id == 1000:
            actual_folds = list(folds)
            actual_folds[0], actual_folds[1] = actual_folds[1], actual_folds[0]
        yield {
            "pseudo_id": draw_id, "trial_ids": meta["trial_ids"],
            "target": actual_target,
            "runs": [{"run_id": run, "prediction": prediction,
                      "test_fold": actual_folds} for run in range(10)],
        }


class PairedIdentityReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = metadata()
        cls.base = m.score_cell(cls.meta, draws(cls.meta))

    def test_declared_source_receipts_retained_without_metric_change(self):
        result = self.base
        for field in ("input_manifest_sha256", "target_generator_sha256"):
            self.assertEqual(result[field], self.meta[field])
        self.assertEqual((result["r2"], result["median_null_r2"],
                          result["corrected_r2"]), (1., 1., 0.))
        for private in ("trial_ids", "target", "runs", "prediction"):
            self.assertNotIn(private, result)

    def test_prediction_change_preserves_target_and_partition_receipts(self):
        changed = m.score_cell(self.meta, draws(self.meta, prediction_error=.1))
        for field in ("draw_targets_sha256", "draw_folds_sha256"):
            self.assertEqual(self.base[field], changed[field])
        self.assertNotEqual(self.base["draw_receipts_sha256"],
                            changed["draw_receipts_sha256"])
        self.assertAlmostEqual(changed["r2"], 8 / 9)

    def test_final_null_target_change_is_detected_without_changing_real_target(self):
        changed = m.score_cell(self.meta, draws(self.meta, changed_target=True))
        self.assertEqual(self.base["actual_target_sha256"], changed["actual_target_sha256"])
        self.assertEqual(self.base["draw_folds_sha256"], changed["draw_folds_sha256"])
        self.assertNotEqual(self.base["draw_targets_sha256"], changed["draw_targets_sha256"])

    def test_final_null_partition_change_is_detected_without_changing_real_folds(self):
        changed = m.score_cell(self.meta, draws(self.meta, changed_folds=True))
        self.assertEqual(self.base["actual_folds_sha256"], changed["actual_folds_sha256"])
        self.assertEqual(self.base["draw_targets_sha256"], changed["draw_targets_sha256"])
        self.assertNotEqual(self.base["draw_folds_sha256"], changed["draw_folds_sha256"])

    def test_arbitrary_input_draw_order_does_not_change_results(self):
        changed = m.score_cell(self.meta, draws(self.meta, reverse=True))
        self.assertEqual(self.base, changed)

    def test_receipts_use_explicit_draw_ids_in_complete_canonical_order(self):
        one = m.score_draw(next(draws(self.meta)), self.meta["trial_ids"], "ephys")
        for result_field, per_draw in (("draw_targets_sha256", "target_sha256"),
                                       ("draw_folds_sha256", "folds_sha256")):
            expected = m.digest([
                {"pseudo_id": draw_id, per_draw: one[per_draw]}
                for draw_id in [-1, *range(1, 1001)]])
            self.assertEqual(self.base[result_field], expected)


if __name__ == "__main__":
    unittest.main()
