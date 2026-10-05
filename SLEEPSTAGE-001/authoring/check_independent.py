"""Reconstruct source epochs and Welch features without the oracle's epoch/PSD code.

Shares MNE EDF/annotation readers and sklearn RandomForest; independently clips
annotation intervals, slices samples, computes SciPy Welch, and iterates LOSO.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path

import mne
import numpy as np
from scipy.signal import welch
from sklearn.ensemble import RandomForestClassifier

CLASSES = ["W", "N1", "N2", "N3", "REM"]
MAPPING = {"Sleep stage W": 0, "Sleep stage 1": 1, "Sleep stage 2": 2,
           "Sleep stage 3": 3, "Sleep stage 4": 3, "Sleep stage R": 4}
BANDS = [(0.5, 4), (4, 8), (8, 12), (12, 16), (16, 30)]


def reconstruct(data, manifest):
    features, labels, subjects, onsets = [], [], [], []
    for subject in range(6):
        records = {row["role"]: row for row in manifest["files"] if row["subject"] == subject}
        for record in records.values():
            path = data / record["path"]
            with path.open("rb") as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest() == record["sha256"]
        raw = mne.io.read_raw_edf(data / records["psg"]["path"], stim_channel=False, preload=False,
                                 verbose=False).pick(["EEG Fpz-Cz", "EEG Pz-Oz"])
        annotations = mne.read_annotations(data / records["hypnogram"]["path"])
        sfreq = raw.info["sfreq"]
        assert sfreq == 100 and raw.first_samp == 0
        # Align the two EDF clocks explicitly; no oracle/MNE epoch-construction call.
        # MNE's EDF annotation reader uses orig_time=None for recording-relative
        # onsets; an explicit origin, when present, must be aligned to the PSG.
        offset = 0.0 if annotations.orig_time is None else (
            annotations.orig_time - raw.info["meas_date"]).total_seconds()
        lower = annotations.onset[1] - 1800
        upper = annotations.onset[-2] + 1800
        start_samples, stages = [], []
        for onset, duration, description in zip(annotations.onset, annotations.duration, annotations.description):
            if description not in MAPPING:
                continue
            start, stop = max(float(onset), lower), min(float(onset + duration), upper)
            for epoch_onset in np.arange(start, stop - 30 + 1e-8, 30):
                sample = int(round((epoch_onset + offset) * sfreq))
                if sample >= 0 and sample + 3000 <= raw.n_times:
                    start_samples.append(sample)
                    stages.append(MAPPING[description])
        signals = raw.get_data()
        epochs = np.stack([signals[:, sample:sample + 3000] for sample in start_samples])
        freq, psd = welch(epochs, fs=100, window="hamming", nperseg=300, noverlap=0,
                          nfft=300, detrend="constant", scaling="density", average="mean", axis=-1)
        keep = (freq >= 0.5) & (freq <= 30)
        freq, psd = freq[keep], psd[..., keep]
        relative = psd / psd.sum(axis=-1, keepdims=True)
        features.append(np.concatenate([relative[..., (freq >= lo) & (freq < hi)].mean(axis=-1)
                                        for lo, hi in BANDS], axis=1))
        labels.extend(stages)
        subjects.extend([subject] * len(stages))
        onsets.extend(start_samples)
        print(f"subject={subject} independently reconstructed epochs={len(stages)}", flush=True)
    return np.concatenate(features), np.array(labels), np.array(subjects), np.array(onsets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/sleep-edf"))
    parser.add_argument("--oracle-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    mne.set_log_level("ERROR")
    manifest = json.loads((args.data_dir / "data_manifest.json").read_text())
    X, y, subjects, onsets = reconstruct(args.data_dir, manifest)
    with np.load(args.oracle_output / "feature_receipt.npz", allow_pickle=False) as receipt:
        assert np.array_equal(receipt["subject"], subjects)
        assert np.array_equal(receipt["onset_sample"], onsets)
        assert np.array_equal(receipt["true_class"], np.array(CLASSES)[y])
        feature_difference = float(np.max(np.abs(receipt["features"] - X)))
        np.testing.assert_allclose(receipt["features"], X, rtol=1e-10, atol=1e-14)
    with (args.oracle_output / "epoch_predictions.csv").open(newline="") as stream:
        oracle = {(int(row["subject"]), int(row["onset_sample"])): row for row in csv.DictReader(stream)}
    assert set(oracle) == set(zip(subjects.tolist(), onsets.tolist())), "epoch source identity mismatch"
    assert all(oracle[(int(s), int(t))]["true_class"] == CLASSES[int(label)]
               for s, t, label in zip(subjects, onsets, y)), "source-stage mismatch"
    predicted = np.empty(len(y), dtype=int)
    for subject in range(6):
        test = subjects == subject
        model = RandomForestClassifier(n_estimators=200, random_state=0, n_jobs=2,
                                        criterion="gini", max_depth=None, min_samples_split=2,
                                        min_samples_leaf=1, max_features="sqrt", bootstrap=True)
        model.fit(X[~test], y[~test])
        predicted[test] = model.predict(X[test])
    disagreements = [{"subject": int(s), "onset_sample": int(t), "independent": CLASSES[int(p)],
                      "oracle": oracle[(int(s), int(t))]["predicted_class"]}
                     for s, t, p in zip(subjects, onsets, predicted)
                     if CLASSES[int(p)] != oracle[(int(s), int(t))]["predicted_class"]]
    report = {"evidence_type": "independent_epoch_construction_and_scipy_psd_shared_reader_and_classifier",
              "n_epochs": len(y), "per_subject_epochs": {str(s): int((subjects == s).sum()) for s in range(6)},
              "source_keys_and_true_labels_agree": True, "prediction_disagreements": disagreements,
              "max_absolute_feature_difference": feature_difference,
              "n_prediction_disagreements": len(disagreements),
              "accuracy": float(np.mean(predicted == y)),
              "versions": {name: importlib.metadata.version(name) for name in ("mne", "numpy", "scipy", "scikit-learn")},
              "scope": "Shared MNE EDF readers and sklearn RF; independently reconstructs annotation clipping, epoch samples, Welch and features. Not clinical or original paper validation."}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    assert not disagreements, "independent implementation changes categorical predictions"


if __name__ == "__main__":
    main()
