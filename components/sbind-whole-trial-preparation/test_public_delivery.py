"""Public delivery checks only; no authentic payloads or scientific campaign."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class DeliveryTests(unittest.TestCase):
    def test_complete_flat_source_namespace_and_pins(self):
        source = json.loads((ROOT / "SOURCE.json").read_bytes())
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
            copied = base / "relocated component"
            elsewhere = base / "unrelated cwd"
            elsewhere.mkdir(); shutil.copytree(ROOT, copied)
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
assert suite.countTestCases() == 11
print(json.dumps({'relocated': True, 'assay': 'WFCI2', 'trial_count': 412, 'full_grid_compiled': True,
                  'discovered': 11, 'old_methods_executed': 0, 'loader_calls': calls}))
"""
            env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script, str(copied)],
                                    cwd=elsewhere, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value["discovered"], 11)
            self.assertEqual(value["old_methods_executed"], 0)
            self.assertEqual(value["loader_calls"], ["WFCI2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
