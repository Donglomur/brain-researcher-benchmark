"""Generated controls for finite journal reductions; no authentic fits or data."""
import importlib.util
import math
import unittest
from fractions import Fraction
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "metrics.py"
SPEC = importlib.util.spec_from_file_location("prior_finite_reductions", MODULE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def metadata(eid="session-1"):
    return {"modality": "ephys", "subject": "mouse-1", "eid": eid,
            "region": "VISp", "predictor": "neural", "n_features": 5,
            "trial_ids": [f"trial-{i}" for i in range(250)],
            "target_model": "optBay", "target": "pLeft",
            "input_manifest_sha256": "1" * 64,
            "target_generator_sha256": "2" * 64}


def extreme_draw(meta, draw_id=-1):
    target = [0.0, 0.001] * 125
    prediction = [5e150] * 250
    return {"pseudo_id": draw_id, "trial_ids": meta["trial_ids"], "target": target,
            "runs": [{"run_id": i, "prediction": prediction,
                      "test_fold": [j % 5 for j in range(250)]} for i in range(10)]}


def summary(eid, r2, null):
    meta = metadata(eid)
    return {**{k: meta[k] for k in ("modality", "subject", "eid", "region", "predictor")},
            "r2": r2, "median_null_r2": null, "corrected_r2": r2 - null,
            "trial_ids_sha256": "3" * 64, "actual_target_sha256": "4" * 64,
            "actual_folds_sha256": "5" * 64, "actual_predictions_sha256": "6" * 64}


class FiniteJournalReductions(unittest.TestCase):
    def test_ten_finite_run_scores_keep_their_common_median(self):
        meta = metadata()
        draw = extreme_draw(meta)
        common = m.pooled_r2(draw["target"], draw["runs"][0]["prediction"])
        self.assertTrue(math.isfinite(common))
        self.assertLess(common, -9e307)
        observed = m.score_draw(draw, meta["trial_ids"], "ephys")
        self.assertEqual(observed["median_run_r2"], common)

    def test_complete_real_plus_thousand_nulls_remains_finite(self):
        meta = metadata()
        draw = extreme_draw(meta)
        common = m.pooled_r2(draw["target"], draw["runs"][0]["prediction"])
        draws = ({**draw, "pseudo_id": i} for i in [-1, *range(1, 1001)])
        observed = m.score_cell(meta, draws)
        self.assertEqual(observed["n_runs"], 10)
        self.assertEqual(observed["n_pseudosessions"], 1000)
        self.assertEqual(observed["r2"], common)
        self.assertEqual(observed["median_null_r2"], common)
        self.assertEqual(observed["corrected_r2"], 0.0)

    def test_complete_region_mean_survives_intermediate_sum_overflow(self):
        rows = [summary("s1", -1e308, 0), summary("s2", -1e308, 0)]
        region = m.summarize_panel(rows, rows)["regional_effects"][0]
        self.assertEqual(region["n_sessions"], 2)
        self.assertEqual(region["mean_session_r2"], -1e308)
        self.assertEqual(region["mean_session_corrected_r2"], -1e308)

    def test_corrected_mean_keeps_cancellation_after_sum_overflow(self):
        rows = [summary("s1", 0, -1e308), summary("s2", 0, -1e308),
                summary("s3", -1e308, 0)]
        expected = float(Fraction(1e308) / 3)
        region = m.summarize_panel(rows, rows)["regional_effects"][0]
        self.assertEqual(region["mean_session_corrected_r2"], expected)
        self.assertEqual(region["mean_session_r2"], -expected)

    def test_ordinary_metrics_and_original_admission_remain_unchanged(self):
        meta = metadata()
        target = [0.2, 0.8] * 125
        draw = {"pseudo_id": -1, "trial_ids": meta["trial_ids"], "target": target,
                "runs": [{"run_id": i, "prediction": [x + (0 if i < 6 else .3) for x in target],
                          "test_fold": [j % 5 for j in range(250)]} for i in range(10)]}
        self.assertEqual(m.score_draw(draw, meta["trial_ids"], "ephys")["median_run_r2"], 1.0)
        rows = [summary("s1", .5, .25), summary("s2", .75, .125)]
        region = m.summarize_panel(rows, rows)["regional_effects"][0]
        self.assertEqual(region["mean_session_r2"], .625)
        self.assertEqual(region["mean_session_corrected_r2"], .4375)
        with self.assertRaises(m.MetricError):
            m.score_cell(meta, [draw])
        with self.assertRaises(m.MetricError):
            m.pooled_r2([.5, .5], [.2, .8])
        with self.assertRaises(m.MetricError):
            m.pooled_r2([.2, .8], [float("nan"), .8])


if __name__ == "__main__":
    unittest.main()
