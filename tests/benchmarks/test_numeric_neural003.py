"""Current source binding and invented NEURAL-003 numeric controls only."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = ROOT / "benchmarks/integrity/current-closures/numeric-neural003/SOURCE_BINDINGS.json"
REGRESSIONS = ROOT / "benchmarks/neural/NEURAL-003/implementations/causal-reaction-time/test_scoring.py"


class NumericNeural003(unittest.TestCase):
    def test_invented_full_roster_regressions(self):
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(REGRESSIONS)],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Ran 12 tests", result.stderr)

    def test_current_descriptor_binds_source_and_preserved_contracts(self):
        binding = json.loads(DESCRIPTOR.read_text())
        self.assertEqual(binding["schema"], "numeric_neural003_current_bindings_v1")
        self.assertFalse(binding["scientific_qualification"])
        self.assertFalse(binding["execution_authority"])
        for row in binding["current_sources"] + binding["preserved_contracts"]:
            with self.subTest(path=row["path"]):
                content = (ROOT / row["path"]).read_bytes()
                self.assertEqual(len(content), row["bytes"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), row["sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
