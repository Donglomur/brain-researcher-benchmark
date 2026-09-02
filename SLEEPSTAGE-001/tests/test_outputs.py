"""Grading checks for SLEEPSTAGE-001 (5-class AASM sleep staging on Sleep-EDF).

Ground truth (validated before release on the pinned subject set [0,1,2,3,4,5],
recording 1; EEG Fpz-Cz + Pz-Oz; 30-s epochs; relative band-power features;
RandomForest(200, random_state=0)):

  SUBJECT-WISE (leave-one-subject-out)  accuracy = 0.775  (kappa 0.682)  <- correct
  RANDOM epoch-wise 5-fold              accuracy = 0.832  (kappa 0.763)  <- inflated

  Subject-wise accuracy is tightly clustered across reasonable pipeline choices (Welch
  segment length, relative vs log-absolute band power, 100-500 trees, class weighting):
  0.772-0.780. Every random epoch-wise scheme is >= 0.830. The accept window below
  (0.745-0.805) passes any genuine subject-wise estimate and fails the inflated
  random-k-fold value.

Consecutive 30-s epochs from one night are highly autocorrelated and share subject
identity, so a RANDOM epoch-wise k-fold leaks near-duplicate neighbours and subject
identity into the training set and INFLATES the accuracy. The honest estimate of how
well the stager generalises to a NEW subject/night is subject-wise (leave-one-subject-out)
cross-validation, which is materially lower. The instruction pins everything except the
cross-validation scheme, so the reported number reveals which scheme was used: the
subject-wise value passes; the inflated random-k-fold value fails.
"""
import csv
import json
import os
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# Correct subject-wise (leave-one-subject-out) accuracy on the pinned set.
EXPECTED = 0.775
TOL = 0.03            # accept [0.745, 0.805]; excludes the inflated random-k-fold value (>= 0.830)
NAIVE = 0.832        # random epoch-wise k-fold -- must NOT pass


def _results():
    return json.loads((OUT / "staging_results.json").read_text(encoding="utf-8"))


def _headline_accuracy(res):
    """The single cross-validated accuracy the submission reports."""
    if isinstance(res, dict):
        for k, v in res.items():
            if k.lower() == "accuracy" and isinstance(v, (int, float)):
                return float(v)
        # fallback: any top-level float field named like an accuracy that is not the
        # explicitly-labelled reference/leaky one
        for k, v in res.items():
            if isinstance(v, (int, float)) and "acc" in k.lower() \
                    and "random" not in k.lower() and "kfold" not in k.lower() \
                    and "reference" not in k.lower() and "leak" not in k.lower():
                return float(v)
    return None


def test_staging_computed():
    res = _results()
    assert int(res.get("n_classes", 0)) == 5 or len(res.get("classes", [])) == 5, \
        "must stage into the 5 AASM classes"
    acc = _headline_accuracy(res)
    kappa = res.get("cohen_kappa", res.get("kappa"))
    assert acc is not None and 0.0 <= acc <= 1.0, "accuracy missing or out of range"
    assert kappa is not None and -1.0 <= float(kappa) <= 1.0, "cohen_kappa missing or out of range"
    # a per-fold breakdown consistent with a real cross-validation over the pinned subjects
    rows = list(csv.DictReader(open(OUT / "per_fold.csv", encoding="utf-8")))
    assert len(rows) >= 5, f"expected a cross-validation with >=5 folds, got {len(rows)}"


def test_crossvalidated_accuracy_is_subjectwise():
    # The honest (subject-generalising) accuracy is ~EXPECTED. A random epoch-wise k-fold
    # leaks autocorrelated / same-subject epochs and inflates the accuracy to ~NAIVE, which
    # fails. Grade the reported headline accuracy.
    res = _results()
    acc = _headline_accuracy(res)
    assert acc is not None, "no accuracy reported in staging_results.json"
    assert abs(acc - EXPECTED) < TOL, (
        f"reported cross-validated accuracy {acc:.3f} is not the subject-generalising "
        f"(leave-one-subject-out) value (~{EXPECTED:.3f} +/- {TOL:.3f}). A random "
        f"epoch-wise k-fold leaks autocorrelated and same-subject epochs and inflates the "
        f"accuracy to ~{NAIVE:.3f}; that is not an honest estimate of staging performance.")
