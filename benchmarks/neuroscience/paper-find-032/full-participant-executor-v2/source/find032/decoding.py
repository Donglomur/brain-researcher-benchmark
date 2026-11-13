"""Actual LDA temporal-generalization definitions; never invoked during BUILD."""
from dataclasses import dataclass
from .core import Refusal
from .support import purge_training, require_disjoint


@dataclass(frozen=True)
class EpochSet:
    data: object
    labels: object
    times: object
    supports: tuple
    event_indices: tuple


def validate_epochs(epochs):
    import numpy as np
    if epochs.data.ndim != 3 or epochs.data.shape[0] != len(epochs.labels):
        raise Refusal('trial/channel/time axes')
    if epochs.data.shape[2] != len(epochs.times) or not epochs.data.shape[1]:
        raise Refusal('channel/time extent')
    if len(epochs.supports) != len(epochs.labels) or len(epochs.event_indices) != len(epochs.labels):
        raise Refusal('epoch/source support join')
    if not np.isfinite(epochs.data).all() or not np.isfinite(epochs.times).all():
        raise Refusal('nonfinite MEG or time data')
    if not set(epochs.labels.tolist()).issubset({1, 2, 3, 4}):
        raise Refusal('four-class labels required')


def fit_generalize(train, train_ids, tests, *, operation):
    """Fit each training time once; all supplied test routes share those exact fits.

    operation is the caller's existing scientific-operation context manager, not
    a source of native facts. The complete deployment must enforce that context.
    """
    import numpy as np
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.metrics import confusion_matrix
    validate_epochs(train)
    if set(train.labels[list(train_ids)].tolist()) != {1, 2, 3, 4}:
        raise Refusal('purged training support lacks a class')
    outputs = {}
    for name, (test, test_ids, labels) in tests.items():
        validate_epochs(test)
        if not test_ids or len(test_ids) != len(labels):
            raise Refusal('empty/misaligned fixed evaluation support')
        if set(labels.tolist()) != {1, 2, 3, 4}:
            raise Refusal('fixed evaluation support lacks a required class')
        require_disjoint(train_ids, train.supports, [test.supports[i] for i in test_ids])
        outputs[name] = {
            'correct': np.zeros((len(train.times), len(test.times)), dtype=np.int64),
            'count': len(test_ids),
            'confusion_counts': np.zeros((len(train.times), len(test.times), 4, 4), dtype=np.int64),
        }
    for ti in range(len(train.times)):
        with operation('lda-fit', {'train_time_index': ti, 'train_trials': len(train_ids)}):
            model = LinearDiscriminantAnalysis()
            model.fit(train.data[list(train_ids), :, ti], train.labels[list(train_ids)])
        cache = {}
        for name, (test, test_ids, labels) in tests.items():
            identity = (id(test), tuple(test_ids))
            if identity not in cache:
                with operation('lda-predict', {'route': name, 'train_time_index': ti,
                                               'test_times': len(test.times), 'test_trials': len(test_ids)}):
                    # LDA is time-independent once fitted. Batch the exact same
                    # channel vectors; this changes call overhead, not the model
                    # or scientific support. Keep every trial/time prediction.
                    vectors = test.data[list(test_ids)].transpose(0, 2, 1).reshape(-1, test.data.shape[1])
                    cache[identity] = model.predict(vectors).reshape(len(test_ids), len(test.times))
            predicted = cache[identity]
            for tj in range(len(test.times)):
                prediction = predicted[:, tj]
                outputs[name]['correct'][ti, tj] = np.count_nonzero(prediction == labels)
                outputs[name]['confusion_counts'][ti, tj] = confusion_matrix(labels, prediction, labels=[1, 2, 3, 4])
    return outputs


def cross_validate(train, tests, *, splits, operation):
    """Use the fixed fold test indices, then purge training by actual sample origin.

    Caller has already equalized matched trial support before splitting. No test
    sample or participant is removed to rescue a failed fit.
    """
    import numpy as np
    folds = []
    observed = []
    for fold, (train_ids, test_by_name) in enumerate(splits):
        train_ids = tuple(int(i) for i in train_ids)
        if not train_ids or set(test_by_name) != set(tests):
            raise Refusal('invalid fixed fold plan')
        branch = {}
        test_supports = []
        for name, (test, labels) in tests.items():
            test_ids = tuple(int(i) for i in test_by_name[name])
            if not test_ids or len(set(test_ids)) != len(test_ids):
                raise Refusal('empty/duplicate fixed test fold')
            if len(test.labels) != len(train.labels) or len(labels) != len(test.labels):
                raise Refusal('matched cross-condition fold denominator')
            branch[name] = (test, test_ids, labels[list(test_ids)])
            test_supports.extend(test.supports[i] for i in test_ids)
        purged = purge_training(train_ids, train.supports, test_supports)
        result = fit_generalize(train, purged, branch, operation=operation)
        folds.append(result)
        observed.append({'fold': fold, 'train': train_ids, 'purged_train': purged,
                         'test': {name: tuple(int(i) for i in test_by_name[name]) for name in tests}})
    for name, (test, _) in tests.items():
        flattened = [i for row in observed for i in row['test'][name]]
        if len(flattened) != len(test.labels) or set(flattened) != set(range(len(test.labels))):
            raise Refusal('fold test support must cover each selected event exactly once')
    products = {}
    for name in tests:
        # Preserve the paper's equal-fold mean accuracy. A separate summed-count
        # product records unequal fold denominators rather than concealing them.
        accuracies = [f[name]['correct'] / f[name]['count'] for f in folds]
        counts = np.stack([f[name]['confusion_counts'] for f in folds])
        denominators = counts.sum(axis=-1, keepdims=True)
        if (denominators == 0).any():
            raise Refusal('an out-of-fold confusion row lacks true-class support')
        products[name] = {'accuracy': np.stack(accuracies).mean(axis=0),
                          'confusion': (counts / denominators).mean(axis=0),
                          'fold_confusion': counts / denominators,
                          'fold_counts': counts, 'support': observed}
    return products


def stratified_plan(train, tests):
    from sklearn.model_selection import StratifiedKFold
    import numpy as np
    split = StratifiedKFold(n_splits=5, shuffle=False)
    def folds(epoch_set):
        if any(np.count_nonzero(epoch_set.labels == label) < 5 for label in (1, 2, 3, 4)):
            raise Refusal('five-fold stratification lacks complete class support')
        return tuple(split.split(epoch_set.data, epoch_set.labels))
    training = folds(train)
    testing = {name: folds(test) for name, (test, _) in tests.items()}
    return tuple((training[i][0], {name: plan[i][1] for name, plan in testing.items()})
                 for i in range(5))


def omission_generalize(train, tests, *, operation):
    test_supports = []
    branch = {}
    for name, test in tests.items():
        ids = tuple(range(len(test.labels)))
        branch[name] = (test, ids, test.labels)
        test_supports.extend(test.supports)
    ids = purge_training(tuple(range(len(train.labels))), train.supports, test_supports)
    outputs = fit_generalize(train, ids, branch, operation=operation)
    return {name: {'accuracy': row['correct'] / row['count'],
                   'test_count': row['count'], 'training_indices': ids}
            for name, row in outputs.items()}
