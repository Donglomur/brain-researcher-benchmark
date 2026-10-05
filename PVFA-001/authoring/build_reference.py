"""Build a v2 bank only from a genuine full three-model source execution.

This command rechecks original input bytes and repeats public ROI preprocessing,
not the three final model fits. It verifies full source/receipt algebra and DTI
WLS normal equations. Independent nonlinear fit checks remain a separate gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK/"tests"))
import proof_of_work as q


def load_oracle():
    sys.path.insert(0, str(TASK/"solution"))
    spec = importlib.util.spec_from_file_location("pvfa_source_authoring", TASK/"solution/compute.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    return oracle


def check_wls(design, signal, beta):
    """Necessary full-receipt weighted normal equations, not independent refits."""
    good = np.isfinite(beta).all(axis=1)
    inverse = np.linalg.pinv(design, rcond=1e-15)
    maximum = 0.
    for start in range(0, len(signal), 256):
        use = good[start:start+256]
        if not use.any(): continue
        observed = signal[start:start+256][use]
        coefficients = beta[start:start+256][use]
        logs = np.log(np.maximum(observed, 1e-4))
        weights = np.exp((logs @ inverse.T) @ design.T)
        assert np.isfinite(weights).all() and np.all(weights > 0)
        weighted_design = weights[:, :, None]*design[None, :, :]
        residual = weights*(coefficients @ design.T-logs)
        gradient = np.einsum("nmp,nm->np", weighted_design, residual)
        denominator = np.linalg.norm(weighted_design, axis=(1,2))*np.linalg.norm(weights*logs, axis=1)
        error = np.linalg.norm(gradient, axis=1)/np.maximum(denominator, np.finfo(float).tiny)
        maximum = max(maximum, float(error.max()))
    assert maximum < 1e-10, "retained DTI coefficients violate WLS normal equations"
    return maximum


def model_entry(receipt, model):
    beta = receipt["beta_"+model]
    entry = {"indices": receipt["signal_indices_"+model], "design": receipt["design_"+model],
             "common_valid": receipt["common_valid"]}
    entry.update({key: beta[:, index] for index, key in enumerate((*q.TENSOR_FIELDS,"neg_log_S0"))})
    for key in ("status", *q.BOOL_FIELDS, *q.INT_FIELDS, *q.FLOAT_FIELDS):
        if key not in entry: entry[key] = receipt[key+"_"+model]
    return entry


def assert_same(actual, expected, name):
    actual, expected = np.asarray(actual), np.asarray(expected)
    assert actual.shape == expected.shape, f"{name}: receipt/source shape mismatch"
    if expected.dtype.kind in "fc":
        assert np.array_equal(actual, expected, equal_nan=True), f"{name}: receipt/source value mismatch"
    else:
        assert np.array_equal(actual, expected), f"{name}: receipt/source value mismatch"


def build(data, output, bank, template):
    output = Path(output)
    oracle = load_oracle()
    oracle.check_versions()
    inputs = oracle.load_inputs(data)
    contract = oracle.metadata_contract(inputs)
    assert q.load_json(template) == contract, "public template differs from source recipe"
    result, metadata = q.load_json(output/"results.json"), q.load_json(output/"run_metadata.json")
    assert result["status"] == metadata["status"] == "ok", "a pilot/failure is not a full bank"
    assert set(metadata["fitted_models"]) == set(q.MODELS), "authoring requires all three genuine fits"
    prepared = oracle.prepare_source(inputs)
    reference = {"ijk": prepared["roi_ijk"], "signal": prepared["signal"],
                 "bvals": prepared["bvals"], "bvecs": prepared["bvecs"], "models": {},
                 "stats": {"pipeline_id": q.PIPELINE_ID, "source_sha256": inputs["hashes"],
                           "metadata_contract": contract, "n_brain_voxels": prepared["n_brain_voxels"],
                           "n_seed_voxels": prepared["n_seed_voxels"], "results": result,
                           "authoring_evidence": {"public_source_preprocessing_repeated": True,
                             "all_source_predictions_reconstructed": True,
                             "all_DTI_weighted_normal_equations_checked": True,
                             "all_nonlinear_fits_independently_repeated": False},
                           "wls_normal_equation_max_relative": {}}}
    with np.load(output/"analysis_arrays.npz", allow_pickle=False) as receipt:
        assert str(receipt["pipeline_id"].item()) == q.PIPELINE_ID
        assert json.loads(str(receipt["metadata_json"].item())) == metadata
        assert json.loads(str(receipt["results_json"].item())) == result
        assert_same(receipt["full_roi_ijk"], prepared["roi_ijk"], "full ROI")
        assert_same(receipt["selected_roi_indices"], np.arange(len(prepared["roi_ijk"])), "complete selection")
        for key, expected in prepared.items():
            assert_same(receipt[key], expected, key)
        for model in q.MODELS:
            entry = model_entry(receipt, model)
            reference["models"][model] = entry
            indices = q.model_indices(reference["bvals"], model)
            assert_same(entry["indices"], indices, model+" source indices")
            design = q.design_matrix(reference["bvals"][indices], reference["bvecs"][indices])
            assert np.allclose(entry["design"], design, atol=1e-10, rtol=1e-12)
            derived = q.derive(q.entry_beta(entry), entry["f"], reference["signal"][:,indices],
                               design, reference["bvals"][indices], model)
            scale = derived["normalization_scale"][:,None]
            q.match_numbers(receipt["prediction_"+model]/scale, derived["normalized_predictions"],
                            model+" private prediction", 1e-10, 1e-10)
            expected_residual = reference["signal"][:,indices]-receipt["prediction_"+model]
            q.match_numbers(receipt["residual_"+model]/scale, expected_residual/scale,
                            model+" private residual", 1e-10, 1e-10)
            if model != "fwdti":
                reference["stats"]["wls_normal_equation_max_relative"][model] = check_wls(design, reference["signal"][:,indices], q.entry_beta(entry))
            else:
                optimizer_q = receipt["optimizer_q_"+model]
                finite = np.isfinite(optimizer_q).all(axis=1)
                assert np.array_equal(optimizer_q[finite,:7], q.entry_beta(entry)[finite])
                assert np.allclose(.5*(1+np.sin(optimizer_q[finite,7]-np.pi/2)), entry["f"][finite], atol=1e-14, rtol=1e-14)
    q.validate_reference(reference)
    _, submitted = q.validate_output_directory(output, reference)
    for model, entry in submitted.items():
        for key in ("status", *q.BOOL_FIELDS, *q.INT_FIELDS, *q.FLOAT_FIELDS):
            assert_same(entry[key], reference["models"][model][key], model+" full-precision public "+key)
    payload = {"ref_roi_ijk": reference["ijk"], "ref_signal": reference["signal"],
               "ref_bvals": reference["bvals"], "ref_bvecs": reference["bvecs"],
               "ref_raw_signal": prepared["raw_signal"], "ref_original_bvals": prepared["original_bvals"],
               "ref_original_bvecs": prepared["original_bvecs"], "ref_volume_indices": prepared["volume_indices"],
               "ref_roi_fa_low": prepared["roi_fa_low"], "ref_roi_md_low": prepared["roi_md_low"],
               "ref_stats": np.array(json.dumps(reference["stats"], allow_nan=False))}
    for model, entry in reference["models"].items():
        payload["volume_indices_"+model], payload["design_"+model] = entry["indices"], entry["design"]
        payload.update({key+"_"+model: entry[key] for key in ("status", *q.BOOL_FIELDS, *q.INT_FIELDS, *q.FLOAT_FIELDS)})
    bank = Path(bank); bank.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".reference-v2-", suffix=".npz", dir=bank.parent, delete=False) as stream:
        temporary = Path(stream.name)
        np.savez_compressed(stream, **payload); stream.flush(); os.fsync(stream.fileno())
    try:
        checked = q.load_reference(temporary)
        q.validate_output_directory(output, checked)
        os.replace(temporary, bank)
    finally:
        if temporary.exists(): temporary.unlink()
    print(json.dumps({"pipeline_id": q.PIPELINE_ID, "reference": str(bank),
                      "n_roi_voxels": len(reference["ijk"]),
                      "wls_normal_equation_max_relative": reference["stats"]["wls_normal_equation_max_relative"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/app/data/sherbrooke"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", "--bank", dest="reference", type=Path, default=TASK/"tests/reference.npz")
    parser.add_argument("--template", type=Path, default=TASK/"environment/method_contract.json")
    args = parser.parse_args()
    build(args.data, args.output, args.reference, args.template)


if __name__ == "__main__": main()
