"""Invented regressions for late resource failures, never authentic inputs."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import io

import task


class ResourceControls(unittest.TestCase):
    def test_canonicalization_rss_breach_prevents_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/'answer.json'
            def encoded(value):
                return b'{}\n'
            # The same high-water observation is excessive in Darwin bytes or Linux KiB.
            with patch.object(task.core, 'canonical', side_effect=encoded), patch.object(
                    task.resource, 'getrusage', return_value=SimpleNamespace(ru_maxrss=5*1024**3)):
                with self.assertRaisesRegex(ValueError, 'RSS'):
                    task.write_json(destination, {'invented': True}, task.budget())
            self.assertFalse(destination.exists())

    def test_late_rss_breach_prevents_terminal_success(self):
        output = SimpleNamespace(buffer=io.BytesIO())
        with patch.object(task, 'provision', return_value={'invented': True}), patch.object(
                task.resource, 'getrusage', return_value=SimpleNamespace(ru_maxrss=5*1024**3)), patch.object(
                task.sys, 'stdout', output):
            with self.assertRaisesRegex(ValueError, 'RSS'):
                task.main(['provision','--inputs','never-read','--output','never-created'])
        self.assertEqual(output.buffer.getvalue(), b'')


if __name__ == '__main__':
    unittest.main()
