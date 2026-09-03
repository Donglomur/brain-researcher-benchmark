"""Grading checks for WMMD-001 (white-matter mean diffusivity, cfin multi-b).

Ground truth (validated before release on dipy's multi-b cfin_multib, b = 0..3000 s/mm^2;
WM ROI = brain-mask(median_otsu vol_idx=[0], radius=4, numpass=2, dilate=1) & low-b(b<=1000)
DTI FA > 0.5 = 10084 voxels; MD in 1e-3 mm^2/s = um^2/ms):

    DKI, all shells (correct)                 : md_mean = 0.883   <-- EXPECTED
    DTI, low-b (b<=1000) only  (also correct) : md_mean = 0.801
    DTI, ALL shells (NAIVE, biased)           : md_mean = 0.586   (0.30e-3 low; ~34%)
    DTI, ALL shells, OLS                       : md_mean = 0.502

The acquisition extends to b = 3000, where the DW signal departs from a single mono-
exponential decay. A plain single-tensor (Gaussian / mono-exponential DTI) fit over the
full b-range absorbs the high-b curvature into an artificially low apparent diffusivity,
so it UNDERESTIMATES MD by ~0.30e-3 (~34%). The kurtosis-tensor diffusion tensor (DKI,
the b->0 limit) recovers the unbiased value ~0.88e-3; restricting a plain tensor to
b<=1000 gives ~0.80e-3. The verifier matches the unbiased-diffusivity region within
tolerance; every DTI-over-all-shells answer (0.50-0.59) falls outside it.

The gap is robust to fit method (WLS/OLS) and light Gaussian smoothing.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED_MD = 0.883    # DKI (correct) mean diffusivity, 1e-3 mm^2/s
TOL_MD = 0.14          # accepts DKI (0.883) and low-b DTI (0.801); fails DTI-all (<=0.586)


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _norm_md(v):
    """Normalise a reported MD to um^2/ms (= 1e-3 mm^2/s), robust to common units:
    mm^2/s (~0.00088) -> x1000; um^2/s (~883) -> /1000; um^2/ms (~0.88) unchanged."""
    v = abs(float(v))
    if v == 0:
        return v
    for _ in range(6):
        if v < 0.05:          # mm^2/s -> um^2/ms
            v *= 1000.0
        elif v > 50.0:        # um^2/s -> um^2/ms
            v /= 1000.0
        else:
            break
    return v


def _find_md(obj):
    """Recursively find the reported mean diffusivity: a numeric leaf under a key that
    names diffusivity (md / diffusiv), excluding kurtosis/anisotropy keys, whose value
    normalises into the plausible brain-tissue MD range [0.1, 5] um^2/ms."""
    stack = [("", obj)]
    fallback = None
    while stack:
        key, cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.items())
        elif isinstance(cur, (list, tuple)):
            stack.extend(("", x) for x in cur)
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            k = key.lower()
            names_md = ("md" in re.split(r"[^a-z]+", k)) or ("diffusiv" in k) or \
                       ("mean_d" in k) or ("meandiff" in k)
            bad = any(b in k for b in ("kurt", "aniso", "anis", "_fa", "fa_", "frac"))
            if names_md and not bad:
                nv = _norm_md(cur)
                if 0.1 <= nv <= 5.0:
                    return nv
                if fallback is None:
                    fallback = nv
    return fallback


def _find_fa(obj):
    stack = [("", obj)]
    while stack:
        key, cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.items())
        elif isinstance(cur, (list, tuple)):
            stack.extend(("", x) for x in cur)
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            k = key.lower()
            if (("fa" in re.split(r"[^a-z]+", k)) or "aniso" in k) and "diff" not in k:
                if 0.0 <= float(cur) <= 1.0:
                    return float(cur)
    return None


def test_mean_diffusivity_reproduced():
    # The white-matter mean diffusivity, estimated with a model appropriate to this wide
    # multi-b acquisition, is ~0.88e-3 mm^2/s. A plain diffusion-tensor fit over ALL
    # shells is biased ~34% low (<=0.59e-3) and falls outside the tolerance.
    data = _load("diffusivity.json")
    md = _find_md(data)
    assert md is not None, f"no mean diffusivity found in diffusivity.json: {data}"
    assert abs(md - EXPECTED_MD) < TOL_MD, (
        f"mean diffusivity {md:.3f}e-3 mm^2/s does not match the unbiased value "
        f"{EXPECTED_MD:.3f} (tol {TOL_MD}). A mono-exponential tensor fit over the full "
        f"b-range underestimates MD (~0.50-0.59e-3); estimate it with a model valid at "
        f"high b (e.g. the diffusion-kurtosis tensor), or restrict a tensor fit to low b.")


def test_fa_reported_and_sane():
    # completeness: an FA for the same WM ROI is reported and physically plausible.
    fa = _find_fa(_load("diffusivity.json"))
    assert fa is not None, "no fractional anisotropy reported in diffusivity.json"
    assert 0.2 <= fa <= 0.95, f"white-matter mean FA {fa:.3f} is implausible"


def test_findings_report():
    # light honesty check: findings.md discusses diffusivity and reports a number
    # consistent with diffusivity.json.
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert "diffusiv" in text, "findings.md does not discuss diffusivity"
    md = _find_md(_load("diffusivity.json"))
    nums = [_norm_md(x) for x in re.findall(r"\d+\.\d+(?:[eE][+-]?\d+)?", text)]
    assert any(abs(n - md) < 0.05 for n in nums), (
        "findings.md does not report a mean diffusivity consistent with diffusivity.json")
