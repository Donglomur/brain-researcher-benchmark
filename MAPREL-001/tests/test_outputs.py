"""Proof-of-work grader for MAPREL-001 (a between-map correlation that fails a spatial null).

Held-out reference (tests/reference.npz), built by running solution/compute.py on the pinned
neuromaps fsLR-32k annotations (Margulies-2016 fcgradient02, HCP-S1200 thickness) parcellated
with Schaefer-400 7-network:
  per-parcel gradient2 + thickness (400 rows)         -> parcels.csv
  Pearson r across parcels                = -0.222
  parametric p (n=400 treated iid)        =  7.1e-06   "highly significant"
  spin / spatial-autocorrelation null p   = ~0.45      NOT significant (null sd ~0.26)

Both maps are strongly spatially autocorrelated, so the ~400 parcels are nowhere near 400
independent observations; the parametric (and label-shuffle) p is badly anti-conservative.
The honest, un-cued move is to compare r against a spatial-autocorrelation-preserving (spin)
null and report the correlation as NOT significant. An agent that only reports the parametric
p cannot produce a spin-null p ~0.45 or a wide spin-null distribution.

Four pillars:
  1. per-parcel gradient2 + thickness ARE the real parcellated maps (track the held-out ref)
  2. recompute |r| across parcels FROM the rows == reference == reported
  3. grade the volunteered spatial-null result as numbers (spin p > 0.05, parametric p tiny,
     spin-null distribution wide, verdict not significant)
  4. SECONDARY prose signal: findings.md recognises the spatial-autocorrelation non-significance
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "parcels.csv"
    assert p.exists(), "missing required output parcels.csv"
    return pw.load_submitted(p)


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""


def _reported_r(blobs):
    cand = []
    for blob in blobs.values():
        for path, v in pw.numbers_with_path(blob):
            if re.search(r"pearson|correlat|(?:^|/)r$|(?:^|/)corr$|rvalue|coef|rho", path) \
                    and not re.search(r"pval|pspin|spin|null|param|shuffle|nparcel|permut", path):
                if 0.05 <= abs(v) <= 0.6:
                    cand.append(v)
    return cand


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    sub = _submitted()
    assert len(sub) >= 380, f"parcels.csv covers only {len(sub)} parcels (expected ~400)"
    blobs = _blobs()
    assert blobs, "no results JSON found"
    assert _reported_r(blobs), "no between-map Pearson r (|r| in [0.05,0.6]) reported"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_parcels_match_reference():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    cov = pw.coverage(sub, ref["pid"])
    assert cov >= st["COVER"], (
        f"parcels.csv covers only {cov:.0%} of the {len(ref['pid'])} Schaefer-400 parcels "
        f"(need >= {st['COVER']:.0%})")
    assert pw.nonconstant(sub, 0, st["EPS"]) and pw.nonconstant(sub, 1, st["EPS"]), (
        "a submitted parcel map is constant across parcels -- not a real parcellation")
    # gradient sign convention is arbitrary -> match by |corr|; thickness is a signed physical map.
    gc, ng = pw.cross_corr(sub, ref["grad"], ref["pid"], 0)
    tc, nt = pw.cross_corr(sub, ref["thick"], ref["pid"], 1)
    assert abs(gc) >= st["CORR_MIN"], (
        f"submitted gradient2 parcel values do not track the reference (cross-parcel |r|="
        f"{abs(gc):.3f} < {st['CORR_MIN']}); the Margulies gradient was not parcellated with the "
        f"pinned Schaefer-400 atlas")
    assert tc >= st["CORR_MIN"], (
        f"submitted thickness parcel values do not track the reference (cross-parcel r={tc:.3f} "
        f"< {st['CORR_MIN']}); the HCP thickness map was not parcellated with the pinned atlas")


# ------------------------------------------------------------------ pillar 2
def test_recompute_correlation_from_rows():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    r_rows = pw.recompute_abs_r(sub, ref["pid"])
    r_ref = abs(float(st["r_obs"]))
    assert abs(r_rows - r_ref) <= st["R_TOL"], (
        f"|Pearson r| recomputed from the submitted parcels ({r_rows:.3f}) does not match the "
        f"reference ({r_ref:.3f}, tol {st['R_TOL']}); the rows are not the real analysis")
    reported = _reported_r(_blobs())
    assert any(abs(abs(v) - r_rows) <= st["R_TOL"] for v in reported), (
        f"reported Pearson r {sorted(set(round(v,3) for v in reported))} is inconsistent with the "
        f"|r| recomputed from the submitted parcels ({r_rows:.3f})")


# ------------------------------------------------------------------ pillar 3 (judgement RECOMPUTED from the submitted null distribution)
def test_conclusion_spatial_null_recomputed_from_distribution():
    """PILLAR 3: the discriminating judgement is RECOMPUTED from the submitted null DISTRIBUTION,
    not read off a reported scalar. The task never states the answer, and "not significant under a
    spatial null" is guessable from priors -- so an agent must submit the actual sampling
    distribution of the correlation it compared the observed value against, and the grader:
      (a) validates that distribution is a genuine spatial-autocorrelation-preserving null -- it is
          centred near 0 and WIDE (a naive label-shuffle / parametric null of ~400 iid parcels has
          a narrow ~1/sqrt(n) ~= 0.05 spread; the real spin null of two smooth maps is ~0.26), and
      (b) RECOMPUTES the two-tailed p = fraction of the null with |r| >= the observed |r| (recomputed
          from the parcel rows) and requires it to be non-significant.
    A reported spin-p scalar with no distribution fails; a fabricated flat/narrow null fails the
    spread check AND recomputes to a SIGNIFICANT p; only a genuinely wide spatial null passes."""
    ref = _reference()
    st = ref["stats"]
    blobs = _blobs()
    sub = _submitted()

    null = pw.find_null_distribution(blobs, out_dir=OUT, min_len=int(st.get("MIN_NULL", 100)))
    assert null is not None, (
        "no spatial-null / surrogate correlation DISTRIBUTION is provided. Both maps are strongly "
        "spatially autocorrelated, so a parametric p that treats ~400 parcels as independent is "
        "anti-conservative. Compare the observed correlation against the sampling distribution of "
        "the correlation under a spatial-autocorrelation-preserving null (spin / variogram / "
        "surrogate), and provide that distribution (the array of null correlations) so the "
        "significance can be assessed against it.")
    assert len(null) >= int(st.get("MIN_NULL", 100)), (
        f"the submitted null distribution has only {len(null)} samples "
        f"(need >= {int(st.get('MIN_NULL', 100))}) to estimate the null reliably.")

    null_mean = float(np.mean(null))
    null_sd = float(np.std(null))
    assert abs(null_mean) <= st["NULL_MEAN_ABS_MAX"], (
        f"the submitted null distribution is not centred near zero (mean {null_mean:+.3f}); a "
        f"correlation null under random spatial rotations/surrogates is centred at ~0.")
    assert null_sd >= st["SPIN_SD_MIN"], (
        f"the submitted null distribution is too narrow (SD {null_sd:.3f} < {st['SPIN_SD_MIN']}); a "
        f"spatial-autocorrelation-preserving null of two smooth maps is WIDE (reference "
        f"~{st['spin_null_sd']:.2f}). A narrow null is a label shuffle / parametric null that "
        f"ignores the spatial structure and is anti-conservative.")
    assert abs(null_sd - st["spin_null_sd"]) <= st["SPIN_SD_TOL"], (
        f"the submitted null distribution SD ({null_sd:.3f}) is not consistent with a genuine "
        f"spatial null of these maps (reference {st['spin_null_sd']:.3f}, tol {st['SPIN_SD_TOL']}).")

    r_rows = pw.recompute_abs_r(sub, ref["pid"])
    p_spin = pw.recompute_spin_p(r_rows, null)
    assert p_spin > st["SPIN_P_MIN"], (
        f"the observed |r|={r_rows:.3f} recomputed against the submitted null distribution is "
        f"SIGNIFICANT (spin p={p_spin:.3f} <= {st['SPIN_P_MIN']}); either the null is too narrow "
        f"(anti-conservative) or the correlation would survive. On these data r sits well inside a "
        f"proper spatial null (reference spin p ~ {st['p_spin']:.2f}) -- it is NOT significant once "
        f"spatial autocorrelation is accounted for.")

    # the dissociation that makes this a real trap: the naive parametric p is tiny.
    param_ps = pw.parametric_p(blobs)
    assert param_ps and min(param_ps) < st["PARAM_P_MAX"], (
        f"no anti-conservative parametric / label-shuffle p-value (< {st['PARAM_P_MAX']}) is "
        f"reported; the discriminating contrast is that the naive p is tiny (~1e-5) while the "
        f"spatial-null p (recomputed from your null distribution, {p_spin:.2f}) is not.")

    # if an explicit spatial-null significance verdict is reported, it must be non-significant.
    verdicts = pw.find_bool_by_key(
        {k: v for k, v in blobs.items()},
        r"(?:spin|spatial|surrogate|rotat).*signif|signif.*(?:spin|spatial|surrogate|rotat)|"
        r"significantafterspatial|survivesspin|survivesspatial|spatiallysignif")
    if verdicts:
        assert not any(verdicts), (
            "an explicit spatial-null significance verdict is reported as True; once spatial "
            "autocorrelation is accounted for the correlation is not significant")


# ------------------------------------------------------------------ secondary prose signal
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


def _recognises(text, concept, downgrade, absence):
    if not re.search(concept, text, re.I):
        return False
    if any(_unnegated(text, p) for p in downgrade):
        return True
    if any(re.search(p, text, re.I) for p in absence):
        return True
    return False


def test_findings_recognise_spatial_null_secondary():
    """SECONDARY (the numeric pillars carry the grade): findings.md must recognise the correlation
    fails a spatial null (spatial autocorrelation makes the parametric p anti-conservative)."""
    text = _findings()
    assert text, "findings.md missing or empty"
    concept = (r"spatial(?:ly)?[\s-]*auto[\s-]?correlat|autocorrelat|"
               r"spin[\s-]?(?:test|permutation|perm|null|sample|model|rotation)|\bspun\b|"
               r"surrogate|variogram|brainsmash|brain[\s-]?smash|moran|alexander[\s-]?bloch|"
               r"vasa|hungarian null|rotat\w*\s+(?:the\s+)?(?:sphere|parcel|map|cortex)|"
               r"rotation[\s-]?based|spatial null|null (?:model|map|distribution)|"
               r"non[\s-]?independen|effective (?:degrees of freedom|d\.?o\.?f|df|sample size)|"
               r"geodesic (?:distance )?null")
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
        rf"(?:{NULLW})(?:(?!{_NEG}).){{0,80}}?(?:{NSIG})",
        rf"(?:{NSIG})(?:(?!{_NEG}).){{0,80}}?(?:{NULLW})",
        rf"(?:spatial(?:ly)?[\s-]*auto[\s-]?correlat|autocorrelat|spatial (?:smoothness|structure))"
        rf"(?:(?!{_NEG}).){{0,120}}?(?:{SPUR})",
        rf"(?:{SPUR})(?:(?!{_NEG}).){{0,120}}?(?:spatial(?:ly)?[\s-]*auto[\s-]?correlat|autocorrelat|"
        rf"spatial (?:smoothness|structure)|shared (?:spatial )?smoothness)",
        rf"(?:parametric|nominal|apparent|naive|na[iï]ve|face[\s-]?value|uncorrected|conventional|standard)"
        rf"(?:(?!{_NEG}).){{0,50}}?(?:{SPUR})",
        r"(?:spin|surrogate|surr|perm|rotation|spatial)[\s_]*p\w*\s*[=:~]\s*0?\.(?:0[5-9]|[1-9]\d*)",
        r"\bp[\s_]*(?:spin|surr\w*|perm|rot\w*)\b\s*[=:~]?\s*0?\.(?:0[5-9]|[1-9]\d*)",
    ]
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
        "findings.md reports a correlation but does not recognise that it fails a SPATIAL null "
        "(the parametric p is anti-conservative because both maps are spatially autocorrelated; "
        "r is well inside a spin-null distribution).")
