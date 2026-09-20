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


def _fd_short_t(j):
    return pw.find_path_number(
        j, path_include=["short"], leaf_re=_T_LEAF,
        path_exclude=["qcfc", "displacement", "residual", "long"],
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
    ref = _reference()
    st = ref["stats"]
    j = _load_json("group_stats.json")

    naive_t = _naive_short_t(j)
    fd_t = _fd_short_t(j)
    assert naive_t is not None, "no naive short-range group t reported"
    assert fd_t is not None, (
        "no HEAD-MOTION-CONTROLLED short-range group t reported. The judgement graded here is "
        "whether the group difference survives controlling for head motion; report the group "
        "test after a mean-FD covariate (or a motion-matched subsample).")

    # (a) the motion-controlled group difference collapses toward null and matches the reference.
    assert abs(fd_t) <= st["FD_T_MAX"], (
        f"reported motion-controlled short-range t = {fd_t:+.3f} is not near zero; on the real "
        f"data the group difference collapses when head motion is controlled "
        f"(reference {st['fd_short_t']:+.3f}).")
    assert abs(fd_t - st["fd_short_t"]) <= st["FD_T_TOL"], (
        f"reported motion-controlled short-range t = {fd_t:+.3f} does not match the reference "
        f"({st['fd_short_t']:+.3f}, tol {st['FD_T_TOL']}).")

    # (b) collapse: the motion-controlled statistic is markedly smaller than the naive one.
    assert abs(naive_t) - abs(fd_t) >= st["COLLAPSE_MIN"], (
        f"the face-value group difference (naive t={naive_t:+.3f}) does not collapse when motion "
        f"is controlled (motion-controlled t={fd_t:+.3f}). A motion-confounded result requires "
        f"the controlled estimate to be markedly attenuated.")

    # (c) the premise: patients move far more than controls (real per-group mean FD).
    fd_schz = _mean_fd(j, "schz") or _mean_fd(j, "patient")
    fd_ctrl = _mean_fd(j, "control")
    assert fd_schz is not None and fd_ctrl is not None, (
        "group_stats.json does not report the per-group mean head motion (mean framewise "
        "displacement for the schizophrenia and control groups) -- the premise of the confound.")
    assert fd_schz > fd_ctrl, (
        f"reported mean FD does not show patients moving more (SCHZ {fd_schz:.3f} vs CONTROL "
        f"{fd_ctrl:.3f}); the motion confound rests on the patient group moving more.")
    assert abs(fd_schz - st["mean_fd_schz"]) <= st["FD_DIFF_TOL"] and \
           abs(fd_ctrl - st["mean_fd_control"]) <= st["FD_DIFF_TOL"], (
        f"reported per-group mean FD (SCHZ {fd_schz:.3f}, CONTROL {fd_ctrl:.3f}) does not match "
        f"the reference (SCHZ {st['mean_fd_schz']:.3f}, CONTROL {st['mean_fd_control']:.3f}).")


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
