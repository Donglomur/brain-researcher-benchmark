"""Build the packaged timeseries bundle for the dynamic-FC task (route b: offline).

Selects a fixed set of ABIDE Dosenbach-160 ROI TIMESERIES (cpac 'filt_noglobal' derivative:
band-pass filtered, NO global-signal regression) from the shared build-only bundle, so the
shipped task needs no network. The task needs the RAW timeseries (the sliding-window / surrogate
analysis operates on them), so we package the per-subject object array of T x 160 series; no
phenotype is needed for this task. Run from the repo root."""
import os
import numpy as np

SRC = "_shared_bundles/dos160_ts.npz"
DST = "DYNCONN-001/data/dos160_dynfc.npz"
NROI = 160
MIN_T = 54          # need >= max(window)+10 usable frames for the 22/30/44-TR sliding windows
N_KEEP = 60         # fixed subject set

d = np.load(SRC, allow_pickle=True)
ts = d["ts"]
kept = []
for arr in ts:
    a = np.asarray(arr, np.float16)
    if a.ndim == 2 and a.shape[0] >= MIN_T and a.shape[1] >= NROI:
        kept.append(a[:, :NROI].astype(np.float16))
    if len(kept) >= N_KEEP:
        break

out = np.empty(len(kept), dtype=object)
out[:] = kept
np.savez_compressed(DST, ts=out, atlas="Dosenbach-160",
                    preprocessing="ABIDE cpac filt_noglobal (band-pass filtered, no GSR)")
mb = os.path.getsize(DST) / 1e6
Ts = [a.shape[0] for a in kept]
print(f"saved {len(kept)} subjects timeseries -> {DST} ({mb:.2f} MB); "
      f"T min/median/max = {min(Ts)}/{int(np.median(Ts))}/{max(Ts)}; ROIs={NROI}")
