"""Public fixed-window spectral arithmetic; no data access at import time."""
import numpy as np
from scipy import signal

FS = 1250.0
WINDOW = 5000
HOP = 2500


def window_spectrum(volts, fs=FS):
    x = np.asarray(volts, dtype=np.float64)
    if x.shape != (WINDOW,) or not np.isfinite(x).all():
        raise ValueError("a finite complete 5000-sample window is required")
    frequencies, power = signal.periodogram(
        x, fs=fs, window=signal.windows.hann(WINDOW, sym=False),
        detrend="constant", return_onesided=True, scaling="density", nfft=WINDOW,
    )
    if not np.isfinite(power).all() or np.any(power < 0):
        raise ValueError("invalid window spectrum")
    return frequencies, power


def theta_integral(frequencies, power):
    selected = (frequencies >= 6) & (frequencies <= 10)
    value = float(np.trapezoid(power[selected], frequencies[selected]))
    if not np.isfinite(value):
        raise ValueError("nonfinite theta integral")
    return value


def peak_summary(frequencies, power):
    frequencies, power = np.asarray(frequencies), np.asarray(power)
    selected = (frequencies >= 6) & (frequencies <= 10)
    f, p = frequencies[selected], power[selected]
    if len(f) != 17 or not np.isfinite(p).all():
        raise ValueError("complete finite quarter-Hz theta band required")
    index = int(np.argmax(p))
    peak = float(f[index])
    edge = index in (0, len(p) - 1)
    if not edge:
        curvature = p[index - 1] - 2 * p[index] + p[index + 1]
        if curvature != 0:
            peak += float(0.5 * (p[index - 1] - p[index + 1]) / curvature * 0.25)
    return {
        "theta_peak_grid_hz": float(f[index]),
        "theta_peak_frequency_hz": peak,
        "peak_at_band_edge": edge,
        "peak_tie_count": int(np.sum(p == p[index])),
        "theta_power_v2": theta_integral(frequencies, power),
    }
