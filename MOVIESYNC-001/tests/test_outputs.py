"""Grading checks for MOVIESYNC-001 (inter-subject correlation of the movie-evoked
visual-cortex response in the development_fmri cohort).

This is a clean REPRODUCTION / easy-control task: measure the inter-subject correlation
(ISC) of the movie-driven BOLD response in visual cortex on the pinned dataset/atlas/
preprocessing, and report it.

Ground truth (validated before release; nilearn 0.13.1, fetch_development_fmri n_subjects=40,
MSDL atlas, confound-cleaned, band-pass 0.01-0.1 Hz, mean over the three visual-cortex
regions ["Vis","Striate","Occ post"]):

  pairwise ISC        : 0.152     (mean Pearson r between every pair of participants)
  leave-one-out ISC   : 0.365     (each participant vs the mean of the others)
  chance              : ~0.0

BOTH are standard, defensible ISC estimators (Nastase et al. 2019, SCAN). Pairwise ISC is
the average correlation between pairs of participants; leave-one-out ISC correlates each
participant with the average of the rest (a higher-SNR template, so it is systematically
larger). The instruction now states explicitly that EITHER estimator is acceptable, so this
grader accepts any legitimate above-chance visual-cortex ISC in the plausible band and only
fails a wrong quantity (chance / a degenerate near-unity value / an implausible number).
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

CHANCE = 0.0
# Both standard estimators must land inside this band: pairwise ~0.152, leave-one-out ~0.365.
# The band is wide enough to admit reasonable variants of either estimator, and tight enough
# to exclude a wrong quantity: a chance-level value (~0, region/pipeline error) below it, and
# a degenerate near-unity value (~1, e.g. a self-correlation / undropped-diagonal bug) above.
ISC_MIN = 0.05
ISC_MAX = 0.60

# keys that look like a reported inter-subject correlation ...
_ISC_KEY = re.compile(r"isc|inter[_-]?subject|synchron|corr", re.I)
# ... but NOT a chance level, a spread, a bound, or a count (per-region and leave-one-out
# values are legitimate ISC estimates here and are intentionally NOT excluded).
_EXCL_KEY = re.compile(
    r"chance|std|sem|var|err|\bci\b|lower|upper|\bmin\b|\bmax\b|conf|"
    r"n_|count|subject|timepoint|region", re.I)


def _iter_scalars(obj, key=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_scalars(v, str(k))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_scalars(v, key)
    else:
        yield key, obj


def _isc_candidates():
    """Every plausible reported inter-subject correlation, at any depth, in any JSON file,
    plus correlations stated in prose."""
    cands = []
    for p in sorted(OUT.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for key, val in _iter_scalars(obj):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                continue
            if not math.isfinite(val):
                continue
            if not _ISC_KEY.search(key) or _EXCL_KEY.search(key):
                continue
            if -1.0 <= val <= 1.0:
                cands.append(float(val))
    prose = ""
    for name in ("findings.md", "run_metadata.json"):
        fp = OUT / name
        if fp.exists():
            prose += "\n" + fp.read_text(encoding="utf-8")
    for m in re.finditer(r"(?:inter[- ]?subject correlation|isc)[^0-9\n]{0,40}?(-?0?\.\d+)", prose, re.I):
        cands.append(float(m.group(1)))
    for m in re.finditer(r"(-?0?\.\d+)[^0-9\n]{0,25}(?:inter[- ]?subject correlation|isc)", prose, re.I):
        cands.append(float(m.group(1)))
    return [c for c in cands if -1.0 <= c <= 1.0]


def test_isc_reported():
    # A parseable, above-chance inter-subject correlation was produced at all.
    cands = _isc_candidates()
    assert cands, "no inter-subject correlation could be parsed from the submission"
    assert max(cands) > CHANCE + 0.03, (
        f"reported ISC values {sorted(set(round(c,3) for c in cands))} are at/below chance "
        f"({CHANCE}) -- the analysis did not recover a movie-driven response")


def test_isc_is_a_valid_visual_estimate():
    # Accept ANY legitimate visual-cortex ISC estimate. Pairwise (~0.152) and leave-one-out
    # (~0.365) are both standard and both PASS; the task no longer discriminates between them.
    # A wrong quantity fails: a chance-level value (below the band, e.g. a region/pipeline
    # error) or a degenerate near-unity value (above the band, e.g. a self-correlation bug).
    cands = _isc_candidates()
    in_band = [c for c in cands if ISC_MIN <= c <= ISC_MAX]
    assert in_band, (
        f"no reported inter-subject correlation falls in the valid visual-cortex band "
        f"[{ISC_MIN}, {ISC_MAX}] (chance {CHANCE}). Parsed values: "
        f"{sorted(set(round(c,3) for c in cands))}. A value near 0 means the movie-driven "
        f"response was not recovered; a value near 1 is a degenerate self-correlation "
        f"artifact, not an inter-subject correlation.")
