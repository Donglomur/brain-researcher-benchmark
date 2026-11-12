"""Invented engineering controls; no empirical roster or neural data is used."""

import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest

_spec = importlib.util.spec_from_file_location(
    "neural008_numeric_claims", Path(__file__).with_name("neural008_numeric_claims.py"))
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
TARGET_IDS, TOLERANCE, check_claims = _module.TARGET_IDS, _module.TOLERANCE, _module.check_claims


def targets():
    """Abstract consecutive identifiers are invented only for these controls."""
    return {
        name: {"aggregate": 0.0, "per_person": {str(i): 0.0 for i in range(78)}}
        for name in TARGET_IDS
    }


def set_target(expected, name, value):
    expected[name] = {
        "aggregate": value,
        "per_person": {str(i): value for i in range(78)},
    }


class NumericClaimsControls(unittest.TestCase):
    def test_no_claims_has_no_verification_denominator(self):
        result = check_claims([], targets())
        self.assertEqual(result["counts"]["not_submitted"], 6)
        self.assertEqual(result["verification_denominator"], 0)
        self.assertIsNone(result["numeric_verification_rate"])

    def test_all_six_match_with_explicit_full_support(self):
        expected = targets()
        claims = [
            {"id": name, "value": row["aggregate"], "per_person": row["per_person"]}
            for name, row in expected.items()
        ]
        result = check_claims(claims, expected)
        self.assertEqual(result["counts"]["consistent"], 6)
        self.assertEqual(result["counts"]["finite_assertions"], 6)
        self.assertEqual(result["verification_numerator"], 6)
        self.assertEqual(result["verification_denominator"], 6)
        self.assertEqual(result["numeric_verification_rate"], 1.0)
        self.assertTrue(all(row["per_person_comparison"]["checked"] == 78
                            for row in result["recognized_claims"]))

    def test_aggregate_only_and_explicit_none_person_values_equivalent(self):
        implicit = check_claims([{"id": TARGET_IDS[0], "value": 0}], targets())
        explicit = check_claims([
            {"id": TARGET_IDS[0], "value": 0, "per_person": None}
        ], targets())
        self.assertEqual(implicit, explicit)

    def test_negative_effect_is_valid_and_can_be_consistent(self):
        expected = targets()
        set_target(expected, TARGET_IDS[0], -0.25)
        result = check_claims([{"id": TARGET_IDS[0], "value": -0.25}], expected)
        self.assertEqual(result["counts"]["negative_expected"], 1)
        self.assertEqual(result["counts"]["consistent"], 1)
        self.assertEqual(result["scientific_claim_validity"], "not_assessed")
        self.assertEqual(result["empirical_provenance"], "not_authenticated")

    def test_null_assertion_is_checked_definedness_not_abstention(self):
        expected = targets()
        set_target(expected, TARGET_IDS[3], None)
        result = check_claims([{"id": TARGET_IDS[3], "value": None}], expected)
        self.assertEqual(result["counts"]["undefined_assertions"], 1)
        self.assertEqual(result["counts"]["finite_assertions"], 0)
        self.assertEqual(result["counts"]["abstain"], 0)
        self.assertEqual(result["verification_numerator"], 1)
        self.assertEqual(result["verification_denominator"], 1)
        self.assertEqual(result["numeric_verification_rate"], 1.0)

    def test_one_undefined_person_requires_undefined_aggregate(self):
        expected = targets()
        expected[TARGET_IDS[3]]["per_person"]["0"] = None
        expected[TARGET_IDS[3]]["aggregate"] = None
        result = check_claims([{"id": TARGET_IDS[3], "value": None}], expected)
        self.assertEqual(result["counts"]["consistent"], 1)
        expected[TARGET_IDS[3]]["aggregate"] = 0.0
        with self.assertRaisesRegex(ValueError, "must be None"):
            check_claims([], expected)

    def test_null_and_finite_mismatch_in_both_directions(self):
        expected = targets()
        set_target(expected, TARGET_IDS[3], None)
        result = check_claims([
            {"id": TARGET_IDS[0], "value": None},
            {"id": TARGET_IDS[3], "value": 0},
        ], expected)
        self.assertEqual(result["counts"]["inconsistent"], 2)
        self.assertEqual(result["counts"]["undefined_assertions"], 1)
        self.assertEqual(result["counts"]["finite_assertions"], 1)
        for row in (result["recognized_claims"][0], result["recognized_claims"][3]):
            self.assertFalse(row["aggregate_comparison"]["definedness_match"])
            self.assertIsNone(row["aggregate_comparison"]["absolute_error"])

    def test_per_person_error_fails_even_when_aggregate_matches(self):
        expected = targets()
        values = dict(expected[TARGET_IDS[0]]["per_person"])
        values["77"] = 0.5
        result = check_claims([
            {"id": TARGET_IDS[0], "value": 0.0, "per_person": values}
        ], expected)
        row = result["recognized_claims"][0]
        self.assertEqual(row["status"], "inconsistent")
        self.assertTrue(row["aggregate_comparison"]["consistent"])
        self.assertEqual(row["per_person_comparison"]["consistent"], 77)
        self.assertEqual(row["per_person_comparison"]["inconsistent"], 1)
        self.assertEqual(row["per_person_comparison"]["mismatches"][0]["person"], "77")

    def test_per_person_null_mismatch_is_visible(self):
        expected = targets()
        expected[TARGET_IDS[3]]["per_person"]["0"] = None
        expected[TARGET_IDS[3]]["aggregate"] = None
        values = dict(expected[TARGET_IDS[3]]["per_person"])
        values["0"] = 0.0
        result = check_claims([
            {"id": TARGET_IDS[3], "value": None, "per_person": values}
        ], expected)
        mismatch = result["recognized_claims"][3]["per_person_comparison"]["mismatches"][0]
        self.assertEqual(result["counts"]["inconsistent"], 1)
        self.assertFalse(mismatch["definedness_match"])
        self.assertEqual(mismatch["person"], "0")

    def test_absolute_tolerance_boundary_is_inclusive(self):
        equal = check_claims([{"id": TARGET_IDS[0], "value": TOLERANCE}], targets())
        greater = check_claims([
            {"id": TARGET_IDS[0], "value": math.nextafter(TOLERANCE, math.inf)}
        ], targets())
        self.assertEqual(equal["counts"]["consistent"], 1)
        self.assertEqual(greater["counts"]["inconsistent"], 1)

    def test_per_person_tolerance_boundary(self):
        values = {str(i): 0.0 for i in range(78)}
        values["0"] = TOLERANCE
        claim = {"id": TARGET_IDS[0], "value": 0.0, "per_person": values}
        self.assertEqual(check_claims([claim], targets())["counts"]["consistent"], 1)
        values["0"] = math.nextafter(TOLERANCE, math.inf)
        self.assertEqual(check_claims([claim], targets())["counts"]["inconsistent"], 1)

    def test_unsupported_abstain_and_omission_do_not_earn_credit(self):
        result = check_claims([
            {"id": TARGET_IDS[0], "value": 0},
            {"id": TARGET_IDS[1], "value": 0.25},
            {"id": TARGET_IDS[2], "abstain": True},
            {"id": "unsupported_assertion", "value": 99},
            {"id": "unsupported_abstention", "abstain": True},
        ], targets())
        self.assertEqual(result["counts"], {
            "submitted": 5, "asserted": 2, "evaluable": 2, "consistent": 1,
            "inconsistent": 1, "abstain": 1, "not_submitted": 3,
            "unsupported": 2, "undefined_assertions": 0, "finite_assertions": 2,
            "negative_expected": 0,
        })
        self.assertEqual(result["numeric_verification_rate"], 0.5)
        self.assertEqual([r["submission_kind"] for r in result["unsupported_claims"]],
                         ["assertion", "abstain"])

    def test_only_unknown_or_abstaining_has_no_rate(self):
        result = check_claims([
            {"id": TARGET_IDS[0], "abstain": True},
            {"id": "unknown", "value": None},
        ], targets())
        self.assertEqual(result["verification_numerator"], 0)
        self.assertEqual(result["verification_denominator"], 0)
        self.assertIsNone(result["numeric_verification_rate"])

    def test_duplicate_known_and_unknown_ids_refused(self):
        for name in (TARGET_IDS[0], "unknown"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "duplicate"):
                check_claims([{"id": name, "value": 0}, {"id": name, "abstain": True}], targets())

    def test_malformed_claim_shapes_refused_including_unknown_ids(self):
        malformed = [
            None, [], {}, {"value": 0}, {"id": ""}, {"id": 1, "value": 0},
            {"id": "unknown"}, {"id": "unknown", "abstain": False},
            {"id": "unknown", "abstain": 1},
            {"id": "unknown", "abstain": True, "value": None},
            {"id": "unknown", "value": 0, "extra": 0},
        ]
        for claim in malformed:
            with self.subTest(claim=claim), self.assertRaises(ValueError):
                check_claims([claim], targets())
        for claims in (None, {}, (), "claims"):
            with self.subTest(claims=claims), self.assertRaises(ValueError):
                check_claims(claims, targets())

    def test_nonfinite_boolean_and_non_numeric_values_refused(self):
        bad_values = (True, False, math.nan, math.inf, -math.inf, "0", [], 10**400)
        for value in bad_values:
            for name in (TARGET_IDS[0], "unknown"):
                with self.subTest(value=repr(value), name=name), self.assertRaises(ValueError):
                    check_claims([{"id": name, "value": value}], targets())
            expected = targets()
            expected[TARGET_IDS[0]]["aggregate"] = value
            with self.subTest(expected=repr(value)), self.assertRaises(ValueError):
                check_claims([], expected)

    def test_bad_person_values_refused_in_claims_and_expected(self):
        for value in (True, False, math.nan, math.inf, "0"):
            expected = targets()
            expected[TARGET_IDS[0]]["per_person"]["0"] = value
            with self.subTest(expected=repr(value)), self.assertRaises(ValueError):
                check_claims([], expected)
            values = {str(i): 0 for i in range(78)}
            values["0"] = value
            for name in (TARGET_IDS[0], "unknown"):
                with self.subTest(claim=repr(value), name=name), self.assertRaises(ValueError):
                    check_claims([{"id": name, "value": 0, "per_person": values}], targets())

    def test_claim_bounds_and_interaction_bounds(self):
        for name in TARGET_IDS:
            bound = 2 if name.startswith("mode_interaction:") else 1
            for value in (-bound, bound):
                with self.subTest(name=name, value=value):
                    self.assertEqual(check_claims([{"id": name, "value": value}], targets())
                                     ["counts"]["evaluable"], 1)
            for value in (-bound - 0.01, bound + 0.01):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    check_claims([{"id": name, "value": value}], targets())

    def test_expected_bounds_and_interaction_endpoints(self):
        for name in TARGET_IDS:
            bound = 2 if name.startswith("mode_interaction:") else 1
            for value in (-bound, bound):
                expected = targets()
                set_target(expected, name, value)
                self.assertEqual(check_claims([{"id": name, "value": value}], expected)
                                 ["counts"]["consistent"], 1)
            expected = targets()
            set_target(expected, name, bound + 0.01)
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_claims([], expected)

    def test_person_claim_bounds_refused(self):
        for name in TARGET_IDS:
            values = {str(i): 0 for i in range(78)}
            values["0"] = 2.1 if name.startswith("mode_interaction:") else 1.1
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_claims([{"id": name, "value": 0, "per_person": values}], targets())

    def test_expected_requires_all_six_exact_ids(self):
        for remove, add in ((True, False), (False, True), (True, True)):
            expected = targets()
            if remove:
                expected.pop(TARGET_IDS[0])
            if add:
                expected["unknown"] = {"aggregate": 0, "per_person": {}}
            with self.subTest(remove=remove, add=add), self.assertRaises(ValueError):
                check_claims([], expected)

    def test_expected_row_shape_is_closed(self):
        for replacement in (None, [], {}, {"aggregate": 0},
                            {"aggregate": 0, "per_person": {}, "extra": 0}):
            expected = targets()
            expected[TARGET_IDS[0]] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                check_claims([], expected)

    def test_expected_requires_exact_78_consistent_person_ids(self):
        for count in (0, 77, 79):
            expected = targets()
            expected[TARGET_IDS[0]]["per_person"] = {str(i): 0 for i in range(count)}
            with self.subTest(count=count), self.assertRaises(ValueError):
                check_claims([], expected)
        expected = targets()
        expected[TARGET_IDS[5]]["per_person"]["78"] = expected[TARGET_IDS[5]]["per_person"].pop("0")
        with self.assertRaisesRegex(ValueError, "exact expected"):
            check_claims([], expected)

    def test_person_ids_are_canonical_ascii_nonnegative_strings(self):
        for bad in (0, "00", "01", "-1", "+1", "1.0", "", " 1", "1 ", "١", "１"):
            expected = targets()
            expected[TARGET_IDS[0]]["per_person"][bad] = expected[TARGET_IDS[0]]["per_person"].pop("0")
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                check_claims([], expected)
        # Noncontiguous invented IDs and zero are supported; no real roster is assumed.
        expected = targets()
        for row in expected.values():
            row["per_person"] = {str(i * 3): 0.0 for i in range(78)}
        self.assertEqual(check_claims([], expected)["counts"]["not_submitted"], 6)

    def test_supplied_person_mapping_requires_exact_expected_ids(self):
        cases = [None, [], {}, {str(i): 0 for i in range(77)}, {str(i): 0 for i in range(79)}]
        # None is expressly valid, so exercise only the malformed non-None cases.
        for values in cases[1:]:
            with self.subTest(kind=type(values).__name__, size=len(values)), self.assertRaises(ValueError):
                check_claims([{"id": TARGET_IDS[0], "value": 0, "per_person": values}], targets())
        values = {str(i): 0 for i in range(1, 79)}
        for name in (TARGET_IDS[0], "unknown"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "exact expected"):
                check_claims([{"id": name, "value": 0, "per_person": values}], targets())

    def test_expected_aggregate_must_be_all_person_mean(self):
        expected = targets()
        expected[TARGET_IDS[0]]["per_person"]["0"] = 0.78
        expected[TARGET_IDS[0]]["aggregate"] = 0.01
        self.assertEqual(check_claims([{"id": TARGET_IDS[0], "value": 0.01}], expected)
                         ["counts"]["consistent"], 1)
        for bad in (0.0, None):
            expected[TARGET_IDS[0]]["aggregate"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "mean"):
                check_claims([], expected)

    def test_no_input_mutation_or_output_aliasing(self):
        expected = targets()
        values = {str(i): 0.0 for i in range(78)}
        values["0"] = 0.5
        claims = [{"id": TARGET_IDS[0], "value": 0, "per_person": values}]
        before = copy.deepcopy((claims, expected))
        result = check_claims(claims, expected)
        self.assertEqual((claims, expected), before)
        result["recognized_claims"][0]["per_person_comparison"]["mismatches"][0]["value"] = 9
        result["recognized_claims"][0]["aggregate_comparison"]["expected"] = 9
        self.assertEqual((claims, expected), before)
        self.assertEqual(check_claims(claims, expected), check_claims(*before))

    def test_results_are_json_serializable_without_nonfinite_values(self):
        expected = targets()
        expected[TARGET_IDS[3]]["per_person"]["0"] = None
        expected[TARGET_IDS[3]]["aggregate"] = None
        result = check_claims([{"id": TARGET_IDS[3], "value": None}], expected)
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)

    def test_claim_order_does_not_change_recognized_results(self):
        expected = targets()
        claims = [{"id": name, "value": 0} for name in TARGET_IDS]
        self.assertEqual(check_claims(claims, expected), check_claims(list(reversed(claims)), expected))


if __name__ == "__main__":
    unittest.main(verbosity=2)
