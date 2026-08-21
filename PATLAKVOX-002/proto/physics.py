"""Prototype physics + estimators for PATLAKVOX-002 (voxelwise Patlak PET).

Goal: de-risk convention-invariance BEFORE building the full task.
numpy/scipy only. All times in MINUTES; rates per-minute; activity kBq/mL.
"""
import numpy as np
from scipy.optimize import least_squares

LN2 = np.log(2.0)
_NFINE = 4096


# ---------------- fine grid + frame averaging ----------------
def fine_grid(dur):
    return np.linspace(0.0, float(np.sum(dur)), _NFINE)


def frame_average(curve_fine, t_fine, edges):
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (curve_fine[1:] + curve_fine[:-1]) * np.diff(t_fine))])
    ce = np.interp(edges, t_fine, cum)
    return np.diff(ce) / np.diff(edges)


def conv_exp_fine(c_fine, t_fine, theta):
    dt = t_fine[1] - t_fine[0]
    return np.convolve(c_fine, np.exp(-theta * t_fine))[: t_fine.size] * dt


# ---------------- decay ----------------
def decay_correct(meas, tmid, half):
    return np.asarray(meas, float) * np.exp((LN2 / half) * np.asarray(tmid, float))


def decay_uncorrect(true, tmid, half):
    return np.asarray(true, float) * np.exp(-(LN2 / half) * np.asarray(tmid, float))


# ---------------- forward compartment models ----------------
def two_tc_comps(K1, k2, k3, k4):
    s = k2 + k3 + k4
    disc = np.sqrt(max(s * s - 4.0 * k2 * k4, 0.0))
    th1, th2 = (s - disc) / 2.0, (s + disc) / 2.0
    if disc < 1e-12:
        th1, th2 = 0.0, k2 + k3
    c1 = K1 * (k3 + k4 - th1) / (th2 - th1)
    c2 = K1 * (th2 - k3 - k4) / (th2 - th1)
    return [(c1, th1), (c2, th2)]


def forward_plasma(cp_fine, t_fine, edges, comps):
    out = np.zeros_like(t_fine)
    for coef, rate in comps:
        out = out + coef * conv_exp_fine(cp_fine, t_fine, rate)
    return frame_average(out, t_fine, edges)


def forward_2tc(cp_fine, t_fine, edges, K1, k2, k3, k4):
    return forward_plasma(cp_fine, t_fine, edges, two_tc_comps(K1, k2, k3, k4))


def forward_1tc(cp_fine, t_fine, edges, K1, k2):
    return forward_plasma(cp_fine, t_fine, edges, [(K1, k2)])


def feng_plasma(t, scale=1.0):
    t = np.asarray(t, float)
    A1, A2, A3 = 21.0 * scale, 0.9 * scale, 0.6 * scale
    L1, L2, L3 = 4.5, 0.20, 0.011
    return np.clip((A1 * t - A2 - A3) * np.exp(-L1 * t) + A2 * np.exp(-L2 * t) + A3 * np.exp(-L3 * t),
                   0.0, None)


# ---------------- integration helpers ----------------
def cumint_rect(y, dur):
    """cumulative integral to each frame END via frame-mean rectangles."""
    return np.cumsum(np.asarray(y, float) * np.asarray(dur, float))


def cumint_trap(y, tmid, dur):
    """cumulative integral via trapezoid through origin + frame midtimes, sampled at frame END."""
    edges = np.concatenate([[0.0], np.cumsum(dur)])
    tt = np.concatenate([[0.0], np.asarray(tmid, float)])
    yy = np.concatenate([[0.0], np.asarray(y, float)])
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (yy[1:] + yy[:-1]) * np.diff(tt))])
    return np.interp(edges[1:], tt, cum)


# ---------------- estimators (reference-style, graphical) ----------------
def tstar_mask(frame_start, t_star_min, keep):
    fs = np.asarray(frame_start, float)
    m = fs >= t_star_min
    return m & keep


def patlak_ki(cp, ct, dur, fs, t_star, keep, integ=cumint_rect):
    """plasma Patlak slope (Ki), ratio-space OLS over kept frames >= t*."""
    icp = integ(cp, dur)
    m = tstar_mask(fs, t_star, keep)
    x = icp[m] / cp[m]
    y = np.asarray(ct, float)[m] / cp[m]
    A = np.column_stack([x, np.ones(x.size)])
    return float(np.linalg.lstsq(A, y, rcond=None)[0][0])


def logan_vt(cp, ct, dur, fs, t_star, keep):
    """plasma Logan VT (slope), ratio-space OLS over kept frames >= t*."""
    icp = cumint_rect(cp, dur); ict = cumint_rect(ct, dur)
    m = tstar_mask(fs, t_star, keep)
    x = icp[m] / ct[m]; y = ict[m] / ct[m]
    A = np.column_stack([x, np.ones(x.size)])
    return float(np.linalg.lstsq(A, y, rcond=None)[0][0])


def ma1_vt(cp, ct, dur, fs, t_star, keep):
    """Ichise MA1 multilinear VT over kept frames >= t*."""
    icp = cumint_rect(cp, dur); ict = cumint_rect(ct, dur)
    m = tstar_mask(fs, t_star, keep)
    w = np.sqrt(np.asarray(dur, float))[m]
    X = np.column_stack([icp[m], ict[m]])
    p, *_ = np.linalg.lstsq(w[:, None] * X, w * np.asarray(ct, float)[m], rcond=None)
    return float(-p[0] / p[1])


def ref_logan_dvr(cr, ct, dur, fs, t_star, k2p, keep):
    """reference Logan DVR (slope), with the k2' term. DVR = slope."""
    icr = cumint_rect(cr, dur); ict = cumint_rect(ct, dur)
    m = tstar_mask(fs, t_star, keep)
    x = (icr[m] + np.asarray(cr, float)[m] / k2p) / ct[m]
    y = ict[m] / ct[m]
    A = np.column_stack([x, np.ones(x.size)])
    return float(np.linalg.lstsq(A, y, rcond=None)[0][0])


def ref_patlak_kiref(cr, ct, dur, fs, t_star, keep, integ=cumint_rect):
    """reference Patlak relative influx (ratio-space OLS)."""
    icr = integ(cr, dur)
    m = tstar_mask(fs, t_star, keep)
    x = icr[m] / np.asarray(cr, float)[m]
    y = np.asarray(ct, float)[m] / np.asarray(cr, float)[m]
    A = np.column_stack([x, np.ones(x.size)])
    return float(np.linalg.lstsq(A, y, rcond=None)[0][0])


def ref_patlak_kiref_multilin(cr, ct, dur, fs, t_star, keep):
    """reference Patlak relative influx (multilinear, regress C_T on [int C_R, C_R])."""
    icr = cumint_rect(cr, dur)
    m = tstar_mask(fs, t_star, keep)
    w = np.sqrt(np.asarray(dur, float))[m]
    X = np.column_stack([icr[m], np.asarray(cr, float)[m]])
    p, *_ = np.linalg.lstsq(w[:, None] * X, w * np.asarray(ct, float)[m], rcond=None)
    return float(p[0])


# ---------------- reversibility from data ----------------
def _line_nrmse(x, y):
    A = np.column_stack([x, np.ones(x.size)])
    c = np.linalg.lstsq(A, y, rcond=None)[0]
    r = y - A @ c
    return float(np.sqrt(np.mean(r * r)) / (np.mean(np.abs(y)) + 1e-12))


def is_reversible_plasma(cp, ct, dur, fs, t_star, keep):
    icp = cumint_rect(cp, dur); ict = cumint_rect(ct, dur)
    m = tstar_mask(fs, t_star, keep)
    logan = _line_nrmse(icp[m] / ct[m], ict[m] / ct[m])
    patlak = _line_nrmse(icp[m] / cp[m], ct[m] / cp[m])
    return logan <= patlak, logan, patlak


# ---------------- independent 2TCM nonlinear ----------------
def fit_2tc_nl(cp, tmid, dur, ct, keep, irr=False):
    tf = fine_grid(dur); edges = np.concatenate([[0.0], np.cumsum(dur)])
    cp_f = np.interp(tf, np.concatenate([[0.0], tmid]), np.concatenate([[0.0], cp]))
    w = np.sqrt(np.asarray(dur, float)) * keep
    if irr:
        def res(p):
            K1, k2, k3 = p
            return w * (ct - forward_2tc(cp_f, tf, edges, K1, k2, k3, 0.0))
        s = least_squares(res, [0.3, 0.1, 0.05], bounds=([1e-3, 1e-3, 1e-4], [3, 2, 2]))
        K1, k2, k3 = s.x
        return dict(K1=K1, k2=k2, k3=k3, k4=0.0, Ki=K1 * k3 / (k2 + k3))
    def res(p):
        K1, k2, k3, k4 = p
        return w * (ct - forward_2tc(cp_f, tf, edges, K1, k2, k3, k4))
    s = least_squares(res, [0.4, 0.1, 0.05, 0.02], bounds=([1e-3, 1e-3, 0.0, 1e-4], [3, 2, 2, 1]))
    K1, k2, k3, k4 = s.x
    return dict(K1=K1, k2=k2, k3=k3, k4=k4, VT=(K1 / k2) * (1.0 + k3 / k4))


# ---------------- SRTM2 basis-grid (reference-tissue, fixed k2') ----------------
_THETA_GRID = np.geomspace(0.004, 0.6, 96)


def srtm2_bpnd(cr, ct, tmid, dur, k2p, keep=None):
    """SRTM2 basis-grid BPND with fixed reference efflux k2'. Duration-weighted."""
    cr = np.asarray(cr, float); ct = np.asarray(ct, float)
    w = np.asarray(dur, float) * (np.ones_like(dur) if keep is None else keep.astype(float))
    best, bp = np.inf, np.nan
    for th in _THETA_GRID:
        Z = cr + (k2p - th) * frame_conv_exp(cr, tmid, dur, th)
        d = float(np.sum(w * Z * Z))
        if d <= 1e-30:
            continue
        R1 = float(np.sum(w * ct * Z) / d)
        r = ct - R1 * Z
        wr = float(np.sum(w * r * r))
        if wr < best:
            best, bp = wr, R1 * k2p / th - 1.0
    return bp


def frame_conv_exp(cr, tmid, dur, theta):
    edges = np.concatenate([[0.0], np.cumsum(dur)])
    tf = fine_grid(dur)
    cr_fine = np.interp(tf, np.concatenate([[0.0], np.asarray(tmid, float)]),
                        np.concatenate([[0.0], np.asarray(cr, float)]))
    return frame_average(conv_exp_fine(cr_fine, tf, theta), tf, edges)
