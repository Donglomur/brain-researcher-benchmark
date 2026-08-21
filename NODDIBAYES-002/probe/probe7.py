"""Probe 7: single-shell (fixed d) fork convention-invariance, and 3-shell.
Does A vs B agree on fractions/count when d is FIXED (single shell) and when 3 shells?"""
import numpy as np
from scipy.optimize import least_squares
import probe as PB
unit = PB.unit


def resid_fixed_d(p, bvals, bvecs, meas, nst, dfix):
    sticks = []
    for k in range(nst):
        sticks.append((p[3*k], unit(p[3*k+1], p[3*k+2])))
    return PB.ball_stick_signal(bvals, bvecs, dfix, sticks) - meas


def fitA_fd(bvals, bvecs, meas, nst, dfix):
    cand = PB.dti_like_dirs(bvals, bvecs, meas, 300, 11)
    if nst == 1:
        v = cand[0]; p0 = [0.5, np.arccos(v[2]), np.arctan2(v[1],v[0])]
        lb=[0,0,-np.pi]; ub=[1,np.pi,np.pi]
    else:
        v1=cand[0]; v2=next((c for c in cand[1:] if abs(c@v1)<0.6), cand[3])
        p0=[0.4,np.arccos(v1[2]),np.arctan2(v1[1],v1[0]),0.3,np.arccos(v2[2]),np.arctan2(v2[1],v2[0])]
        lb=[0,0,-np.pi,0,0,-np.pi]; ub=[1,np.pi,np.pi,1,np.pi,np.pi]
    return least_squares(resid_fixed_d,p0,args=(bvals,bvecs,meas,nst,dfix),bounds=(lb,ub),max_nfev=3000)


def fitB_fd(bvals, bvecs, meas, nst, dfix):
    r=np.random.default_rng(77); best=None
    for s in range(6):
        if nst==1:
            v=PB.sphere_dirs(50,100+s)[r.integers(0,50)]
            p0=[0.4,np.arccos(v[2]),np.arctan2(v[1],v[0])]; lb=[0,0,-2*np.pi]; ub=[1,np.pi,2*np.pi]
        else:
            vv=PB.sphere_dirs(50,200+s); v1,v2=vv[r.integers(0,50)],vv[r.integers(0,50)]
            p0=[0.35,np.arccos(v1[2]),np.arctan2(v1[1],v1[0]),0.35,np.arccos(v2[2]),np.arctan2(v2[1],v2[0])]
            lb=[0,0,-2*np.pi,0,0,-2*np.pi]; ub=[1,np.pi,2*np.pi,1,np.pi,2*np.pi]
        res=least_squares(resid_fixed_d,p0,args=(bvals,bvecs,meas,nst,dfix),bounds=(lb,ub),method="dogbox",max_nfev=3000)
        if best is None or res.cost<best.cost: best=res
    return best


def parse_fd(x,nst):
    st=[(x[3*k],unit(x[3*k+1],x[3*k+2])) for k in range(nst)]
    st.sort(key=lambda t:-t[0]); return st


DFIX = 1.7e-3
# ---- single-shell b=1500, 48 dirs
for shells, ndir, tag in [([1500.], 48, "1-shell b1500 x48"), ([1000.,2000.,3000.],24,"3-shell x24")]:
    bvals,bvecs = PB.gradient_table(shells, ndir, 6, seed=5)
    print(f"\n=== {tag}: M={len(bvals)} (SNR 30) ===")
    for name, st in [("single 0.6",[(0.6,unit(np.pi/2,0))]),
                     ("cross90 0.45/0.35",[(0.45,unit(np.pi/2,0)),(0.35,unit(np.pi/2,np.pi/2))]),
                     ("cross70 0.45/0.35",[(0.45,unit(np.pi/2,0)),(0.35,unit(np.pi/2,np.radians(70)))])]:
        nst=len(st)
        fdis=[]
        for seed in range(15):
            m=PB.simulate(bvals,bvecs,DFIX,st,30,seed=400+seed)
            if shells==[1500.]:
                a=parse_fd(fitA_fd(bvals,bvecs,m,nst,DFIX).x,nst)
                b=parse_fd(fitB_fd(bvals,bvecs,m,nst,DFIX).x,nst)
            else:
                a=PB.parse(PB.fit_methodA(bvals,bvecs,m,nst).x,nst)[1]
                b=PB.parse(PB.fit_methodB(bvals,bvecs,m,nst).x,nst)[1]
            fdis.append(max(abs(a[k][0]-b[k][0]) for k in range(nst)))
        fdis=np.array(fdis)
        print(f"  {name:20s} |fA-fB| median={np.median(fdis):.4f} p90={np.percentile(fdis,90):.4f} max={np.max(fdis):.4f}")
