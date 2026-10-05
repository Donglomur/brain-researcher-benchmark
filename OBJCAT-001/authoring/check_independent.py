"""Independent Haxby extraction/preprocessing/ANOVA with shared libsvm fits.

No oracle, verifier, reference-bank, Nilearn cleaning or sklearn feature-selection
imports. Read original source bytes and the public metadata template; oracle CSVs
are opened only after the independent participant outputs have been produced.
Source processing/fits require the parent's reviewed execution contract.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import warnings

import nibabel as nib
import numpy as np
from scipy.signal import detrend
from sklearn.svm import SVC

PIPELINE_ID = "haxby2-runwise-anova500-loro-v2"
MANIFEST_SHA256 = "702e97410687dea0193f5d300d988e86c02a1c14cd1fac3016f7a6f7d865cb3a"
SOURCE_PINS = {
    "bold": ("subj2/bold.nii.gz", 284094471, "d3e71d07ef780d11673580653cdbe10365e4e93fd78d0f8ed27582086fd0b701"),
    "labels": ("subj2/labels.txt", 12040, "9bda5eaa9900b7506b4836348a67e5c38f76eda5d11ee9f337577821b64e4800"),
    "mask": ("mask.nii.gz", 2969, "d9b531908176bdb5e749f144852ed2adce0712bb476a3fc607abe939363f0b1d")}
CATEGORIES = ("bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe")
SVC_SETTINGS = dict(kernel="linear", C=1., tol=.001, shrinking=True, cache_size=200,
                    probability=False, class_weight=None, verbose=False, max_iter=-1,
                    decision_function_shape="ovr", break_ties=False, random_state=None,
                    degree=3, gamma="scale", coef0=0.)
K = 500
F_ATOL, F_RTOL = 1e-8, 1e-6


def require(condition, reason):
    if not condition: raise ValueError(reason)


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""): result.update(block)
    return result.hexdigest()


def reject_symlinks(path):
    path = Path(path).absolute()
    require(not any(value.is_symlink() for value in (path, *path.parents)), f"symlink path not permitted: {path}")


def fresh_paths(output, report):
    output, report = Path(output), Path(report)
    for path in (output, report, report.with_suffix(".arrays.npz")):
        reject_symlinks(path)
        require(not path.exists(), f"refusing existing independent evidence: {path}")
    require(not report.resolve().is_relative_to(output.resolve()), "report must be outside the participant output directory")


def source_labels(path):
    lines = Path(path).read_text().splitlines()
    require(lines and lines[0].split() == ["labels", "chunks"], "original label columns changed")
    rows = [line.split() for line in lines[1:]]
    require(len(rows) == 1452 and all(len(row) == 2 for row in rows), "original label row count/schema changed")
    labels = np.asarray([row[0] for row in rows])
    require(all(row[1].isdigit() for row in rows), "source chunk is not a nonnegative integer")
    runs = np.asarray([int(row[1]) for row in rows], dtype=np.int64)
    require(set(runs.tolist()) == set(range(12)) and np.all(runs[1:] >= runs[:-1]), "original acquisition run identity/order changed")
    for run in range(12):
        counts = Counter(labels[runs == run].tolist())
        require(counts == {"rest": 49, **dict.fromkeys(CATEGORIES, 9)}, "per-run original label support changed")
    return labels, runs


def verify_inputs(data_dir):
    data_dir = Path(data_dir)
    manifest_path = data_dir / "data_manifest.json"
    reject_symlinks(manifest_path)
    require(sha256(manifest_path) == MANIFEST_SHA256, "original source manifest SHA256 mismatch")
    manifest = json.loads(manifest_path.read_text())
    require(manifest["task_id"] == "OBJCAT-001" and manifest["subject"] == 2, "wrong source task/subject")
    require(len(manifest["files"]) == 3 and {entry["role"] for entry in manifest["files"]} == set(SOURCE_PINS), "wrong source file set")
    paths, hashes = {}, {}
    for entry in manifest["files"]:
        expected = SOURCE_PINS[entry["role"]]
        require((entry["path"], entry["size_bytes"], entry["sha256"]) == expected, "source identity does not match hard pins")
        path = data_dir / expected[0]
        reject_symlinks(path)
        require(path.is_file() and path.stat().st_size == expected[1] and sha256(path) == expected[2], "original source size/hash mismatch")
        paths[entry["role"]], hashes[entry["path"]] = path, expected[2]
    labels, runs = source_labels(paths["labels"])
    return paths, hashes, labels, runs


def image_geometry(bold, mask):
    require(len(bold.shape) == 4 and len(mask.shape) == 3 and tuple(bold.shape[:3]) == tuple(mask.shape), "unaligned image dimensions")
    require(bold.shape[3] == 1452, "wrong original time dimension")
    require(np.isfinite(bold.affine).all() and np.isfinite(mask.affine).all(), "nonfinite affine")
    require(np.allclose(bold.affine, mask.affine, atol=1e-6, rtol=0), "mask affine differs; no resampling")
    zooms = np.asarray(bold.header.get_zooms(), dtype=float)
    require(np.isfinite(zooms).all() and np.all(zooms > 0), "invalid original voxel/time sizes")
    return {"bold_shape": list(bold.shape), "mask_shape": list(mask.shape), "affine": bold.affine.tolist(),
            "header_zooms": zooms.tolist(), "header_units": list(bold.header.get_xyzt_units()),
            "stored_bold_dtype": str(bold.get_data_dtype()), "stored_mask_dtype": str(mask.get_data_dtype())}


def clean_full_runs(X, runs):
    """SciPy least-squares detrend, separate full-run sample standardization.

    Center before detrending so exactly constant source signals remain zero.
    Recenter the residual and apply the public float64-epsilon divisor convention.
    No original task/rest labels enter this operation.
    """
    X, runs = np.asarray(X, dtype=np.float64), np.asarray(runs)
    require(X.ndim == 2 and runs.shape == (len(X),) and np.isfinite(X).all(), "invalid independent cleaning input")
    cleaned = np.empty_like(X)
    constant_counts = {}
    for run in sorted(set(runs.tolist())):
        use = np.flatnonzero(runs == run)
        require(len(use) > 1, "sample standard deviation requires more than one volume")
        values = np.array(X[use], dtype=np.float64, copy=True)
        values -= values.mean(axis=0)
        residual = detrend(values, axis=0, type="linear", overwrite_data=False)
        residual -= residual.mean(axis=0)
        std = residual.std(axis=0, ddof=1)
        near_constant = std < np.finfo(np.float64).eps
        std[near_constant] = 1.
        cleaned[use] = residual / std
        constant_counts[str(int(run))] = int(np.count_nonzero(near_constant))
    require(np.isfinite(cleaned).all(), "independent cleaning produced nonfinite values")
    return cleaned, constant_counts


def prepare_original(paths, labels, runs):
    bold, mask = nib.load(paths["bold"]), nib.load(paths["mask"])
    geometry = image_geometry(bold, mask)
    # get_fdata applies original slope/intercept explicitly in float64. Never resample.
    image = bold.get_fdata(dtype=np.float64, caching="unchanged")
    mask_values = mask.get_fdata(dtype=np.float64, caching="unchanged")
    require(np.isfinite(image).all() and np.isfinite(mask_values).all(), "nonfinite scaled source image/mask")
    require(np.all((mask_values == 0) | (mask_values == 1)), "supplied mask is not binary")
    positions = np.flatnonzero(mask_values.ravel(order="C") == 1)
    require(len(positions) >= K, "insufficient mask features")
    coordinates = np.column_stack(np.unravel_index(positions, mask_values.shape, order="C")).astype(np.int64)
    X = np.array(image.reshape((-1, image.shape[-1]), order="C")[positions].T, dtype=np.float64, order="C")
    del image, mask_values
    cleaned, constants = clean_full_runs(X, runs)
    del X
    keep = np.asarray([label != "rest" for label in labels])
    prepared = {"X": cleaned[keep], "mask_ijk": coordinates, "volume_id": np.flatnonzero(keep),
                "run": runs[keep], "true_label": labels[keep], "full_run": runs, "full_label": labels}
    report = {"geometry": geometry, "n_full_volumes": len(labels), "n_nonrest_volumes": int(keep.sum()),
              "n_mask_voxels": len(positions), "scaled_source_all_finite": True, "mask_finite_binary": True,
              "cleaned_dtype": str(cleaned.dtype), "near_constant_features_per_full_run": constants,
              "source_slope": float(bold.dataobj.slope), "source_intercept": float(bold.dataobj.inter)}
    return prepared, report


def explicit_anova(X, labels):
    """Between/within centered sum-of-squares, not sklearn's f_classif routine."""
    X, labels = np.asarray(X, dtype=np.float64), np.asarray(labels)
    require(X.ndim == 2 and labels.shape == (len(X),) and np.isfinite(X).all(), "invalid ANOVA inputs")
    groups = sorted(set(labels.tolist()))
    require(len(groups) >= 2 and len(X) > len(groups), "insufficient ANOVA degrees of freedom")
    grand_mean = X.mean(axis=0)
    between, within = np.zeros(X.shape[1]), np.zeros(X.shape[1])
    for group in groups:
        block = X[labels == group]
        group_mean = block.mean(axis=0)
        between += len(block) * (group_mean - grand_mean) ** 2
        centered = block - group_mean
        within += np.einsum("ij,ij->j", centered, centered)
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = (between / (len(groups) - 1)) / (within / (len(X) - len(groups)))
    return scores


def selected_features(scores, k):
    scores = np.asarray(scores, dtype=np.float64)
    require(scores.ndim == 1 and 0 < k <= len(scores) and np.count_nonzero(np.isfinite(scores)) >= k, "insufficient finite ANOVA candidates")
    floor = np.finfo(np.float64).min
    # Python's explicit score/index tuple ordering is independently implemented.
    ordered = sorted(range(len(scores)), key=lambda index: (floor if np.isnan(scores[index]) else float(scores[index]), index))
    selected = np.asarray(sorted(ordered[-k:]), dtype=np.int64)
    require(np.isfinite(scores[selected]).all(), "nonfinite selected ANOVA score")
    return selected


def fit_independent(prepared, k=K):
    X, labels, runs = prepared["X"], prepared["true_label"], prepared["run"]
    require(X.dtype == np.float64 and np.isfinite(X).all(), "classifier input is not finite float64")
    levels = np.asarray(sorted(set(runs.tolist())), dtype=np.int64)
    classes = np.asarray(sorted(set(labels.tolist())))
    prediction = np.empty_like(labels)
    selected_sets, scores_all, scores_selected, fold_accuracy, n_train, n_test, warnings_by_run = [], [], [], [], [], [], {}
    for run in levels:
        train = np.flatnonzero(runs != run)
        test = np.flatnonzero(runs == run)
        require(len(test) > 0 and np.array_equal(np.unique(labels[train]), classes), "fold lacks required train/test support")
        scores = explicit_anova(X[train], labels[train])
        selected = selected_features(scores, k)
        estimator = SVC(**SVC_SETTINGS)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            estimator.fit(X[np.ix_(train, selected)], labels[train])
        require(estimator.fit_status_ == 0 and np.array_equal(estimator.classes_, classes), "independent SVC failed or class ordering changed")
        values = estimator.predict(X[np.ix_(test, selected)])
        require(set(values) <= set(classes), "prediction outside original classes")
        prediction[test] = values
        selected_sets.append(selected); scores_all.append(scores); scores_selected.append(scores[selected])
        fold_accuracy.append(sum(actual == expected for actual, expected in zip(values, labels[test])) / len(test))
        n_train.append(len(train)); n_test.append(len(test))
        warnings_by_run[str(int(run))] = [str(item.message) for item in captured]
    arrays = {key: value for key, value in prepared.items() if key != "X"}
    arrays.update(run_ids=levels, classes=classes, predicted_label=prediction, selected_indices=np.asarray(selected_sets),
                  anova_f=np.asarray(scores_all), selected_f=np.asarray(scores_selected), fold_accuracy=np.asarray(fold_accuracy),
                  fold_n_train=np.asarray(n_train), fold_n_test=np.asarray(n_test))
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, "cv_accuracy": math.fsum(fold_accuracy) / len(levels),
              "n_samples": len(labels), "n_voxels": X.shape[1], "n_selected": k, "n_categories": len(classes),
              "n_runs": len(levels), "chance": 1 / len(classes)}
    return arrays, result, warnings_by_run


def read_template(path, hashes, geometry):
    template = json.loads(Path(path).read_text())
    require(template["pipeline_id"] == PIPELINE_ID and template["source_manifest_sha256"] == MANIFEST_SHA256, "wrong public template identity")
    require(template["source_sha256"] == hashes and template["geometry"] == geometry, "template source hashes/geometry differ from original")
    require(template["classifier"] == {"name": "SVC", **SVC_SETTINGS}, "public classifier settings changed")
    require(template["feature_selection"]["k"] == K and template["preprocessing"]["standard_deviation_ddof"] == 1
            and template["preprocessing"]["dtype"] == "float64", "public numerical contract changed")
    return template


def write_csv(path, fields, rows):
    with path.open("x", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(fields); writer.writerows(rows)


def emit_outputs(output, arrays, result, template):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "predictions.csv", ("volume_id", "held_out_run", "true_label", "predicted_label"),
              zip(arrays["volume_id"], arrays["run"], arrays["true_label"], arrays["predicted_label"]))
    write_csv(output / "per_fold.csv", ("fold", "held_out_run", "n_train_samples", "n_test_samples", "accuracy"),
              ((index + 1, run, arrays["fold_n_train"][index], arrays["fold_n_test"][index], arrays["fold_accuracy"][index]) for index, run in enumerate(arrays["run_ids"])))
    write_csv(output / "selected_features.csv", ("held_out_run", "feature_index", "i", "j", "k", "f_statistic"),
              ((run, feature, *arrays["mask_ijk"][feature], score) for index, run in enumerate(arrays["run_ids"])
               for feature, score in zip(arrays["selected_indices"][index], arrays["selected_f"][index])))
    metadata = {**template, "status": "ok", "n_full_volumes": len(arrays["full_label"]), "cleaned_dtype": "float64",
                **{key: result[key] for key in ("n_samples", "n_voxels", "n_selected", "n_categories", "n_runs")},
                "independent_implementation": "Equivalent public target recipe: NiBabel original float64 extraction, SciPy linear detrend/sample SD, centered explicit ANOVA, Python stable score/index selection, fresh sklearn libsvm fits."}
    for name, value in (("decoding_results.json", result), ("run_metadata.json", metadata)):
        with (output / name).open("x") as stream: stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
    with (output / "findings.md").open("x") as stream:
        stream.write(f"Mean held-out-run accuracy: {result['cv_accuracy']:.10f} across {result['n_runs']} runs. "
                     "Feature selection used training-run labels only. Full-run unlabeled cleaning includes rest and is an offline normalization, not online decoding. "
                     "This is a single-subject whole-brain method case, not the paper's original pattern-correlation result, localization, or population inference. "
                     "ANOVA scores rank features but are not voxelwise inferential significance. Mask generation/independent-selection provenance is unresolved.\n")


def exact_int(value):
    try: number = Decimal(str(value))
    except InvalidOperation as error: raise ValueError("malformed oracle CSV integer") from error
    require(number.is_finite() and number == number.to_integral_value() and 0 <= number <= np.iinfo(np.int64).max,
            "oracle CSV identity/count is not an exact nonnegative integer")
    return int(number)


def csv_table(path, fields, key_names):
    result = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames)
                and set(fields) <= set(reader.fieldnames), "oracle CSV header/schema mismatch")
        for row in reader:
            require(None not in row and all(value is not None for value in row.values()), "malformed oracle CSV row")
            key = tuple(exact_int(row[name]) for name in key_names)
            require(key not in result, "duplicate oracle CSV source key")
            result[key] = row
    return result


def compare_oracle_csvs(oracle, arrays):
    """Only genuine public CSVs, not private oracle arrays or a reference bank."""
    oracle = Path(oracle)
    predictions = csv_table(oracle / "predictions.csv", ("volume_id", "held_out_run", "true_label", "predicted_label"), ("volume_id",))
    require(set(predictions) == {(int(value),) for value in arrays["volume_id"]}, "oracle source volume membership differs")
    disagreements = []
    for j, volume in enumerate(arrays["volume_id"]):
        row = predictions[(int(volume),)]
        require(exact_int(row["held_out_run"]) == arrays["run"][j] and row["true_label"] == arrays["true_label"][j], "oracle sample/source-label association differs")
        if row["predicted_label"] != arrays["predicted_label"][j]:
            disagreements.append({"volume_id": int(volume), "run": int(arrays["run"][j]), "oracle": row["predicted_label"], "independent": str(arrays["predicted_label"][j])})
    features = csv_table(oracle / "selected_features.csv", ("held_out_run", "feature_index", "i", "j", "k", "f_statistic"), ("held_out_run", "feature_index"))
    expected_keys = {(int(run), int(feature)) for index, run in enumerate(arrays["run_ids"]) for feature in arrays["selected_indices"][index]}
    membership_different = sorted(set(features) ^ expected_keys)
    max_f_difference, bad_f, bad_coordinates, per_run = 0., [], [], []
    for index, run in enumerate(arrays["run_ids"]):
        wanted = set(arrays["selected_indices"][index].tolist())
        actual = {key[1] for key in features if key[0] == run}
        maximum = 0.
        for feature, expected_f in zip(arrays["selected_indices"][index], arrays["selected_f"][index]):
            key = (int(run), int(feature))
            if key not in features: continue
            row = features[key]
            if [exact_int(row[name]) for name in ("i", "j", "k")] != arrays["mask_ijk"][feature].tolist(): bad_coordinates.append(list(key))
            actual_f = float(row["f_statistic"])
            require(math.isfinite(actual_f), "nonfinite oracle F score")
            difference = abs(actual_f - float(expected_f))
            maximum, max_f_difference = max(maximum, difference), max(max_f_difference, difference)
            if difference > F_ATOL + F_RTOL * abs(float(expected_f)): bad_f.append(list(key))
        per_run.append({"held_out_run": int(run), "n_selected": len(wanted), "selected_sets_equal": actual == wanted,
                        "max_abs_F_difference": maximum, "independent_accuracy": float(arrays["fold_accuracy"][index])})
    folds = csv_table(oracle / "per_fold.csv", ("fold", "held_out_run", "n_train_samples", "n_test_samples", "accuracy"), ("held_out_run",))
    require(set(folds) == {(int(value),) for value in arrays["run_ids"]}, "oracle held-out fold set differs")
    fold_errors = []
    for index, run in enumerate(arrays["run_ids"]):
        row = folds[(int(run),)]
        require(exact_int(row["fold"]) == index + 1 and exact_int(row["n_train_samples"]) == arrays["fold_n_train"][index]
                and exact_int(row["n_test_samples"]) == arrays["fold_n_test"][index], "oracle fold sample identities differ")
        accuracy = float(row["accuracy"])
        if not math.isfinite(accuracy) or abs(accuracy - arrays["fold_accuracy"][index]) > 1e-6: fold_errors.append(int(run))
    passed = not (disagreements or membership_different or bad_f or bad_coordinates or fold_errors)
    return {"passed": passed, "n_predictions": len(predictions), "prediction_disagreements": disagreements,
            "selected_membership_symmetric_difference": membership_different, "F_tolerance_failures": bad_f,
            "coordinate_mismatches": bad_coordinates, "fold_accuracy_mismatches": fold_errors,
            "max_abs_selected_F_difference": max_f_difference, "per_run": per_run}


def run_check(data_dir, oracle, output, template_path, report_path):
    fresh_paths(output, report_path)
    paths, hashes, labels, runs = verify_inputs(data_dir)
    prepared, source_report = prepare_original(paths, labels, runs)
    template = read_template(template_path, hashes, source_report["geometry"])
    arrays, result, fit_warnings = fit_independent(prepared)
    del prepared
    emit_outputs(output, arrays, result, template)
    artifact = Path(report_path).with_suffix(".arrays.npz")
    with artifact.open("xb") as stream:
        np.savez_compressed(stream, **arrays, pipeline_id=PIPELINE_ID, source_sha256_json=json.dumps(hashes),
                            source_manifest_sha256=MANIFEST_SHA256, results_json=json.dumps(result, allow_nan=False))
    comparison = compare_oracle_csvs(oracle, arrays)
    output_hashes = {path.name: sha256(path) for path in Path(output).iterdir() if path.is_file()}
    return {"status": "passed" if comparison["passed"] else "failed", "pipeline_id": PIPELINE_ID,
            "source_sha256": hashes, "source_manifest_sha256": MANIFEST_SHA256,
            "public_method_contract_sha256": sha256(template_path), "source": source_report,
            "independent_components": ["original content-pinned NiBabel float64 extraction in C-order", "separate full-run SciPy least-squares detrend and sample SD including rest",
                                       "explicit centered between/within-class ANOVA sums", "Python score/index stable tie order and original voxel coordinates", "fresh 12 held-out-run classifier fits"],
            "shared_components": ["original acquisition, supplied mask and source labels", "NiBabel reader", "NumPy/SciPy numerical libraries", "same sklearn SVC/libsvm classifier and public fixed settings"],
            "limitations": ["Not independent classifier implementation or biological replication.", "One-subject offline-normalized method case, not online or population performance.", "No frontier-agent difficulty evidence."],
            "versions": {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-learn", "nibabel", "nilearn")}},
            "result": result, "comparison": comparison, "fit_warnings": fit_warnings,
            "independent_output_directory": str(output), "independent_output_sha256": output_hashes,
            "independent_arrays": str(artifact), "independent_arrays_sha256": sha256(artifact)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="/app/data/objcat")
    parser.add_argument("--oracle-output", required=True)
    parser.add_argument("--output-dir", required=True, help="Fresh participant-compatible independent output directory")
    parser.add_argument("--method-contract", default="/app/method_contract.json")
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    report_path = Path(args.report)
    try: fresh_paths(args.output_dir, report_path)
    except ValueError as error:
        print(json.dumps({"status": "failed", "error": str(error)})); return 1
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try: report = run_check(args.data_dir, args.oracle_output, args.output_dir, args.method_contract, report_path)
    except Exception as error:
        report = {"status": "failed", "pipeline_id": PIPELINE_ID, "error_type": type(error).__name__, "error": str(error)}
    with report_path.open("x") as stream: stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "report": str(report_path)}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__": raise SystemExit(main())
