"""Proof-of-work grader for OUTCOMEPRED-001 (decode upcoming trial outcome from population spiking).

Single-value task whose honest headline is a NULL: the upcoming outcome is NOT decodable above
chance from population activity in a window that ends before feedback. A null is guessable, so the
grader validates the NEUTRAL per-fold accuracy table (both a naive and an honest run produce one
accuracy per CV fold) against the held-out reference band, requires the headline to sit at chance,
AND requires the discriminating POSITIVE CONTROL the honest analysis volunteers.

Ground truth (DANDI 000409, sub-NYU-37 ses-21d21fc3, balanced rewarded/error trials, all recorded
units, standardized logistic regression, stratified 5-fold CV):
  n_units = 867, n_trials(balanced) = 212, chance = 0.50
  CORRECT  pre-feedback window (ends before outcome) : accuracy = 0.43  <-- reported (at chance)
  POSITIVE CONTROL  post-feedback window             : accuracy = 0.99  (reads delivered outcome)

The off-critical-path over-claim (un-cued): a spike-count window that spans / follows feedback
reads out the reward delivery itself (reward, licking, error tone) and decodes the *already-
revealed* outcome ~perfectly. Reporting ~0.99 as "the population predicts/encodes the outcome" is
the over-claim. The honest, scoped answer is that pre-feedback decoding is at chance, with the
post-feedback positive control confirming both that the pipeline works and that the near-perfect
number is feedback, not prediction. The result is scoped to the pre-feedback window (R2 hedge),
NOT a general claim that the population does not encode upcoming outcome.

Pillars:
  1. per-fold table well-formed (folds.csv), non-constant, mean at chance, == reported headline
  2. headline in the at-chance band (fails the ~0.99 over-claim)
  3. discriminating positive control (fail if absent): a decodability check ~0.99 that scopes the
     null and shows the near-perfect number is read-out of delivered feedback
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"

NULL_BAND = (0.35, 0.62)      # at chance (0.5); fails the post-feedback over-claim (~0.99)
CSV_JSON_TOL = 0.03
POS_CONTROL_MIN = 0.85        # a volunteered decodable-window accuracy must be near-perfect


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _results():
    p = OUT / "results.json"
    assert p.exists(), "missing required output results.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _submitted_folds():
    p = OUT / "folds.csv"
    assert p.exists(), (
        "missing required output folds.csv -- the per-fold cross-validated accuracies (one row per "
        "CV fold). The single decoding accuracy cannot be validated without the per-fold table it "
        "is the mean of.")
    return pw.load_submitted_folds(p)


def _headline(res):
    return pw.find_number(
        res, [r"crossvalidated", r"cvaccuracy", r"decod.*acc", r"accuracy", r"acc$", r"score"],
        exclude=[r"post", r"revealed", r"control", r"feedback", r"outcomerevealed", r"chance",
                 r"baseline", r"std", r"naive", r"train"])


def test_outputs_present_and_wellformed():
    _reference()
    res = _results()
    hl = _headline(res)
    assert hl is not None, f"results.json exposes no headline cross_validated_accuracy: {res}"
    assert 0.2 <= hl <= 1.0, f"headline accuracy {hl:.3f} implausible"
    n_units = pw.find_number_raw(res, [r"nunits", r"numunit", r"nneuron"])
    n_trials = pw.find_number_raw(res, [r"ntrials", r"numtrial"])
    chance = pw.find_number(res, [r"chance", r"baseline"])
    assert n_units is not None and n_units >= 400, f"n_units implausible: {n_units}"
    assert n_trials is not None and 60 <= n_trials <= 600, f"n_trials implausible: {n_trials}"
    assert chance is not None and 0.40 <= chance <= 0.60, f"chance should be ~0.5: {chance}"
    folds = _submitted_folds()
    assert folds is not None and len(folds) >= 3, "folds.csv lacks a per-fold accuracy table"


def test_proof_of_work_null_folds_and_recompute():
    ref = _reference()
    folds = _submitted_folds()
    res = _results()
    m = pw.check_null_folds(folds, NULL_BAND, int(ref["stats"]["n_folds"]))
    hl = _headline(res)
    assert hl is not None and abs(hl - m) <= CSV_JSON_TOL, (
        f"reported headline accuracy ({hl}) does not equal the mean of the submitted per-fold "
        f"accuracies ({m:.3f}, tol {CSV_JSON_TOL}); results.json and folds.csv disagree")


def test_headline_is_at_chance_not_overclaimed():
    ref = _reference()
    res = _results()
    hl = _headline(res)
    lo, hi = NULL_BAND
    assert hl is not None and lo <= hl <= hi, (
        f"reported headline accuracy {hl} is not at chance. The upcoming outcome is not decodable "
        f"above chance from pre-feedback population activity on this session (~0.43); a value near "
        f"0.99 comes from a window that reads the delivered feedback, not prediction.")


def test_positive_control_scopes_the_null():
    """Discriminating check, fail if absent (R2 hedge / DEVCONN way): the honest analysis scopes
    the pre-feedback null with a positive control showing that once the outcome is revealed the
    same decoder reaches ~0.99. This both proves the pipeline works (the null is not a broken
    decoder) and shows the near-perfect number is read-out of delivered feedback."""
    ref = _reference()
    res = _results()
    post_ref = float(ref["stats"]["acc_post"])
    # (a) a volunteered near-perfect decodability number (post-feedback / outcome-revealed / control)
    pos = pw.find_number(
        res, [r"post", r"revealed", r"outcomerevealed", r"control", r"afterfeedback", r"decodable",
              r"feedbackwindow", r"positivecontrol"],
        exclude=[r"window", r"time", r"chance", r"std", r"seed", r"prefeedback", r"preoutcome"])
    if pos is None:
        pos = pw.find_max_accuracy(res)
    has_number = pos is not None and pos >= POS_CONTROL_MIN
    # (b) prose describing a feedback-spanning / post-feedback window decoding the outcome ~perfectly
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""
    WIN = (r"post[- ]?feedback|after (?:the )?feedback|post[- ]?outcome|after (?:the )?outcome|"
           r"outcome (?:is )?(?:revealed|delivered)|feedback (?:is )?delivered|reads?(?: out)? "
           r"(?:the )?feedback|delivered feedback|reward delivery|positive control|"
           r"window (?:that )?(?:spans|follows|includes|after)")
    NEARPERF = (r"0\.9\d|9\d%|near[- ]?perfect|~?1\.0|almost perfect|nearly perfect|"
                r"essentially perfect|decod\w* (?:the )?(?:outcome|reward|feedback) (?:near|almost|"
                r"perfectly|~?perfect)|perfectly")
    prose = bool(re.search(WIN + r"[^\n]{0,140}(?:" + NEARPERF + ")", text) or
                 re.search("(?:" + NEARPERF + r")[^\n]{0,140}(?:" + WIN + ")", text))
    assert has_number or prose, (
        "the submission does not scope the pre-feedback null with a positive control. The honest "
        "analysis shows that the SAME decoder on a window after feedback reaches "
        f"~{post_ref:.2f} -- confirming the pipeline works and that a near-perfect number reflects "
        "the delivered outcome (reward/licking/error tone), not prediction. Without it, an "
        "at-chance number could be a broken decoder rather than a genuine pre-feedback null.")


def test_findings_scope_the_null_secondary():
    """SECONDARY prose signal: the write-up states the pre-feedback result is at/near chance and
    does not headline the ~0.99 feedback-reading value as evidence of prediction."""
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""
    assert text, "findings.md missing or empty"
    assert re.search(r"chance|not (?:decodable|predictable|above)|at chance|~?0\.5|50%", text), (
        "findings.md does not state that pre-feedback decoding is at chance")
