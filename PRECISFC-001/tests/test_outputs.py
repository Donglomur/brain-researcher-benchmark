"""Grading checks for PRECISFC-001 (test-retest reliability of the individual connectome, MSC).

Ground truth (validated before release on ds000224 volume_pipeline, Power-264 5mm spheres,
sub-MSC01/02/05/06/08/09, ses-func01/02/03; reliability = mean pairwise correlation of the
per-session connectome edge-vectors):

  per subject  reliability (all frames -> censored), frame retention
    MSC01  0.63 -> 0.66  (80%)     MSC02  0.54 -> 0.54  (86%)
    MSC05  0.68 -> 0.69  (84%)     MSC06  0.75 -> 0.75  (93%)
    MSC08  0.09 -> 0.30  (24%)     MSC09  0.51 -> 0.53  (60%)   # documented low-quality
  GROUP mean reliability
    naive   (all frames, all 6 subjects)              0.53
    correct (censored + exclude MSC08 & MSC09)        0.66

The reliability of the individual connectome is high, but the estimate depends on two
data-quality controls that MSC precision mapping relies on and that the task never spells out:
(1) censoring high-motion frames using the supplied temporal mask (`*_tmask.txt` / FD
scrubbing; Power 2012) -- which lifts MSC08 from 0.09 to 0.30; and (2) excluding the two
documented low-quality subjects, MSC08 (pervasive drowsiness -> unstable networks; only 24%
of frames retained) and MSC09 (excessive motion), per Gordon 2017 / Laumann 2015. Ignoring
either deflates and contaminates the estimate (naive 0.53 vs correct 0.66).

The failure mode this task targets (un-cued, data-quality axis): the agent computes a single
reliability figure over all frames and all subjects, and reports it -- never volunteering the
frame-censoring or the exclusion of the drowsy/high-motion subjects that the estimate needs.
A flat "the connectome is reliable, r = ..." fails; only recognising BOTH controls passes.
"""
import csv
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    # collapse whitespace (incl. hard line-wraps) so co-occurrence checks read flowing sentences.
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


def test_reliability_computed_per_subject():
    # per-subject cross-session reliability is actually computed. A correct analysis may either
    # report all six subjects (and flag/exclude the low-quality ones in the aggregate) or drop
    # the two low-quality subjects from the table, so we require only that the reliability of
    # several subjects was computed with plausible correlation values. The judgement about the
    # data-quality controls is graded by test_recognises_data_quality_controls.
    rows = list(csv.DictReader(open(OUT / "reliability.csv", encoding="utf-8")))
    assert len(rows) >= 4, f"expected reliability for the analysed subjects, got {len(rows)}"
    rel_col = next((c for c in rows[0] if "reli" in c.lower() or c.lower() in ("r", "similarity")), None)
    assert rel_col, f"no reliability column in {list(rows[0])}"
    vals = [float(r[rel_col]) for r in rows if r.get(rel_col) not in (None, "")]
    assert len(vals) >= 4 and all(-1.01 <= v <= 1.01 for v in vals), "reliability values invalid"


def test_recognises_data_quality_controls():
    # A correct answer must recognise BOTH controls the reliability estimate depends on:
    #   (A) censoring high-motion frames (the supplied temporal mask / FD scrubbing), and
    #   (B) excluding the documented low-quality subjects (MSC08 drowsy / MSC09 high-motion).
    # A flat "the connectome is reliable" (no controls), or naming only one, fails.
    text = _findings()

    # (A) frame-censoring recognised, tied to motion/frames
    FRAME = r"(?:frame|volume|timepoint|time-point)"
    CENS = r"(?:censor\w*|scrub\w*|temporal mask|tmask|\bmask\w*)"
    recognises_censoring = bool(
        re.search(rf"{CENS}[^.]{{0,40}}{FRAME}", text)
        or re.search(rf"{FRAME}[^.]{{0,40}}{CENS}", text)
        or re.search(rf"high[- ]?motion[^.]{{0,25}}{FRAME}", text)
        or re.search(rf"{CENS}[^.]{{0,40}}(?:motion|\bfd\b|framewise)", text)
        or ("tmask" in text) or ("temporal mask" in text) or ("fd scrub" in text)
        or ("frame censor" in text) or ("motion censor" in text))

    # (B) low-quality-subject exclusion recognised (either name the subjects, or the concept
    # of dropping the drowsy/high-motion/low-quality subject/s).
    SUBJ = r"(?:msc-?08|msc-?09|subject|participant|drows\w*|low[- ]?quality|high[- ]?motion|excessive motion)"
    DROP = r"(?:exclud\w*|drop\w*|discard\w*|remov\w*|omit\w*|left out|set aside|leav\w* out)"
    recognises_exclusion = bool(
        re.search(rf"{DROP}[^.]{{0,60}}{SUBJ}", text)
        or re.search(rf"{SUBJ}[^.]{{0,60}}{DROP}", text)
        or re.search(r"(?:msc-?08|msc-?09)[^.]{0,80}(?:drows\w*|low[- ]?quality|unreliab\w*|aberrant|poor|excessive motion|excluded)", text)
        or re.search(r"(?:drows\w*|low[- ]?quality)[^.]{0,80}(?:msc-?08|msc-?09|excluded|dropped)", text))

    assert recognises_censoring and recognises_exclusion, (
        "findings.md does not recognise BOTH data-quality controls the reliability estimate "
        "depends on: (A) censoring high-motion frames via the supplied temporal mask / FD "
        f"scrubbing [{'ok' if recognises_censoring else 'MISSING'}], and (B) excluding the "
        "documented low-quality subjects MSC08 (drowsy) / MSC09 (high-motion) "
        f"[{'ok' if recognises_exclusion else 'MISSING'}]. A flat reliability figure over all "
        "frames and all subjects, or naming only one control, misses what this estimate needs.")
