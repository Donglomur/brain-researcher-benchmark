#!/usr/bin/env python3
"""Single-session original-MAT metadata and shape inspection, never decoding.

The public entry point binds the published cfa24/M1 asset. The structure helper
is intentionally unqualified and exists for generated HDF5 controls. Neither
path reads events, pose, or joint-angle values or performs original alignment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import types

AUTHOR_COMMIT = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
SESSION = "cfa24_20220727_160603"
FILENAME = "R,cfa24_20220727_160603,thresholded,DLC3.mat"
FILE_ID = 60332984
SOURCE_BYTES = 980063226
SOURCE_MD5 = "5c89cea4cae04adf8c21f46b740d2c4b"
READER_BYTES = 34094
READER_SHA256 = "ffe2d7d43386f53f92e9e97b07e422581d8fc05e2fa53471bdb9ba38bbcd7ab6"
SCALAR_EXTRA = ("LR", "liftTimeDLC", "syncTime", "hasNeuralData", "maxCams")
LIMIT_CAPS = {
    "max_decoded_elements": 5000000,
    "max_trials": 20000,
    "max_shape_nodes": 100000,
    "max_clock_points_per_trial": 100000,
    "max_report_bytes": 16777216,
}


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load_reader(path):
    """Execute only the already-pinned selective reader, at authorized runtime."""
    path = Path(path)
    for item in [path, *path.parents]:
        require(not item.is_symlink(), "Reader symlink refused")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == READER_BYTES, "Reader file identity refused")
        body = handle.read(READER_BYTES + 1)
        after = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                 before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size,
                                        after.st_mtime_ns, after.st_ctime_ns),
                "Reader changed while loading")
    require(len(body) == READER_BYTES and hashlib.sha256(body).hexdigest() == READER_SHA256,
            "Reader source pin mismatch")
    module = types.ModuleType("calcium_single_session_pinned_reader")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def validate_limits(limits):
    require(isinstance(limits, dict) and set(limits) == set(LIMIT_CAPS),
            "Exactly the five inspection limits are required")
    for key, cap in LIMIT_CAPS.items():
        require(type(limits[key]) is int and 0 < limits[key] <= cap,
                "Unsupported bounded limit: " + key)
    return dict(limits)


def json_scalar(value, a, name, *, nan=False):
    out = a.scalar(value, name, nan=nan)
    return "NaN" if math.isnan(out) else out


def inspect_structure(h5_file, a, limits):
    """Inspect a supplied HDF5 handle; never authenticate it as the public asset.

    Generated controls call this helper. Only inspect_file supplies independent
    filename/byte-count/whole-file hash binding. Shape-only datasets are never
    passed to Mat73._leaf or Dataset.__getitem__.
    """
    limits = validate_limits(limits)
    np, h5py = a.np, a.h5py

    def guard_attribute(node, name, *, scalar_only=False):
        require(name in node.attrs, "Missing bounded MATLAB attribute: " + name)
        attr = node.attrs.get_id(name)
        space = None
        try:
            dtype = attr.dtype
            space = attr.get_space()
            count = space.get_simple_extent_npoints()
            require(h5py.check_dtype(vlen=dtype) is None and dtype.kind in "Siufb" and
                    not dtype.fields and 0 < dtype.itemsize <= 256 and
                    0 < count <= 256 and count * dtype.itemsize <= 256,
                    "Unbounded/vlen MATLAB attribute refused: " + name)
            require(not scalar_only or count == 1, "MATLAB attribute must be scalar: " + name)
            require(not scalar_only or dtype.kind in "iufb", "MATLAB flag attribute must be numeric")
            if name == "MATLAB_class":
                require(dtype.kind == "S" and count == 1, "MATLAB_class must be fixed-width ASCII")
        finally:
            if space is not None:
                space.close()
            attr.close()

    def guard_storage(node, *, reading):
        require(isinstance(node, h5py.Dataset), "Expected HDF5 dataset")
        require(not node.is_virtual and not node.external, "External/virtual HDF5 storage refused")
        ref = h5py.check_dtype(ref=node.dtype)
        require(ref is None or ref is h5py.Reference, "Region reference refused")
        require(not node.dtype.fields and 0 < node.dtype.itemsize <= 8 and
                (ref is h5py.Reference or (h5py.check_dtype(vlen=node.dtype) is None and
                                         node.dtype.kind in "iufb")),
                "Unsupported/vlen dataset storage")
        plist = node.id.get_create_plist()
        try:
            require(plist.get_nfilters() <= 3, "Too many HDF5 filters")
            require(all(plist.get_filter(i)[0] in {1, 2, 3}
                        for i in range(plist.get_nfilters())), "Unreviewed HDF5 filter refused")
        finally:
            plist.close()
        if reading and node.chunks is not None:
            require(math.prod(node.chunks) * node.dtype.itemsize <= 8388608,
                    "Decoded HDF5 chunk exceeds8MiB")

    class GuardedMat73(a.Mat73):
        def _class(self, node):
            guard_attribute(node, "MATLAB_class")
            return super()._class(node)

        def _charge(self, node):
            guard_storage(node, reading=True)
            return super()._charge(node)

    reader = GuardedMat73(h5_file, max_elements=limits["max_decoded_elements"],
                          max_records=limits["max_trials"])
    fields = dict(a.RAW_FIELDS)
    fields.update({key: None for key in SCALAR_EXTRA})
    rows = reader.read("R", fields)
    census = a.raw_census(rows, SESSION, types.SimpleNamespace(SESSIONS={SESSION: ("cfa24", "M1")}))
    group = reader._child(h5_file, "R")
    count = len(rows)
    shape_nodes = 0

    def nodes_for(parent, name, expected):
        child = reader._child(parent, name)
        if isinstance(child, h5py.Dataset) and h5py.check_dtype(ref=child.dtype) is not None and "MATLAB_class" not in child.attrs:
            reader._charge(child)
            require(child.ndim <= 2 and (child.ndim < 2 or 1 in child.shape),
                    "Reference field must be a MATLAB vector: " + name)
            refs = child[()].T.reshape(-1, order="F")
            require(len(refs) == expected, "Original field count mismatch: " + name)
            return [h5_file[ref] for ref in refs if reader._nonnull(ref)]
        require(expected == 1, "Nonscalar R field lacks references: " + name)
        return [child]

    def shape_only(node, name, allowed_ranks):
        nonlocal shape_nodes
        shape_nodes += 1
        require(shape_nodes <= limits["max_shape_nodes"], "Shape-node limit exceeded")
        guard_storage(node, reading=False)
        require(h5py.check_dtype(ref=node.dtype) is None and node.dtype.kind in "iufb" and not node.dtype.fields,
                "Compound/complex/reference numeric shape refused")
        cls = reader._class(node)
        require(cls in {"double", "single", "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "logical"},
                "Unsupported numeric MATLAB class")
        require(node.ndim in allowed_ranks and all(0 <= int(x) <= 2**53 for x in node.shape),
                "Unsupported MATLAB rank/extent: " + name)
        # MATLAB-empty metadata can encode dimensions in dataset VALUES. Reading
        # those as a pose/angle payload would violate this operator's boundary.
        if "MATLAB_empty" in node.attrs:
            guard_attribute(node, "MATLAB_empty", scalar_only=True)
            require(not bool(node.attrs["MATLAB_empty"]),
                    "MATLAB_empty value-encoded shape requires a separately reviewed reader")
        shape = list(reversed([int(x) for x in node.shape]))
        return {"matlab_shape": shape, "dtype": str(node.dtype), "matlab_class": cls,
                "elements": math.prod(shape), "values_read": False}

    def clock(node, name):
        shape = shape_only(node, name, {1, 2})
        dims = shape["matlab_shape"]
        require(len(dims) < 2 or 1 in dims or shape["elements"] == 0,
                "Clock must be a MATLAB vector: " + name)
        require(shape["elements"] <= limits["max_clock_points_per_trial"], "Clock point limit exceeded")
        vector = np.asarray(reader._leaf(node)).reshape(-1, order="F")
        require(vector.dtype.kind in "iuf" and bool(np.all(np.isfinite(vector))), "Nonfinite/nonnumeric clock")
        if vector.dtype.kind in "iu":
            require(bool(np.all(vector <= 2**53)) and
                    (vector.dtype.kind == "u" or bool(np.all(vector >= -(2**53)))), "Clock integer precision loss")
        vector = vector.astype(float)
        require(vector.size < 2 or bool(np.all(np.diff(vector) > 0)), "Clock is not strictly increasing")
        steps = np.diff(vector)
        require(bool(np.all(np.isfinite(steps))), "Clock differences overflow")
        median = float(np.median(steps)) if steps.size else None
        deviation = float(np.max(np.abs(steps - median))) if steps.size else None
        require(median is None or (math.isfinite(median) and math.isfinite(deviation)),
                "Clock summary overflow")
        summary = {"count": int(vector.size), "matlab_shape": dims,
                   "values_sha256": digest(vector.tolist()),
                   "first_ms": float(vector[0]) if vector.size else None,
                   "last_ms": float(vector[-1]) if vector.size else None,
                   "median_step_ms": median,
                   "maximum_step_deviation_ms": deviation}
        return vector, summary

    m = reader.read("M", {"ROILags": None, "cycleDurMs": None})
    require(len(m) == 1, "M must be scalar")
    lags, lag_hash = a.roi_metadata(m[0])
    lag_values = lags.reshape(-1, order="F").astype(float)
    cycle = a.scalar(m[0]["cycleDurMs"], "cycleDurMs")
    require(cycle > 0 and cycle >= 10, "Cycle must support the author's10ms event grid")
    events = nodes_for(group, "events", count)
    frames = nodes_for(group, "frameTimes", count)
    cams = nodes_for(group, "cam", count)
    poses = nodes_for(group, "posXYZ", count) if "posXYZ" in group else None
    joints = nodes_for(group, "jointAngles", count) if "jointAngles" in group else None
    eligible_positions = [i for i, row in enumerate(census["ordered_original_trials"])
                          if row["eligible_by_loadLock4Decode"]]
    eligible_set = set(eligible_positions)
    require(eligible_positions, "No author-eligible trials")
    max_cam_positions = [i for i in eligible_positions if a.flag(rows[i]["maxCams"], "maxCams")]
    neural_positions = [i for i in eligible_positions if a.flag(rows[i]["hasNeuralData"], "hasNeuralData")]
    require(max_cam_positions, "No eligible maxCams trial for original camera time base")
    require(neural_positions, "No eligible neural trial for original ROI width")
    first_cam, first_neural = max_cam_positions[0], neural_positions[0]
    first_cam_summary = None
    original_roi_width = None
    records, pending = [], []

    def unused_scalar(value, name):
        array = np.asarray(value)
        if array.size == 0:
            return {"state": "empty", "matlab_shape": list(array.shape)}
        if array.dtype.kind == "b":
            return a.flag(value, name)
        return json_scalar(value, a, name, nan=True)

    for index, row in enumerate(rows):
        scalar_values = {}
        for key in a.RAW_FIELDS:
            if key in ("animalID", "date"):
                scalar_values[key] = a.text(row[key], key)
            elif key in ("success", "goodDLC", "wrongZoneFirst", "has_radical"):
                scalar_values[key] = a.flag(row[key], key)
            elif key == "trialNumber":
                scalar_values[key] = a.number(row[key], key)
            else:
                scalar_values[key] = json_scalar(row[key], a, key, nan=True)
        for key in ("hasNeuralData", "maxCams"):
            scalar_values[key] = (a.flag(row[key], key) if index in eligible_set
                                  else unused_scalar(row[key], key))
        lr = (a.number(row["LR"], "LR") if index in eligible_set else unused_scalar(row["LR"], "LR"))
        require(index not in eligible_set or lr in (1, 2), "LR must preserve source1/2 coding")
        scalar_values["LR"] = lr
        for key in ("liftTimeDLC", "syncTime"):
            scalar_values[key] = (json_scalar(row[key], a, key, nan=True) if index in eligible_set
                                  else unused_scalar(row[key], key))
        rec = {"raw_ordinal_one_based": index + 1, "original_trial_number": scalar_values["trialNumber"],
               "scalar_values": scalar_values, "eligibility": census["ordered_original_trials"][index],
               "eligible_clock_and_shape_inspection": index in eligible_set}
        if index not in eligible_set:
            records.append(rec)
            continue
        evshape = shape_only(events[index], "events", {2})
        frame_values, frame_summary = clock(frames[index], "frameTimes")
        camera = cams[index]
        require(isinstance(camera, h5py.Group) and reader._class(camera) == "struct", "cam must be struct")
        times_child = reader._child(camera, "times")
        is_refs = isinstance(times_child, h5py.Dataset) and h5py.check_dtype(ref=times_child.dtype) is not None and "MATLAB_class" not in times_child.attrs
        camera_count = math.prod(times_child.shape) if is_refs else 1
        require(0 < camera_count <= 16, "Unsupported camera count")
        camera_times = nodes_for(camera, "times", camera_count)
        cam_values, cam_summary = clock(camera_times[0], "cam(1).times")
        if index == first_cam:
            require(cam_values.size >= 2, "First eligible maxCams clock needs at least2points")
            first_cam_summary = {"raw_ordinal_one_based": index + 1,
                                 "original_trial_number": scalar_values["trialNumber"],
                                 "clock": cam_summary, "cam_time_base_ms": cam_summary["median_step_ms"]}
        pos = shape_only(poses[index], "posXYZ", {2, 3}) if poses is not None else None
        ang = shape_only(joints[index], "jointAngles", {2}) if joints is not None else None
        if pos is not None and pos["elements"]:
            require(len(pos["matlab_shape"]) == 3 and pos["matlab_shape"][1] == 3 and
                    pos["matlab_shape"][2] >= 15, "Nonempty pose must be time×XYZ×at_least15markers")
            require(pos["matlab_shape"][0] == cam_summary["count"], "Pose/camera row mismatch")
        if ang is not None and ang["elements"]:
            require(ang["matlab_shape"] == [cam_summary["count"], 24], "Joint/camera24-channel row mismatch")
        if scalar_values["hasNeuralData"]:
            require(evshape["matlab_shape"][0] == frame_summary["count"] and frame_summary["count"] >= 2,
                    "Neural/frame row mismatch or insufficient source support")
            require(evshape["matlab_shape"][1] == int(lag_values.size), "Events/ROI-lag column mismatch")
        if index == first_neural:
            original_roi_width = evshape["matlab_shape"][1]
        event = scalar_values["liftTimeDLC"]
        sync = scalar_values["syncTime"]
        finite_event = event != "NaN"
        finite_sync = sync != "NaN"
        frame_bounds = None
        if scalar_values["hasNeuralData"] and finite_event and finite_sync:
            # Preserve the author's operation order; this is a float64 metadata
            # diagnostic, not proof of native MATLAB type/numerical parity.
            ev_relative = event - sync
            require(math.isfinite(ev_relative), "Event-sync clock subtraction overflow")
            frame_zero = 1 + (ev_relative - float(frame_values[0])) / cycle
            require(math.isfinite(frame_zero), "Event frame-coordinate overflow")
            first_coordinate = frame_zero + (-270 / cycle)
            last_coordinate = frame_zero + (870 / cycle)
            require(math.isfinite(first_coordinate) and math.isfinite(last_coordinate),
                    "Padded frame-coordinate overflow")
            early = first_coordinate - float(np.max(lag_values)) / cycle
            late = last_coordinate - float(np.min(lag_values)) / cycle
            require(math.isfinite(early) and math.isfinite(late), "Neural frame geometry overflow")
            lo, hi = math.floor(early), math.ceil(late)
            frame_bounds = {"minimum_one_based_index": lo, "maximum_one_based_index": hi,
                            "within_events_rows": 1 <= lo and hi <= evshape["matlab_shape"][0]}
        camera_bounds = None
        if cam_values.size and finite_event and finite_sync:
            start, end = float(cam_values[0] + sync - event), float(cam_values[-1] + sync - event)
            require(math.isfinite(start) and math.isfinite(end), "Event-relative camera clock overflow")
            camera_bounds = {"first_event_relative_ms": start, "last_event_relative_ms": end,
                             "covers_original101_grid": start <= -200 and end >= 800}
        gates = []
        if not scalar_values["hasNeuralData"]:
            gates.append("hasNeuralData_false_author_neural_lock_skips")
        frame_matches_cycle = frame_summary["median_step_ms"] == cycle and frame_summary["maximum_step_deviation_ms"] == 0
        if scalar_values["hasNeuralData"] and not frame_matches_cycle:
            gates.append("recorded_frame_clock_not_exact_fixed_cycle_model")
        if poses is None:
            gates.append("posXYZ_absent_requires_original_addPosXYZ_route")
        elif not pos["elements"]:
            gates.append("pose_empty_author_kinematic_lock_skips")
        if joints is None:
            gates.append("jointAngles_absent_getInverseKinematics_source_required")
        elif not ang["elements"]:
            gates.append("jointAngles_field_present_but_empty_no_automatic_helper_fallback")
        if not finite_event:
            gates.append("event_nan_author_lock_skips")
        if not finite_sync:
            gates.append("sync_nan_clock_unusable")
        if frame_bounds is not None and not frame_bounds["within_events_rows"]:
            gates.append("padded_neural_frame_support_incomplete")
        if camera_bounds is None or not camera_bounds["covers_original101_grid"]:
            gates.append("original_camera101_grid_support_incomplete")
        rec.update({"events": evshape, "frame_clock": frame_summary, "camera1_clock": cam_summary,
                    "camera_count": camera_count, "posXYZ": pos, "jointAngles": ang,
                    "frame_clock_exactly_matches_cycle_duration": frame_matches_cycle,
                    "padded_neural_frame_bounds": frame_bounds, "camera_event_bounds": camera_bounds,
                    "author_neural_lock_precondition": scalar_values["hasNeuralData"] and finite_event and finite_sync,
                    "author_kinematic_lock_precondition": finite_event and pos is not None and bool(pos["elements"]),
                    "gates": gates})
        pending.append((rec, cam_summary["median_step_ms"]))
        records.append(rec)
    for rec, median_step in pending:
        rec["camera_step_equals_author_shared_median"] = median_step == first_cam_summary["cam_time_base_ms"]
        if median_step != first_cam_summary["cam_time_base_ms"]:
            rec["gates"].append("camera_step_differs_from_author_first_eligible_maxCams_median")
    result = {
        "schema": "calcium_single_session_metadata_shapes_v1", "task_id": "NEURAL-025",
        "session_id": SESSION, "author_commit": AUTHOR_COMMIT,
        "source_binding": {"published_asset_verified": False, "scope": "supplied_hdf5_structure_only"},
        "complete_scalar_census": census, "trials": records,
        "first_eligible_max_cams": first_cam_summary,
        "first_eligible_neural": {"raw_ordinal_one_based": first_neural + 1,
                                  "original_trial_number": records[first_neural]["original_trial_number"],
                                  "source_roi_columns": original_roi_width},
        "roi_metadata": {"cycle_duration_ms": cycle, "roi_columns": int(lag_values.size),
                          "roilags_sha256": lag_hash, "minimum_lag_ms": float(np.min(lag_values)),
                          "maximum_lag_ms": float(np.max(lag_values))},
        "source_preparation": {"locked_grid_ms": [-200, 800, 10], "locked_rows": 101,
                               "requested_neural_padded_grid_ms": [-270, 870, 10], "padded_rows": 115,
                               "evaluation_grid_ms": [-100, 400, 10], "evaluation_rows": 51,
                               "smooth_sd_ms": 35, "added_predictor_lags": 0,
                               "alignment_executed": False, "numeric_parity_established": False},
        "read_accounting": {"decoded_elements": reader.loaded, "shape_nodes": shape_nodes,
                            "signal_pose_joint_values_read": False},
        "qualification": {"native_clock_alignment": False, "original_column_lineage": False,
                          "inverse_kinematics_parity": False, "upstream_exposure": False,
                          "full_cohort_admission": False, "scientific_qualification": False},
        "limits": limits,
    }
    require(len(canonical(result)) <= limits["max_report_bytes"], "Report exceeds admitted byte limit")
    return result


def inspect_file(manifest, input_root, reader_path):
    """Strict public-asset entry; whole-file hashing is an explicit future cost."""
    a = load_reader(reader_path)
    require(isinstance(manifest, dict) and set(manifest) == {"schema", "author_commit", "source", "limits"},
            "Unexpected single-session manifest fields")
    require(manifest["schema"] == "calcium_single_session_metadata_manifest_v1" and
            manifest["author_commit"] == AUTHOR_COMMIT, "Wrong source manifest identity")
    entry = manifest["source"]
    require(isinstance(entry, dict) and set(entry) == {"session_id", "figshare_file_id", "path", "bytes", "sha256"},
            "Unexpected original source entry")
    require(entry["session_id"] == SESSION and type(entry["figshare_file_id"]) is int and
            entry["figshare_file_id"] == FILE_ID and type(entry["bytes"]) is int and entry["bytes"] == SOURCE_BYTES,
            "Wrong published single-session asset")
    require(isinstance(entry["path"], str) and Path(entry["path"]).name == FILENAME,
            "Wrong original MAT filename")
    limits = validate_limits(manifest["limits"])
    handle, before = a.opened_mat(Path(input_root), entry, {"max_file_bytes": SOURCE_BYTES}, published_md5=SOURCE_MD5)
    try:
        with a.h5py.File(handle, "r") as h5:
            result = inspect_structure(h5, a, limits)
        a.stable(handle, before)
    finally:
        handle.close()
    result["source_binding"] = {"published_asset_verified": True, "session_id": SESSION,
                                "filename": FILENAME, "figshare_file_id": FILE_ID,
                                "bytes": SOURCE_BYTES, "published_md5": SOURCE_MD5,
                                "sha256": entry["sha256"], "manifest_sha256": digest(manifest),
                                "whole_file_bytes_hashed": SOURCE_BYTES,
                                "scope": "file_checksums_and_metadata_only_not_scientific_identity"}
    require(len(canonical(result)) <= limits["max_report_bytes"], "Bound report exceeds admitted byte limit")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--reader", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    a = load_reader(args.reader)
    manifest = a.read_json(args.manifest, args.manifest_sha256, 65536)
    for path in [args.output, *args.output.parents]:
        require(not path.is_symlink(), "Output symlink refused")
    require(args.output.is_absolute() and args.output.parent.is_dir() and not args.output.exists(),
            "Output must be a new absolute private file")
    result = inspect_file(manifest, args.input_root, args.reader)
    body = canonical(result) + b"\n"
    require(len(body) <= manifest["limits"]["max_report_bytes"], "Output byte cap exceeded")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
    print(json.dumps({"output_bytes": len(body), "output_sha256": hashlib.sha256(body).hexdigest(),
                      "scientific_qualification": False}, sort_keys=True))


if __name__ == "__main__":
    main()
