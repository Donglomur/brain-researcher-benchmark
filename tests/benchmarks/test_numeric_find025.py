"""Verify the explicit current FIND025 numerical source binding."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = ROOT / 'benchmarks/integrity/current-closures/numeric-find025/SOURCE.json'


class NumericFind025Bindings(unittest.TestCase):
    def test_current_source_and_preserved_contract_match_descriptor(self):
        descriptor = json.loads(DESCRIPTOR.read_text())
        self.assertEqual(descriptor['schema'], 'numeric-find025-current-source-v1')
        self.assertFalse(descriptor['execution_authority'])
        self.assertFalse(descriptor['scientific_qualification'])
        for group in ('current_files', 'unchanged_contract_files'):
            for pin in descriptor[group]:
                with self.subTest(group=group, path=pin['path']):
                    body = (ROOT / pin['path']).read_bytes()
                    self.assertEqual(len(body), pin['bytes'])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), pin['sha256'])


if __name__ == '__main__':
    unittest.main()
