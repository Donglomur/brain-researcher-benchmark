"""Reference (oracle) solution for DECODE-001 — Haxby VT object-category decoding.

The honest reference reports the RUN-BLOCKED (leave-one-run-out) cross-validated accuracy
and VOLUNTEERS what the task never asks: a random k-fold cross-validation inflates the
accuracy substantially, because fMRI volumes are temporally autocorrelated and acquired in
blocked runs, so a random split places near-duplicate adjacent volumes in both the training
and test folds (leakage). The valid accuracy is the run-blocked one (~0.63 for the 8-way
decoding, chance 0.125), NOT the inflated random-CV number (~0.92).

Validated (nilearn-pinned Haxby, VT mask, 8 categories, 12 runs):
  8-way accuracy, leave-one-run-out : ~0.63  (chance 0.125)   # valid
  8-way accuracy, random 5-fold     : ~0.92                    # inflated by leakage
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import (LeaveOneGroupOut, StratifiedKFold,
                                     cross_val_predict, cross_val_score)
from sklearn.metrics import accuracy_score
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

y_all = lab["labels"].values
runs = lab["chunks"].values
masker = NiftiMasker(mask_img=hax.mask_vt[0], standardize=True, detrend=True)
X_all = masker.fit_transform(hax.func[0])

sel = np.isin(y_all, CATS)
X, y, g = X_all[sel], y_all[sel], runs[sel]
n_runs = int(len(np.unique(g)))
if X.shape[0] < 100 or n_runs < 4:
    fail(f"unexpected Haxby shape: X={X.shape}, runs={n_runs}")

svc = SVC(kernel="linear", C=1.0)

# ---- HONEST: run-blocked leave-one-run-out cross-validation ----
y_pred = cross_val_predict(svc, X, y, groups=g, cv=LeaveOneGroupOut())
acc_runblocked = float(accuracy_score(y, y_pred))
per_class = {c: float(np.mean(y_pred[y == c] == c)) for c in CATS}

# ---- the un-cued pitfall, VOLUNTEERED: random k-fold leaks autocorrelated TRs ----
acc_randkfold = float(cross_val_score(
    svc, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0)).mean())

chance = 1.0 / len(CATS)
(OUT / "decoding_accuracy.json").write_text(json.dumps({
    "cv_scheme": "leave-one-run-out (run-blocked)",
    "n_classes": len(CATS), "chance": chance,
    "n_samples": int(X.shape[0]), "n_runs": n_runs,
    "accuracy_8way": acc_runblocked,
    "per_class_accuracy": per_class,
    "leaky_random_kfold_accuracy_for_reference": acc_randkfold,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "haxby2001", "subject": "default (subj2)",
    "mask": "ventral-temporal (mask_vt)", "n_voxels": int(X_all.shape[1]),
    "n_runs": n_runs, "classifier": "linear SVM (C=1)",
    "cross_validation": "leave-one-run-out (run-blocked)",
    "preprocessing": "NiftiMasker standardize + detrend; 8 categories, rest excluded",
}, indent=2))

(OUT / "findings.md").write_text(f"""# DECODE-001 — object-category decoding in ventral temporal cortex

## Decoding reproduces
Object category is decodable from the ventral-temporal (VT) multivoxel pattern. With a
linear SVM and **run-blocked (leave-one-run-out)** cross-validation, the 8-way accuracy is
**{acc_runblocked:.3f}** (chance {chance:.3f}) — well above chance, reproducing Haxby et al. (2001).

## The cross-validation scheme is decisive
A **random k-fold** cross-validation on these data reports **{acc_randkfold:.3f}** — far
higher — but that figure is **inflated by leakage**: fMRI volumes are temporally
autocorrelated and acquired in blocked runs, so a random split places near-duplicate adjacent
volumes in both the training and test folds. That does not reflect real generalisation across
independent data. The valid estimate is the **run-blocked {acc_runblocked:.3f}**; the
{acc_randkfold:.3f} figure must not be reported as the decoding performance.

## Conclusion
Category decodes from VT cortex at ~{acc_runblocked:.2f} (8-way) under run-blocked
cross-validation. Any accuracy near {acc_randkfold:.2f} indicates cross-validation that was
not blocked by run and is not a valid estimate of decoding.
""")
print(f"OK: 8-way run-blocked acc={acc_runblocked:.3f} (chance {chance:.3f}); "
      f"random-kfold leaked acc={acc_randkfold:.3f}")
