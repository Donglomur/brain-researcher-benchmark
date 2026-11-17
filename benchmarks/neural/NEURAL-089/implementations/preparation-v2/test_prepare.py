"""Generated software controls; no authentic arrays, annotations or model fits."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare
import numpy as np
import h5py


def load_predecessor():
    spec = importlib.util.spec_from_file_location(
        "neural089_prepare_predecessor", HERE.parent / "delivery-source/prepare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREDECESSOR = load_predecessor()
SOURCE_PATHS = [prepare.SOURCE_FILES[name][0] for name in ("lock", "classes", "channels")]


class NoNeuralRead:
    ndim = 2
    dtype = np.dtype("float32")

    def __init__(self, samples):
        self.shape = (306, samples)

    def __getitem__(self, key):
        raise AssertionError("clock inspection must not read neural values")


class GeneratedHeader(dict):
    def __init__(self, times):
        super().__init__(data=NoNeuralRead(len(times)), times=times)
        self.attrs = {"sample_frequency": 250., "channel_names": "C", "channel_types": "mag"}


class PreparationTests(unittest.TestCase):
    def test_exact_original_source_membership(self):
        lock, classes, channels = prepare.source_specifications(*SOURCE_PATHS)
        self.assertEqual(len(lock["runs"]), 90)
        self.assertEqual([sum(r["split"] == s for r in lock["runs"])
                          for s in ("train", "validation", "query")], [88, 1, 1])
        self.assertEqual(len(classes), 39)
        self.assertEqual(len(channels["channel_names"]), 306)

    def test_byte_identical_relocation_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            relocated = []
            for index, source in enumerate(SOURCE_PATHS):
                destination = Path(folder) / str(index)
                destination.write_bytes(source.read_bytes())
                relocated.append(destination)
            self.assertEqual(prepare.source_specifications(*relocated),
                             prepare.source_specifications(*SOURCE_PATHS))

    def test_predecessor_accepts_substituted_specifications_until_asset_access(self):
        """Counterexamples retain the previous structural checks and native counts."""
        values = [json.loads(p.read_bytes()) for p in SOURCE_PATHS]
        changes = []
        changed = copy.deepcopy(values[0])
        next(r for r in changed["runs"] if r["split"] == "train")["run_key"][1] = "999"
        changes.append((0, changed))
        changed = copy.deepcopy(values[1])
        changed["classes"][0], changed["classes"][1] = changed["classes"][1], changed["classes"][0]
        changes.append((1, changed))
        changed = copy.deepcopy(values[2])
        changed["channel_names"][0], changed["channel_names"][1] = (
            changed["channel_names"][1], changed["channel_names"][0])
        changes.append((2, changed))
        for field, changed in changes:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                alternate = root / "alternate.json"
                alternate.write_text(json.dumps(changed))
                paths = SOURCE_PATHS.copy()
                paths[field] = alternate
                key = root / "key"
                key.write_bytes(b"k" * 32)
                operands = (*paths, root, root / "output", key, 1_000_000_000)
                with mock.patch.object(PREDECESSOR, "verify_asset",
                                       side_effect=RuntimeError("recording opened")):
                    with self.assertRaisesRegex(RuntimeError, "recording opened"):
                        PREDECESSOR.build(*operands)
                with mock.patch.object(prepare, "verify_asset",
                                       side_effect=AssertionError("recording opened")):
                    with self.assertRaises(ValueError):
                        prepare.build(*operands)
                self.assertFalse((root / "output").exists())

    def test_rejected_source_does_not_open_key_or_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / "lock"
            lock.write_bytes(SOURCE_PATHS[0].read_bytes().replace(b'Sherlock1', b'Sherlock9'))
            read = prepare.read
            forbidden = root / "must-not-open-key"

            def guard(path, *args, **kwargs):
                self.assertNotEqual(path, forbidden)
                return read(path, *args, **kwargs)

            with mock.patch.object(prepare, "read", side_effect=guard):
                with self.assertRaisesRegex(ValueError, "exact frozen original lock"):
                    prepare.build(lock, *SOURCE_PATHS[1:], root, root / "output", forbidden, 1_000_000)
            self.assertFalse((root / "output").exists())

    def test_sample_local_rounding_and_early_clock_drift(self):
        schema = {"channel_names": ["C"], "channel_types": ["mag"]}
        for dtype in (np.float32, np.float64):
            with self.subTest(dtype=dtype):
                times = (np.arange(201500, dtype=np.float64) / 250).astype(dtype)
                self.assertEqual(prepare.inspect_h5(GeneratedHeader(times), schema), 201500)
                altered = times.copy()
                altered[25] += (2e-5 if dtype == np.float32 else 1e-14)
                # This drift is much larger than stored rounding at 0.1 sec,
                # yet the predecessor grants every sample the last sample's tolerance.
                self.assertEqual(PREDECESSOR.inspect_h5(GeneratedHeader(altered), schema), 201500)
                with self.assertRaisesRegex(ValueError, "sample-local"):
                    prepare.inspect_h5(GeneratedHeader(altered), schema)

    def test_one_ulp_allowed_but_two_rejected(self):
        schema = {"channel_names": ["C"], "channel_types": ["mag"]}
        for dtype in (np.float32, np.float64):
            times = (np.arange(500) / 250).astype(dtype)
            times[125] = np.nextafter(times[125], dtype(np.inf))
            self.assertEqual(prepare.inspect_h5(GeneratedHeader(times), schema), 500)
            times[125] = np.nextafter(times[125], dtype(np.inf))
            with self.assertRaises(ValueError):
                prepare.inspect_h5(GeneratedHeader(times), schema)

    def test_origin_monotonicity_and_chunk_boundary(self):
        schema = {"channel_names": ["C"], "channel_types": ["mag"]}
        times = (np.arange(65538) / 250).astype(np.float32)
        for index, value in ((0, .004), (65536, times[65535]), (65536, np.nan)):
            with self.subTest(index=index, value=value):
                altered = times.copy()
                altered[index] = value
                with self.assertRaises(ValueError):
                    prepare.inspect_h5(GeneratedHeader(altered), schema)

    def test_generated_hdf5_transform_and_query_privacy_preserved(self):
        # Known channel offsets and temporal slope make window alignment and
        # population standardization independently checkable by hand.
        signal = np.arange(250, dtype=np.float64)[None, :] + np.arange(306)[:, None]
        mean, std, samples = prepare.training_stats([signal[:, :137], signal[:, 137:]])
        np.testing.assert_allclose(mean, np.arange(306) + 124.5, rtol=0, atol=1e-12)
        np.testing.assert_allclose(std, np.sqrt((250 ** 2 - 1) / 12), rtol=0, atol=1e-12)
        self.assertEqual(samples, 250)
        events, accounting = prepare.parse_events(
            b"idx\tkind\tsegment\ttimemeg\n0\tphoneme\taa_B\t0.5\n1\tphoneme\tsil\t0\n",
            ["aa"], 250)
        self.assertEqual(accounting["target_rows"], 1)
        self.assertEqual(events[0]["start"], 125)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "query.h5"
            records = prepare.write_run(path, signal, events, mean, std, b"k" * 32, "a" * 64, False)
            with h5py.File(path, "r") as result:
                self.assertEqual(set(result), {"windows", "ids"})
                self.assertEqual(result["windows"].shape, (1, 306, 125))
                expected = np.broadcast_to((np.arange(125, 250) - 124.5) / std[0], (306, 125)).astype("<f4")
                np.testing.assert_array_equal(result["windows"][0], expected)
                self.assertEqual(result["ids"][0].decode(), records[0]["query_id"])
                self.assertEqual(result.attrs["units"], "training_channel_standard_deviations")
                self.assertNotIn("label", result.attrs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
