"""Generated algebraic controls; no neural recordings, fitting or model calls."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import paired as p

sys.path.insert(0, str(p.LEGACY.parent))
import generated_control as g


def fixture():
    training = g.make_training()
    training["protocol"]["profile"] = "historical_symmetric"
    layout = {s: {"neural": [{"id": f"unit-{i}", "unit": "generated-units"} for i in range(78)],
                  "behavior": [{"id": c, "unit": "generated-units"} for c in p.BEHAVIOR]}
              for s in p.e.SESSIONS}
    training["channel_layout"] = layout
    source_plan = p.e.select(training)
    targets, author = g.make_artifacts(training, source_plan)
    for artifact in (targets, author):
        artifact["channel_layout"] = layout
        for row in artifact["cases"]:
            for kind, repeats in (("neural", 39), ("behavior", 2)):
                row[kind] = [values * repeats for values in row[kind]]
                row[kind + "_channel_ids"] = [c["id"] for c in layout[row["session_id"]][kind]]
    candidate_training = {"protocol": training["protocol"], "channel_layout": layout,
                          "candidate_id": "arbitrary-new-method", "code_sha256": "a" * 64, "cases": []}
    for row in training["cases"]:
        candidate_training["cases"].append({
            **{key: row[key] for key in ("session_id", "fold", "fit_sample_ids", "selection_sample_ids")},
            "dimensions": {str(d): {"training_neural_cc": .8 if d == 4 else .4,
                                     "training_behavior_cc": .8 if d == 8 else .4,
                                     "configuration_sha256": p.e.digest({"arbitrary_config_dimension": d})}
                           for d in p.e.DIMENSIONS}})
    candidate_plan = p.select_candidate(candidate_training)
    candidate = {"protocol": training["protocol"], "channel_layout": layout,
                 "candidate_id": candidate_training["candidate_id"], "code_sha256": "a" * 64,
                 "selection_plan_sha256": p.e.digest(candidate_plan), "cases": []}
    x, z = [-1., -1., 1., 1.], [-1., 1., -1., 1.]
    for row in targets["cases"]:
        for d in p.e.DIMENSIONS:
            result = {k: row[k] for k in ("session_id", "fold", "sample_ids", "neural_channel_ids", "behavior_channel_ids")}
            result.update(dimension=d, configuration_sha256=p.e.digest({"arbitrary_config_dimension": d}))
            for kind, repeats, rho in (("neural", 39, .3), ("behavior", 2, .7)):
                # The held-grid best is deliberately NOT the training-selected dimension.
                rho = .95 if d == 128 else rho
                result[kind] = [[rho*a + math.sqrt(1-rho*rho)*b,
                                 rho*b + math.sqrt(1-rho*rho)*a] * repeats for a, b in zip(x, z)]
            candidate["cases"].append(result)
    return training, targets, author, candidate_training, candidate_plan, candidate


class PairedScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training, cls.targets, cls.author, cls.ct, cls.plan, cls.candidate = fixture()
        cls.reference = p.freeze_reference(cls.training, cls.targets, cls.author)
        cls.ref_hash, cls.plan_hash = p.e.digest(cls.reference), p.e.digest(cls.plan)

    def score(self, **changes):
        args = dict(targets=self.targets, reference=self.reference, plan=self.plan, predictions=self.candidate,
                    reference_sha256=self.ref_hash, plan_sha256=self.plan_hash)
        args.update(changes)
        return p.compare(**args)

    def test_full_grid_and_independent_orthogonal_oracle(self):
        result = self.score()
        self.assertEqual(len(self.reference["source_grid_results"]["all_grid_scores"]), 1960)
        self.assertEqual(len(result["candidate_grid_scores"]), 280)
        self.assertEqual(len(result["candidate_selected_scores"]), 35)
        self.assertEqual(len(result["paired_fold_deltas"]), 245)
        self.assertEqual(len(result["paired_session_deltas"]), 49)
        # Each channel is rho*x + sqrt(1-rho^2)*z, x orthogonal to z.
        summary = result["paper_unit_summary"]["arbitrary-new-method"]
        self.assertAlmostEqual(summary["neural_cc"]["mean"], .3)
        self.assertAlmostEqual(summary["behavior_cc"]["mean"], .7)
        for row in result["paired_fold_deltas"]:
            if row["comparator"] == "linear":
                self.assertAlmostEqual(row["neural_cc_delta"], .1)
                self.assertAlmostEqual(row["behavior_cc_delta"], .1)
        self.assertEqual(result["scientific_improvement"], "not_assessed")
        self.assertEqual(result["scientific_reproduction"], "not_assessed")
        self.assertEqual(self.reference["scientific_reproduction"], "not_assessed")
        self.assertEqual(summary["neural_cc"]["n"], 35)

    def test_held_best_dimension_is_not_selected(self):
        result = self.score()
        self.assertEqual({r["dimension"] for r in result["candidate_selected_scores"]}, {8})
        best_held = [r for r in result["candidate_grid_scores"] if r["dimension"] == 128]
        self.assertTrue(all(r["neural"]["mean_cc"] > .9 for r in best_held))

    def test_no_silent_channel_or_sample_realignment(self):
        for kind in ("neural_channel_ids", "behavior_channel_ids", "sample_ids"):
            bad = copy.deepcopy(self.candidate)
            bad["cases"][0][kind].reverse()
            with self.subTest(kind=kind), self.assertRaises(p.e.ContractError):
                self.score(predictions=bad)

    def test_units_and_coordinates_are_part_of_identity(self):
        bad = copy.deepcopy(self.candidate)
        bad["channel_layout"][p.e.SESSIONS[0]]["behavior"][0]["unit"] = "new-scale"
        with self.assertRaisesRegex(p.e.ContractError, "identity/unit drift"):
            self.score(predictions=bad)

    def test_missing_duplicate_or_narrowed_candidate_grid_rejected(self):
        for mutation in ("missing", "duplicate", "only_selected"):
            bad = copy.deepcopy(self.candidate)
            if mutation == "missing":
                bad["cases"].pop()
            elif mutation == "duplicate":
                bad["cases"].append(bad["cases"][0])
            else:
                bad["cases"] = [r for r in bad["cases"] if r["dimension"] == 8]
            with self.subTest(mutation=mutation), self.assertRaises(p.e.ContractError):
                self.score(predictions=bad)

    def test_missing_flat_or_nonfinite_prediction_never_improves_score(self):
        for value in (None, float("nan"), float("inf"), "constant"):
            bad = copy.deepcopy(self.candidate)
            if value == "constant":
                for row in bad["cases"][0]["neural"]:
                    row[0] = 1
            else:
                bad["cases"][0]["neural"][0][0] = value
            with self.subTest(value=value), self.assertRaises(p.e.ContractError):
                self.score(predictions=bad)

    def test_counterfeit_author_reference_and_plan_rejected_by_owner_pins(self):
        bad = copy.deepcopy(self.reference)
        bad["source_grid_results"]["selected_scores"][0]["neural"]["mean_cc"] = -.9
        with self.assertRaisesRegex(p.e.ContractError, "reference changed"):
            self.score(reference=bad)
        bad_plan = copy.deepcopy(self.plan)
        bad_plan["cases"][0]["selected_dimension"] = 128
        with self.assertRaisesRegex(p.e.ContractError, "selection plan changed"):
            self.score(plan=bad_plan)

    def test_target_drift_rejected_even_with_same_samples(self):
        bad = copy.deepcopy(self.targets)
        bad["cases"][0]["neural"][0][0] += 1
        with self.assertRaisesRegex(p.e.ContractError, "targets changed"):
            self.score(targets=bad)

    def test_config_and_code_binding(self):
        for mutation in ("code", "config", "plan"):
            bad = copy.deepcopy(self.candidate)
            if mutation == "code":
                bad["code_sha256"] = "b" * 64
            elif mutation == "config":
                bad["cases"][0]["configuration_sha256"] = "b" * 64
            else:
                bad["selection_plan_sha256"] = "b" * 64
            with self.subTest(mutation=mutation), self.assertRaises(p.e.ContractError):
                self.score(predictions=bad)

    def test_author_grid_and_source_profile_are_not_optional(self):
        bad = copy.deepcopy(self.author)
        bad["cases"].pop()
        with self.assertRaises(p.e.ContractError):
            p.freeze_reference(self.training, self.targets, bad)
        bad_training = copy.deepcopy(self.training)
        bad_training["channel_layout"][p.e.SESSIONS[0]]["neural"][0]["id"] = "different-neuron"
        with self.assertRaisesRegex(p.e.ContractError, "training protocol/channel layout"):
            p.freeze_reference(bad_training, self.targets, self.author)
        for profile, lag in (("prospective_causal", 1), ("historical_symmetric", 2)):
            bad = copy.deepcopy(self.ct)
            bad["protocol"].update(profile=profile, neural_lag_samples=lag)
            with self.subTest(profile=profile, lag=lag), self.assertRaises(p.e.ContractError):
                p.select_candidate(bad)

    def test_selection_rejects_held_samples_and_partial_dimensions(self):
        for mutation in ("held", "dimension", "fold", "collision"):
            bad = copy.deepcopy(self.ct)
            if mutation == "held":
                bad["cases"][0]["selection_sample_ids"].append(0)
            elif mutation == "dimension":
                del bad["cases"][0]["dimensions"]["128"]
            elif mutation == "fold":
                bad["cases"].pop()
            else:
                bad["candidate_id"] = "linear"
            with self.subTest(mutation=mutation), self.assertRaises(p.e.ContractError):
                p.select_candidate(bad)

    def test_channel_mean_not_flattened_correlation(self):
        # Opposite signs cancel in the channel mean despite a high-variance first channel.
        truth = [[-100, -1], [-100, 1], [100, -1], [100, 1]]
        pred = [[a, -b] for a, b in truth]
        self.assertAlmostEqual(p.e.channel_cc(truth, pred)["mean_cc"], 0)

    def test_cli_select_freezes_same_canonical_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            source, out = Path(directory) / "training.json", Path(directory) / "plan.json"
            source.write_text(json.dumps(self.ct))
            result = subprocess.run([sys.executable, str(Path(p.__file__)), "select-candidate", "--training", str(source),
                                     "--output", str(out)], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(out.read_text()), self.plan)
            self.assertEqual(json.loads(result.stdout)["canonical_sha256"], self.plan_hash)


if __name__ == "__main__":
    unittest.main()
