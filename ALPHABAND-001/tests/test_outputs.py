"""Proof-of-work grader for ALPHABAND-001 (reproduce the Berger effect on EEGBCI).

The grade is carried by NUMBERS against a held-out reference (`reference.npz`) built by
running the oracle on the pinned EEGBCI recordings (subjects 1-5, run 1 eyes-open / run 2
eyes-closed; band 8-13 Hz; common-average reference; Welch 2-s segments):

  PILLAR 1  the submitted per-subject table (per_subject.csv) must cover the 5 subjects, be
            non-constant, and match the held-out per-subject OCCIPITAL eyes-closed/eyes-open
            alpha ratios. These real occipital per-subject ratios span ~1.3-48; a whole-head
            pipeline (the un-cued trap) compresses them to ~4 and cannot match.
  PILLAR 2  the mean of the submitted per-subject ratios must match BOTH the reference
            occipital mean AND the reported headline ratio.
  PILLAR 3  the DISCRIMINATING number is occipital-vs-whole-head: the reported ratio must be
            the occipital ratio (~19.6), far above the whole-head dilution (~4.4).
"""
import json
import os
import re
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

RATIO_VAL_TOL = 2.5     # per-subject occipital ratio absolute floor
RATIO_REL_TOL = 0.30    # ... or within 30% of the reference (wide dynamic range)
GROUP_TOL = 3.0         # group ratio vs reference / reported


def _load(name):
    p = OUT / name
    assert p.exists(), f"missing required output {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _headline(data):
    if isinstance(data, dict):
        v = data.get("occipital_alpha_ratio_ec_over_eo")
        if v is not None:
            return _num(v)
        for k, val in data.items():
            if isinstance(val, (int, float)) and "ratio" in k.lower() and "wholehead" not in k.lower():
                return float(val)
    return None


def _submitted():
    csvp = OUT / "per_subject.csv"
    assert csvp.exists(), (
        "missing per_subject.csv -- the task requires a per-subject table with each subject's "
        "eyes-closed and eyes-open occipital alpha power and their ratio")
    return pw.load_submitted(str(csvp), {
        "ratio": ["ratio"],
        "ec": ["ec_occipital", "ec_alpha", "ec"],
        "eo": ["eo_occipital", "eo_alpha", "eo"],
    })[0]


# ---- PILLAR 3: occipital-vs-whole-head -------------------------------------------------
def test_headline_is_occipital_ratio():
    data = _load("alpha_ratio.json")
    r = _headline(data)
    occ = float(REF["occ_mean"]); wh = float(REF["wholehead_mean"])
    assert r is not None, "alpha_ratio.json missing the occipital EC/EO ratio"
    assert abs(r - occ) <= GROUP_TOL, (
        f"reported occipital alpha ratio {r:.2f} is not the occipital Berger ratio "
        f"({occ:.2f} +/- {GROUP_TOL}). A whole-head average (~{wh:.1f}) dilutes the effect.")
    assert r >= wh + 5.0, (
        f"reported ratio {r:.2f} is not clearly above the whole-head dilution ({wh:.1f}); "
        f"the effect must be measured over the occipital electrodes")


# ---- PILLAR 1: per-subject occipital ratio proof of work -------------------------------
def test_per_subject_ratio_proof_of_work():
    sub = _submitted()
    present = pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_ratio"], "ratio", RATIO_VAL_TOL,
        cover=0.90, match=0.80, eps=1e-2, signed=True, rel_tol=RATIO_REL_TOL)
    # Berger direction: eyes-closed occipital alpha exceeds eyes-open for most subjects
    ratios = [sub[i]["ratio"] for i in present]
    assert sum(r > 1.0 for r in ratios) >= 0.8 * len(ratios), \
        f"eyes-closed should exceed eyes-open occipitally for most subjects, got {ratios}"


# ---- PILLAR 2: recompute the group ratio from the rows ---------------------------------
def test_recompute_ratio_from_rows():
    sub = _submitted()
    present = [i for i in (pw.canon_id(x) for x in REF["ref_ids"])
               if i in sub and sub[i].get("ratio") is not None]
    reported = _headline(_load("alpha_ratio.json"))
    pw.check_recompute(sub, present, "ratio", float(REF["occ_mean"]), reported,
                       tol_ref=GROUP_TOL, tol_report=GROUP_TOL)


# ---- SECONDARY: the write-up reports the occipital effect ------------------------------
def test_findings_reports_occipital():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert "occipital" in text and ("closed" in text or "berger" in text), \
        "findings.md does not report the occipital eyes-closed alpha enhancement"
