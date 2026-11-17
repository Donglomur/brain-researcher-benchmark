"""Portable dependency and interface checks; no numerical suite or models here."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
DEPENDENCY = ROOT.parent / "whole-trial-preparation"
CURRENT_SOURCE = Path("benchmarks/integrity/current-closures/input-sbind/CONTINUOUS_NORMALIZATION_SOURCE.json")
CURRENT_DEPENDENCY = Path("benchmarks/integrity/current-closures/input-sbind/WHOLE_TRIAL_SOURCE.json")
ORIGINAL_SOURCE = (1871, "f07a901cf4d8f9ef44d97909dfd6e730cf57c9cd2ad47e96806f9a6c680ca5ea")
DEPENDENCY_SOURCE = (1452, "9110b9ef65bc205e719edd4cfb0d41e5e8edfb6bd6a51a2480ee780a1913e08d")
CURRENT_DEPENDENCY_SOURCE = (1453, "19fe75433f4ac67ee15d16ced4d96d906e37d24195270acf9d85cc753a6d5afb")


def authenticate(root, expected=None):
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise RuntimeError("ordinary component directory required")
    manifest = root / "SOURCE.json"
    if not stat.S_ISREG(manifest.lstat().st_mode):
        raise RuntimeError("ordinary source manifest required")
    raw = manifest.read_bytes()
    original = json.loads(raw)
    original_pin = ORIGINAL_SOURCE if root == ROOT else expected
    if original_pin is not None and (len(raw), hashlib.sha256(raw).hexdigest()) != original_pin:
        raise RuntimeError("original source manifest changed")
    if root == ROOT or root == DEPENDENCY:
        current = ROOT.parents[4] / (CURRENT_SOURCE if root == ROOT else CURRENT_DEPENDENCY)
        if any(p.is_symlink() for p in (current, *current.parents)) or not stat.S_ISREG(current.lstat().st_mode):
            raise RuntimeError("ordinary current source manifest required")
        raw = current.read_bytes()
        if root == DEPENDENCY and (len(raw), hashlib.sha256(raw).hexdigest()) != CURRENT_DEPENDENCY_SOURCE:
            raise RuntimeError("selected current dependency descriptor changed")
    source = json.loads(raw)
    added = {"files", "current_dependencies"} if root == ROOT else {"files"}
    if {k: v for k, v in source.items() if k not in added} != {k: v for k, v in original.items() if k != "files"}:
        raise RuntimeError("historical source metadata changed")
    old_rows = {x["path"]: x for x in original["files"]}
    new_rows = {x["path"]: x for x in source["files"]}
    changed = {"test_numerical_preparation.py", "test_public_delivery.py"} if root == ROOT else {
        "trial_preparation.py", "test_trial_preparation.py", "test_public_delivery.py"}
    if set(old_rows) != set(new_rows) or {name for name in old_rows if old_rows[name] != new_rows[name]} != changed:
        raise RuntimeError("unexpected current source change")
    names = [x["path"] for x in source["files"]]
    if len(names) != len(set(names)) or any(Path(x).name != x for x in names):
        raise RuntimeError("flat unique component names required")
    if {p.name for p in root.iterdir()} != set(names) | {"SOURCE.json"}:
        raise RuntimeError("exact component namespace required")
    for item in source["files"]:
        p = root / item["path"]
        if not stat.S_ISREG(p.lstat().st_mode):
            raise RuntimeError("ordinary source member required")
        body = p.read_bytes()
        if len(body) != item["bytes"] or hashlib.sha256(body).hexdigest() != item["sha256"]:
            raise RuntimeError("selected source member changed")
    return source


class DeliveryTests(unittest.TestCase):
    def test_exact_new_namespace_and_reused_published_dependency(self):
        own = authenticate(ROOT)
        dependency = authenticate(DEPENDENCY, DEPENDENCY_SOURCE)
        self.assertEqual(own["dependencies"][0]["source"],
                         {"bytes": DEPENDENCY_SOURCE[0], "sha256": DEPENDENCY_SOURCE[1]})
        self.assertEqual(own["dependencies"][0]["path"], "../sbind-whole-trial-preparation")
        self.assertEqual(own["current_dependencies"], [{
            "path": "benchmarks/paper/PAPER-CANDIDATE-20261114-SBIND/implementations/whole-trial-preparation",
            "source": {"path": str(CURRENT_DEPENDENCY), "bytes": CURRENT_DEPENDENCY_SOURCE[0],
                       "sha256": CURRENT_DEPENDENCY_SOURCE[1]},
            "historical_source": {"bytes": DEPENDENCY_SOURCE[0], "sha256": DEPENDENCY_SOURCE[1]}}])
        self.assertNotIn("trial_preparation.py", {x["path"] for x in own["files"]})
        self.assertNotIn("test_trial_preparation.py", {x["path"] for x in own["files"]})
        self.assertIn("SCOPE_CLARIFICATION.md", {x["path"] for x in dependency["files"]})
        self.assertIn("NATIVE_CALLER_CLARIFICATION.md", {x["path"] for x in own["files"]})
        self.assertFalse(own["scientific_qualification"])

    def test_relocated_shared_types_and_complete_grid_admission(self):
        authenticate(ROOT); authenticate(DEPENDENCY, DEPENDENCY_SOURCE)
        with tempfile.TemporaryDirectory(prefix="sbind normalization delivery ") as temporary:
            base = Path(temporary); checkout = base / "relocated checkout"
            components = checkout / "benchmarks/paper/PAPER-CANDIDATE-20261114-SBIND/implementations"
            components.mkdir(parents=True)
            copied = components / ROOT.name; inherited = components / DEPENDENCY.name
            shutil.copytree(ROOT, copied); shutil.copytree(DEPENDENCY, inherited)
            relocated_descriptor = checkout / CURRENT_SOURCE
            relocated_descriptor.parent.mkdir(parents=True)
            shutil.copyfile(ROOT.parents[4] / CURRENT_SOURCE, relocated_descriptor)
            shutil.copyfile(ROOT.parents[4] / CURRENT_DEPENDENCY, checkout / CURRENT_DEPENDENCY)
            elsewhere = base / "unrelated cwd"; elsewhere.mkdir()
            script = """import hashlib, inspect, json, pathlib, sys, unittest
root, dependency = (pathlib.Path(x).resolve() for x in sys.argv[1:3])
sys.path[:0] = [str(root), str(dependency)]
import numerical_preparation as subject
import trial_preparation as inherited
import test_trial_preparation as original_fixture
import test_numerical_preparation as new_fixture
import test_public_delivery as delivery
delivery.authenticate(root)
delivery.authenticate(dependency, delivery.DEPENDENCY_SOURCE)
assert delivery.DEPENDENCY == dependency
assert subject.trials is inherited and original_fixture.subject is inherited
assert pathlib.Path(inherited.__file__).resolve() == dependency / 'trial_preparation.py'
assert pathlib.Path(subject.__file__).resolve() == root / 'numerical_preparation.py'
c, s, r, pins, protocol = new_fixture.metadata()
admitted = subject.admit_representations(r, pins['representations_sha256'], protocol)
assert len(admitted) == 10 and [len(a.trials) for a in protocol.assays] == [248, 412]
assert all(len(a.folds) == 5 for a in protocol.assays)
assert 'owner_targets_sink' in inspect.signature(subject.prepare_selected_fold).parameters
assert not any(n == 'numpy' or n == 'torch' or n == 'sbind' or n.startswith('sbind.') for n in sys.modules)
suite = unittest.defaultTestLoader.discover(str(root), pattern='test_*.py')
assert suite.countTestCases() == 10
print(json.dumps({'relocated': True, 'shared_dependency_types': True, 'full_grid_admitted': True,
                  'assay_trials': [248,412], 'declarations': 10, 'discovered_new_package_methods': 10,
                  'numerical_methods_executed': 0, 'old_indexing_methods_executed': 0}))
"""
            env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script,
                                     str(copied), str(inherited)], cwd=elsewhere, env=env,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(result.stdout)
            self.assertTrue(record["shared_dependency_types"])
            self.assertEqual(record["assay_trials"], [248, 412])
            self.assertEqual(record["numerical_methods_executed"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
