"""Independent numerical graders, invoked only after immutable submission commit."""
from .contracts import require, unique, digest

def check_probabilities(submission, public):
    import math
    require(submission['case_id']==public['case_id'], 'wrong case')
    require(submission['classes']==public['classes'], 'class order')
    require(submission['ids']==public['ids'], 'prediction IDs/order')
    p=submission['probabilities']
    require(len(p)==len(public['ids']), 'prediction count')
    for row in p:
        require(len(row)==len(public['classes']), 'probability width')
        require(all(type(x) in (float,int) and math.isfinite(x) and 0<=x<=1 for x in row), 'probability range')
        require(abs(sum(row)-1)<=1e-8, 'probability simplex')
    return p

def score_prediction(submission, public, private):
    import numpy as np
    p=np.asarray(check_probabilities(submission,public))
    require(private['ids']==public['ids'] and private['case_id']==public['case_id'], 'private/public inverse')
    classes=public['classes']
    y=np.asarray([classes.index(v) for v in private['labels']])
    require(len(y)==len(p), 'private label count')
    pred=p.argmax(axis=1)
    units=[]
    require(len(private['units'])==len(p),'private biological unit count')
    for mouse in sorted(set(private['units'])):
        ix=np.asarray([i==mouse for i in private['units']])
        present=sorted(set(y[ix].tolist()))
        recall=[float(np.mean(pred[ix & (y==c)]==c)) for c in present]
        # Absent test classes are disclosed; do not pretend all-class coverage.
        units.append({'mouse':mouse,'balanced_accuracy':float(np.mean(recall)),
                      'log_loss':float(-np.log(np.maximum(p[np.where(ix)[0],y[ix]],1e-15)).mean()),
                      'observed_classes':[classes[c] for c in present], 'n_trials':int(ix.sum())})
    require(units,'no scoreable mouse')
    from .inference import uncertainty
    intervals={k:uncertainty([r[k] for r in units]) if len(units)>=2 else None
               for k in ('balanced_accuracy','log_loss')}
    return {'mouse_values':units,'balanced_accuracy':float(np.mean([r['balanced_accuracy'] for r in units])),
            'log_loss':float(np.mean([r['log_loss'] for r in units])),
            'claim':public['claim'],'n_mice':len(units),'task':'NEURAL-043','uncertainty':intervals}

def score_prediction_cohort(submissions,public_packets,private_packets):
    """Pool held-out predictions within mouse before recall; never average block scores."""
    require(len(submissions)==len(public_packets)==len(private_packets),'packet inverse')
    groups={}
    for submission,public,private in zip(submissions,public_packets,private_packets):
        check_probabilities(submission,public)
        require(private['ids']==public['ids'],'packet private/public inverse')
        key=(tuple(public['classes']),public['claim'])
        g=groups.setdefault(key,{'ids':[],'probabilities':[],'labels':[],'units':[]})
        for name in ('ids','probabilities'):
            g[name].extend(submission[name])
        g['labels'].extend(private['labels']);g['units'].extend(private['units'])
    results=[]
    for (classes,claim),g in groups.items():
        unique(g['ids'],'cohort held-out trial')
        public={'case_id':'cohort','classes':list(classes),'claim':claim,'ids':g['ids']}
        submission={**public,'probabilities':g['probabilities']}
        private={**public,'labels':g['labels'],'units':g['units']}
        results.append(score_prediction(submission,public,private))
    return {'strata':results,'unlike_class_spaces_pooled':False}

def score_responses(submission,public,private):
    import numpy as np
    require(submission['case_id']==public['case_id'] and submission['ids']==public['ids']==private['ids'],'response IDs')
    unique(public['ids'],'held-response identity')
    p=np.asarray(submission['responses'],dtype=float);y=np.asarray(private['responses'],dtype=float)
    require(p.shape==y.shape==(len(public['ids']),) and np.isfinite(p).all(),'response shape/finite')
    return {'mse':float(np.mean((p-y)**2)),'unit':private['units'][0],
            'task':'NEURAL-044','claim':'held_mouse_response_prediction'}

def grade_investigation(submission, recomputed, tolerances):
    import math
    require(submission['task']=='NEURAL-044', 'wrong investigation')
    require(submission['estimand']=='conditional_tuning_response_association', 'unsupported estimand/causal claim')
    require(submission['source_digest']==recomputed['source_digest'], 'source binding')
    reported=submission['mouse_values']; expected=recomputed['mouse_values']
    unique([x['mouse'] for x in reported], 'reported mouse')
    require({x['mouse'] for x in reported}=={x['mouse'] for x in expected}, 'mouse reporting omission')
    found={x['mouse']:x for x in reported}; errors=[]
    for row in expected:
        got=found[row['mouse']]
        for field in ('effect','improvement'):
            if row[field] is None:
                require(got[field] is None, 'fabricated estimable result')
                continue
            value=got[field]
            require(type(value) in (float,int) and math.isfinite(value), 'nonfinite claim')
            error=abs(value-row[field])
            require(error<=tolerances['absolute']+tolerances['relative']*abs(row[field]), 'numerical claim differs')
            errors.append(error)
    require(submission['disposition_digest']==recomputed['disposition_digest'], 'selection/exclusion mismatch')
    require(set(submission['controls'])==set(recomputed['controls']), 'missing control family')
    def compare(got,want):
        if type(want) in (int,float):
            require(type(got) in (int,float) and math.isfinite(got),'invalid numerical control')
            require(abs(got-want)<=tolerances['absolute']+tolerances['relative']*abs(want),'control numerical claim differs')
        elif isinstance(want,dict):
            require(isinstance(got,dict) and set(got)==set(want),'control fields')
            for k in want:compare(got[k],want[k])
        elif isinstance(want,list):
            require(isinstance(got,list) and len(got)==len(want),'control extent')
            for a,b in zip(got,want):compare(a,b)
        else:require(type(got) is type(want) and got==want,'control disposition differs')
    compare(submission['control_results'],recomputed['control_results'])
    require(submission['interpretation'] in ('positive','negative','null','inconclusive'), 'missing interpretation')
    # Agreement with a preferred sign or biological story is never rewarded.
    return {'task':'NEURAL-044','numerical_reproduction_pass':True,
            'max_absolute_error':max(errors,default=0),'n_mice':len(expected),
            'interpretation_scored':False,'scientific_qualification':False}
