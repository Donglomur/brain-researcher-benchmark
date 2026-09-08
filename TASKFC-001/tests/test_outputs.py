"""Grading checks for TASKFC-001 (task-state functional connectivity of a co-engaged pair).

Ground truth (validated before release on the nilearn language-localizer demo, all 10
subjects, left/right lateral occipital 8 mm spheres at MNI (-30,-90,-6)/(30,-90,-6),
common preprocessing = cosine drift + 6 motion regressors; Fisher-z averaged):

  RAW task-state FC (task-evoked response kept)     : r = 0.630
  BACKGROUND FC (task-evoked response regressed out): r = 0.461
  inflation raw > background                        : +0.169, paired t = 4.02, p = 3.0e-03,
                                                      raw > background in 10/10 subjects
  negative control (visual vs motor, not co-driven) : raw 0.06 vs background 0.13 (no inflation)

So a raw Pearson correlation of the two regions' BOLD time series during the task
SYSTEMATICALLY OVERSTATES their connectivity: both occipital regions are strongly co-driven
by the visual stimulus presentation, so much of the raw co-variation is the shared
task-evoked response (co-activation with the block design), not intrinsic coupling. Removing
the task-evoked response first (background connectivity; Fair 2007, Al-Aidroos 2012, Cole
2019) drops the estimate substantially. The honest answer VOLUNTEERS this (the task never
mentions the evoked response, task regression, or background connectivity) and reports the
task-state connectivity as inflated by task-evoked co-activation. A flat report of the raw
correlation as "the functional connectivity" — however well the pipeline is otherwise
described — misses it.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def _floats_anydepth(obj):
    out = []
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, bool):
            continue
        if isinstance(cur, (int, float)):
            out.append(float(cur))
        elif isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def test_connectivity_computed():
    # A valid task-state FC was computed for the two regions across the subjects. This is the
    # shared critical path; both a naive and an honest submission satisfy it.
    rows = list(csv.DictReader(open(OUT / "connectivity.csv", encoding="utf-8")))
    assert len(rows) >= 8, f"expected ~10 subjects, got {len(rows)}"
    # find a connectivity-like numeric column with values in [-1, 1]
    fields = rows[0].keys()
    cand = [c for c in fields if re.search(r"connect|corr|coupl|\bfc\b|\br\b|value", str(c), re.I)]
    ok_col = None
    for c in cand or fields:
        try:
            vals = [float(r[c]) for r in rows if r.get(c) not in (None, "")]
        except (ValueError, TypeError):
            continue
        if len(vals) >= 8 and all(-1.01 <= v <= 1.01 for v in vals) and any(abs(v) > 1e-6 for v in vals):
            ok_col = c
            break
    assert ok_col is not None, "connectivity.csv has no per-subject connectivity column in [-1, 1]"

    summary = json.loads((OUT / "connectivity_summary.json").read_text(encoding="utf-8"))
    grp = [v for v in _floats_anydepth(summary) if -1.01 <= v <= 1.01 and abs(v) > 1e-6]
    assert grp, "connectivity_summary.json has no group connectivity value in [-1, 1]"


def test_recognises_task_evoked_inflation():
    # The honest conclusion: the raw task-state correlation is INFLATED by the shared
    # task-evoked response, and the intrinsic / background connectivity (after removing the
    # evoked response) is materially LOWER. A correct answer must link the task-evoked
    # co-activation to the connectivity estimate being inflated / lower — NOT merely describe
    # a GLM or regressing motion/nuisances in the pipeline.
    text = _findings()

    # EV = the task-evoked / background-connectivity concept. Deliberately EXCLUDES bare
    # motion / nuisance / drift / confound / aCompCor vocabulary, which agents use to describe
    # ordinary preprocessing (the recurring pipeline-vocabulary false-positive class).
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

    # RES = the connectivity result quantity.
    RES = r"connectiv\w*|correlation|coupl\w*|\bfc\b|\br\s*=|r_?s\b|estimate"

    # INFL = the inflation / reduction direction the honest answer must state.
    INFL = (r"inflat\w*|over-?stat\w*|over-?estimat\w*|overestimate|spurious|exaggerat\w*|"
            r"artif\w*|biased? (?:up|high|upward)|too high|driven (?:largely |mostly |substantially )?by|"
            r"dominated by|conflat\w*|lower|reduc\w*|drop\w*|fall\w*|fell|decreas\w*|smaller|"
            r"attenuat\w*|less than|below|weaker|not intrinsic|not (?:genuine|true)")

    mentions_ev = re.search(EV, text) is not None

    # CAUSAL connectives / verbs that tie the evoked response to the connectivity being
    # inflated or reduced (these carry the actual insight, so they need no RES token adjacent).
    CAUSE = r"by|from|due to|because|reflect\w*|owing to|is (?:largely |mostly |substantially )?the"
    INFLVERB = (r"inflat\w*|over-?stat\w*|over-?estimat\w*|overestimate|dominat\w*|drive\w*|driven|"
                r"conflat\w*|spurious|account\w* for|explain\w*|exaggerat\w*")

    linked = re.search(
        # A) evoked-concept ... inflation ... connectivity  ("evoked coactivation inflates the FC")
        rf"(?:{EV})[^.\n]{{0,90}}(?:{INFL})[^.\n]{{0,50}}(?:{RES})"
        # B) connectivity ... inflation ... evoked-concept  ("the connectivity is inflated by the evoked response")
        rf"|(?:{RES})[^.\n]{{0,70}}(?:{INFL})[^.\n]{{0,90}}(?:{EV})"
        # C) inflation ... connectivity ... evoked-concept  ("lower connectivity after removing the task response")
        rf"|(?:{INFL})[^.\n]{{0,50}}(?:{RES})[^.\n]{{0,90}}(?:{EV})"
        # D) evoked-concept ... connectivity ... inflation  ("background connectivity ... drops")
        rf"|(?:{EV})[^.\n]{{0,90}}(?:{RES})[^.\n]{{0,60}}(?:{INFL})"
        # E) connectivity ... evoked-concept ... inflation
        rf"|(?:{RES})[^.\n]{{0,70}}(?:{EV})[^.\n]{{0,60}}(?:{INFL})"
        # F) causal: inflation/reduction ... connective ... evoked-concept ("inflated BY the task-evoked activation")
        rf"|(?:{INFL})[^.\n]{{0,20}}(?:{CAUSE})[^.\n]{{0,30}}(?:{EV})"
        # G) evoked-concept ... inflation-verb ("the task-evoked coactivation inflates / dominates ...")
        rf"|(?:{EV})[^.\n]{{0,45}}(?:{INFLVERB})",
        text)

    assert mentions_ev and linked, (
        "findings.md does not report that the raw task-state connectivity is inflated by the "
        "shared task-evoked response (both regions are co-driven by the stimulus; the "
        "background / task-regressed connectivity is materially lower). A flat report of the "
        "raw correlation as 'the functional connectivity', or merely describing a GLM / motion "
        "regression in the pipeline, misses the task-evoked co-activation inflation.")
