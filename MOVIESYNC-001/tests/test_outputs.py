"""Grading checks for MOVIESYNC-001 (inter-subject correlation of the movie-evoked
visual-cortex response in the development_fmri cohort).

Ground truth (validated before release; nilearn 0.13.1, fetch_development_fmri n_subjects=40,
MSDL atlas, confound-cleaned, band-pass 0.01-0.1 Hz, mean over the three visual-cortex
regions ["Vis","Striate","Occ post"]):

  pairwise ISC  (CORRECT)          : 0.152
  leave-one-out ISC (INFLATED)     : 0.365     (chance ~ 0.0)

Inter-subject correlation can be estimated two ways. PAIRWISE ISC -- the mean Pearson
correlation between the movie time courses of every PAIR of participants -- is the
convention-invariant "correlation between participants" and is ~0.15 in visual cortex.
LEAVE-ONE-OUT ISC -- correlating each participant with the MEAN of the others -- builds a
high-SNR template that suppresses idiosyncratic noise, so it is systematically higher
(~0.37 here, about 2.4x) and is NOT comparable to the pairwise value (Nastase et al. 2019).

The task pins the dataset, atlas, region set, nuisance regression and band-pass and asks
only for "the inter-subject correlation" -- it never names the estimator. A submission that
reports the leave-one-out ~0.37 fails; a pairwise ~0.15 passes.
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.152    # correct, pairwise
TOL = 0.10          # admits pairwise variants (~0.05-0.25); excludes the leave-one-out ~0.30-0.40
CHANCE = 0.0

# keys that look like a reported inter-subject correlation ...
_ISC_KEY = re.compile(r"isc|inter[_-]?subject|synchron|corr", re.I)
# ... but NOT a leave-one-out / template estimate, a per-region breakdown we should not
# preferentially match, a chance level, a spread, or a count.
_EXCL_KEY = re.compile(
    r"leave|loo|one[_-]?out|template|inflat|mean[_-]?of[_-]?other|group[_-]?average|"
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


def test_isc_is_pairwise_not_leave_one_out():
    # The honest between-subject correlation in visual cortex is ~0.152 (pairwise). A
    # leave-one-out pipeline reports ~0.37; that must NOT pass. So we require the submission
    # to have reported a value consistent with the pairwise estimate.
    cands = _isc_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and abs(best - EXPECTED) < TOL, (
        f"reported inter-subject correlation is not consistent with the pairwise estimate "
        f"{EXPECTED:.3f} +/- {TOL} (chance {CHANCE}). Parsed values: "
        f"{sorted(set(round(c,3) for c in cands))}. A value near 0.37 is the leave-one-out "
        f"high-SNR-template artifact, not the correlation between two participants.")
