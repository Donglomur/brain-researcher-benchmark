"""Generated software controls only: no source arrays, labels, fits or model trials."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("neural068_scorer", Path(__file__).with_name("scorer.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    metadata = []
    for idx, (run, _) in enumerate(s.RUNS):
        n = 2 + (idx // 2) % 3
        length = 600 + n + 1
        metadata.append({"run": run, "source_sha256": "a" * 64,
                         "time_s": [i * .02 for i in range(length)],
                         "trial": [1] * 500 + [2] * 100 + [3] * (n + 1),
                         "eval_mask": [True] * (length - 1) + [False]})
    layout = s.make_layout(metadata)
    targets, contexts = {}, {}
    for idx, row in enumerate(layout["runs"]):
        # Each run individually is constant; pooled session varies between sets.
        value = (idx % 2) * 10. * (1 + idx // 2)
        y = [[value] * 7 for _ in row["row_ids"]]
        targets[row["run"]] = {"row_ids": row["row_ids"], "targets": y}
        for arm in s.ARMS:
            for budget in s.BUDGETS:
                error = {0: 1., 5: .5, 10: 0.}[budget] if arm == "neural_clock" else 2.
                prediction = [[v + error for v in x] for x in y]
                prediction[-1] = [987654.] * 7  # A masked row must not change score.
                contexts[s.context_id(row["run"], arm, budget)] = {
                    "row_ids": row["row_ids"], "predictions": prediction}
    submission = {"schema": s.VERSION, "packet_id": layout["packet_id"], "contexts": contexts}
    return metadata, layout, submission, targets


class ScoreTests(unittest.TestCase):
    def test_pooled_sessions_paired_budgets_masks_and_equal_weights(self):
        _, layout, submission, targets = fixture()
        result = s.score(layout, submission, targets.__getitem__)
        # Independent closed form: two sets at 0 and 10*k have variance 25*k²;
        # improvement from unit residual to zero is 1/(25*k²), regardless of n.
        expected = sum(1 / (25 * k * k) for k in range(1, 8)) / 7
        self.assertEqual(result["status"], "scored")
        self.assertEqual(result["primary"]["0"], 0.)
        self.assertAlmostEqual(result["primary"]["5"], .75 * expected)
        self.assertAlmostEqual(result["primary"]["10"], expected)
        self.assertEqual(result["paired_gains"]["clock_only"], {"0": 0., "5": 0., "10": 0.})
        self.assertAlmostEqual(result["neural_minus_clock"]["0"], 3 * expected)
        self.assertAlmostEqual(result["neural_minus_clock_recalibration_gain"]["10"], expected)
        self.assertEqual(result["contexts"], 84)
        self.assertEqual(result["full_rows"] - result["scored_rows"], 14)
        self.assertEqual([x["session"] for x in result["by_session"]], list(s.SESSIONS))
        self.assertEqual(sum(len(x["runs"]) for x in result["by_session"]), 14)

    def test_variance_weighting_is_not_uniform_channel_average(self):
        target = [[0., 0.] + [0.] * 5, [2., 20.] + [0.] * 5]
        pred = [[1., 0.] + [0.] * 5, [1., 20.] + [0.] * 5]
        result = s.variance_weighted_r2(target, pred)
        self.assertAlmostEqual(result["r2"], 200 / 202)
        self.assertEqual(result["per_channel_r2"][:2], [0., 1.])

    def test_constant_channels_have_zero_weight_but_errors_are_retained(self):
        target = [[0.] + [.1] * 6, [2.] + [.1] * 6, [4.] + [.1] * 6]
        prediction = [[row[0]] + [10.] * 6 for row in target]
        result = s.variance_weighted_r2(target, prediction)
        self.assertEqual(result["r2"], 1.)
        self.assertEqual(result["constant_channels"], [False] + [True] * 6)
        self.assertEqual(result["sst"][1:], [0.] * 6)
        self.assertTrue(all(x > 0 for x in result["sse"][1:]))
        self.assertEqual(result["per_channel_r2"][1:], [None] * 6)

    def test_all_constant_session_blocks_primary_without_dropping_session(self):
        _, layout, submission, targets = fixture()
        for run, _ in s.RUNS[:2]:
            targets[run]["targets"] = [[.1] * 7 for _ in targets[run]["row_ids"]]
        result = s.score(layout, submission, targets.__getitem__)
        self.assertEqual(result["status"], "undefined_constant_target_session")
        self.assertIsNone(result["primary"])
        self.assertEqual(result["constant_target_sessions"], ["S6"])
        self.assertEqual(len(result["by_session"]), 7)

    def test_all_admission_failures_precede_any_target_read(self):
        _, layout, submission, _ = fixture()
        first = next(iter(submission["contexts"]))
        def no_targets(run):
            self.fail("Malformed prediction reached evaluator target callback")
        mutations = [
            lambda x: x["contexts"].pop(first),
            lambda x: x["contexts"].update({"extra": {}}),
            lambda x: x.update(packet_id="wrong"),
            lambda x: x["contexts"][first]["row_ids"].reverse(),
            lambda x: x["contexts"][first]["predictions"].pop(),
            lambda x: x["contexts"][first]["predictions"][0].pop(),
            lambda x: x["contexts"][first]["predictions"][0].__setitem__(0, True),
            lambda x: x["contexts"][first]["predictions"][0].__setitem__(0, math.nan),
            lambda x: x["contexts"][first]["predictions"][-1].__setitem__(0, math.inf),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(submission)
                mutation(bad)
                with self.assertRaises(s.ContractError):
                    s.score(layout, bad, no_targets)

    def test_target_row_order_cannot_be_silently_changed(self):
        _, layout, submission, targets = fixture()
        targets = copy.deepcopy(targets)
        targets[s.RUNS[0][0]]["row_ids"].reverse()
        with self.assertRaisesRegex(s.ContractError, "target row order"):
            s.score(layout, submission, targets.__getitem__)

    def test_layout_hash_is_not_substitute_for_official_session_binding(self):
        _, layout, submission, targets = fixture()
        layout["runs"][0]["session"] = "S7"
        layout["packet_id"] = s.digest({k: layout[k] for k in ("schema", "runs")})
        submission["packet_id"] = layout["packet_id"]
        with self.assertRaisesRegex(s.ContractError, "session join"):
            s.score(layout, submission, targets.__getitem__)

    def test_native_clock_prefix_guard_and_masks(self):
        metadata, _, _, _ = fixture()
        mutations = [
            lambda x: x[0]["time_s"].__setitem__(100, 100.),
            lambda x: x[0]["eval_mask"].__setitem__(0, 1),
            lambda x: x[0]["eval_mask"].__setitem__(slice(600, None), [False] * len(x[0]["eval_mask"][600:])),
            lambda x: x[0]["trial"].__setitem__(slice(500, 550), [3] * 50),
            lambda x: x[0]["trial"].__setitem__(slice(499, 500), [2]),
            lambda x: x.reverse(),
        ]
        for mutation in mutations:
            bad = copy.deepcopy(metadata)
            mutation(bad)
            with self.assertRaises(s.ContractError):
                s.make_layout(bad)
        bad = copy.deepcopy(metadata)
        bad[0]["trial"] = [1] * 500 + [2] * 50 + [3] * (len(bad[0]["trial"]) - 550)
        with self.assertRaisesRegex(s.ContractError, "receptive fields"):
            s.make_layout(bad)

    def test_overflow_and_underflow_never_make_a_score(self):
        for target, prediction in [
            ([[0.] * 7, [1.] * 7], [[1e308] * 7, [1e308] * 7]),
            ([[0.] * 7, [1e-300] * 7], [[0.] * 7, [0.] * 7]),
        ]:
            with self.assertRaises(s.ContractError):
                s.variance_weighted_r2(target, prediction)

    def test_cli_and_strict_json(self):
        _, layout, submission, targets = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, data in (("layout", layout), ("submission", submission), ("targets", targets)):
                (root / f"{filename}.json").write_text(json.dumps(data))
            output = root / "result.json"
            cmd = [sys.executable, "-I", "-B", str(Path(__file__).with_name("scorer.py")),
                   "--layout", str(root / "layout.json"), "--submission", str(root / "submission.json"),
                   "--targets", str(root / "targets.json"), "--output", str(output)]
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(output.read_text())["status"], "scored")
            (root / "duplicate.json").write_text('{"contexts":{},"contexts":{}}')
            with self.assertRaisesRegex(s.ContractError, "Duplicate JSON"):
                s.read_json(root / "duplicate.json")
            # Missing context must fail before even trying to open absent targets.
            submission["contexts"].pop(next(iter(submission["contexts"])))
            (root / "submission.json").write_text(json.dumps(submission))
            (root / "targets.json").unlink()
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("84 contexts", run.stderr)
            self.assertNotIn("FileNotFoundError", run.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
