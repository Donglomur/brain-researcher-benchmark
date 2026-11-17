"""Portable distribution checks using only complete invented fixture metadata."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryTests(unittest.TestCase):
    def test_flat_distribution_and_no_private_paths(self):
        source = json.loads((ROOT / "SOURCE.json").read_bytes())
        names = {m["path"] for m in source["files"]}
        self.assertEqual(names | {"SOURCE.json"}, {x.name for x in ROOT.iterdir() if x.is_file()})
        self.assertEqual(len(names), len(source["files"]))
        for item in source["files"]:
            self.assertEqual(Path(item["path"]).name, item["path"])
            body = (ROOT / item["path"]).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (item["bytes"], item["sha256"]))
            self.assertTrue(body.endswith(b"\n"))
            self.assertFalse(body.endswith(b"\n\n"))
            self.assertTrue(all(line == line.rstrip() for line in body.splitlines()))
            for forbidden in (b"/" + b"Users/", b"authoring/" + b"delivery-", b"benchmark-" + b"engineering-evidence", b"X-Amz-" + b"Signature"):
                self.assertNotIn(forbidden, body)

    def test_actual_cli_from_relocated_source_and_unrelated_cwd(self):
        with tempfile.TemporaryDirectory(prefix="neuro-public-generated-") as temp:
            base = Path(temp)
            root = base / "component with spaces"
            root.mkdir()
            (base / "unrelated").mkdir()
            for member in ROOT.iterdir():
                if member.is_file():
                    shutil.copyfile(member, root / member.name)
            f = load("poyo_relocated_fixture", root / "test_evaluator.py")
            design, prediction, target = f.fixture()
            for name, obj in (("design", design), ("prediction", prediction), ("target", target)):
                (base / (name + ".json")).write_bytes(f.encode(obj))
            dp, tp = f.pin(f.encode(design)), f.pin(f.encode(target))
            argv = [sys.executable, "-I", "-S", "-B", str(root / "evaluator.py"),
                    "--design", str(base / "design.json"), "--design-bytes", str(dp["bytes"]),
                    "--design-sha256", dp["sha256"], "--predictions", str(base / "prediction.json"),
                    "--targets", str(base / "target.json"), "--targets-bytes", str(tp["bytes"]),
                    "--targets-sha256", tp["sha256"], "--output", str(base / "report.json")]
            result = subprocess.run(argv, cwd=base / "unrelated", capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((base / "report.json").read_bytes())
            self.assertEqual((report["corpus_sessions"], report["corpus_animals"], report["cases"]), (158, 7, 4))
            self.assertEqual(len(report["results"]), 16)
            self.assertFalse(report["scientific_qualification"])
            self.assertEqual(report["results"][0]["r2"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
