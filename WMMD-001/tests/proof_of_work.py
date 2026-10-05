"""Complete source-bound receipts for one public WLS diffusion configuration.

These are computational references, not independent diffusivity truth. No
correlation, physiological band, incomplete coverage or prose keyword can pass.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

PIPELINE_ID = "cfin-unsmoothed-wls-md-fa-v2"
CONFIGS = ("dki_all", "dti_lowb", "dti_all")
MD_UNITS = "1e-3 mm^2/s"
SIGNAL_FLOOR = 1e-4
REPORT_ATOL = REPORT_RTOL = 1e-6
PRED_ATOL, PRED_RTOL = 1e-5, 1e-6
METRICS = ("md", "fa", "S0_hat", "observed_b0", "normalization_scale",
           "nrmse", "log_rmse", "n_signal_floored", "n_eigenvalues_floored")
INTEGER_METRICS = {"n_signal_floored", "n_eigenvalues_floored"}
FILES = ("md_voxelwise.csv", "diffusivity.json", "run_metadata.json", "findings.md")


def finite(value, name):
    assert not isinstance(value, (bool, np.bool_)), f"{name}: boolean is not a number"
    try: result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise AssertionError(f"{name}: expected finite number") from exc
    assert np.isfinite(result), f"{name}: expected finite number"
    return result


def integer(value, name):
    value = finite(value, name)
    assert value.is_integer(), f"{name}: expected exact integer"
    return int(value)


def load_json(path):
    try: value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc: raise AssertionError(f"cannot read {path}") from exc
    assert isinstance(value, dict), f"{path}: expected object"
    return value


def design_matrix(bvals, bvecs, config):
    """Explicit DIPY 1.12.1 design convention, no b-vector renormalization."""
    assert config in CONFIGS
    b = np.asarray(bvals, float)
    g = np.asarray(bvecs, float)
    assert g.shape == (len(b), 3) and np.isfinite(b).all() and np.isfinite(g).all()
    x, y, z = g.T
    columns = [-b*x*x, -2*b*x*y, -b*y*y, -2*b*x*z, -2*b*y*z, -b*z*z]
    if config == "dki_all":
        powers = [(4,0,0),(0,4,0),(0,0,4),(3,1,0),(3,0,1),(1,3,0),(0,3,1),
                  (1,0,3),(0,1,3),(2,2,0),(2,0,2),(0,2,2),(2,1,1),(1,2,1),(1,1,2)]
        multiplicity = [1,1,1,4,4,4,4,4,4,6,6,6,12,12,12]
        columns += [b*b/6*m*x**a*y**c*z**d for (a,c,d), m in zip(powers, multiplicity)]
    columns.append(-np.ones(len(b)))
    return np.column_stack(columns)


def derive(beta, signal, design, bvals):
    """Reconstruct every required value from raw coefficients and source signal."""
    beta, signal, design = (np.asarray(value, float) for value in (beta, signal, design))
    assert beta.ndim == signal.ndim == design.ndim == 2
    assert beta.shape[0] == signal.shape[0] and beta.shape[1] == design.shape[1]
    assert signal.shape[1] == design.shape[0] == len(bvals)
    assert beta.shape[1] in (7, 22) and all(np.isfinite(value).all() for value in (beta, signal, design))
    assert np.all(design[:, -1] == -1), "design intercept must be -1"
    b0 = np.asarray(bvals) <= 50
    assert b0.any(), "source configuration requires b0"
    observed = np.mean(signal[:, b0], axis=1)
    scale = np.maximum(observed, SIGNAL_FLOOR)
    tensor = np.empty((len(beta), 3, 3))
    tensor[:, 0, 0], tensor[:, 1, 1], tensor[:, 2, 2] = beta[:, 0], beta[:, 2], beta[:, 5]
    tensor[:, 0, 1] = tensor[:, 1, 0] = beta[:, 1]
    tensor[:, 0, 2] = tensor[:, 2, 0] = beta[:, 3]
    tensor[:, 1, 2] = tensor[:, 2, 1] = beta[:, 4]
    eigenvalues, eigenvectors = np.linalg.eigh(tensor)
    floor = 1e-6 / (-float(design.min()))
    clipped = np.maximum(eigenvalues, floor)
    md_mm = np.mean(clipped, axis=1)
    fa = np.sqrt(1.5*np.sum((clipped-md_mm[:, None])**2, axis=1)/np.sum(clipped**2, axis=1))
    tensor_post = (eigenvectors*clipped[:, None, :]) @ np.swapaxes(eigenvectors, 1, 2)
    post = beta.copy()
    post[:, :6] = tensor_post[:, [0,0,1,0,1,2], [0,1,1,2,2,2]]
    with np.errstate(over="ignore", invalid="ignore"):
        s0 = np.exp(-beta[:, -1])
    assert np.isfinite(s0).all() and np.all(s0 > 0), "nonfinite/nonpositive coefficient-derived S0"
    predictions = np.empty(signal.shape)
    nrmse, log_rmse = np.empty(len(beta)), np.empty(len(beta))
    for start in range(0, len(beta), 512):
        end = min(start+512, len(beta))
        with np.errstate(over="ignore", invalid="ignore"):
            predicted = np.exp(post[start:end] @ design.T)
            raw_log_residual = beta[start:end] @ design.T - np.log(np.maximum(signal[start:end], SIGNAL_FLOOR))
            nrmse[start:end] = np.sqrt(np.mean((predicted-signal[start:end])**2, axis=1))/scale[start:end]
            log_rmse[start:end] = np.sqrt(np.mean(raw_log_residual**2, axis=1))
        assert np.isfinite(predicted).all(), "nonfinite post-floor signal prediction"
        predictions[start:end] = predicted / scale[start:end, None]
    result = {
        "md": md_mm*1000, "fa": fa, "S0_hat": s0, "observed_b0": observed,
        "normalization_scale": scale, "nrmse": nrmse, "log_rmse": log_rmse,
        "n_signal_floored": np.sum(signal < SIGNAL_FLOOR, axis=1),
        "n_eigenvalues_floored": np.sum(eigenvalues < floor, axis=1),
        "normalized_predictions": predictions,
    }
    assert all(np.isfinite(value).all() for value in result.values()), "nonfinite derived receipt"
    return result


def summarize(config, values):
    return {
        "status": "ok", "pipeline_id": PIPELINE_ID, "model_config": config,
        "md_units": MD_UNITS, "n_wm_voxels": len(values["md"]),
        **{key+"_mean": float(np.mean(values[key])) for key in ("md", "fa", "S0_hat", "nrmse", "log_rmse")},
        "n_signal_floored_total": int(np.sum(values["n_signal_floored"])),
        "n_eigenvalues_floored_total": int(np.sum(values["n_eigenvalues_floored"])),
        "n_voxels_signal_floored": int(np.count_nonzero(values["n_signal_floored"])),
        "n_voxels_eigenvalues_floored": int(np.count_nonzero(values["n_eigenvalues_floored"])),
    }


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
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert type(actual) is type(expected) and actual == expected, f"{name}: public recipe mismatch"
    else:
        tolerance = 1e-6 if any(key in name for key in ("affine", "voxel_size", "header_zoom")) else 1e-12*abs(expected)
        assert abs(finite(actual, name)-expected) <= tolerance, f"{name}: public recipe mismatch"


def match_summary(actual, expected):
    for key, value in expected.items():
        assert key in actual, f"summary missing {key}"
        if isinstance(value, str): assert actual[key] == value, f"summary {key} mismatch"
        elif isinstance(value, int): assert integer(actual[key], key) == value, f"summary {key} mismatch"
        else: assert np.isclose(finite(actual[key], key), value, atol=REPORT_ATOL, rtol=REPORT_RTOL), f"summary {key} is not derived from submitted rows"


def coefficient_match(beta, expected):
    tolerance = np.full(beta.shape[1], 1e-12)
    tolerance[:6] = 1e-10; tolerance[-1] = 1e-7
    assert np.all(np.abs(beta-expected) <= tolerance + 1e-6*np.abs(expected)), "raw coefficients differ from declared source model"


def validate_reference(reference):
    stats = reference["stats"]
    assert stats["pipeline_id"] == PIPELINE_ID, "obsolete reference pipeline"
    assert set(stats["metadata_by_config"]) == set(CONFIGS)
    assert set(stats["results_by_config"]) == set(CONFIGS)
    ijk, signal = reference["ijk"], reference["signal"]
    assert ijk.ndim == 2 and ijk.shape[1] == 3 and ijk.dtype.kind in "iu"
    assert len(ijk) > 0 and len(set(map(tuple, ijk))) == len(ijk) and np.all(ijk >= 0)
    assert signal.shape == (len(ijk), len(reference["bvals"])) and np.isfinite(signal).all()
    assert reference["bvecs"].shape == (len(reference["bvals"]), 3)
    assert integer(stats["n_brain_voxels"], "bank brain count") >= len(ijk)
    for config in CONFIGS:
        expected_indices = np.flatnonzero(np.round(reference["bvals"], -2) <= 1000) if config == "dti_lowb" else np.arange(len(reference["bvals"]))
        entry = reference["configs"][config]
        assert np.array_equal(entry["indices"], expected_indices), "reference source shell membership mismatch"
        expected_design = design_matrix(reference["bvals"][expected_indices], reference["bvecs"][expected_indices], config)
        assert entry["design"].shape == expected_design.shape and np.allclose(entry["design"], expected_design, atol=1e-10, rtol=1e-12), "reference design convention mismatch"
        assert entry["beta"].shape == (len(ijk), expected_design.shape[1])
        derived = derive(entry["beta"], signal[:, expected_indices], entry["design"], reference["bvals"][expected_indices])
        for key in METRICS:
            assert entry[key].shape == (len(ijk),) and np.isfinite(entry[key]).all()
            if key in INTEGER_METRICS: assert np.array_equal(entry[key], derived[key]), f"reference {key} mismatch"
            else: assert np.allclose(entry[key], derived[key], atol=1e-10, rtol=1e-9), f"reference {key} arithmetic mismatch"
        contract = stats["metadata_by_config"][config]
        assert contract["pipeline_id"] == PIPELINE_ID and contract["model_config"] == config
        assert contract["source_sha256"] == stats["source_sha256"]
        match_summary(stats["results_by_config"][config], summarize(config, entry))
        entry["normalized_predictions"] = derived["normalized_predictions"]
    reference["index"] = {tuple(int(v) for v in xyz): index for index, xyz in enumerate(ijk)}
    return reference


def load_reference(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("reference.npz")
    try:
        with np.load(path, allow_pickle=False) as bank:
            reference = {"ijk": bank["ref_roi_ijk"], "signal": bank["ref_signal"],
                         "bvals": bank["ref_bvals"], "bvecs": bank["ref_bvecs"],
                         "stats": json.loads(str(bank["ref_stats"].item())), "configs": {}}
            for config in CONFIGS:
                reference["configs"][config] = {"indices": bank["volume_indices_"+config], "design": bank["design_"+config],
                                                "beta": bank["beta_"+config], **{key: bank[key+"_"+config] for key in METRICS}}
    except (OSError, ValueError, KeyError) as exc: raise AssertionError("missing, corrupt or obsolete measured reference bank") from exc
    return validate_reference(reference)


def require_files(output):
    for name in FILES: assert (Path(output)/name).is_file(), f"missing required output {name}"
    assert (Path(output)/"findings.md").read_text(encoding="utf-8-sig").strip(), "empty findings.md"


def read_voxel_table(path, reference, config):
    p = reference["configs"][config]["beta"].shape[1]
    columns = ["i", "j", "k", *METRICS, *[f"beta_{j}" for j in range(p)]]
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames is not None, "missing voxel CSV header"
        reader.fieldnames = [key.strip() for key in reader.fieldnames]
        assert len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate CSV column"
        assert set(columns) <= set(reader.fieldnames), "missing required voxel CSV columns"
        found = {}
        for row in reader:
            if not any(str(value or "").strip() for value in row.values()): continue
            key = tuple(integer(row[c], "voxel "+c) for c in ("i", "j", "k"))
            assert key not in found, "duplicate voxel coordinates"
            assert key in reference["index"], "voxel outside complete source ROI"
            values = {name: finite(row[name], name) for name in columns[3:]}
            for name in INTEGER_METRICS:
                values[name] = integer(row[name], name)
                assert values[name] >= 0, "negative floor count"
            found[key] = values
    assert set(found) == set(reference["index"]), "voxel table must cover every source ROI voxel exactly once"
    ordered = [found[tuple(int(v) for v in xyz)] for xyz in reference["ijk"]]
    return {"beta": np.array([[row[f"beta_{j}"] for j in range(p)] for row in ordered]),
            **{name: np.array([row[name] for row in ordered]) for name in METRICS}}


def validate_voxel_receipt(table, reference, config):
    entry = reference["configs"][config]
    coefficient_match(table["beta"], entry["beta"])
    indices = entry["indices"]
    derived = derive(table["beta"], reference["signal"][:, indices], entry["design"], reference["bvals"][indices])
    for key in METRICS:
        if key in INTEGER_METRICS:
            assert np.array_equal(table[key], derived[key]), f"{key} does not match source/coefficient floor count"
        elif key == "S0_hat":
            assert np.allclose(table[key]/derived["normalization_scale"], derived[key]/derived["normalization_scale"], atol=REPORT_ATOL, rtol=REPORT_RTOL), "S0_hat not derived from raw intercept"
        else:
            assert np.allclose(table[key], derived[key], atol=REPORT_ATOL, rtol=REPORT_RTOL), f"{key} not derived from source signal and raw coefficients"
    assert np.allclose(derived["normalized_predictions"], entry["normalized_predictions"], atol=PRED_ATOL, rtol=PRED_RTOL), "normalized predictions differ from declared source model"
    return derived


def validate_summaries(output, table, reference, config):
    output = Path(output)
    match_summary(load_json(output/"diffusivity.json"), summarize(config, table))
    metadata = load_json(output/"run_metadata.json")
    match_metadata(metadata, reference["stats"]["metadata_by_config"][config])
    assert metadata.get("status") == "ok"
    assert integer(metadata.get("n_wm_voxels"), "n_wm_voxels") == len(reference["ijk"])
    assert integer(metadata.get("n_brain_voxels"), "n_brain_voxels") == reference["stats"]["n_brain_voxels"]


def read_submission(output, reference):
    result = load_json(Path(output)/"diffusivity.json")
    config = result.get("model_config")
    assert config in CONFIGS, "declare one public model_config"
    assert result.get("md_units") == MD_UNITS, "explicit MD units must be 1e-3 mm^2/s; no magnitude guessing"
    return config, read_voxel_table(Path(output)/"md_voxelwise.csv", reference, config)


def validate_output_directory(output, reference):
    require_files(output)
    config, table = read_submission(output, reference)
    validate_voxel_receipt(table, reference, config)
    validate_summaries(output, table, reference, config)
    return config, table
