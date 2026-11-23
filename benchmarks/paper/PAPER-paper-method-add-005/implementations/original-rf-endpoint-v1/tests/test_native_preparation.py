"""Tiny generated NetCDF controls; no native data, model or RF execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_preparation", ROOT / "native_preparation.py")
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


def fixture():
    values = np.empty((8, 3, 7), dtype=np.float64)
    for event in range(8):
        values[event, 0] = event + np.arange(7)
        values[event, 1] = event * 3 + np.arange(7) * 2
    values[:, -1] = 99  # The label at time coordinate 0 is deliberately invalid.
    values[:, -1, 0] = [1, 2, 1, 2, 1, 2, 1, 2]
    values[1, 0, 1:6] = 100  # Quality exclusion must not remove this RF event.
    return xr.Dataset({"ecog": (n.DIMENSIONS, values)}, coords={
        "events": [3, 1, 2, 1, 3, 2, 7, 7], "channels": [0, 1, 2],
        "time": [-3., -2., -1., 0., 1., 2., 3.],
    })


class NativePreparationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "generated_ecog_data.nc"
        fixture().to_netcdf(self.source, engine="scipy")
        self.digest = n.endpoint.digest_file(self.source)
        self.args = dict(expected_sha256=self.digest, participant="EC01", kind="generated_control")

    def test_source_positional_extraction_and_all_event_decoder_support(self):
        arrays, metadata = n.prepare_netcdf(self.source, **self.args)
        with xr.open_dataset(self.source) as source:
            # Exercise the pinned author's actual xarray indexing operations.
            train_index = [1, 3, 2, 5, 0, 4]
            source_train = source[dict(events=train_index, channels=slice(0, 2),
                                       time=np.arange(1, 6))].to_array().values.squeeze()
            source_labels = source[dict(events=train_index, channels=source.channels[-1],
                                        time=0)].to_array().values.squeeze() - 1.0
            source_test = source[dict(events=[6, 7], channels=slice(0, 2),
                                      time=np.arange(1, 6))].to_array().values.squeeze()
        np.testing.assert_array_equal(arrays["train_labels"], source_labels)
        np.testing.assert_array_equal(arrays["test_labels"], [0, 1])
        self.assertEqual(metadata["train_source_indices"], train_index)
        self.assertEqual(metadata["train_events"] + metadata["test_events"], 8)
        self.assertFalse(arrays["train_quality"][0, 0])
        np.testing.assert_allclose(arrays["train_mean"][0], source_train[1:, 0].mean())
        np.testing.assert_allclose(arrays["train_scale"][0], source_train[1:, 0].std())
        recovered_train = arrays["train_z"] * arrays["train_scale"][None, :, None] + arrays["train_mean"][None, :, None]
        np.testing.assert_allclose(recovered_train, source_train)
        observed, _ = n.endpoint.observed_channels(2, .5, 0)
        decoder = n.endpoint.decoder_inputs(arrays["test_z"], arrays["train_mean"], arrays["train_scale"],
                                           {arm: arrays["test_z"] for arm in n.endpoint.IMPUTERS}, observed)
        np.testing.assert_allclose(decoder["fully_observed"], source_test.reshape(2, -1), rtol=2e-7, atol=2e-6)
        self.assertEqual(arrays["native_row_ids"][0], f"sha256:{self.digest}:event:0")
        self.assertEqual(metadata["native_extraction"]["dimension_order"], list(n.DIMENSIONS))
        self.assertEqual(metadata["historical_paper_day7_mapping"], "unresolved")

    def test_hash_rejected_before_dataset_open_and_changed_file_rejected(self):
        with patch.object(xr, "open_dataset", side_effect=AssertionError("must not open")):
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                n.prepare_netcdf(self.source, **dict(self.args, expected_sha256="0" * 64))
        with patch.object(n.endpoint, "digest_file", side_effect=[self.digest, "0" * 64]):
            with self.assertRaisesRegex(ValueError, "changed during extraction"):
                n.prepare_netcdf(self.source, **self.args)

    def test_ambiguous_variables_axis_reordering_and_missing_coordinates_fail(self):
        cases = {
            "multiple": fixture().assign(second=fixture().ecog),
            "transposed": fixture().transpose("channels", "events", "time"),
            "missing": fixture().drop_vars("events"),
        }
        for name, dataset in cases.items():
            with self.subTest(name=name):
                path = self.root / f"{name}.nc"
                dataset.to_netcdf(path, engine="scipy")
                with self.assertRaises(ValueError):
                    n.prepare_netcdf(path, **dict(self.args, expected_sha256=n.endpoint.digest_file(path)))

    def test_cli_bundle_roundtrip_and_no_overwrite(self):
        output = self.root / "operator-bundle"
        argv = [str(self.source), str(output), "--expected-sha256", self.digest,
                "--participant", "EC01", "--kind", "generated_control"]
        n.main(argv)
        metadata = json.loads((output / "preparation.json").read_text())
        artifact = metadata["prepared_artifact"]
        npz = output / artifact["path"]
        self.assertEqual(artifact["sha256"], n.endpoint.digest_file(npz))
        self.assertEqual(artifact["bytes"], npz.stat().st_size)
        with np.load(npz, allow_pickle=False) as arrays:
            self.assertEqual(set(arrays), set(metadata["array_identities"]))
            for name in arrays:
                self.assertEqual(n.endpoint.array_digest(arrays[name]), metadata["array_identities"][name])
        with patch.object(n, "prepare_netcdf", side_effect=AssertionError("must not re-extract")):
            with self.assertRaises(SystemExit) as error:
                n.main(argv)
        self.assertEqual(error.exception.code, 2)

    def test_failed_serialization_leaves_no_partial_bundle(self):
        arrays, metadata = n.prepare_netcdf(self.source, **self.args)
        output = self.root / "failed-bundle"
        with patch.object(n.json, "dump", side_effect=OSError("generated write failure")):
            with self.assertRaisesRegex(OSError, "generated write failure"):
                n.write_bundle(output, arrays, metadata)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
