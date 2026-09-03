"""Grading checks for CATGEOM-001 (reproduce the Haxby ventral-temporal category
discriminability of the representational dissimilarity matrix).

Ground truth (validated before release on the real streamed data; nilearn 0.13.1 /
scikit-learn 1.8.0, Haxby subject 3, mask_vt, drop rest, NiftiMasker zscore_sample+detrend,
dissimilarity = 1 - Pearson correlation between per-(category, run) mean patterns, 12 runs):

  cross-run     (CORRECT, pooled)         : discriminability = +0.0563
  cross-run     (CORRECT, per-run-pair)   : discriminability = +0.0628
  all-pairs RDM (NAIVE, full RDM)         : discriminability = +0.0321   <- must NOT pass
  within-run    (NAIVE, per-run RDMs avg) : discriminability = -0.346

Each category is estimated once per acquisition run. Two patterns from the SAME run share
that run's structured noise, so their correlation is spuriously high and their dissimilarity
spuriously low. WITHIN-category dissimilarities are forced to be cross-run (a category appears
once per run), but BETWEEN-category dissimilarities can be taken same-run or cross-run -- and
that asymmetry is decisive. The naive analyst builds the full RDM over all (category, run)
patterns: its between-category set then MIXES IN the same-run pairs (~8% of them), whose shared
within-run noise deflates the mean between-category dissimilarity, so the discriminability sags
to ~+0.032. Taking the between-category dissimilarities from within-run RDMs only (per-run RDMs
averaged) is worse -- the between-category dissimilarity collapses below the within-category one
and the index goes strongly NEGATIVE (~-0.35), an artifact where different categories look MORE
similar than repeats of the same category. Computing every dissimilarity ACROSS DIFFERENT RUNS
-- matching the between-category run-structure to the within-category's -- removes the bias and
gives the honest small positive (~+0.056-0.063).

The task pins the subject, mask, sample selection, masker, dissimilarity metric and the
discriminability formula -- it never says how acquisition runs enter the dissimilarities. There
is a clean empty gap between the same-run-contaminated family (all-pairs +0.032 and lower;
within-run -0.35) and the fully-cross-run family (+0.056 to +0.063): any method that lets
same-run pairs into the between-category mean lands at +0.032 or below, any fully-cross-run
method lands at +0.056 or above. So a graded band of [+0.044, +0.15] fails BOTH naive answers
(the natural all-pairs RDM included) and passes every fully-cross-run estimate, including the
leave-one-run-out cross-validated variant (+0.134).
"""
import json
import math
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.056        # correct, fully cross-run (used only to pick the headline candidate)
# Asymmetric graded band. Floor sits in the empty gap (0.032, 0.056): it fails the natural
# all-pairs RDM (+0.0321) and the within-run artifact (-0.346), and passes every fully-cross-run
# estimate (pooled +0.056, per-run-pair +0.063, leave-one-run-out +0.134).
BAND_LO, BAND_HI = 0.044, 0.15
LO, HI = -1.0, 1.0      # sanity range for a parseable discriminability

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
    # The honest, bias-free discriminability is a small POSITIVE value obtained by computing every
    # dissimilarity ACROSS DIFFERENT RUNS (pooled +0.056, per-run-pair +0.063, leave-one-run-out
    # +0.134 -- all fully cross-run). Both same-run-contaminated answers must NOT pass: the natural
    # all-pairs full RDM (+0.032, between-category deflated by same-run pairs) and the within-run
    # RDM artifact (-0.346). The graded band [+0.044, +0.15] sits in the empty gap between the two
    # families. `best` is the reported candidate nearest the cross-run value, so a run that also
    # records a naive contrast is judged on its cross-run number.
    cands = _discrim_candidates()
    best = min(cands, key=lambda c: abs(c - EXPECTED)) if cands else None
    assert best is not None and BAND_LO <= best <= BAND_HI, (
        f"reported category discriminability {best if best is not None else 'None'} is not in the "
        f"fully-cross-run band [{BAND_LO:+.3f}, {BAND_HI:+.3f}]. Parsed values: "
        f"{sorted(set(round(c, 3) for c in cands))}. A value near +0.03 is the natural all-pairs RDM "
        f"(its between-category dissimilarities are deflated by same-run pairs that share within-run "
        f"noise); a strongly negative value near -0.35 is the within-run RDM artifact. The honest "
        f"geometry compares patterns only across different acquisition runs and is ~+0.056-0.063.")
