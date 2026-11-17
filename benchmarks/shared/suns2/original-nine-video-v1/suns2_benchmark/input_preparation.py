"""Bounded original SUNS2 HDF5 schema and complete-read preparation.

Importing this module never imports h5py or opens data. Actual use requires an
independently admitted clean process, authenticated inputs, a frozen runtime,
and the external wall/RSS monitor. Generated tests exercise fake HDF5 objects.
The temporal template remains quarantined even after a successful read.
"""
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

from .constants import VIDEO_IDS

MAX_ROOT_OBJECTS = 32
MAX_ATTRIBUTES = 32
MAX_NAME_BYTES = 256
MAX_CHUNK_BYTES = 16 * 1024 * 1024
MAX_CHUNKS = 65536
RAW_CACHE_BYTES = 4 * 1024 * 1024
META_CACHE_BYTES = 16 * 1024 * 1024
INITIAL_META_CACHE_BYTES = 1024 * 1024
CONTIGUOUS_SLICE_BYTES = 1024 * 1024
MAX_METADATA_BYTES = 65536
MAX_FILE_BYTES = 30001400
VIDEO_SHAPE = (6000, 50, 50)
MAX_VIDEO_ELEMENTS = 15000000
MAX_VIDEO_LOGICAL_BYTES = 120000000
MAX_TEMPLATE_ELEMENTS = 4096
MAX_TEMPLATE_LOGICAL_BYTES = 32768
ALLOWED_FILTERS = (1, 2, 3)
# On an unverifiable native close, retain the backing object until the owned
# process is terminated. Never close a fileobj while a native file ID may use it.
_UNCLOSED_NATIVE_RESOURCES = []


class PreparationRefused(ValueError):
    """Input, runtime or resource profile differs from the admitted contract."""


def _need(condition, message):
    if not condition:
        raise PreparationRefused(message)


def _tick(deadline):
    _need(time.monotonic() < deadline, "HDF5 preparation deadline exceeded")


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class BoundedReadOnlyFile:
    """A fixed-file HDF5 fileobj driver with application-level read accounting.

The backing file remains owned by the caller and must outlive the HDF5 handle.
The accounting counts bytes returned to HDF5, not OS physical I/O or the prior
authentication pass. No data bytes are retained in this adapter.
"""
    def __init__(self, source, size, deadline):
        _need(type(size) is int and 0 < size <= MAX_FILE_BYTES, "source file size bound")
        self.source = source
        self.size = size
        self.deadline = deadline
        self.return_cap = 4 * size
        self.returned_bytes = 0
        self.read_calls = 0
        self.read_failures = 0
        self.seek_calls = 0
        self.closed = False

    def _check(self):
        _tick(self.deadline)
        _need(not self.closed, "read adapter is closed")

    def tell(self):
        self._check()
        position = self.source.tell()
        _need(0 <= position <= self.size, "source position outside authenticated file")
        return position

    def seek(self, offset, whence=0):
        self._check()
        _need(type(offset) is int and whence in (0, 1, 2), "invalid bounded seek")
        base = 0 if whence == 0 else self.tell() if whence == 1 else self.size
        position = base + offset
        _need(0 <= position <= self.size, "seek outside authenticated file")
        self.seek_calls += 1
        return self.source.seek(position, 0)

    def read(self, size=-1):
        self._check()
        _need(type(size) is int and size >= -1, "invalid read size")
        remaining = self.size - self.tell()
        amount = remaining if size == -1 else min(size, remaining)
        _need(amount <= self.return_cap - self.returned_bytes, "HDF5 file-read budget exceeded")
        self.read_calls += 1
        try:
            data = self.source.read(amount)
        except BaseException:
            self.read_failures += 1
            raise
        self.returned_bytes += len(data)
        _need(len(data) == amount, "authenticated source truncated during HDF5 read")
        return data

    def readinto(self, buffer):
        view = memoryview(buffer).cast("B")
        data = self.read(len(view))
        view[:len(data)] = data
        return len(data)

    def readable(self):
        return not self.closed

    def seekable(self):
        return not self.closed

    def writable(self):
        return False

    def write(self, *args, **kwargs):
        raise PreparationRefused("HDF5 source writes are forbidden")

    def truncate(self, *args, **kwargs):
        raise PreparationRefused("HDF5 source truncation is forbidden")

    def flush(self):
        self._check()

    def close(self):
        self.closed = True

    def receipt(self):
        return {"returned_bytes": self.returned_bytes, "return_cap_bytes": self.return_cap,
                "read_calls": self.read_calls, "seek_calls": self.seek_calls,
                "read_failures": self.read_failures,
                "physical_IO_bytes": None}


@dataclass(frozen=True)
class NativeRuntime:
    h5py: object
    numpy: object
    observed_versions: dict
    plugin_directory: str
    clean_preimport_verified: bool


def initialize_runtime(expected_versions, plugin_directory):
    """Verify the prelaunch plugin environment, then import existing bindings.

This mirrors retained N099's reviewed HDF5_PLUGIN_PRELOAD='::' mechanism.
It never assumes h5py.h5pl.set_loading_state exists. The caller must use a
fresh pinned launcher which sets the environment before starting Python;
checking sys.modules alone cannot prove no other extension loaded HDF5.
Runtime/version selection is supplied by the trusted frozen native protocol.
"""
    _need(os.environ.get("HDF5_PLUGIN_PRELOAD") == "::",
          "HDF5_PLUGIN_PRELOAD=:: must be set before Python startup")
    _need(not any(k == "h5py" or k.startswith("h5py.") for k in sys.modules),
          "fresh unimported h5py stack required")
    root = Path(plugin_directory)
    _need(root.is_absolute() and not root.is_symlink(), "absolute nonsymlink plugin directory required")
    info = root.stat()
    _need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
          and info.st_mode & 0o077 == 0 and not any(root.iterdir()),
          "plugin directory must be empty, private and owner-controlled")
    _need(os.environ.get("HDF5_PLUGIN_PATH") == str(root), "prelaunch plugin directory mismatch")
    _need(type(expected_versions) is dict and set(expected_versions) == {"h5py", "numpy", "hdf5"},
          "trusted exact runtime versions required")
    import h5py  # Deliberately lazy; not executed by generated fake-object controls.
    import numpy
    observed = {"h5py": str(h5py.__version__), "numpy": str(numpy.__version__),
                "hdf5": str(h5py.version.hdf5_version)}
    _need(observed == expected_versions, "native runtime version mismatch")
    return NativeRuntime(h5py, numpy, observed, str(root), True)


def configure_fapl(h5py, reader):
    """Configure caches before data are opened; unsupported APIs fail closed.

The local h5py source/tests expose fileobj, get/set_cache and get/set_mdc_config.
Actual availability and round-trip values remain part of native qualification.
"""
    fapl = h5py.h5p.create(h5py.h5p.FILE_ACCESS)
    try:
        fapl.set_fileobj_driver(h5py.h5fd.fileobj_driver, reader)
        settings = list(fapl.get_cache())
        _need(len(settings) == 4, "unknown raw cache configuration")
        settings[1:] = [521, RAW_CACHE_BYTES, 1.0]
        fapl.set_cache(*settings)
        actual = fapl.get_cache()
        _need(actual[1] == 521 and actual[2] == RAW_CACHE_BYTES and actual[3] == 1.0,
              "raw cache configuration did not round-trip")
        config = fapl.get_mdc_config()
        for attr in ("set_initial_size", "initial_size", "min_size", "max_size"):
            _need(hasattr(config, attr), "metadata cache API unavailable")
        config.set_initial_size = 1
        config.initial_size = INITIAL_META_CACHE_BYTES
        config.min_size = INITIAL_META_CACHE_BYTES
        config.max_size = META_CACHE_BYTES
        fapl.set_mdc_config(config)
        actual = fapl.get_mdc_config()
        _need(actual.set_initial_size == 1 and actual.initial_size == INITIAL_META_CACHE_BYTES
              and actual.min_size == INITIAL_META_CACHE_BYTES
              and actual.max_size == META_CACHE_BYTES,
              "metadata cache configuration did not round-trip")
        return fapl
    except BaseException:
        fapl.close()
        raise


def _dtype_profile(dtype):
    _need(getattr(dtype, "kind", None) in ("i", "u", "f"), "primitive integer/float dtype required")
    _need(type(dtype.itemsize) is int and dtype.itemsize in (1, 2, 4, 8), "numeric itemsize bound")
    _need(getattr(dtype, "fields", None) is None and getattr(dtype, "subdtype", None) is None
          and getattr(dtype, "metadata", None) is None and not getattr(dtype, "hasobject", True),
          "compound/subarray/reference/vlen/object/enum dtype refused")
    _need(getattr(dtype, "byteorder", None) in ("<", ">", "=", "|"), "dtype byte order")
    return {"kind": dtype.kind, "itemsize": dtype.itemsize, "byteorder": dtype.byteorder,
            "description": str(dtype)}


def _dtype_semantics(profile):
    """Compare primitive meaning, preserving the original representation in receipts.

    NumPy documents '=' as the host's native byte order. HDF5 and decoded
    NumPy arrays may spell that same order differently; descriptions are also
    presentation, not data types. A real endian/kind/width change still fails.
    """
    order = profile["byteorder"]
    if profile["itemsize"] == 1:
        order = "|"
    elif order == "=":
        order = "<" if sys.byteorder == "little" else ">"
    else:
        _need(order != "|", "multibyte numeric dtype needs byte order")
    return profile["kind"], profile["itemsize"], order


def _shape(value):
    _need(type(value) is tuple and len(value) <= 3
          and all(type(n) is int and n > 0 for n in value), "bounded nonempty dataset shape required")
    return value


def _filters(dcpl, itemsize):
    count = dcpl.get_nfilters()
    _need(type(count) is int and 0 <= count <= 3, "filter count bound")
    result, seen = [], set()
    for i in range(count):
        filter_id, flags, parameters, name = dcpl.get_filter(i)
        _need(type(filter_id) is int and filter_id in ALLOWED_FILTERS and filter_id not in seen,
              "nonallowlisted or duplicate HDF5 filter")
        _need(type(flags) is int and flags & ~1 == 0, "unsupported filter flags")
        _need(type(parameters) is tuple and all(type(n) is int and 0 <= n <= 0xffffffff for n in parameters),
              "filter parameters")
        if filter_id == 1:
            _need(len(parameters) == 1 and parameters[0] <= 9, "deflate level")
        elif filter_id == 2:
            _need(parameters == (itemsize,), "shuffle element size")
        else:
            _need(parameters == (), "Fletcher32 parameters")
        _need(type(name) is bytes and len(name) <= 128, "filter name bound")
        seen.add(filter_id)
        result.append({"id": filter_id, "flags": flags, "parameters": list(parameters)})
    return result


def _storage_profile(dataset, h5py, dimensions, dtype):
    """Reject unsupported storage even on root datasets not selected for values."""
    dcpl = dataset.id.get_create_plist()
    try:
        _need(dcpl.get_external_count() == 0, "external dataset storage refused")
        _need(not dataset.is_virtual and dcpl.get_layout() != h5py.h5d.VIRTUAL, "virtual dataset refused")
        filters = _filters(dcpl, dtype["itemsize"])
    finally:
        dcpl.close()
    chunks = dataset.chunks
    if chunks is None:
        _need(not filters, "filtered contiguous layout refused")
        chunk_count, chunk_bytes = None, None
    else:
        chunks = _shape(chunks)
        _need(len(chunks) == len(dimensions), "chunk rank mismatch")
        chunk_bytes = math.prod(chunks) * dtype["itemsize"]
        chunk_count = math.prod((n + c - 1) // c for n, c in zip(dimensions, chunks))
        _need(chunk_bytes <= MAX_CHUNK_BYTES and chunk_count <= MAX_CHUNKS, "chunk expansion/count bound")
    return {"chunks": None if chunks is None else list(chunks),
            "maximum_decoded_chunk_bytes": chunk_bytes, "chunk_count": chunk_count,
            "filters": filters}


def dataset_profile(dataset, h5py, role):
    """Validate structure before reading any array value."""
    _need(isinstance(dataset, h5py.Dataset), "selected object is not a Dataset")
    _need(len(dataset.attrs) <= MAX_ATTRIBUTES, "dataset attribute-count bound")
    dimensions = _shape(dataset.shape)
    dtype = _dtype_profile(dataset.dtype)
    elements = math.prod(dimensions)
    _need(type(dataset.size) is int and dataset.size == elements, "dataset size/shape mismatch")
    if role == "video":
        _need(dimensions == VIDEO_SHAPE and elements == MAX_VIDEO_ELEMENTS, "original full video shape required")
        _need(elements * dtype["itemsize"] <= MAX_VIDEO_LOGICAL_BYTES, "video logical-byte bound")
    else:
        _need(role == "template", "unknown HDF5 role")
        _need(elements <= MAX_TEMPLATE_ELEMENTS and elements * dtype["itemsize"] <= MAX_TEMPLATE_LOGICAL_BYTES
              and len([n for n in dimensions if n != 1]) <= 1, "template vector size bound")
    return {"shape": list(dimensions), "elements": elements, "dtype": dtype,
            "logical_bytes": elements * dtype["itemsize"],
            **_storage_profile(dataset, h5py, dimensions, dtype),
            "attribute_count": len(dataset.attrs), "attribute_values_read": 0}


def select_root_dataset(handle, h5py, role, deadline):
    """Follow author root-selection order; never choose a shape-matching fallback."""
    _tick(deadline)
    _need(len(handle) <= MAX_ROOT_OBJECTS and len(handle.attrs) <= MAX_ATTRIBUTES,
          "root object/attribute-count bound")
    names = list(handle.keys())
    _need(0 < len(names) <= MAX_ROOT_OBJECTS and len(names) == len(set(names)), "root key roster")
    objects, candidates = [], []
    for name in names:
        _tick(deadline)
        _need(type(name) is str and 0 < len(name.encode("utf-8")) <= MAX_NAME_BYTES
              and "/" not in name and "\x00" not in name, "root key name bound")
        link = handle.get(name, getlink=True)
        _need(type(link) is h5py.HardLink, "soft/external/user-defined root link refused")
        obj = handle[name]
        # This deliberately stricter preparation profile refuses root groups;
        # it never walks hidden links or changes the author's dataset choice.
        _need(isinstance(obj, h5py.Dataset), "root groups/non-datasets are outside preparation profile")
        _need(len(obj.attrs) <= MAX_ATTRIBUTES, "root dataset attribute-count bound")
        dims = _shape(obj.shape)
        dtype = _dtype_profile(obj.dtype)
        count = math.prod(dims)
        _need(count <= MAX_VIDEO_ELEMENTS and type(obj.size) is int and obj.size == count,
              "root candidate element bound")
        _storage_profile(obj, h5py, dims, dtype)
        objects.append(obj)
        candidates.append({"name": name, "shape": list(dims), "elements": count})
    selected_index = 0 if len(names) == 1 else max(range(len(names)), key=lambda i: candidates[i]["elements"])
    name = names[selected_index]
    _need(role != "template" or name == "filter_tempolate", "source template dataset name mismatch")
    profile = dataset_profile(objects[selected_index], h5py, role)
    return objects[selected_index], {"root_candidates": candidates, "selected_name": name,
                                    "selection_rule": "sole root key; otherwise first largest root Dataset in observed key order",
                                    "root_attribute_values_read": 0, **profile}


def selections(profile):
    """A nonoverlapping complete scan, with each checked logical chunk once."""
    dimensions = tuple(profile["shape"])
    chunks = profile["chunks"]
    if chunks is not None:
        starts = [range(0, n, c) for n, c in zip(dimensions, chunks)]
        for origin in itertools.product(*starts):
            yield tuple(slice(start, min(start + width, total))
                        for start, width, total in zip(origin, chunks, dimensions))
    elif not dimensions:
        yield ()
    else:
        row_bytes = math.prod(dimensions[1:]) * profile["dtype"]["itemsize"]
        _need(row_bytes <= CONTIGUOUS_SLICE_BYTES, "contiguous row exceeds slice bound")
        step = max(1, CONTIGUOUS_SLICE_BYTES // row_bytes)
        for start in range(0, dimensions[0], step):
            yield (slice(start, min(start + step, dimensions[0])),) + tuple(slice(0, n) for n in dimensions[1:])


def scan_dataset(dataset, profile, numpy, deadline, progress=None):
    """Decode all values, keeping only counts and finite-status metadata."""
    progress = {} if progress is None else progress
    progress.update(attempted_selections=0, completed_selections=0,
                    requested_logical_bytes=0, returned_logical_bytes=0,
                    failed_native_selection_return_unknown=False)
    elements, logical_bytes, calls = 0, 0, 0
    native_in_flight = False
    try:
        for selection in selections(profile):
            _tick(deadline)
            expected_shape = tuple(s.stop - s.start for s in selection)
            expected_elements = math.prod(expected_shape)
            progress["attempted_selections"] += 1
            progress["requested_logical_bytes"] += expected_elements * profile["dtype"]["itemsize"]
            native_in_flight = True
            block = dataset[selection]
            native_in_flight = False
            progress["returned_logical_bytes"] += int(block.nbytes)
            _need(tuple(block.shape) == expected_shape and block.size == expected_elements,
                  "HDF5 returned a different selection shape")
            decoded_dtype = _dtype_profile(block.dtype)
            # Keep both spellings if a failure occurs; the previous generated
            # refusal lacked enough evidence to identify its exact alias.
            progress["source_dtype"] = profile["dtype"]
            progress["decoded_dtype"] = decoded_dtype
            _need(_dtype_semantics(decoded_dtype) == _dtype_semantics(profile["dtype"]),
                  "decoded dtype changed")
            _need(block.nbytes == expected_elements * profile["dtype"]["itemsize"], "decoded byte count")
            _need(block.nbytes <= (MAX_CHUNK_BYTES if profile["chunks"] is not None else CONTIGUOUS_SLICE_BYTES),
                  "decoded selection exceeds bound")
            if profile["dtype"]["kind"] == "f":
                _need(bool(numpy.isfinite(block).all()), "non-finite video/template value")
            elements += block.size
            logical_bytes += block.nbytes
            calls += 1
            progress["completed_selections"] += 1
            del block
    except BaseException as exc:
        progress["failed_native_selection_return_unknown"] = native_in_flight
        exc.scan_progress = dict(progress)
        raise
    _need(elements == profile["elements"] and logical_bytes == profile["logical_bytes"],
          "complete source dataset scan required")
    _need(profile["chunk_count"] is None or calls == profile["chunk_count"], "each logical chunk must be read once")
    return {"elements_read": elements, "logical_value_bytes_read": logical_bytes,
            "selection_calls": calls, "all_values_finite": True, "signal_values_retained": False}


def _validate_entry(entry):
    _need(type(entry) is dict and set(entry) == {"name", "bytes", "sha256"}, "exact HDF5 source entry required")
    name = entry["name"]
    _need(type(name) is str and name not in ("", ".", "..") and "/" not in name and "\\" not in name
          and "\x00" not in name and name.endswith(".h5"), "root HDF5 file name required")
    _need(type(entry["bytes"]) is int and 0 < entry["bytes"] <= MAX_FILE_BYTES
          and type(entry["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", entry["sha256"]), "source pin shape")
    return name


def _authenticate_open(root_fd, entry, deadline):
    name = _validate_entry(entry)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
    source = os.fdopen(fd, "rb", buffering=0)
    consumed = 0
    try:
        before = os.fstat(fd)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == entry["bytes"],
              "regular nonalias source size mismatch")
        digest = hashlib.sha256()
        while consumed < entry["bytes"]:
            _tick(deadline)
            block = source.read(min(CONTIGUOUS_SLICE_BYTES, entry["bytes"] - consumed))
            _need(bool(block), "truncated source during authentication")
            consumed += len(block)
            digest.update(block)
        _need(digest.hexdigest() == entry["sha256"] and _signature(before) == _signature(os.fstat(fd)),
              "source identity changed or hash mismatch")
        source.seek(0)
        return source, before, consumed
    except BaseException as exc:
        exc.partial_receipt = {"name": entry["name"], "stage": "source_authentication",
                               "source_hash_bytes": consumed, "HDF5_returned_file_bytes": 0,
                               "logical_array_bytes_returned": 0, "physical_IO_bytes": None}
        source.close()
        raise


def inspect_one(root_fd, entry, role, runtime, deadline):
    """One admitted file; generated controls substitute a fake native API."""
    _need(type(runtime) is NativeRuntime and runtime.clean_preimport_verified, "clean native initializer required")
    source, before, hash_bytes = _authenticate_open(root_fd, entry, deadline)
    reader = BoundedReadOnlyFile(source, entry["bytes"], deadline)
    fapl = file_id = handle = dataset = None
    native_open_attempted = native_open_completed = handle_constructed = False
    result = None
    primary_error = None
    cleanup_errors = []
    scan_progress = {}
    try:
        fapl = configure_fapl(runtime.h5py, reader)
        native_open_attempted = True
        file_id = runtime.h5py.h5f.open(b"suns2-bounded-readonly", runtime.h5py.h5f.ACC_RDONLY, fapl=fapl)
        native_open_completed = True
        handle = runtime.h5py.File(file_id)
        handle_constructed = True
        dataset, profile = select_root_dataset(handle, runtime.h5py, role, deadline)
        values = scan_dataset(dataset, profile, runtime.numpy, deadline, scan_progress)
        _need(_signature(before) == _signature(os.fstat(source.fileno())), "source changed during HDF5 inspection")
        result = {"name": entry["name"], "bytes": entry["bytes"], "sha256": entry["sha256"],
                  "role": role, "source_hash_bytes": hash_bytes, "schema": profile,
                  "readability": values, "file_adapter": reader.receipt(),
                  "template_provenance_qualified": False if role == "template" else None}
    except BaseException as exc:
        primary_error = exc
    finally:
        native_close_error = False
        for label, resource in (("handle", handle), ("file_id", file_id), ("fapl", fapl)):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as exc:
                    cleanup_errors.append(f"{label}: {type(exc).__name__}: {exc}")
                    native_close_error = native_close_error or label in ("handle", "file_id")
        # A false FileID.valid alone cannot prove Dataset IDs closed after a
        # failed high-level close. File.close normally closes those IDs first.
        native_open_unknown = (native_close_error
                               or (native_open_attempted and not native_open_completed)
                               or (file_id is not None and not handle_constructed))
        if file_id is not None:
            try:
                native_open_unknown = native_open_unknown or bool(file_id.valid)
            except BaseException as exc:
                native_open_unknown = True
                cleanup_errors.append(f"file_id validity: {type(exc).__name__}: {exc}")
        if native_open_unknown:
            _UNCLOSED_NATIVE_RESOURCES.append((handle, file_id, fapl, dataset, primary_error, reader, source))
            cleanup_errors.append("native closure unverified; backing file retained for owned-process termination")
        else:
            for label, resource in (("reader", reader), ("source", source)):
                try:
                    resource.close()
                except BaseException as exc:
                    cleanup_errors.append(f"{label}: {type(exc).__name__}: {exc}")
    if cleanup_errors:
        failure = PreparationRefused("native cleanup failed: " + "; ".join(cleanup_errors))
        failure.cleanup_errors = cleanup_errors
        failure.native_closure_unverified = native_open_unknown
        failure.partial_receipt = {"name": entry["name"], "stage": "native_cleanup",
                                   "source_hash_bytes": hash_bytes, "file_adapter": reader.receipt(),
                                   "scan_progress": scan_progress, "cleanup_errors": cleanup_errors,
                                   "native_closure_unverified": native_open_unknown}
        raise failure from primary_error
    if primary_error is not None:
        primary_error.partial_receipt = {"name": entry["name"], "stage": "HDF5_inspection",
                                         "source_hash_bytes": hash_bytes, "file_adapter": reader.receipt(),
                                         "scan_progress": scan_progress, "cleanup_errors": [],
                                         "native_closure_unverified": False}
        raise primary_error
    result["file_adapter"] = reader.receipt()
    return result


def inspect_bank(bank_root, entries, runtime, *, deadline=None):
    """Inspect exactly nine full movies plus the quarantined source template.

``entries`` must be an operator-authenticated manifest projection, not participant
claims. This API does not create that authority, admit its own run, or load MAT.
"""
    deadline = time.monotonic() + 120 if deadline is None else deadline
    names = [f"{video}.h5" for video in VIDEO_IDS] + ["1P_spike_tempolate.h5"]
    _need(type(entries) is list and len(entries) == 10 and all(type(e) is dict for e in entries)
          and [e.get("name") for e in entries] == names, "exact source-order nine movies and template required")
    for index, entry in enumerate(entries):
        _validate_entry(entry)
        _need(entry["bytes"] == (MAX_FILE_BYTES if index < 9 else 2048),
              "original source member size differs from the pinned inventory")
    root = Path(bank_root)
    _need(root.is_absolute(), "explicit absolute protected bank root required")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    rows = []
    def compact_progress(failed_name=None, failed=None):
        completed = [{"name": r["name"], "source_hash_bytes": r["source_hash_bytes"],
                      "HDF5_returned_file_bytes": r["file_adapter"]["returned_bytes"],
                      "logical_value_bytes_returned": r["readability"]["logical_value_bytes_read"]}
                     for r in rows]
        return {"completed_files": completed, "completed_file_count": len(completed),
                "completed_source_hash_bytes": sum(r["source_hash_bytes"] for r in completed),
                "completed_HDF5_returned_file_bytes": sum(r["HDF5_returned_file_bytes"] for r in completed),
                "completed_logical_value_bytes_returned": sum(r["logical_value_bytes_returned"] for r in completed),
                "failed_file_name": failed_name, "failed_file": failed,
                "missing_failed_counters_are_unknown_not_zero": failed_name is not None and failed is None}
    try:
        for index, entry in enumerate(entries):
            try:
                rows.append(inspect_one(root_fd, entry, "video" if index < 9 else "template", runtime, deadline))
            except BaseException as exc:
                exc.bank_progress = compact_progress(entry["name"], getattr(exc, "partial_receipt", None))
                raise
            if len(json.dumps(rows, ensure_ascii=True, allow_nan=False).encode()) > MAX_METADATA_BYTES - 4096:
                exc = PreparationRefused("HDF5 per-file metadata exceeds panel output reserve")
                exc.bank_progress = compact_progress()
                exc.partial_receipt = exc.bank_progress
                raise exc
    finally:
        os.close(root_fd)
    report = {"schema": "suns2-original-hdf5-preparation/v1", "status": "complete_schema_and_readability",
              "videos": 9, "video_order": list(VIDEO_IDS), "files": rows,
              "runtime_versions": runtime.observed_versions,
              "plugin_policy": "prelaunch HDF5_PLUGIN_PRELOAD=::; empty private plugin path; exact version pin",
              "source_hash_bytes": sum(r["source_hash_bytes"] for r in rows),
              "HDF5_returned_file_bytes": sum(r["file_adapter"]["returned_bytes"] for r in rows),
              "logical_value_bytes_read": sum(r["readability"]["logical_value_bytes_read"] for r in rows),
              "movie_axes": ["time", "row", "col"], "original_MAT_mask_axes": ["col", "row", "neuron"],
              "coordinate_rule": "movie[t,row,col] corresponds to original MAT mask[col,row,neuron]",
              "spatial_registration_newly_established": False,
              "source_data_transformed": False, "template_participant_admitted": False,
              "manual_MAT_arrays_loaded": False, "model_or_scoring_run": False,
              "physical_IO_bytes": None, "memory_cap_is_OS_hard_limit": False}
    encoded = json.dumps(report, ensure_ascii=True, allow_nan=False).encode()
    if len(encoded) > MAX_METADATA_BYTES:
        exc = PreparationRefused("HDF5 metadata output cap")
        exc.bank_progress = compact_progress()
        exc.partial_receipt = exc.bank_progress
        raise exc
    return report
