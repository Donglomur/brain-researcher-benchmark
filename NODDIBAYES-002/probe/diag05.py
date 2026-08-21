"""Diagnose sub-05 (and sub-03) reference vs independent disagreements: is the reference stuck
in a local minimum (SSE_ref > SSE_indep -> fix init/multistart) or are the voxels genuinely
ambiguous (both find same SSE, different params -> design out)?"""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path("/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/NODDIBAYES-002")
sys.path.insert(0, str(ROOT / "solution"))
sys.path.insert(0, str(ROOT / "synth_build"))
import bas_ref as R, bas_pipeline as P
import generate_fixtures as G

for sid in ["sub-05", "sub-03"]:
    cfg = G.COHORT[sid]
    subj = P.load_subject(ROOT / "environment" / "data" / sid)
    res = P.analyze(subj)
    mask = res["mask"]; n_ref = res["maps"]["n_fibres"]
    _, vtype, _, _, _, planted, single_shell = G.build_subject(sid, cfg)
    # recompute the normalized/kept signal the reference used
    bvals, bvecs, dwi = subj["bvals"], subj["bvecs"], subj["dwi"]
    s0 = R.estimate_s0(dwi, bvals); norm = dwi / np.clip(s0, 1e-9, None)[None, :]
    dropped = res["dropped_volumes"]; keep = np.ones(dwi.shape[0], bool)
    for w in dropped: keep[w] = False
    bk, gk, nk = bvals[keep], bvecs[keep], norm[keep]
    dfix = None if P.n_shells(bk) >= 2 else float(subj["sidecar"]["fixed_diffusivity_mm2_s"])

    # find 2-fibre-truth voxels; compare reference 2-stick fit SSE to a heavy multistart SSE
    from scipy.optimize import least_squares
    def unit(t,p): s=np.sin(t); return np.array([s*np.cos(p),s*np.sin(p),np.cos(t)])
    def predict(d,st):
        S=(1-sum(f for f,_ in st))*np.exp(-bk*d)
        for f,v in st: S=S+f*np.exp(-bk*d*(gk@v)**2)
        return S
    def heavy2(meas):
        best=None
        rng=np.random.default_rng(1)
        for s in range(40):
            p0=[]; lb=[]; ub=[]
            if dfix is None: p0=[1.7e-3]; lb=[1e-4]; ub=[3.5e-3]
            for k in range(2):
                v=rng.standard_normal(3); v/=np.linalg.norm(v); t=np.arccos(v[2]); ph=np.arctan2(v[1],v[0])
                p0+=[0.35,t,ph]; lb+=[0,0,-2*np.pi]; ub+=[0.99,np.pi,2*np.pi]
            def resid(p):
                d=p[0] if dfix is None else dfix; off=1 if dfix is None else 0
                st=[(p[off+3*k],unit(p[off+3*k+1],p[off+3*k+2])) for k in range(2)]
                return predict(d,st)-meas
            r=least_squares(resid,p0,bounds=(lb,ub),method="trf",max_nfev=6000)
            if best is None or r.cost<best.cost: best=r
        return best

    idx = np.where(mask & (planted["count"] == 2))[0]
    worse = 0; ambclose = 0; nchk = 0
    for i in idx:
        meas = nk[:, i]
        # reference 2-stick
        rank1 = R._coarse_rank(meas, bk, gk); r1 = R._fit(meas, bk, gk, 1, dfix, [rank1[0]])
        _, st1, _ = R._parse(r1, 1, dfix)
        rank2 = R._coarse_rank(meas, bk, gk, exclude=st1[0][1], min_sep_cos=np.cos(np.radians(35)))
        r2 = R._fit(meas, bk, gk, 2, dfix, [st1[0][1], rank2[0]])
        sse_ref = float(np.sum(r2.fun**2))
        hb = heavy2(meas); sse_hv = float(hb.cost*2)
        nchk += 1
        if sse_ref > sse_hv * 1.02:      # reference clearly worse -> local min
            worse += 1
        if abs(sse_ref - sse_hv) < 0.02 * sse_ref:
            ambclose += 0
    print(f"{sid}: 2-fibre voxels={nchk}  reference-stuck-in-local-min (SSE_ref>1.02*SSE_heavy): {worse}")
