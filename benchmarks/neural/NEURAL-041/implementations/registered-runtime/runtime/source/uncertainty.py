"""Protected paired-patient uncertainty, conditional on captured predictions.

The only source RNG site is default_rng(seed), then integer patient resampling.
The seed is an independently precommitted signed-profile field; no RNG was run
during construction. This is not variation over refitted training datasets.
"""
from core import need,integer

def paired(scores,seed,replicates=10000):
    import numpy as np
    integer(seed,0,2**64-1);need(replicates==10000,'preselected diagnostic resampling extent')
    baseline='reference/combined';base={r['patient']:r for r in scores[baseline]['patients']};people=sorted(base)
    need(len(people)>=3,'patient-level uncertainty requires replication')
    g=np.random.default_rng(seed)
    # One shared draw bank preserves pairing across all metrics and families.
    draw=g.integers(0,len(people),size=(replicates,len(people)))
    out={}
    for family,score in scores.items():
        current={r['patient']:r for r in score['patients']};need(set(current)==set(base),'identical complete patient population')
        metrics={}
        for metric in('balanced_accuracy','log_loss'):
            delta=np.asarray([current[p][metric]-base[p][metric] for p in people])
            sampled=delta[draw].mean(axis=1)
            metrics[metric]={'patient_differences':[{'patient':p,'difference':float(v)} for p,v in zip(people,delta)],
                'mean_difference':float(delta.mean()),'conditional_patient_bootstrap_interval':np.quantile(sampled,[.025,.975]).tolist(),
                'orientation':'higher better' if metric=='balanced_accuracy' else 'lower better'}
        out[family]=metrics
    return {'baseline':baseline,'replicates':replicates,'patient_pairing':True,'conditional_on_frozen_predictions':True,
        'training_resampling_variation_included':False,'outer_training_overlap_caveat':True,'comparisons':out}
