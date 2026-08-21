"""Prototype 2: convention/method invariance of MSMT-CSD tissue fractions.
Compare THREE ways to get fractions on the SAME data:
  (M1) arithmetic spherical-mean per shell -> 3-tissue NNLS with pinned powder columns
  (M2) per-shell SH l=0 coefficient (direction-robust powder) -> same NNLS
  (M3) FULL multishell multitissue SH block least-squares -> l=0 tissue amounts
Uses UNIFORM (spiral/Jones) directions. If all three agree tightly AND recover planted,
the fraction is well-determined + convention-invariant.
"""
import numpy as np
from math import factorial
from scipy.special import lpmv
from scipy.optimize import nnls

D_PAR, D_PERP, D_GM, D_CSF = 1.7e-3, 0.3e-3, 0.9e-3, 3.0e-3


def wm_resp(b, theta):
    return np.exp(-b * (D_PAR * np.cos(theta) ** 2 + D_PERP * np.sin(theta) ** 2))


def gm_resp(b):  return np.exp(-b * D_GM)
def csf_resp(b): return np.exp(-b * D_CSF)


def powder_wm(b, n=8000):
    ct = np.linspace(-1, 1, n)
    return float(np.mean(wm_resp(b, np.arccos(ct))))


# ---- uniform directions on the sphere (electrostatic-ish via golden spiral) ----
def uniform_dirs(n, jitter_seed=None):
    k = np.arange(n) + 0.5
    z = 1.0 - 2.0 * k / n
    phi = k * np.pi * (3.0 - np.sqrt(5.0))
    r = np.sqrt(np.clip(1 - z * z, 0, None))
    d = np.stack([r * np.cos(phi), r * np.sin(phi), z], axis=1)
    if jitter_seed is not None:
        rng = np.random.default_rng(jitter_seed)
        d = d + 0.02 * rng.standard_normal(d.shape)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
    return d


# ---- SH ----
def sh_index(lmax): return [(l, m) for l in range(0, lmax + 1, 2) for m in range(-l, l + 1)]


def sh_matrix(dirs, lmax):
    d = dirs / np.clip(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-12, None)
    x, y, z = d[:, 0], d[:, 1], d[:, 2]
    theta = np.arccos(np.clip(z, -1, 1)); phi = np.arctan2(y, x); ct = np.cos(theta)
    idx = sh_index(lmax); B = np.zeros((d.shape[0], len(idx)))
    for j, (l, m) in enumerate(idx):
        am = abs(m)
        norm = np.sqrt((2 * l + 1) / (4 * np.pi) * factorial(l - am) / factorial(l + am))
        P = lpmv(am, l, ct)
        if m > 0:   B[:, j] = np.sqrt(2) * norm * P * np.cos(am * phi)
        elif m < 0: B[:, j] = np.sqrt(2) * norm * P * np.sin(am * phi)
        else:       B[:, j] = norm * P
    return B, idx


def wm_zonal(b, lmax, n=8000):
    """zonal r_l (orthonormal) of WM response at shell b."""
    ct = np.linspace(-1, 1, n); R = wm_resp(b, np.arccos(ct))
    orders = list(range(0, lmax + 1, 2))
    Bz = np.stack([np.sqrt((2 * l + 1) / (4 * np.pi)) * lpmv(0, l, ct) for l in orders], axis=1)
    # orthonormal on uniform-ct measure: <Y_l0,Y_l0> = integral = 1 over full sphere -> use mean*2?
    # project: r_l = 2*pi*integral R Y_l0 dct ... simpler: least squares
    r, *_ = np.linalg.lstsq(Bz, R, rcond=None)
    return np.array(r), orders


def simulate(shells, ndirs, fod_dirs, fod_w, aWM, fGM, fCSF, seed=0, corrupt=None):
    bvals = [0.0, 0.0]; bvecs = [[0, 0, 0], [0, 0, 0]]; S = [1.0, 1.0]
    for si, b in enumerate(shells):
        g = uniform_dirs(ndirs[si], jitter_seed=seed + si)
        for j, gi in enumerate(g):
            s_wm = 0.0
            for fd, fw in zip(fod_dirs, fod_w):
                th = np.arccos(np.clip(abs(gi @ fd), -1, 1)); s_wm += fw * wm_resp(b, th)
            s_wm /= sum(fod_w)
            s = aWM * s_wm + fGM * gm_resp(b) + fCSF * csf_resp(b)
            bvals.append(b); bvecs.append(gi); S.append(s)
    return np.array(bvals), np.array(bvecs, float), np.array(S)


def shells_of(bvals):
    ub = []
    for b in np.unique(np.round(bvals)):
        if b < 50: continue
        ub.append(float(b))
    return sorted(ub)


def frac_M1(bvals, S, three):
    ub = shells_of(bvals)
    sbar = np.array([S[np.abs(bvals - b) < 1e-6].mean() for b in ub])
    A = [np.array([powder_wm(b) for b in ub])]
    names = ["WM"]
    A.append(csf_resp(np.array(ub))); names.append("CSF")
    if three: A.append(gm_resp(np.array(ub))); names.append("GM")
    A = np.stack(A, 1)
    # add b0 row (=1 for all tissues, sbar=1)
    A = np.vstack([np.ones(A.shape[1]), A]); yv = np.concatenate([[1.0], sbar])
    x, _ = nnls(A, yv); return dict(zip(names, x / x.sum()))


def frac_M2(bvals, bvecs, S, three):
    ub = shells_of(bvals)
    sbar = []
    for b in ub:
        sel = np.abs(bvals - b) < 1e-6
        B, idx = sh_matrix(bvecs[sel], 0)  # l=0 only -> DC
        c, *_ = np.linalg.lstsq(B, S[sel], rcond=None)
        sbar.append(c[0] / np.sqrt(4 * np.pi))  # l=0 coeff * Y00 = mean
    sbar = np.array(sbar)
    A = [np.array([powder_wm(b) for b in ub])]; names = ["WM"]
    A.append(csf_resp(np.array(ub))); names.append("CSF")
    if three: A.append(gm_resp(np.array(ub))); names.append("GM")
    A = np.stack(A, 1); A = np.vstack([np.ones(A.shape[1]), A]); yv = np.concatenate([[1.0], sbar])
    x, _ = nnls(A, yv); return dict(zip(names, x / x.sum()))


def frac_M3(bvals, bvecs, S, three, lmax=8):
    """Full multishell multitissue SH block least squares -> l=0 amounts -> fractions."""
    ub = shells_of(bvals)
    idx = sh_index(lmax); ncoef = len(idx)
    cols = []  # design columns
    # WM: ncoef columns; GM: 1; CSF: 1
    rows_sig = []
    # build measurement rows: b0 + each shell dir
    b0sel = bvals < 50
    meas_idx = list(np.where(b0sel)[0]) + [i for i in range(len(bvals)) if not b0sel[i]]
    M = []
    y = []
    ntis = 3 if three else 2
    for i in range(len(bvals)):
        b = bvals[i]; g = bvecs[i]
        row = np.zeros(ncoef + ntis)
        if b < 50:
            # b0: WM l=0 conv factor with r0(0); GM/CSF response(0)=1
            r0, orders = wm_zonal(0.0, lmax)
            B, _ = sh_matrix(g[None, :] if np.linalg.norm(g) > 0 else np.array([[0, 0, 1.]]), lmax)
            conv = np.array([np.sqrt(4 * np.pi / (2 * l + 1)) * r0[orders.index(l)] for (l, m) in idx])
            row[:ncoef] = B[0] * conv
            row[ncoef + 0] = gm_resp(0.0) if three else csf_resp(0.0)
            if three:
                row[ncoef + 1] = csf_resp(0.0); row[ncoef + 2] = 0  # placeholder
            # careful ordering below
        M.append(None)  # rebuild cleanly below
    # cleaner rebuild:
    return _frac_M3_clean(bvals, bvecs, S, ub, three, lmax)


def _frac_M3_clean(bvals, bvecs, S, ub, three, lmax):
    idx = sh_index(lmax); ncoef = len(idx); orders = list(range(0, lmax + 1, 2))
    names = ["WM", "GM", "CSF"] if three else ["WM", "CSF"]
    nt = len(names)
    rows = []; y = []
    for i in range(len(bvals)):
        b = bvals[i]; g = bvecs[i]
        row = np.zeros(ncoef + (nt - 1))  # WM SH coefs + (nt-1) iso amounts
        r0, ords = wm_zonal(b, lmax)
        if np.linalg.norm(g) < 1e-9:
            g = np.array([0, 0, 1.0])
        B, _ = sh_matrix(g[None, :], lmax)
        conv = np.array([np.sqrt(4 * np.pi / (2 * l + 1)) * r0[ords.index(l)] for (l, m) in idx])
        row[:ncoef] = B[0] * conv
        col = ncoef
        for t in names[1:]:
            row[col] = gm_resp(b) if t == "GM" else csf_resp(b)
            col += 1
        rows.append(row); y.append(S[i])
    M = np.array(rows); y = np.array(y)
    sol, *_ = np.linalg.lstsq(M, y, rcond=None)
    # WM b0-signal amount = l=0 coef * powder_wm(0)/... actually mean b0 WM = f00 * Y00 * conv0 mean
    # simpler: WM b0 signal contribution = f00 * sqrt(4pi/1)*r0(0) * (1/sqrt4pi) = f00*r0(0)
    r0_0, ords0 = wm_zonal(0.0, lmax)
    wm_amt = sol[0] * r0_0[0]  # f00 * r_{l0}(0) ; but r0(0) with orthonormal... check scale
    iso = sol[ncoef:]
    amts = [wm_amt] + list(iso)
    amts = np.clip(amts, 0, None)
    return dict(zip(names, np.array(amts) / np.sum(amts)))


# ===== run =====
fod = [np.array([1., 0, 0]), np.array([0, np.cos(np.deg2rad(70)), np.sin(np.deg2rad(70))])]
fw = [1.0, 0.7]
aWM, fGM, fCSF = 0.60, 0.15, 0.25
shells = [1000., 2000., 3000.]; ndirs = [45, 60, 64]
bvals, bvecs, S = simulate(shells, ndirs, fod, fw, aWM, fGM, fCSF, seed=3)
print("planted: WM=%.3f GM=%.3f CSF=%.3f" % (aWM, fGM, fCSF))
print("M1 arith-mean:", {k: round(v, 4) for k, v in frac_M1(bvals, S, True).items()})
print("M2 SH-l0     :", {k: round(v, 4) for k, v in frac_M2(bvals, bvecs, S, True).items()})
print("M3 full-block:", {k: round(v, 4) for k, v in _frac_M3_clean(bvals, bvecs, S, shells, True, 8).items()})
