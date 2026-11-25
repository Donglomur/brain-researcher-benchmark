"""Generated complete-roster controls; no authentic observations or target files."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cerebellar_mean_grade", ROOT / "grade.py")
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)
science, roster = grade.load_sources(ROOT)


def invented(identity, amplitude):
    n = identity["trials"]
    value = {"identity": identity, "curve": {"starts_index1": [1], "FP": [0.], "TP": [0.]},
             "selected_index1": 1, "selected_trial_counts": [[0, 0, 0, 0] for _ in range(n)]}
    if identity["figure"] == "F3":
        value["timing"] = {"mean_silencing": [amplitude] * 350, "mean_peak_index1": 1,
                           "trial_peak_indices1": [1] * n,
                           "trial_flat_selected_window": [True] * n}
    return value


def complete_generated_panel(amplitude):
    """Replace only file transport, retaining the actual 1,020-record validation.

    All source identities are public. Each target/response is invented here;
    no filesystem data or historical numerical report is opened.
    """
    names = {grade.filename(identity): identity for identity in roster}
    manifest = {"files": {name: {"bytes": 1, "sha256": "0" * 64} for name in names},
                "total_bytes": len(names)}
    def inventory(folder, pin, expected, reference=False):
        if set(expected) != set(names):
            raise AssertionError("complete original roster changed")
        return Path("reference" if reference else "candidate"), copy.deepcopy(manifest)
    def read_file(path, *args, **kwargs):
        identity = names[Path(path).name]
        if Path(path).parent.name == "reference":
            value = {"target": invented(identity, 0.),
                     "trial_count_steps": [[[1, 0, 0, 0, 0]] for _ in range(identity["trials"])]}
        else:
            value = invented(identity, amplitude)
        return json.dumps(value, allow_nan=False).encode()
    with patch.object(grade, "inventory", inventory), patch.object(grade, "read_file", read_file):
        return grade.evaluate(science, roster, "candidate", {}, "reference", {}, lambda: None)


class MeanPrecisionControls(unittest.TestCase):
    def check_panel(self, amplitude):
        report = complete_generated_panel(amplitude)
        self.assertEqual(report["status"], "scored")
        self.assertEqual(report["records_scored"], 1020)
        self.assertEqual(report["private_reference_records_loaded"], 1020)
        rows = report["diagnostics"]["F3"]
        column = rows["columns"].index("mean_trace_MAE")
        self.assertEqual(len(rows["rows"]), 14)
        for row in rows["rows"]:
            self.assertEqual(row[column], abs(amplitude))
        means = report["summary"]["figures"]["F3"]
        for mouse in means["by_mouse"].values():
            self.assertEqual(mouse["mean_trace_MAE"], abs(amplitude))
        self.assertEqual(means["equal_mouse_mean"]["mean_trace_MAE"], abs(amplitude))
        return report

    def test_nonzero_minimum_mean_error_survives_complete_panel(self):
        self.check_panel(math.ulp(0.0))

    def test_tiny_negative_mean_error_survives_complete_panel(self):
        self.check_panel(-2 * math.ulp(0.0))

    def test_ordinary_and_zero_errors_preserve_complete_panel(self):
        for amplitude in (0.0, 0.125):
            with self.subTest(amplitude=amplitude):
                report = self.check_panel(amplitude)
                self.assertIsNone(report["summary"]["combined_scalar_score"])
                self.assertFalse(report["scientific_qualified"])


if __name__ == "__main__":
    unittest.main()
