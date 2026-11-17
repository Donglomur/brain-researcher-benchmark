import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import numpy as np
    from scipy.io import savemat
except ImportError:
    np = None
from prepare_mat import prepare


@unittest.skipIf(np is None, "Optional MAT conversion needs an existing numpy/scipy runtime")
class PrepareTests(unittest.TestCase):
    def save(self, path, neural=None, position=None):
        savemat(path, {"Hippocampus_data": {"session_A": {"R_neuron_binned": np.array([[0, 1, 0, 1] * 2, [1, 1, 0, 0] * 2]) if neural is None else neural, "Position": np.arange(8) if position is None else position}}})

    def test_generated_mat_readthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generated.mat"; self.save(path)
            identities = {"session_A": {"animal_id": "generated-animal", "neuron_ids": ["a", "b"]}}
            packet = prepare(path, "Hippocampus_data", identities)
            self.assertEqual(packet["sessions"][0]["neural"][0], [0, 1])
            self.assertEqual(len(packet["sessions"][0]["stimulus"]), 8)
            self.assertEqual(packet["data_kind"], "operator_prepared_unqualified")
            self.assertEqual(len(packet["provenance"]["file_sha256"]), 64)
            json.dumps(packet, allow_nan=False)
            with self.assertRaises(ValueError): prepare(path, "invented_root", identities)
            with self.assertRaises(ValueError): prepare(path, "Hippocampus_data", {})

    def test_noninteger_raw_traces_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generated.mat"
            self.save(path, neural=np.array([[.5] * 8, [1.] * 8]))
            with self.assertRaises(ValueError): prepare(path, "Hippocampus_data", {"session_A": {"animal_id": "a", "neuron_ids": ["x", "y"]}})


if __name__ == "__main__": unittest.main()
