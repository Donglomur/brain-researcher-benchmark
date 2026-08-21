"""Feasibility probe: is the ML ball-and-stick fraction convention-invariant
across two GENUINELY DIFFERENT optimizers/inits?  If yes -> task is gradeable.
If no  -> REJECT (fractions carry a regularization/optimizer convention)."""
import numpy as np
from scipy.optimize import least_squares

rng = np.random.default_rng(0)


# ------------------------------------------------------------------ gradient table
def sphere_dirs(n, seed):
    # deterministic ~uniform directions via spiral
    r = np.random.default_rng(seed)
    idx = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * idx / n)
    gold = np.pi * (1 + 5 ** 0.5)
    theta = gold * idx
    x = np.sin(phi) * np.cos(theta)
    y = np.sin(phi) * np.sin(theta)
    z = np.cos(phi)
    d = np.stack([x, y, z], 1)
    # random rotation for variety
    return d


def gradient_table(shells, ndir, n_b0, seed):
    bvals = [0.0] * n_b0
    bvecs = [np.array([0, 0, 0.0])] * n_b0
    for si, b in enumerate(shells):
        dirs = sphere_dirs(ndir, seed + si)
        for d in dirs:
            bvals.append(b)
            bvecs.append(d)
    return np.array(bvals), np.array(bvecs)


# ------------------------------------------------------------------ forward model
def unit(theta, phi):
    return np.array([np.sin(theta) * np.cos(phi),
                     np.sin(theta) * np.sin(phi),
                     np.cos(theta)])


def ball_stick_signal(bvals, bvecs, d, sticks):
    # sticks: list of (f, v)
    iso = np.exp(-bvals * d)
    ftot = sum(f for f, v in sticks)
    S = (1 - ftot) * iso
    for f, v in sticks:
        proj = bvecs @ v
        S = S + f * np.exp(-bvals * d * proj ** 2)
    return S  # normalized by S0


def simulate(bvals, bvecs, d, sticks, snr, seed):
    S = ball_stick_signal(bvals, bvecs, d, sticks)
    sigma = 1.0 / snr
    r = np.random.default_rng(seed)
    n1 = r.normal(0, sigma, S.shape)
    n2 = r.normal(0, sigma, S.shape)
    return np.sqrt((S + n1) ** 2 + n2 ** 2)


# ------------------------------------------------------------------ fitting
def residual_n(params, bvals, bvecs, meas, nstick):
    d = params[0]
    sticks = []
    for k in range(nstick):
        f = params[1 + 3 * k]
        th = params[2 + 3 * k]
        ph = params[3 + 3 * k]
        sticks.append((f, unit(th, ph)))
    pred = ball_stick_signal(bvals, bvecs, d, sticks)
    return pred - meas


def dti_like_dirs(bvals, bvecs, meas, ncand=200, seed=1):
    # crude: find directions of minimal attenuation-adjusted signal among candidates
    cand = sphere_dirs(ncand, seed)
    dwi = bvals > 0
    # signal along each candidate: use measurements; pick dirs where signal is LOW (fibre => low signal along fibre)
    scores = []
    for v in cand:
        proj = np.abs(bvecs[dwi] @ v)
        w = np.clip(proj, 0, 1)
        # weighted mean signal near this direction
        near = w > 0.9
        if near.sum() < 1:
            scores.append(np.inf)
        else:
            scores.append(meas[dwi][near].mean())
    scores = np.array(scores)
    order = np.argsort(scores)
    return cand[order]


def fit_methodA(bvals, bvecs, meas, nstick):
    # init: DTI-like candidate dirs (low-signal directions = fibre dirs)
    cand = dti_like_dirs(bvals, bvecs, meas, ncand=300, seed=11)
    d0 = 1.7e-3
    if nstick == 1:
        v = cand[0]
        th, ph = np.arccos(v[2]), np.arctan2(v[1], v[0])
        p0 = [d0, 0.5, th, ph]
        lb = [0.1e-3, 0, 0, -np.pi]
        ub = [3e-3, 1, np.pi, np.pi]
    else:
        v1 = cand[0]
        # pick second candidate well-separated from v1
        v2 = None
        for c in cand[1:]:
            if abs(c @ v1) < 0.6:
                v2 = c
                break
        if v2 is None:
            v2 = cand[3]
        th1, ph1 = np.arccos(v1[2]), np.arctan2(v1[1], v1[0])
        th2, ph2 = np.arccos(v2[2]), np.arctan2(v2[1], v2[0])
        p0 = [d0, 0.4, th1, ph1, 0.3, th2, ph2]
        lb = [0.1e-3, 0, 0, -np.pi, 0, 0, -np.pi]
        ub = [3e-3, 1, np.pi, np.pi, 1, np.pi, np.pi]
    res = least_squares(residual_n, p0, args=(bvals, bvecs, meas, nstick),
                        bounds=(lb, ub), method="trf", max_nfev=4000)
    return res


def fit_methodB(bvals, bvecs, meas, nstick):
    # DIFFERENT init: multi-start from random dirs; DIFFERENT optimizer settings (lm-ish via 'dogbox')
    d0 = 1.9e-3
    best = None
    starts = 6
    r = np.random.default_rng(77)
    for s in range(starts):
        if nstick == 1:
            v = sphere_dirs(50, 100 + s)[r.integers(0, 50)]
            th, ph = np.arccos(v[2]), np.arctan2(v[1], v[0])
            p0 = [d0, 0.4, th, ph]
            lb = [0.1e-3, 0, 0, -2 * np.pi]
            ub = [3e-3, 1, np.pi, 2 * np.pi]
        else:
            vv = sphere_dirs(50, 200 + s)
            i1, i2 = r.integers(0, 50), r.integers(0, 50)
            v1, v2 = vv[i1], vv[i2]
            th1, ph1 = np.arccos(v1[2]), np.arctan2(v1[1], v1[0])
            th2, ph2 = np.arccos(v2[2]), np.arctan2(v2[1], v2[0])
            p0 = [d0, 0.35, th1, ph1, 0.35, th2, ph2]
            lb = [0.1e-3, 0, 0, -2 * np.pi, 0, 0, -2 * np.pi]
            ub = [3e-3, 1, np.pi, 2 * np.pi, 1, np.pi, 2 * np.pi]
        res = least_squares(residual_n, p0, args=(bvals, bvecs, meas, nstick),
                            bounds=(lb, ub), method="dogbox", max_nfev=4000)
        if best is None or res.cost < best.cost:
            best = res
    return best


def parse(params, nstick):
    d = params[0]
    sticks = []
    for k in range(nstick):
        f = params[1 + 3 * k]
        v = unit(params[2 + 3 * k], params[3 + 3 * k])
        sticks.append((f, v))
    sticks.sort(key=lambda t: -t[0])
    return d, sticks


def ang(u, v):
    c = abs(np.dot(u, v)) / (np.linalg.norm(u) * np.linalg.norm(v))
    return np.degrees(np.arccos(np.clip(c, 0, 1)))


# ------------------------------------------------------------------ experiment
bvals, bvecs = gradient_table([1000., 2000.], ndir=30, n_b0=6, seed=5)
print("n measurements:", len(bvals), "shells:", sorted(set(bvals)))

d_true = 1.7e-3
tests = [
    ("cross-orth 0.5/0.3", [(0.5, unit(np.pi/2, 0)), (0.3, unit(np.pi/2, np.pi/2))]),
    ("cross-60  0.45/0.30", [(0.45, unit(np.pi/2, 0)), (0.30, unit(np.pi/2, np.radians(60)))]),
    ("cross-45  0.45/0.30", [(0.45, unit(np.pi/2, 0)), (0.30, unit(np.pi/2, np.radians(45)))]),
    ("single   0.6",        [(0.6, unit(np.pi/2, 0))]),
]
for snr in [40, 30, 20]:
    print(f"\n===== SNR {snr} =====")
    for name, sticks_true in tests:
        nst = len(sticks_true)
        meas = simulate(bvals, bvecs, d_true, sticks_true, snr, seed=123)
        rA = fit_methodA(bvals, bvecs, meas, nst)
        rB = fit_methodB(bvals, bvecs, meas, nst)
        dA, stA = parse(rA.x, nst)
        dB, stB = parse(rB.x, nst)
        tt = sorted(sticks_true, key=lambda t: -t[0])
        line = f"{name:22s} | "
        for k in range(nst):
            line += (f"f{k+1} true={tt[k][0]:.3f} A={stA[k][0]:.3f} B={stB[k][0]:.3f} "
                     f"angA={ang(stA[k][1], tt[k][1]):.1f} angB={ang(stB[k][1], tt[k][1]):.1f} | ")
        line += f"|fA-fB|max={max(abs(stA[k][0]-stB[k][0]) for k in range(nst)):.4f}"
        print(line)
