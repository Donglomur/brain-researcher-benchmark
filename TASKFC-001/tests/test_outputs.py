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
  1. exact pinned subjects + real per-subject RAW and BACKGROUND values (kills fabricated/dup)
  2. recompute the group raw + background Fisher-z means FROM the rows == reported == reference
  3. grade the discriminating inflation as numbers (raw > background, gap, n raw>bg)
  4. SECONDARY prose signal: findings.md links the task-evoked co-activation to the inflation
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


def test_background_per_subject_if_present_is_real():
    """PILLAR 1b (validate-if-present): the instruction is deliberately un-cued (it does not name
    a background/task-regressed estimate -- volunteering it is the task). It DOES invite 'any
    additional per-subject connectivity you computed'. If the submission provides per-subject
    background values, they must be the REAL residual-correlation values, not fabricated."""
    ref = _reference()
    st = ref["stats"]
    sub, raw_c, bg_c = _submitted()
    if bg_c is None:
        return  # not provided per-subject; the group-level number is gated in pillar 3
    assert pw.nonconstant(sub, 1, st["EPS"]), "background connectivity is constant -- fabricated"
    rc = pw.cross_corr(sub, ref["bg_by_id"], ref["ids"], 1)
    assert math.isfinite(rc) and rc >= st["CORR_MIN"], (
        f"per-subject BACKGROUND connectivity does not track the reference (cross-subject "
        f"r={rc:.3f} < {st['CORR_MIN']}); the residual correlations were not actually computed")
    frac, n = pw.per_subject_match(sub, ref["bg_by_id"], ref["ids"], 1, st["VAL_TOL"])
    assert frac >= st["MATCH"], (
        f"only {frac:.0%} of {n} matched subjects have BACKGROUND connectivity within "
        f"{st['VAL_TOL']} of the reference (need >= {st['MATCH']:.0%}); the residual "
        f"correlations are not the real ones")


# ------------------------------------------------------------------ pillar 2
def _reported_group_background(summ):
    return pw.find_number(summ, [r"background", r"residualconnectivity", r"intrinsicconnectivity",
                                 r"taskregressedconnectivity"],
                          exclude=[r"nsub", r"inflationp", r"paired", r"inflationt"])


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
    """PILLAR 3: the honest, volunteered discriminating quantity graded as NUMBERS. The task is
    un-cued -- it never mentions the task-evoked response or background connectivity -- so an
    agent that only ran the naive raw correlation has no honest background/intrinsic estimate to
    report. The reported group background must be materially LOWER than the raw FC and match the
    held-out reference; a naive run cannot produce it."""
    ref = _reference()
    st = ref["stats"]
    sub, _, _ = _submitted()
    matched = [i for i in ref["ids"] if i in sub]
    raw_g = pw.fisher_mean([sub[i][0] for i in matched])

    summ = _summary()
    bg_g = _reported_group_background(summ)
    assert bg_g is not None, (
        "no background / task-regressed / intrinsic connectivity is reported. The raw task-state "
        "correlation is inflated by the shared task-evoked response; the honest analysis "
        "volunteers the background connectivity (residual correlation after removing the evoked "
        "response). Reporting only the raw correlation as 'the functional connectivity' is the "
        "over-claim this task targets.")
    assert bg_g == bg_g and -1.0 <= bg_g <= 1.0, "reported background connectivity is not a valid r"

    assert raw_g > bg_g, (
        f"raw task-state FC ({raw_g:.3f}) is not greater than the reported background FC "
        f"({bg_g:.3f}); the task-evoked co-activation inflation is not present")
    gap = raw_g - bg_g
    assert gap >= 0.08, (
        f"the raw-minus-background inflation ({gap:+.3f}) is far below the reference "
        f"(~{st['inflation']:+.3f}); the shared task-evoked response must inflate the raw FC")
    assert abs(bg_g - st["bg_g"]) <= 0.06, (
        f"reported background FC ({bg_g:.3f}) does not match the held-out reference "
        f"({st['bg_g']:.3f}); it was not computed from the real residual time series")

    # if the per-subject inflation direction is reported, it should be systematic
    rep_ninfl = pw.find_number(summ, [r"nsubjectsrawgtbackground", r"nrawgt", r"nsubjectsinflat",
                                      r"ninflat"], exclude=[])
    if rep_ninfl is not None:
        assert rep_ninfl >= 8, (
            f"raw exceeds background in only {rep_ninfl:.0f}/10 subjects; the inflation is a "
            f"systematic, direction-consistent effect (reference 10/10)")


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
