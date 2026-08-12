"""Build the packaged timeseries bundle for EFFCONN-001 (route b: offline).

Directed-connectivity reliability needs the RAW per-subject ROI timeseries (to fit a
vector-autoregressive / Granger model and to split each subject's run in half), so this packages
the per-subject Dosenbach-160 timeseries themselves — not a precomputed connectome. Reads the
build-only shared bundle (_shared_bundles/dos160_ts.npz, git-ignored) and writes the shipped,
network-free bundle EFFCONN-001/data/dos160_causal.npz.

Subset: subjects with >= 150 time points (so each split-half keeps >= 75 TRs for a stable VAR),
first 250 in bundle order (deterministic). Kept phenotype: dx only (this task uses timeseries;
dx is retained for provenance / ASD-TD counts, not for a group contrast).
"""
import os
import numpy as np

SHARED = os.path.expanduser(
    "~/Desktop/brain-researcher-benchmark/_shared_bundles/dos160_ts.npz")
OUT = os.path.expanduser(
    "~/Desktop/brain-researcher-benchmark/EFFCONN-001/data/dos160_causal.npz")
NROI, MIN_T, N_KEEP = 160, 150, 250

d = np.load(SHARED, allow_pickle=True)
ts_all, dx_all = d["ts"], d["dx"]
T = np.array([ts_all[i].shape[0] for i in range(len(ts_all))])
keep = np.where(T >= MIN_T)[0][:N_KEEP]

ts = np.empty(len(keep), object)
for k, i in enumerate(keep):
    ts[k] = np.asarray(ts_all[i], np.float16)[:, :NROI]     # T x 160, float16
dx = dx_all[keep].astype(np.int8)                            # 1 = ASD, 2 = TD

np.savez_compressed(OUT, ts=ts, dx=dx, atlas="Dosenbach-160", n_roi=NROI)
mb = os.path.getsize(OUT) / 1e6
Ts = [ts[k].shape[0] for k in range(len(ts))]
print(f"saved {len(ts)} subjects ({mb:.1f} MB)  T min/median/max = "
      f"{min(Ts)}/{int(np.median(Ts))}/{max(Ts)}  asd/td = {np.bincount(dx)[1:3]}")
