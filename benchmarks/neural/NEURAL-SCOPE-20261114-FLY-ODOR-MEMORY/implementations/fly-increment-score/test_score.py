"""Generated software controls; no authentic measurements or model results."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

_path = Path(__file__).with_name("score.py")
_spec = importlib.util.spec_from_file_location("fly_score", _path)
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)
TARGET_SHA = "a" * 64
PLAN_SHA = "b" * 64


def episode(key, fly, *, genotype="VT062617", condition="pulse", role="primary",
            eligible=True, target=0, future=None):
    return {"episode_id": key, "trial_id": "trial-" + key, "fly_id": fly,
            "genotype": genotype, "condition": condition, "role": role,
            "eligible": eligible, "exclusion_reasons": [] if eligible else ["undefined_goal"],
            "target_mm_s": target if eligible else None, "future_reencounter": future}


def operands():
    # Three episodes from A versus one from B make pooled-episode scoring wrong.
    rows = [episode("a1", "A", future=False), episode("a2", "A", future=True),
            episode("a3", "A", condition="plume"), episode("b1", "B"),
            episode("c1", "C", eligible=False),
            episode("d1", "A", condition="no_odor", role="no_odor_diagnostic"),
            episode("e1", "E", genotype="52G12")]
    targets = {"schema": "fly-odor-evaluation-set/v1", "task_id": score.TASK_ID,
               "target_definition": score.DEFINITION, "target_units": "mm/s",
               "evaluation_plan_sha256": PLAN_SHA, "episodes": rows}
    def predictions(arm, values):
        return {"schema": "fly-odor-predictions/v1", "task_id": score.TASK_ID,
                "arm": arm, "access_mode": "frozen_program", "method_id": arm + "-method",
                "targets_sha256": TARGET_SHA, "evaluation_plan_sha256": PLAN_SHA,
                "predictions": [{"episode_id": key, "prediction_mm_s": value}
                                for key, value in values.items()]}
    nuisance = predictions("nuisance", {"a1": 2, "a2": 2, "a3": 2, "b1": 0, "d1": 100, "e1": 10})
    neural = predictions("neural_plus_nuisance", {"a1": 1, "a2": 1, "a3": 1, "b1": 3, "d1": 0, "e1": 0})
    return targets, nuisance, neural


def evaluate(operands_):
    return score.score(*operands_, targets_sha256=TARGET_SHA)


class PairedFlyScorerTests(unittest.TestCase):
    def test_hand_calculated_macro_preserves_animal_not_episode_weight(self):
        report = evaluate(operands())
        genotype = {row["genotype"]: row for row in report["genotype_reports"]}
        primary = genotype["VT062617"]["primary"]
        self.assertEqual(primary["fly_macro"], {"nuisance_mse_mm2_s2": 2.0,
                                              "neural_mse_mm2_s2": 5.0,
                                              "paired_loss_reduction_mm2_s2": -3.0})
        self.assertEqual((primary["census_episodes"], primary["eligible_episodes"]), (5, 4))
        self.assertEqual((primary["census_flies"], primary["scored_flies"]), (3, 2))
        self.assertEqual(primary["exclusion_reason_counts"], {"undefined_goal": 1})
        effects = {row["fly_id"]: row for row in primary["all_fly_effects"]}
        self.assertEqual(effects["A"]["paired_loss_reduction_mm2_s2"], 3.0)
        self.assertEqual(effects["B"]["paired_loss_reduction_mm2_s2"], -9.0)
        self.assertIsNone(effects["C"]["paired_loss_reduction_mm2_s2"])
        self.assertEqual(genotype["52G12"]["primary"]["fly_macro"]["paired_loss_reduction_mm2_s2"], 100)
        conditions = {row["condition"]: row for row in genotype["VT062617"]["condition_reports"]}
        self.assertEqual(conditions["pulse"]["fly_macro"]["paired_loss_reduction_mm2_s2"], -3)
        self.assertEqual(conditions["plume"]["fly_macro"]["paired_loss_reduction_mm2_s2"], 3)
        self.assertEqual(conditions["no_odor"]["fly_macro"]["paired_loss_reduction_mm2_s2"], 10000)

    def test_no_future_reencounter_or_diagnostic_filtering_of_primary(self):
        original = operands()
        changed = copy.deepcopy(original)
        for row in changed[0]["episodes"]:
            row["future_reencounter"] = not bool(row["future_reencounter"])
        for arm in changed[1:]:
            next(row for row in arm["predictions"] if row["episode_id"] == "d1")["prediction_mm_s"] = -777
        before = evaluate(original)["genotype_reports"]
        after = evaluate(changed)["genotype_reports"]
        for one, two in zip(before, after):
            self.assertEqual(one["primary"], two["primary"])

    def test_submission_failure_does_not_drop_missing_or_invalid_predictions(self):
        for arm_index in (1, 2):
            for mutation in ("missing", "extra", "duplicate", "ineligible", "nan", "bool", "overflow"):
                with self.subTest(arm=arm_index, mutation=mutation):
                    args = operands()
                    rows = args[arm_index]["predictions"]
                    if mutation == "missing":
                        rows.pop()
                    elif mutation in ("extra", "ineligible"):
                        rows.append({"episode_id": "c1" if mutation == "ineligible" else "unknown",
                                     "prediction_mm_s": 0})
                    elif mutation == "duplicate":
                        rows.append(copy.deepcopy(rows[0]))
                    else:
                        rows[0]["prediction_mm_s"] = {"nan": float("nan"), "bool": True, "overflow": 1e308}[mutation]
                    with self.assertRaises(score.InvalidEvaluation):
                        evaluate(args)

    def test_identity_units_and_eligibility_refusals(self):
        mutations = [
            lambda target: target.update(target_units="rad/s"),
            lambda target: target["episodes"].append(copy.deepcopy(target["episodes"][0])),
            lambda target: target["episodes"][1].update(genotype="52G12"),
            lambda target: target["episodes"][1].update(trial_id="trial-a1", condition="plume"),
            lambda target: target["episodes"][0].update(exclusion_reasons=["bad"]),
            lambda target: target["episodes"][4].update(exclusion_reasons=[]),
            lambda target: target["episodes"][4].update(target_mm_s=0),
            lambda target: target["episodes"][0].update(future_reencounter=1),
            lambda target: target["episodes"][0].update(target_mm_s=True),
            lambda target: target["episodes"][0].update(role=[]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                args = operands()
                mutation(args[0])
                with self.assertRaises(score.InvalidEvaluation):
                    evaluate(args)

    def test_each_mode_is_separate_and_pair_cannot_cross_modes(self):
        for mode in sorted(score.MODES):
            args = operands()
            args[1]["access_mode"] = args[2]["access_mode"] = mode
            self.assertEqual(evaluate(args)["access_mode"], mode)
        for field, value in (("access_mode", "direct_observation"),
                             ("evaluation_plan_sha256", "c" * 64),
                             ("targets_sha256", "c" * 64),
                             ("arm", "nuisance")):
            args = operands()
            args[2][field] = value
            with self.subTest(field=field), self.assertRaises(score.InvalidEvaluation):
                evaluate(args)

    def test_empty_eligible_census_returns_undefined_not_successful_zero(self):
        args = operands()
        for row in args[0]["episodes"]:
            row.update(eligible=False, exclusion_reasons=["undefined_goal"], target_mm_s=None)
        args[1]["predictions"] = args[2]["predictions"] = []
        for genotype in evaluate(args)["genotype_reports"]:
            self.assertEqual(genotype["primary"]["scored_flies"], 0)
            self.assertIsNone(genotype["primary"]["fly_macro"]["paired_loss_reduction_mm2_s2"])

    def test_row_order_is_irrelevant(self):
        args = operands()
        expected = evaluate(args)
        args[0]["episodes"].reverse()
        args[1]["predictions"].reverse()
        args[2]["predictions"].reverse()
        self.assertEqual(evaluate(args), expected)

    def test_source_authentication_duplicate_keys_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operand.json"
            for payload in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff'):
                path.write_bytes(payload)
                with self.subTest(payload=payload), self.assertRaises(score.InvalidEvaluation):
                    score.read_json(path, hashlib.sha256(payload).hexdigest())
            path.write_bytes(b'{}')
            with self.assertRaises(score.InvalidEvaluation):
                score.read_json(path, "0" * 64)

    def test_cli_private_exclusive_output_and_failed_input_leaves_no_score(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            targets, nuisance, neural = operands()
            payload = json.dumps(targets).encode()
            target_sha = hashlib.sha256(payload).hexdigest()
            for arm in (nuisance, neural):
                arm["targets_sha256"] = target_sha
            arguments = []
            for name, value in (("targets", targets), ("nuisance", nuisance), ("neural", neural)):
                payload = json.dumps(value).encode()
                path = directory / (name + ".json")
                path.write_bytes(payload)
                arguments.extend(["--" + name, str(path), "--" + name + "-sha256", hashlib.sha256(payload).hexdigest()])
            output = directory / "score.json"
            arguments.extend(["--output", str(output)])
            self.assertEqual(score.main(arguments), 0)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            report_bytes = output.read_bytes()
            with self.assertRaises(SystemExit) as error:
                score.main(arguments)
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_bytes(), report_bytes)
            fresh = directory / "must-not-exist.json"
            arguments[-1] = str(fresh)
            (directory / "neural.json").write_text("{}")
            with self.assertRaises(SystemExit) as error:
                score.main(arguments)
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(fresh.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
