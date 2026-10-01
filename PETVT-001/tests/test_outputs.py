"""Real-data arterial-input kinetic method case with documented decay footing.
Activity sampling times do not establish activity decay correction status.
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

VAL_TOL_REL = 0.15     # per-subject V_T vs held-out reference (honest/MA1 ~1%; naive >=17%)
VAL_TOL_ABS = 0.08
COVER = 1.0
MATCH = 6.0 / 7.0
MEAN_TOL_REF = 0.07    # recomputed cohort mean vs reference honest mean (0.797)
MEAN_TOL_JSON = 0.06   # recomputed cohort mean vs reported JSON mean


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    ref=pw.load_reference(REF_PATH)
    assert ref["stats"].get("pipeline_id")=="source-documented-decay-footing-v1", "failed_precondition: resolve arterial activity footing and regenerate corresponding V_T reference"
    return ref


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _submitted_map():
    p = OUT / "vt_estimates.csv"
    assert p.exists(), "missing required output vt_estimates.csv (one row per participant)"
    rows, headers = pw.read_rows(p)
    assert rows, "vt_estimates.csv has no rows"
    # keep cortical rows if a target/region column distinguishes them
    tgt = pw.pick_col(headers, ("target", "region", "roi", "targetregion"))
    if tgt is not None:
        cort = [r for r in rows if re.search(r"cort", str(r.get(tgt, "")), re.I)]
        if len(cort) >= 6:
            rows = cort
    val = pw.pick_col(headers, ("vt", "distributionvolume", "totaldistributionvolume"),
                      exclude=("ma1", "ref", "std", "se", "sd", "cov", "2tcm", "err"))
    assert val is not None, f"no V_T column in vt_estimates.csv: {headers}"
    id_groups = [(("subject", "subid", "participant", "id", "sub"), ("session", "ses"))]
    return pw.build_submitted_map(rows, headers, id_groups, val)


def test_outputs_present_and_wellformed():
    ref = _reference()
    m = _load_json("run_metadata.json")
    smap = _submitted_map()
    assert len(smap) == 7, f"expected all seven participants, got {len(smap)}"
    assert {pw.norm(k) for k in smap}=={pw.norm(k) for k in ref["ids"]}, "exact pinned participant/session IDs required"
    vals = list(smap.values())
    assert all(0.2 <= v <= 1.6 for v in vals), \
        f"cortical [18F]SF51 V_T outside a physiological range: {vals}"


# ---------------------------------------------------------------- pillar 1
def test_proof_of_work_per_subject_matches_reference():
    ref = _reference()
    smap = _submitted_map()
    matched = pw.match_items(smap, ref["ids"], ref["values"])
    coverage = len(matched) / len(ref["ids"])
    assert coverage >= COVER, (
        f"vt_estimates.csv covers only {coverage:.0%} of the {len(ref['ids'])} real ds005619 "
        f"participants by id (need >= {COVER:.0%}); fabricated or missing subject ids.")
    import statistics
    subvals = [s for _, s, _ in matched]
    assert statistics.pstdev(subvals) > 1e-4, (
        "submitted V_T is constant across participants -- not a real per-subject estimate")
    close = sum(1 for _, s, r in matched if pw.within(s, r, VAL_TOL_REL, VAL_TOL_ABS))
    frac = close / len(matched)
    assert frac >= MATCH, (
        f"only {frac:.0%} of matched participants are within tolerance of the held-out "
        f"reference V_T (need >= {MATCH:.0%}). The per-subject cortical V_T does not match the "
        f"metabolite-corrected, decay-referenced arterial-plasma reference -- a whole-blood or "
        f"uncorrected-plasma input gives per-subject values 17-50% off.")


# ---------------------------------------------------------------- pillar 2
def test_recompute_cohort_mean():
    import statistics
    ref = _reference()
    smap = _submitted_map()
    matched = pw.match_items(smap, ref["ids"], ref["values"])
    mean_rows = statistics.fmean([s for _, s, _ in matched])
    mean_ref = float(ref["stats"]["mean_honest"])
    assert abs(mean_rows - mean_ref) <= MEAN_TOL_REF, (
        f"cohort-mean cortical V_T recomputed from the submitted rows ({mean_rows:.3f}) does "
        f"not match the held-out reference ({mean_ref:.3f}, tol {MEAN_TOL_REF})")
    reported = pw.find_number(_load_json("run_metadata.json"),
                              [r"vtmean", r"meanvt", r"cortexvtmean", r"cohort.*vt", r"vt.*mean"],
                              exclude=[r"ma1", r"perscan", r"persubject", r"ratio", r"max", r"min"])
    if reported is None:
        reported = pw.find_number(_load_json("run_metadata.json"), [r"mean"], exclude=[r"ma1", r"ratio"])
    assert reported is not None and abs(mean_rows - reported) <= MEAN_TOL_JSON, (
        f"cohort-mean V_T recomputed from the rows ({mean_rows:.3f}) does not match the reported "
        f"mean ({reported}); the table and the reported summary disagree.")


# ---------------------------------------------------------------- pillar 3 (discriminating magnitude)
def test_cohort_vt_is_honest_input_not_naive():
    import statistics
    ref = _reference()
    smap = _submitted_map()
    matched = pw.match_items(smap, ref["ids"], ref["values"])
    mean_rows = statistics.fmean([s for _, s, _ in matched])
    st = ref["stats"]
    honest = float(st["mean_honest"])
    naive_means = [float(st["mean_uncorrected_plasma"]), float(st["mean_whole_blood"]),
                   float(st["mean_no_decay_ref"])]
    d_honest = abs(mean_rows - honest)
    assert all(d_honest < abs(mean_rows - nm) for nm in naive_means), (
        f"cohort-mean cortical V_T ({mean_rows:.3f}) is closer to a naive input construction "
        f"({naive_means}) than to the honest metabolite-corrected arterial-plasma value "
        f"({honest:.3f}). Whole-blood / uncorrected-plasma / non-decay-referenced inputs give "
        f"the wrong V_T.")
    # descriptive (NOT genotype-attributed): the per-subject estimate genuinely varies
    vals = [s for _, s, _ in matched]
    ratio = max(vals) / min(vals) if min(vals) > 0 else 1.0
    assert ratio >= 1.6, (
        f"per-participant V_T spread (max/min {ratio:.2f}) is too small to be the real cohort "
        f"of per-subject estimates.")


# ---------------------------------------------------------------- secondary prose signal
def test_findings_input_construction_secondary():
    """SECONDARY (the numeric pillars carry the grade): the write-up should recognise that the
    invasive V_T depends on the arterial INPUT construction (parent/metabolite-corrected
    plasma), not merely name 'the arterial input'."""
    text = ((OUT / "findings.md").read_text(encoding="utf-8").lower()
            if (OUT / "findings.md").exists() else "")
    assert text, "findings.md missing or empty"
    names_input = re.search(r"plasma|arterial|input function|blood", text)
    considered = re.search(
        r"(?:plasma|input|arterial)[^.\n]{0,40}(?:parent|metabolit|corrected|intact)"
        r"|(?:parent[- ]?fraction|metabolit\w*|intact[- ]?parent|corrected)[^.\n]{0,40}"
        r"(?:plasma|input|arterial)"
        r"|(?:whole[- ]?blood|uncorrected|total plasma)[^.\n]{0,60}"
        r"(?:not the input|differ|bias|wrong|instead|lower|higher|over[- ]?estimat|under[- ]?estimat)"
        r"|(?:input|plasma)[^.\n]{0,40}(?:choice|definition|construction|depend|differ|matters)"
        r"|(?:parent[- ]?fraction|metabolite)[- ]?correct", text)
    assert names_input and considered, (
        "findings.md does not articulate the arterial-input construction as a considered choice "
        "(the metabolite-corrected parent-in-plasma input, or that V_T depends on it).")
