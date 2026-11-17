import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as e
from sequence import sequence_similarity


def imaging_bundle():
    wall = np.array(["leaf1", "leaf1", "circle1", "circle1", "leaf2", "leaf2"] * 4)
    trial = np.repeat(np.arange(len(wall)), 3)
    frame_wall = wall[trial]
    corridor = np.tile([1, 1, 0], len(wall))
    activity = np.zeros(len(frame_wall))
    for n, stim in enumerate(wall):
        activity[n * 3:n * 3 + 2] = [1, 3] if stim == "leaf1" else [0, 0]
    spks = np.tile(activity, (12, 1))
    interpolated = np.zeros((12, len(wall), 60))
    peaks = [1, 10, 25] * 4
    for cell, peak in enumerate(peaks):
        for tr, stim in enumerate(wall):
            selected = peak if stim == "leaf1" else (26 - peak if stim == "leaf2" else 2)
            interpolated[cell, tr, selected] = 1
    return {"spks": spks, "area_ids": np.repeat([8, 0, 5, 3], 3),
            "frame_wall": frame_wall, "frame_move": np.ones(len(frame_wall)),
            "frame_corridor": corridor, "frame_gray": 1 - corridor, "frame_trial": trial,
            "trial_wall": wall, "stimulus_names": np.array(["circle1", "leaf1", "leaf2"]),
            "stimulus_ids": np.array([0, 2, 3]), "interp_spks": interpolated,
            "sound_delay_position": np.tile([10, 20, 30, 40, 0, 0], 4)}


class NumericControls(unittest.TestCase):
    def test_arithmetic_standard_deviation_source_formula(self):
        result = e.source_dprime([[1, np.nan, 3]], [[0, 0]])
        self.assertEqual(result[0], 4.)

    def test_zero_variance_preserves_source_comparisons(self):
        dp = e.source_dprime([[1, 1], [2, 2], [0, 0]], [[1, 1], [1, 1], [1, 1]])
        self.assertTrue(np.isnan(dp[0]))
        self.assertTrue(np.isposinf(dp[1]))
        self.assertTrue(np.isneginf(dp[2]))
        ar = e.area_fractions(dp, [8, 8, 8])["V1"]
        self.assertEqual(ar["fractions"][0]["either"], 2 / 3)
        self.assertEqual(ar["dprime_diagnostics"], {"finite": 0, "nan": 1, "positive_infinity": 1, "negative_infinity": 1})
        json.dumps(e.finite_json(dp), allow_nan=False)

    def test_frame_masks_and_all_area_denominators(self):
        bundle = imaging_bundle()
        # Outlier in a nonmoving leaf1 frame must not influence selectivity.
        bundle["spks"][:, 0] = 10000
        bundle["frame_move"][0] = 0
        dp, report = e.selectivity(e.validate_bundle(bundle))
        expected = e.source_dprime(bundle["spks"][:, (bundle["frame_wall"] == "leaf1") & (bundle["frame_move"] > 0) & (bundle["frame_corridor"] > 0)],
                                   bundle["spks"][:, (bundle["frame_wall"] == "circle1") & (bundle["frame_corridor"] > 0)])
        np.testing.assert_equal(dp, expected)
        self.assertEqual(report["moving_texture_frame_counts"], [15, 16])
        self.assertEqual([report["areas"][a]["cell_count"] for a in e.AREAS], [3] * 4)

    def test_all_trial_reward_cue_split_and_positive_stimulus_gate(self):
        bundle = imaging_bundle()
        bundle["trial_wall"] = np.array(["leaf1"] * 4 + ["circle1"] * 4)
        bundle["sound_delay_position"] = np.array([70, 80, 90, 100, 60, 60, 60, 60])
        bundle["interp_spks"] = np.tile(np.array([10, 20, 30, 40, 0, 0, 0, 0])[None, :, None], (12, 1, 60)).astype(float)
        bundle["interp_spks"][:, :, :5] = 9999
        bundle["interp_spks"][:, :, 40:] = -9999
        stim_dp = np.array([0, -1, 1] * 4)
        result = e.reward_prediction(e.validate_bundle(bundle), stim_dp)
        self.assertEqual(result["cue_split_all_trials_mean"], 12.5)
        self.assertEqual((result["early_trial_count"], result["late_trial_count"]), (1, 3))
        self.assertAlmostEqual(result["dprime"][0], 4.898979485566356)
        self.assertEqual(result["areas"]["V1"]["fraction"], 2 / 3)

    def test_lick_inclusive_boundaries_global_cutoff_no_event_double_count(self):
        wall = np.array(["leaf1", "circle1"] * 101)
        result = e.lick_learning(wall, ["circle1", "leaf1"], [0, 2], [20, 40, 30, 19.9, 40.1, 25], [0, 0, 1, 2, 3, 200])
        self.assertEqual(result["rewarded"]["trial_count"], 100)
        self.assertEqual(result["rewarded"]["response_count"], 1)
        self.assertEqual(result["nonrewarded"]["response_count"], 1)

    def test_sequence_peaks_reference_repeat_and_reversal(self):
        result = sequence_similarity(e.validate_bundle(imaging_bundle()))
        self.assertEqual(result["reference_trial_indices"], [1, 13])
        self.assertEqual(result["repeat_test_trial_indices"], [7, 19])
        for area in e.AREAS:
            out = result["areas"][area]
            self.assertEqual(out["selected_cell_count"], 3)  # Inclusive top-percentile ties.
            self.assertAlmostEqual(out["targets"]["2"]["correlation"], 1.)
            self.assertAlmostEqual(out["targets"]["3"]["correlation"], -1.)
            self.assertIsNone(out["targets"]["0"]["correlation"])

    def test_sequence_selection_isolated_from_odd_raw_frame_activity(self):
        first = imaging_bundle()
        second = imaging_bundle()
        second["spks"][:, second["frame_trial"] % 2 == 1] = 1e8
        a = sequence_similarity(e.validate_bundle(first))
        b = sequence_similarity(e.validate_bundle(second))
        self.assertEqual(a, b)

    def test_bundle_rejects_empty_trials_and_unknown_valid_frame_labels(self):
        bundle = imaging_bundle()
        bundle["trial_wall"] = np.array([], dtype="U7")
        with self.assertRaisesRegex(ValueError, "empty trial"):
            e.validate_bundle(bundle)
        bundle = imaging_bundle()
        bundle["frame_wall"][0] = "unknown"
        with self.assertRaisesRegex(ValueError, "unmapped moving"):
            e.validate_bundle(bundle)

    def test_native_behavior_reward_categories_and_ambiguity(self):
        behavior = {"ntrials": 4, "WallName": np.array(["textureA", "textureB"] * 2),
                    "isRew": [0, 1, 0, 1], "LickPos": [30, 30], "LickTrind": [1, 3]}
        result = e.normalize_author_behavior(behavior)
        self.assertEqual(result["stimulus_ids"].tolist(), [0, 2])
        out = e.lick_learning(*(result[k] for k in ("trial_wall", "stimulus_names", "stimulus_ids", "lick_position", "lick_trial")))
        self.assertEqual(out["reward_minus_nonreward"], 1.)
        behavior["isRew"] = [1, 1, 0, 1]
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            e.normalize_author_behavior(behavior)

    def test_native_behavior_never_relabels_source_sibling_categories(self):
        for rewarded in ([1, 0], [0, 1]):
            behavior = {"ntrials": 2, "WallName": np.array(["leaf1", "leaf2"]),
                        "isRew": rewarded, "LickPos": [], "LickTrind": []}
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                e.normalize_author_behavior(behavior)

    def test_native_bridge_all_planes_linear_interpolation(self):
        frames = 120
        wall = np.array(["leaf1", "circle1"])
        pos = np.arange(frames, dtype=float)
        neural = {"spks": [np.array([pos]), np.array([pos * 2])]}
        beh = {"ntrials": 2, "WallName": wall, "Corridor_Length": 60,
               "ft_WallID": np.repeat(wall, 60), "ft_move": np.ones(frames),
               "ft_CorrSpc": np.ones(frames), "ft_GraySpc": np.zeros(frames),
               "ft_trInd": np.repeat([0, 1], 60), "ft_PosCum": pos,
               "UniqWalls": wall, "stim_id": [2, 0], "SoundDelPos": [20, 30]}
        result = e.normalize_author_imaging(neural, {"iarea": [8, 0]}, beh)
        self.assertEqual(result["spks"].shape, (2, frames))
        np.testing.assert_allclose(result["interp_spks"].reshape(2, -1), np.array([pos, 2 * pos]))
        beh["ntrials"] = 2.5
        with self.assertRaisesRegex(ValueError, "integral"):
            e.normalize_author_imaging(neural, {"iarea": [8, 0]}, beh)


class PanelControls(unittest.TestCase):
    def write_panel(self, root):
        sessions = []
        # Different trial sizes ensure distinct authentic-style session contents.
        for animal, before_n, after_n in [("A", 4, 6), ("B", 8, 10)]:
            for stage, n in [("before", before_n), ("after", after_n)]:
                name = animal + "_" + stage
                path = root / (name + ".npz")
                nlick = 1 if stage == "before" else n // 2
                np.savez(path, trial_wall=np.array(["leaf1", "circle1"] * (n // 2)),
                         stimulus_names=np.array(["leaf1", "circle1"]), stimulus_ids=[2, 0],
                         lick_position=np.full(nlick, 30.), lick_trial=np.arange(nlick) * 2)
                sessions.append({"session_id": name, "animal_id": animal, "condition": "unsupervised", "stage": stage,
                                 "kind": "behavior", "npz_path": path.name, "sha256": e.digest(path), "expected_counts": {"trial_count": n}})
        plan = {"schema_version": 1, "task_id": e.TASK, "stages": ["before", "after"],
                "population_evidence": "generated engineering control; not an empirical cohort",
                "expected_session_ids": [s["session_id"] for s in sessions], "sessions": sessions}
        path = root / "panel.json"
        path.write_text(json.dumps(plan))
        return path, plan

    def test_cli_complete_declared_panel_equal_animal_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, plan = self.write_panel(root)
            report = e.evaluate_panel(path)
            effect = report["condition_changes"]["unsupervised"]["lick_learning/reward_minus_nonreward"]
            self.assertEqual(effect["n_animals"], 2)
            self.assertEqual(effect["mean"], .625)  # mean(A=.5, B=.75), not pooled trials.
            self.assertEqual(effect["sem"], .125)
            self.assertEqual(report["scientific_qualification"], "unknown")
            self.assertFalse(report["full_contract_complete"])
            out = root / "out.json"
            e.main([str(path), "--output", str(out)])
            self.assertEqual(json.loads(out.read_text())["panel_sha256"], e.digest(path))

    def test_all_five_learning_stages_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, plan = self.write_panel(root)
            plan["sessions"] = plan["sessions"][:2]
            plan["stages"] = ["before", "day2", "day3", "day4", "after"]
            for number, stage in enumerate(plan["stages"][1:-1], start=1):
                file = root / (stage + ".npz")
                count = 12 + 2 * number
                np.savez(file, trial_wall=np.array(["leaf1", "circle1"] * (count // 2)),
                         stimulus_names=np.array(["leaf1", "circle1"]), stimulus_ids=[2, 0],
                         lick_position=[30.], lick_trial=[0])
                plan["sessions"].append({"session_id": stage, "animal_id": "A", "condition": "unsupervised", "stage": stage,
                                         "kind": "behavior", "npz_path": file.name, "sha256": e.digest(file), "expected_counts": {"trial_count": count}})
            plan["expected_session_ids"] = [s["session_id"] for s in plan["sessions"]]
            path.write_text(json.dumps(plan))
            report = e.evaluate_panel(path)
            self.assertEqual(len(report["condition_stage_means"]), 5)
            self.assertEqual(report["change_endpoints"], ["before", "after"])
            self.assertEqual(report["condition_changes"]["unsupervised"]["lick_learning/reward_minus_nonreward"]["mean"], .5)

    def test_missing_longitudinal_stage_and_input_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, plan = self.write_panel(root)
            plan["sessions"] = plan["sessions"][:-1]
            plan["expected_session_ids"] = [s["session_id"] for s in plan["sessions"]]
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "both declared"):
                e.evaluate_panel(path)
            path, plan = self.write_panel(root)
            plan["sessions"][0]["sha256"] = "0" * 64
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "input hash mismatch"):
                e.evaluate_panel(path)

    def test_cross_condition_animal_and_omitted_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path, plan = self.write_panel(Path(temp))
            plan["sessions"][1]["condition"] = "supervised"
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "multiple exposure"):
                e.evaluate_panel(path)
            plan["sessions"][1]["condition"] = "unsupervised"
            plan["expected_session_ids"].append("missing")
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "inventory"):
                e.evaluate_panel(path)


if __name__ == "__main__":
    unittest.main()
