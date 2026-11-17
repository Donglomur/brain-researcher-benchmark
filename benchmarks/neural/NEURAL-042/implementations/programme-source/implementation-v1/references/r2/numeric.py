"""R2 direct convolution, explicit analytic Fourier multiplier and bin sums."""
import math
from .budget import require

FS = 400
SAMPLES = 1000
LOW = (4, 6)
HIGH = tuple(range(70, 141, 5))
PAIRS = tuple((f, g) for f in LOW for g in HIGH)


def libraries(*, production=False):
    import numpy as np
    if production and np.__version__ != "2.2.6":
        raise RuntimeError("R2 production requires qualified NumPy 2.2.6")
    return np


def kernel(low, high, budget):
    np = libraries()
    require(type(low) in (int, float) and type(high) in (int, float)
            and math.isfinite(low) and math.isfinite(high)
            and 0 < low < high < FS / 2, "band", budget)
    df = min(max(0.25 * low, 2.0), low, FS / 2 - high)
    order = 2 * math.ceil((3.3 * FS / df) / 2)
    count = order + 1
    with budget.numeric(64 * count, 100 * count, 256 * count):
        j = np.arange(-order // 2, order // 2 + 1, dtype=np.float64)
        window = 0.54 + 0.46 * np.cos(2 * math.pi * j / order)
        parts = []
        for cutoff in (high + df / 2, low - df / 2):
            z = (2 * cutoff / FS) * j
            sinc = np.ones(count, dtype=np.float64)
            nonzero = z != 0
            sinc[nonzero] = np.sin(math.pi * z[nonzero]) / (math.pi * z[nonzero])
            raw = (2 * cutoff / FS) * sinc * window
            total = float(np.sum(raw, dtype=np.float64))
            require(math.isfinite(total) and total != 0, "filter_normalizer", budget)
            parts.append(raw / total)
        answer = parts[0] - parts[1]
        require(np.isfinite(answer).all(), "filter_finite", budget)
        budget.tick()
        return answer


def direct_filter(x, h, budget):
    """Endpoint repeat and direct linear convolution, never an FFT convolution."""
    np = libraries()
    require(x.ndim == 2 and h.ndim == 1 and h.size % 2 == 1,
            "direct_filter_shape", budget)
    n, length = x.shape
    require(length > 0, "direct_filter_length", budget)
    pad = h.size // 2
    with budget.numeric(n * (8 * length + 16 * pad) + 64,
                        2 * max(1, n) * length * h.size,
                        8 * n * length + 64 * (length + 2 * pad)):
        out = np.empty((n, length), dtype=np.float64)
        for i in range(n):
            budget.tick()
            extended = np.concatenate((np.full(pad, x[i, 0]), x[i],
                                       np.full(pad, x[i, -1])))
            out[i] = np.convolve(extended, h, mode="valid")
            budget.tick()
        require(np.isfinite(out).all(), "direct_filter_finite", budget)
        return out


def analytic_fourier(x, budget):
    """DFT multiplier is explicit; no Hilbert transform helper is called."""
    np = libraries()
    require(x.ndim == 2 and x.shape[1] >= 2 and np.isfinite(x).all(),
            "analytic_shape_finite", budget)
    n, length = x.shape
    with budget.numeric(10 * n * length + length,
                        max(1, n) * length * max(1, math.ceil(math.log2(length))) * 12,
                        112 * n * length + 8 * length):
        multiplier = np.zeros(length, dtype=np.float64)
        multiplier[0] = 1
        if length % 2 == 0:
            multiplier[length // 2] = 1
            multiplier[1:length // 2] = 2
        else:
            multiplier[1:(length + 1) // 2] = 2
        budget.tick()
        spectrum = np.fft.fft(x, axis=1)
        budget.tick()
        answer = np.fft.ifft(spectrum * multiplier[None, :], axis=1)
        budget.tick()
        require(np.isfinite(answer).all(), "analytic_finite", budget)
        return answer


def band_analytic(x, low, high, budget, counters):
    h = kernel(low, high, budget)
    counters["analytic_filter_calls"] += 1
    counters["filtered_trial_calls"] += int(x.shape[0])
    # Retain returned filtered array while the Fourier work is live.
    with budget.live(16 * x.size + 16 * h.size):
        filtered = direct_filter(x, h, budget)
        return analytic_fourier(filtered, budget)


def features(x, rates, budget, counters):
    np = libraries()
    n, length = x.shape
    budget.reserve("elements", 4 * n * length + 128 * n + 64)
    budget.reserve("work_units", 4 * n * length + 128 * n + 64)
    low_phase = {}
    theta = np.zeros(n, dtype=np.float64)
    gamma = np.zeros(n, dtype=np.float64)
    harmonic = {}
    for f in LOW:
        z = band_analytic(x, f - 1, f + 1, budget, counters)
        with budget.numeric(8 * n * length, 12 * n * length, 80 * n * length):
            low_phase[f] = np.angle(z)
            theta += np.mean(np.abs(z) ** 2, axis=1) / len(LOW)
    for f, g in PAIRS:
        z = band_analytic(x, g - f, g + f, budget, counters)
        with budget.numeric(16 * n * length, 30 * n * length, 144 * n * length):
            amplitude = np.abs(z)
            high_phase = np.angle(z)
            gamma += np.mean(amplitude ** 2, axis=1) / len(PAIRS)
            h = round(g / f)  # Python's declared ties-to-even rule.
            harmonic[(f, g)] = np.mean(np.exp(1j * (h * low_phase[f] - high_phase)), axis=1)
    with budget.numeric(12 * n * length + 20 * n, 24 * n * length,
                        112 * n * length + 160 * n):
        dx = np.diff(x, axis=1)
        positive = np.mean(np.maximum(dx, 0) ** 2, axis=1)
        negative = np.mean(np.minimum(dx, 0) ** 2, axis=1)
        denominator = positive + negative
        asymmetry = np.divide(positive - negative, denominator,
                              out=np.zeros(n, dtype=np.float64), where=denominator != 0)
        finite = bool(np.isfinite(theta).all() and np.isfinite(gamma).all()
                      and np.isfinite(asymmetry).all())
        require(finite, "feature_nonfinite", budget)
        positive_power = bool((theta > 0).all() and (gamma > 0).all())
        nuisance = None
        if positive_power:
            nuisance = np.column_stack((np.log(theta), np.log(gamma), np.log1p(rates)))
            require(np.isfinite(nuisance).all(), "nuisance_nonfinite", budget)
        budget.tick()
        return {"low_phase": low_phase, "theta_power": theta, "gamma_power": gamma,
                "firing_rate": rates, "waveform_asymmetry": asymmetry,
                "harmonic": harmonic, "nuisance": nuisance,
                "positive_power": positive_power}


def phase_bins(phase, budget):
    np = libraries()
    require(phase.ndim == 2 and phase.size > 0 and np.isfinite(phase).all()
            and (phase >= -math.pi).all() and (phase <= math.pi).all(),
            "phase_shape_finite", budget)
    n = int(phase.size)
    with budget.numeric(20 * n + 256, 20 * n, 112 * n + 2048):
        # Exact P binary64 order: add, modulo, divide, multiply, floor.
        # No reciprocal multiplication, subtract/re-add wrapping or clipping.
        bins = np.floor(((phase.reshape(-1) + math.pi) % (2 * math.pi))
                        / (2 * math.pi) * 18).astype(np.int64)
        require(bool((bins >= 0).all() and (bins < 18).all()), "phase_bin_range", budget)
        counts = np.zeros(18, dtype=np.int64)
        np.add.at(counts, bins, 1)
        budget.tick()
        return {"indices": bins, "counts": counts, "shape": tuple(phase.shape)}


def mi_from_bins(plan, amplitude, budget):
    np = libraries()
    require(tuple(amplitude.shape) == plan["shape"], "mi_shape", budget)
    n = int(amplitude.size)
    with budget.numeric(3 * n + 144, 8 * n + 300, 32 * n + 2048):
        require(bool(np.isfinite(amplitude).all() and (amplitude >= 0).all()),
                "amplitude_finite_nonnegative", budget)
        if bool((plan["counts"] == 0).any()):
            return None
        sums = np.zeros(18, dtype=np.float64)
        np.add.at(sums, plan["indices"], amplitude.reshape(-1))
        means = sums / plan["counts"]
        total = float(np.sum(means, dtype=np.float64))
        if not math.isfinite(total) or total <= 0:
            return None
        q = means / total
        positive = q > 0
        value = float((np.sum(q[positive] * np.log(q[positive])) + math.log(18)) / math.log(18))
        if not math.isfinite(value):
            return None
        budget.tick()
        return max(0.0, value)


def tort_mi(phase, amplitude, budget):
    return mi_from_bins(phase_bins(phase, budget), amplitude, budget)

