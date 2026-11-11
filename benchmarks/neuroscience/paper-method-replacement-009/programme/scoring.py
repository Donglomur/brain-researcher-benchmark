"""Protected scientific scorer source. Never executed in BUILD ONLY controls."""
from .domain import Refusal, closed, Pin, strict_json

def metric(target, truth, prediction):
    import numpy as np
    from sklearn.metrics import roc_auc_score, accuracy_score, r2_score
    y, p = np.asarray(truth), np.asarray(prediction)
    if y.shape != p.shape or y.size == 0 or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise Refusal('score complete finite support')
    if target in ('choice', 'allen_gabor', 'allen_grating', 'allen_lick'):
        if target in ('choice', 'allen_lick'):
            if np.any(p < 0) or np.any(p > 1) or not set(y.reshape(-1).tolist()) <= {0,1}: raise Refusal('binary score')
            auc = None if len(set(y.reshape(-1).tolist())) < 2 else float(roc_auc_score(y.reshape(-1), p.reshape(-1)))
            return {'auc': auc, 'accuracy': float(accuracy_score(y.reshape(-1), p.reshape(-1) > .5)),
                    'undefined_reason': 'single_class' if auc is None else None, 'n': len(y)}
        raise Refusal('multiclass prediction must use score_multiclass')
    if target == 'prior':
        a, b = y.reshape(-1), p.reshape(-1)
        if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
            return {'pearson': None, 'undefined_reason': 'constant_or_insufficient', 'n': len(y)}
        return {'pearson': float(np.corrcoef(a,b)[0,1]), 'undefined_reason': None, 'n': len(y)}
    if np.var(y) == 0: return {'r2': None, 'undefined_reason': 'constant_truth', 'n': len(y)}
    return {'r2': float(r2_score(y.reshape(-1), p.reshape(-1))), 'undefined_reason': None, 'n': len(y)}

def score_multiclass(truth, probabilities, class_order):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    y, p = np.asarray(truth), np.asarray(probabilities)
    if p.shape != (len(y),len(class_order)) or not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1):
        raise Refusal('multiclass finite shape')
    if not np.allclose(p.sum(axis=1),1.,rtol=0,atol=1e-12): raise Refusal('probability simplex')
    if not set(y.tolist()) <= set(class_order): raise Refusal('fixed class vocabulary')
    predicted = np.asarray(class_order)[p.argmax(axis=1)]
    complete = set(y.tolist()) == set(class_order)
    return {'accuracy': float((predicted == y).mean()),
            'auc': float(roc_auc_score(y,p,labels=class_order,multi_class='ovr',average='macro')) if complete else None,
            'undefined_reason': None if complete else 'missing_query_class', 'n':len(y)}

def aggregate(rows, primary_metric):
    """All requested rows survive; no averaging away an operational failure."""
    import numpy as np
    complete = all(r['status'] == 'complete' and r['metrics'].get(primary_metric) is not None for r in rows)
    animals = {}
    for r in rows: animals.setdefault(r['animal'], []).append(r)
    def average(group):
        if any(r['status'] != 'complete' or r['metrics'].get(primary_metric) is None for r in group): return None
        return float(np.mean([r['metrics'][primary_metric] for r in group]))
    animal_rows = [{'animal':a,'sessions':[r['session'] for r in g], 'value':average(g)} for a,g in sorted(animals.items())]
    return {'population': rows, 'complete_common_support': complete,
            'equal_session': average(rows), 'animal_rows': animal_rows,
            'equal_animal': float(np.mean([r['value'] for r in animal_rows])) if complete and animal_rows else None,
            'units': 'session and animal, never time bin or neuron as independent replicate'}

def paired_improvement(candidate, reference, expected_order, meaningful_margin):
    """Fixed independent references; candidate-reported own baselines are diagnostic only."""
    if type(meaningful_margin) not in (int,float) or meaningful_margin < 0: raise Refusal('prespecified margin')
    if list(candidate) != list(expected_order) or list(reference) != list(expected_order): raise Refusal('paired full support')
    differences = []
    for key in expected_order:
        c,r = candidate[key],reference[key]
        if c['support'] != r['support'] or c['split'] != r['split'] or c['target'] != r['target']:
            raise Refusal('paired target/split identity')
        if c['status'] != 'complete' or r['status'] != 'complete' or c['value'] is None or r['value'] is None:
            differences.append({'case':key,'difference':None,'status':'unavailable'})
        else: differences.append({'case':key,'difference':c['value']-r['value'],'status':'complete'})
    # No implicitly chosen significance, multiplicity, equivalence or aggregate pass threshold.
    return {'differences':differences,'prespecified_margin':meaningful_margin,
            'qualified_improvement':False, 'reason':'requires measured paired cost and prespecified animal-level inference',
            'candidate_baselines_accepted_as_reference':False}

def read_validated_prediction(store, leaf, target):
    from .interchange import read_array
    import numpy as np
    value=read_array(store,leaf)
    if value.size==0 or not np.isfinite(value).all():raise Refusal('complete finite prediction')
    if target=='choice' and (np.any(value<0) or np.any(value>1)):raise Refusal('binary prediction range')
    return value

def read_selected_truth(prepared, rows):
    from .interchange import read_array
    import numpy as np
    document=prepared.document()
    return read_array(prepared.owner.store,document['y'])[np.asarray(rows,dtype=np.int64)]

def score_after_capture(barrier):
    """Fixed whole sealed census; no caller-supplied captures, cases or truth operands.

    Every prediction tree and numerical prediction is checked before the first
    protected target read. Native isolation still needs its separate real issuer.
    """
    from .publication import ResultBarrier
    if type(barrier) is not ResultBarrier:raise Refusal('actual campaign result barrier')
    if barrier.score_attempted:raise Refusal('scoring already attempted')
    barrier.score_attempted=True
    try:
        trees=barrier.require();operands=[]
        for tree in trees:
            for prepared,pcap,praw,lcap,lraw,lineage in tree.records:
                pdoc=strict_json(praw)
                case=prepared.owner.case(prepared.case_id)
                rows,ids=prepared.query_support()
                prediction=read_validated_prediction(barrier.store,pdoc['prediction'],case.target)
                operands.append((tree,prepared,case,rows,prediction))
        results=[]
        for tree,prepared,case,rows,prediction in operands:
            truth=read_selected_truth(prepared,rows)
            scores=metric(case.target,truth,prediction)
            results.append({'job':tree.job.job_id,'condition':tree.job.condition,
                            'case_id':case.case_id,'session':case.session,'animal':case.animal,
                            'status':'complete','metrics':scores})
        return barrier.store.put_json('scoring/full-case-metrics.private.json',results)
    except BaseException as exc:
        barrier.store.budget.fail('scoring',exc);raise
