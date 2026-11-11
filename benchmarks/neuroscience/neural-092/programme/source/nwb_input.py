"""Bounded direct reader for the held Allen Visual Coding Neuropixels schema.

Source: held AllenSDK nwb_api/project_cache/ecephys_init and the two closed NWB
schema inventories. No SDK imports, pickle, network, models or cached metrics.
Authentication covers the same regular descriptor used by h5py before/after
reading. Construction caps refuse unsupported inputs; they never subsample.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import math
import os
from pathlib import Path
import re
import stat

import h5py
import numpy as np

AREAS = ("VISp", "VISl", "VISal", "VISrl", "VISam", "VISpm")
MAX_FILE = 32 * 1024**3
MAX_UNITS, MAX_ELECTRODES, MAX_TRIALS = 50_000, 20_000, 100_000
MAX_SPIKES_UNIT, MAX_SPIKES_TOTAL, MAX_RUNNING = 5_000_000, 1_000_000_000, 5_000_000
MAX_COUNT_BYTES = 512 * 1024**2
BASE_FIELDS = {"color", "contrast", "id", "mask", "opacity", "orientation", "phase", "size",
               "spatial_frequency", "start_time", "stimulus_block", "stimulus_index", "stimulus_name",
               "stop_time", "units"}
FAMILY_EXTRA = {"static_gratings": set(), "drifting_gratings": {"temporal_frequency"},
                "flashes": set(), "gabors": {"temporal_frequency", "x_position", "y_position"}}


class InputError(ValueError):
    pass


class UnsupportedSchema(InputError):
    pass


def _identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_uid, s.st_gid,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _hash(handle, size):
    handle.seek(0)
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        block = handle.read(min(1024**2, remaining))
        if not block:
            raise InputError("short source file")
        digest.update(block)
        remaining -= len(block)
    if handle.read(1):
        raise InputError("source exceeds pinned size")
    return digest.hexdigest()


def _safe_graph(f):
    stack, seen, links = [f], set(), 0
    while stack:
        group = stack.pop()
        addr = h5py.h5o.get_info(group.id).addr
        if addr in seen:
            continue
        seen.add(addr)
        for name in group:
            links += 1
            if links > 200_000:
                raise UnsupportedSchema("HDF object graph exceeds source cap")
            link = group.get(name, getlink=True)
            if not isinstance(link, h5py.HardLink):
                raise UnsupportedSchema("soft/external HDF links forbidden")
            obj = group[name]
            if isinstance(obj, h5py.Group):
                stack.append(obj)
            elif isinstance(obj, h5py.Dataset):
                if obj.is_virtual or obj.external:
                    raise UnsupportedSchema("VDS/external dataset storage forbidden")
            else:
                raise UnsupportedSchema("unsupported HDF object")


@contextmanager
def opened(path, descriptor):
    """Yield read-only h5py over one pinned FD; reject symlink path components."""
    if not isinstance(descriptor, dict):
        raise InputError("descriptor mapping required")
    size, sha = descriptor.get("bytes"), descriptor.get("sha256")
    if type(size) is not int or not 0 < size <= MAX_FILE or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise InputError("bounded byte/SHA256 descriptor required")
    raw_path = Path(path)
    if ".." in raw_path.parts:
        raise InputError("parent traversal components are not accepted")
    path = Path(os.path.abspath(os.fspath(raw_path)))
    parts = path.parts[1:]
    if not parts:
        raise InputError("file path required")
    dirs, chain, handle, f = [], [], None, None
    try:
        current = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        dirs.append(current)
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
            s = os.fstat(child)
            chain.append((current, part, (s.st_dev, s.st_ino, s.st_mode)))
            dirs.append(child)
            current = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        handle = os.fdopen(fd, "rb", buffering=0)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != size:
            raise InputError("pinned regular source size required")
        identity = _identity(before)
        if _hash(handle, size) != sha or _identity(os.fstat(fd)) != identity:
            raise InputError("source SHA/stability mismatch before decode")
        named = os.stat(parts[-1], dir_fd=current, follow_symlinks=False)
        if _identity(named) != identity:
            raise InputError("source name/FD mismatch")
        handle.seek(0)
        f = h5py.File(handle, "r")
        _safe_graph(f)
        try:
            yield f
        finally:
            f.close()
            f = None
            if _hash(handle, size) != sha or _identity(os.fstat(fd)) != identity or _identity(os.stat(parts[-1], dir_fd=current, follow_symlinks=False)) != identity:
                raise InputError("source changed during use")
            for parent, name, expected in chain:
                s = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if (s.st_dev, s.st_ino, s.st_mode) != expected:
                    raise InputError("source parent path changed during use")
    finally:
        if f is not None:
            f.close()
        if handle is not None:
            handle.close()
        for fd in reversed(dirs):
            os.close(fd)


def _dataset(f, path, cap):
    if path not in f or not isinstance(f[path], h5py.Dataset):
        raise UnsupportedSchema("required dataset missing: " + path)
    d = f[path]
    if d.ndim != 1 or d.shape[0] > cap or d.is_virtual or d.external:
        raise UnsupportedSchema("unsupported dataset geometry/storage: " + path)
    return d


def _vector(f, path, cap, *, kind=None):
    d = _dataset(f, path, cap)
    string = h5py.check_string_dtype(d.dtype)
    if string is not None:
        if kind is not None:
            raise UnsupportedSchema("numeric/bool field has string dtype: " + path)
        values, used = [], 0
        for start in range(0, len(d), 256):
            # Bounded fixed-width HDF conversion, with one extra byte to detect
            # unsupported strings instead of accepting a truncated value.
            chunk = d.astype("S4097")[start:start + 256]
            for raw in chunk:
                raw = bytes(raw)
                used += len(raw)
                if len(raw) > 4096 or used > 8 * 1024**2:
                    raise UnsupportedSchema("string field exceeds source cap: " + path)
                try:
                    values.append(raw.decode("utf-8"))
                except UnicodeDecodeError as exc:
                    raise UnsupportedSchema("non-UTF8 source string") from exc
        return values
    if d.dtype.kind not in "fiub" or (kind is not None and d.dtype.kind not in kind):
        raise UnsupportedSchema("nonprimitive/unsupported dtype: " + path)
    return d[:]


def _ids(f, path, cap):
    a = _vector(f, path, cap, kind="iu")
    if np.any(a < 0) or len(set(int(x) for x in a)) != len(a):
        raise UnsupportedSchema("duplicate/negative native IDs: " + path)
    return a


def _primitive(value):
    if isinstance(value, str):
        return value
    value = value.item() if isinstance(value, np.generic) else value
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        raise UnsupportedSchema("infinite native metadata")
    return value


def select_units(f):
    uid = _ids(f, "units/id", MAX_UNITS)
    n = len(uid)
    fields = {name: _vector(f, "units/" + name, MAX_UNITS, kind=None if name == "quality" else "fiu")
              for name in ("peak_channel_id", "quality", "amplitude_cutoff", "presence_ratio", "isi_violations")}
    if any(len(v) != n for v in fields.values()):
        raise UnsupportedSchema("unit metadata length mismatch")
    if f["units/peak_channel_id"].dtype.kind not in "iu":
        raise UnsupportedSchema("peak_channel_id must be native integer IDs")
    root = "general/extracellular_ephys/electrodes/"
    eid = _ids(f, root + "id", MAX_ELECTRODES)
    loc = _vector(f, root + "location", MAX_ELECTRODES)
    valid = _vector(f, root + "valid_data", MAX_ELECTRODES, kind="b")
    if len(eid) != len(loc) or len(eid) != len(valid):
        raise UnsupportedSchema("electrode metadata length mismatch")
    electrodes = {int(i): (str(a), bool(v)) for i, a, v in zip(eid, loc, valid)}
    index = _vector(f, "units/spike_times_index", MAX_UNITS, kind="iu")
    spikes = _dataset(f, "units/spike_times", MAX_SPIKES_TOTAL)
    if spikes.dtype.kind != "f" or spikes.dtype.itemsize != 8 or len(index) != n or np.any(index < 0) or np.any(index[1:] < index[:-1]) or (int(index[-1]) if n else 0) != len(spikes):
        raise UnsupportedSchema("invalid complete spike ragged extent")
    records, dispositions, start = [], Counter(), 0
    for i, unit in enumerate(uid):
        peak = int(fields["peak_channel_id"][i])
        area, usable = electrodes.get(peak, (None, None))
        qc = {k: _primitive(fields[k][i]) for k in ("amplitude_cutoff", "presence_ratio", "isi_violations")}
        quality = str(fields["quality"][i])
        reasons = []
        if area is None:
            reasons.append("missing_peak_channel")
        if usable is not True:
            reasons.append("invalid_channel_data")
        if area not in AREAS:
            reasons.append("outside_six_visual_areas")
        if quality != "good":
            reasons.append("quality_not_good")
        for name, passes in (("amplitude_cutoff", lambda x: x <= .1),
                             ("presence_ratio", lambda x: x >= .95),
                             ("isi_violations", lambda x: x <= .5)):
            value = qc[name]
            domain = (value is not None and value >= 0 and
                      (name == "isi_violations" or value <= 1))
            if not domain:
                reasons.append("invalid_domain_" + name)
            elif not passes(value):
                reasons.append("failed_" + name)
        stop = int(index[i])
        record = {"id": int(unit), "unit_row": i, "peak_channel_id": peak, "area": area,
                  "valid_data": usable, "quality": quality, **qc,
                  "spike_start": start, "spike_stop": stop, "eligible": not reasons, "reasons": reasons}
        records.append(record)
        dispositions.update(reasons or ["eligible"])
        start = stop
    return {"units": [r for r in records if r["eligible"]], "all_units": records,
            "dispositions": dict(dispositions), "spike_times_count": len(spikes)}


def _tags(f, root, n):
    values = _vector(f, root + "/tags", MAX_TRIALS * 8)
    ends = _vector(f, root + "/tags_index", MAX_TRIALS, kind="iu")
    if len(ends) != n or np.any(ends < 0) or np.any(ends[1:] < ends[:-1]) or (int(ends[-1]) if n else 0) != len(values):
        raise UnsupportedSchema("invalid tag ragged extent")
    result, start = [], 0
    for stop in ends:
        stop = int(stop)
        result.append([str(x) for x in values[start:stop]])
        start = stop
    return result


def _validate_times(start, stop):
    start, stop = np.asarray(start, dtype=float), np.asarray(stop, dtype=float)
    if start.shape != stop.shape or not np.isfinite(start).all() or not np.isfinite(stop).all() or np.any(stop <= start):
        raise UnsupportedSchema("finite increasing interval endpoints required")
    return start, stop


def intervals(f, family):
    if family not in FAMILY_EXTRA:
        raise UnsupportedSchema("unsupported stimulus family")
    root = "intervals/" + family + "_presentations"
    fields = BASE_FIELDS | FAMILY_EXTRA[family]
    allowed = fields | {"tags", "tags_index", "timeseries", "timeseries_index"}
    if root not in f or not isinstance(f[root], h5py.Group) or set(f[root]) != allowed:
        raise UnsupportedSchema("missing/unsupported native family schema: " + family)
    ids = _ids(f, root + "/id", MAX_TRIALS)
    n = len(ids)
    data = {name: _vector(f, root + "/" + name, MAX_TRIALS) for name in sorted(fields - {"id"})}
    if any(len(v) != n for v in data.values()):
        raise UnsupportedSchema("native stimulus scalar lengths differ")
    _validate_times(data["start_time"], data["stop_time"])
    tags = _tags(f, root, n)
    rows = []
    for i, uid in enumerate(ids):
        row = {"id": int(uid), **{name: _primitive(values[i]) for name, values in data.items()}, "tags": tags[i]}
        row["missing_scalar_fields"] = [name for name in data if row[name] is None]
        rows.append(row)
    return rows


def invalid_intervals(f):
    root = "intervals/invalid_times"
    if root not in f:
        return {"status": "missing", "intervals": np.empty((0, 2)), "rows": []}
    if set(f[root]) != {"id", "start_time", "stop_time", "tags", "tags_index"}:
        raise UnsupportedSchema("unsupported invalid-times schema")
    ids = _ids(f, root + "/id", MAX_TRIALS)
    start, stop = _validate_times(_vector(f, root + "/start_time", MAX_TRIALS, kind="f"),
                                 _vector(f, root + "/stop_time", MAX_TRIALS, kind="f"))
    if len(start) != len(ids):
        raise UnsupportedSchema("invalid-time lengths differ")
    tags = _tags(f, root, len(ids))
    rows = [{"id": int(uid), "start_time": float(a), "stop_time": float(b), "tags": t}
            for uid, a, b, t in zip(ids, start, stop, tags)]
    union = []
    for a, b in sorted(zip(start, stop)):
        if union and a <= union[-1][1]:
            union[-1][1] = max(union[-1][1], float(b))
        else:
            union.append([float(a), float(b)])
    return {"status": "present", "intervals": np.asarray(union, dtype=float).reshape(-1, 2),
            "rows": rows, "policy": "conservative union of all tags"}


def _windows(value):
    a = np.asarray(value)
    if a.ndim != 2 or a.shape[1] != 2 or len(a) > MAX_TRIALS or a.dtype.kind not in "fiu":
        raise InputError("bounded [windows,2] numeric endpoints required")
    a = a.astype(float)
    _validate_times(a[:, 0], a[:, 1])
    if np.any(a < 0):
        raise InputError("negative native query window")
    return a


def count_windows(f, units, windows):
    windows = _windows(windows)
    if len(windows) * len(units) * 8 > MAX_COUNT_BYTES:
        raise UnsupportedSchema("complete count output exceeds 512MiB cap")
    canonical = {r["id"]: r for r in select_units(f)["all_units"]}
    ids = [r["id"] for r in units]
    if len(set(ids)) != len(ids) or any(uid not in canonical or r != canonical[uid] for uid, r in zip(ids, units)):
        raise InputError("unit records must match this exact native table")
    output = np.empty((len(windows), len(units)), dtype=np.int64)
    dataset = _dataset(f, "units/spike_times", MAX_SPIKES_TOTAL)
    for j, unit in enumerate(units):
        lo, hi = unit["spike_start"], unit["spike_stop"]
        if hi - lo > MAX_SPIKES_UNIT:
            raise UnsupportedSchema("complete unit spike slice exceeds source cap")
        spikes = dataset[lo:hi]  # one unit only; never dataset[:]
        if not np.isfinite(spikes).all() or np.any(spikes < 0) or np.any(spikes[1:] < spikes[:-1]):
            raise UnsupportedSchema("unit spike seconds must be finite sorted nonnegative")
        output[:, j] = np.searchsorted(spikes, windows[:, 1], side="left") - np.searchsorted(spikes, windows[:, 0], side="left")
    return output


def _unit_attr(dataset, expected):
    value = dataset.attrs.get("unit")
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if value != expected or float(dataset.attrs.get("conversion", 1.)) != 1. or float(dataset.attrs.get("offset", 0.)) != 0.:
        raise UnsupportedSchema("unreviewed source units/conversion")


def _pupil_covariates(f, windows):
    root = "processing/filtered_gaze_mapping"
    if root not in f:
        return [None] * len(windows), {"pupil": "missing_filtered_gaze_mapping", "no_pupil_values_inferred": True}
    data_path, time_path = root + "/pupil_area/data", root + "/pupil_area/timestamps"
    data = _dataset(f, data_path, MAX_RUNNING)
    times_dataset = _dataset(f, time_path, MAX_RUNNING)
    if data.dtype.kind != "f" or data.dtype.itemsize != 8 or times_dataset.dtype.kind != "f" or times_dataset.dtype.itemsize != 8:
        raise UnsupportedSchema("unreviewed pupil dtype")
    _unit_attr(data, "Pixels ^ 2")
    _unit_attr(times_dataset, "seconds")
    times = _vector(f, time_path, MAX_RUNNING, kind="f")
    if len(data) != len(times) or not np.isfinite(times).all() or np.any(times[1:] <= times[:-1]):
        raise UnsupportedSchema("pupil times must be finite strictly ordered and aligned")
    values, support = [], []
    for a, b in windows:
        left = int(np.searchsorted(times, a, side="left"))
        right = int(np.searchsorted(times, b, side="left"))
        lower = int(np.searchsorted(times, a, side="right")) - 1
        reason, maximum_gap, value = None, None, None
        if lower < 0 or right >= len(times):
            reason = "missing_bracketing_timestamp"
        elif left == right:
            reason = "no_inside_samples"
        else:
            gaps = np.diff(times[lower:right + 1])
            maximum_gap = float(np.max(gaps)) if len(gaps) else 0.
            if maximum_gap > .05:
                reason = "sampling_gap_over_0.05_seconds"
            else:
                # Neither the lower outside sample nor the upper/future
                # bracket value is read. Only [start,stop) values contribute.
                samples = data[left:right]
                if not np.isfinite(samples).all() or np.any(samples <= 0):
                    reason = "nonfinite_or_nonpositive_inside_sample"
                else:
                    value = float(sum((Fraction.from_float(float(x)) for x in samples), Fraction()) / len(samples))
        values.append(value)
        support.append({"status": "complete" if reason is None else reason,
                        "inside_samples": right - left, "maximum_bracketing_gap_seconds": maximum_gap})
    return values, {"pupil": "native_filtered_pupil_area_sample_mean_pixels_squared",
                    "pupil_windows": support, "maximum_gap_seconds": .05,
                    "endpoint_policy": "timestamps bracket both endpoints; values only [start,stop)",
                    "publisher_filter_causality": "not established; filtered source may be noncausal",
                    "no_pupil_values_inferred": True}


def state_covariates(f, windows_pre):
    windows = _windows(windows_pre)
    pupil, pupil_support = _pupil_covariates(f, windows)
    root = "processing/running/"
    paths = [root + "running_speed/timestamps", root + "running_speed_end_times/timestamps", root + "running_speed/data"]
    if any(path not in f for path in paths):
        return {"running": [None] * len(windows), "pupil": pupil,
                "support": {"running": "missing", **pupil_support}}
    for path, unit in zip(paths, ("seconds", "seconds", "cm/s")):
        _unit_attr(f[path], unit)
    start, stop, speed = [_vector(f, p, MAX_RUNNING, kind="f") for p in paths]
    start, stop = _validate_times(start, stop)
    if len(speed) != len(start) or np.any(start[1:] < stop[:-1]):
        raise UnsupportedSchema("overlapping/unaligned native running intervals")
    running, coverage = [], []
    for a, b in windows:
        left, right = np.searchsorted(stop, a, side="right"), np.searchsorted(start, b, side="left")
        covered, weighted = Fraction(), Fraction()
        nonfinite = 0
        for i in range(left, right):
            lo, hi = max(float(a), float(start[i])), min(float(b), float(stop[i]))
            if hi <= lo:
                continue
            if not math.isfinite(float(speed[i])):
                nonfinite += 1
                continue
            duration = Fraction.from_float(hi) - Fraction.from_float(lo)
            covered += duration
            weighted += duration * Fraction.from_float(abs(float(speed[i])))
        expected = Fraction.from_float(float(b)) - Fraction.from_float(float(a))
        complete = covered == expected
        running.append(float(weighted / expected) if complete else None)
        coverage.append({"status": "complete" if complete else "missing_coverage", "covered_fraction": float(covered / expected),
                         "nonfinite_speed_samples": nonfinite})
    return {"running": running, "pupil": pupil,
            "support": {"running": "native_interval_weighted_absolute_cm_s", "running_windows": coverage,
                        **pupil_support}}
