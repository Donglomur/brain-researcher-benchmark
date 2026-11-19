"""Data-free controls for the documented NPvC cell-selection transformation."""

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cell_support import SourceCellError, construct_cell_support


def fixture():
    # Explicit generated complete-size metadata; these are not original cells.
    table = []
    for row_index in range(4732):
        session = row_index % 64
        table.append([100 + session, 10 + session % 8, 500 + session // 8, 0, 0, 0, 0])
    table[0][3] = 1             # global cell1: ACC
    table[64][6] = 1            # global cell65: unlabelled
    table[2047][4] = 1          # global cell2048: cPPC
    table[4731][5] = 1          # global cell4732: RETRO
    return table, {"okunlabeled": [65], "ACC": [1], "RETRO": [4732], "PPC": [2048]}


class CellSupportControls(unittest.TestCase):
    def test_global_one_based_rows_and_projection_column_order(self):
        table, selectors = fixture()
        before = copy.deepcopy((table, selectors))
        result = construct_cell_support(table, selectors)
        self.assertEqual([r["source_global_cell_index"] for r in result["cells"]], [1, 65, 2048, 4732])
        first, second, third, last = result["cells"]
        self.assertEqual((first["source_session_number"], first["source_animal_number"], first["source_animal_session_number"]), (100, 10, 500))
        self.assertEqual(second["source_session_number"], 100)
        self.assertEqual(third["projection_flags"], {"ACC": 0, "cPPC": 1, "RETRO": 0, "unlabeled": 0})
        self.assertEqual(last["projection_flags"], {"ACC": 0, "cPPC": 0, "RETRO": 1, "unlabeled": 0})
        self.assertEqual(last["quality_selector_memberships"], ["RETRO"])
        self.assertEqual(result["source_cell_rows"], 4732)
        self.assertEqual(result["source_session_count"], 64)
        self.assertEqual(result["selected_unique_cell_count"], 4)
        self.assertEqual(len(result["not_selected_global_cell_indices"]), 4728)
        self.assertEqual(set(result["not_selected_global_cell_indices"]) | {1, 65, 2048, 4732}, set(range(1, 4733)))
        self.assertEqual((table, selectors), before)
        self.assertFalse(result["scope"]["original_study_eligibility_established"])
        self.assertFalse(result["scope"]["archive_or_trace_row_mapping_established"])

    def test_overlap_preserved_once_without_projection_priority(self):
        table, selectors = fixture()
        table[0][4] = 1
        selectors["PPC"] = [2048, 1]
        result = construct_cell_support(table, selectors)
        self.assertEqual(result["selected_unique_cell_count"], 4)
        self.assertEqual(result["selection_counts"], {"okunlabeled": 1, "ACC": 1, "RETRO": 1, "PPC": 2})
        self.assertEqual(result["cells"][0]["quality_selector_memberships"], ["ACC", "PPC"])
        self.assertEqual(result["cells"][0]["projection_flags"]["ACC"], 1)
        self.assertEqual(result["cells"][0]["projection_flags"]["cPPC"], 1)
        self.assertEqual(result["multiple_selector_cell_indices"], [1])
        self.assertEqual(result["multiple_projection_flag_cell_indices"], [1])

    def test_selector_order_does_not_change_cell_identity(self):
        table, selectors = fixture()
        table[64][3] = 1
        selectors["ACC"] = [65, 1]
        left = construct_cell_support(table, selectors)
        selectors["ACC"] = [1, 65]
        right = construct_cell_support(table, selectors)
        self.assertEqual(left, right)
        self.assertEqual(left["cells"][1]["quality_selector_memberships"], ["okunlabeled", "ACC"])

    def test_matlab_integral_doubles_preserve_global_identifiers(self):
        table, selectors = fixture()
        floating = [[float(v) for v in row] for row in table]
        floating_selectors = {k: [float(v) for v in row] for k, row in selectors.items()}
        self.assertEqual(construct_cell_support(table, selectors), construct_cell_support(floating, floating_selectors))

    def test_index_refusals_do_not_silently_drop_or_round(self):
        for invalid in [0, 4733, True, 1.5, float("nan"), float("inf"), "1"]:
            with self.subTest(index=invalid):
                table, selectors = fixture()
                selectors["ACC"] = [invalid]
                with self.assertRaises(SourceCellError):
                    construct_cell_support(table, selectors)
        table, selectors = fixture()
        selectors["ACC"] = [1, 1]
        with self.assertRaisesRegex(SourceCellError, "repeats"):
            construct_cell_support(table, selectors)

    def test_selector_flag_contradiction_refuses_without_relabeling(self):
        table, selectors = fixture()
        selectors["PPC"] = [4732]
        with self.assertRaisesRegex(SourceCellError, "contradicts"):
            construct_cell_support(table, selectors)

    def test_complete_table_and_source_session_consistency(self):
        table, selectors = fixture()
        with self.assertRaises(SourceCellError):
            construct_cell_support(table[:-1], selectors)
        bad = copy.deepcopy(table)
        bad[1].append(0)
        with self.assertRaises(SourceCellError):
            construct_cell_support(bad, selectors)
        bad = copy.deepcopy(table)
        bad[64][1] = 999
        with self.assertRaisesRegex(SourceCellError, "conflicting"):
            construct_cell_support(bad, selectors)
        bad = copy.deepcopy(table)
        for row in bad:
            if row[0] == 163:
                row[:3] = [100, 10, 500]
        with self.assertRaisesRegex(SourceCellError, "64 source sessions"):
            construct_cell_support(bad, selectors)

    def test_required_selectors_and_no_empty_success(self):
        table, selectors = fixture()
        selectors.pop("RETRO")
        with self.assertRaises(SourceCellError):
            construct_cell_support(table, selectors)
        with self.assertRaisesRegex(SourceCellError, "select no"):
            construct_cell_support(table, {k: [] for k in ["okunlabeled", "ACC", "RETRO", "PPC"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
