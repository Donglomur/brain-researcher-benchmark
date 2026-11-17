"""Distinct portable interface checks; no original source or neural body needed."""
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


class PortableInterface(unittest.TestCase):
    def test_complete_manifest_and_declared_originals(self):
        manifest = json.loads((ROOT / "SOURCE_MANIFEST.json").read_bytes())
        expected = {v["path"] for v in manifest["files"]} | {"SOURCE_MANIFEST.json"}
        self.assertEqual({p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()}, expected)
        self.assertEqual(len(expected), len(manifest["files"]) + 1)
        for row in manifest["files"]:
            p = ROOT / row["path"]
            self.assertFalse(p.is_symlink())
            raw = p.read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row["bytes"], row["sha256"]))
            self.assertNotIn(b"/" + b"Users/", raw)
            self.assertNotIn(b"benchmark-" + b"engineering-evidence", raw)
            self.assertEqual(raw, ("\n".join(x.rstrip() for x in raw.decode().splitlines()).rstrip() + "\n").encode())
        spec = json.loads((ROOT / "SPEC.json").read_bytes())
        self.assertFalse(spec["ready_to_run_authentic_benchmark"])
        self.assertFalse(spec["native_reference_qualified"])
        self.assertFalse(spec["candidate_execution_verified"])
        self.assertEqual(spec["new_benchmark_count"], 0)
        self.assertEqual(spec["runtime"]["third_party_packages"], [])
        loader = importlib.util.spec_from_file_location("owned_consensus_correction", ROOT / "correct_sources.py")
        c = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(c)
        inputs = json.loads((ROOT / "SOURCE_INPUTS.json").read_bytes())
        self.assertEqual(inputs["revision"], c.REVISION)
        self.assertFalse(inputs["bodies_supplied"])
        self.assertFalse(inputs["redistribution_authorized"])
        self.assertEqual(set(inputs["source_roles"]), set(c.SOURCES))
        for role, row in inputs["source_roles"].items():
            path, size, sha, start, end, branch_sha = c.SOURCES[role]
            self.assertEqual((row["destination"], row["bytes"], row["sha256"],
                              row["branch_start"], row["branch_end"], row["branch_sha256"]),
                             (path, size, sha, start, end, branch_sha))
            self.assertEqual(row["branch_bytes"], end - start)

    def invoke(self, args, cwd, supplied_root=None):
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "PYTHONHOME", "CONSENSUS_SOURCE_ROOT")}
        if supplied_root is not None:
            env["CONSENSUS_SOURCE_ROOT"] = str(supplied_root)
        return subprocess.run([sys.executable, "-I", "-S", "-B", *map(str, args)],
                              cwd=cwd, env=env, capture_output=True, timeout=20)

    def test_relocated_real_cli_refuses_wrong_complete_preimages(self):
        with tempfile.TemporaryDirectory(prefix="consensus public relocation ") as td:
            work = Path(td)
            package = work / "standalone source"
            shutil.copytree(ROOT, package)
            result = self.invoke([package / "correct_sources.py", "--help"], work)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertIn(b"--analysis-source", result.stdout)
            inputs = json.loads((package / "SOURCE_INPUTS.json").read_bytes())
            command = [package / "correct_sources.py"]
            for role in ("fit", "analyze", "analysis"):
                row = inputs["source_roles"][role]
                generated = work / (role + " invented source")
                generated.write_bytes(b"x" * row["bytes"])
                self.assertNotEqual(hashlib.sha256(generated.read_bytes()).hexdigest(), row["sha256"])
                command.extend(["--" + role + "-source", generated])
            output = work / "must not exist"
            command.extend(["--output", output])
            result = self.invoke(command, work)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"fit: exact original identity required", result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(any(p.name == "CORRECTION_REPORT.json" for p in work.rglob("*")))

    def test_relocated_owner_integration_absence_is_explicit_not_success(self):
        with tempfile.TemporaryDirectory(prefix="consensus source availability ") as td:
            work = Path(td)
            package = work / "standalone source"
            shutil.copytree(ROOT, package)
            command = [package / "test_correction.py", "OwnerSourceIntegration"]
            absent = self.invoke(command, work)
            self.assertEqual(absent.returncode, 0, absent.stderr.decode())
            self.assertIn(b"owner-supplied pinned upstream sources absent", absent.stderr)
            self.assertIn(b"skipped", absent.stderr)
            empty = work / "owner declared empty tree"
            empty.mkdir()
            supplied = self.invoke(command, work, supplied_root=empty)
            self.assertNotEqual(supplied.returncode, 0)
            self.assertIn(b"FileNotFoundError", supplied.stderr)
            self.assertNotIn(b"skipped", supplied.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
