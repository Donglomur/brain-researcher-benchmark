"""Grading checks for OUTCOMEPRED-001 (decode the UPCOMING trial outcome from population spiking).

Ground truth (validated before release on DANDI 000409, sub-NYU-37 ses-21d21fc3, balanced
rewarded/error trials, all recorded units, standardized logistic regression, stratified 5-fold CV):

  n_units = 867, n_trials(balanced) = 212, chance = 0.50
  CORRECT  strictly PRE-feedback window (feedback -0.20..-0.05 s) : accuracy ~ 0.5  (~chance) <-- reported
  NAIVE    feedback-spanning window (feedback 0.00..+0.40 s)      : accuracy ~ 0.99 (reads feedback)

The off-critical-path error this task targets (un-cued): the outcome (reward vs. error) is
physically delivered at feedback -- the reward, the consummatory licking, the error tone. A
spike-count window that extends across / after feedback therefore reads out the *already-revealed*
outcome almost perfectly (~0.99). That is not decoding the UPCOMING outcome; it is reading the
delivered feedback. Predicting the outcome from activity that ends before feedback is at chance:
balanced accuracy stays ~0.5 for any strictly pre-feedback window (0.43-0.57 across windows and
sessions), stable across regularization.

The failure mode: the agent windows around the feedback event (where "outcome" is defined),
reports ~0.99, and concludes the population predicts/encodes the trial outcome -- when it has
decoded feedback that already happened. Only a strictly pre-feedback estimate (~chance) honestly
answers how well the UPCOMING outcome can be decoded. A headline ~0.99 fails the check below --
exactly as a peri-movement window fails the sibling upcoming-choice task.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

CHANCE = 0.50
TOL = 0.15              # a headline must not beat the stated chance level by more than this

# keys that name a feedback-reading / post-outcome contrast rather than the upcoming-outcome result
_CONTROL_PAT = re.compile(r"post|after|reveal|feedback|reward|deliver|outcome_reveal|"
                          r"naive|inflat|contaminat|leak|control|error_?tone", re.I)
_ACC_PAT = re.compile(r"accuracy|acc\b|decod|score", re.I)
# spread/dispersion keys that are not the headline point estimate
_SPREAD_PAT = re.compile(r"_std|\bstd|stdev|std_?dev|\bsem\b|deviat|error|variance|\bvar\b|spread|ci_|confidence", re.I)


def _results():
    return json.loads((OUT / "results.json").read_text(encoding="utf-8"))


def _as_fraction(v):
    """Accept an accuracy given either as a fraction (0..1) or a percentage (50..100)."""
    v = float(v)
    return v / 100.0 if v > 1.5 else v


def _num_items(obj):
    """Yield (key, float) for every real number anywhere in a nested dict/list."""
    stack = [("", obj)]
    while stack:
        key, cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                stack.append((k, v))
        elif isinstance(cur, list):
            for v in cur:
                stack.append((key, v))
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            yield key, float(cur)


def _headline():
    """The reported upcoming-outcome accuracy: an accuracy-like value whose key does NOT name the
    feedback-reading / post-outcome comparison. Prefer a key that also reads as cross-validated."""
    res = _results()
    best = None
    for k, v in res.items():
        if not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            continue
        if _CONTROL_PAT.search(k) or _SPREAD_PAT.search(k) or not _ACC_PAT.search(k):
            continue
        f = _as_fraction(v)
        if re.search(r"\bcross|\bcv\b|valid|predict|upcoming", k, re.I):
            return f
        if best is None:
            best = f
    return best


def _reported_chance():
    for k, v in _results().items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and re.search(r"chance|baseline", k, re.I):
            return _as_fraction(v)
    return CHANCE


def test_decoding_ran():
    res = _results()
    n_trials = n_units = None
    for k, v in _num_items(res):
        if n_trials is None and re.search(r"n_?trials|num.*trial", k, re.I):
            n_trials = v
        if n_units is None and re.search(r"n_?units|num.*unit|n_?neuron", k, re.I):
            n_units = v
    assert n_trials is not None and 60 <= n_trials <= 560, f"n_trials implausible: {n_trials}"
    assert n_units is not None and n_units >= 200, f"n_units implausible: {n_units}"
    chance = _reported_chance()
    assert 0.45 <= chance <= 0.85, f"chance/baseline level implausible: {chance}"


def test_headline_upcoming_outcome_accuracy_is_not_above_chance():
    # The reported upcoming-outcome accuracy must not beat chance by more than TOL. The honest,
    # strictly pre-feedback estimate is ~chance (0.43-0.57). A window that spans feedback reports
    # ~0.99 -- that decodes the delivered outcome (reward/licking/error tone), not the upcoming
    # one, and must fail here (as a peri-movement window fails the upcoming-choice sibling task).
    primary = _headline()
    assert primary is not None, "results.json exposes no headline decoding accuracy"
    chance = _reported_chance()
    assert primary <= chance + TOL, (
        f"reported upcoming-outcome accuracy {primary:.3f} exceeds the stated chance level "
        f"{chance:.2f} by more than {TOL:.2f}. A ~0.99 estimate comes from a spike-count window "
        f"that includes the feedback period, so it decodes the already-delivered outcome "
        f"(reward/licking/error tone) rather than the upcoming one. The strictly pre-feedback "
        f"accuracy is ~chance.")
    assert primary >= chance - 0.25, (
        f"reported accuracy {primary:.3f} is implausibly far below chance {chance:.2f}")


def test_findings_state_outcome_near_chance():
    # Honesty: the write-up must characterise the upcoming-outcome result as at/near chance and
    # must not headline a near-perfect number as the decoding answer.
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"chance|baseline|0\.5|50%|not .*(predict|decod|above)|at chance", text), \
        "findings.md does not state the chance/baseline level or a near-chance result"
    primary = _headline()
    chance = _reported_chance()
    assert primary is not None and primary <= chance + TOL, \
        "headline decoding accuracy in results.json is not the honest near-chance value"
