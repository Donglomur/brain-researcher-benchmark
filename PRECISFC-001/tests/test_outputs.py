"""Grading checks for PRECISFC-001 (test-retest reliability of the individual connectome, MSC).

Ground truth (validated before release on ds000224 volume_pipeline, Power-264 5mm spheres,
sub-MSC01/02/05/06/08/09, ses-func01/02/03; reliability = mean pairwise correlation of the
per-session connectome edge-vectors):

  per subject  cross-session reliability, frame retention
    MSC01  0.63  (80%)     MSC02  0.54  (86%)
    MSC05  0.68  (84%)     MSC06  0.75  (93%)
    MSC08  0.09  (24%)     MSC09  0.51  (60%)   # documented low-quality
  GROUP mean reliability
    naive   (all 6 subjects)                   0.53
    exclude MSC08 & MSC09                       0.65   (~ 0.66 if frames are also censored)

The individual connectome is highly reliable, but the naive group figure (all six subjects) is
dragged down and CONTAMINATED by two subjects that MSC precision mapping documents as low quality
and sets aside: MSC08 (pervasive self-reported drowsiness -> unstable, aberrant networks; only 24%
of frames survive motion censoring; cross-session reliability collapses to ~0.09) and MSC09
(excessive in-scanner motion) -- Gordon 2017; Laumann 2015; Seitzman 2019. The task lists all six
subjects and never says any should be set aside.

The failure mode this task targets (un-cued, data-quality / sample-selection axis): the agent
computes one reliability figure over all six subjects and reports it (~0.53), never volunteering
that MSC08 is a degenerate outlier (0.09) it can see in its own per-subject table and that the two
documented low-quality subjects should be excluded/flagged from the estimate. A flat "the connectome
is reliable, r = 0.53" fails; recognising the low-quality-subject exclusion passes. (Frame-censoring
with the supplied temporal mask is an accepted refinement, but is NOT required -- excluding the two
low-quality subjects already recovers the honest ~0.65, so an answer that excludes them without
censoring is fully correct.)
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
    # several subjects was computed with plausible correlation values. The un-cued judgement about
    # excluding the documented low-quality subjects is graded by the next test.
    rows = list(csv.DictReader(open(OUT / "reliability.csv", encoding="utf-8")))
    assert len(rows) >= 4, f"expected reliability for the analysed subjects, got {len(rows)}"
    rel_col = next((c for c in rows[0] if "reli" in c.lower() or c.lower() in ("r", "similarity")), None)
    assert rel_col, f"no reliability column in {list(rows[0])}"
    vals = [float(r[rel_col]) for r in rows if r.get(rel_col) not in (None, "")]
    assert len(vals) >= 4 and all(-1.01 <= v <= 1.01 for v in vals), "reliability values invalid"


def test_recognises_low_quality_subject_exclusion():
    # The un-cued judgement: the two documented low-quality subjects (MSC08 pervasively drowsy ->
    # unstable networks; MSC09 excessive motion) contaminate the naive group reliability and should
    # be excluded / flagged from the estimate. A flat reliability figure over all six subjects, with
    # no recognition that the low-quality subjects should be set aside, fails.
    text = _findings()

    # explicit low-quality subject ids
    SUBJID = r"msc-?0?[89]"
    # subject-level data-quality descriptors. NB: bare "high motion" / "motion" is ALSO
    # frame-censoring vocabulary ("removed high-motion frames"), so it is handled separately and
    # only counts when tied to a subject id -- it is NOT in this set.
    QUAL = (r"(?:drows\w*|sleep\w*|low[- ]?quality|poor[- ]?quality|unreliab\w*|aberrant|unstable|"
            r"outlier\w*|degenerate|low[- ]?data|documented (?:low|poor)|too noisy|noisy scan|"
            r"little (?:usable|data)|not usable)")
    # an action that sets a subject aside from the aggregate
    ACT = (r"(?:exclud\w*|drop\w*|discard\w*|remov\w*|omit\w*|set aside|left out|leav\w* out|"
           r"disregard\w*|down[- ]?weight\w*|flag\w*)")
    # a generic subject noun so a non-id-naming answer can still qualify
    SUBJGEN = r"(?:subject|participant|scan)"
    # forbid frame/censoring vocabulary between an action verb and a subject id, so
    # "removed high-motion FRAMES for MSC08" (censoring) does not read as excluding the subject.
    NOFRAME = r"(?:(?!frame|volume|time[- ]?point|censor|scrub|\bmask|motion param)[^.])"

    recognises = bool(
        # (A) an explicit low-quality subject id set aside / flagged (no frame-censoring word between)
        re.search(rf"{ACT}{NOFRAME}{{0,50}}{SUBJID}", text)
        or re.search(rf"{SUBJID}{NOFRAME}{{0,50}}{ACT}", text)
        # (B) an explicit low-quality subject id characterised as low-quality / drowsy / an outlier
        or re.search(rf"{SUBJID}[^.]{{0,80}}{QUAL}", text)
        or re.search(rf"{QUAL}[^.]{{0,80}}{SUBJID}", text)
        # (C) an explicit id characterised as high-motion (id present -> not frame vocabulary)
        or re.search(rf"{SUBJID}[^.]{{0,60}}(?:high[- ]?motion|excessive motion|too much motion)", text)
        or re.search(rf"(?:high[- ]?motion|excessive motion|too much motion)[^.]{{0,40}}{SUBJID}", text)
        # (D) generic "exclude/flag the (two) low-quality/drowsy/high-motion SUBJECT(s)" (subject
        # noun required, so frame-censoring phrasing cannot satisfy it)
        or re.search(rf"{ACT}\s+(?:the\s+)?(?:two|both|2|these)?\s*(?:documented\s+)?"
                     rf"(?:{QUAL}|high[- ]?motion|drowsy)\s+(?:\w+\s+){{0,1}}?{SUBJGEN}s?", text)
    )

    assert recognises, (
        "findings.md does not recognise that the documented low-quality subjects (MSC08 pervasively "
        "drowsy -> unstable networks / only ~24% of frames usable; MSC09 excessive motion) are "
        "outliers that contaminate the naive group reliability and should be excluded / flagged from "
        "the estimate. A single reliability figure over all six subjects (~0.53), with no recognition "
        "that the low-quality subjects should be set aside, misses what this estimate needs -- the "
        "individual connectome is highly reliable (~0.65) once they are excluded.")
