"""Reusable proof-of-work helpers for HIPPOTHETA-001 (see PROOF_OF_WORK_SPEC.md).

Single-value task (one theta peak frequency). A lone scalar is guessable, so the grader also
validates the finest NEUTRAL intermediate the analysis produces -- the power spectrum the peak is
read from (any spectral analysis, naive or honest, produces one) -- against a held-out reference
(tests/reference.npz). The reference spectrum is the honest movement-conditioned spectrum. Its
5-11 Hz shape correlates ~0.90-1.0 across hippocampal channels but only ~0.14 with the
whole-recording spectrum, so a shape-match cleanly separates the honest locomotion estimate
(~9 Hz) from the naive whole-recording estimate (~7.9 Hz, dragged down by REM/immobility slow
theta) and from a fabricated bump.
"""
import csv, json, math, re, statistics
from pathlib import Path
import numpy as np


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    out = {
        "freq": np.asarray(z["ref_freq"], dtype=float),
        "pow": np.asarray(z["ref_pow"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    if "ref_freq_full" in z.files:
        out["freq_full"] = np.asarray(z["ref_freq_full"], dtype=float)
        out["pow_full"] = np.asarray(z["ref_pow_full"], dtype=float)
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_submitted_spectrum(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return None, None
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, avoid=()):
        for c in cands:
            if c in norm_to_raw:
                return norm_to_raw[c]
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(x in nrm for x in avoid):
                return raw
        return None

    fcol = pick(("frequencyhz", "frequency", "freq", "hz", "f"), avoid=("power", "psd"))
    pcol = pick(("power", "psd", "spectraldensity", "spectrum", "welch", "amplitude", "p"),
                avoid=("freq", "hz"))
    if fcol is None or pcol is None or fcol == pcol:
        return None, None
    fs, ps = [], []
    for r in rows:
        try:
            f = float(r.get(fcol)); p = float(r.get(pcol))
        except (TypeError, ValueError):
            continue
        if math.isfinite(f) and math.isfinite(p):
            fs.append(f); ps.append(p)
    if len(fs) < 5:
        return None, None
    order = np.argsort(fs)
    return np.asarray(fs)[order], np.asarray(ps)[order]


def band_peak(freq, power, band=(6.0, 10.0)):
    m = (freq >= band[0]) & (freq <= band[1])
    if m.sum() < 2:
        return float("nan")
    fb, pb = freq[m], power[m]
    k = int(np.argmax(pb))
    if 0 < k < len(pb) - 1:
        y0, y1, y2 = pb[k - 1], pb[k], pb[k + 1]
        den = (y0 - 2 * y1 + y2)
        d = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        step = fb[1] - fb[0]
        return float(fb[k] + d * step)
    return float(fb[k])


def check_spectrum_matches_reference(freq, power, ref, band_corr_min=0.88, broadband_min=0.30,
                                     search=(5.0, 11.0), theta=(6.0, 10.0), peak_tol=0.7):
    """Pillar 1. The submitted spectrum must BE the real movement-conditioned spectrum: it is
    non-constant, broadband (a real LFP spectrum has substantial off-peak power, not a narrow
    synthetic bump), its 5-11 Hz shape (interpolated onto the reference grid) correlates with the
    held-out reference, and its 6-10 Hz peak sits at the reference locomotion peak (~9 Hz), not
    the whole-recording peak (~7.9 Hz)."""
    assert freq is not None and power is not None and len(freq) >= 5, (
        "spectrum.csv could not be parsed into a (frequency, power) power spectrum")
    rf = ref["freq"]
    lo = max(search[0], float(freq.min()), float(rf.min()))
    hi = min(search[1], float(freq.max()), float(rf.max()))
    assert hi - lo >= 3.0, (
        f"submitted spectrum does not span the theta search band {search}; only [{lo:.1f},{hi:.1f}]")
    grid = rf[(rf >= lo) & (rf <= hi)]
    sub = np.interp(grid, freq, power)
    refb = np.interp(grid, rf, ref["pow"])
    assert statistics.pstdev(sub.tolist()) > 1e-12, (
        "submitted spectrum is constant across the theta band -- not a real power spectrum")
    # broadband guard: a real LFP theta spectrum has substantial power away from the peak; a narrow
    # fabricated gaussian bump concentrates all power at the peak.
    sub_pos = sub - min(0.0, float(np.min(sub)))
    peakp = float(np.max(sub_pos))
    broadband = float(np.median(sub_pos)) / peakp if peakp > 0 else 0.0
    assert broadband >= broadband_min, (
        f"the submitted spectrum is a narrow bump (median/peak power {broadband:.2f} < "
        f"{broadband_min}); a real CA1 LFP theta spectrum has broadband 1/f power around the peak, "
        f"not an isolated synthetic peak")
    if np.std(sub) == 0 or np.std(refb) == 0:
        corr = float("nan")
    else:
        corr = float(np.corrcoef(sub, refb)[0, 1])
    assert math.isfinite(corr) and corr >= band_corr_min, (
        f"the submitted spectrum's theta-band shape does not track the held-out movement-"
        f"conditioned reference (band r={corr:.2f} < {band_corr_min}). A whole-recording spectrum "
        f"(dominated by slow REM/immobility theta) or a fabricated bump does not match it.")
    sub_peak = band_peak(freq, power, theta)
    ref_peak = float(ref["stats"]["loco_peak"])
    assert math.isfinite(sub_peak) and abs(sub_peak - ref_peak) <= peak_tol, (
        f"the peak of the submitted 6-10 Hz spectrum ({sub_peak:.2f} Hz) is not at the honest "
        f"movement-related theta peak (~{ref_peak:.2f} Hz); a whole-recording estimate peaks ~7.9 Hz")
    return corr, sub_peak


def broadband_landmarks(freq, power, theta=(6.0, 10.0)):
    """1/f-background landmarks of a real CA1 LFP spectrum. Returns (p_low, p_peak, p_high,
    r_low = P(3 Hz)/P(theta peak), r_high = P(theta peak)/P(35 Hz)). A lone bump on a flat/near-
    zero background has ~no power at 3 Hz and 35 Hz, so r_low collapses toward 0 and r_high blows
    up with tiny denominators -- it cannot reproduce the real, ordered 1/f falloff around theta."""
    def at(t):
        i = int(np.argmin(np.abs(freq - t)))
        return float(max(power[i], 0.0))
    tm = (freq >= theta[0]) & (freq <= theta[1])
    p_peak = float(np.max(power[tm])) if tm.any() else float("nan")
    p_low = at(3.0)
    p_high = at(35.0)
    r_low = (p_low / p_peak) if p_peak > 0 else 0.0
    r_high = (p_peak / p_high) if p_high > 0 else float("inf")
    return p_low, p_peak, p_high, r_low, r_high


def theta_half_width(freq, power, theta=(6.0, 10.0)):
    """Half-width (Hz) of the theta peak above the aperiodic (1/f) background, plus the theta
    residual-peak frequency and the log-log 1/f slope. The 1/f trend is fit on log-log power
    excluding the theta (6-11 Hz) and theta-harmonic (14-20 Hz) bands; the theta peak's FWHM is
    measured on the flattened residual. This bandwidth is a data-specific feature a guessed bump
    of arbitrary width does not match."""
    freq = np.asarray(freq, float)
    power = np.asarray(power, float)
    logf = np.log10(np.maximum(freq, 1e-9))
    logp = np.log10(np.maximum(power, 1e-12))
    excl = ((freq >= 6) & (freq <= 11)) | ((freq >= 14) & (freq <= 20))
    if (~excl).sum() < 5:
        return float("nan"), float("nan"), float("nan")
    A = np.polyfit(logf[~excl], logp[~excl], 1)
    res = logp - np.polyval(A, logf)
    tm = (freq >= theta[0]) & (freq <= theta[1])
    if not tm.any():
        return float("nan"), float("nan"), float(A[0])
    idxs = np.where(tm)[0]
    k = int(idxs[int(np.argmax(res[idxs]))])
    hpk = res[k]
    half = hpk / 2.0
    lo = k
    while lo > 0 and res[lo] >= half:
        lo -= 1
    hi = k
    while hi < len(res) - 1 and res[hi] >= half:
        hi += 1
    return float(freq[k]), float(freq[hi] - freq[lo]), float(A[0])


def broadband_logcorr(freq, power, ref_freq, ref_pow, bb=(2.0, 45.0), min_span=18.0):
    """Pearson corr of log10-power vs the held-out reference on a shared broadband grid.
    Returns (corr, lo, hi, span). Log space so the 1/f background + theta bump + harmonic all
    contribute; a lone bump (flat elsewhere) has a very different broadband log-shape."""
    freq = np.asarray(freq, float)
    power = np.asarray(power, float)
    lo = max(bb[0], float(freq.min()), float(ref_freq.min()))
    hi = min(bb[1], float(freq.max()), float(ref_freq.max()))
    span = hi - lo
    if span < min_span:
        return float("nan"), lo, hi, span
    grid = ref_freq[(ref_freq >= lo) & (ref_freq <= hi)]
    if len(grid) < 10:
        return float("nan"), lo, hi, span
    sub = np.log10(np.maximum(np.interp(grid, freq, power), 1e-12))
    ref = np.log10(np.maximum(np.interp(grid, ref_freq, ref_pow), 1e-12))
    if np.std(sub) < 1e-9 or np.std(ref) < 1e-9:
        return float("nan"), lo, hi, span
    return float(np.corrcoef(sub, ref)[0, 1]), lo, hi, span


def check_broadband_structure(freq, power, ref, corr_min=0.9, low_min=0.9, high_min=10.0,
                              high_max=150.0, hw_lo=1.0, hw_hi=6.5, bb=(2.0, 45.0), min_span=18.0):
    """Pillar (anti-fabrication): the submitted spectrum must carry the real BROADBAND CA1 LFP
    structure -- a 1/f background with the theta peak riding on it and a high-frequency noise
    floor -- not a synthetic peak. A lone bump on a flat background fails every clause below.

      * broadband coverage: the spectrum must span ~2-45 Hz (not just the theta window);
      * broadband shape: log10-power tracks the held-out movement-conditioned reference over
        2-45 Hz (Pearson corr >= corr_min);
      * 1/f landmarks: P(3 Hz)/P(theta peak) >= low_min (substantial low-frequency power -- a bump
        has ~none) AND high_min <= P(theta peak)/P(35 Hz) <= high_max (a real, bounded falloff --
        a bump / pure power law without a noise floor gives a runaway ratio);
      * theta bandwidth: the theta peak's half-width above the 1/f background is in [hw_lo, hw_hi].
    """
    freq = np.asarray(freq, float)
    power = np.asarray(power, float)
    assert freq is not None and len(freq) >= 10, "spectrum.csv is too short to be a real spectrum"
    m = (freq >= bb[0]) & (freq <= bb[1])
    fb, pb = freq[m], power[m]
    span = (float(fb.max()) - float(fb.min())) if len(fb) else 0.0
    assert len(fb) >= 10 and span >= min_span, (
        f"spectrum.csv covers only [{fb.min() if len(fb) else float('nan'):.1f},"
        f"{fb.max() if len(fb) else float('nan'):.1f}] Hz; report the BROADBAND power spectrum "
        f"(about {bb[0]:.0f}-{bb[1]:.0f} Hz) so the 1/f background around the theta peak is present, "
        f"not just the narrow theta window")
    rff = ref.get("freq_full")
    rpf = ref.get("pow_full")
    assert rff is not None, "reference lacks a broadband spectrum"
    corr, lo, hi, cspan = broadband_logcorr(fb, pb, rff, rpf, bb=bb, min_span=min_span)
    assert math.isfinite(corr) and corr >= corr_min, (
        f"the submitted spectrum's broadband (2-45 Hz) log-power shape does not match the held-out "
        f"CA1 LFP reference (r={corr:.2f} < {corr_min}). A synthetic peak on a flat background, or a "
        f"spectrum lacking the real 1/f background, does not track it.")
    p3, ppk, p35, r_low, r_high = broadband_landmarks(fb, pb)
    assert ppk > 0, "no theta-band power in the submitted spectrum"
    assert r_low >= low_min, (
        f"the submitted spectrum has too little low-frequency (1/f) power: P(3 Hz)/P(peak)="
        f"{r_low:.2f} < {low_min}. A real CA1 LFP spectrum has substantial power at 3 Hz "
        f"(comparable to the theta peak); an isolated theta bump does not.")
    assert high_min <= r_high <= high_max, (
        f"the submitted spectrum's high-frequency falloff is not physiological: "
        f"P(peak)/P(35 Hz)={r_high:.1f} outside [{high_min}, {high_max}]. A real spectrum falls to a "
        f"bounded high-frequency noise floor; a bump or a pure power law without a noise floor does not.")
    _, hw, _slope = theta_half_width(fb, pb)
    assert math.isfinite(hw) and hw_lo <= hw <= hw_hi, (
        f"the theta peak's half-width above the 1/f background ({hw:.2f} Hz) is outside the real "
        f"range [{hw_lo}, {hw_hi}] Hz; a narrow synthetic bump or a flat spectrum does not match "
        f"the real theta bandwidth")
    return corr, r_low, r_high, hw


def find_number(obj, key_patterns, exclude=None):
    exc = [re.compile(e) for e in (exclude or [])]
    pats = [re.compile(p) for p in key_patterns]
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if any(p.search(nk) for p in pats) and not any(e.search(nk) for e in exc):
                        fv = float(v)
                        if math.isfinite(fv):
                            return fv
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def find_all_numbers(obj, key_patterns, exclude=None):
    exc = [re.compile(e) for e in (exclude or [])]
    pats = [re.compile(p) for p in key_patterns]
    out = []
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = _norm(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if any(p.search(nk) for p in pats) and not any(e.search(nk) for e in exc):
                        fv = float(v)
                        if math.isfinite(fv):
                            out.append(fv)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out
