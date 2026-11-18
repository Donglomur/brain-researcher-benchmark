"""Changed native-dataframe boundary controls; every value here is generated."""
import argparse
from fractions import Fraction
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import platform
import sys
import tempfile
from types import SimpleNamespace
import unittest

import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("fig5_fit_export", HERE / "fit_export.py")
exporter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exporter)
ALIGNMENT = None
SCRATCH = None


class InertFit(SimpleNamespace):
    def fit(self, *args, **kwargs):
        raise AssertionError("native fitting must never be invoked by the connector")


def group_fixture(population=10):
    frame = pd.DataFrame({"cell": [20, 10, 20, 10], "basef": [5., 5., 5., 5.],
                          "preceding": [1., 2., 3., 4.], "opto": [9., 8., 7., 6.]},
                         index=["repeat", "repeat", 7, 7])
    fit = InertFit(
        data=frame.copy(deep=True), formula=exporter.SOURCE_FORMULA,
        coefs=pd.DataFrame({"Estimate": [population, 2.], "T-stat": [float("nan"), 4.],
                            "Sig": ["", "*"]}, index=["(Intercept)", "basef"]),
        fixef=pd.DataFrame({"(Intercept)": [population + 2., population + 1.],
                            "basef": [2., 2.], "preceding": [4., 3.]}, index=["R_B", "R_A"]),
        ranef=pd.DataFrame({"preceding": [3., 4.], "(Intercept)": [1., 2.]}, index=["R_A", "R_B"]))
    return fit, frame, [10, 20], [{"factor_level": "R_B", "cell_id": 20},
                                 {"factor_level": "R_A", "cell_id": 10}]


def fixture():
    result = {name: {} for name in ("models", "source_frames", "expected_cell_ids", "factor_bindings")}
    for group, population in (("activated", 10), ("suppressed", -5)):
        for name, value in zip(result, group_fixture(population)):
            result[name][group] = value
    result.update(conditional_semantics="fixed_plus_random",
                  runtime_record={"python": platform.python_version(), "pymer4": None, "lme4": None},
                  limits={"max_rows": 32, "max_cells": 8, "max_columns": 16, "max_output_bytes": 100000},
                  alignment_source=ALIGNMENT)
    return result


class NativeBoundaryControls(unittest.TestCase):
    def run_export(self, data=None):
        return exporter.export_panel(**(fixture() if data is None else data))

    def test_real_dataframe_bridge_preserves_both_groups_and_both_branches(self):
        result = self.run_export()
        self.assertEqual(set(result["exports"]), {"activated", "suppressed"})
        self.assertEqual(result["diagnostic"]["activated"]["rows"][0]["literal_notebook_intercept"], 31.)
        self.assertEqual(result["diagnostic"]["activated"]["rows"][0]["conditional_model_intercept"], 21.)
        self.assertEqual(result["diagnostic"]["suppressed"]["rows"][0]["literal_minus_conditional"], -5.)
        self.assertFalse(result["scientific_qualification"])
        self.assertIsNone(result["reproduction_accepted"])
        self.assertIsNone(result["improvement_accepted"])

    def test_complete_rows_duplicate_indices_and_equal_baselines_survive(self):
        result = self.run_export()
        source = result["lineage"]["activated"]["source_frame_projection"]
        self.assertEqual([r["position"] for r in source["rows"]], [0, 1, 2, 3])
        self.assertEqual([r["index_label"] for r in source["rows"]], ["repeat", "repeat", 7, 7])
        self.assertEqual([r["cell_id"] for r in source["rows"]], [20, 10, 20, 10])
        self.assertEqual(len(result["exports"]["activated"]["trial_covariates"]), 4)
        diagnostic = result["diagnostic"]["activated"]
        self.assertEqual([r["trial_rows"] for r in diagnostic["rows"]], [2, 2])
        self.assertEqual([r["basef"] for r in diagnostic["rows"]], [5., 5.])
        self.assertFalse(diagnostic["legacy_pd_unique_diagnostic"]["vector_length_matches"])

    def test_native_coefficient_row_and_column_order_join_by_explicit_factor(self):
        before = self.run_export()
        data = fixture()
        model = data["models"]["activated"]
        model.fixef = model.fixef.iloc[::-1, ::-1]
        model.ranef = model.ranef.iloc[::-1, ::-1]
        result = self.run_export(data)
        self.assertEqual(result["diagnostic"], before["diagnostic"])
        raw = result["lineage"]["activated"]["raw_coefficients"]
        self.assertEqual(raw["fixef"]["index"], ["R_A", "R_B"])
        self.assertEqual(raw["fixef"]["columns"], ["preceding", "basef", "(Intercept)"])
        self.assertEqual(raw["ranef"]["columns"], ["(Intercept)", "preceding"])

    def test_raw_tables_keep_ancillary_nonfinite_cells_without_altering_estimates(self):
        result = self.run_export()
        raw = result["lineage"]["activated"]["raw_coefficients"]
        self.assertEqual(raw["coefs"]["values"][0], [10., {"nonfinite": "nan"}, ""])
        self.assertEqual(raw["coefs"]["index"], ["(Intercept)", "basef"])
        self.assertEqual(result["exports"]["activated"]["fixed"], {"intercept": 10., "basef": 2.})
        self.assertEqual(raw["fixef"]["values"][0][0], 12.)
        self.assertEqual(raw["ranef"]["values"][0][1], 1.)
        json.dumps(result, allow_nan=False)
        for value, state in ((float("inf"), "+inf"), (float("-inf"), "-inf")):
            data = fixture(); data["models"]["activated"].coefs.iloc[0, 1] = value
            result = self.run_export(data)
            self.assertEqual(result["lineage"]["activated"]["raw_coefficients"]["coefs"]["values"][0][1],
                             {"nonfinite": state})

    def test_wider_real_conversion_refuses_rounding_overflow_and_underflow(self):
        for value in (Fraction(1, 3), Fraction(1, 10**4000), Fraction(10**4000)):
            for location in ("modeled", "estimate", "ancillary"):
                data = fixture()
                if location == "modeled":
                    frame = data["source_frames"]["activated"]
                    frame["preceding"] = frame["preceding"].astype(object)
                    frame.iloc[0, frame.columns.get_loc("preceding")] = value
                    data["models"]["activated"].data = frame.copy(deep=True)
                else:
                    frame = data["models"]["activated"].coefs
                    column = "Estimate" if location == "estimate" else "T-stat"
                    frame[column] = frame[column].astype(object)
                    frame.iloc[0, frame.columns.get_loc(column)] = value
                with self.subTest(location=location), self.assertRaisesRegex(exporter.ExportError, "binary64"):
                    self.run_export(data)
        data = fixture(); frame = data["models"]["activated"].coefs
        frame["T-stat"] = frame["T-stat"].astype(object)
        frame.iloc[0, 1] = Fraction(1, 2)
        result = self.run_export(data)
        self.assertEqual(result["lineage"]["activated"]["raw_coefficients"]["coefs"]["values"][0][1], .5)

    def test_integer_and_string_cell_ids_and_factor_levels_are_not_conflated(self):
        data = fixture()
        for group in exporter.GROUPS:
            frame = data["source_frames"][group]
            frame["cell"] = pd.Series([1, "1", 1, "1"], index=frame.index, dtype=object)
            data["models"][group].data = frame.copy(deep=True)
            data["models"][group].fixef.index = pd.Index([1, "1"], dtype=object)
            data["models"][group].ranef.index = pd.Index(["1", 1], dtype=object)
            data["expected_cell_ids"][group] = ["1", 1]
            data["factor_bindings"][group] = [{"factor_level": "1", "cell_id": "1"},
                                             {"factor_level": 1, "cell_id": 1}]
        result = self.run_export(data)
        self.assertEqual(result["exports"]["activated"]["expected_cell_ids"], ["1", 1])
        self.assertEqual([r["cell_id"] for r in result["diagnostic"]["activated"]["rows"]], ["1", 1])
        self.assertEqual(result["lineage"]["activated"]["raw_coefficients"]["fixef"]["index"], [1, "1"])
        self.assertEqual(result["lineage"]["activated"]["raw_coefficients"]["ranef"]["index"], ["1", 1])

    def test_factor_mapping_duplicate_missing_extra_and_wrong_type_refused(self):
        changes = [
            [{"factor_level": "R_A", "cell_id": 10}],
            [{"factor_level": "R_A", "cell_id": 10}, {"factor_level": "R_A", "cell_id": 20}],
            [{"factor_level": "R_A", "cell_id": 10}, {"factor_level": "R_B", "cell_id": 10}],
            [{"factor_level": "R_A", "cell_id": 10}, {"factor_level": "R_C", "cell_id": 20}],
            [{"factor_level": "R_A", "cell_id": 10}, {"factor_level": "R_B", "cell_id": "20"}],
        ]
        for bindings in changes:
            with self.subTest(bindings=bindings):
                data = fixture(); data["factor_bindings"]["activated"] = bindings
                with self.assertRaises(exporter.ExportError): self.run_export(data)

    def test_panel_and_supplied_roster_are_complete(self):
        for name in ("models", "source_frames", "expected_cell_ids", "factor_bindings"):
            data = fixture(); del data[name]["suppressed"]
            with self.subTest(name=name), self.assertRaises(exporter.ExportError): self.run_export(data)
        data = fixture(); data["expected_cell_ids"]["activated"] = [10]
        with self.assertRaises(exporter.ExportError): self.run_export(data)
        data = fixture(); data["expected_cell_ids"]["activated"] = [10, 10]
        with self.assertRaises(exporter.ExportError): self.run_export(data)

    def test_model_data_row_order_index_and_value_mismatches_refused(self):
        for change in ("order", "index", "response"):
            data = fixture(); model = data["models"]["activated"]
            if change == "order": model.data = model.data.iloc[::-1]
            elif change == "index": model.data.index = [0, 1, 2, 3]
            else: model.data.iloc[0, model.data.columns.get_loc("opto")] = 99.
            with self.subTest(change=change), self.assertRaises(exporter.ExportError): self.run_export(data)

    def test_nonfinite_modeled_rows_are_never_dropped(self):
        for column in ("basef", "preceding", "opto"):
            for missing in (float("nan"), float("inf")):
                data = fixture(); frame = data["source_frames"]["activated"]
                frame.iloc[0, frame.columns.get_loc(column)] = missing
                data["models"]["activated"].data = frame.copy(deep=True)
                with self.subTest(column=column, missing=missing), self.assertRaises(exporter.ExportError):
                    self.run_export(data)

    def test_nonfinite_selected_coefficients_and_unsupported_raw_cells_refused(self):
        for table, row, column, value in (("coefs", 0, "Estimate", float("inf")),
                                         ("fixef", 0, "preceding", float("nan")),
                                         ("ranef", 0, "(Intercept)", float("nan")),
                                         ("coefs", 0, "Sig", object())):
            data = fixture(); frame = getattr(data["models"]["activated"], table)
            if column == "Sig": frame[column] = frame[column].astype(object)
            frame.iloc[row, frame.columns.get_loc(column)] = value
            with self.subTest(table=table, column=column), self.assertRaises(exporter.ExportError): self.run_export(data)

    def test_native_coefficient_identity_and_fixed_notebook_order_refusals(self):
        for change in ("fixed_order", "missing_estimate", "duplicate_factor", "missing_factor", "extra_random_term"):
            data = fixture(); model = data["models"]["activated"]
            if change == "fixed_order": model.coefs = model.coefs.iloc[::-1]
            elif change == "missing_estimate": model.coefs = model.coefs.rename(columns={"Estimate": "estimate"})
            elif change == "duplicate_factor": model.fixef.index = ["R_A", "R_A"]
            elif change == "missing_factor": model.ranef = model.ranef.iloc[:1]
            else: model.ranef["unexpected"] = 0.
            with self.subTest(change=change), self.assertRaises(exporter.ExportError): self.run_export(data)

    def test_random_deviations_are_required_not_derived(self):
        for value in (None, [], {"cell": pd.DataFrame()}):
            data = fixture(); data["models"]["activated"].ranef = value
            with self.subTest(value=type(value).__name__), self.assertRaises(exporter.ExportError): self.run_export(data)
        data = fixture(); data["models"]["activated"].ranef.iloc[0, 1] = 123.
        result = self.run_export(data)
        self.assertEqual(result["exports"]["activated"]["random"][0]["intercept"], 123.)
        self.assertEqual(result["diagnostic"]["activated"]["rows"][0]["conditional_random_identity_residual"], -122.)

    def test_formula_identity_checked_when_exposed_otherwise_explicitly_unknown(self):
        data = fixture(); del data["models"]["activated"].formula
        result = self.run_export(data)
        self.assertIsNone(result["lineage"]["activated"]["formula"]["matches_exposed_string"])
        self.assertFalse(result["lineage"]["activated"]["actual_R_model_frame_verified"])
        data = fixture(); data["models"]["activated"].formula = "opto ~ 1 + preceding + (1|cell)"
        with self.assertRaises(exporter.ExportError): self.run_export(data)

    def test_semantics_and_versions_remain_explicit_and_unverified(self):
        data = fixture(); data["conditional_semantics"] = "random_deviation"
        with self.assertRaises(exporter.ExportError): self.run_export(data)
        result = self.run_export()
        self.assertIsNone(result["runtime_record"]["pymer4"])
        self.assertIsNone(result["runtime_record"]["lme4"])
        self.assertFalse(result["historical_runtime_verified"])

    def test_complete_capacity_refusal_never_returns_partial_panel(self):
        for field, value in (("max_rows", 3), ("max_cells", 1), ("max_columns", 2), ("max_output_bytes", 100)):
            data = fixture(); data["limits"][field] = value
            with self.subTest(field=field), self.assertRaises(exporter.ExportError): self.run_export(data)

    def test_existing_diagnostic_retains_within_cell_baseline_refusal(self):
        data = fixture(); frame = data["source_frames"]["activated"]
        frame.iloc[0, frame.columns.get_loc("basef")] = 8.
        data["models"]["activated"].data = frame.copy(deep=True)
        with self.assertRaisesRegex(ValueError, "not constant within a cell"): self.run_export(data)

    def test_alignment_dependency_identity_is_enforced(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            path = Path(directory) / "invalid.py"
            path.write_bytes(b"not-source")
            data = fixture(); data["alignment_source"] = path
            with self.assertRaisesRegex(exporter.ExportError, "source pin mismatch"): self.run_export(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment-source", type=Path)
    parser.add_argument("--scratch-root", type=Path)
    options = parser.parse_args()
    ALIGNMENT, SCRATCH = options.alignment_source, options.scratch_root
    result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeBoundaryControls))
    # Bounded combined output, including failure summaries; no unbounded trace log.
    failures = [{"test": test.id(), "detail": detail[-240:]} for test, detail in (result.failures + result.errors)[:10]]
    print(json.dumps({"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "skips": len(result.skipped), "details": failures, "python": platform.python_version(),
                      "pandas": importlib.metadata.version("pandas"), "numpy": importlib.metadata.version("numpy"),
                      "pymer4_or_rpy2_imported": any(n == "pymer4" or n.startswith("rpy2") for n in sys.modules)}))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
