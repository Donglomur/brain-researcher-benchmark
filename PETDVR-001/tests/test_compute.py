"""Synthetic-only numerical and serialization mechanics; never original TACs."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("petdvr_compute_mechanics", TASK/"solution/compute.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def source_data(n=6, ct=None, cr=None):
    starts = np.arange(n, dtype=float)*600
    data = {"frame_start": starts, "frame_end": starts+600,
            "reference": np.full(n, 2.0) if cr is None else np.asarray(cr, dtype=float)}
    for target in c.TARGETS:
        data[target] = np.full(n, 4.0) if ct is None else np.asarray(ct, dtype=float)
    return data


def sidecar(data):
    return dict(FrameTimesStart=data["frame_start"].tolist(),
                FrameDuration=(data["frame_end"]-data["frame_start"]).tolist(),
                ScanStart=0, InjectionStart=0, ImageDecayCorrected=True,
                ImageDecayCorrectionTime=0, Units="Bq/mL")


def scan(data=None):
    data = source_data() if data is None else data
    return dict(subject="sub-01", session="ses-baseline", data=data,
                midpoint=(data["frame_start"]+data["frame_end"])/2)


def test_first_integral_is_half_whole_frame_area():
    actual = c.midpoint_integral([4, 6, -2], [0, 60, 180], [60, 180, 240])
    np.testing.assert_array_equal(actual, [2, 10, 15])


def test_zero_current_target_still_contributes_previous_frame_areas():
    data = source_data(4, [2, 0, -2, 4], [1, 0, 2, 2])
    g = c.make_graph(data, "highbinding")
    np.testing.assert_array_equal(g["valid"], [True, False, True, True])
    np.testing.assert_array_equal(g["ratio_valid"], [True, False, True, True])
    assert g["it"][2] == 10 and g["y"][2] == -5
    assert np.isnan(g["x"][1]) and g["tr"][2] == -1


def test_ct_zero_is_valid_ratio_zero_when_cr_nonzero():
    g = c.make_graph(source_data(1, [0], [2]), "highbinding")
    assert not g["valid"][0] and g["ratio_valid"][0] and g["tr"][0] == 0


def test_cr_zero_does_not_invalidate_logan_graph():
    g = c.make_graph(source_data(1, [2], [0]), "highbinding")
    assert g["valid"][0] and not g["ratio_valid"][0]
    assert g["x"][0] == 0 and g["rt"][0] == 0


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_concentration_fails(bad):
    with pytest.raises(ValueError):
        c.midpoint_integral([bad], [0], [60])


def test_overflow_fails_not_graph_omission():
    with pytest.raises((ValueError, FloatingPointError)):
        c.make_graph(source_data(3, [1e-300]*3, [1e300]*3), "highbinding")


@pytest.mark.parametrize("n", [0, 1, 2])
def test_minimum_three_distinct_graph_frames(n):
    fit, pred = c.centered_ols(np.arange(n), np.arange(n))
    assert fit["fit_status"] == "insufficient_frames" and pred is None
    assert fit["logan_slope"] is None
    assert (fit["Sxx_min2"] is None) == (n == 0)


def test_centered_ols_and_residual_definition():
    x, y = np.array([1, 2, 4, 8.]), np.array([5, 7, 8, 18.])
    fit, pred = c.centered_ols(x, y)
    expected = np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[0]
    np.testing.assert_allclose([fit["logan_slope"], fit["intercept_min"]], expected, atol=1e-13)
    assert fit["sse_min2"] == pytest.approx(np.sum((pred-y)**2))
    assert fit["rmse_min"] == pytest.approx(np.sqrt(np.mean((pred-y)**2)))


@pytest.mark.parametrize("x", [[2, 2, 2], [1, 1+1e-13, 1+2e-13]])
def test_public_precision_rule_rejects_collapsed_x(x):
    fit, pred = c.centered_ols(x, [2, 3, 4])
    assert fit["fit_status"] == "rank_deficient_under_public_rule" and pred is None
    assert fit["Sxx_min2"] <= fit["rank_threshold_min2"]


def test_finite_tiny_nonzero_denominator_not_replaced():
    g = c.make_graph(source_data(3, [1e-14, -1e-14, 2e-14]), "highbinding")
    assert g["valid"].all() and np.isfinite(g["x"]).all()
    assert g["x"][0] == 1e15


def test_constant_y_r_squared_explicitly_undefined():
    fit, pred = c.centered_ols([1, 2, 3], [5, 5, 5])
    assert fit["fit_status"] == "ok" and fit["logan_slope"] == 0
    assert fit["r_squared"] is None and fit["r_squared_status"] == "constant_y"
    np.testing.assert_array_equal(pred, [5, 5, 5])


@pytest.mark.parametrize("value", [0.1, 0.2, -0.1, 1e-30])
def test_identical_decimal_y_is_exactly_constant(value):
    fit, pred = c.centered_ols([1, 2, 3], [value]*3)
    assert fit["Syy_min2"] == 0 and fit["r_squared"] is None
    assert fit["r_squared_status"] == "constant_y" and fit["sse_min2"] == 0
    np.testing.assert_array_equal(pred, [value]*3)


def test_identical_decimal_x_has_exact_zero_centered_moment():
    fit, _ = c.centered_ols([0.1]*3, [1, 2, 3])
    assert fit["Sxx_min2"] == 0 and fit["fit_status"] == "rank_deficient_under_public_rule"


@pytest.mark.parametrize("ratio,times,cv_status,trend_status", [
    ([], [], "no_valid_ratio", "no_valid_ratio"),
    ([2], [1], "ok", "insufficient_distinct_times"),
    ([0], [1], "zero_mean", "insufficient_distinct_times"),
    ([-2, 2], [1, 2], "zero_mean", "ok"),
    ([-4, -2], [1, 2], "ok", "ok"),
    ([1, 3], [1, 1], "ok", "insufficient_distinct_times"),
])
def test_ratio_statuses(ratio, times, cv_status, trend_status):
    result = c.ratio_diagnostics(ratio, times)
    assert result["ratio_cv_status"] == cv_status
    assert result["ratio_trend_status"] == trend_status
    if ratio and np.mean(ratio) != 0:
        assert result["ratio_cv"] == pytest.approx(np.std(ratio, ddof=0)/abs(np.mean(ratio)))


def test_common_end_uses_frame_end_not_midpoint():
    data = source_data(6)
    data["frame_end"][-1] = 3100  # midpoint3000, but frame is not wholly available.
    data["frame_start"][-1] = 2900
    _, _, fits, points = c.analyze_scan(scan(data), ["highbinding"])
    row = next(r for r in fits if r["start_min"] == 40 and r["end_policy"] == "common50")
    assert row["n_window"] == row["n_fit"] == 1
    assert row["actual_window_end_s"] == 3000
    assert row["fit_status"] == "insufficient_frames"
    subset = [r for r in points if r["start_min"] == 40 and r["end_policy"] == "common50"]
    assert len(subset) == 1 and not subset[0]["in_fit"] and subset[0]["predicted_y_min"] is None


def test_equal_start_and_end_boundaries_are_included():
    data = source_data(4)
    data["frame_start"] = np.array([0, 300, 900, 1500.])
    data["frame_end"] = np.array([300, 900, 1500, 3000.])
    _, _, fits, points = c.analyze_scan(scan(data), ["highbinding"])
    row = next(r for r in fits if r["start_min"] == 10 and r["end_policy"] == "common50")
    assert row["first_window_frame"] == 1 and row["last_window_frame"] == 3
    assert row["n_fit"] == 3 and row["fit_status"] == "ok"


def test_invalid_graph_frames_retained_in_window_receipt_and_ratio_diagnostics():
    data = source_data(4, [0, 2, 4, 6], [2, 2, 2, 2])
    _, graphs, fits, points = c.analyze_scan(scan(data), ["highbinding"])
    row = next(r for r in fits if r["start_min"] == 0 and r["end_policy"] == "native")
    subset = [r for r in points if r["start_min"] == 0 and r["end_policy"] == "native"]
    assert row["n_window"] == row["n_ratio"] == 4 and row["n_fit"] == 3
    assert len(subset) == 4 and subset[0]["point_status"] == "zero_target"
    assert graphs[0]["target_over_reference"] == 0
    assert row["ratio_mean"] == 1.5


def test_empty_temporal_windows_keep_undefined_rows():
    _, _, fits, _ = c.analyze_scan(scan(source_data(1)), ["highbinding"])
    row = next(r for r in fits if r["start_min"] == 40 and r["end_policy"] == "native")
    assert row["n_window"] == row["n_fit"] == row["n_ratio"] == 0
    assert row["first_window_frame"] is None and row["rank_threshold_min2"] is None


def test_pairing_never_substitutes_single_available_scan():
    fits = []
    for subject, session in c.SCANS:
        _, _, rows, _ = c.analyze_scan(dict(scan(), subject=subject, session=session), ["highbinding"])
        fits.extend(rows)
    selected = next(r for r in fits if (r["subject"], r["session"], r["end_policy"], r["start_min"]) == ("sub-01", "ses-rescan", "native", 0))
    selected.update(fit_status="insufficient_frames", logan_slope=None)
    summary = c.make_summary(fits, ["highbinding"], c.SCANS)
    pair = next(r for r in summary["paired_changes"] if (r["subject"], r["end_policy"], r["start_min"]) == ("sub-01", "native", 0))
    assert pair["pair_status"] == "incomplete_pair" and pair["rescan_minus_baseline"] is None
    group = next(r for r in summary["group_windows"] if (r["end_policy"], r["start_min"]) == ("native", 0))
    assert group["n_expected_scans"] == 4 and group["n_expected_subjects"] == 2
    assert group["n_defined_scans"] == 3 and group["n_defined_pairs"] == 1


@pytest.mark.parametrize("field,value", [("ScanStart", 1), ("InjectionStart", 1),
    ("ImageDecayCorrected", False), ("ImageDecayCorrectionTime", 3), ("Units", "unknown")])
def test_wrong_source_timing_units_or_decay_fails(field, value):
    data = source_data()
    pet = sidecar(data)
    pet[field] = value
    with pytest.raises(ValueError):
        c.validate_timing(data, pet)


def test_unknown_gap_cannot_be_integrated():
    data = source_data()
    data["frame_start"][1] += 1
    with pytest.raises(ValueError):
        c.validate_timing(data, sidecar(data))


def test_tsv_required_columns_are_finite_and_unique():
    columns = ["frame_start", "frame_end", "reference", *c.TARGETS]
    valid = "\t".join(columns)+"\n"+"\t".join(["0", "60", *(["2"]*8)])+"\n"
    parsed, data = c.parse_tsv(valid)
    assert parsed == columns and data["reference"][0] == 2
    with pytest.raises(ValueError):
        c.parse_tsv(valid.replace("reference", "highbinding", 1))
    with pytest.raises(ValueError):
        c.parse_tsv(valid.replace("\t2", "\tnan", 1))


def test_synthetic_pilot_has_seven_public_files_and_private_separate(tmp_path):
    method = json.loads((TASK/"environment/method_contract.json").read_text())
    inputs = dict(method=method, manifest={"files": []}, scans=[scan()], observed=[],
                  targets=["highbinding"], status="resource_pilot")
    out, private = c.prepare_destinations(tmp_path/"output", tmp_path/"private")
    summary, statuses = c.run(inputs, out, private)
    assert set(p.name for p in out.iterdir()) == set(method["outputs"])
    assert set(p.name for p in private.iterdir()) == {"analysis_arrays.npz"}
    assert summary["status"] == "resource_pilot" and sum(statuses.values()) == 10
    with np.load(private/"analysis_arrays.npz", allow_pickle=False) as arrays:
        assert json.loads(str(arrays["summary_json"])) == summary


def test_refuse_existing_evidence_and_nested_private(tmp_path):
    out = tmp_path/"out"
    out.mkdir()
    (out/"sentinel").write_text("keep")
    with pytest.raises(FileExistsError):
        c.prepare_destinations(out, tmp_path/"private")
    assert (out/"sentinel").read_text() == "keep"
    with pytest.raises(ValueError):
        c.prepare_destinations(tmp_path/"new", tmp_path/"new/private")


def test_failure_produces_reason_and_findings_without_source(tmp_path):
    rc = c.main(["--source-dir", str(tmp_path/"absent"), "--method-contract", str(tmp_path/"absent.json"),
                 "--output-dir", str(tmp_path/"out"), "--private-dir", str(tmp_path/"private")])
    assert rc == 1
    assert json.loads((tmp_path/"out/summary.json").read_text())["status"] == "failed_precondition"
    assert (tmp_path/"out/findings.md").read_text().strip()


def test_native_task_stager_layout(tmp_path):
    helper = tmp_path/"task/environment/stage_data.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("# fixture only")
    assert c.resolve_stager_path(tmp_path/"task/solution/compute.py", tmp_path/"absent.py") == helper


def test_harbor_solution_copy_uses_baked_helper(tmp_path):
    helper = tmp_path/"opt/source/stage_data.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("# fixture only")
    assert c.resolve_stager_path(tmp_path/"solution/compute.py", helper) == helper


def test_stager_missing_or_symlink_fails(tmp_path):
    helper = tmp_path/"helper.py"
    helper.symlink_to(tmp_path/"missing.py")
    with pytest.raises(ValueError):
        c.resolve_stager_path(tmp_path/"solution/compute.py", helper)
