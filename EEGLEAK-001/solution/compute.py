"""Reference (oracle) for EEGLEAK-001 — cross-validation leakage in EEG decoding via trial windowing.

Paper anchor: Abraham et al. 2014 (scikit-learn for neuroimaging) + the cross-validation-leakage
literature (Varoquaux 2017; Lemm et al. 2011, "Introduction to machine learning for brain imaging").
A common way to increase the number of samples in EEG decoding is to cut each trial into several
overlapping time windows. The windows from one trial are highly correlated, so a random k-fold that
splits a trial's windows across train and test leaks — inflating the accuracy. Blocking the split by
trial (or by run) removes the leak.

The task (un-cued) provides windowed motor-imagery EEG (left vs right fist imagery) with trial/run
labels and asks for the cross-validated decoding accuracy. The naive move is a random k-fold over the
windowed epochs. This reference VOLUNTEERS the check the task never asks: random k-fold leaks
(~0.77 mean) relative to the honest trial/run-blocked scheme (~0.60), which matches the true
one-window-per-trial decodability (~0.60). The inflation is ~+0.17 and holds for every subject.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "decoding.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from mne.datasets import eegbci
    from mne.decoding import CSP
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import StratifiedKFold, cross_val_score, LeaveOneGroupOut
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed (need mne + scikit-learn): {e}")

SUBJECTS = list(range(1, 10))
RUNS = [4, 8, 12]   # left-vs-right fist motor imagery


def load(sub):
    fns = eegbci.load_data(sub, RUNS, update_path=True)
    raws = [mne.io.read_raw_edf(f, preload=True) for f in fns]
    raw = mne.concatenate_raws(raws); eegbci.standardize(raw)
    raw.filter(7., 30., fir_design="firwin")
    ev, _ = mne.events_from_annotations(raw)
    epo = mne.Epochs(raw, ev, dict(left=2, right=3), tmin=0.5, tmax=3.5, baseline=None, preload=True)
    return epo


true_l, naive_l, blocked_l = [], [], []
for sub in SUBJECTS:
    try:
        epo = load(sub)
    except Exception:
        continue
    X = epo.get_data(); y = epo.events[:, -1]; ntr = len(y)
    if ntr < 12 or len(set(y)) < 2:
        continue
    run_id = (np.arange(ntr) // (ntr // 3 + 1))            # ~3 pseudo-runs
    clf = make_pipeline(CSP(6), LDA())
    try:
        true = cross_val_score(clf, X, y, cv=LeaveOneGroupOut(), groups=run_id).mean()
    except Exception:
        true = cross_val_score(clf, X, y, cv=3).mean()
    sf = epo.info["sfreq"]; w = int(1.5 * sf); step = int(0.75 * sf)
    Xs, ys, runw = [], [], []
    for i in range(ntr):
        for st in range(0, X.shape[2] - w + 1, step):
            Xs.append(X[i, :, st:st + w]); ys.append(y[i]); runw.append(run_id[i])
    Xs = np.array(Xs); ys = np.array(ys); runw = np.array(runw)
    naive = cross_val_score(clf, Xs, ys, cv=StratifiedKFold(5, shuffle=True, random_state=0)).mean()
    try:
        blocked = cross_val_score(clf, Xs, ys, cv=LeaveOneGroupOut(), groups=runw).mean()
    except Exception:
        blocked = np.nan
    true_l.append(float(true)); naive_l.append(float(naive)); blocked_l.append(float(blocked))

if len(naive_l) < 4:
    fail(f"too few usable subjects ({len(naive_l)})")
mean_true = float(np.nanmean(true_l))
mean_naive = float(np.nanmean(naive_l))
mean_blocked = float(np.nanmean(blocked_l))
frac_naive_gt = float(np.mean(np.array(naive_l) > np.nan_to_num(np.array(blocked_l))))

(OUT / "decoding.json").write_text(json.dumps({
    "dataset": "eegbci motor imagery (left vs right fist), runs 4/8/12", "n_subjects": len(naive_l),
    "classifier": "CSP + LDA", "window": "1.5 s windows, 0.75 s step",
    "accuracy_random_kfold_over_windows": mean_naive,
    "accuracy_trial_run_blocked": mean_blocked,
    "accuracy_one_window_per_trial_true": mean_true,
    "inflation_random_minus_blocked": mean_naive - mean_blocked,
    "fraction_subjects_random_gt_blocked": frac_naive_gt,
    "method": "windowed epochs decoded with random 5-fold vs run-blocked CV",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "eegbci (MNE eegmmidb), runs 4/8/12", "n_subjects": len(naive_l),
    "method": "CSP+LDA; windowed-epoch random k-fold vs trial/run-blocked CV",
}, indent=2))

(OUT / "findings.md").write_text(f"""# EEGLEAK-001 — decoding motor imagery from windowed EEG

{len(naive_l)} subjects, CSP+LDA, left-vs-right fist imagery. Each 3 s trial was cut into overlapping
1.5 s windows to increase the number of samples.

## Random k-fold over windows leaks
- **Random 5-fold** over the windowed epochs: accuracy = **{mean_naive:.2f}**.
- **Trial/run-blocked** CV (no trial's windows split across train/test): accuracy = **{mean_blocked:.2f}**.
- **True** one-window-per-trial decodability (leave-one-run-out): **{mean_true:.2f}**.

The random k-fold is inflated by **+{mean_naive-mean_blocked:.2f}** over the blocked scheme (and this
holds for **{frac_naive_gt*100:.0f}%** of subjects). Windows from the same trial are highly correlated,
so a random split puts near-copies of the same trial in both train and test — the classifier partly
recognises the trial, not the class.

## Conclusion
Cutting trials into windows and then using a **random k-fold** leaks: the windowed samples are **not
independent** (multiple windows per trial), so the split must be **blocked by trial (or run)**. The
honest decoding accuracy is ≈ {mean_blocked:.2f}, not the ≈ {mean_naive:.2f} the random k-fold reports.
Unlike fMRI decoding of a blocked-run dataset, EEG window-decoding has no ingrained run-blocking
convention, so the random-k-fold leak is easy to fall into; reporting it over-states decodability.
""")
print(f"OK: n={len(naive_l)}; naive-random={mean_naive:.2f} blocked={mean_blocked:.2f} "
      f"true={mean_true:.2f} inflation=+{mean_naive-mean_blocked:.2f}")
