"""Prospective NEURAL042 fixed numerical tool; no data are bundled here.

Tort MI and EEGLAB-style windowed-sinc bandpasses follow the cited author
sources. Endpoint policy, matching, deterministic RNG and patient aggregation
are prospective benchmark choices, not a claim of MATLAB or paper parity.
"""
import hashlib
import math
import numpy as np
from scipy.signal import fftconvolve, hilbert
from scipy.optimize import linear_sum_assignment

FS = 400
N = 1000
LF = (4, 6)
HF = tuple(range(70, 141, 5))
METRICS = ('corrected_mi', 'mi', 'trial_null', 'shift_null', 'early_mi',
           'late_mi', 'theta_power', 'gamma_power', 'firing_rate',
           'harmonic_plv', 'waveform_asymmetry')
DESIGNS = ('count_only', 'nuisance_matched')
CONTRASTS = ('load3_minus_load1_correct', 'correct_minus_incorrect_within_load')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def rng_for(identity):
    seed = int.from_bytes(hashlib.sha256(('neural042-v1:' + identity).encode()).digest()[:8], 'big')
    return np.random.default_rng(seed)


def kernel(low, high):
    """EEGLAB default Hamming transition heuristic; independently expressed.

    DC-normalized lowpass difference implements firws' bandpass construction.
    These are passband edges. This is not scipy.firwin's unity-band-gain rule.
    """
    need(0 < low < high < FS / 2, 'Passband outside Nyquist')
    df = min(max(low * .25, 2), low, FS / 2 - high)
    order = int(math.ceil((3.3 * FS / df) / 2) * 2)
    t = np.arange(-order // 2, order // 2 + 1, dtype=float)
    win = np.hamming(order + 1)
    def lp(f):
        b = 2 * f / FS * np.sinc(2 * f / FS * t) * win
        return b / b.sum()
    return lp(high + df / 2) - lp(low - df / 2)


def analytic(x, low, high):
    """Filter each maintenance trial separately; never touch adjacent/probe data.

    Input exactly [0,2.5)s. Repeat its first/last values by kernel half-length,
    convolve symmetrically, then Hilbert on the 1000 retained samples. This
    explicit finite-window rule differs from the demo's real [-.5,3]s padding.
    """
    x = np.asarray(x, dtype=float)
    need(x.ndim == 2 and x.shape[1] == N and np.isfinite(x).all(), 'Finite trial x 1000 maintenance input')
    b = kernel(low, high)
    pad = len(b) // 2
    padded = np.pad(x, ((0, 0), (pad, pad)), mode='edge')
    filtered = fftconvolve(padded, b[None, :], mode='valid', axes=1)
    return hilbert(filtered, axis=1)


def mi(phase, amplitude):
    """Pooled trial/sample Tort MI, 18 bins. Unoccupied bins are unscorable.

    +pi wraps to -pi. No invented pseudocount or pseudopower. Constant positive
    amplitude returns zero; all-zero amplitude is undefined, not a null effect.
    """
    p, a = np.asarray(phase, float).ravel(), np.asarray(amplitude, float).ravel()
    need(p.shape == a.shape and p.size > 0 and np.isfinite(p).all()
         and np.isfinite(a).all() and (a >= 0).all(), 'Invalid phase/amplitude')
    bins = np.floor(((p + np.pi) % (2 * np.pi)) / (2 * np.pi) * 18).astype(int)
    counts = np.bincount(bins, minlength=18)
    if (counts == 0).any():
        return None
    means = np.bincount(bins, weights=a, minlength=18) / counts
    total = means.sum()
    if not math.isfinite(float(total)) or total <= 0:
        return None
    prob = means / total
    pos = prob > 0
    return float(max(0., (np.sum(prob[pos] * np.log(prob[pos])) + np.log(18)) / np.log(18)))


def features(x, rates):
    x, rates = np.asarray(x, float), np.asarray(rates, float)
    need(x.ndim == 2 and x.shape[1] == N and rates.shape == (len(x),)
         and np.isfinite(x).all() and np.isfinite(rates).all() and (rates >= 0).all(), 'Complete finite features')
    pairs = []
    for lf in LF:
        lo = analytic(x, lf - 1, lf + 1)
        for hf in HF:
            hi = analytic(x, hf - lf, hf + lf)
            pairs.append((np.angle(lo), np.abs(hi), np.angle(hi), lf, hf))
    theta = np.mean([np.mean(np.abs(analytic(x, lf - 1, lf + 1)) ** 2, axis=1) for lf in LF], axis=0)
    gamma = np.mean([np.mean(a * a, axis=1) for _, a, _, _, _ in pairs], axis=0)
    # Descriptive nonsinusoidal proxy: imbalance of positive/negative slopes.
    # It is a nuisance diagnostic, not proof that waveform harmonics are absent.
    d = np.diff(x, axis=1)
    rise = np.mean(np.maximum(d, 0) ** 2, axis=1)
    fall = np.mean(np.minimum(d, 0) ** 2, axis=1)
    asym = np.divide(rise - fall, rise + fall, out=np.zeros(len(x)), where=rise + fall > 0)
    return {'pairs': pairs, 'theta_power': theta, 'gamma_power': gamma,
            'firing_rate': rates, 'waveform_asymmetry': asym}


def match(a, b, nuisance, ids, strata, design):
    """Per wire/contrast: exact order-quartile + probe-membership strata.

    Count-only picks stable opaque-ID order. Nuisance arm maximizes the number
    of valid pairs, then minimizes squared standardized covariate distance;
    all three absolute standardized differences must be <=0.5. Standardization
    is pooled within stratum and contrast, without any PAC outcome. Zero-variance
    covariates need exact equality; no loosening, replacement or duplicate trial.
    """
    need(design in DESIGNS, 'Unknown matching design')
    x = np.asarray(nuisance, float)
    need(x.shape == (len(ids), 3) and np.isfinite(x).all()
         and len(set(ids)) == len(ids) and len(strata) == len(ids), 'Matching inputs')
    chosen_a, chosen_b = [], []
    for s in sorted(set(strata)):
        aa = sorted((i for i in a if strata[i] == s), key=lambda i: ids[i])
        bb = sorted((i for i in b if strata[i] == s), key=lambda i: ids[i])
        if not aa or not bb:
            continue
        if design == 'count_only':
            k = min(len(aa), len(bb)); chosen_a += aa[:k]; chosen_b += bb[:k]
            continue
        sd = np.std(x[aa + bb], axis=0, ddof=0)
        diff = np.abs(x[aa, None, :] - x[None, bb, :])
        safe = np.where(sd > 0, sd, 1.)
        delta = diff / safe
        valid = np.all(np.where(sd > 0, delta <= .5, diff == 0), axis=2)
        cost = np.sum(delta * delta, axis=2)
        # Any valid cost <=0.75; penalty dominates every possible valid sum.
        penalty = (min(len(aa), len(bb)) + 1.) * 4.
        row, col = linear_sum_assignment(np.where(valid, cost, penalty))
        for i, j in zip(row, col):
            if valid[i, j]:
                chosen_a.append(aa[i]); chosen_b.append(bb[j])
    return np.asarray(chosen_a, int), np.asarray(chosen_b, int)


def condition_stats(f, ix, identity, n_surrogates=200):
    need(type(n_surrogates) is int and n_surrogates > 1, 'At least two surrogates')
    if len(ix) < 10:
        return None
    g = rng_for(identity)
    values = {k: [] for k in ('mi', 'trial_null', 'shift_null', 'early_mi', 'late_mi', 'harmonic_plv')}
    for phase, amplitude, hp, lf, hf in f['pairs']:
        p, a, h = phase[ix], amplitude[ix], hp[ix]
        obs, early, late = mi(p, a), mi(p[:, :500], a[:, :500]), mi(p[:, 500:], a[:, 500:])
        if any(v is None for v in (obs, early, late)):
            return None
        nulls, shifts = [], []
        for _ in range(n_surrogates):
            # Uniform nonidentity cyclic permutation of whole trials preserves
            # the event-locked amplitude envelope. No same-trial pair is used.
            j = int(g.integers(1, len(ix)))
            nulls.append(mi(p, np.roll(a, j, axis=0)))
            # Independent 0.5..2.0s wrap for each trial preserves that amplitude
            # sequence's exact DFT magnitudes, unlike IID sample shuffling.
            offsets = g.integers(200, 801, size=len(ix))
            aa = np.take_along_axis(a, (np.arange(N)[None, :] - offsets[:, None]) % N, axis=1)
            shifts.append(mi(p, aa))
        if any(v is None for v in nulls + shifts):
            return None
        values['mi'].append(obs); values['early_mi'].append(early); values['late_mi'].append(late)
        values['trial_null'].append(float(np.mean(nulls))); values['shift_null'].append(float(np.mean(shifts)))
        values['harmonic_plv'].append(float(abs(np.mean(np.exp(1j * (round(hf / lf) * p - h))))))
    result = {k: float(np.mean(v)) for k, v in values.items()}
    result['corrected_mi'] = result['mi'] - result['trial_null']
    for k in ('theta_power', 'gamma_power', 'firing_rate', 'waveform_asymmetry'):
        result[k] = float(np.mean(f[k][ix]))
    return result


def wire_effects(x, rates, loads, correct, probe, ids, order, identity, n_surrogates=200):
    """All selected trials are operator-reviewed before this pure numerical API."""
    n = len(ids)
    need(n > 0 and all(len(v) == n for v in (rates, loads, correct, probe, order)), 'Trial metadata lengths')
    need(set(loads) <= {1, 3} and set(correct) <= {0, 1} and set(probe) <= {0, 1}, 'Exact load/accuracy/probe coding')
    need(len(set(order)) == n and all(type(i) is int and 0 <= i < 140 for i in order), 'Original 140-trial row identity')
    f = features(x, rates)
    # Strictly positive power is required for logarithmic nuisance covariates.
    if np.any(f['theta_power'] <= 0) or np.any(f['gamma_power'] <= 0):
        return {d: {c: None for c in CONTRASTS} for d in DESIGNS}
    nuisance = np.column_stack((np.log(f['theta_power']), np.log(f['gamma_power']), np.log1p(rates)))
    strata = [f'{order[i] // 35}:{probe[i]}' for i in range(n)]
    results = {}
    for design in DESIGNS:
        results[design] = {}
        for contrast in CONTRASTS:
            comparisons = [(lambda i: loads[i] == 3 and correct[i] == 1,
                            lambda i: loads[i] == 1 and correct[i] == 1)] if contrast == CONTRASTS[0] else [
                (lambda i, l=l: loads[i] == l and correct[i] == 1,
                 lambda i, l=l: loads[i] == l and correct[i] == 0) for l in (1, 3)]
            effects, support = [], []
            for part, (positive, negative) in enumerate(comparisons):
                aa, bb = match([i for i in range(n) if positive(i)], [i for i in range(n) if negative(i)], nuisance, ids, strata, design)
                va = condition_stats(f, aa, f'{identity}:{design}:{contrast}:{part}:a', n_surrogates)
                vb = condition_stats(f, bb, f'{identity}:{design}:{contrast}:{part}:b', n_surrogates)
                if va is None or vb is None:
                    effects = []; break
                effects.append({k: va[k] - vb[k] for k in METRICS}); support.append(len(aa))
            results[design][contrast] = None if not effects else {
                'metrics': {k: float(np.mean([v[k] for v in effects])) for k in METRICS},
                'matched_pairs': support}
    return results


def summarize(values, identity, bootstrap=10000):
    """Independent unit is patient; no channel/trial pseudoreplication."""
    x = np.asarray(values, float)
    if len(x) < 2:
        return {'n_patients': len(x), 'mean': None, 'ci95': None, 'sign_flip_p': None}
    need(np.isfinite(x).all(), 'Finite patient contrasts')
    g = rng_for(identity)
    means = np.mean(x[g.integers(0, len(x), size=(bootstrap, len(x)))], axis=1)
    null = np.mean(x[None, :] * g.choice([-1, 1], size=(bootstrap, len(x))), axis=1)
    return {'n_patients': len(x), 'mean': float(np.mean(x)),
            'ci95': np.quantile(means, [.025, .975], method='linear').tolist(),
            'sign_flip_p': float((1 + np.sum(np.abs(null) >= abs(np.mean(x)))) / (bootstrap + 1))}
