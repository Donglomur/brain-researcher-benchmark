"""Probe 3: realistic per-subject reference fit -> (a) timing budget,
(b) corrupt-direction bite magnitude, (c) spurious-f2 distribution over a cohort
of single-fibre voxels (does the naive no-ARD pipeline fail the count/f2 panels?)."""
import time
import numpy as np
from scipy.optimize import least_squares
import probe as PB

bvals, bvecs = PB.gradient_table([1000., 2000.], ndir=30, n_b0=6, seed=5)
unit = PB.unit
dwi = bvals > 0
CAND = PB.sphere_dirs(60, 999)  # fixed candidate direction set for init


def coarse_dir(meas):
    # direction of minimal DWI signal (fibre lies along low-signal dirs)
    s = []
    for v in CAND:
        proj = np.abs(bvecs[dwi] @ v)
        near = proj > 0.85
        s.append(meas[dwi][near].mean() if near.sum() else np.inf)
    return CAND[int(np.argmin(s))]


def fit1(meas):
    v = coarse_dir(meas)
    th, ph = np.arccos(v[2]), np.arctan2(v[1], v[0])
    p0 = [1.7e-3, 0.5, th, ph]
    res = least_squares(PB.residual_n, p0, args=(bvals, bvecs, meas, 1),
                        bounds=([0.1e-3, 0, 0, -np.pi], [3e-3, 1, np.pi, np.pi]), max_nfev=2000)
    return res


def fit2(meas, v1):
    # init stick1 from 1-stick, stick2 from residual coarse dir
    r1 = fit1(meas)
    d1, st1 = PB.parse(r1.x, 1)
    resid = meas - PB.ball_stick_signal(bvals, bvecs, d1, st1)
    # second dir: min of residual-corrected — reuse coarse_dir on residual proxy
    v2 = None
    sc = []
    for v in CAND:
        if abs(v @ st1[0][1]) > 0.7:
            sc.append(np.inf); continue
        proj = np.abs(bvecs[dwi] @ v); near = proj > 0.85
        sc.append(meas[dwi][near].mean() if near.sum() else np.inf)
    v2 = CAND[int(np.argmin(sc))]
    th1, ph1 = np.arccos(st1[0][1][2]), np.arctan2(st1[0][1][1], st1[0][1][0])
    th2, ph2 = np.arccos(v2[2]), np.arctan2(v2[1], v2[0])
    p0 = [d1, st1[0][0]*0.8, th1, ph1, 0.25, th2, ph2]
    lb = [0.1e-3, 0, 0, -np.pi, 0, 0, -np.pi]
    ub = [3e-3, 1, np.pi, np.pi, 1, np.pi, np.pi]
    res = least_squares(PB.residual_n, p0, args=(bvals, bvecs, meas, 2),
                        bounds=(lb, ub), method="trf", max_nfev=3000)
    return res, r1


F_MIN = 0.15


def voxel_fit(meas):
    r2, r1 = fit2(meas, None)
    d, st2 = PB.parse(r2.x, 2)
    f1, f2 = st2[0][0], st2[1][0]
    # ARD prune
    supported = [(f, v) for f, v in st2 if f >= F_MIN]
    n = len(supported)
    if n == 2:
        return 2, st2[0][0], st2[1][0], st2[0][1], st2[1][1], d
    elif n == 1:
        d1, st1 = PB.parse(r1.x, 1)
        return 1, st1[0][0], 0.0, st1[0][1], None, d1
    else:
        return 0, 0.0, 0.0, None, None, d


# build a cohort of voxels: mix of iso, single, cross
def make_cohort(nvox, seed):
    r = np.random.default_rng(seed)
    truth = []
    for i in range(nvox):
        u = r.random()
        if u < 0.30:  # iso
            truth.append(("iso", []))
        elif u < 0.65:  # single
            f = r.uniform(0.45, 0.65)
            v = PB.sphere_dirs(200, seed + i)[r.integers(0, 200)]
            truth.append(("single", [(f, v)]))
        else:  # cross, angle >= 60
            v1 = PB.sphere_dirs(200, seed + 1000 + i)[r.integers(0, 200)]
            # second dir >= 60 deg from v1
            v2 = None
            for c in PB.sphere_dirs(200, seed + 2000 + i):
                if abs(c @ v1) < np.cos(np.radians(60)):
                    v2 = c; break
            f1 = r.uniform(0.40, 0.55); f2 = r.uniform(0.28, 0.40)
            truth.append(("cross", [(f1, v1), (f2, v2)]))
    return truth


print("=== (a) TIMING: full-subject fit, 250 voxels ===")
truth = make_cohort(250, 42)
sigs = np.array([PB.simulate(bvals, bvecs, 1.7e-3, st, 30, seed=500 + i)
                 for i, (_, st) in enumerate(truth)])
t0 = time.time()
results = [voxel_fit(sigs[i]) for i in range(len(truth))]
dt = time.time() - t0
print(f"  250 voxels fit in {dt:.1f}s  => 7 subjects ~ {dt*7:.0f}s")

# accuracy of count
cnt_true = [0 if t == "iso" else (1 if t == "single" else 2) for t, _ in truth]
cnt_fit = [r[0] for r in results]
acc = np.mean([a == b for a, b in zip(cnt_true, cnt_fit)])
print(f"  count accuracy vs truth: {acc*100:.1f}%")
# confusion
import collections
conf = collections.Counter((a, b) for a, b in zip(cnt_true, cnt_fit))
print("  confusion (true->fit):", dict(conf))

print("\n=== (c) spurious f2 on SINGLE-fibre voxels (naive no-ARD reports these) ===")
sp = [results[i] for i in range(len(truth)) if truth[i][0] == "single"]
# refit single voxels with 2-stick to see spurious f2 the naive pipeline would report
spf2 = []
for i, (t, st) in enumerate(truth):
    if t != "single":
        continue
    r2, _ = fit2(sigs[i], None)
    _, st2 = PB.parse(r2.x, 2)
    spf2.append(st2[1][0])
spf2 = np.array(spf2)
print(f"  n single={len(spf2)}  spurious f2: median={np.median(spf2):.3f} "
      f"p90={np.percentile(spf2,90):.3f} max={np.max(spf2):.3f} frac>0.10={np.mean(spf2>0.10):.2f}")

print("\n=== (b) CORRUPT-direction bite: scale one DWI by 0.1, no rejection ===")
# take clean cross voxels, corrupt one direction, fit WITHOUT rejection, measure f/angle shift
cross_idx = [i for i, (t, _) in enumerate(truth) if t == "cross"][:40]
shifts_f = []; shifts_ang = []
corrupt_dir = np.where(dwi)[0][10]  # some DWI index
for i in cross_idx:
    clean = sigs[i]
    corr = clean.copy(); corr[corrupt_dir] *= 0.1
    rc, _ = fit2(clean, None); dcln, stc = PB.parse(rc.x, 2)
    rk, _ = fit2(corr, None); dcor, stk = PB.parse(rk.x, 2)
    shifts_f.append(abs(stc[0][0] - stk[0][0]))
    shifts_f.append(abs(stc[1][0] - stk[1][0]))
    shifts_ang.append(PB.ang(stc[0][1], stk[0][1]))
print(f"  f1/f2 shift from ONE corrupt dir: median={np.median(shifts_f):.3f} "
      f"p90={np.percentile(shifts_f,90):.3f} max={np.max(shifts_f):.3f}")
print(f"  primary-orientation shift: median={np.median(shifts_ang):.1f}deg max={np.max(shifts_ang):.1f}deg")
