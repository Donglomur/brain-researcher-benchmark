"""Independent source/count/preprocessing implementation; shared sklearn solver.

Does not import the oracle. The alternate spike counter uses Python bisect_left;
fold allocation and train-only centering/scaling are implemented explicitly.
The optional wrong global-scaling control is an authoring negative, not a new
scientific analysis. Both fitting paths are run only when explicitly invoked.
"""
import argparse
from bisect import bisect_left
import csv
import hashlib
import json
from pathlib import Path
import shutil
import warnings

import numpy as np

SOURCE_NAME = "sub-Cori_ses-20161214T120000.nwb"
SOURCE_SHA256 = "d8433a826049f82cd832f41f98a9f9fafad0ac66998d4dbfd89b15b594fc4236"
RECIPES = ("stimulus_blocked", "stimulus_random", "peri_response_blocked", "peri_response_random")


def count_with_bisect(spike_trains, centers, start, stop):
    return np.asarray([[bisect_left(spikes, center + stop) - bisect_left(spikes, center + start)
                        for spikes in spike_trains] for center in centers], dtype=np.int64)


def explicit_folds(labels):
    """Implement sklearn's published allocation, not its splitter classes."""
    n = len(labels)
    sizes = np.full(5, n // 5, dtype=np.int64); sizes[:n % 5] += 1
    blocked = np.repeat(np.arange(5), sizes)
    _, first, inverse = np.unique(labels, return_index=True, return_inverse=True)
    _, first_order = np.unique(first, return_inverse=True)
    encoded = first_order[inverse]
    sorted_y = np.sort(encoded)
    allocation = np.asarray([np.bincount(sorted_y[i::5], minlength=2) for i in range(5)])
    rng = np.random.RandomState(0)
    shuffled = np.empty(n, dtype=np.int64)
    for category in range(2):
        assignment = np.arange(5).repeat(allocation[:, category])
        rng.shuffle(assignment)
        shuffled[encoded == category] = assignment
    return {"blocked": blocked, "random": shuffled}


def manual_standardization(train, test):
    train, test = np.asarray(train, dtype=float), np.asarray(test, dtype=float)
    means = np.sum(train, axis=0) / len(train)
    variance = np.sum((train - means) ** 2, axis=0) / len(train)
    scales = np.sqrt(variance)
    scales[scales == 0] = 1.0
    return (train - means) / scales, (test - means) / scales, means, scales


def probability_left(decision):
    magnitude = np.exp(-np.abs(decision))
    return np.where(decision >= 0, 1 / (1 + magnitude), magnitude / (1 + magnitude))


def independent_source(data_dir):
    import h5py
    path = Path(data_dir) / SOURCE_NAME
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    assert digest == SOURCE_SHA256 and path.stat().st_size == 311814662
    with h5py.File(path, "r") as nwb:
        trials, units = nwb["intervals/trials"], nwb["units"]
        ids = trials["id"][:]
        included = trials["included"][:]
        choices = trials["response_choice"][:]
        stimulus, response = trials["visual_stimulus_time"][:], trials["response_time"][:]
        mask = ((included == True) & ((choices == -1) | (choices == 1))
                & np.isfinite(stimulus) & np.isfinite(response))
        assert len(set(ids.tolist())) == len(ids) and np.all(np.diff(stimulus[mask]) >= 0)
        unit_ids = units["id"][:]
        assert len(set(unit_ids.tolist())) == len(unit_ids)
        ends = units["spike_times_index"][:]
        flat = units["spike_times"][:]
        assert len(ends) == len(unit_ids) and ends[-1] == len(flat)
        spikes, previous = [], 0
        for stop in ends:
            times = flat[previous:int(stop)]
            assert np.isfinite(times).all() and np.all(np.diff(times) >= 0)
            spikes.append(times); previous = int(stop)
        annotations = units["phy_annotations"][:]
    data = {"trial_ids": ids[mask], "true_choice": choices[mask].astype(np.int64), "unit_ids": unit_ids,
            "unit_annotations": annotations, "stimulus_times": stimulus[mask], "response_times": response[mask]}
    data["counts_stimulus"] = count_with_bisect(spikes, stimulus[mask], 0.0, 0.25)
    data["counts_peri_response"] = count_with_bisect(spikes, response[mask], -0.1, 0.1)
    return data


def fit_independent(x, y, folds, *, globally_scaled=False):
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    decisions = np.empty(len(y), dtype=float)
    states = []
    if globally_scaled:
        wrong_x = StandardScaler(with_mean=True, with_std=True).fit_transform(x)
    for fold in range(5):
        training, testing = folds != fold, folds == fold
        if globally_scaled:
            train, test = wrong_x[training], wrong_x[testing]
            means = scales = None
        else:
            train, test, means, scales = manual_standardization(x[training], x[testing])
        model = LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", tol=0.0001,
                                   max_iter=2000, fit_intercept=True, class_weight=None, random_state=None)
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            model.fit(train, y[training])
        assert np.array_equal(model.classes_, [-1, 1])
        decisions[testing] = test @ model.coef_[0] + model.intercept_[0]
        states.append((means, scales))
    return {"decision": decisions, "probability_left": probability_left(decisions),
            "predicted_choice": np.where(decisions > 0, 1, -1), "states": states}


def save_wrong_control(output_dir, original_dir, data, wrong, original_results):
    """Write coherent wrong numerical outputs; claim the normal metadata on purpose."""
    output_dir = Path(output_dir)
    if output_dir.resolve() == Path(original_dir).resolve():
        raise ValueError("negative control must not overwrite genuine outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(original_dir) / "run_metadata.json", output_dir / "run_metadata.json")
    result = json.loads(json.dumps(original_results))
    prediction_rows, fold_rows = [], []
    for recipe in RECIPES:
        split = recipe.rsplit("_", 1)[1]
        folds, y = data[f"fold_{split}"], data["true_choice"]
        fitted, accuracy = wrong[recipe], []
        for fold in range(5):
            test, train = folds == fold, folds != fold
            choice = 1 if np.sum(y[train] == 1) > np.sum(y[train] == -1) else -1
            correct = int(np.sum(fitted["predicted_choice"][test] == y[test]))
            base_correct = int(np.sum(y[test] == choice)); n_test = int(np.sum(test))
            accuracy.append(correct / n_test)
            fold_rows.append({"recipe": recipe, "fold": fold, "n_train": int(np.sum(train)),
                              "n_test": n_test, "n_correct": correct, "accuracy": correct / n_test,
                              "baseline_choice": choice, "baseline_n_correct": base_correct,
                              "baseline_accuracy": base_correct / n_test})
            for i in np.flatnonzero(test):
                prediction_rows.append({"recipe": recipe, "trial_id": int(data["trial_ids"][i]),
                                        "fold": fold, "true_choice": int(y[i]),
                                        "predicted_choice": int(fitted["predicted_choice"][i]),
                                        "baseline_choice": choice, "decision_value": float(fitted["decision"][i]),
                                        "probability_left": float(fitted["probability_left"][i])})
        result["accuracy_by_window_and_split"][recipe] = float(np.mean(accuracy))
        result["accuracy_std_by_window_and_split"][recipe] = float(np.std(accuracy))
        result["pooled_accuracy_by_window_and_split"][recipe] = float(np.mean(fitted["predicted_choice"] == y))
    result["cross_validated_accuracy"] = result["accuracy_by_window_and_split"]["stimulus_blocked"]
    for name, rows in [("trial_predictions.csv", prediction_rows), ("folds.csv", fold_rows)]:
        with (output_dir / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    (output_dir / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    (output_dir / "findings.md").write_text(
        "# Authoring negative control\n\n"
        "Scaling was deliberately fitted to all trials before cross-validation. "
        "Metadata was deliberately left claiming the valid recipe to test numerical rejection.\n"
        + json.dumps(result["accuracy_by_window_and_split"], indent=2) + "\n")


def check(output_dir, data_dir, report_path, leakage_output=None):
    output_dir = Path(output_dir)
    with np.load(output_dir / "analysis_arrays.npz", allow_pickle=False) as archive:
        retained = {key: archive[key] for key in archive.files}
    data = independent_source(data_dir)
    for key, value in data.items():
        np.testing.assert_array_equal(retained[key], value, err_msg=f"independent source/count mismatch: {key}")
    for split, membership in explicit_folds(data["true_choice"]).items():
        np.testing.assert_array_equal(retained[f"fold_{split}"], membership)
        data[f"fold_{split}"] = membership
    checks, wrong, control_checks = {}, {}, {}
    for recipe in RECIPES:
        window, split = recipe.rsplit("_", 1)
        fitted = fit_independent(data[f"counts_{window}"], data["true_choice"], data[f"fold_{split}"])
        np.testing.assert_array_equal(fitted["predicted_choice"], retained[f"predicted_choice_{recipe}"])
        for field in ["decision", "probability_left"]:
            np.testing.assert_allclose(fitted[field], retained[f"{field}_{recipe}"], atol=1e-6, rtol=1e-6)
        for fold, (mean, scale) in enumerate(fitted["states"]):
            np.testing.assert_allclose(mean, retained[f"scaler_means_{recipe}"][fold], atol=1e-12, rtol=1e-12)
            np.testing.assert_allclose(scale, retained[f"scaler_scales_{recipe}"][fold], atol=1e-12, rtol=1e-12)
        checks[recipe] = {"n_predictions": len(data["true_choice"]), "label_disagreements": 0,
                          "max_abs_decision_diff": float(np.max(np.abs(fitted["decision"] - retained[f"decision_{recipe}"]))),
                          "max_abs_probability_diff": float(np.max(np.abs(fitted["probability_left"] - retained[f"probability_left_{recipe}"])))}
        if leakage_output is not None:
            wrong[recipe] = fit_independent(data[f"counts_{window}"], data["true_choice"],
                                            data[f"fold_{split}"], globally_scaled=True)
            control_checks[recipe] = {
                "label_disagreements": int(np.sum(wrong[recipe]["predicted_choice"] != retained[f"predicted_choice_{recipe}"])),
                "max_abs_decision_diff": float(np.max(np.abs(wrong[recipe]["decision"] - retained[f"decision_{recipe}"]))),
                "max_abs_probability_diff": float(np.max(np.abs(wrong[recipe]["probability_left"] - retained[f"probability_left_{recipe}"])))}
    if leakage_output is not None:
        original_results = json.loads((output_dir / "results.json").read_text())
        save_wrong_control(leakage_output, output_dir, data, wrong, original_results)
    report = {"status": "passed", "source_sha256": SOURCE_SHA256,
              "n_trials": int(len(data["trial_ids"])), "n_units": int(len(data["unit_ids"])),
              "source_counts": "all entries exactly match Python bisect implementation",
              "fold_membership": "explicit allocation matches retained sklearn split IDs",
              "preprocessing": "independent training-only mean and population variance",
              "shared_component": "same pinned sklearn LogisticRegression/lbfgs solver, not an independent optimizer",
              "n_models_checked": 20, "recipes": checks,
              "global_scaling_negative": control_checks,
              "scientific_limit": "computational recipe agreement does not identify causal or pre-movement choice coding"}
    Path(report_path).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/steinmetz"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--leakage-output", type=Path)
    args = parser.parse_args()
    check(args.output_dir, args.data_dir, args.report, args.leakage_output)
