"""Probe 2: (a) model-selection margin for the fibre COUNT (0/1/2),
(b) fragile envelope (small crossing angle, small f2) to define the SAFE design,
(c) d agreement, (d) isotropic (0-fibre) detection."""
import numpy as np
from scipy.optimize import least_squares
import probe as PB  # reuse forward model + fitting

bvals, bvecs = PB.gradient_table([1000., 2000.], ndir=30, n_b0=6, seed=5)
unit = PB.unit


def fit(meas, nstick):
    return PB.fit_methodA(bvals, bvecs, meas, nstick)


def sse(res):
    return float(np.sum(res.fun ** 2))


def fit0(meas):
    # 0-stick (pure ball): fit only d
    from scipy.optimize import least_squares as ls
    def r(p):
        d = p[0]
        return np.exp(-bvals * d) - meas
    res = ls(r, [1.7e-3], bounds=([0.1e-3], [3e-3]), max_nfev=2000)
    return res


M = len(bvals)
print(f"M={M} measurements\n")

# ---- (a)+(d) model selection margins: SSE for 0/1/2-stick fits on each true type
print("=== SSE reduction across nested models (SNR 30) ===")
print(f"{'truth':26s} {'sse0':>9s} {'sse1':>9s} {'sse2':>9s} {'1vs0 %':>8s} {'2vs1 %':>8s} {'f2@2stick':>10s}")
cases = [
    ("iso (0 fibre)",       1.7e-3, []),
    ("single f=0.5",        1.7e-3, [(0.5, unit(np.pi/2, 0))]),
    ("single f=0.6",        1.7e-3, [(0.6, unit(np.pi/2, 0))]),
    ("single f=0.7",        1.7e-3, [(0.7, unit(np.pi/2, 0))]),
    ("cross90 0.4/0.35",    1.7e-3, [(0.4, unit(np.pi/2,0)), (0.35, unit(np.pi/2,np.pi/2))]),
    ("cross90 0.45/0.30",   1.7e-3, [(0.45, unit(np.pi/2,0)), (0.30, unit(np.pi/2,np.pi/2))]),
    ("cross60 0.45/0.30",   1.7e-3, [(0.45, unit(np.pi/2,0)), (0.30, unit(np.pi/2,np.radians(60)))]),
]
for name, d, st in cases:
    meas = PB.simulate(bvals, bvecs, d, st, 30, seed=321)
    r0, r1, r2 = fit0(meas), fit(meas, 1), fit(meas, 2)
    s0, s1, s2 = sse(r0), sse(r1), sse(r2)
    _, st2 = PB.parse(r2.x, 2)
    f2 = st2[1][0]
    print(f"{name:26s} {s0:9.4f} {s1:9.4f} {s2:9.4f} {100*(s0-s1)/s0:8.1f} {100*(s1-s2)/s1:8.2f} {f2:10.3f}")

# ---- (b) fragile envelope: how small a crossing angle / f2 stays convention-invariant?
print("\n=== fragile envelope: f_A vs f_B agreement at hard geometries (SNR 30) ===")
print(f"{'geom':30s} {'f2true':>7s} {'f2_A':>7s} {'f2_B':>7s} {'|dA-dB|f':>9s} {'angErr2':>8s}")
frag = [
    ("cross30 0.45/0.30", [(0.45, unit(np.pi/2,0)), (0.30, unit(np.pi/2,np.radians(30)))]),
    ("cross40 0.45/0.30", [(0.45, unit(np.pi/2,0)), (0.30, unit(np.pi/2,np.radians(40)))]),
    ("cross90 0.5/0.10",  [(0.5, unit(np.pi/2,0)), (0.10, unit(np.pi/2,np.pi/2))]),
    ("cross90 0.5/0.15",  [(0.5, unit(np.pi/2,0)), (0.15, unit(np.pi/2,np.pi/2))]),
    ("cross90 0.5/0.20",  [(0.5, unit(np.pi/2,0)), (0.20, unit(np.pi/2,np.pi/2))]),
]
for name, st in frag:
    meas = PB.simulate(bvals, bvecs, 1.7e-3, st, 30, seed=321)
    rA = PB.fit_methodA(bvals, bvecs, meas, 2)
    rB = PB.fit_methodB(bvals, bvecs, meas, 2)
    dA, stA = PB.parse(rA.x, 2)
    dB, stB = PB.parse(rB.x, 2)
    tt = sorted(st, key=lambda t: -t[0])
    print(f"{name:30s} {tt[1][0]:7.3f} {stA[1][0]:7.3f} {stB[1][0]:7.3f} "
          f"{abs(stA[1][0]-stB[1][0]):9.4f} {PB.ang(stA[1][1], tt[1][1]):8.1f}")

# ---- (c) d agreement on a clean 2-fibre voxel across SNR
print("\n=== diffusivity d agreement (cross90 0.45/0.30) ===")
for snr in [40, 30, 20]:
    st = [(0.45, unit(np.pi/2,0)), (0.30, unit(np.pi/2,np.pi/2))]
    meas = PB.simulate(bvals, bvecs, 1.7e-3, st, snr, seed=321)
    rA, rB = PB.fit_methodA(bvals, bvecs, meas, 2), PB.fit_methodB(bvals, bvecs, meas, 2)
    print(f"  SNR{snr}: dA={rA.x[0]*1e3:.4f}e-3 dB={rB.x[0]*1e3:.4f}e-3 |dA-dB|={abs(rA.x[0]-rB.x[0])*1e3:.5f}e-3")
