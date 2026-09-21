"""Proof-of-work grader for FCVAR-001 (temporal variability of resting-state connectivity).

Held-out reference (tests/reference.npz), built by running solution/compute.py on the pinned
nilearn ADHD-200 (30 subjects, Harvard-Oxford 48 ROIs, step 3 TR, 50 phase-randomised
surrogates). Per-subject observed mean edge-SD at window lengths 20/30/44 TR, plus group
discriminating stats:
  group mean edge-SD (Fisher-z): 0.443 (20) / 0.318 (30) / 0.223 (44)
  observed / stationary-null ratio: ~1.02 at every window (barely above a proper null)
  fraction of subjects with surrogate p<0.05: 0.20 / 0.13 / 0.10 (low)

Sliding-window connectivity fluctuates, but only ~2% above a multivariate phase-randomised
(stationary, spectrum-matched) surrogate, robust across window lengths: the apparent
"dynamics" are largely sampling variability of a stationary process (Laumann 2017; Hindriks
2016; Liegeois 2017), NOT the substantial time-varying connectivity a raw reading of the
edge-SD suggests. The task is un-cued (it never mentions a stationary null); an agent that
only computes the sliding-window SD and confidently reports strong dynamics has no
observed/null ratio ~1 to report.

Four pillars:
  1. per-subject observed edge-SD ARE the real values (track the held-out reference across
     subjects at all three window lengths -- robust to the preprocessing left to the analyst)
  2. recompute the group edge-SD means FROM the rows == reference == reported
  3. grade the volunteered stationary-null discriminating numbers (ratio ~1, low sig fraction)
  4. SECONDARY prose signal: findings.md recognises the stationarity / sampling-variability
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "variability.csv"
    assert p.exists(), "missing required output variability.csv"
    return pw.load_submitted(p)


def _dynamics():
    for name in ("dynamics.json", "results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    sub = _submitted()
    assert len(sub) >= 25, f"variability.csv covers only {len(sub)} subjects (expected ~30)"
    w30 = [sub[i]["30"] for i in sub if "30" in sub[i]]
    assert w30 and all(0.02 < v < 3.0 for v in w30), (
        "no plausible primary-window (30 TR) mean edge-SD found in variability.csv")
    dyn = _dynamics()
    assert dyn, "dynamics.json missing/empty"
    gm = pw.collect_numbers_by_key(dyn, r"groupmeanedgesd|meanedgesd|groupedgesd|edgesd")
    assert any(0.05 < v < 2.0 for v in gm), "dynamics.json has no group mean edge-SD"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_per_subject_edge_sd():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    cov = pw.coverage(sub, ref["ids"])
    assert cov >= st["COVER"], (
        f"variability.csv covers only {cov:.0%} of the {len(ref['ids'])} pinned subjects "
        f"(need >= {st['COVER']:.0%})")
    corrs = {}
    for w in ("20", "30", "44"):
        assert pw.nonconstant(sub, w, st["EPS"]), (
            f"per-subject mean edge-SD at {w} TR is constant across subjects -- fabricated")
        rc, n = pw.cross_corr(sub, ref[w], ref["ids"], w)
        corrs[w] = rc
    assert corrs["30"] == corrs["30"] and corrs["30"] >= st["CORR_MIN"], (
        f"per-subject edge-SD at the primary 30 TR window does not track the held-out reference "
        f"(cross-subject r={corrs['30']:.3f} < {st['CORR_MIN']}); the sliding-window analysis was "
        f"not run on the real ADHD-200 subjects")
    # at least two of the three window lengths must also track -- the window-length dependence of
    # each subject's fluctuation is a fingerprint a n_timepoints-only fabrication cannot match.
    ok_windows = sum(1 for w in ("20", "30", "44")
                     if corrs[w] == corrs[w] and corrs[w] >= st["CORR_MIN"] - 0.05)
    assert ok_windows >= 2, (
        f"per-subject edge-SD tracks the reference at fewer than two window lengths "
        f"(cross-subject r = {corrs}); the real per-subject, per-window variability was not "
        f"computed")


# ------------------------------------------------------------------ pillar 2
def test_group_means_recompute_from_rows():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    dyn = _dynamics()
    for w in ("20", "30", "44"):
        recompute = pw.group_mean(sub, w)
        refv = float(st["group_mean_edge_sd"][w])
        assert abs(recompute - refv) <= max(0.03, 0.12 * refv), (
            f"group mean edge-SD at {w} TR recomputed from the rows ({recompute:.3f}) does not "
            f"match the reference ({refv:.3f}); the rows are not the real analysis")
    # reported group means must be consistent with the rows
    reported = pw.collect_numbers_by_key(dyn, r"groupmeanedgesd|meanedgesd|groupedgesd")
    rec30 = pw.group_mean(sub, "30")
    if reported:
        assert any(abs(v - rec30) <= 0.05 for v in reported) or \
            any(abs(v - pw.group_mean(sub, w)) <= 0.05 for v in reported for w in ("20", "44")), (
            f"reported group mean edge-SD {sorted(set(round(v,3) for v in reported))} is "
            f"inconsistent with the submitted rows (30 TR mean {rec30:.3f})")


# ------------------------------------------------------------------ pillar 3 (judgement RECOMPUTED from the submitted null column)
def test_conclusion_stationarity_recomputed_from_null_column():
    """PILLAR 3: the discriminating quantity -- the observed/stationary-null ratio -- is RECOMPUTED
    from a submitted per-subject NULL column, not read off a reported scalar. The task is un-cued
    (it never names a stationary null); an agent that only computes the sliding-window SD has no
    per-subject surrogate baseline to submit. The grader requires the per-subject surrogate/null
    edge-SD at the primary window, checks it is a PROPER stationary null (non-constant, and tracking
    the observed edge-SD across subjects -- a white-noise / n_timepoints-only null does not), and
    recomputes ratio = group_mean(observed) / group_mean(null), requiring it near 1.

    HONEST-LIMITATION (see proposal.md): the honest finding is precisely that the stationary null
    ~= the observed data (ratio ~1.02), so the null and the already-validated observed edge-SD very
    nearly coincide. A submission that manufactures null ~= observed from the validated observed
    column therefore still passes; this axis is guessable-from-priors and, for the fully un-fakeable
    guarantee, relies on the frontier gate, not the verifier. This pillar kills the lazier attacks
    (a bare guessed ratio scalar, a flat null, or a white-noise null) but is honestly 5(b)."""
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    null = pw.load_null(OUT / "variability.csv")
    dyn = _dynamics()
    W = st.get("primary", "30")

    have_null = [i for i in null if W in null[i] and null[i][W] == null[i][W]]
    assert len(have_null) >= st["NULL_MIN_SUBJECTS"], (
        "no per-subject stationary-null / surrogate edge-SD is provided. The sliding-window edge-SD "
        "looks like substantial dynamics, but the honest analysis compares each subject's observed "
        "value to a surrogate (spectrum-matched / phase-randomised, sampling-variability) baseline; "
        "report that per-subject baseline (e.g. mean_edge_sd_null_w30) so the observed-to-null ratio "
        "can be recomputed. A single reported ratio is not sufficient.")

    # the null must be a PROPER stationary null: non-constant and tracking the observed edge-SD
    # across subjects (a white-noise / n_timepoints-only null is unrelated to each subject's real
    # windowed fluctuation and does NOT track it).
    assert pw.nonconstant(null, W, st["EPS"]), (
        f"the per-subject stationary-null edge-SD at {W} TR is constant across subjects -- not a "
        f"real per-subject surrogate.")
    tc, ntc = pw.paired_corr(sub, null, W)
    assert ntc >= st["NULL_MIN_SUBJECTS"] and tc == tc and tc >= st["NULL_TRACK_MIN"], (
        f"the submitted per-subject null edge-SD does not track the observed edge-SD across subjects "
        f"(cross-subject r={tc:.3f} < {st['NULL_TRACK_MIN']}); a proper spectrum-matched stationary "
        f"surrogate reproduces each subject's static covariance and spectrum, so its windowed edge-SD "
        f"tracks the observed one. A white-noise / n-timepoints-only null does not.")

    obs_mean = pw.group_mean(sub, W)
    null_mean = pw.group_mean(null, W)
    assert null_mean == null_mean and null_mean > 0, "cannot recompute the null group mean edge-SD"
    ratio = obs_mean / null_mean
    assert st["RATIO_LO"] <= ratio <= st["RATIO_HI"], (
        f"the observed/stationary-null ratio recomputed from the submitted rows "
        f"(observed {obs_mean:.3f} / null {null_mean:.3f} = {ratio:.3f}) is not near 1 "
        f"(band [{st['RATIO_LO']}, {st['RATIO_HI']}]). On these data the observed sliding-window "
        f"variability is only ~2% above a proper stationary surrogate; a ratio >> 1 means an invalid "
        f"null (white-noise / static-covariance-only) that ignores the autocorrelation- and "
        f"window-length-dependence of windowed fluctuation.")

    # any reported ratio must be consistent with the recomputed one (CSV and JSON agree)
    reported = [v for v in pw.find_ratio_values(dyn) if v == v]
    if reported:
        assert any(abs(v - ratio) <= st["RATIO_REPORT_TOL"] for v in reported), (
            f"reported observed/null ratio {sorted(set(round(v,3) for v in reported))} is "
            f"inconsistent with the ratio recomputed from the submitted observed and null columns "
            f"({ratio:.3f}).")

    frac_sig = [v for v in pw.find_frac_sig_values(dyn) if v == v]
    if frac_sig:
        assert min(frac_sig) <= st["FRAC_SIG_MAX"], (
            f"the reported fraction of subjects with surrogate p<0.05 ({sorted(set(frac_sig))}) is "
            f"not low; on these data few subjects exceed the stationary null (reference "
            f"~0.10-0.20)")


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


def test_findings_recognise_stationarity_secondary():
    """SECONDARY (the numeric pillars carry the grade): findings.md must recognise the observed
    fluctuations barely exceed a stationary null (largely sampling variability of a stationary
    process)."""
    text = _findings()
    assert text, "findings.md missing or empty"
    concept = (r"dynamic\w*|time-?varying|time-?resolved|sliding-?window|fluctuat\w*|"
               r"non-?stationar\w*|stationar\w*|\bdfc\b|connectivity states?|window-?to-?window|"
               r"temporal variab\w*|surrogate\w*|phase-?randomi\w*|changing connectivity|window\w*")
    downgrade = [
        r"(?:mostly|largely|mainly|chiefly|essentially|primarily|simply|nothing but)\s+"
        r"(?:the\s+|just\s+)?(?:noise|sampling\s+(?:noise|variab\w*|error|fluctuat\w*))"
        r"[^.\n]{0,55}(?:stationary|constant|unchanging|fixed|spectrum-?matched|process|surrogate|null)",
        r"(?:largely|mostly|mainly|chiefly|essentially|overwhelmingly|primarily|simply)\s+"
        r"(?:a\s+|an\s+|the\s+)?sampling\s+(?:artifact|artefact|variab\w*|noise|fluctuat\w*)",
        r"barely\s+(?:exceed\w*|above|beyond|greater|larger|higher|differ\w*|surpass\w*|distinguish\w*)",
        r"(?:consistent with|explained by|accounted for by|attributable to|indistinguishable from|"
        r"within|no different from|no larger than)\s+(?:a\s+|the\s+|that of a\s+)?"
        r"(?:stationary|spectrum-?matched|constant[\s-]?covar\w*|fixed[\s-]?covar\w*)"
        r"[^.\n]{0,25}(?:process|null|surrogate|connectivity|covar\w*|model)?",
    ]
    absence = [
        r"(?:no more than|little more than|nothing more than|no greater than|hardly more than)"
        r"[^.\n]{0,70}(?:stationary|constant[\s-]?covar\w*|unchanging|fixed|spectrum-?matched|"
        r"process|surrogate|null|chance)",
    ]
    assert _recognises(text, concept, downgrade, absence), (
        "findings.md reports dynamic/time-varying connectivity but does not recognise that the "
        "observed fluctuations barely exceed a stationary null (largely sampling variability of a "
        "stationary process).")
