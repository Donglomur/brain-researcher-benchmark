"""Generated software controls; none of these arrays are biological observations."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("vestibular_evaluator", Path(__file__).with_name("evaluate.py"))
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)


def fixture():
    animals = ["generated-A", "generated-B", "generated-C"]
    neurons, pairs, groups, cases = [], [], [], []
    for animal, n, p in zip(animals, (17, 16, 16), (12, 12, 11)):
        ns = [f"{animal}-neuron-{i}" for i in range(n)]
        neurons.extend({"id": name, "animal_id": animal} for name in ns)
        for i in range(p):
            pair_id, group_id = f"{animal}-pair-{i}", f"{animal}-group-{i}"
            members = [ns[(2 * i) % n], ns[(2 * i + 1) % n]]
            pairs.append({"id": pair_id, "animal_id": animal, "neuron_ids": members})
            groups.append({"id": group_id, "animal_id": animal, "session_id": animal + "-session",
                           "recording_id": "recording-" + str(i), "stratum": "simultaneous_pair",
                           "pair_id": pair_id, "neuron_ids": members})
            cases.append({"id": group_id + "-repeat", "group_id": group_id, "condition": "naturalistic",
                          "repeat_id": "repeat-1", "sample_ticks": [9007199254740993, 9007199254740994],
                          "valid_mask": [True, True], "target": [0.0, 1.0], "prior": [0.0, 0.0]})
    coverage = []
    for animal in animals:
        local = [g["id"] for g in groups if g["animal_id"] == animal]
        for condition in E.CONDITIONS:
            for stratum in E.STRATA:
                available = condition == "naturalistic" and stratum == "simultaneous_pair"
                cell = {"animal_id": animal, "condition": condition, "stratum": stratum,
                        "status": "available" if available else "unavailable",
                        "group_repeats": [{"group_id": g, "repeat_ids": ["repeat-1"]} for g in local] if available else [],
                        "unavailable_groups": {g: "generated unavailable condition" for g in local}
                        if stratum == "simultaneous_pair" and not available else {}}
                if not available:
                    cell["reason"] = "generated unavailable condition or stratum"
                coverage.append(cell)
    ref = {"schema": "vestibular-reference-v1", "task_id": E.TASK, "evaluation_id": "generated-evaluation",
           "evidence_id": "1" * 64, "access_condition": "numerical",
           "binding": {"kind": "generated_control", "source_version": "no biological data",
                       "source_sha256": "2" * 64, "roster_sha256": "3" * 64, "protocol_sha256": "4" * 64,
                       "target_unit": "generated-velocity-unit", "tick_unit": "generated-native-tick",
                       "mask_basis": "input_acquisition_metadata",
                       "prior": {"id": "generated-training-prior", "selection_split": "training_only",
                                 "selection_protocol_sha256": "5" * 64}},
           "animals": animals, "neurons": neurons, "pairs": pairs, "groups": groups,
           "excluded_pairs": {}, "excluded_neurons": {}, "conditions": list(E.CONDITIONS),
           "additional_conditions": {}, "coverage": coverage, "cases": cases}
    return ref, submission(ref)


def submission(ref, mode="fixed_program"):
    return {"schema": "vestibular-predictions-v1", "task_id": E.TASK,
            "evaluation_id": ref["evaluation_id"], "evidence_id": ref["evidence_id"],
            "access_condition": ref["access_condition"], "mode": mode,
            "cases": [{"id": c["id"], "sample_ticks": c["sample_ticks"][:],
                       "prediction": [v if v is not None else 0.0 for v in c["target"]]} for c in ref["cases"]]}


def primary(result, animal="generated-A", condition="naturalistic"):
    return next(r for r in result["primary_animal_condition_vector"] if r["animal_id"] == animal and r["condition"] == condition)


class EvaluatorControls(unittest.TestCase):
    def setUp(self):
        self.ref, self.pred = fixture()

    def assert_failure(self, ref=None, pred=None, status=None):
        result = E.evaluate(self.ref if ref is None else ref, self.pred if pred is None else pred)
        self.assertNotEqual(result["status"], "valid_submission")
        if status:
            self.assertEqual(result["status"], status)
        self.assertIsNone(result["primary_animal_condition_vector"])
        self.assertFalse(result["scientific_qualification"])
        return result

    def test_complete_census_perfect_prediction_and_visible_unavailability(self):
        result = E.evaluate(self.ref, self.pred)
        self.assertEqual(result["status"], "valid_submission")
        self.assertEqual(len(result["primary_animal_condition_vector"]), 27)
        self.assertEqual(result["coverage"]["pair_census"], 35)
        self.assertEqual(result["coverage"]["neuron_census"], 49)
        self.assertEqual(result["coverage"]["required_cases"], 35)
        for animal in self.ref["animals"]:
            row = primary(result, animal)
            self.assertEqual(row["candidate_mse"], 0.0)
            self.assertEqual(row["prior_mse"], 0.5)
            self.assertEqual(row["prior_improvement"], 0.5)
        unavailable = primary(result, condition="sinusoidal1Hz")
        self.assertIsNone(unavailable["candidate_mse"])
        self.assertTrue(unavailable["reason"])
        self.assertFalse(result["interpretation"]["scientific_qualification"])
        self.assertIsNone(result["interpretation"]["cross_animal_primary_aggregate"])
        self.assertTrue(any(len(gs) > 1 for gs in result["coverage"]["shared_neuron_groups"].values()))

    def test_equal_repeat_then_equal_group_not_sample_pooling(self):
        animal = self.ref["animals"][0]
        gs = [g["id"] for g in self.ref["groups"] if g["animal_id"] == animal]
        cell = next(c for c in self.ref["coverage"] if (c["animal_id"], c["condition"], c["stratum"]) == (animal, "naturalistic", "simultaneous_pair"))
        cell["group_repeats"] = [{"group_id": gs[0], "repeat_ids": ["r1", "r2"]}, {"group_id": gs[1], "repeat_ids": ["r1"]}]
        cell["unavailable_groups"] = {g: "generated excluded recording condition" for g in gs[2:]}
        self.ref["cases"] = [c for c in self.ref["cases"] if c["group_id"] not in gs]
        settings = [(gs[0], "r1", 1, 1.0, 3.0), (gs[0], "r2", 3, 3.0, 1.0), (gs[1], "r1", 2, 2.0, 4.0)]
        predictions = {}
        for g, repeat, n, p, prior in settings:
            key = g + repeat
            self.ref["cases"].append({"id": key, "group_id": g, "condition": "naturalistic", "repeat_id": repeat,
                                      "sample_ticks": list(range(n)), "valid_mask": [True] * n,
                                      "target": [0.0] * n, "prior": [prior] * n})
            predictions[key] = [p] * n
        candidate = submission(self.ref)
        for row in candidate["cases"]:
            if row["id"] in predictions:
                row["prediction"] = predictions[row["id"]]
        row = primary(E.evaluate(self.ref, candidate))
        self.assertEqual(row["candidate_mse"], 4.5)
        self.assertEqual(row["prior_mse"], 10.5)
        self.assertEqual(row["prior_improvement"], 6.0)
        self.assertEqual(row["secondary_sample_weighted_mse"], 6.0)
        self.assertEqual(row["valid_samples"], 6)
        self.assertEqual(row["repeat_count"], 3)

    def test_constant_targets_and_scale_sign_diagnostics(self):
        result = E.repeat_metrics([-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0])
        self.assertAlmostEqual(result["mse"], 2.0 / 3.0)
        self.assertAlmostEqual(result["r2"], 0.0)
        self.assertAlmostEqual(result["pearson_r"], 1.0)
        self.assertAlmostEqual(result["scale_slope"], 2.0)
        self.assertEqual(result["sign_agreement"], 1.0)
        flip = E.repeat_metrics([-1.0, 1.0], [1.0, -1.0])
        self.assertEqual(flip["scale_slope"], -1.0)
        self.assertEqual(flip["sign_agreement"], 0.0)
        constant = E.repeat_metrics([2.0, 2.0], [1.0, 1.0])
        self.assertIsNone(constant["r2"])
        self.assertIsNone(constant["pearson_r"])
        self.assertEqual(constant["mse"], 1.0)

    def test_missing_extra_duplicate_and_misaligned_predictions_fail_whole_submission(self):
        mutations = []
        x = copy.deepcopy(self.pred); x["cases"].pop(); mutations.append(x)
        x = copy.deepcopy(self.pred); x["cases"].append(copy.deepcopy(x["cases"][0])); mutations.append(x)
        x = copy.deepcopy(self.pred); x["cases"][0]["id"] = "unknown"; mutations.append(x)
        x = copy.deepcopy(self.pred); x["cases"][0]["sample_ticks"][0] += 1; mutations.append(x)
        x = copy.deepcopy(self.pred); x["cases"][0]["sample_ticks"][0] = float(x["cases"][0]["sample_ticks"][0]); mutations.append(x)
        x = copy.deepcopy(self.pred); x["cases"][0]["prediction"].append(0); mutations.append(x)
        x = copy.deepcopy(self.pred); x["cases"][0]["valid_mask"] = [False, True]; mutations.append(x)
        for x in mutations:
            with self.subTest(mutation=x["cases"][0]):
                self.assert_failure(pred=x, status="invalid_submission")

    def test_nonfinite_boolean_and_extreme_prediction_refusal(self):
        for value in (True, False, float("nan"), float("inf"), "1.0", 1e308, 10 ** 1000, 2 ** 53 + 1):
            x = copy.deepcopy(self.pred); x["cases"][0]["prediction"][0] = value
            with self.subTest(value_type=type(value).__name__):
                self.assert_failure(pred=x, status="invalid_submission")

    def test_metric_integer_precision_cannot_hide_prediction_error(self):
        self.ref["cases"][0]["target"] = [2 ** 53 + 1, 2 ** 53 + 1]
        self.ref["cases"][0]["prior"] = [2 ** 53, 2 ** 53]
        self.pred["cases"][0]["prediction"] = [2 ** 53, 2 ** 53]
        self.assert_failure(status="invalid_reference")
        self.assertEqual(E.finite(2 ** 53), float(2 ** 53))

    def test_arithmetic_underflow_is_not_perfect_prediction_or_constant_target(self):
        self.assertEqual(E.mean([5e-324, 5e-324]), 5e-324)
        self.assertEqual(E.mean([-5e-324, -5e-324]), -5e-324)
        self.assertEqual(E.mean([1e308, 1e308]), 1e308)
        self.assertEqual(E.mean([-1.0, 1.0]), 0.0)
        with self.assertRaises(E.Invalid):
            E.mean([0.0, 5e-324])
        tiny_ref, _ = fixture()
        for case in tiny_ref["cases"]:
            case.update(sample_ticks=[0], valid_mask=[True], target=[0.0], prior=[0.0])
        tiny_pred = submission(tiny_ref)
        for case in tiny_pred["cases"]:
            case["prediction"] = [2.2227587494850775e-162]
        tiny_result = E.evaluate(tiny_ref, tiny_pred)
        self.assertEqual(tiny_result["status"], "valid_submission")
        self.assertEqual(primary(tiny_result)["candidate_mse"], 5e-324)
        self.assertEqual(primary(tiny_result)["secondary_sample_weighted_mse"], 5e-324)
        with self.assertRaises(E.Invalid):
            E.repeat_metrics([0.0, 0.0], [1e-200, 1e-200])
        with self.assertRaises(E.Invalid):
            E.repeat_metrics([0.0, 1e-200], [0.0, 1e-200])
        self.ref["cases"][0]["target"] = [0.0, 1e-200]
        self.ref["cases"][0]["prior"] = [0.0, 1e-200]
        self.assert_failure(pred=submission(self.ref), status="invalid_reference")

    def test_masked_samples_still_need_finite_complete_predictions(self):
        self.ref["cases"][0]["valid_mask"] = [False, True]
        self.ref["cases"][0]["target"][0] = None
        self.pred["cases"][0]["prediction"][0] = 999.0
        result = E.evaluate(self.ref, self.pred)
        self.assertEqual(result["status"], "valid_submission")
        self.assertEqual(primary(result)["candidate_mse"], 0.0)
        self.pred["cases"][0]["prediction"][0] = float("nan")
        self.assert_failure(status="invalid_submission")

    def test_reference_census_repeat_and_mask_admission(self):
        variants = []
        x = copy.deepcopy(self.ref); x["neurons"].pop(); variants.append(x)
        x = copy.deepcopy(self.ref); x["pairs"].pop(); variants.append(x)
        x = copy.deepcopy(self.ref); x["cases"].pop(); variants.append(x)
        x = copy.deepcopy(self.ref); x["coverage"].pop(); variants.append(x)
        x = copy.deepcopy(self.ref); x["cases"][0]["valid_mask"] = [False, False]; variants.append(x)
        x = copy.deepcopy(self.ref); x["cases"][0]["valid_mask"] = [1, 1]; variants.append(x)
        x = copy.deepcopy(self.ref); x["binding"]["mask_basis"] = "best_target_correlation"; variants.append(x)
        x = copy.deepcopy(self.ref); x["binding"]["prior"]["selection_split"] = "held_target_oracle"; variants.append(x)
        x = copy.deepcopy(self.ref); x["coverage"][2].pop("reason"); variants.append(x)
        for ref in variants:
            with self.subTest(case=variants.index(ref)):
                self.assert_failure(ref=ref, status="invalid_reference")

    def test_no_pseudopopulation_cross_animal_or_duplicate_group_alias(self):
        variants = []
        x = copy.deepcopy(self.ref); x["groups"][0]["neuron_ids"].append(x["neurons"][2]["id"]); variants.append(x)
        x = copy.deepcopy(self.ref); x["groups"][0]["animal_id"] = x["animals"][1]; variants.append(x)
        x = copy.deepcopy(self.ref); x["groups"].append(dict(x["groups"][0], id="alias")); variants.append(x)
        x = copy.deepcopy(self.ref); x["groups"][0]["pair_id"] = x["pairs"][1]["id"]; variants.append(x)
        for ref in variants:
            self.assert_failure(ref=ref, status="invalid_reference")

    def test_single_neuron_stratum_never_changes_pair_primary(self):
        ref = self.ref
        animal = ref["animals"][0]
        gid = "generated-single"
        ref["groups"].append({"id": gid, "animal_id": animal, "session_id": "single-session", "recording_id": "single-recording",
                              "stratum": "single_neuron", "neuron_ids": [ref["neurons"][0]["id"]], "pair_id": None})
        for cell in ref["coverage"]:
            if cell["animal_id"] == animal and cell["stratum"] == "single_neuron":
                if cell["condition"] == "naturalistic":
                    cell.update(status="available", group_repeats=[{"group_id": gid, "repeat_ids": ["one"]}])
                    cell.pop("reason")
                else:
                    cell["unavailable_groups"] = {gid: "generated missing condition"}
        ref["cases"].append({"id": "single-case", "group_id": gid, "condition": "naturalistic", "repeat_id": "one",
                             "sample_ticks": [0], "valid_mask": [True], "target": [0.0], "prior": [0.0]})
        candidate = submission(ref); candidate["cases"][-1]["prediction"] = [100.0]
        result = E.evaluate(ref, candidate)
        self.assertEqual(primary(result)["candidate_mse"], 0.0)
        row = next(x for x in result["single_neuron_diagnostics"] if x["animal_id"] == animal and x["condition"] == "naturalistic")
        self.assertEqual(row["candidate_mse"], 10000.0)

    def test_mode_comparison_uses_identical_reference_support_and_exposure(self):
        investigation = copy.deepcopy(self.pred); investigation["mode"] = "case_investigation"
        for case in self.pred["cases"]:
            case["prediction"] = [v + 1 for v in case["prediction"]]
        result = E.compare(self.ref, self.pred, investigation)
        self.assertEqual(result["status"], "valid_comparison")
        self.assertEqual(next(x for x in result["primary_comparison"] if x["status"] == "available")["investigation_improvement"], 1.0)
        for key in ("evidence_id", "access_condition", "evaluation_id"):
            bad = copy.deepcopy(investigation); bad[key] = "different"
            failure = E.compare(self.ref, self.pred, bad)
            self.assertEqual(failure["status"], "invalid_comparison")
            self.assertIsNone(failure["primary_comparison"])

    def test_order_invariance_and_exact_large_integer_clocks(self):
        baseline = E.evaluate(self.ref, self.pred)
        self.pred["cases"].reverse()
        for rows in (self.ref["cases"], self.ref["groups"], self.ref["coverage"]):
            rows.reverse()
        actual = E.evaluate(self.ref, self.pred)
        self.assertEqual(baseline["primary_animal_condition_vector"], actual["primary_animal_condition_vector"])
        self.assertEqual(baseline["repeat_diagnostics"], actual["repeat_diagnostics"])

    def test_cli_hash_limits_duplicate_keys_and_malformed_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference.json"; candidate = root / "prediction.json"
            raw = (json.dumps(self.ref) + "\n").encode(); reference.write_bytes(raw)
            candidate.write_text(json.dumps(self.pred))
            arguments = ["--reference", str(reference), "--reference-sha256", hashlib.sha256(raw).hexdigest(),
                         "--submission", str(candidate), "--max-reference-bytes", str(len(raw)),
                         "--max-submission-bytes", "100000"]
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = E.main(arguments)
            self.assertEqual(code, 0); self.assertEqual(json.loads(output.getvalue())["status"], "valid_submission")
            for index, limit in ((7, len(raw) - 1), (9, 1)):
                too_small = arguments[:]; too_small[index] = str(limit)
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(E.main(too_small), 2)
                self.assertEqual(json.loads(output.getvalue())["status"], "invalid_input")
            bad_hash = arguments[:]; bad_hash[3] = "0" * 64
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(E.main(bad_hash), 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "invalid_reference")
            candidate.write_text('{"cases":[],"cases":[]}')
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(E.main(arguments), 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "invalid_input")
            candidate.write_text("[" * 3000 + "0" + "]" * 3000)
            reference.unlink()  # malformed candidate is refused before any reference read
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(E.main(arguments), 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
