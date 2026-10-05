"""Build a scientific bank only from source-verified executed oracle outputs.

This program does not fit a classifier or create a replacement scientific dataset.
The public outputs, retained fit state, and freshly reread NWB must agree before
the old bank is atomically replaced.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "solution"))
import compute


def validate_fit_state(arrays):
    from scipy.special import expit
    y = arrays["true_choice"]
    for recipe in compute.RECIPES:
        window, split = recipe.rsplit("_", 1)
        x = arrays[f"counts_{window}"].astype(float)
        folds = arrays[f"fold_{split}"]
        for key in ("coefficients", "scaler_means", "scaler_scales"):
            values = arrays[f"{key}_{recipe}"]
            assert values.shape == (5, x.shape[1]) and np.isfinite(values).all(), "invalid fitted model state"
        assert arrays[f"intercepts_{recipe}"].shape == (5,)
        assert np.isfinite(arrays[f"intercepts_{recipe}"]).all()
        for fold in range(5):
            train, test = folds != fold, folds == fold
            mean = x[train].mean(axis=0)
            scale = x[train].std(axis=0, ddof=0)
            scale[scale == 0] = 1
            np.testing.assert_allclose(arrays[f"scaler_means_{recipe}"][fold], mean, atol=1e-12, rtol=1e-12)
            np.testing.assert_allclose(arrays[f"scaler_scales_{recipe}"][fold], scale, atol=1e-12, rtol=1e-12)
            decision = ((x[test] - mean) / scale) @ arrays[f"coefficients_{recipe}"][fold]
            decision += arrays[f"intercepts_{recipe}"][fold]
            np.testing.assert_allclose(arrays[f"decision_{recipe}"][test], decision, atol=1e-10, rtol=1e-10)
        decision = arrays[f"decision_{recipe}"]
        np.testing.assert_array_equal(arrays[f"predicted_choice_{recipe}"], np.where(decision > 0, 1, -1))
        np.testing.assert_allclose(arrays[f"probability_left_{recipe}"], expit(decision), atol=1e-12, rtol=1e-12)
        iterations = arrays[f"n_iter_{recipe}"]
        assert iterations.shape == (5,) and np.all((iterations > 0) & (iterations <= 2000))
        assert np.all(iterations == np.floor(iterations))


def build(output_dir, data_dir, reference_path):
    output_dir, reference_path = Path(output_dir), Path(reference_path)
    with np.load(output_dir / "analysis_arrays.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    source, selection_counts, contract = compute.load_data(data_dir)
    for key, expected in source.items():
        np.testing.assert_array_equal(arrays[key], expected, err_msg=f"retained source mismatch: {key}")
    template = json.loads((TASK / "environment/method_contract.json").read_text())
    assert template == contract, "public template and executed source contract differ"
    metadata = json.loads(str(arrays["metadata_json"]))
    assert metadata == json.loads((output_dir / "run_metadata.json").read_text()), "metadata receipt mismatch"
    assert metadata.get("status") == "ok", "failed analysis cannot become a scientific bank"
    for key, value in contract.items():
        assert metadata.get(key) == value, f"executed contract mismatch: {key}"
    for split, expected in compute.fold_assignments(source["true_choice"]).items():
        np.testing.assert_array_equal(arrays[f"fold_{split}"], expected)
        baseline = np.empty(len(expected), dtype=np.int64)
        for fold in range(5):
            baseline[expected == fold] = compute.majority_choice(source["true_choice"][expected != fold])
        np.testing.assert_array_equal(arrays[f"baseline_choice_{split}"], baseline)
    validate_fit_state(arrays)
    results, _ = compute.summarize(arrays, selection_counts)
    assert results == json.loads((output_dir / "results.json").read_text()), "public summary is not derived from retained OOF predictions"
    stats = {"pipeline_id": compute.PIPELINE_ID, "source_sha256": contract["source_sha256"],
             "metadata_contract": contract, "selection_counts": selection_counts,
             "response_timing_counts": results["response_timing_counts"], "results": results}
    keys = list(source)
    for split in compute.SPLITS:
        keys.extend([f"fold_{split}", f"baseline_choice_{split}"])
    for recipe in compute.RECIPES:
        keys.extend([f"predicted_choice_{recipe}", f"decision_{recipe}", f"probability_left_{recipe}"])
    bank = {f"ref_{key}": arrays[key] for key in keys}
    bank["ref_stats"] = np.asarray(json.dumps(stats, allow_nan=False))
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=reference_path.parent, prefix=".source-verified-", suffix=".npz", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        np.savez_compressed(temporary, **bank)
        sys.path.insert(0, str(TASK / "tests"))
        import proof_of_work
        import decoding_contract
        reference = proof_of_work.load_reference(temporary)
        decoding_contract.validate_output_directory(output_dir, reference)
        temporary.replace(reference_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(json.dumps({"reference": str(reference_path), "n_trials": results["n_trials"],
                      "n_units": results["n_units"], "accuracy_by_window_and_split": results["accuracy_by_window_and_split"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/steinmetz"))
    parser.add_argument("--reference", type=Path, default=TASK / "tests/reference.npz")
    args = parser.parse_args()
    build(args.output_dir, args.data_dir, args.reference)
