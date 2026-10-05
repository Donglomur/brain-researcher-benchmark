"""Synthetic mechanics only; never opens the original NWB or oracle/verifier."""
import ast
import csv
import importlib.util
import json
from pathlib import Path

import h5py
import numpy as np
import pytest


CHECKER = Path(__file__).with_name("check_independent.py")
SPEC = importlib.util.spec_from_file_location("allenosi_independent", CHECKER)
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


@pytest.mark.parametrize("spikes,starts,stops,expected", [
    ([0, 1, 1, 2, 3], [0, 1, 2], [1, 2, 3], [1, 2, 1]),
    ([0, 1], [0], [1], [1]),  # Last finite endpoint is not histogram's closed edge.
    ([-1, 0, 0, .5, 1, 1, 2], [0, .5, 1], [1, 2, 2], [3, 3, 2]),
    ([], [0, 1], [1, 2], [0, 0]),
    ([3, 3], [0], [3], [0]),
    ([1, 1, 2], [1, 1, 1], [2, 3, 2], [2, 3, 2]),
])
def test_half_open_histogram_endpoints(spikes, starts, stops, expected):
    assert q.histogram_windows(spikes, starts, stops).tolist() == expected


@pytest.mark.parametrize("spikes,starts,stops", [
    ([2, 1], [0], [3]), ([0, np.nan], [0], [3]), ([0, np.inf], [0], [3]),
    ([0], [1], [1]), ([0], [2], [1]), ([0], [0], [np.inf]), ([0], [], []),
])
def test_bad_spikes_or_windows_fail_without_repair(spikes, starts, stops):
    with pytest.raises(ValueError):
        q.histogram_windows(spikes, starts, stops)


def presentation_fixture():
    # Unequal durations within each condition distinguish rate means from pooling.
    directions = np.repeat(np.arange(0, 360, 45), 4)
    frequency = np.tile([1, 1, 2, 2], 8)
    starts = 10. + np.arange(32) * 4
    return {"id": 700 + np.arange(32) * 3, "start_time": starts,
            "stop_time": starts + np.tile([1, 2, 1, 2], 8),
            "orientation": directions, "temporal_frequency": frequency}


def response_fixture():
    p = q.select_presentations(presentation_fixture())
    duration = p["duration_seconds"]
    values = np.array([[12, 5, 2, 4, 8, 6, 2, 3], [0] * 8, [6, 2, 2, 1, 6, 2, 2, 1]])
    rates = np.column_stack([values[:, int(angle // 45)] if tf == 1 else np.ones(3)
                            for angle, tf in zip(p["direction"], p["temporal_frequency"])])
    rates[1] = 0
    return {**p, "spike_count": (rates * duration).astype(np.int64), "baseline_spike_count": np.zeros((3, 32), dtype=np.int64),
            "unit_id": np.array([93, 101, 4]), "peak_channel_id": np.array([40, 20, 5]),
            "source_isi_violations": np.array([.1, np.nan, .5]),
            "source_amplitude_cutoff": np.array([.01, .02, .02]), "source_presence_ratio": np.array([.95, .96, .96])}


def test_source_rate_means_not_pooled_counts():
    data = response_fixture()
    data["spike_count"][0, :2] = [10, 0]
    out, _ = q.derive_independent(data, False)
    assert out["mean_rate_hz"][0, 0, 0] == 5
    assert out["mean_rate_hz"][0, 0, 0] != pytest.approx(10 / 3)


def test_tf_uses_highest_direction_not_tf_average():
    data = response_fixture()
    tf, direction, duration = (data[key] for key in ("temporal_frequency", "direction", "duration_seconds"))
    data["spike_count"][0] = ((tf == 1) * 10 * duration).astype(int)
    selected = (tf == 2) & (direction == 45)
    data["spike_count"][0, selected] = (20 * duration[selected]).astype(int)
    out, _ = q.derive_independent(data, False)
    assert out["preferred_temporal_frequency"][0] == 2


def test_exact_ties_and_zero_response_denominator():
    data = response_fixture()
    data["spike_count"][0] = data["duration_seconds"].astype(int)
    out, result = q.derive_independent(data, False)
    assert out["preferred_temporal_frequency"][0] == 1
    assert out["preferred_orientation"][0] == 0
    assert out["osi"][0] == 0 and out["osi_defined"][0]
    assert out["osi"][1] == 0 and not out["osi_defined"][1] and not out["selective"][1]
    assert result["n_visp_units_analyzed"] == 3 and result["n_osi_undefined"] == 1


def test_equal_weight_opposite_directions_with_unequal_repeats():
    data = response_fixture()
    # Delete one of the two 0-degree/TF1 trials while keeping both opposite trials.
    for key in ("presentation_id", "start_time", "stop_time", "duration_seconds", "direction", "temporal_frequency"):
        data[key] = np.delete(data[key], 1)
    data["spike_count"] = np.delete(data["spike_count"], 1, axis=1)
    out, _ = q.derive_independent(data, False)
    assert out["r_pref_hz"][0] == (12 + 8) / 2
    assert out["r_pref_hz"][0] != pytest.approx((12 + 8 + 8) / 3)
    assert out["osi"][0] == pytest.approx(2 / 3)


def test_strict_osi_threshold_no_rounding_of_categories():
    data = response_fixture()
    out, _ = q.derive_independent(data, False)
    assert out["osi"][2] == .5 and not out["selective"][2]
    data["spike_count"][2] *= 100000
    data["spike_count"][2, 0] += 1
    out, _ = q.derive_independent(data, False)
    assert .5 < out["osi"][2] < .500001 and out["selective"][2]


def test_qc_is_optional_and_preserves_all_source_units():
    data = response_fixture()
    primary, primary_result = q.derive_independent(data, False)
    full, result = q.derive_independent(data, True)
    assert result["n_visp_units_analyzed"] == primary_result["n_visp_units_analyzed"] == 3
    np.testing.assert_array_equal(full["osi"], primary["osi"])
    assert full["qc_pass"].tolist() == [True, False, False]
    assert result["n_qc_responsive_units"] == 1
    assert not any(name in primary_result for name in q.QC_RESULT_NAMES)


@pytest.mark.parametrize("field,value", [("isi_violations", .5), ("amplitude_cutoff", .1), ("presence_ratio", .9)])
def test_qc_thresholds_strict(field, value):
    data = response_fixture()
    data["source_" + field][0] = value
    out, result = q.derive_independent(data, True)
    assert not out["qc_pass"][0]
    assert result["qc_responsive_selective_fraction"] is None
    assert result["n_qc_responsive_orientation_selective"] == 0


def test_responsiveness_strict_boundaries():
    data = response_fixture()
    data["spike_count"][0] = (2 * data["duration_seconds"]).astype(int)
    out, _ = q.derive_independent(data, True)
    assert not out["responsive"][0]
    data["spike_count"][0] = (3 * data["duration_seconds"]).astype(int)
    data["baseline_spike_count"][0] = 1  # Baseline2Hz, peak3Hz does not exceed baseline+1.
    out, _ = q.derive_independent(data, True)
    assert not out["responsive"][0]


@pytest.mark.parametrize("token", ["", "null", "nan", "None", np.nan])
def test_blank_orientation_retained_as_excluded_source_row(token):
    data = presentation_fixture()
    data["orientation"] = np.concatenate((data["orientation"].astype(object), np.array([token], object)))
    data["temporal_frequency"] = np.concatenate((data["temporal_frequency"].astype(object), np.array(["null"], object)))
    for key, value in (("id", 9000), ("start_time", 150), ("stop_time", 152)):
        data[key] = np.r_[data[key], value]
    out = q.select_presentations(data)
    assert out["n_original_presentations"] == 33 and out["n_blank_presentations"] == 1
    assert len(out["presentation_id"]) == 32 and 9000 not in out["presentation_id"]


@pytest.mark.parametrize("mutation", ["bad_token", "missing_tf", "infinite_tf", "bad_direction", "missing_cell", "unordered", "duplicate_id"])
def test_source_preconditions_fail_closed(mutation):
    data = presentation_fixture()
    if mutation == "bad_token":
        data["orientation"] = data["orientation"].astype(object)
        data["orientation"][0] = "not-a-condition"
    elif mutation == "missing_tf":
        data["temporal_frequency"] = data["temporal_frequency"].astype(float)
        data["temporal_frequency"][0] = np.nan
    elif mutation == "infinite_tf":
        data["temporal_frequency"] = data["temporal_frequency"].astype(float)
        data["temporal_frequency"][0] = np.inf
    elif mutation == "bad_direction": data["orientation"][0] = 46
    elif mutation == "missing_cell":
        for key in data: data[key] = data[key][2:]
    elif mutation == "unordered": data["start_time"][[0, 1]] = data["start_time"][[1, 0]]
    else: data["id"][1] = data["id"][0]
    with pytest.raises(ValueError): q.select_presentations(data)


def hdf5_fixture(path, include_metric=True):
    source = presentation_fixture()
    trains = [np.array([0, 10, 10, 10.5, 11, 12]), np.array([1, 2]), np.array([])]
    with h5py.File(path, "w") as h:
        u = h.create_group("units")
        u["id"] = [93, 8, 101]
        u["peak_channel_id"] = [40, 7, 20]
        u["spike_times_index"] = np.cumsum([len(train) for train in trains])
        u["spike_times"] = np.concatenate(trains)
        u["spike_times"].attrs["description"] = "times (s) of detected spiking events"
        if include_metric:
            for name, values in (("isi_violations", [.1, .2, np.nan]), ("amplitude_cutoff", [.01, .02, .03]), ("presence_ratio", [.95, .95, .95])):
                u[name] = values
        e = h.create_group("general/extracellular_ephys/electrodes")
        e["id"] = [20, 7, 40]  # Deliberately neither unit-row positions nor ID order.
        e["location"] = np.array(["VISp", "LGd", "VISp"], dtype=h5py.string_dtype())
        p = h.create_group("intervals/drifting_gratings_presentations")
        for key, value in source.items(): p[key] = value
        p["start_time"].attrs["description"] = "Start time of epoch, in seconds"
        p["stop_time"].attrs["description"] = "Stop time of epoch, in seconds"
        p["contrast"] = np.full(32, .8)
    return path


def test_original_ragged_join_source_identity_and_duplicate_counts(tmp_path):
    arrays, report = q.read_original(hdf5_fixture(tmp_path / "tiny.nwb"), True)
    assert arrays["unit_id"].tolist() == [93, 101]
    assert arrays["visp_source_rows"].tolist() == [0, 2]
    assert arrays["peak_channel_id"].tolist() == [40, 20]
    assert arrays["spike_count"][0, 0] == 3  # Two10s plus10.5, stop11s excluded.
    assert np.all(arrays["spike_count"][1] == 0)
    assert report["n_duplicate_timestamps"] == 1
    assert report["n_original_spikes"] == 8


def test_no_metrics_does_not_change_primary_identity(tmp_path):
    arrays, report = q.read_original(hdf5_fixture(tmp_path / "tiny.nwb", False), True)
    assert arrays["unit_id"].tolist() == [93, 101]
    out, result = q.derive_independent(arrays, True)
    assert not out["qc_pass"].any() and result["qc_responsive_selective_fraction"] is None
    assert report["qc_fields_available"] == []


@pytest.mark.parametrize("mutation", ["foreign_channel", "bad_ragged", "unordered_spike", "duplicate_electrode", "invalid_overlap"])
def test_hdf5_source_defects_are_not_repaired(tmp_path, mutation):
    path = hdf5_fixture(tmp_path / "tiny.nwb")
    with h5py.File(path, "a") as h:
        if mutation == "foreign_channel": h["units/peak_channel_id"][0] = 999
        elif mutation == "bad_ragged": h["units/spike_times_index"][-1] = 1
        elif mutation == "unordered_spike": h["units/spike_times"][0] = 99
        elif mutation == "duplicate_electrode": h["general/extracellular_ephys/electrodes/id"][0] = 7
        else:
            bad = h.create_group("intervals/invalid_times")
            bad["start_time"], bad["stop_time"] = [10.5], [12.5]
    with pytest.raises(ValueError): q.read_original(path, True)


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_source_keyed_table_order_can_differ(tmp_path):
    expected = [dict(unit_id=5, spike_count=2, rate_hz=1.), dict(unit_id=90, spike_count=4, rate_hz=2.)]
    path = tmp_path / "counts.csv"
    write_csv(path, list(reversed(expected)))
    report = q.compare_table(path, expected, {"unit_id": "integer"}, {"spike_count": "integer", "rate_hz": "float"})
    assert report["passed"] and report["rows"] == 2


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "foreign", "noninteger_count", "false_integer_count", "false_rate"])
def test_count_receipts_detect_mutations(tmp_path, mutation):
    expected = [dict(unit_id=5, spike_count=2, rate_hz=1.), dict(unit_id=90, spike_count=4, rate_hz=2.)]
    rows = [dict(row) for row in expected]
    if mutation == "duplicate": rows.append(rows[0])
    elif mutation == "missing": rows.pop()
    elif mutation == "foreign": rows[0]["unit_id"] = 99
    elif mutation == "noninteger_count": rows[0]["spike_count"] = 2.1
    elif mutation == "false_integer_count": rows[0]["spike_count"] = 3
    else: rows[0]["rate_hz"] = 1.01
    path = tmp_path / "counts.csv"
    write_csv(path, rows)
    if mutation in {"false_integer_count", "false_rate"}:
        assert not q.compare_table(path, expected, {"unit_id": "integer"}, {"spike_count": "integer", "rate_hz": "float"})["passed"]
    else:
        with pytest.raises(ValueError): q.compare_table(path, expected, {"unit_id": "integer"}, {"spike_count": "integer", "rate_hz": "float"})


def test_category_not_relaxed_by_numeric_reporting_tolerance():
    assert q.compare_value(.5, .5000001, "float")[0]
    assert not q.compare_value(0, 45, "category")[0]
    assert not q.compare_value("false", True, "boolean")[0]
    assert not q.compare_value(1., 1.00000000001, "category")[0]
    assert q.compare_value("", np.nan, "optional")[0]
    assert not q.compare_value("nan", np.nan, "optional")[0]


@pytest.mark.parametrize("trigger", ["baseline", "qc", "result", "metadata"])
def test_partial_optional_bundle_rejected(tmp_path, trigger):
    result, metadata = {}, {"include_qc": False}
    if trigger in {"baseline", "qc"}: (tmp_path / ("baseline_counts.csv" if trigger == "baseline" else "qc_sensitivity.csv")).write_text("header\n")
    elif trigger == "result": result["n_qc_responsive_units"] = 0
    else: metadata["include_qc"] = True
    with pytest.raises(ValueError): q.optional_qc_requested(tmp_path, result, metadata)


def test_no_oracle_verifier_or_searchsorted_dependency():
    tree = ast.parse(CHECKER.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in {"compute", "proof_of_work"} for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {"compute", "proof_of_work"}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "searchsorted"


def test_manifest_authentication_fails_before_opening_nwb(tmp_path):
    (tmp_path / "data_manifest.json").write_text(json.dumps({"files": []}))
    with pytest.raises(ValueError, match="manifest SHA256"):
        q.authenticate(tmp_path)


def emit_tiny_receipts(output, arrays, result, source_report, include_qc):
    """Format synthetic fixture arithmetic only; no source bank/reference writing."""
    output.mkdir()
    def public(value):
        if isinstance(value, (np.integer, np.bool_)): return value.item()
        if isinstance(value, (float, np.floating)) and not np.isfinite(value): return ""
        return value
    def emit(name, rows):
        write_csv(output / name, [{key: public(value) for key, value in row.items()} for row in rows])
    uid, pid = arrays["unit_id"], arrays["presentation_id"]
    emit("presentations.csv", [{key: arrays[key][j] for key in ("presentation_id", "start_time", "stop_time", "duration_seconds", "direction", "temporal_frequency")} for j in range(len(pid))])
    emit("trial_responses.csv", [dict(unit_id=u, presentation_id=p, spike_count=arrays["spike_count"][i, j], rate_hz=arrays["rate_hz"][i, j])
                                 for i, u in enumerate(uid) for j, p in enumerate(pid)])
    emit("condition_means.csv", [dict(unit_id=u, direction=d, temporal_frequency=t, n_presentations=arrays["condition_n_presentations"][di, ti], mean_rate_hz=arrays["mean_rate_hz"][i, di, ti])
                                 for i, u in enumerate(uid) for di, d in enumerate(q.DIRECTIONS) for ti, t in enumerate(arrays["temporal_frequencies"])])
    emit("units.csv", [dict(unit_id=u, **{key: arrays[key][i] for key in ("peak_channel_id", "preferred_temporal_frequency", "preferred_orientation", "r_pref_hz", "r_orth_hz", "peak_rate_hz", "osi", "osi_defined", "selective")}) for i, u in enumerate(uid)])
    if include_qc:
        emit("baseline_counts.csv", [dict(unit_id=u, presentation_id=p, spike_count=arrays["baseline_spike_count"][i, j]) for i, u in enumerate(uid) for j, p in enumerate(pid)])
        emit("qc_sensitivity.csv", [dict(unit_id=u, **{key: arrays[key][i] for key in (*q.QC_NAMES, "qc_metrics_complete", "qc_pass", "baseline_rate_hz", "responsive", "in_qc_responsive")}) for i, u in enumerate(uid)])
    metadata = {"status": "ok", "pipeline_id": q.PIPELINE_ID, "dandiset_id": "000021", "dandiset_version": "0.251116.2246",
                "asset_id": q.ASSET_ID, "asset_path": "sub-707296975/" + q.SOURCE_NAME,
                "subject_id": "707296975", "session_id": "721123822", "region": "VISp", "include_qc": include_qc,
                "source_sha256": {q.SOURCE_NAME: q.SOURCE_SHA256}, "directions": list(q.DIRECTIONS),
                "temporal_frequencies": arrays["temporal_frequencies"].tolist(),
                **{key: source_report[key] for key in ("n_units_total", "n_visp_units_total", "n_original_presentations", "n_blank_presentations", "n_gratings_presentations")}}
    (output / "run_metadata.json").write_text(json.dumps(metadata))
    (output / "results.json").write_text(json.dumps(result))
    (output / "findings.md").write_text("Synthetic mechanics fixture, not an original-source result.\n")
    np.savez_compressed(output / "analysis_arrays.npz", **arrays, metadata_json=json.dumps(metadata), result_json=json.dumps(result))


@pytest.mark.parametrize("include_qc", [True, False])
def test_complete_checker_glue_on_tiny_hdf5_only(tmp_path, monkeypatch, include_qc):
    path = hdf5_fixture(tmp_path / "tiny.nwb")
    source, source_report = q.read_original(path, include_qc)
    arrays, result = q.derive_independent(source, include_qc)
    output = tmp_path / "tiny-output"
    emit_tiny_receipts(output, arrays, result, source_report, include_qc)
    # Only authentication is substituted: the rest rereads this tiny HDF5 file.
    monkeypatch.setattr(q, "authenticate", lambda unused: (path, {"synthetic_test_only": True}))
    report = q.check(tmp_path, output, tmp_path / "report.json")
    assert report["status"] == "passed" and report["tables"]["trial_responses.csv"]["rows"] == 64
    with np.load(tmp_path / "report.counts.npz", allow_pickle=False) as artifact:
        assert str(artifact["pipeline_id"].item()) == q.PIPELINE_ID
        assert artifact["spike_count"][0, 0] == 3
        assert ("baseline_spike_count" in artifact) == include_qc
    assert q.digest(tmp_path / "report.counts.npz") == report["independent_counts_sha256"]


def test_private_receipt_mutation_is_detected(tmp_path):
    source, source_report = q.read_original(hdf5_fixture(tmp_path / "tiny.nwb"), True)
    arrays, result = q.derive_independent(source, True)
    output = tmp_path / "tiny-output"
    emit_tiny_receipts(output, arrays, result, source_report, True)
    with np.load(output / "analysis_arrays.npz", allow_pickle=False) as receipt:
        modified = {key: receipt[key] for key in receipt.files}
    modified["spike_count"][0, 0] += 1
    np.savez_compressed(output / "analysis_arrays.npz", **modified)
    comparisons = q.compare_private(output, arrays)
    assert comparisons["spike_count"]["n_disagreements"] == 1
    assert not comparisons["spike_count"]["passed"]


@pytest.mark.parametrize("target,symlink", [("report.json", False), ("report.counts.npz", False),
                                           ("report.json", True), ("report.counts.npz", True)])
def test_existing_evidence_never_overwritten_or_reprocessed(tmp_path, monkeypatch, target, symlink):
    path = tmp_path / target
    if symlink:
        path.symlink_to(tmp_path / "missing-target")
    else:
        path.write_bytes(b"retained original evidence")
    def forbidden_authentication(unused):
        raise AssertionError("original source processing must not begin when evidence exists")
    monkeypatch.setattr(q, "authenticate", forbidden_authentication)
    with pytest.raises(ValueError, match="refusing to overwrite existing evidence"):
        q.check(tmp_path, tmp_path, tmp_path / "report.json")
    assert q.main(["--data-dir", str(tmp_path), "--oracle-output", str(tmp_path), "--report", str(tmp_path / "report.json")]) == 1
    if symlink:
        assert path.is_symlink() and not path.exists()
    else:
        assert path.read_bytes() == b"retained original evidence"
