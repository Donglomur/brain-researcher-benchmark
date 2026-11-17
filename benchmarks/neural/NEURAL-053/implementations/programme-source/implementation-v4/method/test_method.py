"""Invented engineering arrays only; no authentic data or runtime qualification."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from .plan import PlanError, canonical_bytes, digest, evaluate, load_plan
from .admission import (AdmissionError, ARTIFACTS, QUALIFICATIONS, TrustedRegistry,
                        byte_identity, current_engine_identities, execute_admitted,
                        run_training_challenges, validate_admission)


def constant(shape, values):
    return {"dtype": "float64", "shape": shape, "values": values}


def example_plan():
    return {"schema": "neural053_row_plan_v1", "input_dim": 2, "class_count": 3,
            "constants": {"weights": constant([2, 3], [1, -1, 0.5, 0.1, 1, -0.3]),
                          "bias": constant([3], [0.2, 0, -0.1])},
            "nodes": [{"id": "scores", "op": "affine", "input": "input", "weight": "weights", "bias": "bias"},
                      {"id": "prob", "op": "softmax", "input": "scores", "axis": "classes"}], "output": "prob"}


class MethodControls(unittest.TestCase):
    def setUp(self):
        self.doc = example_plan()
        self.plan = load_plan(self.doc)
        self.x = np.array([[1, 2], [-2, 0], [0.25, -0.5], [0, 0], [4, -1]], dtype=np.float64)

    def test_scalar_vectorized_truth_and_immutability(self):
        weights = np.array(self.doc["constants"]["weights"]["values"]).reshape(2, 3)
        raw = self.x @ weights + np.array([0.2, 0, -0.1])
        expected = np.exp(raw - raw.max(axis=1, keepdims=True))
        expected /= expected.sum(axis=1, keepdims=True)
        np.testing.assert_allclose(evaluate(self.plan, self.x), expected, atol=1e-14)
        np.testing.assert_allclose(evaluate(self.plan, self.x, backend="scalar"), expected, atol=1e-14)
        before = self.plan.digest
        self.doc["constants"]["weights"]["values"][0] = 999
        self.assertEqual(self.plan.digest, before)
        np.testing.assert_allclose(evaluate(self.plan, self.x), expected, atol=1e-14)

    def test_unsupported_batch_axis_hidden_state_forward_and_dtype_refused(self):
        mutations = []
        d = copy.deepcopy(self.doc); d["nodes"][0]["op"] = "query_cluster"; mutations.append(d)
        d = copy.deepcopy(self.doc); d["nodes"][-1]["axis"] = "batch"; mutations.append(d)
        d = copy.deepcopy(self.doc); d["constants"]["hidden"] = constant([], [3]); mutations.append(d)
        d = copy.deepcopy(self.doc); d["nodes"][0]["input"] = "prob"; mutations.append(d)
        d = copy.deepcopy(self.doc); d["constants"]["bias"]["dtype"] = "object"; mutations.append(d)
        d = copy.deepcopy(self.doc); d["nodes"][0]["callback"] = "opaque"; mutations.append(d)
        d = copy.deepcopy(self.doc); d["constants"]["bias"]["values"][0] = float("nan"); mutations.append(d)
        for bad in mutations:
            with self.subTest(bad=bad), self.assertRaises(PlanError): load_plan(bad)

    def test_domain_nonfinite_and_no_backend_fallback(self):
        d = copy.deepcopy(self.doc)
        d["nodes"].insert(0, {"id": "logged", "op": "log", "input": "input"})
        d["nodes"][1]["input"] = "logged"
        p = load_plan(d)
        with self.assertRaises(PlanError): evaluate(p, self.x)
        with self.assertRaises(PlanError): evaluate(self.plan, self.x, backend="automatic")
        with self.assertRaises(PlanError): evaluate(self.plan, np.array([[float("inf"), 0]]))

    def test_tree_and_cycle_refusal(self):
        d = {"schema": "neural053_row_plan_v1", "input_dim": 2, "class_count": 3,
             "constants": {"left": constant([3], [2, 0, -1]), "right": constant([3], [-1, 0, 2])},
             "nodes": [{"id": "tree_scores", "op": "tree", "input": "input", "tree": [
                 {"feature": 0, "threshold": 0, "left": 1, "right": 2}, {"scores": "left"}, {"scores": "right"}]},
                 {"id": "prob", "op": "softmax", "input": "tree_scores", "axis": "classes"}], "output": "prob"}
        p = load_plan(d)
        self.assertEqual(evaluate(p, self.x).argmax(axis=1).tolist(), [2, 0, 2, 0, 2])
        np.testing.assert_allclose(evaluate(p, self.x), evaluate(p, self.x, backend="scalar"))
        d["nodes"][0]["tree"][0]["left"] = 0
        with self.assertRaises(PlanError): load_plan(d)

    def test_feature_arithmetic_is_row_local_and_all_unaries_have_domains(self):
        # Each score row is [x0+x1, x0-x1, x0*x1]. This independent closed form
        # detects accidental feature/batch axis confusion in several operations.
        d = {"schema": "neural053_row_plan_v1", "input_dim": 2, "class_count": 3, "constants": {},
             "nodes": [{"id": "a", "op": "gather", "input": "input", "indices": [0]},
                       {"id": "b", "op": "gather", "input": "input", "indices": [1]},
                       {"id": "plus", "op": "add", "inputs": ["a", "b"]},
                       {"id": "minus", "op": "sub", "inputs": ["a", "b"]},
                       {"id": "times", "op": "mul", "inputs": ["a", "b"]},
                       {"id": "scores", "op": "concat", "inputs": ["plus", "minus", "times"]},
                       {"id": "prob", "op": "softmax", "input": "scores", "axis": "classes"}], "output": "prob"}
        p = load_plan(d)
        scores = np.column_stack((self.x[:, 0] + self.x[:, 1], self.x[:, 0] - self.x[:, 1], self.x[:, 0] * self.x[:, 1]))
        expected = np.exp(scores - scores.max(axis=1, keepdims=True)); expected /= expected.sum(axis=1, keepdims=True)
        np.testing.assert_allclose(evaluate(p, self.x), expected)
        np.testing.assert_allclose(evaluate(p, self.x[::-1])[::-1], expected)
        for op in ("abs", "exp", "log", "log1p", "sqrt", "cos", "tanh", "sigmoid", "relu"):
            u = copy.deepcopy(self.doc)
            u["nodes"].insert(0, {"id": "unary", "op": op, "input": "input"})
            u["nodes"][1]["input"] = "unary"
            up = load_plan(u)
            positive = np.abs(self.x) + 0.5
            np.testing.assert_allclose(evaluate(up, positive), evaluate(up, positive, backend="scalar"), atol=1e-13)
        for op in ("log", "log1p", "sqrt"):
            u = copy.deepcopy(self.doc); u["nodes"].insert(0, {"id": "unary", "op": op, "input": "input"}); u["nodes"][1]["input"] = "unary"
            with self.assertRaises(PlanError): evaluate(load_plan(u), np.array([[-2., -3.]]))
        huge = copy.deepcopy(self.doc); huge["constants"]["bias"]["values"][0] = 10**400
        with self.assertRaises(PlanError): load_plan(huge)

    def test_constant_operations_and_feature_sum(self):
        d = {"schema": "neural053_row_plan_v1", "input_dim": 2, "class_count": 3,
             "constants": {"one": constant([], [1]), "two": constant([], [2]), "zero": constant([], [0])},
             "nodes": [{"id": "added", "op": "add_const", "input": "input", "constant": "one"},
                       {"id": "subtracted", "op": "sub_const", "input": "added", "constant": "one"},
                       {"id": "multiplied", "op": "mul_const", "input": "subtracted", "constant": "two"},
                       {"id": "divided", "op": "div_const", "input": "multiplied", "constant": "two"},
                       {"id": "summed", "op": "sum", "input": "divided", "axis": "features"},
                       {"id": "zerod", "op": "mul_const", "input": "summed", "constant": "zero"},
                       {"id": "scores", "op": "concat", "inputs": ["zerod", "zerod", "zerod"]},
                       {"id": "prob", "op": "softmax", "input": "scores", "axis": "classes"}], "output": "prob"}
        np.testing.assert_allclose(evaluate(load_plan(d), self.x), np.full((5, 3), 1/3))
        d["nodes"][3]["constant"] = "zero"
        with self.assertRaises(PlanError): load_plan(d)

    def _fixture_receipt(self):
        fake = byte_identity(b"invented-engineering-evidence-not-scientific-qualification")
        artifacts = {name: dict(fake) for name in ARTIFACTS}
        artifacts["plan"] = byte_identity(self.plan.encoded)
        artifacts["state"] = byte_identity(canonical_bytes(json.loads(self.plan.encoded)["constants"]))
        artifacts.update(current_engine_identities())
        bindings = {"schema": "neural053_method_bindings_v2", "task_id": "NEURAL-053",
                    "profile": "invented_engineering", "input_dim": 2, "class_count": 3,
                    "query_rows": 5, "backend": "vectorized", "entrypoint": "method.plan:evaluate",
                    "context": {"fold_token": "invented-fold", "arm": "neural", "mode": "fixed_program",
                                "replication": 0, "attempt_id": "invented-attempt", "reference_family": None,
                                "comparison_scope": "invented-paired-context"}, "artifacts": artifacts}
        challenge = run_training_challenges(self.plan, self.x, ["a", "b", "c", "d", "e"],
                                            training_support_sha256=artifacts["fit_support"]["sha256"],
                                            profile="invented_engineering")
        review = {"author_id": "invented-author", "reviewer_id": "invented-independent-reviewer",
                  "decision": "accepted", "reviewed_bindings_sha256": digest(bindings),
                  "row_local_reasoning": "Invented control exercises affine and per-row softmax only.",
                  "source_closure_complete": True, "no_query_values": True,
                  "supported_operations": list(self.plan.operations)}
        receipt = {"schema": "neural053_method_admission_v2", "bindings": copy.deepcopy(bindings),
                   "review": review, "challenges": challenge}
        return receipt, bindings

    def _registry(self, receipt, bindings, directory):
        raw = canonical_bytes({"schema": "neural053_trusted_admission_registry_v1", "task_id": "NEURAL-053",
                               "profile": "invented_engineering", "approved_receipts": [digest(receipt)],
                               "approved_qualifications": sorted({bindings["artifacts"][name]["sha256"] for name in QUALIFICATIONS})})
        path = Path(directory) / "invented_registry.json"
        path.write_bytes(raw)
        return TrustedRegistry.from_file(path, expected_bytes=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_complete_invented_path_and_canonical_refusal(self):
        receipt, bindings = self._fixture_receipt()
        with tempfile.TemporaryDirectory(prefix="neural053-method-engineering-") as tmp:
            registry = self._registry(receipt, bindings, tmp)
            called = []
            def loader(): called.append(True); return self.x
            result, admission = execute_admitted(receipt, bindings, registry, self.plan, loader,
                                                 required_profile="invented_engineering")
            self.assertEqual(called, [True]); self.assertEqual(admission["profile"], "invented_engineering")
            np.testing.assert_allclose(result, evaluate(self.plan, self.x))
            called.clear()
            with self.assertRaises(AdmissionError): execute_admitted(receipt, bindings, registry, self.plan, loader)
            self.assertEqual(called, [])

    def test_unapproved_stale_and_missing_qualification_refuse_before_loader(self):
        receipt, bindings = self._fixture_receipt()
        with tempfile.TemporaryDirectory(prefix="neural053-method-engineering-") as tmp:
            registry = self._registry(receipt, bindings, tmp)
            called = []
            def loader(): called.append(True); return self.x
            changed = copy.deepcopy(bindings); changed["context"]["attempt_id"] = "stale"
            with self.assertRaises(AdmissionError):
                execute_admitted(receipt, changed, registry, self.plan, loader, required_profile="invented_engineering")
            bad = copy.deepcopy(receipt); bad["review"]["reviewer_id"] = "invented-author"
            with self.assertRaises(AdmissionError):
                execute_admitted(bad, bindings, registry, self.plan, loader, required_profile="invented_engineering")
            bad = copy.deepcopy(receipt); bad["bindings"]["artifacts"]["runtime_qualification"]["sha256"] = "b" * 64
            changed = copy.deepcopy(bad["bindings"]); bad["review"]["reviewed_bindings_sha256"] = digest(changed)
            # Even an approved receipt does not replace separately approved qualifications.
            regdoc = registry.document(); regdoc["approved_receipts"] = [digest(bad)]
            raw = canonical_bytes(regdoc)
            reg2 = TrustedRegistry(raw, hashlib.sha256(raw).hexdigest())
            with self.assertRaises(AdmissionError):
                execute_admitted(bad, changed, reg2, self.plan, loader, required_profile="invented_engineering")
            self.assertEqual(called, [])

    def test_approved_but_incomplete_challenge_or_self_review_refused(self):
        receipt, bindings = self._fixture_receipt()
        with tempfile.TemporaryDirectory(prefix="neural053-method-engineering-") as tmp:
            for field in ("challenges", "review"):
                bad = copy.deepcopy(receipt)
                if field == "challenges": bad["challenges"]["results"].pop()
                else: bad["review"]["reviewer_id"] = bad["review"]["author_id"]
                registry = self._registry(bad, bindings, tmp)
                with self.assertRaises(AdmissionError):
                    validate_admission(bad, bindings, registry, self.plan, required_profile="invented_engineering")

    def test_training_only_challenges_require_complete_support(self):
        with self.assertRaises(AdmissionError):
            run_training_challenges(self.plan, self.x, ["a", "b", "c", "d", "e"],
                                    training_support_sha256="a" * 64)  # default authentic64 refuses invented5
        with self.assertRaises(AdmissionError):
            run_training_challenges(self.plan, self.x, ["a", "a", "c", "d", "e"],
                                    training_support_sha256="a" * 64, profile="invented_engineering")


if __name__ == "__main__":
    unittest.main()
