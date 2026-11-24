"""Generated complete-panel comparisons; no authentic data or participant execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("neural068_access", Path(__file__).with_name("compare_access.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
s = c.scorer
WRITTEN = 0


def fixture():
    metadata = []
    for index, (run, _) in enumerate(s.RUNS):
        count = 2 + (index // 2) % 3
        n = 600 + count + 1
        metadata.append({"run": run, "source_sha256": "a" * 64,
                         "time_s": [i * .02 for i in range(n)],
                         "trial": [1] * 500 + [2] * 100 + [3] * (count + 1),
                         "eval_mask": [True] * (n - 1) + [False]})
    layout = s.make_layout(metadata)
    targets, direct, program = {}, {}, {}
    for index, row in enumerate(layout["runs"]):
        value = (index % 2) * 10. * (1 + index // 2)
        targets[row["run"]] = {"row_ids": list(row["row_ids"]),
                               "targets": [[value] * 7 for _ in row["row_ids"]]}
        for arm in s.ARMS:
            for budget in s.BUDGETS:
                key = s.context_id(row["run"], arm, budget)
                for contexts, error in ((direct, 1. if arm == "neural_clock" else 2.),
                                        (program, {0: 2., 5: 1., 10: 0.}[budget]
                                         if arm == "neural_clock" else 2.)):
                    prediction = [[value + error] * 7 for _ in row["row_ids"]]
                    prediction[-1] = [987654.] * 7
                    contexts[key] = {"row_ids": list(row["row_ids"]), "predictions": prediction}
    def submission(contexts):
        return {"schema": s.VERSION, "packet_id": layout["packet_id"], "contexts": contexts}
    return layout, submission(direct), submission(program), targets


class AccessComparisonTests(unittest.TestCase):
    def test_complete_paired_session_contrasts_and_original_endpoints(self):
        layout, direct, program, targets = fixture()
        seen = []
        def loader(run):
            seen.append(run)
            return targets[run]
        before = copy.deepcopy((layout, direct, program, targets))
        result = c.compare(layout, direct, program, loader)
        # Each session pools two constant runs at 0 and 10*k: variance 25*k².
        expected = sum(1 / (25 * k * k) for k in range(1, 8)) / 7
        self.assertEqual(result["status"], "compared")
        self.assertEqual(seen, [run for run, _ in s.RUNS])
        self.assertEqual((layout, direct, program, targets), before)
        self.assertEqual(result["matched_panel"]["contexts_per_condition"], 84)
        self.assertEqual(result["matched_panel"]["biological_participants"], 1)
        self.assertEqual([row["session"] for row in result["by_session"]], list(s.SESSIONS))
        absolute = result["absolute_r2_difference"]["neural_clock"]
        gain = result["recalibration_gain_difference"]["neural_clock"]
        self.assertAlmostEqual(absolute["0"], -3 * expected)
        self.assertAlmostEqual(absolute["5"], 0.)
        self.assertAlmostEqual(absolute["10"], expected)
        self.assertEqual(gain["0"], 0.)
        self.assertAlmostEqual(gain["5"], 3 * expected)
        self.assertAlmostEqual(gain["10"], 4 * expected)
        self.assertAlmostEqual(result["neural_minus_clock_recalibration_gain_difference"]["10"], 4 * expected)
        for name, submission in zip(c.CONDITIONS, (direct, program)):
            self.assertEqual(result["condition_scores"][name], s.score(layout, submission, targets.__getitem__))
        self.assertFalse(result["access_compliance_verified"])
        self.assertFalse(result["scientific_qualification"])

    def test_condition_swap_changes_sign_and_identical_answers_tie(self):
        layout, direct, program, targets = fixture()
        forward = c.compare(layout, direct, program, targets.__getitem__)
        reverse = c.compare(layout, program, direct, targets.__getitem__)
        tie = c.compare(layout, direct, direct, targets.__getitem__)
        for field in ("absolute_r2_difference", "recalibration_gain_difference"):
            for arm in s.ARMS:
                for budget in map(str, s.BUDGETS):
                    self.assertAlmostEqual(reverse[field][arm][budget], -forward[field][arm][budget])
                    self.assertEqual(tie[field][arm][budget], 0.)

    def test_both_complete_submissions_admitted_before_any_target_read(self):
        layout, direct, program, _ = fixture()
        first = next(iter(direct["contexts"]))
        def forbidden(run):
            self.fail("Unadmitted condition reached targets")
        for condition in (0, 1):
            for mutation in (lambda x: x["contexts"].pop(first),
                             lambda x: x.update(packet_id="b" * 64),
                             lambda x: x["contexts"][first]["row_ids"].reverse(),
                             lambda x: x["contexts"][first]["predictions"][0].__setitem__(0, float("nan"))):
                with self.subTest(condition=condition):
                    submissions = copy.deepcopy([direct, program])
                    mutation(submissions[condition])
                    with self.assertRaises(s.ContractError):
                        c.compare(layout, *submissions, forbidden)

    def test_shared_mutable_loader_buffer_cannot_change_other_condition_targets(self):
        layout, direct, program, targets = fixture()
        buffer = {"row_ids": [], "targets": []}
        seen = []
        def loader(run):
            seen.append(run)
            buffer["row_ids"][:] = targets[run]["row_ids"]
            buffer["targets"][:] = copy.deepcopy(targets[run]["targets"])
            return buffer
        actual = c.compare(layout, direct, program, loader)
        self.assertEqual(actual, c.compare(layout, direct, program, targets.__getitem__))
        self.assertEqual(len(seen), 14)

    def test_all_constant_session_retained_and_comparison_undefined(self):
        layout, direct, program, targets = fixture()
        for run, _ in s.RUNS[:2]:
            targets[run]["targets"] = [[.1] * 7 for _ in targets[run]["row_ids"]]
        result = c.compare(layout, direct, program, targets.__getitem__)
        self.assertEqual(result["status"], "undefined_constant_target_session")
        self.assertIsNone(result["recalibration_gain_difference"])
        for score in result["condition_scores"].values():
            self.assertEqual(score["constant_target_sessions"], ["S6"])
            self.assertEqual(len(score["by_session"]), 7)
            self.assertIsNone(score["primary"])

    def test_target_identity_is_not_inferred_from_shape(self):
        layout, direct, program, targets = fixture()
        targets[s.RUNS[-1][0]]["row_ids"].reverse()
        with self.assertRaisesRegex(s.ContractError, "target row order"):
            c.compare(layout, direct, program, targets.__getitem__)

    def test_operator_cli_and_rejection_before_target_file_open(self):
        global WRITTEN
        layout, direct, program, targets = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in (("layout", layout), ("direct", direct), ("program", program), ("targets", targets)):
                raw = json.dumps(data).encode()
                WRITTEN += len(raw)
                (root / (name + ".json")).write_bytes(raw)
            args = [item for name in ("layout", "direct", "program", "targets", "output")
                    for item in ("--" + name, str(root / (name + ".json")))]
            c.main(args)
            WRITTEN += (root / "output.json").stat().st_size
            self.assertEqual(json.loads((root / "output.json").read_text())["status"], "compared")
            (root / "targets.json").unlink()
            program["contexts"].pop(next(iter(program["contexts"])))
            raw = json.dumps(program).encode()
            WRITTEN += len(raw)
            (root / "program.json").write_bytes(raw)
            with self.assertRaisesRegex(s.ContractError, "84 contexts"):
                c.main(args)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        print("GENERATED_WRITE_BYTES=" + str(WRITTEN))
