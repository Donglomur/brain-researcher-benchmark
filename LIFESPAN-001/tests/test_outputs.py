"""Proof-of-work grader for LIFESPAN-001 — how the resting connectome's organization changes
across the adult lifespan (NKI), summarised as global mean FC vs system segregation.

The previous verifier checked shapes + a keyword sentence. This grader validates the EXACT
packaged NKI subjects and their per-subject connectome summaries against a held-out reference
(tests/reference.npz), recomputes BOTH age relationships FROM the submitted rows, and grades the
scientific judgement AS NUMBERS: the naive summary (global mean FC) is ~flat with age while the
correct summary (system segregation) DECLINES (de-differentiation), matching the held-out
reference. Keyword prose is only secondary.

Reference (packaged NKI Destrieux-148 region time series, n=59, ages 18-78):
  global mean FC vs age      r = +0.15 (p 0.26)   <- naive summary, ~no change
  system segregation vs age  r = -0.28 (p 0.03)   <- declines (de-differentiation)
  within vs age +0.03 (flat) ; between vs age +0.12 (rises) -> drives the segregation decline
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
_R = r"pearsonr|pearson|^r$|^rvalue$|^corr|correlation"


def _reference():
    assert REF_PATH.exists(), "held-out reference tests/reference.npz is missing"
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "connectome_summary.csv"
    assert p.exists(), (
        "missing required per-subject output connectome_summary.csv (subject_id, age, "
        "global_connectivity, system_segregation, ...)")
    return pw.load_submitted(p)


def _results():
    p = OUT / "results.json"
    assert p.exists(), "missing required output results.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"results.json is not valid JSON: {e}")


def _findings():
    return re.sub(r"\s+", " ", (OUT / "findings.md").read_text(encoding="utf-8").lower())


def _r_glob(j):
    # leaf_re selects the pearson-r leaf, so path_exclude only needs branch (not quantity) filters
    return pw.find_path_number(j, path_include=["overall"], leaf_re=_R,
                               path_exclude=["segreg", "within", "between"],
                               prefer=["overall", "global", "mean"]) or \
        pw.find_path_number(j, path_include=["global"], leaf_re=_R,
                            path_exclude=["segreg", "within", "between"])


def _r_seg(j):
    return pw.find_path_number(j, path_include=["segreg"], leaf_re=_R,
                               path_exclude=["within", "between"])


def _r_named(j, name):
    return pw.find_path_number(j, path_include=[name], leaf_re=_R,
                               path_exclude=["segreg", "overall"])


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    sub = _submitted()
    assert len(sub) >= 40, f"connectome_summary.csv must carry per-subject rows; parsed {len(sub)}"
    n_wb = sum(1 for i in sub if sub[i].get("within") is not None and sub[i].get("between") is not None)
    assert n_wb >= 40, (
        "connectome_summary.csv must carry per-subject within_network_connectivity AND "
        "between_network_connectivity columns (the mean within-network and between-network edge "
        "connectivity of each subject's connectome). The system segregation is recomputed from "
        f"them; only {n_wb} rows provide both.")
    j = _results()
    assert isinstance(j, dict) and j, "results.json empty"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); sub = _submitted()
    pw.check_subjects_and_values(sub, ref, ref["stats"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_both_age_relationships_from_rows():
    ref = _reference(); sub = _submitted(); st = ref["stats"]; j = _results()
    matched = [i for i in ref["ids"] if i in sub and sub[i]["age"] is not None]
    import math
    ages = [sub[i]["age"] for i in matched]

    r_glob_rows = pw.pearson([sub[i]["global"] for i in matched], ages)
    assert math.isfinite(r_glob_rows), "cannot recompute global-vs-age r from the submitted rows"
    assert abs(r_glob_rows - st["r_glob"]) <= st["RECOMP_GLOB_TOL"], (
        f"global-vs-age r recomputed from the rows ({r_glob_rows:+.3f}) does not match the reference "
        f"({st['r_glob']:+.3f}, tol {st['RECOMP_GLOB_TOL']}).")
    rep_glob = _r_glob(j)
    assert rep_glob is not None and abs(r_glob_rows - rep_glob) <= st["RECOMP_GLOB_TOL"] + 0.02, (
        f"reported global-vs-age r ({rep_glob}) is not what the submitted rows produce "
        f"({r_glob_rows:+.3f}); CSV and JSON disagree.")

    # RECOMPUTE segregation-vs-age FROM the mandatory within/between columns (not the seg column,
    # not the reported scalar). seg_i = (within_i - between_i)/within_i.
    r_seg_rows, n_seg = pw.recompute_segregation_age_r(sub, matched, ref)
    assert math.isfinite(r_seg_rows) and n_seg >= 20, (
        "cannot recompute the segregation-vs-age relationship from the submitted per-subject "
        "within/between-network connectivity columns (they are required).")
    assert abs(r_seg_rows - st["r_seg"]) <= st["RECOMP_SEG_TOL"], (
        f"segregation-vs-age r recomputed from the within/between columns ({r_seg_rows:+.3f}) does "
        f"not match the reference ({st['r_seg']:+.3f}, tol {st['RECOMP_SEG_TOL']}).")
    rep_seg = _r_seg(j)
    if rep_seg is not None:
        assert abs(r_seg_rows - rep_seg) <= st["RECOMP_SEG_TOL"] + 0.03, (
            f"reported segregation-vs-age r ({rep_seg}) is not what the submitted within/between "
            f"rows produce ({r_seg_rows:+.3f}); CSV and JSON disagree.")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_conclusion_segregation_declines_global_flat_numeric():
    """Grade the judgement AS NUMBERS, with the segregation-vs-age relationship RECOMPUTED from the
    mandatory per-subject within/between columns -- not read from a reported scalar. An agent that
    omits the network columns, or fabricates them without the real per-subject network structure,
    cannot reach this gate by publishing r_seg ~ -0.28."""
    ref = _reference(); st = ref["stats"]; j = _results()
    sub = _submitted()
    matched = [i for i in ref["ids"] if i in sub and sub[i]["age"] is not None]
    import math
    ages = [ref["by_id"][i]["age"] for i in matched]

    # RECOMPUTE both summaries from the rows.
    r_glob = pw.pearson([sub[i]["global"] for i in matched], ages)
    r_seg, n_seg = pw.recompute_segregation_age_r(sub, matched, ref)
    assert math.isfinite(r_glob), "cannot recompute the global-vs-age r from the rows"
    assert math.isfinite(r_seg) and n_seg >= 20, (
        "cannot recompute the SYSTEM SEGREGATION vs age relationship from the submitted per-subject "
        "within/between-network connectivity columns. The judgement graded here is that the "
        "connectome's organization (network segregation) changes with age even though the global "
        "mean is ~flat; the within/between-network connectivity columns are required so it can be "
        "recomputed.")

    # (a) global mean FC is ~flat with age (the naive summary shows little/no change).
    assert abs(r_glob) <= st["GLOB_MAX_ABS"], (
        f"global-vs-age r recomputed from the rows = {r_glob:+.3f} is not the ~flat naive summary "
        f"(reference {st['r_glob']:+.3f}); overall mean connectivity is roughly unchanged with age.")

    # (b) system segregation (recomputed from within/between) DECLINES with age, matching reference.
    assert r_seg <= st["SEG_MAX"], (
        f"segregation-vs-age r recomputed from the within/between columns = {r_seg:+.3f} is not the "
        f"negative decline the organization shows (reference {st['r_seg']:+.3f}); the networks "
        f"de-differentiate with age.")
    assert abs(r_seg - st["r_seg"]) <= st["SEG_MATCH_TOL"], (
        f"segregation-vs-age r recomputed from the within/between columns = {r_seg:+.3f} is far from "
        f"the reference ({st['r_seg']:+.3f}, tol {st['SEG_MATCH_TOL']}).")

    # (c) segregation is clearly MORE negative than the global summary (the dissociation).
    assert r_glob - r_seg >= st["SEG_GLOB_GAP"], (
        f"the segregation summary ({r_seg:+.3f}) is not meaningfully more negative than the global "
        f"summary ({r_glob:+.3f}); the point is that organization changes where the global average "
        f"does not.")

    # (d) de-differentiation mechanism, recomputed from the rows: between-network rises with age
    #     more than within-network (the driver of the segregation decline).
    r_w = pw.pearson([sub[i]["within"] for i in matched], ages)
    r_b = pw.pearson([sub[i]["between"] for i in matched], ages)
    if math.isfinite(r_w) and math.isfinite(r_b):
        assert r_b > r_w, (
            f"between-network vs age r ({r_b:+.3f}) does not exceed within-network ({r_w:+.3f}); the "
            f"segregation decline is driven by between-network connectivity rising with age.")

    # (e) consistency: any REPORTED segregation-vs-age r must agree with the recompute.
    rep_seg = _r_seg(j)
    if rep_seg is not None:
        assert abs(rep_seg - r_seg) <= st["SEG_MATCH_TOL"] + 0.03, (
            f"reported segregation-vs-age r ({rep_seg:+.3f}) is inconsistent with the value "
            f"recomputed from the submitted within/between columns ({r_seg:+.3f}).")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_engage_segregation_and_avoid_flat_null():
    """SECONDARY (numbers carry the grade). findings.md must report that network
    segregation/organization DECLINES with age (de-differentiation) while overall mean
    connectivity is ~unchanged, and must NOT conclude a flat 'connectivity does not change with
    age' null read off the global average."""
    text = _findings()
    seg = re.search(r"(?:segregation|de-?differentiat\w*|organi[sz]ation|within-?\s*minus-?\s*between|"
                    r"network\s+differ\w*|system\s+segregation)", text)
    declines = re.search(r"(?:declin\w*|decreas\w*|reduc\w*|lower\w*|falls?|drops?|negativ\w*|"
                         r"de-?differentiat\w*|less\s+segregat\w*|weaken\w*)", text)
    flatglobal = re.search(r"(?:overall|global|mean)\s+(?:mean\s+)?(?:connectivity|fc)[^.\n]{0,60}"
                           r"(?:unchanged|flat|stable|no\s+(?:significant\s+)?(?:change|relationship)|"
                           r"not\s+(?:signif\w*|relat\w*)|roughly\s+constant|little\s+change)", text)
    assert seg and declines, (
        "findings.md does not report that network segregation / connectome organization declines "
        "with age (de-differentiation).")
    assert flatglobal, (
        "findings.md does not report that the naive summary (overall/global mean connectivity) is "
        "roughly unchanged with age -- the contrast that makes the segregation decline the point.")

    # over-claim guard: must not conclude a flat 'connectivity does not change with age' as THE result.
    null_concl = re.search(
        r"(?:conclude\w*|therefore|thus|so\s+that|overall,?)[^.\n]{0,60}"
        r"(?:connectivity|connectome)[^.\n]{0,40}(?:does not|doesn.t|no)\s+(?:change|vary|differ)[^.\n]{0,20}(?:with\s+age|across)"
        r"|resting[- ]?state\s+connectivity\s+(?:is\s+)?(?:stable|unchanged|does not change)\s+(?:with\s+age|across the\s+(?:adult\s+)?lifespan)",
        text)
    disclaim = re.search(r"(?:but|however|misleading|only\s+the\s+global|organi[sz]ation\s+(?:does|still)|"
                         r"segregation\s+(?:declin|decreas|still))", text)
    assert not (null_concl and not disclaim), (
        "findings.md over-claims a flat 'connectivity does not change with age' conclusion from the "
        "global average; the connectome's organization (segregation) does change (declines).")
