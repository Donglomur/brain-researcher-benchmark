"""Offline descriptive two-point OSI, not AllenSDK gOSI or neuron prevalence.

Importing performs no I/O. --inspect-source only inspects source structure and
spike ordering; it never calls response counting or OSI functions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

PIPELINE_ID = "allen-visp-two-point-osi-v2"
DANDISET = "000021"
VERSION = "0.251116.2246"
ASSET_ID = "224b57e5-c9a3-46ef-85db-966713f3ccbe"
ASSET = "sub-707296975/sub-707296975_ses-721123822.nwb"
SOURCE_SHA256 = "4e284295a1be5c6cca49df84fab52ad38b4749d2361b2edebeb676051cf09921"
MANIFEST_SHA256 = "0997a4b254812d6967c87444809039197a4864d98838c4f6432d05cdfccd6534"
DIRECTIONS = np.arange(0, 360, 45, dtype=float)
ORIENTATIONS = np.arange(0, 180, 45, dtype=float)
STIMULUS_PATH = "intervals/drifting_gratings_presentations"
ELECTRODE_PATH = "general/extracellular_ephys/electrodes"
QC_FIELDS = ("isi_violations", "amplitude_cutoff", "presence_ratio")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def decoded(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def integral_array(value, name):
    array = np.asarray(value)
    if array.ndim != 1 or array.dtype.kind not in "iuf":
        raise ValueError(f"{name}: expected one-dimensional numeric IDs/indices")
    if not np.all(np.isfinite(array)) or np.any(array < 0):
        raise ValueError(f"{name}: nonfinite or negative IDs/indices")
    cast = array.astype(np.int64)
    if not np.array_equal(array, cast):
        raise ValueError(f"{name}: IDs/indices must be integral and fit int64")
    return cast


def unique_ids(value, name):
    array = integral_array(value, name)
    if len(np.unique(array)) != len(array):
        raise ValueError(f"{name}: duplicate source IDs")
    return array


def load_inputs(data):
    """Authenticate the staged immutable source, without NWB analysis/network."""
    data = Path(data)
    path = data / "data_manifest.json"
    if sha256_file(path) != MANIFEST_SHA256:
        raise ValueError("data_manifest.json differs from the frozen manifest")
    manifest = json.loads(path.read_text())
    if (manifest["dandiset_id"], manifest["dandiset_version"]) != (DANDISET, VERSION):
        raise ValueError("wrong immutable DANDI release")
    if len(manifest["files"]) != 1:
        raise ValueError("expected exactly one NWB source")
    entry = manifest["files"][0]
    if (entry["role"], entry["asset_id"], entry["source_path"], entry["sha256"]) != (
        "session_nwb", ASSET_ID, ASSET, SOURCE_SHA256
    ):
        raise ValueError("unexpected source identity")
    path = data / entry["path"]
    if path.resolve().parent != data.resolve():
        raise ValueError("source must be a basename inside the data directory")
    if path.stat().st_size != entry["size_bytes"] or sha256_file(path) != SOURCE_SHA256:
        raise ValueError("NWB source size/checksum mismatch")
    return {"path": path, "manifest": manifest,
            "source_sha256": {entry["path"]: entry["sha256"]}}


def metadata_contract(inputs):
    """Pure fit/count-free public contract from authenticated manifest values."""
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": "allen-visual-coding-neuropixels",
        "dandiset_id": DANDISET, "dandiset_version": VERSION,
        "asset_path": ASSET, "asset_id": ASSET_ID,
        "subject_id": "707296975", "session_id": "721123822",
        "source_sha256": dict(inputs["source_sha256"]), "region": "VISp",
        "source_manifest_sha256": MANIFEST_SHA256,
        "unit_selection": {"mapping": "units.peak_channel_id to electrodes.id then location",
                           "primary": "all source VISp clusters; no QC or response filter",
                           "ordering": "original source row order; IDs never renumbered"},
        "presentations": {"table": STIMULUS_PATH,
                          "blank_rule": "missing orientation; temporal_frequency may also be missing",
                          "missing_tokens": ["", "null", "none", "nan"],
                          "directions_degrees": DIRECTIONS.tolist(),
                          "contrast": 0.8,
                          "temporal_frequency": "all finite positive source levels, ascending",
                          "support": "every direction x temporal-frequency cell nonempty",
                          "duration": "original stop_time minus start_time; finite and positive"},
        "invalid_intervals": {"table": "intervals/invalid_times",
                              "policy": "fail if any source invalid interval overlaps a selected stimulus window; also baseline windows if QC requested; do not drop units or presentations"},
        "responses": {"interval": "[start_time, stop_time)",
                      "rate": "integer count divided by actual presentation duration",
                      "condition_mean": "unweighted mean of per-presentation rates",
                      "duplicate_spike_timestamps": "retained; no sorting or deduplication"},
        "osi": {"preferred_tf": "largest single-direction condition mean across each TF",
                "tf_tie": "exact equality; lowest temporal frequency",
                "folding": "equal mean of opposite-direction condition means",
                "orientations_degrees": ORIENTATIONS.tolist(),
                "orientation_tie": "exact equality; lowest orientation",
                "orthogonal": "(preferred_orientation + 90) modulo 180",
                "formula": "(R_pref-R_orth)/(R_pref+R_orth)",
                "zero_denominator": "OSI=0, osi_defined=false, selective=false",
                "selective": "strictly OSI > 0.5 from unrounded counts/durations",
                "threshold": 0.5,
                "preference_data": "same trials as reported responses; descriptive only"},
        "optional_qc": {"isi_violations_lt": 0.5, "amplitude_cutoff_lt": 0.1,
                        "presence_ratio_gt": 0.9,
                        "missing_metrics": "retain primary unit, blank unavailable metrics, qc_pass=false",
                        "baseline_interval": "[start_time-0.5, start_time)",
                        "baseline_mean": "unweighted mean of per-presentation 0.5-second rates",
                        "peak_rate_gt_hz": 2.0, "peak_minus_baseline_gt_hz": 1.0,
                        "empty_denominator": "null fraction; zero numerator and denominator",
                        "primary_effect": "none"},
        "numerical_tolerances": {"rates_osi_fractions_atol": 1e-6,
                                 "rates_osi_fractions_rtol": 1e-6,
                                 "source_times_atol_seconds": 1e-9, "source_times_rtol": 0,
                                 "qc_metrics_atol": 1e-6, "qc_metrics_rtol": 1e-6,
                                 "ids_counts_categories": "exact"},
        "software": {"numpy": "2.1.3", "h5py": "3.12.1"},
    }


def source_number(value):
    if value is None:
        return np.nan
    if isinstance(value, (str, bytes)):
        text = decoded(value).strip()
        if text.lower() in {"", "null", "none", "nan"}:
            return np.nan
        value = text
    number = float(value)
    if np.isinf(number):
        raise ValueError("infinite source presentation value")
    return number


def presentation_support(presentations):
    """Check original table support only, with no response-derived selection."""
    ids = unique_ids(presentations["id"], "presentation IDs")
    start = np.asarray(presentations["start_time"], dtype=float)
    stop = np.asarray(presentations["stop_time"], dtype=float)
    direction = np.asarray([source_number(x) for x in presentations["orientation"]])
    tf = np.asarray([source_number(x) for x in presentations["temporal_frequency"]])
    if any(x.shape != ids.shape for x in (start, stop, direction, tf)):
        raise ValueError("inconsistent presentation column lengths")
    if not np.all(np.isfinite(start)) or not np.all(np.isfinite(stop)) or np.any(stop <= start):
        raise ValueError("all presentation intervals must be finite and positive")
    if np.any(np.diff(start) < 0):
        raise ValueError("source presentations not chronological; never silently sort")
    blank = np.isnan(direction)
    selected = ~blank
    if not np.any(selected):
        raise ValueError("no nonblank grating presentations")
    if np.any(~np.isfinite(tf[selected])) or np.any(tf[selected] <= 0):
        raise ValueError("nonblank presentation has missing/nonpositive temporal frequency")
    directions = np.unique(direction[selected])
    if not np.array_equal(directions, DIRECTIONS):
        raise ValueError("nonblank directions must be 0..315 degrees in 45-degree steps")
    tfs = np.unique(tf[selected])
    support = np.asarray([[np.count_nonzero(selected & (direction == d) & (tf == t))
                           for t in tfs] for d in DIRECTIONS], dtype=np.int64)
    if np.any(support == 0):
        raise ValueError("missing direction x temporal-frequency cell; no zero imputation")
    return {"presentation_id": ids[selected], "start_time": start[selected],
            "stop_time": stop[selected], "duration_seconds": (stop - start)[selected],
            "direction": direction[selected], "temporal_frequency": tf[selected],
            "directions": DIRECTIONS.copy(), "temporal_frequencies": tfs,
            "condition_n_presentations": support, "selected_source_rows": np.flatnonzero(selected),
            "n_original_presentations": int(len(ids)), "n_blank_presentations": int(blank.sum())}


def read_source(inputs):
    """Read source structure and ordered spikes; never count response windows.

    All unit IDs, mappings and spike trains are checked. Only VISp spike arrays
    are retained. Repeated timestamps are preserved, never sorted/deduplicated.
    """
    import h5py

    with h5py.File(inputs["path"], "r") as nwb:
        units, electrodes = nwb["units"], nwb[ELECTRODE_PATH]
        unit_ids = unique_ids(units["id"][:], "unit IDs")
        electrode_ids = unique_ids(electrodes["id"][:], "electrode IDs")
        locations = np.asarray([decoded(x) for x in electrodes["location"][:]])
        if len(locations) != len(electrode_ids):
            raise ValueError("electrode ID/location lengths differ")
        peak = integral_array(units["peak_channel_id"][:], "unit peak_channel_id")
        if len(peak) != len(unit_ids):
            raise ValueError("unit ID/peak-channel lengths differ")
        lookup = dict(zip(electrode_ids.tolist(), locations.tolist()))
        unresolved = sorted(set(peak.tolist()) - set(lookup))
        if unresolved:
            raise ValueError(f"peak-channel IDs absent from electrode IDs: {unresolved[:20]}")
        regions = np.asarray([lookup[int(x)] for x in peak])
        visp_rows = np.flatnonzero(regions == "VISp")
        if len(visp_rows) == 0:
            raise ValueError("source has no VISp clusters")
        qc = {}
        for field in QC_FIELDS:
            value = np.asarray(units[field][:], dtype=float) if field in units else np.full(len(unit_ids), np.nan)
            if value.shape != unit_ids.shape:
                raise ValueError(f"QC column {field} has incorrect shape")
            qc[field] = value
        ends = integral_array(units["spike_times_index"][:], "spike ragged endpoints")
        spike_dataset = units["spike_times"]
        if len(ends) != len(unit_ids) or not len(ends) or np.any(np.diff(ends) < 0) or ends[-1] != len(spike_dataset):
            raise ValueError("invalid spike_times ragged indices")
        spikes, spike_hash = [], hashlib.sha256()
        duplicate_counts = np.zeros(len(unit_ids), dtype=np.int64)
        visp_set, previous = set(visp_rows.tolist()), 0
        for row, end in enumerate(ends):
            train = np.asarray(spike_dataset[previous:int(end)], dtype=np.float64)
            if not np.all(np.isfinite(train)) or np.any(np.diff(train) < 0):
                raise ValueError(f"unit {unit_ids[row]} has nonfinite/unordered spikes; never sort silently")
            duplicate_counts[row] = np.count_nonzero(np.diff(train) == 0)
            spike_hash.update(train.astype("<f8", copy=False).tobytes())
            if row in visp_set:
                spikes.append(train)
            previous = int(end)
        table = nwb[STIMULUS_PATH]
        required = ("id", "start_time", "stop_time", "orientation", "temporal_frequency")
        presentations = {key: table[key][:] for key in required}
        contrast = np.asarray(table["contrast"][:], float) if "contrast" in table else None
        invalid = nwb.get("intervals/invalid_times")
        invalid_times = {"start_time": np.empty(0), "stop_time": np.empty(0), "tags": []}
        if invalid is not None:
            invalid_times = {"start_time": np.asarray(invalid["start_time"][:], float),
                             "stop_time": np.asarray(invalid["stop_time"][:], float),
                             "tags": [decoded(x) for x in invalid["tags"][:]] if "tags" in invalid else []}
            if "tags_index" in invalid:
                invalid_times["tags_index"] = integral_array(invalid["tags_index"][:], "invalid interval tags_index")
        extra_columns = {}
        for key in table:
            dataset = table[key]
            if key not in required and isinstance(dataset, h5py.Dataset) and dataset.shape == presentations["id"].shape:
                values = dataset[:]
                tokens = sorted(set(decoded(x) for x in values))
                extra_columns[key] = {"dtype": str(values.dtype), "n_unique": len(tokens),
                                      "unique_values_first_50": tokens[:50]}
        attrs = {key: {name: decoded(value) for name, value in table[key].attrs.items()
                       if name in {"description", "unit", "neurodata_type"}} for key in required}
        result = {
            "unit_ids_all": unit_ids, "peak_channel_ids_all": peak,
            "unit_regions_all": regions, "electrode_ids": electrode_ids,
            "electrode_locations": locations, "visp_source_rows": visp_rows,
            "unit_id": unit_ids[visp_rows], "peak_channel_id": peak[visp_rows],
            "spikes": spikes, "qc": {key: value[visp_rows] for key, value in qc.items()},
            "qc_present_fields": [key for key in QC_FIELDS if key in units],
            "spike_times_index": ends, "spike_duplicates_by_unit": duplicate_counts,
            "spike_times_sha256_le_float64": spike_hash.hexdigest(),
            "presentations_raw": presentations, "stimulus_columns": sorted(table.keys()),
            "stimulus_column_attributes": attrs, "unit_columns": sorted(units.keys()),
            "electrode_columns": sorted(electrodes.keys()),
            "stimulus_extra_columns": extra_columns,
            "interval_table_names": sorted(nwb["intervals"].keys()),
            "invalid_times_present": "invalid_times" in nwb or "intervals/invalid_times" in nwb,
            "invalid_times": invalid_times, "contrast": contrast,
        }
        if "session_id" in nwb:
            result["nwb_session_id"] = decoded(nwb["session_id"][()])
        if "general/subject/subject_id" in nwb:
            result["nwb_subject_id"] = decoded(nwb["general/subject/subject_id"][()])
    return result


def source_condition_checks(source, presentations, include_qc):
    contrast = source["contrast"]
    if contrast is None or contrast.shape != np.asarray(source["presentations_raw"]["id"]).shape:
        raise ValueError("missing/malformed source contrast column")
    if not np.all(contrast[presentations["selected_source_rows"]] == 0.8):
        raise ValueError("selected source gratings do not all have contrast 0.8; never silently mix")
    invalid = source["invalid_times"]
    starts, stops = invalid["start_time"], invalid["stop_time"]
    if starts.shape != stops.shape or not np.all(np.isfinite(starts)) or not np.all(np.isfinite(stops)) or np.any(stops <= starts):
        raise ValueError("malformed source invalid intervals")
    pstart, pstop = presentations["start_time"], presentations["stop_time"]
    stimulus_overlap = np.asarray([np.count_nonzero((pstart < stop) & (pstop > start))
                                   for start, stop in zip(starts, stops)], dtype=np.int64)
    baseline_overlap = np.asarray([np.count_nonzero((pstart - 0.5 < stop) & (pstart > start))
                                   for start, stop in zip(starts, stops)], dtype=np.int64)
    if np.any(stimulus_overlap) or (include_qc and np.any(baseline_overlap)):
        raise ValueError("source invalid interval overlaps a requested window; no silent filtering")
    return {"n_invalid_intervals": len(starts), "invalid_interval_tags": invalid["tags"],
            "selected_stimulus_overlap_counts_by_invalid_interval": stimulus_overlap.tolist(),
            "selected_baseline_overlap_counts_by_invalid_interval": baseline_overlap.tolist(),
            "selected_contrast_values": np.unique(contrast[presentations["selected_source_rows"]]).tolist()}


def inspect_source(inputs):
    """Structure-only probe; intentionally no analyze/count_spikes call."""
    source = read_source(inputs)
    raw = source["presentations_raw"]
    report = {"status": "source_structure_only", "pipeline_id": PIPELINE_ID,
              "source_sha256": inputs["source_sha256"],
              "n_units_total": len(source["unit_ids_all"]), "n_visp_units_total": len(source["unit_id"]),
              "unit_ids": source["unit_ids_all"].tolist(), "visp_unit_ids": source["unit_id"].tolist(),
              "visp_peak_channel_ids": source["peak_channel_id"].tolist(),
              "n_electrodes": len(source["electrode_ids"]),
              "unit_columns": source["unit_columns"], "electrode_columns": source["electrode_columns"],
              "stimulus_columns": source["stimulus_columns"],
              "stimulus_column_attributes": source["stimulus_column_attributes"],
              "stimulus_extra_columns": source["stimulus_extra_columns"],
              "interval_table_names": source["interval_table_names"],
              "invalid_times_present": source["invalid_times_present"],
              "n_original_presentations": len(raw["id"]),
              "presentation_ids": integral_array(raw["id"], "presentation IDs").tolist(),
              "orientation_tokens": sorted(set(decoded(x) for x in raw["orientation"])),
              "temporal_frequency_tokens": sorted(set(decoded(x) for x in raw["temporal_frequency"])),
              "all_spikes_finite_nondecreasing": True,
              "spike_times_sha256_le_float64": source["spike_times_sha256_le_float64"],
              "n_units_with_duplicate_spike_timestamps": int(np.count_nonzero(source["spike_duplicates_by_unit"])),
              "n_duplicate_spike_timestamps": int(source["spike_duplicates_by_unit"].sum()),
              "nwb_session_id": source.get("nwb_session_id"), "nwb_subject_id": source.get("nwb_subject_id"),
              "qc_present_fields": source["qc_present_fields"],
              "visp_qc_nonfinite_by_field": {key: int(np.count_nonzero(~np.isfinite(value)))
                                            for key, value in source["qc"].items()},
              "response_counting_performed": False}
    try:
        p = presentation_support(raw)
        report["source_conditions"] = source_condition_checks(source, p, include_qc=True)
        duration = p["duration_seconds"]
        original_rows = p["selected_source_rows"]
        previous_stop = np.asarray(raw["stop_time"], float)[np.maximum(original_rows - 1, 0)]
        baseline_overlaps = (original_rows > 0) & (p["start_time"] - 0.5 < previous_stop)
        report["support"] = {"n_blank_presentations": p["n_blank_presentations"],
                             "n_gratings_presentations": len(duration), "directions": p["directions"].tolist(),
                             "temporal_frequencies": p["temporal_frequencies"].tolist(),
                             "condition_n_presentations": p["condition_n_presentations"].tolist(),
                             "duration_min_seconds": float(duration.min()), "duration_max_seconds": float(duration.max()),
                             "n_baseline_windows_starting_before_zero": int(np.count_nonzero(p["start_time"] < 0.5)),
                             "n_baseline_windows_overlapping_preceding_grating_table_interval": int(baseline_overlaps.sum()),
                             "baseline_preceding_interval_overlap_presentation_ids": p["presentation_id"][baseline_overlaps].tolist()}
    except (ValueError, KeyError) as error:
        report["support_error"] = str(error)
    return report


def count_spikes(spikes, starts, stops):
    starts, stops = np.asarray(starts, float), np.asarray(stops, float)
    if starts.shape != stops.shape or not np.all(np.isfinite(starts)) or not np.all(np.isfinite(stops)) or not np.all(stops > starts):
        raise ValueError("invalid counting intervals")
    counts = np.empty((len(spikes), len(starts)), dtype=np.int64)
    for i, train in enumerate(spikes):
        train = np.asarray(train, float)
        if not np.all(np.isfinite(train)) or np.any(np.diff(train) < 0):
            raise ValueError("spikes must already be finite and nondecreasing")
        counts[i] = np.searchsorted(train, stops, side="left") - np.searchsorted(train, starts, side="left")
    return counts


def condition_means(counts, presentations):
    counts = np.asarray(counts)
    durations = presentations["duration_seconds"]
    if counts.ndim != 2 or counts.shape[1] != len(durations) or np.any(counts < 0):
        raise ValueError("invalid trial count matrix")
    if not np.all(np.isfinite(counts)) or np.any(counts != np.floor(counts)):
        raise ValueError("trial counts must be finite nonnegative integers")
    rates = counts / durations[None, :]
    tfs = presentations["temporal_frequencies"]
    means = np.empty((len(counts), 8, len(tfs)), dtype=float)
    for di, direction in enumerate(DIRECTIONS):
        for ti, tf in enumerate(tfs):
            use = ((presentations["direction"] == direction) & (presentations["temporal_frequency"] == tf))
            if not np.any(use):
                raise ValueError("missing condition; do not impute response")
            means[:, di, ti] = rates[:, use].mean(axis=1)
    return rates, means


def two_point_osi(means, temporal_frequencies):
    means, tfs = np.asarray(means, float), np.asarray(temporal_frequencies, float)
    if means.ndim != 3 or means.shape[1:] != (8, len(tfs)):
        raise ValueError("expected unit x 8 directions x temporal-frequency means")
    if not np.all(np.isfinite(means)) or np.any(means < 0) or np.any(np.diff(tfs) <= 0):
        raise ValueError("invalid means or temporal frequencies")
    tf_idx = np.argmax(means.max(axis=1), axis=1)
    rows = np.arange(len(means))
    folded = (means[:, :4, :] + means[:, 4:, :]) / 2.0
    tuning = folded[rows, :, tf_idx]
    preferred = np.argmax(tuning, axis=1)
    r_pref, r_orth = tuning[rows, preferred], tuning[rows, (preferred + 2) % 4]
    denominator = r_pref + r_orth
    defined = denominator > 0
    osi = np.divide(r_pref - r_orth, denominator, out=np.zeros(len(means)), where=defined)
    return {"preferred_temporal_frequency": tfs[tf_idx], "preferred_orientation": ORIENTATIONS[preferred],
            "r_pref_hz": r_pref, "r_orth_hz": r_orth, "peak_rate_hz": means.max(axis=(1, 2)),
            "osi": osi, "osi_defined": defined, "selective": defined & (osi > 0.5)}


def qc_sensitivity(source_qc, baseline_counts, peak_rate):
    baseline = np.asarray(baseline_counts, dtype=float).mean(axis=1) / 0.5
    complete = np.logical_and.reduce([np.isfinite(source_qc[key]) for key in QC_FIELDS])
    passed = (complete & (source_qc["isi_violations"] < 0.5) & (source_qc["amplitude_cutoff"] < 0.1)
              & (source_qc["presence_ratio"] > 0.9))
    responsive = (peak_rate > 2.0) & (peak_rate > baseline + 1.0)
    return {**source_qc, "qc_metrics_complete": complete, "qc_pass": passed,
            "baseline_rate_hz": baseline, "responsive": responsive, "in_qc_responsive": passed & responsive}


def analyze(source, include_qc=True):
    p = presentation_support(source["presentations_raw"])
    source_condition_checks(source, p, include_qc)
    counts = count_spikes(source["spikes"], p["start_time"], p["stop_time"])
    rates, means = condition_means(counts, p)
    units = two_point_osi(means, p["temporal_frequencies"])
    n = len(source["unit_id"])
    result = {"status": "ok", "pipeline_id": PIPELINE_ID,
              "orientation_selective_fraction": float(units["selective"].mean()),
              "n_visp_units_total": n, "n_visp_units_analyzed": n,
              "n_orientation_selective": int(units["selective"].sum()),
              "n_osi_undefined": int((~units["osi_defined"]).sum()), "osi_threshold": 0.5}
    arrays = {**p, "unit_id": source["unit_id"], "peak_channel_id": source["peak_channel_id"],
              "spike_count": counts, "rate_hz": rates, "mean_rate_hz": means, **units}
    if include_qc:
        if np.any(p["start_time"] < 0.5):
            raise ValueError("optional baseline extends before recording time zero")
        baseline_counts = count_spikes(source["spikes"], p["start_time"] - 0.5, p["start_time"])
        qc = qc_sensitivity(source["qc"], baseline_counts, units["peak_rate_hz"])
        nkept = int(qc["in_qc_responsive"].sum())
        nsel = int((qc["in_qc_responsive"] & units["selective"]).sum())
        result.update(n_qc_responsive_units=nkept, n_qc_responsive_orientation_selective=nsel,
                      qc_responsive_selective_fraction=nsel / nkept if nkept else None)
        arrays["baseline_spike_count"] = baseline_counts
        arrays.update(qc)
    return arrays, result


def scalar(value):
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (np.floating, float)) and not np.isfinite(value):
        return ""
    return value


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows([[scalar(value) for value in row] for row in rows])


def write_outputs(output, inputs, source, arrays, result, include_qc):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    uid, pid = arrays["unit_id"], arrays["presentation_id"]
    fields = ("presentation_id", "start_time", "stop_time", "duration_seconds", "direction", "temporal_frequency")
    write_csv(output / "presentations.csv", fields, zip(*(arrays[key] for key in fields)))
    write_csv(output / "trial_responses.csv", ("unit_id", "presentation_id", "spike_count", "rate_hz"),
              ((unit, pres, arrays["spike_count"][ui, pi], arrays["rate_hz"][ui, pi])
               for ui, unit in enumerate(uid) for pi, pres in enumerate(pid)))
    write_csv(output / "condition_means.csv", ("unit_id", "direction", "temporal_frequency", "n_presentations", "mean_rate_hz"),
              ((unit, direction, tf, arrays["condition_n_presentations"][di, ti], arrays["mean_rate_hz"][ui, di, ti])
               for ui, unit in enumerate(uid) for di, direction in enumerate(DIRECTIONS)
               for ti, tf in enumerate(arrays["temporal_frequencies"])))
    fields = ("unit_id", "peak_channel_id", "preferred_temporal_frequency", "preferred_orientation",
              "r_pref_hz", "r_orth_hz", "peak_rate_hz", "osi", "osi_defined", "selective")
    write_csv(output / "units.csv", fields, zip(*(arrays[key] for key in fields)))
    if include_qc:
        fields = ("unit_id", *QC_FIELDS, "qc_metrics_complete", "qc_pass", "baseline_rate_hz", "responsive", "in_qc_responsive")
        write_csv(output / "qc_sensitivity.csv", fields, zip(*(arrays[key] for key in fields)))
        write_csv(output / "baseline_counts.csv", ("unit_id", "presentation_id", "spike_count"),
                  ((unit, pres, arrays["baseline_spike_count"][ui, pi])
                   for ui, unit in enumerate(uid) for pi, pres in enumerate(pid)))
    metadata = {**metadata_contract(inputs), "status": "ok", "n_units_total": len(source["unit_ids_all"]),
                "n_visp_units_total": len(uid), "n_original_presentations": arrays["n_original_presentations"],
                "n_blank_presentations": arrays["n_blank_presentations"], "n_gratings_presentations": len(pid),
                "directions": DIRECTIONS.tolist(), "temporal_frequencies": arrays["temporal_frequencies"].tolist(),
                "include_qc": bool(include_qc)}
    for name, obj in (("results.json", result), ("run_metadata.json", metadata)):
        (output / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    findings = (f"# All-VISp custom two-point OSI\n\n{result['n_orientation_selective']} of {len(uid)} source VISp clusters "
                f"have OSI > 0.5 (fraction {result['orientation_selective_fraction']:.8f}). "
                f"{result['n_osi_undefined']} zero-response clusters remain in the denominator with undefined-by-convention "
                "OSI set to zero. Preference and response use the same trials; ties are computational conventions, "
                "not evidence of a unique biological preference. This describes one session's recorded clusters, "
                "not unbiased neuron/population prevalence, AllenSDK gOSI, or the paper's numerical finding.\n")
    if include_qc:
        findings += (f"\nThe optional QC+responsive subset contains {result['n_qc_responsive_units']} clusters, "
                     f"with selective fraction {result['qc_responsive_selective_fraction']}. Its preceding-window "
                     "baseline is not assumed to be spontaneous activity. Changing this denominator does not "
                     "establish that noise caused the change.\n")
    (output / "findings.md").write_text(findings)
    private = dict(arrays)
    for key in QC_FIELDS:
        private["source_" + key] = source["qc"][key]
    private.update(unit_ids_all=source["unit_ids_all"], unit_regions_all=source["unit_regions_all"],
                   visp_source_rows=source["visp_source_rows"],
                   spike_times_sha256_le_float64=source["spike_times_sha256_le_float64"],
                   metadata_json=json.dumps(metadata, allow_nan=False), result_json=json.dumps(result, allow_nan=False))
    np.savez_compressed(output / "analysis_arrays.npz", **private)
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="/app/data/allenosi")
    parser.add_argument("--output", default=os.environ.get("OUTPUT_DIR", "/app/output"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect-source", action="store_true")
    mode.add_argument("--print-contracts", action="store_true")
    parser.add_argument("--no-qc", action="store_true")
    parser.add_argument("--report", help="optional structure-only JSON report path")
    args = parser.parse_args(argv)
    if args.print_contracts:
        inputs = load_inputs(args.data)
        print(json.dumps(metadata_contract(inputs), indent=2, allow_nan=False))
        return
    if args.inspect_source:
        inputs = load_inputs(args.data)
        report = inspect_source(inputs)
        text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(text)
        print(text, end="")
        return
    try:
        inputs = load_inputs(args.data)
        source = read_source(inputs)
        arrays, result = analyze(source, include_qc=not args.no_qc)
        write_outputs(args.output, inputs, source, arrays, result, not args.no_qc)
        print(json.dumps(result, allow_nan=False))
    except Exception as error:
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        failure = {"status": "failed_precondition", "pipeline_id": PIPELINE_ID, "reason": str(error)}
        for name in ("results.json", "run_metadata.json"):
            (output / name).write_text(json.dumps(failure, indent=2, allow_nan=False) + "\n")
        (output / "findings.md").write_text("# Failed precondition\n\n" + str(error) + "\n")
        raise


if __name__ == "__main__":
    main()
