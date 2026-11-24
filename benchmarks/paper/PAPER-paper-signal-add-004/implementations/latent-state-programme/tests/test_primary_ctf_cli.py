"""Generated CLI/dispatch controls; no authentic archive, arrays or model fits."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import primary_ctf_inputs as target


class PrimaryCtfCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.spec = {
            'ctf_archive': {'path': '/unopened/original.zip', 'bytes': target.CTF_BYTES,
                            'sha256': target.CTF_SHA},
            'ctf_directory': {'path': '/unopened/directory.json', 'bytes': target.DIRECTORY_BYTES,
                              'sha256': target.DIRECTORY_SHA}}
        self.spec_path = self.root / 'spec.json'
        self.output = self.root / 'prepared'

    def arguments(self, raw=None):
        raw = target.encoded(self.spec) if raw is None else raw
        self.spec_path.write_bytes(raw)
        return ['--spec', str(self.spec_path), '--spec-bytes', str(len(raw)),
                '--spec-sha256', hashlib.sha256(raw).hexdigest(),
                '--output', str(self.output), '--read-bytes', '1000000',
                '--write-bytes', '200000', '--array-bytes', '50000']

    def test_dispatch_preserves_source_spec_and_charges_metadata(self):
        arguments = self.arguments()
        result = {'inputs': {'ctf_people': 65, 'primary_branches': ['ctf_tde', 'ctf_dynemo']},
                  'completion': {'bytes': 123, 'sha256': 'c' * 64},
                  'logical_IO': {'read': 2345, 'write': 1234}}
        stream = io.StringIO()
        # Only dispatch is substituted: production build is independently tested
        # on generated members; this is not an authenticated preparation result.
        with patch.object(target, 'build', return_value=result) as build, redirect_stdout(stream):
            self.assertEqual(target.main(arguments), 0)
        build.assert_called_once_with(self.spec, self.output,
                                      {'read_bytes': 1000000 - self.spec_path.stat().st_size,
                                       'write_bytes': 200000, 'array_bytes': 50000})
        receipt = json.loads(stream.getvalue())
        self.assertEqual(receipt['preparation'], result)
        self.assertEqual(receipt['logical_IO'],
                         {'read': self.spec_path.stat().st_size + 2345, 'write': 1234})
        self.assertFalse(receipt['scientific_qualification'])
        self.assertFalse(self.output.exists())

    def test_changed_spec_identity_rejected_before_build(self):
        arguments = self.arguments()
        arguments[arguments.index('--spec-sha256') + 1] = '0' * 64
        with patch.object(target, 'build', side_effect=AssertionError('build reached')):
            with self.assertRaisesRegex(ValueError, 'operator-bound bytes/SHA'):
                target.main(arguments)
        self.assertFalse(self.output.exists())

    def test_duplicate_spec_keys_rejected_before_build(self):
        arguments = self.arguments(b'{"ctf_archive": {}, "ctf_archive": {}}\n')
        with patch.object(target, 'build', side_effect=AssertionError('build reached')):
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
                target.main(arguments)

    def test_cli_does_not_bypass_fixed_original_source_identity(self):
        self.spec['ctf_archive']['sha256'] = '0' * 64
        arguments = self.arguments()
        with self.assertRaisesRegex(ValueError, 'fixed original CTF identity'):
            target.main(arguments)
        self.assertFalse(self.output.exists())

    def test_no_read_or_build_when_output_already_exists(self):
        arguments = self.arguments()
        self.output.mkdir()
        with patch.object(target, 'capture', side_effect=AssertionError('input opened')):
            with self.assertRaisesRegex(ValueError, 'Fresh primary-CTF output root'):
                target.main(arguments)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_spec_read_budget_exhaustion_precedes_capture(self):
        arguments = self.arguments()
        arguments[arguments.index('--read-bytes') + 1] = str(self.spec_path.stat().st_size)
        with patch.object(target, 'capture', side_effect=AssertionError('input opened')):
            with self.assertRaisesRegex(ValueError, 'positive primary-input read allocation'):
                target.main(arguments)

    def test_failed_preparation_emits_no_success_receipt(self):
        arguments = self.arguments()
        stream = io.StringIO()
        with patch.object(target, 'build', side_effect=ValueError('incomplete preparation')):
            with redirect_stdout(stream), self.assertRaisesRegex(ValueError, 'incomplete preparation'):
                target.main(arguments)
        self.assertEqual(stream.getvalue(), '')

    def test_invalid_budget_or_digest_is_usage_error_before_io(self):
        for option, value in [('--read-bytes', '0'), ('--write-bytes', '-1'),
                              ('--array-bytes', '1.5'), ('--spec-bytes', '0'),
                              ('--spec-sha256', 'not-a-digest')]:
            with self.subTest(option=option):
                arguments = self.arguments()
                arguments[arguments.index(option) + 1] = value
                with patch.object(target, 'capture', side_effect=AssertionError('input opened')):
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
                        target.main(arguments)
                self.assertEqual(result.exception.code, 2)

    def test_help_needs_no_source_capture_or_numpy(self):
        stream = io.StringIO()
        with patch.object(target, 'capture', side_effect=AssertionError('input opened')):
            with redirect_stdout(stream), self.assertRaises(SystemExit) as result:
                target.main(['--help'])
        self.assertEqual(result.exception.code, 0)
        self.assertIn('--spec-sha256', stream.getvalue())
        self.assertIn('--array-bytes', stream.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
