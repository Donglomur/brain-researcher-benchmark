"""Generated arithmetic and native-array layout controls, never real sessions."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "fig3_score.py"
spec = importlib.util.spec_from_file_location("fig3_score", MODULE)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    # Unequal folds distinguish the author's mean-of-folds from pooled scoring:
    # 11 samples: first fold has two correct, other nine have one antipodal.
    # Expected session score -0.8, whereas pooling gives -7/11.
    rows = []
    for animal in s.ANIMALS:
        for day in s.DAYS:
            for cell in s.CELL_TYPES:
                for model in s.MODELS:
                    test_set = "all" if model == "random" else model[-1]
                    folds = []
                    for i in range(10):
                        n = 2 if i == 0 else 1
                        folds.append({"sample_ids": [f"{test_set}-{i}-{j}" for j in range(n)],
                                      "actual": [0.0] * n,
                                      "predicted": [0.0 if i == 0 else math.pi] * n})
                    # Model-specific values expose a mistaken native axis transpose.
                    value = (s.MODELS.index(model) - 2) / 4
                    rows.append({"animal": animal, "day": day, "cell_type": cell,
                                 "model": model, "folds": folds,
                                 "shuffle_scores": [[value] * 10 for _ in range(100)]})
    return {"schema": s.SCHEMA, "source_commit": s.COMMIT,
            "preparation_sha256": "1" * 64, "fold_receipt_sha256": "2" * 64, "rows": rows}


def native_fixture(panel):
    native = {key: {} for key in ("actual", "pred", "scores", "scores_shuffle")}
    support = {}
    index = {(r["animal"], r["day"], r["cell_type"], r["model"]): r for r in panel["rows"]}
    for day in s.DAYS:
        support[str(day)] = {}
        for key in native:
            native[key][str(day)] = {}
        for animal in s.ANIMALS:
            support[str(day)][animal] = {}
            for key in native:
                native[key][str(day)][animal] = {}
            for cell in s.CELL_TYPES:
                actual, predicted, stored = {}, {}, []
                for model in s.MODELS:
                    row = index[animal, day, cell, model]
                    actual[model] = [f["actual"] for f in row["folds"]]
                    predicted[model] = [f["predicted"] for f in row["folds"]]
                    support[str(day)][animal][model] = [f["sample_ids"] for f in row["folds"]]
                    stored.append([1.0] + [-1.0] * 9)
                native["actual"][str(day)][animal][cell] = actual
                native["pred"][str(day)][animal][cell] = predicted
                native["scores"][str(day)][animal][cell] = stored
                native["scores_shuffle"][str(day)][animal][cell] = [
                    [[(k - 2) / 4 for k in range(5)] for _ in range(10)] for _ in range(100)]
    return native, support


class Fig3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = fixture()

    def changed_row(self, change):
        panel = dict(self.panel)
        panel["rows"] = list(panel["rows"])
        panel["rows"][0] = copy.deepcopy(panel["rows"][0])
        change(panel["rows"][0])
        return panel

    def test_source_fold_weighting_and_complete_conditions(self):
        out = s.score_panel(self.panel)
        self.assertEqual(len(out["rows"]), 1155)
        self.assertEqual(sum(r["figure3b"] for r in out["rows"]), 462)
        for row in out["rows"]:
            self.assertAlmostEqual(row["mean_cosine"], -0.8)
            self.assertNotAlmostEqual(row["mean_cosine"], -7 / 11)
            self.assertEqual(row["sample_count"], 11)

    def test_paired_extreme_gains_with_mouse_units(self):
        candidate = copy.deepcopy(self.panel)
        for row in candidate["rows"]:
            for fold in row["folds"]:
                fold["predicted"] = [0.0] * len(fold["actual"])
        out = s.compare(candidate, self.panel)
        self.assertEqual(len(out["session_conditions"]), 1155)
        self.assertEqual(len(out["mouse_conditions"]), 165)
        self.assertTrue(all(r["sessions"] == 7 for r in out["mouse_conditions"]))
        self.assertAlmostEqual(out["mouse_conditions"][0]["mean_paired_gain"], 1.8)
        self.assertIsNone(out["paper_win"])

    def test_native_adapter_correct_axis_and_stored_score_check(self):
        native, support = native_fixture(self.panel)
        out = s.export_native(native, support, "1" * 64, "2" * 64)
        # Native source traverses day then animal; row order has no scientific
        # meaning, while within-fold observation order is strictly preserved.
        row_key = lambda r: (r["animal"], r["day"], r["cell_type"], r["model"])
        self.assertEqual(sorted(out["rows"], key=row_key), sorted(self.panel["rows"], key=row_key))
        native["scores"]["3"]["GCAMP3"]["rr"][0][0] = 0
        with self.assertRaisesRegex(s.InputError, "stored scores disagree"):
            s.export_native(native, support, "1" * 64, "2" * 64)

    def test_missing_companion_duplicate_and_unknown_mouse_fail(self):
        panel = dict(self.panel, rows=self.panel["rows"][:-1])
        with self.assertRaises(s.InputError):
            s.score_panel(panel)
        panel = dict(self.panel, rows=self.panel["rows"][:-1] + [self.panel["rows"][0]])
        with self.assertRaises(s.InputError):
            s.score_panel(panel)
        with self.assertRaises(s.InputError):
            s.score_panel(self.changed_row(lambda r: r.update(animal="GCAMP2")))

    def test_nonfinite_effect_size_and_boolean_rejected(self):
        for invalid in (float("nan"), float("inf"), True, 2.7):
            with self.subTest(invalid=invalid), self.assertRaises(s.InputError):
                s.score_panel(self.changed_row(lambda r: r["shuffle_scores"][0].__setitem__(0, invalid)))

    def test_cross_population_target_and_repeat_sample_rejected(self):
        with self.assertRaisesRegex(s.InputError, "test samples/targets differ"):
            s.score_panel(self.changed_row(lambda r: r["folds"][0]["actual"].__setitem__(0, 0.5)))
        with self.assertRaisesRegex(s.InputError, "repeated test sample"):
            s.score_panel(self.changed_row(lambda r: r["folds"][1]["sample_ids"].__setitem__(0, "0-0-0")))

    def test_pair_receipt_and_consistent_target_tamper_rejected(self):
        panel = dict(self.panel, fold_receipt_sha256="3" * 64)
        with self.assertRaisesRegex(s.InputError, "fold_receipt_sha256 differs"):
            s.compare(panel, self.panel)
        panel = copy.deepcopy(self.panel)
        for row in panel["rows"]:
            for fold in row["folds"]:
                fold["actual"] = [0.1] * len(fold["actual"])
        with self.assertRaisesRegex(s.InputError, "target mismatch"):
            s.compare(panel, self.panel)

    def test_empty_folds_and_wrong_split_order_rejected(self):
        with self.assertRaises(s.InputError):
            s.score_panel(self.changed_row(lambda r: r["folds"][0].update(sample_ids=[], actual=[], predicted=[])))
        with self.assertRaisesRegex(s.InputError, "np.array_split"):
            s.score_panel(self.changed_row(lambda r: r["folds"].reverse()))

    def test_strict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for payload in ('{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}'):
                path.write_text(payload)
                with self.assertRaises(s.InputError):
                    s.read_json(path)

    def test_score_cli_and_no_output_for_incomplete_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, output = Path(tmp) / "panel.json", Path(tmp) / "scores.json"
            path.write_text(json.dumps(self.panel))
            command = [sys.executable, "-I", "-B", str(MODULE), "score", "--panel", str(path),
                       "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            scored = json.loads(output.read_text())
            self.assertEqual(len(scored["rows"]), 1155)
            self.assertAlmostEqual(scored["rows"][0]["mean_cosine"], -0.8)
            output.unlink()
            path.write_text(json.dumps(dict(self.panel, rows=[])))
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
