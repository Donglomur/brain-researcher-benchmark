"""Generated matrix controls only: no original observations or source execution."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("find025_variance_panel", HERE / "variance_panel.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def operands():
    operator = {"schema": "find025_covariance_operands_v1", "source_commit": v.SOURCE_COMMIT,
                "unit_ids": ["generated:a", "generated:b", "generated:c"],
                "d_prep": 2, "d_move": 1, "preparation_id": "generated:preparation",
                "support_ids": {x: "generated:" + x for x in v.EPOCHS},
                "covariances": {x: np.diag([9., 4., 1.]).tolist() for x in v.EPOCHS}}
    operator["covariances"]["moving"] = np.diag([1., 4., 16.]).tolist()
    candidate = {"schema": "find025_subspace_bases_v1", "unit_ids": list(operator["unit_ids"]),
                 "null_basis": [[1., 0.], [0., 1.], [0., 0.]],
                 "potent_basis": [[0.], [0.], [1.]]}
    return operator, candidate


def encode(candidate):
    return json.dumps(candidate, allow_nan=False, separators=(",", ":")).encode()


def run(operator, candidate):
    body = encode(candidate)
    return v.evaluate_panel(operator, body, sha256(body).hexdigest())


class VariancePanelControls(unittest.TestCase):
    def test_all_eight_source_routes_and_crossed_ranks(self):
        result = run(*operands())
        expected = [1., .25, 1., 1/9, 1., 13/9, 1/13, 1/9]
        self.assertEqual(len(result["results"]), 8)
        for row, value in zip(result["results"], expected):
            self.assertEqual(row["status"], "computed")
            self.assertAlmostEqual(row["value"], value, places=14)
        self.assertGreater(result["results"][5]["value"], 1)
        self.assertEqual(result["results"][5]["denominator_rank"], 1)
        self.assertEqual(result["results"][6]["denominator_rank"], 2)
        self.assertIsNone(result["paper_pass"])
        self.assertFalse(result["scientifically_qualified"])
        self.assertFalse(result["readiness_promoted"])

    def test_basis_rotation_and_sign_changes_preserve_the_subspaces(self):
        operator, candidate = operands()
        before = run(operator, candidate)
        candidate["null_basis"] = [[.6, -.8], [.8, .6], [0., 0.]]
        candidate["potent_basis"] = [[0.], [0.], [-1.]]
        after = run(operator, candidate)
        for a, b in zip(before["results"], after["results"]):
            self.assertAlmostEqual(a["value"], b["value"], places=14)

    def test_covariance_rotation_cannot_be_replaced_by_diagonal_only(self):
        operator, candidate = operands()
        operator["covariances"]["stationary"] = [[5., 0., 4.], [0., 4., 0.], [4., 0., 5.]]
        result = run(operator, candidate)
        self.assertAlmostEqual(result["results"][0]["value"], 9/13, places=14)
        self.assertAlmostEqual(result["results"][3]["value"], 5/9, places=14)

    def test_common_covariance_scale_preserves_all_ratios(self):
        operator, candidate = operands()
        baseline = run(operator, candidate)
        for scale in (1e-90, 1e90):
            changed = deepcopy(operator)
            changed["covariances"] = {k: (np.asarray(c)*scale).tolist()
                                      for k, c in operator["covariances"].items()}
            for a, b in zip(baseline["results"], run(changed, candidate)["results"]):
                self.assertAlmostEqual(a["value"], b["value"], places=13)

    def test_zero_epoch_remains_two_undefined_assigned_outputs(self):
        operator, candidate = operands()
        operator["covariances"]["delay"] = np.zeros((3, 3)).tolist()
        result = run(operator, candidate)
        self.assertEqual(len(result["results"]), 8)
        undefined = [r for r in result["results"] if r["status"] == "undefined"]
        self.assertEqual({r["output"] for r in undefined}, {"null_delay", "potent_delay"})
        self.assertTrue(all(r["value"] is None for r in undefined))

    def test_wrong_unit_order_is_rejected_not_realigned(self):
        operator, candidate = operands()
        candidate["unit_ids"].reverse()
        with self.assertRaisesRegex(v.CandidateError, "order"):
            run(operator, candidate)

    def test_candidate_covariance_or_scalar_injection_is_rejected(self):
        for key in ("covariances", "score", "denominator", "d_prep"):
            operator, candidate = operands()
            candidate[key] = 1
            with self.assertRaisesRegex(v.CandidateError, "exact fields"):
                run(operator, candidate)

    def test_basis_scaling_and_cross_space_overlap_are_rejected(self):
        for mutation in ("scale", "overlap"):
            operator, candidate = operands()
            if mutation == "scale":
                candidate["null_basis"][0][0] = 2.
            else:
                candidate["potent_basis"] = [[1.], [0.], [0.]]
            with self.assertRaisesRegex(v.CandidateError, "orthonormal"):
                run(operator, candidate)

    def test_bad_matrix_shapes_and_boolean_numbers_are_rejected(self):
        for mutation in ("rows", "columns", "boolean", "complex", "huge_int"):
            operator, candidate = operands()
            if mutation == "rows": candidate["null_basis"].pop()
            elif mutation == "columns": candidate["null_basis"][0].append(0.)
            elif mutation == "boolean": candidate["null_basis"][0][0] = True
            elif mutation == "complex": candidate["null_basis"][0][0] = "1+0j"
            else: candidate["null_basis"][0][0] = 10**200
            with self.assertRaises(v.CandidateError): run(operator, candidate)

    def test_operator_indefinite_or_asymmetric_covariance_aborts_panel(self):
        for mutation in ("indefinite", "asymmetric"):
            operator, candidate = operands()
            if mutation == "indefinite": operator["covariances"]["response"][2][2] = -1.
            else: operator["covariances"]["response"][0][1] = 1e-14
            with self.assertRaises(v.OperatorError): run(operator, candidate)

    def test_missing_epoch_or_rank_mismatch_does_not_shorten_panel(self):
        for mutation in ("epoch", "boolean_rank", "too_many", "zero_rank", "unit_count"):
            operator, candidate = operands()
            if mutation == "epoch": del operator["covariances"]["delay"]
            elif mutation == "boolean_rank": operator["d_prep"] = True
            elif mutation == "too_many": operator["d_move"] = 2
            elif mutation == "zero_rank": operator["d_move"] = 0
            else: operator["unit_ids"] = ["x"] * (v.MAX_UNITS + 1)
            with self.assertRaises(v.OperatorError): run(operator, candidate)

    def test_changed_source_or_empty_support_rejected(self):
        for mutation in ("source", "support"):
            operator, candidate = operands()
            if mutation == "source": operator["source_commit"] = "0" * 40
            else: operator["support_ids"]["delay"] = ""
            with self.assertRaises(v.OperatorError): run(operator, candidate)

    def test_tampered_or_overlarge_bytes_rejected(self):
        operator, candidate = operands()
        body = encode(candidate)
        with self.assertRaisesRegex(v.CandidateError, "SHA256"):
            v.evaluate_panel(operator, body+b" ", sha256(body).hexdigest())
        too_large = b" " * (v.MAX_PAYLOAD_BYTES + 1)
        with self.assertRaisesRegex(v.CandidateError, "bounded"):
            v.evaluate_panel(operator, too_large, sha256(too_large).hexdigest())

    def test_duplicate_json_and_nonfinite_values_rejected(self):
        operator, candidate = operands()
        bodies = [b'{"schema":"x","schema":"y"}',
                  encode(candidate).replace(b'[[1.0,0.0]', b'[[NaN,0.0]'),
                  encode(candidate).replace(b'[[1.0,0.0]', b'[[1e400,0.0]')]
        for body in bodies:
            with self.assertRaises(v.CandidateError):
                v.evaluate_panel(operator, body, sha256(body).hexdigest())

    def test_inputs_are_not_mutated_or_returned(self):
        operator, candidate = operands()
        original_operator, original_candidate = deepcopy(operator), deepcopy(candidate)
        result = run(operator, candidate)
        self.assertEqual(operator, original_operator)
        self.assertEqual(candidate, original_candidate)
        serialized = json.dumps(result)
        self.assertNotIn("generated:a", serialized)
        self.assertNotIn("covariances", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
