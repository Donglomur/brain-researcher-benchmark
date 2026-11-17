"""Minimal future click-timing inspection; importing this module opens nothing.

The explicit CLI execution path authenticates each complete source file before
opening HDF5 on that same descriptor. It reads values from exactly the three
trial columns below. No spikes, spike indices, units, or images are read.
An external admission is required before running the CLI on authentic files;
the command-line execution flag is an accident guard, not that admission.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


SOURCE_SHA256 = "320eb843e01353ce59936393df37dd9eda1d12150f9fc9fc66f48aa968dc9966"
SOURCE_FILES = 26
SOURCE_BYTES = 455615424
SOURCE_ROWS = 5238
DECODED_VALUE_BYTES = 125712
ROW_HISTOGRAM = {200: 6, 201: 6, 202: 13, 206: 1}
TRIAL_PATHS = ("intervals/trials/id", "intervals/trials/start_time",
               "intervals/trials/stop_time")
HASH_CHUNK_BYTES = 1048576
MAX_JSON_BYTES = 1048576
MAX_DECODED_CHUNK_BYTES = 1048576
ALLOWED_FILTER_IDS = (1, 2, 3)  # Built-in deflate, shuffle, Fletcher32 only.
RESPONSE_US = tuple(range(0, 100001, 1000))
HISTORY_US = tuple(range(-100000, 1, 1000))


class ClickInspectionError(ValueError):
    """The complete fixed timing roster cannot be admitted as represented."""


def require(condition, message):
    if not condition:
        raise ClickInspectionError(message)


def _finite(value, name):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    require(valid, name + " must be finite numeric data, excluding bool")
    return float(value)


def _strict_int(value, name, minimum=None, maximum=None):
    require(type(value) is int, name + " must be an integer, excluding bool")
    if minimum is not None:
        require(value >= minimum, name + " is below its bound")
    if maximum is not None:
        require(value <= maximum, name + " exceeds its bound")
    return value


def _digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "Expected a lowercase SHA-256 digest")
    return value


def _text(value, label):
    require(type(value) is str and 0 < len(value) <= 4096
            and all(ord(c) >= 32 for c in value), label + " must be bounded text")
    return value


def _object(value, label):
    require(type(value) is dict, label + " must be an object")
    return value


def _get(value, key, label):
    _object(value, label)
    require(key in value, label + " is missing " + key)
    return value[key]


def _edges(anchor, offsets):
    values = [anchor + offset / 1000000 for offset in offsets]
    require(all(math.isfinite(x) for x in values), "Nonfinite absolute bin edge")
    require(all(a < b for a, b in zip(values, values[1:])),
            "Selected 1-ms bins are not representable at this source timestamp")
    return values


def validate_trial_rows(ids, starts, stops, *, expected_rows):
    """Validate supplied Python lists, preserving every row in source order.

    IDs need not equal row ordinals. Negative reference timestamps are permitted.
    Every response [t,t+.1) and history [t-.1,t) has 100 strictly ordered,
    representable bins. Every history is disjoint from *all* scored responses;
    touching half-open endpoints are allowed without a rounding tolerance.
    This establishes timing geometry only, never continuous observation.
    """
    _strict_int(expected_rows, "expected_rows", minimum=1, maximum=206)
    require(all(type(values) is list and len(values) == expected_rows
                for values in (ids, starts, stops)),
            "All three columns must preserve exactly the declared source rows")
    for identifier in ids:
        _strict_int(identifier, "source trial id", -(2 ** 63), 2 ** 63 - 1)
    require(len(set(ids)) == expected_rows, "Source trial IDs must be unique")
    starts = [_finite(v, "click start") for v in starts]
    stops = [_finite(v, "click stop") for v in stops]
    require(all(b > a for a, b in zip(starts, starts[1:])),
            "Source click starts must be strictly chronological")
    require(all(b > a for a, b in zip(stops, stops[1:])),
            "Source click stops must be strictly chronological")
    durations = [stop - start for start, stop in zip(starts, stops)]
    require(all(math.isfinite(d) and d > 0 for d in durations),
            "Every source click must have finite positive duration")
    response_windows, history_windows = [], []
    min_width = math.inf
    for start in starts:
        response = _edges(start, RESPONSE_US)
        history = _edges(start, HISTORY_US)
        response_windows.append((response[0], response[-1]))
        history_windows.append((history[0], history[-1]))
        min_width = min(min_width, *(b - a for a, b in zip(response, response[1:])),
                        *(b - a for a, b in zip(history, history[1:])))
    # Starts and both families of endpoints are ordered. Moving this index once
    # gives a complete all-history versus all-response intersection check.
    first_candidate = 0
    for history_start, history_stop in history_windows:
        while (first_candidate < expected_rows
               and response_windows[first_candidate][1] <= history_start):
            first_candidate += 1
        if first_candidate < expected_rows:
            response_start, response_stop = response_windows[first_candidate]
            require(not (response_start < history_stop and history_start < response_stop),
                    "A permitted history overlaps a scored response window")
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    require(all(math.isfinite(gap) for gap in gaps), "Nonfinite onset interval")
    return {
        "rows": [{"row_ordinal": index, "source_trial_id": identifier,
                  "start_time": start, "stop_time": stop}
                 for index, (identifier, start, stop) in enumerate(zip(ids, starts, stops))],
        "timing_stats": {
            "row_count": expected_rows,
            "first_click_start_seconds": starts[0],
            "last_click_start_seconds": starts[-1],
            "minimum_click_duration_seconds": min(durations),
            "maximum_click_duration_seconds": max(durations),
            "minimum_onset_interval_seconds": min(gaps) if gaps else None,
            "maximum_onset_interval_seconds": max(gaps) if gaps else None,
            "minimum_represented_bin_width_seconds": min_width,
            "history_response_windows_disjoint": True,
            "timestamps_are_reference_relative": True,
            "recording_extent_inferred": False,
        },
        "continuous_support_verified": False,
    }


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _json_constant(value):
    raise ClickInspectionError("Nonfinite JSON constant: " + value)


def _json_float(value):
    return _finite(float(value), "JSON float")


def _read_pinned_json(path, expected_sha256):
    _digest(expected_sha256)
    with Path(path).open("rb") as handle:
        body = handle.read(MAX_JSON_BYTES + 1)
    require(len(body) <= MAX_JSON_BYTES, "Metadata exceeds 1-MiB bound")
    require(hashlib.sha256(body).hexdigest() == expected_sha256,
            "Metadata digest mismatch")
    try:
        result = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_pairs,
                            parse_constant=_json_constant, parse_float=_json_float)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ClickInspectionError("Invalid bounded metadata JSON") from exc
    return _object(result, "Metadata document")


def inspection_plan(sources, support, *, sources_sha256):
    """Validate the exact previously selected roster; access no source files."""
    require(sources_sha256 == SOURCE_SHA256, "Unselected source manifest digest")
    require(_get(support, "schema", "support") == "neural099-conditional-source-support/v1",
            "Unsupported declared support schema")
    require(_get(support, "source_manifest_sha256", "support") == sources_sha256,
            "Declared support references a different source manifest")
    qualification = _object(_get(support, "qualification", "support"), "qualification")
    require(_get(qualification, "metadata_profile_matched", "qualification") is True,
            "Expected the qualified metadata profile, not a loose source projection")
    require(_get(qualification, "trial_values_authenticated", "qualification") is False,
            "Timing stage expects the uninspected declared roster")
    require(_get(qualification, "observation_coverage_verified", "qualification") is False,
            "Timing stage must not inherit a verified exposure claim")
    source_assets = _get(sources, "assets", "sources")
    support_assets = _get(support, "assets", "support")
    require(type(source_assets) is list and len(source_assets) == SOURCE_FILES
            and type(support_assets) is list and len(support_assets) == SOURCE_FILES,
            "The complete 26-file source roster is required")
    by_id = {}
    for asset in support_assets:
        aid = _text(_get(asset, "asset_id", "support asset"), "asset_id")
        require(aid not in by_id, "Duplicate declared support asset")
        by_id[aid] = asset
    result, basenames, seen = [], set(), set()
    for source in source_assets:
        aid = _text(_get(source, "asset_id", "source asset"), "asset_id")
        require(aid in by_id and aid not in seen, "Unknown or duplicate source asset")
        seen.add(aid)
        declared = by_id[aid]
        path = _text(_get(source, "path", "source asset"), "source path")
        parts = path.split("/")
        require(not PurePosixPath(path).is_absolute()
                and all(part not in ("", ".", "..") for part in parts)
                and "\\" not in path, "Expected a relative POSIX source asset path")
        basename = parts[-1]
        require(basename not in basenames, "Raw-root basename mapping is ambiguous")
        basenames.add(basename)
        nbytes = _strict_int(_get(source, "bytes", "source asset"), "source bytes", 1)
        digest = _digest(_get(source, "sha256", "source asset"))
        subject = _text(_get(source, "subject_id", "source asset"), "source subject")
        require(_get(declared, "source_subject_id", "support asset") == subject,
                "Source subject mismatch")
        require(_get(declared, "source_asset", "support asset")
                == {"path": path, "bytes": nbytes, "sha256": digest},
                "Declared support and source file identity mismatch")
        count = _strict_int(_get(declared, "source_trial_rows", "support asset"),
                            "source trial rows", 1, 206)
        require(count in ROW_HISTOGRAM, "Unexpected source trial count")
        result.append({"asset_id": aid, "source_subject_id": subject,
                       "source_path": path, "basename": basename,
                       "bytes": nbytes, "sha256": digest, "expected_rows": count})
    require(seen == set(by_id), "Source roster is incomplete")
    require(sum(a["bytes"] for a in result) == SOURCE_BYTES, "Unexpected total source bytes")
    require(Counter(a["expected_rows"] for a in result) == ROW_HISTOGRAM,
            "Expected exact per-file source row-count histogram")
    require(sum(a["expected_rows"] for a in result) == SOURCE_ROWS,
            "All 5238 declared source rows must be preserved")
    return sorted(result, key=lambda a: a["asset_id"])


def _trial_dataset(handle, path, h5api, expected_rows):
    require(path in TRIAL_PATHS, "Dataset is not in the timing read allowlist")
    current = handle
    parts = path.split("/")
    for index, part in enumerate(parts):
        link = current.get(part, getlink=True)
        require(isinstance(link, h5api.HardLink), "Indirect or missing trial path component")
        current = current[part]
        if index < len(parts) - 1:
            require(isinstance(current, h5api.Group), "Trial path ancestor is not a group")
    require(isinstance(current, h5api.Dataset), "Trial column is not a dataset")
    require(not current.is_virtual and not current.external,
            "Virtual or externally stored trial columns are forbidden")
    require(current.shape == (expected_rows,), "Unexpected trial column shape")
    expected_kind = "i" if path.endswith("/id") else "f"
    dtype = current.dtype
    require(dtype.kind == expected_kind and dtype.itemsize == 8
            and dtype.fields is None and dtype.subdtype is None,
            "Expected int64 IDs and float64 start/stop columns")
    chunks = current.chunks
    if chunks is not None:
        require(type(chunks) is tuple and len(chunks) == 1
                and type(chunks[0]) is int and chunks[0] > 0
                and chunks[0] * 8 <= MAX_DECODED_CHUNK_BYTES,
                "Trial dataset chunk exceeds the separately bounded native decode extent")
    creation = current.id.get_create_plist()
    filter_count = creation.get_nfilters()
    require(type(filter_count) is int and 0 <= filter_count <= len(ALLOWED_FILTER_IDS),
            "Unreviewed HDF5 filter pipeline")
    seen_filters = set()
    for index in range(filter_count):
        filter_id = creation.get_filter(index)[0]
        require(type(filter_id) is int and filter_id in ALLOWED_FILTER_IDS
                and filter_id not in seen_filters, "Unreviewed HDF5 filter or plugin")
        seen_filters.add(filter_id)
    require(not seen_filters or chunks is not None,
            "Filtered trial dataset must have a bounded chunk layout")
    return current


def read_trial_columns(handle, *, h5api, expected_rows):
    """Read the three vetted columns only; h5py is supplied by the explicit CLI.

    Pure fake objects may exercise link/shape/type refusal without native HDF5.
    Every dataset is vetted before any values are read.
    """
    _strict_int(expected_rows, "expected_rows", 1, 206)
    datasets = [_trial_dataset(handle, p, h5api, expected_rows) for p in TRIAL_PATHS]
    values = [dataset[()].tolist() for dataset in datasets]
    require(all(type(value) is list and len(value) == expected_rows for value in values),
            "Decoded column shape differs from its vetted header")
    return values


def _file_signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _inspect_one(root_fd, asset, h5api):
    # The descriptor remains the same across authentication and native decoding.
    descriptor = os.open(asset["basename"], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == asset["bytes"],
                "Source is not a regular file with its authenticated size")
        digest, consumed = hashlib.sha256(), 0
        while True:
            chunk = source.read(min(HASH_CHUNK_BYTES, asset["bytes"] - consumed + 1))
            if not chunk:
                break
            consumed += len(chunk)
            require(consumed <= asset["bytes"], "Source grew beyond its authenticated extent")
            digest.update(chunk)
        require(consumed == asset["bytes"] and digest.hexdigest() == asset["sha256"],
                "Complete source file digest mismatch")
        require(_file_signature(before) == _file_signature(os.fstat(source.fileno())),
                "Source metadata changed during authentication")
        source.seek(0)
        with h5api.File(source, "r", rdcc_nbytes=1048576) as handle:
            ids, starts, stops = read_trial_columns(handle, h5api=h5api,
                                                    expected_rows=asset["expected_rows"])
        require(_file_signature(before) == _file_signature(os.fstat(source.fileno())),
                "Source metadata changed during timing inspection")
    result = validate_trial_rows(ids, starts, stops, expected_rows=asset["expected_rows"])
    return {**{key: asset[key] for key in ("asset_id", "source_subject_id", "source_path",
                                          "bytes", "sha256")},
            **result, "value_reads": list(TRIAL_PATHS),
            "decoded_value_bytes": asset["expected_rows"] * 3 * 8,
            "full_file_hash_bytes": consumed}


def _encode_output(value):
    body = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    require(len(body) <= MAX_JSON_BYTES, "Timing output exceeds the 1-MiB artifact bound")
    return body


def initialize_runtime():
    """Initialize the admitted runtime without opening any source file.

    The launcher must set HDF5_PLUGIN_PRELOAD=:: before starting Python. This
    function verifies the setting and refuses an already imported h5py stack;
    it does not retrofit the environment onto an initialized HDF5 library.
    HDF5 1.14.6 H5PLpublic.h/H5PLint.c document and implement this mechanism.
    No h5py plugin setter or ctypes bridge is assumed to exist.
    """
    require(os.environ.get("HDF5_PLUGIN_PRELOAD") == "::",
            "Launcher must set HDF5_PLUGIN_PRELOAD=:: before Python startup")
    require(not any(name == "h5py" or name.startswith("h5py.") for name in sys.modules),
            "Runtime initialization requires a fresh, unimported h5py stack")
    # Intentionally lazy: generated tests and module import never import h5py.
    import h5py
    import numpy
    observed_versions = {"h5py": str(h5py.__version__), "numpy": str(numpy.__version__),
                         "hdf5": str(h5py.version.hdf5_version)}
    return h5py, observed_versions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-authenticated-click-read", action="store_true")
    parser.add_argument("--sources", required=True)
    parser.add_argument("--sources-sha256", required=True)
    parser.add_argument("--declared-support", required=True)
    parser.add_argument("--declared-support-sha256", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    require(args.execute_authenticated_click_read,
            "Explicit execution flag and separate authentic-read admission are required")
    require(args.sources_sha256 == SOURCE_SHA256, "Source manifest must be the selected fixed pin")
    sources = _read_pinned_json(args.sources, args.sources_sha256)
    support = _read_pinned_json(args.declared_support, args.declared_support_sha256)
    plan = inspection_plan(sources, support, sources_sha256=args.sources_sha256)
    output = Path(args.output)
    require(not output.exists() and not output.is_symlink(), "Output must be a new artifact")
    root = Path(args.raw_root)
    require(root.is_absolute(), "Raw root must be an explicit absolute directory")
    require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"),
            "Platform lacks required no-follow file primitives")
    h5py, observed_versions = initialize_runtime()
    require(observed_versions == {"h5py": "3.13.0", "hdf5": "1.14.6", "numpy": "2.2.6"},
            "Runtime versions differ from the admitted import-only probe; no source read")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        records = [_inspect_one(root_fd, asset, h5py) for asset in plan]
    finally:
        os.close(root_fd)
    decoded = sum(record["decoded_value_bytes"] for record in records)
    require(decoded == DECODED_VALUE_BYTES, "Unexpected decoded trial value budget")
    report = {
        "schema": "neural099-authenticated-click-timing-inspection/v1",
        "sources_sha256": args.sources_sha256,
        "declared_support_sha256": args.declared_support_sha256,
        "source_files": SOURCE_FILES, "source_bytes_hashed": SOURCE_BYTES,
        "logical_file_hash_bytes": SOURCE_BYTES,
        "source_trial_rows": SOURCE_ROWS, "decoded_value_bytes": decoded,
        "logical_selected_array_value_bytes": decoded,
        "physical_hdf5_and_os_read_bytes": None,
        "native_working_memory_bytes": None,
        "observed_runtime_versions": observed_versions,
        "native_storage_policy": {"maximum_decoded_chunk_bytes": MAX_DECODED_CHUNK_BYTES,
                                  "raw_chunk_cache_bytes": 1048576,
                                  "allowed_filter_ids": list(ALLOWED_FILTER_IDS),
                                  "hdf5_plugin_loading_disabled": True,
                                  "plugin_disable_method": "launcher_HDF5_PLUGIN_PRELOAD_equals_double_colon",
                                  "limits_are_not_a_total_native_memory_bound": True},
        "per_asset_value_read_allowlist": list(TRIAL_PATHS),
        "records": records,
        "selected_response_microseconds": [0, 100000],
        "selected_history_microseconds": [-100000, 0],
        "bins_per_window": 100, "nominal_bin_width_microseconds": 1000,
        "windows_are_half_open": True,
        "qualification": {"actual_trial_values_authenticated": True,
                          "selected_timing_geometry_valid": True,
                          "continuous_support_verified": False,
                          "biological_identity_verified": False,
                          "spike_response_values_read": False,
                          "physiological_rate_qualified": False,
                          "ready_for_scoring": False},
    }
    body = _encode_output(report)
    with output.open("xb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"output": str(output), "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(),
                      "source_files": SOURCE_FILES, "source_bytes_hashed": SOURCE_BYTES,
                      "decoded_value_bytes": decoded}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
