"""Actual finite-pseudopopulation and weighted/masked crossed resampling.

Source-only implementation. No estimator or RNG executes during import. These
are prespecified empirical competitors, not exact confidence procedures. See
METHODS_F01.md for the population, correction, hierarchy and failure policy.
"""
import hashlib
import json
import math
from .common import require, result, ScientificGate

FINITE = 'finite_integer_pseudopop_calibrated_v1'
MASKED = 'crossed_known_ratio_mask_pairs_v1'
IID = 'crossed_iid_rows_columns_aligned_trials'
RNG = 'numpy.PCG64.SeedSequence-axis-domain-v1'


def design_for(protocol):
    """Metadata selection; never infer a finite design from sample dimensions."""
    if protocol.get('family') == 'F10':
        require(protocol.get('sampling') == 'uniform_without_replacement',
                'F10 requires its original finite sampling law')
        return FINITE
    if protocol.get('family') == 'F11':
        require(protocol.get('sampling') == 'iid_rows_columns', 'F11 sampling law')
        require(protocol.get('weight_law') == 'known_density_ratio' and
                protocol.get('mask_law') == 'independent_entry_bernoulli',
                'F11 must retain known weights and joint mask law')
        return MASKED
    require(protocol.get('sampling') == 'iid_rows_columns' and
            protocol.get('mask_law', 'complete') == 'complete' and
            protocol.get('weight_law', 'none') == 'none',
            'unsupported crossed resampling design', 'qualification_required')
    return IID


def validate_plan(protocol, request):
    design = design_for(protocol)
    require(protocol.get('resampling_design') == design, 'resampling design substitution')
    require(protocol.get('resampling_qualification_id'),
            'G14 source and empirical qualification required', 'qualification_required')
    seeds = request.get('seeds')
    require(type(seeds) is list and len(seeds) == 999 and
            all(type(s) is int and 0 <= s < 2**64 for s in seeds) and
            len(set(seeds)) == 999, '999 unique presealed uint64 seeds required')
    digest = hashlib.sha256(json.dumps(seeds, separators=(',', ':')).encode()).hexdigest()
    require(request.get('seeds_sha256') == digest, 'seed ledger substitution')
    rng = request.get('rng_source', {})
    require(rng.get('algorithm') == RNG and type(rng.get('numpy_version')) is str
            and rng['numpy_version'], 'exact RNG dependency source required')
    require(request.get('point_request', {}).get('weight_normalization',
            'fixed_tuple_count') == 'fixed_tuple_count', 'target normalization changed')
    return design


def _indices(np, design, P, Q, finite, seed):
    # Separate deterministic streams: row draws cannot consume column state.
    row = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, 0])))
    col = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, 1])))
    if design == FINITE:
        R, C = finite
        # Distinct pseudo-units, NOT a with-replacement draw from P/Q units.
        ir = np.arange(P) if P == R else row.choice(R, size=P, replace=False) // (R // P)
        ic = np.arange(Q) if Q == C else col.choice(C, size=Q, replace=False) // (C // Q)
    else:
        ir, ic = row.integers(P, size=P), col.integers(Q, size=Q)
    return ir, ic


def _slice(arrays, ir, ic):
    out = {'trials': arrays['trials'][:, ir][:, :, ic]}
    if 'mask' in arrays:
        out['mask'] = arrays['mask'][:, ir][:, :, ic]
    if 'row_weights' in arrays:
        out['row_weights'] = arrays['row_weights'][ir]
    if 'column_weights' in arrays:
        out['column_weights'] = arrays['column_weights'][ic]
    return out


def resample(payload):
    import numpy as np
    from .references import point
    p, req = payload['protocol'], payload['request']
    design = validate_plan(p, req)
    require(np.__version__ == req['rng_source']['numpy_version'], 'RNG environment changed')
    a = {k: np.asarray(v) for k, v in payload['arrays'].items()
         if k in {'trials', 'mask', 'row_weights', 'column_weights'}}
    require(a['trials'].ndim == 3, 'aligned T,P,Q input required')
    T, P, Q = a['trials'].shape
    require(T == p['trial_view'] and p.get('trials_aligned') is True,
            'original aligned trial hierarchy required')
    require(P > 1 and Q > 1, 'two crossed sampling units required', 'insufficient_support')
    finite = req['point_request'].get('finite_population')
    if design == FINITE:
        require(finite in ([512, 256], (512, 256)), 'exact finite population required')
        R, C = finite
        require(R >= P and C >= Q and R % P == 0 and C % Q == 0,
                'integer pseudo-population replication required', 'qualification_required')
        require(p.get('mask_law', 'complete') == 'complete' and
                ('mask' not in a or a['mask'].all()), 'F10 complete observed population sample')
        require(all((a[k] == 1).all() for k in ('row_weights', 'column_weights') if k in a),
                'F10 uniform units cannot carry importance weights')
        cR = math.sqrt(P * (R - 1) / (R * (P - 1)))
        cC = math.sqrt(Q * (C - 1) / (C * (Q - 1)))
    else:
        require(finite is None, 'infinite weighted/iid resampling cannot change finite target')
        cR = cC = 1.
    if design == MASKED:
        require({'mask', 'row_weights', 'column_weights'} <= set(a),
                'F11 requires all observed weights and mask operands')
        require(p.get('mask_unit') == 'entry_shared_trials' and
                0 < p.get('mask_probability', 0) <= 1,
                'F11 shared-trial Bernoulli unit law required')
        require(a['mask'].shape == a['trials'].shape and
                (a['mask'] == a['mask'][0]).all(), 'shared mask alignment')
        require(a['row_weights'].shape == (P,) and a['column_weights'].shape == (Q,),
                'weight identities align with original axes')
        require(np.isfinite(a['row_weights']).all() and (a['row_weights'] > 0).all()
                and (a['column_weights'] == 1).all(), 'known positive row density ratios')
    # Validate observed IDs before replacing them by logical bootstrap slot IDs.
    for field, n in (('row_ids', P), ('column_ids', Q)):
        ids = p.get(field)
        require(ids is None or (len(ids) == n and len(set(ids)) == n),
                'original axis IDs are not unique/aligned')
    proto = dict(p, row_ids=None, column_ids=None)
    calls = []
    def estimate(ir, ic):
        try:
            out = point(dict(payload, arrays=_slice(a, ir, ic), protocol=proto,
                             request=req['point_request']))
        except ScientificGate as error:
            out = result(status=error.status, diagnostics={'reason': str(error)})
        calls.append(out['status'])
        pair = [out['outputs'].get('A'), out['outputs'].get('B')]
        return pair, out
    rows, cols = np.arange(P), np.arange(Q)
    base, original = estimate(rows, cols)
    def finite_pair(pair):
        return all(v is not None and math.isfinite(v) for v in pair)
    require(finite_pair(base), 'original joint moments unavailable', original['status'])
    gamma, moments, statuses, parents = [], [], [], []
    for seed in req['seeds']:
        ir, ic = _indices(np, design, P, Q, finite, seed)
        both, out = estimate(ir, ic)
        if design == FINITE:
            row_pair, row_out = (base, original) if P == finite[0] else estimate(ir, cols)
            col_pair, col_out = (base, original) if Q == finite[1] else estimate(rows, ic)
            good = finite_pair(both) and finite_pair(row_pair) and finite_pair(col_pair)
            # Calibrate each independent count vector, including its interaction.
            # This is an explicit moment-level replicate, not altered trial data.
            pair = [base[j] + cR * (row_pair[j] - base[j]) +
                    cC * (col_pair[j] - base[j]) + cR * cC *
                    (both[j] - row_pair[j] - col_pair[j] + base[j])
                    for j in range(2)] if good else [None, None]
            original_statuses = [out['status'], row_out['status'], col_out['status']]
        else:
            pair = both
            original_statuses = [out['status']]
        value = pair[0] / pair[1] if finite_pair(pair) and pair[1] != 0 else None
        ok = (value is not None and math.isfinite(value) and value > 0 and
              all(s == 'ok' for s in original_statuses))
        # Invalid replicates remain in the denominator and in the full ledger.
        gamma.append(value if ok else np.nan)
        moments.append(pair)
        statuses.append('ok' if ok else 'nonphysical_estimate')
        parents.append({'seed': seed, 'point_statuses': original_statuses,
                        'row_indices': ir.tolist(), 'column_indices': ic.tolist()})
    covariance = np.cov(np.asarray(moments, float).T, ddof=1) if all(map(finite_pair, moments)) else None
    if design == FINITE and P == finite[0] and Q == finite[1] and covariance is not None:
        # A complete deterministic F10 population has no sampling uncertainty;
        # avoid an artificial rounding residual from centering identical floats.
        covariance = np.zeros((2, 2), dtype=float)
    valid = all(s == 'ok' for s in statuses)
    status_labels = sorted(set(calls) | set(statuses))
    code = {label: i for i, label in enumerate(status_labels)}
    return result({'bootstrap_gamma': np.asarray(gamma), 'moment_covariance': covariance,
                   'statuses': np.asarray([code[s] for s in statuses], dtype=np.uint16),
                   'point_call_statuses': np.asarray([code[s] for s in calls], dtype=np.uint16),
                   'replicate_point_statuses': np.asarray([[code[s] for s in v['point_statuses']]
                       for v in parents], dtype=np.uint16),
                   'replicate_row_indices': np.asarray([v['row_indices'] for v in parents], dtype=np.int64),
                   'replicate_column_indices': np.asarray([v['column_indices'] for v in parents], dtype=np.int64),
                   'seeds': np.asarray(req['seeds'], dtype=np.uint64)},
        {'resamples': 999, 'seeds_sha256': req['seeds_sha256'], 'status_labels': status_labels,
         'design': design, 'rng_source': req['rng_source'], 'finite_population': finite,
         'row_correction': cR, 'column_correction': cC, 'actual_point_calls': len(calls),
         'original_point_status': original['status'],
         'weight_normalization': 'fixed_tuple_count', 'all_trials_carried': True,
         'mask_reestimated_or_imputed': False},
        ['Empirical crossed bootstrap competitor; no universal finite-sample coverage theorem.',
         'Finite correction matches linear first-order count covariance, not exact nonlinear risk.',
         'Weighted/masked product resampling can overcount interactions or fail near degeneracy; G14 remains.'],
        status='ok' if valid else 'nonphysical_estimate')
