"""Fixed original model calls plus a separately named prospective training driver.

Only written source in this phase. The driver fixes test-normalization, omitted
minibatches and per-session validation averaging; it is NOT the released script.
Exact released scripts remain immutable descriptor-bound historical routes.
"""
import types
from .domain import Refusal, MissingDefinition, closed, Pin

CLASSES = {'single_rrr': 'ReducedRankDecoder', 'mlp': 'MLPDecoder',
           'multi_rrr': 'MultiSessionReducedRankDecoder',
           'multi_region_rrr': 'MultiRegionReducedRankDecoder'}

def load_original_model_module(source_store, source_pin):
    # The fixed selected decoder body imports native libraries. Never call in BUILD ONLY.
    raw = source_store.read(source_pin)
    if source_pin.sha256 != '21de9478dcd0a2dd90500b3b3cf48535d5beacb0ca60b119f82c2cd65a8f25f4':
        raise Refusal('original decoder source identity')
    module = types.ModuleType('trial_session_selected_original_decoders')
    exec(compile(raw, source_pin.path, 'exec'), module.__dict__)
    return module

def model_config(method, cases, target, configuration):
    closed(configuration, ('schema', 'rank', 'global_rank', 'lr', 'weight_decay', 'epochs',
                           'batch_size', 'scheduler_t_max', 'seed', 'mlp'), 'training configuration')
    if configuration['schema'] != 'trial_session_prospective_training_v1': raise Refusal('training schema')
    if method not in CLASSES or not cases: raise Refusal('model route')
    t = cases[0]['train_x'].shape[1]; out = cases[0]['train_y'].shape[1]
    if any(c['train_x'].shape[1] != t or c['train_y'].shape[1] != out for c in cases):
        raise Refusal('shared temporal/output axes')
    rank = configuration['rank']
    if type(rank) is not int or rank < 1 or any(rank > min(c['train_x'].shape[2], t) for c in cases):
        raise Refusal('rank support')
    for k in ('epochs', 'batch_size', 'scheduler_t_max'):
        if type(configuration[k]) is not int or configuration[k] < 1: raise Refusal('training finite bounds')
    config = {'n_units': cases[0]['train_x'].shape[2], 'n_t_steps': t,
              'model': {'target': 'clf' if target == 'choice' else 'reg', 'output_size': out},
              'optimizer': {'lr': configuration['lr'], 'weight_decay': configuration['weight_decay']},
              'reduced_rank': {'temporal_rank': rank}, 'temporal_rank': rank,
              'mlp': configuration['mlp']}
    if method.startswith('multi_'):
        config['n_units'] = [c['train_x'].shape[2] for c in cases]
        config['eid_to_indx'] = {c['session']: i for i, c in enumerate(cases)}
    if method == 'multi_region_rrr':
        # Original forward.squeeze loses singleton rank/output axes; preserve and refuse that branch.
        if out == 1 or rank == 1: raise MissingDefinition('original multi-region squeeze compatibility repair required')
        regions = list(dict.fromkeys(c['region'] for c in cases))
        config.update(global_basis_rank=configuration['global_rank'], n_regions=len(regions),
                      region_to_indx={r:i for i,r in enumerate(regions)}, eid_region_to_indx={})
        for i, c in enumerate(cases): config['eid_region_to_indx'].setdefault(c['session'], {})[c['region']] = i
    return config

def fit_linear(train_x, train_y, validation_x, validation_y, target, grid, seed):
    import numpy as np
    from sklearn.linear_model import LogisticRegression, Ridge
    if not grid or any(not np.isfinite(x) or x <= 0 for x in grid): raise Refusal('explicit positive regularization grid')
    x = train_x.reshape(len(train_x), -1); vx = validation_x.reshape(len(validation_x), -1)
    best = None; trace = []
    for penalty in grid:
        if target == 'choice':
            labels = np.asarray(train_y).reshape(-1)
            if set(labels.tolist()) != {0., 1.}: raise Refusal('training class support')
            model = LogisticRegression(C=1./penalty, max_iter=1000, random_state=seed)
            model.fit(x, labels)
            probabilities = model.predict_proba(vx)
            # Validation log loss is the prospective selector, not original default sklearn CV accuracy.
            if tuple(model.classes_) != (0., 1.): raise Refusal('fixed class mapping')
            p = probabilities[:, 1]; yy = validation_y.reshape(-1)
            loss = -np.mean(yy*np.log(np.clip(p, 1e-15, 1))+(1-yy)*np.log(np.clip(1-p, 1e-15, 1)))
        else:
            model = Ridge(alpha=penalty); model.fit(x, train_y)
            loss = np.mean((model.predict(vx)-validation_y)**2)
        if not np.isfinite(loss): raise Refusal('nonfinite validation')
        trace.append({'penalty': penalty, 'validation_loss': float(loss)})
        if best is None or loss < best[0]: best = (float(loss), model, penalty)
    return best[1], {'selection': 'prospective_fixed_validation_loss', 'grid': trace, 'selected': best[2]}

def predict_linear(model, query_x, target):
    if target == 'choice': return model.predict_proba(query_x.reshape(len(query_x), -1))[:, 1:2]
    return model.predict(query_x.reshape(len(query_x), -1))

def fit_original_class(module, method, cases, target, configuration, deadline_check):
    """Actual selected original constructor/forward; all numerical operations future-only.

    Equal-session mean training/validation loss, every final partial batch retained.
    deadline_check is a budget observation hook only, never a native-admission capability.
    """
    import copy
    import numpy as np
    import torch
    config = model_config(method, cases, target, configuration)
    torch.manual_seed(configuration['seed'])
    model = getattr(module, CLASSES[method])(config).double()
    optimizer = torch.optim.AdamW(model.parameters(), lr=configuration['lr'], weight_decay=configuration['weight_decay'])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=configuration['scheduler_t_max'])
    loss_fn = torch.nn.CrossEntropyLoss() if target == 'choice' else torch.nn.MSELoss()
    def forward(c, x):
        return model(x, c['session'], c['region']) if method.startswith('multi_') else model(x)
    def labels(y):
        t = torch.from_numpy(np.asarray(y))
        return t.argmax(dim=1).long() if target == 'choice' else t.double()
    data = [(c, torch.from_numpy(c['train_x']).double(), labels(c['train_y']),
             torch.from_numpy(c['validation_x']).double(), labels(c['validation_y'])) for c in cases]
    if any(len(x)==0 or len(vx)==0 for _,x,_,vx,_ in data): raise Refusal('empty fit/selection split')
    best = None; trace = []
    batch = configuration['batch_size']
    for epoch in range(configuration['epochs']):
        deadline_check(); model.train(); optimizer.zero_grad()
        # Accumulate exact equal-session objective over all rows before one epoch update.
        for c,x,y,_,_ in data:
            order = torch.randperm(len(x))
            for start in range(0, len(x), batch):
                deadline_check(); idx = order[start:start+batch]
                loss = loss_fn(forward(c,x[idx]),y[idx]) * (len(idx)/len(x)/len(data))
                if not torch.isfinite(loss): raise Refusal('nonfinite training loss')
                loss.backward()
        optimizer.step(); scheduler.step(); model.eval()
        with torch.no_grad():
            val = sum(float(loss_fn(forward(c,vx),vy)) for c,_,_,vx,vy in data)/len(data)
        if not np.isfinite(val): raise Refusal('nonfinite selection loss')
        trace.append({'epoch': epoch, 'validation_loss': val})
        if best is None or val < best[0]: best = (val, copy.deepcopy(model.state_dict()), epoch)
    model.load_state_dict(best[1]); model.eval()
    return model, {'training_profile': 'prospective_full_support_epoch_objective_v1',
                   'selected_epoch': best[2], 'trace': trace, 'configuration': configuration}

def predict_original_class(model, method, case, query_x, target):
    import torch
    with torch.no_grad():
        x = torch.from_numpy(query_x).double()
        out = model(x, case['session'], case['region']) if method.startswith('multi_') else model(x)
        if target == 'choice': out = torch.softmax(out, dim=-1)[:, 1:2]
        return out.detach().cpu().numpy()

def select_configurations(fit, configurations):
    """No implicit TableS2 grid: exact earlier finite configurations are mandatory."""
    if not configurations: raise MissingDefinition('exact selected hyperparameter roster')
    outcomes = []
    for c in configurations:
        model, trace = fit(c)
        outcomes.append((trace['trace'][trace['selected_epoch']]['validation_loss'], model, trace))
    return min(outcomes, key=lambda row: row[0])[1:]
