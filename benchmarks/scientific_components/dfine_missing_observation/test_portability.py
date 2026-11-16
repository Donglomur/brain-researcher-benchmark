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

    def test_relocated_complete_cli_and_private_target_order(self):
        with tempfile.TemporaryDirectory(prefix="dfine public relocated ") as td:
            work = Path(td)
            package = work / "standalone source"
            shutil.copytree(ROOT, package)
            f = module(package / "test_scorer.py")
            profile, candidate, reference, targets = f.fixture()
            for name, value in (("profile", profile), ("candidate", candidate), ("reference", reference), ("targets", targets)):
                (work / (name + ".json")).write_bytes(f.s.json_bytes(value))
            profile_hash = hashlib.sha256((work / "profile.json").read_bytes()).hexdigest()
            command = [package / "scorer.py", "--profile", work / "profile.json", "--profile-sha256", profile_hash,
                       "--candidate", work / "candidate.json", "--reference", work / "reference.json",
                       "--private-targets", work / "targets.json", "--output", work / "report.json"]
            result = self.invoke(command, work)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report = json.loads((work / "report.json").read_bytes())
            self.assertEqual(report["declared_prediction_cells"], 595)
            self.assertEqual(len(report["curves"]), 17)
            self.assertTrue(all(abs(r["candidate_cc"] - 1) < 1e-14 and r["reference_cc"] == 0 for r in report["curves"]))
            self.assertIsNone(report["overall_scalar"])
            self.assertFalse(report["claims"]["scientific_qualification"])
            # A missing target would raise FileNotFoundError if opened early.
            (work / "targets.json").unlink()
            for role, full in (("candidate", candidate), ("reference", reference)):
                with self.subTest(role=role):
                    (work / (role + ".json")).write_bytes(f.s.json_bytes(full[:-1]))
                    failed = list(command)
                    failed[-1] = work / (role + "-refused.json")
                    result = self.invoke(failed, work)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"incomplete prediction population", result.stderr)
                    self.assertNotIn(b"FileNotFoundError", result.stderr)
                    self.assertFalse(Path(failed[-1]).exists())
                    (work / (role + ".json")).write_bytes(f.s.json_bytes(full))
            failed = list(command)
            failed[4] = "0" * 64
            failed[-1] = work / "hash-refused.json"
            result = self.invoke(failed, work)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"owner-profile identity mismatch", result.stderr)
            self.assertFalse(Path(failed[-1]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
