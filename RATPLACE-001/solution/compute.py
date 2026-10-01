"""Quarantined Skaggs prototype: the pinned source lacks independent tracking.

The mandatory precondition below stops before network access or numerical work.
The historical prototype is retained for inspection, not as a valid estimator.
"""
import json
import os
import sys
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

DANDISET = "001754"
VERSION = "0.260728.1352"
ASSET_ID = "b8dbee0b-e84e-45f9-998d-39bee1803fc9"
ASSET_SHA256 = "f35c398d7e266ed81a960e00e8fb623bc5992deaed6f70c85cee340f431b5950"
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
        {"status": "failed_precondition", "reason": reason, "dandiset": DANDISET, "asset": ASSET,
         "version": VERSION, "asset_id": ASSET_ID, "source_sha256": ASSET_SHA256,
         "scientific_precondition": "independently_sampled_position_not_established"}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


# Original-byte inspection on 2026-10-01 establishes that this exact asset's
# SpatialSeries contains positions at spike occurrence times. Counting these
# rows as 20-ms dwell intervals conditions occupancy on the ensemble spikes.
# Interpolation or elapsed-time shuffles cannot restore unobserved behavior.
# Do not remove this gate without a reviewed independent tracking source and
# a genuinely rebuilt estimator/reference contract. See SOURCE_BLOCKER.md.
fail(
    "The pinned Rat1 NWB contains positions sampled at spike occurrence times, "
    "not independent 50 Hz tracking. Dwell-time occupancy, running selection, "
    "and Skaggs shuffle correction cannot be validated from this trace. "
    "Recover independently sampled tracking or revise the data contract first."
)

import numpy as np
from alignment import sample_indices, shifted_spikes, running_samples


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
        asset = client.get_dandiset(DANDISET, VERSION).get_asset_by_path(ASSET)
        if not (local.exists() and local.stat().st_size > 5_000_000):
            asset.download(str(local))
    import hashlib
    with local.open("rb") as stream:
        digest=hashlib.file_digest(stream,"sha256").hexdigest()
    if digest != ASSET_SHA256:
        fail("raw NWB hash does not match the published pinned asset; refusing cache")
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
included = running_samples(t, xy, BL, RUN_THRESH, DT)
xr, yr, tr = xy[included, 0], xy[included, 1], t[included]
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
full_bins = np.full(len(t), -1, int)
full_bins[included] = brun
occ_time = np.bincount(brun[brun >= 0], minlength=NB).astype(float) * DT
p = occ_time / occ_time.sum()
rng = np.random.default_rng(SEED)
L = len(tr)
minshift = int(MIN_SHIFT_S * FS)

rows = []
for ui in range(n_units):
    st = spikes[ui]
    idx = sample_indices(t, st, included, DT)
    sb = full_bins[idx]
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
        shuffled = shifted_spikes(st, BL, rng, MIN_SHIFT_S)
        sbh = full_bins[sample_indices(t, shuffled, included, DT)]
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
syn_times = tr[np.where(rng2.random(L) < lam * DT)[0]]
syn_idx = sample_indices(t, syn_times, included, DT)
sc = np.bincount(full_bins[syn_idx][full_bins[syn_idx] >= 0], minlength=NB).astype(float)
with np.errstate(divide="ignore", invalid="ignore"):
    r = sc / np.clip(occ_time, 1e-9, None)
raw_syn = skaggs(p, r)
nv = np.empty(N_SHUFF)
for s in range(N_SHUFF):
    shuffled = shifted_spikes(syn_times, BL, rng2, MIN_SHIFT_S)
    sbh = full_bins[sample_indices(t, shuffled, included, DT)]
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
    # Historical unvalidated prototype: no numerical conclusion is established.
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
    "version": VERSION, "asset_id": ASSET_ID, "source_sha256": ASSET_SHA256,
    "session": "ses-19980425T124500", "subject": "Rat1",
    "epochs_used": "Baseline rectangular-track (session_type == 'BL')",
    "n_units": len(rows), "grid": [NX, NY], "n_bins": NB,
    "run_threshold_px_s": RUN_THRESH, "running_seconds": round(float(occ_time.sum()), 1),
}, indent=2))

(OUT / "findings.md").write_text(
    f"# Rat1 CA1 spatial-information sensitivity case\n\n"
    f"Analysed {len(rows)} recorded units with the declared 20-bin running occupancy. "
    f"Raw mean={raw_mean:.3f}, elapsed-time shuffle-null mean={null_mean:.3f}, "
    f"raw-minus-null mean={corr_mean:.3f} bits/spike; {nsig} units exceed their null 95th percentile. "
    f"These are estimator- and binning-dependent observations, not evidence that CA1 lacks place coding. "
    f"The optional synthetic alignment diagnostic does not replace source data or establish neural truth.\n"
)

print(f"n_units={len(rows)} raw={raw_mean:.3f} null={null_mean:.3f} corrected={corr_mean:.3f} "
      f"n_sig={nsig} pos_ctrl_raw={pos_ctrl['raw_bits_per_spike']:.3f} "
      f"pos_ctrl_null={pos_ctrl['shuffle_null_bits_per_spike']:.3f} sig={pos_ctrl['significant']}")
