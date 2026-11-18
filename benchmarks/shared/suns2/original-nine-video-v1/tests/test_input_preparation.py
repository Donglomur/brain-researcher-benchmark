"""Generated fake-interface controls; no h5py import or scientific arrays."""
import io
import hashlib
import math
import os
import pathlib
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from suns2_benchmark import input_preparation as prep


class Dtype:
    kind = "u"
    itemsize = 2
    byteorder = "<"
    fields = subdtype = metadata = None
    hasobject = False

    def __str__(self):
        return f"{self.kind}{self.itemsize}"


class Attrs:
    def __init__(self, count=0):
        self.count = count

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        raise AssertionError("attribute values must not be accessed")


class DCPL:
    def __init__(self, filters=(), external=0, layout=1):
        self.filters, self.external, self.layout = filters, external, layout
        self.closed = False

    def get_nfilters(self):
        return len(self.filters)

    def get_filter(self, i):
        return self.filters[i]

    def get_external_count(self):
        return self.external

    def get_layout(self):
        return self.layout

    def close(self):
        self.closed = True


class Block:
    def __init__(self, shape, dtype, finite=True):
        self.shape, self.dtype, self.finite = shape, dtype, finite
        self.size = math.prod(shape)
        self.nbytes = self.size * dtype.itemsize


class Dataset:
    def __init__(self, shape=prep.VIDEO_SHAPE, *, dtype=None, chunks=None, filters=(), external=0,
                 virtual=False, attrs=0, finite=True):
        self.shape = shape
        self.size = math.prod(shape)
        self.dtype = dtype or Dtype()
        self.chunks = chunks
        self.is_virtual = virtual
        self.attrs = Attrs(attrs)
        self.finite = finite
        self.requests = []
        self.dcpl = DCPL(filters, external, 3 if virtual else 2 if chunks else 1)
        self.id = types.SimpleNamespace(get_create_plist=lambda: self.dcpl)

    def __getitem__(self, selection):
        self.requests.append(selection)
        return Block(tuple(s.stop-s.start for s in selection), self.dtype, self.finite)


class HardLink:
    pass


class File:
    def __init__(self, records, links=None, attrs=0):
        self.records = dict(records)
        self.links = links or {k: HardLink() for k in self.records}
        self.attrs = Attrs(attrs)

    def __len__(self):
        return len(self.records)

    def keys(self):
        return self.records.keys()

    def get(self, key, getlink=False):
        assert getlink is True
        return self.links[key]

    def __getitem__(self, key):
        return self.records[key]


H5 = types.SimpleNamespace(Dataset=Dataset, HardLink=HardLink, h5d=types.SimpleNamespace(VIRTUAL=3))
NP = types.SimpleNamespace(isfinite=lambda block: types.SimpleNamespace(all=lambda: block.finite))


class Fapl:
    def __init__(self, broken=False):
        self.cache = [0, 1, 1, 0.0]
        self.config = types.SimpleNamespace(set_initial_size=0, initial_size=1, min_size=1, max_size=1)
        self.broken = broken
        self.closed = False

    def set_fileobj_driver(self, driver, reader):
        self.driver, self.reader = driver, reader

    def get_cache(self):
        return self.cache

    def set_cache(self, *values):
        if not self.broken:
            self.cache = list(values)

    def get_mdc_config(self):
        return self.config

    def set_mdc_config(self, config):
        self.config = config

    def close(self):
        self.closed = True


def deadline():
    return time.monotonic() + 30


class PreparationControls(unittest.TestCase):
    def test_module_import_does_not_import_h5py(self):
        self.assertFalse(any(k == "h5py" or k.startswith("h5py.") for k in sys.modules))

    def test_bounded_reader_counts_and_denies_writes(self):
        stream = prep.BoundedReadOnlyFile(io.BytesIO(b"abcd"), 4, deadline())
        for _ in range(4):
            self.assertEqual(stream.read(), b"abcd")
            stream.seek(0)
        self.assertEqual(stream.returned_bytes, 16)
        with self.assertRaises(prep.PreparationRefused):
            stream.read(1)
        for call in (lambda: stream.seek(5), lambda: stream.seek(-1), lambda: stream.write(b"x"),
                     lambda: stream.truncate(0)):
            with self.assertRaises(prep.PreparationRefused):
                call()
        self.assertEqual(stream.source.getvalue(), b"abcd")

    def test_readinto_and_truncation_accounting(self):
        stream = prep.BoundedReadOnlyFile(io.BytesIO(b"abc"), 3, deadline())
        target = bytearray(2)
        self.assertEqual(stream.readinto(target), 2)
        self.assertEqual(target, b"ab")
        self.assertEqual(stream.read(10), b"c")
        broken = prep.BoundedReadOnlyFile(io.BytesIO(b"a"), 3, deadline())
        with self.assertRaises(prep.PreparationRefused):
            broken.read(3)
        self.assertEqual(broken.returned_bytes, 1)

    def test_deadline_refuses_before_read(self):
        source = io.BytesIO(b"a")
        stream = prep.BoundedReadOnlyFile(source, 1, time.monotonic()-1)
        with self.assertRaises(prep.PreparationRefused):
            stream.read()
        self.assertEqual(stream.returned_bytes, 0)

    def test_source_selection_is_ordered_largest_not_shape_fallback(self):
        full = Dataset()
        selected, info = prep.select_root_dataset(File([("small", Dataset((2,))), ("full", full)]), H5, "video", deadline())
        self.assertIs(selected, full)
        self.assertEqual(info["selected_name"], "full")
        wrong = Dataset((50, 50, 6000))
        with self.assertRaises(prep.PreparationRefused):
            prep.select_root_dataset(File([("first_tied_wrong", wrong), ("full", full)]), H5, "video", deadline())
        self.assertEqual(full.requests, [])

    def test_links_groups_and_metadata_limits_fail_before_values(self):
        full = Dataset()
        cases = [File([("x", full)], links={"x": object()}),
                 File([("group", types.SimpleNamespace(attrs=Attrs()))]),
                 File([("x", Dataset(attrs=33))]),
                 File([("x", full)], attrs=33),
                 File([(f"x{i}", Dataset((1,))) for i in range(33)])]
        for handle in cases:
            with self.subTest(handle=handle), self.assertRaises(prep.PreparationRefused):
                prep.select_root_dataset(handle, H5, "video", deadline())
        self.assertEqual(full.requests, [])

    def test_structural_types_external_virtual_and_filters(self):
        dtype = Dtype()
        dtype.metadata = {"vlen": "object"}
        for data in (Dataset(dtype=dtype), Dataset(external=1), Dataset(virtual=True),
                     Dataset(chunks=(1, 50, 50), filters=((32001, 1, (), b"plugin"),)),
                     Dataset(chunks=(1, 50, 50), filters=((1, 1, (10,), b"deflate"),)),
                     Dataset(chunks=(1, 50, 50), filters=((2, 1, (8,), b"shuffle"),))):
            with self.subTest(data=data), self.assertRaises(prep.PreparationRefused):
                prep.dataset_profile(data, H5, "video")
            self.assertEqual(data.requests, [])

    def test_unselected_decoy_storage_is_screened(self):
        for small in (Dataset((2,), external=1), Dataset((2,), virtual=True),
                      Dataset((2,), chunks=(2,), filters=((32001, 1, (), b"plugin"),))):
            full = Dataset()
            with self.assertRaises(prep.PreparationRefused):
                prep.select_root_dataset(File([("small", small), ("full", full)]), H5, "video", deadline())
            self.assertEqual(small.requests + full.requests, [])

    def test_chunk_expansion_count_and_allowed_filter_profiles(self):
        for chunks in ((6000, 50, 50), (1, 1, 1)):
            with self.assertRaises(prep.PreparationRefused):
                prep.dataset_profile(Dataset(chunks=chunks), H5, "video")
        data = Dataset(chunks=(100, 50, 50), filters=((2, 1, (2,), b"shuffle"), (1, 1, (6,), b"deflate")))
        profile = prep.dataset_profile(data, H5, "video")
        self.assertEqual(profile["chunk_count"], 60)
        result = prep.scan_dataset(data, profile, NP, deadline())
        self.assertEqual(result["elements_read"], 15000000)
        self.assertEqual(len(data.requests), 60)
        self.assertEqual(len({tuple((s.start, s.stop) for s in req) for req in data.requests}), 60)

    def test_complete_contiguous_read_does_not_sample(self):
        data = Dataset()
        profile = prep.dataset_profile(data, H5, "video")
        result = prep.scan_dataset(data, profile, NP, deadline())
        self.assertEqual(result["logical_value_bytes_read"], 30000000)
        self.assertEqual(result["elements_read"], 15000000)
        self.assertEqual(data.requests[0][0].start, 0)
        self.assertEqual(data.requests[-1][0].stop, 6000)
        self.assertTrue(all((req[0].stop-req[0].start)*50*50*2 <= 1048576 for req in data.requests))

    def test_nonfinite_float_refused(self):
        dtype = Dtype()
        dtype.kind, dtype.itemsize = "f", 4
        data = Dataset(dtype=dtype, finite=False)
        with self.assertRaises(prep.PreparationRefused) as caught:
            prep.scan_dataset(data, prep.dataset_profile(data, H5, "video"), NP, deadline())
        self.assertEqual(len(data.requests), 1)
        self.assertGreater(caught.exception.scan_progress["returned_logical_bytes"], 0)
        self.assertEqual(caught.exception.scan_progress["completed_selections"], 0)
        self.assertFalse(caught.exception.scan_progress["failed_native_selection_return_unknown"])

    def test_dtype_native_alias_and_swapped_endian_guard(self):
        base = {"kind": "u", "itemsize": 2, "byteorder": "=", "description": "uint16"}
        native = "<" if sys.byteorder == "little" else ">"
        alias = dict(base, byteorder=native, description="u2")
        self.assertEqual(prep._dtype_semantics(base), prep._dtype_semantics(alias))
        for changed in (dict(base, byteorder=">" if native == "<" else "<"),
                        dict(base, kind="i"), dict(base, itemsize=4)):
            self.assertNotEqual(prep._dtype_semantics(base), prep._dtype_semantics(changed))
        with self.assertRaises(prep.PreparationRefused):
            prep._dtype_semantics(dict(base, byteorder="|"))
        one = dict(base, itemsize=1)
        self.assertEqual(prep._dtype_semantics(one), prep._dtype_semantics(dict(one, byteorder="|")))

    def test_dtype_mismatch_receipt_preserves_both_profiles(self):
        class DifferentDecodedDataset(Dataset):
            def __getitem__(self, selection):
                result = super().__getitem__(selection)
                result.dtype = Dtype()
                result.dtype.kind = "i"
                return result
        data = DifferentDecodedDataset((1, 4))
        profile = prep.dataset_profile(data, H5, "template")
        with self.assertRaises(prep.PreparationRefused) as caught:
            prep.scan_dataset(data, profile, NP, deadline())
        progress = caught.exception.scan_progress
        self.assertEqual(progress["source_dtype"]["kind"], "u")
        self.assertEqual(progress["decoded_dtype"]["kind"], "i")
        self.assertEqual(progress["returned_logical_bytes"], 8)
        self.assertFalse(progress["failed_native_selection_return_unknown"])

    def test_template_name_vector_bound_and_quarantine_profile(self):
        data = Dataset((1, 100))
        _, profile = prep.select_root_dataset(File([("filter_tempolate", data)]), H5, "template", deadline())
        self.assertEqual(profile["elements"], 100)
        for name, shape in (("wrong", (1, 100)), ("filter_tempolate", (2, 2)),
                            ("filter_tempolate", (4097,))):
            with self.assertRaises(prep.PreparationRefused):
                prep.select_root_dataset(File([(name, Dataset(shape))]), H5, "template", deadline())

    def test_cache_configuration_roundtrips_and_failure_closes(self):
        for broken in (False, True):
            fapl = Fapl(broken)
            h5 = types.SimpleNamespace(h5p=types.SimpleNamespace(FILE_ACCESS=1, create=lambda _: fapl),
                                       h5fd=types.SimpleNamespace(fileobj_driver=2))
            if broken:
                with self.assertRaises(prep.PreparationRefused):
                    prep.configure_fapl(h5, object())
                self.assertTrue(fapl.closed)
            else:
                result = prep.configure_fapl(h5, object())
                self.assertIs(result, fapl)
                self.assertEqual(result.config.max_size, prep.META_CACHE_BYTES)
                self.assertEqual(result.get_cache()[2], prep.RAW_CACHE_BYTES)

    def test_initializer_refuses_bad_environment_or_preimport_before_native(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(prep.PreparationRefused):
                prep.initialize_runtime({}, "/does-not-exist")
        with patch.dict(os.environ, {"HDF5_PLUGIN_PRELOAD": "::"}, clear=True):
            with patch.dict(sys.modules, {"h5py": object()}):
                with self.assertRaises(prep.PreparationRefused):
                    prep.initialize_runtime({}, "/does-not-exist")

    def test_missing_full_panel_refused_before_bank_open(self):
        with self.assertRaises(prep.PreparationRefused):
            prep.inspect_bank("/does-not-exist", [], object())

    def test_metadata_cap_preserves_compact_completed_costs(self):
        entries = [{"name": f"{video}.h5", "bytes": prep.MAX_FILE_BYTES, "sha256":"0"*64}
                   for video in prep.VIDEO_IDS]
        entries.append({"name":"1P_spike_tempolate.h5", "bytes":2048, "sha256":"0"*64})
        def fake_inspect(root_fd, entry, role, runtime, stop):
            return {"name":entry["name"], "source_hash_bytes":10,
                    "file_adapter":{"returned_bytes":20},
                    "readability":{"logical_value_bytes_read":30}, "large_metadata":"x"*60000}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(prep, "inspect_one", side_effect=fake_inspect):
                with self.assertRaises(prep.PreparationRefused) as caught:
                    prep.inspect_bank(str(pathlib.Path(tmp).resolve()), entries, object())
        progress = caught.exception.bank_progress
        self.assertEqual(progress["completed_file_count"], 2)
        self.assertEqual(progress["completed_source_hash_bytes"], 20)
        self.assertEqual(progress["completed_logical_value_bytes_returned"], 60)
        self.assertNotIn("large_metadata", str(progress))
        self.assertLess(len(str(progress)), 4096)

    def test_complete_roster_entry_schema_preflight_precedes_bank_open(self):
        entries = [{"name": f"{video}.h5", "bytes": prep.MAX_FILE_BYTES, "sha256":"0"*64}
                   for video in prep.VIDEO_IDS]
        entries.append({"name":"1P_spike_tempolate.h5", "bytes":2048, "sha256":"invalid"})
        with self.assertRaises(prep.PreparationRefused):
            prep.inspect_bank("/does-not-exist", entries, object())

    def _native_lifecycle(self, *, constructor_fails=False, native_close_fails=False,
                          handle_close_fails=False, fapl_close_fails=False, nonfinite=False):
        events, opened = [], []
        class ID:
            valid = True
            def close(self):
                events.append("id-close")
                if native_close_fails:
                    raise RuntimeError("generated native close failure")
                self.valid = False
        native_id = ID()
        class Cache(Fapl):
            def close(self):
                events.append("fapl-close")
                if fapl_close_fails:
                    raise RuntimeError("generated fapl close failure")
                self.closed = True
        cache = Cache()
        dtype = Dtype()
        dtype.kind = "f"
        data = Dataset((4,), dtype=dtype, finite=not nonfinite)
        class Handle(File):
            def close(self):
                events.append("handle-close")
                native_id.valid = False
                if handle_close_fails:
                    raise RuntimeError("generated high-level close failure")
        def construct(identifier):
            events.append("construct")
            if constructor_fails:
                raise RuntimeError("generated wrapper construction failure")
            return Handle([("filter_tempolate", data)])
        h5 = types.SimpleNamespace(Dataset=Dataset, HardLink=HardLink, h5d=H5.h5d,
             h5p=types.SimpleNamespace(FILE_ACCESS=1, create=lambda _: cache),
             h5fd=types.SimpleNamespace(fileobj_driver=2),
             h5f=types.SimpleNamespace(ACC_RDONLY=0, open=lambda *a, **k: native_id), File=construct)
        runtime = prep.NativeRuntime(h5, NP, {"h5py":"fake", "numpy":"fake", "hdf5":"fake"}, "fake", True)
        original_open = prep._authenticate_open
        def record_open(*args):
            result = original_open(*args)
            opened.append(result[0])
            return result
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            value = b"generated-only"
            (root/"fixture.h5").write_bytes(value)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with patch.object(prep, "_authenticate_open", side_effect=record_open):
                    try:
                        prep.inspect_one(fd, {"name":"fixture.h5", "bytes":len(value),
                            "sha256":hashlib.sha256(value).hexdigest()}, "template", runtime, deadline())
                    except BaseException as exc:
                        result = exc
                    else:
                        result = None
                is_closed = opened[0].closed
                if native_close_fails or constructor_fails or handle_close_fails:
                    retained = prep._UNCLOSED_NATIVE_RESOURCES.pop()
                    native_id.valid = False  # Test-only cleanup of a fake ID.
                    retained[-2].close()
                    retained[-1].close()
            finally:
                os.close(fd)
        return result, events, is_closed

    def test_constructor_failure_preserves_native_uncertainty(self):
        error, events, closed = self._native_lifecycle(constructor_fails=True)
        self.assertIsInstance(error, prep.PreparationRefused)
        self.assertEqual(events, ["construct", "id-close", "fapl-close"])
        self.assertFalse(closed)
        self.assertTrue(error.partial_receipt["native_closure_unverified"])

    def test_handle_close_failure_does_not_trust_invalid_file_id_alone(self):
        error, events, closed = self._native_lifecycle(handle_close_fails=True)
        self.assertIsInstance(error, prep.PreparationRefused)
        self.assertFalse(closed)
        self.assertTrue(error.native_closure_unverified)

    def test_fapl_close_error_does_not_skip_source_close(self):
        error, events, closed = self._native_lifecycle(fapl_close_fails=True)
        self.assertIsInstance(error, prep.PreparationRefused)
        self.assertTrue(closed)
        self.assertFalse(error.native_closure_unverified)
        self.assertIn("fapl-close", events)
        self.assertGreater(error.partial_receipt["scan_progress"]["returned_logical_bytes"], 0)

    def test_unknown_native_close_retains_backing_source_and_costs(self):
        error, events, closed = self._native_lifecycle(constructor_fails=True, native_close_fails=True)
        self.assertIsInstance(error, prep.PreparationRefused)
        self.assertFalse(closed)
        self.assertTrue(error.native_closure_unverified)
        self.assertEqual(error.partial_receipt["source_hash_bytes"], len(b"generated-only"))

    def test_partial_nonfinite_read_costs_survive_failure(self):
        error, events, closed = self._native_lifecycle(nonfinite=True)
        self.assertIsInstance(error, prep.PreparationRefused)
        self.assertTrue(closed)
        self.assertEqual(error.partial_receipt["scan_progress"]["returned_logical_bytes"], 8)
        self.assertEqual(error.partial_receipt["scan_progress"]["completed_selections"], 0)


if __name__ == "__main__":
    unittest.main()
