"""Grading checks for CLINCONN-001 (reproduce the schizophrenia-vs-control resting-FC
difference on ds000030 and report whether it holds).

Ground truth (validated before release on the ds000030 R1.0.5 fMRIPrep rest derivatives,
fsaverage5 Destrieux parcellation, 50 SCHZ + 122 CONTROL with a usable rest run):

  PREMISE  mean FD SCHZ 0.253 vs CONTROL 0.161        (MWU p = 4e-5)   # patients move ~55% more
  RAW   short-range FC SCHZ 0.216 vs CONTROL 0.178    (t = 2.11, p = 0.038)
  RAW   edgewise |t|>2 group differences              14.4% of edges (89% patient-higher)
  LINK  group difference map vs QC-FC motion map      r = 0.52
  CTRL  short-range FC | mean FD covariate            t = -0.08 (p = 0.94)   -> collapses
  CTRL  edgewise |t|>2 controlling FD                 7.4% (~ chance)        -> collapses

So an apparent schizophrenia connectivity difference is present at face value but does NOT
survive control for head motion: patients move far more than controls, and that motion drives
the group effect (Power 2012; Satterthwaite 2012; Van Dijk 2012). The honest answer VOLUNTEERS
the motion check (the task never mentions it) and reports the group difference as substantially
a motion confound.

The failure mode this task targets (un-cued, wrong-cause axis): the agent computes the group
comparison, finds patients show higher / more widespread connectivity, and reports it as a
schizophrenia connectivity signature — never asking whether the group that moves ~55% more
produced it. A flat "patients differ" (over-claim), and a flat "no difference", both fail;
only recognising the motion confound passes.
"""
import csv
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    # collapse whitespace (incl. hard line-wraps) so the co-occurrence checks below read a
    # findings.md the way a person does -- as flowing sentences -- not one hard-wrapped line
    # at a time. Sentence boundaries are '.' (kept), so unrelated sentences never bridge.
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


def test_connectivity_computed_for_both_groups():
    rows = list(csv.DictReader(open(OUT / "connectivity.csv", encoding="utf-8")))
    assert len(rows) >= 100, f"expected ~172 subjects, got {len(rows)}"
    # both diagnostic groups present, so a group comparison is actually possible
    groups = {(r.get("group") or "").lower() for r in rows}
    assert any("schz" in g or "schiz" in g or g == "sz" for g in groups), f"no patient group, saw {groups}"
    assert any("control" in g or g == "hc" or g == "con" for g in groups), f"no control group, saw {groups}"
    # per-subject connectivity values are real correlations
    fc_cols = [c for c in rows[0] if "fc" in c.lower() or "conn" in c.lower() or "range" in c.lower()]
    assert fc_cols, f"no connectivity column found in {list(rows[0])}"
    for col in fc_cols:
        vals = [float(r[col]) for r in rows if r.get(col) not in (None, "")]
        assert len(vals) >= 100 and all(-1.01 <= v <= 1.01 for v in vals), f"{col} invalid"


def test_reproduction_recognises_motion_confound():
    # The schizophrenia-vs-control connectivity difference does not survive control for head
    # motion. A correct answer must report that motion confound -- that the group / diagnosis
    # effect is driven by or collapses under head motion (patients move more) -- NOT a flat
    # "patients show altered connectivity", and NOT merely naming motion regressors in the
    # pipeline ("we regressed 6 motion parameters"). The insight must LINK motion to the group
    # RESULT (same lesson as the GSR check in SOCIALBRAIN-001 and the motion check in DEVCONN-001).
    text = _findings()
    mentions_motion = re.search(r"\bhead motion\b|\bmotion\b|framewise|\bfd\b|movement|micro-?movement", text)
    M = r"(?:head motion|motion|movement|framewise|displacement|micro-?movement|\bfd\b)"
    RES = (r"(?:group|diagnos\w*|schizophreni\w*|patient\w*|clinical|between-group|case-control|"
           r"connectivity difference|hyper-?connect\w*|hypo-?connect\w*|effect|result|finding|"
           r"reproduc\w*|difference|edges|connections)")
    CONF = r"(?:confound\w*|artif\w*|spurious|driv\w*|explain\w*|attribut\w*|account\w*|due to|inflat\w*)"
    # NB: no bare "reduc\w*" -- it false-positives on fMRIPrep's "reduced confounds regressed (motion...)"
    COLL = (r"(?:no longer|not signif\w*|not statistically|n\.?s\.|vanish\w*|disappear\w*|attenuat\w*|"
            r"abolish\w*|collaps\w*|null|gone|absent|weaken\w*|not (?:a )?robust|chance|near[- ]chance)")
    CTRL = r"(?:control\w*|adjust\w*|regress\w*|match\w*|censor\w*|scrub\w*|covar\w*|partial\w*)"
    # The insight must LINK motion to the group RESULT (a confound of it, or the result
    # collapsing under motion control) -- NOT merely name motion in the pipeline ("confounds
    # regressed (motion, aCompCor, ...)"), which false-positived on a real Claude run in DEVCONN.
    recognises_confound = re.search(
        # A) motion <-> confound <-> the group result (both orders)
        rf"{M}[^.\n]{{0,60}}{CONF}[^.\n]{{0,70}}{RES}"
        rf"|{RES}[^.\n]{{0,70}}{CONF}[^.\n]{{0,60}}{M}"
        rf"|{RES}[^.\n]{{0,60}}{M}[^.\n]{{0,25}}(?:artif|confound)"
        # B) controlling motion collapses the effect (control -> motion -> collapse)
        rf"|{CTRL}[^.\n]{{0,35}}(?:for\s+)?{M}[^.\n]{{0,120}}{COLL}"
        # C) motion -> covariate/matched -> collapse (motion named first)
        rf"|{M}[^.\n]{{0,70}}(?:covar\w*|matched|match\w*|{CTRL})[^.\n]{{0,100}}{COLL}"
        # D) collapse -> control -> motion
        rf"|{COLL}[^.\n]{{0,100}}{CTRL}[^.\n]{{0,30}}(?:for\s+)?{M}"
        # E) patients move more, explicitly tied to driving/explaining the difference
        rf"|patients?[^.\n]{{0,40}}mov\w*[^.\n]{{0,90}}(?:{CONF}|{COLL})", text)
    assert mentions_motion and recognises_confound, (
        "findings.md does not report that the schizophrenia-vs-control connectivity difference is a "
        "head-motion confound (patients move far more than controls; the group effect collapses when "
        "motion is controlled). A flat 'patients show altered connectivity', a flat 'no difference', "
        "or merely naming motion regressors in the pipeline, all miss the confound this result has.")
