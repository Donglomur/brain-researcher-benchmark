"""Grading checks for TIMEDECODE-001 (single-trial MEG modality decoding, MNE sample).

Ground truth (validated before release on the pinned pipeline -- MNE `sample`
gradiometers; -0.2..0.5 s epochs, baseline (None, 0), grad reject 4000e-13, decim=2;
each 0.05-0.45 s post-stimulus time sample of every trial is one example; StandardScaler
+ logistic regression; 5-fold cross-validation; auditory (ids 1,2) vs visual (ids 3,4)):

  folds grouped BY TRIAL (leakage-free)        accuracy = 0.666   <- correct
  ordinary random k-fold over pooled samples   accuracy = 0.791   <- inflated

  Each trial contributes many autocorrelated time samples that all share one modality
  label. Splitting the pooled (trial x time) samples with a random k-fold puts samples
  from the same trial in both train and test, so the model is scored on near-duplicates
  of trials it has seen and the accuracy is inflated. The honest estimate keeps every
  trial wholly on one side of the split (StratifiedGroupKFold / GroupKFold by trial).

  The trial-grouped accuracy is tightly clustered across reasonable un-pinned choices
  (StratifiedGroupKFold vs plain GroupKFold, fold count, logistic vs LDA, small window
  shifts): ~0.66-0.70. Every random-k-fold scheme is >= 0.77. The accept window below
  (0.615-0.725) passes any genuine trial-grouped estimate and fails the inflated
  random-k-fold value.
"""
import csv
import json
import os
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# Correct trial-grouped (leakage-free) accuracy on the pinned pipeline.
EXPECTED = 0.67
TOL = 0.055           # accept [0.615, 0.725]; excludes the random-k-fold value (>= 0.77)
NAIVE = 0.791        # random k-fold over pooled samples -- must NOT pass
CHANCE = 0.5


def _results():
    return json.loads((OUT / "decoding_results.json").read_text(encoding="utf-8"))


def _headline_accuracy(res):
    """The single cross-validated accuracy the submission reports."""
    if isinstance(res, dict):
        for k, v in res.items():
            if k.lower() == "accuracy" and isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        # fallback: any top-level float named like an accuracy that is not the
        # explicitly-labelled reference / random-k-fold / leaky one
        for k, v in res.items():
            kl = k.lower()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and "acc" in kl \
                    and "random" not in kl and "kfold" not in kl and "k_fold" not in kl \
                    and "leak" not in kl and "reference" not in kl and "chance" not in kl \
                    and "naive" not in kl:
                return float(v)
    return None


def test_decoding_computed():
    res = _results()
    assert int(res.get("n_classes", 0)) == 2 or len(res.get("classes", [])) == 2, \
        "must be a two-class (auditory vs visual) decoding problem"
    acc = _headline_accuracy(res)
    assert acc is not None and CHANCE < acc <= 1.0, \
        "accuracy missing, at/below chance, or out of range"
    # a per-fold breakdown consistent with a cross-validated decoding
    rows = list(csv.DictReader(open(OUT / "per_fold.csv", encoding="utf-8")))
    assert len(rows) >= 3, f"expected a per-fold CV breakdown (>=3 folds), got {len(rows)}"


def test_accuracy_is_leakage_free():
    # The honest (trial-grouped) accuracy is ~EXPECTED. Splitting the pooled (trial x
    # time) samples with an ordinary random k-fold leaks same-trial samples across the
    # split and inflates the accuracy to ~NAIVE, which fails.
    res = _results()
    acc = _headline_accuracy(res)
    assert acc is not None, "no accuracy reported in decoding_results.json"
    assert abs(acc - EXPECTED) < TOL, (
        f"reported cross-validated accuracy {acc:.3f} is not the leakage-free "
        f"(trial-grouped) value (~{EXPECTED:.3f} +/- {TOL:.3f}). Splitting the pooled "
        f"(trial x time) samples with an ordinary random k-fold puts samples from the "
        f"same trial in both train and test and inflates the accuracy to ~{NAIVE:.3f}; "
        f"that is not an honest estimate of decoding performance.")
