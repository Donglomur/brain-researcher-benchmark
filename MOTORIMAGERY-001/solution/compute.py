"""Reference solution for MOTORIMAGERY-001.

Decode imagined movement (hands vs feet) from the mu/beta EEG of the PhysioNet EEGBCI
motor-imagery runs with CSP + LDA, per subject, and report the CROSS-VALIDATED decoding
accuracy averaged over a pinned set of subjects.

The one choice the brief leaves un-cued is WHERE the CSP spatial filters are fit relative
to the train/test split. CSP is a supervised, data-driven spatial filter: it uses the
class labels to find channel mixtures that maximise the variance ratio between the two
classes. If it is fit ONCE on the whole recording and only the LDA is then
cross-validated, the test epochs have already shaped the spatial filters -> the features
are contaminated and the accuracy is badly INFLATED (here to near-ceiling). The honest
estimate refits CSP INSIDE every cross-validation fold, on the training epochs only
(a scikit-learn Pipeline of CSP -> LDA does exactly this).

Everything else is pinned (subjects, runs, band-pass, epoch window, all EEG channels,
4 CSP components, LDA, 5-fold stratified CV), so only the CSP-fit placement moves the
number. Validated on the pinned subjects (see findings.md): the within-fold (nested)
accuracy is materially LOWER than the CSP-fit-on-all value.
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

SUBJECTS = list(range(1, 11))     # PINNED fixed subject set
RUNS = [6, 10, 14]                # imagined hands (both fists) vs feet (both feet)
FMIN, FMAX = 7.0, 30.0            # mu/beta band
TMIN, TMAX = 1.0, 2.0            # sustained-imagery window, s relative to cue
N_COMPONENTS = 4
N_SPLITS = 5
CHANCE = 0.5


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "eegbci (PhysioNet EEG Motor Movement/Imagery)"}, indent=2))
    (OUT / "decoding_results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import mne
    from mne.datasets import eegbci
    from mne.decoding import CSP
    from sklearn.pipeline import Pipeline
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.metrics import accuracy_score, cohen_kappa_score
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")


def subject_epochs(subj):
    """Band-passed hands-vs-feet epochs (all EEG channels) for one subject."""
    fnames = eegbci.load_data(subjects=[subj], runs=RUNS, verbose=False)
    raws = [mne.io.read_raw_edf(f, preload=True, verbose=False) for f in fnames]
    raw = mne.concatenate_raws(raws, verbose=False)
    eegbci.standardize(raw)                       # canonical 10-05 channel names
    raw.set_montage(mne.channels.make_standard_montage("standard_1005"), verbose=False)
    raw.filter(FMIN, FMAX, fir_design="firwin", skip_by_annotation="edge", verbose=False)
    # T1 = both fists (hands), T2 = both feet (feet); T0 (rest) is ignored
    events, _ = mne.events_from_annotations(raw, event_id=dict(T1=2, T2=3), verbose=False)
    picks = mne.pick_types(raw.info, eeg=True, exclude="bads")
    ep = mne.Epochs(raw, events, dict(hands=2, feet=3), TMIN, TMAX, proj=True,
                    picks=picks, baseline=None, preload=True, verbose=False)
    return ep.get_data(copy=False), ep.events[:, -1]


def csp_lda():
    return Pipeline([
        ("csp", CSP(n_components=N_COMPONENTS, reg=None, log=True, norm_trace=False)),
        ("lda", LinearDiscriminantAnalysis()),
    ])


try:
    data = {s: subject_epochs(s) for s in SUBJECTS}
except Exception as e:
    fail(f"could not build motor-imagery epochs from EEGBCI: {e}")

if any(len(y) < 20 or len(np.unique(y)) < 2 for _, y in data.values()):
    fail("insufficient epochs / classes in at least one subject")

rows = []
acc_nested, kappa_nested, acc_leaky = [], [], []
for s in SUBJECTS:
    X, y = data[s]
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)

    # ---- HONEST: CSP refit inside every fold (nested) ----
    yt, yp = [], []
    for tr, te in cv.split(X, y):
        clf = csp_lda().fit(X[tr], y[tr])
        yt.append(y[te]); yp.append(clf.predict(X[te]))
    yt = np.concatenate(yt); yp = np.concatenate(yp)
    a = float(accuracy_score(yt, yp)); k = float(cohen_kappa_score(yt, yp))
    acc_nested.append(a); kappa_nested.append(k)
    rows.append(dict(subject=s, n_epochs=int(len(y)), accuracy=round(a, 4), kappa=round(k, 4)))

    # ---- for the write-up: CSP fit on ALL epochs, then CV only the LDA (leaky) ----
    csp_all = CSP(n_components=N_COMPONENTS, reg=None, log=True, norm_trace=False)
    Xf = csp_all.fit_transform(X, y)
    acc_leaky.append(float(cross_val_score(
        LinearDiscriminantAnalysis(), Xf, y,
        cv=StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42),
        scoring="accuracy").mean()))

acc = float(np.mean(acc_nested))
kappa = float(np.mean(kappa_nested))
acc_leaky_mean = float(np.mean(acc_leaky))
n_epochs_total = int(sum(len(y) for _, y in data.values()))

with open(OUT / "per_subject.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["subject", "n_epochs", "accuracy", "kappa"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

(OUT / "decoding_results.json").write_text(json.dumps({
    "cv_scheme": "per-subject 5-fold stratified CV, CSP refit within each fold (nested)",
    "accuracy": acc,
    "cohen_kappa": kappa,
    "n_subjects": len(SUBJECTS),
    "n_epochs_total": n_epochs_total,
    "n_classes": 2,
    "classes": ["hands", "feet"],
    "chance_level": CHANCE,
    "csp_fit_on_all_accuracy_for_reference": acc_leaky_mean,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "eegbci (PhysioNet EEG Motor Movement/Imagery Dataset)",
    "subjects": SUBJECTS,
    "runs": RUNS,
    "contrast": "imagined hands (both fists) vs feet (both feet)",
    "band_hz": [FMIN, FMAX],
    "epoch_sec": [TMIN, TMAX],
    "channels": "all EEG channels",
    "decoder": f"CSP(n_components={N_COMPONENTS}) -> LinearDiscriminantAnalysis",
    "cv_scheme": "per-subject 5-fold stratified CV with CSP refit within each fold (nested)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# MOTORIMAGERY-001 - imagined hands-vs-feet CSP+LDA decoding (EEGBCI)

On the pinned EEGBCI motor-imagery set (subjects {SUBJECTS}, runs {RUNS}; band-pass
{FMIN:g}-{FMAX:g} Hz; {TMIN:g}-{TMAX:g} s epochs; all EEG channels; CSP with
{N_COMPONENTS} components + LDA), the **honest, leakage-free** decoding accuracy --
per-subject 5-fold cross-validation with the **CSP spatial filters refit inside every
fold** -- is:

* **accuracy = {acc:.3f}** (Cohen kappa = {kappa:.3f}), chance = {CHANCE:.2f}

averaged over the {len(SUBJECTS)} subjects ({n_epochs_total} epochs total).

## Why CSP must be fit inside the CV fold
CSP is a supervised spatial filter that uses the class labels to build channel mixtures.
If it is fit **once on the whole recording** and only the LDA is then cross-validated,
the held-out epochs have already shaped the spatial filters, so the features are
contaminated and the accuracy is inflated to about **{acc_leaky_mean:.3f}** --
near ceiling, roughly {acc_leaky_mean - acc:.3f} above the nested value. That inflated
figure does **not** reflect how the decoder would generalise to unseen trials; the
within-fold (nested) accuracy above does.
""")

print(f"OK: nested acc={acc:.4f} kappa={kappa:.4f} | csp-on-all acc={acc_leaky_mean:.4f} | "
      f"gap={acc_leaky_mean - acc:.4f} | n_epochs={n_epochs_total}")
