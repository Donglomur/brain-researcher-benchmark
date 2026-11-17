"""Only public relocation/private-operand boundaries; no authentic inputs."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import prepare_pid


class PublicInterface(unittest.TestCase):
    def test_relocated_help_has_no_private_dependency(self):
        output = io.StringIO()
        with mock.patch('sys.argv', ['prepare_pid.py', '--help']), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as caught:
                prepare_pid.main()
        self.assertEqual(caught.exception.code, 0)
        self.assertIn('--archive', output.getvalue())
        self.assertIn('--output', output.getvalue())

    def test_missing_binding_refuses_before_archive_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'never-created'
            with (mock.patch.object(prepare_pid, '__file__', str(root / 'prepare_pid.py')),
                 mock.patch('sys.argv', ['prepare_pid.py', '--archive', str(root / 'never-opened.zip'), '--output', str(output)]),
                 mock.patch('builtins.open', side_effect=AssertionError('archive opened')) as opened):
                with self.assertRaises(FileNotFoundError):
                    prepare_pid.main()
                opened.assert_not_called()
            self.assertFalse(output.exists())

    def test_changed_binding_refuses_before_archive_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # No original binding is copied or reconstructed.
            (root / 'BINDING.json').write_bytes(b'{}\n')
            output = root / 'never-created'
            with (mock.patch.object(prepare_pid, '__file__', str(root / 'prepare_pid.py')),
                 mock.patch('sys.argv', ['prepare_pid.py', '--archive', str(root / 'never-opened.zip'), '--output', str(output)]),
                 mock.patch('builtins.open', side_effect=AssertionError('archive opened')) as opened):
                with self.assertRaisesRegex(prepare_pid.Held, 'binding_source_identity'):
                    prepare_pid.main()
                opened.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
