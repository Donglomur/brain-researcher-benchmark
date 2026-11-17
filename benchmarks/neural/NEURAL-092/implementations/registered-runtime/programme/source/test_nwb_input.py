"""Invented tiny HDF5 fixtures only; no authentic NWB values are opened."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import h5py
import numpy as np

spec = importlib.util.spec_from_file_location("nwb_input_generated", Path(__file__).with_name("nwb_input.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def descriptor(path):
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def strings(g, name, values):
    g.create_dataset(name, data=values, dtype=h5py.string_dtype("utf-8"))


def fixture(path):
    with h5py.File(path, "w") as f:
        units = f.create_group("units")
        units["id"] = [101, 102, 103, 104]
        units["peak_channel_id"] = [11, 12, 13, 999]
        strings(units, "quality", ["good", "good", "noise", "good"])
        units["amplitude_cutoff"] = [.1, .101, .01, .01]
        units["presence_ratio"] = [.95, .96, .99, .99]
        units["isi_violations"] = [.5, .1, .1, .1]
        units["spike_times_index"] = [5, 6, 6, 7]
        units["spike_times"] = np.array([0., .5, 1., 1., 2., .2, .3], dtype="f8")
        electrodes = f.create_group("general/extracellular_ephys/electrodes")
        electrodes["id"] = [13, 11, 12]
        strings(electrodes, "location", ["VISl", "VISp", "LGd"])
        electrodes["valid_data"] = [True, True, False]
        for family, extra in m.FAMILY_EXTRA.items():
            g = f.create_group("intervals/" + family + "_presentations")
            for field in m.BASE_FIELDS | extra:
                if field == "id":
                    g[field] = [1, 2]
                elif field == "start_time":
                    g[field] = [.1, 1.1]
                elif field == "stop_time":
                    g[field] = [.3, 1.3]
                elif field == "stimulus_name":
                    strings(g, field, [family, family])
                elif field in ("mask", "phase", "size", "units", "color"):
                    strings(g, field, ["native", "null"])
                else:
                    g[field] = [0., np.nan if field == "orientation" else 1.]
            strings(g, "tags", ["stimulus", "stimulus"])
            g["tags_index"] = [1, 2]
            g["timeseries"] = [0, 0]
            g["timeseries_index"] = [1, 2]
        g = f.create_group("intervals/invalid_times")
        g["id"] = [1, 2, 3]
        g["start_time"] = [.2, .4, 1.5]
        g["stop_time"] = [.5, .8, 1.7]
        strings(g, "tags", ["probeA", "all_probes", "stimulus"])
        g["tags_index"] = [1, 2, 3]
        for name in ("running_speed", "running_speed_end_times"):
            g = f.create_group("processing/running/" + name)
            g["timestamps"] = [0., .5, 1.] if name == "running_speed" else [.5, 1., 1.5]
            g["timestamps"].attrs["unit"] = "seconds"
            g["data"] = [-2., 4., np.nan]
            g["data"].attrs["unit"] = "cm/s"


class NWBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.path = self.root / "fixture.nwb"
        fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_hash_same_fd_and_channel_id_join(self):
        with m.opened(self.path, descriptor(self.path)) as f:
            table = m.select_units(f)
            self.assertEqual([r["id"] for r in table["units"]], [101])
            self.assertEqual(table["units"][0]["area"], "VISp")
            self.assertEqual(table["units"][0]["spike_stop"], 5)
            self.assertIn("failed_amplitude_cutoff", table["all_units"][1]["reasons"])
            self.assertIn("invalid_channel_data", table["all_units"][1]["reasons"])
            self.assertIn("missing_peak_channel", table["all_units"][3]["reasons"])

    def test_wrong_hash_and_symlink_paths_rejected(self):
        bad = descriptor(self.path)
        bad["sha256"] = "0" * 64
        with self.assertRaises(m.InputError):
            with m.opened(self.path, bad):
                pass
        link = self.root / "link.nwb"
        link.symlink_to(self.path)
        with self.assertRaises((m.InputError, OSError)):
            with m.opened(link, descriptor(self.path)):
                pass
        parent = self.root / "linked_parent"
        parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises((m.InputError, OSError)):
            with m.opened(parent / self.path.name, descriptor(self.path)):
                pass
        with self.assertRaises(m.InputError):
            with m.opened(parent / ".." / self.path.name, descriptor(self.path)):
                pass

    def test_replaced_source_name_detected_after_use(self):
        pin = descriptor(self.path)
        copy = self.root / "copy.nwb"
        copy.write_bytes(self.path.read_bytes())
        with self.assertRaises(m.InputError):
            with m.opened(self.path, pin):
                os.replace(copy, self.path)

    def test_soft_external_and_virtual_links_rejected(self):
        for kind in ("soft", "external", "vds"):
            p = self.root / (kind + ".h5")
            with h5py.File(p, "w", libver="latest") as f:
                f["data"] = [1., 2.]
                if kind == "soft":
                    f["bad"] = h5py.SoftLink("/data")
                elif kind == "external":
                    f["bad"] = h5py.ExternalLink("missing.h5", "/data")
                else:
                    layout = h5py.VirtualLayout(shape=(2,), dtype="f8")
                    layout[:] = h5py.VirtualSource(str(p), "data", shape=(2,))
                    f.create_virtual_dataset("bad", layout)
            with self.assertRaises(m.UnsupportedSchema):
                with m.opened(p, descriptor(p)):
                    pass

    def test_all_native_scalar_fields_and_missing_values(self):
        with m.opened(self.path, descriptor(self.path)) as f:
            for family in m.FAMILY_EXTRA:
                rows = m.intervals(f, family)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["stimulus_name"], family)
                self.assertEqual(rows[1]["phase"], "null")
                self.assertIsNone(rows[1]["orientation"])
                self.assertIn("orientation", rows[1]["missing_scalar_fields"])
                self.assertEqual(rows[0]["tags"], ["stimulus"])

    def test_invalid_union_uses_every_tag(self):
        with m.opened(self.path, descriptor(self.path)) as f:
            invalid = m.invalid_intervals(f)
            np.testing.assert_array_equal(invalid["intervals"], [[.2, .8], [1.5, 1.7]])
            self.assertEqual(len(invalid["rows"]), 3)

    def test_half_open_spike_windows_and_full_ragged_identity(self):
        with m.opened(self.path, descriptor(self.path)) as f:
            units = m.select_units(f)["units"]
            got = m.count_windows(f, units, [[0., .5], [.5, 1.], [1., 2.], [2., 3.]])
            np.testing.assert_array_equal(got[:, 0], [1, 1, 2, 1])
            changed = [dict(units[0], spike_stop=4)]
            with self.assertRaises(m.InputError):
                m.count_windows(f, changed, [[0., 1.]])

    def test_unsorted_unit_spikes_and_bad_ragged_extent_rejected(self):
        with h5py.File(self.path, "r+") as f:
            f["units/spike_times"][1] = 3.
        with m.opened(self.path, descriptor(self.path)) as f:
            with self.assertRaises(m.UnsupportedSchema):
                m.count_windows(f, m.select_units(f)["units"], [[0., 1.]])
        with h5py.File(self.path, "r+") as f:
            f["units/spike_times_index"][-1] = 6
        with m.opened(self.path, descriptor(self.path)) as f:
            with self.assertRaises(m.UnsupportedSchema):
                m.select_units(f)

    def test_running_interval_weighted_absolute_and_missing_pupil(self):
        with m.opened(self.path, descriptor(self.path)) as f:
            state = m.state_covariates(f, [[0., 1.], [.25, .75], [1., 1.5], [1.5, 2.]])
            self.assertEqual(state["running"], [3., 3., None, None])
            self.assertEqual(state["pupil"], [None] * 4)
            self.assertEqual(state["support"]["pupil"], "missing_filtered_gaze_mapping")
            self.assertEqual(state["support"]["running_windows"][2]["nonfinite_speed_samples"], 1)

    def test_running_overlap_units_and_unknown_fields_rejected(self):
        with h5py.File(self.path, "r+") as f:
            f["processing/running/running_speed_end_times/timestamps"][0] = .6
        with m.opened(self.path, descriptor(self.path)) as f:
            with self.assertRaises(m.UnsupportedSchema):
                m.state_covariates(f, [[0., 1.]])
        with h5py.File(self.path, "r+") as f:
            f["intervals/static_gratings_presentations/unknown_metric"] = [0., 1.]
        with m.opened(self.path, descriptor(self.path)) as f:
            with self.assertRaises(m.UnsupportedSchema):
                m.intervals(f, "static_gratings")

    def test_pupil_uses_inside_values_brackets_for_support_only(self):
        with h5py.File(self.path, "r+") as f:
            g = f.create_group("processing/filtered_gaze_mapping/pupil_area")
            g["timestamps"] = np.arange(31.) / 30
            g["timestamps"].attrs["unit"] = "seconds"
            g["data"] = np.full(31, 10.)
            g["data"].attrs["unit"] = "Pixels ^ 2"
            g["data"].attrs["conversion"] = 1.
            # Upper bracket at .5 is invalid, but belongs to neither the mean
            # nor finite-positive support of the [.0,.5) query.
            g["data"][15] = np.nan
        with m.opened(self.path, descriptor(self.path)) as f:
            s = m.state_covariates(f, [[0., .5], [.5, 1.], [1., 1.1]])
            self.assertEqual(s["pupil"], [10., None, None])
            self.assertEqual(s["support"]["pupil_windows"][0]["inside_samples"], 15)
            self.assertEqual(s["support"]["pupil_windows"][1]["status"], "nonfinite_or_nonpositive_inside_sample")
            self.assertIn("may be noncausal", s["support"]["publisher_filter_causality"])

    def test_pupil_gap_is_missing_not_interpolated(self):
        with h5py.File(self.path, "r+") as f:
            g = f.create_group("processing/filtered_gaze_mapping/pupil_area")
            g["timestamps"] = [0., .02, .2, .22]
            g["timestamps"].attrs["unit"] = "seconds"
            g["data"] = [1., 2., 3., 4.]
            g["data"].attrs["unit"] = "Pixels ^ 2"
        with m.opened(self.path, descriptor(self.path)) as f:
            s = m.state_covariates(f, [[0., .2]])
            self.assertEqual(s["pupil"], [None])
            self.assertEqual(s["support"]["pupil_windows"][0]["status"], "sampling_gap_over_0.05_seconds")


if __name__ == "__main__":
    unittest.main(verbosity=2)
