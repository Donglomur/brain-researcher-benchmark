#!/usr/bin/env python3
"""Prospective NEURAL-072 matrix encoder and independent contrast scorer.

No recordings, checkpoints, or author encoder are bundled. See scope documentation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

SOURCE_TASK_SHA256 = 'f19b5081130f76f0a66fe032e459c891b2a759931f2ebc69cbe99d17797f6cc7'
TASK_SHA256 = '26b292bd06b0b3a11c7e9b96e44e4a7a1cd0a14ac559b579a3cb70db684630ae'
ARMS = ('nuisance', 'lexical', 'contextual')
CONTRASTS = (('lexical', 'nuisance'), ('contextual', 'nuisance'), ('contextual', 'lexical'))
NUISANCE = ['acoustic_envelope', 'word_rate', 'lexical_log_frequency', 'time']
HOLDS = ['authentic_NEURAL071_membership_and_full_population', 'scan_stimulus_transcript_HRF_clock',
         'derivative_annex_and_atlas_identity', 'checkpoint_training_exposure_and_feature_lineage',
         'data_stimulus_code_checkpoint_rights', 'source_locked_predictive_reference',
         'protected_native_execution_and_independent_reproduction', 'final_protocol_and_resource_admission']


class ContractError(ValueError):
    """An input violates the prospective recipe or its declared population."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def digest(obj):
    """Semantic JSON digest; file digests are separately recorded in provenance."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def integer(x, name, minimum=0):
    require(type(x) is int and x >= minimum, name + ' must be an integer >= ' + str(minimum))
    return x


def matrix(x, name):
    try:
        a = np.asarray(x, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ContractError(name + ' must be numeric') from exc
    require(a.ndim == 2 and a.size > 0 and np.isfinite(a).all(), name + ' must be a finite nonempty matrix')
    return a


def vector(x, name):
    try:
        a = np.asarray(x, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ContractError(name + ' must be numeric') from exc
    require(a.ndim == 1 and np.isfinite(a).all(), name + ' must be a finite vector')
    return a


def validate(protocol, cases):
    require(isinstance(protocol,dict) and isinstance(cases,dict), 'protocol and cases must be objects')
    require(protocol.get('task_id') == 'NEURAL-072', 'wrong task')
    require(protocol.get('task_sha256') == TASK_SHA256, 'task contract pin mismatch')
    require(protocol.get('recipe') == 'prospective-whitened-ridge-v1', 'unknown recipe')
    require(cases.get('source_task') == 'NEURAL-071', 'cases must originate from NEURAL-071')
    require(cases.get('source_task_sha256') == SOURCE_TASK_SHA256, 'NEURAL-071 contract pin differs')
    require(protocol.get('cases_sha256') == digest(cases), 'frozen NEURAL-071 cases differ')
    require(protocol.get('context_direction') == 'past_and_present', 'future context is forbidden')
    require(protocol.get('nuisance_columns') == NUISANCE, 'required nuisance columns and order differ')
    require(protocol.get('metric') == 'run-centered-pooled-family-r2', 'metric must be frozen')
    require(protocol.get('constant_target_policy') == 'reject', 'constant targets may not be silently dropped')
    require(protocol.get('case_scope') == 'within_listener', 'new-listener transfer requires a separate contract')
    for key in ('atlas_pin', 'clock_manifest_pin', 'checkpoint_pin', 'checkpoint_exposure', 'feature_lineage_pin', 'rights_review_pin'):
        require(isinstance(protocol.get(key), str) and protocol[key].strip(), key + ' must be explicit (unresolved values do not admit science)')
    lags = protocol.get('lags')
    require(isinstance(lags, list) and lags and all(type(x) is int and x >= 0 for x in lags) and lags == sorted(set(lags)), 'lags must be unique ordered nonnegative samples')
    integer(protocol.get('feature_rank'), 'feature_rank', 1)
    alphas = protocol.get('alphas')
    require(isinstance(alphas, list) and alphas and all(type(x) in (int, float) and np.isfinite(x) and x > 0 for x in alphas), 'alphas must be positive finite values')
    require(alphas == sorted(set(alphas)), 'alpha grid must be ordered and unique')
    integer(protocol.get('bootstrap_replicates'), 'bootstrap_replicates', 1)
    integer(protocol.get('null_replicates'), 'null_replicates', 1)
    integer(protocol.get('seed'), 'seed', 0)
    integer(protocol.get('null_min_shift'), 'null_min_shift', 1)
    require(protocol['null_min_shift'] >= max(lags), 'null guard must cover lag support')
    runs = cases.get('runs')
    require(isinstance(runs, list) and len(runs) > 0, 'missing complete run inventory')
    ids, family_splits, listeners = set(), {}, {}
    story_families, passage_families, scans = {}, {}, set()
    target_ids = cases.get('target_ids')
    require(isinstance(target_ids, list) and target_ids and all(isinstance(x, str) and x for x in target_ids) and len(set(target_ids)) == len(target_ids), 'fixed target identities required')
    for run in runs:
        require(isinstance(run,dict), 'every run must be an object')
        for field in ('id', 'listener', 'story_family', 'story', 'scan_identity'):
            require(isinstance(run.get(field), str) and run[field], 'run identity missing: ' + field)
        require(run['id'] not in ids, 'duplicate run ID'); ids.add(run['id'])
        require(run.get('split') in ('train', 'dev', 'test'), 'invalid split')
        require(run['scan_identity'] not in scans, 'duplicate scan identity'); scans.add(run['scan_identity'])
        family = run['story_family']
        require(story_families.setdefault(run['story'], family) == family, 'same story assigned different families')
        passages = run.get('passage_ids')
        require(isinstance(passages,list) and passages and all(isinstance(x,str) and x for x in passages) and len(set(passages)) == len(passages), 'reviewed passage identities required')
        for passage in passages:
            require(passage_families.setdefault(passage, family) == family, 'repeated passage assigned different families')
        require(family_splits.setdefault(family, run['split']) == run['split'], 'story family crosses partitions')
        listeners.setdefault(run['listener'], set()).add(run['split'])
        n = integer(run.get('n_time'), 'n_time', 3)
        indices = run.get('indices')
        require(isinstance(indices, list) and len(indices) >= 3 and all(type(i) is int for i in indices), 'at least three frozen rows required')
        require(indices == list(range(indices[0], indices[-1]+1)), 'scored/fitted rows must be a single contiguous interval per run')
        require(indices[0] >= max(lags) and indices[-1] < n, 'lag support or row outside run')
        require(type(run.get('tr')) in (int, float) and np.isfinite(run['tr']) and run['tr'] > 0, 'TR invalid')
        require(type(run.get('scanner_start')) in (int, float) and np.isfinite(run['scanner_start']), 'scanner clock invalid')
        require(type(run.get('story_start')) in (int, float) and type(run.get('story_end')) in (int, float) and np.isfinite([run['story_start'],run['story_end']]).all() and run['story_start'] < run['story_end'], 'story interval invalid')
        if run['split'] == 'test':
            require(len(indices) > 2 * protocol['null_min_shift'] + 1, 'test interval too short for nontrivial null shifts')
    require(all(v == {'train', 'dev', 'test'} for v in listeners.values()), 'each listener requires train, dev and test stories')
    require(len({r['story_family'] for r in runs if r['split']=='test'}) >= 2 and len(listeners) >= 2, 'crossed uncertainty requires at least two test families and listeners')
    return runs


def prepare(protocol, cases, features):
    runs = validate(protocol, cases)
    require(isinstance(features,dict), 'features must be an object keyed by run')
    require(set(features) == {r['id'] for r in runs}, 'feature inventory differs from frozen cases')
    result = {}
    dimensions = None
    for r in runs:
        f = features[r['id']]
        require(isinstance(f,dict), 'run features must be an object')
        require(set(f) == {'nuisance', 'lexical', 'contextual', 'support_start', 'support_end'}, 'feature keys differ')
        blocks = [matrix(f[k], k) for k in ARMS]
        require(all(x.shape[0] == r['n_time'] for x in blocks), 'feature time dimension differs')
        require(blocks[0].shape[1] == len(NUISANCE), 'nuisance width differs')
        widths = tuple(x.shape[1] for x in blocks)
        if dimensions is None: dimensions = widths
        require(dimensions == widths, 'feature dimensions differ between runs')
        support_start = vector(f['support_start'], 'support_start')
        support_end = vector(f['support_end'], 'support_end')
        require(support_start.shape == (r['n_time'],) and support_end.shape == support_start.shape and np.isfinite(support_start).all() and np.isfinite(support_end).all(), 'feature support shape/values invalid')
        times = r['scanner_start'] + r['tr'] * np.arange(r['n_time'])
        require(np.all(support_start <= support_end) and np.all(support_end <= times + 1e-9), 'future or inverted feature context')
        rows = np.asarray(r['indices'])
        used = np.unique(np.concatenate([rows-lag for lag in protocol['lags']]))
        require(np.all(support_start[used] >= r['story_start'] - 1e-9) and np.all(support_end[used] <= r['story_end'] + 1e-9), 'feature context/lag support crosses story boundary')
        require(np.all(times[rows] >= r['story_start']) and np.all(times[rows] <= r['story_end']), 'target rows cross story boundary')
        context_samples = int(np.ceil(np.max(times[used]-support_start[used]) / r['tr']))
        require(protocol['null_min_shift'] >= context_samples + max(protocol['lags']), 'null guard must cover context plus lag support')
        result[r['id']] = {arm: np.concatenate([x[rows-lag] for lag in protocol['lags']], axis=1) for arm, x in zip(ARMS, blocks)}
    return result


def targets(cases, values, split_set):
    runs = [r for r in cases['runs'] if r['split'] in split_set]
    require(isinstance(values,dict), 'targets must be an object keyed by run')
    require(set(values) == {r['id'] for r in runs}, 'target inventory must exactly match allowed splits; hidden targets cannot enter fitting')
    out = {}
    for r in runs:
        a = matrix(values[r['id']], 'targets')
        require(a.shape == (len(r['indices']), len(cases['target_ids'])), 'target shape differs from frozen rows/atlas')
        out[r['id']] = a
    return out


def whitener(x):
    mean = x.mean(axis=0)
    _, s, vt = np.linalg.svd(x-mean, full_matrices=False)
    keep = s > (s[0] * 1e-10 if s.size and s[0] else 1e-10)
    require(keep.any(), 'no nonconstant feature direction')
    transform = vt[keep].T * (np.sqrt(len(x))/s[keep])
    return mean, transform


class Design:
    """Train-only nuisance whitening and residualized equal-rank feature whitening."""
    def __init__(self, blocks, rank):
        self.nmean, self.ntransform = whitener(blocks['nuisance'])
        nuisance = (blocks['nuisance']-self.nmean) @ self.ntransform
        self.parts = {}
        for arm in ('lexical', 'contextual'):
            x = blocks[arm]
            mean = x.mean(axis=0)
            beta = np.linalg.lstsq(nuisance, x-mean, rcond=1e-10)[0]
            residual = x-mean-nuisance@beta
            _, s, vt = np.linalg.svd(residual, full_matrices=False)
            # Reference the ORIGINAL block scale: residual roundoff is not signal.
            original_scale = np.linalg.norm(x-mean, ord=2)
            tolerance = original_scale * max(1e-10, np.finfo(float).eps * max(x.shape))
            available = int(np.sum(s > tolerance))
            require(available >= rank, arm + ' cannot support frozen feature rank')
            self.parts[arm] = (mean, beta, vt[:rank].T * (np.sqrt(len(x))/s[:rank]))
        self.rank = rank
        for arm in ('lexical','contextual'):
            design = self.transform(blocks,arm)
            require(np.allclose(design.T@design, len(design)*np.eye(design.shape[1]), rtol=1e-8, atol=1e-8), 'unstable residual whitening: training Gram is not orthogonal')

    def transform(self, blocks, arm):
        nuisance = (blocks['nuisance']-self.nmean) @ self.ntransform
        if arm == 'nuisance': return nuisance
        mean, beta, transform = self.parts[arm]
        feature = (blocks[arm]-mean-nuisance@beta) @ transform
        return np.concatenate([nuisance, feature], axis=1)


def stack_blocks(run_list, prepared):
    return {arm: np.concatenate([prepared[r['id']][arm] for r in run_list]) for arm in ARMS}


def ridge(x, y, alpha):
    mean = y.mean(axis=0)
    coefficients = np.linalg.solve(x.T@x + alpha*np.eye(x.shape[1]), x.T@(y-mean))
    return coefficients, mean


def fit_predict(protocol, cases, features, training_targets):
    """Access boundary: this function accepts train/dev targets only, never test targets."""
    prepared = prepare(protocol, cases, features)
    ys = targets(cases, training_targets, {'train', 'dev'})
    output, ledger = {}, []
    for listener in sorted({r['listener'] for r in cases['runs']}):
        rs = [r for r in cases['runs'] if r['listener'] == listener]
        train = [r for r in rs if r['split']=='train']; dev = [r for r in rs if r['split']=='dev']
        train_blocks = stack_blocks(train, prepared)
        design = Design(train_blocks, protocol['feature_rank'])
        y = np.concatenate([ys[r['id']] for r in train])
        losses = []
        for alpha in protocol['alphas']:
            by_family = {}
            # Shared alpha is selected by equally weighted lexical/contextual dev MSE.
            for arm in ('lexical', 'contextual'):
                coef, mean = ridge(design.transform(train_blocks, arm), y, alpha)
                for r in dev:
                    error = np.mean((ys[r['id']]-(design.transform(prepared[r['id']],arm)@coef+mean))**2)
                    by_family.setdefault(r['story_family'], []).append(float(error))
            losses.append(float(np.mean([np.mean(v) for v in by_family.values()])))
        alpha = protocol['alphas'][int(np.argmin(losses))]
        allowed = train+dev
        blocks = stack_blocks(allowed, prepared)
        design = Design(blocks, protocol['feature_rank'])
        y = np.concatenate([ys[r['id']] for r in allowed])
        dfs = {}
        for arm in ARMS:
            x = design.transform(blocks, arm)
            coef, mean = ridge(x, y, alpha)
            eigenvalues = np.linalg.eigvalsh(x.T@x)
            dfs[arm] = float(1 + np.sum(eigenvalues/(eigenvalues+alpha)))
            for r in rs:
                if r['split']=='test':
                    output.setdefault(r['id'], {})[arm] = (design.transform(prepared[r['id']],arm)@coef+mean).tolist()
        require(abs(dfs['lexical']-dfs['contextual']) < 1e-7, 'matched arms differ in effective degrees of freedom')
        ledger.append({'listener': listener, 'alpha': alpha, 'dev_losses_in_alpha_order': losses,
                       'selection_fits': 2*len(protocol['alphas']), 'final_fits':3,
                       'training_rows':len(y), 'nuisance_rank':design.ntransform.shape[1],
                       'linguistic_rank':design.rank, 'effective_df_including_intercept':dfs})
    return {'task_id':'NEURAL-072', 'protocol_sha256':digest(protocol), 'cases_sha256':digest(cases),
            'predictions':output, 'fit_ledger':ledger, 'recipe_status':'prospective_engineering_only'}


def prediction_arrays(protocol, cases, prediction):
    require(isinstance(prediction,dict), 'predictions must be an object')
    require(prediction.get('task_id') == 'NEURAL-072', 'prediction task ID differs')
    require(prediction.get('protocol_sha256') == digest(protocol) and prediction.get('cases_sha256') == digest(cases), 'prediction protocol/case pin mismatch')
    runs = [r for r in cases['runs'] if r['split']=='test']
    values = prediction.get('predictions', {})
    require(isinstance(values,dict), 'predictions must map run IDs to arms')
    require(set(values)=={r['id'] for r in runs}, 'missing or extra prediction runs')
    out = {}
    for r in runs:
        require(isinstance(values[r['id']],dict), 'run predictions must be an object')
        require(set(values[r['id']]) == set(ARMS), 'exactly three prediction arms required')
        out[r['id']] = {}
        for arm in ARMS:
            a = matrix(values[r['id']][arm], arm)
            require(a.shape == (len(r['indices']),len(cases['target_ids'])), 'prediction shape differs')
            out[r['id']][arm] = a
    return out


def cell_metrics(cases, ys, predictions):
    sums = {}
    for r in cases['runs']:
        if r['split'] != 'test': continue
        y, p = ys[r['id']], predictions[r['id']]
        with np.errstate(over='ignore', invalid='ignore'):
            sst = np.sum((y-y.mean(axis=0))**2, axis=0)
        require(np.isfinite(sst).all(), 'nonfinite target variance')
        require(np.all(sst > 0), 'constant target in a frozen run: reject; do not omit')
        key = (r['listener'],r['story_family'])
        cell = sums.setdefault(key, {'sst':np.zeros(y.shape[1]), 'sse':{a:np.zeros(y.shape[1]) for a in ARMS}, 'runs':[]})
        cell['sst'] += sst; cell['runs'].append(r['id'])
        for arm in ARMS:
            with np.errstate(over='ignore', invalid='ignore'):
                sse = np.sum((y-p[arm])**2, axis=0)
                cell['sse'][arm] += sse
            require(np.isfinite(cell['sse'][arm]).all(), 'nonfinite squared prediction error')
        require(np.isfinite(cell['sst']).all(), 'nonfinite pooled target variance')
    result = []
    for (listener,family), s in sorted(sums.items()):
        r2 = {a:1-s['sse'][a]/s['sst'] for a in ARMS}
        contrasts = {a+'_minus_'+b:(s['sse'][b]-s['sse'][a])/s['sst'] for a,b in CONTRASTS}
        require(all(np.isfinite(v).all() for v in list(r2.values())+list(contrasts.values())), 'nonfinite variance score')
        result.append({'listener':listener,'story_family':family,'runs':s['runs'],
                       'r2_by_target':{a:v.tolist() for a,v in r2.items()},
                       'contrast_by_target':{k:v.tolist() for k,v in contrasts.items()},
                       'contrasts':{k:float(v.mean()) for k,v in contrasts.items()}})
    return result


def summarize(cells, listener_weights=None, family_weights=None):
    keys = list(cells[0]['contrasts'])
    lw = listener_weights or {c['listener']:1 for c in cells}
    fw = family_weights or {c['story_family']:1 for c in cells}
    listeners = {}
    for c in cells:
        weight = fw.get(c['story_family'],0)
        if weight and lw.get(c['listener'],0):
            listeners.setdefault(c['listener'], []).append((weight,c['contrasts']))
    require(bool(listeners), 'bootstrap draw has no observed cells')
    return {k:float(sum(lw[l]*sum(w*v[k] for w,v in rows)/sum(w for w,v in rows) for l,rows in listeners.items())/sum(lw[l] for l in listeners)) for k in keys}


def bootstrap(cells, count, seed):
    rng = np.random.default_rng(seed)
    listeners = sorted({c['listener'] for c in cells}); families = sorted({c['story_family'] for c in cells})
    draws, empty = [], 0
    for _ in range(count):
        lw = dict(zip(listeners, rng.multinomial(len(listeners), np.full(len(listeners),1/len(listeners)))))
        fw = dict(zip(families, rng.multinomial(len(families), np.full(len(families),1/len(families)))))
        try: draws.append(summarize(cells,lw,fw))
        except ContractError: empty += 1
    require(len(draws) >= max(1,int(.9*count)), 'too many empty crossed-cluster bootstrap draws')
    return {'method':'crossed listener x story-family pigeonhole percentile bootstrap', 'requested':count,
            'valid':len(draws),'empty':empty, 'seed':seed,
            'intervals_95':{k:np.quantile([d[k] for d in draws],[.025,.975]).tolist() for k in draws[0]},
            'limitation':'Descriptive uncertainty for the frozen observed incidence design; small cluster counts and nonrandom missing cells limit population inference.'}


def null_diagnostics(protocol, cases, ys, predictions):
    rng = np.random.default_rng(protocol['seed']+1)
    observed = summarize(cell_metrics(cases,ys,predictions))['contextual_minus_lexical']
    null_values = []
    for _ in range(protocol['null_replicates']):
        shifted = {}
        # Same random phase fraction per story family preserves shared stimulus grouping.
        phases = {f:float(rng.random()) for f in sorted({r['story_family'] for r in cases['runs'] if r['split']=='test'})}
        for r in cases['runs']:
            if r['split']!='test': continue
            p = predictions[r['id']]; n = len(p['lexical']); guard=protocol['null_min_shift']
            choices = np.arange(guard+1,n-guard)
            require(len(choices)>0, 'no admissible circular shifts')
            shift = int(choices[min(int(phases[r['story_family']]*len(choices)),len(choices)-1)])
            shifted[r['id']] = {a:p[a] for a in ARMS}
            shifted[r['id']]['contextual'] = p['lexical'] + np.roll(p['contextual']-p['lexical'],shift,axis=0)
        null_values.append(summarize(cell_metrics(cases,ys,shifted))['contextual_minus_lexical'])
    return {'kind':'run-bounded circular shift of contextual-minus-lexical prediction contribution',
            'values':null_values, 'diagnostic_upper_tail_fraction':float((1+sum(v>=observed for v in null_values))/(1+len(null_values))),
            'minimum_shift_samples_exclusive':protocol['null_min_shift'],
            'limitation':'Alignment diagnostic only: circular stationarity and conditional exchangeability are not established; this is not a calibrated significance p-value or a refitted null encoder.'}


def score(protocol, cases, test_targets, prediction):
    validate(protocol,cases)
    ys = targets(cases,test_targets,{'test'})
    p = prediction_arrays(protocol,cases,prediction)
    cells = cell_metrics(cases,ys,p)
    return {'task_id':'NEURAL-072','protocol_sha256':digest(protocol),'cases_sha256':digest(cases),
            'recipe_status':'prospective_engineering_only','scientific_qualified':False,'submission_ready':False,
            'preserved_holds':HOLDS,'cells':cells,'listener_macro_contrasts':summarize(cells),
            'by_story_family':{f:summarize([c for c in cells if c['story_family']==f]) for f in sorted({c['story_family'] for c in cells})},
            'by_listener':{l:summarize([c for c in cells if c['listener']==l]) for l in sorted({c['listener'] for c in cells})},
            'uncertainty':bootstrap(cells,protocol['bootstrap_replicates'],protocol['seed']),
            'temporal_null':null_diagnostics(protocol,cases,ys,p),
            'counts':{'listeners':len({c['listener'] for c in cells}),'story_families':len({c['story_family'] for c in cells}),
                      'listener_family_cells':len(cells),'runs':len(ys),'targets':len(cases['target_ids'])}}


def load(path):
    def reject_constant(value): raise ContractError('nonfinite JSON number '+value)
    def unique_keys(pairs):
        obj = {}
        for key,value in pairs:
            require(key not in obj, 'duplicate JSON key: '+key); obj[key]=value
        return obj
    return json.loads(Path(path).read_text(),parse_constant=reject_constant,object_pairs_hook=unique_keys)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['predict','score'])
    for name in ('protocol','cases','targets','output'): parser.add_argument('--'+name,required=True)
    parser.add_argument('--features'); parser.add_argument('--predictions')
    args=parser.parse_args()
    try:
        protocol,cases=load(args.protocol),load(args.cases)
        if args.mode=='predict':
            require(args.features is not None and args.predictions is None,'predict needs features, no predictions')
            result=fit_predict(protocol,cases,load(args.features),load(args.targets))
        else:
            require(args.predictions is not None and args.features is None,'score needs predictions, no features')
            result=score(protocol,cases,load(args.targets),load(args.predictions))
        result['input_file_sha256']={k:hashlib.sha256(Path(v).read_bytes()).hexdigest() for k,v in vars(args).items() if k not in ('mode','output') and v is not None}
        Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    except (ContractError, OSError, json.JSONDecodeError, np.linalg.LinAlgError) as exc:
        parser.exit(2,'NEURAL-072 rejected input: '+str(exc)+'\n')


if __name__=='__main__': main()
