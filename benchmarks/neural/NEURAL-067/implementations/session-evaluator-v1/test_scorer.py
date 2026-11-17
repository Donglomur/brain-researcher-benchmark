"""Generated controls only: no recorded observations, target artifacts or fitting."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("neural067_scorer", Path(__file__).with_name("scorer.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    targets, entries = {}, []
    for run, session, count in s.QUERY:
        scale = 1 if session == "S6" else 10
        velocity = [[0.0] * 7, [2.0 * scale, 4.0 * scale, 0, 0, 0, 0, 0]]
        targets[run] = {
            "run": run, "session": session, "row_ids": list(range(count)),
            "velocity": velocity + [[0.0] * 7] * (count - 2),
            "eval_mask": [True, True] + [False] * (count - 2),
        }
    for arm in s.ARMS:
        for run, session, count in s.QUERY:
            values = targets[run]["velocity"]
            error = 1 if arm == "neural" and session == "S6" else 0
            prediction = [list(row) for row in values[:2]]
            if arm == "clock":
                prediction = [[0.0] * 7, [0.0] * 7]
            else:
                for row in prediction:
                    row[0] += error
                    row[1] += error
            # Deliberately large finite unscored errors test the mask placement.
            prediction += [[1000.0] * 7] * (count - 2)
            entries.append({"arm": arm, "run": run, "session": session,
                            "row_ids": list(range(count)), "prediction": prediction})
    submission = {"schema": "neural067_session_predictions_v1", "contract_sha256": s.CONTRACT_SHA256,
                  "columns": list(s.COLUMNS), "entries": entries}
    return submission, targets


class MetricTests(unittest.TestCase):
    def test_weighted_not_coordinate_average(self):
        y = [[0] * 7, [2, 4, 0, 0, 0, 0, 0]]
        p = [[1, 1, 0, 0, 0, 0, 0], [3, 5, 0, 0, 0, 0, 0]]
        result = s.metric(y, p)
        self.assertAlmostEqual(result["variance_weighted_r2"], 0.6)
        self.assertEqual(result["per_channel_r2"], [0.0, 0.75, None, None, None, None, None])
        self.assertEqual(result["sse"], [2, 2, 0, 0, 0, 0, 0])
        self.assertEqual(result["sst"], [2, 8, 0, 0, 0, 0, 0])

    def test_constant_exact_or_wrong_remains_undefined(self):
        y = [[0.1] * 7] * 3
        for p in (y, [[0] * 7] * 3):
            result = s.metric(y, p)
            self.assertIsNone(result["variance_weighted_r2"])
            self.assertEqual(result["status"], "undefined_all_targets_constant")
            self.assertEqual(result["per_channel_r2"], [None] * 7)
            self.assertEqual(result["sst"], [0] * 7)

    def test_underflow_and_overflow_are_not_fabricated_scores(self):
        with self.assertRaises(ValueError):
            s.metric([[0] * 7, [1e-200] * 7], [[0] * 7] * 2)
        with self.assertRaises(ValueError):
            s.metric([[1e308] * 7, [-1e308] * 7], [[0] * 7] * 2)

    def test_small_support_and_nonfinite_rejected(self):
        for y, p in (([[0] * 7], [[0] * 7]),
                     ([[0] * 7] * 2, [[float("nan")] * 7] * 2),
                     ([[0] * 7] * 2, [[True] * 7] * 2)):
            with self.assertRaises(ValueError):
                s.metric(y, p)

    def test_undefined_is_not_dropped(self):
        self.assertEqual(s.summary([1.0, None, 0.0]),
                         {"mean": None, "std": None, "status": "undefined_session_retained"})


class CompletePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.submission, cls.targets = fixture()

    def test_complete_source_roster_and_arithmetic(self):
        self.assertEqual(sum(n for _, _, n in s.QUERY), 34490)
        self.assertEqual(len(s.QUERY), 14)
        result = s.grade(self.submission, self.targets.__getitem__)
        self.assertEqual(result["full_rows_per_arm"], 34490)
        self.assertEqual(result["masked_rows_per_arm"], 28)
        neural = result["arms"]["neural"]
        self.assertAlmostEqual(neural["held_out_session_r2"]["mean"], 33 / 35)
        self.assertAlmostEqual(neural["by_session"]["S6"]["variance_weighted_r2"], 3 / 5)
        self.assertAlmostEqual(result["arms"]["clock"]["held_out_session_r2"]["mean"], -1)
        self.assertAlmostEqual(result["paired_session_differences"]["neural_clock_minus_clock"]
                               ["session_difference"]["mean"], 2)
        self.assertEqual(result["held_in"]["status"], "not_in_declared_query_panel")
        self.assertFalse(result["causal_program_execution_verified"])
        self.assertFalse(result["access_mode_verified"])

    def test_joins_runs_before_computing_variance(self):
        targets = dict(self.targets)
        for index, (run, session, _) in enumerate(s.QUERY[:2]):
            targets[run] = dict(targets[run])
            # Each run is constant; pooled session is variable in every channel.
            targets[run]["velocity"] = [[float(index)] * 7] * len(targets[run]["row_ids"])
        result = s.grade(self.submission, targets.__getitem__)
        self.assertEqual(result["arms"]["neural"]["by_session"]["S6"]["status"], "defined")
        self.assertEqual(result["arms"]["neural"]["by_session"]["S6"]["sst"], [1.0] * 7)

    def test_one_constant_session_invalidates_primary_without_dropping(self):
        targets = dict(self.targets)
        for run, _, count in s.QUERY[:2]:
            targets[run] = dict(targets[run], velocity=[[0.1] * 7] * count)
        result = s.grade(self.submission, targets.__getitem__)
        for arm in s.ARMS:
            self.assertEqual(len(result["arms"][arm]["by_session"]), 7)
            self.assertIsNone(result["arms"][arm]["held_out_session_r2"]["mean"])
        self.assertIsNone(result["paired_session_differences"]["neural_clock_minus_clock"]
                          ["session_difference"]["mean"])

    def test_missing_reordered_and_duplicate_blocks_fail_before_targets(self):
        for entries in (self.submission["entries"][:-1],
                        self.submission["entries"][1:] + self.submission["entries"][:1],
                        self.submission["entries"][:-1] + self.submission["entries"][:1]):
            submitted = dict(self.submission, entries=entries)
            with self.assertRaises(ValueError):
                s.grade(submitted, lambda run: self.fail("private callback before admission"))

    def test_row_id_mask_shape_and_numeric_failures(self):
        for field, replacement in (("row_ids", [0] * s.QUERY[0][2]),
                                   ("prediction", [[0] * 6] * s.QUERY[0][2]),
                                   ("prediction", [[float("inf")] * 7] * s.QUERY[0][2])):
            entry = dict(self.submission["entries"][0], **{field: replacement})
            submitted = dict(self.submission, entries=[entry] + self.submission["entries"][1:])
            with self.assertRaises(ValueError):
                s.grade(submitted, lambda run: self.fail("target read"))
        run = s.QUERY[0][0]
        for mask in ([1] * s.QUERY[0][2], [True], [False] * s.QUERY[0][2]):
            targets = dict(self.targets)
            targets[run] = dict(targets[run], eval_mask=mask)
            if len(mask) == s.QUERY[0][2] and mask[0] is False:
                # The other run still contributes two rows, so this is allowed.
                result = s.grade(self.submission, targets.__getitem__)
                self.assertEqual(result["masked_rows_per_arm"], 26)
            else:
                with self.assertRaises(ValueError):
                    s.grade(self.submission, targets.__getitem__)

    def test_empty_session_refused(self):
        targets = dict(self.targets)
        for run, _, count in s.QUERY[:2]:
            targets[run] = dict(targets[run], eval_mask=[False] * count)
        with self.assertRaisesRegex(ValueError, "two masked rows"):
            s.grade(self.submission, targets.__getitem__)

    def test_wrong_contract_columns_or_extra_values_rejected(self):
        for key, value in (("contract_sha256", "0" * 64), ("columns", list(reversed(s.COLUMNS)))):
            with self.assertRaises(ValueError):
                s.grade(dict(self.submission, **{key: value}), lambda run: self.fail("target read"))
        extra = dict(self.submission, evaluator_target="forbidden")
        with self.assertRaises(ValueError):
            s.grade(extra, lambda run: self.fail("target read"))

    def test_target_identity_is_bound(self):
        run = s.QUERY[0][0]
        targets = dict(self.targets)
        targets[run] = dict(targets[run], session="S7")
        with self.assertRaisesRegex(ValueError, "run/session"):
            s.grade(self.submission, targets.__getitem__)

    def test_prediction_is_captured_before_operator_callback(self):
        submitted = dict(self.submission, entries=list(self.submission["entries"]))
        first = dict(submitted["entries"][0], prediction=list(submitted["entries"][0]["prediction"]))
        submitted["entries"][0] = first
        def loader(run):
            first["prediction"][0] = [999] * 7
            return self.targets[run]
        result = s.grade(submitted, loader)
        self.assertAlmostEqual(result["arms"]["neural"]["held_out_session_r2"]["mean"], 33 / 35)


class JsonTests(unittest.TestCase):
    def test_duplicate_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            for content in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    s.read_json(path)


class CliTests(unittest.TestCase):
    def test_complete_cli_and_output_refusal(self):
        submitted, targets = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prediction_path, target_path, output = (root / name for name in ("prediction.json", "target.json", "grade.json"))
            prediction_path.write_bytes(s.canonical(submitted))
            target_path.write_bytes(s.canonical({"schema": "neural067_session_targets_v1",
                                                "contract_sha256": s.CONTRACT_SHA256, "runs": targets}))
            argv = ["scorer.py", "--submission", str(prediction_path), "--targets", str(target_path), "--output", str(output)]
            with patch("sys.argv", argv):
                s.main()
                result = json.loads(output.read_text())
                self.assertAlmostEqual(result["arms"]["neural"]["held_out_session_r2"]["mean"], 33 / 35)
                with self.assertRaisesRegex(ValueError, "output must be new"):
                    s.main()

    def test_invalid_submission_does_not_open_target_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            prediction_path = root / "prediction.json"
            prediction_path.write_text("{}")
            argv = ["scorer.py", "--submission", str(prediction_path), "--targets", str(root / "absent.json"),
                    "--output", str(root / "grade.json")]
            with patch("sys.argv", argv), self.assertRaisesRegex(ValueError, "submission fields"):
                s.main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
