"""Proof-of-work grader for N2PC-001 (ERP CORE N2pc component amplitude at PO7/PO8).

The grade is carried by NUMBERS against a held-out reference (`reference.npz`) built by
running the oracle on the ERP CORE N2pc recordings (subjects 1/3-13; PO7/PO8; 0.1-30 Hz;
average reference; -200..0 baseline; 200-300 ms mean amplitude):

  PILLAR 1  the submitted per-subject table (per_subject.csv) must cover the exact 12-subject
            sample, be non-constant, and match the held-out per-subject SIGNED
            contralateral-minus-ipsilateral N2pc amplitudes (a negativity). An abs()-ed,
            sign-flipped, or field-pooled table fails.
  PILLAR 2  the mean of the submitted per-subject N2pc column must match BOTH the reference
            grand-average AND the reported headline amplitude.
  PILLAR 3  the DISCRIMINATING number is lateralized-vs-pooled: the reported N2pc must be the
            per-side contralateral-minus-ipsilateral difference (~-1.4 uV), whereas the
            fixed-electrode difference pooled across the balanced visual fields cancels to ~0.
            A pooled fixed-electrode pipeline (~+/-0.3 uV) cannot match the signed N2pc.
"""
import json
import os
import re
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

N2PC_VAL_TOL = 0.85    # per-subject signed N2pc amplitude (uV)
GROUP_TOL = 0.40       # grand-average N2pc vs reference / reported (uV)
FIXED_TOL = 0.45       # reported pooled fixed-electrode difference vs reference (~0)
NEG_MAX = -0.70        # the N2pc must be clearly negative (below the pooled cancellation)


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
        "contralateral, ipsilateral and contralateral-minus-ipsilateral (N2pc) amplitudes")
    return pw.load_submitted(str(csvp), {
        "n2pc": ["n2pc", "contra_minus_ipsi", "contra-ipsi", "diff"],
        "contra": ["contra_uv", "contralateral"],
        "ipsi": ["ipsi_uv", "ipsilateral"],
    })[0]


# ---- PILLAR 3: lateralized-vs-pooled ---------------------------------------------------
def test_headline_is_signed_lateralized_n2pc():
    data = _load("n2pc.json")
    amp = _num(data.get("n2pc_amplitude_uv"))
    fixed = _num(data.get("fixed_po8_minus_po7_pooled_uv_for_reference"))
    m = float(REF["n2pc_mean"]); fx = float(REF["fixed_mean"])
    assert amp is not None, "n2pc.json missing n2pc_amplitude_uv"
    assert amp < 0, f"n2pc_amplitude_uv must be the SIGNED contralateral-minus-ipsilateral N2pc " \
                    f"(a negative value); got {amp}"
    assert amp <= NEG_MAX, (
        f"reported N2pc {amp:.2f} uV is not a clear negativity; a field-pooled fixed-electrode "
        f"difference cancels to ~{fx:.2f} uV and must not be reported as the N2pc")
    assert abs(amp - m) <= GROUP_TOL, (
        f"reported N2pc {amp:.2f} uV is not within {GROUP_TOL} of the reference grand-average "
        f"{m:.2f} uV")
    assert fixed is not None and abs(fixed - fx) <= FIXED_TOL and abs(fixed) < 0.9, (
        f"the pooled fixed-electrode difference must be reported and near zero "
        f"(reference {fx:.2f} uV); got {fixed} -- this is the discriminating contrast")


# ---- PILLAR 1: per-subject signed N2pc proof of work -----------------------------------
def test_per_subject_n2pc_proof_of_work():
    sub = _submitted()
    present = pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_n2pc"], "n2pc", N2PC_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-2, signed=True)
    n_neg = sum(sub[i]["n2pc"] < 0 for i in present)
    assert n_neg >= 0.75 * len(present), \
        f"most subjects should show a negative N2pc; only {n_neg}/{len(present)} are negative"


# ---- PILLAR 2: recompute the grand-average from the rows -------------------------------
def test_recompute_grandaverage_from_rows():
    sub = _submitted()
    present = [i for i in (pw.canon_id(x) for x in REF["ref_ids"])
               if i in sub and sub[i].get("n2pc") is not None]
    reported = _num(_load("n2pc.json").get("n2pc_amplitude_uv"))
    pw.check_recompute(sub, present, "n2pc", float(REF["n2pc_mean"]), reported,
                       tol_ref=GROUP_TOL, tol_report=GROUP_TOL)


# ---- SECONDARY: the write-up reports the lateralized profile ---------------------------
def test_findings_reports_n2pc():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("contralateral" in text or "n2pc" in text) and ("po7" in text or "po8" in text), \
        "findings.md does not report the contralateral N2pc at PO7/PO8"
