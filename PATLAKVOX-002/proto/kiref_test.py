"""Ki_ref (reference-Patlak) robustness + stability: motion bias, naive-fail, t* stability,
integration-convention robustness. Decides whether the reference-Patlak fork is shippable."""
import numpy as np
import physics as P
from mc import schedule, add_noise, detect_motion, repair, stat, HALF


def run():
    K1r, k2r = 0.45, 0.09
    trap_targets = [(K1r, k2r, 0.10, 0.0), (K1r, k2r, 0.06, 0.0), (K1r, k2r, 0.14, 0.0),
                    (K1r, k2r, 0.18, 0.0)]
    n_ref_vox = 40
    ratio_multi, motion_bias = [], []
    tstar_stab, integ_stab = [], []
    for seed in range(40, 80):
        dur, start = schedule(60.0); tmid = start + dur/2; half = HALF["C-11"]; fs = start
        tf = P.fine_grid(dur); edges = np.concatenate([[0.0], np.cumsum(dur)])
        cp_fine = P.feng_plasma(tf, 1.0)
        cr_true = P.forward_1tc(cp_fine, tf, edges, K1r, k2r)
        rng = np.random.default_rng(seed + 111)
        cr = np.mean([add_noise(cr_true, tmid, dur, 0.8, half, rng) for _ in range(n_ref_vox)], axis=0)
        cand = np.where(fs >= 32.0)[0]; mf = sorted([cand[len(cand)//2], cand[-1]])
        for f in mf:
            cr[f] *= 0.5
        allk = np.ones(len(dur), bool)
        for (K1, k2, k3, k4) in trap_targets:
            ct_true = P.forward_2tc(cp_fine, tf, edges, K1, k2, k3, k4)
            ct = add_noise(ct_true, tmid, dur, 0.8, half, rng)
            for f in mf:
                ct[f] *= 0.5
            gmean = 0.5*(cr+ct); keep = detect_motion(gmean, fs, 25.0)
            crr = repair(cr, keep, tmid); ctr = repair(ct, keep, tmid)
            kr = P.ref_patlak_kiref(crr, ctr, dur, fs, 25.0, allk)
            km = P.ref_patlak_kiref_multilin(crr, ctr, dur, fs, 25.0, allk)
            ratio_multi.append(abs(kr-km)/abs(km))
            kn = P.ref_patlak_kiref(cr, ct, dur, fs, 25.0, allk)   # naive (no repair)
            motion_bias.append(abs(kn-kr)/abs(kr))
            kr20 = P.ref_patlak_kiref(crr, ctr, dur, fs, 20.0, allk)
            kr30 = P.ref_patlak_kiref(crr, ctr, dur, fs, 30.0, allk)
            tstar_stab.append(abs(kr30-kr20)/abs(kr))
            kr_trap = P.ref_patlak_kiref(crr, ctr, dur, fs, 25.0, allk, integ=P.cumint_rect)
            kr_trapz = P.ref_patlak_kiref(crr, ctr, dur, fs, 25.0, allk, integ=lambda y, d: P.cumint_trap(y, tmid, d))
            integ_stab.append(abs(kr_trap-kr_trapz)/abs(kr))
    stat("Kiref ratio vs multi", ratio_multi)
    stat("Kiref motion bias(naive)", motion_bias)
    stat("Kiref t* 20-vs-30 stab", tstar_stab)
    stat("Kiref rect-vs-trap integ", integ_stab)


if __name__ == "__main__":
    run()
