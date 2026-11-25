"""Generated source-identity controls; no authentic neural data or scientific runs."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np

ROOT = Path(os.environ.get("DANT_COMPONENT_ROOT", Path(__file__).resolve().parents[1]))
SPEC = importlib.util.spec_from_file_location("source_identity_evaluator", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)


def fixture(path, shift=0):
    with h5py.File(path, "w") as h:
        group = h.create_group("spikeInfo")
        for name in ("RatName", "SpikeTimes", "SessionIndex", "Waveform", "Kcoords", "Xcoords", "Ycoords", "PETH"):
            refs = group.create_dataset(name, shape=(2, 1), dtype=h5py.ref_dtype)
            for unit in range(2):
                value = {"RatName": np.array([78, 97]),
                         "SpikeTimes": np.array([[1., 2.]]),
                         "SessionIndex": np.array([[unit + 1]]),
                         "Waveform": np.arange(6).reshape(3, 2) + shift + unit,
                         "Kcoords": np.array([[1, 1]]),
                         "Xcoords": np.array([[10, 20]]),
                         "Ycoords": np.array([[30, 40]]),
                         "PETH": np.array([[1., 2., 3., 4.]])}[name]
                refs[unit, 0] = h.create_dataset(name + str(unit), data=value).ref
        waveform_offset = h["Waveform0"].id.get_offset()
    return waveform_offset


def asset(path):
    raw = path.read_bytes()
    return {**e.ROSTER["Nasha"], "bytes": len(raw),
            "checksum": "md5:" + hashlib.md5(raw).hexdigest()}


class ConversionSourceIdentity(unittest.TestCase):
    def test_stable_source_preserves_arrays_and_binds_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source.mat", root / "converted"
            fixture(source)
            raw = source.read_bytes()
            with patch.dict(e.ROSTER, {"Nasha": asset(source)}):
                result = e.convert_spikeinfo(source, output, "Nasha")
            self.assertEqual(result["source"], {"name": "source.mat", "bytes": len(raw),
                                               "sha256": hashlib.sha256(raw).hexdigest()})
            np.testing.assert_array_equal(np.load(output / "waveform_all.npy", allow_pickle=False)[0],
                                          [[0, 2, 4], [1, 3, 5]])
            self.assertEqual((result["unit_count"], result["session_count"]), (2, 2))
            self.assertFalse(result["scientific_qualified"])

    def test_path_replacement_cannot_substitute_unauthenticated_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, replacement, output = root / "source.mat", root / "replacement.mat", root / "converted"
            fixture(source)
            fixture(replacement, shift=100)
            frozen = asset(source)
            original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            real_file = h5py.File

            def replace_before_decode(value, mode, *args, **kwargs):
                os.replace(replacement, source)
                return real_file(value, mode, *args, **kwargs)

            with patch.dict(e.ROSTER, {"Nasha": frozen}), patch.object(h5py, "File", replace_before_decode):
                try:
                    result = e.convert_spikeinfo(source, output, "Nasha")
                except e.ContractError:
                    self.assertFalse(output.exists())
                else:
                    # A retained descriptor may remain stable after a pathname
                    # replacement. Its original bytes are the only valid output.
                    self.assertEqual(result["source"]["sha256"], original_sha)
                    np.testing.assert_array_equal(
                        np.load(output / "waveform_all.npy", allow_pickle=False)[0],
                        [[0, 2, 4], [1, 3, 5]])
            self.assertEqual(list(root.glob(".spikeinfo-*")), [])

    def test_in_place_mutation_after_decode_cannot_publish(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source.mat", root / "converted"
            offset = fixture(source)
            frozen = asset(source)
            real_stack = np.stack
            changed = False

            def mutate_after_decode(*args, **kwargs):
                nonlocal changed
                if not changed:
                    changed = True
                    with source.open("r+b") as stream:
                        stream.seek(offset)
                        stream.write(np.array([900], dtype=np.int64).tobytes())
                return real_stack(*args, **kwargs)

            with patch.dict(e.ROSTER, {"Nasha": frozen}), patch.object(np, "stack", mutate_after_decode):
                with self.assertRaises(e.ContractError):
                    e.convert_spikeinfo(source, output, "Nasha")
            self.assertTrue(changed)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".spikeinfo-*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
