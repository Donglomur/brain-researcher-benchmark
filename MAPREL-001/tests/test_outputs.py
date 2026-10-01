"""Proof-of-work grader for MAPREL-001 (a between-map correlation that fails a spatial null).

Held-out reference (tests/reference.npz), built by running solution/compute.py on the pinned
neuromaps fsLR-32k annotations (Margulies-2016 fcgradient02, HCP-S1200 thickness) parcellated
with Schaefer-400 7-network:
  per-parcel gradient2 + thickness (400 rows)         -> parcels.csv
  Pearson r across parcels                = -0.222
  parametric p (n=400 treated iid)        =  7.1e-06   "highly significant"
  spin / spatial-autocorrelation null p   = ~0.45      NOT significant (null sd ~0.26)

Both maps are strongly spatially autocorrelated, so the ~400 parcels are nowhere near 400
independent observations; the parametric (and label-shuffle) p is badly anti-conservative.
The honest, un-cued move is to compare r against a spatial-autocorrelation-preserving (spin)
null and report the correlation as NOT significant. An agent that only reports the parametric
p cannot produce a spin-null p ~0.45 or a wide spin-null distribution.

Four pillars:
  1. per-parcel gradient2 + thickness ARE the real parcellated maps (track the held-out ref)
  2. recompute |r| across parcels FROM the rows == reference == reported
  3. grade the volunteered spatial-null result as numbers (spin p > 0.05, parametric p tiny,
     spin-null distribution wide, verdict not significant)
  4. SECONDARY prose signal: findings.md recognises the spatial-autocorrelation non-significance
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "parcels.csv"
    assert p.exists(), "missing required output parcels.csv"
    return pw.load_submitted(p)


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""


def _reported_r(blobs):
    cand = []
    for blob in blobs.values():
        for path, v in pw.numbers_with_path(blob):
            if re.search(r"pearson|correlat|(?:^|/)r$|(?:^|/)corr$|rvalue|coef|rho", path) \
                    and not re.search(r"pval|pspin|spin|null|param|shuffle|nparcel|permut", path):
                if 0.05 <= abs(v) <= 0.6:
                    cand.append(v)
    return cand


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    sub = _submitted()
    assert len(sub) >= 380, f"parcels.csv covers only {len(sub)} parcels (expected ~400)"
    blobs = _blobs()
    assert blobs, "no results JSON found"
    assert _reported_r(blobs), "no between-map Pearson r (|r| in [0.05,0.6]) reported"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_parcels_match_reference():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    cov = pw.coverage(sub, ref["pid"])
    assert cov >= st["COVER"], (
        f"parcels.csv covers only {cov:.0%} of the {len(ref['pid'])} Schaefer-400 parcels "
        f"(need >= {st['COVER']:.0%})")
    assert pw.nonconstant(sub, 0, st["EPS"]) and pw.nonconstant(sub, 1, st["EPS"]), (
        "a submitted parcel map is constant across parcels -- not a real parcellation")
    # gradient sign convention is arbitrary -> match by |corr|; thickness is a signed physical map.
    gc, ng = pw.cross_corr(sub, ref["grad"], ref["pid"], 0)
    tc, nt = pw.cross_corr(sub, ref["thick"], ref["pid"], 1)
    assert abs(gc) >= st["CORR_MIN"], (
        f"submitted gradient2 parcel values do not track the reference (cross-parcel |r|="
        f"{abs(gc):.3f} < {st['CORR_MIN']}); the Margulies gradient was not parcellated with the "
        f"pinned Schaefer-400 atlas")
    assert tc >= st["CORR_MIN"], (
        f"submitted thickness parcel values do not track the reference (cross-parcel r={tc:.3f} "
        f"< {st['CORR_MIN']}); the HCP thickness map was not parcellated with the pinned atlas")


# ------------------------------------------------------------------ pillar 2
def test_recompute_correlation_from_rows():
    ref = _reference()
    st = ref["stats"]
    sub = _submitted()
    r_rows = pw.recompute_abs_r(sub, ref["pid"])
    r_ref = abs(float(st["r_obs"]))
    assert abs(r_rows - r_ref) <= st["R_TOL"], (
        f"|Pearson r| recomputed from the submitted parcels ({r_rows:.3f}) does not match the "
        f"reference ({r_ref:.3f}, tol {st['R_TOL']}); the rows are not the real analysis")
    reported = _reported_r(_blobs())
    assert any(abs(abs(v) - r_rows) <= st["R_TOL"] for v in reported), (
        f"reported Pearson r {sorted(set(round(v,3) for v in reported))} is inconsistent with the "
        f"|r| recomputed from the submitted parcels ({r_rows:.3f})")


# ------------------------------------------------------------------ pillar 3 (judgement RECOMPUTED from the submitted null distribution)
def test_declared_spin_construction():
    from spin_contract import validate_spin
    ref = _reference()
    sub = _submitted()
    assert set(sub) == set(ref["pid"]), "exact pinned parcels required"
    report = json.loads((OUT / "results.json").read_text())
    geometry_path = Path(__file__).resolve().parent / "geometry_reference_v2.npz"
    assert geometry_path.exists(), "genuine pinned geometry v2 reference required"
    geometry = np.load(geometry_path, allow_pickle=False)
    evidence = np.load(OUT / "spin_evidence.npz", allow_pickle=False)
    pa = np.array([sub[i][0] for i in ref["pid"]])
    pb = np.array([sub[i][1] for i in ref["pid"]])
    validate_spin(pa, pb, evidence, report, geometry)

def test_findings_present():
    assert _findings().strip()
