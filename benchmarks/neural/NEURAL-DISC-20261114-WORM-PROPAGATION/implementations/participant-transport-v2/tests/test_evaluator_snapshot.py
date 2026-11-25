"""Generated source-custody controls; no biological inputs or scorer execution."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def subject(root, source=b'VALUE = "authenticated"\n'):
    root = root.resolve()
    # Keep the real transport function, but provide an explicitly generated
    # evaluator module and pin. No original calcium data or scorer is imported.
    spec = importlib.util.spec_from_file_location("worm_transport_snapshot_control", ROOT / "participant_transport.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    transport = root / "participant-transport-v2" / "participant_transport.py"
    target = root / "initial-evaluator-v1" / "worm_evaluator.py"
    target.parent.mkdir(parents=True)
    transport.parent.mkdir()
    target.write_bytes(source)
    module.__file__ = str(transport)
    module.EVALUATOR_SHA256 = hashlib.sha256(source).hexdigest()
    return module, target


class EvaluatorSnapshotTests(unittest.TestCase):
    def test_stable_authenticated_module_retains_import_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            module, target = subject(Path(directory))
            loaded = module.evaluator()
            self.assertEqual(loaded.VALUE, "authenticated")
            self.assertEqual(loaded.__file__, str(target))
            self.assertEqual(loaded.__spec__.origin, str(target))

    def test_replaced_path_does_not_replace_authenticated_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            module, target = subject(Path(directory))
            original_read = Path.read_bytes
            reads = []

            def replace_after_read(path):
                payload = original_read(path)
                if path == target:
                    reads.append(path)
                    path.write_bytes(b'VALUE = "replacement-after-authentication"\n')
                return payload

            with mock.patch.object(Path, "read_bytes", replace_after_read):
                loaded = module.evaluator()
            self.assertEqual(len(reads), 1)
            self.assertEqual(loaded.VALUE, "authenticated")
            self.assertIn(b"replacement-after-authentication", target.read_bytes())

    def test_wrong_hash_is_rejected_before_generated_module_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            module, target = subject(Path(directory), b'raise AssertionError("must not execute")\n')
            module.EVALUATOR_SHA256 = "0" * 64
            with self.assertRaisesRegex(ValueError, "predecessor evaluator changed"):
                module.evaluator()


if __name__ == "__main__":
    unittest.main()
