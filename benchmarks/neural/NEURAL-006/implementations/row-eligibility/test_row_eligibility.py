"""Invented controls only; no original CSV, RDS, R, model or Docker access."""
import copy
import json
from pathlib import Path
import runpy
import unittest

API = runpy.run_path(str(Path(__file__).with_name("row_eligibility.py")), run_name="_eligibility")
audit = API["audit"]


def fixture():
    # Two people, three trials each. The source filter drops row2, and distinct
    # original variables omit rows3/5/6 in different model families.
    subjects = ["invented-A"] * 3 + ["invented-B"] * 3
    after_filter = [1, 3, 4, 5, 6]
    missing_by_variable = {"FRN_N2_offer_s": [3], "P3a_offer_s": [5],
                           "P3b_base_offer_s": [6], "abs_epe_valence_s": [2]}
    models = []
    for name, variables in API["MODELS"]:
        missing = {v: missing_by_variable.get(v, [])[:] for v in variables}
        omitted_sources = set().union(*(set(v) for v in missing.values()))
        positions = [i for i, src in enumerate(after_filter, 1) if src not in omitted_sources]
        original = [after_filter[i - 1] for i in positions]
        omitted = [i for i in range(1, 6) if i not in positions]
        models.append(dict(name=name, variables=list(variables), missing_rows_by_variable=missing,
                           nonfinite_rows_by_variable={v: [] for v in variables},
                           native_frame_rows=positions[:], native_omitted_rows=omitted,
                           native_na_action_class=["omit"] if omitted else [],
                           saved_frame_rows=positions[:], saved_source_rows=original,
                           saved_nobs=len(original), saved_group_count=len({subjects[i-1] for i in original}),
                           saved_formula_matches=True))
    return dict(schema=API["SCHEMA"], source=dict(
        files=[dict(name=name, rows=6, columns=["invented_column"], parse_problems=0) for name in API["FILES"]],
        subjects=subjects, trial_global=[1, 2, 3, 1, 2, 3], author_filter_missing_rows=[2],
        saved_original_rows=list(range(1, 7)), saved_subjects=subjects[:],
        saved_ordered_people=["invented-A", "invented-B"], saved_author_filter_source_rows=after_filter),
        runtime=dict(na_action="na.omit", R="invented-R", platform="invented-platform",
                     package_versions={p: "invented" for p in ["readr", "dplyr", "lme4", "jsonlite"]}), models=models)


def checked(wire):
    return audit(wire, expected_people=2, trials_per_person=3)


class EligibilityControls(unittest.TestCase):
    def test_complete_nontrivial_alignment(self):
        private, safe = checked(fixture())
        self.assertEqual(safe["status"], "consistent")
        self.assertEqual(safe["models_matching"], 11)
        self.assertEqual(private["models"][0]["expected_original_source_rows"], [1, 4, 5, 6])
        self.assertEqual(private["models"][4]["expected_original_source_rows"], [1, 3, 4, 6])
        self.assertEqual(private["models"][8]["expected_original_source_rows"], [1, 3, 4, 5])

    def test_original_coordinate_off_by_one_retained(self):
        wire = fixture(); wire["models"][0]["saved_source_rows"] = [1, 3, 4, 5]
        private, safe = checked(wire)
        self.assertEqual(safe["status"], "inconsistent_or_held")
        self.assertFalse(private["models"][0]["checks"]["saved_source_composition_matches"])
        self.assertEqual(safe["models_checked"], 11)

    def test_same_count_different_subset_does_not_pass(self):
        wire = fixture(); wire["models"][0]["saved_frame_rows"] = [1, 2, 3, 4]
        self.assertEqual(checked(wire)[1]["models_matching"], 10)

    def test_native_mask_disagreement(self):
        wire = fixture(); wire["models"][0]["native_frame_rows"] = [1, 2, 3, 4]
        self.assertFalse(checked(wire)[0]["models"][0]["checks"]["native_frame_matches_independent_mask"])

    def test_native_omissions_disagreement(self):
        wire = fixture(); wire["models"][0]["native_omitted_rows"] = [3]
        self.assertEqual(checked(wire)[1]["models_matching"], 10)

    def test_saved_filter_disagreement_not_silently_adopted(self):
        wire = fixture(); wire["source"]["saved_author_filter_source_rows"] = [1, 2, 4, 5, 6]
        private, safe = checked(wire)
        self.assertFalse(safe["source_support_matches"])
        self.assertEqual(private["models"][0]["expected_original_source_rows"], [1, 4, 5, 6])

    def test_subject_swap_detected_without_reordering(self):
        wire = fixture(); wire["source"]["saved_subjects"][0] = "invented-B"
        self.assertFalse(checked(wire)[1]["source_support_matches"])

    def test_trial_duplicate_refused(self):
        wire = fixture(); wire["source"]["trial_global"][1] = 1
        with self.assertRaises(ValueError): checked(wire)

    def test_missing_model_and_missing_variable_refused(self):
        wire = fixture(); wire["models"].pop()
        with self.assertRaises(ValueError): checked(wire)
        wire = fixture(); del wire["models"][0]["missing_rows_by_variable"]["sub"]
        with self.assertRaises(ValueError): checked(wire)

    def test_reordered_files_and_models_refused(self):
        wire = fixture(); wire["source"]["files"][0:2] = reversed(wire["source"]["files"][0:2])
        with self.assertRaises(ValueError): checked(wire)
        wire = fixture(); wire["models"][0:2] = reversed(wire["models"][0:2])
        with self.assertRaises(ValueError): checked(wire)

    def test_boolean_or_duplicate_row_refused(self):
        wire = fixture(); wire["models"][0]["saved_nobs"] = True
        with self.assertRaises(ValueError): checked(wire)
        wire = fixture(); wire["models"][0]["saved_frame_rows"] = [1, 1, 3, 4]
        with self.assertRaises(ValueError): checked(wire)

    def test_changed_na_action_refused(self):
        wire = fixture(); wire["runtime"]["na_action"] = "na.exclude"
        with self.assertRaises(ValueError): checked(wire)

    def test_formula_and_group_mismatch_retained(self):
        wire = fixture(); wire["models"][0]["saved_formula_matches"] = False
        wire["models"][1]["saved_group_count"] = 1
        self.assertEqual(checked(wire)[1]["models_matching"], 9)

    def test_parse_problems_and_infinite_values_held(self):
        wire = fixture(); wire["source"]["files"][0]["parse_problems"] = 1
        self.assertEqual(checked(wire)[1]["status"], "inconsistent_or_held")
        wire = fixture(); wire["models"][0]["nonfinite_rows_by_variable"]["abs_rpe_s"] = [1]
        private, safe = checked(wire)
        self.assertEqual(safe["status"], "inconsistent_or_held")
        self.assertEqual(private["models"][0]["nonfinite_modeled_source_rows"], [1])

    def test_no_missingness_is_not_a_required_omission(self):
        wire = fixture(); model = wire["models"][0]
        model["missing_rows_by_variable"] = {v: [] for v in model["variables"]}
        model.update(native_frame_rows=[1,2,3,4,5], native_omitted_rows=[], native_na_action_class=[],
                     saved_frame_rows=[1,2,3,4,5], saved_source_rows=[1,3,4,5,6], saved_nobs=5)
        self.assertEqual(checked(wire)[1]["models_matching"], 11)

    def test_strict_json_and_no_private_safe_fields(self):
        for body in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises(ValueError): API["strict_json"](body)
        wire = fixture(); before = copy.deepcopy(wire); _, safe = checked(wire)
        self.assertEqual(wire, before)
        text = json.dumps(safe)
        self.assertNotIn("invented-A", text)
        self.assertNotIn("saved_source_rows", text)
        self.assertFalse(safe["publication_parity"])
        self.assertFalse(safe["scientifically_qualified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
