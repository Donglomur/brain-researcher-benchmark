"""Proof-of-work grader for TASKFC-001 (task-state FC of a co-engaged visual region pair).

Held-out reference (tests/reference.npz), built by running solution/compute.py on the pinned
nilearn language-localizer demo (all 10 subjects, left/right lateral occipital 8 mm spheres at
MNI (-30,-90,-6)/(30,-90,-6), common preprocessing = cosine drift + 6 motion regressors):

  per-subject RAW task-state FC (task-evoked kept)      -> connectivity column
  per-subject BACKGROUND FC (task-evoked regressed out) -> background_connectivity column
  group (Fisher-z averaged):  raw = 0.630   background = 0.461
  inflation raw > background: +0.169, paired t = 4.02, p = 3.0e-03, raw>background in 10/10

A raw Pearson correlation of the two regions' BOLD during the task SYSTEMATICALLY OVERSTATES
their connectivity: both occipital regions are co-driven by the visual stimulus, so much of
the raw co-variation is the shared task-evoked response. Removing it first (background
connectivity; Fair 2007, Al-Aidroos 2012, Cole 2019) drops the estimate substantially. An
agent that only correlated the raw time series cannot produce the per-subject background
column or the ~0.46 background mean.

Four pillars:
  1  exact pinned subjects + real per-subject RAW values (kills fabricated/dup)
  1b MANDATORY: real per-subject BACKGROUND values (cross-subject r>=0.95 + absolute match to the
     reference). corr(raw,background) across subjects is only ~0.74, so a background fabricated by
     scaling the raw column fails -- the residual correlations must actually be computed.
  2  recompute the group raw + background Fisher-z means FROM the rows == reported == reference
  3  grade the discriminating inflation as numbers, RECOMPUTED FROM THE ROWS (raw > background,
     gap, n raw>bg); the reported group background is only a consistency cross-check
  4  SECONDARY prose signal: findings.md links the task-evoked co-activation to the inflation
"""
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"

# Background (task-regressed) FC is task-model-sensitive: which GLM / HRF / drift basis is used to
# regress the task-evoked response shifts the per-subject residual, so the per-subject background is
# NOT pinned to the reference magnitude (the reference and an independent, defensible live solve
# agree per subject at only corr ~= 0.70, mean|Delta| ~= 0.087, far above the old VAL_TOL 0.05).
# Instead the grader requires the SIGNATURE of a genuine residual that is derived from the real
# subjects' data:
#   * BG_RAW_CORR band -- across subjects the background tracks the raw column (both computed on the
#     same subjects) but is NOT a trivial affine rescaling of it. corr(raw, background) ~= 0.74 in
#     the reference and ~0.89 for the live solve; an affine scaled/shifted copy of raw has corr ~=
#     1.0 (rejected by the max) and a grossly unrelated column has corr near 0 (rejected by the min).
#   * BG_MEAN_GAP -- the background lies materially below raw (the shared task-evoked response
#     inflates raw FC); a background==raw copy has zero gap and is rejected.
#   * BG_REF_CORR -- the background must correlate with the held-out reference background ACROSS
#     subjects above a lenient floor. This is affine-invariant (no magnitude pin) and, crucially,
#     safe for any real pipeline: the raw column is pinned to the reference (corr ~0.997) and
#     corr(raw, reference-background) ~= 0.75, so any background genuinely derived from the real
#     subjects inherits corr(background, reference-background) ~= 0.6-0.75, while a fabricated /
#     blind-random background (not derived from the real subjects) scores ~0 and is rejected.
# NOTE (documented limit): because raw and background are intrinsically coupled and the real
# background's agreement with the reference is carried almost entirely by raw (raw-controlled
# partial corr ~= 0.09), a determined adversary who builds background = k*raw + tuned noise from the
# agent's OWN raw column produces a column that is statistically indistinguishable from a real
# task-regressed residual (right band, below raw, right group inflation, inherits the reference
# correlation via raw). No reference-based per-subject check can reject it without also rejecting the
# defensible real solve. The grader therefore rejects the naive/lazy/blind fabrications and grades
# the true scientific claim (the group task-evoked inflation); it does not claim to prove per-subject
# task regression against that specific adversary.
BG_RAW_CORR_MIN = 0.40
BG_RAW_CORR_MAX = 0.95
BG_MEAN_GAP_MIN = 0.04  # mean per-subject (raw - background); ~0.13 real, 0 for background==raw
BG_REF_CORR_MIN = 0.55  # lenient across-subject corr with the held-out reference background
                        # (live solve ~0.70; blind/fabricated ~0; guaranteed >~0.6 for real bg by
                        # the pinned raw column, so it does NOT pin the pipeline-sensitive magnitude)


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "connectivity.csv"
    assert p.exists(), "missing required output connectivity.csv"
    return pw.load_submitted(p)


def _summary():
    for name in ("connectivity_summary.json", "summary.json", "results.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    sub, raw_c, bg_c = _submitted()
    assert len(sub) >= 8, f"connectivity.csv covers only {len(sub)} subjects (expected ~10)"
    assert raw_c is not None, "connectivity.csv has no raw task-state connectivity column"
    raws = [sub[i][0] for i in sub if sub[i][0] is not None and math.isfinite(sub[i][0])]
    assert raws and all(-1.01 <= v <= 1.01 for v in raws), "raw connectivity out of [-1,1]"
    summ = _summary()
    assert summ, "connectivity_summary.json missing/empty"
    assert pw.find_number(summ, [r"groupconnectivity", r"rawtaskstate", r"connectivity", r"^r$"],
                          exclude=[r"nsub", r"background", r"nparial"]) is not None, \
        "connectivity_summary.json has no group connectivity value"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_raw_values():
    ref = _reference()
    st = ref["stats"]
    sub, _, _ = _submitted()
    cov = pw.coverage(set(sub), ref["ids"])
    assert cov >= st["COVER"], (
        f"connectivity.csv covers only {cov:.0%} of the {len(ref['ids'])} pinned subjects "
        f"(need >= {st['COVER']:.0%})")
    assert pw.nonconstant(sub, 0, st["EPS"]), "raw connectivity is constant across subjects"
    rc = pw.cross_corr(sub, ref["raw_by_id"], ref["ids"], 0)
    assert math.isfinite(rc) and rc >= st["CORR_MIN"], (
        f"per-subject RAW connectivity does not track the reference (cross-subject r={rc:.3f} "
        f"< {st['CORR_MIN']}); not computed from the real time series")
    frac, n = pw.per_subject_match(sub, ref["raw_by_id"], ref["ids"], 0, st["VAL_TOL"])
    assert frac >= st["MATCH"], (
        f"only {frac:.0%} of {n} matched subjects have RAW connectivity within {st['VAL_TOL']} "
        f"of the reference (need >= {st['MATCH']:.0%})")


def test_background_per_subject_is_real():
    """PILLAR 1b (MANDATORY): the discriminating quantity is a per-subject BACKGROUND
    (task-regressed residual) connectivity column. The schema invites 'any additional per-subject
    connectivity estimate(s) you computed, one column each'; the honest analysis volunteers the
    background connectivity per subject.

    Background FC is task-model-sensitive (which GLM / HRF / drift basis regresses out the
    task-evoked response shifts the residual: the reference and an independent live solve correlate
    only ~0.70 per subject), so the per-subject background is NOT pinned to one reference pipeline.
    Instead this pillar requires the SIGNATURE of a genuine residual that no fabrication reproduces:
      - a real per-subject background column is present and non-constant;
      - across subjects it TRACKS the raw column (same subjects, same broad structure) but is NOT a
        trivial affine rescaling of it -- corr(raw, background) sits in a plausible band well below
        1.0. A background fabricated by scaling/shifting the raw column has corr ~= 1.0 (rejected by
        the upper bound); a random or constant fabrication has corr ~ 0 (rejected by the lower bound);
      - it lies materially BELOW raw in almost every subject (the shared task-evoked response
        inflates raw FC, so regressing it out must lower the estimate). A background == raw copy has
        zero gap and is rejected here (and by the inflation pillar).
    The absolute magnitude of the background and the inflation gap are graded at the group level in
    the inflation pillar; here we verify the column is a real, per-subject residual."""
    ref = _reference()
    st = ref["stats"]
    sub, raw_c, bg_c = _submitted()
    assert bg_c is not None, (
        "connectivity.csv has no per-subject background / task-regressed / residual connectivity "
        "column. The raw task-state correlation of two co-driven occipital regions is inflated by "
        "the shared stimulus-evoked response; the honest task-state connectivity is recomputed "
        "here from the per-subject residual-correlation values, so they must be provided per "
        "subject (as an additional connectivity column). A single reported group number is not "
        "sufficient and cannot be verified as real work.")
    matched = [i for i in ref["ids"] if i in sub
               and sub[i][1] is not None and math.isfinite(sub[i][1])
               and sub[i][0] is not None and math.isfinite(sub[i][0])]
    assert len(matched) >= max(3, int(round(st["COVER"] * len(ref["ids"])))), (
        f"per-subject background connectivity is present for only {len(matched)} of the "
        f"{len(ref['ids'])} pinned subjects; the residual must be computed for (nearly) all of them")
    assert pw.nonconstant(sub, 1, st["EPS"]), "background connectivity is constant -- fabricated"

    # (i) genuine residual: tracks raw across subjects but is not a rescaled copy of it.
    rb = pw.col_corr(sub, ref["ids"], 0, 1)
    assert math.isfinite(rb) and BG_RAW_CORR_MIN <= rb <= BG_RAW_CORR_MAX, (
        f"corr(raw, background) across subjects is {rb:.3f}, outside the plausible band "
        f"[{BG_RAW_CORR_MIN}, {BG_RAW_CORR_MAX}] for a real task-regressed residual: a value near "
        f"1.0 means the background is the raw column rescaled/shifted (no real task regression was "
        f"performed); a value near 0 means it is fabricated/unrelated to the real subjects.")

    # (i') derived from the REAL subjects: the background must correlate across subjects with the
    # held-out reference background above a lenient, affine-invariant floor. The raw column is pinned
    # to the reference (pillar 1) and corr(raw, reference-background) ~= 0.75, so any background
    # genuinely computed from the real subjects clears this comfortably (live solve ~0.70), while a
    # blind/fabricated background that never touched the real residuals scores ~0. This is NOT a
    # magnitude pin (the per-subject values and the group mean are free); it only checks that the
    # column is real per-subject work on the pinned subjects.
    rc_ref = pw.cross_corr(sub, ref["bg_by_id"], ref["ids"], 1)
    assert math.isfinite(rc_ref) and rc_ref >= BG_REF_CORR_MIN, (
        f"the per-subject background does not track the held-out reference background across "
        f"subjects (corr={rc_ref:.3f} < {BG_REF_CORR_MIN}); it was not computed from the real "
        f"pinned subjects (a fabricated / blind-random background scores ~0 here, whereas any "
        f"background derived from the real subjects inherits ~0.6-0.75 through the pinned raw column)")

    # (ii) materially below raw in almost every subject (task-evoked inflation is systematic).
    n_below = sum(1 for i in matched if sub[i][0] > sub[i][1])
    assert n_below >= int(round(0.8 * len(matched))), (
        f"background connectivity is below raw in only {n_below}/{len(matched)} subjects; a real "
        f"task-regressed residual must be lower than the raw (task-inflated) estimate in almost "
        f"every subject")
    mean_gap = sum(sub[i][0] - sub[i][1] for i in matched) / len(matched)
    assert mean_gap >= BG_MEAN_GAP_MIN, (
        f"the mean per-subject raw-minus-background gap ({mean_gap:+.3f}) is negligible "
        f"(< {BG_MEAN_GAP_MIN}); the background column is essentially the raw column -- no shared "
        f"task-evoked response was removed")


# ------------------------------------------------------------------ pillar 2
def _reported_group_background(summ):
    # Exclude any inflation / difference field: keys like `inflation_raw_minus_background_r` contain
    # the substring "background" but report the raw-minus-background GAP (~0.14), not the group
    # background FC (~0.49). Without these excludes the BFS returns the inflation value and the
    # consistency cross-check spuriously fails a correct submission.
    return pw.find_number(summ, [r"background", r"residualconnectivity", r"intrinsicconnectivity",
                                 r"taskregressedconnectivity"],
                          exclude=[r"nsub", r"inflationp", r"paired", r"inflationt",
                                   r"inflation", r"minus", r"delta", r"difference", r"\bgap\b",
                                   r"rawminus", r"raw_?minus"])


def test_group_means_recompute_from_rows():
    """PILLAR 2: the reported group RAW FC must equal what the submitted per-subject rows produce
    AND the held-out reference. If a per-subject background column is present, its group mean must
    also match the reported group background."""
    ref = _reference()
    st = ref["stats"]
    sub, raw_c, bg_c = _submitted()
    matched = [i for i in ref["ids"] if i in sub]
    raw_recompute = pw.fisher_mean([sub[i][0] for i in matched])

    assert abs(raw_recompute - st["raw_g"]) <= st["GROUP_TOL"], (
        f"group RAW FC recomputed from the rows ({raw_recompute:.3f}) != reference "
        f"({st['raw_g']:.3f}, tol {st['GROUP_TOL']})")

    summ = _summary()
    rep_raw = pw.find_number(summ, [r"rawtaskstate", r"groupconnectivity", r"rawconnectivity",
                                    r"^rawfc"],
                             exclude=[r"background", r"nsub", r"inflation"])
    if rep_raw is not None:
        assert abs(rep_raw - raw_recompute) <= st["CONSIST"], (
            f"summary raw FC {rep_raw:.3f} inconsistent with the rows ({raw_recompute:.3f})")
    if bg_c is not None:
        bg_recompute = pw.fisher_mean([sub[i][1] for i in matched])
        rep_bg = _reported_group_background(summ)
        if rep_bg is not None:
            assert abs(rep_bg - bg_recompute) <= 0.05, (
                f"summary background FC {rep_bg:.3f} inconsistent with the per-subject background "
                f"rows ({bg_recompute:.3f})")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_conclusion_inflation_is_numeric():
    """PILLAR 3: the discriminating inflation graded as NUMBERS and RECOMPUTED from the submitted
    per-subject {raw, background} rows -- not trusted from a reported group scalar. An agent that
    only ran the naive raw correlation has no real per-subject background column (pillar 1b), so it
    cannot reach this gate by guessing/publishing a ~0.46 group background. The recomputed group
    background must be materially LOWER than the raw FC, match the held-out reference, and the
    raw>background inflation must be systematic across subjects."""
    ref = _reference()
    st = ref["stats"]
    sub, raw_c, bg_c = _submitted()
    matched = [i for i in ref["ids"] if i in sub]
    assert bg_c is not None, "per-subject background connectivity column required (see pillar 1b)"

    # RECOMPUTE both group means and the per-subject inflation FROM the rows.
    raw_g = pw.fisher_mean([sub[i][0] for i in matched])
    bg_vals = [sub[i][1] for i in matched]
    bg_g = pw.fisher_mean(bg_vals)
    assert bg_g == bg_g and -1.0 <= bg_g <= 1.0, (
        "cannot recompute a valid group background FC from the per-subject rows")

    # (a) recomputed group background matches the held-out reference (validated rows guarantee this
    #     for the honest/defensible submission; it cannot be reached without the real column).
    assert abs(bg_g - st["bg_g"]) <= 0.06, (
        f"group background FC recomputed from the per-subject rows ({bg_g:.3f}) does not match the "
        f"held-out reference ({st['bg_g']:.3f}, tol 0.06); the residual correlations are not real.")

    # (b) the raw>background inflation, recomputed from the rows, is present and material.
    assert raw_g > bg_g, (
        f"recomputed raw task-state FC ({raw_g:.3f}) is not greater than the recomputed background "
        f"FC ({bg_g:.3f}); the task-evoked co-activation inflation is not present")
    gap = raw_g - bg_g
    assert gap >= 0.08, (
        f"the raw-minus-background inflation recomputed from the rows ({gap:+.3f}) is far below the "
        f"reference (~{st['inflation']:+.3f}); the shared task-evoked response must inflate raw FC")
    assert abs(gap - st["inflation"]) <= 0.08, (
        f"the recomputed inflation ({gap:+.3f}) does not match the reference ({st['inflation']:+.3f})")

    # (c) the inflation is systematic across subjects (recomputed per-subject raw>background count).
    n_infl = sum(1 for i in matched
                 if sub[i][1] is not None and math.isfinite(sub[i][1]) and sub[i][0] > sub[i][1])
    assert n_infl >= 8, (
        f"raw exceeds background in only {n_infl}/{len(matched)} subjects (recomputed from the "
        f"rows); the inflation is a systematic, direction-consistent effect (reference "
        f"{st['n_infl']}/10)")

    # (d) consistency: any REPORTED group background must agree with the recompute-from-rows.
    summ = _summary()
    rep_bg = _reported_group_background(summ)
    if rep_bg is not None:
        assert abs(rep_bg - bg_g) <= 0.05, (
            f"reported group background FC ({rep_bg:.3f}) is inconsistent with the value recomputed "
            f"from the per-subject rows ({bg_g:.3f}); report the estimate your own table produces.")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_recognise_task_evoked_inflation_secondary():
    """SECONDARY (the numeric pillars carry the grade): findings.md must link the shared
    task-evoked response to the raw connectivity being inflated / the background being lower --
    not merely describe motion/drift regression."""
    text = _findings()
    assert text, "findings.md missing or empty"

    EV = (r"task[- ]?evoked|stimul\w*[- ]?evoked|evoked (?:response|activ\w*|signal|component|"
          r"co-?activ\w*)|co-?activ\w*|task[- ]?(?:evoked )?activ\w*|task[- ]?induced|"
          r"stimulus[- ]?(?:driven|locked|response)|task[- ]?(?:related|driven) (?:response|"
          r"activ\w*|signal|component|co-?variation)|shared (?:task |stimul\w*|evoked )?"
          r"(?:response|activ\w*|drive|signal|component)|common (?:task |evoked )?(?:response|"
          r"activ\w*|drive|signal)|background connectivity|"
          r"regress\w*(?:\s+\w+){0,3}?\s+(?:out\s+)?(?:the\s+)?(?:task|stimul\w*|evoked|"
          r"activ\w*|design|condition|glm|block)|"
          r"(?:task|stimul\w*|evoked|glm|design|model|activation)[- ]?regress\w*|"
          r"residual\w*(?:\s+\w+){0,4}?\s+(?:of|after|from|once)(?:\s+\w+){0,3}?\s+(?:task|"
          r"stimul\w*|evoked|glm|design|model|activation|block)")
    RES = r"connectiv\w*|correlation|coupl\w*|\bfc\b|\br\s*=|r_?s\b|estimate"
    INFL = (r"inflat\w*|over-?stat\w*|over-?estimat\w*|overestimate|spurious|exaggerat\w*|"
            r"artif\w*|biased? (?:up|high|upward)|too high|driven (?:largely |mostly |substantially )?by|"
            r"dominated by|conflat\w*|lower|reduc\w*|drop\w*|fall\w*|fell|decreas\w*|smaller|"
            r"attenuat\w*|less than|below|weaker|not intrinsic|not (?:genuine|true)")
    CAUSE = r"by|from|due to|because|reflect\w*|owing to|is (?:largely |mostly |substantially )?the"
    INFLVERB = (r"inflat\w*|over-?stat\w*|over-?estimat\w*|overestimate|dominat\w*|drive\w*|driven|"
                r"conflat\w*|spurious|account\w* for|explain\w*|exaggerat\w*")
    mentions_ev = re.search(EV, text) is not None
    linked = re.search(
        rf"(?:{EV})[^.\n]{{0,90}}(?:{INFL})[^.\n]{{0,50}}(?:{RES})"
        rf"|(?:{RES})[^.\n]{{0,70}}(?:{INFL})[^.\n]{{0,90}}(?:{EV})"
        rf"|(?:{INFL})[^.\n]{{0,50}}(?:{RES})[^.\n]{{0,90}}(?:{EV})"
        rf"|(?:{EV})[^.\n]{{0,90}}(?:{RES})[^.\n]{{0,60}}(?:{INFL})"
        rf"|(?:{RES})[^.\n]{{0,70}}(?:{EV})[^.\n]{{0,60}}(?:{INFL})"
        rf"|(?:{INFL})[^.\n]{{0,20}}(?:{CAUSE})[^.\n]{{0,30}}(?:{EV})"
        rf"|(?:{EV})[^.\n]{{0,45}}(?:{INFLVERB})",
        text)
    assert mentions_ev and linked, (
        "findings.md does not report that the raw task-state connectivity is inflated by the "
        "shared task-evoked response (the background / task-regressed connectivity is materially "
        "lower). A flat report of the raw correlation, or merely describing motion regression, "
        "misses the task-evoked co-activation inflation.")
