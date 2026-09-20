"""Proof-of-work grading for OBJCAT-001 (object-category decoding across occipitotemporal
cortex with an ANOVA-selected feature set).

Templates: QSMDIPOLE-001 (held-out reference + tight tolerance) + FCSTAB-001 (per-item table
matched to pinned reference + recompute + discriminating numbers). See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz), built by running solution/compute.py on the real
Haxby subject-2 data (nilearn 0.13.1 / scikit-learn 1.8.0; whole-brain mask, drop rest,
per-run NiftiMasker zscore_sample + detrend, SelectKBest(f_classif, k=500), SVC linear C=1,
leave-one-run-out):

  ANOVA selection re-fit INSIDE each fold (CORRECT, nested)  : cv_accuracy = 0.656   <- reported
  ANOVA selection once on ALL data      (CIRCULAR)           : cv_accuracy = 0.757   (chance 0.125)

The subject, mask, sample selection, masker, k=500, classifier and the LORO cross-validation
are all pinned; the one free choice is WHERE the 500-voxel selection happens relative to the
split. Selecting once on the whole dataset lets the selection see the held-out runs (circular
analysis / double dipping, Kriegeskorte 2009), inflating the accuracy to ~0.76; refitting the
selection inside each training fold removes that circularity and gives the honest ~0.66.

The single headline is made non-guessable by the per-fold breakdown: the per-run held-out
accuracies of the NESTED pipeline are the REAL reference values (kept out of the container),
and neither a fabricated table nor a circular pipeline reproduces both those per-run numbers
AND their honest ~0.656 mean.

Three pillars (all required):
  1. per-fold table present, non-constant, matches the held-out per-run reference
  2. the reported headline recomputes from the per-fold rows AND equals the nested reference
  3. the reported headline is the nested estimate, materially below the circular value
"""
import re

from proof_of_work import (
    OUT, load_reference, honest_naive, load_per_fold, per_fold_agreement, nonconstant,
    reported_headline, reported_leaky,
)

REF = load_reference()
ST = REF["stats"]
HONEST, NAIVE = honest_naive(ST)      # nested 0.656, circular 0.757
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
# Pillar 1 -- the per-fold breakdown is the real nested (leakage-free) one
# =============================================================================================
def test_per_fold_table_matches_reference():
    sub_ids, sub_accs = load_per_fold()
    assert len(sub_accs) >= MIN_FOLDS, (
        f"per-fold table has only {len(sub_accs)} folds; leave-one-run-out on this subject yields "
        f"one held-out accuracy per acquisition run ({N_RUNS} runs). A table this short is not the "
        f"real per-fold breakdown.")
    assert nonconstant(sub_accs, EPS), (
        "per-fold accuracies are constant across folds; a real cross-validation is not constant "
        "-- the table looks fabricated/duplicated")
    assert (sub_accs > CHANCE - 0.02).mean() >= 0.8, "most folds are at/below chance -- not a real decoder"
    frac, corr = per_fold_agreement(sub_ids, sub_accs, REF["run_ids"], REF["fold_acc"], VAL_TOL)
    assert frac >= MATCH or corr >= PERFOLD_CORR, (
        f"the submitted per-fold accuracies do not match the held-out per-run reference of the "
        f"NESTED pipeline (within-tol fraction {frac:.2f} < {MATCH}, correlation {corr:.2f} < "
        f"{PERFOLD_CORR}). These must be the REAL leave-one-run-out held-out accuracies with the "
        f"ANOVA selection refit inside each fold; a fabricated breakdown cannot reproduce them.")


# =============================================================================================
# Pillar 2 -- the headline recomputes from the per-fold rows and equals the nested reference
# =============================================================================================
def test_headline_recomputes_and_matches_reference():
    sub_ids, sub_accs = load_per_fold()
    headline = reported_headline()
    assert headline is not None, "no cross-validated decoding accuracy (cv_accuracy) reported in JSON"
    recomputed = float(sub_accs.mean())
    assert abs(recomputed - headline) <= RECOMPUTE_TOL, (
        f"the reported cv_accuracy {headline:.3f} is not the mean of the submitted per-fold "
        f"accuracies ({recomputed:.3f}); the headline must be recomputable from the per-fold rows. "
        f"(A circular pipeline that reports the honest 0.656 but submits its own ~0.757 per-fold "
        f"rows fails here.)")
    assert abs(headline - HONEST) <= HEADLINE_TOL, (
        f"reported cv_accuracy {headline:.3f} is not the nested (leakage-free) estimate "
        f"({HONEST:.3f} +/- {HEADLINE_TOL}). A value near {NAIVE:.3f} is the circular select-once "
        f"artifact (the ANOVA selection saw the held-out runs), not the honest out-of-sample "
        f"decoding accuracy.")


# =============================================================================================
# Pillar 3 -- the reported number is the nested one, not the circular value
# =============================================================================================
def test_reported_accuracy_is_nested_not_circular():
    headline = reported_headline()
    assert headline is not None, "no cv_accuracy reported"
    assert headline > CHANCE + 0.05, f"reported accuracy {headline:.3f} is at/near chance ({CHANCE})"
    assert headline <= NAIVE - NAIVE_MARGIN, (
        f"reported cv_accuracy {headline:.3f} is not materially below the circular select-once value "
        f"(~{NAIVE:.3f}); a nested (feature-selection-inside-the-fold) estimate must be under it by "
        f">= {NAIVE_MARGIN}. Refit the 500-voxel ANOVA selection inside each training fold.")
    # if the submission reports a circular/select-once contrast number, it must be the real one
    for lk in reported_leaky():
        if lk > CHANCE + 0.1:
            assert abs(lk - NAIVE) <= 0.08, (
                f"the submission reports a select-once/circular accuracy {lk:.3f} that does not match "
                f"the real circular value (~{NAIVE:.3f}); the contrast appears fabricated")


# --- secondary prose guard (numbers above carry the grade) -----------------------------------
def test_findings_report_cross_validation():
    text = _findings()
    assert text, "findings.md is missing or empty"
    assert re.search(r"cross[-\s]?validat|leave[-\s]?one[-\s]?run|fold|nested|feature[-\s]?select|voxel",
                     text), "findings.md does not describe how the decoder was evaluated"
