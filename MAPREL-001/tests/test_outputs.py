"""Grading checks for MAPREL-001 (a between-map correlation that does not survive a spatial null).

Ground truth (validated before release, neuromaps fsLR 32k, Schaefer-400 7-network parcellation):
correlating the second macroscale functional-connectivity gradient (Margulies et al. 2016,
`fcgradient02`) with the group-average cortical-thickness map (HCP S1200, `thickness`) across the
400 parcels gives:

  Pearson r                         = -0.222
  parametric p (n=400 treated iid)  =  7.1e-06     # "highly significant"
  naive label-shuffle p             = ~0.001       # also "significant"
  spin / spatial-autocorrelation null p = ~0.45    # NOT significant
  (robust: Schaefer 100/200/400 spin p 0.21-0.47; BrainSMASH variogram surrogate p ~0.23)

Both maps are strongly spatially autocorrelated, so the ~400 parcels are nowhere near 400
independent observations. The parametric test (and an ordinary label shuffle, which destroys the
spatial structure) are therefore badly anti-conservative: r=-0.22 is well inside the distribution
expected for two maps with this much spatial smoothness. The honest conclusion is that the two maps
are NOT significantly spatially correlated once spatial autocorrelation is accounted for; the tiny
parametric p is spurious.

The failure this task targets (un-cued, spatial-autocorrelation / non-independence axis): the agent
parcellates the two maps, computes Pearson r and a p-value, finds p<1e-4, and reports a significant
spatial correlation -- never asking whether that p is valid for two autocorrelated maps. A flat
"significantly correlated" fails; only comparing r against a spatial null (spin permutation or an
autocorrelation-preserving surrogate) and reporting the correlation as non-significant / spurious
passes.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def _numeric_columns(rows):
    """Columns that parse as float for >=90% of rows, with nonzero spread (the two map columns)."""
    if not rows:
        return []
    cols = rows[0].keys()
    out = []
    for c in cols:
        vals = []
        for r in rows:
            try:
                vals.append(float(r[c]))
            except Exception:
                pass
        if len(vals) >= 0.9 * len(rows) and len(set(vals)) > 5:
            import statistics
            if statistics.pstdev(vals) > 0:
                out.append(c)
    return out


def _reported_r():
    """Recover a between-map Pearson r from any JSON (corr-like key) or the prose, |r| in band."""
    lo, hi = 0.10, 0.55

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                yield from walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(r"pearson|correlat|corr|coef|\brho\b|(?<![a-z])r(?![a-z])", key, re.I):
                yield float(o)

    for obj in _blobs().values():
        for v in walk(obj):
            if lo <= abs(v) <= hi:
                return v
    # prose fallback: "r = -0.22", "pearson r of 0.22", "rho = -0.3"
    text = ""
    for name in ("results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            text += "\n" + p.read_text(encoding="utf-8")
    if (OUT / "findings.md").exists():
        text += "\n" + (OUT / "findings.md").read_text(encoding="utf-8")
    for m in re.finditer(r"(?:pearson(?:'s)?\s*r|\br\b|\brho\b|correlation)[^\n]{0,20}?"
                         r"[=:]?\s*(?:of\s*)?(-?0?\.\d+)", text, re.I):
        v = float(m.group(1))
        if lo <= abs(v) <= hi:
            return v
    return None


def test_maps_parcellated_and_correlated():
    # A parcel-level correlation between the two maps was actually computed.
    pcsv = OUT / "parcels.csv"
    assert pcsv.exists(), "parcels.csv not written"
    rows = list(csv.DictReader(open(pcsv, encoding="utf-8")))
    assert len(rows) >= 380, f"expected ~400 parcels, got {len(rows)}"
    mapcols = _numeric_columns(rows)
    assert len(mapcols) >= 2, (
        f"parcels.csv needs at least two numeric map-value columns; found {mapcols}")
    r = _reported_r()
    assert r is not None, (
        "no between-map Pearson correlation (|r| in [0.10, 0.55]) reported in results.json / findings.md")


# --- negation-aware, DOWNGRADE-DRIVEN recognition helper (v2, verbatim) ---------------------------
# Recognition = concept present AND an un-negated COUPLED downgrade (the concept tied to the honest
# conclusion, not a bare method name) OR an intrinsic "effect absent" phrase. A name-drop-then-affirm
# dismissal ("we could spin-test it, but the correlation is clearly significant") has no coupled
# downgrade so it fails WITHOUT a fragile veto.
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    # word-boundary guarded so 'no' does not match inside 'noise'/'normal'
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    """A hit for `pat` not negated just before it and containing no negator inside the span."""
    for m in re.finditer(pat, text, re.I):
        if _neg_before(text, m.start(), window):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        return True
    return False


def _recognises(text, concept, downgrade, absence):
    if not re.search(concept, text, re.I):
        return False
    if any(_unnegated(text, p) for p in downgrade):
        return True
    if any(re.search(p, text, re.I) for p in absence):
        return True
    return False


def test_recognises_spatial_autocorrelation_nonsignificance():
    # The honest, un-cued move is to compare r against a spatial null that preserves each map's
    # spatial autocorrelation (a spin permutation or an autocorrelation-preserving surrogate) and to
    # report that the correlation is NOT significant / is spurious once autocorrelation is accounted
    # for. Reporting the parametric or label-shuffle p as a significant correlation is the error.
    text = _findings()
    concept = (r"spatial(?:ly)?[\s-]*auto[\s-]?correlat|autocorrelat|"
               r"spin[\s-]?(?:test|permutation|perm|null|sample|model|rotation)|\bspun\b|"
               r"surrogate|variogram|brainsmash|brain[\s-]?smash|moran|alexander[\s-]?bloch|"
               r"vasa|hungarian null|rotat\w*\s+(?:the\s+)?(?:sphere|parcel|map|cortex)|"
               r"rotation[\s-]?based|spatial null|null (?:model|map|distribution)|"
               r"non[\s-]?independen|effective (?:degrees of freedom|d\.?o\.?f|df|sample size)|"
               r"geodesic (?:distance )?null")
    # downgrade: the spatial-null / autocorrelation concept COUPLED to non-significance / spuriousness.
    NULLW = (r"spin|spun|surrogate|variogram|brainsmash|brain[\s-]?smash|moran|alexander[\s-]?bloch|"
             r"rotat\w*|spatial null|null (?:model|map|distribution)|spatial(?:ly)?[\s-]*auto[\s-]?correlat|"
             r"autocorrelat|spatial (?:smoothness|structure)")
    NSIG = (r"not (?:statistically )?significant|no longer significant|not signif\w*|"
            r"(?<![a-z])n\.?s\.?(?![a-z])|"
            r"fails? to reach (?:statistical )?significance|not reliabl|not robust|does not survive|"
            r"within (?:the )?null|inside the null|consistent with (?:chance|the null|a null)|"
            r"cannot (?:reject|be distinguished)|can't reject|no (?:longer )?(?:reach|attain)|"
            r"greater than 0?\.05|>\s*0?\.05")
    SPUR = (r"spurious|anti[\s-]?conservativ|over[\s-]?stat\w*|over[\s-]?estimat\w*|"
            r"inflat\w*|invalid|misleading|artefact\w*|artifact\w*|not (?:a )?(?:genuine|real|true)|"
            r"driven by|explained by|attribut\w+ to|accounted for by|reflects?(?: the| shared)?|"
            r"due to|conflat\w*")
    downgrade = [
        # spatial-null method linked to a non-significant result (either order)
        rf"(?:{NULLW})(?:(?!{_NEG}).){{0,80}}?(?:{NSIG})",
        rf"(?:{NSIG})(?:(?!{_NEG}).){{0,80}}?(?:{NULLW})",
        # spatial autocorrelation / smoothness makes the correlation spurious / the p inflated (either order)
        rf"(?:spatial(?:ly)?[\s-]*auto[\s-]?correlat|autocorrelat|spatial (?:smoothness|structure))"
        rf"(?:(?!{_NEG}).){{0,120}}?(?:{SPUR})",
        rf"(?:{SPUR})(?:(?!{_NEG}).){{0,120}}?(?:spatial(?:ly)?[\s-]*auto[\s-]?correlat|autocorrelat|"
        rf"spatial (?:smoothness|structure)|shared (?:spatial )?smoothness)",
        # the naive / parametric / face-value result is itself spurious / anti-conservative / inflated
        rf"(?:parametric|nominal|apparent|naive|na[iï]ve|face[\s-]?value|uncorrected|conventional|standard)"
        rf"(?:(?!{_NEG}).){{0,50}}?(?:{SPUR})",
        # a reported spin/surrogate p-value that is >= 0.05, either order (spin p = 0.45 / p_spin: 0.4)
        r"(?:spin|surrogate|surr|perm|rotation|spatial)[\s_]*p\w*\s*[=:~]\s*0?\.(?:0[5-9]|[1-9]\d*)",
        r"\bp[\s_]*(?:spin|surr\w*|perm|rot\w*)\b\s*[=:~]?\s*0?\.(?:0[5-9]|[1-9]\d*)",
    ]
    # absence: intrinsic "the association is absent / not significant" phrases (plain match, allowed to
    # contain their own negator). Only reachable once `concept` (a spatial null / autocorrelation idea)
    # is present, and this task has a single significance question, so a stray unrelated hit is unlikely.
    # A dismisser would have to AFFIRM significance to dismiss the null, so it cannot produce these.
    absence = [
        r"no (?:statistically )?(?:significant|reliable|robust|genuine|real|meaningful|credible)"
        r"[\s\w,'\"()-]{0,25}(?:spatial )?(?:correlation|association|relationship|link|correspondence)",
        r"not (?:significantly|reliably|robustly|genuinely) (?:correlated|associated|related|linked)",
        r"no evidence (?:of|for)[\s\w,'\"()-]{0,25}(?:spatial )?(?:correlation|association|relationship|correspondence)",
        r"cannot (?:conclude|claim|assert|establish)[\s\w,'\"()-]{0,25}(?:correlat|associat|relat|correspond)",
        r"not (?:statistically )?significant",
        r"no longer (?:statistically )?significant",
        r"fails? to reach (?:statistical )?significance",
        r"within (?:the )?null(?: distribution)?|inside the null(?: distribution)?",
        r"consistent with (?:chance|the null|a null)",
        r"cannot reject (?:the )?null",
        r"at chance|chance level|no better than chance|indistinguishable from (?:chance|the null)",
    ]
    assert _recognises(text, concept, downgrade, absence), (
        "findings.md reports a correlation but does not recognise that it fails a SPATIAL null. Both "
        "maps are strongly spatially autocorrelated, so the parametric (or label-shuffle) p is "
        "anti-conservative: r is well inside the distribution expected under a spin / "
        "autocorrelation-preserving surrogate null (spin p ~ 0.45). The honest conclusion is that the "
        "two maps are NOT significantly spatially correlated once spatial autocorrelation is accounted "
        "for; the tiny parametric p is spurious. A flat 'significantly correlated' misses this.")
