"""Prospective portable Stage2 operator method; fitting is never run on import.

The caller must create an OS-isolated fresh process for each of 27 contexts.
This in-memory API is not a sandbox and cannot establish execution provenance.
"""
import importlib.util
import math
from pathlib import Path
import sys
import time

import numpy as np

_spec = importlib.util.spec_from_file_location('_spatial_contracts', Path(__file__).with_name('contracts.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

ECCENTRICITIES = (0., .00551, .014, .0269, .0459, .0731, .112, .166, .242, .348, .498, .707, 1.)
SIGMAS = (1., 2., 4., 8., 16., 32., 64.)
SEED_EXPONENTS = (.5, .25, .125)
RATIOS = tuple(10. ** (-8. + i * (7.9 / 17.)) for i in range(18))
LOW_S = 1e-6
HIGH_GR = float(np.nextafter(1., 0.))
MAX_NFEV = 500
MAX_RESIDUAL_CALLS_PER_START = 3000
SOLVER_KWARGS = dict(method='trf', jac='2-point', ftol=1e-8, xtol=1e-8,
                     gtol=1e-8, x_scale=1., loss='linear', f_scale=1.,
                     diff_step=None, tr_solver='exact', max_nfev=MAX_NFEV,
                     verbose=0)


def geometry_grid():
    """Source loop order and float-exact duplicates retained; fixed bounds only."""
    out = []
    for ei, ecc in enumerate(ECCENTRICITIES):
        for ai in range(1 if ei == 0 else 16):
            angle = 2 * math.pi * ai / 16
            row = 50.5 - math.sin(angle) * 100 * ecc
            col = 50.5 + math.cos(angle) * 100 * ecc
            for sigma in SIGMAS:
                for exponent in SEED_EXPONENTS:
                    if -49 <= row <= 150 and -49 <= col <= 150:
                        out.append((row, col, sigma * math.sqrt(exponent)))
    C.need(len(out) == 3969 and len(set(out)) == 2835, 'frozen grid counts')
    return out


def training_gain(y, prediction, *, sign_free):
    """Training-only DC projection; no fitted/intercept value crosses contexts."""
    y = np.asarray(y); h = np.asarray(prediction)
    C.need(y.ndim == 1 and h.shape == y.shape and y.size > 0
           and np.isfinite(y).all() and np.isfinite(h).all(), 'finite training support')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        yc = y - np.mean(y); hc = h - np.mean(h)
        # Scale before dot products: a finite nonconstant Gaussian tail can
        # otherwise have hc@hc==0 through underflow, silently inventing gain0.
        hs = float(np.max(np.abs(hc))); ys = float(np.max(np.abs(yc)))
        gain = 0.
        if hs and ys:
            hn, yn = hc / hs, yc / ys
            coefficient = float((hn @ yn) / (hn @ hn))
            am, ae = math.frexp(coefficient); ym, ye = math.frexp(ys); hm, he = math.frexp(hs)
            gain = math.ldexp(am * ym / hm, ae + ye - he)
            C.need(gain != 0. or coefficient == 0., 'training_gain_underflow')
        if not sign_free:
            gain = max(0., gain)
        residual = gain * hc - yc
        rs = float(np.max(np.abs(residual)))
        if rs:
            rm, re = math.frexp(rs); normalized = residual / rs
            sse = math.ldexp(rm * rm * float(normalized @ normalized), 2 * re)
            C.need(sse > 0., 'nonzero_training_sse_underflow')
        else:
            sse = 0.
    C.need(math.isfinite(gain) and math.isfinite(sse) and np.isfinite(residual).all(), 'representable training objective')
    return gain, residual, sse


class Budget:
    """Pre-operation logical counts; external supervisor must enforce hard limits."""
    def __init__(self, limits, clock=time.monotonic):
        C.need(type(limits) is dict and set(limits) == {'origin', 'deadline', 'max_forward_calls', 'max_residual_calls'}, 'exact original-clock limits')
        C.need(all(type(limits[k]) in (int, float) and math.isfinite(limits[k]) for k in ('origin', 'deadline'))
               and limits['deadline'] > limits['origin'], 'finite original absolute deadline')
        C.need(all(type(limits[k]) is int and limits[k] > 0 for k in ('max_forward_calls', 'max_residual_calls')), 'positive shared call caps')
        self.limits = limits.copy(); self.clock = clock
        self.forward_calls = 0; self.residual_calls = 0
        self.check()

    def check(self):
        now = self.clock()
        if not math.isfinite(now) or now < self.limits['origin'] or now >= self.limits['deadline']:
            raise RuntimeError('original_context_deadline')

    def take(self, kind):
        self.check()
        attr = kind + '_calls'; cap = self.limits['max_' + attr]
        if getattr(self, attr) >= cap:
            raise RuntimeError('context_' + kind + '_call_cap')
        setattr(self, attr, getattr(self, attr) + 1)


def validate_context(context, rows):
    C.need(type(context) is dict and set(context) == {'participant', 'role', 'response_indices', 'signals'}, 'exact training context fields')
    person, role = context['participant'], context['role']
    selected = C.context_rows(rows, person)
    idx = C.indices(role)
    C.need(context['response_indices'] == idx, 'unaltered original sample indices')
    signals = context['signals']
    C.need(type(signals) is dict and set(signals) == set(C.S.protocol.SIGNALS), 'all four released signals')
    n = C.S.protocol.RELEASED_COUNTS[person]
    # Validate every shape before numerical iteration, including the last signal.
    for signal, value in signals.items():
        C.need(type(value) is dict and set(value) == {'responses', 'aperture', 'aperture_identity', 'band'}, 'exact signal context fields')
        y, a = value['responses'], value['aperture']
        C.source_responses(y, (n, len(idx)))
        C.need(type(a) is np.ndarray and a.dtype == np.dtype('float64') and a.shape == (100, 100, 75), 'full signed aperture')
        C.need(C.S.interface._sha(value['aperture_identity']), 'operator-bound exact aperture SHA256')
        C.need(value['band'] == C.S.protocol.band(person, signal), 'released participant band')
    for value in signals.values():
        C.need(np.isfinite(value['aperture']).all(), 'finite signed aperture')
    return selected, idx


def _unit(aperture, geometry, ratio, idx, budget):
    budget.take('forward')
    result = C.S.forward.evaluate(aperture, [*geometry, 1., ratio], model='GS' if ratio else 'OG')
    C.need(result['status'] == 'defined', 'unsupported portable baseline forward: ' + str(result['reason']))
    return result['prediction'][idx]


def project_og_grid(aperture, idx, geometries, budget, block_size=16):
    """Blocked input-only OG basis, same equation as vendored scalar forward.

    BLAS summation order can differ; no bitwise native parity is claimed.
    Production fixes block_size16 and the complete3969-entry grid. Small
    invented geometry/aperture arrays exercise the factorization in controls.
    """
    C.need(type(block_size) is int and block_size == 16, 'frozen block width')
    res = aperture.shape[0]
    rows, cols = np.meshgrid(np.arange(1, res + 1, dtype=float),
                             np.arange(1, res + 1, dtype=float), indexing='ij')
    design = aperture.reshape((res * res, aperture.shape[2]), order='F').T[idx]
    predictions = np.empty((len(geometries), len(idx)), dtype=np.float64)
    for offset in range(0, len(geometries), block_size):
        block = geometries[offset:offset + block_size]
        kernels = np.empty((res * res, len(block)), dtype=np.float64)
        with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
            for i, (r, c, s) in enumerate(block):
                budget.take('forward')
                exponent = -.5 * ((rows-r)/s)**2 - .5 * ((cols-c)/s)**2
                kernel = np.exp(exponent) * (1. / (2*np.pi*np.float64(s)**2))
                kernels[:, i] = kernel.reshape(-1, order='F')
            predictions[offset:offset + len(block)] = (design @ kernels).T
        budget.check()
    C.need(np.isfinite(predictions).all(), 'representable complete grid projection')
    return predictions


def _distinct_best(ranked, count, excluded=()):
    selected = []; seen = set(excluded)
    for _, _, geometry in sorted(ranked, key=lambda x: (x[0], x[1])):
        key = tuple(float(z) for z in geometry)
        if key not in seen:
            selected.append(key); seen.add(key)
            if len(selected) == count:
                return selected
    raise ValueError('insufficient distinct complete grid starts')


def choose_starts(y, aperture, idx, og_predictions, *, model, sign_free, budget):
    grid = geometry_grid()
    ranked = []
    for i, (geometry, h) in enumerate(zip(grid, og_predictions)):
        budget.check()
        ranked.append((training_gain(y, h, sign_free=sign_free)[2], i, geometry))
    C.need(len(ranked) == 3969, 'complete source grid predictions')
    ratio = .1 if model == 'GS' else 0.
    mandatory = [(50.5, 50.5, 25., ratio), (50.5, 50.5, 2.5, ratio)]
    if model == 'OG':
        all_ranked = [(sse, i, (*geometry, 0.)) for sse, i, geometry in ranked]
    else:
        best = _distinct_best(ranked, 4)
        all_ranked = []
        for geometry in best:
            for gr in RATIOS:
                pred = _unit(aperture, geometry, gr, idx, budget)
                sse = training_gain(y, pred, sign_free=sign_free)[2]
                all_ranked.append((sse, len(all_ranked), (*geometry, gr)))
        C.need(len(all_ranked) == 72, 'all four geometries times eighteen GS ratios')
    return mandatory + _distinct_best(all_ranked, 2, mandatory)


def _solver():
    # No installation, download or capability promotion; exact qualified runtime needed.
    import scipy
    from scipy.optimize import least_squares
    C.need(sys.version_info[:3] == (3, 11, 6) and np.__version__ == '2.4.6'
           and scipy.__version__ == '1.17.1', 'frozen portable solver runtime')
    return least_squares


def fit_case(y, aperture, idx, og_predictions, *, model, sign_free, budget, solver, audit):
    keep = np.isfinite(y)
    if not keep.any():
        audit.update(status='unsupported_no_training_support', starts=[])
        return [50.5, 50.5, 0., 0., 0.]
    y = y[keep]; idx = np.asarray(idx)[keep]
    og_predictions = [h[keep] for h in og_predictions]
    starts = choose_starts(y, aperture, idx, og_predictions, model=model, sign_free=sign_free, budget=budget)
    candidates = []; audit['starts'] = [{'start_geometry': list(start), 'status': 'not_entered'} for start in starts]
    for start_index, start in enumerate(starts):
        count = 0
        start_log = audit['starts'][start_index]
        start_log['status'] = 'entered'
        def residual(x):
            nonlocal count
            if count >= MAX_RESIDUAL_CALLS_PER_START:
                raise RuntimeError('per_start_residual_call_cap')
            budget.take('residual'); count += 1
            pred = _unit(aperture, x[:3], float(x[3]) if model == 'GS' else 0., idx, budget)
            return training_gain(y, pred, sign_free=sign_free)[1]
        lower = [-49., -49., LOW_S] + ([0.] if model == 'GS' else [])
        upper = [150., 150., np.inf] + ([HIGH_GR] if model == 'GS' else [])
        x0 = list(start if model == 'GS' else start[:3])
        # Source-shaped starts already interior for S/GR. SciPy may move a bound
        # point into its strict feasible interior; candidate parameters are never repaired.
        try:
            result = solver(residual, x0, bounds=(lower, upper), **SOLVER_KWARGS)
            budget.check()
            C.need(type(result.status) in (int, np.int32, np.int64) and 0 <= result.status <= 4, 'finite solver termination')
            C.need(type(result.nfev) in (int, np.int32, np.int64) and 0 <= result.nfev <= MAX_NFEV, 'bounded solver nfev')
            x = np.asarray(result.x, dtype=float)
            C.need(x.shape == (len(x0),) and np.isfinite(x).all()
                   and np.all(x >= lower) and np.all(x <= upper), 'solver parameter domain')
            # Count final check independently of SciPy's nfev conventions.
            residual(x)
            pred = _unit(aperture, x[:3], float(x[3]) if model == 'GS' else 0., idx, budget)
            gain, _, sse = training_gain(y, pred, sign_free=sign_free)
            parameters = [float(z) for z in x[:3]] + [gain, float(x[3]) if model == 'GS' else 0.]
            candidates.append((sse, len(candidates), parameters))
            start_log.update(status='evaluation_limit' if result.status == 0 else 'solver_terminated',
                             solver_status=int(result.status), solver_nfev=int(result.nfev),
                             residual_calls=count, training_dc_sse=sse)
        except Exception as exc:
            message = str(exc)
            start_log.update(status='failed', residual_calls=count,
                             error_type=type(exc).__name__[:80], error=message[:512],
                             error_truncated=len(message)>512, original_error_characters=len(message))
            audit['status'] = 'failed_whole_context_required'
            raise
    C.need(len(candidates) == 4, 'all four mandatory starts complete')
    best = min(candidates, key=lambda x: (x[0], x[1]))
    audit.update(status='defined', chosen_start=best[1], training_dc_sse=best[0])
    return best[2]


def fit_context(context, rows, roster_sha256, *, limits, clock=time.monotonic, solver=None):
    """Return (exact canonical output bytes, audit), or raise with no partial output.

    solver injection is for invented controls only. Production must omit it and
    supply external process/runtime/source receipts; no receipt is minted here.
    """
    budget = Budget(limits, clock)
    selected, idx = validate_context(context, rows)
    budget.check(); fit = _solver() if solver is None else solver
    output = []; reports = []
    audit = {'profile': C.PROFILE, 'participant': context['participant'], 'role': context['role'],
             'cases': reports, 'scientific_qualification': False,
             'solver_injected_control_only': solver is not None}
    try:
        # Cache only inside this fresh participant-role context. No response or
        # fit state can be exported for another role by this API.
        grid_cache = {}
        for signal in C.S.protocol.SIGNALS:
            item = context['signals'][signal]
            identity = item['aperture_identity']
            if identity not in grid_cache:
                grid_cache[identity] = (item['aperture'], project_og_grid(item['aperture'], idx, geometry_grid(), budget))
            else:
                C.need(np.array_equal(item['aperture'], grid_cache[identity][0]), 'same aperture identity must bind exact same numeric array')
            predictions = grid_cache[identity][1]
            chosen = [r for r in selected if r['signal'] == signal]
            signal_ids = list(dict.fromkeys(r['electrode_id'] for r in chosen))
            for row in chosen:
                report = {'case_id': row['case_id']}; reports.append(report)
                params = fit_case(item['responses'][signal_ids.index(row['electrode_id'])],
                                  item['aperture'], idx, predictions,
                                  model=row['model'], sign_free=row['allow_negative_gain'],
                                  budget=budget, solver=fit, audit=report)
                output.append({'case_id': row['case_id'], 'parameters': params})
        doc = {'schema': 'visual_alpha_context_parameters_v1', 'roster_sha256': roster_sha256,
               'participant': context['participant'], 'role': context['role'], 'cases': output}
        admitted = C.admit_context(C.encode(doc), rows, roster_sha256, context['participant'], context['role'])
        budget.check()
        audit.update(status='complete', forward_calls=budget.forward_calls, residual_calls=budget.residual_calls)
        return C.encode(admitted), audit
    except Exception as exc:
        audit.update(status='failed_no_output', forward_calls=budget.forward_calls, residual_calls=budget.residual_calls)
        # Retain the complete attempted-start account for the supervising caller.
        exc.spatial_audit = audit
        raise


def prospective_resources(person, role, *, distinct_apertures=4):
    """Metadata-derived ceilings, explicitly not an empirical runtime promise."""
    C.need(type(distinct_apertures) is int and 1 <= distinct_apertures <= 4, 'metadata-bound distinct aperture count')
    n = C.S.protocol.RELEASED_COUNTS[person]; t = len(C.indices(role)); cases = n * 8
    residual = cases * 4 * MAX_RESIDUAL_CALLS_PER_START
    return {'participant': person, 'role': role, 'cases': cases,
            'aperture_bytes': 4 * 100 * 100 * 75 * 8,
            'response_bytes': 4 * n * t * 8,
            'single_signal_grid_prediction_bytes': 3969 * t * 8,
            'distinct_apertures': distinct_apertures,
            'cached_grid_prediction_bytes': distinct_apertures * 3969 * t * 8,
            'kernel_block_bytes': 10000 * 16 * 8,
            'audit_json_bytes_upper_bound': 8192 + cases * 3072,
            'audit_bound_derivation': 'four fixed successful start rows <=512B each plus512B case wrapper and512B slack;8192B global/header allowance includes at most one512-character escaped failure message; fixed case IDs <=128B; finite scalar repr <=24 chars; failure stops context',
            'grid_design_upper_bytes': 10000 * (75 + t) * 8,
            'grid_kernel_elements': distinct_apertures * 3969 * 10000,
            'grid_projection_multiply_add_pairs': distinct_apertures * 3969 * 10000 * t,
            'dynamic_forward_pixel_frame_multiply_add_pairs_upper': (6*n*72 + residual + cases*4) * 10000 * 75,
            'solver_starts_per_case': 4, 'solver_max_nfev_per_start': MAX_NFEV,
            'max_residual_calls_per_start': MAX_RESIDUAL_CALLS_PER_START,
            'max_residual_calls': residual,
            'max_forward_calls': distinct_apertures * 3969 + 6 * n * 72 + residual + cases * 4,
            'wall_seconds': None, 'process_memory_bytes': None,
            'limit_selection': 'operator must freeze finite equal candidate/baseline deadline and process envelope before numeric exposure',
            'qualification': 'unmeasured; array formulas exclude interpreter/BLAS workspace; supervisor must enforce; cap exhaustion fails complete context',
            'scope_reduction_allowed': False}
