"""Proof-of-work grader for EMOMATCH-001 -- reproduce the emotion-matching (faces>shapes)
activation on AOMIC PIOP2 (ds002790) and report which of it is emotion-specific vs a
reaction-time (time-on-task) artifact.

Earlier verifiers graded the discriminating conclusion -- that under a reaction-time-controlled
(variable-epoch) model the cognitive-control "emotion" effect COLLAPSES while the amygdala/
fusiform response SURVIVES -- as REPORTED SCALARS in group_stats.json. An agent that fitted only
the standard (constant-epoch) GLM could then GUESS those alternative-model numbers (the amygdala
survives ~unchanged, the control ROIs fall to ~n.s.) without ever fitting the second model, and
pass. This grader closes that. The emotion>control contrast must be submitted PER SUBJECT under
each first-level modelling choice the agent considered; the grader validates each per-subject
column against a held-out reference (tests/reference.npz, never shipped to the agent) and
RECOMPUTES the collapse/survival discriminator from the validated per-subject columns. A run that
fitted only one model has no genuine second column; a fabricated/shrunk second column fails the
per-subject reference match (the cognitive-control collapse is a specific per-subject re-estimate
that cannot be guessed from the naive column).

The grader NEVER keys off a column name: it assigns, per region and BY VALUE, which submitted
column is the standard-model estimate and which is the alternative-model estimate (best per-subject
match to each reference). The required schema therefore does not name the modelling lever that
separates them.

Reference (ds002790 fMRIPrep, Schaefer-100/7 + amygdala/fusiform/control spheres, n=20):
  RT  emotion ~1.86 s vs control ~1.32 s
  amygdala emotion>control  t  ~7.9 -> ~8.2  (survives the alternative model)
  control-ROI emotion>control t ~3.7 -> ~1.2 (collapses under the alternative model)
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


def _rt_mean(j, cond):
    return pw.find_path_number(j, path_include=["reaction"], leaf_re=cond,
                               path_exclude=["diff", "paired", "cohen", "frac"]) or \
        pw.find_path_number(j, path_include=[cond], leaf_re=r"rt|reaction|means|seconds|meanrt",
                            path_exclude=["diff", "paired"])


def _assign():
    """Load rows and assign, per region, the standard-model and alternative-model columns by value.
    Returns (ref, st, sub, cols) where cols[region] = (std_col, alt_col, diag)."""
    ref = _reference(); st = ref["stats"]
    sub, region_cols = _submitted()
    cols = {}
    for region in pw.REGIONS:
        cols[region] = pw.assign_model_columns(sub, ref, region, cover=st["COVER"])
    return ref, st, sub, cols


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub, region_cols = _submitted()
    assert len(sub) >= 12, f"activation.csv must carry per-subject contrasts; parsed {len(sub)} rows"
    j = _stats()
    assert isinstance(j, dict) and j, "group_stats.json empty"
    meta = OUT / "run_metadata.json"
    assert meta.exists() and json.loads(meta.read_text()), "run_metadata.json missing/empty"


# ------------------------------------------------------------------ pillar 1 (real per-subject data, BOTH models)
def test_proof_of_work_subjects_and_values():
    ref, st, sub, cols = _assign()
    amy_std, amy_alt, amy_diag = cols["amygdala"]
    ctl_std, ctl_alt, ctl_diag = cols["control"]
    assert amy_std is not None, (
        f"activation.csv has no amygdala emotion>control column tracking the real per-subject "
        f"contrasts (diagnostics: {amy_diag}).")
    # standard-model amygdala + control per subject must be the real ones
    pw.check_region_column(sub, ref, "amygdala", amy_std, "amygdala",
                           st["VAL_TOL"], st["CORR_MIN"], st["COVER"], st["MATCH"], st["EPS"],
                           "amygdala/standard")
    if ctl_std is not None:
        pw.check_region_column(sub, ref, "control", ctl_std, "control",
                               st["VAL_TOL"], st["CORR_MIN"], st["COVER"], st["MATCH"], st["EPS"],
                               "control/standard")
    # a genuine SECOND model must be present for the discriminating (cognitive-control) region
    assert ctl_std is not None and ctl_alt is not None and ctl_alt != ctl_std, (
        "activation.csv reports the cognitive-control emotion>control contrast under only ONE "
        "first-level modelling choice. The task asks you to report the per-subject contrast under "
        "EACH modelling choice you consider; a single first-level model cannot establish whether "
        "the broad 'emotion' activation is robust to the modelling decisions the task leaves open.")
    pw.check_region_column(sub, ref, "control", ctl_alt, "control_rt",
                           st["RT_VAL_TOL"], st["RT_CORR_MIN"], st["COVER"], st["RT_MATCH"],
                           st["EPS"], "control/alternative")
    # and for the amygdala (so the dissociation is measured under the same alternative model)
    assert amy_alt is not None and amy_alt != amy_std, (
        "activation.csv reports the amygdala emotion>control contrast under only ONE first-level "
        "modelling choice; report it per subject under each modelling choice you consider.")
    pw.check_region_column(sub, ref, "amygdala", amy_alt, "amygdala_rt",
                           st["RT_VAL_TOL"], st["RT_CORR_MIN"], st["COVER"], st["RT_MATCH"],
                           st["EPS"], "amygdala/alternative")


# ------------------------------------------------------------------ pillar 2 (recompute naive group t from rows)
def test_recompute_and_crosscheck():
    ref, st, sub, cols = _assign()
    amy_std, amy_alt, _ = cols["amygdala"]
    matched = pw.column_values(sub, ref, "amygdala", amy_std)
    t_amy = pw.group_t_from_column(sub, "amygdala", amy_std, matched)
    assert math.isfinite(t_amy), "cannot recompute the amygdala group t from the rows"
    assert abs(t_amy - st["amygdala_naive_t"]) <= st["RECOMP_TOL"], (
        f"amygdala group t recomputed from the submitted standard-model rows ({t_amy:.2f}) does not "
        f"match the reference ({st['amygdala_naive_t']:.2f}, tol {st['RECOMP_TOL']}).")
    # optional consistency with a reported amygdala standard-model t
    j = _stats()
    rep = pw.find_path_number(j, path_include=["amygdala"], leaf_re=_T,
                              path_exclude=["rt", "variable", "duration", "controll", "matched",
                                            "amygdalal", "amygdalar", "left", "right", "lhemi",
                                            "rhemi", "hemisphere", "_lh", "_rh"],
                              prefer=["naive", "raw", "constant", "fixed"])
    if rep is not None:
        assert abs(t_amy - rep) <= st["RECOMP_TOL"] + 0.5, (
            f"reported amygdala standard-model t ({rep}) is not the one-sample t of the submitted "
            f"amygdala rows ({t_amy:.2f}); CSV and JSON disagree.")


# ------------------------------------------------------------------ pillar 3 (judgement RECOMPUTED from the two model columns)
def test_conclusion_is_reaction_time_confound_recomputed():
    """Grade the discriminating conclusion by RECOMPUTING it from the two validated per-subject
    columns -- never from a reported/guessable scalar. Recompute the group one-sample t for the
    cognitive-control ROIs and the amygdala under the standard and alternative models. The
    cognitive-control effect collapses under the alternative model; the amygdala survives; and the
    amygdala remains above the collapsed control ROIs (the emotion-specificity dissociation). An
    agent that fitted only one model, or fabricated the second column, cannot produce a genuinely
    re-estimated collapsed control column and fails here."""
    ref, st, sub, cols = _assign()
    amy_std, amy_alt, _ = cols["amygdala"]
    ctl_std, ctl_alt, _ = cols["control"]
    assert None not in (amy_std, amy_alt, ctl_std, ctl_alt) and amy_alt != amy_std and ctl_alt != ctl_std, (
        "need the emotion>control contrast under two distinct first-level modelling choices, for "
        "the amygdala and the cognitive-control ROIs, to assess whether the broad activation is "
        "modelling-dependent.")
    m_amy = pw.column_values(sub, ref, "amygdala", amy_std)
    m_amy_a = pw.column_values(sub, ref, "amygdala", amy_alt)
    m_ctl = pw.column_values(sub, ref, "control", ctl_std)
    m_ctl_a = pw.column_values(sub, ref, "control", ctl_alt)
    amy_n = pw.group_t_from_column(sub, "amygdala", amy_std, m_amy)
    amy_r = pw.group_t_from_column(sub, "amygdala", amy_alt, m_amy_a)
    ctl_n = pw.group_t_from_column(sub, "control", ctl_std, m_ctl)
    ctl_r = pw.group_t_from_column(sub, "control", ctl_alt, m_ctl_a)
    for name, v in (("amygdala std", amy_n), ("amygdala alt", amy_r),
                    ("control std", ctl_n), ("control alt", ctl_r)):
        assert math.isfinite(v), f"cannot recompute the {name} group t from the submitted rows"

    # (a) amygdala SURVIVES the alternative model (stays strongly positive, matches reference).
    assert amy_r >= st["AMY_SURVIVE_MIN"], (
        f"amygdala group t recomputed under the alternative model ({amy_r:.2f}) does not survive; on "
        f"the real data the amygdala emotion effect is robust (reference {st['amygdala_rt_t']:.2f}).")
    assert abs(amy_r - st["amygdala_rt_t"]) <= st["AMY_T_TOL"], (
        f"amygdala alternative-model t ({amy_r:.2f}) does not match the reference "
        f"({st['amygdala_rt_t']:.2f}, tol {st['AMY_T_TOL']}).")

    # (b) cognitive-control ROIs COLLAPSE under the alternative model (a real drop to ~n.s.).
    assert ctl_r <= st["CTRL_RT_MAX"], (
        f"cognitive-control group t recomputed under the alternative model ({ctl_r:.2f}) did not "
        f"collapse; the domain-general 'emotion' effect is a time-on-task artifact and should fall "
        f"to ~n.s. (reference {st['control_rt_t']:.2f}).")
    assert ctl_n - ctl_r >= st["CTRL_COLLAPSE_MARGIN"], (
        f"the cognitive-control 'emotion' effect (standard t={ctl_n:.2f}) does not collapse under "
        f"the alternative model (t={ctl_r:.2f}); a time-on-task artifact requires a real drop.")

    # (c) dissociation: the amygdala remains far above the collapsed control ROIs.
    assert amy_r > ctl_r, (
        f"under the alternative model the amygdala ({amy_r:.2f}) must remain above the collapsed "
        f"control ROIs ({ctl_r:.2f}); the dissociation is the emotion-specificity result.")


def test_reaction_time_premise_numeric():
    """The premise (a number any run reads from the events file, but which anchors the confound):
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
def test_findings_engage_confound_and_avoid_overclaim():
    """SECONDARY (numbers carry the grade). findings.md must state that the broad cognitive-control
    'emotion network' is a reaction-time / time-on-task confound while the amygdala/fusiform
    response is emotion-specific, and must not report the whole broad network as a genuine emotion
    network."""
    text = _findings()
    RT = r"(?:reaction[- ]?time|response[- ]?time|\brt\b|time[- ]?on[- ]?task|time on task|difficulty|slower|took longer|duration|modelling|model)"
    COLL = (r"(?:collaps\w*|disappear\w*|vanish\w*|attenuat\w*|no longer|not signif\w*|n\.?s\.|"
            r"reverse\w*|driven by|artif\w*|confound\w*|explain\w*|not emotion|non-?specific|"
            r"time[- ]?on[- ]?task|does not survive|drops?|reduc\w* to)")
    SURV = r"(?:amygdal\w*|fusiform|face)"
    engages = re.search(rf"{RT}[^.\n]{{0,80}}{COLL}|{COLL}[^.\n]{{0,80}}{RT}", text)
    engages_survive = re.search(rf"{SURV}[^.\n]{{0,90}}(?:surviv\w*|robust|unchanged|remain\w*|"
                                rf"still signif\w*|emotion-?specific|genuine|specific)", text)
    assert engages, (
        "findings.md does not report that the broad cognitive-control 'emotion' activation is a "
        "reaction-time / time-on-task confound (it collapses when trial duration/RT is modelled).")
    assert engages_survive, (
        "findings.md does not report that the amygdala/fusiform face response survives reaction-time "
        "control (the emotion-specific result).")
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
