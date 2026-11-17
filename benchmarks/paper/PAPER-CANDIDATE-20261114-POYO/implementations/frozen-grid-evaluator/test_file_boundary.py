"""Only the added ordinary-file admission boundary; no scientific suite replay."""
import os
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("poyo_boundary_evaluator", Path(__file__).with_name("evaluator.py"))
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


class FileBoundaryTests(unittest.TestCase):
    def test_regular_and_no_follow(self):
        with tempfile.TemporaryDirectory(prefix="poyo-file-generated-") as tmp:
            root = Path(tmp)
            (root / "regular").write_bytes(b"generated")
            (root / "alias").symlink_to(root / "regular")
            self.assertEqual(ev.read_bytes(root / "regular"), b"generated")
            with self.assertRaises(OSError):
                ev.read_bytes(root / "alias")

    def test_fifo_refuses_without_blocking(self):
        with tempfile.TemporaryDirectory(prefix="poyo-file-generated-") as tmp:
            path = Path(tmp) / "fifo"
            os.mkfifo(path)
            with self.assertRaisesRegex(ValueError, "ordinary regular"):
                ev.read_bytes(path)

    def test_declared_limit_before_body(self):
        with tempfile.TemporaryDirectory(prefix="poyo-file-generated-") as tmp:
            path = Path(tmp) / "large"
            path.write_bytes(b"invented" * 8)
            original = ev.MAX_BYTES
            try:
                ev.MAX_BYTES = 32
                with self.assertRaisesRegex(ValueError, "bounded ordinary"):
                    ev.read_bytes(path)
            finally:
                ev.MAX_BYTES = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
