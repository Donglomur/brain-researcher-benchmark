"""Explicit native-readout convention diagnostic, never canonical animal R².

No partial intersection/deduplication is allowed to hide missing original
support. GT serialization/aggregate helper parity is separately qualified.
"""
from core import need


def session(target,prediction,offsets,joins):
    import numpy as np
    if len(joins)+1!=len(offsets):return {'status':'not_comparable','reason':'original trial membership mismatch'}
    trial=np.array([r['source_trial'] for r in joins],dtype=np.int64)
    sizes=np.diff(offsets)
    if len(np.unique(trial))!=len(trial):
        return {'status':'not_comparable','reason':'native intersection would collapse original duplicate occurrences'}
    if not len(sizes) or not np.all(sizes==sizes[0]):
        return {'status':'not_comparable','reason':'native rectangular N,T,D readout does not represent full ragged support'}
    if len(target)<2:return {'status':'not_comparable','reason':'native R2 requires two observations'}
    # Emulate the original full unique trial alignment, retaining every trial.
    _,i,j=np.intersect1d(trial,trial,return_indices=True)
    need(len(i)==len(trial)==len(j),'no native diagnostic coverage loss')
    truth=np.stack([target[a:b,1] for a,b in zip(offsets[:-1],offsets[1:])]).astype(np.float32)
    pred=np.stack([prediction[a:b,1] for a,b in zip(offsets[:-1],offsets[1:])]).astype(np.float32)
    if not np.isfinite(pred).all():return {'status':'not_comparable','reason':'native float32 prediction conversion overflow'}
    import importlib.metadata
    need(importlib.metadata.version('torchmetrics')=='1.9.0','exact native diagnostic metric version')
    import torch
    from torchmetrics import R2Score
    metric=R2Score()
    metric.update(torch.from_numpy(pred[i].reshape(-1,1)),torch.from_numpy(truth[j].reshape(-1,1)))
    value=metric.compute()
    if not bool(torch.isfinite(value).item()):
        return {'status':'not_comparable','reason':'native float32 metric reduction is nonfinite',
                'trial_count':len(trial),'timestamp_count':len(target),
                'dependency_or_physical_exception_suppressed':False}
    return {'status':'computed_convention_diagnostic','r2':float(value.item()),
            'trial_count':len(trial),'timestamp_count':len(target),'dtype':'float32',
            'negative_r2_clipped':False,'source_GT_serialization_and_aggregation_parity_not_established':True,
            'not_original_TS1_calibrated_protocol_or_SOTA_comparison':True}


def seed_aggregate(replicates,expected_sessions):
    """Known clipping/averaging convention; no missing-session or seed dropping."""
    need(len(replicates)==3,'all three actual candidate realizations')
    seed_means=[]
    for rows in replicates:
        need(set(rows)==set(expected_sessions),'complete native-diagnostic session roster')
        if any(r['status']!='computed_convention_diagnostic' for r in rows.values()):
            return {'status':'not_comparable','value':None,'reason':'at least one required session lacks full native rectangular support'}
        seed_means.append(sum(max(0.,rows[s]['r2']) for s in expected_sessions)/len(expected_sessions))
    return {'status':'computed_convention_diagnostic','value':sum(seed_means)/3,
            'seed_session_means':seed_means,'clips_negative_session_r2_before_means':True,
            'animal_grouping':False,'canonical_metric_unchanged':True,
            'source_GT_serialization_and_aggregation_parity_not_established':True}
