"""Grading checks for EMOMATCH-001 (reproduce the emotion-matching faces>shapes activation on
AOMIC PIOP2 / ds002790 and characterise the emotion-processing network).

Ground truth (validated before release on the ds002790 fMRIPrep emomatching derivatives, n=20,
Schaefer-100/7-network cortex + amygdala, fusiform and cognitive-control 6mm spheres, group
one-sample t across subjects; NAIVE = constant-duration epochs, RT = variable-duration epochs
where each trial's duration equals its reaction time):

  PREMISE  emotion (face) trials are much slower than control (shape) trials:
           RT 1.86 s vs 1.32 s   (difference 0.54 s; emotion slower in 95% of subjects;
                                   paired t 6.7, Cohen d 1.67, p 7e-7)
  NAIVE    emotion > control activates the amygdala (t +7.9) and fusiform (t +7.7) AND the
           domain-general cognitive-control ROIs (anterior insula, dlPFC, IPS; aggregate mean
           t +3.74, p 0.0014 -- significantly positive)
  RT       modelling the reaction-time difference (variable-epoch GLM) makes the cognitive-control
           activation COLLAPSE (aggregate mean t +3.74 -> +1.22, n.s.; anterior insula reverses to
           t -3.01, IPS collapses), while the AMYGDALA (t 7.9 -> 8.3, -5%) and FUSIFORM
           (t 7.7 -> 6.3) effects SURVIVE.

So the amygdala/fusiform response is a genuine emotion/face-selective effect, but the broad
fronto-parietal / insular "emotion network" is largely a TIME-ON-TASK (reaction-time / task
difficulty) confound: emotion trials simply take longer, and that activation does not survive
modelling the reaction-time difference (Grinband et al. 2008; Yarkoni et al. 2009).

The failure mode this task targets (un-cued, wrong-cause axis): the agent fits the GLM, finds
emotion > control activation across amygdala, fusiform AND fronto-parietal / insular cortex, and
reports a distributed "emotion network", never asking whether the two conditions differ in
reaction time (they differ enormously) and whether the broad activation is a time-on-task
confound. A flat "emotion activates a distributed network including PFC/insula/parietal"
over-claims; only recognising the reaction-time / time-on-task confound (that the broad
activation is driven by the longer emotion trials and collapses when trial duration / RT is
modelled, while amygdala/fusiform survive) passes. Merely naming reaction_time as one nuisance
regressor in the pipeline does NOT pass -- the insight must be linked to the emotion RESULT.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    # collapse whitespace (incl. hard line-wraps) so the co-occurrence checks read findings.md
    # the way a person does -- flowing sentences -- not one hard-wrapped line at a time.
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _walk_numbers(obj):
    """yield every (key, value) leaf where value is numeric, at any depth."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                yield str(k).lower(), float(v)
            else:
                yield from _walk_numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_numbers(v)


def test_activation_computed():
    rows = list(csv.DictReader(open(OUT / "activation.csv", encoding="utf-8")))
    assert len(rows) >= 12, f"expected >=12 subjects with an emomatching run, got {len(rows)}"
    # locate the amygdala emotion>control column (a priori face/emotion region)
    amy_cols = [c for c in rows[0] if "amyg" in c.lower()]
    assert amy_cols, f"no amygdala emotion>control column in {list(rows[0])}"
    ac = amy_cols[0]
    vals = [float(r[ac]) for r in rows if r.get(ac) not in (None, "", "n/a")]
    assert len(vals) >= 12, "too few amygdala effect values"
    mean_amy = sum(vals) / len(vals)
    # the amygdala emotion>control effect is a real, positive activation (faces>shapes)
    assert mean_amy > 0, f"amygdala emotion>control should be positive on average, got {mean_amy:.3f}"


def test_group_result_present():
    blobs = _blobs()
    assert "group_stats.json" in blobs, "group_stats.json missing or unparseable"
    gs = blobs["group_stats.json"]
    if isinstance(gs, dict) and gs.get("status") == "failed_precondition":
        assert False, "group_stats.json reports failed_precondition"
    # there is a group-level emotion>control test somewhere with a real t-statistic
    tvals = [v for k, v in _walk_numbers(gs) if k in ("t", "tstat", "t_stat", "tval", "t_value")]
    assert any(abs(v) > 2.0 for v in tvals), (
        "no group-level t-statistic > 2 found in group_stats.json -- the emotion>control group "
        "effect does not appear to have been computed")


def test_recognises_time_on_task_confound():
    # The broad fronto-parietal / insular "emotion" activation is a reaction-time / time-on-task
    # confound (emotion trials take much longer than control trials) that collapses when trial
    # duration / RT is modelled, while amygdala/fusiform survive. A correct answer must LINK the
    # reaction-time / time-on-task / difficulty difference to the emotion RESULT -- NOT a flat
    # "emotion activates a distributed network", and NOT merely naming reaction_time as one
    # nuisance regressor ("we regressed motion and response_time"). Same style as the motion
    # check in CLINCONN-001 / DEVCONN-001 and the GSR check in SOCIALBRAIN-001.
    text = _findings()
    # time-on-task marker
    TOT = (r"(?:time[- ]on[- ]task|reaction[- ]?time|response[- ]?time|\brt\b|"
           r"trial (?:duration|length)|(?:stimulus |trial )?duration difference|"
           r"difficult\w*|task difficulty|effort\w*|longer (?:to respond|reaction|response|on)|"
           r"respond\w* (?:more )?slow\w*|slower (?:on |for )?(?:the )?emotion|took longer)")
    mentions_tot = re.search(TOT, text)
    # a token referring to the emotion RESULT / the broad activation
    RES = (r"(?:emotion\w*|affect\w*|face\w*|activation|activ\w*|contrast|effect|response|network|"
           r"fronto-?pariet\w*|prefront\w*|\bpfc\b|insula\w*|cingulate|salien\w*|"
           r"cognitive[- ]control|control network|dorsal[- ]?atten\w*|attention|widespread|"
           r"distributed|broad\w*|parietal|cluster\w*|region\w*)")
    # a NARROW result token for the collapse branches: identical to RES but WITHOUT the bare
    # "response" alternative, which collides with the pipeline term "response time" / "reaction
    # time" (TOT) and would let a nuisance-regressor sentence self-satisfy the result linkage.
    RESN = (r"(?:emotion\w*|affect\w*|face\w*|activation|activ\w*|contrast|effect|network|"
            r"fronto-?pariet\w*|prefront\w*|\bpfc\b|insula\w*|cingulate|salien\w*|"
            r"cognitive[- ]control|control network|dorsal[- ]?atten\w*|attention|widespread|"
            r"distributed|broad\w*|parietal|cluster\w*|region\w*)")
    # confound / attribution
    CONF = (r"(?:confound\w*|artif\w*|spurious|driv\w*|explain\w*|attribut\w*|account\w*|due to|"
            r"reflect\w*|not (?:truly |really |necessarily )?emotion[- ]specific|not specific|"
            r"rather than emotion|mislead\w*|inflat\w*|contaminat\w*)")
    # collapse under control of duration / RT.
    # NB: no bare "reduc\w*" -- it false-positives on pipeline vocabulary ("modelled response
    # time as a parametric regressor, which reduced residual variance"), exactly the collision
    # dropped in DEVCONN-001 / CLINCONN-001. The remaining tokens are strong collapse words that
    # a nuisance-regressor description does not use.
    COLL = (r"(?:no longer|not signif\w*|not statistically|n\.?s\.|vanish\w*|disappear\w*|"
            r"attenuat\w*|abolish\w*|collaps\w*|null|gone|absent|weaken\w*|shrink\w*|"
            r"revers\w*|does not survive|doesn't survive|did not survive|not robust|"
            r"drop\w* (?:to|out)|falls? to)")
    CTRL = (r"(?:control\w*|adjust\w*|regress\w*|model\w*|includ\w*|account\w*|covar\w*|"
            r"variable[- ]epoch|duration[- ]?modulat\w*|matched?|partial\w*)")
    recognises = re.search(
        # A) time-on-task / RT <-> confound <-> the emotion result (both orders)
        rf"{TOT}[^.\n]{{0,90}}{CONF}[^.\n]{{0,90}}{RES}"
        rf"|{RES}[^.\n]{{0,90}}{CONF}[^.\n]{{0,90}}{TOT}"
        rf"|{RES}[^.\n]{{0,70}}{TOT}[^.\n]{{0,40}}(?:confound|artif|driv|attribut|not (?:emotion[- ]specific|specific))"
        # B) controlling duration/RT collapses the broad effect  (control -> TOT -> RESULT -> collapse).
        #    The RESULT token (RESN) is required so a bare nuisance-pipeline sentence
        #    ("modelled response time ... which reduced variance") cannot self-satisfy the branch:
        #    the collapse must be OF the emotion / broad activation, not of residual variance.
        rf"|{CTRL}[^.\n]{{0,40}}(?:for |the )?{TOT}[^.\n]{{0,110}}{RESN}[^.\n]{{0,60}}{COLL}"
        # C) TOT -> control/model -> RESULT -> collapse
        rf"|{TOT}[^.\n]{{0,80}}(?:{CTRL})[^.\n]{{0,80}}{RESN}[^.\n]{{0,50}}{COLL}"
        # D) the broad activation collapses when duration/RT is modelled
        rf"|{RESN}[^.\n]{{0,90}}{COLL}[^.\n]{{0,90}}(?:{CTRL}[^.\n]{{0,30}})?{TOT}"
        # E) emotion trials take longer, explicitly tied to driving/explaining the activation
        rf"|emotion[^.\n]{{0,40}}(?:longer|slower|more time)[^.\n]{{0,120}}(?:{CONF}|{COLL})", text)
    assert mentions_tot and recognises, (
        "findings.md does not report that the broad emotion>control activation is a reaction-time "
        "/ time-on-task confound (emotion trials take much longer than control trials; the "
        "fronto-parietal / insular activation collapses when trial duration / reaction time is "
        "modelled, while amygdala/fusiform survive). A flat 'emotion activates a distributed "
        "network', or merely naming reaction_time as a nuisance regressor, misses the confound.")
