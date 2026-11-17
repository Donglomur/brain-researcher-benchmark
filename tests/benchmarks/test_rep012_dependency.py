"""Generated refusal controls for the REP012 public dependency locator.

Only public source is copied into a fresh temporary checkout. No private
reference is created or read, and no numerical grade is produced.
"""

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = "benchmarks/paper/PAPER-FIND-REP-012/implementations/registered-runtime/score.py"
FACADE = "benchmarks/paper/PAPER-FIND-REP-012/implementations/pooled-associations/artifact_io.py"
CORE = "benchmarks/paper/PAPER-FIND-REP-012/implementations/pooled-associations/scorer_core.py"
REFERENCE = "artifacts-build/compartment-bounded-preparation-001/scientific/private_expected.json"
INPUT_SHA = "d5f1d739eb1da61e01c2bb2e510dbd85d1c958f8243bc4b653c087a8c118cb1e"
REFERENCE_PIN = {
    "bytes": 1976,
    "sha256": "1f3c61c9286b0e3df7825a10eb878d8711d974a70d38e4a2d0a6dad90004b898",
}
SOURCE_PINS = {
    FACADE: (5699, "a8cad32aeb96b319dbe360c913aea8433840a65d72c8667d48aa52f94269270a"),
    CORE: (15037, "b3e9ba4bcc3492b31877399704f5d85f12b3dab01550f8a02be84dca2882b368"),
}


def literal_constants(source):
    """Inspect bridge bindings without importing or executing the bridge."""
    wanted = {"FACADE", "FACADE_PIN", "REFERENCE", "REFERENCE_PIN", "INPUT_SHA"}
    result = {}
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in wanted):
            result[node.targets[0].id] = ast.literal_eval(node.value)
    return result


def invented_abstention():
    """A valid submission shape with invented identities and no estimates."""
    return {
        "schema_version": 1,
        "task_id": "PAPER-FIND-REP-012",
        "input_manifest_sha256": INPUT_SHA,
        "analysis_id": "released_source_four_pooled_pearson_v1",
        "cohort": {
            "member_count": 2,
            "raw_rows": 8,
            "unique_mice": 1,
            "shared_mouse_ids": ["INVENTED_INTERFACE_MOUSE"],
            "raw_row_ids_sha256": "b" * 64,
        },
        "endpoints": [
            {
                "endpoint_id": name,
                "status": "abstained",
                "reason": "INVENTED interface control; no scientific estimate.",
                "result": None,
            }
            for name in ("apical_local", "basal_local", "apical_coincident", "basal_coincident")
        ],
    }


class Rep012Dependency(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rep012-dependency-")
        self.addCleanup(temporary.cleanup)
        # Resolve macOS temporary-directory aliases before the source's strict
        # ordinary-ancestry checks. This is never the real repository root.
        self.root = Path(temporary.name).resolve()
        self.source_bodies = {}
        for relative in (BRIDGE, FACADE, CORE):
            body = (ROOT / relative).read_bytes()
            if relative in SOURCE_PINS:
                self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), SOURCE_PINS[relative])
            self.source_bodies[relative] = body
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        self.submission = self.root / "submission.json"
        self.output = self.root / "grade.json"
        self.reference = self.root / REFERENCE
        self.assertFalse(self.reference.exists())

    def invoke(self, body):
        self.submission.write_bytes(body)
        return subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(self.root / BRIDGE),
             "--submission", str(self.submission), "--output", str(self.output)],
            cwd=self.root, capture_output=True, timeout=5,
        )

    def report(self):
        self.assertFalse(self.reference.exists())
        result = json.loads(self.output.read_bytes())
        self.assertIsNone(result["score"])
        self.assertIsNone(result["reference_pin"])
        self.assertFalse(result["candidate_code_executed"])
        return result

    def test_exact_public_closure_preserves_protected_identities(self):
        constants = literal_constants(self.source_bodies[BRIDGE])
        self.assertEqual(constants["FACADE"], FACADE)
        self.assertEqual(constants["FACADE_PIN"], SOURCE_PINS[FACADE])
        self.assertEqual(constants["REFERENCE"], REFERENCE)
        self.assertEqual(constants["REFERENCE_PIN"], REFERENCE_PIN)
        self.assertEqual(constants["INPUT_SHA"], INPUT_SHA)
        self.assertEqual((self.root / FACADE).parent / "scorer_core.py", self.root / CORE)

    def test_tampered_public_facade_is_refused_before_execution(self):
        original = self.source_bodies[FACADE]
        tampered = original.replace(b"Operator artifact facade", b"Xperator artifact facade", 1)
        self.assertNotEqual(tampered, original)
        self.assertEqual(len(tampered), len(original))
        (self.root / FACADE).write_bytes(tampered)
        process = self.invoke(b"{}")
        self.assertNotEqual(process.returncode, 0)
        self.assertIn(b"Exact stable trusted facade bytes", process.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.reference.exists())

    def test_tampered_public_core_is_an_operator_error(self):
        original = self.source_bodies[CORE]
        tampered = original.replace(b"Finite result-artifact", b"Xinite result-artifact", 1)
        self.assertNotEqual(tampered, original)
        self.assertEqual(len(tampered), len(original))
        (self.root / CORE).write_bytes(tampered)
        process = self.invoke(b"{}")
        self.assertEqual(process.returncode, 1, process.stderr)
        result = self.report()
        self.assertEqual(result["status"], "operator_error")
        self.assertIn("Trusted scorer source pin changed", result["reason"])

    def test_malformed_submission_is_rejected_before_missing_reference(self):
        process = self.invoke(b'{"schema_version":1,"schema_version":1}')
        self.assertEqual(process.returncode, 2, process.stderr)
        result = self.report()
        self.assertEqual(result["status"], "invalid_submission")
        self.assertFalse(result["private_reference_decoded"])

    def test_valid_abstention_still_requires_the_fixed_private_reference(self):
        body = json.dumps(invented_abstention(), allow_nan=False).encode("utf-8")
        process = self.invoke(body)
        self.assertEqual(process.returncode, 1, process.stderr)
        result = self.report()
        self.assertEqual(result["status"], "operator_error")
        self.assertIn(str(self.reference), result["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
