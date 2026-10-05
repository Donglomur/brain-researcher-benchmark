"""Independent piecewise-linear reference convolution and full numerical checks.

This module does not import the oracle or fit a model. Its recurrence integrates
the declared reference interpolation exactly over each midpoint-to-midpoint segment.
"""
from pathlib import Path
import numpy as np
from proof_of_work import (PIPELINE_ID, SCANS, TARGET, REFERENCE, MODEL, PARAMETERS, SOURCE_TAC_FIELDS,
    LOWER, UPPER, BOUND_ATOL, PARAM_ATOL, PARAM_RTOL, SIGNAL_ATOL, SIGNAL_RTOL,
    SOURCE_ATOL, SOURCE_RTOL, METRIC_ATOL, METRIC_RTOL, SUMMARY_ATOL, PERCENT_ATOL,
    number, integer, read_json, match_contract, load_estimates, load_tac_fit)


def srtm_prediction(mid_min, reference, params):
    t, cr = np.asarray(mid_min, float), np.asarray(reference, float)
    params = np.asarray(params, float)
    assert t.ndim == 1 and len(t) > 0 and t.shape == cr.shape
    assert np.isfinite(t).all() and np.isfinite(cr).all() and t[0] > 0 and (np.diff(t) > 0).all()
    assert params.shape == (3,) and np.isfinite(params).all() and ((params >= LOWER) & (params <= UPPER)).all()
    r1, k2, bp = params; theta = k2/(1.+bp)
    knots = np.concatenate(([0.], t)); values = np.concatenate(([0.], cr))
    integral, output = 0., np.empty(len(t))
    for i, width in enumerate(np.diff(knots)):
        q = theta*width
        # phi functions use Taylor expansions where subtractive cancellation
        # would otherwise lose the slope contribution for small theta*dt.
        if abs(q) < 1e-4:
            phi1 = 1-q/2+q*q/6-q**3/24+q**4/120-q**5/720
            phi2 = .5-q/6+q*q/24-q**3/120+q**4/720-q**5/5040
        else:
            exponential_difference = np.expm1(-q)
            phi1 = -exponential_difference/q
            phi2 = (q+exponential_difference)/(q*q)
        slope = (values[i+1]-values[i])/width
        integral = np.exp(-q)*integral + values[i]*width*phi1 + slope*width*width*phi2
        output[i] = r1*values[i+1] + (k2-r1*theta)*integral
    return output


def near(actual, expected, atol, rtol, message):
    assert np.isfinite(actual).all() and np.allclose(actual, expected, atol=atol, rtol=rtol), message


def validate_frames(rows, reference):
    expected_keys = {(*SCANS[int(scan)], int(frame)) for scan, frame in zip(reference["frame_scan"], reference["frame_index"])}
    assert set(rows) == expected_keys, "exact complete source scan/frame membership required"
    ordered = [rows[(*SCANS[int(scan)], int(frame))] for scan, frame in zip(reference["frame_scan"], reference["frame_index"])]
    fields = ("frame_start_s", "frame_end_s", "mid_time_min", *SOURCE_TAC_FIELDS, "target", "reference", "predicted_target", "residual")
    arrays = {field: np.asarray([row[field] for row in ordered], float) for field in fields}
    for field in ("frame_start_s", "frame_end_s", "mid_time_min", "target", "reference"):
        near(arrays[field], reference[field], SOURCE_ATOL, SOURCE_RTOL, f"source {field} differs")
    for column, field in enumerate(SOURCE_TAC_FIELDS):
        assert (arrays[field] >= 0).all(), "negative required regional TAC"
        near(arrays[field], reference["source_tacs"][:, column], SOURCE_ATOL, SOURCE_RTOL, f"source {field} differs")
    near(arrays["target"], (arrays["left_putamen"]+arrays["right_putamen"])/2,
         SOURCE_ATOL, SOURCE_RTOL, "target must be equal-hemisphere mean")
    near(arrays["reference"], (arrays["left_cerebellum_cortex"]+arrays["right_cerebellum_cortex"])/2,
         SOURCE_ATOL, SOURCE_RTOL, "reference must be equal-hemisphere cortex mean")
    near(arrays["mid_time_min"], (arrays["frame_start_s"]+arrays["frame_end_s"])/120.,
         SOURCE_ATOL, SOURCE_RTOL, "midpoint time must be in minutes")
    assert (arrays["frame_end_s"] > arrays["frame_start_s"]).all(), "nonpositive frame duration"
    assert (arrays["frame_start_s"] >= 0).all(), "negative frame start"
    return arrays


def validate_estimates(rows, frames, reference):
    assert set(rows) == set(SCANS), "exact four source scan estimates required"
    for scan, key in enumerate(SCANS):
        row = rows[key]
        assert (row["target"], row["reference_region"], row["model"], row["status"]) == (TARGET, REFERENCE, MODEL, "ok"), "wrong target/reference/model/status"
        params = np.asarray([row[field] for field in PARAMETERS], float)
        assert np.isfinite(params).all() and ((params >= LOWER) & (params <= UPPER)).all(), "fit parameters outside public computational bounds"
        near(params, reference["params"][scan], PARAM_ATOL, PARAM_RTOL, "parameters differ from declared source fit")
        assert 0 <= integer(row["selected_start_index"]) < 3 and 1 <= integer(row["optimizer_status"]) <= 4
        assert 1 <= integer(row["nfev"]) <= 5000, "invalid successful optimizer diagnostics"
        assert np.array_equal(row["at_lower_bound"], np.isclose(params, LOWER, atol=BOUND_ATOL, rtol=0)), "lower-bound flags differ from reported parameters"
        assert np.array_equal(row["at_upper_bound"], np.isclose(params, UPPER, atol=BOUND_ATOL, rtol=0)), "upper-bound flags differ from reported parameters"
        near(number(row["k2prime"]), params[1]/params[0], PARAM_ATOL[1], PARAM_RTOL, "k2prime must equal k2/R1")
        mask = reference["frame_scan"] == scan
        scale = float(reference["reference_scale"][scan])
        near(number(row["reference_scale"]), scale, SOURCE_ATOL, SOURCE_RTOL, "normalization scale must equal source reference maximum")
        reconstructed = srtm_prediction(frames["mid_time_min"][mask], frames["reference"][mask], params)
        prediction, residual, target = frames["predicted_target"][mask], frames["residual"][mask], frames["target"][mask]
        near(prediction/scale, reconstructed/scale, SIGNAL_ATOL, SIGNAL_RTOL, "TAC predictions do not reconstruct from submitted SRTM parameters")
        near(prediction/scale, reference["prediction"][mask]/scale, SIGNAL_ATOL, SIGNAL_RTOL, "TAC prediction differs from source fit")
        near(residual/scale, (prediction-target)/scale, SIGNAL_ATOL, SIGNAL_RTOL, "signed residual must be prediction minus observation")
        near(residual/scale, reference["residual"][mask]/scale, SIGNAL_ATOL, SIGNAL_RTOL, "residual differs from source fit")
        # Recompute from prediction-target, not from a separately rounded residual column.
        difference = (prediction-target)/scale
        normalized_sse = float(np.dot(difference, difference))
        normalized_rmse = float(np.sqrt(normalized_sse/len(difference)))
        for field in ("sse", "rmse", "normalized_rmse"):
            assert number(row[field]) >= 0, "negative residual metric"
        near(number(row["sse"])/(scale*scale), normalized_sse, METRIC_ATOL, METRIC_RTOL, "SSE does not recompute")
        near(number(row["rmse"])/scale, normalized_rmse, METRIC_ATOL, METRIC_RTOL, "RMSE does not recompute")
        near(number(row["normalized_rmse"]), normalized_rmse, METRIC_ATOL, METRIC_RTOL, "normalized RMSE does not recompute")
    return rows


def paired_metrics(estimates):
    pairs = []
    for subject in ("sub-01", "sub-02"):
        baseline = float(estimates[(subject, "ses-baseline")]["BP_ND"])
        rescan = float(estimates[(subject, "ses-rescan")]["BP_ND"])
        mean, difference = (baseline+rescan)/2., abs(baseline-rescan)
        pairs.append({"subject": subject, "baseline_BP_ND": baseline, "rescan_BP_ND": rescan,
            "absolute_difference": difference, "pair_mean": mean,
            "test_retest_pct": 100*difference/mean if mean > 0 else None,
            "status": "ok" if mean > 0 else "undefined_nonpositive_mean"})
    defined = sum(pair["test_retest_pct"] is not None for pair in pairs)
    return {"n_scans": 4, "n_subjects": 2, "putamen_BP_ND_mean": float(np.mean([estimates[key]["BP_ND"] for key in SCANS])),
        "per_subject": pairs, "n_defined_pairs": defined,
        "test_retest_pct": float(np.mean([pair["test_retest_pct"] for pair in pairs])) if defined == 2 else None}


def validate_results(result, estimates):
    assert result.get("status") == "ok" and result.get("pipeline_id") == PIPELINE_ID, "incorrect result status/pipeline"
    expected = paired_metrics(estimates)
    for field in ("n_scans", "n_subjects", "n_defined_pairs"):
        assert integer(result[field]) == expected[field], f"incorrect {field}"
    assert abs(number(result["putamen_BP_ND_mean"])-expected["putamen_BP_ND_mean"]) <= SUMMARY_ATOL, "mean BP must recompute from all scans"
    rows = result["per_subject"]
    assert isinstance(rows, list) and len(rows) == 2 and all(isinstance(row, dict) for row in rows)
    assert {row["subject"] for row in rows} == {"sub-01", "sub-02"}, "exact two paired participants required"
    submitted = {row["subject"]: row for row in rows}
    for pair in expected["per_subject"]:
        row = submitted[pair["subject"]]
        assert row["status"] == pair["status"], "incorrect pair status"
        for field in ("baseline_BP_ND", "rescan_BP_ND", "absolute_difference", "pair_mean"):
            assert abs(number(row[field])-pair[field]) <= SUMMARY_ATOL, f"incorrect paired {field}"
        if pair["test_retest_pct"] is None:
            assert row["test_retest_pct"] is None, "nonpositive-mean pair percentage must be null"
        else:
            assert abs(number(row["test_retest_pct"])-pair["test_retest_pct"]) <= PERCENT_ATOL, "incorrect paired test-retest percentage"
    if expected["test_retest_pct"] is None:
        assert result["test_retest_pct"] is None, "group percentage requires both defined pairs"
    else:
        assert abs(number(result["test_retest_pct"])-expected["test_retest_pct"]) <= PERCENT_ATOL, "group percentage must be mean of both paired percentages"
    return expected


def validate_metadata(metadata, reference):
    assert metadata.get("status") == "ok", "metadata status must be ok"
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata["source_sha256"] == reference["stats"]["source_sha256"], "source hash mapping differs"
    observations = metadata["per_scan_observations"]
    assert isinstance(observations, list) and len(observations) == 4
    mapping = {}
    for row in observations:
        key = row["subject"], row["session"]
        assert key in SCANS and key not in mapping, "duplicate or foreign scan observation"
        mapping[key] = row
    for scan, key in enumerate(SCANS):
        mask = reference["frame_scan"] == scan; row = mapping[key]
        assert integer(row["n_frames"]) == int(mask.sum()), "incorrect source frame count"
        start, end = float(reference["frame_start_s"][mask][0]), float(reference["frame_end_s"][mask][-1])
        for field, value in (("start_s", start), ("end_s", end), ("duration_s", end-start)):
            near(number(row[field]), value, SOURCE_ATOL, SOURCE_RTOL, "incorrect source scan duration")


def validate_output_directory(output, reference):
    output = Path(output)
    frames = validate_frames(load_tac_fit(output / "tac_fit.csv"), reference)
    estimates = validate_estimates(load_estimates(output / "bp_estimates.csv"), frames, reference)
    summary = validate_results(read_json(output / "pet_results.json"), estimates)
    validate_metadata(read_json(output / "run_metadata.json"), reference)
    assert (output / "findings.md").read_text(encoding="utf-8").strip(), "nonempty findings required"
    return summary
