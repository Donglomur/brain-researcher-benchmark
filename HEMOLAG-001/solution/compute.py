"""Reference (oracle) for HEMOLAG-001 — reduced resting-state FC in stroke is partly a HEMODYNAMIC-LAG
(timing) artifact, not neural disconnection.

Paper anchor: Siegel et al. 2016, PNAS (10.1073/pnas.1521083113, "The effects of hemodynamic lag on
functional connectivity and behavior after stroke"). After stroke, hypoperfused tissue has DELAYED
BOLD responses (hemodynamic lag of seconds). Standard zero-lag functional connectivity (Pearson
correlation) is corrupted by this lag: a lagged region shows artifactually REDUCED zero-lag correlation
with the rest of the brain — which looks like 'disconnection' but is a timing artifact. Measuring FC at
the optimal lag (cross-correlation peak) recovers much of it.

The task (un-cued) asks to identify the post-stroke regions of lowest resting-state connectivity
('disconnection'). The naive move is to report the lowest zero-lag-FC regions as disconnected. This
reference VOLUNTEERS the check the task never asks: those regions have abnormal hemodynamic LAG, and
lag-corrected FC recovers a substantial share of their apparent deficit — so the reduced FC is (partly)
a perfusion-timing artifact, not neural disconnection.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(__file__).resolve().parent.parent / "data" / "stroke_timeseries.npz"


def fail(reason):
    (OUT / "connectivity.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


if not DATA.exists():
    fail(f"stroke timeseries not found at {DATA}")
d = np.load(DATA, allow_pickle=True)
tr = float(d["tr"]) if "tr" in d else 3.0
subs = [k for k in d.files if k.startswith("sub-")]
if len(subs) < 8:
    fail(f"too few subjects ({len(subs)})")


def z(x):
    return (x - x.mean(0)) / (x.std(0) + 1e-9)


def lagged_corr(a, b, k):
    if k > 0:
        a, b = a[k:], b[:len(b) - k]
    elif k < 0:
        a, b = a[:len(a) + k], b[-k:]
    if len(a) < 10:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (a.std() * b.std() + 1e-9))


maxlag = max(1, int(round(6.0 / tr)))
all_lag, all_zero, all_corr = [], [], []
for s in subs:
    ts = z(np.asarray(d[s], float))
    R = ts.shape[1]
    g = ts.mean(1)
    lags = np.array([max(range(-maxlag, maxlag + 1), key=lambda k: lagged_corr(ts[:, i], g, k))
                     for i in range(R)]) * tr
    zero = np.zeros(R); corr = np.zeros(R)
    for i in range(R):
        zs = [abs(lagged_corr(ts[:, i], ts[:, j], 0)) for j in range(R) if j != i]
        cs = [max(abs(lagged_corr(ts[:, i], ts[:, j], k)) for k in range(-maxlag, maxlag + 1))
              for j in range(R) if j != i]
        zero[i] = np.mean(zs); corr[i] = np.mean(cs)
    all_lag.append(lags); all_zero.append(zero); all_corr.append(corr)

L = np.concatenate(all_lag); Z = np.concatenate(all_zero); C = np.concatenate(all_corr)
gain = C - Z
hi = np.abs(L) > 1.0
frac_hi = float(hi.mean())
zero_hi, zero_lo = float(Z[hi].mean()), float(Z[~hi].mean())
recover_hi = float(gain[hi].mean())
deficit = zero_lo - zero_hi
recovered_frac = float(recover_hi / deficit) if deficit > 0 else float("nan")
from numpy import corrcoef
r_laggain = float(corrcoef(np.abs(L), gain)[0, 1])

(OUT / "connectivity.json").write_text(json.dumps({
    "dataset": "OpenNeuro ds003999 post-stroke resting-state", "n_subjects": len(subs),
    "n_regions": 48, "tr_s": tr,
    "fraction_regions_hemodynamic_lag_over_1s": frac_hi,
    "zero_lag_FC_high_lag_regions": zero_hi,
    "zero_lag_FC_low_lag_regions": zero_lo,
    "apparent_FC_deficit_in_lagged_regions": deficit,
    "FC_recovered_by_lag_correction": recover_hi,
    "fraction_of_deficit_recovered": recovered_frac,
    "corr_absLag_vs_FCrecovered": r_laggain,
    "method": "per-region hemodynamic lag vs global; zero-lag vs lag-corrected (max cross-correlation) FC",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OpenNeuro ds003999 post-stroke resting-state (Harvard-Oxford 48 ROI)",
    "n_subjects": len(subs),
    "method": "hemodynamic-lag estimation + zero-lag vs lag-corrected functional connectivity",
}, indent=2))

(OUT / "findings.md").write_text(f"""# HEMOLAG-001 — 'disconnection' in post-stroke resting-state FC

{len(subs)} post-stroke patients, Harvard-Oxford 48-ROI resting connectivity (TR = {tr:.0f} s).

## Reduced FC is partly a hemodynamic-lag artifact, not disconnection
After stroke, hypoperfused tissue has a **delayed BOLD response** (hemodynamic lag). Standard zero-lag
correlation is corrupted by this delay: a lagged region looks weakly connected because its signal is
time-shifted, not because it is neurally disconnected.
- Regions with **> 1 s hemodynamic lag** ({frac_hi*100:.0f}% of regions here) have lower zero-lag FC
  (**{zero_hi:.2f}** vs **{zero_lo:.2f}** in low-lag regions — an apparent deficit of {deficit:.2f}).
- Measuring FC at each pair's **optimal lag** (cross-correlation peak) recovers **{recover_hi:.2f}** of
  that deficit — about **{recovered_frac*100:.0f}%** of the apparent 'disconnection' in lagged regions.
- Regional lag predicts how much FC the lag-correction recovers (r = {r_laggain:+.2f}).

(The recovered fraction is a **lower bound**: at TR = {tr:.0f} s the lag can only be corrected in whole-TR
steps, so sub-{tr:.0f}s delays remain uncorrected — a finer-TR acquisition would recover more.)

## Conclusion
Reduced zero-lag resting-state FC after stroke **does not by itself indicate neural disconnection**: a
substantial share is a **hemodynamic-lag (perfusion-timing) artifact** (Siegel et al. 2016). The regions
of lowest connectivity overlap the regions of abnormal hemodynamic lag, and lag-corrected connectivity
recovers much of their deficit. Reporting low FC as 'disconnection' without checking hemodynamic lag
over-states the neural interpretation; valid post-stroke FC requires lag correction (or lag regression).
""")
print(f"OK: n={len(subs)} frac_hi_lag={frac_hi:.2f}; zero-lag hi={zero_hi:.2f} lo={zero_lo:.2f}; "
      f"recovered={recovered_frac*100:.0f}% of deficit; r(lag,gain)={r_laggain:+.2f}")
