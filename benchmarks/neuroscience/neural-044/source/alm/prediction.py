"""Train-only deterministic references. The estimator never sees held-out labels."""
from .contracts import require
from .splits import validate_fold

def design(rows, indices, kind, classes):
    import numpy as np
    require(kind in ('neural','history_time','neural_history_time'), 'design kind')
    output = []
    for i in indices:
        r = rows[i]
        nuisance = [r['time'], r['previous_reward'], r['history_speed']]
        nuisance += [int(r['previous_direction']==c) for c in classes]
        v = list(r['x']) if kind != 'history_time' else []
        if kind != 'neural':
            v += nuisance
        output.append(v)
    x = np.asarray(output, dtype=float)
    require(np.isfinite(x).all(), 'nonfinite feature design')
    return x

def fit_reference(rows, fold, kind, c_value):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    classes = validate_fold(rows, fold)
    train, test = fold['train'], fold['test']
    labels = [classes.index(rows[i]['y']) for i in train]
    if kind == 'class_prior':
        counts = np.bincount(labels, minlength=len(classes)) + 1
        return np.tile(counts / counts.sum(), (len(test), 1))
    x = design(rows, train, kind, classes)
    q = design(rows, test, kind, classes)
    # Fixed C is a preregistered reference, not selected on held-out accuracy.
    model = make_pipeline(StandardScaler(), LogisticRegression(C=c_value,
                          solver='lbfgs', max_iter=2000, class_weight='balanced'))
    model.fit(x, labels)
    require(np.all(model[-1].n_iter_ < 2000), 'reference did not converge')
    require(model[-1].classes_.tolist() == list(range(len(classes))), 'reference class order')
    return model.predict_proba(q)

def reference_predictions(rows, folds, c_value):
    from .contracts import Refusal
    outputs, dispositions = [], []
    for fold in folds:
        try:
            validate_fold(rows, fold)
        except Refusal as error:
            dispositions.append({'fold':fold['id'], 'status':'not_estimable', 'reason':str(error)})
            continue
        for kind in ('class_prior','history_time','neural','neural_history_time'):
            probability = fit_reference(rows, fold, kind, c_value)
            outputs.append({'fold':fold['id'], 'reference':kind,
                            'ids': [[rows[i]['mouse'],rows[i]['session'],rows[i]['trial_id']] for i in fold['test']],
                            'classes':rows[fold['test'][0]]['classes'], 'probabilities':probability.tolist()})
        from .controls import block_label_rotation
        null_rows=block_label_rotation(rows,fold['train'])
        null_probability=fit_reference(null_rows,fold,'neural',c_value)
        outputs.append({'fold':fold['id'],'reference':'whole_block_label_rotation',
                        'ids':[[rows[i]['mouse'],rows[i]['session'],rows[i]['trial_id']] for i in fold['test']],
                        'classes':rows[fold['test'][0]]['classes'],'probabilities':null_probability.tolist()})
        dispositions.append({'fold':fold['id'], 'status':'predicted'})
    return outputs, dispositions
