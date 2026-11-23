"""Tiny invented source-profile controls; no recording, sorter or truth assets."""
from fractions import Fraction
import importlib.util
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load_bank(name):
    spec = importlib.util.spec_from_file_location(
        "k4_admission_" + name, ROOT / "payload/legacy/banks" / name / "bank.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R1, R2 = load_bank("r1"), load_bank("r2")


def pair(value):
    value = Fraction(value)
    return [value.numerator, value.denominator]


def request(*, truth=(100,), detected=(100,), origin=0, frequency=30000,
            dtype="float64", truth_depth=Fraction(1, 2), detected_depth=Fraction(1, 2)):
    def unit(name, samples, depth):
        return {"unit_id": name, "source_samples": list(samples), "depth": pair(depth),
                "events": [pair(Fraction(s - origin, frequency)) for s in samples]}
    return {
        "operation": "source20",
        "case": {"id": "generated-software-control", "kind": "synthetic",
                 "duration": [1, 1], "quality_bin_seconds": [1, 1000],
                 "truth": [unit("truth", truth, truth_depth)],
                 "detected": [unit("detected", detected, detected_depth)]},
        "source_profile": {"numpy_version": np.__version__, "argsort_kind": "quicksort",
                           "depth_dtype": dtype, "sample_frequency": pair(frequency),
                           "sample_origin": pair(origin), "source_clock_admitted": True,
                           "dt_samples": 6},
        "limits": {"max_truth_units": 2, "max_detected_units": 2,
                   "max_total_events": 8, "max_pair_edges": 4,
                   "max_work": 100000, "max_precision_digits": 8},
    }


class Source20AdmissionTests(unittest.TestCase):
    def gate(self, value, reason):
        response = R2.dispatch(value)
        self.assertEqual(response["status"], "required-unscorable", response)
        self.assertIsNone(response["result"])
        self.assertEqual(response["gaps"][0]["id"], reason)

    def agrees_with_r1(self, value):
        response = R2.dispatch(value)
        self.assertEqual(response["status"], "ok", response)
        expected = R1.source20(value, R1.Meter(value["limits"]))
        actual = response["result"]
        for left, right in zip(expected["rows"], actual["rows"]):
            for key in ("fmax", "fmiss", "fpos", "best_ind", "top_inds", "matched_all"):
                self.assertEqual(left[key], right[key], key)
        return actual["rows"][0]

    def test_exact_native_depth_and_sample_profile_preserve_score(self):
        for dtype in ("float32", "float64"):
            with self.subTest(dtype=dtype):
                row = self.agrees_with_r1(request(dtype=dtype))
                self.assertEqual(row["fmax"], 1.0)

    def test_negative_safe_sample_coordinates_keep_explicit_origin(self):
        row = self.agrees_with_r1(request(truth=(-100,), detected=(-100,), origin=-200))
        self.assertEqual(row["fmax"], 1.0)

    def test_largest_safe_six_sample_addition_is_allowed(self):
        sample = 2**63 - 7
        row = self.agrees_with_r1(request(truth=(sample,), detected=(sample,), origin=sample-100))
        self.assertEqual(row["fmax"], 1.0)

    def test_upper_native_integer_overflow_is_unscorable(self):
        for sample in (2**63 - 6, 2**63, 2**80):
            with self.subTest(sample=sample):
                self.gate(request(truth=(sample,), detected=(sample,), origin=sample-100),
                          "R-source-int64-domain")

    def test_lower_native_integer_overflow_is_unscorable(self):
        sample = -(2**63) - 1
        self.gate(request(truth=(sample,), detected=(sample,), origin=sample-100),
                  "R-source-int64-domain")

    def test_cross_unit_difference_overflow_is_unscorable(self):
        self.gate(request(truth=(-(2**63),), detected=(0,), origin=-(2**63), frequency=2**64),
                  "R-source-int64-difference")

    def test_float_tolerance_cannot_claim_integer_source_profile(self):
        value = request()
        value["source_profile"]["dt_samples"] = 6.0
        self.gate(value, "R-source-runtime")

    def test_float32_detected_depth_rounding_is_unscorable(self):
        self.gate(request(dtype="float32", detected_depth=Fraction(1, 10)),
                  "R-source-depth-representation")

    def test_float32_truth_depth_rounding_is_unscorable(self):
        self.gate(request(dtype="float32", truth_depth=Fraction(1, 10)),
                  "R-source-depth-representation")

    def test_float64_detected_depth_rounding_is_unscorable(self):
        self.gate(request(detected_depth=Fraction(1, 10)), "R-source-depth-representation")

    def test_float64_truth_depth_rounding_is_unscorable(self):
        self.gate(request(truth_depth=Fraction(1, 10)), "R-source-depth-representation")

    def test_exact_binary_fraction_of_decimal_float_is_allowed(self):
        for dtype in ("float32", "float64"):
            depth = Fraction(float(np.asarray(0.1, dtype=dtype)))
            with self.subTest(dtype=dtype):
                row = self.agrees_with_r1(request(dtype=dtype, truth_depth=depth, detected_depth=depth))
                self.assertEqual(row["fmax"], 1.0)

    def test_initialized_zero_floor_remains_disclosed(self):
        row = self.agrees_with_r1(request(truth=(100,), detected=(1000,)))
        self.assertEqual((row["fmax"], row["fmiss"], row["fpos"]), (0, 0, 0))
        self.assertEqual(row["definedness"], "initialized-zero-not-evidence-of-no-errors")

    def test_literal_event_reuse_is_preserved_without_bijective_repair(self):
        row = self.agrees_with_r1(request(truth=(100, 101), detected=(100,)))
        self.assertEqual(row["matched_all"][0], 2)
        self.assertEqual(row["inspected"][0]["distinct_detected_matched"], 1)
        self.assertEqual(row["fmax"], 1.0)

    def test_unresolved_paper40_is_not_enabled_by_source_admission(self):
        value = request()
        value["operation"] = "paper40"
        self.gate(value, "R-paper40-scientific-policy")

    def test_changed_numpy_profile_remains_unscorable(self):
        value = request()
        value["source_profile"]["numpy_version"] = "uninstalled-source-version"
        self.gate(value, "R-source-runtime")


if __name__ == "__main__":
    unittest.main(verbosity=2)
