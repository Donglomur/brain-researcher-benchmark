"""Authoring-only v2 bank from all three genuine, source-checked executions.

Rebuilds only the public low-b ROI definition. It does not refit the three output
models, download source files or use the obsolete reference as input.
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
    spec = importlib.util.spec_from_file_location("wmmd_source_for_authoring", TASK/"solution/compute.py")
    oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
    return oracle


def verify_wls_normal_equations(design, signal, beta):
    """Necessary full-ROI two-pass WLS identity; not an independent full refit.

    OLS defines the fixed weights. The separate checker independently refits a
    declared sample; this check covers every retained coefficient vector.
    """
    inverse = np.linalg.pinv(design, rcond=1e-15)
    maximum = 0.
    for start in range(0, len(signal), 256):
        stop = min(start+256, len(signal))
        y = np.log(np.maximum(signal[start:stop], q.SIGNAL_FLOOR))
        weights = np.exp((y @ inverse.T) @ design.T)
        assert np.isfinite(weights).all() and np.all(weights > 0)
        weighted_design = weights[:, :, None]*design[None, :, :]
        residual = weights*(beta[start:stop] @ design.T-y)
        gradient = np.einsum("nmp,nm->np", weighted_design, residual)
        denominator = np.linalg.norm(weighted_design, axis=(1, 2))*np.linalg.norm(weights*y, axis=1)
        relative = np.linalg.norm(gradient, axis=1)/np.maximum(denominator, np.finfo(float).tiny)
        maximum = max(maximum, float(relative.max()))
    assert maximum < 1e-10, "genuine coefficient receipt violates its WLS normal equations"
    return maximum


def template_for(directory, config):
    directory = Path(directory)
    combined = directory/"method_contract.json"
    if combined.is_file():
        mapping = json.loads(combined.read_text())
        if set(q.CONFIGS) <= set(mapping): return mapping[config]
    return json.loads((directory/f"method_contract_{config}.json").read_text())


def build(data, outputs, bank, templates):
    assert set(outputs) == set(q.CONFIGS), "all three genuine executions are needed for the authoring bank"
    oracle = load_oracle()
    image, bvals, bvecs, hashes = oracle.load_inputs(data)
    raw, brain, fa_low, roi = oracle.prepare_data(image, bvals, bvecs)
    coordinates, signal = np.argwhere(roi), raw[roi]
    del raw
    reference = {"ijk": coordinates, "signal": signal, "bvals": bvals, "bvecs": bvecs,
                 "configs": {}, "stats": {"pipeline_id": q.PIPELINE_ID, "source_sha256": hashes,
                    "n_brain_voxels": int(brain.sum()), "metadata_by_config": {},
                    "results_by_config": {}, "wls_normal_equation_max_relative": {}}}
    payload = {"ref_roi_ijk": coordinates, "ref_signal": signal,
               "ref_bvals": bvals, "ref_bvecs": bvecs, "ref_roi_fa_low": fa_low[roi]}
    for config in q.CONFIGS:
        output = Path(outputs[config])
        contract = oracle.metadata_contract(image, bvals, bvecs, hashes, config)
        assert template_for(templates, config) == contract, "public template differs from declared source recipe"
        indices, design = oracle.config_design(bvals, bvecs, config)
        with np.load(output/"analysis_arrays.npz", allow_pickle=False) as receipt:
            for name, expected in (("roi_ijk", coordinates), ("signal", signal), ("bvals", bvals),
                                   ("bvecs", bvecs), ("volume_indices", indices), ("design", design),
                                   ("roi_fa_low", fa_low[roi])):
                assert np.array_equal(receipt[name], expected), f"genuine {config} receipt/source mismatch: {name}"
            assert int(receipt["n_brain_voxels"].item()) == int(brain.sum())
            assert json.loads(str(receipt["metadata_json"].item())) == contract
            entry = {"indices": indices, "design": design, "beta": receipt["beta"],
                     **{key: receipt[key] for key in q.METRICS}}
        assert entry["beta"].shape == (len(coordinates), design.shape[1]) and np.isfinite(entry["beta"]).all()
        normal_error = verify_wls_normal_equations(design, signal[:, indices], entry["beta"])
        reference["configs"][config] = entry
        reference["stats"]["metadata_by_config"][config] = contract
        reference["stats"]["results_by_config"][config] = q.load_json(output/"diffusivity.json")
        reference["stats"]["wls_normal_equation_max_relative"][config] = normal_error
        payload.update({"volume_indices_"+config: indices, "design_"+config: design,
                        "beta_"+config: entry["beta"], **{key+"_"+config: entry[key] for key in q.METRICS}})
    q.validate_reference(reference)
    for config in q.CONFIGS:
        declared, table = q.validate_output_directory(outputs[config], reference)
        assert declared == config
        assert np.array_equal(table["beta"], reference["configs"][config]["beta"]), "CSV coefficients do not retain genuine full-precision receipt"
    payload["ref_stats"] = np.array(json.dumps(reference["stats"], allow_nan=False))
    bank = Path(bank); bank.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".reference-v2-", suffix=".npz", dir=bank.parent, delete=False) as stream:
        temporary = Path(stream.name)
        np.savez_compressed(stream, **payload); stream.flush(); os.fsync(stream.fileno())
    try:
        checked = q.load_reference(temporary)
        for config in q.CONFIGS: q.validate_output_directory(outputs[config], checked)
        os.replace(temporary, bank)
    finally:
        if temporary.exists(): temporary.unlink()
    print(json.dumps({"bank": str(bank), "pipeline_id": q.PIPELINE_ID, "n_roi_voxels": len(coordinates),
                      "n_brain_voxels": int(brain.sum()), "wls_normal_equation_max_relative": reference["stats"]["wls_normal_equation_max_relative"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/app/data/cfin"))
    parser.add_argument("--outputs-root", type=Path, help="directory containing dki_all/dti_lowb/dti_all outputs")
    parser.add_argument("--output", action="append", default=[], help="CONFIG=PATH; repeat for all three")
    parser.add_argument("--bank", type=Path, default=TASK/"tests/reference.npz")
    parser.add_argument("--templates", type=Path, default=TASK/"environment")
    args = parser.parse_args()
    assert bool(args.outputs_root) != bool(args.output), "choose --outputs-root or three --output mappings"
    outputs = {config: args.outputs_root/config for config in q.CONFIGS} if args.outputs_root else dict(value.split("=", 1) for value in args.output)
    build(args.data, outputs, args.bank, args.templates)


if __name__ == "__main__": main()
