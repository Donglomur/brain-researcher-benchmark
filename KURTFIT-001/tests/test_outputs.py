"""Grading checks for KURTFIT-001 (mean kurtosis in white matter, CFIN multi-b).

Ground truth (validated before release on the dipy-pinned CFIN multi-shell data;
brain mask via median_otsu, 1.25 mm FWHM Gaussian smoothing, white matter = tensor
FA > 0.4, MK clipped to [0, 3], whole brain):

  MK in WM, DKI fit CAPPED at b <= 2000 s/mm^2 : 1.021   <- correct
  MK in WM, DKI fit over ALL shells (b<=3000)  : 0.957   <- naive (high-b bias)

DKI is a cumulant (Taylor) expansion of the log-signal in b and is only valid at
moderate b-values; beyond b ~ 2000-2500 s/mm^2 the quadratic kurtosis term no
longer describes the signal, so including the b = 2200..3000 shells biases MK
downward (Jensen & Helpern 2010; Veraart et al. 2011). The correct fit restricts
to moderate b; the value that reproduces is ~1.02, and an all-shell fit (~0.96)
does not match. The reference reports the moderate-b MK.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# reference (moderate-b) MK in WM and grading tolerance
EXPECTED_MK = 1.021
TOL = 0.035
# the all-shell (naive) value must NOT be accepted
NAIVE_MK = 0.957


def _load_json(name):
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _walk(obj):
    """Yield every (key, value) pair at any depth of a nested json object."""
    stack = [(None, obj)]
    while stack:
        k, v = stack.pop()
        if isinstance(v, dict):
            for kk, vv in v.items():
                stack.append((kk, vv))
        elif isinstance(v, list):
            for vv in v:
                stack.append((k, vv))
        else:
            yield k, v


def _headline_mk():
    """The MK value the submission reports as its white-matter answer.

    Preference order: an explicit mean_kurtosis_wm field; else any numeric field
    whose key names mean-kurtosis in white matter; else a labelled number in
    findings.md. We deliberately pick the WM-MK the submission puts forward as its
    result, not any incidental number.
    """
    for name in ("dki_results.json", "results.json", "run_metadata.json"):
        obj = _load_json(name)
        if not obj:
            continue
        for k, v in _walk(obj):
            if k and str(k).lower().replace(" ", "") in (
                    "mean_kurtosis_wm", "meankurtosiswm", "mk_wm", "mkwm",
                    "wm_mk", "wmmk", "mean_kurtosis", "meankurtosis", "mk"):
                try:
                    val = float(v)
                    if 0.2 <= val <= 2.0:  # a plausible MK, not a b-value or count
                        return val, k
                except (TypeError, ValueError):
                    continue
    # fall back to findings.md: a number near an MK / mean-kurtosis mention
    fp = OUT / "findings.md"
    if fp.exists():
        text = fp.read_text(encoding="utf-8")
        for m in re.finditer(r"(mean[- ]?kurtosis|\bMK\b)[^\n]{0,40}?([01]\.\d{2,})", text, re.I):
            try:
                return float(m.group(2)), "findings.md"
            except ValueError:
                continue
        for m in re.finditer(r"([01]\.\d{2,})[^\n]{0,20}?(mean[- ]?kurtosis|\bMK\b)", text, re.I):
            try:
                return float(m.group(1)), "findings.md"
            except ValueError:
                continue
    return None, None


def test_dki_fit_produced():
    val, src = _headline_mk()
    assert val is not None, (
        "no white-matter mean-kurtosis value found in dki_results.json / findings.md")
    # a physically plausible white-matter MK
    assert 0.5 <= val <= 1.8, f"reported WM mean kurtosis {val} is out of physical range"


def test_white_matter_roi_reported():
    # a real WM average was taken over a sensible number of voxels
    obj = _load_json("dki_results.json") or _load_json("run_metadata.json") or {}
    n_wm = None
    for k, v in _walk(obj):
        if k and "wm" in str(k).lower() and ("vox" in str(k).lower() or "n_" in str(k).lower()):
            try:
                n_wm = int(v)
            except (TypeError, ValueError):
                pass
    findings = (OUT / "findings.md")
    mentions_wm = findings.exists() and re.search(
        r"white[- ]?matter|\bwm\b|\bFA\b", findings.read_text(encoding="utf-8"), re.I)
    assert (n_wm is not None and n_wm >= 500) or mentions_wm, (
        "submission does not report a white-matter ROI (voxel count or FA-based WM definition)")


def test_mk_matches_moderate_b_reference():
    # The headline WM mean kurtosis must reproduce the moderate-b reference (~1.02).
    # An all-shell DKI fit (which includes b = 2200..3000, where the cumulant
    # expansion is invalid) yields ~0.96 and must NOT be accepted.
    val, src = _headline_mk()
    assert val is not None, "no WM mean-kurtosis value to grade"
    assert abs(val - EXPECTED_MK) < TOL, (
        f"reported WM mean kurtosis {val:.3f} (from {src}) does not match the "
        f"moderate-b reference {EXPECTED_MK:.3f} +/- {TOL} -- an all-shell fit "
        f"(~{NAIVE_MK}) biases MK downward because DKI's cumulant expansion is "
        f"only valid at moderate b (<= ~2000-2500 s/mm^2)")
    # guard: the naive all-shell value is genuinely outside tolerance
    assert abs(NAIVE_MK - EXPECTED_MK) >= TOL
