import numpy as np
from proto_frac import (wm_response_signal, gm_response, csf_response, sph_mean_wm,
                        make_dirs, simulate_voxel, spherical_mean_per_shell, unmix_fractions,
                        D_PAR, D_PERP, D_GM, D_CSF)

# --- 1. exact powder means with a HUGE uniform sampling vs the analytic column ---
for b in [1000., 2000., 3000.]:
    print(f"b={b}: WMpowder(sph_mean_wm)={sph_mean_wm(b):.5f}  GM={gm_response(b):.5f}  CSF={csf_response(b):.5f}")

# --- 2. condition number of the 3-tissue design at these shells ---
b = np.array([0., 1000., 2000., 3000.])
A = np.stack([np.array([1.0]+[sph_mean_wm(bb) for bb in b[1:]]),
              csf_response(b), gm_response(b)], axis=1)
print("\n3-tissue design A (rows=b, cols=WM,CSF,GM):\n", np.round(A, 4))
print("cond(A) =", np.linalg.cond(A))

# --- 3. use EXACT planted spherical means (no finite-dir sampling): dense uniform dirs ---
fod_dirs = [np.array([1., 0., 0.]), np.array([0., np.cos(np.deg2rad(70)), np.sin(np.deg2rad(70))])]
fod_w = [1.0, 0.7]
aWM, fGM, fCSF = 0.60, 0.15, 0.25
# build the exact spherical mean by dense uniform sampling
def exact_mean(b):
    g = make_dirs(20000, seed=7)
    s_wm = np.zeros(g.shape[0])
    for fd, fw in zip(fod_dirs, fod_w):
        ct = np.abs(g @ fd); th = np.arccos(np.clip(ct,-1,1))
        s_wm += fw*wm_response_signal(b, th)
    s_wm /= sum(fod_w)
    s = aWM*s_wm + fGM*gm_response(b) + fCSF*csf_response(b)
    return s.mean()
ubx = [0.,1000.,2000.,3000.]
meansx = {0.:1.0, 1000.:exact_mean(1000.), 2000.:exact_mean(2000.), 3000.:exact_mean(3000.)}
print("\nexact (dense) spherical means:", {k: round(v,5) for k,v in meansx.items()})
frx = unmix_fractions(ubx, meansx, three_tissue=True)
print("unmix with EXACT means:", {k: round(v,4) for k,v in frx.items()}, "  planted WM=0.60 CSF=0.25 GM=0.15")

# --- 4. now with realistic dense per-shell dirs (60-90) ---
for ndir in [30, 60, 90, 200]:
    bvals, bvecs, S = simulate_voxel([1000.,2000.,3000.], [ndir]*3, fod_dirs, fod_w, fGM, fCSF, aWM)
    ub, means = spherical_mean_per_shell(bvals, S)
    fr = unmix_fractions(ub, means, True)
    print(f"ndir/shell={ndir:4d}: ", {k: round(v,4) for k,v in fr.items()})
