"""Generated structural controls; no recordings, model fitting or paper score."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("audit", Path(__file__).with_name("coactivity_row_audit.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(identity, animal, state, session="early", distance=2, area=1):
    return dict(row_id=identity, animal_id=animal, stability=state,
                session=session, distance_um=distance, area_um2=area)


class RowAuditTests(unittest.TestCase):
    def test_two_animals_are_positionally_misassigned(self):
        # Native order A(stable),B(elim); response concatenation B,A;
        # source animal tags remain A,B. Both random-effect groups are wrong.
        result = module.audit([row("A-pair", "A", "stable"), row("B-pair", "B", "eliminated")])
        for model in ("size_models_lines_260_264", "session_model_lines_382_384"):
            self.assertEqual(result[model]["response_row_ids"], ["B-pair", "A-pair"])
            self.assertEqual(result[model]["animal_tag_row_ids"], ["A-pair", "B-pair"])
            self.assertEqual(len(result[model]["paired_animal_mismatches"]), 2)

    def test_size_and_session_permutations_are_distinct(self):
        rows = [row("large-early", "A", "eliminated", area=2),
                row("small-middle", "B", "eliminated", session="middle", area=1)]
        result = module.audit(rows)
        self.assertEqual(result["size_models_lines_260_264"]["response_row_ids"], ["small-middle", "large-early"])
        self.assertEqual(result["session_model_lines_382_384"]["response_row_ids"], ["large-early", "small-middle"])
        self.assertTrue(result["session_model_lines_382_384"]["animal_alignment_holds_for_supplied_rows"])

    def test_missing_area_breaks_size_table_length_but_not_session_table(self):
        result = module.audit([row("missing", "A", "stable", area=None)])
        self.assertTrue(result["size_models_lines_260_264"]["table_length_mismatch"])
        self.assertEqual(result["size_models_lines_260_264"]["response_rows"], 0)
        self.assertTrue(result["session_model_lines_382_384"]["animal_alignment_holds_for_supplied_rows"])

    def test_original_bin_extent_and_exact_cutoff(self):
        rows = [row("boundary", "A", "stable", distance=50, area=1.0960),
                row("last", "A", "stable", distance=54.99),
                row("excluded", "A", "stable", distance=55),
                row("missing", "A", "stable", distance=None)]
        result = module.audit(rows)
        self.assertEqual(result["distance_excluded_row_ids"], ["excluded", "missing"])
        self.assertEqual(result["size_models_lines_260_264"]["response_row_ids"], ["boundary", "last"])

    def test_permutation_with_same_animal_is_not_reported_as_group_error(self):
        rows = [row("stable", "A", "stable"), row("elim", "A", "eliminated")]
        before = copy.deepcopy(rows)
        result = module.audit(rows)
        self.assertTrue(result["size_models_lines_260_264"]["animal_alignment_holds_for_supplied_rows"])
        self.assertEqual(rows, before)

    def test_duplicate_identity_and_invalid_metadata_fail(self):
        good = row("x", "A", "stable")
        for rows in ([good, good], [{**good, "area_um2": float("nan")}],
                     [{**good, "distance_um": True}], [{**good, "session": "late"}]):
            with self.assertRaises(ValueError):
                module.audit(rows)


if __name__ == "__main__":
    unittest.main()
