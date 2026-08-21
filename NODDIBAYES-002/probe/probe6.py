"""Probe 6: FINAL count criterion + full invariance.
R02 = (SSE0-SSE2)/SSE0  (isotropy gate, uses BEST model)
R21 = (SSE1-SSE2)/SSE1  (second-fibre gate)
count: R02<T02 ->0 ; elif R21<T21 ->1 ; else 2.
Report per-class R distributions AND A-vs-B count disagreements."""
import numpy as np
from scipy.optimize import least_squares
import probe as PB

bvals, bvecs = PB.gradient_table([1000., 2000.], ndir=30, n_b0=6, seed=5)


def sse0(meas):
    def r(p): return np.exp(-bvals * p[0]) - meas
    return float(np.sum(least_squares(r, [1.7e-3], bounds=([0.1e-3],[3e-3]), max_nfev=1500).fun**2))


def sse_n(meas, n, method):
    fit = PB.fit_methodA if method == "A" else PB.fit_methodB
    res = fit(bvals, bvecs, meas, n)
    return float(np.sum(res.fun**2))


def gen(kind, i, snr, seed):
    r = np.random.default_rng(seed + i)
    if kind == "iso":
        st = []
    elif kind == "single":
        st = [(r.uniform(0.50, 0.70), PB.sphere_dirs(300, 10+i)[r.integers(0,300)])]
    else:
        v1 = PB.sphere_dirs(300, 20+i)[r.integers(0,300)]
        v2 = next(c for c in PB.sphere_dirs(300, 30+i) if abs(c@v1) < np.cos(np.radians(60)))
        st = [(r.uniform(0.42, 0.55), v1), (r.uniform(0.30, 0.42), v2)]
    return PB.simulate(bvals, bvecs, 1.7e-3, st, snr, seed=7000+i)


def cnt(s0, s1, s2, T02=0.55, T21=0.50):
    if (s0 - s2)/s0 < T02: return 0
    if (s1 - s2)/max(s1,1e-12) < T21: return 1
    return 2


for SNR in [30, 40]:
    N = 40
    print(f"\n===== SNR {SNR}, {N}/type =====")
    print(f"{'kind':8s} {'R02 med':>8s} {'R02 p5':>7s} {'R02 p95':>8s} | {'R21 med':>8s} {'R21 p5':>7s} {'R21 p95':>8s}")
    stash = {}
    for k in ["iso", "single", "cross"]:
        r02, r21 = [], []
        AB = 0
        for i in range(N):
            m = gen(k, i, SNR, 111)
            s0 = sse0(m)
            s1A = sse_n(m,1,"A"); s2A = sse_n(m,2,"A")
            r02.append((s0-s2A)/s0); r21.append((s1A-s2A)/max(s1A,1e-12))
            s1B = sse_n(m,1,"B"); s2B = sse_n(m,2,"B")
            if cnt(s0,s1A,s2A) != cnt(s0,s1B,s2B): AB += 1
        r02, r21 = np.array(r02), np.array(r21)
        stash[k] = AB
        print(f"{k:8s} {np.median(r02):8.3f} {np.percentile(r02,5):7.3f} {np.percentile(r02,95):8.3f} | "
              f"{np.median(r21):8.3f} {np.percentile(r21,5):7.3f} {np.percentile(r21,95):8.3f}  A/B-disagree={AB}/{N}")
