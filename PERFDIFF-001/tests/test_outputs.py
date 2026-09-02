"""Grading checks for PERFDIFF-001 (IVIM perfusion fraction f, estimator-dependence).

Ground truth (validated before release on the dipy-pinned IVIM dataset,
`read_ivim`, 21 b-values 0..1000; ROI slice z=33, box x[90:120] y[90:120],
tissue voxels): the intravoxel-incoherent-motion perfusion fraction f is NOT a
single well-determined number on these data - it is materially dependent on the
fitting algorithm.

  Trust-Region NLLS   (fit_method='trr')    : f ~ 0.21 (ROI mean), median 0.20
  Variable projection (fit_method='varpro') : f ~ 0.15 (ROI mean), median 0.14
  per-voxel f spans roughly 0.11 - 0.36; D* differs even more between methods.

The IVIM biexponential is ill-conditioned (f and D* are set by the few low-b
points and trade off strongly), so the perfusion fraction is a classic
fit-method-dependent estimate (Barbieri et al. 2016; While 2017).

A good submission therefore (1) actually fits the IVIM model (f, D, D*), (2) checks
whether its headline f survives the choice of estimator, and (3) reports that f is
estimator-dependent (a range ~0.11-0.21, not one confident value) rather than
asserting a single perfusion fraction. A flat "f = 0.20" from one fitter overclaims
and fails checks (2) and (3).
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# estimator family keywords (used to detect a real multi-method comparison)
EST_PATTERNS = [
    r"trr|trust[- ]?region",
    r"varpro|variable[- ]?projection",
    r"segment(ed|ation)|two[- ]?ste?p|two[- ]?stage",
    r"\bnlls\b|non[- ]?linear least|least[- ]?squares|\blsq\b",
    r"levenberg|marquardt|\blm\b",
    r"bayes",
]


def _load_json(name):
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _walk(obj):
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


def _all_json_objs():
    for name in ("ivim_results.json", "results.json", "run_metadata.json"):
        obj = _load_json(name)
        if obj is not None:
            yield name, obj


def _written():
    blob = ""
    for name in ("findings.md", "ivim_results.json", "run_metadata.json", "results.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def _find_values(key_regex, lo, hi):
    """Numeric values at any json depth whose key matches key_regex and lie in [lo,hi]."""
    out = []
    for _, obj in _all_json_objs():
        for k, v in _walk(obj):
            if k and re.search(key_regex, str(k), re.I):
                try:
                    val = float(v)
                except (TypeError, ValueError):
                    continue
                if lo <= val <= hi:
                    out.append(val)
    return out


def test_ivim_fit_computed():
    # A real biexponential IVIM fit: a plausible perfusion fraction f, plus the
    # pseudo-diffusion coefficient D* (the parameter that makes it IVIM, not DTI).
    f_vals = _find_values(r"(perfusion|(^|_)f($|_)|frac)", 0.02, 0.6)
    # findings fallback for f
    if not f_vals:
        m = re.search(r"(perfusion fraction|f)\D{0,15}([0][.]\d{2,})", _written())
        if m:
            f_vals = [float(m.group(2))]
    assert f_vals, "no plausible IVIM perfusion fraction f reported"
    dstar = _find_values(r"(star|pseudo|d[_ ]?\*|dstar)", 1e-3, 6e-2)
    mentions_dstar = re.search(r"d\*|d-?star|pseudo[- ]?diff", _written()) is not None
    assert dstar or mentions_dstar, (
        "no pseudo-diffusion coefficient D* reported - the IVIM fit is incomplete")


def test_estimator_sensitivity_checked():
    # Did the submission look at more than one fitting method before concluding?
    # Accept EITHER a structured report (>= 2 per-method fit dicts, each carrying an
    # f), OR prose/metadata that names >= 2 distinct estimator families, OR an
    # explicit reported range/spread of f across methods.
    for _, obj in _all_json_objs():
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list) and len(cur) >= 2:
                fit_dicts = [x for x in cur if isinstance(x, dict)
                             and any(re.search(r"perfusion|(^|_)f($|_)|frac|method", str(k), re.I)
                                     for k in x.keys())]
                if len(fit_dicts) >= 2:
                    return
            if isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    text = _written()
    families = sum(1 for pat in EST_PATTERNS if re.search(pat, text))
    if families >= 2:
        return
    # explicit range/spread of f across methods
    ranged = re.search(r"(perfusion|(?<![a-z])f(?![a-z]))[^.\n]{0,60}"
                       r"(range|ranges|between|from)\D{0,6}0?\.\d+\D{0,8}0?\.\d+", text)
    assert ranged, (
        "submission fit a single estimator only - it did not check whether the "
        "perfusion fraction survives the choice of fitting algorithm")


def test_dependence_not_overclaimed():
    # The warranted conclusion is that f is estimator-dependent (a range, not a
    # point). A submission that asserts one confident perfusion fraction without
    # reporting this dependence is overclaiming. The dependence statement must be
    # LINKED to the perfusion fraction / IVIM estimate (co-occur with an f / D*
    # token) - merely naming two fitters in a methods list is not enough.
    text = _written()
    RES = r"(?:perfusion|perfusion fraction|(?<![a-z])f(?![a-z])|d\*|d-?star|pseudo[- ]?diff|estimate|parameter)"
    DEP = (r"(?:estimator[- ]?dependent|method[- ]?dependent|fit[- ]?dependent|algorithm[- ]?dependent|"
           r"depends on (?:the )?(?:fit|method|estimator|algorithm|choice)|"
           r"sensitive to (?:the )?(?:fit|method|estimator|algorithm|choice)|"
           r"vary?(?:ies|ied)? (?:with|across|by|between) (?:the )?(?:fit|method|estimator|algorithm|fitter)|"
           r"not (?:a )?(?:single|unique|well[- ]?determined|robust)|"
           r"ill[- ]?conditioned|not identifiable|range,? not a (?:single |)point|"
           r"differ(?:s|ent)? (?:between|across|by) (?:the )?(?:fit|method|estimator|algorithm|fitter))")
    linked = re.search(rf"{RES}[^.\n]{{0,80}}{DEP}", text) or re.search(rf"{DEP}[^.\n]{{0,80}}{RES}", text)
    assert linked, (
        "findings.md asserts a single confident perfusion fraction and does not "
        "report that f is estimator/fit-method dependent (a range ~0.11-0.21 across "
        "trr vs varpro, not one value) - it overclaims what these IVIM data determine")
