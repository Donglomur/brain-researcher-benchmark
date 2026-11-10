"""Fixed fitting, DEV selection, passive freeze, and read-only query inference."""
import copy,random,hashlib
import numpy as np
import torch
from .catalog import need,identity
from .models import build,neural_forward


def seed_all(seed):random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);torch.use_deterministic_algorithms(True)
def state_copy(m):return {k:v.detach().cpu().clone() for k,v in m.state_dict().items()}
def state_digest(state):
    h=hashlib.sha256()
    for k,v in sorted(state.items()):h.update(k.encode());h.update(str((v.dtype,tuple(v.shape))).encode());h.update(v.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
    return h.hexdigest()
def balanced(y,logits,k):
    y=np.asarray(y).reshape(-1);p=np.asarray(logits).reshape(-1,k).argmax(-1)
    need(set(y)==set(range(k)),'DEV balanced accuracy requires every class');return float(np.mean([np.mean(p[y==c]==c) for c in range(k)]))
def fit_normalization(x):
    a=np.abs(x);axes=tuple(i for i in range(x.ndim) if i!=x.ndim-2);q=np.quantile(a,.95,axis=axes);return np.where(q>1e-8,q,1.)
def project(x,pos,canonical):
    """Prospective fixed geometry interpolation; no labels, fit, or query batch state."""
    if pos.shape==canonical.shape and np.array_equal(pos,canonical):return x
    dist=np.linalg.norm(canonical[:,None,:]-pos[None,:,:],axis=-1);out=[]
    for row in dist:
        order=np.argsort(row,kind='stable')[:min(3,len(row))]
        if row[order[0]]==0:w=np.zeros(len(order));w[0]=1.
        else:w=1/np.maximum(row[order],1e-12)**2;w/=w.sum()
        out.append(np.sum(x[...,order,:]*w.reshape((1,)*(x.ndim-2)+(len(w),1)),axis=-2))
    return np.stack(out,axis=-2)
def prepare(x,pos,normalizer,canonical):
    z=project(x,pos,canonical);shape=(1,)*(z.ndim-2)+(len(normalizer),1);return (z/normalizer.reshape(shape)).astype('float32')
def head_parameter(name):return (name.startswith('classifier.') and not (name=='classifier.encoder' or name.startswith('classifier.encoder.'))) or any(s in name for s in ('head','cls_query_token','sequence_encoder','final_layer'))
def construct(c,geometry,initial=None):
    r=c['recipe'];m=build(r['base'],len(geometry),r['samples'],r['classes'],r['sequence_length']==20,c['ablation'],c['purpose'])
    if hasattr(m,'bind_geometry'):
        table=geometry;table_samples=r['samples']
        if c['ablation'].get('component')=='learnable_PE' and initial:
            candidates=[v for k,v in initial.items() if k.endswith('fourier4d.positions')]
            need(len(candidates)<=1,'one qualified learned-position table')
            if candidates:
                table=candidates[0].cpu().numpy()/m.position_scale;times=[v for k,v in initial.items() if k.endswith('fourier4d.temporal.weight')];need(len(times)==1,'complete learned position/time table');table_samples=(len(times[0])-1)*180+200;need(r['samples']<=table_samples,'learned table cannot extrapolate to unseen temporal support')
        m.bind_geometry(torch.as_tensor(table,dtype=torch.float32),table_samples)
    return m.to(c['device'])
def forward(m,c,x,pos,channel_ids):
    r=c['recipe'];p=torch.as_tensor(pos,dtype=torch.float32,device=c['device']).unsqueeze(0).expand(len(x),-1,-1)
    return neural_forward(m,r['base'],torch.as_tensor(x,device=c['device']),p,channel_ids,r['sequence_length']==20)
def freeze_encoder(m,lp):
    for n,p in m.named_parameters():p.requires_grad_(not lp or head_parameter(n))
    need(any(p.requires_grad for p in m.parameters()),'nonempty trained mask')
    m.eval() if lp else m.train()
    if lp:
        for name,child in m.named_modules():
            if name and head_parameter(name):child.train()

def fit(c,train,dev,initial=None,trace_limit=100000):
    r=c['recipe'];tm,x,pos,y=train;dm,v,vpos,dy=dev
    need(not set(tm['events'])&set(dm['events']),'TRAIN and DEV events disjoint')
    if c['condition']!='source':need(not set(tm['people'])&set(dm['people']),'protected TRAIN/DEV people disjoint')
    need(set(y.reshape(-1))==set(range(r['classes'])),'all training classes')
    norm=fit_normalization(x);x=prepare(x,pos,norm,pos);v=prepare(v,vpos,norm,pos)
    seed_all(c['seed']);m=construct(c,pos,initial)
    if initial is not None:
        if any(k.startswith('asset.') for k in initial):
            from .assets import adapt_asset
            initial=adapt_asset(initial,r['base'],m)
        shape=m.state_dict();initial={k:v for k,v in initial.items() if k not in shape or v.shape==shape[k].shape or not head_parameter(k)}
        missing,unexpected=m.load_state_dict(initial,strict=False)
        need(not unexpected and all(head_parameter(n) for n in missing),'pretrained parent covers every encoder tensor exactly')
    else:need(c['initialization']=='scratch','qualified initial state required')
    planned=sum(s['epochs']*len(s['learning_rates'])*((len(x)+r['batch_size']-1)//r['batch_size']) for s in r['stages'])
    planned+=sum(len(s['learning_rates']) for s in r['stages'])-1+len(r['stages']) # actual trial resets and selected-state transitions
    need(planned<=trace_limit,'complete fitting trace capacity before first step')
    from .step_trace import step_row
    stage_start=state_copy(m);history=[];update=0;all_steps=[]
    patch_count=x.shape[-2]*((x.shape[-1]-200)//180+1)*r['sequence_length'];sample_count=x.shape[-2]*x.shape[-1]*r['sequence_length']
    for stage in r['stages']:
        best=None;best_score=None;best_trial=None
        for trial,lr in enumerate(stage['learning_rates']):
            seed_all(c['seed']+trial);before=state_digest(m.state_dict());m.load_state_dict(stage_start,strict=True);freeze_encoder(m,stage['name']=='LP')
            if all_steps:all_steps.append(step_row(before,m,len(all_steps),update,update,lr,[],tm,0,0))
            optimizer=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=lr,weight_decay=stage['weight_decay'])
            rng=np.random.default_rng(c['seed']+trial)
            for epoch in range(stage['epochs']):
                freeze_encoder(m,stage['name']=='LP');order=rng.permutation(len(x))
                for start in range(0,len(order),r['batch_size']):
                    ids=order[start:start+r['batch_size']];before=state_digest(m.state_dict());optimizer.zero_grad(set_to_none=True)
                    logits=forward(m,c,x[ids],pos,tm['channel_ids']);target=torch.as_tensor(y[ids].reshape(-1),dtype=torch.long,device=c['device'])
                    loss=torch.nn.functional.cross_entropy(logits.reshape(-1,r['classes']),target);need(torch.isfinite(loss).item(),'finite training loss');loss.backward();optimizer.step()
                    if hasattr(m,'project'):m.project()
                    all_steps.append(step_row(before,m,len(all_steps),update,update+1,lr,ids.tolist(),tm,patch_count,sample_count));update+=1
                m.eval();parts=[]
                with torch.no_grad():
                    for start in range(0,len(v),r['batch_size']):parts.append(forward(m,c,v[start:start+r['batch_size']],pos,tm['channel_ids']).cpu().numpy())
                score=balanced(dy,np.concatenate(parts),r['classes']);history.append({'phase':stage['name'],'trial':trial,'epoch':epoch,'DEV_balanced_accuracy':score,'update':update})
                if best_score is None or score>best_score:best_score=score;best=state_copy(m);best_trial=history[-1].copy()
        need(best is not None,'selected DEV state required');stage_start=best;before=state_digest(m.state_dict());m.load_state_dict(best,strict=True);all_steps.append(step_row(before,m,len(all_steps),update,update,lr,[],tm,0,0))
    m.eval();return {'weights':state_copy(m),'normalizer':torch.tensor(norm),'geometry':torch.tensor(pos),'history':history,'steps':all_steps,'selected':best_trial,'trained_mask':[n for n,p in m.named_parameters() if p.requires_grad],'fitted_dependencies':[tm['support'],dm['support']],'channel_ids':tm['channel_ids']}

def predict(c,state,view):
    manifest,x,pos,y=view;need(y is None,'no query labels');r=c['recipe'];need(len(x)==1,'fresh process handles one epoch or one20epoch sequence')
    tensors=state['tensors'];geometry=tensors['adapter.geometry'].cpu().numpy();norm=tensors['adapter.normalizer'].cpu().numpy()
    weights={k[len('model.'):]:v for k,v in tensors.items() if k.startswith('model.')};m=construct(c,geometry,weights);m.load_state_dict(weights,strict=True);m.eval();before=state_digest(m.state_dict())
    with torch.no_grad():logits=forward(m,c,prepare(x,pos,norm,geometry),geometry,state['channel_ids']);flat=logits.reshape(-1,r['classes']);prob=(flat if c['purpose']=='R-native' else flat.softmax(-1)).cpu().numpy()
    need(state_digest(m.state_dict())==before,'prediction cannot change frozen buffers or weights');return prob

def soup(states):
    need(len(states) in (5,10),'full5or10 soup');keys=set(states[0]);need(all(set(s)==keys for s in states),'same tensor schema');out={}
    for k in sorted(keys):
        first=states[0][k];need(all(s[k].shape==first.shape and s[k].dtype==first.dtype for s in states),'same exact tensor shape/dtype')
        if k.startswith('model.') and first.is_floating_point():out[k]=torch.stack([s[k].to(torch.float64) for s in states]).mean(0).to(first.dtype)
        else:need(all(torch.equal(s[k],first) for s in states),'nonfloating buffers and fitted adapters must be identical');out[k]=first.clone()
    return out
