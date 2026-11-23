"""Invented complete-shape controls, without authentic observations or model runs."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paired = load("poyo_pair_test", HERE / "compare.py")
generated = load("poyo_protected_fixtures", HERE.parent / "protected-grid-evaluator" / "test_protection.py")
encode = generated.old.encode
pin = generated.old.pin


class PairedTests(unittest.TestCase):
    def run_pair(self, d, first, second, targets, calls):
        body = encode(d)
        return paired.evaluate_pair(body, pin(body), encode(first), encode(second),
                                    lambda: calls.append("private") or encode(targets))

    def test_both_complete_public_grids_precede_private_loader(self):
        d, p, t = generated.fixture()
        mutations = (
            lambda x: x["results"].pop(),
            lambda x: x["results"][-1]["rows"][-1].update(values=[True, 0]),
            lambda x: x["results"][-1]["rows"][-1].update(row_id="wrong"),
            lambda x: x["results"][-1].update(session_id="unlisted-session"),
        )
        for index in (0, 1):
            for mutation in mutations:
                with self.subTest(condition=index, mutation=mutation):
                    arms = [copy.deepcopy(p), copy.deepcopy(p)]
                    mutation(arms[index])
                    calls = []
                    with self.assertRaises(ValueError):
                        self.run_pair(d, *arms, t, calls)
                    self.assertEqual(calls, [])

    def test_global_support_conflict_precedes_private_loader(self):
        d, p, t = generated.fixture()
        d["cases"][2]["adaptation_trials"][0] = "test"
        for row in d["cases"][2]["rows"]:
            row["trial_id"] = "other-test"
            row["timestamp"] += 100
        calls = []
        with self.assertRaisesRegex(ValueError, "cross-budget adaptation"):
            self.run_pair(d, p, p, t, calls)
        self.assertEqual(calls, [])

    def test_one_target_snapshot_and_unchanged_full_arm_reports(self):
        d, first, t = generated.fixture()
        second = copy.deepcopy(first)
        for result in second["results"]:
            if result["method"] == "pretrained" and result["session_id"] == "s156":
                for row in result["rows"]:
                    row["values"] = [value * 2 for value in row["values"]]
        calls = []
        result = self.run_pair(d, first, second, t, calls)
        self.assertEqual(calls, ["private"])
        body = encode(d)
        for name, submission in zip(paired.CONDITIONS, (first, second)):
            expected = paired.scorer.evaluate(body, pin(body), encode(submission), lambda: encode(t))
            self.assertEqual(result["conditions"][name], expected)
        self.assertEqual(len(result["session_differences"]), 16)
        changed = [r for r in result["session_differences"]
                   if r["method"] == "pretrained" and r["session_id"] == "s156"]
        self.assertEqual([r["r2_difference"] for r in changed], [-1.0, -1.0])
        self.assertEqual([r["dimension_r2_differences"] for r in changed], [[-1.0, -1.0]] * 2)
        overall = [r for r in result["summary_differences"]
                   if r["method"] == "pretrained" and r["group"] == "all"]
        self.assertEqual([r["session_macro_r2_difference"] for r in overall], [-0.5, -0.5])
        for key in ("scientific_qualification", "historical_reproduction", "input_provenance_verified",
                    "condition_isolation_verified", "independent_authorship_verified", "matched_resource_budgets_verified"):
            self.assertIs(result[key], False)

    def test_exact_operand_identities_include_representation(self):
        d, p, t = generated.fixture()
        db, pb, tb = encode(d), encode(p), encode(t)
        second = json.dumps(p, indent=2).encode()
        out = paired.evaluate_pair(db, pin(db), pb, second, lambda: tb)
        self.assertEqual(out["design_identity"], pin(db))
        self.assertEqual(out["target_identity"], pin(tb))
        self.assertEqual(out["prediction_identities"], dict(zip(paired.CONDITIONS, (pin(pb), pin(second)))))
        self.assertNotEqual(pin(pb), pin(second))
        self.assertTrue(all(r["r2_difference"] == 0 for r in out["session_differences"]))

    def test_invalid_private_snapshot_is_loaded_once_and_refused(self):
        d, p, t = generated.fixture()
        t["cases"][-1]["rows"][-1]["values"][0] += 1
        calls = []
        with self.assertRaisesRegex(ValueError, "stitched target mismatch"):
            self.run_pair(d, p, p, t, calls)
        self.assertEqual(calls, ["private"])
        body = encode(d)
        with self.assertRaisesRegex(ValueError, "shared target snapshot"):
            paired.evaluate_pair(body, pin(body), encode(p), encode(p), lambda: bytearray(encode(t)))

    def test_cli_valid_pair_and_public_refusal_before_missing_targets(self):
        d, p, t = generated.fixture()
        db, pb, tb = encode(d), encode(p), encode(t)
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for name, body in (("design.json", db), ("first.json", pb), ("second.json", pb), ("targets.json", tb)):
                (root / name).write_bytes(body)
            output = root / "report.json"
            command = [sys.executable, "-I", "-S", "-B", str(HERE / "compare.py"),
                       "--design", str(root / "design.json"), "--design-bytes", str(len(db)),
                       "--design-sha256", pin(db)["sha256"], "--paper-data", str(root / "first.json"),
                       "--paper-data-author-code", str(root / "second.json"),
                       "--targets", str(root / "targets.json"), "--targets-bytes", str(len(tb)),
                       "--targets-sha256", pin(tb)["sha256"], "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, timeout=15)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            report = json.loads(output.read_bytes())
            self.assertEqual(report["external_target_loads"], 1)
            self.assertEqual(report["target_identity"], pin(tb))
            output.unlink()
            (root / "targets.json").unlink()
            p["results"].pop()
            (root / "second.json").write_bytes(encode(p))
            failed = subprocess.run(command, capture_output=True, timeout=15)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(b"missing complete methods", failed.stderr)
            self.assertNotIn(b"FileNotFoundError", failed.stderr)
            self.assertFalse(output.exists())

    def test_changed_scorer_is_not_imported(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            component = root / "paired-grid-evaluator"
            dependency = root / "protected-grid-evaluator"
            component.mkdir(); dependency.mkdir()
            (component / "compare.py").write_bytes((HERE / "compare.py").read_bytes())
            (dependency / "evaluator.py").write_text("raise RuntimeError('changed source executed')\n")
            with self.assertRaisesRegex(ValueError, "protected scorer source differs"):
                load("poyo_changed_dependency", component / "compare.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
