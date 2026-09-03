"""Grading checks for MOTORIMAGERY-001 (imagined hands-vs-feet CSP+LDA decoding, EEGBCI).

Ground truth (validated before release on the pinned set — subjects 1-10, runs 6/10/14;
band-pass 7-30 Hz; 1.0-2.0 s epochs; all EEG channels; CSP with 4 components + LDA;
per-subject 5-fold stratified CV; accuracy = mean over the 10 subjects):

  CSP refit WITHIN each fold (nested / leakage-free)  accuracy = 0.673   <- correct
  CSP fit ONCE on ALL epochs, then CV only the LDA    accuracy = 0.942   <- inflated

  The leakage-free accuracy is tightly clustered across reasonable but un-pinned choices
  (CV fold count and shuffle seed, 4-6 CSP components, mu-band lower edge 7-8 Hz):
  0.647-0.711. Every "CSP-fit-on-all" scheme is >= 0.918 (near ceiling). The accept
  window below (0.573-0.773) passes any genuine within-fold estimate and fails the
  inflated CSP-fit-on-all value.

CSP is a SUPERVISED spatial filter: it uses the class labels to build the channel
mixtures whose log-variance feeds the LDA. If it is fit once on the whole recording and
only the LDA is then cross-validated, the held-out epochs have already shaped the spatial
filters, so the features are contaminated and the accuracy is badly INFLATED. The honest
estimate refits CSP inside every fold on the training epochs only. Everything except the
placement of the CSP fit is pinned, so the reported number reveals which was done: the
within-fold value passes; the inflated CSP-fit-on-all value fails.
"""
import csv
import json
import os
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# Correct within-fold (nested) accuracy on the pinned set.
EXPECTED = 0.673
TOL = 0.10            # accept [0.573, 0.773]; excludes the inflated CSP-fit-on-all value (>= 0.918)
NAIVE = 0.942        # CSP fit on all epochs then CV the LDA -- must NOT pass
CHANCE = 0.5


def _results():
    return json.loads((OUT / "decoding_results.json").read_text(encoding="utf-8"))


def _headline_accuracy(res):
    """The single cross-validated accuracy the submission reports."""
    if isinstance(res, dict):
        for k, v in res.items():
            if k.lower() == "accuracy" and isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        # fallback: any top-level float field named like an accuracy that is not the
        # explicitly-labelled reference/leaky one
        for k, v in res.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and "acc" in k.lower() \
                    and "all" not in k.lower() and "leak" not in k.lower() \
                    and "reference" not in k.lower() and "chance" not in k.lower():
                return float(v)
    return None


def test_decoding_computed():
    res = _results()
    assert int(res.get("n_classes", 0)) == 2 or len(res.get("classes", [])) == 2, \
        "must be a two-class (hands vs feet) decoding problem"
    acc = _headline_accuracy(res)
    assert acc is not None and CHANCE < acc <= 1.0, \
        "accuracy missing, at/below chance, or out of range"
    # a per-subject breakdown consistent with the pinned 10-subject decoding
    rows = list(csv.DictReader(open(OUT / "per_subject.csv", encoding="utf-8")))
    assert len(rows) >= 10, f"expected one row per subject (>=10), got {len(rows)}"


def test_accuracy_is_leakage_free():
    # The honest (within-fold CSP) accuracy is ~EXPECTED. Fitting the CSP spatial filters
    # once on ALL epochs and cross-validating only the LDA leaks the held-out epochs into
    # the filters and inflates the accuracy to ~NAIVE (near ceiling), which fails.
    res = _results()
    acc = _headline_accuracy(res)
    assert acc is not None, "no accuracy reported in decoding_results.json"
    assert abs(acc - EXPECTED) < TOL, (
        f"reported cross-validated accuracy {acc:.3f} is not the leakage-free "
        f"(within-fold CSP) value (~{EXPECTED:.3f} +/- {TOL:.3f}). Fitting the CSP "
        f"spatial filters on all epochs before the split and cross-validating only the "
        f"LDA inflates the accuracy to ~{NAIVE:.3f} (near ceiling); that is not an "
        f"honest estimate of decoding performance.")
