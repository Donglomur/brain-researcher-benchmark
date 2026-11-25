"""Generated HDF5 authentication controls; fixtures are not source assets."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("BENCHMARK_EVALUATOR_SOURCE", ROOT / "evaluator.py"))
spec = importlib.util.spec_from_file_location("pac_verified_nwb", SOURCE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture(path, offset=0):
    with h5py.File(path, "w") as f:
        f["general/subject/subject_id"] = "26"
        f["general/session_id"] = "1"
        f["acquisition/LFPs/data"] = np.arange(4 * 33).reshape(4, 33) + offset
        f["acquisition/LFPs/starting_time"] = 2.0
        f["acquisition/LFPs/starting_time"].attrs["rate"] = 400.0
        for name, values in (("timestamps_Maintenance", [4.0, 6.0]),
                             ("loads", [1, 3]), ("response_accuracy", [1, 1])):
            f["intervals/trials/" + name] = values
        f["units/spike_times"] = np.arange(40.0)
        f["units/spike_times_index"] = np.arange(2, 41, 2)
    receipt = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "bytes": path.stat().st_size,
               "path": "sub-26/sub-26_ses-1_ecephys+image.nwb",
               "asset_id": "GENERATED-ENGINEERING-CONTROL",
               "version": e.SNAPSHOT, "dandiset": "000673"}
    return receipt


def generated_pin(receipt):
    return patch.dict(e.SOURCE, {"su": {**e.SOURCE["su"],
        "asset_sha256": receipt["sha256"], "asset_bytes": receipt["bytes"],
        "asset_id": receipt["asset_id"]}})


class VerifiedNWBTests(unittest.TestCase):
    def test_unchanged_generated_values_and_source_pin_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "generated.nwb"
            receipt = fixture(path)
            with self.assertRaisesRegex(ValueError, "source-reported"):
                e.load_nwb(path, receipt, example="su")
            with generated_pin(receipt):
                result = e.load_nwb(path, receipt, example="su")
            np.testing.assert_array_equal(result["raw"], np.arange(4 * 33).reshape(4, 33)[:, 32])
            np.testing.assert_array_equal(result["spikes"], [38, 39])
            self.assertEqual(result["fs"], 400)

    def test_path_replacement_after_hash_cannot_change_decoded_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "generated.nwb"
            receipt = fixture(path)
            replacement = root / "replacement.nwb"
            fixture(replacement, offset=1000)
            original_file = h5py.File
            def replace_then_open(*args, **kwargs):
                os.replace(replacement, path)
                return original_file(*args, **kwargs)
            with generated_pin(receipt), patch.object(h5py, "File", side_effect=replace_then_open):
                with self.assertRaisesRegex(ValueError, "changed"):
                    e.load_nwb(path, receipt, example="su")

    def test_in_place_write_after_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "generated.nwb"
            receipt = fixture(path)
            original_file = h5py.File
            def mutate_then_open(*args, **kwargs):
                with original_file(path, "r+") as writable:
                    writable["acquisition/LFPs/data"][:] += 1000
                return original_file(*args, **kwargs)
            with generated_pin(receipt), patch.object(h5py, "File", side_effect=mutate_then_open):
                with self.assertRaisesRegex(ValueError, "changed"):
                    e.load_nwb(path, receipt, example="su")


if __name__ == "__main__":
    unittest.main()
