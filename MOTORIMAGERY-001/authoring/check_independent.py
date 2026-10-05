"""Independent source/epoch/null checks and a bounded alternate CSP/LDA solve.

Imports neither the oracle nor verifier. MNE EDF signal decoding, channel naming,
montage and FIR filtering are shared. EDF annotation parsing, epoch slicing,
pair-preserving permutations, statistics, covariance construction, CSP orchestration
and pooled-covariance LDA are implemented here. NumPy/SciPy numerical primitives
are shared dependencies, not an independent linear-algebra library.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import time
import traceback
from pathlib import Path

import numpy as np
from scipy import linalg, stats

PIPELINE = "eegbci-paired-null-held-run-csp-v3"
MANIFEST_SHA256 = "939a5725a743d3162f24ac1d10c6088888991559c4a07207ee935a4061fc88c7"
RUNS = (6, 10, 14)
SCORE_ATOL, SCORE_RTOL = 1e-7, 1e-5
FEATURE_ATOL, FEATURE_RTOL = 2e-8, 2e-7
VERSIONS = {"numpy": "2.2.6", "scipy": "1.17.0", "scikit-learn": "1.8.0", "mne": "1.12.1"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def close(actual, expected, name, atol=1e-6, rtol=1e-6):
    require(np.shape(actual) == np.shape(expected), f"{name}: shape mismatch")
    require(np.all(np.isfinite(actual)) and np.all(np.isfinite(expected)), f"{name}: nonfinite values")
    require(np.allclose(actual, expected, atol=atol, rtol=rtol), f"{name}: numerical mismatch")
    return float(np.max(np.abs(np.asarray(actual) - np.asarray(expected)))) if np.size(actual) else 0.0


def edf_header_annotations(path):
    """Read original EDF header/TAL bytes without MNE events or epoch objects."""
    with path.open("rb") as stream:
        fixed = stream.read(256)
        count, header_size = int(fixed[252:256]), int(fixed[184:192])
        records, seconds = int(fixed[236:244]), float(fixed[244:252])
        raw = stream.read(header_size - 256)
        fields, offset = {}, 0
        for name, width in [("label", 16), ("transducer", 80), ("unit", 8), ("physical_min", 8),
                            ("physical_max", 8), ("digital_min", 8), ("digital_max", 8),
                            ("prefilter", 80), ("samples", 8), ("reserved", 32)]:
            fields[name] = [raw[offset + width*i:offset + width*(i+1)].decode("ascii").strip() for i in range(count)]
            offset += width * count
        require(offset == len(raw), "EDF header size mismatch")
        samples = [int(value) for value in fields["samples"]]
        record_size = 2 * sum(samples)
        require(header_size + records * record_size == path.stat().st_size, "EDF record/file size mismatch")
        tal_indices = [i for i, label in enumerate(fields["label"]) if label == "EDF Annotations"]
        eeg = [i for i in range(count) if i not in tal_indices]
        annotations = []
        for record in range(records):
            for channel in tal_indices:
                stream.seek(header_size + record * record_size + 2 * sum(samples[:channel]))
                for entry in stream.read(2 * samples[channel]).split(b"\x00"):
                    parts = entry.split(b"\x14")
                    labels = [part.decode("ascii") for part in parts[1:] if part]
                    if labels:
                        time = parts[0].split(b"\x15")
                        onset = float(time[0])
                        duration = float(time[1]) if len(time) > 1 else 0.0
                        for label in labels:
                            annotations.append((onset, duration, label))
    return {"labels": [fields["label"][i] for i in eeg], "units": [fields["unit"][i] for i in eeg],
            "sfreq": [samples[i] / seconds for i in eeg], "n_samples": [samples[i]*records for i in eeg],
            "annotations": annotations, "duration": records*seconds}


def epoch_ledger(header, subject, run):
    """Original chronological T1/T2 identities, before any exclusions."""
    require(len(header["labels"]) == 64 and header["sfreq"] == [160.0]*64, "Original EEG dimensions changed")
    require(header["units"] == ["uV"]*64, "Original EEG physical units changed")
    require(len(set(header["n_samples"])) == 1, "Mixed sampling lengths")
    cues = [(t, d, label) for t, d, label in header["annotations"] if label in ("T1", "T2")]
    samples = [int(np.rint(t * 160.0)) for t, _, _ in cues]
    require(all(b > a for a, b in zip(samples, samples[1:])), "Cue samples must be unique and chronological")
    bad = [(t, t+d) for t, d, label in header["annotations"] if label.lower().startswith("bad")]
    rows = []
    for index, ((_, _, label), sample) in enumerate(zip(cues, samples)):
        first, stop = sample + 160, sample + 321
        reasons = []
        if first < 0 or stop > header["n_samples"][0]:
            reasons.append("out_of_bounds")
        if any(left < stop/160 and right > first/160 for left, right in bad):
            reasons.append("annotation")
        rows.append(dict(subject=subject, run=run, event_index=index, event_sample=sample,
                         source_class=int(label == "T2"), retained=int(not reasons), drop_reason=";".join(sorted(reasons))))
    return rows


def paired_labels(labels, runs, event_indices, n_permutations):
    """Preserve original cue pairs; exclusions never compact pair identities."""
    labels = np.asarray(labels, dtype=int)
    runs, event_indices = np.asarray(runs), np.asarray(event_indices)
    require(set(np.unique(labels)) == {0, 1}, "Both source classes are required")
    result = np.repeat(labels[None], n_permutations + 1, axis=0)
    rng = np.random.RandomState(0)
    for replicate in range(1, n_permutations + 1):
        for run in RUNS:
            within = np.flatnonzero(runs == run)
            for pair in sorted(set((event_indices[within] // 2).tolist())):
                members = within[event_indices[within] // 2 == pair]
                members = members[np.argsort(event_indices[members])]
                require(len(members) <= 2, "Duplicate original pair membership")
                if len(members) == 2:
                    require(set(event_indices[members]) == {2*pair, 2*pair+1}, "Invalid original pair IDs")
                    result[replicate, members] = rng.permutation(labels[members])
    return result


def independent_csp(X, labels, n_components=4):
    """Rebuild pinned MNE 1.12.1 empirical/GED behavior, not its CSP class.

    Empirical covariance assumes centered data rather than subtracting a mean;
    MNE's bias correction yields XX.T/(number_of_time_samples-1). Rank is
    estimated on the training data using its relative singular-value threshold.
    The restricting transformation is identity at full rank and otherwise a
    principal basis of the average class covariance. Only training data enter.
    """
    X, labels = np.asarray(X, dtype=float), np.asarray(labels, dtype=int)
    require(X.ndim == 3 and np.isfinite(X).all(), "Invalid training epochs")
    require(set(np.unique(labels)) == {0, 1}, "CSP requires both classes")
    channels = X.shape[1]
    flattened = X.transpose(1, 0, 2).reshape(channels, -1)
    singular = linalg.svdvals(flattened)
    rank_threshold = len(singular) * singular[0] * np.finfo(float).eps
    rank = int(np.sum(singular > rank_threshold))
    require(rank >= n_components, "Independent CSP training rank is insufficient")
    covariances = []
    for label in (0, 1):
        data = X[labels == label].transpose(1, 0, 2).reshape(channels, -1)
        covariance = (data @ data.T) / (data.shape[1] - 1)
        if rank < channels:
            _, vectors = linalg.eigh(covariance)
            basis = vectors[:, -rank:]
            covariance = basis @ (basis.T @ covariance @ basis) @ basis.T
        covariances.append(covariance)
    left, right = covariances
    if rank == channels:
        basis = np.eye(channels)
    else:
        _, vectors = linalg.eigh((left + right) / 2)
        basis = vectors[:, -rank:]
    eigenvalues, vectors = linalg.eigh(basis.T @ left @ basis, basis.T @ (left + right) @ basis)
    order = np.argsort(np.abs(eigenvalues - 0.5))[::-1][:n_components]
    filters = (basis @ vectors[:, order]).T
    return filters, {"rank": rank, "rank_threshold": float(rank_threshold),
                     "selected_eigenvalues": eigenvalues[order].tolist(),
                     "retained_singular_min": float(singular[rank-1]), "singular_max": float(singular[0])}


def log_power(X, filters):
    power = np.mean((filters @ X)**2, axis=2)
    require(np.all(np.isfinite(power)) and np.all(power > 0), "CSP power must be finite and positive")
    return np.log(power)


def independent_lda(features, labels):
    """Pooled within-class covariance eigensolve, not sklearn's two SVDs."""
    features, labels = np.asarray(features, dtype=float), np.asarray(labels, dtype=int)
    means = np.stack([features[labels == label].mean(axis=0) for label in (0, 1)])
    priors = np.array([np.mean(labels == label) for label in (0, 1)])
    require(len(labels) > 2 and np.all(priors > 0), "LDA needs both classes and positive residual df")
    within = features - means[labels]
    scale = np.std(within, axis=0, ddof=0)
    scale[scale == 0] = 1.0
    standardized = within / scale
    covariance = standardized.T @ standardized / (len(labels) - 2)
    eigenvalues, vectors = linalg.eigh(covariance)
    keep = eigenvalues > 1e-8  # pinned SVD tolerance 1e-4, squared
    precision = (vectors[:, keep] / eigenvalues[keep]) @ vectors[:, keep].T
    coef = (precision @ ((means[1] - means[0]) / scale)) / scale
    intercept = float(-0.5 * (means[1] + means[0]) @ coef + np.log(priors[1] / priors[0]))
    return coef, intercept, {"within_rank": int(keep.sum()), "normalized_covariance_eigenvalues": eigenvalues.tolist()}


def holm(values):
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    adjusted, largest = [0.0]*len(values), 0.0
    for index, subject in enumerate(order):
        largest = max(largest, (len(values)-index)*values[subject])
        adjusted[subject] = min(1.0, largest)
    return np.asarray(adjusted)


def subject_statistics(target, predicted):
    counts = np.sum(target == predicted, axis=1)
    accuracies = counts / target.shape[1]
    p = (1 + int(np.sum(counts[1:] >= counts[0]))) / len(counts)
    y, yh = target[0], predicted[0]
    expected = sum(np.mean(y == label)*np.mean(yh == label) for label in (0, 1))
    kappa = (accuracies[0] - expected) / (1-expected)
    return dict(accuracy=float(accuracies[0]), kappa=float(kappa), perm_p=float(p),
                null_mean=float(np.mean(accuracies[1:])), null_sd=float(np.std(accuracies[1:], ddof=0)),
                n_null_ge_observed=int(np.sum(counts[1:] >= counts[0])))


def source_epochs(data_dir, subjects):
    """Reverify bytes, parse EDF annotations independently, share only MNE signal I/O/FIR."""
    import mne
    from mne.datasets import eegbci

    manifest_raw = (data_dir / "data_manifest.json").read_bytes()
    require(hashlib.sha256(manifest_raw).hexdigest() == MANIFEST_SHA256, "Input manifest identity differs")
    manifest = json.loads(manifest_raw)
    ledger, data, retained, audit = [], [], [], []
    for record in manifest["files"]:
        path = data_dir / record["path"]
        require(not path.is_symlink() and path.stat().st_size == record["size_bytes"], "Source path/size mismatch")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], "Original EDF digest mismatch")
        if record["subject"] not in subjects:
            continue
        header = edf_header_annotations(path)
        rows = epoch_ledger(header, record["subject"], record["run"])
        require(len(rows) == 15, "Original task event count changed")
        require(all({rows[i]["source_class"], rows[i+1]["source_class"]} == {0, 1} for i in range(0, 14, 2)),
                "Original paired cue schedule differs")
        raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
        require(raw.ch_names == header["labels"] and raw.first_samp == 0, "EDF reader/header identity disagreement")
        eegbci.standardize(raw)
        raw.set_montage(mne.channels.make_standard_montage("standard_1005"), verbose="ERROR")
        picks = mne.pick_types(raw.info, eeg=True, exclude=[])
        require(len(picks) == 64 and np.array_equal(picks, np.arange(64)), "EEG channel order mismatch")
        raw.filter(7.0, 30.0, picks=picks, filter_length="auto", l_trans_bandwidth="auto", h_trans_bandwidth="auto",
                   n_jobs=1, method="fir", phase="zero", fir_window="hamming", fir_design="firwin",
                   skip_by_annotation=("edge", "bad_acq_skip"), pad="reflect_limited", verbose="ERROR")
        filtered = raw.get_data(picks=picks)
        for row in rows:
            if row["retained"]:
                start = row["event_sample"] + 160
                epoch = filtered[:, start:start+161]
                require(epoch.shape == (64, 161), "Independent epoch boundary error")
                data.append(epoch)
                retained.append(row)
        ledger.extend(rows)
        audit.append({"path": record["path"], "sha256": record["sha256"], "duration_seconds": header["duration"],
                      "n_source_events": len(rows), "n_retained": sum(row["retained"] for row in rows),
                      "observed_balanced_pairs": 7, "sfreq": 160, "physical_unit": "uV", "reader_output_unit": "V",
                      "channels": raw.ch_names})
    return np.stack(data), retained, ledger, audit


def identity(row):
    return tuple(int(row[key]) for key in ("subject", "run", "event_index"))


def source_row(row):
    return {key: str(row[key]) if key == "drop_reason" else int(row[key]) for key in
            ("subject", "run", "event_index", "event_sample", "source_class", "retained", "drop_reason")}


def unique_rows(rows, key_function, name):
    mapped = {key_function(row): row for row in rows}
    require(len(mapped) == len(rows), f"{name}: duplicate identity")
    return mapped


def compare_ledgers(actual, expected, name):
    actual = unique_rows([source_row(row) for row in actual], identity, name)
    expected = unique_rows([source_row(row) for row in expected], identity, "independent ledger")
    require(actual == expected, f"{name}: original source event membership differs")


def aggregate_statistics(rows, n_permutations):
    accuracy = np.array([row["accuracy"] for row in rows])
    pvalues = np.array([row["perm_p"] for row in rows])
    adjusted = holm(pvalues)
    for row, value in zip(rows, adjusted):
        row["holm_p"] = float(value)
    if len(accuracy) < 2 or np.all(accuracy == accuracy[0]):
        tvalue = pvalue = None
    else:
        # Independently assemble the t statistic; use the shared SciPy t CDF.
        tvalue = float((accuracy.mean()-0.5) / (np.std(accuracy, ddof=1) / math.sqrt(len(accuracy))))
        pvalue = float(2 * stats.t.sf(abs(tvalue), len(accuracy)-1))
    return {"n_subjects": len(rows), "n_epochs_total": sum(row["n_epochs"] for row in rows),
            "n_classes": 2, "chance_level": 0.5, "accuracy": float(accuracy.mean()),
            "cohen_kappa": float(np.mean([row["kappa"] for row in rows])),
            "finite_sample_null_sd": float(np.mean([row["null_sd"] for row in rows])),
            "group_t_vs_chance": tvalue, "group_p_vs_chance": pvalue,
            "n_subjects_significant_perm_p05": int(np.sum(pvalues < .05)),
            "n_subjects_significant_holm_p05": int(np.sum(adjusted < .05)),
            "n_subjects_below_chance": int(np.sum(accuracy < .5)),
            "n_subjects_above_half_nominal": int(np.sum(accuracy > .5)),
            "permutation_p_resolution": 1/(n_permutations+1)}


def validate_public_outputs(output, arrays, ledger, subjects, permutations):
    compare_ledgers(read_csv(output / "source_epochs.csv"), ledger, "public source ledger")
    rows = read_csv(output / "oof_predictions.csv")
    mapped = unique_rows(rows, lambda row: (*identity(row), int(row["replicate"])), "public OOF")
    n = len(arrays["subject"])
    require(len(mapped) == n*(permutations+1), "Public OOF coverage differs")
    for index in range(n):
        key = tuple(int(arrays[k][index]) for k in ("subject", "run", "event_index"))
        for replicate in range(permutations+1):
            require((*key, replicate) in mapped, "Missing public source event/replicate")
            row = mapped[(*key, replicate)]
            for field in ("event_sample", "source_class"):
                require(int(row[field]) == int(arrays[field][index]), f"Public OOF {field} differs")
            for field in ("target_class", "predicted_class"):
                require(int(row[field]) == int(arrays[field][replicate, index]), f"Public OOF {field} differs")
            close(float(row["decision_score"]), arrays["decision_score"][replicate, index],
                  "public decision score", SCORE_ATOL, SCORE_RTOL)
            require(int(row["predicted_class"]) == int(float(row["decision_score"]) > 0), "Public score/class sign mismatch")
    summaries = []
    folds = unique_rows(read_csv(output / "fold_receipts.csv"),
                        lambda row: (int(row["subject"]), int(row["replicate"]), int(row["test_run"])), "public folds")
    require(len(folds) == len(subjects)*(permutations+1)*3, "Public fold coverage differs")
    for subject in subjects:
        selected = arrays["subject"] == subject
        y, yh = arrays["target_class"][:, selected], arrays["predicted_class"][:, selected]
        runs = arrays["run"][selected]
        summaries.append({"subject": subject, "n_epochs": int(selected.sum()), "n_runs": len(np.unique(runs)),
                          **subject_statistics(y, yh)})
        for replicate in range(permutations+1):
            for run in RUNS:
                row = folds[(subject, replicate, run)]
                test = runs == run
                expected = {"n_train": int((~test).sum()), "n_test": int(test.sum()),
                            "n_train_class0": int(np.sum(y[replicate, ~test] == 0)),
                            "n_train_class1": int(np.sum(y[replicate, ~test] == 1)),
                            "n_test_class0": int(np.sum(y[replicate, test] == 0)),
                            "n_test_class1": int(np.sum(y[replicate, test] == 1))}
                for key, value in expected.items():
                    require(int(row[key]) == value, f"Fold {key} differs")
                close(float(row["accuracy"]), np.mean(y[replicate, test] == yh[replicate, test]), "fold accuracy")
    group = aggregate_statistics(summaries, permutations)
    per_subject = unique_rows(read_csv(output / "per_subject.csv"), lambda row: int(row["subject"]), "subject summaries")
    require(set(per_subject) == set(subjects), "Subject summary identities differ")
    for expected in summaries:
        actual = per_subject[expected["subject"]]
        for key, value in expected.items():
            if key in ("subject", "n_epochs", "n_runs", "n_null_ge_observed"):
                require(int(actual[key]) == value, f"Subject summary {key} differs")
            else:
                close(float(actual[key]), value, f"Subject summary {key}")
    headline = json.loads((output / "decoding_results.json").read_text())
    expected_status = "ok" if subjects == list(range(1, 11)) and permutations == 200 else "resource_pilot"
    require(headline["status"] == expected_status and headline["pipeline_id"] == PIPELINE, "Public result identity differs")
    for key, value in group.items():
        if value is None:
            require(headline[key] is None, f"Undefined group quantity {key} must be null")
        elif isinstance(value, int):
            require(type(headline[key]) is int and headline[key] == value, f"Group count {key} differs")
        else:
            close(headline[key], value, f"Group summary {key}")
    return summaries, group


def check(data_dir, output, report, pilot=False):
    report["versions"] = {package: importlib.metadata.version(package) for package in VERSIONS}
    require(report["versions"] == VERSIONS, "Independent checker dependency pins differ")
    with np.load(output / "analysis_arrays.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    for key in ("subjects", "n_permutations", "subject", "run", "event_index", "event_sample", "source_class", "target_class",
                "predicted_class", "fold_subject", "fold_replicate", "fold_test_run", "csp_rank", "lda_classes"):
        require(arrays[key].dtype.kind in "iu", f"Private identity/class array {key} must be integer-valued")
    subjects = [int(s) for s in arrays["subjects"]]
    permutations = int(arrays["n_permutations"])
    require((subjects, permutations) == ([1], 5) if pilot else
            (subjects, permutations) == (list(range(1, 11)), 200), "Unexpected scope; --pilot permits only S001/B5")
    require(str(arrays["pipeline_id"]) == PIPELINE, "Wrong private pipeline identity")
    report.update(subjects=subjects, n_permutations=permutations,
                  selected_replicates=[r for r in (0, 1, 100, 200) if r <= permutations])
    report["current_stage"] = "original EDF parsing, shared FIR, independent run-local epoch slicing"
    X, retained, ledger, source_audit = source_epochs(data_dir, subjects)
    report["sources"] = source_audit
    compare_ledgers(json.loads(str(arrays["source_epochs_json"])), ledger, "private source ledger")
    source_indices = unique_rows([{**row, "position": i} for i, row in enumerate(retained)], identity, "retained source")
    n = len(arrays["subject"])
    require(n == len(retained), "Private retained count differs")
    keys = [tuple(int(arrays[name][i]) for name in ("subject", "run", "event_index")) for i in range(n)]
    require(len(set(keys)) == n and set(keys) == set(source_indices), "Private retained source identities differ")
    X = X[[source_indices[key]["position"] for key in keys]]
    for i, key in enumerate(keys):
        for field in ("event_sample", "source_class"):
            require(int(arrays[field][i]) == source_indices[key][field], f"Private {field} differs from EDF")
    report["max_epoch_absolute_difference_volts"] = close(arrays["X"], X, "independent epoch matrix", 1e-15, 1e-10)
    require(arrays["target_class"].shape == (permutations+1, n), "Private target dimensions differ")
    require(arrays["predicted_class"].shape == arrays["decision_score"].shape == arrays["target_class"].shape,
            "Private prediction dimensions differ")
    require(np.isfinite(arrays["decision_score"]).all(), "Nonfinite decision score")
    require(np.array_equal(arrays["predicted_class"], (arrays["decision_score"] > 0).astype(int)), "Private score/class signs differ")
    for subject in subjects:
        keep = arrays["subject"] == subject
        expected = paired_labels(arrays["source_class"][keep], arrays["run"][keep], arrays["event_index"][keep], permutations)
        require(np.array_equal(arrays["target_class"][:, keep], expected), "Original-pair permutation labels differ")
    metadata = json.loads(str(arrays["metadata_json"]))
    require(metadata == json.loads((output / "run_metadata.json").read_text()), "Private/public metadata differ")
    require(metadata["pipeline_id"] == PIPELINE and metadata["source_manifest_sha256"] == MANIFEST_SHA256,
            "Metadata source/pipeline identity differs")
    require(metadata["executed_subjects"] == subjects and metadata["executed_permutations"] == permutations,
            "Metadata executed scope differs")
    source_manifest = json.loads((data_dir / "data_manifest.json").read_text())
    require(metadata["source_sha256"] == {r["path"]: r["sha256"] for r in source_manifest["files"]}, "Metadata source hashes differ")
    require(metadata["channels"] == source_audit[0]["channels"] and metadata["sfreq"] == 160,
            "Metadata original channel identity/sample rate differ")
    observations = []
    for subject in subjects:
        for run in RUNS:
            these = [row for row in ledger if row["subject"] == subject and row["run"] == run]
            kept = sum(row["retained"] for row in these)
            observations.append(dict(subject=subject, run=run, n_source_events=len(these), n_retained=kept, n_dropped=len(these)-kept))
    require(metadata["n_epochs_by_run"] == observations == json.loads(str(arrays["run_observations_json"])),
            "Per-run original event accounting differs")
    for field, value in {"n_subjects": len(subjects), "n_epochs_total": n, "n_source_events": len(ledger),
                         "n_dropped_epochs": len(ledger)-n}.items():
        require(metadata[field] == value, f"Metadata {field} differs")
    report["subject_statistics"], report["group_statistics"] = validate_public_outputs(output, arrays, ledger, subjects, permutations)
    fold_keys = list(zip(arrays["fold_subject"].astype(int), arrays["fold_replicate"].astype(int), arrays["fold_test_run"].astype(int)))
    expected_keys = {(s, replicate, run) for s in subjects for replicate in range(permutations+1) for run in RUNS}
    require(len(set(fold_keys)) == len(fold_keys) and set(fold_keys) == expected_keys, "Private model-fold identities differ")
    folds = {key: i for i, key in enumerate(fold_keys)}
    for field, shape in {"csp_filters": (len(folds), 4, 64), "csp_rank": (len(folds),),
                         "csp_eigenvalues": (len(folds), 4), "lda_coef": (len(folds), 4),
                         "lda_intercept": (len(folds),), "lda_classes": (len(folds), 2)}.items():
        require(arrays[field].shape == shape and np.isfinite(arrays[field]).all(), f"Private {field} shape/finite check failed")
    require(np.all(arrays["lda_classes"] == [0, 1]), "Private model class direction differs")
    require(np.all((arrays["csp_rank"] >= 4) & (arrays["csp_rank"] <= 64)), "Private CSP rank outside channel dimension")
    report["current_stage"] = "all-fold saved-model score reconstruction"
    maximum = 0.0
    for subject, replicate, run in sorted(folds):
        model = folds[(subject, replicate, run)]
        test = (arrays["subject"] == subject) & (arrays["run"] == run)
        scores = log_power(X[test], arrays["csp_filters"][model]) @ arrays["lda_coef"][model] + arrays["lda_intercept"][model]
        maximum = max(maximum, close(scores, arrays["decision_score"][replicate, test], "saved-model decision scores", SCORE_ATOL, SCORE_RTOL))
    report["all_saved_fold_models_checked"] = len(folds)
    report["max_saved_model_score_absolute_difference"] = maximum
    report["independent_folds"] = []
    alternate = {field: [] for field in ("subject", "run", "event_index", "event_sample", "replicate",
                                        "source_class", "target_class", "predicted_class", "decision_score")}
    for subject in subjects:
        for replicate in report["selected_replicates"]:
            for run in RUNS:
                report["current_stage"] = f"independent classifier subject={subject} replicate={replicate} held_run={run}"
                train = (arrays["subject"] == subject) & (arrays["run"] != run)
                test = (arrays["subject"] == subject) & (arrays["run"] == run)
                target = arrays["target_class"][replicate]
                model = folds[(subject, replicate, run)]
                filters, csp_qc = independent_csp(X[train], target[train])
                train_features, test_features = log_power(X[train], filters), log_power(X[test], filters)
                feature_difference = max(close(train_features, log_power(X[train], arrays["csp_filters"][model]),
                                                "independent training CSP features", FEATURE_ATOL, FEATURE_RTOL),
                                         close(test_features, log_power(X[test], arrays["csp_filters"][model]),
                                               "independent test CSP features", FEATURE_ATOL, FEATURE_RTOL))
                require(csp_qc["rank"] == int(arrays["csp_rank"][model]), "Independent training rank differs")
                eigen_difference = close(csp_qc["selected_eigenvalues"], arrays["csp_eigenvalues"][model],
                                         "CSP eigenvalues", 2e-8, 2e-7)
                coef, intercept, lda_qc = independent_lda(train_features, target[train])
                scores = test_features @ coef + intercept
                score_difference = close(scores, arrays["decision_score"][replicate, test],
                                         "independent classifier decisions", SCORE_ATOL, SCORE_RTOL)
                predictions = (scores > 0).astype(int)
                disagreement = int(np.sum(predictions != arrays["predicted_class"][replicate, test]))
                report["independent_folds"].append({"subject": subject, "replicate": replicate, "held_run": run,
                    "csp": csp_qc, "lda": lda_qc, "max_log_power_difference": feature_difference,
                    "max_eigenvalue_difference": eigen_difference, "max_score_difference": score_difference,
                    "score_matched_near_boundary_label_disagreements": disagreement,
                    "independent_accuracy": float(np.mean(predictions == target[test]))})
                for index, score, prediction in zip(np.flatnonzero(test), scores, predictions):
                    for field in ("subject", "run", "event_index", "event_sample", "source_class"):
                        alternate[field].append(int(arrays[field][index]))
                    alternate["replicate"].append(replicate)
                    alternate["target_class"].append(int(target[index]))
                    alternate["predicted_class"].append(int(prediction))
                    alternate["decision_score"].append(float(score))
    report["current_stage"] = "complete"
    rank_by_fold = {(row["subject"], row["held_run"]): row["csp"]["rank"] for row in report["independent_folds"]}
    for (subject, _, run), model in folds.items():
        require(arrays["csp_rank"][model] == rank_by_fold[(subject, run)],
                "Training rank changed across label-only permutations")
    report["independent_refit_folds"] = len(report["independent_folds"])
    report["max_independent_score_absolute_difference"] = max(row["max_score_difference"] for row in report["independent_folds"])
    result = {field: np.asarray(values, dtype=float if field == "decision_score" else np.int64) for field, values in alternate.items()}
    result.update(pipeline_id=np.array(PIPELINE), source_manifest_sha256=np.array(MANIFEST_SHA256),
                  source_sha256_json=np.array(json.dumps(metadata["source_sha256"], sort_keys=True)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/eegbci"))
    parser.add_argument("--oracle-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true", help="Permit only the predeclared subject-1, B=5 resource pilot")
    args = parser.parse_args()
    alternate_path = args.report.with_suffix(".alternate_scores.npz")
    if args.report.exists() or alternate_path.exists():
        raise SystemExit("Preserve existing independent-check evidence; use new output paths")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "pipeline_id": PIPELINE,
              "independent_components": ["original EDF header/TAL annotation parsing", "run-local epoch slicing and source ledger",
                "original-pair null label generation", "all OOF/fold/summary algebra and Holm correction",
                "uncentered class second moments and training rank", "CSP generalized eigensystem orchestration",
                "normalized pooled-within-covariance LDA instead of sklearn two-SVD fit"],
              "shared_components": ["original source files", "MNE EDF signal decoding and channel standardization/montage",
                "MNE FIR filtering", "NumPy RandomState generator", "NumPy/SciPy numerical kernels including generalized eigh",
                "public estimator contract", "SciPy t distribution survival function"],
              "limits": ["Not an independent acquisition or independently implemented FIR filter",
                "Only observed and selected null replicates receive independent classifier refits; all saved models are algebraically checked",
                "No eigenvector-sign comparison; features and class-1 decision scores are compared",
                "Score-matched near-zero sign changes are reported, not rejected solely for classification disagreement",
                "The paired null assumes within-pair exchangeability; no experimental randomization claim"],
              "tolerances": {"epoch_atol_volts": 1e-15, "epoch_rtol": 1e-10,
                "log_power_atol": FEATURE_ATOL, "log_power_rtol": FEATURE_RTOL,
                "decision_score_atol": SCORE_ATOL, "decision_score_rtol": SCORE_RTOL}}
    started = time.monotonic()
    try:
        alternate = check(args.data_dir, args.oracle_output, report, args.pilot)
        np.savez_compressed(alternate_path, **alternate)
        report.update(status="passed", alternate_scores_path=str(alternate_path),
                      alternate_scores_sha256=hashlib.sha256(alternate_path.read_bytes()).hexdigest())
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
    report["elapsed_seconds"] = time.monotonic()-started
    with args.report.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("status", "elapsed_seconds")}, allow_nan=False))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
