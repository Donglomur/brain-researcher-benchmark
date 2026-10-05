"""Offline, source-keyed registered-response decoding sensitivity.

This is a secondary computational recipe, not pre-movement or causal choice
coding. Importing this module performs no fit, download, or filesystem write.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import warnings

import numpy as np

PIPELINE_ID = "registered-choice-window-split-v2"
DATASET_ID = "dandi-000017-0.240329.1926"
SOURCE_NAME = "sub-Cori_ses-20161214T120000.nwb"
SOURCE_SIZE = 311814662
SOURCE_SHA256 = "d8433a826049f82cd832f41f98a9f9fafad0ac66998d4dbfd89b15b594fc4236"
ASSET_ID = "92694e6e-84fd-4198-a7e3-64e764f8e086"
WINDOWS = {"stimulus": ("visual_stimulus_time", 0.0, 0.25),
           "peri_response": ("response_time", -0.1, 0.1)}
SPLITS = ("blocked", "random")
RECIPES = tuple(f"{window}_{split}" for window in WINDOWS for split in SPLITS)
PRIMARY = "stimulus_blocked"
CLASSIFIER = {"C": 1.0, "penalty": "l2", "solver": "lbfgs", "tol": 0.0001,
              "max_iter": 2000, "fit_intercept": True, "class_weight": None,
              "random_state": None}
PREDICTION_FIELDS = ["recipe", "trial_id", "fold", "true_choice", "predicted_choice",
                     "baseline_choice", "decision_value", "probability_left"]
FOLD_FIELDS = ["recipe", "fold", "n_train", "n_test", "n_correct", "accuracy",
               "baseline_choice", "baseline_n_correct", "baseline_accuracy"]


def metadata_contract(source_sha256=None):
    """Public template: input identity and methods only; no fitted answers."""
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID,
        "dandiset_id": "000017", "dandiset_version": "0.240329.1926",
        "asset_id": ASSET_ID, "asset_path": "sub-Cori/" + SOURCE_NAME,
        "source_sha256": source_sha256 or {SOURCE_NAME: SOURCE_SHA256},
        "source_size_bytes": {SOURCE_NAME: SOURCE_SIZE},
        "trial_selection": {"included": True, "allowed_choices": [-1, 1],
                            "finite_alignment_columns": ["visual_stimulus_time", "response_time"],
                            "order": "NWB_trials_table", "chronology_check": "nondecreasing_stimulus_time"},
        "choice_labels": {"-1": "right", "1": "left"},
        "units": {"selection": "all_NWB_units", "order": "NWB_units_table", "quality_filter": None},
        "features": {"windows": {name: {"alignment": spec[0], "bounds_s": list(spec[1:])}
                                  for name, spec in WINDOWS.items()},
                     "boundary": "left_closed_right_open", "clip_to_trial": False,
                     "transform": "raw_spike_count"},
        "standardizer": {"name": "StandardScaler", "with_mean": True, "with_std": True,
                         "variance_ddof": 0, "fit_on": "training_fold_only"},
        "classifier": {"name": "LogisticRegression", **CLASSIFIER,
                       "convergence_warning": "error", "decision_zero_choice": -1},
        "cross_validation": {"blocked": {"name": "KFold", "n_splits": 5, "shuffle": False},
                             "random": {"name": "StratifiedKFold", "n_splits": 5,
                                        "shuffle": True, "random_state": 0},
                             "reuse_membership_across_windows": True},
        "baseline": {"name": "training_fold_majority", "tie_choice": -1,
                     "global_majority_fraction": "descriptive_only"},
        "aggregation": {"headline": "mean_of_five_fold_accuracies", "fold_std_ddof": 0,
                        "primary_recipe": PRIMARY, "pooled_accuracy": "all_heldout_trials"},
        "response_timing": {"before_stimulus": "response < stimulus",
                            "within_stimulus_window": "stimulus <= response < stimulus + 0.25",
                            "at_or_after_window_end": "response >= stimulus + 0.25",
                            "event": "registered_response_not_movement_onset"},
        "tolerances": {"decision_atol": 1e-6, "decision_rtol": 1e-6,
                       "probability_atol": 1e-6, "probability_rtol": 1e-6,
                       "summary_atol": 1e-6, "categorical_predictions": "exact"},
        "software": {"numpy": "2.2.6", "scipy": "1.14.1", "scikit-learn": "1.7.2", "h5py": "3.16.0"},
    }


def verify_source(data_dir):
    data_dir = Path(data_dir).resolve()
    manifest = json.loads((data_dir / "source_manifest.json").read_text())
    if (manifest.get("dandiset_id") != "000017"
            or manifest.get("dandiset_version") != "0.240329.1926"):
        raise ValueError("manifest does not identify the published dataset version")
    entries = manifest["files"]
    if len(entries) != 1:
        raise ValueError("require precisely the published session NWB")
    entry = entries[0]
    if (entry["path"] != SOURCE_NAME or entry["role"] != "session_nwb"
            or entry["sha256"] != SOURCE_SHA256 or entry["size_bytes"] != SOURCE_SIZE
            or entry["asset_id"] != ASSET_ID):
        raise ValueError("manifest does not identify the pinned published session")
    path = data_dir / SOURCE_NAME
    if path.stat().st_size != SOURCE_SIZE:
        raise ValueError("session size mismatch")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("session SHA256 mismatch")
    return path, {SOURCE_NAME: digest}


def integer_ids(values, name):
    values = np.asarray(values)
    if (values.ndim != 1 or not np.issubdtype(values.dtype, np.number)
            or not np.isfinite(values).all() or np.any(values != np.floor(values))):
        raise ValueError(f"invalid {name} identities")
    ids = values.astype(np.int64)
    if len(np.unique(ids)) != len(ids):
        raise ValueError(f"duplicate {name} identities")
    return ids


def select_trials(trial_ids, included, choices, stimulus, response):
    trial_ids = integer_ids(trial_ids, "trial")
    included, choices, stimulus, response = map(np.asarray, (included, choices, stimulus, response))
    if any(a.shape != trial_ids.shape for a in (included, choices, stimulus, response)):
        raise ValueError("trial columns have inconsistent dimensions")
    if not np.isin(included, [False, True]).all():
        raise ValueError("included is not Boolean")
    inc = included.astype(bool)
    binary = np.isin(choices, [-1, 1])
    aligned = np.isfinite(stimulus) & np.isfinite(response)
    selected = inc & binary & aligned
    if np.any(np.diff(stimulus[selected]) < 0):
        raise ValueError("selected source rows are not chronological; do not silently reorder")
    y = choices[selected].astype(np.int64)
    if any(np.sum(y == value) < 5 for value in [-1, 1]):
        raise ValueError("each response class needs at least five selected trials")
    counts = {"n_source_trials": int(len(trial_ids)), "n_not_included": int(np.sum(~inc)),
              "n_included_nonbinary_choice": int(np.sum(inc & ~binary)),
              "n_included_binary_invalid_alignment": int(np.sum(inc & binary & ~aligned)),
              "n_selected_trials": int(np.sum(selected))}
    return selected, counts


def spike_counts(spikes, centers, lower, upper):
    centers = np.asarray(centers, dtype=float)
    if centers.ndim != 1 or not np.isfinite(centers).all() or not lower < upper:
        raise ValueError("invalid feature windows")
    x = np.empty((len(centers), len(spikes)), dtype=np.int64)
    for column, times in enumerate(spikes):
        times = np.asarray(times, dtype=float)
        if times.ndim != 1 or not np.isfinite(times).all() or np.any(np.diff(times) < 0):
            raise ValueError("spike trains must be finite and nondecreasing")
        x[:, column] = (np.searchsorted(times, centers + upper, side="left")
                        - np.searchsorted(times, centers + lower, side="left"))
    return x


def load_data(data_dir):
    """Read source-verified NWB table/ragged unit arrays, without fitting."""
    import h5py
    path, source_sha256 = verify_source(data_dir)
    with h5py.File(path, "r") as nwb:
        tr, units = nwb["intervals/trials"], nwb["units"]
        ids = integer_ids(tr["id"][:], "trial")
        included, choices = tr["included"][:], tr["response_choice"][:]
        stimulus, response = tr["visual_stimulus_time"][:], tr["response_time"][:]
        selected, selection_counts = select_trials(ids, included, choices, stimulus, response)
        unit_ids = integer_ids(units["id"][:], "unit")
        annotations = np.asarray(units["phy_annotations"][:], dtype=np.int64)
        if annotations.shape != unit_ids.shape:
            raise ValueError("unit quality annotations do not align with unit IDs")
        ends = np.asarray(units["spike_times_index"][:])
        flat = np.asarray(units["spike_times"][:], dtype=float)
        if (ends.shape != unit_ids.shape or not len(ends) or not np.isfinite(ends).all()
                or np.any(ends != np.floor(ends)) or np.any(np.diff(ends) < 0)
                or ends[0] < 0 or ends[-1] != len(flat)):
            raise ValueError("invalid NWB ragged spike index")
        spikes = np.split(flat, ends[:-1].astype(np.int64))
    arrays = {"trial_ids": ids[selected], "true_choice": np.asarray(choices[selected], dtype=np.int64),
              "stimulus_times": np.asarray(stimulus[selected], dtype=float),
              "response_times": np.asarray(response[selected], dtype=float), "unit_ids": unit_ids,
              "unit_annotations": annotations}
    for window, (column, lower, upper) in WINDOWS.items():
        centers = arrays["stimulus_times" if column == "visual_stimulus_time" else "response_times"]
        arrays[f"counts_{window}"] = spike_counts(spikes, centers, lower, upper)
    selection_counts["n_source_units"] = int(len(unit_ids))
    return arrays, selection_counts, metadata_contract(source_sha256)


def fold_assignments(y):
    from sklearn.model_selection import KFold, StratifiedKFold
    result = {}
    for name, cv in [("blocked", KFold(n_splits=5, shuffle=False)),
                     ("random", StratifiedKFold(n_splits=5, shuffle=True, random_state=0))]:
        assignment = np.full(len(y), -1, dtype=np.int64)
        for fold, (train, test) in enumerate(cv.split(np.zeros((len(y), 1)), y)):
            if set(np.unique(y[train])) != {-1, 1}:
                raise ValueError("a training fold lacks a response class")
            assignment[test] = fold
        if np.any(assignment < 0):
            raise ValueError("cross-validation did not hold out every trial exactly once")
        result[name] = assignment
    return result


def majority_choice(values):
    return 1 if np.sum(np.asarray(values) == 1) > np.sum(np.asarray(values) == -1) else -1


def fit_recipe(x, y, folds):
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    predicted = np.empty(len(y), dtype=np.int64)
    decision, probability = np.empty(len(y)), np.empty(len(y))
    coefficients, intercepts, means, scales, iterations = [], [], [], [], []
    for fold in range(5):
        train, test = folds != fold, folds == fold
        scaler = StandardScaler(with_mean=True, with_std=True)
        x_train = scaler.fit_transform(x[train])
        model = LogisticRegression(**CLASSIFIER)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            model.fit(x_train, y[train])
        if not np.array_equal(model.classes_, [-1, 1]):
            raise ValueError("unexpected classifier class ordering")
        x_test = scaler.transform(x[test])
        predicted[test] = model.predict(x_test)
        decision[test] = model.decision_function(x_test)
        probability[test] = model.predict_proba(x_test)[:, 1]
        coefficients.append(model.coef_[0]); intercepts.append(model.intercept_[0])
        means.append(scaler.mean_); scales.append(scaler.scale_); iterations.append(model.n_iter_[0])
    if not np.isfinite(decision).all() or not np.isfinite(probability).all():
        raise ValueError("classifier produced nonfinite held-out predictions")
    return {"predicted_choice": predicted, "decision": decision, "probability_left": probability,
            "coefficients": np.asarray(coefficients), "intercepts": np.asarray(intercepts),
            "scaler_means": np.asarray(means), "scaler_scales": np.asarray(scales),
            "n_iter": np.asarray(iterations, dtype=np.int64)}


def summarize(arrays, selection_counts):
    y = arrays["true_choice"]
    fold_rows, means, pooled, stds, baselines, pooled_baselines = [], {}, {}, {}, {}, {}
    for window in WINDOWS:
        for split in SPLITS:
            recipe = f"{window}_{split}"
            assignment = arrays[f"fold_{split}"]
            pred, base = arrays[f"predicted_choice_{recipe}"], arrays[f"baseline_choice_{split}"]
            accuracies, baseline_accuracies = [], []
            for fold in range(5):
                test = assignment == fold
                n_test = int(np.sum(test))
                if not n_test:
                    raise ValueError("empty held-out fold")
                correct = int(np.sum(pred[test] == y[test]))
                base_correct = int(np.sum(base[test] == y[test]))
                accuracies.append(correct / n_test); baseline_accuracies.append(base_correct / n_test)
                fold_rows.append({"recipe": recipe, "fold": fold, "n_train": int(len(y) - n_test),
                                  "n_test": n_test, "n_correct": correct, "accuracy": correct / n_test,
                                  "baseline_choice": int(base[test][0]), "baseline_n_correct": base_correct,
                                  "baseline_accuracy": base_correct / n_test})
            means[recipe] = float(np.mean(accuracies)); stds[recipe] = float(np.std(accuracies, ddof=0))
            pooled[recipe] = float(np.mean(pred == y))
            baselines[split] = float(np.mean(baseline_accuracies))
            pooled_baselines[split] = float(np.mean(base == y))
    st, rt = arrays["stimulus_times"], arrays["response_times"]
    timing = {"before_stimulus": int(np.sum(rt < st)),
              "within_stimulus_window": int(np.sum((rt >= st) & (rt < st + 0.25))),
              "at_or_after_window_end": int(np.sum(rt >= st + 0.25))}
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, "n_trials": int(len(y)),
              "n_units": int(len(arrays["unit_ids"])), "selection_counts": selection_counts,
              "global_majority_fraction": float(max(np.mean(y == -1), np.mean(y == 1))),
              "response_timing_counts": timing, "cross_validated_accuracy": means[PRIMARY],
              "accuracy_by_window_and_split": means, "pooled_accuracy_by_window_and_split": pooled,
              "accuracy_std_by_window_and_split": stds, "baseline_accuracy_by_split": baselines,
              "pooled_baseline_accuracy_by_split": pooled_baselines}
    return result, fold_rows


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def write_outputs(output_dir, arrays, selection_counts, contract):
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    result, fold_rows = summarize(arrays, selection_counts)
    metadata = {**contract, "status": "ok", "n_trials": result["n_trials"], "n_units": result["n_units"],
                "selection_counts": selection_counts, "response_timing_counts": result["response_timing_counts"],
                "primary_recipe": PRIMARY,
                "unit_quality_counts": {str(int(label)): int(np.sum(arrays["unit_annotations"] == label))
                                        for label in np.unique(arrays["unit_annotations"])},
                "optimizer_iterations_by_recipe": {r: arrays[f"n_iter_{r}"].tolist() for r in RECIPES}}
    predictions = []
    for recipe in RECIPES:
        split = recipe.rsplit("_", 1)[1]
        for row, trial in enumerate(arrays["trial_ids"]):
            predictions.append({"recipe": recipe, "trial_id": int(trial), "fold": int(arrays[f"fold_{split}"][row]),
                                "true_choice": int(arrays["true_choice"][row]),
                                "predicted_choice": int(arrays[f"predicted_choice_{recipe}"][row]),
                                "baseline_choice": int(arrays[f"baseline_choice_{split}"][row]),
                                "decision_value": float(arrays[f"decision_{recipe}"][row]),
                                "probability_left": float(arrays[f"probability_left_{recipe}"][row])})
    write_csv(output_dir / "trial_predictions.csv", PREDICTION_FIELDS, predictions)
    write_csv(output_dir / "folds.csv", FOLD_FIELDS, fold_rows)
    write_json(output_dir / "results.json", result); write_json(output_dir / "run_metadata.json", metadata)
    arrays["metadata_json"] = np.asarray(json.dumps(metadata, allow_nan=False))
    np.savez_compressed(output_dir / "analysis_arrays.npz", **arrays)
    lines = ["# Registered-response decoding sensitivity", "",
             f"Selected {result['n_trials']} trials and all {result['n_units']} NWB units from one session.",
             "The following accuracies are unweighted means of five held-out fold accuracies:", ""]
    for recipe in RECIPES:
        split = recipe.rsplit("_", 1)[1]
        lines.append(f"- {recipe}: {result['accuracy_by_window_and_split'][recipe]:.6f}; "
                     f"training-fold-majority baseline {result['baseline_accuracy_by_split'][split]:.6f}.")
    lines += ["", f"Dataset-wide majority fraction {result['global_majority_fraction']:.6f} is descriptive, not a trained baseline.",
              f"Sequential trial selection counts: {json.dumps(selection_counts, sort_keys=True)}.",
              "The source included flag excludes disengagement; it does not apply the paper's additional response-timing exclusions.",
              f"Unit quality annotation counts (1=multi-unit, 2=good, 3=unsorted): {json.dumps(metadata['unit_quality_counts'], sort_keys=True)}. No quality filter is applied.",
              f"Registered-response timing counts: {json.dumps(result['response_timing_counts'], sort_keys=True)}.",
              "Response time is not movement onset; stimulus alignment does not establish pre-movement information.",
              "Window recipes differ in both alignment and duration; split recipes differ in stratification and temporal allocation.",
              "Contiguous KFold trains on both sides of held-out blocks, without an embargo. Fold variability is not an independent-session confidence interval.",
              "All-unit decoding is a secondary method case, not a replication of the paper's residualized regional finding or evidence of causal choice coding."]
    (output_dir / "findings.md").write_text("\n".join(lines) + "\n")
    return result


def run(output_dir, data_dir):
    arrays, selection_counts, contract = load_data(data_dir)
    for split, folds in fold_assignments(arrays["true_choice"]).items():
        arrays[f"fold_{split}"] = folds
        baseline = np.empty(len(folds), dtype=np.int64)
        for fold in range(5):
            baseline[folds == fold] = majority_choice(arrays["true_choice"][folds != fold])
        arrays[f"baseline_choice_{split}"] = baseline
    for window in WINDOWS:
        for split in SPLITS:
            recipe = f"{window}_{split}"
            fitted = fit_recipe(arrays[f"counts_{window}"], arrays["true_choice"], arrays[f"fold_{split}"])
            arrays.update({f"{key}_{recipe}": value for key, value in fitted.items()})
    result = write_outputs(output_dir, arrays, selection_counts, contract)
    print(json.dumps(result, allow_nan=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "/app/output"))
    parser.add_argument("--data-dir", default=os.environ.get("STEINMETZ_DATA_DIR", "/app/data/steinmetz"))
    args = parser.parse_args()
    try:
        run(args.output_dir, args.data_dir)
    except Exception as exc:
        output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
        failed = {"status": "failed_precondition", "pipeline_id": PIPELINE_ID, "reason": str(exc)}
        write_json(output / "run_metadata.json", failed); write_json(output / "results.json", failed)
        (output / "findings.md").write_text("# Failed analysis\n\n" + str(exc) + "\n")
        raise


if __name__ == "__main__":
    main()
