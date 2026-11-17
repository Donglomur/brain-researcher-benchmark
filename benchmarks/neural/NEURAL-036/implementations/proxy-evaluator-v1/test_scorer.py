"""Generated software controls; no authentic observations or target access."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("proxy_scorer", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def fixture():
    folds = {str(f): [format(10 * f + i, "064x") for i in range(10)] for f in range(7)}
    support = {"task_id": "NEURAL-036", "folds": folds}
    targets = {"task_id": "NEURAL-036", "targets": {
        q: {"target": 0, "persistence": .125} for ids in folds.values() for q in ids}}
    values = {"joint": .25, "history": 1, "reverse": .5, "shift": .75}
    submission = {"task_id": "NEURAL-036", "predictions": [
        {"fold": f, "arm": a, "id": q, "fraction": values[a]}
        for f, ids in folds.items() for a in values for q in ids]}
    return submission, support, targets


class Metrics(unittest.TestCase):
    def test_current_primary_is_learned_history_not_fixed_persistence(self):
        result = scorer.score(*fixture())
        self.assertEqual(result["primary"]["name"], scorer.PRIMARY)
        self.assertEqual(result["primary"]["estimate"], .75)
        self.assertEqual(result["primary"]["pointwise_descriptive_bootstrap95"], [.75, .75])
        self.assertEqual(result["contrasts"]["persistence_minus_joint"]["estimate"], -.125)
        self.assertEqual(result["mouse_macro_mae"], {"joint": .25, "history": 1, "reverse": .5, "shift": .75})
        self.assertEqual((result["mice"], result["sessions"], result["queries"], result["predictions"]), (7, 14, 70, 280))

    def test_session_then_equal_mouse_means_and_paired_bootstrap(self):
        submission, support, targets = fixture()
        # One mouse differs; its first session has error one, second error zero.
        for row in submission["predictions"]:
            row["fraction"] = int(row["fold"] == "0" and row["id"] in support["folds"]["0"][:5]
                                  and row["arm"] in ("history", "reverse"))
        result = scorer.score(submission, support, targets)
        self.assertEqual(result["per_mouse"][0]["sessions"][0]["mae"]["history"], 1)
        self.assertEqual(result["per_mouse"][0]["sessions"][1]["mae"]["history"], 0)
        self.assertEqual(result["per_mouse"][0]["history_minus_joint"], .5)
        self.assertEqual(result["primary"]["estimate"], 1 / 14)
        # With one nonzero mouse, each draw is .5*Binomial(7,1/7)/7.
        # The 2.5/97.5 percentiles are zero and three selected copies.
        self.assertEqual(result["primary"]["pointwise_descriptive_bootstrap95"], [0, 3 / 14])
        self.assertEqual(result["contrasts"]["history_minus_joint"], result["contrasts"]["reverse_minus_joint"])

    def test_valid_constants_endpoints_negative_gain_and_order_independence(self):
        submission, support, targets = fixture()
        for row in submission["predictions"]:
            row["fraction"] = int(row["arm"] == "joint")
        original = scorer.score(submission, support, targets)
        self.assertEqual(original["primary"]["estimate"], -1)
        self.assertIsNone(original["acceptance_threshold"])
        submission["predictions"].reverse()
        self.assertEqual(scorer.score(submission, support, targets), original)

    def test_linear_percentile(self):
        self.assertEqual(scorer.percentile([0, 4, 1, 3], .25), .75)


class Admission(unittest.TestCase):
    def test_support_rejects_cross_mouse_overlap_and_wrong_folds(self):
        _, support, _ = fixture()
        for mutate in (
            lambda s: s["folds"]["1"].__setitem__(0, s["folds"]["0"][0]),
            lambda s: s["folds"].__setitem__("7", s["folds"].pop("6")),
            lambda s: s["folds"]["0"].pop(),
            lambda s: s["folds"]["0"].__setitem__(0, "not-an-opaque-id"),
            lambda s: s.__setitem__("task_id", "NEURAL-035"),
        ):
            bad = copy.deepcopy(support)
            mutate(bad)
            with self.subTest(support=bad), self.assertRaises(scorer.ContractError):
                scorer.validate_support(bad)

    def test_malformed_predictions(self):
        submission, support, _ = fixture()
        expected = scorer.validate_support(support)
        mutations = [
            lambda s: s["predictions"].pop(),
            lambda s: s["predictions"].__setitem__(0, s["predictions"][1]),
            lambda s: s["predictions"][0].__setitem__("arm", "persistence"),
            lambda s: s["predictions"][0].__setitem__("fold", 0),
            lambda s: s["predictions"][0].__setitem__("id", "f" * 64),
            lambda s: s["predictions"][0].__setitem__("target", 0),
        ]
        for value in (True, False, "0.5", None, -0.01, 1.01, float("nan"), float("inf"), 10**500):
            mutations.append(lambda s, value=value: s["predictions"][0].__setitem__("fraction", value))
        for index, mutate in enumerate(mutations):
            bad = copy.deepcopy(submission)
            mutate(bad)
            with self.subTest(index=index), self.assertRaises(scorer.ContractError):
                scorer.validate_submission(bad, expected)

    def test_targets_reject_missing_extra_or_invalid_rows(self):
        _, support, targets = fixture()
        q = support["folds"]["0"][0]
        for mutate in (
            lambda t: t["targets"].pop(q),
            lambda t: t["targets"].__setitem__("f" * 64, {"target": 0, "persistence": 0}),
            lambda t: t["targets"][q].__setitem__("target", True),
            lambda t: t["targets"][q].__setitem__("persistence", 2),
        ):
            bad = copy.deepcopy(targets)
            mutate(bad)
            with self.assertRaises(scorer.ContractError):
                scorer.validate_targets(bad, support)

    def test_strict_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(scorer.ContractError):
                scorer.strict_json(raw)


class FileBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS /var is a symlink; use the actual directory for strict path I/O.
        self.root = Path(self.temp.name).resolve()
        self.submission, self.support, self.targets = fixture()

    def write(self, name, obj):
        raw = json.dumps(obj).encode()
        path = self.root / name
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def arguments(self):
        submission, _ = self.write("submission.json", self.submission)
        support, support_hash = self.write("support.json", self.support)
        targets, targets_hash = self.write("targets.json", self.targets)
        return [submission, support, support_hash, targets, targets_hash]

    def test_last_row_failure_never_opens_targets(self):
        self.submission["predictions"][-1]["fraction"] = 2
        args = self.arguments()
        original = scorer.read_json
        paths = []
        def observed(path, *a, **kw):
            paths.append(Path(path))
            if Path(path) == args[3]:
                raise AssertionError("numeric target read before complete admission")
            return original(path, *a, **kw)
        with patch.object(scorer, "read_json", side_effect=observed):
            result = scorer.evaluate(*args)
        self.assertEqual(result["status"], "invalid_submission")
        self.assertEqual(paths, [args[0], args[1]])

    def test_operator_errors_are_distinct_from_invalid_submission(self):
        args = self.arguments()
        args[2] = "0" * 64
        self.assertEqual(scorer.evaluate(*args)["status"], "operator_error")
        args = self.arguments()
        args[4] = "0" * 64
        self.assertEqual(scorer.evaluate(*args)["status"], "operator_error")
        args = self.arguments()
        args[3].unlink()
        self.assertEqual(scorer.evaluate(*args)["status"], "operator_error")
        for pin in (2, 4):
            args = self.arguments()
            args[pin] = None
            self.assertEqual(scorer.evaluate(*args)["status"], "operator_error")

    def test_cli_scores_and_refuses_report_overwrite(self):
        args = self.arguments()
        output = self.root / "report.json"
        argv = [item for pair in zip(("--submission", "--support", "--support-sha256", "--targets", "--targets-sha256"), map(str, args)) for item in pair]
        argv += ["--output", str(output)]
        with patch("builtins.print"):
            self.assertEqual(scorer.main(argv), 0)
        self.assertEqual(json.loads(output.read_text())["primary"]["estimate"], .75)
        saved = output.read_bytes()
        with self.assertRaises(FileExistsError):
            scorer.main(argv)
        self.assertEqual(output.read_bytes(), saved)

    def test_symlinks_and_oversize_inputs_rejected(self):
        path, _ = self.write("small.json", {})
        alias = self.root / "alias.json"
        alias.symlink_to(path)
        with self.assertRaises(scorer.ContractError):
            scorer.read_json(alias, 100)
        with self.assertRaises(scorer.ContractError):
            scorer.read_json(path, 1)


if __name__ == "__main__":
    unittest.main()
