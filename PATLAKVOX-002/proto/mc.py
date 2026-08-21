"""MC invariance + robustness de-risk for PATLAKVOX-002 (interp-repair motion handling)."""
import numpy as np
import physics as P

LN2 = np.log(2.0)
HALF = {"C-11": 20.4, "F-18": 109.8}
GAIN = 45.0


def schedule(total):
    dur = [0.25] * 4 + [0.5] * 4 + [1.0] * 4 + [2.0] * 5
    t = sum(dur)
    while t < total - 1e-6:
        dur.append(4.0); t += 4.0
    dur = np.asarray(dur, float)
    start = np.concatenate([[0.0], np.cumsum(dur)])[:-1]
    return dur, start


def add_noise(true_curve, tmid, dur, sigma, half, rng):
    meas = P.decay_uncorrect(true_curve, tmid, half)
    sd = sigma * np.sqrt(np.clip(meas, 1e-9, None) / (dur * GAIN))
    n1 = sd * rng.standard_normal(meas.size)
    n2 = sd * rng.standard_normal(meas.size)
    noisy = np.sqrt((meas + n1) ** 2 + n2 ** 2)
    return P.decay_correct(noisy, tmid, half)


def detect_motion(global_mean, fs, t_star, gross=0.30, maxdrop=5):
    """Iterative (one-at-a-time) gross-outlier frame detection in log global activity.
    Refits a local quadratic through the remaining kept late frames each pass, so a single
    dropped outlier stops swamping its neighbours."""
    g = np.asarray(global_mean, float)
    keep = np.ones(g.size, bool)
    lg = np.log(np.clip(g, 1e-9, None))
    idx = list(np.where(fs >= t_star)[0])
    for _ in range(maxdrop):
        cur = [j for j in idx if keep[j]]
        if len(cur) < 4:
            break
        worst, worstdev = None, gross
        for i in cur:
            others = [j for j in cur if j != i]
            A = np.column_stack([np.ones(len(others)), fs[others], fs[others] ** 2])
            coef, *_ = np.linalg.lstsq(A, lg[others], rcond=None)
            pred = coef[0] + coef[1] * fs[i] + coef[2] * fs[i] ** 2
            dev = abs(lg[i] - pred)
            if dev > worstdev:
                worst, worstdev = i, dev
        if worst is None:
            break
        keep[worst] = False
    return keep


def repair(tac, keep, tmid):
    """linear-interpolate the flagged frames from kept neighbours (decay-corrected activity)."""
    tac = np.asarray(tac, float).copy()
    if keep.all():
        return tac
    tac[~keep] = np.interp(tmid[~keep], tmid[keep], tac[keep])
    return tac


def stat(name, arr):
    a = np.array(arr)
    print(f"  {name:24s} n={a.size:4d}  median={np.median(a)*100:6.2f}%  "
          f"max={np.max(a)*100:6.2f}%  p90={np.percentile(a,90)*100:6.2f}%")


def mrtm2_dvr(cr, ct, dur, fs, tstar, k2p):
    m = fs >= tstar
    U = (P.cumint_rect(cr, dur) + np.asarray(cr, float) / k2p)[m]
    V = P.cumint_rect(ct, dur)[m]
    w = np.sqrt(dur)[m]
    p, *_ = np.linalg.lstsq(w[:, None] * np.column_stack([U, V]), w * np.asarray(ct, float)[m], rcond=None)
    return -p[0] / p[1]


ALL = None


def run():
    tstar_p = 20.0
    trap_vox = [("trap", 0.36, 0.11, 0.055, 0.0), ("trap", 0.30, 0.10, 0.040, 0.0),
                ("trap", 0.42, 0.12, 0.070, 0.0)]
    rev_vox = [("rev", 0.50, 0.10, 0.060, 0.030), ("rev", 0.45, 0.12, 0.050, 0.040),
               ("rev", 0.55, 0.11, 0.080, 0.025)]

    ki_diffs, vt_diffs = [], []
    ki_motion_bias, vt_motion_bias = [], []
    repair_ki_err, repair_vt_err = [], []
    det_ok = 0; det_tot = 0; rev_correct = 0; rev_total = 0

    for seed in range(40, 80):
        dur, start = schedule(90.0); tmid = start + dur / 2; half = HALF["F-18"]; fs = start
        tf = P.fine_grid(dur); edges = np.concatenate([[0.0], np.cumsum(dur)])
        cp_fine = P.feng_plasma(tf, 1.0)
        cp_true = P.frame_average(cp_fine, tf, edges)
        rng = np.random.default_rng(seed)
        allkeep = np.ones(len(dur), bool)
        cand = np.where(fs >= 40.0)[0]
        mf = sorted([cand[len(cand)//3], cand[2*len(cand)//3], cand[-1]])
        factors = {mf[0]: 0.5, mf[1]: 0.55, mf[2]: 0.45}

        clean_tacs, motion_tacs, truths, kps = [], [], [], []
        for (kind, K1, k2, k3, k4) in trap_vox + rev_vox:
            ct_true = P.forward_2tc(cp_fine, tf, edges, K1, k2, k3, k4)
            ct = add_noise(ct_true, tmid, dur, 0.28, half, rng)
            ctm = ct.copy()
            for f, fac in factors.items():
                ctm[f] *= fac
            clean_tacs.append(ct); motion_tacs.append(ctm)
            truths.append((kind, K1 * k3 / (k2 + k3), (K1/k2)*(1+k3/k4) if k4 > 0 else np.nan))
            kps.append((K1, k2, k3, k4))

        gmean = np.mean(motion_tacs, axis=0)
        keep = detect_motion(gmean, fs, tstar_p)
        detected = set(np.where(~keep)[0]); det_tot += 1; det_ok += (detected == set(mf))

        for ct, ctm, (kind, ki_t, vt_t), (K1, k2, k3, k4) in zip(clean_tacs, motion_tacs, truths, kps):
            ctr = repair(ctm, keep, tmid)                       # repaired TAC (correct action)
            if kind == "trap":
                ki_ref = P.patlak_ki(cp_true, ctr, dur, fs, tstar_p, allkeep)
                nl = P.fit_2tc_nl(cp_true, tmid, dur, ctr, allkeep.astype(float), irr=True)
                ki_diffs.append(abs(ki_ref - nl["Ki"]) / nl["Ki"])
                ki_clean = P.patlak_ki(cp_true, ct, dur, fs, tstar_p, allkeep)
                repair_ki_err.append(abs(ki_ref - ki_clean) / ki_clean)
                ki_naive = P.patlak_ki(cp_true, ctm, dur, fs, tstar_p, allkeep)
                ki_motion_bias.append(abs(ki_naive - ki_ref) / ki_ref)
                rf, lo, pa = P.is_reversible_plasma(cp_true, ctr, dur, fs, tstar_p, allkeep)
                rev_total += 1; rev_correct += (rf == False)
            else:
                vt_ref = P.ma1_vt(cp_true, ctr, dur, fs, tstar_p, allkeep)
                nl = P.fit_2tc_nl(cp_true, tmid, dur, ctr, allkeep.astype(float), irr=False)
                vt_diffs.append(abs(vt_ref - nl["VT"]) / nl["VT"])
                vt_clean = P.ma1_vt(cp_true, ct, dur, fs, tstar_p, allkeep)
                repair_vt_err.append(abs(vt_ref - vt_clean) / vt_clean)
                vt_naive = P.ma1_vt(cp_true, ctm, dur, fs, tstar_p, allkeep)
                vt_motion_bias.append(abs(vt_naive - vt_ref) / vt_ref)
                rf, lo, pa = P.is_reversible_plasma(cp_true, ctr, dur, fs, tstar_p, allkeep)
                rev_total += 1; rev_correct += (rf == True)

    print("=== PLASMA invariance (repaired ref vs 2TCM-NL on repaired) ===")
    stat("Ki  Patlak-vs-2TCM", ki_diffs)
    stat("VT  MA1-vs-2TCM", vt_diffs)
    print("=== repair fidelity (repaired vs clean-data estimate) ===")
    stat("Ki repair err", repair_ki_err)
    stat("VT repair err", repair_vt_err)
    print("=== motion robustness (naive-uncorrected vs repaired) ===")
    stat("Ki motion bias", ki_motion_bias)
    stat("VT motion bias", vt_motion_bias)
    print(f"=== motion detection exact: {det_ok}/{det_tot}   reversibility: {rev_correct}/{rev_total} ===")

    # ---------------- REFERENCE subjects ----------------
    print("\n=== REFERENCE subjects (DVR) ===")
    tstar_r = 25.0
    K1r, k2r = 0.45, 0.09
    rev_targets = [(K1r, k2r, 0.20, 0.09), (K1r, k2r, 0.15, 0.08), (K1r, k2r, 0.10, 0.09)]
    dvr_diffs, dvr_motion_bias, dvr_repair_err = [], [], []
    for seed in range(40, 80):
        dur, start = schedule(60.0); tmid = start + dur/2; half = HALF["C-11"]; fs = start
        tf = P.fine_grid(dur); edges = np.concatenate([[0.0], np.cumsum(dur)])
        cp_fine = P.feng_plasma(tf, 1.0)
        cr_true = P.forward_1tc(cp_fine, tf, edges, K1r, k2r)
        rng = np.random.default_rng(seed + 500)
        cr = add_noise(cr_true, tmid, dur, 0.9, half, rng)
        cand = np.where(fs >= 35.0)[0]; mf = sorted([cand[len(cand)//2], cand[-1]])
        crm = cr.copy()
        for f in mf:
            crm[f] *= 0.5
        allkeep = np.ones(len(dur), bool)
        for (K1, k2, k3, k4) in rev_targets:
            ct_true = P.forward_2tc(cp_fine, tf, edges, K1, k2, k3, k4)
            ct = add_noise(ct_true, tmid, dur, 0.9, half, rng)
            ctm = ct.copy()
            for f in mf:
                ctm[f] *= 0.5
            gmean = 0.5*(crm + ctm)
            keep = detect_motion(gmean, fs, tstar_r)
            crr = repair(crm, keep, tmid); ctr = repair(ctm, keep, tmid)
            dvr_ref = P.ref_logan_dvr(crr, ctr, dur, fs, tstar_r, k2r, allkeep)
            dvr_m = mrtm2_dvr(crr, ctr, dur, fs, tstar_r, k2r)
            dvr_diffs.append(abs(dvr_ref - dvr_m) / dvr_ref)
            dvr_clean = P.ref_logan_dvr(cr, ct, dur, fs, tstar_r, k2r, allkeep)
            dvr_repair_err.append(abs(dvr_ref - dvr_clean)/dvr_clean)
            dvr_naive = P.ref_logan_dvr(crm, ctm, dur, fs, tstar_r, k2r, allkeep)
            dvr_motion_bias.append(abs(dvr_naive - dvr_ref) / dvr_ref)
    stat("DVR ref-Logan vs MRTM2", dvr_diffs)
    stat("DVR repair err", dvr_repair_err)
    stat("DVR motion bias", dvr_motion_bias)


if __name__ == "__main__":
    run()
