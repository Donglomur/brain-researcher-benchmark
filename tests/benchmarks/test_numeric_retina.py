"""Invented numeric controls only; no retinal data or scientific qualification."""
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/shared/retina-coding/construction"
BINDINGS = ROOT / "benchmarks/integrity/current-closures/numeric-retina/SOURCE_BINDINGS.json"


def load_kernels():
    """Load only the two reviewed standard-library modules from their exact paths."""
    saved = sys.modules.get("retina_contract")
    try:
        for name in ("retina_contract", "scientific_kernels"):
            spec = importlib.util.spec_from_file_location(name, PACKAGE / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            if name == "retina_contract":
                sys.modules[name] = module
            spec.loader.exec_module(module)
        return module
    finally:
        if saved is None:
            sys.modules.pop("retina_contract", None)
        else:
            sys.modules["retina_contract"] = saved


kernels = load_kernels()


def rational_reference(target, prediction):
    """Independent exact rational oracle for the supplied binary64 values."""
    y, p = list(map(Fraction, target)), list(map(Fraction, prediction))
    mean = sum(y) / len(y)
    sse = sum((a - b) ** 2 for a, b in zip(y, p))
    sst = sum((a - mean) ** 2 for a in y)
    return float(sse), float(sse / len(y)), None if sst == 0 else float(1 - sse / sst)


class RetinaNumericTests(unittest.TestCase):
    def test_lossy_integer_admission_refuses_each_vector(self):
        base = 2 ** 53
        for target, prediction, label in (
            ([base + 1, base + 3], [base, base + 2], "target"),
            ([base, base + 2, base + 4], [base + 1, base + 3, base + 5], "prediction"),
            ([0, 1], [0, -(base + 1)], "prediction"),
        ):
            with self.subTest(label=label, target=target):
                with self.assertRaisesRegex(kernels.Refusal, label + ":integer_precision"):
                    kernels.score_response(target, prediction)

    def test_exact_large_integers_remain_admissible(self):
        base = 2 ** 53
        result = kernels.score_response([base, base + 2, base + 4],
                                        [base + 2, base + 4, base + 6])
        self.assertEqual((result["sse"], result["mse"], result["r2_unclipped"]), (12., 4., -.5))
        result = kernels.score_response([2 ** 1023] * 2, [2 ** 1023] * 2)
        self.assertEqual(result["mse"], 0.)
        self.assertTrue(result["constant_target_hold"])

    def test_exact_float_translation_does_not_round_target_mean(self):
        base = float(2 ** 53)
        unshifted = kernels.score_response([0., 2.], [0., 0.])
        shifted = kernels.score_response([base, base + 2.], [base, base])
        self.assertEqual(shifted, unshifted)
        self.assertEqual(shifted["r2_unclipped"], -1.)

    def test_unrepresentable_positive_sse_refuses(self):
        with self.assertRaisesRegex(kernels.Refusal, "metric:underflow"):
            kernels.score_response([0., 1e-200], [0., 0.])

    def test_unrepresentable_positive_mse_refuses_even_if_sse_is_representable(self):
        tiny = math.ldexp(1., -537)
        self.assertEqual(tiny * tiny, math.ulp(0.))
        with self.assertRaisesRegex(kernels.Refusal, "metric:underflow"):
            kernels.score_response([0., tiny], [0., 0.])

    def test_representable_subnormal_losses_are_not_rejected(self):
        tiny = math.ldexp(1., -537)
        result = kernels.score_response([0., tiny], [-tiny, 0.])
        self.assertEqual(result["sse"], 2 * math.ulp(0.))
        self.assertEqual(result["mse"], math.ulp(0.))
        self.assertEqual(result["r2_unclipped"], -3.)
        self.assertFalse(result["constant_target_hold"])

    def test_sse_and_mse_round_independently_at_subnormal_boundary(self):
        tiny = math.ldexp(1., -537)
        target, prediction = [0.] * 3, [-tiny, -tiny, -tiny / 2]
        expected_sse, expected_mse, _ = rational_reference(target, prediction)
        result = kernels.score_response(target, prediction)
        self.assertEqual(result["sse"], expected_sse)
        self.assertEqual(result["mse"], expected_mse)

    def test_half_minimum_subnormal_boundary_is_rounded_once(self):
        boundary = math.ldexp(math.sqrt(.5), -537)
        for tiny in (math.nextafter(boundary, 0.), boundary,
                     math.nextafter(boundary, math.inf)):
            target, prediction = [0.], [-tiny]
            expected_sse, expected_mse, _ = rational_reference(target, prediction)
            with self.subTest(tiny=tiny):
                if expected_mse == 0:
                    with self.assertRaisesRegex(kernels.Refusal, "metric:underflow"):
                        kernels.score_response(target, prediction)
                else:
                    result = kernels.score_response(target, prediction)
                    self.assertEqual(result["sse"], expected_sse)
                    self.assertEqual(result["mse"], expected_mse)

    def test_subnormal_boundary_uses_exact_original_difference(self):
        # The tiny positive target matters at the rounding boundary even when
        # subtracting the prediction in binary64 first would lose that term.
        boundary = math.nextafter(math.ldexp(math.sqrt(.5), -537), 0.)
        target, prediction = [math.ldexp(boundary, -52)], [-boundary]
        expected_sse, expected_mse, _ = rational_reference(target, prediction)
        result = kernels.score_response(target, prediction)
        self.assertEqual(result["sse"], expected_sse)
        self.assertEqual(result["mse"], expected_mse)

    def test_tiny_nonconstant_perfect_fit_remains_nonconstant(self):
        for tiny in (1e-200, math.ulp(0.)):
            with self.subTest(tiny=tiny):
                result = kernels.score_response([0., tiny], [0., tiny])
                self.assertEqual(result["sse"], 0.)
                self.assertEqual(result["mse"], 0.)
                self.assertEqual(result["r2_unclipped"], 1.)
                self.assertFalse(result["constant_target_hold"])

    def test_large_internal_sst_does_not_prevent_representable_outputs(self):
        for target, prediction in (([0., 1e308], [0., 1e308]),
                                   ([0., 1e200], [1., 1e200])):
            with self.subTest(target=target):
                result = kernels.score_response(target, prediction)
                sse, mse, r2 = rational_reference(target, prediction)
                self.assertEqual((result["sse"], result["mse"], result["r2_unclipped"]),
                                 (sse, mse, r2))
                self.assertFalse(result["constant_target_hold"])

    def test_large_constant_target_avoids_sum_overflow(self):
        result = kernels.score_response([1e308, 1e308], [1e308, 1e308])
        self.assertTrue(result["constant_target_hold"])
        self.assertIsNone(result["r2_unclipped"])
        self.assertEqual(result["mse"], 0.)

    def test_overflow_and_nonfinite_ratio_remain_explicit_refusals(self):
        cases = (([0., 1.], [1e154, 1.], "metric:nonfinite_ratio"),
                 ([0., 1.], [1e308, 1.], "metric:overflow"),
                 ([1e308], [-1e308], "metric:overflow"))
        for target, prediction, reason in cases:
            with self.subTest(reason=reason, target=target):
                with self.assertRaisesRegex(kernels.Refusal, reason):
                    kernels.score_response(target, prediction)

    def test_generated_translations_and_scales_match_exact_rational_oracle(self):
        # Binary powers ensure the generated inputs are the intended exact values.
        for exponent in (-500, -30, 0, 30, 500):
            unit = math.ldexp(1., exponent)
            for origin in (0., 16 * unit, math.ldexp(unit, 53)):
                for errors in ((0, 0, 0, 0), (2, -2, 0, 2), (8, 6, 4, 2)):
                    target = [origin + k * unit for k in (0, 2, 6, 8)]
                    prediction = [a + e * unit for a, e in zip(target, errors)]
                    with self.subTest(exponent=exponent, origin=origin, errors=errors):
                        actual = kernels.score_response(target, prediction)
                        expected = rational_reference(target, prediction)
                        for field, value in zip(("sse", "mse", "r2_unclipped"), expected):
                            self.assertTrue(math.isclose(actual[field], value, rel_tol=2e-14,
                                                         abs_tol=0.), (field, actual[field], value))

    def test_existing_scientific_guards_and_fields_remain(self):
        for target, prediction, reason in (([0., 1.], [0.], "complete_frames"),
                                           ([0., 1.], [0., True], "finite"),
                                           ([0., 1.], [0., float("nan")], "finite"),
                                           ([-1., 0.], [0., 0.], "negative_firing_rate")):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(kernels.Refusal, reason):
                    kernels.score_response(target, prediction)
        result = kernels.score_response([0., 1.], [-2., -1.])
        self.assertEqual(result["frames"], 2)
        self.assertEqual(result["negative_prediction_frames"], 2)
        self.assertEqual(result["r2_unclipped"], -15.)
        self.assertEqual(result["r2_historical_clipped"], 0.)
        self.assertFalse(result["historical_nan_dropping_used"])

    def test_pair_ranking_also_refuses_lossy_integer_coercion(self):
        with self.assertRaisesRegex(kernels.Refusal, "protected_target:integer_precision"):
            kernels.pair_disagreement_ranking([[0, 0]] * 2, [[1, 1]] * 2,
                [[2 ** 53, 2 ** 53 + 1]] * 2, [{"id": "f", "frames": [0, 1]}])

    def test_current_descriptor_binds_reviewed_sources_and_preserves_holds(self):
        descriptor = json.loads(BINDINGS.read_text())
        self.assertEqual(descriptor["schema"], "retina_numeric_current_bindings_v1")
        self.assertFalse(descriptor["scientific_qualification"])
        self.assertFalse(descriptor["execution_authority"])
        self.assertEqual(descriptor["legacy_offline_control_count"], 76)
        for row in descriptor["files"]:
            with self.subTest(path=row["path"]):
                body = (ROOT / row["path"]).read_bytes()
                self.assertEqual(len(body), row["bytes"])
                self.assertEqual(hashlib.sha256(body).hexdigest(), row["sha256"])


if __name__ == "__main__":
    unittest.main()
