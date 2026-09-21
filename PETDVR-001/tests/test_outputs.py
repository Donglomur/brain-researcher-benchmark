"""Proof-of-work grader for PETDVR-001 ([11C]DASB SERT DVR, Logan reference-tissue analysis).

Reproduction task: the deliverable is a per-scan x per-region DVR table and the cohort
summary. The un-cued shortcut is regressing the Logan plot over ALL frames from t=0 (the
early distribution phase is still curved), which biases the slope DOWN ~16-34% on every
scan even though the overall fit R^2 stays ~0.99. The equilibrium-aware slope (linear
segment only) is the honest DVR. That choice changes the per-item DVR itself, so the grader
validates the submitted per-scan/per-region DVR against a held-out reference (tests/
reference.npz, built from the oracle on the real ds001420 TACs, never shipped to the agent),
recomputes the high-binding cohort mean from the submitted rows, and grades the cohort DVR
against the equilibrium-aware value versus the naive all-frames value -- WITHOUT naming the
equilibrium window in the instruction (the QSMDIPOLE held-out-reference model).

Held-out ground truth (Logan reference-tissue, linear-segment slope):
  high-binding per scan 2.681 / 3.169 / 2.886 / 3.078, mean 2.953 (MA1 agrees ~1%).
  regional means highbinding 2.95 / thalamus 2.37 / caudate 1.97 / putamen 2.50.
  Naive all-frames (t*=0): highbinding mean 2.354; thalamus 1.81; caudate 1.30 (16-34% low).
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

VAL_TOL_REL = 0.12     # per-item DVR vs held-out reference (honest/MA1 ~1-2%; naive >=16%)
VAL_TOL_ABS = 0.22
COVER_HB = 0.9         # coverage of the 4 high-binding scans
MATCH = 0.80           # fraction of matched items within tolerance
MEAN_TOL_REF = 0.18
MEAN_TOL_JSON = 0.12

REGION_ALIAS = {"highbinding": "highbinding", "highbind": "highbinding",
                "thalamus": "thalamus", "thalamic": "thalamus",
                "caudate": "caudate", "putamen": "putamen"}


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _submitted_map():
    p = OUT / "dvr_estimates.csv"
    assert p.exists(), "missing required output dvr_estimates.csv (one row per scan and region)"
    rows, headers = pw.read_rows(p)
    assert rows, "dvr_estimates.csv has no rows"
    val = pw.pick_col(headers, ("dvr", "slope", "ratio", "distributionvolumeratio"),
                      exclude=("ma1", "mrtm", "srtm", "bp", "tstar", "se", "std", "sd"))
    assert val is not None, f"no DVR column in dvr_estimates.csv: {headers}"
    id_groups = [(("subject", "subid", "participant", "sub"), ("session", "ses", "target")),
                 (("session", "ses"), ("subject", "target")),
                 (("target", "region", "roi"), ("subject", "session"))]
    return pw.build_submitted_map(rows, headers, id_groups, val, region_alias=REGION_ALIAS)


def _highbinding(smap, ref):
    return pw.match_items(smap, ref["ids"], ref["values"], subset_tokens="highbinding")


def test_outputs_present_and_wellformed():
    ref = _reference()
    smap = _submitted_map()
    hb = _highbinding(smap, ref)
    assert len(hb) >= 4, f"expected a high-binding DVR for all four scans, got {len(hb)}"
    assert all(1.0 <= s <= 5.0 for _, s, _ in hb), \
        f"high-binding [11C]DASB DVR outside a plausible range: {[s for _, s, _ in hb]}"


# ---------------------------------------------------------------- pillar 1
def test_proof_of_work_per_item_matches_reference():
    ref = _reference()
    smap = _submitted_map()
    matched = pw.match_items(smap, ref["ids"], ref["values"])
    hb = _highbinding(smap, ref)
    assert len(hb) / 4.0 >= COVER_HB, (
        f"dvr_estimates.csv covers only {len(hb)}/4 of the real high-binding scans by id; "
        f"fabricated or missing subject/session ids.")
    import statistics
    subvals = [s for _, s, _ in matched]
    assert len(subvals) >= 4 and statistics.pstdev(subvals) > 1e-3, (
        "submitted DVR values are constant across scans/regions -- not a real per-item table")
    close = sum(1 for _, s, r in matched if pw.within(s, r, VAL_TOL_REL, VAL_TOL_ABS))
    frac = close / len(matched)
    assert frac >= MATCH, (
        f"only {frac:.0%} of matched scan/region DVRs are within tolerance of the held-out "
        f"reference (need >= {MATCH:.0%}). The per-item DVR does not match the equilibrium-aware "
        f"Logan slope -- an all-frames fit (early, curved phase included) is ~16-34% low.")
    # the high-binding scans specifically must match (the headline)
    hb_close = sum(1 for _, s, r in hb if pw.within(s, r, VAL_TOL_REL, VAL_TOL_ABS))
    assert hb_close >= 3, (
        f"only {hb_close}/4 high-binding scans match the held-out reference; the all-frames "
        f"under-estimate (~2.35 vs ~2.95) is present.")
    # the high-binding DVR genuinely varies across the four scans (ref pstdev ~0.19); a table
    # that fills every scan with the same (correct-mean) value is not a real per-scan estimate.
    assert statistics.pstdev([s for _, s, _ in hb]) > 0.06, (
        "the high-binding DVR is (near-)identical across all four scans -- not a real per-scan "
        "Logan fit (the reference varies 2.68-3.17 across scans).")


# ---------------------------------------------------------------- pillar 2
def test_recompute_highbinding_mean():
    import statistics
    ref = _reference()
    smap = _submitted_map()
    hb = _highbinding(smap, ref)
    mean_rows = statistics.fmean([s for _, s, _ in hb])
    mean_ref = float(ref["stats"]["highbinding_mean_honest"])
    assert abs(mean_rows - mean_ref) <= MEAN_TOL_REF, (
        f"mean high-binding DVR recomputed from the submitted rows ({mean_rows:.3f}) does not "
        f"match the held-out reference ({mean_ref:.3f}, tol {MEAN_TOL_REF})")
    reported = pw.find_number(_load_json("run_metadata.json"),
                              [r"highbindingdvrmean", r"highbinding.*mean", r"mean.*highbinding",
                               r"dvrmean", r"meandvr"],
                              exclude=[r"naive", r"allframes", r"perscan", r"region", r"thal",
                                       r"caud", r"putamen", r"tstar"])
    if reported is None:
        reported = pw.find_number(_load_json("run_metadata.json"), [r"mean"],
                                  exclude=[r"naive", r"tstar", r"region"])
    assert reported is not None and abs(mean_rows - reported) <= MEAN_TOL_JSON, (
        f"mean high-binding DVR recomputed from the rows ({mean_rows:.3f}) does not match the "
        f"reported mean ({reported}); the table and reported summary disagree.")


# ---------------------------------------------------------------- pillar 3 (equilibrium discriminator)
def test_dvr_is_equilibrium_aware_not_allframes():
    import statistics
    ref = _reference()
    smap = _submitted_map()
    hb = _highbinding(smap, ref)
    mean_rows = statistics.fmean([s for _, s, _ in hb])
    st = ref["stats"]
    honest = float(st["highbinding_mean_honest"])
    naive = float(st["highbinding_mean_naive"])
    assert abs(mean_rows - honest) < abs(mean_rows - naive), (
        f"mean high-binding DVR ({mean_rows:.3f}) is closer to the naive all-frames value "
        f"({naive:.3f}) than to the equilibrium-aware value ({honest:.3f}) -- the early, "
        f"non-linear frames were not excluded from the Logan fit.")
    midpoint = (honest + naive) / 2.0
    assert mean_rows >= midpoint, (
        f"mean high-binding DVR {mean_rows:.3f} sits below the honest/naive midpoint "
        f"{midpoint:.3f}; consistent with an all-frames (t*=0) Logan fit, not the linear "
        f"segment.")
    # regional profile: if thalamus/caudate reported, they too must be at the equilibrium
    # level (naive drags every high-binding region down ~24-34%).
    for tok, naive_key in (("thalamus", "region_mean_naive"), ("caudate", "region_mean_naive")):
        reg = pw.match_items(smap, ref["ids"], ref["values"], subset_tokens=tok)
        if len(reg) >= 4:
            m = statistics.fmean([s for _, s, _ in reg])
            hon = float(st["region_mean_honest"][tok])
            nai = float(st["region_mean_naive"][tok])
            assert abs(m - hon) < abs(m - nai), (
                f"mean {tok} DVR ({m:.3f}) is closer to the naive all-frames value ({nai:.3f}) "
                f"than the equilibrium-aware value ({hon:.3f}).")


# ---------------------------------------------------------------- secondary prose signal
def test_findings_fit_window_secondary():
    """SECONDARY (the numeric pillars carry the grade): the write-up should treat the Logan
    linear segment / equilibrium onset as a considered choice, not merely 'fit the Logan plot'."""
    blob = ""
    for name in ("findings.md", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    text = blob.lower()
    assert text.strip(), "no findings.md / run_metadata.json produced"
    window = re.search(
        r"linear (segment|phase|portion|part|region)|equilibrium|steady[- ]?state"
        r"|\bt\s*\*|\btstar\b|t-?star|fit window|fitting window|start (time|frame)"
        r"|exclud\w+[^.\n]{0,40}(early|initial|first|pre)|(early|initial|first)[^.\n]{0,40}"
        r"(exclud|drop|discard|omit|remov)|late[- ]?time|after[^.\n]{0,20}(min|equilibr)", text)
    has_result = re.search(r"dvr|distribution volume ratio|slope|\bmin\b|\d\.\d", text)
    assert window and has_result, (
        "findings/run_metadata do not treat the Logan fit window (linear segment / equilibrium "
        "onset / excluded early frames) as a considered choice.")
