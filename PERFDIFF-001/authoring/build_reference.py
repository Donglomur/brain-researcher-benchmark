"""Build a source-bound IVIM bank only from retained genuine fit outputs."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ivim_reference_compute", TASK / "solution/compute.py")
compute = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compute)


def build(output_dir, data_dir, destination):
    output, destination = Path(output_dir), Path(destination)
    image, bvals, _, hashes = compute.load_inputs(data_dir)
    contract = compute.metadata_contract(image, bvals, hashes)
    public = json.loads((TASK / "environment/method_contract.json").read_text())
    if public != contract:
        raise ValueError("public method contract differs from verified source/configuration")
    coordinates, signal, b0, tissue, eligible = compute.extract_source_roi(image, bvals)
    with np.load(output / "fit_receipt.npz", allow_pickle=False) as receipt:
        saved_contract = json.loads(str(receipt["metadata_json"]))
        arrays = {key: receipt[key].copy() for key in receipt.files if key != "metadata_json"}
    if saved_contract != contract:
        raise ValueError("retained fits are not bound to this public source/recipe")
    source_arrays = {"roi_ijk": coordinates, "signal": signal, "bvals": bvals,
                     "b0_observed": b0, "tissue_eligible": tissue, "eligible": eligible}
    for name, expected in source_arrays.items():
        if not np.array_equal(arrays[name], expected, equal_nan=True):
            raise ValueError(f"retained source array differs: {name}")
    common = eligible.copy()
    for method in compute.METHODS:
        params = arrays[f"params_{method}"]
        if params.shape != (900, 4) or np.isinf(params).any():
            raise ValueError(f"invalid complete parameter array: {method}")
        common &= arrays[f"status_{method}"] == "ok"
    if not np.array_equal(common, arrays["common_valid"]) or not common.any():
        raise ValueError("no valid common intersection, or retained common mask differs")
    result = json.loads((output / "ivim_results.json").read_text())
    expected_result = compute.summarize_results(arrays, common, result["primary_method"])
    if result != expected_result:
        raise ValueError("public result does not exactly reproduce retained fit summaries")
    stats = {"pipeline_id": compute.PIPELINE_ID, "dataset_id": compute.DATASET_ID,
             "source_sha256": hashes, "metadata_contract": contract, "results": result}
    bank = {f"ref_{name}": value for name, value in source_arrays.items()}
    bank["ref_common_valid"] = common
    bank["ref_stats"] = np.asarray(json.dumps(stats, sort_keys=True, allow_nan=False))
    for name, value in arrays.items():
        if name not in source_arrays and name != "common_valid":
            bank[name] = value

    # Validate the new bank and every public output before replacing the old bank.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="ivim-reference-", suffix=".npz",
                                     dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
        np.savez_compressed(stream, **bank)
    try:
        sys.path.insert(0, str(TASK / "tests"))
        import proof_of_work as proof
        import ivim_contract as checks
        proof.REF_PATH = temporary
        reference = proof.load_reference()
        groups = proof.load_parameters(output / "parameters_voxelwise.csv")
        checked, common_checked = checks.validate_parameters(groups, reference)
        primary = checks.validate_results(result, checked, common_checked)
        checks.validate_f_maps(proof.load_f_map(output / "f_voxelwise.csv"),
                               proof.load_f_map(output / "f_sweep.csv", sweep=True),
                               groups, reference, primary)
        checks.validate_metadata(proof.read_json(output / "run_metadata.json"), reference, primary)
        if not (output / "findings.md").read_text().strip():
            raise ValueError("findings are absent")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(json.dumps({"reference": str(destination), "n_box_voxels": len(coordinates),
                      "n_common_valid": int(common.sum()), "pipeline_id": compute.PIPELINE_ID,
                      "source_sha256": hashes}, indent=2))
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--data-dir", default="/app/data/ivim")
    parser.add_argument("--destination", default=str(TASK / "tests/reference.npz"))
    args = parser.parse_args()
    build(args.output_dir, args.data_dir, args.destination)


if __name__ == "__main__":
    main()
