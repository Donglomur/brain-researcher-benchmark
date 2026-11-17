"""Generated engineering controls; not authentic source payloads or science runs."""
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

MODULE = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("n027", MODULE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture():
    metadata = [
        {"session_id": "a_d_b", "mname": "a", "datexp": "d", "blk": "b", "phase": "before"},
        {"session_id": "b_d_b", "mname": "b", "datexp": "d", "blk": "b", "phase": "before"},
        {"session_id": "c_d_b", "mname": "c", "datexp": "d", "blk": "b", "phase": "reward_free_after"},
        {"session_id": "d_d_b", "mname": "d", "datexp": "d", "blk": "b", "phase": "reward_free_after"},
    ]
    plan = {"schema_version": 1, "classes": [0, 2], "position_edges": [0.0, 0.4, 0.8],
            "train_mice": ["a", "b"], "evaluation_mice": ["c", "d"], "train_phases": ["before"],
            "evaluation_phases": ["reward_free_after"], "calibration": "source_anatomical_area_mean_v1",
            "pre_reward_training_attestation": True,
            "phase_semantics": {"before": "Pre-reward engineering fixture", "reward_free_after": "Post exposure engineering fixture"}, "sessions": metadata}
    sessions = []
    walls = np.repeat([30, 90, 30, 90], 4)
    for meta in metadata:
        spks = np.stack([(walls == 90).astype(float) * (i+1) + np.tile([0, .1, 0, .1], 4) for i in range(4)])
        beh = {"ft_WallID": walls.copy(), "ft_trInd": np.repeat(np.arange(4), 4).astype(float),
               "ft_move": np.ones(16), "ft_Pos": np.tile([1., 2., 6., 7.], 4), "ft_CorrSpc": np.ones(16),
               "Corridor_Length": 10., "UniqWalls": [30, 90], "stim_id": [0, 2]}
        sessions.append(dict(meta, spks=[spks[:2], spks[2:]], iarea=[8, 0, 5, 3], behavior=beh))
    return plan, sessions


class PacketTests(unittest.TestCase):
    def test_complete_frame_to_endpoint_path(self):
        p, s = fixture()
        report, predictions, q = e.evaluate(s, p, bootstrap_draws=100)
        metrics = report["neural"]["by_phase"]["reward_free_after"]
        self.assertEqual(metrics["mouse_macro_balanced_accuracy"], 1)
        self.assertEqual(report["movement_position"]["by_phase"]["reward_free_after"]["mouse_macro_balanced_accuracy"], .5)
        self.assertTrue(report["movement_position"]["diagnostics"]["constant_probability_output"])
        self.assertEqual(report["scientific_qualification"], "unknown")
        self.assertEqual(len(q), 16)
        self.assertEqual(set(q[0]), {"item_id", "neural", "context"})
        self.assertTrue(report["holds"])
        self.assertEqual(len(predictions["neural"]), 16)

    def test_source_wall_mapping_and_trial_bins(self):
        p, s = fixture()
        r, audit = e.construct_session(s[0], p)
        self.assertEqual([x["label"] for x in r], [0, 0, 2, 2, 0, 0, 2, 2])
        self.assertEqual(r[0]["neural"], [.05]*4)
        np.testing.assert_allclose(r[0]["context"], [1., .15])
        self.assertEqual(audit["retained_trials"], 4)
        self.assertEqual(audit["area_counts"], {"V1": 1, "mHV": 1, "lHV": 1, "aHV": 1})

    def test_string_source_wall_identity_mapping(self):
        p, s = fixture()
        s[0]["behavior"]["ft_WallID"] = np.where(s[0]["behavior"]["ft_WallID"] == 30, "circle1", "leaf1")
        s[0]["behavior"]["UniqWalls"] = np.array(["circle1", "leaf1"])
        r, _ = e.construct_session(s[0], p)
        self.assertEqual([x["label"] for x in r], [0, 0, 2, 2, 0, 0, 2, 2])
        s[0]["behavior"]["ft_WallID"][0] = "wrong"
        with self.assertRaisesRegex(ValueError, "inconsistent|unmapped"):
            e.construct_session(s[0], p)

    def test_infinite_unselected_trial_rejected_but_nan_audited(self):
        p, s = fixture()
        s[0]["behavior"]["ft_CorrSpc"][0] = 0
        s[0]["behavior"]["ft_trInd"][0] = np.inf
        with self.assertRaisesRegex(ValueError, "infinite trial"):
            e.construct_session(s[0], p)
        s[0]["behavior"]["ft_trInd"][0] = np.nan
        _, audit = e.construct_session(s[0], p)
        self.assertEqual(audit["discarded_unassigned_trial_frames"], 1)

    def test_position_units_outside_domain_rejected(self):
        p, s = fixture(); s[0]["behavior"]["ft_Pos"][0] = 101
        with self.assertRaisesRegex(ValueError, "verify source units"):
            e.construct_session(s[0], p)

    def test_no_cross_trial_interpolation(self):
        p, s = fixture()
        # Missing first bin in trial 0 must exclude it, not borrow trial 1 frames.
        s[0]["behavior"]["ft_move"][:2] = 0
        r, audit = e.construct_session(s[0], p)
        self.assertEqual(len(r), 6)
        self.assertFalse(any(x["trial_id"] == 0 for x in r))
        self.assertEqual(audit["exclusions"], [{"trial_id": 0, "reason": "incomplete_fixed_position_grid"}])

    def test_exact_last_edge_and_internal_edge(self):
        p, s = fixture()
        s[0]["behavior"]["ft_Pos"] = np.tile([0, 4, 7, 8.], 4)
        r, _ = e.construct_session(s[0], p)
        self.assertEqual(r[0]["frame_count"], 1)
        self.assertEqual(r[1]["frame_count"], 3)

    def test_behavior_tail_audited_and_short_vector_rejected(self):
        p, s = fixture()
        for k in e.SOURCE_FIELDS:
            s[0]["behavior"][k] = np.r_[s[0]["behavior"][k], 123]
        _, audit = e.construct_session(s[0], p)
        self.assertTrue(all(x == 1 for x in audit["behavior_tail_frames"].values()))
        s[0]["behavior"]["ft_Pos"] = np.zeros(15)
        with self.assertRaisesRegex(ValueError, "shorter"):
            e.construct_session(s[0], p)

    def test_bad_neural_source_area_and_stimuli(self):
        p, sessions = fixture()
        for mutation, message in [
            (lambda s: s.update(iarea=[8, 8, 5, 3]), "missing cortical"),
            (lambda s: s["spks"][0].__setitem__((0, 0), np.nan), "nonfinite"),
            (lambda s: s["behavior"]["ft_WallID"].__setitem__(0, 90), "inconsistent"),
            (lambda s: s["behavior"].update(UniqWalls=[30, 30]), "ambiguous"),
            (lambda s: s["behavior"]["ft_trInd"].__setitem__(0, np.nan), "missing trial"),
            (lambda s: s["behavior"]["ft_trInd"].__setitem__(-1, 0), "recurs"),
        ]:
            with self.subTest(message=message):
                s = copy.deepcopy(sessions[0]); mutation(s)
                with self.assertRaisesRegex(ValueError, message):
                    e.construct_session(s, p)

    def test_population_phase_and_mouse_leakage(self):
        p, s = fixture()
        with self.assertRaisesRegex(ValueError, "population"):
            e.prepare(s[:-1], p)
        p["evaluation_mice"].append("a")
        with self.assertRaisesRegex(ValueError, "animal"):
            e.prepare(s, p)
        p, s = fixture(); p["evaluation_phases"] = ["before"]
        with self.assertRaisesRegex(ValueError, "phases overlap"):
            e.prepare(s, p)
        p, s = fixture(); s[-1]["phase"] = "before"
        with self.assertRaisesRegex(ValueError, "unplanned"):
            e.prepare(s, p)

    def test_equal_class_availability_required(self):
        p, s = fixture(); s[2]["behavior"]["ft_WallID"][:] = 30
        with self.assertRaisesRegex(ValueError, "availability"):
            e.prepare(s, p)

    def test_target_and_query_values_do_not_fit_reference(self):
        p, s = fixture(); train, expected, _ = e.prepare(s, p)
        model = e.Reference(p["classes"], "neural").fit(train)
        q = e.query(expected); first = model.predict(q)
        mean = model.mean.copy(); scale = model.scale.copy()
        switched = copy.deepcopy(expected)
        for row in switched:
            row["label"] = 2 if row["label"] == 0 else 0
        self.assertEqual(first, model.predict(e.query(switched)))
        shifted = copy.deepcopy(q)
        for row in shifted: row["neural"] = [1000.] * 4
        model.predict(shifted)
        np.testing.assert_array_equal(model.mean, mean)
        np.testing.assert_array_equal(model.scale, scale)
        q[0]["ft_WallID"] = 90
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            model.predict(q)

    def test_train_class_and_mouse_weighting(self):
        p, s = fixture(); train, _, _ = e.prepare(s, p)
        original = e.Reference(p["classes"], "neural").fit(train)
        # Duplicate all packets of one mouse, renaming only IDs; fitting must not change.
        duplicates = copy.deepcopy([r for r in train if r["mname"] == "a"])
        for r in duplicates: r["item_id"] += "duplicate"
        duplicate = e.Reference(p["classes"], "neural").fit(train + duplicates)
        np.testing.assert_allclose(original.mean, duplicate.mean)
        np.testing.assert_allclose(original.centroids, duplicate.centroids)
        np.testing.assert_allclose(original.variance, duplicate.variance)

    def test_cli_safe_numeric_npz(self):
        p, sessions = fixture()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/"plan.json").write_text(json.dumps(p))
            for s in sessions:
                np.savez(root/(s["session_id"]+".npz"), spks=np.concatenate(s["spks"]), iarea=s["iarea"], **s["behavior"])
            result = subprocess.run([sys.executable, str(MODULE), "--plan", str(root/"plan.json"), "--session-dir", d, "--output-dir", str(root/"out")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root/"out/report.json").read_text())
            self.assertEqual(len(report["input_pins"]), 4)
            self.assertEqual(report["resources"]["evaluation_packets"], 16)


class ScoringTests(unittest.TestCase):
    def oracle(self):
        # Independent review-derived unequal mouse/class counts distinguish macros.
        rows = []
        predictions = []
        for mouse, labels in (("A", [0, 2]), ("B", [0]*6 + [2]*2)):
            for i, y in enumerate(labels):
                iid = mouse + str(i)
                rows.append({"item_id": iid, "mname": mouse, "phase": "P", "label": y})
                p = ([.9, .1] if y == 0 else [.1, .9]) if mouse == "A" else [.8, .2]
                predictions.append({"item_id": iid, "probabilities": p})
        return rows, predictions

    def test_independent_mouse_macro_oracle(self):
        rows, predictions = self.oracle()
        out = e.score(rows, list(reversed(predictions)), [0, 2])["by_phase"]["P"]
        oracle = (-math.log(.9) + (-6*math.log(.8)-2*math.log(.2))/8)/2
        self.assertAlmostEqual(out["mouse_macro_log_loss"], oracle, places=13)
        self.assertEqual(out["mouse_macro_balanced_accuracy"], .75)

    def test_malformed_missing_duplicate_unknown_probabilities(self):
        rows, predictions = self.oracle()
        for bad in [predictions[:-1], predictions+[predictions[0]], [dict(p, item_id="unknown") if i == 0 else p for i,p in enumerate(predictions)]]:
            with self.assertRaises(ValueError): e.score(rows, bad, [0,2])
        for invalid in ([np.nan,.2], [-.1,1.1], [.1,.2], [.5,.5,.0], [np.inf,0]):
            bad = copy.deepcopy(predictions); bad[0]["probabilities"] = invalid
            with self.assertRaises(ValueError): e.score(rows, bad, [0,2])

    def test_public_scorer_and_reference_reject_invalid_class_sets(self):
        rows, predictions = self.oracle()
        for classes in ([0, 0], [2, 0], [0], [0, 7], [0, float("nan")]):
            with self.subTest(classes=classes):
                with self.assertRaises(ValueError): e.score(rows, predictions, classes)
                with self.assertRaises(ValueError): e.Reference(classes, "neural")

    def test_null_zero_and_tie_policy(self):
        rows, predictions = self.oracle()
        for p in predictions: p["probabilities"] = [.5,.5]
        out = e.score(rows, predictions, [0,2])
        self.assertTrue(out["diagnostics"]["constant_probability_output"])
        self.assertEqual(out["by_phase"]["P"]["mouse_macro_balanced_accuracy"], .5)
        for p in predictions: p["probabilities"] = [1.,0.]
        out = e.score(rows, predictions, [0,2])
        self.assertEqual(out["diagnostics"]["zero_target_probability_count"], 3)
        self.assertTrue(math.isfinite(out["by_phase"]["P"]["mouse_macro_log_loss"]))

    def test_pairing_rejects_different_items_and_label_bindings(self):
        rows, predictions = self.oracle()
        left = e.score(rows, predictions, [0,2])
        changed_rows, changed_predictions = copy.deepcopy(rows), copy.deepcopy(predictions)
        for r in changed_rows: r["item_id"] += "other"
        for r in changed_predictions: r["item_id"] += "other"
        right = e.score(changed_rows, changed_predictions, [0,2])
        with self.assertRaisesRegex(ValueError, "paired expected"):
            e.compare(left, right, draws=100)
        changed_rows = copy.deepcopy(rows)
        for row in changed_rows: row["label"] = 2 if row["label"] == 0 else 0
        right = e.score(changed_rows, predictions, [0,2])
        with self.assertRaisesRegex(ValueError, "paired expected"):
            e.compare(left, right, draws=100)

    def test_cluster_uncertainty_and_single_mouse(self):
        rows, predictions = self.oracle()
        score = e.score(rows, predictions, [0,2])
        comparison = e.compare(score, score, draws=100)["P"]
        self.assertEqual(comparison["paired_mice"], ["A", "B"])
        self.assertEqual(comparison["metrics"]["neural_minus_control_log_loss"]["percentile_95_ci"], [0.,0.])
        one = e.score(rows[:2], predictions[:2], [0,2])
        comparison = e.compare(one, one, draws=100)["P"]
        self.assertEqual(comparison["replication"], "single_mouse_descriptive_only")
        self.assertIsNone(comparison["metrics"]["neural_log_loss"]["percentile_95_ci"])


if __name__ == "__main__":
    unittest.main()
