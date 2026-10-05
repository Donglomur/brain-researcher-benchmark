"""Offline six-subject Sleep-EDF LOSO method baseline.

The original R&K annotations are collapsed into five labels; this is neither an
AASM rescoring nor a numerical reproduction of Kemp's slow-wave finding.
Importing this module performs no analysis, download, or filesystem writes.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

PIPELINE_ID = "sleepedf-loso-v2"
DATASET_ID = "sleep-edfx-1.0.0"
SUBJECTS = list(range(6))
RECORDING = 1
CHANNELS = ["EEG Fpz-Cz", "EEG Pz-Oz"]
CLASSES = ["W", "N1", "N2", "N3", "REM"]
BANDS = [[0.5, 4], [4, 8], [8, 12], [12, 16], [16, 30]]
ANN2LABEL = {"Sleep stage W": 0, "Sleep stage 1": 1, "Sleep stage 2": 2,
             "Sleep stage 3": 3, "Sleep stage 4": 3, "Sleep stage R": 4}
PREPROCESSING = {
    "crop_rule": "second_annotation_minus_1800_to_penultimate_plus_1800",
    "n_fft": 300, "n_per_seg": 300, "n_overlap": 0, "window": "hamming",
    "remove_dc": True, "average": "mean", "fmin": 0.5, "fmax": 30.0,
    "normalization": "sum_psd_bins", "band_reduction": "mean",
    "feature_order": "band_then_channel", "bands": BANDS,
}
CLASSIFIER = {
    "name": "RandomForestClassifier", "n_estimators": 200, "random_state": 0,
    "criterion": "gini", "max_depth": None, "min_samples_split": 2,
    "min_samples_leaf": 1, "max_features": "sqrt", "bootstrap": True,
}
PREDICTION_FIELDS = ["subject", "recording", "onset_sample", "true_class",
                     "predicted_class", "heldout_subject"]


def metadata_contract(source_sha256):
    """Return the public, data-specific analysis contract."""
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID,
        "subjects": SUBJECTS, "recording": RECORDING, "channels": CHANNELS,
        "epoch_sec": 30, "sfreq": 100, "classes": CLASSES,
        "preprocessing": PREPROCESSING, "classifier": CLASSIFIER,
        "cv_scheme": "leave-one-subject-out", "source_sha256": source_sha256,
    }


def load_inputs(data_dir):
    """Validate all twelve staged EDFs before resolving subject/file pairs."""
    data_dir = Path(data_dir).resolve()
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    entries = manifest["files"]
    if len(entries) != 2 * len(SUBJECTS):
        raise ValueError("require exactly six PSG/hypnogram pairs")
    pairs, source_sha256 = {}, {}
    for item in entries:
        subject, recording, role = item["subject"], item["recording"], item["role"]
        if type(subject) is not int or subject not in SUBJECTS:
            raise ValueError("source manifest has an unexpected subject")
        if type(recording) is not int or recording != RECORDING or role not in {"psg", "hypnogram"}:
            raise ValueError("source manifest has an unexpected recording or role")
        key = (subject, role)
        relative = Path(item["path"])
        path = (data_dir / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(data_dir):
            raise ValueError("source manifest paths must stay inside the data directory")
        if key in pairs or item["path"] in source_sha256:
            raise ValueError("duplicate source manifest entry")
        if path.stat().st_size != item["size_bytes"]:
            raise ValueError(f"source size mismatch: {relative}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"source SHA256 mismatch: {relative}")
        pairs[key] = path
        source_sha256[item["path"]] = digest
    expected = {(s, role) for s in SUBJECTS for role in ("psg", "hypnogram")}
    if set(pairs) != expected:
        raise ValueError("source manifest does not contain the exact six recording pairs")
    return pairs, source_sha256


def subject_epochs(psg, hypnogram, *, preload=True):
    """Apply the declared crop and return source-keyed, chronological epochs."""
    import mne

    raw = mne.io.read_raw_edf(psg, stim_channel=False, preload=False, verbose=False)
    if raw.info["sfreq"] != 100:
        raise ValueError("the pinned EEG derivations must be sampled at 100 Hz")
    if not set(CHANNELS).issubset(raw.ch_names):
        raise ValueError("one of the two prescribed EEG derivations is absent")
    ann = mne.read_annotations(hypnogram)
    if len(ann) < 3:
        raise ValueError("insufficient annotations for the prescribed crop")
    crop_start = float(ann[1]["onset"] - 1800)
    crop_end = float(ann[-2]["onset"] + 1800)
    ann.crop(crop_start, crop_end, verbose=False)
    raw.set_annotations(ann, emit_warning=False)
    raw.pick(CHANNELS)
    if raw.ch_names != CHANNELS:
        raise ValueError("unexpected EEG channel order")
    if preload:
        raw.load_data(verbose=False)
    events, _ = mne.events_from_annotations(
        raw, event_id=ANN2LABEL, chunk_duration=30.0, verbose=False)
    epochs = mne.Epochs(
        raw, events, event_id=None, tmin=0.0, tmax=29.99,
        baseline=None, preload=preload, on_missing="ignore", verbose=False)
    if not preload:
        epochs.drop_bad(verbose=False)
    onsets = epochs.events[:, 0].astype(np.int64)
    labels = epochs.events[:, 2].astype(np.int64)
    if not len(onsets) or np.any(np.diff(onsets) <= 0):
        raise ValueError("source epochs are empty or not strictly chronological")
    observed = {
        "crop_start_s": crop_start, "crop_end_s": crop_end,
        "n_epochs": int(len(onsets)),
        "first_onset_sample": int(onsets[0]), "last_onset_sample": int(onsets[-1]),
    }
    return epochs, labels, onsets, observed


def subject_features(psg, hypnogram):
    """Compute the declared ten band/channel features without cross-epoch fitting."""
    from mne.time_frequency import psd_array_welch

    epochs, labels, onsets, observed = subject_epochs(psg, hypnogram)
    psd, frequencies = psd_array_welch(
        epochs.get_data(), sfreq=100, fmin=0.5, fmax=30.0,
        n_fft=300, n_per_seg=300, n_overlap=0, window="hamming",
        remove_dc=True, average="mean", n_jobs=1, verbose=False)
    denominator = psd.sum(axis=-1, keepdims=True)
    if not np.isfinite(psd).all() or np.any(denominator <= 0):
        raise ValueError("invalid or zero-power EEG epoch")
    relative = psd / denominator
    features = np.concatenate([
        relative[:, :, (frequencies >= lo) & (frequencies < hi)].mean(axis=-1)
        for lo, hi in BANDS
    ], axis=1)
    if features.shape != (len(labels), 10) or not np.isfinite(features).all():
        raise ValueError("invalid ten-feature EEG matrix")
    return features, labels, onsets, observed


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(output_dir, data_dir):
    import mne
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix
    from sklearn.model_selection import LeaveOneGroupOut

    mne.set_log_level("ERROR")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs, source_sha256 = load_inputs(data_dir)
    features, labels, groups, onset_samples, observations = [], [], [], [], []
    for subject in SUBJECTS:
        x, y, onsets, observed = subject_features(
            inputs[subject, "psg"], inputs[subject, "hypnogram"])
        features.append(x)
        labels.append(y)
        groups.append(np.full(len(y), subject, dtype=np.int64))
        onset_samples.append(onsets)
        observations.append({"subject": subject, "recording": RECORDING, **observed})
    x, y, groups, onsets = map(np.concatenate, (features, labels, groups, onset_samples))
    if set(np.unique(y)) != set(range(len(CLASSES))):
        raise ValueError("the source cohort does not contain all five scored classes")
    np.savez_compressed(
        output_dir / "feature_receipt.npz", features=x, subject=groups,
        recording=np.full(len(y), RECORDING, dtype=np.int64), onset_sample=onsets,
        true_class=np.asarray(CLASSES, dtype="U3")[y])
    predictions = np.full(len(y), -1, dtype=np.int64)
    subject_rows, count_rows = [], []
    parameters = {key: value for key, value in CLASSIFIER.items() if key != "name"}
    for train, test in LeaveOneGroupOut().split(x, y, groups):
        subject = int(groups[test][0])
        if set(groups[train]) != set(SUBJECTS) - {subject}:
            raise ValueError("unexpected LOSO training membership")
        model = RandomForestClassifier(**parameters, n_jobs=2)
        predictions[test] = model.fit(x[train], y[train]).predict(x[test])
        subject_rows.append({
            "subject": subject, "n_test_epochs": int(len(test)),
            "accuracy": float(accuracy_score(y[test], predictions[test])),
            "kappa": float(cohen_kappa_score(y[test], predictions[test])),
        })
        matrix = confusion_matrix(y[test], predictions[test], labels=range(len(CLASSES)))
        for i, truth in enumerate(CLASSES):
            for j, prediction in enumerate(CLASSES):
                count_rows.append({"subject": subject, "true_class": truth,
                                   "predicted_class": prediction, "n_epochs": int(matrix[i, j])})
    if np.any(predictions < 0):
        raise ValueError("some source epochs have no held-out prediction")
    prediction_rows = [
        {"subject": int(subject), "recording": RECORDING, "onset_sample": int(onset),
         "true_class": CLASSES[int(truth)], "predicted_class": CLASSES[int(prediction)],
         "heldout_subject": int(subject)}
        for subject, onset, truth, prediction in zip(groups, onsets, y, predictions)
    ]
    accuracy = float(accuracy_score(y, predictions))
    kappa = float(cohen_kappa_score(y, predictions))
    result = {
        "pipeline_id": PIPELINE_ID, "cv_scheme": "leave-one-subject-out",
        "accuracy": accuracy, "cohen_kappa": kappa, "n_subjects": len(SUBJECTS),
        "n_epochs": int(len(y)), "n_classes": len(CLASSES), "classes": CLASSES,
    }
    metadata = {"status": "ok", **metadata_contract(source_sha256),
                "per_subject_observations": observations}
    write_csv(output_dir / "epoch_predictions.csv", PREDICTION_FIELDS, prediction_rows)
    write_csv(output_dir / "per_subject.csv",
              ["subject", "n_test_epochs", "accuracy", "kappa"], subject_rows)
    write_csv(output_dir / "confusion_counts.csv",
              ["subject", "true_class", "predicted_class", "n_epochs"], count_rows)
    write_json(output_dir / "staging_results.json", result)
    write_json(output_dir / "run_metadata.json", metadata)
    (output_dir / "findings.md").write_text(
        "# Sleep-EDF LOSO method baseline\n\n"
        f"Across {len(y)} scored epochs from six held-out recordings, accuracy was "
        f"{accuracy:.6f} and pooled Cohen kappa was {kappa:.6f}. Each subject's night "
        "was predicted using only the other five subjects. The source-keyed epoch "
        "predictions reproduce every confusion matrix and reported metric.\n\n"
        "These recordings use the original Rechtschaffen–Kales annotations, with "
        "stages 3 and 4 collapsed into N3. They were not rescored under AASM rules. "
        "This fixed six-recording method baseline supports a limited new-subject "
        "evaluation within the selected cohort; it does not reproduce Kemp's "
        "original slow-wave finding or establish performance in other populations.\n")
    print(json.dumps({"status": "ok", **result}, allow_nan=False))
    return result


def main():
    output_dir = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
    data_dir = Path(os.environ.get("SLEEPEDF_DATA_DIR", "/app/data/sleep-edf"))
    try:
        run(output_dir, data_dir)
    except Exception as error:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {"status": "failed_precondition", "reason": str(error),
                   "dataset_id": DATASET_ID, "pipeline_id": PIPELINE_ID}
        write_json(output_dir / "run_metadata.json", failure)
        write_json(output_dir / "staging_results.json", failure)
        (output_dir / "findings.md").write_text(f"# Failed precondition\n\n{error}\n")
        print(f"failed_precondition: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
