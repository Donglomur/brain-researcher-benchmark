"""Source-grounded PAC numerical evaluator; authentic/native qualification is unknown.

No author implementation is vendored. The equations and defaults are documented
in source_contract.json, including the GPL notices on the original FIR helpers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage, optimize, signal, special, stats

TASK_ID = 'PAPER-paper-signal-add-001'
SNAPSHOT = '0.240118.2135'
SOURCE_COMMIT = 'a25e8cc3f61630a428f190381745257d4506f148'
LF = np.arange(2., 15., 2.)
HF = np.arange(30., 151., 5.)
SU_HF = np.arange(70., 141., 5.)
SOURCE = json.loads(Path(__file__).with_name('source_contract.json').read_text())
HOLDS = [
    'No authentic recordings or MATLAB reference execution have been evaluated.',
    'Numerical equivalence and grading tolerances require independent native validation.',
    'The SU LFP/spike length defect is repaired only by an explicitly prospective alignment.',
    'Eligible patient/channel/unit population and owner-approved extension protocol remain unfrozen.',
    'Source exposure, protected replay, equal access budgets and component rights remain unqualified.',
]


def _array(x: Any, ndim: int, name: str) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    if a.ndim != ndim or not a.size or not np.isfinite(a).all():
        raise ValueError(f'{name} must be a nonempty finite {ndim}-D array')
    return a


def _integer(x: Any, name: str, minimum: int = 0) -> int:
    if isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return int(x)


def _sample_count(seconds: float, fs: float) -> int:
    n = seconds * fs
    if not np.isfinite(n) or seconds < 0 or not np.isclose(n, round(n), atol=1e-8, rtol=0):
        raise ValueError('window boundary must be a nonnegative integral sample count')
    return int(round(n))


def epoch_lfp(raw: Any, start_time: float, fs: float, maintenance: Any,
              pre: float, post: float, *, right_edge_bins: bool = False) -> np.ndarray:
    """Source Boolean window selection on an N-element clock.

    Unequal epoch lengths are rejected, as they cannot form the source matrix.
    The prospective SU right-edge correction is allowed only on sample-grid
    onsets; no implicit interpolation of off-grid spike/LFP clocks is made.
    """
    x = _array(raw, 1, 'raw LFP')
    onset = _array(maintenance, 1, 'maintenance')
    if not np.isfinite(start_time) or not np.isfinite(fs) or fs <= 0:
        raise ValueError('invalid sampling clock')
    if np.any(np.diff(onset) <= 0):
        raise ValueError('maintenance timestamps must be strictly increasing')
    before, after = _sample_count(pre, fs), _sample_count(post, fs)
    clock = start_time + np.arange(len(x)) / fs
    positions = (onset - start_time) * fs
    if right_edge_bins and not np.allclose(positions, np.rint(positions), atol=1e-7, rtol=0):
        raise ValueError('off-grid SU maintenance needs a frozen cross-clock alignment policy')
    trials = []
    for t in onset:
        # Search the actual source clock, preserving inclusive inequality semantics.
        if t - pre < clock[0] or t + post > clock[-1]:
            raise ValueError('incomplete maintenance epoch; do not silently trim trials')
        lo = np.searchsorted(clock, t - pre, side='left')
        hi = np.searchsorted(clock, t + post, side='right')
        trial = x[lo:hi]
        if right_edge_bins:
            if len(trial) != before + after + 1:
                raise ValueError('SU inclusive clock boundary is ambiguous')
            trial = trial[1:]
        trials.append(trial)
    if len({len(t) for t in trials}) != 1 or not len(trials[0]):
        raise ValueError('unequal/empty source epoch lengths require explicit policy')
    return np.column_stack(trials)


def binary_spike_epochs(spikes: Any, maintenance: Any, fs: float,
                        pre: float = 1.5, post: float = 4.) -> np.ndarray:
    """Author binary occupancy: (onset-pre,onset+post], ceil bins; ties collapse."""
    s = np.asarray(spikes, dtype=float)
    if s.ndim != 1 or not np.isfinite(s).all() or np.any(np.diff(s) < 0):
        raise ValueError('spikes must be a finite sorted vector (may be empty)')
    onset = _array(maintenance, 1, 'maintenance')
    if not np.isfinite(fs) or fs <= 0 or np.any(np.diff(onset) <= 0):
        raise ValueError('invalid clock or maintenance ordering')
    n = _sample_count(pre + post, fs)
    if n == 0:
        raise ValueError('empty spike window')
    out = np.zeros((n, len(onset)), dtype=bool)
    for j, t in enumerate(onset):
        rel = s[(s > t - pre) & (s <= t + post)] - (t - pre)
        ix = np.ceil(rel * fs).astype(int) - 1
        if np.any((ix < 0) | (ix >= n)):
            raise ValueError('spike-bin floating boundary is outside declared window')
        out[ix, j] = True
    return out


def source_fir_coefficients(fs: float, low: float, high: float) -> np.ndarray:
    """Independent SciPy expression of source filter equations, not native-verified.

    The bundled windows.m uses alpha=25/46 (not scipy's default Hamming 0.54).
    Each constituent lowpass is separately DC-normalized before subtraction.
    """
    if not np.isfinite([fs, low, high]).all() or not 0 < low < high < fs / 2:
        raise ValueError('band must lie strictly inside (0, Nyquist)')
    transition = min(max(low * .25, 2.), low, fs / 2 - high)
    order = int(2 * np.ceil(3.3 * fs / transition / 2))
    edges = (low - transition / 2, high + transition / 2)
    lp = [signal.firwin(order + 1, edge, fs=fs,
                       window=('general_hamming', 25 / 46), scale=True)
          for edge in edges]
    return lp[1] - lp[0]


def band_analytic(epochs: Any, fs: float, low: float, high: float) -> np.ndarray:
    x = _array(epochs, 2, 'epochs')
    b = source_fir_coefficients(fs, low, high)
    # Symmetric FIR, trial-local constant endpoint extension, group-delay removal.
    y = ndimage.convolve1d(x, b, axis=0, mode='nearest')
    return signal.hilbert(y, axis=0)


def _crop(x: np.ndarray, fs: float, edge: float) -> np.ndarray:
    n = _sample_count(edge, fs)
    if 2 * n >= x.shape[0]:
        raise ValueError('edge trimming removes all samples')
    return x[n:-n] if n else x


def tort(phase: Any, amplitude: Any, bins: int = 18) -> dict[str, Any]:
    """Pooled phase-bin mean amplitude; exact +pi excluded as in MATLAB histc.

    Empty/zero bins are reported as undefined, matching source NaN semantics;
    they are never replaced with pseudocounts or silently excluded.
    """
    p = _array(phase, 2, 'phase')
    a = _array(amplitude, 2, 'amplitude')
    bins = _integer(bins, 'bins', 2)
    if p.shape != a.shape or np.any(a < 0) or np.any((p < -np.pi) | (p > np.pi)):
        raise ValueError('phase/amplitude shape, range or nonnegativity violation')
    # rad2deg before histc is deliberate; source arithmetic boundary semantics.
    edges = np.linspace(-180., 180., bins + 1)
    indices = np.searchsorted(edges, np.rad2deg(p), side='right') - 1
    counts = np.array([np.sum(indices == k) for k in range(bins)], dtype=int)
    means = np.array([np.mean(a[indices == k]) if counts[k] else np.nan
                      for k in range(bins)])
    valid = bool(np.isfinite(means).all() and np.all(means > 0))
    probs = means / means.sum() if valid else np.full(bins, np.nan)
    mi = float(1 + np.sum(probs * np.log(probs)) / np.log(bins)) if valid else None
    return {'mi': mi, 'phase_probability': probs, 'mean_amplitude': means,
            'occupancy': counts, 'excluded_upper_edge_samples': int(np.sum(indices == bins)),
            'status': 'defined' if valid else 'undefined_empty_or_zero_amplitude_bin'}


def tort_with_surrogates(phase: Any, amplitude: Any, *, permutations: Any | None = None,
                         bins: int = 18) -> dict[str, Any]:
    p, a = _array(phase, 2, 'phase'), _array(amplitude, 2, 'amplitude')
    result = tort(p, a, bins)
    result.update({'surrogate_mi': [], 'surrogate_mean': None, 'surrogate_sd': None,
                   'z_mi': None, 'surrogate_status': 'not_requested'})
    if permutations is None:
        return result
    perm = np.asarray(permutations)
    if (perm.ndim != 2 or not np.issubdtype(perm.dtype, np.integer)
            or perm.shape[1] != a.shape[1] or len(perm) < 2):
        raise ValueError('at least two integer trial permutations required')
    expected = np.arange(a.shape[1])
    if not np.all(np.sort(perm, axis=1) == expected):
        raise ValueError('each surrogate must be a complete trial permutation')
    values = [tort(p, a[:, q], bins)['mi'] for q in perm]
    result['surrogate_mi'] = values
    if any(v is None for v in values) or result['mi'] is None:
        result['surrogate_status'] = 'undefined_phase_bins'
        return result
    mean, sd = float(np.mean(values)), float(np.std(values, ddof=1))
    result.update(surrogate_mean=mean, surrogate_sd=sd,
                  surrogate_status='defined' if sd > 0 else 'zero_surrogate_variance',
                  z_mi=(result['mi'] - mean) / sd if sd > 0 else None)
    return result


def comodulogram(epochs: Any, fs: float, *, n_surrogates: int = 0, seed: int = 0,
                 lf: Any = LF, hf: Any = HF, edge: float = .5) -> dict[str, Any]:
    x = _array(epochs, 2, 'epochs')
    low, high = _array(lf, 1, 'LF grid'), _array(hf, 1, 'HF grid')
    n_surrogates = _integer(n_surrogates, 'n_surrogates')
    _integer(seed, 'seed')
    if n_surrogates == 1:
        raise ValueError('sample surrogate SD requires zero or at least two surrogates')
    rng = np.random.default_rng(seed)
    out: list[list[dict[str, Any]]] = []
    for l in low:
        phase = np.angle(_crop(band_analytic(x, fs, l - 1., l + 1.), fs, edge))
        row = []
        for h in high:
            amplitude = np.abs(_crop(band_analytic(x, fs, h - l, h + l), fs, edge))
            # Fresh source-style randperm per frequency pair; explicit deterministic seed.
            perms = (np.stack([rng.permutation(x.shape[1]) for _ in range(n_surrogates)])
                     if n_surrogates else None)
            row.append(tort_with_surrogates(phase, amplitude, permutations=perms))
        out.append(row)
    mi = np.array([[np.nan if c['mi'] is None else c['mi'] for c in r] for r in out])
    probs = np.array([[c['phase_probability'] for c in r] for r in out])
    selected_lf = np.flatnonzero((low >= 4) & (low <= 6))
    selected_hf = np.flatnonzero((high >= 70) & (high <= 140))
    curve = (probs[np.ix_(selected_lf, selected_hf)].mean(axis=(0, 1))
             if len(selected_lf) and len(selected_hf) else None)
    return {'lf_hz': low, 'hf_hz': high, 'mi': mi, 'phase_probability': probs,
            'fig2d_curve': curve, 'cells': out, 'n_trials': x.shape[1],
            'seed': seed, 'n_surrogates': n_surrogates,
            'filter_status': 'source_equations_reexpressed_native_parity_unverified'}


def validate_lfp_masks(loads: Any, correct: Any) -> tuple[np.ndarray, np.ndarray]:
    l = _array(loads, 1, 'loads')
    c = _array(correct, 1, 'accuracy')
    if len(l) != len(c) or not np.isin(c, [0, 1]).all():
        raise ValueError('invalid trial metadata')
    masks = np.asarray(SOURCE['lfp']['stratified_trials_one_based'], dtype=int) - 1
    if masks.max() >= len(l) or len(np.unique(masks)) != masks.size:
        raise ValueError('source trial masks unavailable or duplicated')
    for j, load in enumerate([1, 3]):
        if not np.all((l[masks[:, j]] == load) & (c[masks[:, j]] == 1)):
            raise ValueError('original selected trials conflict with load/accuracy metadata')
    return masks[:, 0], masks[:, 1]


def lfp_example(raw: Any, start_time: float, fs: float, maintenance: Any,
                loads: Any, correct: Any, *, n_surrogates: int = 0, seed: int = 0) -> dict[str, Any]:
    l1, l3 = validate_lfp_masks(loads, correct)
    if len(maintenance) != len(loads):
        raise ValueError('trial metadata length mismatch')
    epochs = epoch_lfp(raw, start_time, fs, maintenance, .5, 3.)
    return {'load1': comodulogram(epochs[:, l1], fs, n_surrogates=n_surrogates, seed=seed),
            'load3': comodulogram(epochs[:, l3], fs, n_surrogates=n_surrogates, seed=seed + 1),
            'selected_trials_one_based': SOURCE['lfp']['stratified_trials_one_based'],
            'analysis_role': 'author_selected_example_source_equation_reexpression'}


def morlet_amplitude(epochs: Any, fs: float, frequencies: Any = SU_HF) -> np.ndarray:
    x = _array(epochs, 2, 'epochs')
    f = _array(frequencies, 1, 'frequencies')
    if not np.isfinite(fs) or fs <= 0 or np.any((f <= 0) | (f >= fs / 2)):
        raise ValueError('wavelet frequencies must be below Nyquist')
    half = _sample_count(1., fs)
    t = np.arange(-half, half + 1) / fs
    nconv = len(t) + len(x) - 1
    nfft = 1 << (nconv - 1).bit_length()
    transformed = np.fft.fft(x, n=nfft, axis=0)
    out = []
    for freq in f:
        width = 7. / (2 * np.pi * freq)
        wavelet = np.exp(2j * np.pi * freq * t) * np.exp(-t**2 / (2 * width**2))
        z = np.fft.ifft(np.fft.fft(wavelet, nfft)[:, None] * transformed, axis=0)
        out.append(np.abs(z[half:half + len(x)]))
    return np.stack(out, axis=2)


def su_count_table(phase: Any, amplitude_by_frequency: Any, binary_spikes: Any) -> dict[str, Any]:
    p = _array(phase, 2, 'phase')
    a = _array(amplitude_by_frequency, 3, 'amplitude by frequency')
    s = np.asarray(binary_spikes)
    if (p.shape != a.shape[:2] or s.shape != p.shape or not np.isin(s, [0, 1]).all()
            or np.any(a < 0) or np.any((p < -np.pi) | (p > np.pi))):
        raise ValueError('unaligned or invalid phase, amplitude or binary spikes')
    pf, sf = p.reshape(-1, order='F'), s.reshape(-1, order='F')
    af = a.reshape((-1, a.shape[2]), order='F')
    sd = af.std(axis=0, ddof=1)
    if not np.isfinite(sd).all() or np.any(sd == 0):
        raise ValueError('source gamma zscore is undefined for constant frequency amplitude')
    gamma = ((af - af.mean(axis=0)) / sd).mean(axis=1)
    high = gamma >= np.median(gamma)
    edges = np.linspace(-np.pi, np.pi, 11)
    bins = np.searchsorted(edges, pf, side='right') - 1
    counts, occupancy, rows = [], [], []
    for i in range(10):
        for g in [False, True]:
            m = (bins == i) & (high == g)
            counts.append(int(sf[m].sum()))
            occupancy.append(int(m.sum()))
            theta = edges[i]
            rows.append([1., np.cos(theta), np.sin(theta), float(g),
                         np.cos(theta) * g, np.sin(theta) * g])
    return {'counts': np.array(counts), 'occupancy': np.array(occupancy),
            'design_full': np.array(rows), 'gamma_threshold': float(np.median(gamma)),
            'gamma_frequency_mean': af.mean(axis=0), 'gamma_frequency_sd': sd,
            'excluded_upper_edge_samples': int(np.sum(bins == 10)),
            'excluded_upper_edge_spikes': int(sf[bins == 10].sum()),
            'normalization': 'source_all_selected_trial_samples_sample_sd',
            'exposure_offset': 'none_as_in_author_helper'}


def poisson_fit(design: Any, counts: Any) -> dict[str, Any]:
    x, y = _array(design, 2, 'design'), _array(counts, 1, 'counts')
    if x.shape[0] != len(y) or np.any(y < 0) or np.any(y != np.rint(y)):
        raise ValueError('Poisson observations must be aligned nonnegative integer counts')
    if y.sum() == 0 or np.linalg.matrix_rank(x) != x.shape[1]:
        raise ValueError('finite identifiable Poisson MLE unavailable')
    # For Poisson log-link models a finite MLE fails if a recession direction
    # leaves all positive-count predictors fixed while decreasing at least one
    # zero-count predictor. A bounded LP detects that cone without arbitrary
    # coefficient clipping or a ridge penalty that would change source models.
    zero = y == 0
    if zero.any():
        recession = optimize.linprog(x[zero].sum(axis=0), A_ub=x[zero],
                                     b_ub=np.zeros(zero.sum()), A_eq=x[~zero],
                                     b_eq=np.zeros((~zero).sum()),
                                     bounds=[(-1., 1.)] * x.shape[1], method='highs')
        if not recession.success or recession.fun < -1e-8:
            raise ValueError('finite Poisson MLE unavailable (zero-count separation)')
    b0 = np.zeros(x.shape[1]); b0[0] = np.log(y.mean())
    def objective(b):
        eta = x @ b
        if np.max(eta) > 700:
            return np.inf
        return float(np.exp(eta).sum() - y @ eta)
    def gradient(b):
        return x.T @ (np.exp(x @ b) - y)
    def hessian(b):
        return x.T @ (np.exp(x @ b)[:, None] * x)
    fit = optimize.minimize(objective, b0, jac=gradient, hess=hessian, method='trust-exact',
                            options={'gtol': 1e-8, 'maxiter': 200})
    gradient_norm = float(np.max(np.abs(gradient(fit.x))))
    if not np.isfinite(fit.x).all() or gradient_norm > 1e-6:
        raise ValueError('Poisson MLE did not converge; retain unit as unavailable')
    return {'coefficients': fit.x, 'log_likelihood': -objective(fit.x) - float(special.gammaln(y + 1).sum()),
            'fitted_counts': np.exp(x @ fit.x), 'parameters': x.shape[1],
            'gradient_max_abs': gradient_norm, 'optimizer_success': bool(fit.success)}


def su_model_comparisons(table: dict[str, Any]) -> dict[str, Any]:
    x, y = table['design_full'], table['counts']
    full = poisson_fit(x, y)
    no_int = poisson_fit(x[:, :4], y)
    no_gamma = poisson_fit(x[:, [0, 1, 2, 4, 5]], y)
    comparisons = {}
    for label, reduced, df in [('interaction', no_int, 2), ('gamma_main_effect', no_gamma, 1)]:
        lr = 2 * (full['log_likelihood'] - reduced['log_likelihood'])
        if lr < -1e-7:
            raise ValueError('nested model likelihood order violated')
        lr = max(0., lr)
        comparisons[label] = {'likelihood_ratio': lr, 'degrees_freedom': df,
                              'p_value': float(stats.chi2.sf(lr, df))}
    return {'full': full, 'no_interaction': no_int, 'no_gamma_main': no_gamma,
            'comparisons': comparisons, 'population_pac_neuron_selection': 'not_performed',
            'native_fitglme_laplace_parity': 'unverified'}


def su_example(raw: Any, spikes: Any, start_time: float, fs: float, maintenance: Any,
               loads: Any, correct: Any, *, alignment: str) -> dict[str, Any]:
    if alignment != 'prospective_right_edge_bins_v1':
        raise ValueError('SU execution requires explicit prospective_right_edge_bins_v1 alignment')
    onset, l, c = _array(maintenance, 1, 'maintenance'), _array(loads, 1, 'loads'), _array(correct, 1, 'accuracy')
    if len(onset) != len(l) or len(l) != len(c) or not np.isin(c, [0, 1]).all():
        raise ValueError('invalid trial metadata')
    artifacts = np.asarray(SOURCE['su']['artifact_trials_one_based']) - 1
    if artifacts.max() >= len(onset):
        raise ValueError('original artifact trial mask not available')
    keep = (l == 3) & (c == 1)
    keep[artifacts] = False
    if keep.sum() < 2:
        raise ValueError('at least two selected trials required')
    epochs = epoch_lfp(raw, start_time, fs, onset, 1.5, 4., right_edge_bins=True)[:, keep]
    binary = binary_spike_epochs(spikes, onset, fs)[:, keep]
    phase = _crop(np.angle(band_analytic(epochs, fs, 3., 7.)), fs, 1.5)
    gamma = _crop(morlet_amplitude(epochs, fs), fs, 1.5)
    binary = _crop(binary, fs, 1.5)
    table = su_count_table(phase, gamma, binary)
    return {'selected_trials_one_based': (np.flatnonzero(keep) + 1), 'alignment': alignment,
            'table': table, 'models': su_model_comparisons(table),
            'analysis_role': 'example_with_explicit_prospective_alignment_correction'}


def patient_contrasts(roster: list[dict[str, Any]], records: list[dict[str, Any]], *,
                      seed: int = 0, bootstrap: int = 2000) -> dict[str, Any]:
    """Prospective equal-session/equal-patient load3-load1 PAC extension.

    Every frozen roster row must be eligible or excluded with a reason. Every
    eligible channel must supply both full source-grid comodulograms. Undefined
    values are rejected for explicit roster revision, never dropped silently.
    """
    _integer(seed, 'seed'); _integer(bootstrap, 'bootstrap', 2)
    if not roster:
        raise ValueError('empty roster')
    def key(r):
        fields = ('patient', 'session', 'channel')
        if any(not isinstance(r.get(k), str) or not r[k] for k in fields):
            raise ValueError('stable patient/session/channel string keys required')
        return tuple(r[k] for k in fields)
    rk = [key(r) for r in roster]
    if len(set(rk)) != len(rk):
        raise ValueError('duplicate roster row')
    for r in roster:
        if type(r.get('eligible')) is not bool or (not r['eligible'] and not r.get('reason')):
            raise ValueError('every row needs explicit eligibility and exclusion reason')
    expected = {key(r) for r in roster if r['eligible']}
    actual = [key(r) for r in records]
    if not expected or len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError('eligible population is incomplete, duplicated or contains extras')
    session_values: dict[tuple[str, str], list[float]] = {}
    for r in records:
        a, b = _array(r['load1_mi'], 2, 'load1 MI'), _array(r['load3_mi'], 2, 'load3 MI')
        if a.shape != (len(LF), len(HF)) or b.shape != a.shape or np.any((a < -1e-12) | (a > 1)) or np.any((b < -1e-12) | (b > 1)):
            raise ValueError('complete finite source-grid MI matrices required')
        delta = float((b - a)[np.ix_((LF >= 4) & (LF <= 6), (HF >= 70) & (HF <= 140))].mean())
        session_values.setdefault(key(r)[:2], []).append(delta)
    patient_values: dict[str, list[float]] = {}
    for (patient, session), values in sorted(session_values.items()):
        patient_values.setdefault(patient, []).append(float(np.mean(values)))
    points = {p: float(np.mean(v)) for p, v in sorted(patient_values.items())}
    values = np.array(list(points.values()))
    interval = None
    if len(values) >= 2:
        rng = np.random.default_rng(seed)
        boot = np.array([rng.choice(values, len(values), replace=True).mean() for _ in range(bootstrap)])
        interval = np.quantile(boot, [.025, .975]).tolist()
    return {'protocol': 'prospective_patient_macro_v1', 'endpoint': 'mean_MI_load3_minus_load1_LF4_6_HF70_140',
            'patient_effects': points, 'mean_effect': float(values.mean()), 'patient_percentile_95_interval': interval,
            'n_patients': len(values), 'n_sessions': len(session_values), 'n_channels': len(records),
            'excluded_roster': [r for r in roster if not r['eligible']],
            'weighting': 'channels_equal_within_session_sessions_equal_within_patient_patients_equal',
            'bootstrap': bootstrap, 'seed': seed, 'scientific_qualification': 'unknown'}


def load_nwb(path: str | Path, receipt: dict[str, Any], *, example: str) -> dict[str, Any]:
    """Local read only; verifies bytes against a supplied source receipt, not its trust.

    No downloads. HDF5 LFP storage is explicitly samples x channels. A receipt is
    not an acquisition-authority credential or evidence of native qualification.
    """
    import h5py
    if example not in ('lfp', 'su'):
        raise ValueError('example must be lfp or su')
    required = ('sha256', 'bytes', 'path', 'asset_id', 'version', 'dandiset')
    if any(k not in receipt for k in required) or receipt['version'] != SNAPSHOT or receipt['dandiset'] != '000673':
        raise ValueError('complete exact 2024 DANDI receipt required')
    p = Path(path)
    digest = hashlib.sha256()
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    if p.stat().st_size != receipt['bytes'] or digest.hexdigest() != receipt['sha256']:
        raise ValueError('local file does not match supplied receipt')
    subject, channel, unit = (4, 49, None) if example == 'lfp' else (26, 33, 20)
    expected_path = f'sub-{subject}/sub-{subject}_ses-1_ecephys+image.nwb'
    if receipt['path'] != expected_path:
        raise ValueError('receipt identifies the wrong source example')
    if (receipt['sha256'] != SOURCE[example]['asset_sha256'] or receipt['bytes'] != SOURCE[example]['asset_bytes'] or receipt['asset_id'] != SOURCE[example]['asset_id']):
        raise ValueError('receipt conflicts with source-reported example asset identity')
    def text_scalar(value):
        value = value[()]
        return value.decode() if isinstance(value, bytes) else str(value)
    with h5py.File(p, 'r') as f:
        if text_scalar(f['general/subject/subject_id']) != str(subject) or text_scalar(f['general/session_id']) != '1':
            raise ValueError('NWB subject/session identity does not match example')
        dataset = f['acquisition/LFPs/data']
        if dataset.ndim != 2 or dataset.shape[1] < channel:
            raise ValueError('expected NWB sample x channel LFP storage')
        clock = f['acquisition/LFPs/starting_time']
        result = {'raw': np.asarray(dataset[:, channel - 1], dtype=float),
                  'start_time': float(clock[()]), 'fs': float(clock.attrs['rate'])}
        for target, source in [('maintenance', 'timestamps_Maintenance'), ('loads', 'loads'), ('correct', 'response_accuracy')]:
            result[target] = np.asarray(f[f'intervals/trials/{source}'][()])
        if unit is not None:
            supplied_index = np.asarray(f['units/spike_times_index'][()])
            flat = f['units/spike_times']
            if (supplied_index.ndim != 1 or flat.ndim != 1 or len(supplied_index) < unit
                    or not np.isfinite(supplied_index).all()
                    or np.any(supplied_index != np.rint(supplied_index))
                    or np.any(supplied_index < 0) or np.any(supplied_index > len(flat))
                    or np.any(np.diff(supplied_index) < 0)):
                raise ValueError('invalid ragged spike index')
            index = supplied_index.astype(np.int64)
            start = index[unit - 2] if unit > 1 else 0
            result['spikes'] = np.asarray(f['units/spike_times'][start:index[unit - 1]], dtype=float)
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    return None if isinstance(value, float) and not np.isfinite(value) else value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['lfp-example', 'su-example', 'patient-contrast'])
    parser.add_argument('input', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--surrogates', type=int, default=0)
    parser.add_argument('--alignment', choices=['prospective_right_edge_bins_v1'])
    args = parser.parse_args()
    if args.output.resolve() in {args.input.resolve(), args.receipt.resolve() if args.receipt else None}:
        parser.error('output must not overwrite an input or receipt')
    if args.mode == 'patient-contrast':
        payload = json.loads(args.input.read_text())
        result = patient_contrasts(payload['roster'], payload['records'], seed=args.seed)
    else:
        if args.receipt is None:
            parser.error('--receipt is required for local NWB analysis')
        example = args.mode.split('-')[0]
        values = load_nwb(args.input, json.loads(args.receipt.read_text()), example=example)
        result = (lfp_example(**values, n_surrogates=args.surrogates, seed=args.seed) if example == 'lfp'
                  else su_example(**values, alignment=args.alignment))
    report = {'task_id': TASK_ID, 'implementation': 'initial-evaluator-v1',
              'source_commit': SOURCE_COMMIT, 'dandi_snapshot': SNAPSHOT,
              'scientific_qualification': 'unknown', 'native_reference_verified': False,
              'grading_tolerance_registered': False, 'holds': HOLDS, 'result': result}
    args.output.write_text(json.dumps(_jsonable(report), indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
