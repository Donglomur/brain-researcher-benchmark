"""Grading checks for PETDVR-001.

Ground truth (established in Step-0 on the PETPrep-derived regional TACs of OpenNeuro
ds001420, [11C]DASB test-retest, 2 participants x test/retest, using the dataset's
pre-computed `reference` region):

  High-binding SERT territory DVR from the Logan reference-tissue graphical plot, taking
  the slope over the LINEAR segment (t* ~ 20-35 min, at transient equilibrium):
    sub-01 base 2.681   sub-01 rescan 3.169   sub-02 base 2.886   sub-02 rescan 3.078
    mean 2.953.  Ichise MA1 over the same segment agrees to ~1 %; the SRTM binding
    potential + 1 lands in the same place (~2.9), so the target number is not method-
    specific -- it is what any equilibrium-aware analysis returns.
  Regional means: highbinding 2.95, thalamus 2.37, caudate 1.97, putamen 2.50.

The shortcut this rules out: regressing the Logan plot over ALL frames from t = 0 (the
early distribution phase is still curved) drags the slope DOWN to a high-binding DVR of
~2.35 -- a ~20 % under-estimate that recurs on every scan -- EVEN THOUGH that all-frames
fit still has R^2 ~ 0.99. So a fit that looks statistically excellent is biased, and the
discriminator is whether the early, non-equilibrium frames were excluded, not the fit
quality. A naive all-frames Logan DVR (~2.35) fails; an equilibrium-aware DVR (~2.95)
passes.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# high-binding DVR: equilibrium-aware ~2.95 (per-scan 2.68-3.17); naive all-frames ~2.35.
HB_LO, HB_HI = 2.60, 3.40
# supporting regional bands (equilibrium-aware vs naive): thalamus 2.37/1.81, caudate 1.97/1.30
THAL_LO = 2.05   # naive ~1.81
CAUD_LO = 1.60   # naive ~1.30


def _rows():
    p = OUT / "dvr_estimates.csv"
    if not p.exists():
        return []
    try:
        return list(csv.DictReader(open(p, encoding="utf-8")))
    except Exception:
        return []


def _dvr_col(hdr):
    """Find the DVR column, tolerating name variation but excluding cross-check columns."""
    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())
    cands = []
    for c in hdr:
        n = norm(c)
        if "ma1" in n or "mrtm" in n or "srtm" in n or "bp" in n or "tstar" in n:
            continue
        if n == "dvr" or n.startswith("dvr") or "dvr" in n or n in ("slope", "ratio"):
            cands.append(c)
    return cands[0] if cands else None


def _region_values(region_substrings):
    """DVR values from dvr_estimates.csv whose target matches any given substring."""
    rows = _rows()
    if not rows:
        return []
    hdr = list(rows[0].keys())
    col = _dvr_col(hdr)
    tcol = None
    for c in hdr:
        if re.sub(r"[^a-z]", "", c.lower()) in ("target", "region", "roi", "targetregion"):
            tcol = c
            break
    if col is None or tcol is None:
        return []
    out = []
    for r in rows:
        tg = re.sub(r"[^a-z]", "", str(r.get(tcol, "")).lower())
        if any(s in tg for s in region_substrings):
            try:
                out.append(float(r[col]))
            except (TypeError, ValueError):
                continue
    return out


def _meta():
    p = OUT / "run_metadata.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _find_numbers(obj, key_substr):
    """Recursively collect floats stored under any key containing key_substr."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if key_substr in str(k).lower() and isinstance(v, (int, float)) and not isinstance(v, bool):
                found.append(float(v))
            if key_substr in str(k).lower() and isinstance(v, list):
                found += [float(x) for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
            found += _find_numbers(v, key_substr)
    elif isinstance(obj, list):
        for v in obj:
            found += _find_numbers(v, key_substr)
    return found


def _highbinding_values():
    """Per-scan high-binding DVR, from the CSV first, else from run_metadata.json."""
    vals = _region_values(["highbinding", "highbind"])
    if len(vals) >= 3:
        return vals
    meta = _meta()
    m = _find_numbers(meta, "highbinding_dvr_per_scan") or _find_numbers(meta, "highbinding")
    return m


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def test_dvr_estimates_present():
    vals = _highbinding_values()
    assert len(vals) >= 4, f"expected a high-binding DVR for all four scans, got {vals}"
    assert all(1.0 <= v <= 5.0 for v in vals[:4]), \
        f"high-binding [11C]DASB DVR outside a plausible range: {vals[:4]}"
    # A reference-tissue graphical (Logan/MA1) analysis must actually have been done.
    txt = _text()
    if (OUT / "dvr_estimates.csv").exists():
        txt += "\n" + (OUT / "dvr_estimates.csv").read_text(encoding="utf-8").lower()
    assert re.search(r"logan|graphical|ma1|ichise|distribution volume ratio|\bdvr\b", txt), \
        "no reference-tissue graphical (Logan/MA1) DVR analysis is named anywhere"


def test_reproduces_highbinding_dvr():
    import statistics
    vals = _highbinding_values()[:4]
    mean = statistics.fmean(vals)
    # Equilibrium-aware Logan/MA1 DVR sits at ~2.95 (2.68-3.17 across scans). Regressing
    # the whole plot from t=0 (early frames not yet linear) collapses it to ~2.35. The band
    # accepts any equilibrium-aware estimate and rejects the all-frames under-estimate.
    assert HB_LO <= mean <= HB_HI, (
        f"mean high-binding DVR {mean:.3f} is outside the equilibrium-aware band "
        f"[{HB_LO}, {HB_HI}]. A value near ~2.35 means the Logan slope was fit over all "
        f"frames including the early, pre-equilibrium (curved) phase, which biases DVR low "
        f"by ~20 % even though the overall fit R^2 is ~0.99; take the slope over the linear "
        f"segment only.")


def test_regional_profile_not_underestimated():
    # A second, independent guard on the same failure: the early-frame bias drags DOWN
    # every high-binding region. If the reported thalamus and caudate DVRs are also at
    # their equilibrium-aware levels (not the ~1.8 / ~1.3 all-frames values), the whole
    # profile is consistent with a linear-segment fit. Only enforced if the region was
    # reported (the profile is requested but a submission may name regions differently).
    thal = _region_values(["thalamus", "thalamic"])
    caud = _region_values(["caudate"])
    import statistics
    if len(thal) >= 4:
        m = statistics.fmean(thal[:4])
        assert m >= THAL_LO, (
            f"mean thalamus DVR {m:.3f} is at the all-frames (~1.81) level, not the "
            f"equilibrium-aware (~2.37) level -- the early, non-linear frames were not excluded")
    if len(caud) >= 4:
        m = statistics.fmean(caud[:4])
        assert m >= CAUD_LO, (
            f"mean caudate DVR {m:.3f} is at the all-frames (~1.30) level, not the "
            f"equilibrium-aware (~1.97) level -- the early, non-linear frames were not excluded")


def test_fit_window_justified():
    # The un-cued judgement: the Logan/MA1 DVR is the slope of the LINEAR segment, so the
    # write-up must treat the start of the linear phase (transient equilibrium) as a
    # considered choice -- name the fit window / equilibrium onset / excluded early frames,
    # or state that the estimate depends on it -- not merely "fit the Logan plot". This is
    # the same false-positive class the shipped PET/rs-fMRI tasks guard against (naming a
    # pipeline step is not the same as justifying the analytic choice). We require the
    # window concept to co-occur with an actual result, not appear as a bare keyword.
    text = _text()
    window = re.search(
        r"linear (segment|phase|portion|part|region)|equilibrium|steady[- ]?state"
        r"|\bt\s*\*|\btstar\b|t-?star|fit window|fitting window|start (time|frame)"
        r"|exclud\w+[^.\n]{0,40}(early|initial|first|pre)|(early|initial|first)[^.\n]{0,40}(exclud|drop|discard|omit|remov)"
        r"|late[- ]?time|after[^.\n]{0,20}(min|equilibr)", text)
    has_result = re.search(r"dvr|distribution volume ratio|slope|\bmin\b|\d\.\d", text)
    assert window and has_result, (
        "findings/run_metadata do not justify the Logan/MA1 fit window as a considered "
        "choice. A reference-tissue graphical DVR is the slope of the LINEAR segment (after "
        "transient equilibrium); the report must say where the linear phase starts / that "
        "early frames were excluded / that the estimate depends on the fit window -- "
        "regressing the whole plot from t=0 gives a fit with R^2 ~ 0.99 that is still "
        "biased ~20 % low.")
