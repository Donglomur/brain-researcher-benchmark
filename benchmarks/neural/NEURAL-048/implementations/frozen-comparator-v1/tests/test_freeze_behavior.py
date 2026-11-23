"""Generated operator CLI controls; no animal observations or fitted models."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


COMPONENT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "neural048_freeze_fixture", Path(__file__).with_name("test_scorer.py"))
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
scorer = fixture_module.scorer


class FreezeBehaviorCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.reference, self.comparator, self.candidate, self.pin = fixture_module.fixture()
        for name, value in (("reference.json", self.reference),
                            ("predictions.json", self.comparator["predictions"]),
                            ("receipt.json", self.comparator["receipt"])):
            (self.root / name).write_text(json.dumps(value))
        self.output = self.root / "comparator.json"

    def run_cli(self):
        return subprocess.run(
            [sys.executable, "-I", "-B", str(COMPONENT / "freeze_behavior.py"),
             str(self.root / "reference.json"), str(self.root / "predictions.json"),
             str(self.root / "receipt.json"), "--execution-manifest-sha256",
             self.comparator["execution_manifest_sha256"], "--output", str(self.output)],
            text=True, capture_output=True, timeout=10)

    def test_complete_cli_roundtrip_uses_canonical_digest_and_original_score(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(set(report), {"comparator_sha256", "digest_kind"})
        self.assertEqual(report["comparator_sha256"], self.pin)
        self.assertNotEqual(report["comparator_sha256"],
                            hashlib.sha256(self.output.read_bytes()).hexdigest())
        comparator = json.loads(self.output.read_text())
        self.assertEqual(comparator, self.comparator)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        expected = scorer.score(self.reference, self.comparator, self.candidate,
                                expected_comparator_sha256=self.pin)
        actual = scorer.score(self.reference, comparator, self.candidate,
                              expected_comparator_sha256=report["comparator_sha256"])
        self.assertEqual(actual, expected)
        self.assertEqual(list(self.root.glob(".neural048-freeze-*")), [])

    def test_existing_comparator_is_not_replaced(self):
        original = b"previously frozen comparator\n"
        self.output.write_bytes(original)
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".neural048-freeze-*")), [])

    def test_dangling_symlink_is_not_followed_or_replaced(self):
        destination = self.root / "missing-target.json"
        self.output.symlink_to(destination)
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.root.glob(".neural048-freeze-*")), [])

    def test_invalid_or_ambiguous_inputs_do_not_create_an_output(self):
        examples = [
            '[{"id":"A-0","behavior":0.5,"behavior":0.8}]',
            '[{"id":"A-0","behavior":NaN}]',
            json.dumps(self.comparator["predictions"][:-1]),
        ]
        for payload in examples:
            with self.subTest(payload=payload):
                (self.root / "predictions.json").write_text(payload)
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertFalse(self.output.exists())
                self.assertEqual(list(self.root.glob(".neural048-freeze-*")), [])


if __name__ == "__main__":
    unittest.main()
