"""Reference-subject fork test: region-averaged (low-noise) C_R.
Compares DVR estimators (ref-Logan, MRTM2, SRTM2) for reversible targets, and reference-Patlak
Ki_ref (ratio vs multilinear) for trapping targets, to decide the invariant reference fork."""
import numpy as np
import physics as P
from mc import schedule, add_noise, detect_motion, repair, stat, HALF, mrtm2_dvr


def run():
    tstar = 25.0
    K1r, k2r = 0.45, 0.09          # reference region 1TC; V_R = K1r/k2r = 5.0
    # reversible targets (share K1r,k2r as ND compartment): DVR = 1 + k3/k4
    rev_targets = [(K1r, k2r, 0.20, 0.09), (K1r, k2r, 0.15, 0.08),
                   (K1r, k2r, 0.12, 0.10), (K1r, k2r, 0.08, 0.09)]
    # trapping targets (share K1r,k2r; k4=0): Ki_ref = k2r*k3/(k2r+k3)
    trap_targets = [(K1r, k2r, 0.10, 0.0), (K1r, k2r, 0.06, 0.0), (K1r, k2r, 0.14, 0.0)]

    dvr_logan_mrtm, dvr_srtm_mrtm, dvr_logan_srtm = [], [], []
    dvr_logan_bias, dvr_srtm_bias = [], []            # vs truth (1+k3/k4)
    kiref_ratio_multi, kiref_bias = [], []
    n_ref_vox = 40
    for seed in range(40, 80):
        dur, start = schedule(60.0); tmid = start + dur/2; half = HALF["C-11"]; fs = start
        tf = P.fine_grid(dur); edges = np.concatenate([[0.0], np.cumsum(dur)])
        cp_fine = P.feng_plasma(tf, 1.0)
        cr_true = P.forward_1tc(cp_fine, tf, edges, K1r, k2r)
        rng = np.random.default_rng(seed + 900)
        # C_R = mean over many reference voxels (low noise)
        crs = [add_noise(cr_true, tmid, dur, 0.8, half, rng) for _ in range(n_ref_vox)]
        cr = np.mean(crs, axis=0)
        cand = np.where(fs >= 32.0)[0]; mf = sorted([cand[len(cand)//2], cand[-1]])
        for f in mf:
            cr[f] *= 0.5
        allk = np.ones(len(dur), bool)
        for (K1, k2, k3, k4) in rev_targets:
            ct_true = P.forward_2tc(cp_fine, tf, edges, K1, k2, k3, k4)
            ct = add_noise(ct_true, tmid, dur, 0.8, half, rng)
            for f in mf:
                ct[f] *= 0.5
            gmean = 0.5*(cr + ct)
            keep = detect_motion(gmean, fs, tstar)
            crr = repair(cr, keep, tmid); ctr = repair(ct, keep, tmid)
            dvr_logan = P.ref_logan_dvr(crr, ctr, dur, fs, tstar, k2r, allk)
            dvr_mrtm = mrtm2_dvr(crr, ctr, dur, fs, tstar, k2r)
            dvr_srtm = P.srtm2_bpnd(crr, ctr, tmid, dur, k2r) + 1.0
            truth = 1.0 + k3/k4
            dvr_logan_mrtm.append(abs(dvr_logan-dvr_mrtm)/dvr_mrtm)
            dvr_srtm_mrtm.append(abs(dvr_srtm-dvr_mrtm)/dvr_mrtm)
            dvr_logan_srtm.append(abs(dvr_logan-dvr_srtm)/dvr_srtm)
            dvr_logan_bias.append(abs(dvr_logan-truth)/truth)
            dvr_srtm_bias.append(abs(dvr_srtm-truth)/truth)
        for (K1, k2, k3, k4) in trap_targets:
            ct_true = P.forward_2tc(cp_fine, tf, edges, K1, k2, k3, k4)
            ct = add_noise(ct_true, tmid, dur, 0.8, half, rng)
            for f in mf:
                ct[f] *= 0.5
            gmean = 0.5*(cr + ct)
            keep = detect_motion(gmean, fs, tstar)
            crr = repair(cr, keep, tmid); ctr = repair(ct, keep, tmid)
            kr = P.ref_patlak_kiref(crr, ctr, dur, fs, tstar, allk)
            km = P.ref_patlak_kiref_multilin(crr, ctr, dur, fs, tstar, allk)
            truth = k2r*k3/(k2r+k3)
            kiref_ratio_multi.append(abs(kr-km)/abs(km))
            kiref_bias.append(abs(kr-truth)/truth)
    print("=== reversible reference targets -> DVR ===")
    stat("DVR ref-Logan vs MRTM2", dvr_logan_mrtm)
    stat("DVR SRTM2 vs MRTM2", dvr_srtm_mrtm)
    stat("DVR ref-Logan vs SRTM2", dvr_logan_srtm)
    stat("DVR ref-Logan bias-vs-truth", dvr_logan_bias)
    stat("DVR SRTM2 bias-vs-truth", dvr_srtm_bias)
    print("=== trapping reference targets -> Ki_ref ===")
    stat("Kiref ratio vs multilin", kiref_ratio_multi)
    stat("Kiref bias-vs-truth", kiref_bias)


if __name__ == "__main__":
    run()
