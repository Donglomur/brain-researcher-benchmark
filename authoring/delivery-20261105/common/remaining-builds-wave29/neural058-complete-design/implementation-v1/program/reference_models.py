"""Concrete independent two-head ridge, forest and set-network producers.

No authentic work at import. All state is primitive arrays/JSON; no estimator
pickle is loaded. Physical memory/device/source parity remains separately gated.
"""
import math
from core import need
from features import fit_representation, encode, weighted_scaler, standardized
from numeric_recipe import RECIPE, seeds


def training_rows(sessions, role, budget):
    import numpy as np
    need(sessions and len({s['session'] for s in sessions})==len(sessions), 'complete unique training sessions')
    from ordering import animals as ordered_animals
    animals=ordered_animals(sessions)
    counts={a:sum(s['animal']==a for s in sessions) for a in animals}
    representation=fit_representation(sessions)
    windows=[]; ys=[]; weights=[]; xs=[]
    for session in sessions:
        need(session['windows'], 'no empty source session')
        for window in session['windows']:
            budget.tick(); n=len(window['times'])
            need(n>0 and window['labels'].shape==(n,2), 'full two-head source targets')
            value=encode(window,representation,role)
            w=np.full(n,1.0/(len(animals)*counts[session['animal']]*len(session['windows'])*n),dtype=np.float64)
            windows.append((value,window['labels'],w)); xs.append(value['tabular']); ys.append(window['labels']); weights.append(w)
    X=np.concatenate(xs); Y=np.concatenate(ys).astype(np.float64); W=np.concatenate(weights)
    need(np.isfinite(X).all() and np.isfinite(Y).all(), 'finite complete training matrix')
    xscale=weighted_scaler(X,W); yscale=weighted_scaler(Y,W)
    need(not bool(yscale['constant'].any()), 'zero source head variance is a fit failure')
    budget.tick()
    return representation,windows,X,Y,W,xscale,yscale


def network(role, context_width, unit_width, regions):
    import torch
    nn=torch.nn
    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.role=role
            if role=='J':
                self.embedding=nn.Embedding(regions,16)
                self.unit=nn.Sequential(nn.Linear(unit_width+16,128),nn.ReLU(),nn.Linear(128,128),nn.ReLU())
            width=context_width+11+(257 if role=='J' else 0)
            self.readout=nn.Sequential(nn.Linear(width,128),nn.ReLU(),nn.Linear(128,128),nn.ReLU(),nn.Linear(128,2))
        def forward(self,context,time,unit,codes):
            n=len(time); parts=[context.expand(n,-1),time]
            if self.role=='J':
                h=self.unit(torch.cat((unit,self.embedding(codes)),dim=1))
                U=len(h); need(U>0,'full nonempty unit set')
                pooled=torch.cat((h.mean(dim=0),h.sum(dim=0)/math.sqrt(U),h.new_tensor([math.log1p(U)])))
                parts.append(pooled.expand(n,-1))
            return self.readout(torch.cat(parts,dim=1))
    return Model()


def fit(config,role,fold,sessions,budget,device='cpu'):
    import numpy as np
    need(role in ('C','J'),'fixed reference role')
    representation,windows,X,Y,W,xscale,yscale=training_rows(sessions,role,budget)
    Z=standardized(X,xscale); T=standardized(Y,yscale)
    state={'schema':'neural058_reference_state_v1','role':role,'fold':fold,'config':dict(config),
           'recipe':RECIPE,'representation':representation,'xscale':xscale,'yscale':yscale,
           'training_sessions':[s['session'] for s in sessions],
           'training_animals':__import__('ordering').animals(sessions)}
    family=config['family']; budget.tick()
    if family=='ridge':
        gram=Z.T@(W[:,None]*Z)
        rhs=Z.T@(W[:,None]*T)
        gram.flat[::len(gram)+1] += config['alpha']
        # No silent pseudoinverse/regularization change on failure.
        coef=np.linalg.solve(gram,rhs)
        need(np.isfinite(coef).all(), 'finite full ridge solution')
        state['coef']=coef
        state['solver_residual']=float(np.linalg.norm(gram@coef-rhs))
    elif family=='forest':
        from sklearn.ensemble import ExtraTreesRegressor
        model=ExtraTreesRegressor(n_estimators=512,max_depth=config['max_depth'],
                                  min_samples_leaf=config['min_samples_leaf'],criterion='squared_error',
                                  bootstrap=False,max_features=1.0,random_state=580058,n_jobs=1)
        model.fit(Z,T,sample_weight=W)
        need(len(model.estimators_)==512,'all512 fitted trees')
        state['trees']=[]
        for estimator in model.estimators_:
            budget.tick(); t=estimator.tree_
            state['trees'].append({'left':t.children_left.copy(),'right':t.children_right.copy(),
                                   'feature':t.feature.copy(),'threshold':t.threshold.copy(),
                                   'value':t.value[:,:,0].copy(), 'impurity':t.impurity.copy(),
                                   'n_node_samples':t.n_node_samples.copy(),
                                   'weighted_n_node_samples':t.weighted_n_node_samples.copy(),
                                   'max_depth':int(t.max_depth),'node_count':int(t.node_count)})
        state['forest_native_prediction_parity_required']=True
    elif family=='set':
        import random
        import torch
        from torch.nn.utils import clip_grad_norm_
        initialization=seeds(role,fold); random.seed(initialization['torch_cpu_and_python'])
        torch.manual_seed(initialization['torch_cpu_and_python']); torch.use_deterministic_algorithms(True)
        # Explicit source-only context scaler, equal to the corresponding
        # repeated context columns' normalized training-observation measure.
        C=np.concatenate([np.broadcast_to(v['context'],(len(y),len(v['context']))) for v,y,w in windows])
        cscale=weighted_scaler(C,W)
        model=network(role,len(windows[0][0]['context']),0 if role=='C' else windows[0][0]['unit'].shape[1],len(representation['regions']))
        model=model.to(device=device,dtype=torch.float32)
        optimizer=torch.optim.AdamW(model.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'],
                                    betas=(.9,.999),eps=1e-8,amsgrad=False,foreach=False,fused=False)
        M=math.ceil(len(windows)/32); history=[]
        for epoch in range(config['epochs']):
            budget.tick(); rng=np.random.Generator(np.random.PCG64(seeds(role,fold,epoch)['numpy_PCG64']))
            order=rng.permutation(len(windows)); epoch_loss=0.0
            for start in range(0,len(order),32):
                optimizer.zero_grad(set_to_none=True)
                for index in order[start:start+32]:
                    budget.tick(); value,y,w=windows[int(index)]
                    c=standardized(value['context'][None,:],cscale)[0]
                    tx=lambda a:torch.as_tensor(a,device=device,dtype=torch.float32)
                    unit=None if role=='C' else tx(value['unit'])
                    codes=None if role=='C' else torch.as_tensor(value['codes'],device=device,dtype=torch.long)
                    prediction=model(tx(c),tx(value['time']),unit,codes)
                    target=tx(standardized(y,yscale)); weight=tx(w)
                    loss=M*torch.sum(weight*torch.mean((prediction-target)**2,dim=1))
                    need(bool(torch.isfinite(loss).item()),'finite full network loss')
                    loss.backward(); epoch_loss+=float(loss.detach().cpu())/M
                norm=clip_grad_norm_(model.parameters(),1.0,error_if_nonfinite=True)
                optimizer.step(); budget.tick()
            history.append({'epoch':epoch,'complete_weighted_loss':epoch_loss,'logical_updates':M})
        state['network']={name:value.detach().cpu().numpy().copy() for name,value in model.state_dict().items()}
        state['cscale']=cscale; state['unit_width']=0 if role=='C' else windows[0][0]['unit'].shape[1]
        state['history']=history; state['initialization']=initialization
        # Complete AdamW state is retained safely, with parameter-name mapping.
        state['optimizer']={}
        for name,param in model.named_parameters():
            state['optimizer'][name]={k:(v.detach().cpu().numpy().copy() if torch.is_tensor(v) else v)
                                       for k,v in optimizer.state[param].items()}
    else: raise ValueError('unknown fixed family')
    budget.tick(); return state


def predict(state,window,budget,device='cpu'):
    import numpy as np
    budget.tick(); role=state['role']; v=encode(window,state['representation'],role)
    z=standardized(v['tabular'],state['xscale']); family=state['config']['family']
    if family=='ridge': y=z@state['coef']
    elif family=='forest':
        # sklearn trees route float32 inputs against float64 thresholds.
        x=z.astype(np.float32); y=np.zeros((len(x),2),dtype=np.float64)
        need(len(state['trees'])==512,'complete512-tree restore')
        for tree in state['trees']:
            budget.tick(); n=tree['node_count']; nodes=np.zeros(len(x),dtype=np.int64)
            need(tree['value'].shape==(n,2),'complete two-head tree state')
            for _ in range(n):
                active=tree['left'][nodes]!=-1
                if not active.any(): break
                rows=np.flatnonzero(active); at=nodes[rows]; features=tree['feature'][at]
                need(np.all((features>=0)&(features<x.shape[1])),'valid complete tree split')
                nodes[rows]=np.where(x[rows,features]<=tree['threshold'][at],tree['left'][at],tree['right'][at])
                need(np.all((nodes>=0)&(nodes<n)),'tree child index')
            else: raise ValueError('cyclic or malformed complete tree')
            y+=tree['value'][nodes]
        y/=512
    elif family=='set':
        import torch
        torch.use_deterministic_algorithms(True)
        model=network(role,len(v['context']),state['unit_width'],len(state['representation']['regions']))
        need(set(model.state_dict())==set(state['network']),'exact full network tensor names')
        for name,value in model.state_dict().items(): need(tuple(value.shape)==state['network'][name].shape,'exact network tensor shape')
        model.load_state_dict({k:torch.as_tensor(a) for k,a in state['network'].items()},strict=True)
        model=model.to(device=device,dtype=torch.float32); model.eval()
        c=standardized(v['context'][None,:],state['cscale'])[0]
        tx=lambda a:torch.as_tensor(a,device=device,dtype=torch.float32)
        with torch.no_grad():
            y=model(tx(c),tx(v['time']),None if role=='C' else tx(v['unit']),
                    None if role=='C' else torch.as_tensor(v['codes'],device=device,dtype=torch.long)).cpu().numpy().astype(np.float64)
    else: raise ValueError('unknown fixed family')
    y=y*state['yscale']['scale']+state['yscale']['mean']
    need(y.shape==(len(window['times']),2) and np.isfinite(y).all(),'complete finite restored prediction')
    budget.tick(); return y
