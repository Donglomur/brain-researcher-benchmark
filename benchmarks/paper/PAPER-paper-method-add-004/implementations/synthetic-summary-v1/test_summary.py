"""Generated controls only; no original targets or fitted outputs."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("summary_under_test", Path(__file__).with_name("summary.py"))
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def unit(identity=0):
    fits = []
    # Literal independent coordinate list, not generated from implementation constants.
    for method in ("acf_full", "isttc_full"):
        for duration in (60, 150, 300, 450, 600):
            fits.append(dict(method=method, duration_s=duration, tau=2.0,
                             tau_lower=-1.0, tau_upper=3.0, fit_r_squared=0.0,
                             acf_lags_1_3=[0.8, 0.7, 0.6]))
    for method in ("pearsonr_trial_avg", "sttc_trial_concat"):
        for n in (40, 60, 80, 100):
            fits.append(dict(method=method, n_trials=n, trial_iteration=0, tau=2.0,
                             tau_lower=-1.0, tau_upper=3.0, fit_r_squared=0.0,
                             acf_lags_1_3=[0.8, 0.7, 0.6]))
    fits.append(dict(method="sttc_trial_avg", n_trials=40, trial_iteration=0, tau=2.0,
                     tau_lower=-1.0, tau_upper=3.0, fit_r_squared=0.0,
                     acf_lags_1_3=[0.8, 0.7, 0.6]))
    return dict(unit_id=identity, tau_ms_true=125.0, fr=2.0, alpha=0.5, lv=1.0, fits=fits)


def select(row, method, value):
    return next(f for f in row["fits"] if f["method"] == method and f.get("duration_s", f.get("n_trials")) == value)


class SummaryTests(unittest.TestCase):
    def test_absolute_error_units_and_source_zero_boundary(self):
        panels = summary.summarize_unit(unit())
        row, admitted = panels["four_methods"][0]
        self.assertEqual((row["tau_ms"], row["tau_diff_abs"], row["tau_diff_rel"]), (100, 25, 20))
        self.assertEqual(row["ci_width"], 4)  # CI stays in lag units, not 200 ms.
        self.assertTrue(admitted)  # R² zero and CI crossing zero are retained.
        self.assertEqual({p: len(rows) for p, rows in panels.items()},
                         {"four_methods": 4, "continuous": 2, "trials": 3, "duration": 10, "trial_count": 8})

    def test_symmetric_absolute_ree_does_not_minimize_signed_bias(self):
        a = unit()
        select(a, "isttc_full", 600)["tau"] = 3.0
        rows = summary.summarize_unit(a)["continuous"]
        self.assertEqual([r["tau_diff_rel"] for r, _ in rows], [20, 20])

    def test_missing_lv_excludes_main_but_not_sensitivity(self):
        a = unit()
        a["lv"] = None
        panels = summary.summarize_unit(a)
        for name in ("four_methods", "continuous", "trials"):
            self.assertFalse(any(flag for _, flag in panels[name]))
        for name in ("duration", "trial_count"):
            self.assertTrue(all(flag for _, flag in panels[name]))
            self.assertTrue(all("lv" not in row for row, _ in panels[name]))

    def test_null_ci_excludes_pair_not_only_bad_method(self):
        a = unit()
        select(a, "acf_full", 150)["tau_lower"] = None
        rows = summary.summarize_unit(a)["duration"]
        self.assertEqual([row["duration_s"] for row, flag in rows if not flag], [150, 150])
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(flag for _, flag in summary.summarize_unit(a)["four_methods"]))

    def test_negative_r_squared_is_condition_local(self):
        a = unit()
        select(a, "pearsonr_trial_avg", 60)["fit_r_squared"] = -0.0001
        rows = summary.summarize_unit(a)["trial_count"]
        self.assertEqual([row["n_trials"] for row, flag in rows if not flag], [60, 60])
        self.assertTrue(all(flag for _, flag in summary.summarize_unit(a)["trials"]))

    def test_extra_trial_method_has_own_three_method_mask(self):
        a = unit()
        select(a, "sttc_trial_avg", 40)["tau"] = None
        panels = summary.summarize_unit(a)
        self.assertFalse(any(flag for _, flag in panels["trials"]))
        self.assertTrue(all(flag for _, flag in panels["four_methods"]))
        self.assertTrue(all(flag for _, flag in panels["trial_count"]))

    def test_acf_nan_and_non_decline_are_false_not_missing_exclusions(self):
        a = unit()
        select(a, "acf_full", 600)["acf_lags_1_3"] = [0.2, None, 0.4]
        select(a, "isttc_full", 600)["acf_lags_1_3"] = [0.2, 0.5, 0.4]
        rows = summary.summarize_unit(a)["continuous"]
        self.assertTrue(all(not row["acf_decline"] and flag for row, flag in rows))

    def test_missing_duplicate_unknown_and_iteration_rejected(self):
        variants = []
        a = unit(); a["fits"].pop(); variants.append(a)
        a = unit(); a["fits"][-1] = copy.deepcopy(a["fits"][0]); variants.append(a)
        a = unit(); a["fits"][0]["duration_s"] = 100; variants.append(a)
        a = unit(); a["fits"][-1]["trial_iteration"] = 1; variants.append(a)
        for a in variants:
            with self.subTest(a=a["fits"][-1]), self.assertRaises(summary.Invalid):
                summary.summarize_unit(a)

    def test_nonfinite_boolean_and_overflow_not_silent_failed_fit(self):
        for bad in (float("nan"), float("inf"), True, 10 ** 1000):
            a = unit(); a["fits"][0]["tau"] = bad
            with self.assertRaises(summary.Invalid):
                summary.summarize_unit(a)
        a = unit(); a["fits"][0]["tau"] = 1e308
        with self.assertRaises(summary.Invalid):
            summary.summarize_unit(a)

    def test_streaming_complete_support_keeps_raw_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            a, b = unit(), unit(1)
            select(b, "acf_full", 600)["tau"] = None
            source = root / "input.jsonl"
            source.write_text(json.dumps(a) + "\n" + json.dumps(b) + "\n")
            report = summary.produce(source, root / "out", expected_units=2)
            self.assertEqual(report["counts"]["four_methods"], {"all_rows": 8, "clean_rows": 4})
            self.assertEqual(report["counts"]["duration"], {"all_rows": 20, "clean_rows": 18})
            with (root / "out/four_methods.all.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[4]["tau"], "")
            self.assertTrue((root / "out/COMPLETE.json").exists())
            self.assertEqual(len((root / "out/support.jsonl").read_text().splitlines()), 2)

    def test_incomplete_and_reordered_units_never_complete(self):
        for records in ([unit()], [unit(1), unit()]):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "input.jsonl"
                source.write_text("\n".join(json.dumps(row) for row in records) + "\n")
                with self.assertRaises(summary.Invalid):
                    summary.produce(source, root / "out", expected_units=2)
                self.assertFalse((root / "out/COMPLETE.json").exists())

    def test_strict_json_and_fresh_output(self):
        for text in ('{"x": 0, "x": 1}', '{"x": NaN}'):
            with self.assertRaises(summary.Invalid):
                summary.strict_json(text)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileExistsError):
                summary.produce(Path(temporary) / "not-read", temporary)


if __name__ == "__main__":
    unittest.main()
