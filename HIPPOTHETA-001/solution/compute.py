"""Reference solution for HIPPOTHETA-001.

Deliverable: the hippocampal theta (6-10 Hz) peak frequency of the CA1 LFP WHILE THE MOUSE IS
LOCOMOTING, session sub-e15-13f1 ses-220117 (DANDI 000552, Huszar et al. 2022, "Preconfigured
dynamics in the hippocampus are guided by embryonic birthdate and rate of neurogenesis").

The off-critical-path error this targets (un-cued): theta frequency is state-dependent. The
running (locomotion) theta is FAST (~9 Hz), whereas theta during REM sleep and awake immobility
is ~1.5 Hz SLOWER (~7.4-7.5 Hz). This recording is a ~7 h session that is mostly home-cage
rest/sleep with a single ~31 min maze epoch. So the theta-band spectral peak taken over the
WHOLE recording (or without conditioning on movement) is dragged down to ~7.9 Hz by the
dominant slow-theta (REM / immobility) periods. Only restricting to locomotion recovers the
movement-related theta peak of ~9 Hz.

Validated ground truth (DANDI 000552, sub-e15-13f1 ses-220117, LFP 1250 Hz, best theta-power
channel, Welch 4 s windows, parabolic peak interpolation, 6-10 Hz band):
  CORRECT  during locomotion (speed > 5 units/s) : 8.99 Hz  (>3 -> 8.86; >8 -> ~8.9)  <-- reported
  NAIVE    whole recording, no movement gating    : 7.92 Hz
  (context) REM theta 7.42 Hz ; awake immobility theta 7.50 Hz
The locomotion peak is stable across the chosen channel (48/63/78 all 8.99 Hz) and across the
running threshold (~8.9 +/- 0.1 Hz). So the honest movement-related theta peak is ~9 Hz -- not
the ~7.9 Hz that a whole-recording spectrum reports.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "000552"
LFP_ASSET = "sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117-raw_ecephys.nwb"
BEH_ASSET = "sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117_behavior+ecephys.nwb"
THETA = (6.0, 10.0)          # theta band (Hz)
SEARCH = (5.0, 11.0)         # slightly wider search so a peak at the band edge is captured
RUN_THRESH = 5.0             # locomotion: running speed above this (position units / s)
SMOOTH_S = 0.25             # position smoothing before differencing (s)


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dandiset": DANDISET, "lfp_asset": LFP_ASSET, "behavior_asset": BEH_ASSET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def content_url(client, path):
    asset = client.get_dandiset(DANDISET, "draft").get_asset_by_path(path)
    return asset.get_content_url(follow_redirects=1, strip_query=False)


# ---- open both assets by streaming (no full download) ----
try:
    import warnings
    warnings.filterwarnings("ignore")
    import remfile
    import h5py
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        lfp_url = content_url(client, LFP_ASSET)
        beh_url = content_url(client, BEH_ASSET)
    hr = h5py.File(remfile.File(lfp_url), "r")
    hb = h5py.File(remfile.File(beh_url), "r")
except Exception as e:
    fail(f"could not resolve/stream DANDI {DANDISET} assets: {e}")

# ---- LFP handle ----
try:
    es = hr["processing/ecephys/LFP/ElectricalSeriesLFP"]
    data = es["data"]
    fs = float(es["starting_time"].attrs["rate"])
    n_samp, n_ch = data.shape
except Exception as e:
    fail(f"LFP ElectricalSeries missing/unexpected: {e}")

# ---- position -> running speed ----
try:
    from scipy.ndimage import gaussian_filter1d
    sp = hb["processing/behavior/SubjectPosition/SpatialSeries"]
    pos = sp["data"][:]
    pts = sp["timestamps"][:]
except Exception as e:
    fail(f"position SpatialSeries missing/unexpected: {e}")

if pos.ndim != 2 or pos.shape[1] < 2 or len(pts) < 100:
    fail(f"position data unexpected shape {pos.shape}")

good = np.isfinite(pos[:, 0]) & np.isfinite(pos[:, 1])
if good.sum() < 100:
    fail("too few finite position samples")
x = np.interp(pts, pts[good], pos[good, 0])
y = np.interp(pts, pts[good], pos[good, 1])
dt = float(np.median(np.diff(pts)))
fs_pos = 1.0 / dt
sig = max(SMOOTH_S * fs_pos, 1.0)
xs = gaussian_filter1d(x, sig)
ys = gaussian_filter1d(y, sig)
speed = np.sqrt(np.gradient(xs, pts) ** 2 + np.gradient(ys, pts) ** 2)

t0, t1 = float(pts[0]), float(pts[-1])   # the epoch during which position is tracked (the maze)

# running segments (contiguous runs of speed > threshold) -> LFP sample ranges
run = speed > RUN_THRESH
segments = []
i, n = 0, len(run)
while i < n:
    if run[i]:
        j = i
        while j < n and run[j]:
            j += 1
        a, b = int(pts[i] * fs), int(pts[j - 1] * fs)
        if 0 <= a < b <= n_samp:
            segments.append((a, b))
        i = j
    else:
        i += 1
run_time = sum((b - a) for a, b in segments) / fs
if run_time < 60:
    fail(f"too little locomotion time detected ({run_time:.1f}s)")

# ---- pick a clear-theta hippocampal channel from a window inside the maze epoch ----
from scipy import signal

def welch_peak(x, band=THETA, search=SEARCH, nperseg=None):
    if nperseg is None:
        nperseg = int(4 * fs)
    if len(x) < nperseg:
        nperseg = max(256, len(x) // 2)
    f, P = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)
    m = (f >= search[0]) & (f <= search[1])
    fb, Pb = f[m], P[m]
    k = int(np.argmax(Pb))
    if 0 < k < len(Pb) - 1:                      # parabolic interpolation of the peak
        y0, y1, y2 = Pb[k - 1], Pb[k], Pb[k + 1]
        den = (y0 - 2 * y1 + y2)
        delta = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        return float(fb[k] + delta * (fb[1] - fb[0]))
    return float(fb[k])

# a ~150 s window near the middle of the maze epoch, all channels (one chunk per channel)
wmid = 0.5 * (t0 + t1)
ws = int(max(t0, wmid - 75) * fs)
we = int(min(t1, wmid + 75) * fs)
try:
    block = data[ws:we, :].astype(np.float32)
except Exception as e:
    fail(f"could not read LFP channel-selection window: {e}")
fw, Pw = signal.welch(block, fs=fs, nperseg=int(4 * fs), axis=0)
theta_mask = (fw >= THETA[0]) & (fw <= THETA[1])
theta_power = Pw[theta_mask, :].mean(axis=0)
best_ch = int(np.argmax(theta_power))

# ---- read the chosen channel across the maze epoch, gather locomotion LFP ----
try:
    lfp_epoch = data[int(t0 * fs):int(t1 * fs), best_ch].astype(np.float32)
except Exception as e:
    fail(f"could not read chosen LFP channel: {e}")
base = int(t0 * fs)
chunks = []
for a, b in segments:
    ia, ib = a - base, b - base
    if 0 <= ia < ib <= len(lfp_epoch):
        chunks.append(lfp_epoch[ia:ib])
lfp_run = np.concatenate(chunks) if chunks else np.array([])
if len(lfp_run) < int(4 * fs):
    fail("insufficient locomotion LFP after gating")

theta_peak = welch_peak(lfp_run)

# whole-recording peak (for the write-up's contrast only; NOT the reported value)
try:
    lfp_full = data[:, best_ch].astype(np.float32)
    whole_peak = welch_peak(lfp_full)
except Exception:
    whole_peak = float("nan")

results = {
    "theta_peak_frequency_hz": round(theta_peak, 3),   # REPORTED: locomotion theta peak
    "theta_band_hz": list(THETA),
    "channel": best_ch,
    "running_criterion": f"speed > {RUN_THRESH} position-units/s (locomotion)",
    "locomotion_time_s": round(run_time, 1),
    "whole_recording_theta_peak_hz": round(whole_peak, 3),  # slow, state-contaminated (context)
    "params": {"lfp_rate_hz": fs, "spectral_estimator": "Welch, 4 s Hann windows, 50% overlap",
               "peak": "parabolic-interpolated argmax over 5-11 Hz"},
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "lfp_asset": LFP_ASSET, "behavior_asset": BEH_ASSET,
    "session": "sub-e15-13f1 ses-e15-13f1-220117", "lfp_rate_hz": fs, "n_channels": int(n_ch),
    "channel": best_ch, "running_criterion": f"speed > {RUN_THRESH} units/s",
    "locomotion_time_s": round(run_time, 1),
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Hippocampal theta peak frequency during locomotion - sub-e15-13f1 ses-220117\n\n"
    f"Estimated the CA1 LFP power spectrum (Welch, 4 s windows) on channel {best_ch} while the "
    f"mouse was locomoting ({run_time:.0f} s of running, speed > {RUN_THRESH} units/s on the "
    f"maze), and took the peak of the 6-10 Hz theta band.\n\n"
    f"**Theta peak frequency during locomotion = {theta_peak:.2f} Hz.** This movement-related "
    f"theta is fast (~9 Hz). For contrast, the theta-band peak taken over the whole ~7 h "
    f"recording is {whole_peak:.2f} Hz: that session is mostly rest/sleep, and theta during REM "
    f"and awake immobility is ~1.5 Hz slower, so a spectrum that does not condition on locomotion "
    f"is pulled down toward ~7.9 Hz and understates the movement-related theta frequency. The "
    f"locomotion estimate (~{theta_peak:.1f} Hz) is stable across the theta channel used and the "
    f"exact running-speed cutoff.\n"
)

print(f"best_ch={best_ch} run_time={run_time:.0f}s LOCOMOTION_peak={theta_peak:.3f}Hz "
      f"whole_recording_peak={whole_peak:.3f}Hz")
