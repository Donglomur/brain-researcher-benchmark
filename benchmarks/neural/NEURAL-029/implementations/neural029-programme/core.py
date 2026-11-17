"""Registered 1s-to-2s calcium response metric; no I/O or fitting."""
import math
from source_identity_join import support_report


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def numeric(x):
    if type(x) is list:
        return all(numeric(y) for y in x)
    return type(x) in (int, float) and math.isfinite(x)


def validate(doc, public, np):
    need(type(doc) is dict and set(doc) == {'schema', 'predictions'} and
         doc['schema'] == 'neural029-predictions-v1', 'exact submission schema')
    expected = {p['pair_id']: p for p in public['pairs']}
    need(expected and len(expected) == len(public['pairs']) and type(doc['predictions']) is list
         and len(doc['predictions']) == len(expected), 'complete pair inventory')
    result = {}
    for row in doc['predictions']:
        need(type(row) is dict and set(row) == {'pair_id', 'values'}, 'exact pair fields')
        key = row['pair_id']
        need(type(key) is str and key in expected and key not in result, 'known unique pair')
        p = expected[key]
        need(type(row['values']) is list and numeric(row['values']), 'finite nonboolean outputs')
        x = np.asarray(row['values'], dtype=np.float64)
        need(x.shape == (len(p['query_ids']), len(p['cell_ids']), 61), 'all query trials/cells/times')
        result[key] = x
    return result


def grade(doc, public, private_loader, np):
    answer = validate(doc, public, np)
    # The operator's private target reader is called only after every output passes.
    payload = private_loader()
    need(type(payload) is dict and set(payload) == {'pairs', 'identity'}, 'bound target and identity payload')
    support = support_report(payload['identity'], public)
    target = payload['pairs']
    need(type(target) is list and len(target) == len(public['pairs']), 'complete private inventory')
    rows = []
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        for p, t in zip(public['pairs'], target, strict=True):
            need(set(t) == {'pair_id', 'mouse_id', 'target', 'baseline', 'fixed_warp_baseline', 'training_scale_squared'}
                 and t['pair_id'] == p['pair_id'] and type(t['mouse_id']) is str and t['mouse_id'],
                 'bound complete private pair')
            identity = support['pairs'][len(rows)]
            need(identity['pair_id'] == t['pair_id'] and identity['mouse_id'] == t['mouse_id'],
                 'target mouse and pair agree with bound source identity')
            y, baseline = t['target'], t['baseline']
            fixed_warp = t['fixed_warp_baseline']
            x = answer[p['pair_id']]
            scale = t['training_scale_squared']
            need(y.shape == x.shape and baseline.shape == x.shape[1:] and
                 fixed_warp.shape == baseline.shape and np.isfinite(fixed_warp).all() and
                 np.isfinite(y).all() and np.isfinite(baseline).all() and
                 type(scale) in (int, float) and math.isfinite(scale) and scale >= 0,
                 'finite exact private target/baseline geometry')
            mse = float(np.mean((x - y) ** 2))
            base_mse = float(np.mean((baseline[None] - y) ** 2))
            fixed_warp_mse = float(np.mean((fixed_warp[None] - y) ** 2))
            variance = float(np.mean((y - np.mean(y, axis=(0, 2), keepdims=True)) ** 2))
            need(all(math.isfinite(z) for z in (mse, base_mse, fixed_warp_mse, variance)), 'representable arithmetic')
            normalized = math.sqrt(mse / scale) if scale else None
            base_normalized = math.sqrt(base_mse / scale) if scale else None
            fixed_warp_normalized = math.sqrt(fixed_warp_mse / scale) if scale else None
            r2 = 1 - mse / variance if variance else None
            need(all(v is None or math.isfinite(v) for v in (normalized, base_normalized, fixed_warp_normalized, r2)),
                 'representable normalized metrics')
            rows.append({'pair_id': p['pair_id'], 'mouse_id': t['mouse_id'],
                'query_trials': len(p['query_ids']), 'registered_cells': len(p['cell_ids']),
                'time_bins': 61, 'rmse': math.sqrt(mse), 'nrmse': normalized,
                'baseline_nrmse': base_normalized, 'baseline_rmse': math.sqrt(base_mse),
                'fixed_warp_nrmse': fixed_warp_normalized, 'fixed_warp_rmse': math.sqrt(fixed_warp_mse),
                'r_squared': r2,
                'candidate_minus_baseline': None if normalized is None else normalized - base_normalized,
                'candidate_minus_fixed_warp': None if normalized is None else normalized - fixed_warp_normalized,
                'fixed_warp_minus_baseline': None if normalized is None else fixed_warp_normalized - base_normalized,
                'undefined_normalization': scale == 0, 'undefined_target_variance': variance == 0})
    def mean(values):
        return None if any(x is None for x in values) else math.fsum(values) / len(values)
    mice = []
    for m in sorted({r['mouse_id'] for r in rows}):
        subset = [r for r in rows if r['mouse_id'] == m]
        mice.append({'mouse_id': m, 'pairs': len(subset), 'nrmse': mean([r['nrmse'] for r in subset]),
                     'baseline_nrmse': mean([r['baseline_nrmse'] for r in subset]),
                     'fixed_warp_nrmse': mean([r['fixed_warp_nrmse'] for r in subset]),
                     'candidate_minus_baseline': mean([r['candidate_minus_baseline'] for r in subset]),
                     'candidate_minus_fixed_warp': mean([r['candidate_minus_fixed_warp'] for r in subset]),
                     'fixed_warp_minus_baseline': mean([r['fixed_warp_minus_baseline'] for r in subset])})
    leave_one_mouse = []
    for held in mice:
        kept = [m for m in mice if m['mouse_id'] != held['mouse_id']]
        leave_one_mouse.append({'omitted_mouse_id': held['mouse_id'], 'retained_mice': len(kept),
            **{key: mean([m[key] for m in kept]) if kept else None for key in
               ('nrmse', 'baseline_nrmse', 'fixed_warp_nrmse', 'candidate_minus_baseline',
                'candidate_minus_fixed_warp', 'fixed_warp_minus_baseline')}})
    return {'schema': 'neural029-grade-v2', 'primary_nrmse': mean([m['nrmse'] for m in mice]),
            'baseline_nrmse': mean([m['baseline_nrmse'] for m in mice]), 'pairs': rows, 'mice': mice,
            'fixed_warp_nrmse': mean([m['fixed_warp_nrmse'] for m in mice]),
            'candidate_minus_baseline': mean([m['candidate_minus_baseline'] for m in mice]),
            'candidate_minus_fixed_warp': mean([m['candidate_minus_fixed_warp'] for m in mice]),
            'fixed_warp_minus_baseline': mean([m['fixed_warp_minus_baseline'] for m in mice]),
            'leave_one_mouse': leave_one_mouse, 'support': support,
            'primary_weighting': 'pair sqrt(pooled MSE / pooled training variance); equal pairs within mouse; equal mice',
            'estimand': 'all-trial expected trajectory; target outcomes hidden',
            'fixed_warp': 'g(t)=t/2 for0<=t<2; g(t)=t-1 for2<=t<=3; source-only linear interpolation',
            'scientific_execution_qualified': False, 'submission_ready': False,
            'all_pairs_retained': True, 'condition_transfer': '1s_to_2s_GrC',
            'causal_or_new_animal_claim': False}
