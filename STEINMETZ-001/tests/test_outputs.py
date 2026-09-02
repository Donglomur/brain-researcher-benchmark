"""Grading checks for STEINMETZ-001 (reproduce the upcoming-choice decoding accuracy).

Ground truth (validated before release on DANDI 000017, sub-Cori ses-20161214, dataset-
'included' left/right trials, all recorded units, 250 ms spike-count window, standardized
logistic regression, 5-fold CV):

  n_trials = 134, chance (majority) = 0.51
  CORRECT  strictly PRE-movement window (stim..+0.25 s) + BLOCKED CV : accuracy = 0.72
  NAIVE    PERI-movement window (response +/-0.1 s)      + RANDOM CV : accuracy = 0.95

Two off-critical-path errors both inflate the estimate: (1) a peri-movement window reads out
motor execution rather than the UPCOMING choice, and (2) random k-fold CV leaks between
temporally adjacent, correlated trials. The honest decoder -- a strictly pre-movement window
scored with blocked (contiguous) cross-validation -- reaches ~0.72, well above chance but far
below the ~0.95 a peri-movement + random-CV pipeline reports. The correct value is stable
across regularization (C 0.1..5 -> 0.72 +/- 0.01).

The failure mode this task targets (un-cued): the agent grabs a window around the response
(where "choice" is defined) and the default random k-fold, and reports ~0.95 -- decoding the
movement already underway, with leakage. Only a pre-movement, non-leaky estimate (~0.72)
reproduces the honest result. A reported ~0.95 fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.72     # honest pre-movement + blocked-CV accuracy
TOL = 0.06          # fails the naive ~0.95 by a wide margin; passes the pre-movement estimate
CHANCE = 0.515


def _results():
    return json.loads((OUT / "results.json").read_text(encoding="utf-8"))


def _as_fraction(v):
    """Accept an accuracy given either as a fraction (0..1) or a percentage (50..100)."""
    v = float(v)
    return v / 100.0 if v > 1.5 else v


def test_decoding_ran():
    res = _results()
    assert isinstance(res, dict)
    # a real decoding run: a plausible number of trials and units, and a stated chance level.
    def find(keypat, obj=res):
        for k, v in (obj.items() if isinstance(obj, dict) else []):
            if re.search(keypat, k, re.I) and isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        return None
    n_trials = find(r"n_?trials|num.*trial")
    n_units = find(r"n_?units|num.*unit|n_?neuron")
    assert n_trials is not None and 80 <= n_trials <= 214, f"n_trials implausible: {n_trials}"
    assert n_units is not None and n_units >= 200, f"n_units implausible: {n_units}"
    chance = find(r"chance|baseline")
    assert chance is not None and 0.45 <= _as_fraction(chance) <= 0.6, \
        f"chance level should be ~0.51 (near-balanced left/right): {chance}"


def test_reported_accuracy_reproduces_premovement_value():
    # Grade the HEADLINE reported accuracy. Prefer an explicitly named primary key; never take a
    # value the submission itself labelled as the peri-movement / motor / random-CV comparison.
    res = _results()
    primary = None
    for k, v in res.items():
        if not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            continue
        if re.search(r"peri|movement|motor|random|naive|inflat|contaminat", k, re.I):
            continue
        if re.search(r"accuracy|acc\b|decod|score", k, re.I) and re.search(r"cross|cv|valid|accuracy|decod", k, re.I):
            primary = _as_fraction(v)
            break
    if primary is None:  # fall back to any non-comparison accuracy-like key
        for k, v in res.items():
            if (isinstance(v, (int, float)) and not isinstance(v, bool)
                    and re.search(r"accuracy|decod", k, re.I)
                    and not re.search(r"peri|movement|motor|random|naive|std|chance", k, re.I)):
                primary = _as_fraction(v)
                break
    assert primary is not None, "results.json exposes no headline cross_validated_accuracy"
    assert abs(primary - EXPECTED) <= TOL, (
        f"reported decoding accuracy {primary:.3f} does not reproduce the honest upcoming-choice "
        f"value {EXPECTED:.2f} +/- {TOL:.2f}. A ~0.95 estimate comes from a peri-movement window "
        f"(motor execution, not upcoming choice) scored with leaky random cross-validation; the "
        f"pre-movement, blocked-CV accuracy is ~0.72.")


def test_findings_report_accuracy_above_chance_not_inflated():
    # Light honesty check: the write-up states an above-chance accuracy consistent with the honest
    # value, and does not headline the inflated ~0.95. Find a percentage/fraction in findings.md.
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"chance|above chance|baseline|0\.5|51%|50%", text), \
        "findings.md does not state the chance/baseline level"
    # the headline reported value must be reproduced somewhere in the prose too
    res = _results()
    primary = None
    for k, v in res.items():
        if (isinstance(v, (int, float)) and not isinstance(v, bool)
                and re.search(r"accuracy|decod", k, re.I)
                and not re.search(r"peri|movement|motor|random|naive|std|chance", k, re.I)):
            primary = _as_fraction(v)
            break
    assert primary is not None and abs(primary - EXPECTED) <= TOL, \
        "headline accuracy in results.json is not the honest pre-movement value"
