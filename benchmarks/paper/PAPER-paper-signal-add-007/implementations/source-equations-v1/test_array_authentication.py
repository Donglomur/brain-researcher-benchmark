"""Generated retained-descriptor controls; no original observations are read."""
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np

SPEC = importlib.util.spec_from_file_location("icnet_array_authentication", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def fixture(root):
    descriptors = {}
    for name, value in (("counts", 1), ("first", 1), ("replacement", 9)):
        path = root / (name + ".npy")
        np.save(path, np.full((2, 512), value, dtype=np.int16))
        descriptors[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    arrays = {name: descriptors["counts"] for name in scorer.ARRAY_NAMES}
    panel = {"schema": "icnet-source-equations-input/v1", "variance_ddof": 0,
             "preparation": {"source_mask_sha256": "1"*64, "alignment_protocol_sha256": "2"*64,
                             "prediction_freeze_sha256": "3"*64, "measurement_times_sha256": "4"*64,
                             "mask_origin": "source_broadband_noise_reliability",
                             "split": "original_four_sounds_held_out_from_training"},
             "animals": {str(a): {"unit_ids": [f"column_{i}" for i in range(512)],
                                   "eligible_mask": [i < (500 if a == 9 else 496) for i in range(512)]}
                         for a in scorer.ANIMALS},
             "cases": [{"animal": a, "sound": s, "time_bins": 2,
                        "measurement_times_seconds": [1, 2], "arrays": dict(arrays)}
                       for a in scorer.ANIMALS for s in scorer.SOUNDS]}
    panel["cases"][0]["arrays"]["recorded_trial1"] = descriptors["first"]
    return panel


class ArrayAuthenticationTests(unittest.TestCase):
    def test_complete_panel_uses_authenticated_descriptor_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); panel = fixture(root); fired = []
            real_sha = hashlib.sha256
            class Digest:
                def __init__(self, *a, **k): self.inner = real_sha(*a, **k)
                def update(self, b): self.inner.update(b)
                def hexdigest(self):
                    result = self.inner.hexdigest()
                    if not fired:
                        fired.append(True)
                        (root / "replacement.npy").replace(root / "first.npy")
                    return result
            with mock.patch.object(scorer.hashlib, "sha256", Digest):
                try:
                    result = scorer.score_panel(panel, root)
                except ValueError as exc:
                    self.assertIn("changed", str(exc))
                else:
                    self.assertEqual(result["cases"][0]["flattened"]["mean_count"], 1.)
                    self.assertEqual(len(result["cases"]), 28)
            self.assertEqual(fired, [True])

    def test_complete_panel_refuses_mutation_during_numeric_consumption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); panel = fixture(root); original_score = scorer.score_case; fired = []
            def mutate_after_read(*args, **kwargs):
                result = original_score(*args, **kwargs)
                if not fired:
                    fired.append(True)
                    with (root / "first.npy").open("r+b") as stream:
                        stream.seek(-1, 2); stream.write(b"\x01")
                return result
            with mock.patch.object(scorer, "score_case", side_effect=mutate_after_read):
                with self.assertRaisesRegex(ValueError, "changed during scoring"):
                    scorer.score_panel(panel, root)
            self.assertEqual(fired, [True])

    def test_stable_full_panel_preserves_complete_support_and_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); panel = fixture(root)
            result = scorer.score_panel(panel, root)
            self.assertEqual(len(result["cases"]), 28)
            self.assertEqual(sum(c["eligible_units"] for c in result["cases"]), 4*3476)
            self.assertTrue(all(c["flattened"]["mean_count"] == 1 for c in result["cases"]))
            self.assertFalse(result["reproduction_evaluated"])
            self.assertFalse(result["improvement_evaluated"])

    def test_numeric_npy_versions_orders_and_mapping_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for version in ((1, 0), (2, 0), (3, 0)):
                for fortran in (False, True):
                    value = np.arange(6, dtype=np.float64).reshape(2, 3)
                    if fortran: value = np.asfortranarray(value)
                    path = root / "array.npy"
                    with path.open("wb") as stream:
                        np.lib.format.write_array(stream, value, version=version)
                    entry = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    with scorer._load_array(root, entry) as actual:
                        self.assertIsInstance(actual, np.memmap)
                        self.assertFalse(actual.flags.writeable)
                        np.testing.assert_array_equal(actual, value)
                        self.assertEqual(actual.flags.f_contiguous, value.flags.f_contiguous)


if __name__ == "__main__":
    unittest.main()
