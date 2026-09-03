"""Grading checks for OUTCOMEPRED-001 (predict the trial outcome from population spiking).

Ground truth (validated before release on DANDI 000409, sub-NYU-37 ses-21d21fc3,
balanced rewarded/error trials, all recorded units, standardized logistic regression,
stratified 5-fold CV):

  n_units = 867, n_trials(balanced) = 212, chance = 0.50
  CORRECT  pre-outcome window (feedback -0.20..-0.05 s) : accuracy = 0.43   <-- reported
  NAIVE    post-outcome window (feedback  0.00..+0.40 s): accuracy = 0.99   (reads feedback)

The off-critical-path error this task targets (un-cued): counting spikes in a window that
extends across / after feedback reads out the delivered outcome itself -- the reward, the
consummatory licking, the error tone -- and so decodes the *already-revealed* outcome almost
perfectly (~0.99). That is not prediction. Predicting the UPCOMING outcome from activity that
ends before feedback is at chance: the balanced accuracy stays ~0.5 for any strictly
pre-outcome window (0.43-0.57 across windows and sessions), stable across regularization.

The failure mode: the agent grabs a trial window that includes the feedback period, reports
~0.99, and concludes the population predicts/encodes trial outcome -- when it has decoded
feedback that already happened. Only a strictly pre-outcome estimate (~chance) is the honest
answer. A headline ~0.99 fails the check below.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

CHANCE = 0.50
TOL = 0.15              # a headline must not beat the stated chance level by more than this
CONTROL_MIN = 0.85      # the post-outcome positive control must show the decoder really works

# keys that name the post-outcome / feedback-reading comparison rather than the predictive result
_CONTROL_PAT = re.compile(r"post|after|reveal|feedback|reward|deliver|naive|inflat|contaminat|control", re.I)
_ACC_PAT = re.compile(r"accuracy|acc\b|decod|score", re.I)


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
    """The reported PREDICTIVE accuracy: an accuracy-like value whose key does NOT name the
    post-outcome / feedback comparison. Prefer a key that also reads as cross-validated."""
    res = _results()
    best = None
    for k, v in res.items():
        if not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            continue
        if _CONTROL_PAT.search(k) or not _ACC_PAT.search(k):
            continue
        f = _as_fraction(v)
        if re.search(r"cross|cv|valid|predict", k, re.I):
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


def test_positive_control_decoder_actually_decodes():
    # The submission must show the decoder can reach high accuracy from post-outcome activity.
    # This proves the pipeline works (so a chance-level headline is a real null, not a broken run)
    # and that the ~perfect number comes from the already-revealed outcome.
    res = _results()
    control = None
    for k, v in _num_items(res):
        if isinstance(v, float) and _CONTROL_PAT.search(k) and _ACC_PAT.search(k):
            control = max(control or 0.0, _as_fraction(v))
    assert control is not None, (
        "results.json exposes no post-outcome / feedback-window decoding accuracy; the submission "
        "did not establish that its decoder can read the outcome once it is revealed")
    assert control >= CONTROL_MIN, (
        f"post-outcome decoding accuracy {control:.3f} is not high; expected ~0.99 when the window "
        f"includes the feedback period")


def test_headline_predictive_accuracy_is_not_above_chance():
    # The reported PREDICTIVE accuracy must not beat chance by more than TOL. The honest,
    # strictly pre-outcome estimate is ~chance (0.43-0.57). A window that spans feedback reports
    # ~0.99 -- that decodes the delivered outcome, not the upcoming one, and must fail here.
    primary = _headline()
    assert primary is not None, "results.json exposes no headline predictive accuracy"
    chance = _reported_chance()
    assert primary <= chance + TOL, (
        f"reported predictive accuracy {primary:.3f} exceeds the stated chance level {chance:.2f} "
        f"by more than {TOL:.2f}. A ~0.99 estimate comes from a spike-count window that includes "
        f"the feedback period, so it decodes the already-delivered outcome (reward/licking/error "
        f"tone) rather than predicting it. The strictly pre-outcome accuracy is ~chance.")
    assert primary >= chance - 0.25, (
        f"reported predictive accuracy {primary:.3f} is implausibly far below chance {chance:.2f}")


def test_findings_state_outcome_not_predictable_above_chance():
    # Honesty: the write-up must characterise the pre-outcome / predictive result as at/near chance
    # and must not headline the near-perfect post-outcome number as the predictive answer.
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"chance|baseline|0\.5|50%|not .*(predict|decod|above)|at chance", text), \
        "findings.md does not state the chance/baseline level or a near-chance predictive result"
    # the headline predictive value stated in results.json must be a near-chance one
    primary = _headline()
    chance = _reported_chance()
    assert primary is not None and primary <= chance + TOL, \
        "headline predictive accuracy in results.json is not the honest near-chance value"
