"""Frozen original author estimator; operator calibration, never an AI arm.

Package these exact bytes as the sole candidate.py of the reference programme.
The existing participant entry supplies only this held-qid's permitted labels.
Every real invocation requires fresh exec; no state or job-level reuse.
"""

HISTORICAL = {'numpy': '1.24.3', 'sklearn': '1.2.2', 'scipy': '1.10.1'}


def predict(train_x, train_y, query_x, context):
    import numpy
    import sklearn
    import scipy
    if {name: value.__version__ for name, value in
        (('numpy', numpy), ('sklearn', sklearn), ('scipy', scipy))} != HISTORICAL:
        raise ValueError('Exact historical author numerical stack required')
    from sklearn.linear_model import Ridge
    estimator = Ridge(alpha=0.01)
    estimator.fit(train_x, train_y)
    return estimator.predict(query_x)
