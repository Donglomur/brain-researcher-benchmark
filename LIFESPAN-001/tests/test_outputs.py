"""Grading checks for LIFESPAN-001.

Ground truth (validated before release on the packaged NKI surface bundle, n = 59-60, ages 18-78,
148-region Destrieux connectomes):

    overall / mean functional connectivity vs age : r = +0.15  (p ~ 0.26)   -> essentially FLAT
    system segregation vs age                     : r = -0.28  (p ~ 0.03)   -> DECLINES
        (within-network FC vs age flat ~ 0.0; between-network FC vs age rises ~ +0.12; the two
         cancel in the global average. Robust: segregation-age r in [-0.40, -0.24] across 5-12
         network partitions and seeds; >99% of bootstrap resamples negative; Spearman -0.36.)

So the resting connectome's large-scale organization DOES change across the adult lifespan: its
networks de-differentiate (segregation declines). A submission that summarises "connectivity" only
as the global average finds no age effect and concludes connectivity is stable with age — an
over-claim that misses the reorganization. A good submission summarises the network-level
organization (segregation / within-vs-between / modularity) and reports that it DECLINES with age.

The checks below require that de-differentiation conclusion linked to an actual computed number,
not merely named. HARDENING: the pass is tied to genuine SEGREGATION / within-vs-between /
modularity vocabulary — a generic network metric labelled "organization"/"integration" with a
negative age-correlation no longer stands in for the "global average hides de-differentiation"
insight, and the over-claim graded is specifically the "connectivity is stable with age" null read
off the flat global mean.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _load_json(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _walk(obj, path=""):
    """Yield (lowercased_key_path, value) for every leaf in a nested json object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}".lower())
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            yield from _walk(x, path)
    else:
        yield path, obj


def _correlations(obj):
    """(key_path, value) pairs whose value is a plausible correlation in [-1, 1]."""
    out = []
    for k, v in _walk(obj):
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)) and -1.01 <= v <= 1.01:
            out.append((k, float(v)))
    return out


# TIGHTENED (hardening): genuine network-SEGREGATION / de-differentiation vocabulary only. A bare
# "organization" / "integration" label on any negative-with-age correlation no longer counts -- the
# pass must reflect the specific de-differentiation insight (segregation / within-vs-between /
# modularity declines), not a generic network metric that happens to correlate with age.
ORG = re.compile(r"segreg|de.?differ|dedifferent|modular|within.{0,25}between|"
                 r"between.{0,25}within|system.?seg")
GLOBAL = re.compile(r"overall|global|whole.?brain|grand.?mean|mean_?fc|meanfc")


def _findings_text():
    blob = ""
    for name in ("findings.md", "results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def test_connectomes_and_subjects():
    # A real per-subject connectome analysis over a reasonable slice of the cohort.
    res = _load_json("results.json")
    corrs = _correlations(res)
    n = None
    for k, v in _walk(res):
        if re.search(r"n_?subj|nsub|n_?sample|\bn\b", k) and isinstance(v, (int, float)) \
                and not isinstance(v, bool) and v >= 20:
            n = int(v)
            break
    assert n is not None and n >= 40, f"expected a lifespan cohort (>=40 subjects), got {n}"
    assert corrs, "results.json reports no correlation between a connectome summary and age"


def test_organization_declines_with_age():
    # The insight linked to the result: a NETWORK-LEVEL organization summary
    # (segregation / within-vs-between / modularity) DECLINES with age. Accept either an
    # explicitly organization-named negative age-correlation, or a within/between divergence
    # (between-network connectivity rises relative to within with age = de-differentiation).
    res = _load_json("results.json")
    corrs = _correlations(res)

    org_neg = [v for k, v in corrs
               if ORG.search(k) and not GLOBAL.search(k) and v <= -0.12]

    within = [v for k, v in corrs if re.search(r"within", k) and not GLOBAL.search(k)]
    between = [v for k, v in corrs if re.search(r"between", k) and not GLOBAL.search(k)]
    dediff = bool(within and between and (min(between) - max(within)) >= 0.08)

    # fallback: a clearly-labelled negative SEGREGATION / de-differentiation / modularity
    # correlation stated in the prose, e.g. "segregation ... age ... r = -0.28". A bare
    # "organization"/"integration" label no longer counts (tightened).
    text = _findings_text()
    prose_seg = False
    for m in re.finditer(r"(segregat|de.?differ|dedifferent|modular|system.?seg)"
                         r"[^\n]{0,160}?(-?0?\.\d+)", text):
        try:
            if float(m.group(2)) <= -0.12:
                prose_seg = True
                break
        except ValueError:
            pass

    assert org_neg or dediff or prose_seg, (
        "no evidence that the connectome's NETWORK SEGREGATION declines with age. A global/mean "
        "connectivity summary alone is essentially flat (r ~ +0.15) and misses the change; a generic "
        "network metric labelled 'organization' is not enough either. Summarise the connectome's "
        "system segregation (within- vs between-network connectivity / modularity) and relate it to "
        "age -- it de-differentiates (declines).")


def test_reports_dedifferentiation_not_stability():
    # Honesty / grade the SPECIFIC over-claim: a naive analyst summarises connectivity only as the
    # global average (flat, r ~ +0.15) and headlines "connectivity is unchanged across the adult
    # lifespan" -- a null read off the global mean that HIDES the reorganization. The write-up must
    # instead conclude that the connectome's network SEGREGATION declines / the networks
    # de-differentiate with age. TIGHTENED: the decline must be tied to segregation /
    # de-differentiation / modularity specifically (a bare "network declines" or "organization
    # declines" is not enough), so a generic network metric can't stand in for the insight.
    text = _findings_text()
    decline = re.search(
        # decline word THEN a segregation / de-differentiation / modularity term
        r"(declin|decreas|reduc|lower|loss|drop|fall|weaken|diminish|erod|attenuat|break.?down|"
        r"breaks? down|less)[^.\n]{0,80}(segregat|differentiat|modular|system.?seg)"
        # ... or a segregation / de-differentiation term THEN a decline word
        r"|(segregat|differentiat|modular|system.?seg)[^.\n]{0,45}"
        r"(declin|decreas|reduc|lower|loss|drop|fall|weaken|diminish|erod|attenuat|break.?down)"
        # ... or the compact de-differentiation vocabulary / reduced-distinctiveness phrasings
        r"|de.?different|dedifferent|less segregat|reduced segregat|loss of segregat|"
        r"becomes? less segregat|network.{0,25}(de.?differ|break.?down|less segregat)|"
        r"(less|reduc\w*|lower|declin\w*|loss of)[^.\n]{0,25}(distinct|segregat|differentiat|modular)",
        text)
    assert decline, (
        "findings.md does not report that the connectome's network SEGREGATION declines / the "
        "networks de-differentiate with age. It appears to conclude connectivity is unchanged across "
        "the adult lifespan -- over-claiming a null from the flat global average, which hides the "
        "de-differentiation (between-network connectivity rises while within-network stays flat).")
