"""Build the CFIN v2 bank only from retained oracle fits and verified raw sources."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np

TASK = Path(__file__).resolve().parents[1]


def oracle_module():
    spec = importlib.util.spec_from_file_location("cfin_oracle", TASK / "solution/compute.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_csv_maps(path, expected_coordinates, *, sweep):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"i", "j", "k", "mk"} | ({"max_b"} if sweep else set())
        if set(reader.fieldnames or ()) != required:
            raise ValueError(f"unexpected oracle CSV fields: {path}")
        groups = {}
        for row in reader:
            coordinate = tuple(int(row[axis]) for axis in ("i", "j", "k"))
            if any(str(value) != row[axis] for axis, value in zip(("i", "j", "k"), coordinate)):
                raise ValueError("oracle coordinates must be exact integers")
            cap = row["max_b"] if sweep else "2000"
            table = groups.setdefault(cap, {})
            if coordinate in table:
                raise ValueError("duplicate oracle voxel coordinate")
            value = float(row["mk"])
            if not np.isfinite(value) or not 0 <= value <= 3:
                raise ValueError("nonfinite or out-of-range oracle MK")
            table[coordinate] = value
    expected = [tuple(map(int, row)) for row in expected_coordinates]
    for cap, table in groups.items():
        if set(table) != set(expected):
            raise ValueError(f"cap {cap} does not have the complete fixed ROI")
    return {cap: np.asarray([table[key] for key in expected]) for cap, table in groups.items()}


def build(output_dir, data_dir, destination):
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dki import mean_kurtosis

    oracle = oracle_module()
    output_dir = Path(output_dir)
    image, bvals, bvecs, hashes = oracle.load_inputs(data_dir)
    contract = oracle.metadata_contract(image, bvals, hashes)
    metadata = json.loads((output_dir / "run_metadata.json").read_text())
    if metadata.get("status") != "ok" or any(metadata.get(key) != value for key, value in contract.items()):
        raise ValueError("oracle metadata does not match the pinned source/pipeline contract")
    smoothed, brain_mask, fa, roi = oracle.prepare_data(image, bvals, bvecs)
    coordinates = np.argwhere(roi)
    source_signal = smoothed[roi]
    observed_s0 = source_signal[:, bvals <= oracle.B0_THRESHOLD].mean(axis=1)
    del smoothed
    receipt = np.load(output_dir / "fit_receipt.npz", allow_pickle=False)
    if json.loads(str(receipt["metadata_json"])) != contract:
        raise ValueError("fit receipt has a different source/pipeline contract")
    if not np.array_equal(receipt["roi_ijk"], coordinates):
        raise ValueError("fit receipt ROI differs from the raw-source DTI selection")
    if not np.allclose(receipt["fa"], fa[roi], rtol=1e-10, atol=1e-10):
        raise ValueError("fit receipt FA differs from raw-source DTI")
    if not np.allclose(receipt["S0_b0"], observed_s0, rtol=1e-10, atol=1e-8):
        raise ValueError("fit receipt mean-b0 signal differs from the raw source")
    main = load_csv_maps(output_dir / "mk_voxelwise.csv", coordinates, sweep=False)
    sweep = load_csv_maps(output_dir / "mk_sweep.csv", coordinates, sweep=True)
    if set(sweep) != {str(cap) for cap in oracle.CAPS}:
        raise ValueError("reference generation requires all five genuine cap fits")
    maps, means = {}, {}
    for cap in oracle.CAPS:
        parameters = receipt[f"params_cap_{cap}"]
        fitted_s0 = receipt[f"S0_hat_cap_{cap}"]
        mk = receipt[f"map_cap_{cap}"]
        if parameters.shape != (len(coordinates), 27) or fitted_s0.shape != (len(coordinates),):
            raise ValueError(f"invalid parameter receipt shape for cap {cap}")
        if not np.isfinite(parameters).all() or not np.isfinite(fitted_s0).all() or np.any(fitted_s0 <= 0):
            raise ValueError(f"invalid parameter receipt values for cap {cap}")
        reconstructed = mean_kurtosis(parameters, min_kurtosis=0, max_kurtosis=3,
                                       analytical=True, fast=True)
        if not np.allclose(mk, reconstructed, rtol=1e-10, atol=1e-10):
            raise ValueError(f"cap {cap} MK does not follow its fitted parameters")
        if not np.allclose(sweep[str(cap)], mk, rtol=0, atol=1e-12):
            raise ValueError(f"cap {cap} CSV does not match retained fit values")
        selected = np.asarray(contract["shell_subsets"][str(cap)]["volume_indices"], int)
        gradients = gradient_table(bvals[selected], bvecs=bvecs[selected],
                                   b0_threshold=oracle.B0_THRESHOLD)
        residual = oracle.predict_and_residual(parameters, fitted_s0, gradients,
                                                source_signal[:, selected], observed_s0)
        if not np.allclose(receipt[f"nrmse_cap_{cap}"], residual, rtol=1e-10, atol=1e-10):
            raise ValueError(f"cap {cap} residual receipt differs from source signal")
        maps[f"map_cap_{cap}"] = np.asarray(mk, dtype=np.float64)
        means[str(cap)] = float(np.mean(mk))
    if not np.allclose(main["2000"], maps["map_cap_2000"], rtol=0, atol=1e-12):
        raise ValueError("primary map does not equal the 2000-shell-cap fit")
    result = json.loads((output_dir / "dki_results.json").read_text())
    exact = {"status": "ok", "pipeline_id": oracle.PIPELINE_ID,
             "n_wm_voxels": len(coordinates), "b_max_used": oracle.PRIMARY_CAP,
             "shells_used": contract["shell_subsets"]["2000"]["shells"]}
    if any(result.get(key) != value for key, value in exact.items()):
        raise ValueError("oracle result identity/count/shell contract mismatch")
    if metadata.get("n_wm_voxels") != len(coordinates) or metadata.get("n_brain_voxels") != int(brain_mask.sum()):
        raise ValueError("oracle metadata mask counts disagree with source")
    if set(result["mean_kurtosis_wm_by_bcap"]) != set(means):
        raise ValueError("oracle means have a different cap set")
    comparisons = [(result["mean_kurtosis_wm"], means["2000"]),
                   (result["mean_kurtosis_wm_allshell"], means["3000"]),
                   (result["mk_shell_cap_spread"], max(means.values()) - min(means.values()))]
    comparisons += [(result["mean_kurtosis_wm_by_bcap"][cap], mean) for cap, mean in means.items()]
    if any(not np.isclose(value, expected, rtol=0, atol=1e-12) for value, expected in comparisons):
        raise ValueError("oracle aggregate does not recompute from its maps")
    stats = {"pipeline_id": oracle.PIPELINE_ID, "source_sha256": hashes,
             "metadata_contract": contract, "means": means, "n_wm_voxels": len(coordinates)}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, ref_roi_ijk=coordinates,
                        ref_stats=np.asarray(json.dumps(stats, sort_keys=True, allow_nan=False)), **maps)
    print(json.dumps({"reference": str(destination), "pipeline_id": oracle.PIPELINE_ID,
                      "n_wm_voxels": len(coordinates), "means": means}, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--reference", type=Path, default=TASK / "tests/reference.npz")
    args = parser.parse_args()
    build(args.output_dir, args.data_dir, args.reference)


if __name__ == "__main__":
    main()
