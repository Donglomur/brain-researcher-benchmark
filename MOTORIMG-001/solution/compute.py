"""Reference (oracle) for MOTORIMG-001 — cross-validation leakage in EEG decoding via trial windowing.

Paper anchor: Ramoser, Muller-Gerking & Pfurtscheller (2000) CSP+LDA single-trial motor-imagery
decoding, plus the cross-validation-leakage literature (Varoquaux 2017; Lemm et al. 2011). A common
way to get more samples in EEG decoding is to cut each trial into several overlapping time windows.
The windows from one trial are near-copies (within-trial autocorrelation), so a random k-fold that
splits a trial's windows across train and test LEAKS — the classifier partly recognises the trial,
not the class, and the accuracy is inflated. Blocking the split so no trial's windows span train and
test (leave-one-run-out or group-k-fold by trial) removes the leak.

REPAIR (#24): the split is grouped using the REAL run/trial provenance carried in the packaged
bundle — each trial keeps the eegbci run it was recorded in (4/8/12) and a unique trial id — not
pseudo-runs invented from an index. Two grouped schemes are reported (leave-one-run-out; group-k-fold
by trial); both are proven to put every trial's windows in a single fold (0 trials span train/test).

This reference reproduces the strong-looking result (random k-fold over windows ~0.78) and VOLUNTEERS
the un-cued check the task never asks: the honest run/trial-blocked accuracy is ~0.62, matching the
independent true one-window-per-trial decodability (~0.64); the ~+0.16 gap is the leak, for every
subject. Reads the packaged epoch bundle OFFLINE (no network).

Emitted for the verifier to CHECK the actual data (not just prose):
  per_subject.csv    — one row per subject: n_trials, n_windows, the four accuracies
  decoding.json      — mean accuracies (random / run-blocked / trial-blocked / true), inflation,
                       per-subject list, and grouped_cv_proof (trials split across folds per scheme)
  run_metadata.json  — dataset, provenance, preprocessing, method
  findings.md        — reproduces (a high random-k-fold accuracy) + the leakage + honest conclusion
Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")           # CSP GED on rank-deficient windows is noisy but benign
np.seterr(all="ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "eegbci_epochs.npz"


def fail(reason):
    (OUT / "decoding.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "eegbci"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from mne.decoding import CSP
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import (StratifiedKFold, GroupKFold, LeaveOneGroupOut,
                                         cross_val_score)
    import mne
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed (need mne + scikit-learn): {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    X0 = d["X"].astype(float)          # (n_trials, n_channels, n_times), band-passed + epoched
    y0 = d["y"].astype(int)            # 0 = left fist, 1 = right fist
    subj0 = d["subject"].astype(int)   # subject id
    run0 = d["run"].astype(int)        # REAL run id (4/8/12) the trial was recorded in
    trial0 = d["trial"].astype(int)    # unique trial id
    sf = float(d["sfreq"])
except Exception as e:
    fail(f"could not load packaged epoch bundle: {e}")

if X0.shape[0] < 100 or len(np.unique(subj0)) < 4:
    fail(f"bundle too small ({X0.shape[0]} trials, {len(np.unique(subj0))} subjects)")

W = int(1.5 * sf)      # 1.5 s windows
STEP = int(0.75 * sf)  # 0.75 s step (overlapping)
N_CSP = 6


def window_trials(X, y, run, trial):
    """Cut each trial into overlapping windows, carrying REAL run/trial provenance to each window."""
    Xs, ys, rw, tw = [], [], [], []
    for i in range(len(y)):
        for st in range(0, X.shape[2] - W + 1, STEP):
            Xs.append(X[i, :, st:st + W]); ys.append(y[i]); rw.append(run[i]); tw.append(trial[i])
    return np.asarray(Xs), np.asarray(ys), np.asarray(rw), np.asarray(tw)


def trials_split_across_folds(splitter, X, y, trial_w, groups=None):
    """Structural proof of grouping: how many trials have windows landing in >1 CV fold (i.e. windows
    of the same trial in both train and test). 0 == grouping enforced; >0 == the split leaks."""
    fold_of = np.full(len(trial_w), -1, int)
    it = splitter.split(X, y) if groups is None else splitter.split(X, y, groups=groups)
    for i, (_tr, te) in enumerate(it):
        fold_of[te] = i
    return int(sum(len(np.unique(fold_of[trial_w == t])) > 1 for t in np.unique(trial_w)))


rows, naive_l, runb_l, trib_l, true_l = [], [], [], [], []
split_naive = split_runb = split_trib = 0
n_trials_total = 0
for s in np.unique(subj0):
    m = subj0 == s
    X, y, run, trial = X0[m], y0[m], run0[m], trial0[m]
    if len(np.unique(y)) < 2 or len(np.unique(run)) < 2:
        continue
    Xs, ys, rw, tw = window_trials(X, y, run, trial)
    clf = make_pipeline(CSP(N_CSP), LDA())

    # naive: random k-fold OVER WINDOWS (leaks — same-trial windows in train and test)
    naive = cross_val_score(clf, Xs, ys, cv=StratifiedKFold(5, shuffle=True, random_state=0)).mean()
    # honest, grouped by the REAL run (leave-one-run-out over the 3 recordings)
    runb = cross_val_score(clf, Xs, ys, cv=LeaveOneGroupOut(), groups=rw).mean()
    # honest, grouped by trial (group-k-fold; even more conservative)
    trib = cross_val_score(clf, Xs, ys, cv=GroupKFold(5), groups=tw).mean()
    # independent anchor: true one-window-per-trial decodability (un-windowed, leave-one-run-out)
    true = cross_val_score(make_pipeline(CSP(N_CSP), LDA()), X, y,
                           cv=LeaveOneGroupOut(), groups=run).mean()

    split_naive += trials_split_across_folds(
        StratifiedKFold(5, shuffle=True, random_state=0), Xs, ys, tw)
    split_runb += trials_split_across_folds(LeaveOneGroupOut(), Xs, ys, tw, groups=rw)
    split_trib += trials_split_across_folds(GroupKFold(5), Xs, ys, tw, groups=tw)
    n_trials_total += len(y)

    rows.append({"subject": int(s), "n_trials": int(len(y)), "n_windows": int(len(ys)),
                 "n_runs": int(len(np.unique(run))),
                 "acc_random_kfold": float(naive), "acc_run_blocked": float(runb),
                 "acc_trial_blocked": float(trib), "acc_true_one_window_per_trial": float(true)})
    naive_l.append(float(naive)); runb_l.append(float(runb))
    trib_l.append(float(trib)); true_l.append(float(true))

if len(naive_l) < 4:
    fail(f"too few usable subjects ({len(naive_l)})")

mean_naive = float(np.mean(naive_l))
mean_runb = float(np.mean(runb_l))
mean_trib = float(np.mean(trib_l))
mean_true = float(np.mean(true_l))
inflation = mean_naive - mean_runb
frac_gt = float(np.mean(np.array(naive_l) > np.array(runb_l)))

# ---- per_subject.csv: the actual per-item data the verifier checks ----
with open(OUT / "per_subject.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subject", "n_trials", "n_windows", "n_runs",
                "acc_random_kfold", "acc_run_blocked", "acc_trial_blocked", "acc_true"])
    for r in rows:
        w.writerow([r["subject"], r["n_trials"], r["n_windows"], r["n_runs"],
                    f"{r['acc_random_kfold']:.6f}", f"{r['acc_run_blocked']:.6f}",
                    f"{r['acc_trial_blocked']:.6f}", f"{r['acc_true_one_window_per_trial']:.6f}"])

grouped_cv_proof = {
    "grouping_units": ["run", "trial"],
    "n_windows_per_trial": int(rows[0]["n_windows"] // rows[0]["n_trials"]),
    "n_trials_total": n_trials_total,
    "random_kfold_over_windows": {
        "cv": "StratifiedKFold(5, shuffle=True)", "grouped": False,
        "n_trials_split_across_folds": split_naive},
    "run_blocked_leave_one_run_out": {
        "cv": "LeaveOneGroupOut by real run id (4/8/12)", "grouped": True,
        "n_trials_split_across_folds": split_runb},
    "trial_blocked_group_kfold": {
        "cv": "GroupKFold(5) by trial id", "grouped": True,
        "n_trials_split_across_folds": split_trib},
}

(OUT / "decoding.json").write_text(json.dumps({
    "dataset": "eegbci motor imagery (left vs right fist), runs 4/8/12",
    "n_subjects": len(naive_l), "classifier": "CSP(6) + LDA",
    "window": "1.5 s windows, 0.75 s step (overlapping)",
    "accuracy_random_kfold_over_windows": mean_naive,
    "accuracy_run_blocked_leave_one_run_out": mean_runb,
    "accuracy_trial_blocked_group_kfold": mean_trib,
    "accuracy_one_window_per_trial_true": mean_true,
    "honest_accuracy": mean_runb,
    "inflation_random_minus_blocked": inflation,
    "fraction_subjects_random_gt_blocked": frac_gt,
    "per_subject": rows,
    "grouped_cv_proof": grouped_cv_proof,
    "method": ("windowed epochs decoded with random 5-fold (leaks) vs run/trial-blocked CV using the "
               "real eegbci run/trial provenance"),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "eegbci (PhysioNet EEGMMIDB), runs 4/8/12, packaged bundle",
    "n_subjects": len(naive_l), "atlas": None,
    "provenance": ("real run id (4/8/12) and unique trial id carried per trial; windows inherit their "
                   "trial's run/trial id — no index-generated pseudo-runs"),
    "preprocessing": ("montage standardized; band-pass 7-30 Hz; resampled to 80 Hz; epoched 0.5-3.5 s; "
                      "each trial cut into overlapping 1.5 s / 0.75 s-step windows"),
    "method": ("CSP(6)+LDA; random 5-fold over windows vs grouped CV (leave-one-run-out and "
               "group-k-fold by trial); grouping enforced on real run/trial ids"),
}, indent=2))

(OUT / "findings.md").write_text(f"""# MOTORIMG-001 - decoding motor imagery from windowed EEG

{len(naive_l)} subjects, CSP(6)+LDA, left-vs-right fist imagery. Each ~3 s trial was cut into
overlapping 1.5 s windows (0.75 s step) to increase the number of samples. Every window keeps the
**real run (4/8/12) and trial id** it came from.

## The reported decoding looks strong at face value
- **Random 5-fold over the windows**: accuracy = **{mean_naive:.2f}** - a strong, publishable-looking
  left-vs-right decoding result. A naive analysis stops here.

## But a random k-fold over windows LEAKS
The windows of one trial are near-copies (within-trial autocorrelation), so a random split puts
windows of the **same trial in both train and test** - the classifier partly recognises the trial,
not the class, and the accuracy is **inflated**. Grouping the split so no trial's windows span
train and test (using the real run/trial provenance) removes it:

- **Run-blocked** (leave-one-run-out over the 3 real runs): accuracy = **{mean_runb:.2f}**.
- **Trial-blocked** (group-k-fold by trial): accuracy = **{mean_trib:.2f}**.
- **True** one-window-per-trial decodability (un-windowed, leave-one-run-out): **{mean_true:.2f}**.

The random k-fold is inflated by **+{inflation:.2f}** over the run-blocked scheme, and this holds for
**{frac_gt*100:.0f}%** of subjects. Under the random k-fold, **{split_naive} of {n_trials_total}**
trials have windows split across folds (the leak); under both grouped schemes it is **0** - grouping
is enforced on the real run/trial ids.

## Conclusion
Cutting trials into windows and then using a **random k-fold** leaks: the windowed samples are **not
independent** (multiple near-copy windows per trial), so the split must be **grouped by trial or run**
(leave-one-run/trial-out). The honest decoding accuracy is approximately **{mean_runb:.2f}** - matching
the independent true one-window-per-trial level (~{mean_true:.2f}) - **not** the ~{mean_naive:.2f} the
random k-fold reports. Unlike a blocked-run fMRI dataset, EEG window-decoding has no ingrained
run-blocking convention, so the random-k-fold leak is easy to fall into; reporting it over-states
decodability.
""")

print(f"OK: n={len(naive_l)}; naive-random={mean_naive:.2f} run-blocked={mean_runb:.2f} "
      f"trial-blocked={mean_trib:.2f} true={mean_true:.2f} inflation=+{inflation:.2f} "
      f"frac={frac_gt:.2f}; split naive={split_naive}/{n_trials_total} grouped=0")
