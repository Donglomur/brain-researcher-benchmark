"""Explicit complete scientific product identities. No array creation on import."""
from dataclasses import dataclass
from .core import Refusal
from .roster import PARTICIPANTS, CONDITIONS, FIGURES


@dataclass(frozen=True, order=True)
class ProductKey:
    participant: str
    stimulus: str
    pipeline: str
    condition: str
    score: str


def participant_products(participant):
    if participant not in PARTICIPANTS:
        raise Refusal('participant not in declared roster')
    rows = []
    for stimulus in ('sound', 'omission'):
        for pipeline in ('replication', 'empirical_null'):
            for condition in CONDITIONS:
                rows.append(ProductKey(participant, stimulus, pipeline, condition, 'accuracy'))
    for pipeline in ('replication', 'empirical_null'):
        for condition in CONDITIONS[1:]:
            rows.append(ProductKey(participant, 'sound', pipeline, condition, 'most_likely'))
    for condition in CONDITIONS:
        rows.append(ProductKey(participant, 'sound', 'random_oof', condition, 'confusion'))
    for condition in CONDITIONS:
        rows.append(ProductKey(participant, 'sound', 'theoretical_null', condition, 'accuracy'))
    return tuple(rows)


def require_complete_products(products):
    expected = {k for s in PARTICIPANTS for k in participant_products(s)}
    if set(products) != expected:
        raise Refusal('missing, extra, or mismatched scientific product identity')
    return tuple(sorted(expected))


def validate_matrix(array, train_times, test_times, *, confusion=False):
    import numpy as np
    expected = ((5,) if confusion else ()) + (len(train_times), len(test_times)) + ((4, 4) if confusion else ())
    if array.shape != expected or array.dtype.kind not in 'fiu' or not np.isfinite(array).all():
        raise Refusal('scientific product axes/type/finite support')
    if not np.logical_and(array >= 0, array <= 1).all():
        raise Refusal('probability/accuracy outside [0,1]')
    if confusion and not np.allclose(array.sum(axis=-1), 1, atol=1e-10, rtol=0):
        raise Refusal('confusion rows must normalize true class to predicted class')
    for times in (train_times, test_times):
        if times.ndim != 1 or not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
            raise Refusal('actual increasing time axes required')


def require_figures(figures):
    if set(figures) != set(FIGURES):
        raise Refusal('all main and supplementary figure consumers required')


def endpoint_products(endpoint):
    complete = {k for p in PARTICIPANTS for k in participant_products(p)}
    if endpoint == 'complete':
        return complete
    if endpoint == 'empirical_and_most_likely':
        return {k for k in complete if k.pipeline != 'theoretical_null'}
    if endpoint == 'theoretical':
        return {k for k in complete if k.pipeline in ('theoretical_null', 'random_oof')}
    raise Refusal('unselected scientific endpoint; arbitrary subsets are forbidden')


def require_endpoint_products(products, endpoint):
    if set(products) != endpoint_products(endpoint):
        raise Refusal('complete preselected endpoint product set required')
    return tuple(sorted(products))
