"""Generated, algebraically specified controls; no authentic targets or fits."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "metrics.py"
SPEC = importlib.util.spec_from_file_location("journal_metrics", MODULE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def metadata(modality="ephys", eid="s1", predictor="neural"):
    return {"modality": modality, "subject": "m1", "eid": eid, "region": "VISp",
            "predictor": predictor, "n_features": 7 if predictor == "movement" else 5,
            "trial_ids": [f"original-{i}" for i in range(250)],
            "target_model": "optBay", "target": "pLeft",
            "input_manifest_sha256": "1" * 64, "target_generator_sha256": "2" * 64}


def draw(meta, draw_id=-1, errors=None):
    # Var(y)=0.09; adding .3 produces R²=0; the mean predictor also has R²=0.
    target = [.2, .8] * 125
    errors = errors if errors is not None else [0] * 10
    fold_count = 5 if meta["modality"] == "ephys" else 50
    return {"pseudo_id": draw_id, "trial_ids": meta["trial_ids"], "target": target,
            "runs": [{"run_id": i, "prediction": [x + error for x in target],
                      "test_fold": [j % fold_count for j in range(250)]}
                     for i, error in enumerate(errors)]}


def draws(meta, null_count=1000):
    yield draw(meta, -1, [0] * 6 + [.3] * 4)
    null = draw(meta, 1, [.3] * 10)
    for i in range(1, null_count + 1):
        yield {**null, "pseudo_id": i}


def summary(eid, score, null, modality="ephys", predictor="neural"):
    return {**{k: v for k, v in metadata(modality, eid, predictor).items()
               if k in ("modality", "subject", "eid", "region", "predictor")},
            "r2": score, "median_null_r2": null, "corrected_r2": score - null,
            "trial_ids_sha256": "3" * 64, "actual_target_sha256": "4" * 64,
            "actual_folds_sha256": "5" * 64, "actual_predictions_sha256": "6" * 64}


class PublishedArithmetic(unittest.TestCase):
    def test_ten_run_median_is_neither_mean_score_nor_score_of_mean_prediction(self):
        meta = metadata()
        observed = m.score_draw(draw(meta, errors=[0] * 6 + [.3] * 4), meta["trial_ids"], "ephys")
        self.assertAlmostEqual(observed["median_run_r2"], 1)
        self.assertNotAlmostEqual(observed["median_run_r2"], .6)  # mean of R²
        self.assertAlmostEqual(m.pooled_r2([.2, .8], [.32, .92]), .84)

    def test_pool_trials_not_average_fold_scores(self):
        self.assertAlmostEqual(m.pooled_r2([0, .1, .9, 1], [0, 0, .9, .9]), 40 / 41)

    def test_complete_streaming_cell_and_thousand_nulls(self):
        result = m.score_cell(metadata(), draws(metadata()))
        self.assertEqual(result["n_runs"], 10)
        self.assertEqual(result["n_pseudosessions"], 1000)
        self.assertAlmostEqual(result["r2"], 1)
        self.assertAlmostEqual(result["median_null_r2"], 0)
        self.assertAlmostEqual(result["corrected_r2"], 1)

    def test_mean_session_corrections_preserves_single_session_and_modality(self):
        rows = [summary("s1", 0, 0), summary("s2", .1, .8), summary("s3", .9, .8),
                summary("w1", .5, .1, modality="wfi")]
        panel = m.summarize_panel(rows, rows)
        self.assertEqual(len(panel["regional_effects"]), 2)
        ephys, wfi = panel["regional_effects"]
        self.assertAlmostEqual(ephys["mean_session_corrected_r2"], -.2)
        self.assertNotAlmostEqual(ephys["mean_session_corrected_r2"], -.7)
        self.assertEqual(wfi["n_sessions"], 1)
        self.assertAlmostEqual(wfi["mean_session_corrected_r2"], .4)


class IdentityAndCoverage(unittest.TestCase):
    def test_original_modality_fold_counts(self):
        for modality, count in (("ephys", 5), ("wfi", 50)):
            meta = metadata(modality)
            m.score_draw(draw(meta), meta["trial_ids"], modality)
            bad = draw(meta)
            bad["runs"][0]["test_fold"] = [i % (50 if count == 5 else 5) for i in range(250)]
            with self.assertRaisesRegex(m.MetricError, "outer folds"):
                m.score_draw(bad, meta["trial_ids"], modality)

    def test_missing_or_duplicate_draw_and_missing_or_duplicate_repeat(self):
        meta = metadata()
        with self.assertRaisesRegex(m.MetricError, "1000"):
            m.score_cell(meta, draws(meta, 200))
        with self.assertRaisesRegex(m.MetricError, "unique real"):
            m.score_cell(meta, [draw(meta), draw(meta)])
        for replacement in (draw(meta)["runs"][:-1], [draw(meta)["runs"][0]] * 10):
            bad = draw(meta)
            bad["runs"] = replacement
            with self.assertRaises(m.MetricError):
                m.score_draw(bad, meta["trial_ids"], "ephys")

    def test_changed_mask_and_trial_order_rejected(self):
        meta = metadata()
        bad = draw(meta)
        bad["trial_ids"] = list(reversed(meta["trial_ids"]))
        with self.assertRaisesRegex(m.MetricError, "order changed"):
            m.score_cell(meta, [bad])
        meta["trial_ids"] = meta["trial_ids"][:249]
        with self.assertRaisesRegex(m.MetricError, "250"):
            m.score_cell(meta, [])

    def test_reject_oracle_nonfinite_constant_and_bad_units(self):
        meta = metadata()
        meta["target"] = "probabilityLeft"
        with self.assertRaisesRegex(m.MetricError, "pLeft"):
            m.score_cell(meta, [])
        meta = metadata()
        meta["n_features"] = 4
        with self.assertRaisesRegex(m.MetricError, "five"):
            m.score_cell(meta, [])
        for prediction in ([float("nan")] * 2, [True, False], [1e308, 1e308]):
            with self.assertRaises(m.MetricError):
                m.pooled_r2([.2, .8], prediction)
        with self.assertRaisesRegex(m.MetricError, "constant"):
            m.pooled_r2([.5, .5], [.2, .8])

    def test_no_silent_intersection_duplicate_region_or_mouse_reassignment(self):
        rows = [summary("s1", .5, .1), summary("s2", .3, .1)]
        with self.assertRaisesRegex(m.MetricError, "population"):
            m.summarize_panel(rows, rows[:1])
        with self.assertRaisesRegex(m.MetricError, "duplicate"):
            m.summarize_panel(rows + rows[:1], rows + rows[:1])
        other = {**rows[0], "subject": "other-mouse", "region": "MOs"}
        with self.assertRaisesRegex(m.MetricError, "multiple mice"):
            m.summarize_panel(rows + [other], rows + [other])

    def test_movement_subset_keeps_full_neural_cohort_and_checks_actual_targets(self):
        rows = [summary("s1", .5, .1), summary("s2", .3, .1),
                summary("s1", .2, 0, predictor="movement")]
        # Native movement fitting may use its own random splits; report this,
        # do not substitute a newly imposed identical-split protocol.
        rows[-1]["actual_folds_sha256"] = "6" * 64
        panel = m.summarize_panel(rows, rows)
        self.assertEqual(panel["n_neural_cells"], 2)
        self.assertEqual(panel["n_movement_cells"], 1)
        self.assertFalse(panel["movement_comparisons"][0]["same_outer_partitions"])
        self.assertAlmostEqual(panel["movement_comparisons"][0]["neural_minus_movement_r2"], .3)
        rows[-1]["actual_target_sha256"] = "7" * 64
        with self.assertRaisesRegex(m.MetricError, "identities"):
            m.summarize_panel(rows, rows)

    def test_file_byte_binding_and_strict_json(self):
        with self.assertRaisesRegex(m.MetricError, "duplicate JSON"):
            m.strict_json('{"x":1,"x":2}')
        with self.assertRaisesRegex(m.MetricError, "nonfinite JSON"):
            m.strict_json('{"x":NaN}')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draws.jsonl"
            sha = hashlib.sha256()
            meta = metadata()
            with path.open("wb") as output:
                for record in draws(meta):
                    content = (json.dumps(record, separators=(",", ":")) + "\n").encode()
                    output.write(content)
                    sha.update(content)
            manifest = {"schema": m.SCHEMA, "expected_cells": [meta],
                        "cells": [{**meta, "prediction_file": "draws.jsonl",
                                   "prediction_file_sha256": sha.hexdigest()}]}
            manifest_path, result_path = Path(tmp) / "manifest.json", Path(tmp) / "result.json"
            manifest_path.write_text(json.dumps(manifest))
            argv = sys.argv
            try:
                sys.argv = [str(MODULE), str(manifest_path), "--output", str(result_path)]
                m.main()
            finally:
                sys.argv = argv
            result = json.loads(result_path.read_text())
            self.assertEqual(result["n_neural_cells"], 1)
            self.assertAlmostEqual(result["regional_effects"][0]["mean_session_corrected_r2"], 1)
            for private_array in ('"prediction":', '"target":', '"trial_ids":'):
                self.assertNotIn(private_array, result_path.read_text())
            with self.assertRaisesRegex(m.MetricError, "hash mismatch"):
                m.score_file(path, meta, "0" * 64)

    def test_movement_is_one_session_level_fit_reused_across_regions(self):
        neural, movement = summary("s1", .5, .1), summary("s1", .2, 0, predictor="movement")
        rows = [neural, movement, {**neural, "region": "MOs"}, {**movement, "region": "MOs"}]
        self.assertEqual(m.summarize_panel(rows, rows)["n_movement_cells"], 2)
        rows[-1]["actual_predictions_sha256"] = "7" * 64
        with self.assertRaisesRegex(m.MetricError, "session-level fit"):
            m.summarize_panel(rows, rows)


if __name__ == "__main__":
    unittest.main()
