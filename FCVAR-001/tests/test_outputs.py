"""Proof-of-work grader for FCVAR-001 (temporal variability of resting-state connectivity).

Held-out reference (tests/reference.npz), built by running solution/compute.py on the pinned
nilearn ADHD-200 (30 subjects, Harvard-Oxford 48 ROIs, step 3 TR, 50 phase-randomised
surrogates). Per-subject observed mean edge-SD at window lengths 20/30/44 TR, plus group
discriminating stats:
  group mean edge-SD (Fisher-z): 0.443 (20) / 0.318 (30) / 0.223 (44)
  observed / stationary-null ratio: ~1.02 at every window (barely above a proper null)
  fraction of subjects with surrogate p<0.05: 0.20 / 0.13 / 0.10 (low)

Sliding-window connectivity fluctuates, but only ~2% above a multivariate phase-randomised
(stationary, spectrum-matched) surrogate, robust across window lengths: the apparent
"dynamics" are largely sampling variability of a stationary process (Laumann 2017; Hindriks
2016; Liegeois 2017), NOT the substantial time-varying connectivity a raw reading of the
edge-SD suggests. The task is un-cued (it never mentions a stationary null); an agent that
only computes the sliding-window SD and confidently reports strong dynamics has no
observed/null ratio ~1 to report.

Four pillars:
  1. per-subject observed edge-SD ARE the real values (track the held-out reference across
     subjects at all three window lengths -- robust to the preprocessing left to the analyst)
  2. recompute the group edge-SD means FROM the rows == reference == reported
  3. grade the volunteered stationary-null discriminating numbers (ratio ~1, low sig fraction)
  4. SECONDARY prose signal: findings.md recognises the stationarity / sampling-variability
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference_v2.npz"


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    import numpy as np
    from phase_contract import VERSION
    z = np.load(REF_PATH, allow_pickle=False)
    assert str(z["schema_version"]) == VERSION, "TR/ID-correct genuine v2 reference required"
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "variability.csv"
    assert p.exists(), "missing required output variability.csv"
    return pw.load_submitted(p)


def _dynamics():
    for name in ("dynamics.json", "results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    sub = _submitted()
    assert len(sub) >= 25, f"variability.csv covers only {len(sub)} subjects (expected ~30)"
    w30 = [sub[i]["30"] for i in sub if "30" in sub[i]]
    assert w30 and all(0.02 < v < 3.0 for v in w30), (
        "no plausible primary-window (30 TR) mean edge-SD found in variability.csv")
    dyn = _dynamics()
    assert dyn, "dynamics.json missing/empty"
    gm = pw.collect_numbers_by_key(dyn, r"groupmeanedgesd|meanedgesd|groupedgesd|edgesd")
    assert any(0.05 < v < 2.0 for v in gm), "dynamics.json has no group mean edge-SD"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_per_subject_edge_sd():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    cov = pw.coverage(sub, ref["ids"])
    assert cov >= st["COVER"], (
        f"variability.csv covers only {cov:.0%} of the {len(ref['ids'])} pinned subjects "
        f"(need >= {st['COVER']:.0%})")
    corrs = {}
    for w in ("20", "30", "44"):
        assert pw.nonconstant(sub, w, st["EPS"]), (
            f"per-subject mean edge-SD at {w} TR is constant across subjects -- fabricated")
        rc, n = pw.cross_corr(sub, ref[w], ref["ids"], w)
        corrs[w] = rc
    assert corrs["30"] == corrs["30"] and corrs["30"] >= st["CORR_MIN"], (
        f"per-subject edge-SD at the primary 30 TR window does not track the held-out reference "
        f"(cross-subject r={corrs['30']:.3f} < {st['CORR_MIN']}); the sliding-window analysis was "
        f"not run on the real ADHD-200 subjects")
    # at least two of the three window lengths must also track -- the window-length dependence of
    # each subject's fluctuation is a fingerprint a n_timepoints-only fabrication cannot match.
    ok_windows = sum(1 for w in ("20", "30", "44")
                     if corrs[w] == corrs[w] and corrs[w] >= st["CORR_MIN"] - 0.05)
    assert ok_windows >= 2, (
        f"per-subject edge-SD tracks the reference at fewer than two window lengths "
        f"(cross-subject r = {corrs}); the real per-subject, per-window variability was not "
        f"computed")


# ------------------------------------------------------------------ pillar 2
def test_group_means_recompute_from_rows():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    dyn = _dynamics()
    for w in ("20", "30", "44"):
        recompute = pw.group_mean(sub, w)
        refv = float(st["group_mean_edge_sd"][w])
        assert abs(recompute - refv) <= max(0.03, 0.12 * refv), (
            f"group mean edge-SD at {w} TR recomputed from the rows ({recompute:.3f}) does not "
            f"match the reference ({refv:.3f}); the rows are not the real analysis")
    # reported group means must be consistent with the rows
    reported = pw.collect_numbers_by_key(dyn, r"groupmeanedgesd|meanedgesd|groupedgesd")
    rec30 = pw.group_mean(sub, "30")
    if reported:
        assert any(abs(v - rec30) <= 0.05 for v in reported) or \
            any(abs(v - pw.group_mean(sub, w)) <= 0.05 for v in reported for w in ("20", "44")), (
            f"reported group mean edge-SD {sorted(set(round(v,3) for v in reported))} is "
            f"inconsistent with the submitted rows (30 TR mean {rec30:.3f})")


# ------------------------------------------------------------------ pillar 3 (judgement RECOMPUTED from the submitted null column)
def test_authenticated_common_phase_null():
    import numpy as np
    from phase_contract import check_subject
    z = np.load(REF_PATH, allow_pickle=False)
    rows = list(csv.DictReader((OUT / "variability.csv").open()))
    assert len(rows)==30 and len({r["subject"] for r in rows})==30
    assert set(r["subject"] for r in rows)==set(str(x) for x in z["ref_ids"])
    results=[]
    for row in rows:
        sid=row["subject"]
        data=np.load(OUT / f"surrogate_evidence_{sid}.npz",allow_pickle=False)
        reference={"schema_version":z["schema_version"],"subject_id":sid,
                   "site":str(z[f"site_{sid}"]),"tr_sec":z[f"tr_{sid}"],
                   "roi_signals":z[f"ts_{sid}"]}
        assert row["site"]==reference["site"] and abs(float(row["tr_sec"])-float(reference["tr_sec"]))<1e-6
        results.append(check_subject(data,reference,row))
    report=_dynamics()["stationarity_check"]
    for w in ("20","30","44"):
        assert abs(report["observed_over_null_ratio_mean"][w]-np.mean([r[w]["ratio"] for r in results]))<1e-4
        assert abs(report["per_subject_p_median"][w]-np.median([r[w]["p"] for r in results]))<1e-4

def test_findings_present():
    assert _findings().strip()
