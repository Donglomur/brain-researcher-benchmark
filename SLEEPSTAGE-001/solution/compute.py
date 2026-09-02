"""Reference solution for SLEEPSTAGE-001.

Stage sleep into the 5 AASM classes (W, N1, N2, N3, REM) from the Sleep-EDF
(PhysioNet, mne.datasets.sleep_physionet) EEG, in 30-s epochs, and report the
CROSS-VALIDATED staging accuracy and Cohen kappa on a pinned set of subjects.

The one choice the brief leaves un-cued is the cross-validation scheme. Consecutive
30-s epochs from the same recording are highly autocorrelated (sleep is piecewise
stationary) and come from the same subject, so a RANDOM epoch-wise k-fold puts
near-duplicate neighbours of each test epoch into the training set and leaks subject
identity -> the accuracy is badly INFLATED. The honest estimate of how well the stager
generalises to a NEW night/subject is SUBJECT-WISE cross-validation
(leave-one-subject-out), where all of a subject's epochs are held out together.

Everything else is pinned (subjects, recording, channels, 30-s epochs, the 5-class AASM
mapping, the relative band-power features, and a 200-tree random forest), so only the
CV scheme moves the number. Validated on the pinned subject set (see findings.md):
subject-wise accuracy is materially LOWER than the random-k-fold accuracy.
"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

SUBJECTS = [0, 1, 2, 3, 4, 5]   # PINNED fixed subject set
RECORDING = [1]                 # night 1

# AASM 5-class mapping (stage 3 and 4 merge into N3)
ANN2LABEL = {"Sleep stage W": 0, "Sleep stage 1": 1, "Sleep stage 2": 2,
             "Sleep stage 3": 3, "Sleep stage 4": 3, "Sleep stage R": 4}
CLASS_NAMES = ["W", "N1", "N2", "N3", "REM"]
BANDS = [(0.5, 4.0), (4.0, 8.0), (8.0, 12.0), (12.0, 16.0), (16.0, 30.0)]  # delta theta alpha sigma beta


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "sleep-edf (PhysioNet Sleep-EDF Expanded)"}, indent=2))
    (OUT / "staging_results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from mne.datasets.sleep_physionet.age import fetch_data
    from mne.time_frequency import psd_array_welch
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold, LeaveOneGroupOut
    from sklearn.metrics import accuracy_score, cohen_kappa_score
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")


def subject_features(subj):
    """Relative band-power features (5 bands x 2 EEG channels) for each 30-s epoch."""
    psg, hyp = fetch_data(subjects=[subj], recording=RECORDING, verbose=False)[0]
    raw = mne.io.read_raw_edf(psg, stim_channel=False, verbose=False, preload=False)
    ann = mne.read_annotations(hyp)
    # trim the long wake padding before/after lights-off (standard Sleep-EDF handling)
    ann.crop(ann[1]["onset"] - 30 * 60, ann[-2]["onset"] + 30 * 60, verbose=False)
    raw.set_annotations(ann, emit_warning=False)
    raw.pick([c for c in raw.ch_names if "Fpz-Cz" in c or "Pz-Oz" in c]).load_data()
    events, _ = mne.events_from_annotations(raw, event_id=ANN2LABEL, chunk_duration=30.0,
                                            verbose=False)
    tmax = 30.0 - 1.0 / raw.info["sfreq"]
    ep = mne.Epochs(raw, events, None, 0.0, tmax, baseline=None, preload=True,
                    verbose=False, on_missing="ignore")
    y = ep.events[:, 2]
    data = ep.get_data()
    sf = raw.info["sfreq"]
    psds, freqs = psd_array_welch(data, sfreq=sf, fmin=0.5, fmax=30.0,
                                  n_fft=int(sf * 3), verbose=False)
    rel = psds / psds.sum(axis=-1, keepdims=True)
    X = np.concatenate([rel[:, :, (freqs >= lo) & (freqs < hi)].mean(axis=-1)
                        for lo, hi in BANDS], axis=1)
    return X, y


try:
    Xs, ys, groups = [], [], []
    for s in SUBJECTS:
        X, y = subject_features(s)
        Xs.append(X); ys.append(y); groups.append(np.full(len(y), s))
    X = np.concatenate(Xs); y = np.concatenate(ys); g = np.concatenate(groups)
except Exception as e:
    fail(f"could not build features from Sleep-EDF: {e}")

if len(np.unique(g)) < len(SUBJECTS) or len(y) < 3000:
    fail(f"insufficient data: {len(np.unique(g))} subjects, {len(y)} epochs")


def rf():
    return RandomForestClassifier(n_estimators=200, random_state=0, n_jobs=-1)


# ---- honest estimate: SUBJECT-WISE (leave-one-subject-out) ----
logo = LeaveOneGroupOut()
rows, yt, yp = [], [], []
for tr, te in logo.split(X, y, g):
    clf = rf().fit(X[tr], y[tr])
    pred = clf.predict(X[te])
    subj = int(g[te][0])
    rows.append(dict(fold=f"subject_{subj}", n_test_epochs=int(len(te)),
                     accuracy=float(accuracy_score(y[te], pred)),
                     kappa=float(cohen_kappa_score(y[te], pred))))
    yt.append(y[te]); yp.append(pred)
yt = np.concatenate(yt); yp = np.concatenate(yp)
acc_subj = float(accuracy_score(yt, yp))
kappa_subj = float(cohen_kappa_score(yt, yp))

# ---- for the write-up: the random epoch-wise k-fold (leaky) number, for contrast ----
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
yt2, yp2 = [], []
for tr, te in skf.split(X, y):
    clf = rf().fit(X[tr], y[tr])
    yt2.append(y[te]); yp2.append(clf.predict(X[te]))
yt2 = np.concatenate(yt2); yp2 = np.concatenate(yp2)
acc_rand = float(accuracy_score(yt2, yp2))
kappa_rand = float(cohen_kappa_score(yt2, yp2))

with open(OUT / "per_fold.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["fold", "n_test_epochs", "accuracy", "kappa"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

(OUT / "staging_results.json").write_text(json.dumps({
    "cv_scheme": "leave-one-subject-out",
    "accuracy": acc_subj,
    "cohen_kappa": kappa_subj,
    "n_subjects": len(SUBJECTS),
    "n_epochs": int(len(y)),
    "n_classes": 5,
    "classes": CLASS_NAMES,
    "random_kfold_accuracy_for_reference": acc_rand,
    "random_kfold_kappa_for_reference": kappa_rand,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "sleep-edf (PhysioNet Sleep-EDF Expanded, age cohort)",
    "subjects": SUBJECTS,
    "recording": RECORDING,
    "channels": ["EEG Fpz-Cz", "EEG Pz-Oz"],
    "epoch_sec": 30,
    "classes": CLASS_NAMES,
    "features": "relative band power (delta/theta/alpha/sigma/beta) per channel, Welch n_fft=3s",
    "classifier": "RandomForestClassifier(n_estimators=200, random_state=0)",
    "cv_scheme": "leave-one-subject-out (subject-wise)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# SLEEPSTAGE-001 - 5-class AASM sleep staging (Sleep-EDF)

On the pinned Sleep-EDF set (subjects {SUBJECTS}, night 1; EEG Fpz-Cz + Pz-Oz; 30-s
epochs; relative band-power features; 200-tree random forest), the **honest,
subject-generalising** staging performance -- **leave-one-subject-out**
cross-validation -- is:

* **accuracy = {acc_subj:.3f}**
* **Cohen kappa = {kappa_subj:.3f}**

over {len(y)} epochs across the 5 AASM classes ({", ".join(CLASS_NAMES)}).

## Why subject-wise, not random k-fold
Consecutive 30-s epochs from one night are highly autocorrelated and share subject
identity, so a **random epoch-wise k-fold leaks**: near-duplicate neighbours of each
test epoch, and other epochs from the same subject, sit in the training set. On these
data that inflates the estimate to accuracy = {acc_rand:.3f} (kappa {kappa_rand:.3f}) --
about {acc_rand - acc_subj:.3f} higher than the subject-wise value. That inflated number
does **not** reflect how the stager would generalise to a new subject/night; the
subject-wise figures above do.
""")

print(f"OK: subject-wise acc={acc_subj:.4f} kappa={kappa_subj:.4f} | "
      f"random-kfold acc={acc_rand:.4f} kappa={kappa_rand:.4f} | "
      f"gap={acc_rand - acc_subj:.4f} | n_epochs={len(y)}")
