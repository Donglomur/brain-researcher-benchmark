"""Reference solution for TIMEDECODE-001.

Decode the stimulus *modality* (auditory vs. visual) from single-trial MEG on the MNE
`sample` dataset, treating each post-stimulus time sample as one classification example,
and report the CROSS-VALIDATED decoding accuracy.

The one choice the brief leaves un-cued is HOW the cross-validation folds are formed.
Each trial contributes many (highly autocorrelated) time samples that all share the same
modality label. If the pooled (trial x time) samples are split with an ordinary random
k-fold, samples from the SAME trial land in both the training and the test fold, so the
classifier is scored partly on near-duplicates of trials it has already seen -> the
accuracy is INFLATED. The honest estimate keeps every trial wholly on one side of the
split (group the folds by trial: StratifiedGroupKFold / GroupKFold), so the held-out
samples come only from unseen trials.

Everything else is pinned (gradiometers, -0.2..0.5 s epochs, baseline (None, 0),
grad reject 4000e-13, decim=2, the 0.05-0.45 s post-stimulus analysis window,
StandardScaler + LogisticRegression, 5 folds), so only the fold grouping moves the
number: the trial-grouped (leakage-free) accuracy is materially LOWER than the random
k-fold value.
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

# Pinned analysis choices -----------------------------------------------------
TMIN, TMAX = -0.2, 0.5          # epoch window (s), cue at 0
WIN_LO, WIN_HI = 0.05, 0.45     # post-stimulus samples used as examples (s)
DECIM = 2
GRAD_REJECT = 4000e-13
N_SPLITS = 5
RANDOM_STATE = 42
CHANCE = 0.5
# event ids in the sample dataset: 1=aud/L 2=aud/R 3=vis/L 4=vis/R
EVENT_ID = dict(aud_l=1, aud_r=2, vis_l=3, vis_r=4)
AUDITORY, VISUAL = (1, 2), (3, 4)


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "mne.datasets.sample (audvis)"}, indent=2))
    (OUT / "decoding_results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import (StratifiedKFold, StratifiedGroupKFold,
                                         cross_val_score)
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")


def load_pooled_samples():
    """Return (X, y, groups): one row per (trial, post-stimulus time sample)."""
    data_path = mne.datasets.sample.data_path()
    raw_fname = os.path.join(str(data_path), "MEG", "sample",
                             "sample_audvis_filt-0-40_raw.fif")
    eve_fname = os.path.join(str(data_path), "MEG", "sample",
                             "sample_audvis_filt-0-40_raw-eve.fif")
    raw = mne.io.read_raw_fif(raw_fname, preload=True, verbose=False)
    events = mne.read_events(eve_fname)
    picks = mne.pick_types(raw.info, meg="grad", eeg=False, stim=False, eog=False,
                           exclude="bads")
    epochs = mne.Epochs(raw, events, EVENT_ID, TMIN, TMAX, proj=True, picks=picks,
                        baseline=(None, 0), preload=True,
                        reject=dict(grad=GRAD_REJECT), decim=DECIM, verbose=False)
    ids = epochs.events[:, -1]
    modality = np.where(np.isin(ids, AUDITORY), 0, 1)          # 0=auditory 1=visual
    tmask = (epochs.times >= WIN_LO) & (epochs.times <= WIN_HI)
    data = epochs.get_data(copy=False)[:, :, tmask]            # (n_trials, n_grad, n_t)
    n_trials, n_grad, n_t = data.shape
    X = data.transpose(0, 2, 1).reshape(n_trials * n_t, n_grad)
    y = np.repeat(modality, n_t)
    groups = np.repeat(np.arange(n_trials), n_t)               # trial index per sample
    return X, y, groups, n_trials, n_t


try:
    X, y, groups, n_trials, n_t = load_pooled_samples()
except Exception as e:
    fail(f"could not build pooled MEG samples from the sample dataset: {e}")

if n_trials < 50 or len(np.unique(y)) < 2:
    fail("insufficient trials / classes")

clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))

# ---- HONEST: keep whole trials on one side of the split (group by trial) ----
gkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
fold_rows = []
grouped_scores = []
for i, (tr, te) in enumerate(gkf.split(X, y, groups), start=1):
    clf.fit(X[tr], y[tr])
    acc = float(clf.score(X[te], y[te]))
    grouped_scores.append(acc)
    fold_rows.append(dict(fold=i, n_test_samples=int(len(te)),
                          n_test_trials=int(len(np.unique(groups[te]))),
                          accuracy=round(acc, 4)))
accuracy = float(np.mean(grouped_scores))

# ---- for the write-up: ordinary random k-fold over the pooled samples (leaky) ----
random_kfold_acc = float(cross_val_score(
    clf, X, y, cv=StratifiedKFold(n_splits=N_SPLITS, shuffle=True,
                                  random_state=RANDOM_STATE)).mean())

n_samples_total = int(len(y))

with open(OUT / "per_fold.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["fold", "n_test_samples", "n_test_trials",
                                      "accuracy"])
    w.writeheader()
    for r in fold_rows:
        w.writerow(r)

(OUT / "decoding_results.json").write_text(json.dumps({
    "cv_scheme": "5-fold cross-validation with folds grouped by trial (leakage-free)",
    "accuracy": accuracy,
    "n_trials": int(n_trials),
    "n_time_samples_per_trial": int(n_t),
    "n_samples_total": n_samples_total,
    "n_classes": 2,
    "classes": ["auditory", "visual"],
    "chance_level": CHANCE,
    "random_kfold_accuracy_for_reference": random_kfold_acc,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "mne.datasets.sample (sample_audvis_filt-0-40)",
    "contrast": "stimulus modality: auditory (L+R) vs visual (L+R)",
    "sensors": "gradiometers (all, exclude bads)",
    "epoch_sec": [TMIN, TMAX],
    "analysis_window_sec": [WIN_LO, WIN_HI],
    "decim": DECIM,
    "example_unit": "one post-stimulus time sample per trial",
    "decoder": "StandardScaler -> LogisticRegression(max_iter=1000)",
    "cv_scheme": "5-fold, folds grouped by trial (StratifiedGroupKFold)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# TIMEDECODE-001 - single-trial MEG decoding of stimulus modality (MNE sample)

Decoding auditory vs. visual stimulus modality from single-trial gradiometer MEG on the
MNE `sample` dataset. Each post-stimulus time sample ({WIN_LO:g}-{WIN_HI:g} s, decim
{DECIM}) of every trial is one example (StandardScaler + logistic regression); the pooled
samples are split with 5-fold cross-validation.

Because every trial contributes many autocorrelated time samples that share one modality
label, the folds must keep each trial wholly on one side of the split. Grouping the folds
by trial (leakage-free) gives:

* **accuracy = {accuracy:.3f}** (chance = {CHANCE:.2f}), {n_trials} trials,
  {n_samples_total} pooled samples.

If instead the pooled samples are shuffled into an ordinary random k-fold, samples from
the same trial fall on both sides of the split and the accuracy rises to about
**{random_kfold_acc:.3f}** -- roughly {random_kfold_acc - accuracy:.3f} above the
trial-grouped value. That inflated figure reflects recognising trials it has already
partly seen, not generalisation to unseen trials; the trial-grouped accuracy above is the
honest estimate.
""")

print(f"OK: grouped acc={accuracy:.4f} | random-kfold acc={random_kfold_acc:.4f} | "
      f"gap={random_kfold_acc - accuracy:.4f} | trials={n_trials} samples={n_samples_total}")
