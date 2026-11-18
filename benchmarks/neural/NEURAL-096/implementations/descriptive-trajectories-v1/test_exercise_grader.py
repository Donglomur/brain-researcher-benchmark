"""Small in-memory controls for operator grading checks; no authentic data."""
from copy import deepcopy
from pathlib import Path
import math
import os
import tempfile
import unittest

import exercise_grader as exercise
from packet import PacketError, strict_json
from score import expected_answer, grade
from trajectory import METHOD, TrajectoryError
from view import ordered_cells


def reference_fixture():
    """Two supported generated cells, with negative, null and positive means.

    This is a scorer fixture, not a simulated neural recording or source packet.
    No trial arrays, output files or authentic source values are constructed.
    """
    cells = []
    for index, (cell_id, _, _, _, _) in enumerate(ordered_cells()):
        supported = index in (5, 37)
        cells.append({
            "cell_id": cell_id,
            "supported": supported,
            "n_long": 2 if supported else 0,
            "n_short": 3 if supported else 0,
            "summary": ({
                "quarter_signed_mean_hz": [-4.0, -2.0, 0.0, 2.0]
                    if index == 5 else [1.0, 2.0, 3.0, 4.0],
                "quarter_rms_hz": [0.0, 2.0, 4.0, 6.0]
                    if index == 5 else [1.0, 3.0, 5.0, 7.0],
            } if supported else None),
        })
    return {"method": METHOD, "cells": cells}


class FixedControlSemantics(unittest.TestCase):
    def setUp(self):
        self.reference = reference_fixture()
        self.expected = expected_answer(self.reference)
        controls, self.supported = exercise.make_controls(self.expected)
        self.controls = {item["name"]: item for item in controls}

    def control_grade(self, name):
        item = self.controls[name]
        result = grade(self.reference, item["answer"])
        exercise.check_grade(name, result, self.supported, item.get("cell_id"),
                             expected_shift_errors=item.get("expected_shift_errors"))
        return result

    def check_shift_grade(self, result, expectation=None):
        if expectation is None:
            expectation = self.controls["one_hz_shift"]["expected_shift_errors"]
        exercise.check_grade("one_hz_shift", result, self.supported,
                             expected_shift_errors=expectation)

    def assert_zero_errors(self, result):
        for field in exercise.FIELDS:
            self.assertEqual(result["numeric_errors"][field], {
                "mean_absolute_error_hz": 0.0,
                "max_absolute_error_hz": 0.0,
                "scored_values": 8,
            })

    def test_control_roster_and_deep_copy_preserve_expected_answer(self):
        self.assertEqual(set(self.controls), {
            "oracle", "one_hz_shift", "false_inference", "supported_abstention",
            "unsupported_fabrication", "wrong_count", "missing_cell",
            "nonfinite_json", "wrong_completion_identity",
        })
        self.assertEqual(self.supported, 2)
        self.assertEqual(sum(item["reject"] for item in self.controls.values()), 3)
        self.assertEqual(self.expected, expected_answer(self.reference))
        self.controls["oracle"]["answer"]["cells"][5]["quarter_signed_mean_hz"][0] = 999.0
        self.assertEqual(self.expected["cells"][5]["quarter_signed_mean_hz"][0], -4.0)
        self.assertEqual(self.controls["wrong_count"]["answer"]["cells"][5]
                         ["quarter_signed_mean_hz"][0], -4.0)

    def test_oracle_accepts_negative_and_zero_descriptive_means(self):
        result = self.control_grade("oracle")
        self.assert_zero_errors(result)
        self.assertIsNone(result["binary_win"])
        self.assertTrue(result["uncertainty_qualification_correct"])
        self.assertTrue(result["interpretation_scope_correct"])
        self.assertEqual(result["support_error_cells"], [])

    def test_one_hz_shift_has_known_error_on_generated_integers(self):
        result = self.control_grade("one_hz_shift")
        expected_rows = self.controls["one_hz_shift"]["expected_shift_errors"]
        self.assertEqual([row["cell_id"] for row in expected_rows],
                         [row["cell_id"] for row in self.expected["cells"]])
        self.assertIsNone(expected_rows[0]["absolute_errors_hz"])
        for index in (5, 37):
            self.assertEqual(expected_rows[index]["absolute_errors_hz"],
                             {field: [1.0] * 4 for field in exercise.FIELDS})
        for field in exercise.FIELDS:
            self.assertEqual(result["numeric_errors"][field], {
                "mean_absolute_error_hz": 1.0,
                "max_absolute_error_hz": 1.0,
                "scored_values": 8,
            })
        falsely_zero = deepcopy(result)
        falsely_zero["numeric_errors"][exercise.FIELDS[0]]["mean_absolute_error_hz"] = 0.0
        with self.assertRaises(ValueError):
            self.check_shift_grade(falsely_zero)

    def test_shift_control_rejects_consistently_doubled_errors(self):
        doubled = self.control_grade("one_hz_shift")
        for field in exercise.FIELDS:
            doubled["numeric_errors"][field]["mean_absolute_error_hz"] *= 2
            doubled["numeric_errors"][field]["max_absolute_error_hz"] *= 2
        for row in doubled["per_cell"]:
            if row["absolute_errors_hz"] is not None:
                for field in exercise.FIELDS:
                    row["absolute_errors_hz"][field] = [2 * x for x in row["absolute_errors_hz"][field]]
        with self.assertRaisesRegex(ValueError, "control error magnitude differs"):
            self.check_shift_grade(doubled)

    def test_shift_control_rejects_inconsistent_error_magnitudes(self):
        original = self.control_grade("one_hz_shift")
        for mismatch in ("coordinate", "mean", "maximum"):
            with self.subTest(mismatch=mismatch):
                changed = deepcopy(original)
                if mismatch == "coordinate":
                    changed["per_cell"][5]["absolute_errors_hz"][exercise.FIELDS[0]][2] = 2.0
                else:
                    metric = "mean_absolute_error_hz" if mismatch == "mean" else "max_absolute_error_hz"
                    changed["numeric_errors"][exercise.FIELDS[1]][metric] = 2.0
                with self.assertRaisesRegex(ValueError, "control error magnitude differs"):
                    self.check_shift_grade(changed)

    def test_shift_control_binds_every_error_to_its_declared_cell_and_quarter(self):
        original = self.control_grade("one_hz_shift")
        for mismatch in ("duplicate_id", "wrong_order", "unsupported_location", "three_plus_five",
                         "false_support", "false_count", "integer_count_flag", "extra_row_key"):
            with self.subTest(mismatch=mismatch):
                changed = deepcopy(original)
                rows = changed["per_cell"]
                if mismatch == "duplicate_id":
                    rows[1]["cell_id"] = rows[0]["cell_id"]
                elif mismatch == "wrong_order":
                    rows[0], rows[1] = rows[1], rows[0]
                elif mismatch == "unsupported_location":
                    rows[0]["absolute_errors_hz"] = rows[5]["absolute_errors_hz"]
                    rows[5]["absolute_errors_hz"] = None
                elif mismatch == "three_plus_five":
                    # Flat total length stays8; each cell must still have4 quarters.
                    value = rows[5]["absolute_errors_hz"][exercise.FIELDS[0]].pop()
                    rows[37]["absolute_errors_hz"][exercise.FIELDS[0]].append(value)
                elif mismatch == "false_support":
                    rows[5]["support_correct"] = False
                elif mismatch == "false_count":
                    rows[5]["counts_correct"] = False
                elif mismatch == "integer_count_flag":
                    rows[5]["counts_correct"] = 1
                else:
                    rows[5]["unlisted"] = "must be rejected"
                with self.assertRaises(ValueError):
                    self.check_shift_grade(changed)

    def test_shift_control_requires_complete_independent_expectations(self):
        result = self.control_grade("one_hz_shift")
        expected = self.controls["one_hz_shift"]["expected_shift_errors"]
        with self.assertRaisesRegex(ValueError, "independently identified shift-control cells"):
            exercise.check_grade("one_hz_shift", result, self.supported)
        with self.assertRaisesRegex(ValueError, "independently identified shift-control cells"):
            self.check_shift_grade(result, expected[:-1])
        duplicated = deepcopy(expected)
        duplicated[1]["cell_id"] = duplicated[0]["cell_id"]
        with self.assertRaisesRegex(ValueError, "identities must be unique"):
            self.check_shift_grade(result, duplicated)
        incomplete = deepcopy(expected)
        incomplete[5]["absolute_errors_hz"][exercise.FIELDS[0]].pop()
        with self.assertRaisesRegex(ValueError, "four control error quarters"):
            self.check_shift_grade(result, incomplete)

    def test_control_agreement_uses_only_frozen_roundoff_rule(self):
        self.assertEqual(exercise.CONTROL_PREDICATE,
                         "abs(a-b) <= max(1e-12 Hz, 1e-12 * max(abs(a), abs(b)))")
        exercise.control_agreement(1e-12, 0.0)
        exercise.control_agreement(0.0, 1e-12)
        immediately_above = math.nextafter(1e-12, math.inf)
        for actual, expected in ((immediately_above, 0.0), (0.0, immediately_above)):
            with self.assertRaisesRegex(ValueError, "control error magnitude differs"):
                exercise.control_agreement(actual, expected)
        large = float(2**40)
        exercise.control_agreement(large + 1.0, large)
        exercise.control_agreement(large, large + 1.0)
        with self.assertRaisesRegex(ValueError, "control error magnitude differs"):
            exercise.control_agreement(large + 2.0, large)
        for invalid in (True, float("nan"), float("inf")):
            with self.assertRaisesRegex(ValueError, "finite control metrics required"):
                exercise.control_agreement(invalid, 1.0)

    def test_false_inference_keeps_zero_error_but_fails_qualification(self):
        result = self.control_grade("false_inference")
        self.assert_zero_errors(result)
        self.assertFalse(result["uncertainty_qualification_correct"])
        self.assertFalse(result["interpretation_scope_correct"])
        invented_qualification = deepcopy(result)
        invented_qualification["uncertainty_qualification_correct"] = True
        with self.assertRaises(ValueError):
            exercise.check_grade("false_inference", invented_qualification, self.supported)

    def test_abstention_prevents_numeric_aggregate(self):
        result = self.control_grade("supported_abstention")
        target = self.expected["cells"][5]["cell_id"]
        self.assertEqual(result["support_error_cells"], [target])
        self.assertEqual(result["missing_numeric_cells"], [target])
        self.assertEqual(result["numeric_errors"], {field: None for field in exercise.FIELDS})
        self.assertEqual(result["numeric_status"], "missing_supported_cell_estimates")
        fabricated_aggregate = deepcopy(result)
        fabricated_aggregate["numeric_errors"][exercise.FIELDS[0]] = {
            "mean_absolute_error_hz": 0.0, "max_absolute_error_hz": 0.0, "scored_values": 4}
        with self.assertRaises(ValueError):
            exercise.check_grade("supported_abstention", fabricated_aggregate, self.supported, target)

    def test_unsupported_fabrication_does_not_disappear_into_zero_error(self):
        result = self.control_grade("unsupported_fabrication")
        target = self.expected["cells"][0]["cell_id"]
        self.assert_zero_errors(result)
        self.assertEqual(result["support_error_cells"], [target])
        self.assertEqual(result["unsupported_cells_given_numbers"], [target])
        omitted_flag = deepcopy(result)
        omitted_flag["unsupported_cells_given_numbers"] = []
        with self.assertRaises(ValueError):
            exercise.check_grade("unsupported_fabrication", omitted_flag, self.supported, target)

    def test_wrong_count_is_reported_separately_from_numeric_error(self):
        result = self.control_grade("wrong_count")
        target = self.expected["cells"][5]["cell_id"]
        self.assert_zero_errors(result)
        self.assertEqual(result["count_error_cells"], [target])
        self.assertEqual(result["support_error_cells"], [])

    def test_missing_cell_is_an_intended_roster_refusal(self):
        with self.assertRaisesRegex(TrajectoryError, "^complete cell roster required$"):
            grade(self.reference, self.controls["missing_cell"]["answer"])

    def test_nonfinite_control_exercises_json_ingestion(self):
        answer = self.controls["nonfinite_json"]["answer"]
        with self.assertRaises(ValueError):
            exercise.encoded(answer)
        body = exercise.encoded(answer, permit_nonfinite=True)
        self.assertIn(b"NaN", body)
        with self.assertRaisesRegex(PacketError, "^nonfinite JSON constant: NaN$"):
            strict_json(body)

    def test_suite_requires_both_supported_and_unsupported_groups(self):
        all_absent = deepcopy(self.expected)
        for cell in all_absent["cells"]:
            cell["support_status"] = "unsupported"
        with self.assertRaisesRegex(ValueError, "requires supported and unsupported"):
            exercise.make_controls(all_absent)
        all_present = deepcopy(self.expected)
        for cell in all_present["cells"]:
            cell["support_status"] = "supported"
        with self.assertRaisesRegex(ValueError, "requires supported and unsupported"):
            exercise.make_controls(all_present)

    def test_refusal_requires_the_intended_exception_and_reason(self):
        intended = {
            "missing_cell": TrajectoryError("complete cell roster required"),
            "nonfinite_json": PacketError("nonfinite JSON constant: NaN"),
            "wrong_completion_identity": TrajectoryError(
                "completion differs from operator-frozen identity"),
        }
        for name, error in intended.items():
            with self.subTest(name=name):
                exercise.check_refusal(name, error)
                with self.assertRaisesRegex(ValueError, "intended validation boundary"):
                    exercise.check_refusal(name, type(error)("producer changed during preparation"))
                with self.assertRaisesRegex(ValueError, "intended validation boundary"):
                    exercise.check_refusal(name, ValueError(str(error)))
        with self.assertRaisesRegex(ValueError, "undeclared refusal control"):
            exercise.check_refusal("oracle", TrajectoryError("complete cell roster required"))

    def test_saved_grade_matches_returned_result_and_candidate_commitment(self):
        result = self.control_grade("oracle")
        candidate_pin = exercise.pin(exercise.encoded(self.controls["oracle"]["answer"]))
        result["submission"] = candidate_pin
        body = exercise.encoded(result)
        exercise.check_saved_grade(body, result, candidate_pin)
        different_candidate = exercise.pin(b"different candidate")
        with self.assertRaisesRegex(ValueError, "exact submitted candidate"):
            exercise.check_saved_grade(body, result, different_candidate)
        malformed = b'{"submission":'
        with self.assertRaises(PacketError):
            exercise.check_saved_grade(malformed, result, candidate_pin)

    def test_saved_grade_type_change_is_not_hidden_by_python_equality(self):
        result = self.control_grade("oracle")
        candidate_pin = exercise.pin(exercise.encoded(self.controls["oracle"]["answer"]))
        result["submission"] = candidate_pin
        changed = deepcopy(result)
        changed["numeric_errors"][exercise.FIELDS[0]]["mean_absolute_error_hz"] = False
        # Python equality aliases False and0.0; the persisted contract must not.
        self.assertEqual(changed, result)
        with self.assertRaisesRegex(ValueError, "persisted grade differs"):
            exercise.check_saved_grade(exercise.encoded(changed), result, candidate_pin)


class ClosedInventoryControls(unittest.TestCase):
    """Only3-byte placeholders are written; no numerical/candidate data files."""
    def make_inventory(self, root):
        for folder in ("submissions", "grades"):
            (root / folder).mkdir()
            (root / folder / "one.json").write_bytes(b"{}\n")
        return {"submissions/one.json": exercise.pin(b"{}\n"),
                "grades/one.json": exercise.pin(b"{}\n")}

    def test_complete_marker_is_explicit_and_does_not_replace_inventory(self):
        with tempfile.TemporaryDirectory(prefix="neural096-control-inventory-") as directory:
            root = Path(directory)
            inventory = self.make_inventory(root)
            exercise.validate_control_inventory(root, inventory)
            with self.assertRaisesRegex(ValueError, "unlisted control entry"):
                exercise.validate_control_inventory(root, inventory, complete=True)
            (root / "REPORT.json").write_bytes(b"{}\n")
            exercise.validate_control_inventory(root, inventory, complete=True)
            with self.assertRaisesRegex(ValueError, "unlisted control entry"):
                exercise.validate_control_inventory(root, inventory)

    def test_empty_extra_directory_and_nested_inventory_path_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="neural096-control-inventory-") as directory:
            root = Path(directory)
            inventory = self.make_inventory(root)
            (root / "submissions" / "unlisted-empty-directory").mkdir()
            with self.assertRaisesRegex(ValueError, "unlisted control entry"):
                exercise.validate_control_inventory(root, inventory)
            with self.assertRaisesRegex(ValueError, "unexpected control inventory path"):
                exercise.validate_control_inventory(root, {"grades/nested/one.json": {}})

    def test_dangling_symlink_cannot_replace_an_expected_grade(self):
        with tempfile.TemporaryDirectory(prefix="neural096-control-inventory-") as directory:
            root = Path(directory)
            inventory = self.make_inventory(root)
            target = root / "grades" / "one.json"
            target.unlink()
            target.symlink_to(root / "missing-target")
            with self.assertRaisesRegex(ValueError, "indirect control entry"):
                exercise.validate_control_inventory(root, inventory)

    def test_special_file_cannot_replace_an_expected_grade(self):
        with tempfile.TemporaryDirectory(prefix="neural096-control-inventory-") as directory:
            root = Path(directory)
            inventory = self.make_inventory(root)
            target = root / "grades" / "one.json"
            target.unlink()
            # The operator runtime is POSIX (macOS/Linux); no pipe is opened.
            os.mkfifo(target)
            with self.assertRaisesRegex(ValueError, "ordinary control file required"):
                exercise.validate_control_inventory(root, inventory)


if __name__ == "__main__":
    unittest.main()
