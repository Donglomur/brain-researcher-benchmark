"""Build the packaged resting-state time-series bundle for RESTNETS-001 (route b: offline).

Precomputes a set of ABIDE control-subject Dosenbach-160 ROI time series, so the shipped task
needs no network. The agent still gets the raw per-subject time series, so it can concatenate the
group data, decompose it with ICA at any model order, and re-run the decomposition across model
orders / random seeds / split-halves to test whether the components reproduce.

Source: the build-only shared bundle `_shared_bundles/dos160_ts.npz` (946 ABIDE subjects,
Dosenbach-160). We keep the CONTROL subjects (DX_GROUP == 2) with a usable time series and store
their per-subject ROI time series (object array, float16) plus the diagnosis phenotype `dx`.
"""
import numpy as np

SRC = "_shared_bundles/dos160_ts.npz"
DST = "RESTNETS-001/data/dos160_ica.npz"
N_SUBJECTS = 80          # control subjects packaged (deterministic: sorted by subject id)
MIN_T = 100              # need enough time points per subject for a stable ICA

d = np.load(SRC, allow_pickle=True)
ts, dx, subid = d["ts"], np.asarray(d["dx"], float), np.asarray(d["subid"])

# control subjects (DX_GROUP == 2) with a usable Dosenbach-160 time series, deterministic order
ctrl = [i for i in np.argsort(subid)
        if dx[i] == 2
        and np.asarray(ts[i]).ndim == 2
        and np.asarray(ts[i]).shape[0] >= MIN_T
        and np.asarray(ts[i]).shape[1] >= 160]
keep = ctrl[:N_SUBJECTS]

out_ts = np.empty(len(keep), dtype=object)
for j, i in enumerate(keep):
    out_ts[j] = np.asarray(ts[i], dtype=np.float16)[:, :160]
out_dx = dx[keep].astype(np.int8)

np.savez_compressed(DST, ts=out_ts, dx=out_dx, atlas="Dosenbach-160",
                    n_rois=160, note="ABIDE control-subject resting-state ROI time series (float16)")

import os
sz = os.path.getsize(DST)
Ts = [a.shape[0] for a in out_ts]
print(f"saved ts=({len(out_ts)} subjects, T in [{min(Ts)},{max(Ts)}] x 160) "
      f"dx(2=control)={np.bincount(out_dx)[2] if out_dx.max()>=2 else 0}  "
      f"file={sz/1e6:.2f}MB")
