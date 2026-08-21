"""Probe 5 (make-or-break): SSE-ratio model selection.
R21 = (SSE1-SSE2)/SSE1 ,  R10 = (SSE0-SSE1)/SSE0.
Test (i) MARGIN: iso/single/cross separated by a wide gap; (ii) INVARIANCE:
methods A and B agree on R (objective value), hence on the count."""
import numpy as np
from scipy.optimize import least_squares
import probe as PB

bvals, bvecs = PB.gradient_table([1000., 2000.], ndir=30, n_b0=6, seed=5)
unit = PB.unit
dwi = bvals > 0


def sse0(meas):
    def r(p): return np.exp(-bvals * p[0]) - meas
    return float(np.sum(least_squares(r, [1.7e-3], bounds=([0.1e-3],[3e-3]), max_nfev=1500).fun**2))


def sse_n(meas, n, method):
    fit = PB.fit_methodA if method == "A" else PB.fit_methodB
    res = fit(bvals, bvecs, meas, n)
    return float(np.sum(res.fun**2)), res


def gen(kind, i, snr, seed):
    r = np.random.default_rng(seed + i)
    if kind == "iso":
        st = []
    elif kind == "single":
        f = r.uniform(0.45, 0.70); v = PB.sphere_dirs(300, 10+i)[r.integers(0,300)]
        st = [(f, v)]
    else:
        v1 = PB.sphere_dirs(300, 20+i)[r.integers(0,300)]
        v2 = None
        for c in PB.sphere_dirs(300, 30+i):
            if abs(c@v1) < np.cos(np.radians(60)): v2 = c; break
        st = [(r.uniform(0.42, 0.55), v1), (r.uniform(0.30, 0.42), v2)]
    return PB.simulate(bvals, bvecs, 1.7e-3, st, snr, seed=7000+i)


SNR = 35
N = 40
data = {k: [gen(k, i, SNR, 111) for i in range(N)] for k in ["iso", "single", "cross"]}

print(f"SNR={SNR}, {N} voxels/type\n")
print(f"{'kind':8s} {'R10 med':>8s} {'R10 p5':>7s} {'R10 p95':>8s} | {'R21 med':>8s} {'R21 p5':>7s} {'R21 p95':>8s}")
R = {}
for k in ["iso", "single", "cross"]:
    r10s, r21s = [], []
    for m in data[k]:
        s0 = sse0(m); s1, _ = sse_n(m, 1, "A"); s2, _ = sse_n(m, 2, "A")
        r10s.append((s0 - s1) / s0); r21s.append((s1 - s2) / max(s1, 1e-12))
    r10s, r21s = np.array(r10s), np.array(r21s)
    R[k] = (r10s, r21s)
    print(f"{k:8s} {np.median(r10s):8.3f} {np.percentile(r10s,5):7.3f} {np.percentile(r10s,95):8.3f} | "
          f"{np.median(r21s):8.3f} {np.percentile(r21s,5):7.3f} {np.percentile(r21s,95):8.3f}")

# invariance of the DECISION between A and B, using pinned thresholds
T10, T21 = 0.50, 0.50
print(f"\nA-vs-B COUNT agreement with T10={T10} T21={T21}:")
for k in ["iso", "single", "cross"]:
    dis = 0
    for m in data[k]:
        s0 = sse0(m)
        s1A,_ = sse_n(m,1,"A"); s2A,_ = sse_n(m,2,"A")
        s1B,_ = sse_n(m,1,"B"); s2B,_ = sse_n(m,2,"B")
        def cnt(s0,s1,s2):
            if (s0-s1)/s0 < T10: return 0
            if (s1-s2)/max(s1,1e-12) < T21: return 1
            return 2
        if cnt(s0,s1A,s2A) != cnt(s0,s1B,s2B): dis += 1
    print(f"  {k:8s}: {dis}/{N} disagreements")
