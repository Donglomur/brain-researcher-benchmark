"""Proof-of-work grader for MOTORIMAGERY-001 (CSP+LDA hands-vs-feet decoding on EEGBCI).

The grade is carried by NUMBERS against a held-out reference (`reference.npz`) built by
running the oracle on the pinned EEGBCI motor-imagery set (subjects 1-10, runs 6/10/14;
7-30 Hz; 1-2 s epochs; all EEG channels; CSP(4)+LDA; per-subject 5-fold CV; 200-permutation
per-subject null):

  PILLAR 1  the submitted per-subject table (per_subject.csv) must cover the 10 subjects, be
            non-constant, and match the held-out per-subject cross-validated accuracies.
  PILLAR 2  the mean of the submitted per-subject accuracies must match BOTH the reference
            group accuracy AND the reported headline accuracy.
  PILLAR 3  the DISCRIMINATING numbers are the individual-reliability summary: the group
            p-value vs chance, the finite-sample permutation-null SD, and the number of
            subjects significant by permutation (and below chance). A naive analysis that only
            reports the group accuracy, or counts subjects above the nominal 0.5, cannot
            reproduce the honest permutation reliability (only ~6/10 significant, not ~8/10
            above 0.5).
"""
import json
import os
import re
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

ACC_VAL_TOL = 0.08     # per-subject CV accuracy
GROUP_TOL = 0.03       # group accuracy vs reference / reported
P_TOL = 0.03           # group p-value vs reference (absolute)
SD_TOL = 0.03          # finite-sample null SD vs reference
COUNT_TOL = 1          # significant / below-chance counts within +/- this many subjects


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
        "missing per_subject.csv -- the task requires a per-subject table with each subject's "
        "cross-validated accuracy, Cohen kappa and permutation p-value")
    return pw.load_submitted(str(csvp), {
        "acc": ["accuracy", "acc"],
        "kappa": ["kappa", "cohen"],
        "p": ["perm_p", "pval", "p_value", "permutation_p"],
    })[0]


# ---- PILLAR 3: individual-reliability discriminators -----------------------------------
def test_reliability_summary_is_honest():
    data = _load("decoding_results.json")
    g_acc = float(REF["group_acc"]); g_p = float(REF["group_p"]); sd = float(REF["null_sd"])
    n_sig = int(REF["n_sig"]); n_below = int(REF["n_below"]); n_above = int(REF["n_above_half"])

    acc = _num(data.get("accuracy"))
    assert acc is not None and abs(acc - g_acc) <= GROUP_TOL, \
        f"reported group accuracy {acc} is not the reference {g_acc:.3f} +/- {GROUP_TOL}"

    gp = _num(data.get("group_p_vs_chance"))
    assert gp is not None and abs(gp - g_p) <= P_TOL, (
        f"group_p_vs_chance {gp} is not the reference one-sample-t p-value {g_p:.3f} +/- {P_TOL}; "
        f"the marginal group effect must be reported honestly")

    nsd = _num(data.get("finite_sample_null_sd"))
    assert nsd is not None and abs(nsd - sd) <= SD_TOL, (
        f"finite_sample_null_sd {nsd} is not the reference permutation-null SD {sd:.3f} +/- "
        f"{SD_TOL}; the finite-sample chance spread must be measured (permutation), not assumed")

    rsig = _num(data.get("n_subjects_significant_perm_p05"))
    assert rsig is not None and abs(rsig - n_sig) <= COUNT_TOL, (
        f"n_subjects_significant_perm_p05 {rsig} is not the reference {n_sig} (+/- {COUNT_TOL}). "
        f"Counting subjects above the nominal 0.5 ({n_above}/10) instead of permutation-"
        f"significant over-claims how many subjects decode (exceeding-chance-by-chance pitfall).")
    assert rsig <= n_above, (
        f"the number of permutation-significant subjects ({rsig}) cannot exceed the number "
        f"above the nominal 0.5 ({n_above}); a naive nominal count over-states reliability")

    rbelow = _num(data.get("n_subjects_below_chance"))
    assert rbelow is not None and abs(rbelow - n_below) <= COUNT_TOL, \
        f"n_subjects_below_chance {rbelow} is not the reference {n_below} (+/- {COUNT_TOL})"


# ---- PILLAR 1: per-subject accuracy proof of work --------------------------------------
def test_per_subject_accuracy_proof_of_work():
    sub = _submitted()
    pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_acc"], "acc", ACC_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-3, signed=True)


# ---- PILLAR 2: recompute the group accuracy from the rows ------------------------------
def test_recompute_accuracy_from_rows():
    sub = _submitted()
    present = [i for i in (pw.canon_id(x) for x in REF["ref_ids"])
               if i in sub and sub[i].get("acc") is not None]
    reported = _num(_load("decoding_results.json").get("accuracy"))
    pw.check_recompute(sub, present, "acc", float(REF["group_acc"]), reported,
                       tol_ref=GROUP_TOL, tol_report=GROUP_TOL)


# ---- SECONDARY: the write-up volunteers the per-user reliability ------------------------
def test_findings_reports_reliability():
    text = re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())
    assert "permutation" in text or "significan" in text or "reliab" in text or "illiteracy" in text, \
        "findings.md does not volunteer the per-subject reliability / permutation caveat"
