import numpy as np
import physics as P
from mc import schedule, add_noise, detect_motion, HALF

for seed in range(40, 45):
    dur, start = schedule(90.0); tmid = start + dur/2; half = HALF["F-18"]; fs = start
    tf = P.fine_grid(dur); edges = np.concatenate([[0.0], np.cumsum(dur)])
    cp_fine = P.feng_plasma(tf, 1.0)
    rng = np.random.default_rng(seed)
    vox = [(0.36,0.11,0.055,0.0),(0.30,0.10,0.040,0.0),(0.42,0.12,0.070,0.0),
           (0.50,0.10,0.060,0.030),(0.45,0.12,0.050,0.040),(0.55,0.11,0.080,0.025)]
    tacs=[]
    for (K1,k2,k3,k4) in vox:
        ct_true=P.forward_2tc(cp_fine,tf,edges,K1,k2,k3,k4)
        tacs.append(add_noise(ct_true,tmid,dur,0.28,half,rng))
    cand=np.where(fs>=40.0)[0]; mf=sorted([cand[len(cand)//3],cand[2*len(cand)//3],cand[-1]])
    fac={mf[0]:0.5,mf[1]:0.55,mf[2]:0.45}
    mt=[t.copy() for t in tacs]
    for t in mt:
        for f,fc in fac.items(): t[f]*=fc
    g=np.mean(mt,axis=0)
    keep=detect_motion(g,fs,20.0)
    det=set(np.where(~keep)[0])
    print(f"seed {seed} planted {mf} detected {sorted(det)}  window frames {list(np.where(fs>=20.0)[0])}")
