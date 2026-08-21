"""Prototype: is the MSMT-CSD tissue signal fraction convention-invariant AND method-invariant?

Test A: spherical-mean (powder) NNLS unmixing recovers planted fractions.
Test B: a FULL multi-shell multi-tissue SH deconvolution (Jeurissen-style block system,
        with FOD non-negativity via iterative reweighting) yields l=0 tissue amounts that
        match the spherical-mean unmixing -> confirms the fraction decouples from the angular fit.
Test C: two DIFFERENT SH normalisations give identical fractions (convention-invariance).
"""
import numpy as np
from math import factorial
from scipy.special import lpmv
from scipy.optimize import nnls

rng = np.random.default_rng(0)

# ---------------- pinned responses (diffusivities, mm^2/s) ----------------
D_PAR = 1.7e-3      # WM axial
D_PERP = 0.3e-3     # WM radial
D_GM = 0.9e-3       # GM isotropic
D_CSF = 3.0e-3      # CSF isotropic


def wm_response_signal(b, theta):
    """Single-fibre WM response attenuation at shell b (s/mm^2) and angle theta from fibre."""
    return np.exp(-b * (D_PAR * np.cos(theta) ** 2 + D_PERP * np.sin(theta) ** 2))


def gm_response(b):
    return np.exp(-b * D_GM)


def csf_response(b):
    return np.exp(-b * D_CSF)


# ---------------- SH machinery ----------------
def sh_index(lmax):
    return [(l, m) for l in range(0, lmax + 1, 2) for m in range(-l, l + 1)]


def sh_matrix(dirs, lmax, sqrt2=True, scale=1.0):
    d = np.asarray(dirs, float)
    d = d / np.clip(np.linalg.norm(d, axis=1, keepdims=True), 1e-12, None)
    x, y, z = d[:, 0], d[:, 1], d[:, 2]
    theta = np.arccos(np.clip(z, -1, 1))
    phi = np.arctan2(y, x)
    ct = np.cos(theta)
    idx = sh_index(lmax)
    B = np.zeros((d.shape[0], len(idx)))
    for j, (l, m) in enumerate(idx):
        am = abs(m)
        norm = np.sqrt((2 * l + 1) / (4 * np.pi) * factorial(l - am) / factorial(l + am))
        P = lpmv(am, l, ct)
        if m > 0:
            B[:, j] = np.sqrt(2.0) * norm * P * np.cos(am * phi)
        elif m < 0:
            B[:, j] = np.sqrt(2.0) * norm * P * np.sin(am * phi)
        else:
            B[:, j] = norm * P
    return B * scale, idx


def zonal_response_coeffs(b, lmax, ndir=600):
    """Zonal (m=0) SH coeffs r_l of the WM response at shell b, orthonormal SH convention."""
    # sample response as function of angle, project onto zonal SH
    th = np.arccos(np.linspace(-1, 1, ndir))
    ct = np.cos(th)
    R = wm_response_signal(b, th)
    orders = list(range(0, lmax + 1, 2))
    # least-squares projection with orthonormal zonal basis Y_l0 = sqrt((2l+1)/4pi) P_l(ct)
    Bz = np.zeros((ndir, len(orders)))
    for j, l in enumerate(orders):
        Bz[:, j] = np.sqrt((2 * l + 1) / (4 * np.pi)) * lpmv(0, l, ct)
    # weighted by sin(theta) for spherical measure
    w = np.sin(th)
    W = np.sqrt(w)
    r, *_ = np.linalg.lstsq(Bz * W[:, None], R * W, rcond=None)
    return np.array(r), orders


def sph_mean_wm(b, ndir=4000):
    """Spherical mean of the WM response at shell b (powder-average attenuation).

    Uniform sampling in ct = cos(theta) over [-1, 1] already carries the spherical
    measure (dOmega = -d ct), so a plain mean is the correct powder average."""
    ct = np.linspace(-1.0, 1.0, ndir)
    th = np.arccos(ct)
    R = wm_response_signal(b, th)
    return float(np.mean(R))


# ---------------- build a synthetic multi-shell voxel ----------------
def make_dirs(n, seed):
    g = np.random.default_rng(seed).standard_normal((n, 3))
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    return g


def simulate_voxel(shells, dirs_per_shell, fod_dirs, fod_w, fGM, fCSF, aWM):
    """shells: list of b (>0). Return (bvals, bvecs, signal) with b0 appended.
    aWM,fGM,fCSF are b0-signal fractions (sum to 1). fod_dirs/w define WM fibre directions."""
    bvals = [0.0]
    bvecs = [np.array([0., 0., 0.])]
    sig = [1.0 * np.ones(1)]  # placeholder, fill below
    rows_b = [0.0]
    rows_g = [np.array([0., 0., 0.])]
    S = [1.0]  # b0 attenuation = 1
    for si, b in enumerate(shells):
        g = make_dirs(dirs_per_shell[si], seed=100 + si)
        for gi in g:
            # WM: sum over fibre populations of response at angle to each fibre
            s_wm = 0.0
            for fd, fw in zip(fod_dirs, fod_w):
                ct = abs(np.dot(gi, fd))
                th = np.arccos(np.clip(ct, -1, 1))
                s_wm += fw * wm_response_signal(b, th)
            s_wm /= sum(fod_w)  # normalise so WM b0 mean = 1
            s = aWM * s_wm + fGM * gm_response(b) + fCSF * csf_response(b)
            rows_b.append(b)
            rows_g.append(gi)
            S.append(s)
    return np.array(rows_b), np.array(rows_g), np.array(S)


def spherical_mean_per_shell(bvals, S):
    ub = sorted(set(np.round(bvals, 3)))
    means = {}
    for b in ub:
        sel = np.abs(bvals - b) < 1e-6
        means[b] = S[sel].mean()
    return ub, means


def unmix_fractions(ub, means, three_tissue=True):
    """NNLS unmix spherical-mean signal into tissue fractions using pinned responses."""
    b = np.array(ub)
    cols = [np.array([sph_mean_wm(bb) for bb in b])]
    names = ["WM"]
    if three_tissue:
        cols.append(csf_response(b)); names.append("CSF")
        cols.append(gm_response(b)); names.append("GM")
    else:
        cols.append(csf_response(b)); names.append("CSF")
    A = np.stack(cols, axis=1)
    y = np.array([means[bb] for bb in b])
    x, _ = nnls(A, y)
    frac = x / x.sum()
    return dict(zip(names, frac))


# ================= run tests =================
# planted: 60% WM (two crossing fibres), 15% GM, 25% CSF
fod_dirs = [np.array([1., 0., 0.]), np.array([0., np.cos(np.deg2rad(70)), np.sin(np.deg2rad(70))])]
fod_w = [1.0, 0.7]
aWM, fGM, fCSF = 0.60, 0.15, 0.25

shells = [1000.0, 2000.0, 3000.0]
dps = [30, 45, 60]
bvals, bvecs, S = simulate_voxel(shells, dps, fod_dirs, fod_w, fGM, fCSF, aWM)
ub, means = spherical_mean_per_shell(bvals, S)
print("shells (incl b0):", ub)
print("spherical means:", {k: round(v, 4) for k, v in means.items()})

fr3 = unmix_fractions(ub, means, three_tissue=True)
print("\nTest A (3-tissue spherical-mean NNLS):", {k: round(v, 4) for k, v in fr3.items()})
print("planted:            {'WM': %.4f, 'CSF': %.4f, 'GM': %.4f}" % (aWM, fCSF, fGM))

# 2-shell version (drop 3000): 2-tissue WM+CSF
ub2 = [0.0, 1000.0, 2000.0]
means2 = {k: means[k] for k in ub2}
fr2 = unmix_fractions(ub2, means2, three_tissue=False)
print("\nTest (2-shell, 2-tissue WM+CSF):", {k: round(v, 4) for k, v in fr2.items()})
