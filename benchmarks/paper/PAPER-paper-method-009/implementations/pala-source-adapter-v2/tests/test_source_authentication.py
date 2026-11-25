"""Generated MAT mutation controls; no original recording is opened."""
from pathlib import Path
import hashlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import loadmat, savemat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_adapter as adapter


def source_bytes(value):
    voltage = np.empty(2, dtype=object)
    voltage[:] = [np.array([value, -.03, .01]), np.array([-.05, value, .02])]
    data = {
        "Trial_MembranePotential": voltage,
        "Trial_MembranePotential_SamplingRate": np.full(2, 20000),
        "Trial_Type": np.array(["Spont", "Spont"], dtype=object),
        "Cell_Type": np.array(["PV", "PV"], dtype=object),
        "Mouse_Name": np.array(["generated-mouse", "generated-mouse"], dtype=object),
        "Cell_Counter": np.ones(2),
    }
    buffer = io.BytesIO()
    savemat(buffer, {"data": data}, long_field_names=True)
    return buffer.getvalue()


def mutate(path, body):
    before = path.stat()
    with path.open("r+b") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    # Deterministic metadata change even on filesystems with coarse timestamps.
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))


class SourceAuthenticationTests(unittest.TestCase):
    def test_stable_generated_mat_preserves_values_and_source_receipt(self):
        body = source_bytes(-.06)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generated.mat"
            path.write_bytes(body)
            with patch.object(adapter, "SOURCE_MD5", hashlib.md5(body).hexdigest()):
                result = adapter.load_pala(path)
        self.assertEqual(result.trials[0].voltage_mv[0], -60.)
        self.assertEqual(result.receipt["source_bytes"], len(body))
        self.assertEqual(result.receipt["source_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(result.receipt["source_md5"], hashlib.md5(body).hexdigest())

    def test_changed_file_after_hash_is_refused_after_real_mat_decode(self):
        original, replacement = source_bytes(-.06), source_bytes(-.04)
        self.assertEqual(len(original), len(replacement))
        decoded = []
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generated.mat"
            path.write_bytes(original)
            def changed_reader(handle, **kwargs):
                mutate(path, replacement)
                value = loadmat(handle, **kwargs)
                decoded.append(value["data"]["Trial_MembranePotential"][0][0])
                return value
            with patch.object(adapter, "SOURCE_MD5", hashlib.md5(original).hexdigest()), \
                 patch.object(adapter, "loadmat", side_effect=changed_reader):
                with self.assertRaisesRegex(adapter.SourceContractError, "changed during MAT decoding"):
                    adapter.load_pala(path)
        self.assertEqual(decoded, [-.04])

    def test_changed_file_at_hash_completion_is_refused_before_decode(self):
        original, replacement = source_bytes(-.06), source_bytes(-.04)
        original_md5 = hashlib.md5
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generated.mat"
            path.write_bytes(original)
            class ChangingDigest:
                def __init__(self):
                    self.digest = original_md5()
                def update(self, block):
                    self.digest.update(block)
                def hexdigest(self):
                    result = self.digest.hexdigest()
                    mutate(path, replacement)
                    return result
            with patch.object(adapter, "SOURCE_MD5", original_md5(original).hexdigest()), \
                 patch.object(adapter.hashlib, "md5", ChangingDigest), \
                 patch.object(adapter, "loadmat") as reader:
                with self.assertRaisesRegex(adapter.SourceContractError, "changed during authentication"):
                    adapter.load_pala(path)
                reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
