"""Independent invented ZIP64 end-directory adversary; no authentic arrays."""
from pathlib import Path
import hashlib
import importlib.util
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

SOURCE = Path(__file__).with_name("training_projection.py")
body = SOURCE.read_bytes()
assert len(body) == 14990 and hashlib.sha256(body).hexdigest() == "4ac3b1985ee6238a60b0577afd611ebee3efcbc5ddddfbc310dafa368a3acabe"
spec = importlib.util.spec_from_file_location("independent_projector_zip64", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

class Zip64EndBoundary(unittest.TestCase):
    def test_zip64_end_record_cannot_override_classic_directory_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, output = root / "invented.npz", root / "train.npz"
            # Opaque invented NPY-prefixed bytes; numerical decoding is never invoked.
            with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_STORED) as archive:
                for i, field in enumerate(m.PUBLIC_FIELDS):
                    info = zipfile.ZipInfo(field + ".npy")
                    info.comment = b"C" * 6000
                    archive.writestr(info, b"\x93NUMPY\x01\x00" + bytes([i]) * 16)
            original = source.read_bytes()
            end = list(struct.unpack("<4s4H2IH", original[-22:]))
            actual_size, actual_offset = end[5], end[6]
            self.assertGreater(actual_size, m.DIRECTORY_CAP_BYTES)
            self.assertEqual(end[3:5], [13, 13])
            old_end_offset = len(original) - 22
            end64 = struct.pack("<4sQ2H2L4Q", b"PK\x06\x06", 44, 45, 45,
                                0, 0, 13, 13, actual_size, actual_offset)
            locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, old_end_offset, 1)
            # The classic record passes the original preflight, but ZipFile uses
            # the ZIP64 size/offset instead of these two classic fields.
            new_end_offset = old_end_offset + len(end64) + len(locator)
            end[5], end[6] = 1, new_end_offset - 1
            payload = original[:-22] + end64 + locator + struct.pack("<4s4H2IH", *end)
            source.write_bytes(payload)
            with patch.object(m.zipfile, "ZipFile", side_effect=AssertionError("ZIP parser must not run")):
                with self.assertRaisesRegex(m.ProjectionError, "ZIP64 end locator"):
                    m.derive_training_packet(source, output, len(payload),
                        hashlib.sha256(payload).hexdigest(), time.monotonic() + 10)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".train-packet-*")), [])

if __name__ == "__main__":
    unittest.main(verbosity=2)
