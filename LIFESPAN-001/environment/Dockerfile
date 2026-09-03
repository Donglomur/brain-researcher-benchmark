FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2 pandas==2.2.3 \
      nibabel==5.3.2 nilearn==0.13.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is committed
# to the repo. Source: NKI Enhanced resting-state surface data (TR=645 ms, fsaverage5), fetched with
# nilearn.datasets.fetch_surf_nki_enhanced (first 60 subjects, ages 18-78). Each subject's left+right
# fsaverage5 time series is parcellated into the 148-region Destrieux atlas (region-mean time series);
# the bundle holds the (n_subjects, 895, 148) region time series plus age and sex. The download is
# ~5 GB from the NKI/NITRC mirror and can be slow; the fetch is retried until it completes, then the
# raw surface files are removed to keep the image small.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import os, glob, time
import numpy as np, pandas as pd, nibabel as nib
from nilearn import datasets

# --- fetch (retry: nilearn resumes partial downloads on the flaky NITRC mirror) ---
N = 60
for attempt in range(80):
    try:
        nki = datasets.fetch_surf_nki_enhanced(n_subjects=N, verbose=0)
        break
    except Exception as e:
        print(f"[fetch retry {attempt}] {type(e).__name__}: {str(e)[:80]}", flush=True)
        time.sleep(3)
else:
    raise SystemExit("could not fetch NKI surface data")
des = datasets.fetch_atlas_surf_destrieux(verbose=0)

data_dir = os.path.dirname(os.path.dirname(nki["func_left"][0]))
pheno = pd.read_csv(os.path.join(data_dir, "NKI_enhanced_surface_phenotypics.csv"))
pheno = pheno.rename(columns={pheno.columns[0]: "Subject"})
age_by = dict(zip(pheno["Subject"], pheno["Age"]))
sex_by = dict(zip(pheno["Subject"], pheno["Sex"]))

labels = des["labels"]
bad = [i for i, n in enumerate(labels) if n in ("Unknown", "Medial_wall")]
labL = np.array(des["map_left"]); labR = np.array(des["map_right"])
region_ids, region_names = [], []
for base, off, hemi in [(labL, 0, "L"), (labR, 100, "R")]:
    for rid in np.unique(base):
        if rid in bad:
            continue
        region_ids.append(rid + off); region_names.append(f"{hemi}_{labels[rid]}")
region_ids = np.array(region_ids); R = len(region_ids)
lab = np.concatenate([labL, labR + 100])

TS, ok_subs = [], []
for lh in nki["func_left"]:
    s = os.path.basename(os.path.dirname(lh))
    rh = os.path.join(os.path.dirname(lh), f"{s}_right_preprocessed_fwhm6.gii")
    if s not in age_by or not os.path.exists(rh):
        continue
    try:
        XL = np.array([d.data for d in nib.load(lh).darrays])
        XR = np.array([d.data for d in nib.load(rh).darrays])
        X = np.concatenate([XL, XR], axis=1)
        if X.shape[0] != 895:
            continue
        rts = np.zeros((X.shape[0], R), dtype=np.float32)
        for j, rid in enumerate(region_ids):
            rts[:, j] = X[:, lab == rid].mean(1)
        TS.append(rts); ok_subs.append(s)
    except Exception as e:
        print("skip", s, e, flush=True)

TS = np.array(TS, dtype=np.float32)
age = np.array([age_by[s] for s in ok_subs], dtype=np.float32)
sex = np.array([sex_by[s] for s in ok_subs])
assert TS.shape[0] >= 50, f"too few subjects extracted: {TS.shape}"
np.savez_compressed("/opt/bundle/nki_surface_roi_timeseries.npz",
                    timeseries=TS, age=age, sex=sex, subject=np.array(ok_subs),
                    region_name=np.array(region_names), tr=np.float32(0.645))
print("built nki_surface_roi_timeseries.npz:", TS.shape, "ages", age.min(), age.max(), flush=True)
PY
# drop the raw ~5 GB surface download; keep only the compact bundle
RUN rm -rf /root/nilearn_data
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
