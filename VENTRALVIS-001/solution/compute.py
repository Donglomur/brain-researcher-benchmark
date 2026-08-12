"""Reference (oracle) for VENTRALVIS-001 — Haxby ventral-temporal object-category decoding.

Reproduces the textbook MVPA result — object category is decodable from the ventral-temporal
(VT) multivoxel pattern far above chance — then VOLUNTEERS the un-cued check the task never asks:
is the reported accuracy an artifact of the cross-validation SCHEME? It is. fMRI volumes are
temporally autocorrelated and acquired in blocked runs, so a random k-fold split places
near-duplicate adjacent volumes in both the train and test folds (temporal leakage), inflating
the accuracy. The valid estimate blocks the cross-validation BY RUN (leave-one-run-out, using the
Haxby `chunks`/run index) so no run ever appears in both train and test.

Defensible pipeline: VT-masked (`mask_vt`) BOLD -> standardize + detrend -> 8 categories (rest
excluded) -> linear SVM -> GROUP-BLOCKED leave-one-run-out CV (groups = `chunks`). The un-cued
comparison re-runs the identical classifier under a random (shuffled) 5-fold split.

Emitted for the verifier to CHECK the actual data (not just prose):
  decoding_accuracy.json — run-blocked 8-way accuracy, per-class accuracy, categories, chance,
                           n_samples, n_runs, the leaky random-k-fold reference, the inflation.
  cv_folds.json          — one record per leave-one-run-out fold: test_run, train_runs, sizes,
                           fold accuracy, and test_run_in_train (must be False for every fold) —
                           the structural proof that no run crosses train/test.
  run_metadata.json      — dataset, subject, mask, n_voxels, run index, classifier, CV, preproc.
  findings.md            — reproduces (decoding holds) + the CV-leakage check + the valid number.

Validated (nilearn-pinned Haxby, VT mask, 8 categories, 12 runs):
  8-way accuracy, leave-one-run-out (run-blocked) : ~0.63  (chance 0.125)   # valid
  8-way accuracy, random 5-fold                   : ~0.92                    # inflated by leakage
Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold, cross_val_score
from sklearn.svm import SVC

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
CATS = ["face", "house", "cat", "bottle", "scissors", "shoe", "chair", "scrambledpix"]


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "haxby2001"}, indent=2))
    (OUT / "decoding_accuracy.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn import datasets
    from nilearn.maskers import NiftiMasker
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    hax = datasets.fetch_haxby()
    lab = pd.read_csv(hax.session_target[0], sep=r"\s+")
except Exception as e:
    fail(f"could not resolve Haxby dataset: {e}")

if not {"labels", "chunks"}.issubset(lab.columns):
    fail(f"Haxby label table missing labels/chunks columns: {list(lab.columns)}")

y_all = lab["labels"].values
runs_all = lab["chunks"].values          # per-volume run index (the group key for run-blocking)
masker = NiftiMasker(mask_img=hax.mask_vt[0], standardize=True, detrend=True)
X_all = masker.fit_transform(hax.func[0])

sel = np.isin(y_all, CATS)
X, y, g = X_all[sel], y_all[sel], runs_all[sel].astype(int)
runs = sorted(int(r) for r in np.unique(g))
n_runs = len(runs)
if X.shape[0] < 100 or n_runs < 4:
    fail(f"unexpected Haxby shape: X={X.shape}, runs={n_runs}")

chance = 1.0 / len(CATS)

# ---- VALID: GROUP-BLOCKED leave-one-run-out CV (no run ever in both train and test) ----
# Manual LOGO so we can EMIT the fold structure (test_run / train_runs) the verifier checks.
logo = LeaveOneGroupOut()
y_pred = np.empty_like(y)
folds = []
for i, (tr, te) in enumerate(logo.split(X, y, g), 1):
    svc = SVC(kernel="linear", C=1.0)
    svc.fit(X[tr], y[tr])
    yp = svc.predict(X[te])
    y_pred[te] = yp
    test_runs = sorted(int(r) for r in np.unique(g[te]))
    train_runs = sorted(int(r) for r in np.unique(g[tr]))
    folds.append({
        "fold": i,
        "test_run": test_runs[0] if len(test_runs) == 1 else test_runs,
        "train_runs": train_runs,
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "fold_accuracy": float(np.mean(yp == y[te])),
        # the run held out for testing must NOT appear among the training runs
        "test_run_in_train": bool(set(test_runs) & set(train_runs)),
    })

acc_runblocked = float(np.mean(y_pred == y))
per_class = {c: float(np.mean(y_pred[y == c] == c)) for c in CATS}
all_blocked = all(not f["test_run_in_train"] for f in folds)
test_runs_union = sorted({f["test_run"] for f in folds})

# ---- the un-cued pitfall, VOLUNTEERED: random k-fold leaks autocorrelated within-run TRs ----
acc_randkfold = float(cross_val_score(
    SVC(kernel="linear", C=1.0), X, y,
    cv=StratifiedKFold(5, shuffle=True, random_state=0)).mean())
inflation = acc_randkfold - acc_runblocked

# ---- decoding_accuracy.json: the numbers the verifier grades ----
(OUT / "decoding_accuracy.json").write_text(json.dumps({
    "cv_scheme": "leave-one-run-out (run-blocked)",
    "n_classes": len(CATS),
    "categories": CATS,
    "chance": chance,
    "n_samples": int(X.shape[0]),
    "n_runs": n_runs,
    "accuracy_8way": acc_runblocked,                          # the VALID headline
    "per_class_accuracy": per_class,
    "leaky_random_kfold_accuracy_for_reference": acc_randkfold,   # inflated — NOT the result
    "inflation_random_minus_runblocked": inflation,
}, indent=2))

# ---- cv_folds.json: structural proof no run crosses train/test ----
(OUT / "cv_folds.json").write_text(json.dumps({
    "cv_scheme": "leave-one-run-out (run-blocked)",
    "group_key": "chunks (per-volume run index)",
    "n_folds": len(folds),
    "n_runs": n_runs,
    "runs": runs,
    "test_runs_union": test_runs_union,
    "no_run_crosses_train_test": bool(all_blocked),
    "folds": folds,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "haxby2001", "subject": "default (subj2)",
    "mask": "ventral-temporal (mask_vt)", "n_voxels": int(X_all.shape[1]),
    "n_runs": n_runs, "run_index": "Haxby chunks (per-volume run id)",
    "classifier": "linear SVM (C=1)",
    "cross_validation": "leave-one-run-out (run-blocked); groups=chunks; no run in both train and test",
    "preprocessing": "NiftiMasker standardize + detrend; 8 categories, rest excluded",
}, indent=2))

(OUT / "findings.md").write_text(f"""# VENTRALVIS-001 — object-category decoding in ventral temporal cortex

## Decoding reproduces
Object category is decodable from the ventral-temporal (VT) multivoxel pattern. With a linear SVM
and **run-blocked (leave-one-run-out)** cross-validation over the {n_runs} Haxby runs, the 8-way
accuracy is **{acc_runblocked:.3f}** (chance {chance:.3f}) — well above chance, reproducing Haxby
et al. (2001).

## The cross-validation scheme is decisive
Re-running the identical classifier under a **random (shuffled) k-fold** split reports
**{acc_randkfold:.3f}** — far higher (a **+{inflation:.3f}** inflation) — but that figure is
**inflated by temporal leakage**: fMRI volumes are temporally autocorrelated and acquired in
blocked runs, so a random split places near-duplicate adjacent volumes from the *same run* in both
the training and test folds. That does not measure generalisation to independent data. Blocking the
cross-validation by run (`chunks`) so that **no run ever appears in both train and test** removes
the leak; every one of the {len(folds)} folds holds out one entire run
(no_run_crosses_train_test = {str(all_blocked).lower()}).

## Conclusion
Category decodes from VT cortex at **~{acc_runblocked:.2f}** (8-way) under run-blocked
cross-validation; that is the valid estimate. An accuracy near **{acc_randkfold:.2f}** is the
signature of a cross-validation that was **not blocked by run** and is inflated by within-run
temporal leakage — it must not be reported as the decoding performance.
""")

print(f"OK: 8-way run-blocked acc={acc_runblocked:.3f} (chance {chance:.3f}); "
      f"random-kfold leaked acc={acc_randkfold:.3f} (+{inflation:.3f}); "
      f"n_runs={n_runs}; folds={len(folds)}; no_run_crosses={all_blocked}")
