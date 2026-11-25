"""Generated source-custody controls; no authentic neural inputs."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("marmoset_dependency_subject", Path(__file__).with_name("constant.py"))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class TestDependencySnapshot(unittest.TestCase):
    def test_replacement_after_authentication_cannot_change_executed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "constant").mkdir()
            source = root / "fixture.py"
            original = b"marker = 'authenticated'\n"
            source.write_bytes(original)
            real_spec = importlib.util.spec_from_file_location
            def replace_before_load(name, path):
                source.write_bytes(b"marker = 'substituted'\n")
                return real_spec(name, path)
            with patch.object(subject, "__file__", str(root / "constant/constant.py")), \
                 patch.object(subject.importlib.util, "spec_from_file_location", side_effect=replace_before_load):
                module = subject._dependency("marmoset_generated_snapshot", "fixture.py",
                                              hashlib.sha256(original).hexdigest())
            self.assertEqual(module.marker, "authenticated")
            self.assertEqual(module.__file__, str(source.resolve()))

    def test_wrong_source_identity_is_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "constant").mkdir()
            (root / "fixture.py").write_bytes(b"raise AssertionError('must not execute')\n")
            with patch.object(subject, "__file__", str(root / "constant/constant.py")):
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    subject._dependency("marmoset_wrong_snapshot", "fixture.py", "0" * 64)

    def test_stable_source_keeps_module_metadata_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "constant").mkdir()
            source = root / "fixture.py"
            original = b"value = 7\n"
            source.write_bytes(original)
            with patch.object(subject, "__file__", str(root / "constant/constant.py")):
                module = subject._dependency("marmoset_stable_snapshot", "fixture.py",
                                              hashlib.sha256(original).hexdigest())
            self.assertEqual(module.value, 7)
            self.assertEqual(module.__file__, str(source.resolve()))
            self.assertEqual(module.__name__, "marmoset_stable_snapshot")


if __name__ == "__main__":
    unittest.main(verbosity=2)
