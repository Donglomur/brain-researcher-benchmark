"""Independent, public fixed-channel measurement mechanics (no oracle imports)."""
import math

import numpy as np

PIPELINE_ID = "fixed-channel-gap-safe-welch-v2"
CONDITIONS = ("locomotion", "whole_session")
FS = 1250.0
WINDOW = 5000
HOP = 2500
CHANNEL = {"lfp_column": 0, "electrode_table_row": 0, "electrode_id": 0,
           "channel_name": "1", "location": "unknown",
           "selection": "Fixed before signal inspection. Never select a more favorable channel."}


def behavior_tables(timestamps, positions, n_samples, *, fs=FS, start=0.0):
    """Reconstruct all original rows, gap-safe blocks, and elementary intervals."""
    t = np.asarray(timestamps, dtype=np.float64)
    xy = np.asarray(positions, dtype=np.float64)
    assert t.ndim == 1 and len(t) >= 2 and xy.shape == (len(t), 2)
    assert np.isfinite(t).all() and np.all(np.diff(t) > 0), "invalid source clock"
    dt0 = float(np.median(np.diff(t)))
    valid = np.isfinite(xy).all(axis=1)
    block_index = np.full(len(t), -1, dtype=int)
    smoothed = np.full(xy.shape, np.nan, dtype=np.float64)
    speed = np.full(len(t), np.nan, dtype=np.float64)
    spans = []
    i = 0
    while i < len(t):
        if not valid[i]:
            i += 1
            continue
        a = i
        i += 1
        while i < len(t) and valid[i] and t[i] - t[i - 1] <= 1.5 * dt0:
            i += 1
        b = i
        block_index[a:b] = len(spans)
        spans.append((a, b))
        for k in range(a, b):
            if t[k] - t[a] < 1.0 or t[b - 1] - t[k] < 1.0:
                continue
            # Search bounds are an acceleration, not the support definition.
            # Include neighboring candidates before testing actual differences.
            left = max(a, int(np.searchsorted(t, t[k] - 1.0, side="left")) - 1)
            right = min(b, int(np.searchsorted(t, t[k] + 1.0, side="right")) + 1)
            candidates = np.arange(left, right)
            candidates = candidates[np.abs(t[candidates] - t[k]) <= 1.0]
            weights = np.exp(-0.5 * ((t[candidates] - t[k]) / 0.25) ** 2)
            smoothed[k] = (weights[:, None] * xy[candidates]).sum(axis=0) / weights.sum()
            assert np.isfinite(smoothed[k]).all(), "smoother overflow"
        for k in range(a + 1, b - 1):
            if not np.isfinite(smoothed[k - 1:k + 2]).all():
                continue
            h0, h1 = t[k] - t[k - 1], t[k + 1] - t[k]
            coefficients = np.array([-h1 / (h0 * (h0 + h1)),
                                     (h1 - h0) / (h0 * h1),
                                     h0 / (h1 * (h0 + h1))])
            derivative = coefficients @ smoothed[k - 1:k + 2]
            speed[k] = np.hypot(*derivative)
            assert math.isfinite(speed[k]), "speed overflow"
    selected = np.zeros(len(t), dtype=bool)
    selected[:-1] = ((block_index[:-1] >= 0) & (block_index[:-1] == block_index[1:])
                    & np.isfinite(speed[:-1]) & np.isfinite(speed[1:])
                    & (speed[:-1] > 5.0) & (speed[1:] > 5.0))
    behavior = []
    for k in range(len(t)):
        behavior.append({
            "row_id": k, "timestamp_s": float(t[k]),
            "x_cm": float(xy[k, 0]) if math.isfinite(xy[k, 0]) else None,
            "y_cm": float(xy[k, 1]) if math.isfinite(xy[k, 1]) else None,
            "position_valid": bool(valid[k]),
            "block_id": int(block_index[k]) if valid[k] else None,
            "smoothed_x_cm": float(smoothed[k, 0]) if math.isfinite(smoothed[k, 0]) else None,
            "smoothed_y_cm": float(smoothed[k, 1]) if math.isfinite(smoothed[k, 1]) else None,
            "smoothed_valid": bool(np.isfinite(smoothed[k]).all()),
            "speed_cm_s": float(speed[k]) if math.isfinite(speed[k]) else None,
            "speed_valid": bool(math.isfinite(speed[k])),
            "selected_interval_to_next": bool(selected[k]),
        })
    blocks = [{"block_id": number, "start_row": a, "end_row_exclusive": b,
               "n_rows": b - a, "start_time_s": float(t[a]), "last_time_s": float(t[b - 1]),
               "n_smoothed": int(np.isfinite(smoothed[a:b]).all(axis=1).sum()),
               "n_speed_valid": int(np.isfinite(speed[a:b]).sum())}
              for number, (a, b) in enumerate(spans)]
    bouts = []
    k = 0
    while k < len(t):
        if not selected[k]:
            k += 1
            continue
        a = k
        while k < len(t) and selected[k]:
            k += 1
        b = k
        sample_a = math.ceil((t[a] - start) * fs)
        sample_b = math.floor((t[b] - start) * fs)
        assert 0 <= sample_a <= sample_b <= n_samples, "behavior outside LFP support"
        count = max(0, 1 + (sample_b - sample_a - WINDOW) // HOP)
        bouts.append({"bout_id": len(bouts), "block_id": int(block_index[a]),
                      "start_row": a, "end_row": b, "start_time_s": float(t[a]),
                      "stop_time_s": float(t[b]), "start_sample": sample_a,
                      "end_sample": sample_b, "n_samples": sample_b - sample_a,
                      "n_windows": count, "status": "retained" if count else "short"})
    return behavior, blocks, bouts, dt0


def window_support(bouts, n_samples):
    rows = []
    for condition in CONDITIONS:
        index = 0
        spans = [(b["bout_id"], b["start_sample"], b["end_sample"]) for b in bouts]
        if condition == "whole_session":
            spans = [(-1, 0, n_samples)]
        for bout_id, a, b in spans:
            for start in range(a, b - WINDOW + 1, HOP):
                rows.append({"condition": condition, "bout_id": bout_id,
                             "window_index": index, "start_sample": start,
                             "end_sample": start + WINDOW})
                index += 1
    return rows


def periodogram(volts, fs=FS):
    x = np.asarray(volts, dtype=np.float64)
    assert x.shape == (WINDOW,) and np.isfinite(x).all(), "invalid LFP window"
    taper = 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(WINDOW) / WINDOW)
    transformed = np.fft.rfft((x - x.mean()) * taper, n=WINDOW)
    power = (transformed.real ** 2 + transformed.imag ** 2) / (fs * np.sum(taper ** 2))
    power[1:-1] *= 2.0
    assert np.isfinite(power).all() and np.all(power >= 0), "PSD overflow"
    return np.fft.rfftfreq(WINDOW, 1.0 / fs), power


def measure_windows(volts, support, fs=FS):
    """Memory-bounded independent periodograms; no per-window tensor required."""
    signal = np.asarray(volts, dtype=np.float64)
    assert signal.ndim == 1 and np.isfinite(signal).all(), "invalid full LFP source"
    sums = {condition: np.zeros(WINDOW // 2 + 1) for condition in CONDITIONS}
    counts = {condition: 0 for condition in CONDITIONS}
    rows = []
    for original in support:
        row = dict(original)
        x = signal[row["start_sample"]:row["end_sample"]]
        freq, power = periodogram(x, fs)
        band = (freq >= 6.0) & (freq <= 10.0)
        row.update(mean_volts=float(x.mean()), mean_square_volts=float(np.mean(x * x)),
                   theta_power_v2=float(np.trapezoid(power[band], freq[band])))
        assert all(math.isfinite(row[key]) for key in ("mean_volts", "mean_square_volts", "theta_power_v2"))
        sums[row["condition"]] += power
        counts[row["condition"]] += 1
        rows.append(row)
    assert all(counts.values()), "no complete locomotion or whole-session window"
    spectra = np.stack([sums[c] / counts[c] for c in CONDITIONS])
    assert np.isfinite(spectra).all()
    return rows, freq, spectra


def peak(power, frequencies):
    frequencies = np.asarray(frequencies, dtype=np.float64)
    power = np.asarray(power, dtype=np.float64)
    use = np.flatnonzero((frequencies >= 6.0) & (frequencies <= 10.0))
    assert len(use) and np.isfinite(power).all() and np.all(power >= 0)
    local = power[use]
    position = int(np.argmax(local))
    k = int(use[position])
    edge = position in (0, len(use) - 1)
    interpolated = float(frequencies[k])
    if not edge:
        a, b, c = power[k - 1:k + 2]
        curvature = float(a - 2.0 * b + c)
        if curvature != 0.0:
            interpolated += 0.5 * float(a - c) / curvature * float(frequencies[k + 1] - frequencies[k])
    return {"theta_peak_grid_hz": float(frequencies[k]), "theta_peak_frequency_hz": interpolated,
            "peak_at_band_edge": edge, "peak_tie_count": int(np.sum(local == local[position]))}


def summarize(behavior, blocks, bouts, windows, frequencies, spectra, *, fs=FS, dt0=None):
    if dt0 is None:
        dt0 = float(np.median(np.diff([r["timestamp_s"] for r in behavior])))
    out = {"status": "ok", "pipeline_id": PIPELINE_ID, "channel": dict(CHANNEL),
           "n_behavior_rows": len(behavior),
           "n_valid_position_rows": sum(r["position_valid"] for r in behavior),
           "n_behavior_blocks": len(blocks), "n_locomotion_bouts": len(bouts),
           "n_retained_bouts": sum(b["status"] == "retained" for b in bouts),
           "n_short_bouts": sum(b["status"] == "short" for b in bouts),
           "dt0_s": dt0, "gap_threshold_s": 1.5 * dt0,
           "locomotion_interval_duration_s": math.fsum(b["stop_time_s"] - b["start_time_s"] for b in bouts),
           "locomotion_sample_support_s": sum(b["n_samples"] for b in bouts) / fs,
           "locomotion_used_support_s": sum(WINDOW + HOP * (b["n_windows"] - 1) for b in bouts if b["n_windows"]) / fs,
           "conditions": {}}
    band = (frequencies >= 6.0) & (frequencies <= 10.0)
    for i, condition in enumerate(CONDITIONS):
        values = peak(spectra[i], frequencies)
        values["n_windows"] = sum(r["condition"] == condition for r in windows)
        values["theta_power_v2"] = float(np.trapezoid(spectra[i, band], frequencies[band]))
        out["conditions"][condition] = values
    out["peak_difference_hz"] = (out["conditions"]["locomotion"]["theta_peak_frequency_hz"]
                                 - out["conditions"]["whole_session"]["theta_peak_frequency_hz"])
    return out
