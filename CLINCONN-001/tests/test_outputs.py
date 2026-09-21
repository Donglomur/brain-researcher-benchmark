"""Proof-of-work grader for CLINCONN-001 — reproduce the schizophrenia-vs-control resting-FC
difference on ds000030 and report whether it survives control for head motion.

The maintainer's audit of the previous verifier: it checked value ranges + a keyword sentence
in findings.md, so it passed on fabricated constant tables plus a motion-mentioning sentence.
This grader closes that. It validates the EXACT ds000030 subjects and their per-subject
connectivity against a held-out reference (tests/reference.npz, built from the oracle run and
never shipped to the agent), recomputes the naive group contrast FROM the submitted rows,
cross-checks CSV<->JSON, and grades the scientific judgement AS NUMBERS: the group difference
present at face value must COLLAPSE toward null when head motion is controlled (the patients
move ~55% more), matching the held-out reference. Keyword prose is only a secondary signal.

Reference (ds000030 R1.0.5 fMRIPrep rest, fsaverage5 Destrieux, 50 SCHZ + 122 CONTROL):
  naive short-range FC group t = +2.11 (p 0.038)   <- present at face value
  FD-controlled short-range t  = -0.08 (p 0.94)    <- collapses toward null
  edgewise |t|>2  14.4% -> 7.4% (~chance) controlling FD
  mean FD  SCHZ 0.253 vs CONTROL 0.161 (MWU p 4e-5)  <- patients move far more
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


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "connectivity.csv"
    assert p.exists(), "missing required output connectivity.csv"
    return pw.load_submitted(p)


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _findings():
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


# ---- report extractors (schema-tolerant, path-aware) ------------------------------------
_T_LEAF = r"^t$|^tstat|^tstatistic$|^statistic$|^tval|^tvalue$|welcht"


def _naive_short_t(j):
    return pw.find_path_number(
        j, path_include=["short"], leaf_re=_T_LEAF,
        path_exclude=["motion", "framewise", "covar", "controll", "adjust", "matched",
                      "residual", "qcfc", "displacement", "partial", "long"],
        prefer=["naive", "raw", "grouptest", "ttest", "welch", "uncontroll", "uncorrect"])


# A reported short-range t is treated as the MOTION-CONTROLLED estimate only when its path is
# EXPLICITLY labelled as motion / FD-controlled / adjusted / covaried / matched. This is a hard
# requirement (path_require_any), not a soft preference: otherwise the picker falls back to the
# only short-range t present -- the NAIVE (raw, uncontrolled) group t -- and the reported-vs-recompute
# cross-check wrongly compares the raw t (~+2.11) against the FD-controlled recompute (~-0.08) and
# fails a correct submission. Raw / uncontrolled / crude labels are excluded outright. When no
# explicitly-controlled short t is reported, this returns None and pillar 3(d) SKIPS the cross-check
# and grades off the FD-covariate recompute from the rows (which is authoritative).
_FD_CONTROL_MARKERS = ["motioncontroll", "motioncontrol", "fdcontroll", "fdcontrol", "fdcovariate",
                       "fdcovar", "covariate", "covary", "motionmatched", "motionadjust",
                       "fdadjust", "adjustedforfd", "adjustedformotion", "controlledforfd",
                       "controlledformotion", "controllingforfd", "controllingformotion",
                       "framewise", "headmotion", "motion", "fd"]
_RAW_MARKERS = ["raw", "naive", "uncontroll", "uncorrect", "uncontrol", "crude", "facevalue",
                "unadjust", "atfacevalue"]


def _fd_short_t(j):
    return pw.find_path_number(
        j, path_include=["short"], leaf_re=_T_LEAF,
        path_exclude=["qcfc", "residual", "long"] + _RAW_MARKERS,
        path_require_any=_FD_CONTROL_MARKERS,
        prefer=["motioncontroll", "fdcovariate", "fdcontroll", "motionmatched", "covariate",
                "framewise", "adjust", "controll", "motion", "matched"])


def _mean_fd(j, grp):
    return pw.find_path_number(
        j, path_include=["fd", grp], leaf_re=None,
        path_exclude=["mwu", "diff", "vs", "gt", "thresh", "residual", "pval"],
        prefer=["meanfd", "motion", "headmotion"]) or pw.find_path_number(
        j, path_include=["framewise", grp], path_exclude=["mwu", "diff", "pval"])


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub = _submitted()
    assert len(sub) >= 100, (
        f"connectivity.csv must carry per-subject connectivity for the ds000030 cohort; "
        f"parsed {len(sub)} usable rows")
    shorts = [v["short"] for v in sub.values()]
    assert all(-1.5 <= v <= 1.5 for v in shorts), "short_range_fc out of plausible range"
    groups = {v["group"] for v in sub.values()}
    assert "schz" in groups and "control" in groups, (
        f"both diagnostic groups must be present for a group comparison; saw {groups}")
    # mean framewise displacement is a required per-subject QC column; the motion-conditioned group
    # comparison is recomputed from it below, so it must be present and non-constant.
    fds = [v["fd"] for v in sub.values() if v.get("fd") is not None]
    assert len(fds) >= 100, (
        "connectivity.csv is missing the per-subject mean_fd (mean framewise displacement) column. "
        "It is a standard motion QC summary from the fMRIPrep confounds and is required per subject.")
    assert all(0 <= v < 5 for v in fds), "mean_fd values out of plausible range (mm)"

    j = _load_json("group_stats.json")
    assert isinstance(j, dict) and j, "group_stats.json is empty"
    meta = _load_json("run_metadata.json")
    assert isinstance(meta, dict) and meta, "run_metadata.json is empty"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference()
    sub = _submitted()
    st = ref["stats"]
    pw.check_subjects_and_values(sub, ref, val_tol=st["VAL_TOL"], corr_min=st["CORR_MIN"],
                                 cover=st["COVER"], match=st["MATCH"], eps=st["EPS"])
    # the per-subject mean_fd column must be the REAL framewise-displacement summary (fabrication
    # teeth for the motion-conditioned collapse recomputed in pillar 3).
    import numpy as _np
    assert not _np.isnan(ref["fd"]).all(), "reference is missing per-subject FD (rebuild reference.npz)"
    pw.check_fd_column(sub, ref, val_tol=st["FD_VAL_TOL"], corr_min=st["FD_CORR_MIN"],
                       cover=st["COVER"], match=st["FD_MATCH"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_and_crosscheck():
    ref = _reference()
    sub = _submitted()
    st = ref["stats"]
    matched = [i for i in sub if i in set(ref["ids"])]
    t_rows, n_s, n_c = pw.recompute_naive_short_t(sub, matched, ref)
    import math
    assert math.isfinite(t_rows), "cannot recompute the naive short-range group t from the rows"
    assert abs(t_rows - st["naive_short_t"]) <= st["RECOMP_TOL"], (
        f"naive short-range group t recomputed from the submitted rows ({t_rows:+.3f}) does not "
        f"match the reference ({st['naive_short_t']:+.3f}, tol {st['RECOMP_TOL']}). The rows are "
        f"not the real analysis.")

    j = _load_json("group_stats.json")
    reported = _naive_short_t(j)
    assert reported is not None, (
        "group_stats.json does not report the naive short-range-FC group test statistic (t)")
    assert abs(t_rows - reported) <= st["RECOMP_TOL"], (
        f"naive short-range group t recomputed from the rows ({t_rows:+.3f}) does not match the "
        f"reported value ({reported:+.3f}, tol {st['RECOMP_TOL']}). CSV and JSON disagree.")

    # group sizes consistent with the reference cohort composition
    assert abs(n_s - st["n_schz"]) <= max(10, 0.2 * st["n_schz"]), (
        f"submitted SCHZ n ({n_s}) inconsistent with the reference ({st['n_schz']})")
    assert abs(n_c - st["n_control"]) <= max(15, 0.2 * st["n_control"]), (
        f"submitted CONTROL n ({n_c}) inconsistent with the reference ({st['n_control']})")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_conclusion_is_motion_confounded_numeric():
    """Grade the discriminating conclusion AS NUMBERS, RECOMPUTED FROM THE ROWS: the face-value
    group difference in short-range FC COLLAPSES toward null under a mean-FD covariate, and patients
    move far more than controls. The FD-covariate group t is recomputed from the submitted
    {short, group, mean_fd} rows -- a guessed collapse cannot pass, and a fabricated FD column fails
    pillar 1. Reported numbers are only a consistency cross-check."""
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    matched = [i for i in sub if i in set(ref["ids"])]
    import math

    # RECOMPUTE the naive and FD-covariate group t + collapse FROM the rows.
    naive_t, _, _ = pw.recompute_naive_short_t(sub, matched, ref)
    fd_t = pw.fd_covariate_short_t(sub, matched)
    assert math.isfinite(naive_t), "cannot recompute the naive short-range group t from the rows"
    assert math.isfinite(fd_t), (
        "cannot recompute the head-motion-controlled (short-range | mean_fd) group t from the "
        "rows -- the per-subject mean_fd column is missing or degenerate. The judgement graded "
        "here is whether the group difference survives controlling for head motion.")

    ref_collapse = abs(st["naive_short_t"]) - abs(st["fd_short_t"])

    # (a) the motion-controlled group difference collapses toward null AND matches the reference.
    #     A shuffled/fabricated FD column does not reproduce this attenuation.
    assert abs(fd_t) <= st["FD_T_MAX"], (
        f"the motion-controlled short-range t recomputed from the rows = {fd_t:+.3f} is not near "
        f"zero; on the real data the group difference collapses when head motion is controlled "
        f"(reference {st['fd_short_t']:+.3f}).")
    assert abs(fd_t - st["fd_short_t"]) <= st["FD_T_TOL"], (
        f"the motion-controlled short-range t recomputed from the rows = {fd_t:+.3f} does not match "
        f"the reference ({st['fd_short_t']:+.3f}, tol {st['FD_T_TOL']}); the submitted short-range "
        f"and/or mean_fd columns are not the real per-subject values.")

    # (b) collapse: the motion-controlled statistic is markedly smaller than the naive one, and the
    #     magnitude of the collapse matches the reference.
    collapse = abs(naive_t) - abs(fd_t)
    assert collapse >= st["COLLAPSE_MIN"], (
        f"the face-value group difference (naive t={naive_t:+.3f}) does not collapse when motion "
        f"is controlled (motion-controlled t={fd_t:+.3f}). A motion-confounded result requires "
        f"the controlled estimate to be markedly attenuated.")
    assert abs(collapse - ref_collapse) <= st["FD_T_TOL"] + st["RECOMP_TOL"], (
        f"the recomputed collapse ({collapse:+.3f}) does not match the reference "
        f"({ref_collapse:+.3f}).")

    # (c) the premise: patients move far more than controls, recomputed from the submitted FD.
    fd_schz = [sub[i]["fd"] for i in matched if sub[i]["group"] == "schz"
               and sub[i].get("fd") is not None and math.isfinite(sub[i]["fd"])]
    fd_ctrl = [sub[i]["fd"] for i in matched if sub[i]["group"] == "control"
               and sub[i].get("fd") is not None and math.isfinite(sub[i]["fd"])]
    assert len(fd_schz) >= 10 and len(fd_ctrl) >= 10, (
        "too few per-subject mean_fd values by group to check the motion premise")
    import statistics as _s
    m_schz, m_ctrl = _s.mean(fd_schz), _s.mean(fd_ctrl)
    assert m_schz > m_ctrl, (
        f"per-subject mean FD does not show patients moving more (SCHZ {m_schz:.3f} vs CONTROL "
        f"{m_ctrl:.3f}); the motion confound rests on the patient group moving more.")
    assert abs(m_schz - st["mean_fd_schz"]) <= st["FD_DIFF_TOL"] and \
           abs(m_ctrl - st["mean_fd_control"]) <= st["FD_DIFF_TOL"], (
        f"per-group mean FD recomputed from the rows (SCHZ {m_schz:.3f}, CONTROL {m_ctrl:.3f}) does "
        f"not match the reference (SCHZ {st['mean_fd_schz']:.3f}, CONTROL {st['mean_fd_control']:.3f}).")

    # (d) consistency: any REPORTED motion-controlled group t must agree with the recompute.
    j = _load_json("group_stats.json")
    rep_fd_t = _fd_short_t(j)
    if rep_fd_t is not None:
        assert abs(rep_fd_t - fd_t) <= st["FD_T_TOL"] + st["RECOMP_TOL"], (
            f"reported motion-controlled short-range t ({rep_fd_t:+.3f}) is inconsistent with the "
            f"value recomputed from the submitted rows ({fd_t:+.3f}).")


def test_edgewise_collapse_numeric():
    """The edge-wise fraction of group-different connections must collapse toward chance when
    motion is controlled (a second discriminating number a naive run cannot produce)."""
    ref = _reference()
    st = ref["stats"]
    j = _load_json("group_stats.json")
    naive = pw.find_path_number(j, path_include=["edge"], leaf_re=r"naive|raw|uncontroll",
                                path_exclude=["qcfc"])
    fdc = pw.find_path_number(j, path_include=["edge"],
                              leaf_re=r"fdcontroll|motioncontroll|controll|^fd|motion|adjust",
                              path_exclude=["qcfc"], prefer=["controll", "fd", "motion"])
    # These are recommended but not hard-required (the group-t collapse already carries pillar 3);
    # when reported they must show the collapse and match the reference.
    if naive is not None and fdc is not None:
        assert abs(naive - st["edgewise_naive"]) <= st["EDGE_TOL"], (
            f"edgewise naive fraction {naive:.3f} != reference {st['edgewise_naive']:.3f}")
        assert fdc < naive, (
            f"edgewise fraction does not fall under motion control ({naive:.3f} -> {fdc:.3f})")
        assert abs(fdc - st["edgewise_fd"]) <= st["EDGE_TOL"] + 0.03, (
            f"edgewise motion-controlled fraction {fdc:.3f} != reference {st['edgewise_fd']:.3f}")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_engage_motion_confound_and_avoid_overclaim():
    """SECONDARY (the numeric pillars carry the grade). findings.md must report that the
    group difference is a head-motion confound (patients move more; it collapses under motion
    control), not merely name motion regressors, and must not over-claim a clean disease
    signature or a demonstrated true null."""
    text = _findings()
    mentions_motion = re.search(r"\bhead motion\b|\bmotion\b|framewise|\bfd\b|movement|micro-?movement", text)
    M = r"(?:head motion|motion|movement|framewise|displacement|micro-?movement|\bfd\b)"
    RES = (r"(?:group|diagnos\w*|schizophreni\w*|patient\w*|clinical|between-group|case-control|"
           r"connectivity difference|hyper-?connect\w*|hypo-?connect\w*|effect|result|finding|"
           r"reproduc\w*|difference|edges|connections)")
    CONF = r"(?:confound\w*|artif\w*|spurious|driv\w*|explain\w*|attribut\w*|account\w*|due to|inflat\w*)"
    COLL = (r"(?:no longer|not signif\w*|not statistically|n\.?s\.|vanish\w*|disappear\w*|attenuat\w*|"
            r"abolish\w*|collaps\w*|null|gone|absent|weaken\w*|not (?:a )?robust|chance|near[- ]chance)")
    CTRL = r"(?:control\w*|adjust\w*|regress\w*|match\w*|censor\w*|scrub\w*|covar\w*|partial\w*)"
    recognises_confound = re.search(
        rf"{M}[^.\n]{{0,60}}{CONF}[^.\n]{{0,70}}{RES}"
        rf"|{RES}[^.\n]{{0,70}}{CONF}[^.\n]{{0,60}}{M}"
        rf"|{RES}[^.\n]{{0,60}}{M}[^.\n]{{0,25}}(?:artif|confound)"
        rf"|{CTRL}[^.\n]{{0,35}}(?:for\s+)?{M}[^.\n]{{0,120}}{COLL}"
        rf"|{M}[^.\n]{{0,70}}(?:covar\w*|matched|match\w*|{CTRL})[^.\n]{{0,100}}{COLL}"
        rf"|{COLL}[^.\n]{{0,100}}{CTRL}[^.\n]{{0,30}}(?:for\s+)?{M}"
        rf"|patients?[^.\n]{{0,40}}mov\w*[^.\n]{{0,90}}(?:{CONF}|{COLL})", text)
    assert mentions_motion and recognises_confound, (
        "findings.md does not report that the schizophrenia-vs-control connectivity difference is "
        "a head-motion confound (patients move far more; the group effect collapses when motion is "
        "controlled). A flat 'patients show altered connectivity', a flat 'no difference', or merely "
        "naming motion regressors in the pipeline, all miss the confound this result has.")
