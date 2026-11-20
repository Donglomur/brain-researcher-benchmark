"""Generated numeric-identity regressions for the maintained Figure 5 diagnostic."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("fig5_numeric_alignment", HERE / "coefficient_alignment.py")
alignment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alignment)


def fixture():
    return {"group": "activated", "expected_cell_ids": ["a"],
            "fixed": {"intercept": 0, "basef": 0},
            "conditional": [{"cell_id": "a", "intercept": 1, "preceding": 2}],
            "random": [{"cell_id": "a", "intercept": 1, "preceding": 2}],
            "trial_covariates": [{"cell_id": "a", "basef": 2**53},
                                 {"cell_id": "a", "basef": 2**53}],
            "conditional_semantics": "fixed_plus_random"}


class NumericIdentityControls(unittest.TestCase):
    def test_unequal_integer_baselines_cannot_round_to_one_value(self):
        data = fixture()
        data["trial_covariates"][1]["basef"] = 2**53 + 1
        before = copy.deepcopy(data)
        with self.assertRaisesRegex(alignment.AlignmentError, "exactly as binary64"):
            alignment.diagnose_group(data)
        self.assertEqual(data, before)

    def test_lossy_coefficients_refuse_but_exact_numeric_inputs_keep_branches(self):
        for location in ("fixed", "conditional", "random"):
            data = fixture()
            row = data[location] if location == "fixed" else data[location][0]
            row["intercept"] = -(2**53 + 1)
            with self.subTest(location=location), self.assertRaisesRegex(
                    alignment.AlignmentError, "exactly as binary64"):
                alignment.diagnose_group(data)
        for value in (2**53, 2**54, 1.5):
            data = fixture()
            for row in data["trial_covariates"]:
                row["basef"] = value
            result = alignment.diagnose_group(data)
            self.assertEqual(result["rows"][0]["basef"], value)
            self.assertEqual(result["rows"][0]["conditional_model_intercept"], 1.)
            self.assertEqual(result["rows"][0]["literal_notebook_intercept"], 1.)
            self.assertFalse(result["scientific_qualification"])

    def test_exporter_loads_corrected_pinned_diagnostic(self):
        path = HERE.parent / "fig5-keyed-fit-export-v1" / "fit_export.py"
        spec = importlib.util.spec_from_file_location("fig5_numeric_exporter", path)
        exporter = importlib.util.module_from_spec(spec); spec.loader.exec_module(exporter)
        loaded = exporter.load_alignment(HERE / "coefficient_alignment.py")
        data = fixture(); data["trial_covariates"][1]["basef"] = 2**53 + 1
        with self.assertRaisesRegex(loaded.AlignmentError, "exactly as binary64"):
            loaded.diagnose_group(data)
        self.assertEqual(loaded.diagnose_group(fixture()), alignment.diagnose_group(fixture()))


if __name__ == "__main__":
    unittest.main()
