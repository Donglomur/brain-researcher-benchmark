"""Grading checks for NETSEG-001.

Ground truth (established in Step-0 on nilearn `fetch_development_fmri` (40 participants),
Schaefer-2018 100-region / 7-network connectomes; provided confounds regressed, parcel time
series detrended and z-scored):

  System segregation (Chan et al. 2014) = (mean_within - mean_between) / mean_within on the
  Fisher-z Pearson connectome, POSITIVE edges only:
    cohort-mean segregation ~0.374  (children ~0.35, adults ~0.47 -- segregation matures)
  Stable across reasonable preprocessing WITH the confounds regressed (0.35 no-detrend, 0.40
  band-passed).

The un-cued crux is the handling of anti-correlations (negative edges). System segregation is
defined on the positive edges; the negative correlations sit mostly BETWEEN networks, so
including them pulls `mean_between` negative and INFLATES segregation by ~half:
    include all edges (negatives kept)   -> cohort mean ~0.55  (+~50 %)
That inflated value is not comparable to the segregation literature -- it manufactures
apparent segregation out of anti-correlation. A magnitude band therefore separates the
positive-edge segregation (~0.37) from the all-edges version (~0.55) mechanically; a run that
also skips the confound regression lands even lower (~0.31 all-edges), outside the band too.
"""
import csv
import json
import os
import re
import statistics
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _seg_values():
    p = OUT / "segregation.csv"
    if not p.exists():
        return []
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    if not rows:
        return []

    def norm(s):
        return re.sub(r"[^a-z]", "", s.lower())
    col = None
    for c in rows[0].keys():
        n = norm(c)
        if "segregation" in n or n in ("seg", "sseg", "s"):
            col = c
            break
    if col is None:
        return []
    vals = []
    for r in rows:
        try:
            vals.append(float(r[col]))
        except (TypeError, ValueError):
            continue
    return vals


def _meta():
    p = OUT / "run_metadata.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _find_numbers(obj, key_substr):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if key_substr in str(k).lower() and isinstance(v, (int, float)) and not isinstance(v, bool):
                found.append(float(v))
            found += _find_numbers(v, key_substr)
    elif isinstance(obj, list):
        for v in obj:
            found += _find_numbers(v, key_substr)
    return found


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def _cohort_mean():
    vals = _seg_values()
    if len(vals) >= 30:
        return statistics.fmean(vals), len(vals)
    # fall back to a reported cohort mean in run_metadata
    m = _find_numbers(_meta(), "segregation_mean") or _find_numbers(_meta(), "mean")
    m = [x for x in m if 0.0 < x < 1.5]
    if m:
        return float(m[0]), len(vals)
    return (statistics.fmean(vals) if vals else float("nan")), len(vals)


def test_segregation_present():
    vals = _seg_values()
    assert len(vals) >= 30, \
        f"expected per-participant system segregation for the ~40-participant cohort, got {len(vals)}"
    assert all(-0.5 <= v <= 1.0 for v in vals), \
        f"system segregation values outside a plausible range: {vals[:5]}..."
    # a real per-subject estimate varies across the cohort (not a constant / fill)
    assert statistics.pstdev(vals) > 1e-3, \
        "segregation is identical across participants -- it was not computed per subject"
    # a within-vs-between network segregation analysis must actually be named
    txt = _text()
    assert re.search(r"segregation|within[- ]?network|between[- ]?network|within[- ]?system|"
                     r"between[- ]?system", txt), \
        "no within-vs-between network segregation analysis is named anywhere"


def test_reproduces_segregation():
    mean, n = _cohort_mean()
    # Reproduction: system segregation is defined on the POSITIVE edges (Chan 2014). The
    # positive-edge cohort mean is ~0.37. Keeping the anti-correlations inflates it to ~0.55
    # (negatives sit mostly between networks); dropping the confound regression on top of that
    # lands ~0.31. Both fall outside the band that the defined (positive-edge) measure yields.
    assert 0.32 <= mean <= 0.47, (
        f"cohort-mean system segregation {mean:.3f} is outside the validated band [0.32, 0.47]. "
        "A value near ~0.55 means the anti-correlations (negative edges) were kept in the "
        "between-network mean, which inflates segregation by ~half; system segregation is "
        "defined on the positive edges only (Chan et al. 2014). Regress the provided confounds, "
        "and set the negative edges aside before forming the within/between means.")


def test_reports_edge_sign_handling():
    # The over-claim this task targets, graded as an explicit DISCLOSURE. System segregation is
    # DEFINED on the positive edges (Chan et al. 2014); the anti-correlations sit predominantly
    # BETWEEN networks, so silently keeping them pulls `mean_between` negative and inflates
    # segregation by ~half (~0.55 vs ~0.37) -- a value not comparable to the literature that
    # manufactures apparent segregation out of anti-correlation. A defensible answer VOLUNTEERS how
    # it handled the negative edges (positive edges only / anti-correlations set aside). This is
    # graded as an explicit edge-sign disclosure, NOT the trivial within/between wording that every
    # segregation description contains (that escape was removed -- it let a silent all-edges run
    # pass). GUARD: the disclosure must accompany an actual segregation result, not a bare keyword.
    text = _text()
    has_result = re.search(r"segregation[^.\n]{0,40}[-+]?\d?\.\d|[-+]?\d?\.\d\d[^.\n]{0,40}"
                           r"segregation|segregation_mean", text)
    # explicit edge-sign disclosure -- unambiguous handling of the correlation sign, not generic
    # within/between segregation prose
    edge_sign = re.search(
        r"positive[- ]?edge|positive[- ]?(correlation|weight|connection|tie|value|fc)|"
        r"anti[- ]?correlation|negative[- ]?(edge|correlation|weight|connection|tie|value|fc)|"
        r"positive edges only|set aside|"
        r"(thresh\w*|clip\w*|floor\w*|rectif\w*)[^.\n]{0,25}(zero|0|negativ)|"
        r"(exclud\w*|remov\w*|discard\w*|drop\w*|ignor\w*|zero\w*|set|keep only|only the|retain\w*)"
        r"[^.\n]{0,20}(negativ|anti[- ]?correl|positive)|"
        r"(negativ\w*|anti[- ]?correl\w*)[^.\n]{0,25}"
        r"(exclud|remov|discard|drop|ignor|set aside|zero|thresh|clip)|"
        r"absolute value|\|r\|", text)
    assert has_result and edge_sign, (
        "findings/run_metadata do not DISCLOSE how the anti-correlations (negative edges) were "
        "handled. System segregation is defined on the positive edges (Chan et al. 2014); silently "
        "keeping the negatives inflates it by ~half (~0.55 vs ~0.37, since anti-correlations sit "
        "mostly between networks). State the edge-sign handling (e.g. positive edges only / "
        "negatives set aside) alongside the reported segregation value.")
