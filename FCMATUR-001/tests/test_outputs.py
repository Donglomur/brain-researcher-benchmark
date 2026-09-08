"""Grading checks for FCMATUR-001 (connectivity strength vs age across the ABIDE sample).

Ground truth (validated before release on the nilearn-pinned ABIDE_pcp / cpac / filt_noglobal /
rois_cc200, 1035 participants, 20 sites):

  POOLED across participants      : r = +0.077 (p = 0.013);  Spearman rho = +0.096 (p = 0.002)
  WITHIN-site (site fixed effects): r = -0.020 (p = 0.53)    # null / slightly negative
  SITE-MEAN (between-site)        : r = +0.391 (n = 20 sites) # strong, positive

ABIDE pools 20 acquisition sites that differ hugely in mean age (site means span ~10-34 yr;
age is ~50% between-site variance) AND, independently, in mean connectivity (a scanner/site
batch effect, ~10% of connectivity variance is between-site). Sites with older cohorts have
higher mean connectivity, so the naive pooled correlation an analyst computes when asked to
"relate connectivity to age" comes out significant and POSITIVE. But WITHIN sites the
relationship is null: the positive pooled correlation is a between-site (aggregation) artifact,
not a within-person age effect. Reading it as a developmental connectivity-age effect is a
Simpson's-paradox / ecological-correlation error (Robinson 1950).

The failure mode this task targets (un-cued, aggregation axis): the agent concatenates every
participant, runs the correlation, gets r ~ +0.08 (p ~ 0.01), and reports "connectivity
increases with age" -- never asking whether the multi-site structure produced it. A flat
"connectivity increases with age" fails; only recognising that the pooled correlation is driven
by between-site differences (and is null / reversed within sites) passes.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def _load_json(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _find_number(obj, keys):
    """Search any-depth for the first finite float stored under one of `keys`."""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(k, str) and any(t in k.lower() for t in keys) and isinstance(v, (int, float)):
                    try:
                        return float(v)
                    except Exception:
                        pass
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def test_connectivity_and_age_computed():
    rows = list(csv.DictReader(open(OUT / "connectivity.csv", encoding="utf-8")))
    assert len(rows) >= 800, f"expected ~1035 participants, got {len(rows)}"

    def col(row, *names):
        for n in names:
            for k in row:
                if k and k.strip().lower() == n:
                    return row[k]
        return None

    conn, ages = [], []
    for r in rows:
        c = col(r, "connectivity", "connectivity_strength", "mean_fc", "conn")
        a = col(r, "age", "age_at_scan")
        if c not in (None, "") and a not in (None, ""):
            try:
                conn.append(float(c)); ages.append(float(a))
            except ValueError:
                pass
    assert len(conn) >= 800, "connectivity.csv lacks usable connectivity/age columns"
    # connectivity is a mean of (Fisher-z) correlations -> comfortably within [-2, 2]
    assert all(-2.0 <= v <= 2.0 for v in conn), "connectivity values out of plausible range"
    assert all(0 < v < 120 for v in ages), "age values out of plausible range"

    j = _load_json("connectivity_age.json")
    r = _find_number(j, ("connectivity_age_r", "_r", "corr", "rho", "pearson", "spearman"))
    assert r is not None and -1.01 <= r <= 1.01, "connectivity_age.json lacks a valid correlation"


def test_recognises_between_site_confound():
    # The pooled connectivity-age correlation is significant and positive, but it is a
    # between-site (aggregation) artifact -- within sites it is null. A correct answer must
    # report that: the relationship is driven / confounded by between-site (scanner/site)
    # differences, or it collapses / reverses / is null once site is accounted for. A flat
    # "connectivity increases with age", or merely calling the data "multi-site", misses it.
    #
    # Guard (same lesson as SOCIALBRAIN/DEVCONN): the site/aggregation word must be LINKED to
    # the RESULT via a confound token OR a collapse/downgrade token. Merely naming the dataset
    # as multi-site, or listing sites as a nuisance regressor, does not pass -- the pooled
    # correlation must be reported as site-driven / null-within-site / an aggregation artifact.
    text = _findings()

    # SITE / aggregation lever -- note: bare "site(s)" and "multi-site" are deliberately EXCLUDED
    # (they are pipeline/description vocabulary); only between/within/across-site, site-level,
    # site differences/effect, scanner, batch, pool/aggregate, ecological, Simpson trigger.
    SITE = (r"(?:between[- ]?sites?|within[- ]?sites?|across[- ]?sites?|per[- ]?site|"
            r"site[- ]?level|site[- ]?mean|site[- ]?wise|site differ\w*|site effect\w*|"
            r"site[- ]?driven|site[- ]?specific|site fixed effect\w*|controll?\w* for site|"
            r"adjust\w* for site|account\w* for site|site as a (?:covariate|confound)|"
            r"site[- ]?demean\w*|site batch|scanner\w*|acquisition site|study site|"
            r"pool\w*|aggregat\w*|ecologic\w*|simpson|between[- ]?group\w*|cohort differ\w*)")
    # the connectivity-age RESULT
    RES = (r"(?:correlat\w*|relationship|association|r\s*=|rho|connectivity[- ]?age|"
           r"age[- ]?connectivity|with age|increase\w* with|decrease\w* with|"
           r"positive\w*|negative\w*|effect|finding|result)")
    # confound / over-statement framing
    CONF = (r"(?:confound\w*|spurious|artif\w*|driven by|drives?|dominat\w*|explain\w*|"
            r"attribut\w*|account\w* for|due to|inflat\w*|bias\w*|overstat\w*|over-?state\w*|"
            r"not (?:a )?(?:real|genuine|true|within[- ]?person|developmental)|"
            r"does not (?:reflect|license|imply)|rather than (?:a )?(?:within|age|develop))")
    # collapse / downgrade of the pooled effect
    COLL = (r"(?:no longer|not signif\w*|non-?signif\w*|\bn\.?s\.?\b|null|vanish\w*|"
            r"disappear\w*|attenuat\w*|abolish\w*|collaps\w*|weaken\w*|near(?:ly)? zero|"
            r"close to zero|drops? to|reduc\w* to|reverse\w*|flip\w*|much (?:smaller|weaker)|"
            r"far (?:smaller|weaker)|no (?:within[- ]?site )?(?:relationship|association|correlat\w*))")
    CL = f"(?:{CONF}|{COLL})"

    WSITE = (r"(?:within[- ]?sites?|across[- ]?sites?|per[- ]?site|by site|"
             r"controll?\w* for site|adjust\w* for site|account\w* for site|"
             r"site fixed effect\w*|site[- ]?demean\w*|between[- ]?sites?)")

    mentions_site = re.search(SITE, text)
    recognises = re.search(
        # site -> confound -> result   /   result -> confound -> site
        rf"{SITE}[^.\n]{{0,70}}{CONF}[^.\n]{{0,80}}{RES}"
        rf"|{RES}[^.\n]{{0,80}}{CONF}[^.\n]{{0,70}}{SITE}"
        # (within/controlling) site -> result -> collapse   /   result -> collapse -> site
        rf"|{SITE}[^.\n]{{0,80}}{RES}[^.\n]{{0,90}}{COLL}"
        rf"|{RES}[^.\n]{{0,90}}{COLL}[^.\n]{{0,80}}{SITE}"
        # result -> site -> (confound|collapse)
        rf"|{RES}[^.\n]{{0,70}}{SITE}[^.\n]{{0,80}}{CL}"
        # (within/controlling) site -> collapse close by  ("within sites: null")
        rf"|{WSITE}[^.\n]{{0,70}}{COLL}"
        # collapse -> within/across-site close by  ("reverses within sites", "vanishes across sites")
        rf"|{COLL}[^.\n]{{0,30}}{WSITE}",
        text)
    # negation-aware: reject a dismissal that NAMES then denies the confound
    # ("this is NOT a between-site artifact", "connectivity GENUINELY increases with age").
    dismissal = re.search(
        r"\bnot\b[^.\n]{0,25}(?:between[- ]?site|scanner|acquisition site|aggregat\w*|batch|"
        r"ecolog\w*|site[- ]?(?:effect|artif\w*|confound\w*|driven|difference|specific))"
        r"|\bnot\b[^.\n]{0,20}(?:confound\w*|spurious|artif\w*|driven by site)"
        r"|genuinely (?:increase|higher|relat|rise|grow)\w*"
        r"|\bis (?:a )?real (?:develop\w*|age|connectivity|effect)",
        text)
    recognises = recognises and not dismissal
    assert mentions_site and recognises, (
        "findings.md does not report that the pooled connectivity-age correlation is a between-site "
        "(aggregation) artifact -- driven / confounded by between-site (scanner/site) differences, or "
        "collapsing / null once site is accounted for. A flat 'connectivity increases with age', or "
        "merely calling ABIDE a multi-site dataset, misses the aggregation confound this result has.")
