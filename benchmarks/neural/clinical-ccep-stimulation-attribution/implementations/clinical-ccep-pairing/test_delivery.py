"""Public placement checks only; all fixture values and identities are invented."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pairing as C
import test_pairing

PRIMARY_SHA = "2426ddc5585a113fb839e3b3dd78bf2c684d3f0d5fef2dac0b9af4ab1ebd6f32"


class DeliveryChecks(unittest.TestCase):
    def test_complete_members_and_unchanged_dependency(self):
        manifest = json.loads((HERE / "COMPONENT_SOURCE.json").read_bytes())
        self.assertEqual({r["path"] for r in manifest["files"]} | {"COMPONENT_SOURCE.json"},
                         {p.name for p in HERE.iterdir()})
        for row in manifest["files"]:
            body = (HERE / row["path"]).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (row["bytes"], row["sha256"]))
        primary = HERE.parent / "clinical-ccep-artifact-grading" / "score.py"
        body = primary.read_bytes()
        self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (14609, PRIMARY_SHA))
        self.assertEqual(Path(C.P.__file__).resolve(), primary)
        self.assertIs(test_pairing.C, C)

    def test_three_commands_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            f = test_pairing.Fixture(base).freeze()
            args = ["--policy", str(f.pp), "--policy-sha256", f.ph,
                    "--control", str(f.cp), "--control-sha256", f.ch]
            command = [sys.executable, "-I", "-S", "-B", str(HERE / "pairing.py")]
            env = dict(os.environ)
            env["PYTHONPATH"] = str(base)
            (base / "score.py").write_text("raise RuntimeError('untrusted import path')\n")
            def invoke(extra):
                p = subprocess.run(command + extra, cwd=base, env=env, capture_output=True,
                                   timeout=10, check=False, umask=0o077)
                self.assertEqual(p.returncode, 0, p.stderr.decode())
                return p.stdout, json.loads(p.stdout)
            emitted, mapping = invoke(["maps"] + args)
            self.assertEqual(emitted, C.canonical(mapping) + b"\n")
            self.assertEqual(mapping, f.mapping)
            f.mp.write_bytes(emitted)
            f.mh = hashlib.sha256(emitted).hexdigest()
            transform = mapping["transforms"][0]
            pair = transform["donors"][0]
            _, packet = invoke(["packet"] + args + ["--map", str(f.mp), "--map-sha256", f.mh,
                "--transform-id", transform["id"], "--recipient-id", pair["recipient"],
                "--recipient-packet", str(f.paths[pair["recipient"]]),
                "--donor-packet", str(f.paths[pair["donor"]])])
            self.assertEqual(packet["response_b64"], f.blocks[pair["donor"]]["response_b64"])
            self.assertEqual(packet["layout_b64"], f.blocks[pair["recipient"]]["layout_b64"])
            self.assertEqual(packet["context_b64"], f.blocks[pair["recipient"]]["context_b64"])
            self.assertNotIn("donor", packet)
            artifact, _ = f.write("all_arms", f.artifact())
            _, report = invoke(["score"] + args + ["--map", str(f.mp), "--map-sha256", f.mh,
                "--artifact", str(artifact), "--targets", str(f.tp)])
            self.assertEqual(report["status"], "scored_support_limited_diagnostic")
            self.assertEqual(set(report["original_full_scores"]), {"candidate", "reference"})
            self.assertFalse(report["scientifically_qualified"])

    def test_same_size_changed_primary_is_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            sibling = base / "clinical-ccep-artifact-grading"
            sibling.mkdir()
            relocated = base / "clinical-ccep-pairing"
            relocated.mkdir()
            (relocated / "pairing.py").write_bytes((HERE / "pairing.py").read_bytes())
            source = bytearray((HERE.parent / "clinical-ccep-artifact-grading/score.py").read_bytes())
            source[0] ^= 1
            (sibling / "score.py").write_bytes(source)
            p = subprocess.run([sys.executable, "-I", "-S", "-B", str(relocated / "pairing.py"), "--help"],
                               cwd=base, capture_output=True, timeout=10, check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn(b"primary source identity", p.stderr)
            self.assertNotIn(b"usage:", p.stdout)

    def test_late_reference_failure_does_not_open_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            f = test_pairing.Fixture(Path(temp)).freeze()
            artifact = copy.deepcopy(f.artifact())
            artifact["arms"][-1]["transforms"][-1]["rows"][-1]["probabilities"] = [1, 1, 1, 1]
            artifact_path, _ = f.write("bad_reference", artifact)
            original = C.P.read_document
            opened = []
            def observe(path, expected=None):
                opened.append(Path(path))
                if Path(path) == f.tp:
                    raise AssertionError("invalid public artifact crossed target barrier")
                return original(path, expected)
            with patch.object(C.P, "read_document", observe), self.assertRaises(C.P.Invalid):
                C.score(f.pp, f.ph, f.cp, f.ch, f.mp, f.mh, artifact_path, f.tp)
            self.assertNotIn(f.tp, opened)
            self.assertIn(artifact_path, opened)


if __name__ == "__main__":
    if sys.flags.optimize:
        raise RuntimeError("assertions must remain enabled")
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryChecks))
    raise SystemExit(0 if result.testsRun == 4 and result.wasSuccessful() and not
                     (result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 1)
