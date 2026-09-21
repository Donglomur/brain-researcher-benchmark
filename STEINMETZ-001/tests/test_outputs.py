"""Proof-of-work grader for STEINMETZ-001 (decode the mouse's upcoming left/right choice).

Single-value reproduction task: the deliverable is one cross-validated decoding accuracy. A lone
scalar is guessable, so the grader also validates the finest NEUTRAL intermediate the analysis
produces -- the per-fold cross-validated accuracies -- against a held-out reference
(tests/reference.npz, built from the oracle run, never shipped to the agent), recomputes the
headline FROM the submitted folds, and requires the headline to land in the honest band that only
a strictly pre-movement, non-leaky decoder reaches.

Ground truth (DANDI 000017, sub-Cori ses-20161214, dataset-'included' left/right trials, all
recorded units, 250 ms per-unit spike-count window, standardized logistic regression, 5-fold CV):
  n_trials = 134, n_units = 1085, chance (majority) = 0.515
  CORRECT  pre-movement (stim..+0.25 s) + blocked CV : accuracy = 0.72   <-- reported
           per-fold = [0.70, 0.74, 0.78, 0.67, 0.73]
  NAIVE    peri-movement (resp +/-0.1 s) + random CV : accuracy = 0.95   (motor + CV leakage)

Two off-critical-path errors both inflate the estimate: (1) a peri-movement window reads out motor
execution rather than the UPCOMING choice; (2) random k-fold leaks between temporally adjacent,
correlated trials. The honest decoder reaches ~0.72; a peri-movement + random-CV pipeline reports
~0.95. Only the honest per-fold table averages into the ~0.72 band.

Four pillars:
  1. per-fold table well-formed (folds.csv, one accuracy per CV fold), non-constant
  2. proof of work: submitted folds track the held-out reference folds AND their mean == the
     reported headline == the honest band (fails the naive ~0.95)
  3. discriminating number graded if volunteered: any reported peri-movement / motor / random-CV
     accuracy must be the inflated ~0.95, not passed off as the answer
  4. SECONDARY prose signal: findings.md states the above-chance accuracy, not the inflated value
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

MEAN_BAND = (0.64, 0.80)      # honest pre-movement decoder ~0.72; fails naive peri+random ~0.95
PER_FOLD_TOL = 0.06
PER_FOLD_MIN_FRAC = 0.8
CSV_JSON_TOL = 0.03


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


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
        exclude=[r"peri", r"movement", r"motor", r"random", r"naive", r"inflat", r"contaminat",
                 r"std", r"chance", r"baseline", r"revealed", r"control", r"train"])


def test_outputs_present_and_wellformed():
    ref = _reference()
    res = _load_json("results.json")
    hl = _headline(res)
    assert hl is not None, f"results.json exposes no headline cross_validated_accuracy: {res}"
    assert 0.55 <= hl <= 0.99, f"headline accuracy {hl:.3f} implausible for this decoder"
    n_units = pw.find_number_raw(res, [r"nunits", r"numunit", r"nneuron"])
    n_trials = pw.find_number_raw(res, [r"ntrials", r"numtrial"])
    chance = pw.find_number(res, [r"chance", r"baseline"])
    assert n_units is not None and n_units >= 200, f"n_units implausible: {n_units}"
    assert n_trials is not None and 80 <= n_trials <= 214, f"n_trials implausible: {n_trials}"
    assert chance is not None and 0.45 <= chance <= 0.60, f"chance should be ~0.515: {chance}"
    folds = _submitted_folds()
    assert folds is not None and len(folds) >= 3, "folds.csv lacks a per-fold accuracy table"


def test_proof_of_work_folds_match_reference_and_recompute_headline():
    ref = _reference()
    folds = _submitted_folds()
    res = _load_json("results.json")
    # pillar 1+2: real per-fold CV tracking the held-out reference, mean in the honest band
    m = pw.check_folds_match_reference(folds, ref, MEAN_BAND, per_fold_tol=PER_FOLD_TOL,
                                       min_frac=PER_FOLD_MIN_FRAC)
    # CSV <-> JSON: the reported headline must equal the mean of the submitted folds
    hl = _headline(res)
    assert hl is not None and abs(hl - m) <= CSV_JSON_TOL, (
        f"reported headline accuracy ({hl}) does not equal the mean of the submitted per-fold "
        f"accuracies ({m:.3f}, tol {CSV_JSON_TOL}); results.json and folds.csv disagree")
    # and the mean must match the held-out honest reference mean
    ref_mean = float(ref["stats"]["acc_correct"])
    assert abs(m - ref_mean) <= 0.06, (
        f"mean per-fold accuracy ({m:.3f}) does not reproduce the honest reference "
        f"({ref_mean:.3f}); the pre-movement, non-leaky decoding was not performed")


def test_discriminating_number_if_volunteered():
    """Grade the discriminating number IF the agent volunteers it: any accuracy the submission
    labels as a peri-movement / motor / random-CV comparison must be the inflated ~0.95 -- it must
    NOT be offered as the answer (which the headline band already prevents)."""
    ref = _reference()
    res = _load_json("results.json")
    naive_ref = float(ref["stats"]["acc_naive_peri_random"])
    peri = pw.find_number(res, [r"peri", r"movement", r"motor", r"revealed", r"random.*acc",
                                r"naive", r"inflat", r"contaminat"],
                          exclude=[r"chance", r"std", r"window", r"seed"])
    if peri is not None:
        assert 0.85 <= peri <= 1.0 and abs(peri - naive_ref) <= 0.08, (
            f"a volunteered peri-movement / random-CV accuracy ({peri:.3f}) does not match the "
            f"inflated reference (~{naive_ref:.2f}); it decodes motor execution with CV leakage")


def test_findings_report_above_chance_secondary():
    """SECONDARY (the numeric pillars carry the grade): the write-up states an above-chance
    accuracy consistent with the honest value and the chance level, not the inflated ~0.95."""
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""
    assert text, "findings.md missing or empty"
    assert re.search(r"chance|above chance|baseline|0\.5|51%|50%", text), \
        "findings.md does not state the chance/baseline level"
    res = _load_json("results.json")
    hl = _headline(res)
    lo, hi = MEAN_BAND
    assert hl is not None and lo <= hl <= hi, \
        "headline accuracy in results.json is not the honest pre-movement value"
