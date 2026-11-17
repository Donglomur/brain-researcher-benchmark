"""Future validation-only L2 baseline; no test labels accepted by this API."""
import numpy as np

def fit_predict(train_x,train_y,validation_x,validation_y,query_x,kind):
    from sklearn.linear_model import Ridge,LogisticRegression
    tr=train_x.reshape(len(train_x),-1);va=validation_x.reshape(len(validation_x),-1);qu=query_x.reshape(len(query_x),-1)
    best=None;bestloss=float('inf');beststrength=None
    for strength in [10.**k for k in range(-4,5)]:
        # Parameterizations explicitly differ: C is inverse regularization for
        # logistic regression; alpha is direct strength for ridge.
        if kind=='binary':
            if set(np.unique(train_y))!={0.,1.}:raise ValueError('both classes required for logistic fit')
            m=LogisticRegression(C=strength,max_iter=10000,solver='lbfgs',random_state=0).fit(tr,train_y[:,0])
            p=m.predict_proba(va)[:,list(m.classes_).index(1.)];p=np.clip(p,1e-15,1-1e-15);y=validation_y[:,0]
            loss=float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p)))
        else:
            m=Ridge(alpha=strength).fit(tr,train_y);loss=float(np.mean((m.predict(va)-validation_y)**2))
        if np.isfinite(loss) and loss<bestloss:best=m;bestloss=loss;beststrength=strength
    if best is None:raise ArithmeticError('no finite validation baseline')
    p=best.predict_proba(qu)[:,list(best.classes_).index(1.)][:,None] if kind=='binary' else best.predict(qu)
    return p,{'selected_strength':beststrength,'selection':'validation_loss','prospective_not_original_GridSearchCV':True}
