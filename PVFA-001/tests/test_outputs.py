"""Grading checks for PVFA-001 (fractional anisotropy of periventricular white
matter, dipy Sherbrooke 3-shell).

Ground truth (validated before release on the dipy-pinned Sherbrooke 3-shell data;
brain mask via median_otsu, 1.25 mm FWHM Gaussian smoothing, a periventricular
region grown from a CSF seed, model estimation on b <= 2000, 1740 voxels):

  free-water-accounted (fwDTI) tissue FA : 0.617   <- correct
  single-tensor DTI FA (b <= 2000)       : 0.527   <- naive (CSF-deflated)
  single-tensor DTI FA (b <= 1000)       : 0.427   <- naive (standard DTI)

Periventricular white matter borders the ventricles and is heavily contaminated by
cerebrospinal fluid partial volume. A single diffusion tensor conflates the fast,
isotropic CSF signal with the tissue, deflating the apparent FA; modelling an
explicit free-water compartment (Pasternak et al. 2009; Hoy et al. 2014) recovers
the tissue FA. The correct fit reports ~0.62; a naive single-tensor fit (~0.53 or
~0.43) does not match. The reference reports the free-water-accounted FA.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# reference (free-water-accounted) FA and grading tolerance
EXPECTED_FA = 0.615
TOL = 0.04
# the naive single-tensor values must NOT be accepted
NAIVE_FA_B2000 = 0.527
NAIVE_FA_B1000 = 0.427

# keys that name the headline answer (normalised: lowercased, spaces/underscores kept)
_ANSWER_KEYS = {
    "fa_periventricular_wm", "fa_periventricular", "periventricular_fa",
    "fa_pv_wm", "fa_pv", "pv_fa", "pvfa", "fa_wm", "wm_fa", "mean_fa_wm",
    "mean_fa", "fa_mean", "fractional_anisotropy", "fa",
}
# never read the naive / context / uncorrected number as the headline answer
_EXCLUDE = ("context", "single_tensor", "singletensor", "uncorrected",
            "naive", "dti", "raw", "conventional", "unc")


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


def _norm(k):
    return str(k).lower().replace(" ", "_").replace("-", "_")


def _headline_fa():
    """The FA value the submission reports as its periventricular-WM answer.

    Preference: an explicit answer field (fa_periventricular_wm, fa_wm, ...) whose
    value is a plausible FA; else a labelled number in findings.md. Keys that name
    the naive / single-tensor / uncorrected value are deliberately skipped so we
    grade the number the submission puts forward as its result.
    """
    for name in ("results.json", "dti_results.json", "run_metadata.json"):
        obj = _load_json(name)
        if not obj:
            continue
        for k, v in _walk(obj):
            if not k:
                continue
            nk = _norm(k)
            if any(bad in nk for bad in _EXCLUDE):
                continue
            if nk in _ANSWER_KEYS:
                try:
                    val = float(v)
                except (TypeError, ValueError):
                    continue
                if 0.1 <= val <= 0.95:  # a plausible FA, not a count / fraction label
                    return val, k
    # fall back to findings.md: a number near an FA mention
    fp = OUT / "findings.md"
    if fp.exists():
        text = fp.read_text(encoding="utf-8")
        for m in re.finditer(r"(fractional[- ]?anisotropy|\bFA\b)[^\n]{0,40}?(0?\.\d{2,})", text, re.I):
            try:
                return float(m.group(2)), "findings.md"
            except ValueError:
                continue
        for m in re.finditer(r"(0?\.\d{2,})[^\n]{0,20}?(fractional[- ]?anisotropy|\bFA\b)", text, re.I):
            try:
                return float(m.group(1)), "findings.md"
            except ValueError:
                continue
    return None, None


def test_fa_produced():
    val, src = _headline_fa()
    assert val is not None, (
        "no periventricular white-matter FA value found in results.json / findings.md")
    # a physically plausible white-matter FA
    assert 0.2 <= val <= 0.9, f"reported periventricular WM FA {val} is out of physical range"


def test_periventricular_roi_reported():
    # a real region average was taken over a sensible number of voxels
    obj = _load_json("results.json") or _load_json("run_metadata.json") or {}
    n_roi = None
    for k, v in _walk(obj):
        if k and "roi" in _norm(k) and ("vox" in _norm(k) or "n_" in _norm(k)):
            try:
                n_roi = int(v)
            except (TypeError, ValueError):
                pass
    findings = (OUT / "findings.md")
    mentions = findings.exists() and re.search(
        r"periventricular|white[- ]?matter|\bwm\b|ventric", findings.read_text(encoding="utf-8"), re.I)
    assert (n_roi is not None and n_roi >= 300) or mentions, (
        "submission does not report a periventricular white-matter region "
        "(voxel count or region definition)")


def test_fa_matches_free_water_reference():
    # The headline FA must reproduce the free-water-accounted reference (~0.62).
    # A single-tensor DTI fit (which conflates CSF partial volume with tissue)
    # yields ~0.53 (b<=2000) or ~0.43 (b<=1000) and must NOT be accepted.
    val, src = _headline_fa()
    assert val is not None, "no periventricular WM FA value to grade"
    assert abs(val - EXPECTED_FA) < TOL, (
        f"reported periventricular WM FA {val:.3f} (from {src}) does not match the "
        f"free-water-accounted reference {EXPECTED_FA:.3f} +/- {TOL} -- a single-tensor "
        f"fit (~{NAIVE_FA_B2000} at b<=2000, ~{NAIVE_FA_B1000} at b<=1000) reports a "
        f"CSF-deflated FA because periventricular white matter is contaminated by "
        f"cerebrospinal-fluid partial volume")
    # guard: the naive single-tensor values are genuinely outside tolerance
    assert abs(NAIVE_FA_B2000 - EXPECTED_FA) >= TOL
    assert abs(NAIVE_FA_B1000 - EXPECTED_FA) >= TOL
