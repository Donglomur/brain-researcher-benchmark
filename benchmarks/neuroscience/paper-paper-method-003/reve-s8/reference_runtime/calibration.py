"""Calibration-only centroids; frozen representation, no query normalization fit."""
import numpy as np
import torch
from .catalog import need
from .engine import construct,prepare,state_digest,state_copy,head_parameter,seed_all
from .reference_ncm import centroids

def embedding(c,tensors,view,channel_ids):
    manifest,x,pos,_=view;r=c['recipe']
    if r['base']=='fixed_spectral_ridge':
        from .reference_spectral import pooled_features
        return pooled_features(x.reshape(-1,x.shape[-2],x.shape[-1]),input_unit='mV')
    need(r['base'].startswith('REVE-'),'fixed few-shot primary representation is REVE')
    geometry=tensors['adapter.geometry'].numpy();norm=tensors['adapter.normalizer'].numpy();m=construct(c,geometry,tensors);m.load_state_dict({k[6:]:v for k,v in tensors.items() if k.startswith('model.')},strict=True);m.eval();before=state_digest(m.state_dict())
    z=torch.as_tensor(prepare(x,pos,norm,geometry),device=c['device']);positions=torch.as_tensor(geometry*m.position_scale,dtype=torch.float32,device=c['device'])[None].expand(len(z),-1,-1)
    with torch.no_grad():features=m.features(z,positions).cpu().numpy()
    need(state_digest(m.state_dict())==before,'frozen representation changed');return features

def calibrate(c,tensors,view,channel_ids):
    manifest,x,pos,y=view;need(y is not None and len(set(manifest['people']))==1,'one own-person calibration')
    n=c['ablation'].get('shots_per_class');need(n in (1,2,5,10,20) and c['recipe']['classes']==2,'full preregistered fewshot support')
    need(len(y)==2*n and all(int((y==k).sum())==n for k in range(2)),'exact N examples per class')
    features=embedding(c,tensors,view,channel_ids);result=dict(tensors);result['ncm.centers']=torch.as_tensor(centroids(features,y,2));return result


def prepare_parent(c,details,tensors,view,lineage=None):
    """PT creates no supervised state: only exact pretrained features + constants.

    Geometry is the disclosed calibration sensor geometry; the normalizer is the
    predeclared 100uV physical scale, with no fitted target-person statistic.
    """
    method=c['recipe']['method']
    if method=='REVE-Base-XFT':
        need(type(lineage)is dict and lineage.get('schema')=='reve-XFT-controller-lineage-v1' and lineage.get('current_stage')=='S10' and lineage.get('fit_product')==lineage.get('current_product') and lineage.get('training')==details['schedule'].get('xft'),'XFT requires validated actual S10 parent lineage')
        need(details['configuration']['recipe']['method']=='REVE-Base-XFT' and 'adapter.normalizer' in tensors and any(k.startswith('model.') for k in tensors),'XFT uses its distinct fitted five-source state')
        return tensors
    if method!='REVE-Base-PT':return tensors
    need(not any(k.startswith('model.') for k in tensors),'PT cannot substitute a supervised adapted state')
    initial={'classifier.encoder.'+k[len('pretrain.encoder.'):]:v for k,v in tensors.items() if k.startswith('pretrain.encoder.')}
    if 'pretrain.cls_query_token' in tensors:initial['classifier.cls_query_token']=tensors['pretrain.cls_query_token']
    if not initial:initial={k:v for k,v in tensors.items() if k.startswith('asset.')}
    need(initial and details['configuration']['recipe']['base']=='REVE-Base','actual pretrained Base representation required')
    geometry=view[2];seed_all(c['seed']);model=construct(c,geometry,initial)
    if any(k.startswith('asset.') for k in initial):
        from .assets import adapt_asset
        initial=adapt_asset(initial,'REVE-Base',model)
    need('classifier.cls_query_token' in initial,'PT attention-pooling query must be pretrained, never a new random feature selector')
    missing,unexpected=model.load_state_dict(initial,strict=False)
    need(not unexpected and all(head_parameter(n) for n in missing),'every actual pretrained encoder tensor must be covered')
    return {**{'model.'+k:v for k,v in state_copy(model).items()},'adapter.geometry':torch.tensor(geometry),'adapter.normalizer':torch.full((len(geometry),),.1,dtype=torch.float64)}
