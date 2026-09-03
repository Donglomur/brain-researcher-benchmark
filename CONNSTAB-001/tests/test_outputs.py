"""Grading checks for CONNSTAB-001 (within-run reproducibility of the resting-state
functional connectome on the ADHD-200 sample).

Ground truth (validated before release; nilearn 0.13.1, fetch_adhd n_subjects=40, MSDL atlas,
Pearson-correlation connectivity, Fisher-z edge vectors, mean over subjects):

  contiguous halves (CORRECT)      : reproducibility r = 0.712
  interleaved odd/even (INFLATED)  : reproducibility r = 0.876

BOLD frames are strongly autocorrelated. If the run is split into two halves by INTERLEAVING
frames (odd vs even, or any per-frame split), the two subsets sample the same slow
fluctuations, so their connectomes are near-duplicates and the reproducibility is inflated
(~0.88, higher in all 40 subjects). Splitting into two CONTIGUOUS, non-overlapping halves
makes the estimates temporally independent and yields the honest reproducibility (~0.71).

The task pins the subject set, atlas and connectivity and asks only for "how reproducible the
connectome is between the two halves of the run" -- it never names how the halves are formed.
A submission that reports the interleaved ~0.88 fails; a contiguous ~0.71 passes.
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.712    # correct, contiguous halves
TOL = 0.09          # admits contiguous variants (~0.62-0.80); excludes the interleaved ~0.87-0.88

# keys that look like a reported reproducibility / reliability correlation ...
_REL_KEY = re.compile(r"repro|reliab|stab|split[_-]?half|similar|corr", re.I)
# ... but NOT an interleaved / odd-even estimate, a spread, a count, or a per-subject list.
_EXCL_KEY = re.compile(
    r"interleav|odd|even|alternat|per[_-]?frame|inflat|"
    r"std|sd|sem|var|err|\bci\b|lower|upper|\bmin\b|\bmax\b|conf|"
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


def _repro_candidates():
    """Every plausible reported reproducibility correlation, at any depth, in any JSON file,
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
            if not _REL_KEY.search(key) or _EXCL_KEY.search(key):
                continue
            if -1.0 <= val <= 1.0:
                cands.append(float(val))
    prose = ""
    for name in ("findings.md", "run_metadata.json"):
        fp = OUT / name
        if fp.exists():
            prose += "\n" + fp.read_text(encoding="utf-8")
    for m in re.finditer(r"(?:reproducib\w*|reliab\w*)[^0-9\n]{0,40}?(-?0?\.\d+)", prose, re.I):
        cands.append(float(m.group(1)))
    for m in re.finditer(r"(-?0?\.\d+)[^0-9\n]{0,25}(?:reproducib\w*|reliab\w*)", prose, re.I):
        cands.append(float(m.group(1)))
    return [c for c in cands if -1.0 <= c <= 1.0]


def test_reproducibility_reported():
    # A parseable, positive reproducibility correlation was produced at all.
    cands = _repro_candidates()
    assert cands, "no connectome reproducibility value could be parsed from the submission"
    assert max(cands) > 0.2, (
        f"reported reproducibility values {sorted(set(round(c,3) for c in cands))} are implausibly "
        f"low -- the connectome was not compared between halves properly")


def test_reproducibility_uses_contiguous_split():
    # The honest between-halves reproducibility is ~0.712 (contiguous). An interleaved split
    # reports ~0.876; that must NOT pass. So we require a value consistent with the
    # contiguous estimate.
    cands = _repro_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and abs(best - EXPECTED) < TOL, (
        f"reported connectome reproducibility is not consistent with the contiguous-split "
        f"estimate {EXPECTED:.3f} +/- {TOL}. Parsed values: "
        f"{sorted(set(round(c,3) for c in cands))}. A value near 0.88 is the interleaved "
        f"odd/even split inflated by temporal autocorrelation, not the honest between-halves "
        f"reproducibility.")
