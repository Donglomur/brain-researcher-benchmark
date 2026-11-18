"""Portable source and real relocated CLI checks over invented inputs only."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


def module(path):
    spec = importlib.util.spec_from_file_location("portable_generated_fixture", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class PortableSource(unittest.TestCase):
    def test_source_ordered_pupil_selection_controls(self):
        fixture_module = module(ROOT / "test_evaluate.py")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            fixture_module.PupilSelection)
        result = unittest.TestResult()
        suite.run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertFalse(result.skipped)

    def test_complete_inventory_and_claims(self):
        inventory = json.loads((ROOT / "SOURCE_MANIFEST.json").read_bytes())
        expected = {r["path"] for r in inventory["files"]} | {"SOURCE_MANIFEST.json"}
        self.assertEqual({p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()}, expected)
        self.assertEqual(len(expected), len(inventory["files"]) + 1)
        for row in inventory["files"]:
            path = ROOT / row["path"]
            self.assertFalse(path.is_symlink())
            raw = path.read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row["bytes"], row["sha256"]))
            self.assertNotIn(b"/" + b"Users/", raw)
            self.assertNotIn(b"benchmark-" + b"engineering-evidence", raw)
            self.assertEqual(raw, ("\n".join(x.rstrip() for x in raw.decode().splitlines()).rstrip() + "\n").encode())
        spec = json.loads((ROOT / "SPEC.json").read_bytes())
        self.assertFalse(spec["ready_to_run_authentic_benchmark"])
        self.assertFalse(spec["candidate_execution_verified"])
        self.assertFalse(spec["native_reference_qualified"])
        self.assertEqual(spec["runtime"]["third_party_packages"], [])

    def invoke(self, argv, cwd):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        return subprocess.run([sys.executable, "-I", "-S", "-B", *map(str, argv)],
                              cwd=cwd, env=env, capture_output=True, timeout=25)

    def test_relocated_complete_descriptive_cli_and_runtime_config(self):
        with tempfile.TemporaryDirectory(prefix="pcca public relocated ") as td:
            work = Path(td)
            package = work / "standalone source"
            shutil.copytree(ROOT, package)
            f = module(package / "test_evaluate.py")
            support, rows = f.fixture()
            (work / "support.json").write_bytes(support)
            f.write(work / "candidate.jsonl", rows)
            f.write(work / "reference.jsonl", rows)
            command = [package / "evaluate.py", "--support", work / "support.json",
                       "--candidate", work / "candidate.jsonl", "--reference", work / "reference.jsonl",
                       "--output", work / "report.json"]
            result = self.invoke(command, work)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report = json.loads((work / "report.json").read_bytes())
            self.assertEqual((len(report["models"]), len(report["pupil_r2"]), len(report["pairs"])), (42, 41, 552))
            self.assertEqual(report["aggregates"]["pooled"]["P03"]["means"]["across"], 1)
            self.assertEqual(report["aggregates"]["pooled"]["P04"]["means"]["across"], .75)
            self.assertIsNone(report["numerical_pass"])
            self.assertTrue(report["reference_present"])
            self.assertTrue(all(v == 0 for r in report["reference_absolute_differences"]["pupil"].values() for g in r.values() for v in g.values()))
            for role in ("candidate", "reference"):
                with self.subTest(role=role):
                    f.write(work / (role + ".jsonl"), rows[:-1])
                    failed = list(command)
                    failed[-1] = work / (role + "-refused.json")
                    result = self.invoke(failed, work)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(b"missing record", result.stderr)
                    self.assertFalse(Path(failed[-1]).exists())
                    f.write(work / (role + ".jsonl"), rows)
            # The companion roster really is required from the relocated package.
            (package / "ROSTER.json").rename(package / "ROSTER.absent")
            failed = list(command)
            failed[-1] = work / "config-refused.json"
            result = self.invoke(failed, work)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"ROSTER.json", result.stderr)
            self.assertFalse(Path(failed[-1]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
