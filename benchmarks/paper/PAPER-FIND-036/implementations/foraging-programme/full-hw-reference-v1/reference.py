"""Complete HW reference component; no data or numerical imports on import.

The current real-label component remains unchanged. This separate source slice
adds the author's training-label shuffle and numeric fitted-state audit. It is
not the whole author script, a historical RNG replay, or scientific admission.
"""
import ast
import copy
import hashlib
import math

import author_replay as prior
from common import TASK, need

SCHEMA = 'foraging_full_hw_reference_v1'
RNG_SCHEMA = 'foraging_prospective_hw_rng_v1'
STATE_SCHEMA = 'foraging_fitted_bnb_state_v1'
AUDIT_ATOL = 1e-12  # Numerical state roundtrip only, never a paper criterion.


class ReferenceFailure(ValueError):
    def __init__(self, message, counts, completed_sessions):
        super().__init__(message)
        self.fit_counts = dict(counts)
        self.completed_sessions = completed_sessions


def author_hw_branch(source):
    """Retain the exact pinned shuffle/fit/predict AST statements, with counters.

    Imports, other classification branches, PFI and top-level execution are
    excluded. The added callbacks only record fit attempts/completions.
    """
    need(type(source) is bytes and len(source) == prior.AUTHOR_BYTES
         and hashlib.sha256(source).hexdigest() == prior.AUTHOR_SHA256,
         'exact retained author classifier source')
    tree = ast.parse(source.decode('utf8'))
    outer = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == 'EventClassifier']
    need(len(outer) == 1, 'unique source EventClassifier')
    inner = [n for n in outer[0].body if isinstance(n, ast.FunctionDef)
             and n.name == 'fitBNB']
    need(len(inner) == 1, 'unique source fitBNB')
    loops = [n for n in inner[0].body if isinstance(n, ast.For)]
    need(bool(loops), 'source CV loop')
    expected = [
        'y_train_shuffle = y[train_index].copy()',
        'rng.shuffle(y_train_shuffle)',
        'clf_real = BernoulliNB(fit_prior=False)',
        'clf_real.fit(X_train, y_train)',
        'clf_fake = BernoulliNB(fit_prior=False)',
        'clf_fake.fit(X_train, y_train_shuffle)',
        'WholeTestResult[test_index, 0] = y_test',
        'WholeTestResult[test_index, 1] = clf_fake.predict_proba(X_test)[:, 1]',
        'WholeTestResult[test_index, 2] = clf_real.predict_proba(X_test)[:, 1]',
    ]
    selected, positions = [], []
    for statement in expected:
        pattern = ast.dump(ast.parse(statement).body[0], include_attributes=False)
        matches = [(i, n) for i, n in enumerate(loops[0].body)
                   if ast.dump(n, include_attributes=False) == pattern]
        need(len(matches) == 1, 'unique unchanged author HW statement')
        positions.append(matches[0][0])
        role = 'real' if statement.startswith('clf_real.fit') else (
            'shuffle' if statement.startswith('clf_fake.fit') else None)
        if role:
            selected.append(ast.parse(f"count('{role}', 'attempted')").body[0])
        selected.append(copy.deepcopy(matches[0][1]))
        if role:
            selected.append(ast.parse(f"count('{role}', 'completed')").body[0])
    need(positions == sorted(positions), 'source statement order')
    args = ['X_train', 'y_train', 'X_test', 'y_test', 'y', 'train_index',
            'WholeTestResult', 'test_index', 'BernoulliNB', 'rng', 'count']
    function = ast.FunctionDef(
        name='_author_hw',
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=x) for x in args],
                           kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=selected + [ast.parse('return clf_real, clf_fake, y_train_shuffle').body[0]],
        decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    scope = {'__builtins__': {}}
    exec(compile(module, '<pinned-foraging-HW-branch>', 'exec'), scope)
    return scope['_author_hw']


def validate_rng(spec):
    need(type(spec) is dict and set(spec) == {'schema', 'seed', 'bit_generator', 'stream'}
         and spec['schema'] == RNG_SCHEMA and spec['bit_generator'] == 'PCG64'
         and spec['stream'] == 'source-member-sorted-HW-only'
         and type(spec['seed']) is int and 0 <= spec['seed'] < 2**128,
         'explicit prospective PCG64 HW seed and stream')


class _RecordedShuffle:
    def __init__(self, np, spec):
        validate_rng(spec)
        self.np = np
        self.rng = np.random.default_rng(spec['seed'])
        need(type(self.rng.bit_generator).__name__ == 'PCG64',
             'source default_rng must use the selected PCG64 algorithm')
        self.initial = copy.deepcopy(self.rng.bit_generator.state)
        self.last = None
        self.calls = 0

    def shuffle(self, values):
        np = self.np
        need(values.dtype == np.dtype('int64') and values.ndim == 1,
             'source training-label shuffle dtype')
        before = copy.deepcopy(self.rng.bit_generator.state)
        original = values.copy()
        # This is the source operation, using the one selected global HW stream.
        self.rng.shuffle(values)
        after = copy.deepcopy(self.rng.bit_generator.state)
        # Audit the same draw on indices without advancing the production stream.
        clone = np.random.Generator(np.random.PCG64(0))
        clone.bit_generator.state = copy.deepcopy(before)
        permutation = np.arange(len(values), dtype=np.int64)
        clone.shuffle(permutation)
        need(clone.bit_generator.state == after
             and np.array_equal(values, original[permutation]),
             'recorded source training permutation agrees with actual shuffle')
        self.last = {'before': before, 'after': after,
                     'training_permutation0': permutation.tolist()}
        self.calls += 1


def _state(np, model, X_train, y_train):
    """Serialize sufficient fitted state as numbers only; no pickle or code."""
    params = model.get_params(deep=False)
    need(params.get('alpha') == 1 and params.get('binarize') == 0
         and params.get('fit_prior') is False and params.get('class_prior') is None,
         'source BernoulliNB defaults and uniform prior')
    need(model.classes_.tolist() == [0, 1]
         and int(model.n_features_in_) == X_train.shape[1], 'fitted classes/features')
    counts = np.asarray(model.class_count_)
    ones = np.asarray(model.feature_count_)
    lp = np.asarray(model.feature_log_prob_)
    priors = np.asarray(model.class_log_prior_)
    d = X_train.shape[1]
    for array, shape in ((counts, (2,)), (ones, (2, d)), (lp, (2, d)), (priors, (2,))):
        need(array.dtype == np.dtype('float64') and array.shape == shape
             and np.isfinite(array).all(), 'complete finite float64 fitted state')
    expected_counts = np.array([(y_train == c).sum() for c in (0, 1)], dtype=np.float64)
    expected_ones = np.stack([(X_train[y_train == c] > 0).sum(axis=0, dtype=np.float64)
                              for c in (0, 1)])
    expected_lp = np.log(expected_ones + 1) - np.log(expected_counts[:, None] + 2)
    need(np.array_equal(counts, expected_counts) and np.array_equal(ones, expected_ones)
         and np.allclose(lp, expected_lp, rtol=0, atol=AUDIT_ATOL)
         and np.allclose(priors, [-math.log(2)] * 2, rtol=0, atol=AUDIT_ATOL),
         'trained state must agree with actual permitted training rows and source equations')
    return {'schema': STATE_SCHEMA, 'classes': [0, 1], 'n_features': int(d),
            'parameters': {'alpha': 1.0, 'binarize': 0.0, 'fit_prior': False,
                           'class_prior': None},
            'class_count': counts.tolist(), 'feature_count': ones.tolist(),
            'feature_log_prob': lp.tolist(), 'class_log_prior': priors.tolist()}


def predict_state(np, state, X):
    """Recompute from admitted numeric state; caller must bound any file input."""
    need(type(state) is dict and set(state) == {
        'schema', 'classes', 'n_features', 'parameters', 'class_count',
        'feature_count', 'feature_log_prob', 'class_log_prior'}, 'exact fitted-state keys')
    need(state['schema'] == STATE_SCHEMA and state['classes'] == [0, 1]
         and type(state['n_features']) is int and state['n_features'] > 0
         and state['parameters'] == {'alpha': 1.0, 'binarize': 0.0,
                                    'fit_prior': False, 'class_prior': None},
         'source state semantics')
    d = state['n_features']
    need(X.dtype == np.dtype('float64') and X.ndim == 2 and X.shape[1] == d
         and np.isfinite(X).all() and (X >= -5).all() and (X <= 5).all(),
         'complete source query features for state audit')
    counts = np.asarray(state['class_count'], dtype=np.float64)
    ones = np.asarray(state['feature_count'], dtype=np.float64)
    lp = np.asarray(state['feature_log_prob'], dtype=np.float64)
    priors = np.asarray(state['class_log_prior'], dtype=np.float64)
    need(counts.shape == (2,) and ones.shape == lp.shape == (2, d)
         and priors.shape == (2,) and all(np.isfinite(a).all() for a in (counts, ones, lp, priors))
         and (counts > 0).all() and (ones >= 0).all() and (ones <= counts[:, None]).all()
         and np.equal(counts, np.floor(counts)).all() and np.equal(ones, np.floor(ones)).all(),
         'numeric fitted-state dimensions and integer sufficient counts')
    need(np.allclose(lp, np.log(ones + 1) - np.log(counts[:, None] + 2), rtol=0, atol=AUDIT_ATOL)
         and np.allclose(priors, [-math.log(2)] * 2, rtol=0, atol=AUDIT_ATOL),
         'numeric fitted-state equations')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        neg = np.log1p(-np.exp(lp))
        joint = (X > 0).astype(np.float64) @ (lp - neg).T + neg.sum(axis=1) + priors
        p = np.exp(joint[:, 1] - np.logaddexp(joint[:, 0], joint[:, 1]))
    need(np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all(), 'finite state predictions')
    return p


def _with_dependencies(prepared, source, loader, tick, runtime, capacity, rng_spec, capture):
    """Generated-control seam; production wrapper fixes loader/runtime."""
    records = sorted(prior._source_records(prepared), key=lambda row: row['source_member'])
    need(type(capacity) is int and capacity > 0
         and 16 * sum(row['rows'] for row in records) <= capacity,
         'complete real-and-shuffle numerical capacity')
    need(callable(capture), 'required complete trained-state capture')
    branch = author_hw_branch(source)
    validate_rng(rng_spec)
    np, estimator, splitter, versions = runtime
    rng = _RecordedShuffle(np, rng_spec)
    counts = {f'{role}_{event}': 0 for role in ('real', 'shuffle')
              for event in ('attempted', 'completed')}
    def count(role, event):
        if event == 'attempted':
            tick()
        counts[f'{role}_{event}'] += 1
        if event == 'completed':
            # The fit has returned successfully: retain that known work even
            # when the deadline check immediately afterwards refuses progress.
            tick()
    summaries, probabilities, audit_pins = {}, {}, []
    try:
        for row in records:
            tick()
            X, y = loader(row)
            need(X.dtype == np.dtype('float64') and X.shape == (row['rows'], row['features'])
                 and y.dtype == np.dtype('int64') and y.shape == (row['rows'],),
                 'complete source float64 features and int64 labels')
            need(np.isfinite(X).all() and (X >= -5).all() and (X <= 5).all()
                 and np.isin(y, [0, 1]).all(), 'finite clipped source features and binary labels')
            class_counts = [int((y == c).sum()) for c in (0, 1)]
            need(class_counts == [row['source_HW_counts'][k] for k in ('avoidance', 'escape')],
                 'complete actual source class counts')
            folds = list(splitter(n_splits=5, shuffle=True, random_state=622).split(X, y))
            need(len(folds) == 5, 'source fivefold count')
            for (train, test), declared in zip(folds, row['folds']):
                need(train.tolist() == declared['train_positions0']
                     and test.tolist() == declared['test_positions0']
                     and set(y[train].tolist()) == {0, 1}, 'canonical source-order seed622 folds')
            whole = np.full((row['rows'], 3), np.nan, dtype=np.float64)
            sid = row['session_id']
            for index, (train, test) in enumerate(folds, 1):
                tick()
                train_x, train_y, test_x = X[train], y[train].copy(), X[test]
                real, shuffled, shuffled_y = branch(
                    train_x, train_y, test_x, y[test], y, train,
                    whole, test, estimator, rng, count)
                models = {'real': _state(np, real, train_x, train_y),
                          'shuffle': _state(np, shuffled, train_x, shuffled_y)}
                for role, column in (('real', 2), ('shuffle', 1)):
                    need(np.allclose(predict_state(np, models[role], test_x),
                                     whole[test, column], rtol=0, atol=AUDIT_ATOL),
                         'fitted-state roundtrip agrees with source predictions')
                audit = {'schema': 'foraging_hw_fold_audit_v1', 'session_id': sid,
                         'fold': index, 'source_member': row['source_member'],
                         'train_positions0': train.tolist(), 'test_positions0': test.tolist(),
                         'rng': copy.deepcopy(rng.last), 'models': models}
                pin = capture(audit)
                need(type(pin) is dict and type(pin.get('bytes')) is int and pin['bytes'] > 0
                     and type(pin.get('sha256')) is str and len(pin['sha256']) == 64
                     and all(c in '0123456789abcdef' for c in pin['sha256']),
                     'captured fold audit descriptor')
                audit_pins.append({'session_id': sid, 'fold': index, **pin})
                tick()
            need(np.array_equal(whole[:, 0], y) and np.isfinite(whole).all()
                 and (whole[:, 1:] >= 0).all() and (whole[:, 1:] <= 1).all(),
                 'complete real/shuffle OOF coverage with original query labels')
            scores = {}
            for role, column in (('real', 2), ('shuffle', 1)):
                p = whole[:, column].copy()
                pred = p >= .5
                confusion = [[int(((y == a) & (pred == b)).sum()) for b in (0, 1)] for a in (0, 1)]
                recalls = [confusion[c][c] / class_counts[c] for c in (0, 1)]
                scores[role] = {'confusion_counts': confusion, 'class_recalls': recalls,
                                'balanced_accuracy': math.fsum(recalls) / 2}
                probabilities[(sid, role)] = p
            summaries[sid] = {'source_member': row['source_member'], 'rows': row['rows'],
                              'class_counts': class_counts, **scores}
            del X, y, whole, real, shuffled, train_x, test_x, models, audit
    except Exception as exc:
        raise ReferenceFailure(f'{type(exc).__name__}: {exc}', counts, len(summaries)) from exc
    need(all(n == 200 for n in counts.values()) and len(summaries) == 40
         and len(probabilities) == 80 and len(audit_pins) == rng.calls == 200,
         'complete400-fit40-session HW reference')
    report = {'schema': SCHEMA, 'task_id': TASK, 'fit_counts': counts, 'sessions': summaries,
              'model_audits': audit_pins, 'source_order': [r['source_member'] for r in records],
              'rng': {'selection': copy.deepcopy(rng_spec), 'initial_state': rng.initial,
                      'final_state': copy.deepcopy(rng.rng.bit_generator.state), 'shuffle_calls': rng.calls},
              'runtime_versions': versions, 'source_classifier': {
                  'bytes': prior.AUTHOR_BYTES, 'sha256': prior.AUTHOR_SHA256},
              'output_numeric_bytes': 16 * sum(r['rows'] for r in records),
              'equal_session_balanced_accuracy': {role: math.fsum(
                  s[role]['balanced_accuracy'] for s in summaries.values()) / 40 for role in ('real', 'shuffle')},
              'state_audit_absolute_tolerance': AUDIT_ATOL,
              'source_shuffle_companions_executed': True,
              'historical_shuffle_realization_reproduced': False,
              'unchanged_whole_script_execution': False, 'historical_environment_equivalence': False,
              'paper_reproduced': None, 'paper_win': None, 'improvement_ready': False}
    return report, probabilities


def replay_prepared(prepared, source, budget, capacity, rng_spec, capture):
    """Operator-only callable; actual inputs and outer runtime require admission."""
    from array_io import open_array
    runtime = prior._load_adopted_runtime()
    def loader(row):
        X = open_array(row['prepared']['X.npy'], budget, (row['rows'], row['features']), 'float64')
        y = open_array(row['prepared']['y.npy'], budget, (row['rows'],), 'int64')
        budget.reading(X.nbytes + y.nbytes)
        return X, y
    return _with_dependencies(prepared, source, loader, budget.tick, runtime,
                              capacity, rng_spec, capture)
