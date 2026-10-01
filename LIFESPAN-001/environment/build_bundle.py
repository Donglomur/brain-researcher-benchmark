
import os, glob, time, json, hashlib
from pathlib import Path
manifest_path=Path(__file__).with_name('cohort_manifest.json')
if not manifest_path.exists():
    manifest_path=Path(__file__).parents[1]/'environment/cohort_manifest.json'
manifest=json.loads(manifest_path.read_text())
expected=set(manifest['subject_ids'])
source_receipts={}
def sha256(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):
            digest.update(block)
    return digest.hexdigest()
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
    if s not in expected:
        continue  # Explicitly outside the declared frozen convenience cohort.
    if s not in age_by or not os.path.exists(rh):
        raise RuntimeError(f"required subject files/metadata absent: {s}")
    source_receipts[s]={"left_sha256":sha256(lh),"right_sha256":sha256(rh)}
    try:
        XL = np.array([d.data for d in nib.load(lh).darrays])
        XR = np.array([d.data for d in nib.load(rh).darrays])
        X = np.concatenate([XL, XR], axis=1)
        if X.shape[0] != 895:
            raise RuntimeError(f"required subject shape differs: {s}: {X.shape}")
        rts = np.zeros((X.shape[0], R), dtype=np.float32)
        for j, rid in enumerate(region_ids):
            rts[:, j] = X[:, lab == rid].mean(1)
        TS.append(rts); ok_subs.append(s)
    except Exception as e:
        raise RuntimeError(f"required subject extraction failed: {s}") from e

TS = np.array(TS, dtype=np.float32)
age = np.array([age_by[s] for s in ok_subs], dtype=np.float32)
sex = np.array([sex_by[s] for s in ok_subs])
assert set(ok_subs)==expected and len(ok_subs)==59, f"declared cohort incomplete: {TS.shape}"
np.savez_compressed("/opt/bundle/nki_surface_roi_timeseries.npz",
                    timeseries=TS, age=age, sex=sex, subject=np.array(ok_subs),
                    region_name=np.array(region_names), tr=np.float32(0.645))
print("built nki_surface_roi_timeseries.npz:", TS.shape, "ages", age.min(), age.max(), flush=True)
Path("/opt/bundle/cohort_manifest.json").write_text(json.dumps(manifest,indent=2))
receipt={"sources":source_receipts,"phenotypic_sha256":sha256(os.path.join(data_dir,"NKI_enhanced_surface_phenotypics.csv")),
         "atlas_left_array_sha256":hashlib.sha256(labL.tobytes()).hexdigest(),"atlas_right_array_sha256":hashlib.sha256(labR.tobytes()).hexdigest(),
         "bundle_sha256":sha256("/opt/bundle/nki_surface_roi_timeseries.npz"),"status":"observed hashes; expected raw-byte pin pending"}
Path("/opt/bundle/build_receipt.json").write_text(json.dumps(receipt,indent=2))
