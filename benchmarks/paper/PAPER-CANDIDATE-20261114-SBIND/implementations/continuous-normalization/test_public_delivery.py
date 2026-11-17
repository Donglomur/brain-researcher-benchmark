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
DEPENDENCY = ROOT.parent / "sbind-whole-trial-preparation"
DEPENDENCY_SOURCE = (1452, "9110b9ef65bc205e719edd4cfb0d41e5e8edfb6bd6a51a2480ee780a1913e08d")


def authenticate(root, expected=None):
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise RuntimeError("ordinary component directory required")
    manifest = root / "SOURCE.json"
    if not stat.S_ISREG(manifest.lstat().st_mode):
        raise RuntimeError("ordinary source manifest required")
    raw = manifest.read_bytes()
    if expected is not None and (len(raw), hashlib.sha256(raw).hexdigest()) != expected:
        raise RuntimeError("selected dependency source manifest changed")
    source = json.loads(raw)
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
        self.assertNotIn("trial_preparation.py", {x["path"] for x in own["files"]})
        self.assertNotIn("test_trial_preparation.py", {x["path"] for x in own["files"]})
        self.assertIn("SCOPE_CLARIFICATION.md", {x["path"] for x in dependency["files"]})
        self.assertIn("NATIVE_CALLER_CLARIFICATION.md", {x["path"] for x in own["files"]})
        self.assertFalse(own["scientific_qualification"])

    def test_relocated_shared_types_and_complete_grid_admission(self):
        authenticate(ROOT); authenticate(DEPENDENCY, DEPENDENCY_SOURCE)
        with tempfile.TemporaryDirectory(prefix="sbind normalization delivery ") as temporary:
            base = Path(temporary); components = base / "relocated checkout" / "components"
            components.mkdir(parents=True)
            copied = components / ROOT.name; inherited = components / DEPENDENCY.name
            shutil.copytree(ROOT, copied); shutil.copytree(DEPENDENCY, inherited)
            elsewhere = base / "unrelated cwd"; elsewhere.mkdir()
            script = """import hashlib, inspect, json, pathlib, sys, unittest
root, dependency = (pathlib.Path(x).resolve() for x in sys.argv[1:3])
sys.path[:0] = [str(root), str(dependency)]
import numerical_preparation as subject
import trial_preparation as inherited
import test_trial_preparation as original_fixture
import test_numerical_preparation as new_fixture
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
assert suite.countTestCases() == 9
print(json.dumps({'relocated': True, 'shared_dependency_types': True, 'full_grid_admitted': True,
                  'assay_trials': [248,412], 'declarations': 10, 'discovered_new_package_methods': 9,
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
