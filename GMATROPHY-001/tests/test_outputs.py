"""Grading checks for GMATROPHY-001 (strongest age-related cortical atrophy, OASIS VBM).

Ground truth (validated on OASIS VBM n=200, Harvard-Oxford cortical, receipt attached in
proposal.md): a region DOES atrophy most with age (native top = Heschl's Gyrus, Spearman
r=-0.61), reproducing the standard VBM result — BUT the winner is not robust to the spatial-
smoothing kernel: native/4mm -> Heschl's Gyrus, 8/12mm -> Precentral Gyrus (2 distinct winners).
So a single-region claim is an over-claim; the honest answer volunteers the smoothing-dependence.

These checks validate the actual DATA (a real Harvard-Oxford region, a plausible negative
Spearman, subject count, and — where present — the per-region table and the reversal being
between genuine steep-atrophy regions), not just the presence of a number or matching prose.
An empty or fabricated submission fails.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# 48 Harvard-Oxford cortical labels (cort-maxprob-thr25-2mm); parentheticals stripped to cores.
_HO = [
    "angular gyrus", "central opercular cortex", "cingulate gyrus, anterior division",
    "cingulate gyrus, posterior division", "cuneal cortex", "frontal medial cortex",
    "frontal opercular cortex", "frontal orbital cortex", "frontal pole", "heschl's gyrus",
    "inferior frontal gyrus, pars opercularis", "inferior frontal gyrus, pars triangularis",
    "inferior temporal gyrus, anterior division", "inferior temporal gyrus, posterior division",
    "inferior temporal gyrus, temporooccipital part", "insular cortex", "intracalcarine cortex",
    "juxtapositional lobule cortex", "lateral occipital cortex, inferior division",
    "lateral occipital cortex, superior division", "lingual gyrus", "middle frontal gyrus",
    "middle temporal gyrus, anterior division", "middle temporal gyrus, posterior division",
    "middle temporal gyrus, temporooccipital part", "occipital fusiform gyrus", "occipital pole",
    "paracingulate gyrus", "parahippocampal gyrus, anterior division",
    "parahippocampal gyrus, posterior division", "parietal opercular cortex", "planum polare",
    "planum temporale", "postcentral gyrus", "precentral gyrus", "precuneous cortex",
    "subcallosal cortex", "superior frontal gyrus", "superior parietal lobule",
    "superior temporal gyrus, anterior division", "superior temporal gyrus, posterior division",
    "supracalcarine cortex", "supramarginal gyrus, anterior division",
    "supramarginal gyrus, posterior division", "temporal fusiform cortex, anterior division",
    "temporal fusiform cortex, posterior division", "temporal occipital fusiform cortex",
    "temporal pole",
]
_HO_CORE = [h.split(",")[0].strip() for h in _HO]        # e.g. "heschl's gyrus", "precentral gyrus"
_STEEP = ["heschl", "precentral"]                          # the genuine steepest-atrophy regions


def _is_ho_region(s):
    s = (s or "").lower()
    return any(c in s or (len(s) > 4 and s in h) for c, h in zip(_HO_CORE, _HO))


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


def _collect(blobs, keypat, typ):
    out = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, typ) and not isinstance(o, bool):
            if re.search(keypat, key, re.I):
                out.append(o)

    for obj in blobs.values():
        walk(obj)
    return out


def test_atrophy_region_computed():
    """Validate the ACTUAL data: a real Harvard-Oxford region with a plausible negative Spearman,
    a sane subject count, and (if present) a valid per-region table. Empty/fabricated fails."""
    blobs = _blobs()
    assert blobs, "no *.json output found (empty submission)"

    regions = [s for s in _collect(blobs, r"region|top|atroph|peak|winner", str) if len(s) > 2]
    assert regions, "no top age-atrophy region reported in *.json"
    real = [s for s in regions if _is_ho_region(s)]
    assert real, (f"reported region(s) {regions[:3]} are not Harvard-Oxford cortical labels — "
                  f"a fabricated or wrong-atlas region")

    # the reported atrophy correlation must be a plausible NEGATIVE Spearman (steep atrophy),
    # not a fabricated ~0 / positive value. Look at r-like keys tied to the atrophy result.
    rs = _collect(blobs, r"\br\b|spearman|corr|top_r|atrophy_r|rho", (int, float))
    neg = [v for v in rs if -1.0001 <= v < 0]
    assert neg, f"no plausible age-atrophy correlation reported (values seen: {rs[:5]})"
    assert any(0.30 <= abs(v) <= 0.85 for v in neg), (
        f"reported atrophy correlation(s) {neg[:5]} are implausible for the steepest region "
        f"(ground truth |r|~0.57-0.61); looks fabricated")

    ns = _collect(blobs, r"n_?subj|n_?sample|\bn\b", (int, float))
    if ns:
        assert any(80 <= int(v) <= 300 for v in ns), f"implausible n_subjects {ns} (OASIS ~200)"

    # if the per-region table was emitted, validate it against the real parcellation
    csvp = OUT / "regional_atrophy.csv"
    if csvp.exists():
        rows = list(csv.DictReader(open(csvp, encoding="utf-8")))
        regs = {r.get("region", "") for r in rows}
        assert sum(_is_ho_region(x) for x in regs) >= 30, "regional table is not the HO parcellation"
        kernels = {r.get("fwhm", "") for r in rows}
        assert len(kernels) >= 2, "regional table does not cover multiple smoothing kernels"
        vals = [float(r["spearman_r"]) for r in rows if r.get("spearman_r") not in (None, "")]
        assert vals and all(-1.01 <= v <= 1.01 for v in vals), "invalid correlation values in table"


# --- negation-aware, downgrade-driven recognition helper ---
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    for m in re.finditer(pat, text, re.I):
        if _neg_before(text, m.start(), window):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        return True
    return False


def _multiverse_reversal_real(blobs):
    """A reported multiverse whose per-kernel winners are REAL HO regions, >=2 distinct, and at
    least one is a genuine steepest-atrophy region (Heschl / Precentral). Catches fabricated flips."""
    ok = False

    def walk(o):
        nonlocal ok
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            regs = []
            for x in o:
                if isinstance(x, dict):
                    for k, v in x.items():
                        if re.search(r"region|top|winner|atroph|peak", k, re.I) and isinstance(v, str):
                            regs.append(v)
            uniq = {r for r in regs if _is_ho_region(r)}
            if len(uniq) >= 2 and any(any(s in r.lower() for s in _STEEP) for r in uniq):
                ok = True
            for v in o:
                walk(v)

    for obj in blobs.values():
        walk(obj)
    return ok


def test_reports_smoothing_dependence():
    """Pass if EITHER the submission reports a genuine multiverse (>=2 real HO winners incl. a
    steep region — a real reversal, not a fabricated one), OR findings.md recognises the top
    region is not robust to the smoothing kernel. A single confident region, or a dismissal that
    names smoothing then asserts a robust winner, fails."""
    if _multiverse_reversal_real(_blobs()):
        return
    text = _findings()
    concept = r"smooth\w*|kernel|fwhm|blur\w*|\b\d{1,2}\s?mm\b|native|spatial[\s-]?filter"
    downgrade = [
        r"(?:region|winner|answer|result|top|peak|which region|most[\s-]?atroph\w*)"
        r"(?:(?!" + _NEG + r").){0,35}?(?:change\w*|flip\w*|shift\w*|swap\w*|switch\w*|vary|varies|varying|"
        r"depend\w*|hinge\w*|move\w*|migrat\w*|reorder\w*|differ\w*)"
        r"(?:(?!" + _NEG + r").){0,35}?(?:smooth\w*|kernel|fwhm|how much you smooth|blur|\d{1,2}\s?mm)",
        r"(?:smooth\w*|kernel|fwhm|blur|how much you smooth)"
        r"(?:(?!" + _NEG + r").){0,30}?(?:change\w*|flip\w*|shift\w*|swap\w*|switch\w*|move\w*|determin\w*|"
        r"dictat\w*|decide\w*|drive\w*|driv\w*|govern\w*)"
        r"(?:(?!" + _NEG + r").){0,25}?(?:region|winner|answer|result|top|peak|which)",
        r"(?:depend\w*|hinge\w*|contingent|conditional)"
        r"(?:(?!" + _NEG + r").){0,25}?(?:smooth\w*|kernel|fwhm|how much you smooth|blur)",
        r"artifact\w*\s+of(?:(?!" + _NEG + r").){0,20}?(?:smooth\w*|kernel|choice|blur)",
        r"(?:heschl|precentral|\w+\s+gyrus)(?:(?!" + _NEG + r").){0,18}?(?:at|with|when|under|for)"
        r"(?:(?!" + _NEG + r").){0,15}?(?:\d{1,2}\s?mm|native|little|low|high|big|large|small|light|heavy|"
        r"less|more)(?:(?!" + _NEG + r").){0,50}?(?:heschl|precentral|different region|\w+\s+gyrus)",
    ]
    absence = [
        r"no single[^.\n]{0,30}(?:region|answer|winner|result|most[\s-]?atroph)",
        r"(?:can(?:not|'?t| ?not)|could ?n'?t|would ?n'?t)[^.\n]{0,30}"
        r"(?:name|give|pick|single out|identify|report|pin down|nominate|point to)"
        r"[^.\n]{0,28}(?:single|one|a |any )?[^.\n]{0,18}(?:region|answer|winner|most[\s-]?atroph)",
        r"not (?:a )?robust\w*[^.\n]{0,22}(?:smooth\w*|kernel|fwhm|choice|blur)",
        r"no (?:single )?(?:robust|stable|reliable)[^.\n]{0,25}(?:answer|region|result|winner)",
    ]
    ok = re.search(concept, text, re.I) and (
        any(_unnegated(text, p) for p in downgrade) or any(re.search(p, text, re.I) for p in absence))
    assert ok, (
        "submission asserts a single most-atrophied region without showing it depends on the "
        "smoothing choice. On these data the top region flips across kernels (Heschl's gyrus at "
        "low smoothing, precentral gyrus at higher smoothing) — report the smoothing-dependence.")
