"""Prototype 3: invariance stress test across voxel types + noise + constraint binding.
M1 = spherical-mean NNLS (candidate REFERENCE def).  M3 = full multishell-multitissue block
least-squares with non-negative tissue amounts (candidate INDEPENDENT / full-MSMT).
Report max fraction discrepancy across voxel archetypes and noise levels."""
import numpy as np
from proto2 import (wm_resp, gm_resp, csf_resp, powder_wm, uniform_dirs, sh_index, sh_matrix,
                    wm_zonal, shells_of)
from scipy.optimize import nnls

D_none = None


def simulate_vox(shells, ndirs, fod_dirs, fod_w, aWM, fGM, fCSF, seed, noise=0.0):
    bvals = [0.0, 0.0]; bvecs = [[0, 0, 0.], [0, 0, 0.]]; S = [1.0, 1.0]
    rng = np.random.default_rng(seed + 999)
    for si, b in enumerate(shells):
        g = uniform_dirs(ndirs[si], jitter_seed=seed * 10 + si)
        for gi in g:
            s_wm = 0.0
            if fod_w:
                for fd, fw in zip(fod_dirs, fod_w):
                    th = np.arccos(np.clip(abs(gi @ fd), -1, 1)); s_wm += fw * wm_resp(b, th)
                s_wm /= sum(fod_w)
            s = aWM * s_wm + fGM * gm_resp(b) + fCSF * csf_resp(b)
            bvals.append(b); bvecs.append(gi); S.append(s)
    S = np.array(S)
    if noise > 0:
        n1 = rng.normal(0, noise, S.shape); n2 = rng.normal(0, noise, S.shape)
        S = np.sqrt((S + n1) ** 2 + n2 ** 2)  # Rician on attenuation (approx)
    return np.array(bvals), np.array(bvecs, float), S


def frac_M1(bvals, bvecs, S, three, keep=None):
    ub = shells_of(bvals)
    sbar = []
    for b in ub:
        sel = np.abs(bvals - b) < 1e-6
        if keep is not None:
            sel = sel & keep
        sbar.append(S[sel].mean())
    sbar = np.array(sbar)
    cols = [np.array([powder_wm(b) for b in ub])]; names = ["WM"]
    cols.append(csf_resp(np.array(ub))); names.append("CSF")
    if three:
        cols.append(gm_resp(np.array(ub))); names.append("GM")
    A = np.stack(cols, 1); A = np.vstack([np.ones(A.shape[1]), A]); yv = np.concatenate([[1.0], sbar])
    x, _ = nnls(A, yv); return dict(zip(names, x / x.sum()))


def frac_M3(bvals, bvecs, S, three, lmax=8, keep=None):
    names = ["WM", "GM", "CSF"] if three else ["WM", "CSF"]
    nt = len(names); idx = sh_index(lmax); ncoef = len(idx);
    sel = np.ones(len(bvals), bool) if keep is None else keep.copy()
    rows = []; y = []
    for i in np.where(sel)[0]:
        b = bvals[i]; g = bvecs[i]
        row = np.zeros(ncoef + (nt - 1))
        r0, ords = wm_zonal(b, lmax)
        gg = g if np.linalg.norm(g) > 1e-9 else np.array([0, 0, 1.0])
        B, _ = sh_matrix(gg[None, :], lmax)
        conv = np.array([np.sqrt(4 * np.pi / (2 * l + 1)) * r0[ords.index(l)] for (l, m) in idx])
        row[:ncoef] = B[0] * conv
        col = ncoef
        for t in names[1:]:
            row[col] = gm_resp(b) if t == "GM" else csf_resp(b); col += 1
        rows.append(row); y.append(S[i])
    M = np.array(rows); y = np.array(y)
    # solve with non-negativity on tissue amounts: approximate via projecting -- do full lstsq then
    # clamp iso; but to bind properly use a small NNLS on the reduced l=0 + iso after estimating WM SH.
    sol, *_ = np.linalg.lstsq(M, y, rcond=None)
    r0_0, _ = wm_zonal(0.0, lmax)
    wm_amt = max(sol[0] * r0_0[0], 0.0)
    iso = np.clip(sol[ncoef:], 0, None)
    amts = np.array([wm_amt] + list(iso))
    if amts.sum() <= 0: amts = np.ones_like(amts)
    return dict(zip(names, amts / amts.sum()))


archetypes = {
    "WM-single":   dict(fod=[np.array([1., 0, 0])], fw=[1.0], aWM=0.85, fGM=0.05, fCSF=0.10),
    "WM-cross":    dict(fod=[np.array([1., 0, 0]), np.array([0, .34, .94])], fw=[1.0, 0.8], aWM=0.7, fGM=0.1, fCSF=0.2),
    "GM-heavy":    dict(fod=[np.array([1., 0, 0])], fw=[1.0], aWM=0.15, fGM=0.75, fCSF=0.10),
    "CSF-heavy":   dict(fod=[np.array([1., 0, 0])], fw=[1.0], aWM=0.10, fGM=0.05, fCSF=0.85),
    "WM/CSF-pv":   dict(fod=[np.array([1., 0, 0])], fw=[1.0], aWM=0.5, fGM=0.0, fCSF=0.5),
    "pure-CSF":    dict(fod=[], fw=[], aWM=0.0, fGM=0.0, fCSF=1.0),
    "pure-GM":     dict(fod=[], fw=[], aWM=0.0, fGM=1.0, fCSF=0.0),
}
shells = [1000., 2000., 3000.]; ndirs = [45, 60, 64]
for noise in [0.0, 0.02, 0.04]:
    print(f"\n=== noise={noise} (3-shell, 3-tissue) ===")
    worst = 0.0
    for name, a in archetypes.items():
        bvals, bvecs, S = simulate_vox(shells, ndirs, a["fod"], a["fw"], a["aWM"], a["fGM"], a["fCSF"], seed=42, noise=noise)
        m1 = frac_M1(bvals, bvecs, S, True); m3 = frac_M3(bvals, bvecs, S, True)
        d = max(abs(m1[k] - m3[k]) for k in m1)
        worst = max(worst, d)
        print(f"  {name:10s} plant(WM={a['aWM']:.2f},GM={a['fGM']:.2f},CSF={a['fCSF']:.2f})  "
              f"M1(WM={m1['WM']:.3f},GM={m1['GM']:.3f},CSF={m1['CSF']:.3f})  "
              f"M3(WM={m3['WM']:.3f},GM={m3['GM']:.3f},CSF={m3['CSF']:.3f})  |M1-M3|max={d:.4f}")
    print(f"  --> worst |M1-M3| across archetypes: {worst:.4f}")
