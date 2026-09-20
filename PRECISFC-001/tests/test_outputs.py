"""Proof-of-work grader for PRECISFC-001 — test-retest reliability of the individual connectome
(MSC / ds000224), and how the documented low-quality subjects affect the group estimate.

The previous verifier checked value ranges + a keyword sentence, so it passed on fabricated
tables. This grader validates the EXACT MSC subjects and their per-subject cross-session
reliability against a held-out reference (tests/reference.npz), recomputes the excluded-group
reliability FROM the submitted rows, and grades the scientific judgement AS NUMBERS: the naive
all-subjects figure is dragged down and recovers once the reliability-outlier subject (MSC08) is
set aside (and/or high-motion frames censored), matching the held-out reference. Frame-censoring
is an accepted refinement (not required), so per-subject values may be censored OR all-frames.

R2 hedge (folded in): the reliability recovery is scoped to the MSC08 outlier (+ frame
censoring). MSC09's OWN cross-session reliability is normal-range (~0.51-0.53); excluding it is a
standard high-motion QC choice, NOT the removal of a reliability outlier. The grader therefore
checks MSC09's reliability is normal-range and rejects a write-up that calls MSC09 a reliability
outlier / aberrant / unstable-network subject.

Reference (ds000224 volume_pipeline, Power-264 5mm, MSC01/02/05/06/08/09, func01-03):
  MSC08 reliability 0.085 (all frames) -> 0.300 (censored)   <- the low-reliability outlier
  MSC09 reliability 0.514 -> 0.531                           <- normal-range (not an outlier)
  group naive (all 6, all frames) 0.533 -> exclude low-quality (+censor) 0.66
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
_GEXC = ["persub", "persubject", "msc", "retention", "frame", "nsession", "nsub", "count"]


def _reference():
    assert REF_PATH.exists(), "held-out reference tests/reference.npz is missing"
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "reliability.csv"
    assert p.exists(), "missing required output reliability.csv"
    return pw.load_submitted(p)


def _stats():
    p = OUT / "reliability_stats.json"
    assert p.exists(), "missing required output reliability_stats.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"reliability_stats.json is not valid JSON: {e}")


def _findings():
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


def _naive_group(j):
    v = pw.find_path_number(j, path_include=["all", "subject"],
                            path_exclude=_GEXC + ["exclud", "without", "drop", "usable", "included", "clean"],
                            prefer=["naive", "allframesallsubject", "allsix", "overall"])
    if v is None:
        v = pw.find_path_number(j, path_include=["naive"], path_exclude=_GEXC)
    return v


def _correct_group(j):
    for inc in (["exclud"], ["without"], ["drop"], ["usable"], ["included"], ["clean"], ["highquality"]):
        v = pw.find_path_number(j, path_include=inc, path_exclude=_GEXC, prefer=["censored", "cens"])
        if v is not None:
            return v
    return None


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub = _submitted()
    assert len(sub) >= 4, f"reliability.csv must carry per-subject reliability; parsed {len(sub)} rows"
    assert all(-1.01 <= v <= 1.01 for v in sub.values()), "reliability values out of range"
    j = _stats()
    assert isinstance(j, dict) and j, "reliability_stats.json empty"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); sub = _submitted(); st = ref["stats"]
    pw.check_subjects_and_values(sub, ref, val_tol=st["VAL_TOL"], cover=st["COVER"],
                                 match=st["MATCH"], eps=st["EPS"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_excluded_group_from_rows():
    """The reported excluded/high-quality group reliability must equal the mean over the usable
    subjects (excluding the documented low-quality subjects) of the SUBMITTED per-subject rows."""
    ref = _reference(); sub = _submitted(); st = ref["stats"]
    usable = [i for i in st["usable"] if i in sub]
    assert len(usable) >= 3, "cannot recompute excluded-group reliability: usable subjects missing"
    recompute = pw.group_mean(sub, usable)
    j = _stats()
    reported = _correct_group(j)
    assert reported is not None, (
        "reliability_stats.json does not report the group reliability EXCLUDING the documented "
        "low-quality subjects (MSC08/MSC09).")
    assert abs(recompute - reported) <= st["RECOMP_TOL"] + 0.02, (
        f"excluded-group reliability recomputed from the submitted rows ({recompute:.3f}) does not "
        f"match the reported value ({reported:.3f}); the rows and the summary disagree.")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_conclusion_recovery_and_outlier_numeric():
    ref = _reference(); sub = _submitted(); st = ref["stats"]; j = _stats()
    naive = _naive_group(j)
    correct = _correct_group(j)
    assert naive is not None, (
        "reliability_stats.json does not report the group reliability INCLUDING all subjects "
        "(the naive figure).")
    assert correct is not None, "no excluded-low-quality group reliability reported."

    # (a) the naive all-subjects figure is dragged down; the excluded figure recovers.
    assert naive <= st["NAIVE_MAX"], (
        f"reported all-subjects group reliability {naive:.3f} is not the dragged-down naive figure "
        f"(reference ~{st['naive_all6_allframes']:.3f}).")
    assert correct >= st["CORRECT_MIN"], (
        f"reported excluded-group reliability {correct:.3f} is below the honest recovered value "
        f"(reference ~{st['correct_censored_excl']:.3f}).")
    assert correct - naive >= st["RECOVERY_MIN"], (
        f"the group reliability does not recover once the low-quality subject(s) are set aside "
        f"(naive {naive:.3f} -> excluded {correct:.3f}); the recovery is the graded result.")
    # excluded figure matches one of the valid reference recoveries (censored or all-frames).
    assert min(abs(correct - st["correct_censored_excl"]), abs(correct - st["correct_allframes_excl"])) <= 0.05, (
        f"reported excluded-group reliability {correct:.3f} matches neither reference recovery "
        f"({st['correct_allframes_excl']:.3f} all-frames / {st['correct_censored_excl']:.3f} censored).")

    # (b) MSC08 is the low-reliability outlier (its real, far-below-band value).
    assert "MSC08" in sub, "MSC08 (the reliability outlier) is missing from the per-subject table."
    assert sub["MSC08"] <= st["MSC08_OUTLIER_MAX"], (
        f"submitted MSC08 reliability {sub['MSC08']:.3f} is not the real low-reliability outlier "
        f"value (censored ~{st['msc08_censored']:.2f} / all-frames ~{st['msc08_allframes']:.2f}).")
    usable_present = [sub[i] for i in st["usable"] if i in sub]
    assert usable_present and sub["MSC08"] < min(usable_present) - 0.1, (
        "MSC08's reliability is not far below the usable subjects; it must be the clear outlier.")

    # (c) R2 HEDGE: MSC09's OWN reliability is normal-range (not a reliability outlier).
    assert "MSC09" in sub, "MSC09 is missing from the per-subject table."
    assert sub["MSC09"] >= st["MSC09_NORMAL_MIN"], (
        f"submitted MSC09 reliability {sub['MSC09']:.3f} is not the real normal-range value "
        f"(~{st['msc09_censored']:.2f}); MSC09 is documented low-quality for MOTION, and its own "
        f"cross-session reliability is normal-range -- it is not a reliability outlier.")


# ------------------------------------------------------------------ secondary prose (with R2 hedge)
def test_findings_scope_recovery_and_hedge_msc09():
    """SECONDARY (numbers carry the grade). findings.md must (a) state that the individual
    connectome is reliable and the naive all-subjects figure is dragged down / recovers when the
    low-quality subject(s) are set aside (and/or frames censored), naming MSC08 as the
    low-reliability outlier; and (b) NOT over-attribute the recovery to MSC09 or call MSC09 a
    reliability outlier (R2 hedge)."""
    text = _findings()

    recovers = re.search(
        r"(?:exclud\w*|set\s+aside|drop\w*|remov\w*|censor\w*|scrub\w*|low[- ]?quality|"
        r"data[- ]?quality)[^.\n]{0,90}"
        r"(?:reliab\w*|recover\w*|rises?|increase\w*|higher|improv\w*|0\.6|0\.5)"
        r"|(?:reliab\w*|group figure|estimate)[^.\n]{0,90}"
        r"(?:dragged|deflat\w*|lower\w*|understate\w*|drag\w*|contaminat\w*)[^.\n]{0,40}"
        r"(?:low[- ]?quality|msc08|outlier|subject)", text)
    assert recovers, (
        "findings.md does not report that the naive all-subjects group reliability is dragged down "
        "and recovers once the low-quality subject(s) are set aside (and/or high-motion frames "
        "censored).")

    msc08_outlier = re.search(
        r"msc0?8[^.\n]{0,80}(?:outlier|low\w*\s+reliab|barely\s+reliab|unreliab\w*|collaps\w*|"
        r"aberrant|unstable|0\.0|0\.1|0\.2|0\.3|drowsy|degenerate|far\s+below)"
        r"|(?:outlier|low\w*\s+reliab|unreliab\w*|barely\s+reliab|degenerate)[^.\n]{0,40}msc0?8", text)
    assert msc08_outlier, (
        "findings.md does not identify MSC08 as the low-reliability outlier (its cross-session "
        "reliability collapses; it is what drags down and, once set aside, recovers the group figure).")

    # R2 HEDGE guard: do not call MSC09 a reliability outlier / aberrant / unstable-networks.
    msc09_outlier_claim = re.search(
        r"msc0?9[^.\n]{0,70}(?:reliab\w*\s+outlier|is\s+an?\s+outlier|aberrant|unstable\s+network|"
        r"barely\s+reliab|unreliab\w*|degenerate|reliab\w*\s+collaps\w*|low\s+reliab\w*)"
        r"|(?:reliab\w*\s+outlier|aberrant|unstable\s+network|degenerate|barely\s+reliab)[^.\n]{0,40}msc0?9",
        text)
    hedge_ok = re.search(
        r"msc0?9[^.\n]{0,90}(?:normal|typical|comparable|usual|in\s+the\s+(?:usable|normal)\s+range|"
        r"motion|high[- ]?motion|excessive\s+motion|standard\s+qc|quality[- ]?control|acceptable|"
        r"not\s+(?:an?\s+)?(?:reliab\w*\s+)?outlier)", text)
    assert not (msc09_outlier_claim and not hedge_ok), (
        "findings.md over-attributes the reliability story to MSC09 (calls it a reliability outlier "
        "/ aberrant / unstable). MSC09's OWN cross-session reliability is normal-range (~0.51-0.53); "
        "it is excluded on a standard high-motion QC basis, not as a reliability outlier -- scope the "
        "reliability recovery to MSC08 (+ frame censoring).")
