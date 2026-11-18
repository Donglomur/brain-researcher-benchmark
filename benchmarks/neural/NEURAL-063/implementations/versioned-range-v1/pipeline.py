"""Complete-cohort metadata/support/projection using unchanged N063 science.

Alternative artifacts deliberately have distinct custody schemas. They are not
canonical S00--S06 receipts and cannot assert full-file authentication.
"""
from bisect import bisect_left
from collections import defaultdict
import hashlib
import importlib
from pathlib import Path
import sys
from manifest import EXPECTED, SELECTION_SHA256, full_scope, validate_assets
from range_io import RangeContractError, canonical, open_versioned


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load_original(root, pins):
    """Load exactly the unchanged six-module stdlib science closure."""
    root = Path(root)
    modules = ("owner", "owner.io", "owner.scoring", "preparation",
               "preparation.algorithm", "preparation.native")
    required = {"owner/__init__.py", "owner/io.py", "owner/scoring.py",
                "preparation/__init__.py", "preparation/algorithm.py", "preparation/native.py"}
    if set(pins) != required:
        raise RangeContractError("exact six-module source closure required")
    if any(name in sys.modules for name in modules):
        raise RangeContractError("original module namespace already populated")
    for relative, pin in pins.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size != pin["bytes"]:
            raise RangeContractError("original source path/extent mismatch")
        if (path.parent / "__pycache__").exists():
            raise RangeContractError("original source cache must be absent")
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            raise RangeContractError("original scientific source changed")
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    try:
        loaded = {name: importlib.import_module(name) for name in modules}
        for name, module in loaded.items():
            relative = name.replace(".", "/") + ("/__init__.py" if name in ("owner", "preparation") else ".py")
            if Path(module.__file__).absolute() != (root / relative).absolute():
                raise RangeContractError("original module origin mismatch")
        return loaded["preparation.native"], loaded["preparation.algorithm"], loaded["owner.io"]
    finally:
        sys.path.pop(0)
        sys.dont_write_bytecode = old


def write_value(store, name, value, role, cap):
    body = canonical(value)
    if len(body) > cap:
        raise RangeContractError("complete artifact exceeds declared output cap")
    return store.write(name + ".json", body, role=role, visibility="operator",
                       producer="neural063-versioned-range-v1").object()


def read_value(store, ref, role, cap, schema):
    if ref.get("visibility") != "operator":
        raise RangeContractError("operator-only alternative artifact required")
    value = store.read_json(ref, roles={role}, cap=cap)
    if value.get("schema") != schema:
        raise RangeContractError("alternative artifact schema mismatch")
    return value


def identity_matches(value, row):
    if any(value.get(k) != row[source] for k, source in
           (("experiment", "ophys_experiment_id"), ("session", "ophys_session_id"),
            ("mouse", "mouse_id"), ("split", "split"))):
        raise RangeContractError("embedded original hierarchy mismatch")


def layout(dataset):
    """HDF5 metadata only; never dataset slicing or value materialization."""
    chunks = None if dataset.chunks is None else list(dataset.chunks)
    chunk_bytes = None
    if chunks:
        chunk_bytes = int(dataset.dtype.itemsize)
        for dim in chunks:
            chunk_bytes *= dim
    variable = bool(getattr(dataset.dtype, "hasobject", False))
    return {"shape": list(dataset.shape), "dtype": str(dataset.dtype),
            "dtype_bytes": int(dataset.dtype.itemsize), "chunks": chunks,
            "compression": dataset.compression, "compression_options": dataset.compression_opts,
            "shuffle": bool(dataset.shuffle), "fletcher32": bool(dataset.fletcher32),
            "scaleoffset": dataset.scaleoffset,
            "dataset_storage_bytes": int(dataset.id.get_storage_size()),
            "contains_variable_length_or_reference": variable,
            "fixed_element_buffer_bytes": int(dataset.size) * int(dataset.dtype.itemsize),
            "full_logical_array_bytes": None if variable else int(dataset.size) * int(dataset.dtype.itemsize),
            "uncompressed_chunk_bytes": None if variable else chunk_bytes,
            "heap_payload_bytes": None if variable else 0,
            "storage_size_covers_variable_length_heap": False if variable else None}


def field_layouts(file, native):
    """Only required HDF5 dataset metadata; no [:], asstr(), or array values."""
    prefix = "processing/ophys/dff/traces/"
    table = "processing/ophys/image_segmentation/cell_specimen_table/"
    fields = {prefix + name: layout(native.internal(file, prefix + name))
              for name in ("data", "timestamps", "rois")}
    for name in ("id", "cell_specimen_id", "valid_roi"):
        fields[table + name] = layout(native.internal(file, table + name))
    intervals = native.internal(file, "intervals")
    for name in sorted(intervals.keys()):
        group = native.internal(file, "intervals/" + name)
        if not hasattr(group, "keys"):
            continue
        keys = set(group.keys())
        if not {"image_name", "omitted"} & keys:
            continue
        required = {"id", "start_time", "image_name", "omitted"}
        if not required <= keys:
            raise RangeContractError("incomplete native presentation table")
        for field in sorted(required):
            path = "intervals/" + name + "/" + field
            fields[path] = layout(native.internal(file, path))
    return fields


def headers(selection, assets_manifest, native, store, budget, runtime, cap):
    assets = validate_assets(assets_manifest, selection)
    entries = []
    for row in full_scope(selection):
        eid = row["ophys_experiment_id"]
        with open_versioned(assets[eid], budget, runtime) as file:
            fields = field_layouts(file, native)
        ref = write_value(store, "layout_" + eid,
            {"schema": "neural063_range_layout_v1", "experiment": eid,
             "asset_sha256": digest(vars(assets[eid])), "fields": fields,
             "array_values_decoded": False, "full_object_BLAKE2b_verified": False},
            "range_layout", cap)
        entries.append({"experiment": eid, "layout": ref})
    return write_value(store, "layout_bank", {"schema": "neural063_range_layout_bank_v1",
        "entries": entries, "selection_sha256": SELECTION_SHA256,
        "assets_sha256": digest(assets_manifest), "source_counts": EXPECTED,
        "array_values_decoded": False, "full_object_BLAKE2b_verified": False}, "range_layout_bank", cap)


def metadata(selection, assets_manifest, layout_bank, native, store, budget, runtime, cap):
    assets = validate_assets(assets_manifest, selection)
    if (layout_bank.get("schema") != "neural063_range_layout_bank_v1" or
            layout_bank["assets_sha256"] != digest(assets_manifest) or
            layout_bank["selection_sha256"] != SELECTION_SHA256):
        raise RangeContractError("full layout census must precede metadata arrays")
    layouts = {e["experiment"]: e["layout"] for e in layout_bank["entries"]}
    if len(layout_bank["entries"]) != 1936 or set(layouts) != set(assets):
        raise RangeContractError("complete original layout census required")
    entries = []
    for row in full_scope(selection):
        eid = row["ophys_experiment_id"]
        expected = read_value(store, layouts[eid], "range_layout", cap, "neural063_range_layout_v1")
        if expected["experiment"] != eid or expected["asset_sha256"] != digest(vars(assets[eid])):
            raise RangeContractError("layout identity mismatch")
        with open_versioned(assets[eid], budget, runtime) as file:
            if field_layouts(file, native) != expected["fields"]:
                raise RangeContractError("same-version layout changed before metadata decoding")
            dataset, info = native.neural_metadata(file, row)
            records = native.presentations(file)
            native_layout = layout(dataset)
        value = {"schema": "neural063_range_native_metadata_v1", "experiment": eid,
                 "mouse": row["mouse_id"], "session": row["ophys_session_id"], "split": row["split"],
                 "asset_sha256": digest(vars(assets[eid])), "neural_metadata": info,
                 "presentations": records, "presentation_sha256": digest(records),
                 "layout": native_layout, "response_projection_performed": False,
                 "full_object_BLAKE2b_verified": False}
        ref = write_value(store, "metadata_" + eid, value, "range_native_metadata", cap)
        entries.append({"experiment": eid, "metadata": ref})
    result = {"schema": "neural063_range_metadata_bank_v1", "entries": entries,
              "source_counts": EXPECTED, "selection_sha256": SELECTION_SHA256,
              "assets_sha256": digest(assets_manifest), "neural_values_decoded": False,
              "layout_bank_sha256": digest(layout_bank),
              "opaque_cache_may_contain_adjacent_signal_bytes": True,
              "full_object_BLAKE2b_verified": False}
    return write_value(store, "metadata_bank", result, "range_metadata_bank", cap)


def derive_session(rows, planes, alg):
    """Same consensus, schedule, clock support and privacy checks as original S04."""
    if not rows or set(planes) != {r["ophys_experiment_id"] for r in rows}:
        raise RangeContractError("complete session planes required")
    sid = rows[0]["ophys_session_id"]
    records = next(iter(planes.values()))["presentations"]
    for row in rows:
        plane = planes[row["ophys_experiment_id"]]
        identity_matches(plane, row)
        if (row["ophys_session_id"] != sid or plane["session"] != sid or
                plane["presentation_sha256"] != digest(records) or plane["presentations"] != records):
            raise RangeContractError("all-plane presentation consensus failed")
    schedule = alg.schedule(records)
    supports = {}
    for row in rows:
        eid = row["ophys_experiment_id"]
        clock = planes[eid]["neural_metadata"]["clock"]
        alg.validate_clock(clock)
        supported, unsupported = [], []
        for k in schedule["selected"]:
            event = records[k]
            try:
                spans = alg.native_bins(clock, event["start"])
            except alg.ClockUnsupported as exc:
                unsupported.append({"key": event["key"], "reason": str(exc), "category": "clock_unsupported"})
                continue
            supported.append({"key": event["key"], "presentation_index": k,
                              "onset": event["start"], "spans": spans})
        privacy = {"scope": "not_query", "history_intervals": 0, "held_target_intervals": 0, "intersections": 0}
        if row["split"] == "query":
            histories = [[e["spans"][0][0], e["spans"][11][1]] for e in supported]
            targets = [[bisect_left(clock, records[k]["start"]), bisect_left(clock, records[k]["start"] + .6)]
                       for k in schedule["selected"]]
            alg.intersections(histories, targets)
            privacy = {"scope": "all_session_scheduled_targets_mapped_to_this_plane_clock",
                       "history_intervals": len(histories), "held_target_intervals": len(targets), "intersections": 0}
        value = {"experiment": eid, "session": sid, "mouse": row["mouse_id"], "split": row["split"],
                 "supported_events": supported, "clock_unsupported_events": unsupported,
                 "privacy": privacy, **{k: schedule[k] for k in
                 ("original_omissions", "timing_excluded", "thinning_excluded", "scheduled")},
                 "supported": len(supported), "clock_unsupported": len(unsupported)}
        if (value["original_omissions"] != value["timing_excluded"] + value["thinning_excluded"] + value["scheduled"] or
                value["scheduled"] != value["supported"] + value["clock_unsupported"]):
            raise RangeContractError("complete disjoint omission census failed")
        supports[eid] = value
    return {"session": sid, "presentations": records, "presentation_sha256": digest(records),
            "experiment_ids": sorted(planes), **schedule}, supports


def schedules(selection, assets_manifest, metadata_bank, alg, store, cap):
    assets = validate_assets(assets_manifest, selection)
    if (metadata_bank.get("schema") != "neural063_range_metadata_bank_v1" or
            metadata_bank["assets_sha256"] != digest(assets_manifest) or
            metadata_bank["selection_sha256"] != SELECTION_SHA256):
        raise RangeContractError("complete alternative metadata binding required")
    entries = {e["experiment"]: e["metadata"] for e in metadata_bank["entries"]}
    rows = full_scope(selection)
    if len(metadata_bank["entries"]) != 1936 or set(entries) != {r["ophys_experiment_id"] for r in rows}:
        raise RangeContractError("complete unique metadata bank required")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["ophys_session_id"]].append(row)
    sessions, experiments = [], []
    for sid, session_rows in sorted(grouped.items()):
        planes = {r["ophys_experiment_id"]: read_value(store, entries[r["ophys_experiment_id"]], "range_native_metadata", cap,
                  "neural063_range_native_metadata_v1")
                  for r in session_rows}
        for eid, plane in planes.items():
            if (plane["asset_sha256"] != digest(vars(assets[eid])) or
                    plane.get("full_object_BLAKE2b_verified") is not False or
                    plane.get("response_projection_performed") is not False):
                raise RangeContractError("metadata source identity/custody mismatch")
        schedule, supports = derive_session(session_rows, planes, alg)
        schedule["schema"] = "neural063_range_session_schedule_v1"
        schedule_ref = write_value(store, "schedule_" + sid, schedule, "range_session_schedule", cap)
        sessions.append({"session": sid, "schedule": schedule_ref})
        for row in session_rows:
            eid = row["ophys_experiment_id"]
            value = {"schema": "neural063_range_support_v1", **supports[eid],
                     "metadata": entries[eid], "schedule": schedule_ref}
            ref = write_value(store, "support_" + eid, value, "range_experiment_support", cap)
            experiments.append({"experiment": eid, "support": ref})
    bank = {"schema": "neural063_range_schedule_bank_v1", "sessions": sessions, "experiments": experiments,
            "selection_sha256": SELECTION_SHA256, "assets_sha256": digest(assets_manifest),
            "metadata_bank_sha256": digest(metadata_bank), "schedule_before_response_projection": True,
            "full_object_BLAKE2b_verified": False}
    return write_value(store, "schedule_bank", bank, "range_schedule_bank", cap)


def project_events(dataset, metadata, records, support, alg, row):
    """Unchanged original population() math; hash exact consumed native slices."""
    result, slices = [], []
    def read_rows(left, right):
        array = dataset[left:right, :]
        slices.append({"left": left, "right": right, "shape": list(array.shape),
                       "dtype": str(array.dtype), "sha256_C_order": hashlib.sha256(array.tobytes(order="C")).hexdigest()})
        return array.tolist()
    for event in support["supported_events"]:
        history, target = alg.population(read_rows, metadata["columns"], event["spans"])
        k, onset = event["presentation_index"], event["onset"]
        previous = [{"image": p["image"], "omitted": p["omitted"], "start_relative_seconds": p["start"] - onset}
                    for p in records[k-3:k]]
        result.append({"source_event": event["key"], "source_experiment": row["ophys_experiment_id"],
                       "source_mouse": row["mouse_id"], "source_session": row["ophys_session_id"],
                       "split": row["split"], "history": history, "target": target,
                       "previous": previous, "context": row["context"], "spans": event["spans"]})
    return result, slices


def projections(selection, assets_manifest, schedule_bank, native, alg, store, budget, runtime, cap):
    assets = validate_assets(assets_manifest, selection)
    rows = full_scope(selection)
    if (schedule_bank.get("schema") != "neural063_range_schedule_bank_v1" or
            schedule_bank.get("schedule_before_response_projection") is not True or
            schedule_bank["assets_sha256"] != digest(assets_manifest) or
            schedule_bank["selection_sha256"] != SELECTION_SHA256 or len(schedule_bank["sessions"]) != 703 or
            {s["session"] for s in schedule_bank["sessions"]} != {row["ophys_session_id"] for row in rows}):
        raise RangeContractError("full pre-response schedule bank required")
    entries = {e["experiment"]: e["support"] for e in schedule_bank["experiments"]}
    if len(schedule_bank["experiments"]) != 1936 or set(entries) != set(assets):
        raise RangeContractError("full projection support join required")
    produced, dispositions, supported_mice = [], [], set()
    count = 0
    for row in rows:
        eid = row["ophys_experiment_id"]
        support = read_value(store, entries[eid], "range_experiment_support", cap, "neural063_range_support_v1")
        previous = read_value(store, support["metadata"], "range_native_metadata", cap, "neural063_range_native_metadata_v1")
        session = read_value(store, support["schedule"], "range_session_schedule", cap, "neural063_range_session_schedule_v1")
        identity_matches(support, row)
        identity_matches(previous, row)
        if session["session"] != row["ophys_session_id"] or eid not in session["experiment_ids"]:
            raise RangeContractError("embedded session schedule identity mismatch")
        with open_versioned(assets[eid], budget, runtime) as file:
            dataset, current = native.neural_metadata(file, row)
            if (current != previous["neural_metadata"] or native.presentations(file) != session["presentations"] or
                    previous["asset_sha256"] != digest(vars(assets[eid]))):
                raise RangeContractError("same-version metadata changed since schedule")
            projected, slice_hashes = project_events(dataset, current, session["presentations"], support, alg, row)
        if len(projected) != support["supported"]:
            raise RangeContractError("projection/support count mismatch")
        count += len(projected)
        if count > 1000000:
            raise RangeContractError("full-panel event bound exceeded; no truncation")
        if projected:
            supported_mice.add(row["mouse_id"])
        ref = write_value(store, "projection_" + eid,
            {"schema": "neural063_range_projection_v1", "experiment": eid, "rows": projected,
             "slice_hashes": slice_hashes, "asset_sha256": digest(vars(assets[eid])),
             "full_object_BLAKE2b_verified": False}, "range_projection", cap)
        produced.append({"experiment": eid, "projection": ref})
        dispositions.append({"experiment": eid, "support": entries[eid], "rows": len(projected)})
    missing = sorted(set(selection["mouse_assignments"]) - supported_mice)
    census = {"schema": "neural063_range_projection_census_v1", "experiments": dispositions,
              "rows": count, "source_counts": EXPECTED, "missing_mouse_support": missing,
              "selection_sha256": SELECTION_SHA256, "assets_sha256": digest(assets_manifest),
              "schedule_bank_sha256": digest(schedule_bank), "full_object_BLAKE2b_verified": False}
    census_ref = write_value(store, "projection_census", census, "range_projection_census", cap)
    if missing:
        raise RangeContractError("full107-mouse support not established; retained census is not completion")
    return write_value(store, "projection_bank", {"schema": "neural063_range_projection_bank_v1",
        "experiments": produced, "rows": count, "census": census_ref,
        "full_object_BLAKE2b_verified": False, "scientific_equivalence_qualified": False}, "range_projection_bank", cap)
