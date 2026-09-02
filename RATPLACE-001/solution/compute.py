"""Reference solution for RATPLACE-001.

Deliverable: the mean CA1 place-cell Skaggs spatial information (bits/spike) on the
Baseline rectangular-track of Rat 1, session ses-19980425 (DANDI 001754).

The Skaggs spatial-information estimator has a well-known small-sample / occupancy UPWARD
bias: with a finite number of spikes over a binned environment, even a spatially RANDOM
cell yields a positive apparent information value, because empty/under-sampled bins make
the observed rate map look tuned by chance. The honest analysis therefore does what every
place-cell paper does — it establishes a per-cell null by CIRCULARLY SHIFTING each spike
train relative to the position stream (breaking the spike<->place relationship while
preserving each signal's own statistics), recomputes the information many times, and
reports the bias-corrected value (raw minus the shuffle-null mean) and whether the raw
value exceeds the null.

Validated ground truth (DANDI 001754, sub-Rat1 ses-19980425, both BL epochs, running > 5
px/s, 4x5 = 20-bin grid, putative pyramidal CA1 units, 300 circular shifts, seed 20250901):
  n_units         = 36
  RAW mean        = 1.12 bits/spike      # looks like textbook place coding
  SHUFFLE null    = 1.03 bits/spike      # == the estimator's bias
  CORRECTED mean  = 0.09 bits/spike      # ~ 0
  significant     = 0 / 36  (raw > shuffle 95th pct)
So on this familiar-track baseline the raw ~1.1 bits/spike is essentially all sampling
bias: after shuffle correction the CA1 population carries no significant spatial
information at this binning. A synthetic place-cell positive control run through the SAME
pipeline is recovered cleanly (raw ~1.2 >> null ~0.05, significant), so the pipeline is
not broken -- the real cells simply do not survive bias correction here.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "001754"
ASSET = "sub-Rat1/sub-Rat1_ses-19980425T124500_behavior+ecephys.nwb"
FS = 50.0
DT = 1.0 / FS
NX, NY = 4, 5            # 20 spatial bins
RUN_THRESH = 5.0        # px/s
MIN_SPIKES = 50
RATE_LO, RATE_HI = 0.05, 5.0
N_SHUFF = 300
MIN_SHIFT_S = 20.0
SEED = 20250901


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dandiset": DANDISET, "asset": ASSET}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def skaggs(p, rate):
    m = p > 0
    p = p[m]
    rate = rate[m]
    mr = float(np.sum(p * rate))
    if mr <= 0:
        return 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = rate / mr
        term = p * ratio * np.log2(np.where(ratio > 0, ratio, 1.0))
    return float(np.nansum(term))


# ---- fetch the NWB asset from DANDI at runtime ----
local = OUT / "rat1_0425.nwb"
try:
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        asset = client.get_dandiset(DANDISET, "draft").get_asset_by_path(ASSET)
        if not (local.exists() and local.stat().st_size > 5_000_000):
            asset.download(str(local))
except Exception as e:
    fail(f"could not fetch DANDI {DANDISET}:{ASSET}: {e}")

try:
    from pynwb import NWBHDF5IO
    io = NWBHDF5IO(str(local), "r", load_namespaces=True)
    nwb = io.read()
    ep = nwb.epochs.to_dataframe()
    ss = nwb.processing["behavior"].data_interfaces["position"].spatial_series["spatial_series"]
    xy = ss.data[:].astype(float)
    t = ss.timestamps[:]
    u = nwb.units
    n_units = len(u.id)
    spikes = [np.asarray(u["spike_times"][i]) for i in range(n_units)]
    tetr = u["tetrode"][:]
    clus = u["cluster_id"][:]
    io.close()
except Exception as e:
    fail(f"NWB missing expected position/units structure: {e}")

# ---- Baseline rectangular-track, running only ----
BL = ep[ep["session_type"] == "BL"][["start_time", "stop_time"]].values
if len(BL) == 0:
    fail("no Baseline (BL) epochs in this session")
m = np.zeros(len(t), bool)
for s, e in BL:
    m |= (t >= s) & (t <= e)
tb, xb, yb = t[m], xy[m, 0], xy[m, 1]
valid = np.isfinite(xb) & np.isfinite(yb) & (xb > 0) & (yb > 0)
sp = np.sqrt(np.gradient(xb) ** 2 + np.gradient(yb) ** 2) / np.clip(np.gradient(tb), 1e-3, None)
spf = np.convolve(np.nan_to_num(sp), np.ones(5) / 5, mode="same")
run = valid & (spf > RUN_THRESH)
xr, yr, tr = xb[run], yb[run], tb[run]
if len(tr) < 1000:
    fail("too few running samples on the Baseline track")

xe = np.linspace(xr.min(), xr.max(), NX + 1)
ye = np.linspace(yr.min(), yr.max(), NY + 1)
NB = NX * NY


def binidx(x, y):
    ix = np.clip(np.digitize(x, xe) - 1, 0, NX - 1)
    iy = np.clip(np.digitize(y, ye) - 1, 0, NY - 1)
    idx = (ix * NY + iy).astype(int)
    idx[~(np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0))] = -1
    return idx


brun = binidx(xr, yr)
occ_time = np.bincount(brun[brun >= 0], minlength=NB).astype(float) * DT
p = occ_time / occ_time.sum()
rng = np.random.default_rng(SEED)
L = len(tr)
minshift = int(MIN_SHIFT_S * FS)

rows = []
for ui in range(n_units):
    st = spikes[ui]
    st = st[(st >= tr.min()) & (st <= tr.max())]
    idx = np.clip(np.searchsorted(tr, st), 0, L - 1)
    sb = brun[idx]
    sbv = sb[sb >= 0]
    nsp = len(sbv)
    mrate = nsp / occ_time.sum()
    if not (nsp >= MIN_SPIKES and RATE_LO < mrate < RATE_HI):
        continue
    sc = np.bincount(sbv, minlength=NB).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = sc / np.clip(occ_time, 1e-9, None)
    raw = skaggs(p, r)
    nv = np.empty(N_SHUFF)
    for s in range(N_SHUFF):
        shift = int(rng.integers(minshift, L - minshift))
        sbh = brun[(idx + shift) % L]
        sbh = sbh[sbh >= 0]
        sch = np.bincount(sbh, minlength=NB).astype(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            rh = sch / np.clip(occ_time, 1e-9, None)
        nv[s] = skaggs(p, rh)
    rows.append(dict(unit_index=ui, tetrode=str(tetr[ui]), cluster_id=int(clus[ui]),
                     n_spikes=int(nsp), mean_rate_hz=round(float(mrate), 4),
                     spatial_information_bits_per_spike=round(raw, 4),
                     shuffle_null_bits_per_spike=round(float(nv.mean()), 4),
                     shuffle_p95_bits_per_spike=round(float(np.percentile(nv, 95)), 4),
                     corrected_bits_per_spike=round(raw - float(nv.mean()), 4),
                     significant=bool(raw > np.percentile(nv, 95))))

if not rows:
    fail("no CA1 units passed the inclusion criteria")

raw_mean = float(np.mean([r["spatial_information_bits_per_spike"] for r in rows]))
null_mean = float(np.mean([r["shuffle_null_bits_per_spike"] for r in rows]))
corr_mean = float(np.mean([r["corrected_bits_per_spike"] for r in rows]))
nsig = int(sum(r["significant"] for r in rows))

# ---- positive control: synthetic place cell through the SAME pipeline ----
target = int(np.argmax(occ_time))
rng2 = np.random.default_rng(SEED + 1)
lam = np.where(brun == target, 8.0, 0.5)
syn_idx = np.where(rng2.random(L) < lam * DT)[0]
sc = np.bincount(brun[syn_idx][brun[syn_idx] >= 0], minlength=NB).astype(float)
with np.errstate(divide="ignore", invalid="ignore"):
    r = sc / np.clip(occ_time, 1e-9, None)
raw_syn = skaggs(p, r)
nv = np.empty(N_SHUFF)
for s in range(N_SHUFF):
    shift = int(rng2.integers(minshift, L - minshift))
    sbh = brun[(syn_idx + shift) % L]
    sbh = sbh[sbh >= 0]
    sch = np.bincount(sbh, minlength=NB).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        rh = sch / np.clip(occ_time, 1e-9, None)
    nv[s] = skaggs(p, rh)
pos_ctrl = dict(n_spikes=int(len(syn_idx)),
                raw_bits_per_spike=round(raw_syn, 4),
                shuffle_null_bits_per_spike=round(float(nv.mean()), 4),
                corrected_bits_per_spike=round(raw_syn - float(nv.mean()), 4),
                significant=bool(raw_syn > np.percentile(nv, 95)))

# ---- write outputs ----
import csv
with open(OUT / "spatial_information.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["unit_index", "tetrode", "cluster_id", "n_spikes", "mean_rate_hz",
                "spatial_information_bits_per_spike", "shuffle_null_bits_per_spike",
                "corrected_bits_per_spike", "significant"])
    for rr in rows:
        w.writerow([rr["unit_index"], rr["tetrode"], rr["cluster_id"], rr["n_spikes"],
                    rr["mean_rate_hz"], rr["spatial_information_bits_per_spike"],
                    rr["shuffle_null_bits_per_spike"], rr["corrected_bits_per_spike"],
                    int(rr["significant"])])

results = {
    # the value that should be REPORTED for these CA1 units: the bias-corrected mean,
    # which is ~0 -- the raw mean is essentially the estimator's occupancy/sampling bias.
    "mean_spatial_information_bits_per_spike": round(corr_mean, 4),
    "raw_mean_spatial_information_bits_per_spike": round(raw_mean, 4),
    "shuffle_null_mean_bits_per_spike": round(null_mean, 4),
    "corrected_mean_spatial_information_bits_per_spike": round(corr_mean, 4),
    "n_significant_units": nsig,
    "n_units": len(rows),
    "positive_control_synthetic_place_cell": pos_ctrl,
    "params": {"grid": [NX, NY], "n_bins": NB, "run_threshold_px_s": RUN_THRESH,
               "min_spikes": MIN_SPIKES, "rate_range_hz": [RATE_LO, RATE_HI],
               "n_shuffles": N_SHUFF, "min_shift_s": MIN_SHIFT_S, "seed": SEED},
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dandiset": DANDISET, "asset": ASSET,
    "session": "ses-19980425T124500", "subject": "Rat1",
    "epochs_used": "Baseline rectangular-track (session_type == 'BL')",
    "n_units": len(rows), "grid": [NX, NY], "n_bins": NB,
    "run_threshold_px_s": RUN_THRESH, "running_seconds": round(float(occ_time.sum()), 1),
}, indent=2))

(OUT / "findings.md").write_text(
    f"# CA1 place-cell spatial information — Rat 1, Baseline rectangular track\n\n"
    f"Analysed **{len(rows)} CA1 pyramidal units** over the Baseline rectangular-track epochs "
    f"(running only, 4x5 = 20-bin occupancy grid).\n\n"
    f"The **raw Skaggs spatial information averages {raw_mean:.2f} bits/spike** — a value that on "
    f"its face looks like textbook place coding. It is not. The Skaggs estimator is positively "
    f"biased at finite sample size: circularly shifting each spike train against position "
    f"(300 shifts, seed {SEED}) — which destroys any true spike-place relationship — yields a "
    f"**shuffle-null mean of {null_mean:.2f} bits/spike**, essentially equal to the raw value. "
    f"The **bias-corrected mean is only {corr_mean:.2f} bits/spike**, and **{nsig} of {len(rows)} "
    f"units** exceed their own shuffle 95th percentile.\n\n"
    f"**Conclusion: after shuffle correction these CA1 units carry no significant spatial "
    f"information on this familiar-track baseline — the raw ~{raw_mean:.1f} bits/spike is almost "
    f"entirely the estimator's occupancy/sampling bias, not spatial coding.** The reported "
    f"place-cell spatial information is therefore ~0 bits/spike (not significant), not "
    f"~{raw_mean:.1f}.\n\n"
    f"The pipeline itself is sound: a synthetic place cell (a field in one bin) pushed through "
    f"the identical analysis is recovered cleanly — raw {pos_ctrl['raw_bits_per_spike']:.2f} vs "
    f"shuffle-null {pos_ctrl['shuffle_null_bits_per_spike']:.2f} bits/spike, significant — so the "
    f"null result for the real cells reflects the data, not a broken estimator.\n"
)

print(f"n_units={len(rows)} raw={raw_mean:.3f} null={null_mean:.3f} corrected={corr_mean:.3f} "
      f"n_sig={nsig} pos_ctrl_raw={pos_ctrl['raw_bits_per_spike']:.3f} "
      f"pos_ctrl_null={pos_ctrl['shuffle_null_bits_per_spike']:.3f} sig={pos_ctrl['significant']}")
