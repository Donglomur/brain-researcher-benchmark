"""Complete-context mean-response error. No file reads or fitting."""
import hashlib
import math
import re
from delivery_io import canonical, exact, need

SHAPES = ((251, 240), (203, 240), (139, 240), (114, 240), (257, 200), (168, 200))


def stable_rms(values):
    """RMS without forming unscaled squares or dividing tiny squared terms."""
    values = tuple(float(value) for value in values)
    need(values and all(math.isfinite(value) for value in values),
         'Finite nonempty residual support required')
    largest = max(abs(value) for value in values)
    if largest == 0:
        return 0.0
    # The norm of ratios is at most sqrt(n), so both intermediates stay
    # representable even when the norm of the original vector would overflow.
    factor = math.hypot(*(value / largest for value in values)) / math.sqrt(len(values))
    result = largest * min(factor, 1.0)
    need(math.isfinite(result) and result > 0,
         'Nonzero RMS is outside representable floating-point range')
    return result


def stable_mean_nonnegative(values):
    """Equal mean preserving tiny uniform errors and avoiding sum overflow."""
    values = tuple(float(value) for value in values)
    need(values and all(math.isfinite(value) and value >= 0 for value in values),
         'Finite nonnegative complete mean support required')
    largest = max(values)
    if largest == 0:
        return 0.0
    factor = math.fsum(value / largest for value in values) / len(values)
    result = largest * min(factor, 1.0)
    need(math.isfinite(result) and result > 0,
         'Nonzero mean is outside representable floating-point range')
    return result


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def public_contract(public):
    exact(public, ['schema', 'packet_id', 'generation', 'contexts'])
    need(public['schema'] == 'neural037-panel-v1' and type(public['generation']) is str and
         re.fullmatch('[a-f0-9]{64}', public['generation']), 'Exact source/protocol generation')
    need(public['packet_id'] == fingerprint({k: v for k, v in public.items() if k != 'packet_id'}),
         'Panel fingerprint')
    need(type(public['contexts']) is list and len(public['contexts']) == 12, 'All six acquisitions xboth complete orders')
    seen = set(); acquisitions = {}
    for context in public['contexts']:
        exact(context, ['context_id', 'acquisition', 'query_order', 'cell_keys', 'frames'])
        acq = context['acquisition']; order = context['query_order']
        need(type(acq) is str and re.fullmatch('acquisition_[1-6]', acq) and order in ('ABC','CBA'), 'Fixed six/order identities')
        need(context['context_id'] == acq + '_' + order and context['context_id'] not in seen, 'Exact unique context ID')
        seen.add(context['context_id'])
        need(type(context['cell_keys']) is list and 1 <= len(context['cell_keys']) <= 10000 and
             context['cell_keys'] == ['cell_%04d' % i for i in range(len(context['cell_keys']))], 'All ordered original ROI rows')
        need(type(context['frames']) is int and 2 <= context['frames'] <= 1000, 'Native source-frame grid')
        shape = (len(context['cell_keys']), context['frames'])
        need(shape == SHAPES[int(acq[-1]) - 1], 'Complete original acquisition ROI/frame geometry')
        if acq in acquisitions: need(acquisitions[acq] == shape, 'Same source cell/grid support across orders')
        acquisitions[acq] = shape
    need(len(acquisitions) == 6 and len(seen) == 12, 'Complete declared panel')
    return {r['context_id']: r for r in public['contexts']}


def admit(public, submission, np):
    wanted = public_contract(public)
    exact(submission, ['schema', 'packet_id', 'outcomes'])
    need(submission['schema'] == 'neural037-predictions-v1' and submission['packet_id'] == public['packet_id'] and
         type(submission['outcomes']) is list and len(submission['outcomes']) == 12, 'Every context required')
    predictions = {}; abstained = []
    for outcome in submission['outcomes']:
        need(type(outcome) is dict and outcome.get('status') in ('complete','abstain'), 'Explicit completion or abstention')
        tail = 'responses' if outcome['status'] == 'complete' else 'reason'
        exact(outcome, ['context_id','status',tail])
        name = outcome['context_id']
        need(type(name) is str and name in wanted and name not in predictions, 'Exact unique context join')
        if outcome['status'] == 'abstain':
            need(type(outcome['reason']) is str and 0 < len(outcome['reason']) <= 256, 'Bounded abstention')
            predictions[name] = None; abstained.append(name); continue
        context = wanted[name]; rows = outcome['responses']; keys = context['cell_keys']; frames = context['frames']
        need(type(rows) is list and len(rows) == len(keys), 'Every original cell required')
        parsed = {}
        for row in rows:
            exact(row,['cell_key','values'])
            key = row['cell_key']; values = row['values']
            need(type(key) is str and key in keys and key not in parsed, 'Exact unique cell join')
            need(type(values) is list and len(values) == frames and all(type(v) in (int,float) and
                 math.isfinite(v) for v in values), 'Finite complete native-frame prediction; no booleans')
            parsed[key] = values
        predictions[name] = np.asarray([parsed[key] for key in keys], dtype=np.float64)
    need(set(predictions) == set(wanted), 'No omitted context')
    return predictions, abstained


def score(public, submission, load_targets, np):
    predictions, abstained = admit(public, submission, np)
    if abstained:
        return {'status':'abstained','metric':None,'private_target_callbacks':0,'failed_contexts':abstained}
    targets = load_targets()
    exact(targets, ['packet_id','contexts'])
    need(targets['packet_id'] == public['packet_id'] and type(targets['contexts']) is dict and
         set(targets['contexts']) == set(predictions), 'Complete pinned private generation')
    rows = []
    for context in public['contexts']:
        name = context['context_id']; target = targets['contexts'][name]
        exact(target,['means','counts','training_scale'])
        means = target['means']; counts = target['counts']; scale = target['training_scale']
        need(isinstance(means,np.ndarray) and isinstance(counts,np.ndarray) and
             means.shape == counts.shape == predictions[name].shape and means.dtype == np.float64 and
             counts.dtype == np.uint16 and np.isfinite(means).all() and np.all(counts <= 50), 'Exact finite private shape/types')
        need(type(scale) in (int,float) and math.isfinite(scale) and scale > 0, 'Training-only positive normalizer')
        mask = counts > 0; support = mask.sum(axis=1)
        observed_cells = support > 0
        need(np.any(observed_cells), 'Entire source condition unobserved; no subset-context score')
        per_cell = [None] * len(support)
        try:
            raw_cell_rms = []
            for index in np.flatnonzero(observed_cells):
                with np.errstate(over='ignore',invalid='ignore'):
                    residual = predictions[name][index,mask[index]] - means[index,mask[index]]
                cell_rms = stable_rms(residual)
                normalized = cell_rms / scale
                cell_mse = normalized * normalized
                # This original diagnostic is required as a finite number. Do
                # not disguise an unrepresentable square as zero, infinity or
                # an unobserved cell, even if the primary RMS would be finite.
                need(math.isfinite(cell_mse) and
                     (cell_rms == 0 or (normalized > 0 and cell_mse > 0)),
                     'Required per-cell normalized MSE is outside representable floating-point range')
                per_cell[index] = cell_mse
                raw_cell_rms.append(cell_rms)
            # RMS of equally weighted cell RMSs is exactly the original root
            # mean of cell MSEs, without premature squaring or tiny-term division.
            raw_rmse = stable_rms(raw_cell_rms)
            nrmse = raw_rmse / scale
            need(math.isfinite(nrmse) and (raw_rmse == 0 or nrmse > 0),
                 'Normalized context RMS is outside representable floating-point range')
        except (OverflowError, ValueError):
            return {'status':'numeric_error','metric':None,'private_target_callbacks':1,
                    'reason':'Complete-panel residual, RMS or required MSE diagnostic is outside representable floating-point range.'}
        rows.append({'context_id':name,'acquisition':context['acquisition'],'query_order':context['query_order'],
                     'cells':len(context['cell_keys']),'observed_cells':int(observed_cells.sum()),
                     'unobserved_cells':int((~observed_cells).sum()),
                     'unobserved_cell_reasons':[{'cell_key':key,'reason':'no_finite_source_trial_at_any_frame'}
                         for key,seen in zip(context['cell_keys'],observed_cells) if not seen],
                     'observed_cell_frames':int(mask.sum()),
                     'unobserved_cell_frames':int((~mask).sum()),'normalized_rmse':nrmse,'raw_rmse':raw_rmse,
                     'per_cell_normalized_mse':per_cell})
    try:
        acquisitions = [{'acquisition': 'acquisition_%d' % i,
                         'normalized_rmse': stable_mean_nonnegative(r['normalized_rmse'] for r in rows
                             if r['acquisition'] == 'acquisition_%d' % i),
                         'raw_rmse': stable_mean_nonnegative(r['raw_rmse'] for r in rows
                             if r['acquisition'] == 'acquisition_%d' % i)} for i in range(1,7)]
        metric = stable_mean_nonnegative(r['normalized_rmse'] for r in rows)
    except (OverflowError, ValueError):
        return {'status':'numeric_error','metric':None,'private_target_callbacks':1,
                'reason':'Complete-panel aggregate mean is outside representable floating-point range.'}
    return {'status':'scored','packet_id':public['packet_id'],'private_target_callbacks':1,
            'primary':'equal_context_mean_normalized_rmse','metric':metric,
            'contexts':rows,'acquisitions':acquisitions,'higher_is_better':False,'scientific_success':None,
            'scope':'Six experiment-local, complete-condition holdouts; no animal-transfer, physical-onset or visual-context claim.',
            'uncertainty':'Descriptive fixed-source panel; no pooled-cell inference or independent-trial assumption.'}
