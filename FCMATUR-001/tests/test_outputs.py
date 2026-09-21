"""Proof-of-work grader for FCMATUR-001 — an ABIDE CC200 case study: is the marginal
connectivity-age association site-conditioned?

The maintainer's review of the previous verifier: it could be passed with 800 duplicate constant
rows, no participant ids/metadata, an arbitrary JSON value and a short site-confound sentence.
This grader closes that: it validates the EXACT ABIDE subjects and their per-subject values
against a held-out reference (tests/reference.npz, built from the oracle run and never shipped to
the agent), recomputes the pooled statistic FROM the submitted rows, cross-checks CSV/JSON/
metadata, and grades the scientific judgement AS NUMBERS — the reported within-site (site-
conditioned) correlation must be attenuated toward null and match the reference, with the
site-conditioning ordering within < pooled < between-site. Keyword prose is only a secondary
signal.

Reference stats (built on the nilearn-pinned ABIDE_pcp / cpac / filt_noglobal / rois_cc200):
  pooled_r ~ +0.077 ; within_site_r ~ -0.020 (~0) ; between_site_r ~ +0.391 (20 sites).
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"

# tolerances
CONN_TOL = 0.05       # per-subject connectivity abs match
AGE_TOL = 0.5         # per-subject age abs match (years)
CORR_MIN = 0.95       # cross-subject corr(submitted, reference) fabrication teeth
COVER = 0.90          # coverage of the real subject ids
RECOMP_TOL = 0.03     # pooled r recomputed-from-rows vs reference and vs reported
WITHIN_MAX = 0.08     # within-site r must be near zero (attenuated toward null)
RECOMP_WITHIN_TOL = 0.05   # within-site r RECOMPUTED-from-rows must match the reference (fabrication
                           # teeth: a shuffled/fabricated site partition yields within ~ pooled and
                           # misses this by ~0.10, while honest+defensible pipelines land within ~0.01)
RECOMP_BETWEEN_TOL = 0.12  # between-site r recomputed-from-rows vs reference (loose: only 20 site means)
ATTEN_MIN = 0.02      # within must be attenuated vs pooled by at least this in magnitude
BETWEEN_MIN = 0.15    # between-site r must be clearly positive
REPORT_CONSIST_TOL = 0.08  # reported within/between must be consistent with the recompute-from-rows


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "connectivity.csv"
    assert p.exists(), "missing required output connectivity.csv"
    return pw.load_submitted(
        p,
        id_cols=("subject", "fileid", "subjectid", "participant", "participantid", "subid", "id"),
        conn_cols=("connectivity", "connectivitystrength", "meanfc", "conn", "fc", "strength"),
        age_cols=("age", "ageatscan"),
        site_cols=("siteid", "site", "scanningsite", "acquisitionsite", "scanner", "scannerid",
                   "sitename", "center", "centre"))


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub, conn, age, site = _submitted()
    assert len(conn) >= 800, (
        f"connectivity.csv must carry per-participant connectivity+age for the ABIDE cohort; "
        f"parsed {len(conn)} usable rows")
    assert all(-2.0 <= v <= 2.0 for v in conn), "connectivity values out of plausible range [-2,2]"
    assert all(0 < v < 120 for v in age), "age values out of plausible range"

    # site is a required per-participant column (plain acquisition metadata); the site-conditioned
    # estimate is recomputed from it below, so it must be present and carry the multi-site structure.
    n_with_site = sum(1 for s in site if s is not None and str(s).strip() != "")
    assert n_with_site >= 0.9 * len(conn), (
        f"connectivity.csv must carry a per-participant acquisition-site column (site_id); only "
        f"{n_with_site}/{len(conn)} rows have one. It is standard ABIDE metadata aligned row-for-row "
        f"with the phenotype and is required to characterise the connectivity–age association at the "
        f"within-site and between-site levels.")
    distinct_sites = {str(s).strip() for s in site if s is not None and str(s).strip() != ""}
    assert len(distinct_sites) >= 2, (
        f"connectivity.csv reports only {len(distinct_sites)} distinct acquisition site(s); ABIDE is "
        f"a multi-site sample and the within/between-site levels require >= 2 sites.")

    j = _load_json("connectivity_age.json")
    assert pw.find_number(j, [r"pooledr", r"marginalr", r"connectivityager", r"pearsonr", r"^r$"],
                          exclude=[r"spearman", r"rho", r"ci", r"pval", r"within", r"between",
                                   r"low", r"high", r"nsites"]) is not None, \
        "connectivity_age.json lacks a pooled/marginal connectivity-age correlation"

    meta = _load_json("run_metadata.json")
    assert isinstance(meta, dict) and meta, "run_metadata.json is empty"

    sens = _load_json("sensitivity.json")
    blob = pw._norm(json.dumps(sens))
    for need in ("motion", "sex", "nonlinear", "site"):
        assert need in blob, f"sensitivity.json does not report the '{need}' sensitivity check"
    assert ("diagnosis" in blob or "dx" in blob or "control" in blob), \
        "sensitivity.json does not report a diagnosis sensitivity check"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference()
    sub, _, _, _ = _submitted()
    pw.check_subjects_and_values(sub, ref, conn_tol=CONN_TOL, age_tol=AGE_TOL,
                                 cover=COVER, corr_min=CORR_MIN)


# ------------------------------------------------------------------ pillar 2
def _reported_pooled(j):
    return pw.find_number(j, [r"pooledr", r"marginalr", r"connectivityager", r"pearsonr", r"^r$"],
                          exclude=[r"spearman", r"rho", r"ci", r"pval", r"within", r"between",
                                   r"low", r"high", r"nsites"])


def test_recompute_and_crosscheck():
    ref = _reference()
    sub, _, _, _ = _submitted()
    matched = [i for i in sub if i in set(ref["ids"])]
    j = _load_json("connectivity_age.json")
    reported = _reported_pooled(j)
    pw.check_recompute(sub, matched, ref, reported, stat_tol=RECOMP_TOL)

    # CSV <-> JSON <-> metadata consistency on n.
    reported_n = pw.find_number(j, [r"^n$", r"nparticip", r"nsubjects", r"samplesize"],
                                exclude=[r"nsites", r"within"])
    meta = _load_json("run_metadata.json")
    meta_n = pw.find_number(meta, [r"nparticip", r"^n$", r"nsubjects"], exclude=[r"nsites"])
    n_rows = len(matched)
    if reported_n is not None:
        assert abs(reported_n - n_rows) <= max(50, 0.1 * n_rows), (
            f"reported n ({reported_n}) is inconsistent with the {n_rows} real subject rows")
    if meta_n is not None:
        assert abs(meta_n - n_rows) <= max(50, 0.1 * n_rows), (
            f"run_metadata n_participants ({meta_n}) is inconsistent with the {n_rows} rows")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_conclusion_is_site_conditioned_numeric():
    """The scientific judgement (is the marginal association site-conditioned?) is graded AS NUMBERS
    and — critically — RECOMPUTED from the submitted per-participant {connectivity, age, site} rows,
    not trusted from a reported scalar. A shuffled/fabricated site partition cannot reproduce the
    reference within-site attenuation, so guessing within ~ 0 without a real site column fails."""
    ref = _reference()
    sub, _, _, _ = _submitted()
    matched = [i for i in sub if i in set(ref["ids"])]
    j = _load_json("connectivity_age.json")
    meta = _load_json("run_metadata.json")

    def look(patterns, exclude):
        return pw.find_number(j, patterns, exclude=exclude) \
            if pw.find_number(j, patterns, exclude=exclude) is not None \
            else pw.find_number(meta, patterns, exclude=exclude)

    reported_pooled = look([r"pooledr", r"marginalr", r"connectivityager", r"pearsonr", r"^r$"],
                           [r"spearman", r"rho", r"ci", r"pval", r"within", r"between", r"low",
                            r"high", r"nsites"])
    reported_within = look([r"withinsiter", r"withinr", r"siteconditionedr", r"siteadjustedr",
                            r"fixedeffectr", r"sitewithinr"],
                           [r"pval", r"ci", r"low", r"high", r"nsites", r"withinsiten", r"spearman",
                            r"rho"])
    reported_between = look([r"betweensiter", r"betweenr", r"ecologicalr", r"sitemeanr", r"sitelevelr"],
                            [r"pval", r"ci", r"low", r"high", r"nsites", r"spearman", r"rho"])

    assert reported_pooled is not None, "no pooled/marginal connectivity-age correlation reported"
    assert reported_within is not None, (
        "no WITHIN-SITE (site-conditioned) connectivity-age correlation reported. The judgement "
        "graded here is whether the marginal association survives conditioning on site; report a "
        "within-site r (e.g. site fixed effects).")
    assert reported_between is not None, (
        "no BETWEEN-SITE (site-mean/ecological) connectivity-age correlation reported.")

    ref_within = float(ref["stats"]["within_site_r"])
    ref_between = float(ref["stats"]["between_site_r"])

    # ---- RECOMPUTE the three levels FROM the submitted rows (the un-guessable gate) ----
    rec = pw.recompute_site_levels(sub, matched, min_per_site=5)
    within = rec["within_site_r"]
    between = rec["between_site_r"]
    pooled = rec["pooled_r"]
    import math as _m
    assert _m.isfinite(within), (
        "cannot recompute the within-site (site fixed effects) connectivity-age correlation from the "
        "submitted rows -- the acquisition-site column is missing, degenerate, or has < 2 usable "
        "sites. The site-conditioned estimate must be derivable from the per-participant table.")
    assert _m.isfinite(between), "cannot recompute the between-site correlation from the submitted rows"

    # (a) within-site RECOMPUTED-from-rows is near zero (attenuated) AND matches the reference. This
    #     is what a shuffled/fabricated site partition fails: it yields within ~ pooled (~ +0.08).
    assert abs(within) <= WITHIN_MAX, (
        f"within-site r recomputed from the submitted rows = {within:+.3f} is not near zero; on the "
        f"real data the marginal association attenuates toward null within sites "
        f"(reference {ref_within:+.3f}). A site partition that does not reproduce this is not the "
        f"real per-participant site assignment.")
    assert abs(within - ref_within) <= RECOMP_WITHIN_TOL, (
        f"within-site r recomputed from the submitted rows = {within:+.3f} does not match the "
        f"reference within-site estimate ({ref_within:+.3f}, tol {RECOMP_WITHIN_TOL}). The submitted "
        f"connectivity/age/site rows do not reproduce the site-conditioned association.")

    # (b) attenuation: within is meaningfully smaller in magnitude than the marginal, and below it.
    assert within < pooled and (abs(pooled) - abs(within)) >= ATTEN_MIN, (
        f"the marginal association (r={pooled:+.3f}) does not attenuate toward null within sites "
        f"(within r={within:+.3f}). A site-conditioned result requires the within-site estimate to "
        f"be attenuated; within ~ pooled misses the site conditioning.")

    # (c) site-conditioning ordering: between-site carries a clearly positive relationship > marginal.
    assert abs(between - ref_between) <= RECOMP_BETWEEN_TOL, (
        f"between-site r recomputed from the submitted rows = {between:+.3f} does not match the "
        f"reference ({ref_between:+.3f}, tol {RECOMP_BETWEEN_TOL}).")
    assert between > pooled and between >= BETWEEN_MIN, (
        f"between-site r = {between:+.3f} does not exceed the marginal (r={pooled:+.3f}); the "
        f"between-site level should carry the positive relationship (reference {ref_between:+.2f}).")

    # (d) consistency: the agent's REPORTED within/between must agree with the recompute-from-rows
    #     (a guessed scalar that disagrees with the submitted table's own site structure fails here).
    assert abs(reported_within - within) <= REPORT_CONSIST_TOL, (
        f"reported within-site r ({reported_within:+.3f}) is inconsistent with the value recomputed "
        f"from the submitted rows ({within:+.3f}, tol {REPORT_CONSIST_TOL}). Report the estimate your "
        f"own per-participant table produces.")
    assert abs(reported_between - between) <= max(RECOMP_BETWEEN_TOL, REPORT_CONSIST_TOL), (
        f"reported between-site r ({reported_between:+.3f}) is inconsistent with the value recomputed "
        f"from the submitted rows ({between:+.3f}).")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_engage_site_conditioning_and_avoid_overclaim():
    """SECONDARY (not the sole gate — the numeric pillars carry the grade). findings.md must
    engage with site-conditioning in prose, and must not make the over-claims the maintainer
    flagged: scanner CAUSALITY or a TRUE NULL / no-age-relationship-at-any-site."""
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()

    SITE = (r"(?:within[- ]?site|between[- ]?site|across[- ]?site|per[- ]?site|site[- ]?condition|"
            r"site[- ]?level|site[- ]?mean|site fixed effect|site differ|site[- ]?driven|"
            r"conditional on site|controll?\w* for site|adjust\w* for site|account\w* for site|"
            r"aggregat\w*|ecologic\w*|simpson|scanner|acquisition site)")
    ATTEN = (r"(?:attenuat\w*|toward\w* (?:the )?null|near(?:ly)? zero|close to zero|"
             r"site[- ]?condition\w*|driven by|carried by|dominat\w*|confound\w*|artif\w*|"
             r"sensitive to site|does not survive|no longer|collaps\w*|weaken\w*|reduc\w* to|"
             r"drops? to)")
    engages = re.search(SITE, text) and re.search(ATTEN, text)
    assert engages, (
        "findings.md does not engage in prose with the site-conditioning of the marginal "
        "connectivity-age association (site + attenuation/conditioning).")

    # over-claim guards (assertions, negation-aware): reject scanner CAUSALITY and TRUE-NULL claims.
    scanner_cause = re.search(
        r"scanner\w*[^.\n]{0,40}(?:caus\w*|because|produce\w*|create\w*|responsible for|drive\w* the)"
        r"|(?:caus\w*|because of|due to)[^.\n]{0,25}scanner",
        text)
    # allow an explicit disclaimer ("not a scanner-caused", "does not establish scanner causation")
    scanner_disclaim = re.search(r"not[^.\n]{0,30}scanner|scanner[^.\n]{0,30}not\b|"
                                 r"(?:cannot|does not|do not|doesn.t)[^.\n]{0,30}(?:scanner|caus)", text)
    assert not (scanner_cause and not scanner_disclaim), (
        "findings.md asserts scanner CAUSALITY, which the data (site conflates scanner/protocol/"
        "cohort) do not support. Report site-conditioning, not a demonstrated scanner effect.")

    true_null = re.search(
        r"no (?:age )?(?:relationship|association|correlation|effect)[^.\n]{0,20}"
        r"(?:at any site|in any site|within any site|at all)"
        r"|(?:proves?|establish\w*|confirm\w*|demonstrat\w*)[^.\n]{0,30}"
        r"(?:no|zero|absent|true null)[^.\n]{0,20}(?:age|relationship|association|effect)"
        r"|connectivity does not (?:change|increase|vary) with age",
        text)
    true_null_disclaim = re.search(
        r"not[^.\n]{0,25}(?:true null|proof of|prove\w*|absence)"
        r"|(?:cannot|does not|do not|doesn.t|cross[- ]?section)[^.\n]{0,40}"
        r"(?:true null|no .*relationship|rule out|within[- ]?person|develop)",
        text)
    assert not (true_null and not true_null_disclaim), (
        "findings.md over-claims a TRUE NULL (no age relationship at any site / connectivity does "
        "not change with age). The within-site estimate is attenuated toward null with a wide CI "
        "on cross-sectional data; it does not establish a true absence of any relationship.")
