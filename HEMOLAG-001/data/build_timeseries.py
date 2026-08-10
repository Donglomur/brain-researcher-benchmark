"""Stroke hemodynamic-lag Step-0 on OpenNeuro ds003999 (29 post-stroke patients, ses-pre rest, TR=3s).
Direct-S3 download + hemolag_worker (cache ROI timeseries, subprocess timeout) + within-patient lag
analysis (Siegel 2016): does lag-correction recover the zero-lag FC 'deficit' in lagged regions?"""
import warnings; warnings.filterwarnings("ignore")
import os, socket, subprocess, time, urllib.request, numpy as np
socket.setdefaulttimeout(120)
BASE="https://s3.amazonaws.com/openneuro.org/ds003999"; OUT="stroke"; os.makedirs(OUT, exist_ok=True)
HERE=os.path.dirname(os.path.abspath(__file__)); CACHE=f"{OUT}/ts_cache.npz"; TR=3.0; TIMEOUT=160
SUBS=("sub-00 sub-01 sub-02 sub-03 sub-05 sub-07 sub-10 sub-11 sub-12 sub-13 sub-14 sub-15 sub-16 "
      "sub-17 sub-18 sub-20 sub-21 sub-22 sub-23 sub-24 sub-25 sub-26 sub-27 sub-28 sub-29 sub-30 "
      "sub-33 sub-34 sub-35").split()

def dl(sub):
    f=f"{OUT}/{sub}.nii.gz"
    if os.path.exists(f) and os.path.getsize(f)>1e6: return f
    url=f"{BASE}/{sub}/ses-pre/func/{sub}_ses-pre_task-rest_bold.nii.gz"
    for att in range(4):
        try:
            urllib.request.urlretrieve(url, f)
            if os.path.getsize(f)>1e6: return f
        except Exception:
            try: os.remove(f)
            except: pass
            time.sleep(3*(att+1))
    return None

cache=dict(np.load(CACHE, allow_pickle=True)) if os.path.exists(CACHE) else {}
print(f"start: {len(cache)} cached; {len(SUBS)} patients", flush=True)
for s in SUBS:
    if s in cache: continue
    f=dl(s)
    if not f: print("  dl-fail",s,flush=True); continue
    o=f"{OUT}/{s}_ts.npy"
    try:
        subprocess.run(["python3",f"{HERE}/hemolag_worker.py",f,o,str(TR)],timeout=TIMEOUT,capture_output=True)
        if os.path.exists(o):
            cache[s]=np.load(o); np.savez(CACHE,**cache); print(f"  done {s} [{len(cache)}/{len(SUBS)}]",flush=True)
        else: print(f"  worker-nofc {s}",flush=True)
    except subprocess.TimeoutExpired: print(f"  timeout {s}",flush=True)

print(f"\nusable subjects: {len(cache)}", flush=True)
import importlib.util
spec=importlib.util.spec_from_file_location("hla", f"{HERE}/hemolag_analysis.py")
hla=importlib.util.module_from_spec(spec); spec.loader.exec_module(hla)
hla.analyse(cache, TR, maxlag_s=9.0)
print("DONE", flush=True)
