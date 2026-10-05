"""Original-NWB cross-check with endpoint histograms and scalar OSI arithmetic.

This authoring diagnostic imports neither solution nor verifier. It shares h5py,
NumPy, the frozen source and the declared estimand, not their counting or summary
implementations. It is not independent acquisition, spike sorting, biological
validation, or an unbiased orientation-selectivity prevalence estimate.

Run only under the reviewed scientific/resource contract. Import is I/O-free.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import platform

import h5py
import numpy as np


PIPELINE_ID = "allen-visp-two-point-osi-v2"
MANIFEST_SHA256 = "0997a4b254812d6967c87444809039197a4864d98838c4f6432d05cdfccd6534"
SOURCE_SHA256 = "4e284295a1be5c6cca49df84fab52ad38b4749d2361b2edebeb676051cf09921"
SOURCE_NAME = "sub-707296975_ses-721123822.nwb"
SOURCE_SIZE = 1736516600
ASSET_ID = "224b57e5-c9a3-46ef-85db-966713f3ccbe"
DIRECTIONS = tuple(range(0, 360, 45))
QC_NAMES = ("isi_violations", "amplitude_cutoff", "presence_ratio")
QC_RESULT_NAMES = ("n_qc_responsive_units", "n_qc_responsive_orientation_selective",
                   "qc_responsive_selective_fraction")
ATOL, RTOL, TIME_ATOL = 1e-6, 1e-6, 1e-9


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def authenticate(data_dir):
    data_dir = Path(data_dir)
    manifest_path = data_dir / "data_manifest.json"
    require(not manifest_path.is_symlink(), "manifest is a symlink")
    require(digest(manifest_path) == MANIFEST_SHA256, "frozen manifest SHA256 mismatch")
    manifest = json.loads(manifest_path.read_text())
    require((manifest["dandiset_id"], manifest["dandiset_version"]) ==
            ("000021", "0.251116.2246"), "wrong published DANDI release")
    require(len(manifest["files"]) == 1, "expected exactly one original NWB")
    entry = manifest["files"][0]
    require((entry["path"], entry["asset_id"], entry["role"], entry["sha256"], entry["size_bytes"]) ==
            (SOURCE_NAME, ASSET_ID, "session_nwb", SOURCE_SHA256, SOURCE_SIZE), "source identity changed")
    path = data_dir / SOURCE_NAME
    require(not path.is_symlink() and path.is_file(), "original source must be a regular nonsymlink file")
    require(path.stat().st_size == SOURCE_SIZE, "source size mismatch")
    require(digest(path) == SOURCE_SHA256, "original NWB SHA256 mismatch")
    return path, manifest


def text(value):
    return value.decode("utf8") if isinstance(value, bytes) else str(value)


def exact_int(value):
    require(not isinstance(value, (bool, np.bool_)), "boolean is not an integer ID/count")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid integer ID/count") from exc
    require(parsed.is_finite() and parsed == parsed.to_integral_value(), "noninteger ID/count")
    require(0 <= parsed <= np.iinfo(np.int64).max, "ID/count outside nonnegative int64")
    return int(parsed)


def integer_column(values, unique=False):
    values = np.asarray(values)
    require(values.ndim == 1, "expected a one-dimensional source identity column")
    result = np.asarray([exact_int(value) for value in values], dtype=np.int64)
    if unique:
        require(len(set(result.tolist())) == len(result), "duplicate original source IDs")
    return result


def source_float(value):
    if value is None or isinstance(value, (str, bytes)) and text(value).strip().lower() in {"", "nan", "none", "null"}:
        return math.nan
    require(not isinstance(value, (bool, np.bool_)), "boolean source condition")
    number = float(value)
    require(not math.isinf(number), "infinite source condition")
    return number


def select_presentations(columns):
    ids = integer_column(columns["id"], unique=True)
    starts = np.asarray(columns["start_time"], dtype=float)
    stops = np.asarray(columns["stop_time"], dtype=float)
    direction = np.array([source_float(value) for value in columns["orientation"]])
    frequency = np.array([source_float(value) for value in columns["temporal_frequency"]])
    require(all(column.shape == ids.shape for column in (starts, stops, direction, frequency)),
            "inconsistent original presentation columns")
    require(np.isfinite(starts).all() and np.isfinite(stops).all() and np.all(stops > starts),
            "invalid original presentation intervals")
    require(np.all(starts[1:] >= starts[:-1]), "presentations not chronological; no silent sorting")
    retained = [row for row, value in enumerate(direction) if math.isfinite(value)]
    require(len(retained) > 0, "no nonblank source presentations")
    require(set(direction[retained]) == set(DIRECTIONS), "unexpected source direction grid")
    require(all(math.isfinite(frequency[row]) and frequency[row] > 0 for row in retained),
            "missing/nonpositive frequency on a nonblank presentation")
    levels = sorted(set(frequency[retained].tolist()))
    support = np.zeros((8, len(levels)), dtype=np.int64)
    for di, angle in enumerate(DIRECTIONS):
        for ti, level in enumerate(levels):
            support[di, ti] = sum(direction[row] == angle and frequency[row] == level for row in retained)
    require(np.all(support > 0), "missing source condition; do not impute a zero response")
    return {"presentation_id": ids[retained], "start_time": starts[retained], "stop_time": stops[retained],
            "duration_seconds": stops[retained] - starts[retained], "direction": direction[retained],
            "temporal_frequency": frequency[retained], "temporal_frequencies": np.asarray(levels),
            "directions": np.asarray(DIRECTIONS, dtype=float), "selected_source_rows": np.asarray(retained),
            "condition_n_presentations": support, "n_original_presentations": len(ids),
            "n_blank_presentations": len(ids) - len(retained)}


def histogram_windows(spikes, starts, stops):
    """Half-open counts without searching a sorted spike train at each endpoint.

    NumPy's last histogram bin includes its right edge. Appending +inf puts the
    last *finite* stop in a following bin, keeping every requested stop exclusive.
    An ordinary histogram ending at max(stops) is wrong for a spike at that stop.
    """
    spikes, starts, stops = [np.asarray(value, dtype=float) for value in (spikes, starts, stops)]
    require(spikes.ndim == starts.ndim == stops.ndim == 1, "expected vector spikes/windows")
    require(len(starts) == len(stops) and len(starts) > 0, "empty or mismatched windows")
    require(np.isfinite(spikes).all() and np.all(spikes[1:] >= spikes[:-1]),
            "nonfinite or unordered spikes; never sort or deduplicate")
    require(np.isfinite(starts).all() and np.isfinite(stops).all() and np.all(stops > starts),
            "nonfinite or nonpositive windows")
    endpoints = sorted(set(starts.tolist() + stops.tolist()))
    index = {value: row for row, value in enumerate(endpoints)}
    bins = np.asarray(endpoints + [math.inf])
    counts, _ = np.histogram(spikes, bins=bins)
    prefix = np.concatenate(([0], np.cumsum(counts, dtype=np.int64)))
    return np.asarray([prefix[index[float(stop)]] - prefix[index[float(start)]]
                       for start, stop in zip(starts, stops)], dtype=np.int64)


def overlap_counts(starts, stops, invalid_starts, invalid_stops):
    return [sum(float(start) < b and float(stop) > a for start, stop in zip(starts, stops))
            for a, b in zip(invalid_starts, invalid_stops)]


def read_original(path, include_qc):
    """Independent HDF5 joins and streaming per-unit ragged reads/counts."""
    with h5py.File(path, "r") as nwb:
        units = nwb["units"]
        electrodes = nwb["general/extracellular_ephys/electrodes"]
        all_ids = integer_column(units["id"][:], unique=True)
        peak = integer_column(units["peak_channel_id"][:])
        eids = integer_column(electrodes["id"][:], unique=True)
        location = [text(value) for value in electrodes["location"][:]]
        require(len(all_ids) == len(peak) and len(eids) == len(location), "source join column mismatch")
        lookup = dict(zip(eids.tolist(), location))
        require(all(value in lookup for value in peak), "unresolved peak-channel electrode ID")
        regions = np.array([lookup[value] for value in peak])
        rows = [row for row, value in enumerate(regions) if value == "VISp"]
        require(rows, "no source VISp units")
        table = nwb["intervals/drifting_gratings_presentations"]
        presentations = select_presentations({key: table[key][:] for key in
                                             ("id", "start_time", "stop_time", "orientation", "temporal_frequency")})
        starts, stops = presentations["start_time"], presentations["stop_time"]
        if include_qc:
            require(np.all(starts >= .5), "baseline extends before recording time zero")
        invalid_a, invalid_b = [], []
        for invalid_path in ("invalid_times", "intervals/invalid_times"):
            if invalid_path in nwb:
                bad = nwb[invalid_path]
                invalid_a.extend(np.asarray(bad["start_time"][:], float).tolist())
                invalid_b.extend(np.asarray(bad["stop_time"][:], float).tolist())
        require(len(invalid_a) == len(invalid_b) and all(math.isfinite(a) and math.isfinite(b) and b > a
                                                       for a, b in zip(invalid_a, invalid_b)), "invalid invalid-time table")
        invalid_overlap = overlap_counts(starts, stops, invalid_a, invalid_b)
        baseline_overlap = overlap_counts(starts - .5, starts, invalid_a, invalid_b)
        require(not any(invalid_overlap), "source-invalid interval overlaps a selected presentation")
        if include_qc:
            require(not any(baseline_overlap), "source-invalid interval overlaps a selected baseline")
        source_qc = {}
        for name in QC_NAMES:
            values = np.asarray(units[name][:], float) if name in units else np.full(len(all_ids), np.nan)
            require(values.shape == all_ids.shape, "invalid source QC column shape")
            source_qc[name] = values[rows]
        ends = integer_column(units["spike_times_index"][:])
        spikes = units["spike_times"]
        require(ends.shape == all_ids.shape and len(ends) > 0 and np.all(ends[1:] >= ends[:-1])
                and ends[-1] == len(spikes), "invalid ragged spike endpoints")
        n, p = len(rows), len(starts)
        counts, baseline = np.empty((n, p), dtype=np.int64), np.empty((n, p), dtype=np.int64)
        row_to_selected = {row: index for index, row in enumerate(rows)}
        combined_starts = np.concatenate((starts, starts - .5)) if include_qc else starts
        combined_stops = np.concatenate((stops, starts)) if include_qc else stops
        all_spike_hash = hashlib.sha256()
        previous, duplicate_count, duplicate_units = 0, 0, 0
        for row, end in enumerate(ends):
            train = np.asarray(spikes[previous:int(end)], dtype=np.float64)
            require(np.isfinite(train).all() and np.all(train[1:] >= train[:-1]),
                    f"invalid original spike order/availability in unit {all_ids[row]}")
            repeated = int(np.count_nonzero(train[1:] == train[:-1]))
            duplicate_count += repeated
            duplicate_units += int(repeated > 0)
            all_spike_hash.update(train.astype("<f8", copy=False).tobytes())
            if row in row_to_selected:
                values = histogram_windows(train, combined_starts, combined_stops)
                selected = row_to_selected[row]
                counts[selected] = values[:p]
                if include_qc:
                    baseline[selected] = values[p:]
            previous = int(end)
        arrays = {**presentations, "unit_id": all_ids[rows], "peak_channel_id": peak[rows],
                  "unit_ids_all": all_ids, "unit_regions_all": regions, "visp_source_rows": np.asarray(rows),
                  "spike_count": counts, **{"source_" + key: value for key, value in source_qc.items()}}
        if include_qc:
            arrays["baseline_spike_count"] = baseline
        arrays["spike_times_sha256_le_float64"] = np.asarray(all_spike_hash.hexdigest())
        report = {"n_units_total": len(all_ids), "n_visp_units_total": n,
                  "n_original_presentations": presentations["n_original_presentations"],
                  "n_blank_presentations": presentations["n_blank_presentations"], "n_gratings_presentations": p,
                  "visp_unit_ids": all_ids[rows].tolist(), "selected_presentation_ids": presentations["presentation_id"].tolist(),
                  "condition_n_presentations": presentations["condition_n_presentations"].tolist(),
                  "n_original_spikes": int(ends[-1]), "n_duplicate_timestamps": duplicate_count,
                  "n_units_with_duplicate_timestamps": duplicate_units,
                  "invalid_interval_presentation_overlap_counts": invalid_overlap,
                  "invalid_interval_baseline_overlap_counts": baseline_overlap,
                  "qc_fields_available": [key for key in QC_NAMES if key in units],
                  "qc_nonfinite_counts": {key: int(np.count_nonzero(~np.isfinite(value))) for key, value in source_qc.items()},
                  "time_descriptions": {"spike_times": text(spikes.attrs.get("description", "")),
                                        **{key: text(table[key].attrs.get("description", "")) for key in ("start_time", "stop_time")}},
                  "selected_contrasts": sorted(set(source_float(value) for value in table["contrast"][:][presentations["selected_source_rows"]]))
                  if "contrast" in table else None,
                  "spike_times_sha256_le_float64": all_spike_hash.hexdigest()}
    return arrays, report


def derive_independent(arrays, include_qc):
    """Separate scalar loops, math.fsum means and explicit ordered preferences."""
    output = dict(arrays)
    counts = arrays["spike_count"]
    require(counts.dtype.kind in "iu" and counts.ndim == 2 and np.all(counts >= 0), "invalid integer response matrix")
    n, p = counts.shape
    duration = arrays["duration_seconds"]
    require(duration.shape == (p,) and np.isfinite(duration).all() and np.all(duration > 0), "invalid durations")
    levels = arrays["temporal_frequencies"]
    cells = {(di, ti): [j for j in range(p) if arrays["direction"][j] == angle and arrays["temporal_frequency"][j] == level]
             for di, angle in enumerate(DIRECTIONS) for ti, level in enumerate(levels)}
    require(all(cells.values()), "missing condition; cannot replace missing data with zero")
    rates = np.empty(counts.shape, float)
    means = np.empty((n, 8, len(levels)), float)
    folded = np.empty((n, 4), float)
    unit_keys = ("preferred_temporal_frequency", "preferred_orientation", "r_pref_hz", "r_orth_hz", "peak_rate_hz", "osi")
    output.update({key: np.empty(n, float) for key in unit_keys})
    output.update(osi_defined=np.zeros(n, bool), selective=np.zeros(n, bool))
    for i in range(n):
        for j in range(p):
            rates[i, j] = int(counts[i, j]) / float(duration[j])
        for (di, ti), members in cells.items():
            means[i, di, ti] = math.fsum(float(rates[i, j]) for j in members) / len(members)
        peaks = [max(float(means[i, di, ti]) for di in range(8)) for ti in range(len(levels))]
        best_ti = max(range(len(levels)), key=lambda ti: (peaks[ti], -float(levels[ti])))
        for oi in range(4):
            folded[i, oi] = (float(means[i, oi, best_ti]) + float(means[i, oi + 4, best_ti])) / 2
        best_oi = max(range(4), key=lambda oi: (float(folded[i, oi]), -oi))
        pref, orth = float(folded[i, best_oi]), float(folded[i, (best_oi + 2) % 4])
        osi = (pref - orth) / (pref + orth) if pref + orth > 0 else 0.
        for key, value in zip(unit_keys, (levels[best_ti], best_oi * 45, pref, orth, max(peaks), osi)):
            output[key][i] = value
        output["osi_defined"][i] = pref + orth > 0
        output["selective"][i] = pref + orth > 0 and osi > .5
    output.update(rate_hz=rates, mean_rate_hz=means, folded_rate_hz=folded)
    require(n > 0, "no VISp denominator")
    numerator = sum(bool(value) for value in output["selective"])
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, "orientation_selective_fraction": numerator / n,
              "n_visp_units_total": n, "n_visp_units_analyzed": n, "n_orientation_selective": numerator,
              "n_osi_undefined": sum(not bool(value) for value in output["osi_defined"]), "osi_threshold": .5}
    if include_qc:
        baseline = arrays["baseline_spike_count"]
        require(baseline.shape == counts.shape and baseline.dtype.kind in "iu" and np.all(baseline >= 0), "invalid baseline count matrix")
        output.update({key: arrays["source_" + key] for key in QC_NAMES})
        output.update({key: np.zeros(n, bool) for key in ("qc_metrics_complete", "qc_pass", "responsive", "in_qc_responsive")})
        output["baseline_rate_hz"] = np.empty(n, float)
        for i in range(n):
            isi, amplitude, presence = [float(output[key][i]) for key in QC_NAMES]
            complete = all(math.isfinite(value) for value in (isi, amplitude, presence))
            passed = complete and isi < .5 and amplitude < .1 and presence > .9
            baseline_rate = math.fsum(int(value) / .5 for value in baseline[i]) / p
            responsive = output["peak_rate_hz"][i] > 2 and output["peak_rate_hz"][i] > baseline_rate + 1
            output["baseline_rate_hz"][i] = baseline_rate
            for key, value in zip(("qc_metrics_complete", "qc_pass", "responsive", "in_qc_responsive"),
                                  (complete, passed, responsive, passed and responsive)):
                output[key][i] = value
        denominator = sum(bool(value) for value in output["in_qc_responsive"])
        numerator = sum(bool(selected and selective) for selected, selective in zip(output["in_qc_responsive"], output["selective"]))
        result.update(n_qc_responsive_units=denominator, n_qc_responsive_orientation_selective=numerator,
                      qc_responsive_selective_fraction=numerator / denominator if denominator else None)
    return output, result


def csv_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames), "missing/duplicate CSV header")
        for row in reader:
            require(None not in row and all(value is not None for value in row.values()), "malformed CSV row")
            if any(value.strip() for value in row.values()):
                yield row


def compare_value(actual, expected, kind):
    if kind == "integer":
        return exact_int(actual) == int(expected), 0.
    if kind == "boolean":
        require(str(actual).strip().lower() in {"true", "false", "0", "1"}, "invalid Boolean receipt")
        return (str(actual).strip().lower() in {"true", "1"}) == bool(expected), 0.
    if kind == "optional" and not math.isfinite(float(expected)):
        return isinstance(actual, str) and not actual.strip(), 0.
    value = float(actual)
    require(math.isfinite(value), "nonfinite public numeric receipt")
    difference = abs(value - float(expected))
    tolerance = TIME_ATOL if kind == "time" else 0 if kind == "category" else ATOL + RTOL * abs(float(expected))
    return difference <= tolerance, difference


def compare_table(path, expected_rows, key_kinds, value_kinds):
    """Source-keyed membership and values, independent of output row order."""
    expected = {tuple(row[key] for key in key_kinds): row for row in expected_rows}
    seen, errors, maximum = set(), [], 0.
    for row in csv_rows(path):
        require(set(key_kinds) | set(value_kinds) <= set(row), f"missing columns: {path.name}")
        key = tuple(exact_int(row[field]) if kind == "integer" else float(row[field]) for field, kind in key_kinds.items())
        require(key in expected and key not in seen, f"unknown/duplicate source key in {path.name}: {key}")
        seen.add(key)
        for field, kind in value_kinds.items():
            okay, difference = compare_value(row[field], expected[key][field], kind)
            maximum = max(maximum, difference)
            if not okay and len(errors) < 20:
                errors.append({"key": list(key), "field": field, "actual": row[field], "expected": str(expected[key][field])})
    require(seen == set(expected), f"incomplete source product in {path.name}: {len(seen)}/{len(expected)}")
    return {"rows": len(seen), "max_abs_numeric_difference": maximum, "errors": errors, "passed": not errors}


def optional_qc_requested(output, result, metadata):
    files = [output / name for name in ("baseline_counts.csv", "qc_sensitivity.csv")]
    requested = any(path.exists() for path in files) or any(key in result for key in QC_RESULT_NAMES) or metadata.get("include_qc") is True
    require(type(metadata.get("include_qc")) is bool and metadata["include_qc"] == requested, "optional QC metadata mismatch")
    if requested:
        require(all(path.is_file() for path in files) and all(key in result for key in QC_RESULT_NAMES), "incomplete optional QC bundle")
    return requested


def compare_public(output, arrays, result, source_report, include_qc):
    uid, pid = arrays["unit_id"], arrays["presentation_id"]
    tables = {}
    tables["presentations.csv"] = compare_table(output / "presentations.csv",
        ({key: arrays[key][j] for key in ("presentation_id", "start_time", "stop_time", "duration_seconds", "direction", "temporal_frequency")} for j in range(len(pid))),
        {"presentation_id": "integer"}, {"start_time": "time", "stop_time": "time", "duration_seconds": "time", "direction": "category", "temporal_frequency": "category"})
    tables["trial_responses.csv"] = compare_table(output / "trial_responses.csv",
        (dict(unit_id=int(unit), presentation_id=int(pres), spike_count=arrays["spike_count"][i, j], rate_hz=arrays["rate_hz"][i, j])
         for i, unit in enumerate(uid) for j, pres in enumerate(pid)), {"unit_id": "integer", "presentation_id": "integer"},
        {"spike_count": "integer", "rate_hz": "float"})
    tables["condition_means.csv"] = compare_table(output / "condition_means.csv",
        (dict(unit_id=int(unit), direction=float(angle), temporal_frequency=float(tf), n_presentations=arrays["condition_n_presentations"][di, ti], mean_rate_hz=arrays["mean_rate_hz"][i, di, ti])
         for i, unit in enumerate(uid) for di, angle in enumerate(DIRECTIONS) for ti, tf in enumerate(arrays["temporal_frequencies"])),
        {"unit_id": "integer", "direction": "category", "temporal_frequency": "category"}, {"n_presentations": "integer", "mean_rate_hz": "float"})
    unit_fields = {"peak_channel_id": "integer", "preferred_temporal_frequency": "category", "preferred_orientation": "category",
                   "r_pref_hz": "float", "r_orth_hz": "float", "peak_rate_hz": "float", "osi": "float", "osi_defined": "boolean", "selective": "boolean"}
    tables["units.csv"] = compare_table(output / "units.csv",
        (dict(unit_id=int(unit), **{field: arrays[field][i] for field in unit_fields}) for i, unit in enumerate(uid)), {"unit_id": "integer"}, unit_fields)
    if include_qc:
        tables["baseline_counts.csv"] = compare_table(output / "baseline_counts.csv",
            (dict(unit_id=int(unit), presentation_id=int(pres), spike_count=arrays["baseline_spike_count"][i, j]) for i, unit in enumerate(uid) for j, pres in enumerate(pid)),
            {"unit_id": "integer", "presentation_id": "integer"}, {"spike_count": "integer"})
        fields = {**{field: "optional" for field in QC_NAMES}, "baseline_rate_hz": "float",
                  **{field: "boolean" for field in ("qc_metrics_complete", "qc_pass", "responsive", "in_qc_responsive")}}
        tables["qc_sensitivity.csv"] = compare_table(output / "qc_sensitivity.csv",
            (dict(unit_id=int(unit), **{field: arrays[field][i] for field in fields}) for i, unit in enumerate(uid)), {"unit_id": "integer"}, fields)
    actual_result = json.loads((output / "results.json").read_text())
    for key, expected in result.items():
        require(key in actual_result, f"missing result {key}")
        actual = actual_result[key]
        if expected is None or isinstance(expected, str):
            require(actual == expected, f"result {key} differs")
        else:
            require(compare_value(actual, expected, "integer" if isinstance(expected, int) else "float")[0], f"result {key} differs")
    metadata = json.loads((output / "run_metadata.json").read_text())
    expected_metadata = {"status": "ok", "pipeline_id": PIPELINE_ID, "dandiset_id": "000021", "dandiset_version": "0.251116.2246",
                         "asset_id": ASSET_ID, "asset_path": "sub-707296975/" + SOURCE_NAME,
                         "subject_id": "707296975", "session_id": "721123822", "region": "VISp", "include_qc": include_qc,
                         "source_sha256": {SOURCE_NAME: SOURCE_SHA256}, "directions": list(DIRECTIONS),
                         "temporal_frequencies": arrays["temporal_frequencies"].tolist(),
                         **{key: source_report[key] for key in ("n_units_total", "n_visp_units_total", "n_original_presentations", "n_blank_presentations", "n_gratings_presentations")}}
    for key, expected in expected_metadata.items():
        require(metadata.get(key) == expected, f"source-bound metadata {key} differs")
    require((output / "findings.md").read_text().strip(), "missing findings text")
    return tables


def compare_private(output, arrays):
    comparisons = {}
    with np.load(output / "analysis_arrays.npz", allow_pickle=False) as receipt:
        for key, expected in arrays.items():
            if key == "folded_rate_hz":  # Extra independent diagnostic, not an oracle schema requirement.
                continue
            require(key in receipt, f"missing private receipt key {key}")
            actual, expected = receipt[key], np.asarray(expected)
            require(actual.shape == expected.shape, f"private shape mismatch for {key}")
            exact = (expected.dtype.kind in "iubUS" or key in ("direction", "temporal_frequency", "temporal_frequencies",
                     "directions", "preferred_temporal_frequency", "preferred_orientation"))
            if exact:
                equal = np.equal(actual, expected)
                difference = 0.
            else:
                equal = np.isclose(actual, expected, atol=TIME_ATOL if key in ("start_time", "stop_time", "duration_seconds") else ATOL,
                                   rtol=0 if key in ("start_time", "stop_time", "duration_seconds") else RTOL, equal_nan=True)
                finite = np.isfinite(actual) & np.isfinite(expected)
                difference = float(np.max(np.abs(actual[finite] - expected[finite]), initial=0))
            comparisons[key] = {"shape": list(expected.shape), "n_disagreements": int(np.count_nonzero(~equal)),
                                "max_abs_difference": difference, "passed": bool(np.all(equal))}
        require(json.loads(str(receipt["metadata_json"].item())) == json.loads((output / "run_metadata.json").read_text()), "private/public metadata disagree")
        require(json.loads(str(receipt["result_json"].item())) == json.loads((output / "results.json").read_text()), "private/public results disagree")
    return comparisons


def require_fresh_evidence_paths(report_path):
    report_path = Path(report_path)
    counts_path = report_path.with_suffix(".counts.npz")
    for path in (report_path, counts_path):
        require(not path.exists() and not path.is_symlink(), f"refusing to overwrite existing evidence: {path}")
    return counts_path


def check(data_dir, output, report_path):
    output, report_path = Path(output), Path(report_path)
    counts_path = require_fresh_evidence_paths(report_path)
    source, _ = authenticate(data_dir)
    metadata = json.loads((output / "run_metadata.json").read_text())
    result = json.loads((output / "results.json").read_text())
    include_qc = optional_qc_requested(output, result, metadata)
    source_arrays, source_report = read_original(source, include_qc)
    arrays, independent_result = derive_independent(source_arrays, include_qc)
    tables = compare_public(output, arrays, independent_result, source_report, include_qc)
    private = compare_private(output, arrays)
    passed = all(value["passed"] for value in tables.values()) and all(value["passed"] for value in private.values())
    # Exclusive creation also protects against an output appearing during analysis.
    with counts_path.open("xb") as stream:
        np.savez_compressed(stream, **arrays, pipeline_id=PIPELINE_ID, source_sha256_json=json.dumps({SOURCE_NAME: SOURCE_SHA256}),
                            results_json=json.dumps(independent_result, allow_nan=False))
    return {"status": "passed" if passed else "failed", "pipeline_id": PIPELINE_ID,
            "source_sha256": {SOURCE_NAME: SOURCE_SHA256}, "source_manifest_sha256": MANIFEST_SHA256,
            "scope": "all original VISp units x all original nonblank drifting-grating presentations",
            "independent_components": ["HDF5 electrode-ID join and original ragged-unit reads", "original nonblank presentation membership and condition support",
                                       "histogram on unique trial/baseline endpoints plus infinity sentinel, no searchsorted spike counts",
                                       "scalar per-trial rates and math.fsum equal-presentation condition means", "explicit TF/orientation exact ties and folded two-point OSI",
                                       "optional original-metric QC, preceding-window counts and all denominator arithmetic"],
            "shared_components": ["same original source acquisition and upstream spike sorting", "same public estimator contract", "h5py HDF5 reader", "NumPy numeric library"],
            "limits": ["Numerical/source implementation agreement is not independent biological evidence.",
                       "Preference and responsiveness use the same trials; no unbiased prevalence or noise-causality claim.",
                       "Optional preceding-window baseline is not presumed spontaneous activity."],
            "versions": {"python": platform.python_version(), "numpy": np.__version__, "h5py": h5py.__version__},
            "tolerances": {"atol": ATOL, "rtol": RTOL, "time_atol_seconds": TIME_ATOL, "IDs_counts_flags_categories": "exact"},
            "source": source_report, "include_qc": include_qc, "independent_results": independent_result,
            "tables": tables, "private_arrays": private, "independent_counts_artifact": str(counts_path),
            "independent_counts_sha256": digest(counts_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="/app/data/allenosi")
    parser.add_argument("--oracle-output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    destination = Path(args.report)
    try:
        require_fresh_evidence_paths(destination)
    except ValueError as error:
        print(json.dumps({"status": "failed", "error": str(error)}))
        return 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = check(args.data_dir, args.oracle_output, destination)
    except Exception as error:
        report = {"status": "failed", "pipeline_id": PIPELINE_ID, "error_type": type(error).__name__, "error": str(error)}
    with destination.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "report": str(destination)}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
