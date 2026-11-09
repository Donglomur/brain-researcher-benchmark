"""Candidate-visible standalone fitted-transform inference. No private imports.

Inputs are the owner-validated, externally pinned public parameter DTO. This
module owns inference only. Its source/runtime and DTO are mounted read-only.
Candidate modifications or malformed inputs may fail, never access private data.
"""
import math
import numpy as np

def apply_transform(dto,neural,context):
    if set(dto)!={'schema','algorithm','parameters'} or dto['schema']!='n073_public_transform_v1':
        raise ValueError('public transform schema')
    a=dto['algorithm'];p={k:np.asarray(v['data'],dtype=np.float64).reshape(v['shape']) for k,v in dto['parameters'].items()}
    view=a['view'];blocks=[]
    if view=='C' and neural is not None:raise ValueError('C-only neural operand forbidden')
    if view=='N' and context is not None:raise ValueError('N-only C operand forbidden')
    if view in ('N','NC'):
        x=np.asarray(neural,dtype=np.float64)
        if x.ndim!=2 or x.shape[1]!=len(p['n_mean']) or not np.all(np.isfinite(x)):
            raise ValueError('full neural rows required')
        if a['representation']=='rms':
            # Scaling first prevents square overflow, exactly matching the fitted
            # transform's binary64 RMS path (all-zero maps remain all zero).
            peak=np.max(np.abs(x),axis=1)
            safe=np.where(peak==0,1.0,peak)
            ratio=x/safe[:,None]
            rms=safe*np.sqrt(np.mean(ratio*ratio,axis=1))
            x=x/np.where(rms==0,1.0,rms)[:,None]
        elif a['representation']!='raw':raise ValueError('representation')
        z=(x-p['n_mean'])/p['n_scale']
        if a['neural_projection']=='full':block=z/math.sqrt(x.shape[1])
        elif a['neural_projection']=='PCA':
            rank=a['pca_rank']
            block=(((z-p['pca_mean'])@p['pca_components']-p['score_mean'])/p['score_scale'])/math.sqrt(rank)
        else:raise ValueError('projection')
        blocks.append(block)
    if view in ('C','NC'):
        c=np.asarray(context,dtype=np.float64)
        if c.ndim!=2 or c.shape[1]!=105 or not np.all(np.isfinite(c)):
            raise ValueError('original C rows required')
        blocks.append(((c-p['c_mean'])/p['c_scale'])/math.sqrt(105))
    if not blocks:raise ValueError('view')
    result=blocks[0] if len(blocks)==1 else np.concatenate(blocks,axis=1)
    if not np.all(np.isfinite(result)):raise ValueError('nonfinite transformed features')
    return result
