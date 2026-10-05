"""Source-bound computational model receipts, not microstructural ground truth.

All selected models cover the full source-defined ROI. Numerical reconstruction
is independent of the solution; no correlation, outcome band or prose gate is
used. The legacy reference bank is deliberately rejected.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

PIPELINE_ID = "sherbrooke-proxy-fa-v2"
MODELS = ("fwdti", "dti_b2000", "dti_b1000")
TENSOR_FIELDS = ("Dxx", "Dxy", "Dyy", "Dxz", "Dyz", "Dzz")
FILES = ("fa_voxelwise.csv", "fa_sweep.csv", "fit_parameters.csv", "results.json",
         "run_metadata.json", "findings.md")
REPORT_ATOL = REPORT_RTOL = 1e-6
PARAM_RTOL = 1e-5
D_ATOL = 1e-8
FA_ATOL = S0_ATOL = PRED_ATOL = 1e-5
STATUSES = ("ok", "invalid_input", "insufficient_signal", "md_threshold",
            "initialization_failed", "high_initial_fraction", "optimizer_failed",
            "nonfinite_candidate", "decomposition_failed")
BOOL_FIELDS = ("fit_attempted", "eligible", "common_valid", "boundary_f_low", "boundary_f_high")
INT_FIELDS = ("nfev", "n_signal_floored")
FLOAT_FIELDS = (*TENSOR_FIELDS, "neg_log_S0", "S0_hat", "f", "fa", "md", "sse", "nrmse",
                "n_eigenvalues_clipped", "optimizer_status", "init_f", "init_md", "observed_b0", "normalization_scale")
TABLE_COLUMNS = ("i", "j", "k", "model", "status", *BOOL_FIELDS, *INT_FIELDS, *FLOAT_FIELDS)
MEAN_FIELDS = ("fa", "md", "f", "S0_hat", "nrmse")


def finite(value, name):
    assert not isinstance(value, (bool, np.bool_)), f"{name}: boolean is not a number"
    try: result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AssertionError(f"{name}: expected finite number") from exc
    assert np.isfinite(result), f"{name}: expected finite number"
    return result


def integer(value, name):
    result = finite(value, name)
    assert result.is_integer(), f"{name}: expected exact integer"
    return int(result)


def boolean(value, name):
    if isinstance(value, (bool, np.bool_)): return bool(value)
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ("true", "1"): return True
        if value in ("false", "0"): return False
    raise AssertionError(f"{name}: expected boolean")


def optional_number(value, name):
    if value is None or (isinstance(value, str) and not value.strip()): return np.nan
    return finite(value, name)


def load_json(path):
    try: obj = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc: raise AssertionError(f"cannot read {path}") from exc
    assert isinstance(obj, dict), f"{path}: expected JSON object"
    return obj


def read_csv(path, columns):
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames is not None, "missing CSV header"
            reader.fieldnames = [str(key).strip() for key in reader.fieldnames]
            assert len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate CSV column"
            assert set(columns) <= set(reader.fieldnames), f"missing required columns in {Path(path).name}"
            rows = []
            for row in reader:
                assert None not in row, "CSV row has extra unlabelled cells"
                if not any(str(v or "").strip() for v in row.values()): continue
                assert all(row.get(key) is not None for key in columns), "truncated CSV row"
                rows.append({key: value.strip() if isinstance(value, str) else value for key, value in row.items()})
    except OSError as exc: raise AssertionError(f"cannot read {path}") from exc
    return rows


def coordinate(row):
    return tuple(integer(row[key], "voxel "+key) for key in ("i", "j", "k"))


def match_metadata(actual, expected, name="metadata"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{name}: expected object"
        if name.endswith("source_sha256") or name.endswith("input_hashes"):
            assert actual == expected, f"{name}: source hash set mismatch"
            return
        for key, value in expected.items():
            assert key in actual, f"{name}: missing {key}"
            match_metadata(actual[key], value, name+"."+key)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{name}: list mismatch"
        for index, value in enumerate(expected): match_metadata(actual[index], value, f"{name}[{index}]")
    elif expected is None or isinstance(expected, (bool, str)):
        assert type(actual) is type(expected) and actual == expected, f"{name}: public recipe mismatch"
    else:
        tolerance = 1e-6 if any(key in name for key in ("affine", "header_zoom", "voxel_size")) else 1e-12*abs(expected)
        assert abs(finite(actual, name)-expected) <= tolerance, f"{name}: public recipe mismatch"


def match_summary(actual, expected, name="summary"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{name}: expected object"
        if name.endswith("status_counts") or ".status_counts_by_model." in name:
            assert set(actual) <= set(STATUSES), f"{name}: unknown status"
            actual = {status: actual.get(status, 0) for status in STATUSES}
        if name.endswith("by_model") or name.endswith("paired_fa_differences") or name.endswith("status_counts"):
            assert set(actual) == set(expected), f"{name}: key set mismatch"
        for key, value in expected.items():
            assert key in actual, f"{name}: missing {key}"
            match_summary(actual[key], value, name+"."+key)
    elif expected is None or isinstance(expected, (bool, str)):
        assert type(actual) is type(expected) and actual == expected, f"{name}: mismatch"
    elif isinstance(expected, int):
        assert integer(actual, name) == expected, f"{name}: count mismatch"
    else:
        assert np.isclose(finite(actual, name), expected, atol=REPORT_ATOL, rtol=REPORT_RTOL), f"{name}: not derived from submitted rows"


def design_matrix(bvals, bvecs):
    """DIPY tensor lower-triangle convention; do not renormalize source b-vectors."""
    b, g = np.asarray(bvals, float), np.asarray(bvecs, float)
    assert g.shape == (len(b), 3) and np.isfinite(b).all() and np.isfinite(g).all()
    x, y, z = g.T
    return np.column_stack((-b*x*x, -2*b*x*y, -b*y*y, -2*b*x*z,
                            -2*b*y*z, -b*z*z, -np.ones(len(b))))


def model_indices(bvals, model):
    assert model in MODELS, "unknown model"
    b = np.asarray(bvals, float)
    membership = ((b >= -1) & (b <= 50)) | ((b >= 950) & (b <= 1050))
    if model != "dti_b1000": membership |= (b >= 1950) & (b <= 2050)
    return np.flatnonzero(membership)


def raw_to_tensor(raw):
    raw = np.asarray(raw, float)
    assert raw.shape[-1] == 6
    tensor = np.empty(raw.shape[:-1]+(3, 3))
    tensor[..., 0, 0], tensor[..., 1, 1], tensor[..., 2, 2] = raw[..., 0], raw[..., 2], raw[..., 5]
    tensor[..., 0, 1] = tensor[..., 1, 0] = raw[..., 1]
    tensor[..., 0, 2] = tensor[..., 2, 0] = raw[..., 3]
    tensor[..., 1, 2] = tensor[..., 2, 1] = raw[..., 4]
    return tensor


def require_files(output):
    for name in FILES: assert (Path(output)/name).is_file(), f"missing required output {name}"
    assert (Path(output)/"findings.md").read_text(encoding="utf-8-sig").strip(), "empty findings.md"


def derive(raw_beta, fraction, signal, design, bvals, model):
    """Independent raw-signal prediction and clipped-tensor summary algebra.

    Undefined candidates remain NaN. No residual or condition-number threshold
    changes support; no eigenvector or transformed-fraction identity is tested.
    """
    beta, fraction, signal = np.asarray(raw_beta, float), np.asarray(fraction, float), np.asarray(signal, float)
    design, bvals = np.asarray(design, float), np.asarray(bvals, float)
    assert beta.shape == (len(signal), 7) and fraction.shape == (len(signal),)
    assert signal.shape[1] == len(bvals) == len(design)
    assert design.shape[1] == 7 and np.isfinite(signal).all() and np.isfinite(design).all()
    assert np.all(design[:, -1] == -1) and np.any(bvals <= 50)
    n = len(signal)
    observed = np.mean(signal[:, bvals <= 50], axis=1)
    scale = np.maximum(observed, 1e-6)
    result = {key: np.full(n, np.nan) for key in ("S0_hat", "fa", "md", "sse", "nrmse", "n_eigenvalues_clipped")}
    predictions = np.full(signal.shape, np.nan)
    tensor_nonzero = np.zeros(n, bool)
    finite_beta = np.isfinite(beta).all(axis=1) & np.isfinite(fraction)
    eigenfloor = 0. if model == "fwdti" else 1e-6/(-float(design.min()))
    if finite_beta.any():
        rows = np.flatnonzero(finite_beta)
        eigenvalues = np.linalg.eigvalsh(raw_to_tensor(beta[rows, :6]))
        clipped = np.maximum(eigenvalues, eigenfloor)
        md = clipped.mean(axis=1)
        denominator = np.sum(clipped**2, axis=1)
        fa = np.zeros(len(rows))
        nonzero = denominator > 0
        fa[nonzero] = np.sqrt(1.5*np.sum((clipped[nonzero]-md[nonzero, None])**2, axis=1)/denominator[nonzero])
        result["md"][rows], result["fa"][rows] = md, fa
        result["n_eigenvalues_clipped"][rows] = np.sum(eigenvalues < eigenfloor, axis=1)
        tensor_nonzero[rows] = nonzero
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        s0 = np.exp(-beta[:, 6])
    result["S0_hat"][finite_beta & np.isfinite(s0)] = s0[finite_beta & np.isfinite(s0)]
    candidates = finite_beta
    for start in range(0, n, 512):
        rows = np.flatnonzero(candidates[start:start+512])+start
        if not len(rows): continue
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            tissue = np.exp(beta[rows] @ design.T)
            # Preserve the source-gradient norms, exactly as the pinned design
            # does; the corrected b-vectors are not renormalized a second time.
            isotropic_exponent = .003*design[:, [0,2,5]].sum(axis=1)
            predicted = tissue*(1-fraction[rows, None]) + s0[rows, None]*fraction[rows, None]*np.exp(isotropic_exponent[None, :])
            sse = np.sum((predicted-signal[rows])**2, axis=1)
        predictions[rows] = np.where(np.isfinite(predicted), predicted/scale[rows, None], np.nan)
        good = np.isfinite(predicted).all(axis=1) & np.isfinite(sse) & np.isfinite(s0[rows]) & (s0[rows] > 0)
        rows, predicted, sse = rows[good], predicted[good], sse[good]
        predictions[rows] = predicted/scale[rows, None]
        result["sse"][rows] = sse
        result["nrmse"][rows] = np.sqrt(sse/len(bvals))/scale[rows]
    minimum = 1e-6 if model == "fwdti" else 1e-4
    result.update(observed_b0=observed, normalization_scale=scale,
                  n_signal_floored=np.sum(signal < minimum, axis=1),
                  normalized_predictions=predictions, tensor_nonzero=tensor_nonzero,
                  boundary_f_low=finite_beta & (fraction <= 1e-6),
                  boundary_f_high=finite_beta & (fraction >= 1-1e-6))
    return result


def summary_values(entry, support):
    return {key+"_mean": float(np.mean(entry[key][support])) if support.any() else None for key in MEAN_FIELDS}


def summarize(main_model, entries):
    assert main_model in entries and 2 <= len(entries) <= 3 and set(entries) <= set(MODELS)
    n = len(next(iter(entries.values()))["eligible"])
    common = np.logical_and.reduce([entry["eligible"] for entry in entries.values()])
    by_model = {}
    for model, entry in entries.items():
        counts = {status: int(np.count_nonzero(entry["status"] == status)) for status in STATUSES}
        clipped = entry["n_eigenvalues_clipped"]
        by_model[model] = dict(summary_values(entry, entry["eligible"]), n_valid=int(entry["eligible"].sum()),
                              status_counts=counts,
                              n_eigenvalues_clipped_total=int(np.nansum(clipped)),
                              n_voxels_eigenvalues_clipped=int(np.count_nonzero(clipped > 0)))
    models = sorted(entries)
    differences = {f"{right}_minus_{left}": float(np.mean(entries[right]["fa"][common]-entries[left]["fa"][common])) if common.any() else None
                   for index, left in enumerate(models) for right in models[index+1:]}
    return {"status": "ok", "pipeline_id": PIPELINE_ID, "main_model": main_model,
            "n_roi_voxels": n, "n_common_valid": int(common.sum()),
            "fa_proxy_roi": by_model[main_model]["fa_mean"], "by_model": by_model,
            "common_valid": {"n_voxels": int(common.sum()), "by_model": {model: summary_values(entry, common) for model, entry in entries.items()},
                             "paired_fa_differences": differences}}


def match_numbers(actual, expected, name, atol=REPORT_ATOL, rtol=REPORT_RTOL):
    actual, expected = np.asarray(actual), np.asarray(expected)
    assert actual.shape == expected.shape, f"{name}: shape mismatch"
    assert np.array_equal(np.isfinite(actual), np.isfinite(expected)), f"{name}: unavailable-value pattern mismatch"
    good = np.isfinite(expected)
    assert np.allclose(actual[good], expected[good], atol=atol, rtol=rtol), f"{name}: numeric mismatch"


def entry_beta(entry):
    return np.column_stack([entry[key] for key in (*TENSOR_FIELDS, "neg_log_S0")])


def validate_entry(entry, reference, model, compare_reference=True):
    expected = reference["models"][model]
    n = len(reference["ijk"])
    assert all(np.asarray(entry[key]).shape == (n,) for key in ("status", *BOOL_FIELDS, *INT_FIELDS, *FLOAT_FIELDS)), "incomplete model receipt"
    assert set(entry["status"]) <= set(STATUSES), "unknown fit status"
    beta = entry_beta(entry)
    indices, design = expected["indices"], expected["design"]
    derived = derive(beta, entry["f"], reference["signal"][:, indices], design, reference["bvals"][indices], model)
    if compare_reference:
        assert np.array_equal(entry["status"], expected["status"]), "fit status differs from declared source recipe"
        assert np.array_equal(entry["fit_attempted"], expected["fit_attempted"]), "attempt status differs from source recipe"
        match_numbers(beta[:, :6], entry_beta(expected)[:, :6], "source raw tensor", D_ATOL, PARAM_RTOL)
        match_numbers(entry["f"], expected["f"], "source fraction", FA_ATOL, PARAM_RTOL)
        match_numbers(entry["fa"], expected["fa"], "source FA", FA_ATOL, PARAM_RTOL)
        match_numbers(derived["S0_hat"]/derived["normalization_scale"], expected["S0_hat"]/derived["normalization_scale"], "source fitted S0", S0_ATOL, PARAM_RTOL)
        for key in ("init_f", "init_md"):
            match_numbers(entry[key], expected[key], "source "+key, D_ATOL if key == "init_md" else FA_ATOL, PARAM_RTOL)
        match_numbers(derived["normalized_predictions"], expected["normalized_predictions"], "source normalized prediction", PRED_ATOL, 0.)
    for key in ("fa", "md", "sse", "nrmse", "observed_b0", "normalization_scale", "S0_hat"):
        actual, target = entry[key], derived[key]
        if key == "S0_hat": actual, target = actual/derived["normalization_scale"], target/derived["normalization_scale"]
        if key == "sse": actual, target = actual/derived["normalization_scale"]**2, target/derived["normalization_scale"]**2
        match_numbers(actual, target, "reconstructed "+key, D_ATOL if key == "md" else REPORT_ATOL, REPORT_RTOL)
    for key in ("n_signal_floored", "n_eigenvalues_clipped"):
        match_numbers(entry[key], derived[key], "reconstructed "+key, 0, 0)
    for key in ("boundary_f_low", "boundary_f_high"):
        assert np.array_equal(entry[key], derived[key]), f"{key}: not derived from submitted fraction"
    ok = entry["status"] == "ok"
    successful = np.ones(n, bool) if model != "fwdti" else np.isin(entry["optimizer_status"], (1,2,3,4))
    finite_candidate = np.isfinite(beta).all(axis=1) & np.isfinite(entry["f"]) & (entry["f"] >= 0) & (entry["f"] <= 1) & np.isfinite(derived["S0_hat"]) & (derived["S0_hat"] > 0) & np.isfinite(derived["normalized_predictions"]).all(axis=1)
    assert np.all(finite_candidate[ok]), "ok status requires finite admissible candidate/predictions"
    eligible = ok & entry["fit_attempted"] & successful & np.isfinite(beta).all(axis=1) & np.isfinite(entry["f"]) & (entry["f"] >= 0) & (entry["f"] < 1) & (derived["S0_hat"] > 0) & np.isfinite(derived["normalized_predictions"]).all(axis=1) & np.isfinite(derived["sse"]) & derived["tensor_nonzero"]
    assert np.array_equal(entry["eligible"], eligible), "eligibility does not follow public status/candidate rule"
    assert np.all(entry["nfev"] >= 0), "negative optimizer nfev"
    unattempted = ~entry["fit_attempted"]
    assert not np.any(ok & unattempted), "ok cannot be unattempted"
    assert np.all(entry["nfev"][unattempted] == 0) and np.all(np.isnan(entry["optimizer_status"][unattempted])), "unattempted optimizer diagnostics"
    assert np.all(np.isnan(beta[unattempted])) and np.all(np.isnan(entry["f"][unattempted])), "unattempted final candidate must be blank"
    if model == "fwdti":
        assert np.all(successful[ok]) and np.all(entry["nfev"][ok] > 0), "successful free-water solver diagnostics"
        attempted_status = entry["optimizer_status"][entry["fit_attempted"]]
        assert np.all(np.isnan(attempted_status) | ((attempted_status == np.floor(attempted_status)) & (attempted_status >= 0) & (attempted_status <= 8))), "invalid MINPACK status"
        assert not np.any((entry["status"] == "optimizer_failed") & successful), "failed solver reports convergence"
    else:
        assert np.all(np.isnan(entry["optimizer_status"])) and np.all(entry["nfev"] == 0), "DTI has no nonlinear optimizer diagnostics"
        assert np.all(entry["f"][np.isfinite(entry["f"])] == 0), "single-tensor fraction must be zero"
    return derived


def read_parameter_table(output, reference):
    found = {}
    for row in read_csv(Path(output)/"fit_parameters.csv", TABLE_COLUMNS):
        model, xyz = row["model"], coordinate(row)
        assert model in MODELS, "unknown model group"
        assert xyz in reference["index"], "voxel outside source ROI"
        group = found.setdefault(model, {})
        assert xyz not in group, "duplicate model/voxel row"
        group[xyz] = {"status": row["status"], **{key: boolean(row[key], key) for key in BOOL_FIELDS},
                      **{key: integer(row[key], key) for key in INT_FIELDS},
                      **{key: optional_number(row[key], key) for key in FLOAT_FIELDS}}
    assert 2 <= len(found) <= 3, "select two or three valid models"
    entries = {}
    for model, group in found.items():
        assert set(group) == set(reference["index"]), "every selected model must cover complete source ROI"
        rows = [group[tuple(xyz)] for xyz in reference["ijk"]]
        entries[model] = {key: np.asarray([row[key] for row in rows]) for key in ("status", *BOOL_FIELDS, *INT_FIELDS, *FLOAT_FIELDS)}
    return entries


def validate_fa_tables(output, entries, main_model, reference):
    for filename, groups in (("fa_voxelwise.csv", [main_model]), ("fa_sweep.csv", list(entries))):
        sweep = filename == "fa_sweep.csv"
        found = {model: {} for model in groups}
        columns = ("i", "j", "k", "fa", "model") if sweep else ("i", "j", "k", "fa")
        for row in read_csv(Path(output)/filename, columns):
            model, xyz = row["model"] if sweep else main_model, coordinate(row)
            assert model in found, "FA table contains undeclared model"
            assert xyz in reference["index"], "FA table voxel outside source ROI"
            assert xyz not in found[model], "duplicate FA model/voxel row"
            found[model][xyz] = optional_number(row["fa"], "fa")
        for model, group in found.items():
            assert set(group) == set(reference["index"]), "FA table must retain complete source ROI"
            values = np.array([group[tuple(xyz)] for xyz in reference["ijk"]])
            match_numbers(values, entries[model]["fa"], "FA cross-file consistency", REPORT_ATOL, REPORT_RTOL)


def validate_output_directory(output, reference):
    output = Path(output)
    require_files(output)
    entries = read_parameter_table(output, reference)
    result, metadata = load_json(output/"results.json"), load_json(output/"run_metadata.json")
    main = result.get("main_model")
    assert main in entries, "main_model must be selected"
    for model, entry in entries.items(): validate_entry(entry, reference, model)
    common = np.logical_and.reduce([entry["eligible"] for entry in entries.values()])
    for entry in entries.values(): assert np.array_equal(entry["common_valid"], common), "common_valid must intersect the selected models only"
    validate_fa_tables(output, entries, main, reference)
    expected = summarize(main, entries)
    match_summary(result, expected)
    match_metadata(metadata, reference["stats"]["metadata_contract"])
    assert metadata.get("status") == "ok" and metadata.get("main_model") == main, "metadata status/main mismatch"
    fitted = metadata.get("fitted_models")
    assert isinstance(fitted, list) and len(fitted) == len(entries) and set(fitted) == set(entries), "metadata fitted_models mismatch"
    for key in ("n_roi_voxels", "n_common_valid"):
        assert integer(metadata.get(key), key) == expected[key], f"metadata {key} mismatch"
    for key in ("n_brain_voxels", "n_seed_voxels"):
        assert integer(metadata.get(key), key) == reference["stats"][key], f"metadata {key} mismatch"
    match_summary(metadata.get("status_counts_by_model"), {model: values["status_counts"] for model, values in expected["by_model"].items()}, "metadata.status_counts_by_model")
    return main, entries


def validate_reference(reference):
    stats = reference["stats"]
    assert stats.get("pipeline_id") == PIPELINE_ID, "obsolete reference pipeline; genuine v2 regeneration required"
    ijk, signal, bvals, bvecs = (reference[key] for key in ("ijk", "signal", "bvals", "bvecs"))
    assert ijk.ndim == 2 and ijk.shape[1] == 3 and ijk.dtype.kind in "iu"
    assert len(ijk) > 0 and np.all(ijk >= 0) and len(set(map(tuple, ijk))) == len(ijk), "invalid reference ROI"
    assert signal.shape == (len(ijk), len(bvals)) and np.isfinite(signal).all(), "invalid reference source signals"
    assert bvecs.shape == (len(bvals), 3) and np.isfinite(bvals).all() and np.isfinite(bvecs).all()
    assert set(reference["models"]) == set(MODELS), "reference requires all three genuine model receipts"
    contract = stats["metadata_contract"]
    assert contract["pipeline_id"] == PIPELINE_ID
    assert contract["source_sha256"] == stats["source_sha256"], "reference source hash mismatch"
    assert integer(stats["n_brain_voxels"], "brain count") >= len(ijk)
    assert integer(stats["n_seed_voxels"], "seed count") > 0
    reference["index"] = {tuple(int(v) for v in xyz): index for index, xyz in enumerate(ijk)}
    for model, entry in reference["models"].items():
        indices = model_indices(bvals, model)
        assert np.array_equal(entry["indices"], indices), "reference source shell membership mismatch"
        design = design_matrix(bvals[indices], bvecs[indices])
        assert entry["design"].shape == design.shape and np.allclose(entry["design"], design, atol=1e-10, rtol=1e-12), "reference design convention mismatch"
        for key in BOOL_FIELDS: assert entry[key].dtype.kind == "b", f"reference {key} must be boolean"
        for key in INT_FIELDS: assert entry[key].dtype.kind in "iu", f"reference {key} must be integer"
        derived = validate_entry(entry, reference, model, compare_reference=False)
        entry["normalized_predictions"] = derived["normalized_predictions"]
    common = np.logical_and.reduce([entry["eligible"] for entry in reference["models"].values()])
    assert all(np.array_equal(entry["common_valid"], common) for entry in reference["models"].values()), "reference common support mismatch"
    result = stats["results"]
    match_summary(result, summarize(result["main_model"], reference["models"]))
    return reference


def load_reference(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("reference.npz")
    try:
        with np.load(path, allow_pickle=False) as bank:
            stats = json.loads(str(bank["ref_stats"].item()))
            assert stats.get("pipeline_id") == PIPELINE_ID, "obsolete reference pipeline; genuine v2 regeneration required"
            reference = {"ijk": bank["ref_roi_ijk"], "signal": bank["ref_signal"],
                         "bvals": bank["ref_bvals"], "bvecs": bank["ref_bvecs"], "stats": stats, "models": {}}
            for model in MODELS:
                reference["models"][model] = {"indices": bank["volume_indices_"+model], "design": bank["design_"+model],
                    **{key: bank[key+"_"+model] for key in ("status", *BOOL_FIELDS, *INT_FIELDS, *FLOAT_FIELDS)}}
    except (OSError, ValueError, KeyError) as exc:
        raise AssertionError("missing, corrupt or obsolete measured reference bank") from exc
    return validate_reference(reference)
