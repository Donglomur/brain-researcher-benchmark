"""Generated algebra/identity controls; no deposited observations or model fits."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "coefficient_alignment", Path(__file__).with_name("coefficient_alignment.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def example(group="activated"):
    return {
        "group": group,
        "expected_cell_ids": ["b", "a"],
        "conditional_semantics": "fixed_plus_random",
        "fixed": {"intercept": 10, "basef": 2},
        "conditional": [
            {"cell_id": "a", "intercept": 9, "preceding": 0.5},
            {"cell_id": "b", "intercept": 11, "preceding": -0.25},
        ],
        "random": [
            {"cell_id": "b", "intercept": 1, "preceding": -0.25},
            {"cell_id": "a", "intercept": -1, "preceding": 0.5},
        ],
        "trial_covariates": [
            {"cell_id": "a", "basef": 7},
            {"cell_id": "b", "basef": 5},
            {"cell_id": "b", "basef": 5},
        ],
    }


class CoefficientAlignmentControls(unittest.TestCase):
    def test_declared_branches_remain_distinct(self):
        result = module.diagnose_group(example())
        self.assertEqual([r["conditional_model_intercept"] for r in result["rows"]], [21, 23])
        self.assertEqual([r["literal_notebook_intercept"] for r in result["rows"]], [31, 33])
        self.assertEqual([r["literal_minus_conditional"] for r in result["rows"]], [10, 10])
        self.assertFalse(result["scientific_qualification"])
        self.assertIsNone(result["reproduction_accepted"])
        self.assertIsNone(result["improvement_accepted"])

    def test_constant_offset_preserves_pairwise_intercept_difference(self):
        rows = module.diagnose_group(example())["rows"]
        literal = rows[0]["literal_notebook_intercept"] - rows[1]["literal_notebook_intercept"]
        conditional = rows[0]["conditional_model_intercept"] - rows[1]["conditional_model_intercept"]
        self.assertEqual(literal, conditional)

    def test_alignment_follows_ids_not_export_row_order(self):
        original = example()
        reordered = copy.deepcopy(original)
        reordered["conditional"].reverse()
        reordered["random"].reverse()
        reordered["trial_covariates"].reverse()
        self.assertEqual(module.diagnose_group(original)["rows"],
                         module.diagnose_group(reordered)["rows"])
        self.assertFalse(module.diagnose_group(original)["legacy_pd_unique_diagnostic"][
            "vector_matches_supplied_cell_order"])

    def test_equal_baseline_across_distinct_cells_is_valid(self):
        export = example()
        for row in export["trial_covariates"]:
            row["basef"] = 5
        result = module.diagnose_group(export)
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["legacy_pd_unique_diagnostic"]["unique_baseline_count"], 1)
        self.assertFalse(result["legacy_pd_unique_diagnostic"]["vector_length_matches"])
        self.assertEqual([r["conditional_model_intercept"] for r in result["rows"]], [21, 19])

    def test_conflicting_within_cell_baseline_fails(self):
        export = example()
        export["trial_covariates"][-1]["basef"] = 6
        with self.assertRaises(module.AlignmentError):
            module.diagnose_group(export)

    def test_duplicate_or_missing_coefficients_fail(self):
        for name in ("conditional", "random"):
            with self.subTest(table=name, fault="duplicate"):
                export = example()
                export[name].append(dict(export[name][0]))
                with self.assertRaises(module.AlignmentError):
                    module.diagnose_group(export)
            with self.subTest(table=name, fault="missing"):
                export = example()
                export[name].pop()
                with self.assertRaises(module.AlignmentError):
                    module.diagnose_group(export)

    def test_missing_or_extra_covariate_cell_fails(self):
        for fault in ("missing", "extra"):
            export = example()
            if fault == "missing":
                export["trial_covariates"] = export["trial_covariates"][1:]
            else:
                export["trial_covariates"].append({"cell_id": "other", "basef": 5})
            with self.subTest(fault=fault), self.assertRaises(module.AlignmentError):
                module.diagnose_group(export)

    def test_integer_and_text_ids_are_not_coerced(self):
        export = example()
        export["expected_cell_ids"][0] = 1
        for name in ("conditional", "random"):
            for row in export[name]:
                if row["cell_id"] == "b":
                    row["cell_id"] = 1
        for row in export["trial_covariates"]:
            if row["cell_id"] == "b":
                row["cell_id"] = "1"
        with self.assertRaises(module.AlignmentError):
            module.diagnose_group(export)

    def test_nonfinite_bool_and_overflow_rejected(self):
        for value in (float("nan"), float("inf"), True, 10**400):
            export = example()
            export["fixed"]["intercept"] = value
            with self.subTest(type=type(value).__name__), self.assertRaises(module.AlignmentError):
                module.diagnose_group(export)
        export = example()
        export["fixed"]["basef"] = 1e308
        with self.assertRaises(module.AlignmentError):
            module.diagnose_group(export)

    def test_semantics_are_required_not_inferred(self):
        for semantics in (None, "random_only", "pymer4"):
            export = example()
            export["conditional_semantics"] = semantics
            with self.subTest(semantics=semantics), self.assertRaises(module.AlignmentError):
                module.diagnose_group(export)

    def test_identity_residual_reported_without_acceptance_tolerance(self):
        export = example()
        export["random"][0]["intercept"] = 2
        result = module.diagnose_group(export)
        self.assertEqual(result["rows"][0]["conditional_random_identity_residual"], -1)
        self.assertIsNone(result["reproduction_accepted"])

    def test_panel_requires_both_names_and_declared_groups(self):
        with self.assertRaises(module.AlignmentError):
            module.diagnose_panel({"activated": example()})
        with self.assertRaises(module.AlignmentError):
            module.diagnose_panel({"activated": example(), "suppressed": example()})
        result = module.diagnose_panel({"activated": example(), "suppressed": example("suppressed")})
        self.assertEqual(set(result), {"activated", "suppressed"})

    def test_no_input_mutation(self):
        export = example()
        original = copy.deepcopy(export)
        module.diagnose_group(export)
        self.assertEqual(export, original)

    def test_unknown_fields_rejected(self):
        export = example()
        export["fixed"]["preceding"] = 123
        with self.assertRaises(module.AlignmentError):
            module.diagnose_group(export)


if __name__ == "__main__":
    unittest.main(verbosity=1)
