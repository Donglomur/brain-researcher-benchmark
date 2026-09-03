"""Grading checks for AASMSTAGE-001 (5-class AASM sleep staging on Sleep-EDF).

Ground truth (validated before release on the pinned set -- subjects [0,1,2,3,4,5],
recording 1; single-EEG relative band-power features; RandomForest(200, random_state=42);
leave-one-subject-out CV over the 30-s epochs):

  stage-fair BALANCED accuracy (mean per-stage recall)   accuracy = 0.661   <- correct
  OVERALL accuracy (fraction of all epochs correct)      accuracy = 0.765   <- inflated

  The five AASM stages are very unequal (N2 ~46% of epochs, N1 ~9%). Overall accuracy is
  dominated by the common stages -- its majority baseline is ~0.46, NOT the 0.20 (1/5)
  chance level of a five-way problem -- so it overstates how well the stages are actually
  identified and hides that the rarest stage (N1) is barely recovered (recall ~0.23). The
  stage-fair figure is the mean of the five per-stage recalls (balanced accuracy), whose
  chance level IS 0.20.

  The stage-fair (balanced) accuracy is tightly clustered across reasonable pipeline
  choices (RandomForest 100-200 trees / seed, logistic regression, SVM): 0.640-0.663.
  Every overall-accuracy value is >= 0.73. The accept window below (0.610-0.710) passes any
  genuine stage-fair estimate and fails the inflated overall-accuracy value.
"""
import csv
import json
import os
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# Correct stage-fair (balanced) accuracy on the pinned set.
EXPECTED = 0.66
TOL = 0.05            # accept [0.610, 0.710]; excludes the inflated overall-accuracy value (>= 0.73)
NAIVE = 0.765        # overall accuracy (fraction of epochs correct) -- must NOT pass
CHANCE = 0.20


def _results():
    return json.loads((OUT / "staging_results.json").read_text(encoding="utf-8"))


def _headline_accuracy(res):
    """The single cross-validated accuracy the submission reports."""
    if isinstance(res, dict):
        for k, v in res.items():
            if k.lower() == "accuracy" and isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        # fallback: any top-level float named like an accuracy that is not the
        # explicitly-labelled overall / reference / chance one
        for k, v in res.items():
            kl = k.lower()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and "acc" in kl \
                    and "overall" not in kl and "reference" not in kl \
                    and "chance" not in kl and "naive" not in kl:
                return float(v)
    return None


def test_staging_computed():
    res = _results()
    assert int(res.get("n_stages", 0)) == 5 or len(res.get("stages", [])) == 5, \
        "must be a five-class (W/N1/N2/N3/REM) staging problem"
    acc = _headline_accuracy(res)
    assert acc is not None and CHANCE < acc <= 1.0, \
        "accuracy missing, at/below chance, or out of range"
    # a per-stage breakdown covering the five stages
    rows = list(csv.DictReader(open(OUT / "per_stage.csv", encoding="utf-8")))
    assert len(rows) >= 5, f"expected one row per stage (>=5), got {len(rows)}"


def test_accuracy_is_stage_fair():
    # The stage-fair (balanced) accuracy is ~EXPECTED. The overall accuracy -- the
    # fraction of all epochs correct -- is inflated by the dominant stages to ~NAIVE and
    # is not the accuracy of identifying the five stages against a 0.20 chance level.
    res = _results()
    acc = _headline_accuracy(res)
    assert acc is not None, "no accuracy reported in staging_results.json"
    assert abs(acc - EXPECTED) < TOL, (
        f"reported cross-validated accuracy {acc:.3f} is not the stage-fair (balanced) "
        f"value (~{EXPECTED:.3f} +/- {TOL:.3f}). On this heavily imbalanced cohort the "
        f"overall accuracy (fraction of epochs correct) is inflated by the dominant "
        f"stages to ~{NAIVE:.3f} (majority baseline ~0.46, not the 0.20 chance level); "
        f"that is not an honest summary of how well the five stages are identified.")
