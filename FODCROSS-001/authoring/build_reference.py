"""Build the fODF v2 bank from source-verified genuine oracle fit receipts."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np

TASK = Path(__file__).resolve().parents[1]


def oracle_module():
    spec = importlib.util.spec_from_file_location("sherbrooke_oracle", TASK / "solution/compute.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def same_array(actual, expected, label, *, exact=False, rtol=1e-10, atol=1e-10):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise ValueError(f"invalid shape/values: {label}")
    matches = np.array_equal(actual, expected) if exact else np.allclose(actual, expected, rtol=rtol, atol=atol)
    if not matches:
        raise ValueError(f"source/fit receipt mismatch: {label}")


def load_maps(path, coordinates, *, sweep):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"i", "j", "k", "n_peaks"} | ({"estimator"} if sweep else set())
        if set(reader.fieldnames or ()) != required:
            raise ValueError(f"unexpected oracle CSV fields: {path}")
        groups = {}
        for row in reader:
            numbers = [int(row[key]) for key in ("i", "j", "k", "n_peaks")]
            if any(str(value) != row[key] for key, value in zip(("i", "j", "k", "n_peaks"), numbers)):
                raise ValueError("oracle coordinates/peak counts must be exact integers")
            coordinate, count = tuple(numbers[:3]), numbers[3]
            if not 0 <= count <= 3:
                raise ValueError("invalid oracle peak count")
            name = row["estimator"] if sweep else "primary"
            table = groups.setdefault(name, {})
            if coordinate in table:
                raise ValueError("duplicate oracle coordinate")
            table[coordinate] = count
    expected = [tuple(map(int, xyz)) for xyz in coordinates]
    if not groups:
        raise ValueError("empty oracle map")
    for name, table in groups.items():
        if set(table) != set(expected):
            raise ValueError(f"oracle group {name} does not contain the exact fixed ROI")
    return {name: np.asarray([table[key] for key in expected], int) for name, table in groups.items()}


def build(output_dir, data_dir, destination):
    oracle = oracle_module()
    oracle.check_versions()
    from dipy.data import default_sphere, small_sphere

    output_dir = Path(output_dir)
    image, bvals, bvecs, hashes = oracle.load_inputs(data_dir)
    contract = oracle.metadata_contract(image, bvals, hashes)
    metadata = json.loads((output_dir / "run_metadata.json").read_text())
    if metadata.get("status") != "ok" or any(metadata.get(key) != value for key, value in contract.items()):
        raise ValueError("oracle metadata does not match pinned source/public recipe")
    if metadata.get("fitted_estimators") != oracle.RECIPES:
        raise ValueError("bank generation requires all three genuine estimator fits")
    result = json.loads((output_dir / "crossing.json").read_text())
    primary = result.get("primary_estimator")
    if primary not in oracle.RECIPES or metadata.get("primary_estimator") != primary:
        raise ValueError("primary estimator mismatch")
    data, shells, brain, fa, roi, masks = oracle.prepare_data(image, bvals, bvecs)
    coordinates = np.argwhere(roi)
    signal = data[roi]
    mean_b0 = signal[:, shells == 0].mean(axis=1)
    models, responses = oracle.make_models(data, shells, bvecs, masks)
    del data
    receipt = np.load(output_dir / "fit_receipt.npz", allow_pickle=False)
    if json.loads(str(receipt["metadata_json"])) != contract:
        raise ValueError("fit receipt source/public recipe mismatch")
    same_array(receipt["roi_ijk"], coordinates, "fixed target ROI", exact=True)
    same_array(receipt["fa"], fa[roi], "low-b DTI FA")
    same_array(receipt["mean_b0"], mean_b0, "raw mean b0")
    for prefix, sphere in (("sphere", default_sphere), ("small_sphere", small_sphere)):
        same_array(receipt[f"{prefix}_vertices"], sphere.vertices, f"{prefix} vertices", exact=True)
        same_array(receipt[f"{prefix}_edges"], sphere.edges, f"{prefix} edges", exact=True)
    for tissue, mask in zip(("wm", "gm", "csf"), masks):
        same_array(receipt[f"response_mask_{tissue}_ijk"], np.argwhere(mask), f"{tissue} response mask", exact=True)
        if metadata["response_tissue_voxel_counts"][tissue] != int(np.count_nonzero(mask)):
            raise ValueError("response-mask count mismatch")
    for key, response in responses.items():
        same_array(receipt[key], response, key)
        same_array(metadata["response_arrays"][key], response, f"metadata {key}")
    primary_map = load_maps(output_dir / "peaks_voxelwise.csv", coordinates, sweep=False)["primary"]
    sweep = load_maps(output_dir / "peaks_sweep.csv", coordinates, sweep=True)
    if set(sweep) != set(oracle.RECIPES):
        raise ValueError("reference generation requires exactly the three public recipes")
    fractions, bank_maps = {}, {}
    for name in oracle.RECIPES:
        model, indices, regularization = models[name]
        coefficients = receipt[f"coeff_{name}"]
        expected_shape = (len(coordinates), 47 if name == "msmt" else 45)
        if coefficients.shape != expected_shape or not np.isfinite(coefficients).all():
            raise ValueError(f"invalid fitted coefficients: {name}")
        same_array(receipt[f"design_{name}"], model._X, f"{name} source-derived design")
        same_array(receipt[f"reg_{name}"], regularization, f"{name} regularization")
        wm_coefficients = coefficients[:, 2:] if name == "msmt" else coefficients
        odfs = wm_coefficients @ model.sampling_matrix(default_sphere).T
        same_array(receipt[f"odf_{name}"], odfs, f"{name} coefficients to ODF")
        extracted = [oracle.extract_peaks(odf, default_sphere) for odf in odfs]
        values = np.asarray([row[0] for row in extracted])
        locations = np.asarray([row[1] for row in extracted])
        same_array(receipt[f"peak_values_{name}"], values, f"{name} peak values")
        same_array(receipt[f"peak_indices_{name}"], locations, f"{name} peak indices", exact=True)
        counts = np.sum(values > 0, axis=1)
        same_array(receipt[f"map_{name}"], counts, f"{name} retained count map", exact=True)
        same_array(sweep[name], counts, f"{name} CSV count map", exact=True)
        residual = oracle.normalized_residual(name, model, coefficients, signal[:, indices], mean_b0)
        same_array(receipt[f"nrmse_{name}"], residual, f"{name} source-signal residual")
        qc = metadata["fit_qc"][name]
        expected_qc = {"n_zero_peak_voxels": int(np.sum(counts == 0)),
                       "n_capped_three_peak_voxels": int(np.sum(counts == 3)),
                       # Sign at exact zero is rounding-sensitive under batched
                       # versus per-voxel BLAS. Validate this diagnostic against
                       # the actual retained samples, already numerically checked.
                       "negative_odf_sample_fraction": float(np.mean(receipt[f"odf_{name}"] < 0)),
                       "dwi_normalized_rmse_median": float(np.median(residual)),
                       "dwi_normalized_rmse_maximum": float(np.max(residual)),
                       "dwi_normalized_rmse_gt_0_1_count": int(np.sum(residual > 0.1))}
        for key, expected in expected_qc.items():
            if not np.isclose(qc[key], expected, rtol=1e-10, atol=1e-10):
                raise ValueError(f"incorrect fit-QC disclosure: {name}/{key}")
        if name == "msmt":
            objective = (0.5 * np.sum((coefficients @ model._X.T) ** 2, axis=1)
                         - np.sum((coefficients @ model._X.T) * signal[:, indices], axis=1))
            minimum = np.min(coefficients @ regularization.T, axis=1)
            same_array(receipt["solver_objective_msmt"], objective, "MSMT solver objective", atol=1e-7)
            same_array(receipt["solver_constraint_minimum_msmt"], minimum, "MSMT constraint minimum")
            if qc.get("solver_status") != "all_optimal":
                raise ValueError("oracle solver did not report convergence")
        fractions[name] = float(np.mean(counts >= 2))
        bank_maps[f"map_{name}"] = counts
    same_array(primary_map, bank_maps[f"map_{primary}"], "primary to sweep linkage", exact=True)
    expected = {"status": "ok", "pipeline_id": oracle.PIPELINE_ID,
                "n_roi_voxels": len(coordinates),
                "n_crossing_voxels": int(np.sum(primary_map >= 2))}
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError("oracle result identity/count mismatch")
    if metadata.get("n_roi_voxels") != len(coordinates) or metadata.get("n_brain_voxels") != int(brain.sum()):
        raise ValueError("oracle metadata mask counts disagree with raw source")
    if set(result["crossing_fraction_by_estimator"]) != set(fractions):
        raise ValueError("reported estimator set differs from fitted maps")
    comparisons = [(result["crossing_fraction"], fractions[primary]),
                   (result["mean_peaks_per_voxel"], float(np.mean(primary_map)))]
    comparisons += [(result["crossing_fraction_by_estimator"][name], value) for name, value in fractions.items()]
    if any(not np.isclose(actual, expected, rtol=0, atol=1e-12) for actual, expected in comparisons):
        raise ValueError("reported aggregate does not recompute from its map")
    stats = {"pipeline_id": oracle.PIPELINE_ID, "source_sha256": hashes,
             "metadata_contract": contract, "frac_by_config": fractions,
             "n_roi_voxels": len(coordinates)}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination, ref_roi_ijk=coordinates,
                        ref_stats=np.asarray(json.dumps(stats, sort_keys=True, allow_nan=False)), **bank_maps)
    print(json.dumps({"reference": str(destination), "pipeline_id": oracle.PIPELINE_ID,
                      "n_roi_voxels": len(coordinates), "frac_by_config": fractions}, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--reference", type=Path, default=TASK / "tests/reference.npz")
    args = parser.parse_args()
    build(args.output_dir, args.data_dir, args.reference)


if __name__ == "__main__":
    main()
