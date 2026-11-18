"""Unadmitted, operator-only replay of the source Figure 6B real-label API branch.

No data, estimator, or numerical library is loaded on import. The public entry
requires the existing protected full40 preparation and a separately admitted
outer process. This is a three-statement author-code slice, not a run of the
whole historical script or a scientific qualification of its reported score.
"""
import ast
import copy
import hashlib
import math
from pathlib import Path

from common import TASK, descriptor, need
from prepare import ARCHIVE, SESSION, VERSIONS
from support import validate_prepared

AUTHOR_BYTES = 8776
AUTHOR_SHA256 = 'abfde10a70eec9a8f621909ec9fac37463efceb7bd5b5dbdb5eff37d6fcf4b63'


class ReplayFailure(ValueError):
    """Expose attempted work without returning a partial panel as a result."""
    def __init__(self, message, attempted_fits, completed_sessions):
        super().__init__(message)
        self.attempted_fits = attempted_fits
        self.completed_sessions = completed_sessions


def author_real_branch(source):
    """Extract only the pinned constructor, fit and OOF-probability statements.

    The three AST statements are unchanged. Only their enclosing function and
    an estimator return are added. No imports, argparse, MAT loading, unseeded
    random generator, PFI, or top-level source statements are executed.
    """
    need(type(source) is bytes and len(source) == AUTHOR_BYTES
         and hashlib.sha256(source).hexdigest() == AUTHOR_SHA256,
         'exact retained author classifier source')
    tree = ast.parse(source.decode('utf8'))
    outer = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name == 'EventClassifier']
    need(len(outer) == 1, 'unique source EventClassifier')
    inner = [n for n in outer[0].body if isinstance(n, ast.FunctionDef)
             and n.name == 'fitBNB']
    need(len(inner) == 1, 'unique source fitBNB')
    loops = [n for n in inner[0].body if isinstance(n, ast.For)]
    # The first loop is the source CV loop; later loops summarize PFI.
    need(bool(loops), 'source CV loop')
    loop = loops[0]
    expected = (
        'clf_real = BernoulliNB(fit_prior=False)',
        'clf_real.fit(X_train, y_train)',
        'WholeTestResult[test_index, 2] = clf_real.predict_proba(X_test)[:, 1]',
    )
    wanted = [ast.dump(ast.parse(s).body[0], include_attributes=False) for s in expected]
    selected = []
    positions = []
    for pattern in wanted:
        matches = [(i, n) for i, n in enumerate(loop.body)
                   if ast.dump(n, include_attributes=False) == pattern]
        need(len(matches) == 1, 'unique unchanged author real-label statement')
        positions.append(matches[0][0])
        selected.append(copy.deepcopy(matches[0][1]))
    need(positions == sorted(positions), 'source statement order')
    args = ['X_train', 'y_train', 'X_test', 'WholeTestResult', 'test_index', 'BernoulliNB']
    function = ast.FunctionDef(
        name='_author_real_branch',
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=x) for x in args],
                           kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=selected + [ast.Return(value=ast.Name(id='clf_real', ctx=ast.Load()))],
        decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {'__builtins__': {}}
    exec(compile(module, '<pinned-foraging-author-real-branch>', 'exec'), namespace)
    return namespace['_author_real_branch']


def _source_records(prepared):
    records = validate_prepared(prepared)
    need(descriptor(prepared['archive']) == ARCHIVE, 'original archive identity')
    scientific = [r['name'] for r in prepared['archive_inventory']
                  if r['disposition'] == 'full_original_classification_MAT']
    need(len(scientific) == len(set(scientific)) == 40
         and set(scientific) == {r['source_member'] for r in records},
         'complete original scientific member roster')
    for row in records:
        match = SESSION.fullmatch(Path(row['source_member']).name)
        need(match is not None and match.group(1) == row['source_session_token']
             and hashlib.sha256(row['source_member'].encode()).hexdigest()[:24] == row['session_id'],
             'source member, session token and private session ID join')
        counts = row['source_HW_counts']
        need(type(counts) is dict and set(counts) == {'avoidance', 'escape'}
             and all(type(n) is int and n > 0 for n in counts.values())
             and sum(counts.values()) == row['rows'], 'exact positive source HW class counts')
        need(row['window_seconds'] == [-1, 1] and row['bin_seconds'] == .05
             and type(row['unit_blocks']) is int and row['unit_blocks'] > 0
             and row['features'] == row['unit_blocks'] * 40 and row['clip'] == [-5, 5]
             and row['native_fold_seed'] == 622
             and row['upstream_whole_session_normalized'] is True
             and row['private_row_maps_candidate_visible'] is False,
             'unchanged full-feature retrospective source recipe')
    return records


def _load_adopted_runtime():
    # Matching this construction profile does NOT prove the historical runtime.
    import numpy as np
    import scipy
    import sklearn
    from sklearn.model_selection import StratifiedKFold
    from sklearn.naive_bayes import BernoulliNB
    actual = {'numpy': np.__version__, 'scipy': scipy.__version__,
              'scikit_learn': sklearn.__version__}
    need(actual == VERSIONS, 'exact adopted construction runtime; no version fallback')
    return np, BernoulliNB, StratifiedKFold, actual


def _replay_with_dependencies(prepared, source, loader, tick, runtime,
                              output_numeric_capacity_bytes):
    """Implementation seam for generated spy controls; not a participant API.

    The production wrapper fixes the loader and estimator dependencies. A caller
    of this internal seam cannot turn its report into an admission certificate.
    """
    records = _source_records(prepared)
    need(type(output_numeric_capacity_bytes) is int and output_numeric_capacity_bytes > 0,
         'explicit full-output numerical capacity')
    output_bytes = 8 * sum(r['rows'] for r in records)
    need(output_bytes <= output_numeric_capacity_bytes, 'complete40 output numerical capacity')
    branch = author_real_branch(source)
    np, estimator, splitter, actual_versions = runtime
    summaries, probabilities = {}, {}
    attempted_fits = 0
    try:
        for row in records:
            tick()
            X, y = loader(row)
            need(X.dtype == np.dtype('float64') and X.shape == (row['rows'], row['features'])
                 and y.dtype == np.dtype('int64') and y.shape == (row['rows'],),
                 'complete prepared float64 features and int64 source-order HW labels')
            need(np.isfinite(X).all() and (X >= -5).all() and (X <= 5).all()
                 and np.isin(y, [0, 1]).all(), 'finite clipped source features and binary HW labels')
            counts = [int((y == label).sum()) for label in (0, 1)]
            need(counts == [row['source_HW_counts']['avoidance'], row['source_HW_counts']['escape']]
                 and min(counts) > 0, 'all original HW class counts')
            regenerated = list(splitter(n_splits=5, shuffle=True, random_state=622).split(X, y))
            need(len(regenerated) == 5, 'source fivefold count')
            # Validate every fold before any fit for this session. Match original
            # positions, not participant-only permuted train/query presentation.
            for (train, test), folded in zip(regenerated, row['folds']):
                need(train.tolist() == folded['train_positions0']
                     and test.tolist() == folded['test_positions0'],
                     'canonical seed622 folds match protected original-row membership')
                need(set(y[train].tolist()) == {0, 1}, 'both source classes in every training fold')
            whole = np.zeros((row['rows'], 3), dtype=np.float64)
            whole[:, 2] = np.nan
            for train, test in regenerated:
                tick()
                attempted_fits += 1
                model = branch(X[train], y[train].copy(), X[test], whole, test, estimator)
                need(model.classes_.tolist() == [0, 1], 'source probability column means escape')
                params = model.get_params(deep=False)
                need(params.get('alpha') == 1 and params.get('binarize') == 0
                     and params.get('fit_prior') is False and params.get('class_prior') is None,
                     'source BernoulliNB defaults and uniform prior')
                tick()
            p = whole[:, 2].copy()
            need(np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all(),
                 'one finite escape probability for every original HW row')
            predicted = p >= .5
            confusion = [[int(((y == i) & (predicted == j)).sum()) for j in (0, 1)]
                         for i in (0, 1)]
            recalls = [confusion[i][i] / counts[i] for i in (0, 1)]
            sid = row['session_id']
            probabilities[sid] = p
            summaries[sid] = {'rows': row['rows'], 'class_counts': counts,
                              'confusion_counts': confusion,
                              'avoidance_recall': recalls[0], 'escape_recall': recalls[1],
                              'balanced_accuracy': math.fsum(recalls) / 2,
                              'source_member': row['source_member'], 'fits': 5}
            del X, y, whole, p, model
    except Exception as exc:
        raise ReplayFailure(f'{type(exc).__name__}: {exc}', attempted_fits, len(summaries)) from exc
    need(attempted_fits == 200 and len(summaries) == len(probabilities) == 40,
         'complete200-fit40-session author real-label branch')
    report = {
        'schema': 'foraging_source_api_real_branch_v1', 'task_id': TASK,
        'source_classifier': {'bytes': AUTHOR_BYTES, 'sha256': AUTHOR_SHA256},
        'runtime_versions': actual_versions, 'completed_real_fits': attempted_fits,
        'sessions': summaries, 'output_numeric_bytes': output_bytes,
        'equal_session_balanced_accuracy': math.fsum(
            r['balanced_accuracy'] for r in summaries.values()) / 40,
        'source_scope': 'three unchanged real-label author statements in an operator wrapper',
        'unchanged_whole_script_execution': False, 'historical_environment_equivalence': False,
        'source_shuffle_companions_executed': False, 'permutation_importance_executed': False,
        'source_or_custody_qualification_established': False,
        'paper_reproduced': None, 'paper_win': None, 'improvement_ready': False,
    }
    return report, probabilities


def replay_prepared(prepared, author_source, budget, output_numeric_capacity_bytes):
    """Future operator callable; deliberately not wired to a CLI or auto-run.

    Caller must authenticate this source closure and the complete preparation,
    admit actual runtime/CPU/RAM/deadlines and protect all outputs. Array loading
    reuses authenticated typed transport. Returned arrays remain operator-only.
    Numerical output capacity excludes metadata, workspace and peak memory.
    """
    from array_io import open_array
    runtime = _load_adopted_runtime()
    def loader(row):
        X = open_array(row['prepared']['X.npy'], budget,
                       (row['rows'], row['features']), 'float64')
        y = open_array(row['prepared']['y.npy'], budget, (row['rows'],), 'int64')
        budget.reading(X.nbytes + y.nbytes)
        return X, y
    return _replay_with_dependencies(prepared, author_source, loader, budget.tick,
                                     runtime, output_numeric_capacity_bytes)
