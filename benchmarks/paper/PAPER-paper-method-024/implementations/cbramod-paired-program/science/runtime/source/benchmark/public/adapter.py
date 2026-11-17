"""Canonical 200Hz/one-second patch adapter, not an official model ABI.

Authentic resampling/filtering/split/source mapping is external and unqualified.
This module never fits normalization, calls a model, or reads source recordings.
"""
import numpy as np


def patches(epoch,dataset,unit='microvolt'):
    x=np.asarray(epoch)
    channels=dataset['channels'];samples=dataset['epoch_seconds']*200
    if x.ndim!=2 or x.shape!=(channels,samples) or x.dtype.kind!='f':
        raise ValueError('exact prequalified channel-by-200Hz epoch rectangle')
    if not np.isfinite(x).all() or np.any(np.abs(x)>1e100):raise ValueError('finite complete epoch')
    if unit not in ('microvolt','volt'):raise ValueError('explicit physical units')
    #100microvolt unit is paper-declared, not a mean fitted on train or test rows.
    scale=100. if unit=='microvolt' else 1e-4
    normalized=x/scale
    if np.any(np.abs(normalized)>np.finfo(np.float32).max):raise ValueError('bounded float32 canonical patches')
    return np.array(normalized,dtype=np.float32,order='C').reshape(channels,dataset['epoch_seconds'],200)


def sleep_sequence(epochs,dataset,unit='microvolt'):
    if dataset['id']!='ISRUC' or type(epochs) is not list or len(epochs)!=20:
        raise ValueError('ISRUC requires20 consecutive prequalified epochs')
    # Consecutive-night identity and sequence boundary are external metadata joins.
    return np.stack([patches(e,dataset,unit) for e in epochs])
