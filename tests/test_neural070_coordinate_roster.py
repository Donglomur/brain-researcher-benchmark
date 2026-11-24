"""Generated roster controls; no authentic input, conversion or model run."""
import argparse
import importlib.util
from pathlib import Path
import sys
import unittest

DEFAULT_PROGRAMME = (Path(__file__).resolve().parents[1]
                     / "benchmarks/neural/NEURAL-070/implementations/registered-runtime/programme")
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--programme-root", type=Path, default=DEFAULT_PROGRAMME)
parser.add_argument("--roster-source", type=Path)
OPTIONS, REMAINING = parser.parse_known_args()
sys.path.insert(0, str(OPTIONS.programme_root.resolve()))
from n070.protocol import PARTICIPANTS, ROIS

source = OPTIONS.roster_source or OPTIONS.programme_root / "n070/roster.py"
spec = importlib.util.spec_from_file_location("n070._coordinate_roster_regression", source)
roster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roster)


def full_roster():
    # Deliberate reuse across independent people/ROIs is valid. One measured
    # coordinate in each cell makes the complete denominator explicit.
    return [{"participant": person, "roi": roi, "coordinate": "coordinate-0",
             "source_index": 0, "space": "fsLR32k",
             "independent_mask_member": "generated-mask"}
            for person in PARTICIPANTS for roi in ROIS]


class CoordinateRosterTests(unittest.TestCase):
    def test_complete_cells_allow_overlap_across_rois_and_people(self):
        result = roster.validate_coordinates(full_roster())
        self.assertTrue(result["complete"])
        self.assertEqual(result["missing_cells"], [])

    def test_source_alias_in_one_cell_refuses(self):
        rows = full_roster()
        rows.append({**rows[0], "coordinate": "different-label-same-source"})
        with self.assertRaisesRegex(ValueError, "Unique source coordinate"):
            roster.validate_coordinates(rows)

    def test_distinct_source_columns_in_one_cell_remain_valid(self):
        rows = full_roster()
        rows.append({**rows[0], "coordinate": "coordinate-1", "source_index": 1})
        self.assertTrue(roster.validate_coordinates(rows)["complete"])

    def test_repeated_coordinate_label_still_refuses(self):
        rows = full_roster()
        rows.append({**rows[0], "source_index": 1})
        with self.assertRaisesRegex(ValueError, "Unique coordinate within ROI"):
            roster.validate_coordinates(rows)

    def test_missing_cell_remains_explicit(self):
        rows = full_roster()
        missing = rows.pop()
        result = roster.validate_coordinates(rows)
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_cells"], [(missing["participant"], missing["roi"])])

    def test_source_index_domain_is_preserved(self):
        for index in (-1, 91282, True, 0.0):
            rows = full_roster()
            rows[0]["source_index"] = index
            with self.subTest(index=index), self.assertRaises(ValueError):
                roster.validate_coordinates(rows)
        rows = full_roster()
        rows[0]["source_index"] = 91281
        self.assertTrue(roster.validate_coordinates(rows)["complete"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *REMAINING], verbosity=2)
