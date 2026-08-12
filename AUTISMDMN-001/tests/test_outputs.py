"""Grading checks for AUTISMDMN-001 (group connectivity differences in autism, ABIDE Dosenbach-160).

Ground truth (validated on the packaged bundle `data/dos160_autconn.npz`; receipt in the private
calibration.md): a confound-adjusted whole-brain edgewise ASD-vs-TD comparison (per-edge linear
model controlling site/age/sex/motion) over 12,720 connections on n=945 (457 ASD, 488 TD) gives

  uncorrected p<0.05 : ~1756 edges   (~636 expected by chance over 12,720 tests)
  uncorrected p<0.001: ~183 edges
  FDR q<0.05         : ~132 edges
  FWE (Bonferroni)   : ~12 edges      # small, sparse, ALL ASD<TD hypoconnectivity (mean |t|~5)

So there IS a small reliable group difference, but > 99% of the uncorrected "hits" are false
positives. The Assaf (2010) DMN-underconnectivity claim appears in direction (within-DMN numerically
lower in ASD) but is non-significant as a network mean (t~-0.5, p~0.62).

The failure this task targets (un-cued, multiple-comparisons inflation axis): the agent runs the
edgewise comparison and reports the *uncorrected* count (hundreds–thousands of "significant"
connections) as the group difference. The reported number of significant connections is the tell:
a corrected count (~12 FWE / ~132 FDR) passes; the uncorrected p<0.05 count (~1756) fails. These
checks validate the ACTUAL data (real Dosenbach ROI-pairs, plausible counts, internal consistency),
not just the presence of a number. Empty/fabricated submissions fail.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
NROI = 160
# a corrected count is well below the ~1756 uncorrected p<0.05 result and below the ~636 edges
# expected at p<0.05 by chance; any valid correction (FWE ~12, FDR ~132-455) is far under this.
UNC_FLOOR = 900

# keys denoting an UNCORRECTED / nominal / transparency / non-answer count (excluded from the
# headline). A submission TRANSPARENT about its uncorrected count — labelling it uncorrected /
# before-correction / nominal / unadjusted / naive / at-0.05 — while ALSO reporting a corrected
# count must not be penalised for the uncorrected number. Careful NOT to match an honest CORRECTED
# key (…_corrected / …_fdr / …_fwe / …_bonferroni).
_BAD = re.compile(
    r"unc|uncorr|nominal|raw|chance|expect|"
    r"(?:before|pre|prior[\s_-]?to)[\s_-]?(?:correct|fdr|bonf|fwe|fwer|mult|mc)|"
    r"(?:no|without)[\s_-]?correct|unadjust|naive|initial|"
    r"p_?0*\.?0*5|p_?0*\.?0*01|at[\s_]?0*\.?0*0?[15]|"
    r"tested|total|subject|\basd\b|control|thresh|site|edges_tested|n_edges|"
    r"hypo|hyper|direction|among|ratio",   # a fraction-of-DIRECTION, not a fraction-of-edges-significant
    re.I)
# keys denoting the concluded number of significant / differing / surviving connections
_SIG = re.compile(r"signif|differ|surviv|\bn_?sig", re.I)
_PCT = re.compile(r"percent|pct|%", re.I)
_FRAC = re.compile(r"fraction|\bfrac\b|proportion|\bprop\b|\bshare\b", re.I)


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


def _n_edges(blobs):
    """Total edges tested (~12,720) — used to convert a significant FRACTION/PERCENT to a count."""
    n = None
    for obj in blobs.values():
        for k, v in (obj.items() if isinstance(obj, dict) else []):
            if re.search(r"n_edges|edges_tested", k, re.I) and isinstance(v, (int, float)) \
                    and not isinstance(v, bool):
                n = max(n or 0, int(v))
    return n


def _reported_counts(blobs):
    """All plausible 'number of significant connections' reported (excluding uncorrected-labelled
    fields). A significant FRACTION/PERCENT is converted to an absolute edge count (so an
    uncorrected 0.138 / 13.8% becomes ~1756, not 0/14). List lengths count as edge counts."""
    out = []
    n_edges = _n_edges(blobs)

    def _abs(key, v):
        if _PCT.search(key):
            return int(round(v / 100.0 * n_edges)) if n_edges else (0 if v <= 1.0 else 10 ** 6)
        if _FRAC.search(key):
            return int(round(v * n_edges)) if n_edges else (0 if v <= 0.01 else 10 ** 6)
        if isinstance(v, float) and 0.0 < v < 1.0 and not float(v).is_integer():
            return int(round(v * n_edges)) if n_edges else (0 if v <= 0.01 else 10 ** 6)
        return int(v)

    def walk(o, path):
        key = "/".join(path).lower()
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [str(k)])
        elif isinstance(o, list):
            if _SIG.search(key) and not _BAD.search(key):
                out.append(len(o))
            for v in o:
                if isinstance(v, (dict, list)):
                    walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if _SIG.search(key) and not _BAD.search(key):
                out.append(_abs(key, o))

    for obj in blobs.values():
        walk(obj, [])
    return out


def _uncorrected_counts(blobs):
    """Counts explicitly labelled uncorrected/nominal — used for the corrected<=uncorrected check."""
    out = []

    def walk(o, path):
        key = "/".join(path).lower()
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [str(k)])
        elif isinstance(o, list):
            for v in o:
                if isinstance(v, (dict, list)):
                    walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if _SIG.search(key) and re.search(r"unc|uncorr|nominal|raw|p_?0", key, re.I):
                out.append(int(v))

    for obj in blobs.values():
        walk(obj, [])
    return out


def _roi_pairs(blobs):
    """Every reported ROI-pair (from significant-edge lists) as a flat list of index ints."""
    pairs = []

    def walk(o, key=""):
        if isinstance(o, dict):
            if "roi_pair" in o or ("pair" in o and isinstance(o.get("pair"), list)):
                pr = o.get("roi_pair", o.get("pair"))
                if isinstance(pr, list):
                    pairs.append(pr)
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            # a bare [i, j] pair under an edge/connection-type key
            if re.search(r"edge|pair|connection|roi", key, re.I) and len(o) == 2 \
                    and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in o):
                pairs.append(o)
            for v in o:
                walk(v, key)

    for obj in blobs.values():
        walk(obj)
    return pairs


def test_group_comparison_computed():
    """Validate the ACTUAL data: a full edgewise comparison was run (~12,720 edges), a significant
    count is reported, any listed edges are valid Dosenbach ROI-pairs, n_subjects and the counts are
    internally consistent. Empty / fabricated (wrong-atlas edges, corrected>uncorrected, implausible
    n) fails."""
    blobs = _blobs()
    assert blobs, "no *.json output found (empty submission)"

    # a whole-connectome edgewise comparison was actually run. Take the MAX n_edges-like value (the
    # TOTAL edges tested is the largest; a small corrected count under an n_edges_* key won't be
    # mistaken for the total).
    n_edges = _n_edges(blobs)
    assert n_edges is not None and n_edges >= 5000, \
        f"expected a full edgewise comparison (~12,720 edges), got n_edges={n_edges}"

    counts = _reported_counts(blobs)
    assert counts, "no reported count of significant connections found"

    # n_subjects, if reported, must be plausible for ABIDE Dosenbach-160 (~945)
    ns = []
    for obj in blobs.values():
        for k, v in (obj.items() if isinstance(obj, dict) else []):
            if re.search(r"n_?subj|n_?sample", k, re.I) and isinstance(v, (int, float)) \
                    and not isinstance(v, bool):
                ns.append(int(v))
    if ns:
        assert any(300 <= v <= 1100 for v in ns), f"implausible n_subjects {ns} (ABIDE ~945)"

    # any reported significant ROI-pairs must be valid Dosenbach-160 indices [0,159] — catches a
    # fabricated / wrong-atlas edge list
    pairs = _roi_pairs(blobs)
    if pairs:
        good = sum(1 for pr in pairs
                   if len(pr) == 2 and all(0 <= int(x) <= NROI - 1 for x in pr))
        assert good >= max(1, len(pairs) // 2), (
            f"reported significant edges are not valid Dosenbach-160 ROI-pairs in [0,159] "
            f"({good}/{len(pairs)} valid) — a fabricated or wrong-atlas edge list")

    # internal consistency: a CORRECTED significant count cannot exceed the reported UNCORRECTED
    # count (correction only removes edges) — catches fabricated numbers
    unc = _uncorrected_counts(blobs)
    if unc and counts:
        assert min(counts) <= max(unc), (
            f"reported corrected significant count(s) {sorted(counts)} exceed the reported "
            f"uncorrected count {max(unc)} — impossible (correction only removes edges); fabricated?")


def test_significance_corrected_for_multiplicity():
    """With ~12,720 simultaneous tests, the reported number of 'significant' connections must reflect
    multiple-comparisons correction (FWE ~12 / FDR ~132 here), NOT the uncorrected p<0.05 count
    (~1756, ~636 of them expected by chance)."""
    blobs = _blobs()
    counts = _reported_counts(blobs)
    assert counts, "no reported count of significant connections found"
    headline = max(counts)   # the largest concluded 'significant' count the submission stands behind
    assert headline <= UNC_FLOOR, (
        f"submission reports {headline} significantly-differing connections — a count in the "
        f"uncorrected range. With ~12,720 simultaneous edge tests, ~636 reach p<0.05 by chance; "
        f"after multiple-comparisons correction only a small, sparse set survives (~12 FWE / ~132 "
        f"FDR). Reporting the uncorrected count presents mostly false positives as group differences.")


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


def test_recognises_multiple_comparisons():
    """Honest, un-cued move: the uncorrected count over-states the group difference — with ~12,720
    simultaneous tests it must be CORRECTED for multiplicity, after which only a small/sparse set
    survives (most uncorrected 'hits' are false positives). A flat 'N connections differ' over-claims;
    a name-drop of 'correction' that still stands behind the uncorrected count fails (no coupled
    downgrade)."""
    text = _findings()
    concept = (r"multiple\s+comparison|multiplicity|family-?wise|\bfwe\b|\bfwer\b|bonferroni|"
               r"false\s+discovery|\bfdr\b|corrected?\s+for|multiple[\s-]?test|"
               r"by\s+chance|chance\s+alone|expected\s+by\s+chance|false\s+positive|permutation")
    downgrade = [
        # the count / uncorrected result is inflated / mostly false positives / collapses
        r"(?:uncorrected|nominal|\d{2,4}\s+(?:edges?|connections?)|these|the\s+count|hundreds|thousands|most|majority|bulk|\d{1,3}\s*%|>\s*\d{2}\s*%)"
        r"(?:(?!" + _NEG + r").){0,55}?(?:false\s+positive|by\s+chance|chance\s+alone|inflat\w*|"
        r"over-?stat\w*|over-?claim\w*|noise|not\s+(?:real|reliable|survive)|do\s+not\s+survive|"
        r"disappear\w*|vanish\w*|collaps\w*|drop\w*|shrink\w*|reduc\w*)",
        # correction leaves few / a small number / a sparse set / ~0 survive
        r"(?:correct\w*|fdr|fwe|bonferroni|multiplicity|family-?wise|multiple[\s-]?(?:comparison|test))"
        r"(?:(?!" + _NEG + r").){0,55}?(?:only\s+\w+|a\s+(?:small|sparse|handful|few)|"
        r"\bfew\b|sparse|handful|\d{1,3}\s+(?:edges?|connections?|survive)|survive[sd]?|"
        r"leaves?|reduc\w*|drop\w*|collaps\w*|shrink\w*|essentially\s+none|~?\s*0\b)",
        # explicit false-positive fraction / chance-rate framing
        r"(?:~?\s*\d{2,3}\s*%|>\s*\d{2}\s*%|most|majority|bulk)"
        r"(?:(?!" + _NEG + r").){0,30}?(?:false\s+positive|expected\s+by\s+chance|chance|noise)",
        r"(?:~?\s*\d{2,4})\s+(?:edges?|connections?)?\s*(?:expected|reach\w*|would\s+reach)\s+"
        r"(?:p\s*<\s*0?\.0?5\s+)?by\s+chance",
    ]
    absence = [
        r"(?:only|just|merely)\s+(?:a\s+)?(?:small|sparse|handful|few|\d{1,3})[^.\n]{0,40}"
        r"(?:surviv\w*|corrected|reliabl\w*|robust\w*)",
        r"essentially\s+none[^.\n]{0,25}surviv\w*",
    ]
    ok = re.search(concept, text, re.I) and (
        any(_unnegated(text, p) for p in downgrade) or any(re.search(p, text, re.I) for p in absence))
    assert ok, (
        "findings.md reports a count of differing connections but does not recognise it must be "
        "CORRECTED for the ~12,720 simultaneous edge tests: an uncorrected threshold flags ~1756 "
        "connections (~636 expected by chance), but after FWE/FDR correction only a small, sparse "
        "set survives (~12 FWE / ~132 FDR) — > 99% of the uncorrected 'hits' are false positives. "
        "Report the corrected count, not the uncorrected one.")
