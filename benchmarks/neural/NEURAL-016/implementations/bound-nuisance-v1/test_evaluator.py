"""Generated software controls; no authentic signals, model fitting or outcomes."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scorer = load("bound_neural016", PACKAGE / "evaluator.py")
fixture = load("previous_neural016_fixture", PACKAGE.parent / "initial-evaluator-v1" / "tests" / "test_evaluator.py")


def packets():
    protocol, target, old = fixture.packets()
    protocol["recipe"]["primary_metric"] = "delta_r2"
    digest = scorer.base.canonical_hash(protocol)
    target["protocol_sha256"] = digest
    nuisance = {"schema_version": 1, "task_id": "NEURAL-016", "protocol_sha256": digest,
                "predictions": [{"row_id": row["row_id"], "nuisance": row["nuisance"]} for row in old["predictions"]],
                "fit_provenance": []}
    candidate = {"schema_version": 1, "task_id": "NEURAL-016", "protocol_sha256": digest,
                 "predictions": [{"row_id": row["row_id"], "full": row["full"]} for row in old["predictions"]],
                 "fit_provenance": [], "claimed_delta_r2": 0.2}
    for record in old["fit_provenance"]:
        common = {"fold_id": record["fold_id"], "fit_row_ids": record["fit_row_ids"],
                  "recipe_sha256": scorer.base.canonical_hash(protocol["recipe"])}
        nuisance["fit_provenance"].append(dict(common, nuisance_artifact_sha256="1" * 64))
        candidate["fit_provenance"].append(dict(common, full_artifact_sha256="2" * 64))
    raw = json.dumps(nuisance).encode()
    return protocol, target, candidate, raw, hashlib.sha256(raw).hexdigest()


def run(inputs):
    p, t, c, raw, pin = inputs
    return scorer.evaluate(p, t, c, nuisance_bytes=raw, expected_nuisance_sha256=pin)


class BoundNuisanceTests(unittest.TestCase):
    def test_exact_sse_and_sign_oracles(self):
        inputs = packets()
        result = run(inputs)
        # Each target block has SST=20; nuisance SSE=4 and perfect full SSE=0.
        self.assertAlmostEqual(result["primary_estimate"], 0.2)
        self.assertAlmostEqual(result["absolute_summary"]["estimate"]["nuisance_r2"], 0.8)
        self.assertEqual(result["full_prediction_statistic"]["value"], 1.0)
        self.assertAlmostEqual(result["claim_score"]["absolute_error"], 0)
        inputs[2]["claimed_delta_r2"] = -0.8
        for row in inputs[2]["predictions"]:
            row["full"] = 0
        negative = run(inputs)
        self.assertAlmostEqual(negative["primary_estimate"], -0.8)
        self.assertAlmostEqual(negative["claim_score"]["absolute_error"], 0)
        self.assertEqual(negative["full_prediction_statistic"]["value"], 0)
        self.assertFalse(negative["admission"]["research_qualified"])

    def test_bias_penalty_and_claim_error(self):
        inputs = packets()
        for row in inputs[2]["predictions"]:
            row["full"] += 10
        result = run(inputs)
        self.assertAlmostEqual(result["primary_estimate"], -19.8)
        self.assertAlmostEqual(result["summary"]["estimate"]["delta_explained_variance"], 0.2)
        self.assertAlmostEqual(result["claim_score"]["absolute_error"], 20)

    def test_absolute_metric_hierarchy_not_pooled_rows(self):
        # P1/e1 blocks: 1,-1 ->0; P1/e2:1; P1=0.5. P2=-1. Macro=-0.25.
        blocks = []
        for person, electrode, value in [("1", "a", 1), ("1", "a", -1), ("1", "b", 1), ("2", "a", -1)]:
            blocks.append({"participant_id": person, "electrode_id": electrode,
                           **{key: value for key in ("nuisance_r2", "full_r2", "nuisance_explained_variance", "full_explained_variance")}})
        summary = scorer.absolute_summary(blocks)
        self.assertEqual(summary["estimate"]["full_r2"], -0.25)
        self.assertEqual([p["full_r2"] for p in summary["participants"]], [0.5, -1])

    def test_candidate_cannot_supply_nuisance(self):
        for location in ("prediction", "fit", "top"):
            inputs = packets()
            candidate = inputs[2]
            if location == "prediction":
                candidate["predictions"][0]["nuisance"] = 1e6
            elif location == "fit":
                candidate["fit_provenance"][0]["nuisance_artifact_sha256"] = "9" * 64
            else:
                candidate["expected_nuisance_sha256"] = "9" * 64
            with self.subTest(location=location), self.assertRaisesRegex(scorer.ContractError, "incorrect fields"):
                run(inputs)

    def test_replaced_comparator_and_byte_rewrite_rejected(self):
        for change in ("values", "whitespace", "artifact"):
            p, t, c, raw, pin = packets()
            nuisance = json.loads(raw)
            if change == "values":
                for row in nuisance["predictions"]:
                    row["nuisance"] = 1e6
                changed = json.dumps(nuisance).encode()
            elif change == "artifact":
                nuisance["fit_provenance"][0]["nuisance_artifact_sha256"] = "9" * 64
                changed = json.dumps(nuisance).encode()
            else:
                changed = raw + b"\n"
            with self.subTest(change=change), self.assertRaisesRegex(scorer.ContractError, "file hash mismatch"):
                run((p, t, c, changed, pin))

    def test_valid_pin_does_not_skip_protocol_or_fit_validation(self):
        for change in ("protocol", "fit", "missing", "duplicate", "extra", "nan"):
            p, t, c, raw, _ = packets()
            nuisance = json.loads(raw)
            if change == "protocol": nuisance["protocol_sha256"] = "0" * 64
            elif change == "fit": nuisance["fit_provenance"][0]["fit_row_ids"] = [c["predictions"][0]["row_id"]]
            elif change == "missing": nuisance["predictions"].pop()
            elif change == "duplicate": nuisance["predictions"].append(copy.deepcopy(nuisance["predictions"][0]))
            elif change == "extra": nuisance["predictions"].append({"row_id": "extra", "nuisance": 0})
            else: nuisance["predictions"][0]["nuisance"] = float("nan")
            changed = json.dumps(nuisance).encode()
            with self.subTest(change=change), self.assertRaises(scorer.ContractError):
                run((p, t, c, changed, hashlib.sha256(changed).hexdigest()))

    def test_full_row_and_fit_coverage(self):
        for change in ("missing", "extra", "duplicate", "nan", "fit"):
            inputs = packets()
            c = inputs[2]
            if change == "missing": c["predictions"].pop()
            elif change == "extra": c["predictions"].append({"row_id": "extra", "full": 0})
            elif change == "duplicate": c["predictions"].append(copy.deepcopy(c["predictions"][0]))
            elif change == "nan": c["predictions"][0]["full"] = float("nan")
            else: c["fit_provenance"][0]["fit_row_ids"] = [c["predictions"][0]["row_id"]]
            with self.subTest(change=change), self.assertRaises(scorer.ContractError):
                run(inputs)

    def test_order_independence_and_no_mutation(self):
        inputs = packets()
        before = copy.deepcopy(inputs)
        expected = run(inputs)
        self.assertEqual(inputs, before)
        inputs[1]["values"].reverse()
        inputs[2]["predictions"].reverse()
        result = run(inputs)
        self.assertEqual(result["summary"], expected["summary"])
        self.assertEqual(result["absolute_summary"], expected["absolute_summary"])

    def test_full_only_null_uses_same_nuisance(self):
        inputs = packets()
        p, _, c, raw, _ = inputs
        nuisance = json.loads(raw)
        null = {"permutation_id": "generated-shift", "control": "joint_linguistic_circular_shift_uniform_time",
                "refitted_recipe_sha256": scorer.base.canonical_hash(p["recipe"]), "shift_manifest_sha256": "3" * 64,
                "predictions": [{"row_id": row["row_id"], "full": row["nuisance"]} for row in nuisance["predictions"]],
                "fit_provenance": copy.deepcopy(c["fit_provenance"])}
        c["null_predictions"] = [null]
        result = run(inputs)
        self.assertEqual(result["null_control"]["replicates"][0]["estimate"]["delta_r2"], 0)
        self.assertEqual(result["null_control"]["status"], "supplied_unverified_exchangeability")
        null["predictions"][0]["nuisance"] = 123
        with self.assertRaisesRegex(scorer.ContractError, "incorrect fields"):
            run(inputs)

    def test_metric_convention_and_strict_json(self):
        inputs = packets()
        inputs[0]["recipe"]["primary_metric"] = "delta_explained_variance"
        with self.assertRaisesRegex(scorer.ContractError, "must be delta_r2"):
            run(inputs)
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(scorer.ContractError):
                scorer.strict_json(raw)

    def test_cli_preserves_score_on_invalid_comparator_before_target_read(self):
        p, t, c, raw, pin = packets()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, packet in (("protocol", p), ("private-targets", t), ("candidate", c)):
                (root / (name + ".json")).write_text(json.dumps(packet))
            (root / "operator-nuisance.json").write_bytes(raw)
            command = [sys.executable, "-B", str(PACKAGE / "evaluator.py")]
            for name in ("protocol", "private-targets", "candidate", "operator-nuisance"):
                command.extend(["--" + name, str(root / (name + ".json"))])
            output = root / "score.json"
            command.extend(["--expected-nuisance-sha256", pin, "--output", str(output)])
            ok = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            preserved = output.read_bytes()
            self.assertEqual(json.loads(preserved)["operator_nuisance_file_sha256"], pin)
            (root / "private-targets.json").unlink()
            (root / "operator-nuisance.json").write_bytes(raw + b"\n")
            bad = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("nuisance file hash mismatch", bad.stderr)
            self.assertNotIn("Traceback", bad.stderr)
            self.assertEqual(output.read_bytes(), preserved)


if __name__ == "__main__":
    unittest.main()
