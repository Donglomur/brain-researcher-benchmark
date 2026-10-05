"""Check the oracle with independent mask extraction and run-wise preprocessing.

Uses nibabel indexing and SciPy detrending rather than NiftiMasker/nilearn.clean.
The source data, scientific recipe, and sklearn/libsvm classifier are shared, so
this is an independent preprocessing implementation, not an independent decoder.
The optional global-clean mode produces a real, deliberately misprocessed control.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.signal import detrend
from sklearn.svm import SVC


CATEGORIES = {"bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe"}
FIELDS = ["volume_id", "held_out_run", "true_label", "predicted_label"]


def load_source(data_dir):
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    hashes = {}
    for record in manifest["files"]:
        path = data_dir / record["path"]
        if path.stat().st_size != record["size_bytes"]:
            raise ValueError(f"Changed source size: {path.name}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"Changed source bytes: {path.name}")
        hashes[record["path"]] = digest
    subject = data_dir / "subj1"
    table = np.genfromtxt(subject / "labels.txt", names=True, dtype=None, encoding="utf-8")
    labels = np.asarray(table["labels"], dtype=str)
    runs = np.asarray(table["chunks"], dtype=int)
    image = nib.load(subject / "bold.nii.gz")
    mask_image = nib.load(subject / "mask4_vt.nii.gz")
    if image.shape[:3] != mask_image.shape or not np.allclose(image.affine, mask_image.affine):
        raise ValueError("Mask and source image must share the same voxel grid")
    mask = np.asanyarray(mask_image.dataobj) > 0
    # Boolean indexing extracts the mask directly, without nilearn preprocessing.
    X = np.asarray(np.asanyarray(image.dataobj)[mask, :].T, dtype=np.float64)
    if X.shape[0] != len(labels) or not np.all(np.isfinite(X)):
        raise ValueError("Invalid source time series or label count")
    if set(np.unique(runs)) != set(range(12)) or set(labels) != CATEGORIES | {"rest"}:
        raise ValueError("Unexpected acquisition runs or stimulus categories")
    return X, labels, runs, hashes


def clean(X, runs, mode):
    result = np.empty_like(X)
    blocks = [np.arange(len(runs))] if mode == "global-clean" else [np.flatnonzero(runs == r) for r in range(12)]
    for indices in blocks:
        values = detrend(X[indices], axis=0, type="linear")
        # Recenter residual roundoff before the public sample-standard-deviation scaling.
        values -= values.mean(axis=0)
        scale = values.std(axis=0, ddof=1)
        scale[scale < np.finfo(np.float64).eps] = 1.0
        result[indices] = values / scale
    return result


def decode(X, labels, runs):
    keep = labels != "rest"
    volume_ids = np.flatnonzero(keep)
    X, labels, runs = X[keep], labels[keep], runs[keep]
    rows, fold_rows = [], []
    for held in range(12):
        test = runs == held
        model = SVC(kernel="linear", C=1.0, tol=0.001, shrinking=True)
        model.fit(X[~test], labels[~test])
        predicted = model.predict(X[test])
        rows.extend({"volume_id": int(v), "held_out_run": held, "true_label": str(y), "predicted_label": str(p)}
                    for v, y, p in zip(volume_ids[test], labels[test], predicted))
        fold_rows.append({"fold": held + 1, "held_out_run": held, "n_test_samples": int(test.sum()),
                          "accuracy": float(np.mean(predicted == labels[test]))})
    metrics = {"cv_accuracy": float(np.mean([row["accuracy"] for row in fold_rows])),
               "n_samples": len(rows), "n_voxels": int(X.shape[1]), "n_categories": 8, "n_runs": 12,
               "chance": 0.125, "cv_accuracy_per_run": [row["accuracy"] for row in fold_rows]}
    return rows, fold_rows, metrics


def compare_oracle(path, rows):
    with (path / "predictions.csv").open(newline="") as stream:
        oracle_rows = list(csv.DictReader(stream))
    oracle = {int(row["volume_id"]): row for row in oracle_rows}
    independent = {row["volume_id"]: row for row in rows}
    if len(oracle) != len(oracle_rows) or set(oracle) != set(independent):
        raise ValueError("Oracle predictions have duplicate or missing source volumes")
    disagreements = []
    for volume_id, row in independent.items():
        other = oracle[volume_id]
        if int(other["held_out_run"]) != row["held_out_run"] or other["true_label"] != row["true_label"]:
            raise ValueError(f"Oracle source identity mismatch at volume {volume_id}")
        if other["predicted_label"] != row["predicted_label"]:
            disagreements.append({"volume_id": volume_id, "held_out_run": row["held_out_run"],
                                  "true_label": row["true_label"], "independent_prediction": row["predicted_label"],
                                  "oracle_prediction": other["predicted_label"]})
    oracle_per_run = []
    for held in range(12):
        selected = [row for row in oracle_rows if int(row["held_out_run"]) == held]
        oracle_per_run.append(float(np.mean([row["true_label"] == row["predicted_label"] for row in selected])))
    return {"n_disagreements": len(disagreements), "agreement_fraction": 1 - len(disagreements) / len(rows),
            "disagreements": disagreements, "oracle_per_run_accuracies": oracle_per_run,
            "oracle_cv_accuracy_recomputed": float(np.mean(oracle_per_run))}


def write_outputs(destination, rows, folds, metrics, mode):
    destination.mkdir(parents=True, exist_ok=True)
    for name, fields, records in [("predictions.csv", FIELDS, rows),
                                   ("per_fold.csv", ["fold", "held_out_run", "n_test_samples", "accuracy"], folds)]:
        with (destination / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
    (destination / "decoding_results.json").write_text(json.dumps(metrics, indent=2) + "\n")
    metadata = {"dataset_id": "haxby2001", "subject": 1, "mask": "mask4_vt", "status": "ok",
                "cross_validation": "leave-one-run-out", "preprocessing": {
                    "cleaning_unit": "all_concatenated_runs" if mode == "global-clean" else "acquisition_run",
                    "clean_before_rest_removal": True, "detrend": True, "standardize": "zscore_sample"},
                "classifier": {"name": "SVC", "kernel": "linear", "C": 1.0, "tol": 0.001, "shrinking": True},
                "control_mode": mode}
    (destination / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (destination / "findings.md").write_text(
        f"Leave-one-run-out accuracy was {metrics['cv_accuracy']:.6f}; preprocessing mode: {mode}. "
        "The global-clean mode deliberately violates the required acquisition-run cleaning contract.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data"))
    parser.add_argument("--oracle-output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=["runwise", "global-clean"], default="runwise")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.mode == "runwise" and args.oracle_output is None:
        parser.error("--oracle-output is required for the independent run-wise check")
    X, labels, runs, hashes = load_source(args.data_dir)
    cleaned = clean(X, runs, args.mode)
    rows, folds, metrics = decode(cleaned, labels, runs)
    report = {
        "evidence_type": "independent_preprocessing_with_shared_classifier",
        "mode": args.mode, "source_sha256": hashes, "n_source_volumes": len(labels),
        "method": "Direct nibabel mask indexing; SciPy linear detrend; sample standard deviation ddof=1; clean before rest removal; manual leave-one-run-out SVC",
        "independent_components": ["mask extraction", "linear detrending", "sample standardization", "fold iteration"],
        "shared_components": ["source data and mask", "scientific preprocessing contract", "sklearn SVC/libsvm implementation and parameters"],
        "interpretation_limit": "Checks a second preprocessing implementation; does not independently validate libsvm or reproduce the original paper's pattern-correlation statistic.",
        "versions": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                     for name in ["numpy", "scipy", "nibabel", "scikit-learn", "nilearn"]}},
        "metrics": metrics, "per_run": folds,
    }
    if args.oracle_output is not None:
        report["oracle_comparison"] = compare_oracle(args.oracle_output, rows)
    if args.output_dir is not None:
        write_outputs(args.output_dir, rows, folds, metrics, args.mode)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"mode": args.mode, "cv_accuracy": metrics["cv_accuracy"],
                      "n_disagreements": report.get("oracle_comparison", {}).get("n_disagreements"),
                      "report": str(args.report)}))


if __name__ == "__main__":
    main()
