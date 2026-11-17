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
            scorer = load("lep_relocated_scorer", root / "scorer.py")
            prior = sys.modules.get("scorer")
            try:
                sys.modules["scorer"] = scorer
                f = load("lep_relocated_fixture", root / "test_scorer.py")
            finally:
                if prior is None:
                    sys.modules.pop("scorer", None)
                else:
                    sys.modules["scorer"] = prior
            prediction, targets, reference = f.fixture()
            for name, obj in (("prediction", prediction), ("targets", targets), ("reference", reference)):
                (base / (name + ".json")).write_bytes(f.raw(obj))
            argv = [sys.executable, "-I", "-S", "-B", str(root / "scorer.py"),
                    "--submission", str(base / "prediction.json"), "--protocol-sha256", f.PROTOCOL,
                    "--representation-sha256", f.REPRESENTATION, "--targets", str(base / "targets.json"),
                    "--targets-sha256", hashlib.sha256(f.raw(targets)).hexdigest(),
                    "--comparator", str(base / "reference.json"),
                    "--comparator-sha256", hashlib.sha256(f.raw(reference)).hexdigest(),
                    "--output", str(base / "report.json")]
            result = subprocess.run(argv, cwd=base / "unrelated", capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((base / "report.json").read_bytes())
            self.assertEqual(report["population"]["nominal_people"], 678)
            self.assertEqual(report["population"]["scored_trial_denominator"], 1356)
            self.assertEqual((report["candidate_mae"], report["reference_mae"]), (0.0, 2.0))
            self.assertTrue(report["output_contract_passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
