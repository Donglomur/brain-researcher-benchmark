"""Proof-of-work grader for AASMSTAGE-001 (5-class AASM sleep staging on Sleep-EDF).

The grade is carried by NUMBERS against a reference (`reference.npz`) built by running the
oracle on the pinned Sleep-EDF cohort (subjects [0..5], recording 1; two-EEG relative
band-power features; RandomForest(200, random_state=42); leave-one-subject-out CV). The
reference is held out of the agent CONTAINER but PUBLIC in this repo (burned) -- a real eval
needs fresh tasks / a server-side reference:

  PILLAR 1  the submitted per-subject table (per_subject.csv) must cover the exact 6-subject
            LOSO sample, be non-constant, and match the held-out per-subject OVERALL and
            stage-fair BALANCED accuracies.
  PILLAR 2  the epoch-weighted OVERALL accuracy recomputed FROM the submitted rows must match
            BOTH the reference overall accuracy AND the reported overall-accuracy number.
  PILLAR 3  the DISCRIMINATING number is balanced-vs-overall: the reported headline accuracy
            must equal the stage-fair BALANCED accuracy (materially BELOW the overall
            accuracy). A naive run that reports the inflated overall accuracy (~0.77) as the
            headline cannot match the balanced accuracy (~0.66) and fails.

The five AASM stages are very unequal (N2 ~46% of epochs, N1 ~9%), so overall accuracy has
a ~0.46 majority baseline, not the 0.20 five-way chance level; the balanced accuracy is the
honest summary. There is no prose-keyword-only judgement gate.
"""
import json
import os
import re
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

OVERALL_VAL_TOL = 0.06     # per-subject overall accuracy (uV-free); LOSO accuracies are specific
BALANCED_VAL_TOL = 0.10    # per-subject balanced accuracy (noisier: rare stages)
GROUP_TOL = 0.06           # group overall/balanced/kappa vs reference / reported
                           # (widened from 0.035: a defensible pipeline / lib-version drift shifts
                           # the group balanced/overall/kappa by ~5-7% (~0.045 absolute), which the
                           # old 0.035 rejected. 0.06 stays well below the overall-vs-balanced gap
                           # (0.105), so reporting the inflated overall (~0.765) as the headline
                           # still fails; GAP_MIN and the per-subject pillars are unchanged.)
GAP_MIN = 0.05             # balanced must be at least this far BELOW overall (the discriminator)


def _load(name):
    p = OUT / name
    assert p.exists(), f"missing required output {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _submitted():
    csvp = OUT / "per_subject.csv"
    assert csvp.exists(), (
        "missing per_subject.csv -- the task requires a per-subject table with each held-out "
        "subject's overall accuracy, stage-fair balanced accuracy and Cohen kappa")
    return pw.load_submitted(str(csvp), {
        "overall": ["overall_accuracy", "overall_acc", "overall"],
        "balanced": ["balanced_accuracy", "balanced_acc", "balanced", "stage_fair", "macro"],
        "kappa": ["kappa", "cohen"],
        "neps": ["n_epochs", "n_test_epochs", "epochs"],
    })[0]


# ---- PILLAR 3: the discriminating number is balanced-vs-overall ------------------------
def test_headline_is_stage_fair_balanced_accuracy():
    data = _load("staging_results.json")
    assert int(data.get("n_stages", len(data.get("stages", [])))) == 5, \
        "must be a five-class (W/N1/N2/N3/REM) staging problem"
    headline = _num(data.get("accuracy"))
    overall = _num(data.get("overall_accuracy_for_reference"))
    kappa = _num(data.get("cohen_kappa"))
    g_bal = float(REF["group_balanced"]); g_ov = float(REF["group_overall"]); g_k = float(REF["group_kappa"])
    assert headline is not None, "staging_results.json missing accuracy"
    assert abs(headline - g_bal) <= GROUP_TOL, (
        f"reported headline accuracy {headline:.3f} is not the stage-fair BALANCED accuracy "
        f"({g_bal:.3f} +/- {GROUP_TOL}). Reporting the inflated overall accuracy (~{g_ov:.3f}) "
        f"as the headline over-claims how well the five stages are identified.")
    assert overall is not None and abs(overall - g_ov) <= GROUP_TOL, (
        f"overall_accuracy_for_reference {overall} is not the reference overall accuracy "
        f"{g_ov:.3f} +/- {GROUP_TOL}")
    assert headline <= overall - GAP_MIN, (
        f"the balanced accuracy ({headline:.3f}) must be materially below the overall accuracy "
        f"({overall:.3f}); the gap encodes the class-imbalance inflation")
    assert kappa is not None and abs(kappa - g_k) <= GROUP_TOL, \
        f"reported cohen_kappa {kappa} is not the reference kappa {g_k:.3f} +/- {GROUP_TOL}"


# ---- PILLAR 1: per-subject overall + balanced accuracy proof of work --------------------
def test_per_subject_overall_proof_of_work():
    sub = _submitted()
    pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_overall"], "overall", OVERALL_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-3, signed=True)


def test_per_subject_balanced_proof_of_work():
    sub = _submitted()
    pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_balanced"], "balanced", BALANCED_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-3, signed=True)


# ---- PILLAR 2: recompute the group overall accuracy from the rows -----------------------
def test_recompute_overall_from_rows():
    sub = _submitted()
    present = [i for i in (pw.canon_id(x) for x in REF["ref_ids"])
               if i in sub and sub[i].get("overall") is not None and sub[i].get("neps") is not None]
    assert len(present) >= 0.9 * len(REF["ref_ids"]), \
        "per_subject.csv must include n_epochs to recompute the epoch-weighted overall accuracy"
    reported_overall = _num(_load("staging_results.json").get("overall_accuracy_for_reference"))
    pw.check_recompute(sub, present, "overall", float(REF["group_overall"]), reported_overall,
                       tol_ref=GROUP_TOL, tol_report=GROUP_TOL, weight_key="neps")


# ---- SECONDARY (not the sole gate): the write-up volunteers the imbalance ---------------
def test_findings_reports_imbalance():
    text = re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())
    assert "balanced" in text or "per-stage" in text or "per-class" in text or "imbalanc" in text, \
        "findings.md does not volunteer the class-imbalance / stage-fair caveat"
