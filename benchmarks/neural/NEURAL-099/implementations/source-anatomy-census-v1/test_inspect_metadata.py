"""Independent generated NWB metadata controls; no authentic neural arrays."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import h5py
import numpy as np


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_neural099_metadata_review", HERE / "inspect_metadata.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def fixture(path):
    """Three clusters on two contacts; IDs deliberately differ from row indices."""
    text = h5py.string_dtype("utf-8")
    with h5py.File(path, "w") as f:
        f.attrs["nwb_version"] = "2.7.0"
        f.create_dataset("session_description", data="clicks", dtype=text)
        f.create_dataset("session_start_time", data="2021-01-01T12:00:00-05:00", dtype=text)
        f.create_dataset("timestamps_reference_time", data=["2021-01-01T12:00:00-05:00"], dtype=text)
        f.create_dataset("general/subject/subject_id", data="generated-animal", dtype=text)
        f.create_dataset("general/session_id", data="generated-clicks", dtype=text)
        signal = f.create_group("acquisition/ExampleLFP")
        signal.attrs["neurodata_type"] = "ElectricalSeries"
        signal.create_dataset("data", data=np.ones((5, 2)))
        f.create_group("processing")
        g = f.create_group("general/extracellular_ephys/Shank1")
        g.attrs["location"] = "MGN"
        t = f.create_group("general/extracellular_ephys/electrodes")
        t.create_dataset("id", data=np.array([90, 12], dtype=np.int64))
        t.create_dataset("location", data=[" ", "MGv"], dtype=text)
        t.create_dataset("group", data=np.array([g.ref, g.ref], dtype=h5py.ref_dtype))
        for axis, data in {"x": [0., 0.], "y": [20., 40.], "z": [0., np.nan]}.items():
            t.create_dataset(axis, data=data)
        u = f.create_group("units")
        u.create_dataset("id", data=np.array([100, 200, 300], dtype=np.int64))
        d = u.create_dataset("electrodes", data=np.array([1, 0, 1], dtype=np.int64))
        d.attrs["table"] = t.ref
        u.create_dataset("quality", data=["good", "mua", "mua"], dtype=text)
        u.create_dataset("spike_times", data=np.array([.01, .02, .03, .04, .05, .06, .07, .08]))
        u.create_dataset("spike_times_index", data=np.array([3, 6, 8], dtype=np.uint64))
        u.create_dataset("waveforms", data=np.ones((3, 8)))
        u.create_dataset("obs_intervals", data=np.array([[0., 5.]]))
        trials = f.create_group("intervals/trials")
        trials.create_dataset("id", data=[0, 1])
        trials.create_dataset("start_time", data=[1., 2.])
        trials.create_dataset("stop_time", data=[1.0001, 2.0001])


def source(path):
    return {"asset_id": "generated-asset", "path": "generated.nwb",
            "bytes": path.stat().st_size, "sha256": reader.digest(path),
            "subject_id": "generated-animal"}


class MetadataCensusControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "generated.nwb"
        fixture(self.path)

    def run_reader(self):
        return reader.inspect(self.path, source(self.path))

    def test_anatomical_rows_not_ids_or_broad_probe_label(self):
        result = self.run_reader()
        self.assertEqual(result["declared_unit_count"], 3)
        self.assertEqual(result["source_anatomy_unit_counts"], {" ": 1, "MGv": 2})
        self.assertEqual([x["electrode_row"] for x in result["unit_assignments"]], [1, 0, 1])
        self.assertEqual([x["location_literal"] for x in result["unit_assignments"]], ["MGv", " ", "MGv"])
        self.assertEqual([x["group_location"] for x in result["unit_assignments"]], ["MGN"] * 3)
        self.assertEqual(result["source_quality_unit_counts"], {"good": 1, "mua": 2})

    def test_only_metadata_dataset_values_are_opened(self):
        actual_get = h5py.Dataset.__getitem__
        opened = []
        def guarded(item, key):
            opened.append(item.name)
            if item.name.lstrip("/") not in reader.ALLOWED_ARRAYS | reader.ALLOWED_SCALARS:
                raise AssertionError("Response or schema-only dataset was read: " + item.name)
            return actual_get(item, key)
        with mock.patch.object(h5py.Dataset, "__getitem__", guarded):
            result = self.run_reader()
        self.assertTrue(opened)
        self.assertFalse(result["response_array_values_opened"])
        self.assertTrue(result["obs_intervals_present"])
        self.assertEqual(result["schema"]["units/spike_times"]["shape"], [8])
        self.assertEqual(result["schema"]["units/obs_intervals"]["shape"], [1, 2])
        self.assertNotIn("/units/obs_intervals", opened)
        self.assertNotIn("/acquisition/ExampleLFP/data", opened)
        self.assertEqual(result["signal_container_schema"]["acquisition"]["ExampleLFP"]["attrs"]["neurodata_type"], "ElectricalSeries")
        self.assertEqual(result["signal_container_schema"]["processing"], {})
        self.assertIsNone(result["signal_container_schema"]["analysis"])

    def test_absent_coverage_is_not_imputed_from_spikes(self):
        with h5py.File(self.path, "a") as f:
            del f["units/obs_intervals"]
        result = self.run_reader()
        self.assertFalse(result["obs_intervals_present"])
        self.assertNotIn("units/obs_intervals", result["schema"])
        self.assertNotIn("recording_duration", result)
        self.assertNotIn("rate", result)

    def test_coordinate_values_remain_in_deposited_scale(self):
        result = self.run_reader()
        self.assertEqual(result["nwb_version"], "2.7.0")
        self.assertEqual(result["coordinate_support"]["y"]["unique_finite_values"], [20., 40.])
        self.assertFalse(result["coordinate_support"]["y"]["physical_unit_conversion_applied"])
        self.assertEqual(result["coordinate_support"]["z"]["finite"], 1)
        self.assertEqual(result["coordinate_support"]["z"]["total"], 2)

    def test_large_integer_unit_identity_is_exact(self):
        with h5py.File(self.path, "a") as f:
            del f["units/id"]
            f.create_dataset("units/id", data=np.array([2**63 + 13, 2**63 + 14, 2**63 + 15], dtype=np.uint64))
        result = self.run_reader()
        self.assertEqual(result["unit_assignments"][0]["unit_id"], 2**63 + 13)

    def test_duplicate_unit_ids_refused(self):
        with h5py.File(self.path, "a") as f:
            f["units/id"][1] = 100
        with self.assertRaisesRegex(ValueError, "Duplicate unit"):
            self.run_reader()

    def test_invalid_contact_indices_refused_without_subset(self):
        for index in [-1, 2, 90]:
            with self.subTest(index=index):
                with h5py.File(self.path, "a") as f:
                    f["units/electrodes"][0] = index
                with self.assertRaisesRegex(ValueError, "Invalid electrode-row"):
                    self.run_reader()

    def test_ragged_contact_schema_requires_explicit_handling(self):
        with h5py.File(self.path, "a") as f:
            f.create_dataset("units/electrodes_index", data=[1, 2, 3])
        with self.assertRaisesRegex(ValueError, "Ragged contact"):
            self.run_reader()

    def test_incorrect_contact_table_reference_refused(self):
        with h5py.File(self.path, "a") as f:
            other = f.create_group("other_table")
            f["units/electrodes"].attrs["table"] = other.ref
        with self.assertRaisesRegex(ValueError, "outside the electrode table"):
            self.run_reader()

    def test_direct_metadata_softlink_refused(self):
        with h5py.File(self.path, "a") as f:
            f.move("units/quality", "quality_elsewhere")
            f["units/quality"] = h5py.SoftLink("/quality_elsewhere")
        with self.assertRaisesRegex(ValueError, "Indirect metadata link"):
            self.run_reader()

    def test_parent_metadata_softlink_refused(self):
        with h5py.File(self.path, "a") as f:
            f.move("general/subject", "subject_elsewhere")
            f["general/subject"] = h5py.SoftLink("/subject_elsewhere")
        with self.assertRaisesRegex(ValueError, "Indirect metadata link"):
            self.run_reader()

    def test_unallowlisted_response_read_is_refused(self):
        with h5py.File(self.path, "r") as f:
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                reader.meta_read(f, "units/spike_times")

    def test_source_mutation_refused_before_hdf_open(self):
        original = source(self.path)
        with h5py.File(self.path, "a") as f:
            f["units/id"][0] = 101
        with mock.patch.object(reader.h5py, "File", side_effect=AssertionError("Must refuse before opening HDF")):
            with self.assertRaisesRegex(ValueError, "Source content differs"):
                reader.inspect(self.path, original)

    def test_hardlink_alias_to_response_index_is_not_metadata(self):
        with h5py.File(self.path, "a") as f:
            del f["units/id"]
            f["units/id"] = f["units/spike_times_index"]
        actual_get = h5py.Dataset.__getitem__
        def guarded(item, key):
            if item.id == item.file["units/spike_times_index"].id:
                raise AssertionError("Response-derived index was opened through a metadata alias")
            return actual_get(item, key)
        with mock.patch.object(h5py.Dataset, "__getitem__", guarded):
            with self.assertRaisesRegex(ValueError, "alias|Alias|role|Role"):
                self.run_reader()


if __name__ == "__main__":
    unittest.main()
