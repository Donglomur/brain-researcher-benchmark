"""Generated complete-panel callback controls; no authentic target reads."""
import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("n068_capture_scorer", Path(__file__).with_name("scorer.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    metadata = []
    for run, _ in s.RUNS:
        metadata.append({"run": run, "source_sha256": "a" * 64,
                         "time_s": [i * .02 for i in range(603)],
                         "trial": [1] * 500 + [2] * 100 + [3] * 3,
                         "eval_mask": [True] * 602 + [False]})
    layout = s.make_layout(metadata)
    targets, contexts = {}, {}
    for index, row in enumerate(layout["runs"]):
        value = (index % 2) * 10. * (1 + index // 2)
        targets[row["run"]] = {"row_ids": list(row["row_ids"]),
                               "targets": [[value] * 7 for _ in row["row_ids"]]}
        for arm in s.ARMS:
            for budget in s.BUDGETS:
                error = {0: 1., 5: .5, 10: 0.}[budget] if arm == "neural_clock" else 2.
                values = [[value + error] * 7 for _ in row["row_ids"]]
                values[-1] = [987654.] * 7
                contexts[s.context_id(row["run"], arm, budget)] = {
                    "row_ids": list(row["row_ids"]), "predictions": values}
    return layout, {"schema": s.VERSION, "packet_id": layout["packet_id"], "contexts": contexts}, targets


def reused_loader(targets):
    # Reuse each inner row as well as the outer container, as a streaming
    # decoder may do. Replacing rows would leave the old row references intact.
    buffer = {"row_ids": [], "targets": [[0.] * 7 for _ in range(3)]}
    seen = []

    def load(run):
        seen.append(run)
        buffer["row_ids"][:] = targets[run]["row_ids"]
        for output, values in zip(buffer["targets"], targets[run]["targets"]):
            output[:] = values
        return buffer

    return load, seen


class TargetCaptureTests(unittest.TestCase):
    def test_exporter_dependency_pin_loads_current_scorer(self):
        path = Path(__file__).with_name("export_layout.py")
        binding = importlib.util.spec_from_file_location("n068_capture_exporter", path)
        exporter = importlib.util.module_from_spec(binding)
        binding.loader.exec_module(exporter)
        module = exporter.scorer_module(Path(__file__).with_name("scorer.py"),
                                        exporter.ReadBudget(100000))
        self.assertEqual(module.VERSION, s.VERSION)

    def test_reused_inner_rows_preserve_complete_session_scores(self):
        layout, submission, targets = fixture()
        untouched = copy.deepcopy((layout, submission, targets))
        expected = s.score(layout, submission, targets.__getitem__)
        loader, seen = reused_loader(targets)
        actual = s.score(layout, submission, loader)
        self.assertEqual(actual, expected)
        self.assertEqual(actual["status"], "scored")
        # Two constant runs at 0 and 10*k have pooled variance25*k².
        closed_form = sum(1. / (25 * k * k) for k in range(1, 8)) / 7
        self.assertAlmostEqual(actual["primary"]["10"], closed_form)
        self.assertEqual(actual["contexts"], 84)
        self.assertEqual(actual["full_rows"] - actual["scored_rows"], 14)
        self.assertEqual(seen, [run for run, _ in s.RUNS])
        self.assertEqual((layout, submission, targets), untouched)

    def test_constant_session_remains_undefined_without_losing_other_targets(self):
        layout, submission, targets = fixture()
        for run, _ in s.RUNS[:2]:
            targets[run]["targets"] = [[.1] * 7 for _ in range(3)]
        loader, _ = reused_loader(targets)
        actual = s.score(layout, submission, loader)
        self.assertEqual(actual, s.score(layout, submission, targets.__getitem__))
        self.assertEqual(actual["constant_target_sessions"], ["S6"])
        self.assertIsNone(actual["primary"])
        self.assertEqual(len(actual["by_session"]), 7)

    def test_incomplete_submission_still_fails_before_target_callback(self):
        layout, submission, targets = fixture()
        submission["contexts"].pop(next(iter(submission["contexts"])))
        loader, seen = reused_loader(targets)
        with self.assertRaises(s.ContractError):
            s.score(layout, submission, loader)
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
