"""Public relocation/input boundaries using invented metadata only."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import test_metadata_contract_v2 as original

m = original.m


class PublicInterface(unittest.TestCase):
    def test_relocated_help_needs_no_private_inputs(self):
        text = io.StringIO()
        with contextlib.redirect_stdout(text):
            with self.assertRaises(SystemExit) as caught:
                m.main(['--help'])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn('--audit-sha256', text.getvalue())
        self.assertIn('--contract', text.getvalue())

    def test_absent_audit_stops_before_contract_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory).resolve()
            calls = []
            original_load = m.io.load_json
            def tracked(path, digest):
                calls.append(str(path))
                return original_load(path, digest)
            with mock.patch.object(m.io, 'load_json', tracked):
                with self.assertRaises(FileNotFoundError):
                    m.main(['--audit', str(p/'absent.json'), '--audit-sha256', '0'*64,
                            '--contract', str(p/'absent-contract.json'), '--output', str(p/'never.json')])
            self.assertEqual(calls, [str(p/'absent.json')])
            self.assertFalse((p/'never.json').exists())

    def test_generated_actual_contract_cannot_replace_frozen_private_identity(self):
        self.assertEqual(m.CONTRACT_BYTES, 221135)
        self.assertEqual(m.CONTRACT_SHA, '1cd811af54ac31ff894b437bb3abbdd473374b1fe167844d84b9f619c5296fd4')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory).resolve()
            audit = b'{}\n'; (p/'audit.json').write_bytes(audit)
            (p/'contract.json').write_bytes(b'{}\n')
            with self.assertRaisesRegex(ValueError, 'manifest bytes differ'):
                m.main(['--audit', str(p/'audit.json'), '--audit-sha256', hashlib.sha256(audit).hexdigest(),
                        '--contract', str(p/'contract.json'), '--output', str(p/'never.json')])
            self.assertFalse((p/'never.json').exists())


if __name__ == '__main__':
    unittest.main()
