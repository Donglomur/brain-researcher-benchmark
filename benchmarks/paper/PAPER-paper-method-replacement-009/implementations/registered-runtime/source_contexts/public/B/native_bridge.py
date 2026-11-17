"""Prospective source-API bridge, not the published end-to-end training script.

Imports are lazy. No candidate or model is run during construction/tests. The
author constructors/forward methods are bound below; full historical scheduling,
state-space and raw-data bridge remain unavailable. This is a future program
component, not a claim of runnable native reproduction.
"""
import importlib,pathlib,sys,math

def author_module(author_root):
    source=author_root/'src'
    expected=(source/'models/decoders.py').resolve()
    cached=sys.modules.get('models.decoders')
    if cached is not None and pathlib.Path(getattr(cached,'__file__','')).resolve()!=expected:raise RuntimeError('author module cache collision')
    sys.path.insert(0,str(source))
    module=importlib.import_module('models.decoders')
    if pathlib.Path(getattr(module,'__file__','')).resolve()!=expected:raise RuntimeError('author module path mismatch')
    return module

def config(n_units,time_bins,output_size,kind,rank,lr,weight_decay,eids=None):
    c={'n_units':n_units,'n_t_steps':time_bins,'model':{'target':'clf' if kind=='binary' else 'reg','output_size':output_size},'optimizer':{'lr':lr,'weight_decay':weight_decay},'temporal_rank':rank,'reduced_rank':{'temporal_rank':rank}}
    if eids is not None:c['eid_to_indx']={e:i for i,e in enumerate(eids)}
    return c

def create_model(author_root,c,multi=False):
    m=author_module(author_root)
    return m.MultiSessionReducedRankDecoder(c) if multi else m.ReducedRankDecoder(c)

def predict(model,x,kind,eid=None):
    import torch
    model.eval()
    with torch.no_grad():
        z=model(x,eid,'all') if eid is not None else model(x)
        if kind=='binary':z=torch.softmax(z,dim=1)[:,1:2]
        return z.detach().cpu().numpy()

def fit_fixed(model,training,validation,epochs,seed):
    """Fixed hyperparameters; select epoch with equal-session validation loss.

    training/validation are mappings EID -> (tensorX,tensorY). Arrays must already
    have fixed training-only normalization. Full-batch updates are an explicit
    prospective optimizer, not the paper's batch16/minibatch schedule. Caller
    performs validation-only rank/lambda selection and retains its manifest.
    """
    import copy,torch
    if epochs<1 or set(training)!=set(validation):raise ValueError('matched nonempty session support')
    torch.manual_seed(seed)
    optimizer=torch.optim.AdamW(model.parameters(),lr=model.learning_rate,weight_decay=model.weight_decay)
    best=None;best_loss=float('inf');multi=hasattr(model,'eid_to_indx')
    def loss(data):
        terms=[]
        for eid in sorted(data):
            x,y=data[eid];z=model(x,eid,'all') if multi else model(x)
            terms.append(torch.nn.functional.cross_entropy(z,y[:,0].long()) if model.target=='clf' else torch.nn.functional.mse_loss(z,y))
        if not terms:raise ValueError('empty sessions')
        return torch.stack(terms).mean()
    for _ in range(epochs):
        model.train();optimizer.zero_grad();value=loss(training)
        if not torch.isfinite(value):raise ArithmeticError('nonfinite training objective')
        value.backward();optimizer.step();model.eval()
        with torch.no_grad():v=float(loss(validation))
        if math.isfinite(v) and v<best_loss:best_loss=v;best=copy.deepcopy(model.state_dict())
    if best is None:raise ArithmeticError('no finite validation state')
    model.load_state_dict(best);return {'best_validation_loss':best_loss,'epochs':epochs,'prospective_full_batch_optimizer':True}
