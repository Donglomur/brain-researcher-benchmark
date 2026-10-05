"""Paired-null, run-held-out EEGBCI CSP/LDA method case; import has no I/O.

Observed and conditionally permuted labels use identical pooled OOF statistics.
No offline result establishes online BCI control or individual inability.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time
import warnings

import numpy as np

try:
    from reliability import permutation_targets, subject_statistics, group_statistics
except ModuleNotFoundError:
    import importlib.util
    _spec = importlib.util.spec_from_file_location("motorimagery_reliability", Path(__file__).with_name("reliability.py"))
    _reliability = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_reliability)
    permutation_targets = _reliability.permutation_targets
    subject_statistics = _reliability.subject_statistics
    group_statistics = _reliability.group_statistics

PIPELINE_ID = "eegbci-paired-null-held-run-csp-v3"
SUBJECTS, RUNS, N_PERMUTATIONS = list(range(1, 11)), [6, 10, 14], 200
MANIFEST_SHA256 = "939a5725a743d3162f24ac1d10c6088888991559c4a07207ee935a4061fc88c7"
SOFTWARE = {"mne": "1.12.1", "sklearn": "1.8.0", "scipy": "1.17.0", "numpy": "2.2.6"}
# Original EDF header order, standardized by the pinned eegbci naming rule;
# source-header inspection predates all classifier execution.
CHANNELS = ["FC5", "FC3", "FC1", "FCz", "FC2", "FC4", "FC6", "C5", "C3", "C1", "Cz",
            "C2", "C4", "C6", "CP5", "CP3", "CP1", "CPz", "CP2", "CP4", "CP6", "Fp1", "Fpz", "Fp2",
            "AF7", "AF3", "AFz", "AF4", "AF8", "F7", "F5", "F3", "F1", "Fz", "F2", "F4", "F6", "F8",
            "FT7", "FT8", "T7", "T8", "T9", "T10", "TP7", "TP8", "P7", "P5", "P3", "P1", "Pz",
            "P2", "P4", "P6", "P8", "PO7", "PO3", "POz", "PO4", "PO8", "O1", "Oz", "O2", "Iz"]
FILTER = {"l_freq": 7., "h_freq": 30., "filter_length": "auto", "l_trans_bandwidth": "auto",
          "h_trans_bandwidth": "auto", "n_jobs": 1, "method": "fir", "iir_params": None,
          "phase": "zero", "fir_window": "hamming", "fir_design": "firwin",
          "skip_by_annotation": ["edge", "bad_acq_skip"], "pad": "reflect_limited"}
CSP_PARAMETERS = {"n_components": 4, "reg": None, "log": True, "norm_trace": False,
                  "cov_est": "concat", "transform_into": "average_power", "rank": None,
                  "cov_method_params": None, "component_order": "mutual_info",
                  "restr_type": "restricting", "info": None}
LDA_PARAMETERS = {"solver": "svd", "priors": None, "shrinkage": None, "tol": 1e-4,
                  "store_covariance": False, "n_components": None, "covariance_estimator": None}
SOURCE_FIELDS = ["subject", "run", "event_index", "event_sample", "source_class", "retained", "drop_reason"]
OOF_FIELDS = ["subject", "run", "event_index", "event_sample", "replicate", "source_class",
              "target_class", "predicted_class", "decision_score"]
FOLD_FIELDS = ["subject", "replicate", "test_run", "n_train", "n_test", "n_train_class0",
               "n_train_class1", "n_test_class0", "n_test_class1", "accuracy"]
SUBJECT_FIELDS = ["subject", "n_epochs", "n_runs", "accuracy", "kappa", "perm_p", "holm_p",
                  "null_mean", "null_sd", "n_null_ge_observed"]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def load_manifest(data_dir, subjects=SUBJECTS, verify=True):
    root = Path(data_dir).resolve()
    raw = (root/"data_manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("source manifest differs from pinned original-source contract")
    manifest = json.loads(raw)
    if manifest["dataset_id"] != "eegmmidb" or manifest["version"] != "1.0.0":
        raise ValueError("unexpected source identity")
    records = manifest["files"]
    keys = [(record["subject"], record["run"]) for record in records]
    if len(records) != 30 or len(set(keys)) != 30 or set(keys) != {(s, r) for s in SUBJECTS for r in RUNS}:
        raise ValueError("source manifest must enumerate thirty original EDFs")
    subjects = list(subjects)
    if not subjects or subjects != sorted(set(subjects)) or not set(subjects) <= set(SUBJECTS):
        raise ValueError("subjects must be a nonempty ascending unique subset of 1..10")
    paths, hashes = {}, {}
    for record in records:
        subject, run = record["subject"], record["run"]
        relative = f"S{subject:03d}/S{subject:03d}R{run:02d}.edf"
        if record["path"] != relative or record["role"] != "eeg_edf":
            raise ValueError("source EDF role/path mismatch")
        path = (root/relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("source path escapes data directory")
        hashes[relative] = record["sha256"]
        if subject in subjects:
            if verify:
                if path.stat().st_size != record["size_bytes"]:
                    raise ValueError(f"source size mismatch: {relative}")
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if digest != record["sha256"]:
                    raise ValueError(f"source SHA256 mismatch: {relative}")
            paths[(subject, run)] = path
    return manifest, paths, hashes


def metadata_contract(manifest):
    """Public production template; no EDF loading, filtering or fitted results."""
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": "eegmmidb", "dataset_version": "1.0.0",
        "source_manifest_sha256": MANIFEST_SHA256,
        "source_sha256": {row["path"]: row["sha256"] for row in manifest["files"]},
        "subjects": SUBJECTS, "runs": RUNS, "software": SOFTWARE, "channels": CHANNELS, "sfreq": 160.,
        "channel_preprocessing": {"standardize": "mne.datasets.eegbci.standardize",
            "montage": "standard_1005", "selection": "all_64_EEG_in_original_order", "exclude": [],
            "reference": "unchanged", "interpolation": False, "data_units": "V"},
        "filter": {"unit": "each_original_acquisition_run_separately", **FILTER},
        "epochs": {"tmin": 1., "tmax": 2., "endpoint": "inclusive", "n_times": 161, "sfreq": 160.,
            "baseline": None, "proj": False, "reject": None, "flat": None, "detrend": None, "decim": 1,
            "reject_by_annotation": True, "event_repeated": "error",
            "event_sample_rounding": "MNE_use_rounding_True",
            "source_event_index": "zero_based_chronological_T1_T2_within_original_run",
            "drop_reasons": {"retained": "", "boundary": "out_of_bounds", "bad_annotation": "annotation",
                             "combination": "sorted_unique_semicolon_joined"}},
        "classes": {"0": "imagined_both_fists_T1", "1": "imagined_both_feet_T2"},
        "csp": CSP_PARAMETERS, "lda": LDA_PARAMETERS,
        "cv": {"scheme": "within_subject_leave_one_acquisition_run_out", "fold_order": RUNS,
            "refit_CSP_and_LDA_each_fold_and_replicate": True,
            "statistic": "pooled_out_of_fold_accuracy_not_unweighted_fold_mean",
            "decision_positive_class": 1, "decision_zero_class": 0},
        "permutation": {"n_permutations": N_PERMUTATIONS, "seed": 0, "rng": "numpy.random.RandomState",
            "reset_per_subject": True, "replicate_order": "1..200_ascending", "run_order": RUNS,
            "pair_ids": list(range(7)), "pair_definition": "original_event_index_integer_division_by_2",
            "shuffle": "rng.permutation(original_labels_of_each_complete_retained_original_pair)",
            "incomplete_pair": "surviving_label_fixed_and_no_RNG_draw", "singleton_event14": "fixed",
            "observed_replicate": 0, "alternative": "greater_or_equal",
            "pvalue": "(1+n_null_ge_observed)/(1+B)", "null_sd_ddof": 0,
            "exchangeability": "conditional_within_original_pair_label_exchangeability_assumed_not_proven_randomization"},
        "multiple_testing": {"method": "Holm", "family": SUBJECTS, "alpha": .05,
                             "significant_rule": "p_strictly_less_than_alpha"},
        "group_test": {"method": "scipy.stats.ttest_1samp", "popmean": .5, "alternative": "two-sided",
            "unit": "subject_pooled_OOF_accuracy", "undefined_rule": "null_t_and_p_if_fewer_than_two_or_zero_subject_variance"},
        "aggregation": {"accuracy": "unweighted_mean_of_subject_pooled_accuracies",
            "kappa": "unweighted_mean_of_subject_kappas", "finite_sample_null_sd": "mean_subject_null_sd"},
        "decision_score_tolerance": {"atol": 1e-7, "rtol": 1e-5},
    }


def check_software():
    import mne
    import scipy
    import sklearn
    actual = {"mne": mne.__version__, "sklearn": sklearn.__version__, "scipy": scipy.__version__, "numpy": np.__version__}
    if actual != SOFTWARE:
        raise ValueError(f"oracle dependency pins differ: {actual}")


def canonical_drop_reason(reasons):
    normalized = set()
    for reason in reasons:
        value = str(reason).upper()
        if value in {"NO_DATA", "TOO_SHORT"}:
            normalized.add("out_of_bounds")
        elif value.startswith("BAD") or value.startswith("EDGE"):
            normalized.add("annotation")
        else:
            raise ValueError(f"unrecognized source epoch drop reason: {reason}")
    return ";".join(sorted(normalized))


def epoch_run(raw, subject, run):
    """Run-local preprocessing and target-event ledger; no classifier fitting."""
    import mne
    from mne.datasets import eegbci
    eegbci.standardize(raw)
    raw.set_montage(mne.channels.make_standard_montage("standard_1005"), verbose="WARNING")
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(picks) != 64 or float(raw.info["sfreq"]) != 160.:
        raise ValueError("expected original 64-channel 160-Hz EEG acquisition")
    channels = [raw.ch_names[index] for index in picks]
    if channels != CHANNELS:
        raise ValueError("source channel identities/order differ from original EDF header contract")
    raw.filter(picks=picks, **FILTER, verbose="WARNING")
    events, _ = mne.events_from_annotations(raw, event_id={"T1": 1, "T2": 2}, use_rounding=True, verbose="WARNING")
    if not len(events) or np.any(np.diff(events[:, 0]) <= 0):
        raise ValueError("target cue samples must be nonempty, unique and chronological")
    epochs = mne.Epochs(raw, events, event_id={"hands": 1, "feet": 2}, tmin=1., tmax=2.,
        baseline=None, picks=picks, preload=True, proj=False, reject=None, flat=None,
        detrend=None, decim=1, reject_by_annotation=True, event_repeated="error", verbose="WARNING")
    x = epochs.get_data(copy=True)
    if x.shape[1:] != (64, 161) or not np.isfinite(x).all():
        raise ValueError("required epochs must be finite 64x161 arrays")
    if not np.allclose(epochs.times, 1.+np.arange(161)/160., atol=1e-15, rtol=0):
        raise ValueError("epoch time grid differs from inclusive 1..2 s")
    kept = set(map(int, epochs.selection))
    rows, raw_drops = [], []
    for index, event in enumerate(events):
        reasons = list(epochs.drop_log[index])
        retained = index in kept
        if retained != (not reasons):
            raise ValueError("epoch selection and drop ledger disagree")
        rows.append({"subject": int(subject), "run": int(run), "event_index": index,
            "event_sample": int(event[0]), "source_class": int(event[2]-1),
            "retained": int(retained), "drop_reason": canonical_drop_reason(reasons)})
        if reasons:
            raw_drops.append({"event_index": index, "mne_drop_reasons": reasons})
    observation = {"subject": int(subject), "run": int(run), "n_source_events": len(events),
                   "n_retained": len(x), "n_dropped": len(events)-len(x)}
    return {"X": x, "run": np.full(len(x), run, dtype=np.int64),
            "event_index": epochs.selection.astype(np.int64), "event_sample": epochs.events[:, 0].astype(np.int64),
            "source_class": epochs.events[:, 2].astype(np.int64)-1, "source_rows": rows,
            "observation": observation, "channels": channels, "raw_drop_reasons": raw_drops,
            "n_times": int(raw.n_times), "first_samp": int(raw.first_samp), "n_annotations": len(raw.annotations)}


def subject_epochs(subject, paths):
    import mne
    parts = []
    for run in RUNS:
        raw = mne.io.read_raw_edf(paths[(subject, run)], preload=True, verbose="WARNING")
        part = epoch_run(raw, subject, run)
        source_labels = np.array([row["source_class"] for row in part["source_rows"]])
        if len(source_labels) != 15 or any(set(source_labels[2*p:2*p+2]) != {0, 1} for p in range(7)):
            raise ValueError("original 15-cue balanced-pair schedule differs from source contract")
        parts.append(part)
    if any(part["channels"] != parts[0]["channels"] for part in parts):
        raise ValueError("channel identities/order differ across original runs")
    result = {key: np.concatenate([part[key] for part in parts], axis=0)
              for key in ("X", "run", "event_index", "event_sample", "source_class")}
    for run in RUNS:
        if set(result["source_class"][result["run"] == run]) != {0, 1}:
            raise ValueError("each retained run must contain both source classes")
    result.update({"source_rows": [row for part in parts for row in part["source_rows"]],
        "run_observations": [part["observation"] for part in parts], "channels": parts[0]["channels"],
        "raw_run_receipts": [{key: part[key] for key in
            ("observation", "raw_drop_reasons", "n_times", "first_samp", "n_annotations")} for part in parts]})
    return result


def csp_lda():
    from mne.decoding import CSP
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.pipeline import Pipeline
    return Pipeline([("csp", CSP(**CSP_PARAMETERS)), ("lda", LinearDiscriminantAnalysis(**LDA_PARAMETERS))])


def fit_subject(subject, epochs, n_permutations, progress=True):
    import mne
    x, source, runs = epochs["X"], epochs["source_class"], epochs["run"]
    targets = permutation_targets(source, runs, epochs["event_index"], n_permutations)
    predicted, decisions = np.empty_like(targets), np.empty(targets.shape, dtype=float)
    fold_rows, private = [], []
    for replicate, y in enumerate(targets):
        for heldout in RUNS:
            train, test = np.flatnonzero(runs != heldout), np.flatnonzero(runs == heldout)
            if set(y[train]) != {0, 1} or not len(test):
                raise ValueError("fold lacks two training classes or test samples")
            with warnings.catch_warnings(record=True) as captured, mne.use_log_level("WARNING"):
                warnings.simplefilter("always")
                pipeline = csp_lda().fit(x[train], y[train])
                scores = np.asarray(pipeline.decision_function(x[test]), dtype=float)
                classes = pipeline.predict(x[test]).astype(np.int64)
            warning_rows = []
            for warning in captured:
                warnings.showwarning(warning.message, warning.category, warning.filename, warning.lineno)
                warning_rows.append({"category": warning.category.__name__, "message": str(warning.message)})
            if not np.isfinite(scores).all() or not np.array_equal(classes, (scores > 0).astype(np.int64)):
                raise ValueError("nonfinite score or binary decision/class mismatch")
            csp, lda = pipeline.named_steps["csp"], pipeline.named_steps["lda"]
            if not np.array_equal(lda.classes_, [0, 1]):
                raise ValueError("unexpected fitted class ordering")
            predicted[replicate, test], decisions[replicate, test] = classes, scores
            fold_rows.append({"subject": subject, "replicate": replicate, "test_run": heldout,
                "n_train": len(train), "n_test": len(test), "n_train_class0": int(np.sum(y[train] == 0)),
                "n_train_class1": int(np.sum(y[train] == 1)), "n_test_class0": int(np.sum(y[test] == 0)),
                "n_test_class1": int(np.sum(y[test] == 1)), "accuracy": float(np.mean(y[test] == classes))})
            private.append({"subject": subject, "replicate": replicate, "test_run": heldout,
                "csp_filters": csp.filters_[:4].copy(), "csp_rank": len(csp.filters_),
                "csp_eigenvalues": np.asarray(csp.evals_[:4], dtype=float).copy(), "lda_coef": lda.coef_[0].copy(),
                "lda_intercept": float(lda.intercept_[0]), "lda_classes": lda.classes_.copy(), "warnings": warning_rows})
        if progress and (replicate == 0 or replicate % 10 == 0 or replicate == n_permutations):
            print(f"subject={subject} replicate={replicate}/{n_permutations} complete", flush=True)
    return {"target_class": targets, "predicted_class": predicted, "decision_score": decisions,
            "fold_rows": fold_rows, "fold_private": private,
            "summary": subject_statistics(subject, runs, targets, predicted)}


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(data_dir, output, subjects=SUBJECTS, n_permutations=N_PERMUTATIONS):
    check_software()
    if type(n_permutations) is not int or not 1 <= n_permutations <= N_PERMUTATIONS:
        raise ValueError("permutation count must be in 1..200")
    manifest, paths, _ = load_manifest(data_dir, subjects)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    started, prepared, fitted = time.monotonic(), {}, {}
    for subject in subjects:
        prepared[subject] = subject_epochs(subject, paths)
        fitted[subject] = fit_subject(subject, prepared[subject], n_permutations)
    channels = prepared[subjects[0]]["channels"]
    if any(prepared[s]["channels"] != channels for s in subjects):
        raise ValueError("standardized channel identities differ across subjects")
    source_rows = [row for s in subjects for row in prepared[s]["source_rows"]]
    observations = [row for s in subjects for row in prepared[s]["run_observations"]]
    subject_rows = [fitted[s]["summary"] for s in subjects]
    group = group_statistics(subject_rows, n_permutations)
    status = "ok" if list(subjects) == SUBJECTS and n_permutations == N_PERMUTATIONS else "resource_pilot"
    group.update({"status": status, "pipeline_id": PIPELINE_ID})
    metadata = metadata_contract(manifest) | {
        "status": status, "n_subjects": len(subjects), "n_epochs_total": group["n_epochs_total"],
        "n_source_events": len(source_rows), "n_dropped_epochs": sum(row["n_dropped"] for row in observations),
        "n_epochs_by_run": observations, "channels": channels, "sfreq": 160.,
        "executed_subjects": list(subjects), "executed_permutations": n_permutations}
    write_csv(output/"source_epochs.csv", SOURCE_FIELDS, source_rows)
    write_csv(output/"fold_receipts.csv", FOLD_FIELDS, [row for s in subjects for row in fitted[s]["fold_rows"]])
    write_csv(output/"per_subject.csv", SUBJECT_FIELDS, subject_rows)
    with (output/"oof_predictions.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OOF_FIELDS)
        writer.writeheader()
        for subject in subjects:
            epoch, fit = prepared[subject], fitted[subject]
            for replicate in range(n_permutations+1):
                for index in range(len(epoch["X"])):
                    writer.writerow({"subject": subject, "replicate": replicate,
                        **{key: int(epoch[key][index]) for key in ("run", "event_index", "event_sample", "source_class")},
                        "target_class": int(fit["target_class"][replicate, index]),
                        "predicted_class": int(fit["predicted_class"][replicate, index]),
                        "decision_score": float(fit["decision_score"][replicate, index])})
    write_json(output/"decoding_results.json", group)
    write_json(output/"run_metadata.json", metadata)
    folds = [row for s in subjects for row in fitted[s]["fold_private"]]
    arrays = {key: np.concatenate([prepared[s][key] for s in subjects], axis=0)
              for key in ("X", "run", "event_index", "event_sample", "source_class")}
    arrays["subject"] = np.concatenate([np.full(len(prepared[s]["X"]), s, dtype=np.int64) for s in subjects])
    arrays.update({key: np.concatenate([fitted[s][key] for s in subjects], axis=1)
                   for key in ("target_class", "predicted_class", "decision_score")})
    arrays.update({"fold_"+key: np.array([row[key] for row in folds], dtype=np.int64)
                   for key in ("subject", "replicate", "test_run")})
    arrays.update({key: np.array([row[key] for row in folds]) for key in
                   ("csp_filters", "csp_rank", "csp_eigenvalues", "lda_coef", "lda_intercept", "lda_classes")})
    arrays.update({"source_epochs_json": np.array(json.dumps(source_rows)),
        "run_observations_json": np.array(json.dumps(observations)), "metadata_json": np.array(json.dumps(metadata)),
        "fold_warnings_json": np.array(json.dumps([{"subject": row["subject"], "replicate": row["replicate"],
            "test_run": row["test_run"], "warnings": row["warnings"]} for row in folds])),
        "raw_run_receipts_json": np.array(json.dumps({str(s): prepared[s]["raw_run_receipts"] for s in subjects})),
        "subjects": np.array(subjects, dtype=np.int64), "n_permutations": np.array(n_permutations),
        "pipeline_id": np.array(PIPELINE_ID)})
    np.savez_compressed(output/"analysis_arrays.npz", **arrays)
    t_description = ("The between-subject t statistic is undefined under the declared small/zero-variance rule."
        if group["group_p_vs_chance"] is None else
        f"The descriptive two-sided subject-level test versus 0.5 gives p={group['group_p_vs_chance']:.8g}.")
    (output/"findings.md").write_text(
        "# Offline held-out-run motor-imagery decoding\n\n"
        f"Status: {status}. Across {len(subjects)} measured subjects, mean pooled OOF accuracy="
        f"{group['accuracy']:.8f} and mean kappa={group['cohen_kappa']:.8f}. "
        f"{group['n_epochs_total']} retained epochs were evaluated; {metadata['n_dropped_epochs']} "
        "source target events were dropped for recorded annotation/boundary reasons. CSP and LDA "
        "were refitted on the other two acquisition runs for every held-out fold.\n\n"
        f"Each subject used {n_permutations} original-pair-preserving label permutations and the "
        f"same pooled OOF statistic. P-value resolution={group['permutation_p_resolution']:.8g}; "
        f"mean subject null SD={group['finite_sample_null_sd']:.8f}. "
        f"{group['n_subjects_significant_perm_p05']} subjects have unadjusted p<0.05 and "
        f"{group['n_subjects_significant_holm_p05']} have Holm-adjusted p<0.05 within the measured "
        f"family of {len(subjects)}; {group['n_subjects_below_chance']} are below nominal 0.5 accuracy. "
        f"{t_description}\n\n"
        "The observed source schedule contains balanced adjacent cue pairs. The null preserves "
        "those original pairs, fixing singleton or orphan labels; it assumes conditional label "
        "exchangeability within a pair, not proven experimental randomization or arbitrary serial "
        "independence. The labels identify visual-cue/imagery conditions, so decoding need not isolate "
        "motor imagery from cue-related activity or other condition-correlated signals. "
        "These fixed-cohort offline observations do not establish online BCI control. "
        "Nonsignificance does not show individual inability or BCI illiteracy. No historical numerical "
        "target, significance count, performance range or decoder-difficulty claim is imposed. "
        + ("This reduced resource pilot is not the production 10-subject/B200 result or a passing reference.\n"
           if status == "resource_pilot" else "\n"))
    print(json.dumps({"status": status, "n_subjects": len(subjects), "n_permutations": n_permutations,
                      "accuracy": group["accuracy"], "elapsed_seconds": time.monotonic()-started}), flush=True)
    return group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/app/data/eegbci"))
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--subjects", type=int, nargs="+", default=SUBJECTS)
    parser.add_argument("--permutations", type=int, default=N_PERMUTATIONS)
    parser.add_argument("--print-contracts", action="store_true")
    args = parser.parse_args()
    if args.print_contracts:
        manifest, _, _ = load_manifest(args.data, args.subjects, verify=False)
        print(json.dumps(metadata_contract(manifest), indent=2, allow_nan=False))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        run(args.data, args.output, args.subjects, args.permutations)
    except Exception as exc:
        failure = {"status": "failed_precondition", "pipeline_id": PIPELINE_ID, "reason": str(exc)}
        write_json(args.output/"run_metadata.json", failure)
        write_json(args.output/"decoding_results.json", failure)
        (args.output/"findings.md").write_text(f"# Failed precondition\n\n{exc}\n")
        raise


if __name__ == "__main__":
    main()
