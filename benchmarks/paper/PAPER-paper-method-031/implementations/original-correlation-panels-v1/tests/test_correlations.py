"""Generated arithmetic/support controls; no paper recordings or targets."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("fast_original_correlations", Path(__file__).parents[1] / "correlations.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def support(family="synthetic_fig3b"):
    real = family == "voltage_fig3f"
    return {"schema": M.SCHEMA, "task_id": M.TASK_ID, "family": family,
            "source_commit": M.SOURCE_COMMIT,
            "source_provenance": "generated-control-not-source-data",
            "strata": [{"condition_id": condition,
                        "recording_id": "fixture-" + condition,
                        "frame_ids": ["frame-" + str(i) for i in range(4982 if real else 4)],
                        "unit_ids": ["pixel-" + str(i) for i in range(100)] if real
                                    else ["neuron-" + str(i) for i in range(10)]}
                       for condition in M.CONDITIONS[family]]}


def packet(frozen, signal, reference=False):
    rows = []
    for row in frozen["strata"]:
        ids = (["synchronized_electrophysiology"]
               if reference and frozen["family"] == "voltage_fig3f" else row["unit_ids"][:])
        values = signal(len(row["frame_ids"]))
        rows.append({**row, "unit_ids": ids, "traces": [values[:] for _ in ids]})
    return {"support_sha256": M.support_sha256(frozen), "strata": rows}


def ramp(count):
    return [float(i) for i in range(count)]


def fixture():
    frozen = support()
    reference = packet(frozen, ramp, reference=True)
    methods = {name: packet(frozen, ramp) for name in M.SYNTHETIC_METHODS}
    return frozen, reference, methods


class CorrelationPanelTests(unittest.TestCase):
    def test_full_synthetic_original_panel_and_signed_candidate(self):
        frozen, reference, methods = fixture()
        candidate = packet(frozen, lambda n: [-v for v in ramp(n)])
        result = M.evaluate_panel(frozen, reference, methods, candidate)
        self.assertEqual(result["original_coefficient_count"], 240)
        self.assertEqual([r["condition_id"] for r in result["strata"]], ["2ms", "4ms", "6ms", "8ms"])
        self.assertEqual(sum(len(r["units"]) for r in result["strata"]), 40)
        for row in result["strata"]:
            for unit in row["units"]:
                self.assertAlmostEqual(unit["methods"]["FAST"]["pearson_r"], 1.0)
                self.assertAlmostEqual(unit["methods"]["candidate"]["pearson_r"], -1.0)
                self.assertAlmostEqual(unit["candidate_minus_FAST_r"], -2.0)
        self.assertIsNone(result["qualification"]["paper_win"])
        self.assertNotIn("mean_pearson", result)

    def test_complete_real_panel_uses_one_synchronized_ephys_trace(self):
        frozen = support("voltage_fig3f")
        reference = packet(frozen, ramp, reference=True)
        methods = {"raw": packet(frozen, lambda n: [-v for v in ramp(n)]),
                   "FAST": packet(frozen, lambda n: [2*v + 37 for v in ramp(n)])}
        result = M.evaluate_panel(frozen, reference, methods)
        self.assertEqual(result["original_coefficient_count"], 200)
        self.assertEqual(result["strata"][0]["original_frames"], 4982)
        self.assertEqual(len(result["strata"][0]["units"]), 100)
        references = {u["reference_float64_sha256"] for u in result["strata"][0]["units"]}
        self.assertEqual(len(references), 1)
        for unit in result["strata"][0]["units"]:
            self.assertAlmostEqual(unit["methods"]["raw"]["pearson_r"], -1)
            self.assertAlmostEqual(unit["methods"]["FAST"]["pearson_r"], 1)
        # An amplitude-changing affine transform may have r=1; no amplitude claim.
        self.assertFalse(result["qualification"]["source_preprocessing_verified"])

    def test_orthogonal_trace_has_zero_correlation_without_lag_search(self):
        frozen, reference, methods = fixture()
        for row in reference["strata"]:
            row["traces"] = [[-1.0, 1.0, -1.0, 1.0] for _ in row["unit_ids"]]
        candidate = packet(frozen, lambda n: [-1.0, -1.0, 1.0, 1.0])
        result = M.evaluate_panel(frozen, reference, methods, candidate)
        self.assertEqual(result["strata"][0]["units"][0]["methods"]["candidate"]["pearson_r"], 0)

    def test_undefined_values_remain_at_original_identities(self):
        frozen, reference, methods = fixture()
        methods["FAST"]["strata"][0]["traces"][0] = [3.0] * 4
        reference["strata"][1]["traces"][2] = [4.0] * 4
        methods["raw"]["strata"][1]["traces"][2] = [5.0] * 4
        result = M.evaluate_panel(frozen, reference, methods, packet(frozen, ramp))
        self.assertEqual(result["original_coefficient_count"], 240)
        self.assertEqual(result["undefined_original_coefficients"], 7)
        first = result["strata"][0]["units"][0]
        self.assertEqual(first["unit_id"], "neuron-0")
        self.assertEqual(first["methods"]["FAST"]["status"], "constant_prediction")
        self.assertIsNone(first["candidate_minus_FAST_r"])
        second = result["strata"][1]["units"][2]
        self.assertEqual(second["methods"]["raw"]["status"], "constant_both")
        self.assertEqual(second["methods"]["FAST"]["status"], "constant_reference")

    def test_large_finite_operands_do_not_overflow(self):
        frozen, reference, methods = fixture()
        candidate = packet(frozen, lambda n: [-1e308, -5e307, 5e307, 1e308])
        reference = packet(frozen, lambda n: [-1e308, -5e307, 5e307, 1e308], reference=True)
        result = M.evaluate_panel(frozen, reference, methods, candidate)
        self.assertAlmostEqual(result["strata"][0]["units"][0]["methods"]["candidate"]["pearson_r"], 1)

    def test_missing_original_method_cannot_be_replaced_by_candidate(self):
        frozen, reference, methods = fixture()
        candidate = methods.pop("FAST")
        with self.assertRaisesRegex(M.PanelError, "all original methods"):
            M.evaluate_panel(frozen, reference, methods, candidate)

    def test_extra_method_and_unknown_packet_fields_rejected(self):
        frozen, reference, methods = fixture()
        methods["other"] = methods["FAST"]
        with self.assertRaises(M.PanelError):
            M.evaluate_panel(frozen, reference, methods)
        del methods["other"]
        methods["FAST"]["fitted_lag"] = 1
        with self.assertRaises(M.PanelError):
            M.evaluate_panel(frozen, reference, methods)

    def test_changed_frame_order_or_unit_identity_fails(self):
        for field in ("frame_ids", "unit_ids"):
            frozen, reference, methods = fixture()
            row = methods["FAST"]["strata"][2]
            row[field] = list(reversed(row[field]))
            with self.subTest(field=field), self.assertRaises(M.PanelError):
                M.evaluate_panel(frozen, reference, methods)

    def test_missing_trace_or_nonfinite_or_boolean_is_not_dropped(self):
        for bad in (None, math.nan, math.inf, True):
            frozen, reference, methods = fixture()
            methods["FAST"]["strata"][0]["traces"][0][0] = bad
            with self.subTest(value=bad), self.assertRaises(M.PanelError):
                M.evaluate_panel(frozen, reference, methods)
        frozen, reference, methods = fixture()
        methods["FAST"]["strata"][0]["traces"].pop()
        with self.assertRaises(M.PanelError):
            M.evaluate_panel(frozen, reference, methods)

    def test_reflected_tail_or_short_output_rejected(self):
        for difference in (-1, 1):
            frozen, reference, methods = fixture()
            methods["FAST"]["strata"][0]["traces"][0] = [1.0] * (4+difference)
            with self.subTest(difference=difference), self.assertRaises(M.PanelError):
                M.evaluate_panel(frozen, reference, methods)

    def test_support_extent_duplicates_and_commitment_fail_closed(self):
        for field in ("frame_ids", "unit_ids"):
            frozen = support()
            frozen["strata"][0][field][-1] = frozen["strata"][0][field][0]
            with self.subTest(field=field), self.assertRaises(M.PanelError):
                M.support_sha256(frozen)
        frozen = support("voltage_fig3f")
        frozen["strata"][0]["frame_ids"].pop()
        with self.assertRaises(M.PanelError):
            M.support_sha256(frozen)
        frozen, reference, methods = fixture()
        methods["FAST"]["support_sha256"] = "0"*64
        with self.assertRaises(M.PanelError):
            M.evaluate_panel(frozen, reference, methods)

    def test_reference_cannot_have_pixel_specific_fitted_traces(self):
        frozen = support("voltage_fig3f")
        reference = packet(frozen, ramp)  #100 inputs instead of one fixed ephys trace
        methods = {name: packet(frozen, ramp) for name in M.VOLTAGE_METHODS}
        with self.assertRaisesRegex(M.PanelError, "unit identities"):
            M.evaluate_panel(frozen, reference, methods)

    def test_input_mutation_absent_and_value_hashes_change(self):
        frozen, reference, methods = fixture()
        before = copy.deepcopy((frozen, reference, methods))
        result = M.evaluate_panel(frozen, reference, methods)
        self.assertEqual((frozen, reference, methods), before)
        methods["FAST"]["strata"][0]["traces"][0][0] = -2.0
        changed = M.evaluate_panel(frozen, reference, methods)
        old = result["strata"][0]["units"][0]["methods"]["FAST"]
        new = changed["strata"][0]["units"][0]["methods"]["FAST"]
        self.assertNotEqual(old["trace_float64_sha256"], new["trace_float64_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
