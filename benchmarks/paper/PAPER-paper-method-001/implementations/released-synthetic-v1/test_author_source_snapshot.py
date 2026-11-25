"""Generated source-loader controls; never imports or runs an author estimator."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
NAMESPACE = "_released_synthetic_author_f18de358"
MODULE_NAMES = (NAMESPACE, NAMESPACE + "._core", NAMESPACE + ".estimators")


class AuthorSourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("released_source_snapshot_control", HERE / "released_synthetic.py")
        self.adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.adapter)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source_dir = self.root / "dimensionality-programme/programme/scientific-runtime/finite_science/literal_author"
        self.source_dir.mkdir(parents=True)
        self.sources = {
            "__init__.py": b'"""Generated inert author-package substitute."""\n',
            "_core.py": b'VALUE = "approved"\n',
            "estimators.py": b'from ._core import VALUE\ndef participation_ratio():\n    return VALUE\n',
        }
        self.write_sources()
        self.pins = {name: hashlib.sha256(body).hexdigest() for name, body in self.sources.items()}
        self.addCleanup(patch.stopall)
        patch.object(self.adapter, "__file__", str(self.root / "released-synthetic-v1/released_synthetic.py")).start()
        patch.object(self.adapter, "_source_pins", return_value=self.pins).start()
        self.saved_modules = {name: sys.modules.get(name) for name in MODULE_NAMES}
        for name in MODULE_NAMES:
            sys.modules.pop(name, None)
        self.addCleanup(self.restore_modules)

    def restore_modules(self):
        for name in MODULE_NAMES:
            sys.modules.pop(name, None)
            if self.saved_modules[name] is not None:
                sys.modules[name] = self.saved_modules[name]

    def write_sources(self):
        for name, body in self.sources.items():
            (self.source_dir / name).write_bytes(body)

    def replaced_after_authentication(self, name, replacement):
        original_read = Path.read_bytes
        def read(path):
            body = original_read(path)
            # Both implementations authenticate this last closure member before
            # executing any source; replace a path after returning its old bytes.
            if path == self.source_dir / "estimators.py":
                (self.source_dir / name).write_bytes(replacement)
            return body
        with patch.object(Path, "read_bytes", read):
            estimator = self.adapter._author_estimator()
        return estimator()

    def test_dependency_replacement_cannot_change_verified_execution(self):
        self.assertEqual(self.replaced_after_authentication("_core.py", b'VALUE = "changed"\n'), "approved")

    def test_estimator_replacement_cannot_change_verified_execution(self):
        self.assertEqual(self.replaced_after_authentication("estimators.py", b'def participation_ratio():\n    return "changed"\n'), "approved")

    def test_unchanged_sources_preserve_callable_and_identity(self):
        first = self.adapter._author_estimator()
        self.assertEqual(first(), "approved")
        self.assertIs(first, self.adapter._author_estimator())
        self.assertEqual(first.__module__, NAMESPACE + ".estimators")

    def test_wrong_initial_source_hash_is_rejected(self):
        (self.source_dir / "_core.py").write_bytes(b'VALUE = "bad"\n')
        with self.assertRaisesRegex(ValueError, "published author dependency changed"):
            self.adapter._author_estimator()
        self.assertFalse(any(name in sys.modules for name in MODULE_NAMES))

    def test_failed_dependency_load_does_not_leave_partial_cache(self):
        body = b'raise RuntimeError("generated dependency failure")\n'
        (self.source_dir / "_core.py").write_bytes(body)
        self.pins["_core.py"] = hashlib.sha256(body).hexdigest()
        with self.assertRaisesRegex(RuntimeError, "generated dependency failure"):
            self.adapter._author_estimator()
        self.assertFalse(any(name in sys.modules for name in MODULE_NAMES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
