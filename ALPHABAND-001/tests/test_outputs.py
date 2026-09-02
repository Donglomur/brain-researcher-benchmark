"""Grading checks for ALPHABAND-001 (reproduce the Berger effect).

Ground truth (validated before release on the PhysioNet EEGBCI dataset, subjects 1-5,
run 1 eyes open / run 2 eyes closed, band 8-13 Hz, common-average reference, Welch PSD
with 2-s segments, mean of per-subject eyes-closed/eyes-open ratios):

  OCCIPITAL (O1/O2/Oz)     ratio mean = 19.6   (per-subject 16.5, 8.0, 24.3, 48.0, 1.3)
  whole-head 64-ch average ratio mean =  4.4   <-- the un-cued trap

The Berger effect is strongly OCCIPITAL. The raw EDF channel labels in this dataset are
non-standard (trailing dots: "O1..", "Oz.."), so a direct pick of the occipital
electrodes silently misses them and a careless pipeline averages over the whole head,
which dilutes the effect to ~4.4. The correct pipeline standardizes the channel names /
sets the 10-05 montage and measures alpha over the occipital electrodes -> ~19.6.

Across reasonable occipital pipeline choices (occipital electrode set, common-average vs
no re-reference, Welch segment length) the correct ratio stays in ~11-23; every
whole-head / global answer within the pinned 8-13 Hz band is <= ~5. The accept window
below (9.6-29.6) therefore passes any genuine occipital measurement and fails the
whole-head trap.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 19.6   # correct occipital ratio (mean across subjects)
TOL = 10.0        # accept [9.6, 29.6]: covers occipital pipeline variation, excludes whole-head (~4.4)
NAIVE = 4.4       # whole-head average -- must NOT pass


def _load_json(name):
    try:
        return json.loads((OUT / name).read_text(encoding="utf-8"))
    except Exception:
        return None


def _headline_ratio():
    """The single occipital EC/EO ratio the submission reports."""
    obj = _load_json("alpha_ratio.json")
    if isinstance(obj, dict):
        # preferred: the named field, searched at any depth
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if isinstance(v, (int, float)) and re.search(
                            r"ratio.*(ec|closed).*(eo|open)|occipital.*ratio|alpha.*ratio|"
                            r"ec.*eo.*ratio|berger", k, re.I):
                        return float(v)
                    stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)
        # otherwise: a plain top-level scalar ratio field
        for k, v in obj.items():
            if isinstance(v, (int, float)) and "ratio" in k.lower():
                return float(v)
    # fallback: scan findings.md for a ratio-like number
    p = OUT / "findings.md"
    if p.exists():
        txt = p.read_text(encoding="utf-8")
        cands = [float(x) for x in re.findall(r"\d+\.\d+", txt)]
        near = [c for c in cands if abs(c - EXPECTED) < TOL]
        if near:
            return near[0]
    return None


def test_per_subject_computed():
    rows = list(csv.DictReader(open(OUT / "per_subject.csv", encoding="utf-8")))
    assert len(rows) >= 5, f"expected 5 subjects, got {len(rows)}"
    ratios = [float(r["ratio"]) for r in rows if r.get("ratio") not in (None, "")]
    assert len(ratios) >= 5, "per-subject ratios missing"
    assert all(r > 0 for r in ratios), "ratios must be positive powers"
    # Berger direction: eyes-closed occipital alpha exceeds eyes-open for most subjects
    assert sum(r > 1.0 for r in ratios) >= 4, \
        f"eyes-closed should exceed eyes-open occipitally for most subjects, got {ratios}"


def test_berger_ratio_reproduced():
    # The occipital eyes-closed/eyes-open alpha ratio is ~19.6. A whole-head average
    # (~4.4) fails. Grade the reported headline ratio.
    r = _headline_ratio()
    assert r is not None, "no occipital alpha ratio reported in alpha_ratio.json / findings.md"
    assert abs(r - EXPECTED) < TOL, (
        f"reported occipital alpha ratio {r:.2f} is not the Berger occipital ratio "
        f"(expected ~{EXPECTED} +/- {TOL}). A whole-head / global average (~{NAIVE}) "
        f"dilutes the occipital effect and is not the requested occipital ratio.")
