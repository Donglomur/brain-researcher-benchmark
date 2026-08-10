"""Robust CNP diagnostic-non-specificity Step-0. Downloads (with timeout+retry) + registers each subject
in a SUBPROCESS with a hard 150s timeout (so a hung dipy registration is killed, not fatal). Reuses the
per-subject FC cache. Then: does a schizophrenia-vs-control connectome classifier also separate bipolar
and ADHD from controls (= non-specific)?"""
import warnings; warnings.filterwarnings("ignore")
import os, io, csv, socket, subprocess, time, urllib.request, numpy as np
socket.setdefaulttimeout(90)
BASE="https://s3.amazonaws.com/openneuro.org/ds000030"; OUT="on_test"; os.makedirs(OUT, exist_ok=True)
CACHE=f"{OUT}/fc_cache2.npz"; PER=30; TIMEOUT=150
HERE=os.path.dirname(os.path.abspath(__file__))

def dl(sub):
    f=f"{OUT}/{sub}_rest.nii.gz"
    if os.path.exists(f) and os.path.getsize(f)>1e6: return f
    for attempt in range(4):
        try:
            urllib.request.urlretrieve(f"{BASE}/{sub}/func/{sub}_task-rest_bold.nii.gz", f); return f
        except Exception:
            try: os.remove(f)
            except: pass
            time.sleep(3 * (attempt + 1))
    return None

plocal=f"{OUT}/participants.tsv"
if os.path.exists(plocal):
    pt=open(plocal).read()
else:
    pt=urllib.request.urlopen(f"{BASE}/participants.tsv").read().decode(); open(plocal,"w").write(pt)
rows=[r for r in csv.DictReader(io.StringIO(pt), delimiter="\t") if r.get("rest")=="1"]
groups={"CONTROL":[],"SCHZ":[],"BIPOLAR":[],"ADHD":[]}
for r in rows:
    if r["diagnosis"] in groups: groups[r["diagnosis"]].append(r["participant_id"])
sel=[(s,g) for g in groups for s in groups[g][:PER]]
cache=dict(np.load(CACHE, allow_pickle=True)) if os.path.exists(CACHE) else {}
print(f"start: {len(cache)} cached; targeting {len(sel)} subjects", flush=True)

for s,g in sel:
    if s in cache: continue
    f=dl(s)
    if not f: print("  dl-fail", s, flush=True); continue
    outp=f"{OUT}/{s}_fc.npy"
    try:
        subprocess.run(["python3", f"{HERE}/cnp_worker.py", f, outp], timeout=TIMEOUT,
                       capture_output=True)
        if os.path.exists(outp):
            cache[s]=np.load(outp); np.savez(CACHE, **cache)
            print(f"  done {s} ({g}) [{len(cache)}/{len(sel)}]", flush=True)
        else:
            print(f"  worker-nofc {s}", flush=True)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT-skip {s} ({g})", flush=True)

# ---- analysis ----
X=[]; y=[]
for s,g in sel:
    if s in cache: X.append(cache[s]); y.append(g)
X=np.array(X); y=np.array(y)
print(f"\nusable: {X.shape}", {g:int((y==g).sum()) for g in groups}, flush=True)
if X.shape[0]<20 or (y=="SCHZ").sum()<6:
    print("INSUFFICIENT DATA"); raise SystemExit

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score

def within_auc(pos):
    m=(y=="CONTROL")|(y==pos); Xm=X[m]; ym=(y[m]==pos).astype(int)
    if ym.sum()<5: return np.nan
    pipe=make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=3000))
    pr=cross_val_predict(pipe, Xm, ym, cv=StratifiedKFold(5,shuffle=True,random_state=0), method="predict_proba")[:,1]
    return roc_auc_score(ym, pr)

# SCHZ-trained model, applied to other disorders vs control (transfer)
sm=(y=="CONTROL")|(y=="SCHZ")
clf=make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=3000)).fit(X[sm], (y[sm]=="SCHZ").astype(int))
def transfer_auc(pos):
    m=(y=="CONTROL")|(y==pos)
    if (y[m]==pos).sum()<5: return np.nan
    return roc_auc_score((y[m]==pos).astype(int), clf.decision_function(X[m]))

print("\n[within-disorder CV AUC vs CONTROL]  SCHZ=%.2f BIPOLAR=%.2f ADHD=%.2f"%(within_auc("SCHZ"),within_auc("BIPOLAR"),within_auc("ADHD")), flush=True)
print("[SCHZ-trained model TRANSFERRED vs CONTROL] SCHZ(self)=%.2f BIPOLAR=%.2f ADHD=%.2f"%(transfer_auc("SCHZ"),transfer_auc("BIPOLAR"),transfer_auc("ADHD")), flush=True)
print("NON-SPECIFIC if the SCHZ model also separates BIPOLAR/ADHD from controls (AUC>>0.5).")
print("DONE", flush=True)
