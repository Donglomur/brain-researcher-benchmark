"""Independent co-smoothing metric core. No candidate code or file deserialization.

Inputs are trusted, operator-validated in-memory arrays. This is NOT a hostile
submission archive parser or an input-isolation implementation.
"""
import math
import numpy as np


def require(ok, message):
    if not ok:
        raise ValueError(message)


def real_array(value, name):
    array = np.asarray(value)
    require(array.dtype.kind in 'fiu', name+' must be real numeric, not bool/complex/object')
    return array.astype(np.float64, copy=False)


def poisson_bits_per_spike(target_counts, expected_counts, valid_mask=None):
    """Official co-bps equation, with strict declared submission-domain checks.

Rates mean expected spikes per bin, not Hz. The official null is the per-neuron
EVALUATION mean over valid trial/time bins; it is a scorer normalization, not a
trainable baseline. Exactly-zero null means are replaced by1e-9 as in nlb_tools.
Unlike upstream, zero/nonfinite predictions are rejected, never silently clipped.
All-zero observed target totals return a documented undefined score, not NaN/0.
"""
    y = real_array(target_counts, 'targets')
    lam = real_array(expected_counts, 'expected counts')
    require(y.ndim == 3 and all(n > 0 for n in y.shape) and y.shape == lam.shape,
            'Expected matching nonempty trial x bin x heldout-unit arrays')
    require(np.isfinite(lam).all() and (lam > 0).all(), 'Predictions must be finite and strictly positive')
    mask = np.ones(y.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    require(mask.dtype == np.bool_ and mask.shape == y.shape, 'Mask must be fixed boolean target shape')
    require(np.any(mask) and np.all(mask.sum(axis=(0,1)) > 0), 'No valid targets for at least one unit')
    observed = y[mask]
    require(np.isfinite(observed).all() and (observed >= 0).all() and
            (observed == np.floor(observed)).all() and (observed <= 2**53).all(),
            'Observed targets must be finite nonnegative integer spike counts')
    safe = np.where(mask, y, 0.0)
    totals = safe.sum(axis=(0,1),dtype=np.float64)
    means = totals / mask.sum(axis=(0,1))
    means[means == 0] = 1e-9
    nspikes = float(totals.sum())
    require(math.isfinite(nspikes), 'Target sum overflow')
    if nspikes == 0:
        return {'status':'undefined_zero_target_spikes','co_bps':None,'target_spikes':0.0,
                'valid_cells':int(mask.sum()),'null_policy':'evaluation_per_neuron_mean'}
    # Factorial terms cancel in log-likelihood ratio. Avoid lambda/mu overflow.
    mu = np.broadcast_to(means,y.shape)
    with np.errstate(over='ignore',invalid='ignore'):
        terms = observed * (np.log(lam[mask]) - np.log(mu[mask])) + mu[mask] - lam[mask]
        improvement_nats = float(np.sum(terms,dtype=np.float64))
    require(math.isfinite(improvement_nats), 'Likelihood ratio overflow/nonfinite')
    value = improvement_nats / (nspikes * math.log(2.0))
    require(math.isfinite(value), 'Nonfinite bits per spike')
    return {'status':'scored','co_bps':value,'target_spikes':nspikes,
            'valid_cells':int(mask.sum()),'null_policy':'evaluation_per_neuron_mean',
            'log_likelihood_improvement_nats':improvement_nats}


def axis_ids(value, name):
    arr = np.asarray(value)
    require(arr.ndim == 1 and len(arr) > 0 and arr.dtype.kind == 'U', name+' must be nonempty Unicode string IDs')
    ids = [str(x) for x in arr]
    require(all(ids) and len(ids) == len(set(ids)), name+' must be unique')
    return ids


def score_submission(submission, gold):
    """Align explicit trial/unit IDs; never infer a target mask from predictions."""
    require(set(submission) == {'trial_ids','heldout_unit_ids','bin_left_edges_ms',
                               'prediction_units','expected_counts','panel_fingerprint'},
            'Unexpected/missing submission fields')
    require(submission['prediction_units'] == 'expected_spikes_per_bin', 'Prediction units must be expected_spikes_per_bin')
    require(submission['panel_fingerprint'] == gold['panel_fingerprint'], 'Panel alignment fingerprint mismatch')
    gi = axis_ids(gold['trial_ids'],'gold trial IDs'); si = axis_ids(submission['trial_ids'],'submission trial IDs')
    gu = axis_ids(gold['heldout_unit_ids'],'gold unit IDs'); su = axis_ids(submission['heldout_unit_ids'],'submission unit IDs')
    require(set(gi) == set(si) and set(gu) == set(su), 'Trial/unit ID set mismatch')
    gtime = real_array(gold['bin_left_edges_ms'],'gold bin coordinates')
    stime = real_array(submission['bin_left_edges_ms'],'submitted bin coordinates')
    require(gtime.ndim == 1 and np.isfinite(gtime).all() and np.all(np.diff(gtime)>0)
            and np.array_equal(gtime,stime), 'Time-bin alignment mismatch')
    expected = real_array(submission['expected_counts'],'expected counts')
    require(expected.shape == (len(si),len(gtime),len(su)), 'Submission shape differs from axes')
    ordered = expected[np.ix_([si.index(x) for x in gi],np.arange(len(gtime)),[su.index(x) for x in gu])]
    return poisson_bits_per_spike(gold['target_counts'],ordered,gold['valid_mask'])
