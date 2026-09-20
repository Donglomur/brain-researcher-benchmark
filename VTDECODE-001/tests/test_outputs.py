"""Proof-of-work grading for VTDECODE-001 (Haxby ventral-temporal object decoding).

Templates: QSMDIPOLE-001 (held-out reference + tight tolerance -> the number is only
hittable by real compute) and FCSTAB-001 (per-item table matched to pinned reference +
recompute + discriminating numbers). See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz), built by running solution/compute.py on the real
Haxby subject-1 ventral-temporal data (nilearn 0.13.1 / scikit-learn 1.8.0; mask_vt, drop
rest, NiftiMasker zscore_sample + detrend t_r=2.5, SVC linear C=1):

  leave-one-run-out (CORRECT, run-blocked) : cv_accuracy = 0.722   <- reported
  random 8-fold      (LEAKY)               : cv_accuracy = 0.958   (chance = 0.125)

Each object category is a sustained within-run block, so volumes from one run are strongly
autocorrelated. A random k-fold split lets near-adjacent volumes appear in both train and
test and inflates the accuracy to ~0.96; blocking the cross-validation by acquisition run
(leave-one-run-out) removes that leakage and gives the honest ~0.72. The task pins the
masker and classifier but never names the fold scheme.

The single headline is made non-guessable by the per-fold breakdown: a run-blocked pipeline
produces one held-out accuracy per acquisition run, and those per-run numbers are the REAL
reference values (kept out of the container). A leaky random-fold pipeline produces a
different fold structure and different per-fold numbers, so it cannot reproduce them.

Three pillars (all required):
  1. per-fold table present, non-constant, agrees with the held-out per-run reference
  2. the reported headline recomputes from the per-fold rows AND equals the run-blocked reference
  3. the reported headline is the run-blocked estimate, materially below the leaky value
"""
import re

from proof_of_work import (
    OUT, load_reference, honest_naive, load_per_fold, per_fold_agreement, nonconstant,
    reported_headline, reported_leaky,
)

REF = load_reference()
ST = REF["stats"]
HONEST, NAIVE = honest_naive(ST)
VAL_TOL = ST["VAL_TOL"]
MATCH = ST["MATCH"]
PERFOLD_CORR = ST["PERFOLD_CORR"]
HEADLINE_TOL = ST["HEADLINE_TOL"]
RECOMPUTE_TOL = ST["MEAN_RECOMPUTE_TOL"]
NAIVE_MARGIN = ST["NAIVE_MARGIN"]
EPS = ST["EPS"]
CHANCE = ST["chance"]
N_RUNS = int(ST["n_runs"])
MIN_FOLDS = max(5, N_RUNS - 3)


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


# =============================================================================================
# Pillar 1 -- the per-fold breakdown is the real run-blocked one
# =============================================================================================
def test_per_fold_table_matches_reference():
    sub_ids, sub_accs = load_per_fold()
    assert len(sub_accs) >= MIN_FOLDS, (
        f"per-fold table has only {len(sub_accs)} folds; a proper run-blocked cross-validation of "
        f"this subject yields one held-out accuracy per acquisition run ({N_RUNS} runs). A table "
        f"this short is not the real per-fold breakdown.")
    assert nonconstant(sub_accs, EPS), (
        "per-fold accuracies are constant across folds; a real cross-validation is not constant "
        "-- the table looks fabricated/duplicated")
    assert (sub_accs > CHANCE - 0.02).mean() >= 0.8, "most folds are at/below chance -- not a real decoder"
    frac, corr = per_fold_agreement(sub_ids, sub_accs, REF["run_ids"], REF["fold_acc"], VAL_TOL)
    assert frac >= MATCH or corr >= PERFOLD_CORR, (
        f"the submitted per-fold accuracies do not match the held-out per-run reference "
        f"(within-tol fraction {frac:.2f} < {MATCH}, correlation {corr:.2f} < {PERFOLD_CORR}). "
        f"These must be the REAL leave-one-run-out held-out accuracies for this subject; a "
        f"random-fold or fabricated breakdown cannot reproduce them.")


# =============================================================================================
# Pillar 2 -- the headline recomputes from the per-fold rows and equals the run-blocked reference
# =============================================================================================
def test_headline_recomputes_and_matches_reference():
    sub_ids, sub_accs = load_per_fold()
    headline = reported_headline()
    assert headline is not None, "no cross-validated decoding accuracy (cv_accuracy) reported in JSON"
    recomputed = float(sub_accs.mean())
    assert abs(recomputed - headline) <= RECOMPUTE_TOL, (
        f"the reported cv_accuracy {headline:.3f} is not the mean of the submitted per-fold "
        f"accuracies ({recomputed:.3f}); the headline must be recomputable from the per-fold rows")
    assert abs(headline - HONEST) <= HEADLINE_TOL, (
        f"reported cv_accuracy {headline:.3f} is not the run-blocked leave-one-run-out estimate "
        f"({HONEST:.3f} +/- {HEADLINE_TOL}). A value near {NAIVE:.3f} is the temporally-leaky "
        f"random-fold artifact, not the honest out-of-sample decoding accuracy.")


# =============================================================================================
# Pillar 3 -- the reported number is the honest run-blocked one, not the leaky value
# =============================================================================================
def test_reported_accuracy_is_run_blocked_not_leaky():
    headline = reported_headline()
    assert headline is not None, "no cv_accuracy reported"
    assert headline > CHANCE + 0.05, f"reported accuracy {headline:.3f} is at/near chance ({CHANCE})"
    assert headline <= NAIVE - NAIVE_MARGIN, (
        f"reported cv_accuracy {headline:.3f} is not materially below the leaky random-fold value "
        f"(~{NAIVE:.3f}); a run-blocked estimate must be well under it (by >= {NAIVE_MARGIN}). "
        f"Report the leave-one-run-out accuracy, not the within-run-leaky random-fold one.")
    # if the submission reports a leaky/random contrast number, it must be the real one
    # (guards against a fabricated 'random-fold' value used to look rigorous)
    for lk in reported_leaky():
        if lk > CHANCE + 0.1:   # ignore any reported chance level
            assert abs(lk - NAIVE) <= 0.08, (
                f"the submission reports a random-fold/leaky accuracy {lk:.3f} that does not match "
                f"the real leaky value (~{NAIVE:.3f}); the contrast appears fabricated")


# --- secondary prose guard (numbers above carry the grade) -----------------------------------
def test_findings_report_cross_validation():
    text = _findings()
    assert text, "findings.md is missing or empty"
    assert re.search(r"cross[-\s]?validat|leave[-\s]?one[-\s]?run|run[-\s]?block|fold", text), (
        "findings.md does not describe how the decoder was cross-validated")
    # must not headline the leaky ~0.96 as the decoding accuracy without flagging it
    m = re.search(r"(?:accuracy|decoding)[^.\n]{0,40}?(0?\.9[5-9]\d*)", text)
    if m:
        near = text[max(0, m.start() - 80):m.start() + 80]
        assert re.search(r"leak|inflat|random|not|artifact|overstat|biased", near), (
            "findings.md presents the ~0.96 random-fold value as the decoding accuracy without "
            "flagging it as the leaky/inflated estimate")
