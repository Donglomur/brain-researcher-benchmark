"""Generated-only controls for the source Figure 5 descriptive boundary."""
import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fig5_group_summary", HERE / "group_summary.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)
ALIGNMENT = None
SCRATCH = None


def fixture():
    groups = {}
    for group, population, baseline in (("activated", 10., 5.), ("suppressed", -4., 2.)):
        roster = ["c3", 1, "1"]
        random = [{"cell_id": cell, "intercept": float(2 * i + 2), "preceding": float(2 * i + 1)}
                  for i, cell in enumerate(roster)]
        conditional = [{"cell_id": row["cell_id"], "intercept": population + row["intercept"],
                        "preceding": row["preceding"]} for row in random]
        # Deliberately uneven trial counts; every cell has equal descriptive weight.
        groups[group] = {"group": group, "expected_cell_ids": roster,
                         "fixed": {"intercept": population, "basef": 2.},
                         "conditional": conditional[::-1], "random": random,
                         "trial_covariates": [{"cell_id": cell, "basef": baseline}
                                              for i, cell in enumerate(roster) for _ in range(i + 1)],
                         "conditional_semantics": "fixed_plus_random"}
    return groups


def run(exports=None, **limits):
    bounds = {"max_cells": 10, "max_trial_rows": 30, "max_output_bytes": 100000}
    bounds.update(limits)
    return summary.summarize_panel(fixture() if exports is None else exports,
                                  limits=bounds, alignment_source=ALIGNMENT)


class GroupSummaryControls(unittest.TestCase):
    def test_complete_equal_cell_companions_keep_both_interpretations(self):
        data = fixture()
        before = copy.deepcopy(data)
        result = run(data)
        self.assertEqual(data, before)
        self.assertEqual(set(result["groups"]), {"activated", "suppressed"})
        for group in result["groups"].values():
            self.assertEqual(group["cell_ids"], ["c3", 1, "1"])
            self.assertEqual(group["cell_count_relative_to_supplied_roster"], 3)
            slope = group["quantities"]["preceding_slope"]
            self.assertEqual(slope["values_in_supplied_cell_order"], [1., 3., 5.])
            self.assertEqual(slope["mean"], 3.)
            self.assertAlmostEqual(slope["sem"], 2 / math.sqrt(3))
            self.assertEqual(slope["notebook_display_rounded_2_decimals"], {"mean": 3., "sem": 1.15})
        activated = result["groups"]["activated"]["quantities"]
        self.assertEqual(activated["literal_notebook_intercept"]["values_in_supplied_cell_order"], [32., 34., 36.])
        self.assertEqual(activated["literal_notebook_intercept"]["mean"], 34.)
        self.assertEqual(activated["conditional_model_intercept"]["mean"], 24.)
        suppressed = result["groups"]["suppressed"]["quantities"]
        self.assertEqual(suppressed["literal_notebook_intercept"]["mean"], 0.)
        self.assertEqual(suppressed["conditional_model_intercept"]["mean"], 4.)
        self.assertEqual(result["diagnostic"]["activated"]["rows"][2]["trial_rows"], 3)

    def test_singleton_retains_undefined_sem_without_false_certainty(self):
        data = fixture()
        for group in data.values():
            group["expected_cell_ids"] = ["c3"]
            for field in ("conditional", "random", "trial_covariates"):
                group[field] = [row for row in group[field] if row["cell_id"] == "c3"]
        value = run(data)["groups"]["activated"]["quantities"]["preceding_slope"]
        self.assertEqual(value["mean"], 1.)
        self.assertIsNone(value["sem"])
        self.assertEqual(value["sem_state"], "undefined_fewer_than_two_cells")
        json.dumps(run(data), allow_nan=False)

    def test_zero_variability_retains_zero_sem(self):
        data = fixture()
        for group in data.values():
            for field in ("conditional", "random"):
                for row in group[field]: row["preceding"] = -2.
        value = run(data)["groups"]["suppressed"]["quantities"]["preceding_slope"]
        self.assertEqual(value["mean"], -2.)
        self.assertEqual(value["sem"], 0.)
        self.assertEqual(value["sem_state"], "defined")

    def test_missing_extra_duplicate_or_nonfinite_cells_never_shrink_panel(self):
        for change in ("missing_group", "extra_group", "missing_cell", "extra_cell", "duplicate_id", "nan", "inf"):
            data = fixture()
            panel = data["activated"]
            if change == "missing_group": del data["suppressed"]
            elif change == "extra_group": data["other"] = copy.deepcopy(panel)
            elif change == "missing_cell": panel["conditional"].pop()
            elif change == "extra_cell": panel["random"].append({"cell_id": "extra", "intercept": 1., "preceding": 1.})
            elif change == "duplicate_id": panel["expected_cell_ids"][1] = "c3"
            else: panel["conditional"][0]["preceding"] = float(change)
            with self.subTest(change=change), self.assertRaises(ValueError): run(data)

    def test_capacity_refusal_is_complete_and_limits_not_scientific_selection(self):
        for field, value in (("max_cells", 2), ("max_trial_rows", 5), ("max_output_bytes", 10), ("max_cells", True)):
            with self.subTest(field=field, value=value), self.assertRaises(summary.SummaryError): run(**{field: value})
        self.assertEqual(run(max_cells=100)["groups"], run()["groups"])

    def test_arithmetic_overflow_is_explicit_not_an_accepted_nonfinite_result(self):
        data = fixture()
        for panel in data.values():
            for field in ("conditional", "random"):
                for row in panel[field]: row["preceding"] = 1e308
        with self.assertRaisesRegex(summary.SummaryError, "nonfinite descriptive arithmetic"): run(data)

    def test_no_original_cohort_runtime_or_scientific_claim(self):
        result = run()
        for field in ("original_cohort_authenticated", "historical_runtime_verified",
                      "animal_uncertainty_established", "scientific_qualification"):
            self.assertIs(result[field], False)
        for field in ("branch_selected", "reproduction_accepted", "improvement_accepted"):
            self.assertIsNone(result[field])
        self.assertEqual(result["alignment_sha256"], summary.ALIGNMENT_SHA256)
        self.assertEqual(set(result["runtime_record"]), {"python", "numpy", "scipy"})
        self.assertFalse(any(name == "pymer4" or name.startswith("rpy2") for name in sys.modules))

    def test_changed_alignment_source_is_refused(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            path = Path(directory) / "changed.py"
            path.write_bytes(b"not-source")
            with self.assertRaisesRegex(summary.SummaryError, "source pin mismatch"):
                summary.summarize_panel(fixture(), limits={"max_cells": 10, "max_trial_rows": 30,
                                                         "max_output_bytes": 100000}, alignment_source=path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment-source", type=Path)
    parser.add_argument("--scratch-root", type=Path)
    args = parser.parse_args()
    ALIGNMENT, SCRATCH = args.alignment_source, args.scratch_root
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GroupSummaryControls))
    print(json.dumps({"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "skips": len(result.skipped), "runtime": {"python": summary.platform.python_version(),
                      "numpy": summary.np.__version__, "scipy": summary.scipy.__version__}}))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
