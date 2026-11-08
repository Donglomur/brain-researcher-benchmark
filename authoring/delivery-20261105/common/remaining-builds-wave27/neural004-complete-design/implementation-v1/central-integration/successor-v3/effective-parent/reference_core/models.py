"""Actual independent mean, complete-kernel and weighted-ridge computations."""
import math
from .protocol import SCHEMA, canonical, pin, require, specification, ids, feature_order, safe_metadata
from .features import array, np_module, geometry


def lineage_admit(lineage):
    safe_metadata(lineage)
    require(type(lineage) is dict and {'source', 'view', 'environment', 'reference_source', 'channel_order'} <= set(lineage), 'lineage_fields')
    feature_order('B', lineage['channel_order'])
    # These descriptors are asserted inputs; independently authenticated by caller.
    for name in ('source', 'view', 'environment', 'reference_source'):
        require(type(lineage[name]) is dict and len(lineage[name]) > 0, 'lineage_descriptor')
    return lineage


def design_admit(design, spec, lineage, budget):
    np = np_module()
    require(type(design) is dict and set(design) == {'matrix', 'rt_seconds', 'instruction', 'feature_order'}, 'design_schema')
    order = feature_order(spec['family'], lineage['channel_order'])
    require(design['feature_order'] == order, 'feature_order')
    X = array(design['matrix'], budget, 2)
    r = array(design['rt_seconds'], budget, 1)
    a = array(design['instruction'], budget, 1)
    require(X.shape == (len(r), len(order)) and r.shape == a.shape, 'design_shape')
    require(bool((r > 0).all()) and bool(((a == 0) | (a == 1)).all()), 'design_covariates')
    require(bool((X[:, 0] == 1).all()) and bool((X[:, 1] == a).all()), 'design_intercept_instruction')
    budget.tick()
    return X, r, a


def row_weights(person_ids, n, budget):
    np = np_module()
    people = ids(person_ids, n, unique=False)
    counts = {p: people.count(p) for p in sorted(set(people))}
    budget.stage(live=n * 32, work=n * max(1, len(counts)))
    w = np.asarray([1.0 / (len(counts) * counts[p]) for p in people], dtype=np.float64)
    require(bool(np.isfinite(w).all()) and abs(float(w.sum()) - 1.0) <= 1e-12, 'weight_normalization')
    return people, counts, w


def _state_admit(state, budget):
    require(type(state) is dict and set(state) == {'schema', 'candidate', 'fit_support', 'lineage', 'feature_order', 'parameters', 'diagnostics'}, 'state_schema')
    require(state['schema'] == SCHEMA, 'state_version')
    spec = specification(state['candidate'])
    lineage_admit(state['lineage'])
    require(state['feature_order'] == feature_order(spec['family'], state['lineage']['channel_order']), 'state_feature_order')
    # Pure JSON is the only representation, never pickle or an executable estimator.
    body = canonical(state)
    budget.state(body)
    support = state['fit_support']
    require(type(support) is dict and set(support) == {'person_ids', 'trial_ids', 'person_counts', 'weights'}, 'fit_support_schema')
    require(type(support['person_counts']) is dict and all(type(v) is int and v > 0 for v in support['person_counts'].values()), 'fit_support_counts')
    n = len(support['trial_ids'])
    trials = ids(support['trial_ids'], n, unique=False)
    people, counts, w = row_weights(support['person_ids'], n, budget)
    require(len(set(zip(people, trials))) == n and counts == support['person_counts'], 'fit_support_identity')
    supplied = array(support['weights'], budget, 1)
    require(supplied.shape == w.shape and bool((supplied == w).all()), 'fit_support_weights')
    return spec, body, w


def fit(candidate_id, training_design, targets, person_ids, trial_ids, lineage, budget):
    np = np_module()
    budget.tick()
    spec = specification(candidate_id)
    lineage_admit(lineage)
    X, rt, a = design_admit(training_design, spec, lineage, budget)
    n, width = X.shape
    y = array(targets, budget, 1)
    require(y.shape == (n,) and bool(((y > 0.025) & (y < 1)).all()), 'target_range_or_shape')
    people, counts, w = row_weights(person_ids, n, budget)
    trials = ids(trial_ids, n, unique=False)
    require(len(set(zip(people, trials))) == n, 'duplicate_fit_trial')
    # Preflight a conservative primitive/list representation before .tolist().
    estimate = 1024 + 256 * n + 256 * width
    require(estimate <= budget.profile['max_state_bytes'], 'resource_state_bytes')
    budget.stage(live=estimate * 4 + X.size * 8 + n * 64, work=X.size * 10)
    mu = float(w @ y)
    require(math.isfinite(mu), 'target_mean_nonfinite')
    diagnostics = {'person_weight': '1/(fit_people*person_trials)', 'fit_people': len(counts), 'fit_trials': n}
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        if spec['kind'] == 'mean':
            means = []
            absent = []
            for level in (0, 1):
                mask = a == level
                missing = not bool(mask.any())
                means.append(mu if missing else float((w[mask] @ y[mask]) / w[mask].sum()))
                absent.append(missing)
            parameters = {'global_mean': mu, 'instruction_means': means, 'absent_instruction': absent}
        elif spec['kind'] == 'kernel':
            u = np.log(rt)
            center = float(w @ u)
            constant = bool((u == u[0]).all())
            variance = 0.0 if constant else float(w @ ((u - center) ** 2))
            require(constant or (math.isfinite(variance) and variance > 0), 'kernel_nonconstant_variance')
            scale = 0.0 if constant else math.sqrt(variance)
            z = np.zeros(n) if constant else (u - center) / scale
            require(bool(np.isfinite(z).all()), 'kernel_z_nonfinite')
            parameters = {'global_mean': mu, 'log_rt_mean': center, 'log_rt_sd': scale,
                          'constant_log_rt': constant, 'rt_seconds': rt.tolist(), 'instruction': a.astype(int).tolist(),
                          'target': y.tolist(), 'standardized_log_rt': z.tolist(), 'bandwidth': spec['bandwidth']}
        else:
            raw = X[:, 1:]
            constant = (raw == raw[0]).all(axis=0)
            mean = w @ raw
            mean[constant] = raw[0, constant]
            variance = w @ ((raw - mean) ** 2)
            variance[constant] = 0.0
            require(bool(np.isfinite(mean).all()) and bool(np.isfinite(variance).all()) and bool((variance[~constant] > 0).all()), 'ridge_variance')
            keep = np.flatnonzero(~constant)
            scales = np.sqrt(variance[keep])
            Z = (raw[:, keep] - mean[keep]) / scales
            p = len(keep)
            lam = spec['lambda']
            matrix_size = min(n, p)
            live = 8 * (X.size * 3 + n * p * 5 + matrix_size**2 * 4 + p * 20 + 16 * p)
            work = n * p * max(n, p) * 4 + matrix_size**3 * 3
            budget.stage(live=live + estimate * 4, work=work)
            rhs = Z.T @ (w * (y - mu))
            if p == 0:
                beta = np.empty(0, dtype=np.float64)
                solver = 'empty_exactconstant_columns'
                norm_a = residual = 0.0
            elif p <= n:
                A = Z.T @ (w[:, None] * Z)
                A.flat[::p + 1] += lam
                beta = np.linalg.solve(A, rhs)
                solver = 'complete_primal'
                norm_a = float(np.abs(A).sum(axis=1).max())
                residual = float(np.abs(A @ beta - rhs).max())
            else:
                scaled = np.sqrt(w)[:, None] * Z
                K = scaled @ scaled.T
                K.flat[::n + 1] += lam
                dual = np.linalg.solve(K, np.sqrt(w) * (y - mu))
                beta = scaled.T @ dual
                solver = 'complete_dual'
                residual = float(np.abs(Z.T @ (w * (Z @ beta)) + lam * beta - rhs).max())
                norm_a = 0.0
                # All primal coordinates retained; exact infinity norm in bounded blocks.
                for start in range(0, p, 16):
                    stop = min(start + 16, p)
                    block = Z[:, start:stop].T @ (w[:, None] * Z)
                    block[np.arange(stop - start), np.arange(start, stop)] += lam
                    norm_a = max(norm_a, float(np.abs(block).sum(axis=1).max()))
                    budget.tick()
            require(bool(np.isfinite(beta).all()) and math.isfinite(norm_a) and math.isfinite(residual), 'ridge_solution_nonfinite')
            norm_beta = float(np.abs(beta).max()) if p else 0.0
            norm_rhs = float(np.abs(rhs).max()) if p else 0.0
            threshold = 1e-10 * max(1.0, norm_a * norm_beta + norm_rhs)
            require(math.isfinite(threshold) and residual <= threshold, 'ridge_residual')
            parameters = {'global_mean': mu, 'lambda': lam, 'means': mean.tolist(), 'constant_mask': constant.tolist(),
                          'keep_indices': keep.tolist(), 'scales': scales.tolist(), 'coefficients': beta.tolist()}
            diagnostics.update({'solver': solver, 'residual_inf': residual, 'residual_threshold': threshold,
                                'matrix_inf': norm_a, 'coefficient_inf': norm_beta, 'rhs_inf': norm_rhs})
    state = {'schema': SCHEMA, 'candidate': candidate_id,
             'fit_support': {'person_ids': people, 'trial_ids': trials, 'person_counts': counts, 'weights': w.tolist()},
             'lineage': dict(lineage), 'feature_order': list(training_design['feature_order']),
             'parameters': parameters, 'diagnostics': diagnostics}
    body = canonical(state)
    budget.state(body)
    budget.tick()
    return state


def predict(state, query_design, query_rt, instruction, trial_ids, lineage, budget):
    np = np_module()
    budget.tick()
    spec, before, w = _state_admit(state, budget)
    lineage_admit(lineage)
    for k in ('source', 'environment', 'reference_source', 'channel_order'):
        require(canonical(state['lineage'][k]) == canonical(lineage[k]), 'prediction_lineage_' + k)
    X, r, a = design_admit(query_design, spec, lineage, budget)
    qr, qa = array(query_rt, budget, 1), array(instruction, budget, 1)
    require(qr.shape == r.shape and qa.shape == a.shape and bool((qr == r).all()) and bool((qa == a).all()), 'query_covariate_join')
    trials = ids(trial_ids, len(r))
    p = state['parameters']
    require(type(p) is dict and type(p.get('global_mean')) in (int, float) and 0.025 < p['global_mean'] < 1, 'state_target_mean')
    fallback = []
    budget.stage(live=8 * (X.size * 3 + len(w) * 20 + len(r) * 10), work=X.size * 5 + len(r) * len(w) * 10)
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        if spec['kind'] == 'mean':
            require(set(p) == {'global_mean', 'instruction_means', 'absent_instruction'}, 'mean_parameters')
            means = array(p['instruction_means'], budget, 1)
            require(means.shape == (2,) and bool(((means > 0.025) & (means < 1)).all()) and type(p['absent_instruction']) is list and len(p['absent_instruction']) == 2 and all(type(x) is bool for x in p['absent_instruction']), 'mean_state')
            predictions = means[a.astype(int)]
            fallback = [trials[i] for i in range(len(r)) if p['absent_instruction'][int(a[i])]]
        elif spec['kind'] == 'kernel':
            require(set(p) == {'global_mean', 'log_rt_mean', 'log_rt_sd', 'constant_log_rt', 'rt_seconds', 'instruction', 'target', 'standardized_log_rt', 'bandwidth'}, 'kernel_parameters')
            require(p['bandwidth'] == spec['bandwidth'] and type(p['constant_log_rt']) is bool, 'kernel_spec')
            z = array(p['standardized_log_rt'], budget, 1)
            target = array(p['target'], budget, 1)
            labels = array(p['instruction'], budget, 1)
            fit_rt = array(p['rt_seconds'], budget, 1)
            require(z.shape == target.shape == labels.shape == fit_rt.shape == w.shape and bool((fit_rt > 0).all()) and bool(((target > 0.025) & (target < 1)).all()) and bool(((labels == 0) | (labels == 1)).all()), 'kernel_rows')
            constant = p['constant_log_rt']
            require(type(p['log_rt_sd']) in (int, float) and ((constant and p['log_rt_sd'] == 0) or (not constant and p['log_rt_sd'] > 0)), 'kernel_scale')
            expected_z = np.zeros(len(w)) if constant else (np.log(fit_rt) - p['log_rt_mean']) / p['log_rt_sd']
            require(bool((expected_z == z).all()), 'kernel_sealed_z')
            query_z = np.zeros(len(r)) if constant else (np.log(r) - p['log_rt_mean']) / p['log_rt_sd']
            predictions = np.empty(len(r))
            for i, value in enumerate(query_z):
                mask = labels == a[i]
                if not bool(mask.any()):
                    predictions[i] = p['global_mean']
                    fallback.append(trials[i])
                    continue
                distance = (value - z[mask]) / spec['bandwidth']
                require(bool(np.isfinite(distance).all()), 'kernel_distance_nonfinite')
                logs = np.log(w[mask]) - 0.5 * distance**2
                require(bool(np.isfinite(logs).all()), 'kernel_logweights_nonfinite')
                weights = np.exp(logs - logs.max())
                denominator = float(weights.sum())
                require(math.isfinite(denominator) and denominator > 0, 'kernel_normalizer')
                predictions[i] = float(weights @ target[mask] / denominator)
                budget.tick()
        else:
            require(set(p) == {'global_mean', 'lambda', 'means', 'constant_mask', 'keep_indices', 'scales', 'coefficients'}, 'ridge_parameters')
            require(p['lambda'] == spec['lambda'], 'ridge_lambda')
            width = X.shape[1] - 1
            means = array(p['means'], budget, 1)
            require(means.shape == (width,) and type(p['constant_mask']) is list and len(p['constant_mask']) == width and all(type(v) is bool for v in p['constant_mask']), 'ridge_stats')
            keep = p['keep_indices']
            require(type(keep) is list and all(type(v) is int for v in keep) and keep == [i for i, flag in enumerate(p['constant_mask']) if not flag], 'ridge_mask')
            require(type(p['scales']) is list and type(p['coefficients']) is list and len(p['scales']) == len(p['coefficients']) == len(keep), 'ridge_coefficient_shape')
            if keep:
                scales = array(p['scales'], budget, 1)
                beta = array(p['coefficients'], budget, 1)
                require(bool((scales > 0).all()), 'ridge_scale')
                predictions = p['global_mean'] + ((X[:, 1:][:, keep] - means[keep]) / scales) @ beta
            else:
                predictions = np.full(len(r), p['global_mean'])
        require(bool(np.isfinite(predictions).all()), 'prediction_nonfinite')
        predictions = np.clip(predictions, 0.0, 1.0)
    require(canonical(state) == before, 'state_mutated_during_prediction')
    budget.tick()
    return {'schema': 'neural004_reference_prediction_v1', 'candidate': state['candidate'], 'state_pin': pin(state),
            'trial_ids': trials, 'prediction': predictions.tolist(), 'fallback_trial_ids': fallback,
            'query_lineage': dict(lineage)}
