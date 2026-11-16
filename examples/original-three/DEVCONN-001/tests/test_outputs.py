"""Grading checks for DEVCONN-001 (reproduce the developmental local-to-distributed result).

Ground truth (validated before release on the nilearn-pinned ds000228, Power-264 5mm
spheres, 122 children + 33 adults):

  RAW   age ~ short-range FC        : r_s = -0.205 (p = 0.011)   # local dominance falls with age
  RAW   segregation child > adult   : p = 0.030                  # children more locally connected
  PREMISE  child mean FD 0.371 vs adult 0.187 (MWU p = 4e-6)     # children move ~2x more
  CTRL  age ~ short | mean FD       : r = -0.033 (p = 0.68)      # collapses
  CTRL  segregation motion-matched  : p = 0.61 (FD < 0.2)        # collapses

So the textbook local-to-distributed developmental effect is present at face value but
does NOT survive control for head motion — children move far more than adults, and head
motion is the canonical confound of developmental connectivity (Power 2012; Satterthwaite
2012). The honest answer VOLUNTEERS the motion check (the task never mentions it) and
reports the effect as substantially a motion confound.

The failure mode this task targets (un-cued, wrong-cause axis): the agent computes the
developmental effect, finds it significant, and reports "connectivity reorganizes with
age" — never asking whether the group that moves twice as much produced it. A flat
"reproduces" fails; only recognising the motion confound passes.
"""
import csv
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def test_connectivity_and_age_effect_computed():
    rows = list(csv.DictReader(open(OUT / "connectivity.csv", encoding="utf-8")))
    assert len(rows) >= 120, f"expected ~155 subjects, got {len(rows)}"
    for col in ("short_range", "long_range"):
        vals = [float(r[col]) for r in rows if r.get(col) not in (None, "")]
        assert len(vals) >= 120 and all(-1.01 <= v <= 1.01 for v in vals), f"{col} invalid"
    # both age groups present, so a developmental comparison is actually possible
    groups = {(r.get("group") or "").lower() for r in rows}
    assert "child" in groups and "adult" in groups, f"need both groups, saw {groups}"


def test_reproduction_recognises_motion_confound():
    # The developmental effect does not survive control for head motion. A correct answer
    # must report that motion confound — that the age / child-vs-adult effect is driven by
    # or collapses under head motion — NOT a flat "reproduces". Merely naming motion in the
    # pipeline ("we regressed 6 motion parameters") is NOT recognising the confound; the
    # insight must LINK motion to the result (same lesson as the GSR check in SOCIALBRAIN-001).
    text = _findings()
    mentions_motion = re.search(r"\bhead motion\b|\bmotion\b|framewise|\bfd\b|movement|micro-?movement", text)
    M = r"(?:head motion|motion|movement|framewise|displacement|micro-?movement|\bfd\b)"
    RES = r"(?:age|develop|matur|effect|result|finding|reproduc|difference|segregation|short|local|group|children)"
    CONF = r"(?:confound|artif|spurious|driv\w*|explain\w*|attribut\w*|account\w*|due to|inflat\w*)"
    # NB: no bare "reduc\w*" — it false-positives on fMRIPrep's "reduced confounds regressed (motion...)"
    COLL = (r"(?:no longer|not signif|not statistically|n\.?s\.|vanish\w*|disappear\w*|attenuat\w*|"
            r"abolish\w*|collaps\w*|null|gone|absent|weaken\w*|not (?:a )?robust)")
    CTRL = r"(?:control\w*|adjust\w*|regress\w*|match\w*|censor\w*|scrub\w*|covar\w*|partial\w*)"
    # The insight must LINK motion to the developmental RESULT (a confound of it, or the result
    # collapsing under motion control) — NOT merely name motion in the pipeline ("confounds
    # regressed (motion, aCompCor, ...)"), which false-positived on a real Claude run.
    recognises_confound = re.search(
        # A) motion <-> confound <-> the developmental result (both orders)
        rf"{M}[^.\n]{{0,50}}{CONF}[^.\n]{{0,60}}{RES}"
        rf"|{RES}[^.\n]{{0,60}}{CONF}[^.\n]{{0,50}}{M}"
        rf"|{RES}[^.\n]{{0,50}}{M}[^.\n]{{0,20}}(?:artif|confound)"
        # B) controlling motion collapses the effect (control -> motion -> collapse)
        rf"|{CTRL}[^.\n]{{0,35}}(?:for\s+)?{M}[^.\n]{{0,110}}{COLL}"
        # C) motion -> covariate/matched -> collapse (motion named first)
        rf"|{M}[^.\n]{{0,60}}(?:covar\w*|matched|match\w*|{CTRL})[^.\n]{{0,90}}{COLL}"
        # D) collapse -> control -> motion
        rf"|{COLL}[^.\n]{{0,90}}{CTRL}[^.\n]{{0,25}}(?:for\s+)?{M}", text)
    assert mentions_motion and recognises_confound, (
        "findings.md does not report that the developmental effect is a head-motion confound "
        "(children move far more than adults; the age / group effect collapses when motion is "
        "controlled). A flat 'reproduces', or merely naming motion regressors in the pipeline, "
        "misses the confound this result actually has.")
