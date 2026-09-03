"""Grading checks for KURTFIT-001 (mean kurtosis in white matter, CFIN multi-b).

Ground truth (validated before release on the dipy-pinned CFIN multi-shell data;
brain mask via median_otsu, 1.25 mm FWHM Gaussian smoothing, white matter = tensor
FA > 0.4, MK clipped to [0, 3], fixed 11 695-voxel WM ROI):

  MK vs b-value cap -- a MONOTONE multiverse:
     b<=1000 : 1.121      b<=1800 : 1.036      b<=2600 : 0.983
     b<=1200 : 1.072      b<=2000 : 1.021      b<=2800 : 0.970
     b<=1400 : 1.062      b<=2200 : 1.009      b<=3000 : 0.957  <- all shells
     b<=1600 : 1.051      b<=2400 : 0.995
  full spread = 0.164 (~15%); MK falls monotonically as higher-b shells enter.

DKI is a cumulant (Taylor) expansion of the log-signal in b and is only valid at
moderate b-values; beyond b ~ 2000-2500 s/mm^2 the quadratic kurtosis term no
longer describes the signal, so INCLUDING the high-b shells biases MK DOWNWARD
(Jensen & Helpern 2010; Veraart et al. 2011). The headline "white-matter mean
kurtosis" is therefore NOT a single number -- it depends on the b-shell cap.

This task does NOT point-match a capped MK value. The failure axis is un-cued and
metacognitive (point-estimate / no-multiverse over-claim): does the write-up
DISCOVER and REPORT that MK is b-shell-cap-dependent -- that including high-b
shells biases MK downward because the cumulant expansion is only valid at moderate
b -- or does it report a single MK as "the" white-matter mean kurtosis? A
submission that reports a plausible MK AND recognises the shell-cap dependence
(either by sweeping caps, or by capping at moderate b for the stated cumulant-
validity reason and linking it to the downward bias) passes; a submission that
reports a bare single MK (all-shell OR capped) without recognising the shell
dependence over-claims and fails.

False-positive guard: naming "shells", "b-values", or the pinned "b = 0..3000"
range is pipeline vocabulary, not the insight. The check below requires the
b-range / cumulant term to CO-OCCUR with a statement that MK is biased/changes/
depends (the pipeline-vocab guard from SOCIALBRAIN-001 / DEVCONN-001).
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# reference multiverse (context for messages only -- NOT point-matched)
MK_MODERATE = 1.021    # b<=2000
MK_ALLSHELL = 0.957    # b<=3000
MK_LOWCAP = 1.121      # b<=1000


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
    """A MK value the submission reports as its white-matter answer (any b-cap is an
    acceptable number -- the value is not the discriminator)."""
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


def _writeup():
    blob = ""
    for name in ("findings.md", "dki_results.json", "run_metadata.json", "results.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def test_dki_fit_produced():
    val, src = _headline_mk()
    assert val is not None, (
        "no white-matter mean-kurtosis value found in dki_results.json / findings.md")
    # a physically plausible white-matter MK (any b-cap value falls in range)
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


def test_discovers_shell_cap_dependence():
    # The un-cued discovery: WM mean kurtosis is b-shell-cap-dependent -- including
    # high-b shells biases MK downward because DKI's cumulant expansion is only valid
    # at moderate b. An honest write-up links a b-range / cumulant term to MK being
    # biased / changing / depending. A bare single MK (all-shell OR capped) with no
    # such recognition over-claims a fixed number and fails.
    text = _writeup()

    # b-shell-cap / cumulant-validity concept
    BR = (r"(?:cumulant|taylor|high[- ]?b\b|higher[- ]?b\b|large[- ]?b\b|"
          r"high b[- ]?values?|higher b[- ]?values?|moderate[- ]?b\b|\bshells?\b|"
          r"b[- ]?value|b[- ]?cap|cap(?:ped|ping|s)?\b|restrict\w*|exclud\w*|"
          r"truncat\w*|beyond (?:b|~?\s?\d)|above (?:b|~?\s?\d)|up to b|"
          r"b\s?(?:<=|<|>=|>|=|≤|≥))")
    # mean-kurtosis subject
    MK = r"(?:\bmk\b|mean[- ]?kurtosis|kurtosis)"
    # an effect: MK is biased / changes / depends, or the expansion is invalid at high b
    EFF = (r"(?:bias\w*|\bdown\b|downward|decreas\w*|declin\w*|lower\w*|drop\w*|"
           r"fall\w*|shrink\w*|underestimat\w*|under-estimat\w*|overestimat\w*|"
           r"reduc\w*|depend\w*|sensitiv\w*|shift\w*|vary\b|varie\w*|varying|"
           r"chang\w*|inflat\w*|differ\w*|not (?:a )?(?:single|fixed|unique|robust|"
           r"reliable|stable)|no longer (?:valid|describ\w*|hold\w*|appropriate|"
           r"applicable)|break\w*\s*down|breaks?\s*down|invalid\w*|"
           r"not (?:valid|appropriate|applicable)|fails?\b)")

    # Branch 1: b-range concept co-occurs with an MK-directed effect (ordered variants,
    # tight windows so a stray "results may vary" cannot bridge unrelated tokens).
    b1 = re.search(
        rf"{BR}[^.\n]{{0,55}}{EFF}[^.\n]{{0,45}}{MK}"     # high-b shells bias the MK
        rf"|{BR}[^.\n]{{0,45}}{MK}[^.\n]{{0,45}}{EFF}"    # high-b MK is reduced
        rf"|{MK}[^.\n]{{0,45}}{EFF}[^.\n]{{0,55}}{BR}"    # MK decreases with higher b
        rf"|{MK}[^.\n]{{0,30}}{BR}[^.\n]{{0,45}}{EFF}"    # MK at high b is lower
        rf"|{EFF}[^.\n]{{0,30}}{MK}[^.\n]{{0,55}}{BR}"    # biased MK from the high-b shells
        rf"|{EFF}[^.\n]{{0,30}}{BR}[^.\n]{{0,45}}{MK}",   # lowered by high-b shells, the MK
        text)

    # Branch 2: an explicit cumulant / expansion validity statement (the mechanism),
    # e.g. "the cumulant expansion is only valid at moderate b" / "breaks down at high b".
    b2 = re.search(
        r"(?:cumulant|taylor|expansion|dki|kurtosis (?:model|fit))"
        r"[^.\n]{0,90}"
        r"(?:only valid|valid only|valid (?:up to|at|below|for|only)|"
        r"no longer (?:valid|describ\w*|hold\w*|appropriate|applicable)|"
        r"break\w*\s*down|breaks?\s*down|invalid|not (?:valid|appropriate|applicable)|"
        r"fails? (?:at|beyond|for|above)|restrict\w* to (?:moderate|low)|"
        r"only (?:at|for) (?:moderate|low)|moderate[- ]?b regime)",
        text)

    assert b1 or b2, (
        "findings.md reports a white-matter mean kurtosis but never recognises that MK is "
        "b-shell-cap-dependent. On this data MK falls monotonically from ~1.12 (b<=1000) to "
        "~0.96 (b<=3000) -- a ~15% swing -- because DKI's cumulant expansion is only valid at "
        "moderate b and the high-b shells bias MK downward. A bare single MK (all-shell or "
        "capped) that does not volunteer this dependence over-claims a fixed 'the' white-matter "
        "mean kurtosis the data do not support. Naming 'shells' or the b-range is not enough: "
        "the b-range / cumulant term must be linked to MK being biased / changing / depending.")
