"""Proof-of-work grader for RESTCONN-001 (is R DMN functionally connected to the cerebellum?).

Single-subject, single-value task: the deliverable is one correlation r and a significance
verdict. A lone scalar is guessable, so (QSMDIPOLE-001 model) the grader also validates the
finest intermediate the analysis produces — the two extracted ROI mean BOLD time series — against
a held-out reference (tests/reference.npz, built from the oracle run, never shipped to the
agent), recomputes the correlation AND the autocorrelation-corrected effective degrees of freedom
FROM the submitted rows, and grades the significance verdict as numbers.

Ground truth (nilearn-pinned ADHD-200 subject 0010064, MSDL atlas, n = 176 TRs, detrend +
band-pass 0.01-0.1 Hz + motion/CompCor/CSF/WM nuisance regression):
  r (R DMN ~ Cereb)                     = +0.316
  naive parametric p (df = n - 2 = 174) = 1.9e-5           -> "highly significant"
  lag-1 autocorrelation of each series  ~ 0.87
  effective sample size (AR1 / Bartlett)~ 24 / 30  (<< 176)
  corrected p (AR1 / Bartlett / circ)   ~ 0.13 / 0.09 / 0.15   -> NOT significant

The correlation is real in magnitude (r ~ 0.32) but its library-default parametric significance
is an artifact of temporal autocorrelation: BOLD does not provide 176 independent samples. Only
extracting the real autocorrelated series yields the ~25 effective df and the non-significant
corrected p; a naive analyst who reports scipy's df=n-2 p (or fabricates the series) cannot.

Four pillars:
  1. submitted ROI time series ARE the real extracted series (track the held-out reference)
  2. recompute r AND the effective df FROM the submitted rows == reference (eff df << n)
  3. grade the verdict as numbers: significant == False, corrected p > 0.05, and the naive
     df=n-2 p is tiny -- the discriminating gap the honest analysis produces
  4. SECONDARY prose signal: findings.md recognises the autocorrelation inflation
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

TS_CORR = 0.90        # submitted ROI series vs held-out reference (cross-time correlation)
R_TOL_REF = 0.06      # recomputed r vs reference
R_TOL_JSON = 0.05     # recomputed r vs reported (CSV <-> JSON consistency)
EFF_DF_MAX = 90.0     # effective df recomputed from the submitted series must be << n (=176)
LAG1_MIN = 0.55       # each series' lag-1 autocorrelation (reference ~0.87); a real BOLD series
#                       is strongly autocorrelated -- a white-noise fake is not
ALPHA = 0.05


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


def _submitted_ts(ref):
    p = OUT / "timeseries.csv"
    assert p.exists(), (
        "missing required output timeseries.csv -- the two extracted ROI mean BOLD time series "
        "(one row per volume). The single correlation cannot be validated without the "
        "fine-grained series it is built from.")
    return pw.load_submitted_timeseries(
        p,
        a_cands=("rdmn", "rightdmn", "dmn", "regiona", "a", "node1", "roi1"),
        b_cands=("cereb", "cerebellum", "cerebellar", "regionb", "b", "node2", "roi2"))


def _reported_r(cj):
    return pw.find_number(cj, [r"^r$", r"pearson", r"correlation", r"^corr$", r"rvalue", r"^rdmn"],
                          exclude=[r"spearman", r"rho", r"pval", r"pvalue", r"ci", r"low", r"high",
                                   r"autocorr", r"lag", r"df", r"eff"])


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    cj = _load_json("connectivity.json")
    r = _reported_r(cj)
    assert r is not None, f"connectivity.json lacks a reported correlation r: {cj}"
    assert 0.20 <= r <= 0.42, (
        f"reported R DMN~Cereb correlation r={r:.3f} is outside the expected range for the "
        f"pinned pipeline (~+0.32) -- wrong region pair or preprocessing")
    a, b = _submitted_ts(ref)
    assert a is not None and len(a) >= 150, "timeseries.csv does not carry the ~176-volume series"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_timeseries_matches_reference():
    ref = _reference()
    a, b = _submitted_ts(ref)
    pw.check_timeseries_matches_reference(a, b, ref, ts_corr=TS_CORR)


# ------------------------------------------------------------------ pillar 2
def test_recompute_correlation_and_effective_df():
    ref = _reference()
    a, b = _submitted_ts(ref)
    cj = _load_json("connectivity.json")

    r_rows = pw.pearson(a, b)
    r_ref = float(ref["stats"]["r"])
    assert abs(r_rows - r_ref) <= R_TOL_REF, (
        f"correlation recomputed from the submitted time series ({r_rows:+.3f}) does not match "
        f"the reference ({r_ref:+.3f}, tol {R_TOL_REF}); the rows are not the real analysis")
    reported = _reported_r(cj)
    assert reported is not None and abs(r_rows - float(reported)) <= R_TOL_JSON, (
        f"correlation recomputed from the rows ({r_rows:+.3f}) does not match the reported r "
        f"({reported}); the CSV and JSON disagree")

    # the autocorrelation signature: recompute the effective df from the submitted series.
    ne_ar1, rx, ry = pw.eff_df_ar1(a, b)
    ne_bart = pw.eff_df_bartlett(a, b)
    assert min(rx, ry) >= LAG1_MIN, (
        f"the submitted series are not strongly temporally autocorrelated (lag-1 acf "
        f"{rx:.2f}/{ry:.2f} < {LAG1_MIN}); a real resting-state BOLD series is (reference ~0.87)")
    assert 3 < ne_ar1 < EFF_DF_MAX and 3 < ne_bart < EFF_DF_MAX, (
        f"effective df recomputed from the submitted series (AR1 {ne_ar1:.0f} / Bartlett "
        f"{ne_bart:.0f}) is not << n=176; the temporal autocorrelation was not carried by the "
        f"series (a naive df = n - 2 = 174 would treat every volume as independent)")


# ------------------------------------------------------------------ pillar 3 (verdict as numbers)
def test_conclusion_not_overclaimed_numeric():
    ref = _reference()
    a, b = _submitted_ts(ref)
    cj = _load_json("connectivity.json")

    # the significance verdict must be FALSE (autocorrelation-aware) ...
    flags = pw.find_significant_flag(cj)
    txt = ((OUT / "findings.md").read_text(encoding="utf-8").lower()
           if (OUT / "findings.md").exists() else "")
    verdict_not_sig = (flags and all(f is False for f in flags)) or bool(re.search(
        r"not (?:statistically )?significant|n't (?:statistically )?significant|"
        r"cannot be (?:declared|considered|called) (?:statistically )?signif|"
        r"no longer significant|fails? to reach signif|significance (?:is )?"
        r"(?:not established|collapses|disappears|vanishes)", txt))
    assert verdict_not_sig, (
        "the submission reports the connection as statistically significant. Once the temporal "
        "autocorrelation is accounted for (effective df << n) this R DMN~cerebellum correlation "
        "is NOT significant at alpha=0.05 -- reporting 'significant' is an overclaim.")

    # ... and that verdict must be FORCED BY THE DATA, not guessed: with the effective df
    # recomputed from the submitted series, the correlation is not significant, while the naive
    # df=n-2 test is (the discriminating gap only real extraction produces).
    r_rows = pw.pearson(a, b)
    ne_ar1, _, _ = pw.eff_df_ar1(a, b)
    ne_bart = pw.eff_df_bartlett(a, b)
    p_corr = max(pw.p_from_neff(r_rows, ne_ar1), pw.p_from_neff(r_rows, ne_bart))
    p_naive = pw.p_from_neff(r_rows, len(a))
    assert p_corr > ALPHA, (
        f"autocorrelation-corrected p recomputed from the submitted series is {p_corr:.3f} "
        f"(<= {ALPHA}); the not-significant verdict is not supported by the submitted data")
    assert p_naive < 0.01, (
        f"the naive df=n-2 p recomputed from the submitted series is {p_naive:.3g}; the "
        f"significance-inflation this task turns on is not present in the submitted series")

    # a reported corrected p-value, if present, must not overclaim significance.
    reported_p = pw.find_number(cj, [r"pvalue", r"^p$", r"pval"],
                                exclude=[r"naive", r"parametric", r"uncorrected", r"df", r"eff",
                                         r"lag", r"autocorr"])
    if reported_p is not None:
        assert reported_p > ALPHA, (
            f"reported p_value = {reported_p:.3g} claims significance; the autocorrelation-"
            f"corrected p is > {ALPHA}")


# ------------------------------------------------------------------ secondary prose signal
AUTO = (r"auto-?correlat|serial(?:ly)?[ -]?correlat|serial dependence|"
        r"temporal(?:ly)?[ -]?(?:depend|correlat|autocorrelat)|"
        r"effective (?:degrees? of freedom|d\.?o\.?f\.?|df|sample ?size|number of (?:samples|observ))|"
        r"pre-?whiten|\bar\(1\)|\bar\(\d\)|autoregressive|bartlett|"
        r"circular(?:ly)?[ -]?shift|block permutation|block bootstrap|phase[- ]?random|"
        r"non-?independen|not independent|independen\w* (?:samples|observ|assum)")
INVAL = (r"inflat|overstate|over-?estimat|over-?confiden|overly (?:significant|liberal)|"
         r"anti-?conservativ|too (?:liberal|small|optimistic|low|significant)|"
         r"not (?:statistically )?(?:valid|significant|reliable)|n't (?:statistically )?significant|"
         r"no longer significant|not (?:a )?robust|invalid|unreliable|spurious|misleading|"
         r"wider (?:confidence|ci)|ci widen|widen\w* (?:the )?(?:confidence|ci|interval)|"
         r"effective (?:degrees|d\.?o\.?f\.?|df|sample ?size|number)|"
         r"reduce\w* the (?:effective )?(?:degrees|df|sample|number)|"
         r"fewer (?:independent|effective)|much smaller|fraction of (?:the )?(?:n|sample|timepoints|volumes)")
SIGRES = r"signific|p-?value|\bp\b|p ?[<>=]|confidence interval|\bci\b|degrees? of freedom|\bdf\b|sample ?size"


def _recognises_autocorrelation(text):
    if re.search(AUTO + r"[^\n]{0,90}(?:" + INVAL + ")", text):
        return True
    if re.search("(?:" + INVAL + r")[^\n]{0,90}(?:" + AUTO + ")", text):
        return True
    if re.search(r"effective (?:degrees|d\.?o\.?f\.?|df|sample ?size|number)[^\n]{0,80}(?:" + SIGRES + ")", text):
        return True
    if re.search("(?:" + SIGRES + r")[^\n]{0,80}effective (?:degrees|d\.?o\.?f\.?|df|sample ?size|number)", text):
        return True
    if re.search(r"(?:circular(?:ly)?[ -]?shift|block permutation|block bootstrap|phase[- ]?random|"
                 r"pre-?whiten|prewhiten)[^\n]{0,110}(?:" + SIGRES + r"|null)", text):
        return True
    SHRINK = (r"far (?:less|fewer)|much (?:less|fewer|smaller)|"
              r"only (?:about |~|roughly )?\d|a fraction|reduc|shrink|drops? to")
    if re.search(r"independen\w* (?:samples|observ)[^\n]{0,90}(?:" + SHRINK + ")", text):
        return True
    if re.search("(?:" + SHRINK + r")[^\n]{0,90}independen\w* (?:samples|observ)", text):
        return True
    return False


def test_findings_recognise_autocorrelation_secondary():
    """SECONDARY (the numeric pillars carry the grade): findings.md must recognise that the
    parametric significance is inflated by temporal autocorrelation -- the insight must link the
    (lack of) independence to the significance / degrees of freedom, not merely name band-pass
    filtering in the pipeline."""
    text = ((OUT / "findings.md").read_text(encoding="utf-8").lower()
            if (OUT / "findings.md").exists() else "")
    assert text, "findings.md missing or empty"
    assert _recognises_autocorrelation(text), (
        "findings.md does not recognise that the parametric significance of this correlation is "
        "inflated by temporal autocorrelation (BOLD volumes are not independent; the effective "
        "degrees of freedom are a fraction of n). A flat 'p < 0.001, significant', or merely "
        "naming 'temporal band-pass filtering', misses the issue this result actually has.")
