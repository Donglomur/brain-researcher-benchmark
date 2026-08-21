"""Where exactly do reference and independent disagree on sub-05? Boundary (borderline count)
or genuine 2-fibre voxels? And is it the independent impl being under-powered?"""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path("/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/NODDIBAYES-002")
sys.path.insert(0, str(ROOT / "solution")); sys.path.insert(0, str(ROOT / "synth_build"))
import bas_pipeline as P, generate_fixtures as G

sid = "sub-05"
res = P.analyze(P.load_subject(ROOT / "environment" / "data" / sid))
mask = res["mask"]; n_ref = np.asarray(res["maps"]["n_fibres"], int)
gi = {m: np.load(f"/tmp/bas_indep/{sid}/{m}.npy") for m in ["n_fibres","f1","f2","v1","v2"]}
n_ind = np.asarray(gi["n_fibres"], int)
_, vtype, _, _, _, planted, _ = G.build_subject(sid, G.COHORT[sid])
tcount = planted["count"]

dis = mask & (n_ref != n_ind)
print(f"sub-05 count disagreements: {dis.sum()} / {mask.sum()} masked")
for i in np.where(dis)[0]:
    print(f"  vox {i}: true={tcount[i]} ref={n_ref[i]} ind={n_ind[i]}  "
          f"ref_f=({res['maps']['f1'][i]:.2f},{res['maps']['f2'][i]:.2f}) "
          f"ind_f=({gi['f1'][i]:.2f},{gi['f2'][i]:.2f})")
# v2 disagreements on ref-count==2
s2 = mask & (n_ref == 2)
def acute(g,r):
    g=g/(np.linalg.norm(g)+1e-12); r=r/(np.linalg.norm(r)+1e-12); return np.degrees(np.arccos(np.clip(abs(g@r),0,1)))
bad=[]
for i in np.where(s2)[0]:
    a=acute(gi["v2"][i], res["maps"]["v2"][i])
    if a>15: bad.append((i,tcount[i],round(a,1), round(res['maps']['f2'][i],2), round(float(gi['f2'][i]),2)))
print(f"v2 disagreements (>15deg) on ref-count==2: {len(bad)} / {s2.sum()}")
for b in bad: print("  vox",b)
