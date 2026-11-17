"""Invented complete-wire regressions; no authentic morphology or reference."""
import copy
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
PROFILE_ROOT = ROOT.parents[1] / "benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADAPTER = load("public_purkinje_adapter", "artifact.py")
SCHEMA, NEW, _, _ = ADAPTER.contracts(PROFILE_ROOT)
# Explicitly bind both generated fixtures and historical scorer to the real schema.
previous_schema = sys.modules.get("schema")
sys.modules["schema"] = SCHEMA
try:
    F = load("numeric_generated_fixture", "numeric_fixtures.py")
    OLD = load("old_numeric_fixture", "regression_fixtures/old_numeric_score.py")
finally:
    if previous_schema is None:
        sys.modules.pop("schema", None)
    else:
        sys.modules["schema"] = previous_schema

def grade(rows, reference=None, scorer=NEW):
    reference = F.rows if reference is None else reference
    calls = []
    def release():
        calls.append(True)
        return F.files(reference)
    result = scorer.grade(F.files(rows), release)
    return result, calls


def omit_bias(value):
    if isinstance(value, dict):
        return {k: omit_bias(v) for k, v in value.items() if k != "bias"}
    if isinstance(value, list):
        return [omit_bias(v) for v in value]
    return value


class NumericScoreRegression(unittest.TestCase):
    def test_exact_baseline_and_complete_denominators_unchanged(self):
        new, calls = grade(F.rows)
        self.assertEqual(new, grade(F.rows, scorer=OLD)[0])
        self.assertEqual(calls, [True])
        self.assertEqual(new["status"], "scored")
        field = new["comparison"]["metrics"]["tables"]["branches.csv"]["fields"]["length_um"]
        self.assertEqual(field["defined_cells"], 10)
        self.assertEqual(field["defined_rows"], 15)
        self.assertIsNone(new["scientific_success"])
        self.assertFalse(new["full_paper_reproduction"])

    def test_nonintegral_and_out_of_range_tokens_reject_before_reference(self):
        for column in ("start_id", "n_edges"):
            for token in ("1.0000000000000001", "1.5", "1000000000.00000001", "-0.1", "1000000001"):
                with self.subTest(column=column, token=token):
                    rows = copy.deepcopy(F.rows)
                    rows["branches.csv"][0][column] = token
                    result, calls = grade(rows)
                    self.assertEqual(result["status"], "invalid_submission")
                    self.assertEqual(calls, [])
                    self.assertEqual(result["private_numeric_reference_loads"], 0)
        rows = copy.deepcopy(F.rows)
        rows["branches.csv"][0]["start_id"] = "1.0000000000000001"
        self.assertEqual(grade(rows, scorer=OLD)[0]["status"], "scored")

    def test_integral_decimal_scientific_and_unicode_spellings(self):
        for token in ("1", "1.0", "+001.000", "1e0", ".1e1", "١.٠", "1.00000000e0"):
            with self.subTest(token=token):
                rows = copy.deepcopy(F.rows)
                rows["branches.csv"][0]["start_id"] = token
                self.assertEqual(grade(rows)[0], grade(F.rows)[0])
        for token in ("1000000000", "1.000e9", "١e٩"):
            rows = copy.deepcopy(F.rows)
            rows["branches.csv"][0]["n_edges"] = token
            result, calls = grade(rows, rows)
            self.assertEqual(result["status"], "scored")
            self.assertEqual(calls, [True])
            self.assertEqual(result, grade(rows, rows, OLD)[0])

    def test_long_exponent_zero_is_bounded_and_preserved(self):
        for token in ("0e" + "9" * 125, "-0.00e-" + "9" * 100,
                      "٠e" + "٩" * 100, "-0"):
            with self.subTest(token=token):
                rows = copy.deepcopy(F.rows)
                rows["branches.csv"][0]["n_edges"] = token
                result, calls = grade(rows, rows)
                self.assertEqual(result["status"], "scored")
                self.assertEqual(calls, [True])
                self.assertEqual(result, grade(rows, rows, OLD)[0])

    def test_nonzero_underflow_rejected_for_ascii_and_unicode(self):
        for token in ("1e-999", "١e-999"):
            rows = copy.deepcopy(F.rows)
            rows["branches.csv"][0]["length_um"] = token
            result, calls = grade(rows)
            self.assertEqual(result["status"], "invalid_submission")
            self.assertEqual(calls, [])
        rows = copy.deepcopy(F.rows)
        rows["branches.csv"][0]["length_um"] = "١e-999"
        self.assertEqual(grade(rows, scorer=OLD)[0]["status"], "scored")
        rows["branches.csv"][0]["length_um"] = "١.٢٥"
        ref = copy.deepcopy(F.rows)
        ref["branches.csv"][0]["length_um"] = "1.25"
        result, _ = grade(rows, ref)
        self.assertEqual(result["comparison"]["metrics"]["primary_equal_cell_branch_length_rmse_um"], 0.0)

    def test_signed_cancellation_residual_and_other_metrics(self):
        for third in (math.nextafter(1.0, math.inf), math.nextafter(1.0, 0.0)):
            rows = copy.deepcopy(F.rows)
            for i, token in enumerate(("1e308", "0", repr(third))):
                rows["branches.csv"][i]["length_um"] = token
            new, calls = grade(rows)
            old, _ = grade(rows, scorer=OLD)
            error = third - 1.0
            expected = float(Fraction.from_float(error) / 3)
            field = new["comparison"]["metrics"]["tables"]["branches.csv"]["fields"]["length_um"]
            self.assertEqual(field["per_cell"][F.S.CELLS[0]]["bias"], expected)
            self.assertNotEqual(expected, 0.0)
            self.assertEqual(omit_bias(new), omit_bias(old))
            self.assertEqual(calls, [True])

    def test_signed_sum_overflow_uses_finite_mean(self):
        maximum = sys.float_info.max
        rows, ref = copy.deepcopy(F.rows), copy.deepcopy(F.rows)
        for i, (candidate, target) in enumerate(((maximum, 0.0), (maximum, 0.0), (0.0, maximum))):
            rows["branches.csv"][i]["length_um"] = repr(candidate)
            ref["branches.csv"][i]["length_um"] = repr(target)
        result, calls = grade(rows, ref)
        self.assertEqual(result["status"], "scored")
        field = result["comparison"]["metrics"]["tables"]["branches.csv"]["fields"]["length_um"]
        self.assertEqual(field["per_cell"][F.S.CELLS[0]]["bias"], float(Fraction.from_float(maximum) / 3))
        self.assertEqual(omit_bias(result), omit_bias(grade(rows, ref, OLD)[0]))
        self.assertEqual(calls, [True])

    def test_missing_identity_and_derived_overflow_policies_unchanged(self):
        rows = copy.deepcopy(F.rows)
        rows["branches.csv"].pop()
        result, calls = grade(rows)
        self.assertEqual(result, grade(rows, scorer=OLD)[0])
        self.assertEqual(result["status"], "incomplete_numerical_coverage")
        self.assertIsNone(result["comparison"]["metrics"])
        self.assertEqual(calls, [True])
        rows, ref = copy.deepcopy(F.rows), copy.deepcopy(F.rows)
        rows["branches.csv"][0]["length_um"] = "1e308"
        ref["branches.csv"][0]["length_um"] = "-1e308"
        result, calls = grade(rows, ref)
        self.assertEqual(result, grade(rows, ref, OLD)[0])
        self.assertEqual(result["status"], "unsupported_derived_numerics")
        self.assertEqual(calls, [True])
        files = F.files(F.rows)
        del files["components.csv"]
        calls = []
        result = NEW.grade(files, lambda: calls.append(True) or F.reference)
        self.assertEqual(result["status"], "invalid_submission")
        self.assertEqual(calls, [])


class SourceReceiptBoundary(unittest.TestCase):
    def test_historical_scorer_receipt_refused_before_candidate_or_reference(self):
        from unittest import mock
        receipt = {"profile": ADAPTER.PROFILE, "schema": 1,
                   "scorer": [8644, "d04eca18294d3cf328c52e3dea8cff63dd59dd639b366f3fe0a6435fea4a5973"],
                   "wire_schema": list(ADAPTER.PINS["schema.py"]),
                   "producer_stopped_attested": True, "files": {}, "total_bytes": 0}
        body = ADAPTER.encoded(receipt, ADAPTER.RECEIPT_CAP)
        with mock.patch.object(ADAPTER, "read", return_value=body) as read:
            with mock.patch.object(ADAPTER, "candidate") as candidate:
                with self.assertRaisesRegex(ADAPTER.Refusal, "Receipt contract"):
                    ADAPTER.load_attempt(ROOT / "invented-unused-attempt", ADAPTER.pin(body), SCHEMA, NEW)
                self.assertEqual(read.call_count, 1)
                candidate.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
