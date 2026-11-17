"""Generated timing and fake HDF-boundary checks; no h5py/data/network imports."""

from copy import deepcopy
from types import SimpleNamespace
import unittest

from inspect_clicks import (ClickInspectionError, TRIAL_PATHS, read_trial_columns,
                            validate_trial_rows)


class TimingTests(unittest.TestCase):
    def test_negative_reference_times_and_source_ids_preserved(self):
        ids, starts, stops = [42, -7, 13], [-1., -.5, 0.], [-.9999, -.4999, .0001]
        before = deepcopy((ids, starts, stops))
        result = validate_trial_rows(ids, starts, stops, expected_rows=3)
        self.assertEqual(result["rows"], [
            {"row_ordinal": 0, "source_trial_id": 42, "start_time": -1., "stop_time": -.9999},
            {"row_ordinal": 1, "source_trial_id": -7, "start_time": -.5, "stop_time": -.4999},
            {"row_ordinal": 2, "source_trial_id": 13, "start_time": 0., "stop_time": .0001}])
        self.assertEqual((ids, starts, stops), before)
        self.assertFalse(result["continuous_support_verified"])
        self.assertFalse(result["timing_stats"]["recording_extent_inferred"])
        self.assertEqual(result["timing_stats"]["minimum_onset_interval_seconds"], .5)

    def test_global_history_response_overlap_refused(self):
        # Each history is disjoint from its own future, but the second history
        # would expose part of the first scored response if supplied statically.
        with self.assertRaisesRegex(ClickInspectionError, "history overlaps"):
            validate_trial_rows([1, 2], [0., .15], [.0001, .1501], expected_rows=2)

    def test_half_open_touching_edges_are_allowed(self):
        result = validate_trial_rows([1, 2], [0., .2], [.0001, .2001], expected_rows=2)
        self.assertTrue(result["timing_stats"]["history_response_windows_disjoint"])
        with self.assertRaises(ClickInspectionError):
            validate_trial_rows([1, 2], [0., .199999], [.0001, .200099], expected_rows=2)

    def test_complete_row_membership_is_required(self):
        for columns in (([1], [0., .5], [.0001, .5001]),
                        ([1, 2], [0.], [.0001, .5001]),
                        ([1, 2], [0., .5], [.0001]),
                        ([1, 2, 3], [0., .5, 1.], [.0001, .5001, 1.0001])):
            with self.subTest(columns=columns):
                with self.assertRaises(ClickInspectionError):
                    validate_trial_rows(*columns, expected_rows=2)
        with self.assertRaises(ClickInspectionError):
            validate_trial_rows([], [], [], expected_rows=0)

    def test_all_206_rows_are_retained(self):
        starts = [index / 2 for index in range(206)]
        result = validate_trial_rows(list(range(1000, 1206)), starts,
                                     [v + .0001 for v in starts], expected_rows=206)
        self.assertEqual(len(result["rows"]), 206)
        self.assertEqual(result["rows"][-1]["source_trial_id"], 1205)

    def test_nonfinite_duplicate_bool_and_nonchronological_values_refused(self):
        cases = [
            ([1, 1], [0., .5], [.0001, .5001]),
            ([True, 2], [0., .5], [.0001, .5001]),
            ([1, 2 ** 63], [0., .5], [.0001, .5001]),
            ([1, 2], [0., float("nan")], [.0001, .5001]),
            ([1, 2], [False, .5], [.0001, .5001]),
            ([1, 2], [0., .5], [.0001, float("inf")]),
            ([1, 2], [.5, 0.], [.5001, .0001]),
            ([1, 2], [0., 0.], [.0001, .0002]),
            ([1, 2], [0., .5], [1., .5001]),
            ([1, 2], [0., .5], [0., .5001]),
        ]
        for columns in cases:
            with self.subTest(columns=columns):
                with self.assertRaises(ClickInspectionError):
                    validate_trial_rows(*columns, expected_rows=2)

    def test_unrepresentable_absolute_bins_refused(self):
        with self.assertRaisesRegex(ClickInspectionError, "not representable"):
            validate_trial_rows([1], [1e15], [1e15 + 1], expected_rows=1)


class HardLink:
    pass


class SoftLink:
    pass


class ExternalLink:
    pass


class FakeArray:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return list(self.values)


class Dataset:
    def __init__(self, values, kind):
        self.values, self.shape = values, (len(values),)
        self.dtype = SimpleNamespace(kind=kind, itemsize=8, fields=None, subdtype=None)
        self.is_virtual, self.external, self.reads = False, [], 0
        self.chunks, self.filters = None, []
        self.id = SimpleNamespace(get_create_plist=lambda: self)

    def get_nfilters(self):
        return len(self.filters)

    def get_filter(self, index):
        return (self.filters[index], 0, (), b"generated")

    def __getitem__(self, key):
        if key != ():
            raise AssertionError("Only the bounded whole-column read is expected")
        self.reads += 1
        return FakeArray(self.values)


class Group:
    def __init__(self, children):
        self.children = children
        self.links = {name: HardLink() for name in children}

    def get(self, name, *, getlink=False):
        if not getlink:
            raise AssertionError("Link inspection must precede dereference")
        return self.links.get(name)

    def __getitem__(self, name):
        if not isinstance(self.links.get(name), HardLink):
            raise AssertionError("Forbidden indirect link was dereferenced")
        return self.children[name]


H5_API = SimpleNamespace(HardLink=HardLink, Group=Group, Dataset=Dataset)


def fake_file():
    datasets = {"id": Dataset([8, 19], "i"),
                "start_time": Dataset([0., .5], "f"),
                "stop_time": Dataset([.0001, .5001], "f")}
    trials = Group(datasets)
    intervals = Group({"trials": trials})
    handle = Group({"intervals": intervals})
    return handle, intervals, trials, datasets


class HdfBoundaryTests(unittest.TestCase):
    def test_only_three_allowlisted_columns_are_read(self):
        handle, _, _, datasets = fake_file()
        # A trap outside the allowlist must never be looked up or read.
        handle.children["units"] = object()
        # An explicitly bounded built-in compressed layout is supported.
        datasets["id"].chunks = (2,)
        datasets["id"].filters = [2, 1, 3]
        values = read_trial_columns(handle, h5api=H5_API, expected_rows=2)
        self.assertEqual(values, [[8, 19], [0., .5], [.0001, .5001]])
        self.assertEqual([dataset.reads for dataset in datasets.values()], [1, 1, 1])

    def test_soft_external_and_missing_links_refused_at_each_component(self):
        for depth in range(3):
            for indirect in (SoftLink(), ExternalLink(), None):
                with self.subTest(depth=depth, indirect=type(indirect).__name__):
                    handle, intervals, trials, datasets = fake_file()
                    node, name = [(handle, "intervals"), (intervals, "trials"),
                                  (trials, "id")][depth]
                    node.links[name] = indirect
                    with self.assertRaises(ClickInspectionError):
                        read_trial_columns(handle, h5api=H5_API, expected_rows=2)
                    self.assertTrue(all(dataset.reads == 0 for dataset in datasets.values()))

    def test_all_headers_vetted_before_any_values_are_read(self):
        mutations = [
            lambda d: setattr(d, "is_virtual", True),
            lambda d: setattr(d, "external", [("other.bin", 0, 16)]),
            lambda d: setattr(d, "shape", (2, 1)),
            lambda d: setattr(d, "shape", (3,)),
            lambda d: setattr(d.dtype, "itemsize", 4),
            lambda d: setattr(d.dtype, "kind", "i"),
            lambda d: setattr(d.dtype, "fields", {"value": object()}),
            lambda d: setattr(d, "chunks", (131073,)),
            lambda d: setattr(d, "chunks", (2, 1)),
            lambda d: setattr(d, "filters", [32000]),
            lambda d: setattr(d, "filters", [1]),
            lambda d: setattr(d, "filters", [1, 1]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                handle, _, _, datasets = fake_file()
                mutation(datasets["stop_time"])
                with self.assertRaises(ClickInspectionError):
                    read_trial_columns(handle, h5api=H5_API, expected_rows=2)
                self.assertTrue(all(dataset.reads == 0 for dataset in datasets.values()))


if __name__ == "__main__":
    unittest.main()
