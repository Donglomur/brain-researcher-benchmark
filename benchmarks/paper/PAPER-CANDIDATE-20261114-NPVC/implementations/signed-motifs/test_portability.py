"""New relocation/source-distribution checks; no old numerical suite replay."""
from pathlib import Path
import copy
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


def validate_root(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("ordinary source directory required")
    descriptor = root / "SOURCE.json"
    if descriptor.is_symlink() or not descriptor.is_file():
        raise ValueError("ordinary source manifest required")
    source = json.loads(descriptor.read_bytes())
    names = [x["path"] for x in source["files"]]
    if any(type(n) is not str or Path(n).name != n or n in (".", "..", "SOURCE.json") for n in names):
        raise ValueError("source members must be unique basenames")
    if len(set(names)) != len(names):
        raise ValueError("duplicate source member")
    if {p.name for p in root.iterdir()} != set(names) | {"SOURCE.json"}:
        raise ValueError("complete source namespace mismatch")
    for member in source["files"]:
        path = root / member["path"]
        if path.is_symlink() or not path.is_file():
            raise ValueError("ordinary source member required")
        raw = path.read_bytes()
        if (len(raw), hashlib.sha256(raw).hexdigest()) != (member["bytes"], member["sha256"]):
            raise ValueError("source member changed")
        if raw != ("\n".join(line.rstrip() for line in raw.decode().splitlines()).rstrip() + "\n").encode():
            raise ValueError("source whitespace changed")
        for forbidden in (b"/" + b"Users/", b"benchmark-" + b"engineering-evidence", b"remaining-" + b"builds-wave40"):
            if forbidden in raw:
                raise ValueError("private source path in public member")
    return source


def fixture(package):
    spec = importlib.util.spec_from_file_location("npvc_generated_fixture", package / "test_motifs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    manifest, rows = mod.inputs()  # Generated fixture factory only, no unittest execution.
    second = copy.deepcopy(manifest["cases"][0])
    second.update(case_id="generated_second", session_id="generated_second_session",
                  projection="unlabeled", outcome="incorrect")
    manifest["cases"].append(second)
    more = copy.deepcopy(rows)
    for row in more:
        row["case_id"] = "generated_second"
    return manifest, rows + more


class Portable(unittest.TestCase):
    def invoke(self, package, work, name="report.json"):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        return subprocess.run([sys.executable, "-I", "-S", "-B", str(package / "motifs.py"),
                               "--manifest", str(work / "manifest.json"),
                               "--records", str(work / "records.jsonl"),
                               "--output", str(work / name)], cwd=work, env=env,
                              capture_output=True, timeout=20)

    def test_complete_public_distribution(self):
        source = validate_root(ROOT)
        self.assertFalse(source["authentic_data_included"])
        self.assertFalse(source["scientific_runtime_qualified"])
        self.assertEqual(source["new_benchmark_count"], 0)
        spec = json.loads((ROOT / "SPEC.json").read_bytes())
        self.assertEqual(spec["runtime"]["third_party_dependencies"], [])
        self.assertFalse(spec["ready_to_run_authentic_benchmark"])
        self.assertFalse(spec["historical_reproduction_established"])

    def test_relocated_cli_preserves_all_supplied_cases_and_holds(self):
        with tempfile.TemporaryDirectory(prefix="npvc relocated ") as td:
            work = Path(td); package = work / "standalone package"
            shutil.copytree(ROOT, package)
            validate_root(package)
            manifest, rows = fixture(package)
            mb = json.dumps(manifest).encode()
            rb = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
            (work / "manifest.json").write_bytes(mb)
            (work / "records.jsonl").write_bytes(rb)
            result = self.invoke(package, work)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report_raw = (work / "report.json").read_bytes()
            report = json.loads(report_raw)
            self.assertEqual([x["case"]["case_id"] for x in report["cases"]], [x["case_id"] for x in manifest["cases"]])
            self.assertTrue(all([s["shuffle_id"] for s in c["shuffles"]] == manifest["shuffle_ids"] for c in report["cases"]))
            self.assertEqual(report["input_custody"]["manifest_sha256"], hashlib.sha256(mb).hexdigest())
            self.assertEqual(report["input_custody"]["records_sha256"], hashlib.sha256(rb).hexdigest())
            for field in ("authentic_population_verified", "historical_reproduction_established", "pair_classification_validated"):
                self.assertFalse(report[field])
            self.assertIsNone(report["numerical_pass"])
            self.assertIsNone(report["bootstrap_confidence_intervals"])
            again = self.invoke(package, work)
            self.assertEqual(again.returncode, 2)
            self.assertIn(b"fresh output", again.stderr)
            self.assertEqual((work / "report.json").read_bytes(), report_raw)
            (work / "records.jsonl").write_text("\n".join(json.dumps(row) for row in rows[:-1]) + "\n")
            refused = self.invoke(package, work, "missing.json")
            self.assertEqual(refused.returncode, 2)
            self.assertIn(b"missing prescribed shuffle", refused.stderr)
            self.assertFalse((work / "missing.json").exists())

    def test_distribution_refuses_changed_source_before_import(self):
        with tempfile.TemporaryDirectory(prefix="npvc mutated ") as td:
            package = Path(td) / "package"; shutil.copytree(ROOT, package)
            original = (package / "motifs.py").read_bytes()
            (package / "motifs.py").write_bytes(original + b"# altered\n")
            with self.assertRaisesRegex(ValueError, "source member changed"):
                validate_root(package)
            (package / "motifs.py").write_bytes(original)
            (package / "unexpected.txt").write_text("generated only\n")
            with self.assertRaisesRegex(ValueError, "namespace"):
                validate_root(package)

    def test_runtime_has_no_private_or_third_party_dependency(self):
        # Load only the relocated runtime body: source docs/tests are not dependencies.
        with tempfile.TemporaryDirectory(prefix="npvc bare ") as td:
            work = Path(td)
            shutil.copyfile(ROOT / "motifs.py", work / "motifs.py")
            result = subprocess.run([sys.executable, "-I", "-S", "-B", str(work / "motifs.py"), "--help"],
                                    cwd=work, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertIn(b"--manifest", result.stdout)
            manifest, rows = fixture(ROOT)
            (work / "manifest.json").write_text(json.dumps(manifest))
            (work / "records.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            completed = self.invoke(work, work)
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())
            report = json.loads((work / "report.json").read_bytes())
            self.assertEqual(len(report["cases"]), len(manifest["cases"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
