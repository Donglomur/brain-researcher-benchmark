"""Source-bound whole-brain nested-feature decoding, Haxby subject 2.

This is a modern single-subject method case, not the paper's original statistic,
an anatomical localization result, population inference, or online decoding.
Import is safe: no downloads, input reads, output creation or model fits.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import warnings

import numpy as np

TASK_ID = "OBJCAT-001"
PIPELINE_ID = "haxby2-runwise-anova500-loro-v2"
SUBJECT = 2
K = 500
CATEGORIES = np.asarray(["bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe"])
MANIFEST_SHA256 = "702e97410687dea0193f5d300d988e86c02a1c14cd1fac3016f7a6f7d865cb3a"
SOURCE_PATHS = {"bold": "subj2/bold.nii.gz", "labels": "subj2/labels.txt", "mask": "mask.nii.gz"}
SVC_PARAMETERS = {"kernel": "linear", "C": 1.0, "degree": 3, "gamma": "scale", "coef0": 0.0,
                  "tol": 0.001, "shrinking": True, "cache_size": 200, "probability": False,
                  "class_weight": None, "verbose": False, "max_iter": -1,
                  "decision_function_shape": "ovr", "break_ties": False, "random_state": None}


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_labels(path):
    lines = Path(path).read_text().splitlines()
    if not lines or lines[0].split() != ["labels", "chunks"]:
        raise ValueError("expected original labels/chunks table")
    labels, runs = [], []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError("malformed original source label row")
        labels.append(parts[0]); runs.append(int(parts[1]))
    labels, runs = np.asarray(labels), np.asarray(runs, dtype=np.int64)
    if labels.shape != (1452,) or not np.array_equal(np.unique(runs), np.arange(12)):
        raise ValueError("source must contain 1452 volumes across acquisition runs 0..11")
    if np.any(np.diff(runs) < 0) or set(labels) != set(CATEGORIES) | {"rest"}:
        raise ValueError("source runs must retain chronological order and original categories")
    for run in range(12):
        values = labels[runs == run]
        if len(values) != 121 or np.count_nonzero(values == "rest") != 49:
            raise ValueError("each complete original run must have 121 volumes including 49 rest")
        if any(np.count_nonzero(values == label) != 9 for label in CATEGORIES):
            raise ValueError("each original run must have nine volumes in each of eight categories")
    return labels, runs


def geometry(bold, mask):
    if len(bold.shape) != 4 or len(mask.shape) != 3 or tuple(bold.shape[:3]) != tuple(mask.shape):
        raise ValueError("BOLD and supplied mask must share a three-dimensional voxel grid")
    if bold.shape[3] != 1452:
        raise ValueError("original BOLD must contain all 1452 source volumes")
    if not np.isfinite(bold.affine).all() or not np.isfinite(mask.affine).all():
        raise ValueError("nonfinite source image geometry")
    if not np.allclose(bold.affine, mask.affine, atol=1e-6, rtol=0):
        raise ValueError("mask/BOLD affines differ; no silent resampling")
    zooms = np.asarray(bold.header.get_zooms(), float)
    if not np.isfinite(zooms).all() or np.any(zooms <= 0):
        raise ValueError("invalid source voxel/time dimensions")
    return {"bold_shape": list(bold.shape), "mask_shape": list(mask.shape),
            "affine": np.asarray(bold.affine).tolist(), "header_zooms": zooms.tolist(),
            "header_units": list(bold.header.get_xyzt_units()),
            "stored_bold_dtype": str(bold.get_data_dtype()), "stored_mask_dtype": str(mask.get_data_dtype())}


def load_inputs(data):
    """Authenticate original bytes, headers and labels; no voxel extraction/fits."""
    import nibabel as nib

    data = Path(data)
    manifest_path = data / "data_manifest.json"
    if MANIFEST_SHA256 is None or sha256_file(manifest_path) != MANIFEST_SHA256:
        raise ValueError("source manifest is not the frozen authenticated task manifest")
    manifest = json.loads(manifest_path.read_text())
    entries = manifest["files"]
    if len(entries) != 3 or {entry["role"]: entry["path"] for entry in entries} != SOURCE_PATHS:
        raise ValueError("expected exactly original subject2 BOLD/labels and supplied whole-brain mask")
    paths, hashes = {}, {}
    for entry in entries:
        path = data / entry["path"]
        if not path.resolve().is_relative_to(data.resolve()):
            raise ValueError("source path escapes data directory")
        if path.stat().st_size != entry["size_bytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"source checksum/size mismatch: {entry['path']}")
        paths[entry["role"]] = path
        hashes[entry["path"]] = entry["sha256"]
    bold, mask = nib.load(paths["bold"]), nib.load(paths["mask"])
    header = geometry(bold, mask)
    labels, runs = read_labels(paths["labels"])
    return {"paths": paths, "manifest": manifest, "source_sha256": hashes,
            "geometry": header, "full_label": labels, "full_run": runs}


def metadata_contract(inputs):
    """Public static contract; reads nothing and performs no signal processing."""
    return {
        "task_id": TASK_ID, "pipeline_id": PIPELINE_ID, "dataset_id": "haxby2001", "subject": SUBJECT,
        "source_manifest_sha256": MANIFEST_SHA256, "source_sha256": inputs["source_sha256"],
        "geometry": inputs["geometry"],
        "mask": {"path": SOURCE_PATHS["mask"], "scope": "supplied whole-brain mask",
                 "membership": "finite binary source mask values == 1", "feature_order": "C-order voxel index",
                 "resampling": False, "smoothing_fwhm": None, "affine_match_atol": 1e-6},
        "preprocessing": {"extraction": "original scaled BOLD values inside fixed mask; float64",
                          "cleaning_unit": "full acquisition run including rest",
                          "implementation": "nilearn.signal.clean", "detrend": True,
                          "standardize": "zscore_sample", "standard_deviation_ddof": 1,
                          "t_r": 2.5, "low_pass": None, "high_pass": None,
                          "confounds": None, "sample_mask": None, "ensure_finite": False,
                          "rest_removal": "after full-run cleaning", "dtype": "float64"},
        "samples": {"categories": CATEGORIES.tolist(), "n_full_volumes": 1452,
                    "n_nonrest_volumes": 864, "run_ids": list(range(12)),
                    "full_volumes_per_run": 121, "nonrest_volumes_per_run": 72,
                    "class_volumes_per_run": 9, "volume_id": "zero-based original BOLD volume"},
        "feature_selection": {"name": "SelectKBest", "score_func": "f_classif", "k": K,
                              "fit_scope": "training runs only, refit for each held-out run",
                              "sort": "stable ascending mergesort, select last 500",
                              "exact_tie": "larger C-order feature index wins at cutoff",
                              "nan_scores": "rank as float64 minimum; retain diagnostic NaN",
                              "precondition": "at least 500 finite F scores and all selected F scores finite",
                              "classifier_feature_order": "ascending source feature index",
                              "interpretation": "feature ranking, not voxelwise inferential significance"},
        "classifier": {"name": "SVC", **SVC_PARAMETERS},
        "cross_validation": {"name": "leave-one-run-out", "headline": "unweighted mean of 12 fold accuracies",
                             "training_samples_per_fold": 792, "test_samples_per_fold": 72,
                             "prediction": "libsvm one-vs-one votes; break_ties=false, not argmax OVR scores"},
        "numerical_tolerances": {"f_statistic_atol": 1e-8, "f_statistic_rtol": 1e-6,
                                 "accuracy_atol": 1e-6, "identities_selected_features_predicted_labels": "exact"},
        "software": {"numpy": "2.2.6", "scipy": "1.17.0", "scikit-learn": "1.8.0",
                     "nilearn": "0.13.1", "nibabel": "5.4.2"},
    }


def extract_and_clean(bold_data, mask_data, full_runs):
    """Extract source C-order voxels and clean complete runs in float64."""
    from nilearn.signal import clean

    bold_data, mask_data = np.asarray(bold_data), np.asarray(mask_data)
    if bold_data.ndim != 4 or mask_data.shape != bold_data.shape[:3] or len(full_runs) != bold_data.shape[3]:
        raise ValueError("signal, mask and run lengths disagree")
    if not np.isfinite(bold_data).all() or not np.isfinite(mask_data).all():
        raise ValueError("nonfinite original source signal/mask; no voxel or sample imputation")
    if not np.all((mask_data == 0) | (mask_data == 1)):
        raise ValueError("provided source mask must be binary; no implicit thresholding")
    mask = mask_data != 0
    mask_ijk = np.argwhere(mask).astype(np.int64)
    if len(mask_ijk) < K:
        raise ValueError("provided mask has fewer than 500 features")
    extracted = bold_data[mask].T.astype(np.float64, copy=True)
    cleaned = clean(extracted, runs=np.asarray(full_runs), detrend=True, standardize="zscore_sample",
                    confounds=None, sample_mask=None, standardize_confounds=True, filter="butterworth",
                    low_pass=None, high_pass=None, t_r=2.5, ensure_finite=False, extrapolate=False)
    if cleaned.dtype != np.float64 or not np.isfinite(cleaned).all():
        raise ValueError("cleaning did not produce finite float64 data")
    return cleaned, mask_ijk


def prepare_source(inputs):
    import nibabel as nib

    bold_img, mask_img = nib.load(inputs["paths"]["bold"]), nib.load(inputs["paths"]["mask"])
    geometry(bold_img, mask_img)
    # Read compressed image exactly once; nibabel applies stored slope/intercept.
    bold = np.asanyarray(bold_img.dataobj)
    mask = np.asanyarray(mask_img.dataobj)
    cleaned, mask_ijk = extract_and_clean(bold, mask, inputs["full_run"])
    del bold, mask
    keep = inputs["full_label"] != "rest"
    volume_id = np.flatnonzero(keep).astype(np.int64)
    return {"X": cleaned[keep], "mask_ijk": mask_ijk, "volume_id": volume_id,
            "run": inputs["full_run"][keep], "true_label": inputs["full_label"][keep],
            "full_volume_id": np.arange(len(keep)), "full_run": inputs["full_run"],
            "full_label": inputs["full_label"]}


def select_features(X, y, k=K):
    from sklearn.feature_selection import SelectKBest, f_classif

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        selector = SelectKBest(f_classif, k=k).fit(X, y)
    scores = np.asarray(selector.scores_, dtype=np.float64)
    indices = selector.get_support(indices=True).astype(np.int64)
    if np.count_nonzero(np.isfinite(scores)) < k or len(indices) != k or not np.isfinite(scores[indices]).all():
        raise ValueError("insufficient finite ANOVA support or nonfinite selected F statistic")
    return scores, indices, [str(item.message) for item in caught]


def fit_nested(prepared, k=K, select_once=False, held_out_runs=None):
    """Fit fixed nested recipe; select_once is an authoring negative control."""
    from sklearn.svm import SVC

    X, y, runs = prepared["X"], prepared["true_label"], prepared["run"]
    if X.dtype != np.float64 or X.ndim != 2 or not np.isfinite(X).all():
        raise ValueError("classifier inputs must be finite float64")
    classes, source_run_ids = np.unique(y), np.unique(runs)
    run_ids = source_run_ids if held_out_runs is None else np.asarray(held_out_runs, dtype=np.int64)
    if not len(run_ids) or not np.array_equal(run_ids, np.unique(run_ids)) or not set(run_ids) <= set(source_run_ids):
        raise ValueError("requested held-out runs must be unique, ordered original acquisition IDs")
    nc, nf, ns, nv = len(classes), len(run_ids), len(y), X.shape[1]
    n_pairs = nc * (nc - 1) // 2
    if nc < 3 or len(source_run_ids) < 2:
        raise ValueError("multiclass run-held-out fit needs >=3 classes and >=2 runs")
    arrays = {key: value for key, value in prepared.items() if key != "X"}
    arrays.update(run_ids=run_ids, classes=classes, anova_f=np.empty((nf, nv)),
                  selected_indices=np.empty((nf, k), dtype=np.int64), selected_f=np.empty((nf, k)),
                  predicted_label=np.empty(ns, dtype=y.dtype), decision_ovr=np.empty((ns, nc)),
                  decision_ovo=np.empty((ns, n_pairs)), fold_n_train=np.empty(nf, dtype=np.int64),
                  fold_n_test=np.empty(nf, dtype=np.int64), fold_accuracy=np.empty(nf),
                  classifier_coef=np.empty((nf, n_pairs, k)), classifier_intercept=np.empty((nf, n_pairs)),
                  classifier_n_support=np.empty((nf, nc), dtype=np.int64),
                  classifier_n_iter=np.empty((nf, n_pairs), dtype=np.int64),
                  classifier_fit_status=np.empty(nf, dtype=np.int64))
    all_warnings = {}
    global_selection = select_features(X, y, k) if select_once else None
    for fi, run in enumerate(run_ids):
        train, test = np.flatnonzero(runs != run), np.flatnonzero(runs == run)
        if not np.array_equal(np.unique(y[train]), classes) or not len(test):
            raise ValueError("fold has missing training class or empty held-out support")
        scores, selected, feature_warnings = global_selection if select_once else select_features(X[train], y[train], k)
        model = SVC(**SVC_PARAMETERS)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(X[np.ix_(train, selected)], y[train])
        if model.fit_status_ != 0 or not np.array_equal(model.classes_, classes):
            raise ValueError("SVC did not converge with all source classes")
        heldout = X[np.ix_(test, selected)]
        predicted = model.predict(heldout)
        ovr = model.decision_function(heldout)
        model.decision_function_shape = "ovo"
        ovo = model.decision_function(heldout)
        if not np.isfinite(ovr).all() or not np.isfinite(ovo).all():
            raise ValueError("nonfinite held-out classifier decision")
        arrays["anova_f"][fi], arrays["selected_indices"][fi], arrays["selected_f"][fi] = scores, selected, scores[selected]
        arrays["predicted_label"][test], arrays["decision_ovr"][test], arrays["decision_ovo"][test] = predicted, ovr, ovo
        arrays["fold_n_train"][fi], arrays["fold_n_test"][fi] = len(train), len(test)
        arrays["fold_accuracy"][fi] = np.mean(predicted == y[test])
        arrays["classifier_coef"][fi], arrays["classifier_intercept"][fi] = model.coef_, model.intercept_
        arrays["classifier_n_support"][fi], arrays["classifier_n_iter"][fi] = model.n_support_, model.n_iter_
        arrays["classifier_fit_status"][fi] = model.fit_status_
        arrays[f"svc_support_volume_ids_{int(run)}"] = prepared["volume_id"][train[model.support_]]
        arrays[f"svc_dual_coef_{int(run)}"] = model.dual_coef_
        all_warnings[str(int(run))] = feature_warnings + [str(item.message) for item in caught]
    arrays["warnings_json"] = json.dumps(all_warnings)
    pilot = not np.array_equal(run_ids, source_run_ids)
    if pilot:
        retained = np.isin(runs, run_ids)
        for key in ("volume_id", "run", "true_label", "predicted_label", "decision_ovr", "decision_ovo"):
            arrays[key] = arrays[key][retained]
    result = {"status": "resource_pilot" if pilot else "ok", "pipeline_id": PIPELINE_ID,
              "cv_accuracy": float(arrays["fold_accuracy"].mean()), "n_samples": len(arrays["volume_id"]),
              "n_voxels": nv, "n_selected": k, "n_categories": nc, "n_runs": nf, "chance": 1.0 / nc}
    if pilot:
        result.update(n_available_samples=ns, n_available_runs=len(source_run_ids))
    return arrays, result


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(fields); writer.writerows(rows)


def write_outputs(output, inputs, arrays, result, control=False):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "predictions.csv", ("volume_id", "held_out_run", "true_label", "predicted_label"),
              zip(arrays["volume_id"], arrays["run"], arrays["true_label"], arrays["predicted_label"]))
    write_csv(output / "per_fold.csv", ("fold", "held_out_run", "n_train_samples", "n_test_samples", "accuracy"),
              ((fi + 1, run, arrays["fold_n_train"][fi], arrays["fold_n_test"][fi], arrays["fold_accuracy"][fi])
               for fi, run in enumerate(arrays["run_ids"])))
    write_csv(output / "selected_features.csv", ("held_out_run", "feature_index", "i", "j", "k", "f_statistic"),
              ((run, feature, *arrays["mask_ijk"][feature], score)
               for fi, run in enumerate(arrays["run_ids"])
               for feature, score in zip(arrays["selected_indices"][fi], arrays["selected_f"][fi])))
    metadata = {**metadata_contract(inputs), "status": result["status"], "cleaned_dtype": "float64",
                "n_full_volumes": len(arrays["full_volume_id"]),
                **{key: result[key] for key in ("n_samples", "n_voxels", "n_selected", "n_categories", "n_runs")}}
    for name, value in (("decoding_results.json", result), ("run_metadata.json", metadata)):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    findings = (f"# Whole-brain nested-feature object decoding\n\nMean held-out-run accuracy was {result['cv_accuracy']:.8f} "
                f"across {result['n_runs']} acquisition runs ({result['n_samples']} object volumes; chance {result['chance']}). "
                "The supplied whole-brain mask was cleaned in float64, separately within each full run including rest. "
                "Only training-run labels determined each fold's 500 ANOVA-selected features. Test-run normalization "
                "uses the complete unlabeled test run; this is offline run-held-out decoding, not online prediction. "
                "The ANOVA values rank autocorrelated volumes and are not voxelwise inferential significance. "
                "Accuracy is conditional on this subject, mask and recipe; it neither localizes the information to "
                "occipitotemporal cortex nor reproduces the original paper's pattern-correlation statistic or supports "
                "population-level claims. No circular-selection accuracy gap is assumed.\n")
    if control:
        findings = ("# Authoring-only negative control\n\nFeatures were deliberately selected once using all run labels. "
                    "The other metadata claims the valid recipe intentionally so rejection tests numerical lineage, "
                    "not a conveniently false declaration. This is not a scientific reference result.\n")
    elif result["status"] == "resource_pilot":
        findings = "# Resource pilot only\n\nOnly the first held-out run was fitted. This is not the twelve-run result or a valid reference bank.\n"
    (output / "findings.md").write_text(findings)
    np.savez_compressed(output / "analysis_arrays.npz", **arrays,
                        metadata_json=json.dumps(metadata, allow_nan=False),
                        results_json=json.dumps(result, allow_nan=False))
    return metadata


def write_failure(output, error):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    value = {"status": "failed_precondition", "pipeline_id": PIPELINE_ID, "reason": str(error)}
    for name in ("decoding_results.json", "run_metadata.json"):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    (output / "findings.md").write_text("# Failed precondition\n\n" + str(error) + "\n")


def inspect_source(inputs):
    """Header/labels/raw finite-support checks only; no cleaning or model fit."""
    import nibabel as nib
    bold_img, mask_img = nib.load(inputs["paths"]["bold"]), nib.load(inputs["paths"]["mask"])
    header = geometry(bold_img, mask_img)
    bold, mask = np.asanyarray(bold_img.dataobj), np.asanyarray(mask_img.dataobj)
    if not np.isfinite(bold).all() or not np.isfinite(mask).all():
        raise ValueError("source BOLD/mask contains nonfinite values")
    if not np.all((mask == 0) | (mask == 1)):
        raise ValueError("provided source mask is not binary")
    if np.count_nonzero(mask) < K:
        raise ValueError("provided mask has fewer than500 candidate voxels")
    observations = []
    for run in np.unique(inputs["full_run"]):
        use = inputs["full_run"] == run
        labels = inputs["full_label"][use]
        volume_ids = np.flatnonzero(use)
        observations.append({"run": int(run), "first_volume_id": int(volume_ids[0]),
                             "last_volume_id": int(volume_ids[-1]), "n_full_volumes": int(use.sum()),
                             "n_nonrest_volumes": int(np.count_nonzero(labels != "rest")),
                             "class_counts": {str(label): int(np.count_nonzero(labels == label))
                                              for label in np.unique(labels)}})
    return {"status": "source_structure_only", "source_sha256": inputs["source_sha256"],
            "geometry": header, "scaled_bold_dtype": str(bold.dtype),
            "stored_slope": float(bold_img.dataobj.slope), "stored_intercept": float(bold_img.dataobj.inter),
            "all_source_bold_finite": True, "mask_finite_binary": True,
            "n_voxels": int(np.count_nonzero(mask)), "n_full_volumes": len(inputs["full_label"]),
            "n_nonrest_volumes": int(np.count_nonzero(inputs["full_label"] != "rest")),
            "per_run": observations, "signal_processing_performed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="/app/data/objcat")
    parser.add_argument("--output", default=os.environ.get("OUTPUT_DIR", "/app/output"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--print-contracts", action="store_true")
    mode.add_argument("--inspect-source", action="store_true")
    parser.add_argument("--select-once-output", help="optional separate authoring-only negative-control output")
    parser.add_argument("--pilot-folds", type=int, choices=[1], help="resource pilot: fit only first held-out run; never a production bank")
    args = parser.parse_args(argv)
    if args.print_contracts or args.inspect_source:
        inputs = load_inputs(args.data)
        value = metadata_contract(inputs) if args.print_contracts else inspect_source(inputs)
        print(json.dumps(value, indent=2, allow_nan=False)); return
    try:
        if args.select_once_output and Path(args.select_once_output).resolve() == Path(args.output).resolve():
            raise ValueError("negative-control output must be a different directory")
        if args.select_once_output and args.pilot_folds:
            raise ValueError("resource pilot and negative control must be separate executions")
        inputs = load_inputs(args.data)
        prepared = prepare_source(inputs)
        arrays, result = fit_nested(prepared, held_out_runs=[0]) if args.pilot_folds else fit_nested(prepared)
        write_outputs(args.output, inputs, arrays, result)
        print(json.dumps(result, allow_nan=False))
    except Exception as error:
        write_failure(args.output, error)
        raise
    if args.select_once_output:
        try:
            control_arrays, control_result = fit_nested(prepared, select_once=True)
            write_outputs(args.select_once_output, inputs, control_arrays, control_result, control=True)
        except Exception as error:
            # Never overwrite a successful original execution with a later
            # authoring-negative failure; preserve both evidence lineages.
            write_failure(args.select_once_output, error)
            raise


if __name__ == "__main__":
    main()
