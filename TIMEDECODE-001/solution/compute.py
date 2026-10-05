"""Offline, source-bound within-recording decoding method control; import safe."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import warnings

import numpy as np

METHOD_SHA = "b4ff29fb1dcf767d6362fb944081fc7200cd77039ebacf83ca7398f761f1da73"
SOURCE_SHA = "533bc28bbcc1e8fe53880504b75756ee4035ecb423e3be84c5fddf1660b779f6"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def write_csv(path, fields, rows):
    with Path(path).open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare_destinations(output, private):
    """Refuse overwrite, symlink and nested output/private evidence directories."""
    output, private = Path(output), Path(private)
    for path in (output, private):
        if any(parent.is_symlink() for parent in path.parents):
            raise ValueError(f"Refusing destination with symlink ancestor: {path}")
        if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
            raise FileExistsError(f"Refusing nonempty/non-directory/symlink destination: {path}")
    a, b = output.resolve(), private.resolve()
    if a == b or a in b.parents or b in a.parents:
        raise ValueError("Output and private evidence directories must be separate")
    for path in (output, private):
        path.mkdir(parents=True, exist_ok=True)


def locate_method(explicit=None):
    choices = [Path(explicit)] if explicit else [Path(__file__).resolve().parents[1] / "environment/method_contract.json", Path("/app/method_contract.json")]
    for path in choices:
        if path.is_file():
            if sha(path) != METHOD_SHA:
                raise ValueError("Public method contract SHA256 mismatch")
            return json.loads(path.read_text())
    raise FileNotFoundError("Public method contract missing")


def verify_source(source):
    manifest = Path(source) / "source_manifest.json"
    if sha(manifest) != SOURCE_SHA:
        raise ValueError("Source manifest SHA256 mismatch")
    candidates = [Path(__file__).resolve().parents[1] / "environment/stage_data.py", Path("/opt/source/stage_data.py")]
    script = next((p for p in candidates if p.is_file()), None)
    if script is None:
        raise FileNotFoundError("Offline source-integrity checker unavailable")
    spec = importlib.util.spec_from_file_location("timedecode_source_integrity", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify_staged(Path(source))


def overlap_counts(samples, epoch_offsets, analysis_offsets, baseline_offsets):
    samples = np.asarray(samples, dtype=np.int64)
    gaps = np.diff(samples)
    def count(left, right):
        return int(np.sum((left[-1] >= gaps + right[0]) & (gaps + right[-1] >= left[0])))
    return {"full_epoch_overlap_pairs": count(epoch_offsets, epoch_offsets),
            "analysis_overlap_pairs": count(analysis_offsets, analysis_offsets),
            "prior_analysis_next_baseline_overlap_pairs": count(analysis_offsets, baseline_offsets)}


def trial_folds(labels):
    from sklearn.model_selection import StratifiedKFold
    labels = np.asarray(labels)
    if set(labels.tolist()) != {0, 1} or min(np.bincount(labels, minlength=2)) < 5:
        raise ValueError("Each class requires at least five retained trials")
    result = np.zeros(len(labels), dtype=np.int64)
    for fold, (train, test) in enumerate(StratifiedKFold(5, shuffle=True, random_state=42).split(np.zeros((len(labels), 1)), labels), 1):
        if len(np.unique(labels[train])) != 2:
            raise ValueError("Training fold has fewer than two classes")
        result[test] = fold
    return result


def construct_source(source):
    import mne
    source = Path(source)
    raw = mne.io.read_raw_fif(source / "MEG/sample/sample_audvis_filt-0-40_raw.fif", preload=False, verbose="warning")
    events = mne.read_events(source / "MEG/sample/sample_audvis_filt-0-40_raw-eve.fif", verbose="warning")
    if len(raw.annotations):
        raise ValueError("Pinned source expected no annotations; do not silently discard unexpected annotations")
    if not np.all(np.diff(events[:, 0]) > 0):
        raise ValueError("Source event samples must be strictly increasing")
    picks = mne.pick_types(raw.info, meg="grad", eeg=False, stim=False, eog=False, exclude="bads")
    names = [raw.ch_names[i] for i in picks]
    if any(set(p["data"]["col_names"]) & set(names) for p in raw.info["projs"]):
        raise ValueError("Unexpected source SSP on selected grads; frozen contract expected identity")
    sfreq = float(raw.info["sfreq"])
    offsets = np.arange(round(-0.2 * sfreq), round(0.5 * sfreq) + 1, dtype=np.int64)
    times = offsets / sfreq
    baseline = offsets[offsets <= 0]
    analysis = np.flatnonzero((times >= 0.05) & (times <= 0.45))
    # PTP membership is explicitly computed over all full-rate samples. MNE performs
    # only released-projector (identity here) and baseline steps, not a secret filter.
    epochs = mne.Epochs(raw, events, {"aud_l": 1, "aud_r": 2, "vis_l": 3, "vis_r": 4},
                        tmin=-0.2, tmax=0.5, baseline=(None, 0), picks=picks, proj=True,
                        preload=True, decim=1, detrend=None, reject=None, flat=None,
                        reject_by_annotation=True, event_repeated="error", verbose="warning")
    if not np.array_equal(epochs.times, times):
        raise ValueError("MNE epoch clock disagrees with declared integer sample offsets")
    all_epochs = epochs.get_data(copy=False)
    if not np.isfinite(all_epochs).all():
        raise ValueError("Nonfinite original gradiometer epoch values")
    source_positions = {int(v): i for i, v in enumerate(epochs.selection)}
    rows, retained_positions, retained_event_indices = [], [], []
    for ei, (event_sample, previous, code) in enumerate(events):
        row = dict(source_event_index=ei, event_sample=int(event_sample), previous_value=int(previous),
                   event_code=int(code), modality="", retained=0, drop_reason="not_target", trial_id="",
                   max_ptp_T_per_m="", max_ptp_channel="")
        if code in (1, 2, 3, 4):
            row["modality"] = 0 if code in (1, 2) else 1
            if event_sample + offsets[0] < raw.first_samp or event_sample + offsets[-1] > raw.last_samp:
                row["drop_reason"] = "out_of_bounds"
            else:
                if ei not in source_positions:
                    raise ValueError(f"Unexplained epoch drop for source event {ei}")
                pos = source_positions[ei]
                ptp = np.ptp(all_epochs[pos], axis=1)
                maximum_channel = int(np.argmax(ptp))
                row["max_ptp_T_per_m"] = float(ptp[maximum_channel])
                row["max_ptp_channel"] = names[maximum_channel]
                if ptp[maximum_channel] > 4e-10:
                    row["drop_reason"] = "amplitude"
                else:
                    row.update(retained=1, drop_reason="retained", trial_id=len(retained_positions))
                    retained_positions.append(pos)
                    retained_event_indices.append(ei)
        rows.append(row)
    retained_event_indices = np.asarray(retained_event_indices, dtype=np.int64)
    full = np.asarray(all_epochs[retained_positions], dtype=np.float64)
    features = np.ascontiguousarray(full[:, :, analysis])
    labels = np.isin(events[retained_event_indices, 2], [3, 4]).astype(np.int64)
    folds = trial_folds(labels)
    candidate_indices = np.flatnonzero(np.isin(events[:, 2], [1, 2, 3, 4]))
    sm = dict(sfreq_hz=sfreq, highpass_hz=float(raw.info["highpass"]), lowpass_hz=float(raw.info["lowpass"]),
              first_samp=int(raw.first_samp), last_samp=int(raw.last_samp), n_times=int(raw.n_times),
              n_source_channels=len(raw.ch_names), selected_grad_names=names,
              source_bads=list(raw.info["bads"]), source_projector_descriptions=[p["desc"] for p in raw.info["projs"]],
              grad_projector_rank=0, annotation_count=len(raw.annotations),
              source_event_code_counts={str(int(k)): int(v) for k, v in zip(*np.unique(events[:, 2], return_counts=True))})
    support = dict(n_source_events=len(events), n_candidate_trials=len(candidate_indices),
                   n_retained_trials=len(labels), n_rejected_trials=len(candidate_indices)-len(labels),
                   retained_event_code_counts={str(k): int(np.sum(events[retained_event_indices, 2] == k)) for k in (1, 2, 3, 4)},
                   epoch_offsets=offsets.tolist(), analysis_offsets=offsets[analysis].tolist(), baseline_offsets=baseline.tolist())
    for prefix, ids in (("candidate", candidate_indices), ("retained", retained_event_indices)):
        support.update({prefix+"_"+k: v for k, v in overlap_counts(events[ids, 0], offsets, offsets[analysis], baseline).items()})
    raw.close()
    return dict(features=features, full_epochs=full, events=events, retained_event_indices=retained_event_indices,
                labels=labels, folds=folds, analysis_offsets=offsets[analysis], epoch_offsets=offsets,
                channel_names=np.asarray(names)), rows, sm, support


def mean_gradient(X, y, coef, intercept):
    from scipy.special import expit
    residual = expit(X @ coef + intercept) - y
    return np.r_[(X.T @ residual + coef) / len(y), np.sum(residual) / len(y)]


def fit_one(X_train, y_train, X_test):
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    scaler = StandardScaler(with_mean=True, with_std=True)
    train = scaler.fit_transform(X_train)
    test = scaler.transform(X_test)
    clf = LogisticRegression(solver="newton-cholesky", l1_ratio=0, C=1.0,
                             fit_intercept=True, class_weight=None, tol=1e-10,
                             max_iter=100, random_state=42)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        clf.fit(train, y_train)
    warning_rows = [{"category": w.category.__name__, "message": str(w.message)} for w in caught]
    if any(issubclass(w.category, ConvergenceWarning) for w in caught):
        raise ValueError("Classifier convergence warning: " + json.dumps(warning_rows))
    coef = clf.coef_[0]
    intercept = float(clf.intercept_[0])
    scores = clf.decision_function(test)
    gradient_inf = float(np.max(np.abs(mean_gradient(train, y_train, coef, intercept))))
    if not (np.isfinite(coef).all() and np.isfinite(intercept) and np.isfinite(scores).all()
            and np.isfinite(gradient_inf) and gradient_inf <= 1e-9):
        raise ValueError(f"Nonfinite/nonstationary logistic fit: mean gradient {gradient_inf}")
    return scores, dict(scaler_mean=scaler.mean_, scaler_scale=scaler.scale_, coef=coef.copy(),
                        intercept=intercept, gradient_inf=gradient_inf,
                        iterations=int(clf.n_iter_.max()), warnings=warning_rows)


def fit_models(source, pilot=False):
    X, y, folds = source["features"], source["labels"], source["folds"]
    n, _, nt = X.shape
    pooled = np.full((n, nt), np.nan)
    per_time = np.full((n, nt), np.nan)
    specs = [("pooled", -1, f) for f in range(1, 6)] + [("per_time", t, f) for t in range(nt) for f in range(1, 6)]
    if pilot:
        chosen = sorted({0, (nt-1)//2, nt-1})
        specs = [("pooled", -1, 1)] + [("per_time", t, 1) for t in chosen]
    model_rows = []
    for estimator, time_index, fold in specs:
        train_ids, test_ids = np.flatnonzero(folds != fold), np.flatnonzero(folds == fold)
        if estimator == "pooled":
            train = X[train_ids].transpose(0, 2, 1).reshape(-1, X.shape[1])
            test = X[test_ids].transpose(0, 2, 1).reshape(-1, X.shape[1])
            labels = np.repeat(y[train_ids], nt)
        else:
            train, test, labels = X[train_ids, :, time_index], X[test_ids, :, time_index], y[train_ids]
        scores, model = fit_one(train, labels, test)
        if estimator == "pooled":
            pooled[test_ids] = scores.reshape(len(test_ids), nt)
        else:
            per_time[test_ids, time_index] = scores
        model.update(model_estimator=estimator, model_time_index=time_index, model_fold=fold)
        model_rows.append(model)
        print(json.dumps({"estimator": estimator, "time_index": time_index, "fold": fold,
                          "n_train": len(labels), "gradient_inf": model["gradient_inf"],
                          "iterations": model["iterations"]}), flush=True)
    return pooled, per_time, model_rows


def public_tables(source, source_meta, pooled, per_time):
    X, labels, folds = source["features"], source["labels"], source["folds"]
    n, nc, nt = X.shape
    predictions, fold_rows, curve = [], [], []
    sfreq = source_meta["sfreq_hz"]
    for estimator, scores in (("pooled", pooled), ("per_time", per_time)):
        if not np.isfinite(scores).all():
            raise ValueError("Incomplete predictions cannot be exported as success")
        for trial in range(n):
            for ti in range(nt):
                predictions.append(dict(estimator=estimator, source_event_index=int(source["retained_event_indices"][trial]),
                    trial_id=trial, time_index=ti, sample_offset=int(source["analysis_offsets"][ti]),
                    time_s=float(source["analysis_offsets"][ti]/sfreq), fold=int(folds[trial]), true_class=int(labels[trial]),
                    predicted_class=int(scores[trial, ti] > 0), decision_score=float(scores[trial, ti])))
        for ti in ([-1] if estimator == "pooled" else range(nt)):
            for fold in range(1, 6):
                train, test = folds != fold, folds == fold
                correct = ((scores[test] > 0) == labels[test, None]) if ti == -1 else ((scores[test, ti] > 0) == labels[test])
                multiplier = nt if ti == -1 else 1
                fold_rows.append(dict(estimator=estimator, time_index="" if ti == -1 else ti, fold=fold,
                    n_train_trials=int(train.sum()), n_test_trials=int(test.sum()),
                    n_train_samples=int(train.sum())*multiplier, n_test_samples=int(test.sum())*multiplier,
                    n_train_class0=int(np.sum(labels[train] == 0)), n_train_class1=int(np.sum(labels[train] == 1)),
                    n_test_class0=int(np.sum(labels[test] == 0)), n_test_class1=int(np.sum(labels[test] == 1)),
                    n_correct=int(correct.sum()), accuracy=float(correct.mean())))
    for ti in range(nt):
        curve.append(dict(time_index=ti, sample_offset=int(source["analysis_offsets"][ti]),
            time_s=float(source["analysis_offsets"][ti]/sfreq),
            accuracy=float(np.mean([r["accuracy"] for r in fold_rows if r["estimator"] == "per_time" and r["time_index"] == ti])),
            pooled_accuracy=float(np.mean((per_time[:, ti] > 0) == labels)), n_test_trials=n))
    result = dict(status="ok", accuracy=float(np.mean([r["accuracy"] for r in fold_rows if r["estimator"] == "pooled"])),
                  pooled_oof_accuracy=float(np.mean((pooled > 0) == labels[:, None])), n_trials=n,
                  n_time_samples_per_trial=nt, n_samples_total=n*nt, n_classes=2, n_channels=nc,
                  n_folds=5, classes=["auditory", "visual"], chance_level=0.5)
    return predictions, fold_rows, curve, result


def save_private(private, source, pooled, per_time, model_rows):
    with (private / "source_features.npz").open("xb") as handle:
        np.savez_compressed(handle, **source)
    keys = ["model_estimator", "model_time_index", "model_fold", "scaler_mean", "scaler_scale", "coef", "intercept", "gradient_inf", "iterations"]
    bank = {key: np.asarray([row[key] for row in model_rows]) for key in keys}
    with (private / "models.npz").open("xb") as handle:
        np.savez_compressed(handle, **bank, pooled_scores=pooled, per_time_scores=per_time)
    write_json(private / "fit_warnings.json", [{k: row[k] for k in ("model_estimator", "model_time_index", "model_fold", "warnings")} for row in model_rows])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=Path("/app/data/timedecode"))
    parser.add_argument("--output-dir", type=Path, default=Path("/app/output"))
    parser.add_argument("--private-dir", type=Path, default=Path("/app/oracle_private"))
    parser.add_argument("--method", type=Path)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    prepare_destinations(args.output_dir, args.private_dir)
    try:
        contract = locate_method(args.method)
        verify_source(args.source_dir)
        source, ledger, sm, support = construct_source(args.source_dir)
        pooled, per_time, models = fit_models(source, pilot=args.pilot)
        save_private(args.private_dir, source, pooled, per_time, models)
        if args.pilot:
            write_json(args.output_dir / "pilot.json", dict(status="pilot_only", source_metadata=sm, support_metadata=support,
                fitted_models=len(models), max_mean_gradient_inf=max(m["gradient_inf"] for m in models),
                warnings=[w for m in models for w in m["warnings"]]))
            return 0
        predictions, folds, curve, result = public_tables(source, sm, pooled, per_time)
        for name, rows in (("source_epochs.csv", ledger), ("oof_predictions.csv", predictions), ("per_fold.csv", folds), ("decoding_timecourse.csv", curve)):
            write_csv(args.output_dir / name, contract["outputs"][name], rows)
        import mne, scipy, sklearn
        metadata = dict(status="ok", source_manifest_sha256=SOURCE_SHA, method_contract_sha256=METHOD_SHA,
            source_metadata=sm, support_metadata=support,
            software_versions={"numpy": np.__version__, "scipy": scipy.__version__, "mne": mne.__version__, "scikit_learn": sklearn.__version__},
            fitting_diagnostics=dict(n_models=len(models), all_converged=True,
                max_mean_gradient_inf=max(m["gradient_inf"] for m in models), warnings=[w for m in models for w in m["warnings"]]))
        write_json(args.output_dir / "decoding_results.json", result)
        write_json(args.output_dir / "run_metadata.json", metadata)
        findings = (
            f"# Within-recording modality-decoding method control\n\n"
            f"The pooled-time classifier has mean-fold accuracy {result['accuracy']:.12g}; "
            f"pooled OOF correct/total is {result['pooled_oof_accuracy']:.12g}. "
            f"There are {result['n_trials']} retained trials and {result['n_time_samples_per_trial']} "
            f"native-rate analysis samples per trial, from one person and one recording. "
            f"Separately fitted per-time classifiers have mean-fold accuracies ranging "
            f"{min(r['accuracy'] for r in curve):.12g} to {max(r['accuracy'] for r in curve):.12g}.\n\n"
            "These are two different fitted estimators, not a temporal-generalization matrix. "
            "The same public whole-trial folds are used for both; train-only scaling prevents "
            "that particular use of held-out rows. Trial grouping does not establish independent "
            "trials or remove all temporal dependence: the released event schedule contains "
            "overlapping full epochs and prior-analysis/next-baseline source samples. "
            "The released mag/EEG projectors do not correct these selected gradiometers. "
            "No claim is made about unseen people, sessions, latencies, cognitive onset, hardware "
            "performance, a named paper's numerical finding, or model-task difficulty.\n")
        with (args.output_dir / "findings.md").open("x") as handle:
            handle.write(findings)
        print(json.dumps(result), flush=True)
        return 0
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        # Preserve any already-written evidence; never replace it with a fake success.
        for name in ("run_metadata.json", "decoding_results.json"):
            path = args.output_dir / name
            if not path.exists():
                write_json(path, dict(status="failed_precondition", reason=reason))
        if not (args.output_dir / "findings.md").exists():
            with (args.output_dir / "findings.md").open("x") as handle:
                handle.write("# Failed precondition\n\n" + reason + "\n")
        print(reason, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
