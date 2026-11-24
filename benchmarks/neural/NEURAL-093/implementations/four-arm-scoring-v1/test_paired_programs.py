"""Generated paired-program controls; no authentic observations or model runs."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import paired_programs
from test_scoring import fixture


class PairedProgrammeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = fixture()

    def arrange(self):
        sources, panel, plan, commit, outputs, private = self.data
        return sources, copy.deepcopy(panel), copy.deepcopy(plan), {
            method: copy.deepcopy(commit) for method in paired_programs.METHODS}, {
            method: copy.deepcopy(outputs) for method in paired_programs.METHODS}, dict(private)

    def update(self, sources, commits, outputs, method, key, mutate):
        controls = sources["controls"]
        doc = controls.parse(outputs[method][key], 262144)
        mutate(doc)
        outputs[method][key] = controls.encoded(doc)
        commits[method]["sessions"][key[0]]["arms"][key[1]]["prediction"] = controls.pin(outputs[method][key])

    def test_identical_programmes_share_one_full_target_capture(self):
        sources, panel, plan, commits, outputs, private = self.arrange()
        calls = []
        report = paired_programs.compare_programs(panel, plan, commits, outputs,
            lambda desc: calls.append(desc["path"]) or private[desc["path"]], np)
        self.assertEqual(len(calls), 39)
        self.assertEqual(len(set(calls)), 39)
        self.assertEqual(report["comparison_endpoint"]["value"]["value"], 0.)
        self.assertEqual(report["paired_mouse_interval"]["lower"], 0.)
        self.assertEqual(report["paired_mouse_interval"]["upper"], 0.)
        self.assertEqual((report["sessions"], report["mice"], report["queries_per_arm"]), (39, 10, 2042))
        self.assertAlmostEqual(report["programme_scores"]["candidate"]["primary"]["value"]["value"], math.log(3))
        self.assertTrue(report["all_312_outputs_validated_before_first_target_read"])
        self.assertFalse(report["restricted_direct_observation_qualified"])
        self.assertFalse(report["scientific_result_established"])
        sources["controls"].encoded(report)

    def test_pairing_retains_equal_session_then_mouse_weights_and_metric_direction(self):
        sources, panel, plan, commits, outputs, private = self.arrange()
        expected_mouse = {}
        for session in panel["sessions"]:
            loss = .1 + session["ordinal"] / 100
            expected_mouse.setdefault(session["mouse"], []).append(math.log(3) - loss)
            p = math.exp(-loss)
            for arm in sources["controls"].ARMS:
                self.update(sources, commits, outputs, "candidate", (session["session_token"], arm),
                    lambda doc, p=p: [row.update(probabilities=[p, (1-p)/2, (1-p)/2]) for row in doc["predictions"]])
        report = paired_programs.compare_programs(panel, plan, commits, outputs, lambda desc: private[desc["path"]], np)
        effects = np.asarray([sum(expected_mouse[mouse])/len(expected_mouse[mouse]) for mouse in sorted(expected_mouse)])
        expected = float(effects.mean())
        pooled = sum((math.log(3)-(.1+s["ordinal"]/100))*len(s["query_tokens"]) for s in panel["sessions"])/2042
        self.assertAlmostEqual(report["comparison_endpoint"]["value"]["value"], expected)
        self.assertNotAlmostEqual(expected, pooled, places=6)
        rng = np.random.Generator(np.random.PCG64(20261102))
        indices = rng.integers(0, 10, size=(10000, 10), dtype=np.int64)
        low, high = np.quantile(effects[indices].mean(axis=1), [.025, .975], method="linear")
        self.assertAlmostEqual(report["paired_mouse_interval"]["lower"], float(low))
        self.assertAlmostEqual(report["paired_mouse_interval"]["upper"], float(high))
        improved = report["equal_mouse_candidate_improvements"]["neural_wheel_plus_context"]
        self.assertGreater(improved["multiclass_Brier_mean_sum3"]["value"], 0)
        self.assertEqual(improved["top1_accuracy"]["value"], 0.)  # Both predict class0.

    def test_malformed_last_output_in_either_programme_prevents_all_targets(self):
        for method in paired_programs.METHODS:
            with self.subTest(method=method):
                sources, panel, plan, commits, outputs, _ = self.arrange()
                key = (panel["sessions"][-1]["session_token"], sources["controls"].ARMS[-1])
                self.update(sources, commits, outputs, method, key,
                    lambda doc: doc["predictions"][-1].update(probabilities=[.9, .9, .9]))
                calls = []
                with self.assertRaises(ValueError):
                    paired_programs.compare_programs(panel, plan, commits, outputs,
                        lambda desc: calls.append(desc), np)
                self.assertEqual(calls, [])

    def test_missing_output_and_cross_programme_policy_mismatch_prevent_targets(self):
        for mutation in ("output", "policy", "query_manifest"):
            with self.subTest(mutation=mutation):
                sources, panel, plan, commits, outputs, _ = self.arrange()
                token = panel["sessions"][-1]["session_token"]
                arm = sources["controls"].ARMS[-1]
                if mutation == "output":
                    outputs["candidate"].pop((token, arm))
                elif mutation == "policy":
                    commits["candidate"]["tuning_policy_sha256"] = "f" * 64
                else:
                    commits["candidate"]["sessions"][token]["arms"][arm]["query_manifest"]["sha256"] = "f" * 64
                calls = []
                with self.assertRaises(ValueError):
                    paired_programs.compare_programs(panel, plan, commits, outputs,
                        lambda desc: calls.append(desc), np)
                self.assertEqual(calls, [])

    def test_zero_true_probability_retains_infinity_and_undefined_pair(self):
        sources, panel, plan, commits, outputs, private = self.arrange()
        key = (panel["sessions"][0]["session_token"], "neural_wheel_plus_context")
        for method in paired_programs.METHODS:
            self.update(sources, commits, outputs, method, key,
                lambda doc: doc["predictions"][0].update(probabilities=[0., .5, .5]))
        report = paired_programs.compare_programs(panel, plan, commits, outputs, lambda desc: private[desc["path"]], np)
        self.assertEqual(report["comparison_endpoint"]["value"]["status"], "undefined")
        self.assertEqual(report["paired_mouse_interval"]["status"], "undefined_nonfinite_mouse_effect")
        for method in paired_programs.METHODS:
            self.assertEqual(report["programme_scores"][method]["primary"]["value"]["status"], "positive_infinity")
        sources["controls"].encoded(report)

    def test_external_mutations_during_target_read_cannot_change_captured_submissions(self):
        _, panel, plan, commits, outputs, private = self.arrange()
        def reader(desc):
            outputs["candidate"].clear()
            commits["candidate"].clear()
            panel["sessions"].clear()
            plan["sessions"].clear()
            return private[desc["path"]]
        report = paired_programs.compare_programs(panel, plan, commits, outputs, reader, np)
        self.assertEqual(report["comparison_endpoint"]["value"]["value"], 0.)
        self.assertEqual(report["protected_mapping_reads"], 39)

    def test_target_hash_error_is_rejected_before_second_programme_scoring(self):
        _, panel, plan, commits, outputs, private = self.arrange()
        calls = []
        with self.assertRaises(ValueError):
            paired_programs.compare_programs(panel, plan, commits, outputs,
                lambda desc: calls.append(desc["path"]) or private[desc["path"]] + b" ", np)
        self.assertEqual(len(calls), 1)

    def test_swapping_programmes_reverses_logloss_and_accuracy_contrasts(self):
        sources, panel, plan, commits, outputs, private = self.arrange()
        for key in outputs["candidate"]:
            self.update(sources, commits, outputs, "candidate", key,
                lambda doc: [row.update(probabilities=[.2, .4, .4]) for row in doc["predictions"]])
        report = paired_programs.compare_programs(panel, plan, commits, outputs, lambda desc: private[desc["path"]], np)
        swapped = paired_programs.compare_programs(panel, plan,
            {"reference": commits["candidate"], "candidate": commits["reference"]},
            {"reference": outputs["candidate"], "candidate": outputs["reference"]},
            lambda desc: private[desc["path"]], np)
        for metric in sources["comparison"].METRICS:
            a = report["equal_mouse_candidate_improvements"]["neural_wheel_plus_context"][metric]["value"]
            b = swapped["equal_mouse_candidate_improvements"]["neural_wheel_plus_context"][metric]["value"]
            self.assertAlmostEqual(a, -b)
        self.assertEqual(report["equal_mouse_candidate_improvements"]["neural_wheel_plus_context"]["top1_accuracy"]["value"], -1.)
        self.assertAlmostEqual(report["paired_mouse_interval"]["lower"], -swapped["paired_mouse_interval"]["upper"])


if __name__ == "__main__":
    unittest.main()
