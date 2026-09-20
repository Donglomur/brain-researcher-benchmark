"""Proof-of-work grader for EMOMATCH-001 — reproduce the emotion-matching (faces>shapes)
activation on AOMIC PIOP2 (ds002790) and report which of it is emotion-specific vs a
reaction-time (time-on-task) artifact.

The previous verifier checked shapes/ranges + a keyword sentence, so it passed on fabricated
tables. This grader validates the EXACT ds002790 emomatching subjects and their per-subject
emotion>control contrast estimates against a held-out reference (tests/reference.npz, built from
the oracle run), recomputes the group one-sample t FROM the submitted rows, and grades the
scientific judgement AS NUMBERS: under a reaction-time-controlled (variable-epoch) model the
amygdala/fusiform response SURVIVES while the domain-general cognitive-control "emotion" effect
COLLAPSES, matching the held-out reference. Keyword prose is only secondary.

Reference (ds002790 fMRIPrep, Schaefer-100/7 + amygdala/fusiform/control spheres, n=20):
  RT  emotion 1.86 s vs control 1.32 s (paired t 7.3, d 1.67; emotion slower 95%)
  amygdala emotion>control  t  7.89 -> 8.25  (survives RT control)
  control-ROI emotion>control t 3.74 -> 1.22 (collapses, n.s.)
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
_T = r"^t$|^tstat|^tstatistic$|^statistic$|^tval|^tvalue$"


def _reference():
    assert REF_PATH.exists(), "held-out reference tests/reference.npz is missing"
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "activation.csv"
    assert p.exists(), "missing required output activation.csv"
    return pw.load_submitted(p)


def _stats():
    p = OUT / "group_stats.json"
    assert p.exists(), "missing required output group_stats.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"group_stats.json is not valid JSON: {e}")


def _findings():
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


# ---- schema-tolerant extractors ---------------------------------------------------------
_HEMI = ["amygdalal", "amygdalar", "left", "right", "lhemi", "rhemi", "hemisphere", "_lh", "_rh"]


def _amy_t(j, model):
    if model == "naive":
        return pw.find_path_number(j, path_include=["amygdala"], leaf_re=_T,
                                   path_exclude=["rt", "variable", "duration", "controll", "matched"] + _HEMI,
                                   prefer=["naive", "raw", "constant", "fixed"])
    return pw.find_path_number(j, path_include=["amygdala"], leaf_re=_T,
                               path_exclude=["naive", "constant", "fixedepoch"] + _HEMI,
                               prefer=["rtcontrolled", "rt", "variable", "duration", "reactiontime"])


def _ctrl_t(j, model):
    """The AGGREGATE cognitive-control ROI emotion>control t (not an individual control ROI)."""
    base_exc = ["amyg", "fusiform", "face", "reaction"]
    exc = base_exc + (["rtcontrolled", "variable", "duration", "matched"] if model == "naive"
                      else ["naive", "constant"])
    pref = (["naive", "raw", "constant"] if model == "naive"
            else ["rtcontrolled", "rt", "variable", "duration", "reactiontime"])
    for agg in (["control", "mean"], ["control", "average"], ["control", "aggregate"],
                ["control", "overall"], ["control", "network"], ["control", "combined"],
                ["cognitivecontrol"]):
        v = pw.find_path_number(j, path_include=agg, leaf_re=_T, path_exclude=exc, prefer=pref)
        if v is not None:
            return v
    return None


def _rt_mean(j, cond):
    return pw.find_path_number(j, path_include=["reaction"], leaf_re=cond,
                               path_exclude=["diff", "paired", "cohen", "frac"]) or \
        pw.find_path_number(j, path_include=[cond], leaf_re=r"rt|reaction|means|seconds|meanrt",
                            path_exclude=["diff", "paired"])


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub = _submitted()
    assert len(sub) >= 12, f"activation.csv must carry per-subject contrasts; parsed {len(sub)} rows"
    j = _stats()
    assert isinstance(j, dict) and j, "group_stats.json empty"
    meta = OUT / "run_metadata.json"
    assert meta.exists() and json.loads(meta.read_text()), "run_metadata.json missing/empty"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); sub = _submitted(); st = ref["stats"]
    pw.check_subjects_and_values(sub, ref, val_tol=st["VAL_TOL"], corr_min=st["CORR_MIN"],
                                 cover=st["COVER"], match=st["MATCH"], eps=st["EPS"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_and_crosscheck():
    ref = _reference(); sub = _submitted(); st = ref["stats"]
    j = _stats()
    matched = [i for i in sub if i in set(ref["ids"])]
    import math

    t_amy = pw.one_sample_t([sub[i]["amygdala"] for i in matched])
    assert math.isfinite(t_amy), "cannot recompute the amygdala group t from the rows"
    assert abs(t_amy - st["amygdala_naive_t"]) <= st["RECOMP_TOL"], (
        f"amygdala group t recomputed from the submitted rows ({t_amy:.2f}) does not match the "
        f"reference naive t ({st['amygdala_naive_t']:.2f}, tol {st['RECOMP_TOL']}).")
    rep_amy = _amy_t(j, "naive")
    assert rep_amy is not None and abs(t_amy - rep_amy) <= st["RECOMP_TOL"], (
        f"reported amygdala naive t ({rep_amy}) is not the one-sample t of the submitted amygdala "
        f"rows ({t_amy:.2f}); CSV and JSON disagree.")

    # control-ROI column recomputes to the reported control naive t
    if all(sub[i]["control"] is not None for i in matched):
        t_ctrl = pw.one_sample_t([sub[i]["control"] for i in matched])
        rep_ctrl = _ctrl_t(j, "naive")
        if rep_ctrl is not None:
            assert abs(t_ctrl - rep_ctrl) <= st["RECOMP_TOL"] + 0.5, (
                f"reported control-ROI naive t ({rep_ctrl}) is not the one-sample t of the submitted "
                f"control-ROI rows ({t_ctrl:.2f}); CSV and JSON disagree.")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_conclusion_is_reaction_time_confound_numeric():
    ref = _reference(); st = ref["stats"]; j = _stats()
    amy_n, amy_r = _amy_t(j, "naive"), _amy_t(j, "rt")
    ctrl_n, ctrl_r = _ctrl_t(j, "naive"), _ctrl_t(j, "rt")
    assert amy_n is not None, "no amygdala naive emotion>control t reported"
    assert amy_r is not None, (
        "no REACTION-TIME-CONTROLLED (variable-epoch) amygdala t reported. The judgement graded "
        "here is which of the emotion activation survives modelling the reaction-time difference; "
        "report the emotion>control contrast under a variable-epoch (duration = reaction time) model.")
    assert ctrl_n is not None and ctrl_r is not None, (
        "no cognitive-control-ROI naive and reaction-time-controlled emotion>control t reported.")

    # (a) amygdala SURVIVES reaction-time control (stays strongly positive, matches reference).
    assert amy_r >= st["AMY_SURVIVE_MIN"], (
        f"reported reaction-time-controlled amygdala t = {amy_r:.2f} does not survive; on the real "
        f"data the amygdala emotion effect is robust to RT control (reference {st['amygdala_rt_t']:.2f}).")
    assert abs(amy_r - st["amygdala_rt_t"]) <= st["AMY_T_TOL"], (
        f"reported RT-controlled amygdala t = {amy_r:.2f} does not match the reference "
        f"({st['amygdala_rt_t']:.2f}, tol {st['AMY_T_TOL']}).")

    # (b) cognitive-control ROIs COLLAPSE under reaction-time control (a real drop to ~n.s.).
    assert ctrl_r <= st["CTRL_RT_MAX"], (
        f"reported reaction-time-controlled control-ROI t = {ctrl_r:.2f} did not collapse; the "
        f"domain-general 'emotion' effect is a time-on-task artifact and should fall to ~n.s. "
        f"(reference {st['control_rt_t']:.2f}).")
    assert ctrl_n - ctrl_r >= st["CTRL_COLLAPSE_MARGIN"], (
        f"the cognitive-control 'emotion' effect (naive t={ctrl_n:.2f}) does not collapse under "
        f"reaction-time control (t={ctrl_r:.2f}); a time-on-task artifact requires a real drop.")

    # (c) the amygdala is far more RT-robust than the control ROIs (dissociation).
    assert amy_r > ctrl_r, (
        f"under RT control the amygdala ({amy_r:.2f}) must remain above the collapsed control ROIs "
        f"({ctrl_r:.2f}); the dissociation is the emotion-specificity result.")


def test_reaction_time_premise_numeric():
    """The premise (a real number a naive run still produces, but which anchors the confound):
    emotion trials take markedly longer than control trials."""
    ref = _reference(); st = ref["stats"]; j = _stats()
    emo = _rt_mean(j, "emotion")
    con = _rt_mean(j, "control")
    assert emo is not None and con is not None, (
        "group_stats.json does not report the per-condition mean reaction time (emotion vs control) "
        "-- the premise of the time-on-task confound.")
    assert emo > con, (
        f"reported reaction times do not show emotion slower than control (emotion {emo:.2f}s vs "
        f"control {con:.2f}s).")
    assert abs(emo - st["rt_emotion"]) <= st["RT_TOL"] and abs(con - st["rt_control"]) <= st["RT_TOL"], (
        f"reported mean reaction times (emotion {emo:.2f}s, control {con:.2f}s) do not match the "
        f"reference (emotion {st['rt_emotion']:.2f}s, control {st['rt_control']:.2f}s).")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_engage_rt_confound_and_avoid_overclaim():
    """SECONDARY (numbers carry the grade). findings.md must state that the broad
    cognitive-control 'emotion network' is a reaction-time / time-on-task confound while the
    amygdala/fusiform response is emotion-specific, and must not report the whole broad network
    as a genuine emotion network."""
    text = _findings()
    RT = r"(?:reaction[- ]?time|response[- ]?time|\brt\b|time[- ]?on[- ]?task|time on task|difficulty|slower|took longer|duration)"
    COLL = (r"(?:collaps\w*|disappear\w*|vanish\w*|attenuat\w*|no longer|not signif\w*|n\.?s\.|"
            r"reverse\w*|driven by|artif\w*|confound\w*|explain\w*|not emotion|non-?specific|"
            r"time[- ]?on[- ]?task|does not survive|drops?|reduc\w* to)")
    SURV = r"(?:amygdal\w*|fusiform|face)"
    engages_rt = re.search(rf"{RT}[^.\n]{{0,80}}{COLL}|{COLL}[^.\n]{{0,80}}{RT}", text)
    engages_survive = re.search(rf"{SURV}[^.\n]{{0,90}}(?:surviv\w*|robust|unchanged|remain\w*|"
                                rf"still signif\w*|emotion-?specific|genuine|specific)", text)
    assert engages_rt, (
        "findings.md does not report that the broad cognitive-control 'emotion' activation is a "
        "reaction-time / time-on-task confound (it collapses when trial duration/RT is modelled).")
    assert engages_survive, (
        "findings.md does not report that the amygdala/fusiform face response survives reaction-time "
        "control (the emotion-specific result).")

    # over-claim guard: must not conclude the whole broad fronto-parietal network is emotion-specific
    overclaim = re.search(
        r"(?:distributed|broad|widespread|whole|entire|fronto-?parietal|cognitive-?control|salience)"
        r"[^.\n]{0,40}emotion[- ]?(?:processing )?network[^.\n]{0,40}(?:genuine|specific|robust|real|reflect)",
        text)
    disclaim = re.search(r"(?:not|isn.t|is not|rather than|artif\w*|confound\w*|time[- ]?on[- ]?task)"
                         r"[^.\n]{0,60}(?:emotion[- ]?(?:processing )?network|distributed|broad)", text)
    assert not (overclaim and not disclaim), (
        "findings.md over-claims the broad fronto-parietal/cognitive-control network as a genuine "
        "emotion-processing network; on these data it is largely a reaction-time (time-on-task) "
        "artifact.")
