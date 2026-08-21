"""Invariance of the tissue-fraction reference (spherical-mean NNLS, M1) vs two independent
estimators: full multishell-multitissue SH block solve (M3) and SH-l0 spherical mean (M2).
Report per-subject per-tissue max/median |frac diff| over the mask + panel pass@ (rtol,atol)."""
import json, sys
from pathlib import Path
import numpy as np
from math import factorial
from scipy.special import lpmv
from scipy.optimize import nnls
ROOT = Path("/private/tmp/claude-501/-Users-nicholas-Desktop-brain-researcher-benchmark/f9fbdff6-413e-4671-9547-7707c56b1d7c/scratchpad/MSMTCSD-002")
sys.path.insert(0, str(ROOT / "solution"))
import msmt_ref as R, msmt_pipeline as P
DATA = ROOT / "environment" / "data"
SUB = [f"sub-{i:02d}" for i in range(1, 9)]
RTOL, ATOL, PASS = 0.10, 0.03, 0.90


def sh_l0_mean(sig_shell, dirs):
    B, _ = R.sh_matrix(dirs, 0)
    c, *_ = np.linalg.lstsq(B, sig_shell, rcond=None)
    return c[0] / np.sqrt(4 * np.pi)


def frac_M2(atten, bvals, bvecs, mask, keep, ntis):
    """SH-l0 spherical mean per shell -> NNLS (independent of arithmetic mean)."""
    b0, shells = R.parse_shells(bvals)
    rows_b = np.array([0.0] + [s[0] for s in shells])
    cols = [R.wm_powder(rows_b)]
    if ntis == 3: cols.append(R.gm_response(rows_b))
    cols.append(R.csf_response(rows_b))
    A = np.stack(cols, 1); names = ["WM"] + (["GM"] if ntis == 3 else []) + ["CSF"]
    nvox = atten.shape[1]; out = {n: np.zeros(nvox) for n in names}
    sbar = np.ones((rows_b.size, nvox))
    for si, (bn, idx) in enumerate(shells):
        sel = idx[keep[idx]]
        sbar[si + 1] = np.array([sh_l0_mean(atten[sel, v], bvecs[sel]) for v in range(nvox)]) \
            if False else _batch_l0(atten[sel], bvecs[sel])
    for v in np.where(mask)[0]:
        x, _ = nnls(A, sbar[:, v]); s = x.sum() or 1.0
        for k, n in enumerate(names): out[n][v] = x[k] / s
    return out


def _batch_l0(sig_sel, dirs):
    B, _ = R.sh_matrix(dirs, 0)
    c, *_ = np.linalg.lstsq(B, sig_sel, rcond=None)
    return c[0] / np.sqrt(4 * np.pi)


def frac_M3(atten, bvals, bvecs, mask, keep, ntis, lmax=6):
    """Full multishell-multitissue block least-squares -> non-neg l=0 tissue amounts."""
    idx = R.sh_index(lmax); ncoef = len(idx)
    names = ["WM", "GM", "CSF"] if ntis == 3 else ["WM", "CSF"]
    niso = ntis - 1; iso_names = names[1:]
    sel = np.where(keep)[0]
    Mrows = []
    for i in sel:
        b = bvals[i]; g = bvecs[i]
        if np.linalg.norm(g) < 1e-9: g = np.array([0, 0, 1.0])
        r0, ords = R.wm_zonal(b, lmax)
        B, _ = R.sh_matrix(g[None, :], lmax)
        conv = np.array([np.sqrt(4 * np.pi / (2 * l + 1)) * r0[ords.index(l)] for (l, m) in idx])
        row = np.zeros(ncoef + niso); row[:ncoef] = B[0] * conv
        for k, nm in enumerate(iso_names):
            row[ncoef + k] = R.gm_response(b) if nm == "GM" else R.csf_response(b)
        Mrows.append(row)
    M = np.array(Mrows); y = atten[sel]
    r0_0, _ = R.wm_zonal(0.0, lmax)
    nvox = atten.shape[1]; out = {n: np.zeros(nvox) for n in names}
    # regularise slightly for stability of the angular part; iso amounts unpenalised
    P_ = np.diag([(l * (l + 1)) ** 2 for (l, m) in idx] + [0.0] * niso).astype(float)
    MtM = M.T @ M; scale = np.trace(MtM) / MtM.shape[0]
    sol = np.linalg.solve(MtM + 1e-4 * scale * P_, M.T @ y)
    for v in np.where(mask)[0]:
        wm_amt = max(sol[0, v] * r0_0[0], 0.0)
        iso = np.clip(sol[ncoef:, v], 0, None)
        amts = np.array([wm_amt] + list(iso)); s = amts.sum() or 1.0
        f = amts / s
        for k, nm in enumerate(names): out[nm][v] = f[k]
    return out


print(f"{'subj':7s} {'tis':4s} {'medDiffM3':>9s} {'maxDiffM3':>9s} {'passM3':>7s}  "
      f"{'medDiffM2':>9s} {'maxDiffM2':>9s} {'passM2':>7s}")
allpass = True
for sid in SUB:
    subj = P.load_subject(DATA / sid)
    ref = P.analyze(subj)
    bvals, bvecs, sig, mask = subj["bvals"], subj["bvecs"], subj["sig"], subj["mask"]
    b0, shells = R.parse_shells(bvals)
    S0 = np.clip(sig[b0].mean(0), 1e-6, None); atten = np.clip(sig / S0, 1e-6, 1.5)
    dropped = ref["dropped"]; keep = np.ones(bvals.size, bool); keep[dropped] = False
    ntis = ref["ntissue"]
    m3 = frac_M3(atten, bvals, bvecs, mask, keep, ntis, lmax=ref["lmax"])
    m2 = frac_M2(atten, bvals, bvecs, mask, keep, ntis)
    for t in (["WM", "GM", "CSF"] if ntis == 3 else ["WM", "CSF"]):
        rf = ref["fracs"][t][mask]
        for tag, mm in [("M3", m3), ("M2", m2)]:
            gf = mm[t][mask]
            ad = np.abs(gf - rf)
            ok = np.isclose(gf, rf, rtol=RTOL, atol=ATOL)
            frac_ok = ok.mean()
            if tag == "M3": md3, mx3, p3 = np.median(ad), ad.max(), frac_ok
            else: md2, mx2, p2 = np.median(ad), ad.max(), frac_ok
        pass3 = p3 >= PASS; pass2 = p2 >= PASS
        allpass = allpass and pass3 and pass2
        print(f"{sid:7s} {t:4s} {md3:9.4f} {mx3:9.4f} {p3*100:6.1f}% "
              f" {md2:9.4f} {mx2:9.4f} {p2*100:6.1f}%  {'OK' if (pass3 and pass2) else 'FAIL'}")
print("\nALL FRACTION PANELS INVARIANT (M2 & M3 pass vs ref):", allpass)
