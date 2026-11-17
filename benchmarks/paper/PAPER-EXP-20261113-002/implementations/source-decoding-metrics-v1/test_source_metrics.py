"""Generated controls only: no original scores, labels, models or recordings."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_metrics", HERE / "source_metrics.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def matrix(diagonal=2 / 3, off_diagonal=1 / 3):
    return [[diagonal if train == test else off_diagonal for test in range(20)]
            for train in range(20)]


def document():
    return {"schema": m.SCHEMA, "sessions": {
        session: {state: {"within_time": [[0.5] * 191 for _ in range(5)],
                          "cross_time": [matrix() for _ in range(5)]}
                  for state in ("stat", "run")}
        for session in m.SESSIONS}}


class SourceMetrics(unittest.TestCase):
    def test_fold_means_are_not_pooled_trial_accuracy(self):
        # Eight observations/class: source threefold split lengths 3,3,2.
        # Fold accuracies 1,0,0 give 1/3, not pooled 3/8.
        folds = [[[label] * 3 for label in range(1, 7)],
                 [[label % 6 + 1] * 3 for label in range(1, 7)],
                 [[label % 6 + 1] * 2 for label in range(1, 7)]]
        out = m.score_within_time_folds(folds)
        self.assertEqual(out["mean_accuracy"], 1 / 3)
        self.assertNotEqual(out["mean_accuracy"], 3 / 8)

    def test_fold_support_and_prediction_domains(self):
        folds = [[[label] * 2 for label in range(1, 7)] for _ in range(3)]
        self.assertEqual(m.score_within_time_folds(folds)["mean_accuracy"], 1)
        for mutation in (lambda x: x.pop(), lambda x: x[0][0].pop(),
                         lambda x: x[0][0].__setitem__(0, True),
                         lambda x: x[0][0].__setitem__(0, 7)):
            bad = copy.deepcopy(folds)
            mutation(bad)
            with self.assertRaises(ValueError):
                m.score_within_time_folds(bad)

    def test_equation21_against_independent_rational_calculation(self):
        # Fractions provide an independent exact arithmetic oracle.
        values = [[Fraction((13 * i + 7 * j) % 31, 31) for j in range(20)]
                  for i in range(20)]
        oracle_den = sum(max(values[j][j] - Fraction(1, 6), 0) for j in range(2, 12))
        oracle = [sum(max(row[j] - Fraction(1, 6), 0) for j in range(2, 12)) / oracle_den
                  for row in values]
        out = m.relative_performance([[float(value) for value in row] for row in values])
        for actual, expected in zip(out["relative_performance"], oracle):
            self.assertAlmostEqual(actual, float(expected), places=14)

    def test_window_selection_and_matrix_orientation(self):
        values = matrix()
        out = m.relative_performance(values)
        self.assertAlmostEqual(out["early_relative_performance"], 0.4)
        # Changing all pre/post stimulus test columns must not affect equation 21.
        for row in values:
            for column in (0, 1, *range(12, 20)):
                row[column] = 1.0
        self.assertEqual(m.relative_performance(values)["relative_performance"],
                         out["relative_performance"])
        values[3][4] = 1.0
        forward = m.relative_performance(values)["early_relative_performance"]
        transposed = m.relative_performance([list(row) for row in zip(*values)])["early_relative_performance"]
        self.assertGreater(forward, transposed)

    def test_ratio_is_not_clipped_to_one(self):
        out = m.relative_performance(matrix(diagonal=1 / 3, off_diagonal=2 / 3))
        self.assertAlmostEqual(out["early_relative_performance"], 2.8)

    def test_mean_permutations_before_above_chance_clipping(self):
        doc = document()
        rows = doc["sessions"][m.SESSIONS[0]]["stat"]["cross_time"]
        for repeat, value in enumerate((0, 0, 0, 0, 0.5)):
            rows[repeat][3][4] = value
        out = m.summarize(doc)["per_mouse"][m.SESSIONS[0]]["stat"]
        # Four early-row off-diagonal? Nine total; one becomes below chance.
        expected_numerator = 8 * (1 / 3 - 1 / 6) + (2 / 3 - 1 / 6)
        self.assertAlmostEqual(out["stimulus_cross_time_above_chance_sum"][3], expected_numerator)

    def test_five_mice_sem_and_ratio_before_cohort_mean(self):
        doc = document()
        for index, session in enumerate(m.SESSIONS):
            for state in m.STATES:
                doc["sessions"][session][state]["within_time"] = [[index / 4] * 191 for _ in range(5)]
                doc["sessions"][session][state]["cross_time"] = [
                    matrix(diagonal=(index + 2) / 7, off_diagonal=0.2) for _ in range(5)]
        out = m.summarize(doc)
        curve = out["group"]["stat"]["within_time_mean_accuracy"]
        self.assertEqual(curve["mean"], [0.5] * 191)
        self.assertAlmostEqual(curve["sem"][0], math.sqrt(0.625 / 4 / 5))
        oracle = sum(row["stat"]["early_relative_performance"] for row in out["per_mouse"].values()) / 5
        self.assertAlmostEqual(out["group"]["stat"]["relative_performance"]["mean"][3], oracle)
        ratio_after_pooling = m.relative_performance(
            out["group"]["stat"]["cross_time_mean_accuracy"]["mean"])["early_relative_performance"]
        self.assertNotAlmostEqual(oracle, ratio_after_pooling)

    def test_undefined_denominator_preserves_all_raw_outputs(self):
        doc = document()
        doc["sessions"][m.SESSIONS[0]]["stat"]["cross_time"] = [
            matrix(diagonal=1 / 6, off_diagonal=0.1) for _ in range(5)]
        out = m.summarize(doc)
        self.assertIsNone(out["group"]["stat"]["relative_performance"]["mean"])
        self.assertEqual(out["group"]["stat"]["relative_performance"]["undefined_sessions"], [m.SESSIONS[0]])
        self.assertIsNone(out["early_paired_run_minus_stat"][m.SESSIONS[0]])
        self.assertEqual(len(out["per_mouse"]), 5)
        self.assertEqual(len(out["per_mouse"][m.SESSIONS[0]]["stat"]["cross_time_mean_accuracy"]), 20)
        self.assertIsNotNone(out["group"]["run"]["relative_performance"]["mean"])

    def test_complete_support_and_accuracy_units(self):
        for mutation in (
            lambda x: x["sessions"].pop(m.SESSIONS[0]),
            lambda x: x["sessions"][m.SESSIONS[0]].pop("run"),
            lambda x: x["sessions"][m.SESSIONS[0]]["stat"]["within_time"].pop(),
            lambda x: x["sessions"][m.SESSIONS[0]]["stat"]["cross_time"][0][0].pop(),
            lambda x: x["sessions"][m.SESSIONS[0]]["stat"]["within_time"][0].__setitem__(0, 50),
            lambda x: x["sessions"][m.SESSIONS[0]]["stat"]["within_time"][0].__setitem__(0, float("nan")),
            lambda x: x["sessions"][m.SESSIONS[0]]["stat"]["within_time"][0].__setitem__(0, True),
        ):
            bad = document()
            mutation(bad)
            with self.assertRaises(ValueError):
                m.summarize(bad)

    def test_json_duplicate_and_nonfinite_refusal(self):
        for raw in ('{"schema":1,"schema":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                m.strict_json(raw)

    def test_cli_full_generated_cohort_digest_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "invented.json"
            target = root / "summary.json"
            raw = json.dumps(document()).encode()
            source.write_bytes(raw)
            command = [sys.executable, "-I", "-S", "-B", str(HERE / "source_metrics.py"),
                       "--input", str(source), "--input-sha256", hashlib.sha256(raw).hexdigest(),
                       "--output", str(target)]
            run = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            original = target.read_bytes()
            output = json.loads(original)
            self.assertEqual(output["biological_units"], 5)
            self.assertEqual(output["cross_time_axes"], ["train_time", "test_time"])
            self.assertNotIn(str(root).encode(), original)
            again = subprocess.run(command, capture_output=True, timeout=10)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(target.read_bytes(), original)
            target.unlink()
            command[command.index("--input-sha256") + 1] = "0" * 64
            invalid = subprocess.run(command, capture_output=True, timeout=10)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
