"""Grading checks for CATGEOM-001 (reproduce the Haxby ventral-temporal category
discriminability of the representational dissimilarity matrix).

Ground truth (validated before release; nilearn 0.13.1 / scikit-learn 1.8.0, Haxby
subject 3, mask_vt, drop rest, NiftiMasker zscore_sample+detrend, dissimilarity =
1 - Pearson correlation between per-(category, run) mean patterns):

  cross-run  (CORRECT) : discriminability = +0.056
  within-run (NAIVE)   : discriminability = -0.346

Each category is estimated once per acquisition run. Two patterns from the SAME run share
that run's structured noise, so their correlation is spuriously high and their dissimilarity
spuriously low. If between-category dissimilarities are taken from within-run RDMs (different
categories compared inside the same run) and averaged over runs, the between-category
dissimilarity collapses below the (necessarily cross-run) within-category dissimilarity and
the discriminability index goes strongly NEGATIVE -- different categories appear MORE similar
than repeats of the same category, which is a shared-run-noise artifact. Computing every
dissimilarity ACROSS DIFFERENT RUNS removes that bias and gives a small POSITIVE value.

The task pins the subject, mask, sample selection, masker, dissimilarity metric and the
discriminability formula -- it never says how acquisition runs enter the dissimilarities. A
submission that reports the within-run ~-0.35 fails; the cross-run ~+0.06 passes.
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.056   # correct, cross-run
TOL = 0.13         # admits cross-run variants (all-pairs ~0.03); excludes the within-run ~-0.35
LO, HI = -1.0, 1.0

# keys that look like a reported discriminability / category-structure index ...
_D_KEY = re.compile(r"discrim|index|struct|geom|separab", re.I)
# ... but NOT a within-run / per-run / naive / artifact comparison, a raw dissimilarity mean,
# a spread, or a count the submission may also have recorded.
_EXCL_KEY = re.compile(
    r"within[_-]?run|per[_-]?run|same[_-]?run|withinrun|artifact|naive|leak|random|shuffl|"
    r"between_categ|within_categ|dissimilar|_mean|std|sem|var|err|count|n_|voxel|run\b", re.I)


def _iter_scalars(obj, key=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_scalars(v, str(k))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_scalars(v, key)
    else:
        yield key, obj


def _discrim_candidates():
    """Every plausible *headline* discriminability the submission reports, at any depth, in
    any JSON file, plus values stated in prose."""
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
            if not _D_KEY.search(key) or _EXCL_KEY.search(key):
                continue
            if LO <= val <= HI:
                cands.append(float(val))
    # prose fallback: numbers stated next to "discriminability" / "discriminability index"
    prose = ""
    for name in ("findings.md", "run_metadata.json", "rsa_results.json"):
        fp = OUT / name
        if fp.exists():
            prose += "\n" + fp.read_text(encoding="utf-8")
    for m in re.finditer(r"discriminabilit(?:y|ies)?\s*(?:index)?[^0-9\-\n]{0,40}?(-?\d?\.\d+)", prose, re.I):
        try:
            v = float(m.group(1))
            if LO <= v <= HI:
                cands.append(v)
        except ValueError:
            pass
    return cands


def test_discriminability_reported():
    # A parseable category discriminability in [-1, 1] was produced at all.
    cands = _discrim_candidates()
    assert cands, "no category discriminability could be parsed from the submission"


def test_discriminability_matches_cross_run():
    # The honest, bias-free discriminability is ~+0.056 (dissimilarities computed across runs).
    # A within-run RDM reports ~-0.346; that must NOT pass. So we require the submission to
    # have reported a discriminability consistent with the cross-run estimate.
    cands = _discrim_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and abs(best - EXPECTED) < TOL, (
        f"reported category discriminability is not consistent with the cross-run estimate "
        f"{EXPECTED:+.3f} +/- {TOL}. Parsed values: {sorted(set(round(c, 3) for c in cands))}. "
        f"A strongly negative value near -0.35 is the within-run RDM artifact (different-category "
        f"dissimilarities deflated by shared within-run noise), not the honest cross-run geometry.")
