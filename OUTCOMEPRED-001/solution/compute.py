"""Offline original-source feedback-window method control; no expected result direction."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import warnings

import h5py
import numpy as np
import scipy
from scipy.special import expit
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

METHOD_SHA256 = "77f75622ff40896214f6545faffb914ded3fcfe7285c65e994d71939a96a59eb"
SOURCE_MANIFEST_SHA256 = "d87c000f92d2aa54b4eaa0de50d5ffd7ab3035141d1fccd45b4e674d1c56d63d"
METHOD_ID = "released-cluster-feedback-window-control-v2"


def reject_symlinks(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Output/source paths and their ancestors must not be symlinks")


def prepare_destinations(output, private, source=None):
    output, private = Path(output).absolute(), Path(private).absolute()
    if output == private or output in private.parents or private in output.parents:
        raise ValueError("Public and private evidence directories must be separate")
    if source is not None:
        source = Path(source).absolute()
        reject_symlinks(source)
        for path in (output, private):
            if path == source or path in source.parents or source in path.parents:
                raise ValueError("Evidence directories must not overlap the original source directory")
    for path in (output, private):
        reject_symlinks(path)
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise FileExistsError("Preserve existing nonempty evidence: " + str(path))
    for path in (output, private):
        path.mkdir(parents=True, exist_ok=True)
    return output, private


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path, fields, rows):
    with Path(path).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_npz(path, arrays):
    if any(np.asarray(value).dtype.kind == "O" for value in arrays.values()):
        raise ValueError("Primitive evidence arrays only")
    with Path(path).open("xb") as stream:
        np.savez_compressed(stream, **arrays)


def load_contract(path):
    reject_symlinks(path)
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != METHOD_SHA256:
        raise ValueError("Frozen public method SHA-256 mismatch")
    return json.loads(raw)


def stager_path(script_path=None, fallback=Path("/opt/source/stage_data.py")):
    local = Path(script_path or __file__).resolve().parents[1] / "environment/stage_data.py"
    return local if local.is_file() else Path(fallback)


def source_verifier(script_path=None, fallback=Path("/opt/source/stage_data.py")):
    path = stager_path(script_path, fallback)
    if not path.is_file():
        raise ValueError("Original-source integrity helper is missing")
    spec = importlib.util.spec_from_file_location("outcomepred_original_source", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_staged


def text_value(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def integer_ids(values, name):
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype.kind not in "iu" or values.size == 0:
        raise ValueError(name + " must be a nonempty integer vector")
    if np.any(values > np.iinfo(np.int64).max):
        raise ValueError(name + " exceeds signed int64")
    result = values.astype(np.int64)
    if len(np.unique(result)) != len(result):
        raise ValueError(name + " contains duplicate IDs")
    return result


def original_labels(values):
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype.kind != "b":
        raise ValueError("Released outcome must have original Boolean dtype")
    return values.astype(np.int64)


def validate_spikes(times, ends, n_units):
    times, ends = np.asarray(times), np.asarray(ends)
    if times.ndim != 1 or times.dtype.kind != "f" or times.dtype.itemsize != 8:
        raise ValueError("Expected original float64 spike-time vector")
    if (ends.ndim != 1 or len(ends) != n_units or ends.dtype.kind not in "iu"
            or np.any(ends > np.iinfo(np.int64).max)):
        raise ValueError("Invalid spike ragged-index dtype/shape")
    ends = ends.astype(np.int64)
    if np.any(ends < 0) or np.any(np.diff(ends) < 0) or ends[-1] != len(times):
        raise ValueError("Incomplete or decreasing spike ragged index")
    if not np.isfinite(times).all() or np.any(times < 0):
        raise ValueError("Spike times must be finite and nonnegative")
    duplicates, start = 0, 0
    for end in ends:
        differences = np.diff(times[start:end])
        if np.any(differences < 0):
            raise ValueError("Original spike train is not sorted; do not silently re-sort")
        duplicates += int(np.sum(differences == 0))
        start = int(end)
    return ends, duplicates


def domain_counts(values, numeric=False):
    keys = [str(float(v)) if numeric else text_value(v) for v in values]
    return {key: keys.count(key) for key in sorted(set(keys))}


def read_source(data_dir, contract):
    data_dir = Path(data_dir)
    manifest = source_verifier()(data_dir)
    manifest_raw = (data_dir / "source_manifest.json").read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != SOURCE_MANIFEST_SHA256:
        raise ValueError("Source manifest identity differs from public method")
    entries = [item for item in manifest["files"] if item["role"] == "session_nwb"]
    if len(entries) != 1 or entries[0]["sha256"] != contract["source"]["nwb_sha256"]:
        raise ValueError("Wrong original session source")
    with h5py.File(data_dir / entries[0]["path"], "r") as handle:
        tr, units = handle["/intervals/trials"], handle["/units"]
        trial_ids, unit_ids = integer_ids(tr["id"][:], "Trial IDs"), integer_ids(units["id"][:], "Unit IDs")
        trials = {}
        for key in contract["source_validation"]["trial_paths"]:
            values = np.asarray(tr[key][:])
            if values.ndim != 1 or len(values) != len(trial_ids):
                raise ValueError("Original trial column has inconsistent length: " + key)
            trials[key] = values
        trials["id"] = trial_ids
        labels = original_labels(trials["is_mouse_rewarded"])
        trials["mouse_wheel_choice"] = np.asarray([text_value(v) for v in trials["mouse_wheel_choice"]])
        for key in ("start_time", "stop_time", "gabor_stimulus_onset_time", "feedback_time",
                    "choice_registration_time", "wheel_movement_onset_time"):
            trials[key] = np.asarray(trials[key], dtype=np.float64)
        if (not np.isfinite(trials["start_time"]).all() or not np.isfinite(trials["stop_time"]).all()
                or np.any(trials["stop_time"] < trials["start_time"])):
            raise ValueError("Invalid original trial interval bounds")
        session_start = text_value(handle["session_start_time"][()])
        reference_time = text_value(handle["timestamps_reference_time"][()])
        if session_start != reference_time:
            raise ValueError("Source time origins differ")
        if (text_value(handle["general/session_id"][()]) != contract["source"]["session_id"]
                or text_value(handle["general/subject/subject_id"][()]) != contract["source"]["subject_id"]):
            raise ValueError("Original subject/session identity mismatch")
        if "obs_intervals" in units or "/intervals/invalid_times" in handle:
            raise ValueError("Unexpected observation-support representation in frozen source")
        times = np.asarray(units["spike_times"][:])
        ends, duplicates = validate_spikes(times, units["spike_times_index"][:], len(unit_ids))
        epochs = handle["/intervals/epochs"]
        task_rows = np.flatnonzero(np.asarray([text_value(v) for v in epochs["protocol_type"][:]]) == "task")
        if len(task_rows) != 1:
            raise ValueError("Expected one original task epoch")
        task_row = int(task_rows[0])
        task_start, task_stop = float(epochs["start_time"][task_row]), float(epochs["stop_time"][task_row])
        if not np.isfinite([task_start, task_stop]).all() or not task_stop > task_start:
            raise ValueError("Invalid source task epoch")
        for key in ("probe_name", "kilosort2_label", "ibl_quality_score"):
            if units[key].shape != unit_ids.shape:
                raise ValueError("Unit metadata identity-axis mismatch")
        summary = dict(n_source_trials=len(trial_ids), n_units=len(unit_ids), n_stored_spikes=len(times),
                       duplicate_adjacent_spike_pairs=duplicates,
                       nwb_version=text_value(handle.attrs["nwb_version"]),
                       session_start_time=session_start, timestamps_reference_time=reference_time,
                       kilosort_label_counts=domain_counts(units["kilosort2_label"][:]),
                       ibl_quality_score_counts=domain_counts(units["ibl_quality_score"][:], numeric=True),
                       probe_counts=domain_counts(units["probe_name"][:]), observation_support="unknown",
                       task_epoch_start_s=task_start, task_epoch_stop_s=task_stop)
    return dict(trials=trials, labels=labels, unit_ids=unit_ids, spike_times=times,
                spike_ends=ends, source_summary=summary, source_manifest=manifest)


def select_trials(trials, labels):
    n = len(labels)
    reasons = np.full(n, "eligible_not_sampled", dtype="<U32")
    choice_ok = np.isin(trials["mouse_wheel_choice"], ["clockwise", "counter_clockwise"])
    stim_ok = np.isfinite(trials["gabor_stimulus_onset_time"])
    feedback_ok = np.isfinite(trials["feedback_time"])
    reasons[~choice_ok] = "invalid_choice"
    reasons[choice_ok & ~stim_ok] = "nonfinite_stimulus"
    reasons[choice_ok & stim_ok & ~feedback_ok] = "nonfinite_feedback"
    eligible = choice_ok & stim_ok & feedback_ok
    positive, negative = np.flatnonzero(eligible & (labels == 1)), np.flatnonzero(eligible & (labels == 0))
    k = min(len(positive), len(negative))
    if k < 5:
        raise ValueError("At least five eligible trials per released outcome class are required")
    rng = np.random.RandomState(0)
    selected = np.sort(np.r_[rng.choice(positive, k, replace=False), rng.choice(negative, k, replace=False)])
    reasons[selected] = "selected"
    selected_folds = np.full(len(selected), -1, dtype=np.int64)
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    for fold, (_, test) in enumerate(splitter.split(np.zeros((len(selected), 1)), labels[selected])):
        selected_folds[test] = fold
    all_folds = np.full(n, -1, dtype=np.int64)
    all_folds[selected] = selected_folds
    return dict(eligible=eligible, selected=selected, reasons=reasons,
                folds=selected_folds, all_folds=all_folds)


def window_endpoints(feedback, window):
    return (np.asarray(feedback, dtype=np.float64) + np.float64(window["start_ms"] / 1000),
            np.asarray(feedback, dtype=np.float64) + np.float64(window["end_ms"] / 1000))


def count_windows(source, selection, windows):
    selected = selection["selected"]
    feedback = source["trials"]["feedback_time"][selected]
    result = np.empty((len(windows), len(selected), len(source["unit_ids"])), dtype=np.int64)
    endpoints = [window_endpoints(feedback, window) for window in windows]
    start = 0
    for unit, end in enumerate(source["spike_ends"]):
        train = source["spike_times"][start:end]
        for analysis, (left, right) in enumerate(endpoints):
            result[analysis, :, unit] = np.searchsorted(train, right, side="left") - np.searchsorted(train, left, side="left")
        start = int(end)
    if np.any(result < 0):
        raise ValueError("Negative spike occurrence count")
    return result


def describe_support(source, selection, windows):
    selected, trials, summary = selection["selected"], source["trials"], source["source_summary"]
    rows = []
    for window in windows:
        left, right = window_endpoints(trials["feedback_time"][selected], window)
        overlaps = (left[:, None] < right[None, :]) & (right[:, None] > left[None, :])
        rows.append(dict(analysis=window["analysis"],
                         n_starts_before_trial_start=int(np.sum(left < trials["start_time"][selected])),
                         n_ends_after_trial_stop=int(np.sum(right > trials["stop_time"][selected])),
                         n_starts_before_stimulus=int(np.sum(left < trials["gabor_stimulus_onset_time"][selected])),
                         n_ends_after_choice_registration=int(np.sum(right > trials["choice_registration_time"][selected])),
                         n_starts_before_task_epoch=int(np.sum(left < summary["task_epoch_start_s"])),
                         n_ends_after_task_epoch=int(np.sum(right > summary["task_epoch_stop_s"])),
                         n_overlapping_selected_window_pairs=int(np.sum(np.triu(overlaps, k=1)))))
    return rows


def scale_training(train, test):
    train, test = np.asarray(train, dtype=np.float64), np.asarray(test, dtype=np.float64)
    if train.ndim != 2 or test.ndim != 2 or train.shape[1] != test.shape[1] or len(train) == 0:
        raise ValueError("Invalid classifier feature shapes")
    if not np.isfinite(train).all() or not np.isfinite(test).all():
        raise ValueError("Nonfinite classifier features")
    mean = np.mean(train, axis=0)
    variance = np.mean((train - mean) ** 2, axis=0)
    eps, n = np.finfo(np.float64).eps, len(train)
    constant = variance <= n * eps * variance + (n * mean * eps) ** 2
    scale = np.where(constant, 1.0, np.sqrt(variance))
    return (train - mean) / scale, (test - mean) / scale, mean, variance, scale


def objective_gradient(X, y, coef, intercept):
    z = X @ coef + intercept
    residual = expit(z) - y
    objective = float(np.sum(np.logaddexp(0, z) - y * z) + 0.5 * np.dot(coef, coef))
    gradient = np.r_[X.T @ residual + coef, np.sum(residual)] / len(y)
    return objective, gradient


def fit_one(train, labels, test):
    X, test_X, mean, variance, scale = scale_training(train, test)
    model = LogisticRegression(C=1.0, solver="newton-cholesky", l1_ratio=0, tol=1e-10,
                               max_iter=100, fit_intercept=True, class_weight=None)
    warning_rows = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                model.fit(X, labels)
            finally:
                warning_rows.extend(f"{item.category.__name__}: {item.message}" for item in caught)
    finally:
        for message in warning_rows:
            print(message, file=sys.stderr, flush=True)
    if not np.array_equal(model.classes_, [0, 1]):
        raise ValueError("Unexpected binary classifier class order")
    coef, intercept = model.coef_[0].copy(), float(model.intercept_[0])
    scores = np.asarray(model.decision_function(test_X), dtype=np.float64)
    objective, gradient = objective_gradient(X, labels, coef, intercept)
    finite = bool(np.isfinite(coef).all() and np.isfinite(intercept) and np.isfinite(scores).all()
                  and np.isfinite(objective) and np.isfinite(gradient).all())
    receipt = dict(scaler_mean=mean, scaler_variance=variance, scaler_scale=scale,
                   coef=coef, intercept=intercept, objective=objective, mean_gradient=gradient,
                   mean_gradient_inf=float(np.max(np.abs(gradient))), finite_parameters=finite,
                   optimizer_status="not_exposed_by_sklearn", n_iter=int(model.n_iter_.max()), warnings=warning_rows)
    return scores, receipt


def fit_models(counts, labels, folds, windows, scores, model_rows, pilot=False):
    for analysis_index, window in enumerate(windows):
        if pilot and window["analysis"] not in {"headline_pre", "control_post"}:
            continue
        for fold in ([0] if pilot else range(5)):
            train, test = folds != fold, folds == fold
            decisions, model = fit_one(counts[analysis_index, train], labels[train], counts[analysis_index, test])
            model.update(analysis=window["analysis"], analysis_index=analysis_index, fold=fold)
            model_rows.append(model)
            if not model["finite_parameters"] or model["mean_gradient_inf"] > 1e-9:
                raise ValueError(f"Nonfinite or nonstationary fit: {window['analysis']} fold {fold}, gradient={model['mean_gradient_inf']}")
            scores[analysis_index, test] = decisions
            print(json.dumps(dict(analysis=window["analysis"], fold=fold, n_iter=model["n_iter"],
                                  mean_gradient_inf=model["mean_gradient_inf"], warnings=model["warnings"])), flush=True)


def source_trial_rows(source, selection):
    trials, labels, rows = source["trials"], source["labels"], []
    for row, trial_id in enumerate(trials["id"]):
        times = {out: float(trials[key][row]) if np.isfinite(trials[key][row]) else None for out, key in [
            ("stimulus_time_s", "gabor_stimulus_onset_time"), ("feedback_time_s", "feedback_time"),
            ("choice_registration_time_s", "choice_registration_time"), ("wheel_movement_onset_time_s", "wheel_movement_onset_time")]}
        rows.append(dict(source_trial_row=row, trial_id=int(trial_id), **times,
                         choice=str(trials["mouse_wheel_choice"][row]), rewarded=int(labels[row]),
                         eligible=int(selection["eligible"][row]), selected=int(selection["all_folds"][row] >= 0),
                         selection_reason=str(selection["reasons"][row]),
                         fold=int(selection["all_folds"][row]) if selection["all_folds"][row] >= 0 else None))
    return rows


def count_arrays(source, selection, counts, windows):
    selected = selection["selected"]
    return dict(analysis=np.asarray([w["analysis"] for w in windows]),
                window_start_s=np.asarray([w["start_ms"] / 1000 for w in windows], dtype=np.float64),
                window_end_s=np.asarray([w["end_ms"] / 1000 for w in windows], dtype=np.float64),
                source_trial_row=selected, trial_id=source["trials"]["id"][selected],
                source_unit_row=np.arange(len(source["unit_ids"]), dtype=np.int64),
                unit_id=source["unit_ids"], spike_count=counts)


def summarize_predictions(source, selection, scores, windows, pilot=False):
    selected, folds = selection["selected"], selection["folds"]
    labels = source["labels"][selected]
    predictions, fold_rows, analyses = [], [], []
    for index, window in enumerate(windows):
        for test_row in np.flatnonzero(np.isfinite(scores[index])):
            score = float(scores[index, test_row])
            source_row = int(selected[test_row])
            predictions.append(dict(analysis=window["analysis"], source_trial_row=source_row,
                                    trial_id=int(source["trials"]["id"][source_row]), fold=int(folds[test_row]),
                                    label=int(labels[test_row]), prediction=int(score > 0), decision_score=score,
                                    window_start_s=window["start_ms"] / 1000, window_end_s=window["end_ms"] / 1000))
        for fold in range(5):
            train, test = folds != fold, folds == fold
            if not np.isfinite(scores[index, test]).all():
                if pilot: continue
                raise ValueError("Incomplete OOF predictions cannot be a complete submission")
            correct = (scores[index, test] > 0) == labels[test]
            fold_rows.append(dict(analysis=window["analysis"], fold=fold,
                                  n_train_trials=int(train.sum()), n_test_trials=int(test.sum()),
                                  n_train_class0=int(np.sum(labels[train] == 0)), n_train_class1=int(np.sum(labels[train] == 1)),
                                  n_test_class0=int(np.sum(labels[test] == 0)), n_test_class1=int(np.sum(labels[test] == 1)),
                                  n_correct=int(correct.sum()), accuracy=float(correct.mean())))
        accuracies = [r["accuracy"] for r in fold_rows if r["analysis"] == window["analysis"]]
        if len(accuracies) == 5:
            analyses.append(dict(analysis=window["analysis"], mean_accuracy=float(np.mean(accuracies)),
                                 pooled_oof_accuracy=float(np.mean((scores[index] > 0) == labels)),
                                 accuracy_sd=float(np.std(accuracies, ddof=0))))
    classes = lambda values: {str(label): int(np.sum(values == label)) for label in (0, 1)}
    results = dict(status="resource_pilot" if pilot else "complete", n_source_trials=len(source["labels"]),
                   n_eligible_trials=int(selection["eligible"].sum()), n_selected_trials=len(selected),
                   n_units=len(source["unit_ids"]), eligible_class_counts=classes(source["labels"][selection["eligible"]]),
                   selected_class_counts=classes(labels), chance=0.5, analyses=analyses)
    curve = []
    if not pilot:
        if len(analyses) != len(windows):
            raise ValueError("Missing complete analysis")
        lookup = {r["analysis"]: r for r in analyses}
        results.update(headline=lookup["headline_pre"], post_feedback=lookup["control_post"],
                       post_minus_pre=lookup["control_post"]["mean_accuracy"] - lookup["headline_pre"]["mean_accuracy"])
        for window in windows:
            if window["analysis"].startswith("curve_"):
                row = lookup[window["analysis"]]
                curve.append(dict(analysis=window["analysis"], window_start_s=window["start_ms"] / 1000,
                                  window_end_s=window["end_ms"] / 1000, accuracy=row["mean_accuracy"],
                                  pooled_oof_accuracy=row["pooled_oof_accuracy"], accuracy_sd=row["accuracy_sd"]))
    else:
        results.update(headline=None, post_feedback=None, post_minus_pre=None, n_models_completed=len(fold_rows))
    return predictions, fold_rows, curve, results


def make_metadata(source, support, models, contract, pilot=False):
    fits = [{key: model[key] for key in ("analysis", "fold", "mean_gradient_inf", "finite_parameters",
                                        "optimizer_status", "n_iter", "warnings")} for model in models]
    return dict(source=contract["source"], source_manifest_sha256=SOURCE_MANIFEST_SHA256,
                method_contract_sha256=METHOD_SHA256, method=contract, source_summary=source["source_summary"],
                support_by_analysis=support, fits=fits,
                software={"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
                          "scikit-learn": sklearn.__version__, "h5py": h5py.__version__},
                status="resource_pilot" if pilot else "complete")


def findings(results):
    if results["status"] == "resource_pilot":
        return "# Resource pilot only\n\nAll count matrices were prepared; only headline/pre and post fold 0 were fit. This is not a complete CV estimate or a graded submission.\n"
    return (
        "# Within-session feedback-window decoding\n\n"
        f"Using {results['n_selected_trials']} balanced trials and all {results['n_units']} released clusters, "
        f"the mean five-fold accuracy was {results['headline']['mean_accuracy']:.6f} for -200 to -50 ms "
        f"and {results['post_feedback']['mean_accuracy']:.6f} for 0 to 400 ms relative to feedback "
        f"(balanced-cohort majority baseline 0.5; post-minus-pre {results['post_minus_pre']:.6f}). "
        "The complete fixed-width profile is in decoding_vs_window.csv.\n\n"
        "These are retrospective, within-session estimates from one mouse; most clusters are labeled MUA, "
        "not independently isolated neurons. Continuous unit observation is not established by the source. "
        "Feedback alignment does not provide online prediction or establish motor/choice independence. "
        "Pre/post widths differ; the contrast does not isolate timing alone or identify a causal feedback component. "
        "Random trial folds do not establish new-session or new-animal generalization. Outcome balancing is not "
        "natural-prevalence deployment evaluation. Fold SD is descriptive, not a confidence interval, and no "
        "null/equivalence test, absence claim or required control success is inferred. This is a paper-derived "
        "method adaptation, not the paper's regional quality-selected nested-CV result.\n")


def save_private(private, source, selection, counts, scores, models, contract):
    arrays = count_arrays(source, selection, counts, contract["windows"])
    arrays.update(labels=source["labels"][selection["selected"]], folds=selection["folds"],
                  source_labels=source["labels"], source_trial_ids=source["trials"]["id"],
                  source_eligible=selection["eligible"], source_selection_reason=selection["reasons"],
                  source_all_folds=selection["all_folds"], decision_score=scores,
                  prediction=np.where(np.isfinite(scores), (scores > 0).astype(np.int64), -1),
                  source_summary_json=np.asarray(json.dumps(source["source_summary"], sort_keys=True)),
                  method_contract_json=np.asarray(json.dumps(contract, sort_keys=True)),
                  source_manifest_sha256=np.asarray(SOURCE_MANIFEST_SHA256),
                  method_contract_sha256=np.asarray(METHOD_SHA256),
                  fit_warnings_json=np.asarray(json.dumps([m["warnings"] for m in models])))
    for key in ("analysis", "analysis_index", "fold", "scaler_mean", "scaler_variance", "scaler_scale",
                "coef", "intercept", "objective", "mean_gradient", "mean_gradient_inf", "n_iter"):
        arrays["model_" + key] = np.asarray([model[key] for model in models])
    write_npz(private / "analysis_arrays.npz", arrays)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("SOURCE_DIR", "/app/data/outcomepred")))
    parser.add_argument("--method-contract", type=Path, default=Path(os.environ.get("METHOD_CONTRACT", "/app/method_contract.json")))
    parser.add_argument("--output-dir", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--private-dir", type=Path, default=Path(os.environ.get("PRIVATE_DIR", "/app/oracle_private")))
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args(argv)
    # Check both paths before making any output; never alter or mask prior evidence.
    output, private = prepare_destinations(args.output_dir, args.private_dir, args.data_dir)
    source = selection = counts = scores = contract = None
    models = []
    try:
        contract = load_contract(args.method_contract)
        source = read_source(args.data_dir, contract)
        selection = select_trials(source["trials"], source["labels"])
        counts = count_windows(source, selection, contract["windows"])
        support = describe_support(source, selection, contract["windows"])
        scores = np.full(counts.shape[:2], np.nan)
        fit_models(counts, source["labels"][selection["selected"]], selection["folds"],
                   contract["windows"], scores, models, args.pilot)
        predictions, folds, curve, results = summarize_predictions(source, selection, scores, contract["windows"], args.pilot)
        metadata = make_metadata(source, support, models, contract, args.pilot)
        for name, rows in (("source_trials.csv", source_trial_rows(source, selection)),
                           ("trial_predictions.csv", predictions), ("folds.csv", folds),
                           ("decoding_vs_window.csv", curve)):
            write_csv(output / name, contract["outputs"][name]["columns"], rows)
        write_npz(output / "spike_counts.npz", count_arrays(source, selection, counts, contract["windows"]))
        save_private(private, source, selection, counts, scores, models, contract)
        with (output / "findings.md").open("x") as stream:
            stream.write(findings(results))
        # Complete status markers follow the public numeric and private evidence writes.
        write_json(output / "run_metadata.json", metadata)
        write_json(output / "results.json", results)
        print(json.dumps(results, allow_nan=False), flush=True)
        return 0
    except Exception as error:
        failure = dict(status="failed_precondition", reason=f"{type(error).__name__}: {error}",
                       source_manifest_sha256=SOURCE_MANIFEST_SHA256, method_contract_sha256=METHOD_SHA256)
        for name in ("results.json", "run_metadata.json"):
            if not (output / name).exists():
                write_json(output / name, failure)
        if not (output / "findings.md").exists():
            with (output / "findings.md").open("x") as stream:
                stream.write("# Failed precondition\n\n" + failure["reason"] + "\n")
        write_json(private / "failure.json", failure)
        if counts is not None and scores is not None and not (private / "analysis_arrays.npz").exists():
            try:
                save_private(private, source, selection, counts, scores, models, contract)
            except Exception as evidence_error:
                print(f"Additional private evidence write failed: {type(evidence_error).__name__}: {evidence_error}",
                      file=sys.stderr, flush=True)
        print(failure["reason"], file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
