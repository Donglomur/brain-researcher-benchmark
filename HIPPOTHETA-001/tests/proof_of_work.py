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
    return {
        "freq": np.asarray(z["ref_freq"], dtype=float),
        "pow": np.asarray(z["ref_pow"], dtype=float),
        "stats": json.loads(str(z["ref_stats"])),
    }


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
