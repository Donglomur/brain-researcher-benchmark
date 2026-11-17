"""Public delivery checks only; no authentic payloads or scientific campaign."""
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
CURRENT_SOURCE = Path("benchmarks/integrity/current-closures/input-sbind/WHOLE_TRIAL_SOURCE.json")
ORIGINAL_SOURCE = (1452, "9110b9ef65bc205e719edd4cfb0d41e5e8edfb6bd6a51a2480ee780a1913e08d")


def selected_source():
    original_path = ROOT / "SOURCE.json"
    if not stat.S_ISREG(original_path.lstat().st_mode):
        raise RuntimeError("ordinary historical source manifest required")
    raw = original_path.read_bytes()
    if (len(raw), hashlib.sha256(raw).hexdigest()) != ORIGINAL_SOURCE:
        raise RuntimeError("historical source manifest changed")
    original = json.loads(raw)
    current_path = ROOT.parents[4] / CURRENT_SOURCE
    if any(p.is_symlink() for p in (current_path, *current_path.parents)) or not stat.S_ISREG(current_path.lstat().st_mode):
        raise RuntimeError("ordinary current source descriptor required")
    selected = json.loads(current_path.read_bytes())
    if {k: v for k, v in selected.items() if k != "files"} != {k: v for k, v in original.items() if k != "files"}:
        raise RuntimeError("historical source metadata changed")
    old = {row["path"]: row for row in original["files"]}
    new = {row["path"]: row for row in selected["files"]}
    if set(old) != set(new) or {name for name in old if old[name] != new[name]} != {
            "trial_preparation.py", "test_trial_preparation.py", "test_public_delivery.py"}:
        raise RuntimeError("unexpected current source change")
    return selected


class DeliveryTests(unittest.TestCase):
    def test_complete_flat_source_namespace_and_pins(self):
        source = selected_source()
        names = {x["path"] for x in source["files"]}
        self.assertEqual(len(names), len(source["files"]))
        self.assertEqual({p.name for p in ROOT.iterdir()}, names | {"SOURCE.json"})
        for item in source["files"]:
            self.assertEqual(Path(item["path"]).name, item["path"])
            p = ROOT / item["path"]
            self.assertFalse(p.is_symlink()); self.assertTrue(p.is_file())
            data = p.read_bytes()
            self.assertEqual(len(data), item["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
        self.assertIn("SCOPE_CLARIFICATION.md", names)
        self.assertFalse(source["scientific_qualification"])

    def test_relocated_owner_api_without_upstream_or_private_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="sbind public delivery ") as temporary:
            base = Path(temporary)
            checkout = base / "relocated checkout"
            copied = checkout / "benchmarks/paper/PAPER-CANDIDATE-20261114-SBIND/implementations/whole-trial-preparation"
            elsewhere = base / "unrelated cwd"
            elsewhere.mkdir(); shutil.copytree(ROOT, copied)
            relocated_descriptor = checkout / CURRENT_SOURCE
            relocated_descriptor.parent.mkdir(parents=True)
            shutil.copyfile(ROOT.parents[4] / CURRENT_SOURCE, relocated_descriptor)
            script = """import json, pathlib, sys, unittest
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
import trial_preparation as source
import test_trial_preparation as fixtures
census, split = fixtures.fixture()
c, s, pins = fixtures.bind(census, split)
calls = []
def load(assay):
    calls.append(assay.assay_id)
    return source.SourceRows(assay.source_sha256, assay.representation_sha256,
        source.SHAPE, assay.channels, fixtures.InventedRows(assay.total_frames))
views = source.prepare_fold(c, s, **pins, assay_id='WFCI2', fold=4, source_loader=load)
assert calls == ['WFCI2']
assert len(set.union(*(set(span.trial_id for span in view.spans) for view in views.values()))) == 412
assert all(view[0].reset for view in views.values())
assert all(view[0].neural[1] == view[0].source_index for view in views.values())
assert not any(name == 'numpy' or name == 'torch' or name == 'sbind' or name.startswith('sbind.') for name in sys.modules)
suite = unittest.defaultTestLoader.discover(str(root), pattern='test_*.py')
assert suite.countTestCases() == 12
print(json.dumps({'relocated': True, 'assay': 'WFCI2', 'trial_count': 412, 'full_grid_compiled': True,
                  'discovered': 12, 'old_methods_executed': 0, 'loader_calls': calls}))
"""
            env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, str(copied)],
                                    cwd=elsewhere, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value["discovered"], 12)
            self.assertEqual(value["old_methods_executed"], 0)
            self.assertEqual(value["loader_calls"], ["WFCI2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
