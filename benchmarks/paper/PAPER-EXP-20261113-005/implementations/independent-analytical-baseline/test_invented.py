"""Invented source controls. Authored but NOT executed during this phase.

These controls contain no participant packet data or reference answers.
Their expected values come from finite enumeration and hand-sized examples.
Running this file in a later, separately authorized phase would import only
its sibling solution.py and the Python standard library.
"""

from contextlib import redirect_stdout
from fractions import Fraction
import io
from itertools import combinations
import json
import unittest
from unittest.mock import mock_open, patch

from solution import (OUTPUT_SCHEMA, PACKET_SCHEMA, Reconstruction,
                      cell_moments, submission_output, write_jsonl)


def invented_packet():
    records = [
        {"id": "a0", "animal": "A", "task": "t0"},
        {"id": "b0", "animal": "B", "task": "t0"},
        {"id": "a1", "animal": "A", "task": "t1"},
        {"id": "b1", "animal": "B", "task": "t1"},
        {"id": "a2", "animal": "A", "task": "t2"},
        {"id": "empty", "animal": "C", "task": "unused-task"},
    ]
    rows = [
        ("u0", "a0", "A", "t0", 0, [0, 0]),
        ("u1", "a0", "A", "t0", 1, [0, -1]),
        ("u2", "b0", "B", "t0", 0, [1, -1]),
        ("u3", "b0", "B", "t0", 1, [1, 1]),
        ("u4", "a1", "A", "t1", 0, [0, -1]),
        ("u5", "b1", "B", "t1", 1, [1, -1]),
        ("u6", "a2", "A", "t2", 2, [0, -1]),
    ]
    return {
        "schema": PACKET_SCHEMA,
        "animals": ["A", "B", "C"],
        "families": [
            {"key": "all-eligible", "labels": ["x", "y", "unused"]},
            {"key": "selected-only", "labels": ["e", "f", "unused"]},
        ],
        "records": records,
        "units": [dict(zip(("id", "recording", "animal", "task",
                            "category", "labels"), row)) for row in rows],
        "contexts": [],
        "historical_diagnostics": {"fixture": "invented"},
    }


class InventedControls(unittest.TestCase):
    def setUp(self):
        self.reconstruction = Reconstruction(invented_packet(),
                                             fixed_dimensions=False)

    def test_small_overlap_by_enumeration(self):
        # Fix the r ROI positions. Enumerate every c-subset of category
        # positions with equal weight; calculate moments from those outcomes.
        # This does not reuse the closed-form variance in its expectation.
        for n in range(7):
            for r in range(n + 1):
                roi = set(range(r))
                for c in range(n + 1):
                    outcomes = [len(roi.intersection(positions))
                                for positions in combinations(range(n), c)]
                    expected_mean = Fraction(sum(outcomes), len(outcomes))
                    expected_variance = (
                        sum((Fraction(value) - expected_mean) ** 2
                            for value in outcomes) / len(outcomes))
                    self.assertEqual(cell_moments(n, r, c),
                                     (expected_mean, expected_variance))

    def test_independent_strata_add_moments(self):
        family = self.reconstruction.case()["families"][0]
        self.assertEqual(family["counts"],
                         [[2, 1, 1, 0, 0, 0, 0, 0],
                          [1, 2, 0, 0, 0, 0, 0, 0],
                          [0] * 8])
        # t0 contributes mean 1 and variance 1/3 to these cells;
        # t1 contributes mean 1/2 and variance 1/4.
        for row in (0, 1):
            for category in (0, 1):
                self.assertEqual(family["mean"][row][category], [3, 2])
                self.assertEqual(family["variance"][row][category], [7, 12])
        self.assertEqual(family["mean"][0][2], [1, 1])
        self.assertEqual(family["variance"][0][2], [0, 1])

    def test_family_eligibility_controls_its_population(self):
        family = self.reconstruction.case()["families"][1]
        self.assertEqual(family["counts"][0], [1, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(family["counts"][1], [0, 1, 0, 0, 0, 0, 0, 0])
        for row in (0, 1):
            for category in (0, 1):
                self.assertEqual(family["mean"][row][category], [1, 2])
                self.assertEqual(family["variance"][row][category], [1, 4])

    def test_whole_animal_across_recordings_and_families(self):
        without_a = self.reconstruction.case(0)
        self.assertEqual(without_a["case"], "without:A")
        self.assertEqual(without_a["families"][0]["counts"],
                         [[0] * 8, [1, 2, 0, 0, 0, 0, 0, 0], [0] * 8])
        self.assertEqual(without_a["families"][1]["counts"],
                         [[0] * 8, [0, 1, 0, 0, 0, 0, 0, 0], [0] * 8])
        for family in without_a["families"]:
            for row_index, row in enumerate(family["counts"]):
                self.assertEqual(family["mean"][row_index],
                                 [[value, 1] for value in row])
                self.assertEqual(family["variance"][row_index], [[0, 1]] * 8)

    def test_zero_fitting_animal_has_a_complete_identical_case(self):
        self.assertEqual(self.reconstruction.case(2)["families"],
                         self.reconstruction.case()["families"])

    def test_zero_fitting_record_may_use_animal_outside_roster(self):
        packet = invented_packet()
        packet["records"].append({
            "id": "outside-empty",
            "animal": "outside-fitting-roster",
            "task": "outside-empty-task",
        })
        reconstruction = Reconstruction(packet, fixed_dimensions=False)
        self.assertEqual(reconstruction.animals, ["A", "B", "C"])
        for deleted in (None, 0, 1, 2):
            self.assertEqual(reconstruction.case(deleted),
                             self.reconstruction.case(deleted))

    def test_unsupported_axes_remain_present(self):
        for deleted in (None, 0, 1, 2):
            for family in self.reconstruction.case(deleted)["families"]:
                for matrix_key in ("counts", "mean", "variance"):
                    self.assertEqual(len(family[matrix_key]), 3)
                    self.assertTrue(all(len(row) == 8
                                        for row in family[matrix_key]))
                self.assertEqual(family["counts"][2], [0] * 8)
                self.assertEqual(family["mean"][2], [[0, 1]] * 8)
                self.assertEqual(family["variance"][2], [[0, 1]] * 8)

    def test_deleting_the_entire_population(self):
        packet = invented_packet()
        packet["animals"] = ["A"]
        packet["records"] = [record for record in packet["records"]
                             if record["animal"] == "A"]
        packet["units"] = [unit for unit in packet["units"]
                           if unit["animal"] == "A"]
        reconstruction = Reconstruction(packet, fixed_dimensions=False)
        for family in reconstruction.case(0)["families"]:
            self.assertEqual(family["counts"], [[0] * 8 for _ in range(3)])
            for matrix_key in ("mean", "variance"):
                self.assertEqual(family[matrix_key],
                                 [[[0, 1]] * 8 for _ in range(3)])

    def test_stdout_mode_has_only_complete_jsonl_and_no_output_file(self):
        captured = io.StringIO()
        with patch("solution.open", create=True,
                   side_effect=AssertionError("stdout mode opened a file")):
            with redirect_stdout(captured):
                with submission_output("-") as output:
                    write_jsonl(self.reconstruction, "0" * 64, output)
        self.assertFalse(captured.closed)
        text = captured.getvalue()
        self.assertTrue(text.endswith("\n"))
        lines = [json.loads(line) for line in text.splitlines()]
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], {
            "schema": OUTPUT_SCHEMA,
            "packet_sha256": "0" * 64,
            "cases": ["full", "without:A", "without:B", "without:C"],
        })
        self.assertEqual([line["case"] for line in lines[1:]],
                         lines[0]["cases"])

    def test_optional_file_mode_uses_exclusive_creation(self):
        opener = mock_open()
        with patch("solution.open", opener, create=True):
            with submission_output("fresh-output.jsonl") as output:
                output.write("invented\n")
        opener.assert_called_once_with("fresh-output.jsonl", "x",
                                       encoding="utf-8", newline="\n")
        opener().write.assert_called_once_with("invented\n")

    def test_optional_file_mode_refuses_existing_destination(self):
        with patch("solution.open", create=True, side_effect=FileExistsError):
            with self.assertRaises(FileExistsError):
                with submission_output("existing-output.jsonl"):
                    self.fail("Exclusive creation did not fail")

    def test_output_byte_limit_applies_before_a_line_is_written(self):
        captured = io.StringIO()
        with patch("solution.MAX_OUTPUT_BYTES", 1):
            with self.assertRaises(ValueError):
                write_jsonl(self.reconstruction, "0" * 64, captured)
        self.assertEqual(captured.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
