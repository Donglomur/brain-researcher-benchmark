"""Generated controls only; no authentic observations or author inference."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("position_score", ROOT / "position_score.py")
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)


def fixture():
    reference = {"schema_version": 1, "kind": "generated_control", "phase": "learned", "mice": {}}
    candidate = {"schema_version": 1, "access_condition": "paper_and_data", "mice": {}}
    # Independent frozen indices: shuffled ten groups begin [8,1]; two frames/group.
    direct_indices = [2, 3, 16, 17]
    for mouse in ps.MICE:
        arms = {arm: {"frame_ids": [f"{mouse}:{arm}:{i}" for i in range(20)],
                      "trial_groups": [i // 2 for i in range(20)],
                      "positions": [i / 20 for i in range(20)]} for arm in ("L", "R")}
        author, shuffles = {}, {}
        for condition in ps.CONDITIONS:
            target = condition[0]
            indices = direct_indices if len(condition) == 1 else list(range(20))
            row = {"frame_ids": [arms[target]["frame_ids"][i] for i in indices],
                   "positions": [arms[target]["positions"][i] for i in indices]}
            if condition.endswith(" Shuffled"):
                shuffles[condition] = [f"{mouse}:{condition}:{i}" for i in range(50)]
                author[condition] = [{**copy.deepcopy(row), "shuffle_id": identity}
                                     for identity in shuffles[condition]]
            else:
                author[condition] = row
        reference["mice"][mouse] = {"arms": arms, "author": author, "shuffle_ids": shuffles}
        candidate["mice"][mouse] = copy.deepcopy(author)
    return reference, candidate


class SourceSplitTests(unittest.TestCase):
    def test_frozen_group_split_not_frame_shuffle(self):
        # RandomState(42) permutes five unique groups as [1,4,2,0,3].
        groups = [4, 4, 0, 1, 2, 3, 1, 1, 4]
        train, test = ps.source_split(groups)
        self.assertEqual(test.tolist(), [3, 6, 7])
        self.assertEqual(train.tolist(), [0, 1, 2, 4, 5, 8])
        self.assertFalse(set(np.asarray(groups)[train]) & set(np.asarray(groups)[test]))

    def test_string_group_sort_and_single_group_refusal(self):
        _, test = ps.source_split(["e", "a", "b", "c", "d", "b"])
        self.assertEqual(test.tolist(), [2, 5])
        for groups in ([1, 1], [True, False], [1, "1"], [0, float("nan")]):
            with self.assertRaises(ps.ContractError):
                ps.source_split(groups)

    def test_direct_split_and_full_prefix_cross_observations(self):
        ref, _ = fixture()
        arms = ref["mice"]["478"]["arms"]
        for key in ("frame_ids", "positions", "trial_groups"):
            arms["R"][key] = arms["R"][key][:14]
        expected, _ = ps._expected(arms)
        self.assertEqual(len(expected["L from R"][0]), 14)
        self.assertEqual(expected["L from R"][0], arms["L"]["frame_ids"][:14])
        self.assertEqual(expected["R from L"][0], arms["R"]["frame_ids"])
        self.assertNotEqual(expected["L"][0], expected["L from R"][0])


class MetricTests(unittest.TestCase):
    def test_hand_calculated_mode_filter_and_tie(self):
        result = ps.source_error([0, 1, 0, 1], [.25, .25, .75, .75], [.25, .25, .75, .75])
        self.assertEqual(result["source_excluded_frames"], 2)
        self.assertAlmostEqual(result["source_modal_filtered_rmse"], math.sqrt(.3125))
        self.assertAlmostEqual(result["full_bin_rmse"], math.sqrt(.3125))
        self.assertEqual(result["common_retained_frames"], 2)

    def test_lower_source_error_can_hide_worse_full_error(self):
        truth = [0, 0, 0, .9]
        baseline = [.1, .1, .1, .8]
        bad_candidate = [1, 1, 1, .9]
        a = ps.source_error(truth, baseline, baseline)
        b = ps.source_error(truth, bad_candidate, baseline)
        self.assertLess(b["source_modal_filtered_rmse"], a["source_modal_filtered_rmse"])
        self.assertGreater(b["full_bin_rmse"], a["full_bin_rmse"])
        self.assertEqual(b["source_retained_frames"], 1)

    def test_constant_prediction_is_undefined_not_zero(self):
        result = ps.source_error([0, 1], [.5, .5], [.25, .75])
        self.assertIsNone(result["source_modal_filtered_rmse"])
        self.assertEqual(result["full_bin_rmse"], .5)
        self.assertEqual(result["source_retained_frames"], 0)

    def test_nonfinite_wrong_shape_and_units_rejected(self):
        for pred in ([.2], [.2, float("nan")], [.2, 100], [.2, True]):
            with self.assertRaises(ps.ContractError):
                ps.source_error([0, 1], pred, [0, 1])


class PanelTests(unittest.TestCase):
    def test_complete_six_condition_reduction_and_direction_labels(self):
        reference, candidate = fixture()
        result = ps.score(reference, candidate)
        self.assertEqual(list(result["mice"]), list(ps.MICE))
        cross = result["mice"]["478"]["conditions"]["L from R"]
        self.assertEqual((cross["rate_map_arm"], cross["spike_and_truth_arm"]), ("R", "L"))
        self.assertEqual(cross["literal_source_posterior_key"], "R from L")
        self.assertEqual(cross["draws"][0]["reproduction_prediction_comparison"]["rmse_from_author"], 0)
        self.assertEqual(cross["improvement_candidate_minus_author"]["source_modal_filtered_rmse"], 0)
        for condition in ps.CONDITIONS:
            metric = result["panel"][condition]["author"]["source_modal_filtered_rmse"]
            self.assertEqual(metric["mouse_values"], [0, 0, 0, 0])
            self.assertEqual(metric["mean"], 0)
            self.assertEqual(metric["population_std_ddof_0"], 0)
        self.assertEqual(result["mice"]["478"]["conditions"][ps.CONDITIONS[-1]]["draw_count"], 50)
        self.assertFalse(result["native_preparation_verified"])
        self.assertIsNone(result["superiority_decision"])
        self.assertIsNone(result["reproduction_decision"])

    def test_paired_access_conditions_preserve_scientific_scores(self):
        reference, candidate = fixture()
        a = ps.score(reference, candidate)
        candidate["access_condition"] = "paper_data_and_author_code"
        b = ps.score(reference, candidate)
        self.assertNotEqual(a["access_condition"], b["access_condition"])
        self.assertEqual(a["panel"], b["panel"])
        self.assertEqual(a["mice"], b["mice"])

    def test_population_std_and_no_undefined_draw_omission(self):
        reference, candidate = fixture()
        # For a direct condition each animal gets a distinct constant error.
        errors = [0, .01, .02, .03]
        for mouse, error in zip(ps.MICE, errors):
            candidate["mice"][mouse]["L"]["positions"] = [v + error for v in
                candidate["mice"][mouse]["L"]["positions"]]
        out = ps.score(reference, candidate)
        summary = out["panel"]["L"]["candidate"]["source_modal_filtered_rmse"]
        self.assertAlmostEqual(summary["mean"], .015)
        self.assertAlmostEqual(summary["population_std_ddof_0"], math.sqrt(.000125))
        row = candidate["mice"]["485"]["L from R Shuffled"][0]
        row["positions"] = [.5] * len(row["positions"])
        out = ps.score(reference, candidate)
        self.assertIsNone(out["panel"]["L from R Shuffled"]["candidate"]["source_modal_filtered_rmse"]["mean"])
        self.assertIsNotNone(out["panel"]["L from R Shuffled"]["candidate"]["full_bin_rmse"]["mean"])

    def test_missing_mouse_draw_or_changed_ids_fails(self):
        for mutate in (lambda c: c["mice"].pop("485"),
                       lambda c: c["mice"]["478"]["L from R Shuffled"].pop(),
                       lambda c: c["mice"]["478"]["L"]["frame_ids"].reverse(),
                       lambda c: c["mice"]["478"]["L from R Shuffled"][0].update(shuffle_id="other")):
            reference, candidate = fixture()
            mutate(candidate)
            with self.assertRaises(ps.ContractError):
                ps.score(reference, candidate)

    def test_cli_and_strict_json(self):
        reference, candidate = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            ref, cand, out = (Path(tmp) / name for name in ("ref.json", "candidate.json", "out.json"))
            ref.write_text(json.dumps(reference)); cand.write_text(json.dumps(candidate))
            run = subprocess.run([sys.executable, str(ROOT / "position_score.py"), str(ref),
                                  str(cand), "--output", str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(out.read_text())
            self.assertEqual(len(result["input_sha256"]["reference"]), 64)
            out.unlink()
            cand.write_text('{"schema_version":1,"schema_version":1,"mice":{}}')
            run = subprocess.run([sys.executable, str(ROOT / "position_score.py"), str(ref),
                                  str(cand), "--output", str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
