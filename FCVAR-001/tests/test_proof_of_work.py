"""Manufactured end-to-end proof tests; public kernel, no original I/O."""
import copy
import hashlib
import sys
import types

import numpy as np
import pytest

import artifact_reader as a
import fixture_support as f
import proof_of_work as p


@pytest.fixture(scope="module")
def manufactured():
    import signal_kernel as kernel
    reference = f.manufactured_reference()
    return reference, f.evidence(reference, kernel), kernel


@pytest.fixture
def case(tmp_path, monkeypatch, manufactured):
    reference, original, kernel = manufactured
    monkeypatch.setattr(p, "load_kernel", lambda: kernel)
    files = copy.deepcopy(original)
    return reference, files, tmp_path / "output"


def validate(case):
    reference, files, path = case
    f.emit(path, files)
    return p.validate_output_directory(path, reference)


def test_complete_genuine_zero_and_undefined_states(case):
    assert validate(case)["status"] == "accepted"


def test_coherent_all_axes_and_row_permutations(case):
    _, files, _ = case
    z = files["roi_evidence.npz"]
    for field in ("participant_ids",): z[field] = z[field][::-1]
    for field in ("geometry_present", "n_voxels", "support_sha256", "roi_active", "raw_sample_sd", "prestandardization_centered_l2", "activity_threshold", "full_clean_centered_l2"):
        z[field] = z[field][::-1, ::-1]
    for field in ("roi_ids", "roi_labels"): z[field] = z[field][::-1]
    for field in ("frame_subject", "frame_index"): z[field] = z[field][::-1]
    for field in ("raw_roi_mean", "clean_roi_series"): z[field] = z[field][::-1, ::-1]
    for field in ("phase_subject", "phase_window", "frequency_index"): z[field] = z[field][::-1]
    z["surrogate_ids"] = z["surrogate_ids"][::-1]
    z["phase_angles"] = z["phase_angles"][::-1, ::-1]
    for name in ("cohort.csv", "variability.csv", "surrogate_statistics.csv"): files[name].reverse()
    files["dynamics.json"]["windows"].reverse(); files["dynamics.json"]["window_lengths_tr"].reverse()
    files["run_metadata.json"]["source_observed"]["roi_labels"].reverse()
    assert validate(case)["status"] == "accepted"


def test_harmless_extras_dtype_aliases_and_descriptive_warnings(case):
    _, files, _ = case
    files["roi_evidence.npz"]["optional"] = np.ones((1,)*12)
    metadata = files["run_metadata.json"]
    metadata["warnings"] = ["A harmless descriptive warning"]
    metadata["source_observed"]["atlas_header"]["storage_dtype"] = "float32"
    metadata["source_observed"]["persons"][f.s.IDS[0]]["bold_header"]["note"] = "extra explanation"
    assert validate(case)["status"] == "accepted"


def test_inactive_tolerated_jitter_never_reactivates(case):
    _, files, _ = case
    files["roi_evidence.npz"]["clean_roi_series"][52:, :] = 5e-8
    assert validate(case)["status"] == "accepted"


@pytest.mark.parametrize("field", ["participant_ids", "roi_ids", "frame_index", "frequency_index", "surrogate_ids"])
def test_duplicate_or_missing_key_rejected(case, field):
    _, files, _ = case
    values = files["roi_evidence.npz"][field]; values[0] = values[1]
    with pytest.raises(ValueError): validate(case)


@pytest.mark.parametrize("change", ["raw", "clean", "mask", "geometry", "voxelcount", "support", "rank", "site", "source_hash", "phase", "phase_dc", "seed", "seed_bool", "literal_id", "drop_null", "denominator", "null_value", "count_bool", "p_value", "significant", "group_available_case", "failure_status"])
def test_material_binding_and_arithmetic_mutations(case, change):
    _, files, _ = case
    z, meta = files["roi_evidence.npz"], files["run_metadata.json"]
    if change == "raw": z["raw_roi_mean"][0, 0] += .1
    elif change == "clean": z["clean_roi_series"][0, 0] += .1
    elif change == "mask": z["roi_active"][0, 0] = False
    elif change == "geometry": z["geometry_present"][0, 0] = False
    elif change == "voxelcount": z["n_voxels"][0, 0] += 1
    elif change == "support": z["support_sha256"][0, 0] = "e"*64
    elif change == "rank": meta["analysis_observed"]["persons"][f.s.IDS[0]]["cleaning_rank"] = 1
    elif change == "site": files["cohort.csv"][0]["site"] = "wrong"
    elif change == "source_hash": meta["source_files"][0]["sha256"] = "e"*64
    elif change == "phase": z["phase_angles"][1, 0] += .01
    elif change == "phase_dc": z["phase_angles"][0, 0] = 1e-8
    elif change == "seed": meta["seed"] = 1
    elif change == "seed_bool": files["dynamics.json"]["seed"] = True
    elif change == "literal_id": z["frame_subject"][0] = "10042"
    elif change == "drop_null": files["surrogate_statistics.csv"].pop()
    elif change == "denominator": files["variability.csv"][0]["p_denominator"] = 50
    elif change == "null_value": files["surrogate_statistics.csv"][0]["mean_edge_sd"] = 1.
    elif change == "count_bool": files["dynamics.json"]["n_subjects"] = True
    elif change == "p_value": files["variability.csv"][0]["p_value"] = .5
    elif change == "significant": files["variability.csv"][0]["significant"] = True
    elif change == "group_available_case": files["dynamics.json"]["windows"][0]["mean_observed_edge_sd"]["value"] = 0.
    elif change == "failure_status": meta["status"] = "failed"
    with pytest.raises(ValueError): validate(case)


@pytest.mark.parametrize("field", ["mean_edge_sd", "mean_edge_sd_null", "observed_over_null_ratio", "p_value"])
def test_negative_near_zero_scalar_rejected_separately_from_tolerance(field):
    with pytest.raises(ValueError, match="nonnegative"):
        p.record({field: "-5e-7"}, {field: 0.}, csv=True)
    p.record({field: "0"}, {field: 0.}, csv=True)


@pytest.mark.parametrize("metric", ["mean_observed_edge_sd", "mean_null_edge_sd", "mean_subject_observed_over_null_ratio", "median_subject_p", "fraction_subjects_significant"])
def test_negative_group_near_zero_rejected(manufactured, metric):
    expected = copy.deepcopy(manufactured[1]["dynamics.json"])
    for row in expected["windows"]:
        row[metric] = dict(n_expected=30, n_defined=30, status="ok", value=0.)
    got = copy.deepcopy(expected); got["windows"][0][metric]["value"] = -5e-7
    with pytest.raises(ValueError, match="nonnegative"):
        p.validate_dynamics(got, expected)


@pytest.mark.parametrize("field", ["p_value", "fraction_subjects_significant", "median_subject_p"])
def test_probability_above_one_rejected(manufactured, field):
    if field == "p_value":
        with pytest.raises(ValueError, match="probability"): p.record({field: 1.+5e-7}, {field: 1.})
    else:
        expected = copy.deepcopy(manufactured[1]["dynamics.json"])
        expected["windows"][0][field] = dict(n_expected=30, n_defined=30, status="ok", value=1.)
        got = copy.deepcopy(expected); got["windows"][0][field]["value"] = 1.+5e-7
        with pytest.raises(ValueError, match="probability"): p.validate_dynamics(got, expected)


@pytest.mark.parametrize("kind", ["empty", "dangling"])
def test_late_authoritative_failure(case, monkeypatch, kind):
    original = p.validate_metadata
    def late(meta, ref, seed):
        original(meta, ref, seed)
        marker = case[2] / a.FAILURE
        if kind == "empty": marker.touch()
        else: marker.symlink_to(case[2] / "absent")
    monkeypatch.setattr(p, "validate_metadata", late)
    with pytest.raises(ValueError, match="late failure_report"): validate(case)


def test_private_kernel_ignores_public_cwd_module_and_sys_modules(tmp_path, monkeypatch):
    private = tmp_path / "private"; private.mkdir()
    public = tmp_path / "public"; public.mkdir()
    body = b"VALUE = 'private held bytes'\n"
    (private / "signal_kernel.py").write_bytes(body)
    (public / "signal_kernel.py").write_text("raise RuntimeError('public execution forbidden')")
    monkeypatch.setattr(p, "__file__", str(private / "proof_of_work.py"))
    monkeypatch.setattr(p, "KERNEL_SHA256", hashlib.sha256(body).hexdigest())
    monkeypatch.chdir(public); monkeypatch.syspath_prepend(str(public))
    poison = types.ModuleType("signal_kernel"); poison.VALUE = "poison"
    monkeypatch.setitem(sys.modules, "signal_kernel", poison)
    assert p.load_kernel().VALUE == "private held bytes"


def test_private_kernel_changed_bytes_fail_closed(tmp_path, monkeypatch):
    (tmp_path / "signal_kernel.py").write_text("VALUE=2\n")
    monkeypatch.setattr(p, "__file__", str(tmp_path / "proof_of_work.py"))
    monkeypatch.setattr(p, "KERNEL_SHA256", "a"*64)
    with pytest.raises(ValueError, match="checksum"): p.load_kernel()


@pytest.fixture(scope="module")
def quantitative():
    # All30 real manufactured replays have three noncollinear active ROIs.
    # No endpoint mocking or canonical endpoint target is used.
    kernel = p.load_kernel()
    reference = f.manufactured_reference(quantitative=True)
    return reference, f.evidence(reference, kernel), kernel


def test_all30_quantitative_complete_group_positive(tmp_path, quantitative):
    reference, files, _ = quantitative
    for row in files["variability.csv"]:
        assert row["observed_status"] == row["inference_status"] == row["ratio_status"] == "ok"
    for row in files["dynamics.json"]["windows"]:
        for key, metric in row.items():
            if key != "window_tr": assert metric["n_defined"] == 30 and metric["status"] == "ok"
    output = tmp_path / "positive"; f.emit(output, files)
    assert p.validate_output_directory(output, reference)["status"] == "accepted"


@pytest.mark.parametrize("change", ["required_null", "group", "rank_count"])
def test_quantitative_numerical_mutations(tmp_path, quantitative, change):
    reference, original, _ = quantitative
    files = copy.deepcopy(original)
    if change == "required_null":
        assert files["surrogate_statistics.csv"][0]["mean_edge_sd"] is not None
        files["surrogate_statistics.csv"][0]["mean_edge_sd"] = None
    elif change == "group":
        value = files["dynamics.json"]["windows"][0]["mean_observed_edge_sd"]["value"]
        assert value is not None
        files["dynamics.json"]["windows"][0]["mean_observed_edge_sd"]["value"] = value + 1.
    else:
        row = files["variability.csv"][0]
        old = row["n_exceedances"]; assert type(old) is int
        row["n_exceedances"] = old-1 if old == 50 else old+1
    output = tmp_path / change; f.emit(output, files)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


def test_source_close_own_series_replay_not_second_canonical_rank_gate(tmp_path, quantitative):
    reference, original, kernel = quantitative
    accepted = {sid: person["clean"] * (1.+1e-8) for sid, person in reference["persons"].items()}
    files = f.evidence(reference, kernel, accepted=accepted)
    assert np.any(files["roi_evidence.npz"]["clean_roi_series"] != original["roi_evidence.npz"]["clean_roi_series"])
    # Counts/p may coherently change at exact floating ties; no assertion that
    # they equal the canonical-series result is permitted.
    output = tmp_path / "own-replay"; f.emit(output, files)
    assert p.validate_output_directory(output, reference)["status"] == "accepted"
