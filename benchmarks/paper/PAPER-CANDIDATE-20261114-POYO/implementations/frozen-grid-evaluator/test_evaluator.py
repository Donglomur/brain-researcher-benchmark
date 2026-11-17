"""Invented POYO grids only; no original traces, learning or scientific qualification."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("poyo_evaluator_under_test", HERE / "evaluator.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def fixture():
    provenance = pin(b"INVENTED ONLY: not authentic scientific evidence")
    families = sorted(ev.FAMILIES)
    corpus = [dict(session_id=f"s{i:03}", animal_id=f"a{i % 7}",
                   source_family=families[i % 4], source=provenance,
                   normalization=dict(mean=[0, 0], std=[1, 1], provenance=provenance))
              for i in range(158)]
    held = ["s156", "s157"]
    design = dict(task_id=ev.TASK, schema="poyo_frozen_grid_v1", policy=ev.POLICY,
                  corpus=corpus, pretraining_sessions=["s000"],
                  architecture="invented-shared-architecture", authority=provenance,
                  budgets=[dict(budget_id="b1", adaptation_trials=1, held_sessions=held),
                           dict(budget_id="b2", adaptation_trials=2, held_sessions=held)], cases=[])
    submission = dict(task_id=ev.TASK, schema="poyo_predictions_v1", policy=ev.POLICY, results=[])
    targets = dict(schema="poyo_targets_v1", cases=[])
    for budget in design["budgets"]:
        for session in held:
            # One duplicated timestamp and two dimensions of very unequal variance.
            times = [0, 1, 1, 2] if session == "s156" else [0, 1, 1, 2, 3, 4]
            vals = [[t - 1, 10 * (t - 1)] for t in times]
            support = [dict(row_id=f"r{i}", trial_id="test", timestamp=t) for i, t in enumerate(times)]
            key = dict(budget_id=budget["budget_id"], session_id=session)
            design["cases"].append(dict(**key, adaptation_trials=[f"adapt{i}" for i in range(budget["adaptation_trials"])],
                                        development_trials=["dev"], rows=support, support_provenance=provenance))
            targets["cases"].append(dict(**key, rows=[dict(row_id=x["row_id"], values=v) for x, v in zip(support, vals)]))
            for method in ev.METHODS:
                predictions = vals if method == "pretrained" else [[0, 0] for _ in vals]
                submission["results"].append(dict(**key, method=method,
                    rows=[dict(row_id=x["row_id"], values=v) for x, v in zip(support, predictions)]))
    return design, submission, targets


class EvaluatorTests(unittest.TestCase):
    def run_case(self, design, submission, targets):
        body = encode(design)
        calls = []
        result = ev.evaluate(body, pin(body), encode(submission), lambda: calls.append("private") or encode(targets))
        self.assertEqual(calls, ["private"])
        return result

    def refused_before_targets(self, design, submission):
        body = encode(design)
        calls = []
        with self.assertRaises(ValueError):
            ev.evaluate(body, pin(body), encode(submission), lambda: calls.append("private"))
        self.assertEqual(calls, [])

    def test_full_corpus_and_held_subset_are_separate(self):
        d, p, t = fixture()
        out = self.run_case(d, p, t)
        self.assertEqual((out["corpus_sessions"], out["corpus_animals"], out["cases"], len(out["results"])), (158, 7, 4, 16))
        self.assertFalse(out["scientific_qualification"])
        self.assertFalse(out["historical_reproduction"])
        self.assertEqual({x["sessions"] for x in out["summaries"] if x["group"] == "all"}, {2})

    def test_duplicate_timestamp_pooling_precedes_error(self):
        d, p, t = fixture()
        row = p["results"][0]
        row["rows"][1]["values"] = [-2, -20]
        row["rows"][2]["values"] = [2, 20]
        out = self.run_case(d, p, t)
        result = out["results"][0]
        self.assertEqual((result["occurrences"], result["stitched_samples"], result["r2"]), (4, 3, 1.0))

    def test_uniform_dimensions_not_variance_weighted(self):
        d, p, t = fixture()
        for row in p["results"][0]["rows"]:
            row["values"] = [row["values"][0] + 1, row["values"][1]]
        out = self.run_case(d, p, t)["results"][0]
        self.assertEqual(out["dimension_r2"], [-0.5, 1.0])
        self.assertEqual(out["r2"], 0.25)
        self.assertNotAlmostEqual(out["r2"], 1 - 3 / 202)

    def test_equal_session_mean_and_negative_contrasts(self):
        d, p, t = fixture()
        # Different sample counts/target variances must not reweight the two sessions.
        for record in p["results"]:
            if record["method"] == "pretrained" and record["session_id"] == "s156":
                for row in record["rows"]:
                    row["values"] = [2 * x for x in row["values"]]
            if record["method"] == "from_scratch":
                target = next(x for x in t["cases"] if x["session_id"] == record["session_id"] and x["budget_id"] == record["budget_id"])
                record["rows"] = copy.deepcopy(target["rows"])
        out = self.run_case(d, p, t)
        overall = next(x for x in out["summaries"] if x["group"] == "all" and x["budget_id"] == "b1" and x["method"] == "pretrained")
        self.assertEqual(overall["session_macro_r2"], 0.5)
        contrast = next(x for x in out["contrasts"] if x["budget_id"] == "b1" and x["comparator"] == "from_scratch")
        self.assertEqual(contrast["mean_difference"], -0.5)

    def test_near_zero_policy_all_branches_and_boundary(self):
        zero = [(Fraction(0), Fraction(0))] * 2
        small = [(Fraction(1, 1000), Fraction(1, 1000))] * 2
        big = [(Fraction(1), Fraction(1))] * 2
        self.assertEqual(ev.r2(small, zero)[1:], ([Fraction(1), Fraction(1)], ["near_zero_residual"] * 2))
        self.assertEqual(ev.r2(big, zero)[1:], ([Fraction(0), Fraction(0)], ["near_constant_target"] * 2))
        varying = [(Fraction(-1), Fraction(-10)), (Fraction(1), Fraction(10))]
        self.assertEqual(ev.r2(zero, varying)[1:], ([Fraction(0), Fraction(0)], ["ordinary_r2"] * 2))
        # Values on both sides of epsilon exercise the two declared branches.
        self.assertEqual(ev.EPSILON, Fraction.from_float(1e-4))
        below = Fraction.from_float(0.007)
        above = Fraction.from_float(0.008)
        self.assertEqual(ev.r2([(below, below)] * 2, zero)[2], ["near_zero_residual"] * 2)
        self.assertEqual(ev.r2([(above, above)] * 2, zero)[2], ["near_constant_target"] * 2)

    def test_complete_prediction_admission_precedes_private_callback(self):
        d, p, _ = fixture()
        for mutation in (lambda x: x["results"].pop(),
                         lambda x: x["results"][-1]["rows"].pop(),
                         lambda x: x["results"][-1]["rows"][-1].update(values=[True, 0]),
                         lambda x: x["results"][-1]["rows"][-1].update(row_id="wrong"),
                         lambda x: x["results"].append(x["results"][0])):
            altered = copy.deepcopy(p); mutation(altered)
            self.refused_before_targets(d, altered)

    def test_design_support_identity_and_split_refusals(self):
        d, p, _ = fixture()
        for mutation in (lambda x: x["corpus"].pop(),
                         lambda x: x["cases"].pop(),
                         lambda x: x["pretraining_sessions"].append("s156"),
                         lambda x: x["cases"][-1]["adaptation_trials"].append("test"),
                         lambda x: x["corpus"][-1]["normalization"].update(std=[0, 1]),
                         lambda x: x.update(authority=None),
                         lambda x: x.update(policy="historical-equivalence-unproven")):
            altered = copy.deepcopy(d); mutation(altered)
            self.refused_before_targets(altered, p)
        body = encode(d)
        with self.assertRaisesRegex(ValueError, "content identity"):
            ev.evaluate(body, pin(body + b" "), encode(p), lambda: self.fail("target read"))

    def test_private_support_refusal_and_exact_large_timestamp(self):
        d, p, t = fixture()
        for case in d["cases"]:
            for row in case["rows"]:
                row["timestamp"] += 2**60
        self.assertEqual(self.run_case(d, p, t)["results"][0]["stitched_samples"], 3)
        t["cases"][-1]["rows"][-1]["row_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "target order"):
            self.run_case(d, p, t)
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            ev.load_json(b'{"a": 1, "a": 2}')

    def test_actual_cli_identity_and_no_clobber(self):
        d, p, t = fixture()
        with tempfile.TemporaryDirectory(prefix="poyo-invented-") as tmp:
            root = Path(tmp)
            for name, obj in (("design", d), ("predictions", p), ("targets", t)):
                (root / (name + ".json")).write_bytes(encode(obj))
            args = [sys.executable, "-I", "-S", "-B", str(HERE / "evaluator.py")]
            for name in ("design", "predictions", "targets"):
                args += ["--" + name, str(root / (name + ".json"))]
            for name, obj in (("design", d), ("targets", t)):
                actual = pin(encode(obj))
                args += ["--" + name + "-bytes", str(actual["bytes"]), "--" + name + "-sha256", actual["sha256"]]
            args += ["--output", str(root / "scores.json")]
            run = subprocess.run(args, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            original = (root / "scores.json").read_bytes()
            refused = subprocess.run(args, capture_output=True, timeout=15)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual((root / "scores.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
