"""Source FC + public fit certificate + own-score arithmetic, without answer labels."""
import hashlib
import os
from pathlib import Path
import numpy as np
import io_contract as io
import metric_contract as m
import source_reference as source


def load_reference():
    return source.load_reference(os.environ.get('EYESTATE_DATA_DIR', '/app/data/eyestate'),
                                 os.environ.get('EYESTATE_METHOD_CONTRACT', '/app/method_contract.json'))


def read_npz(path, required):
    with np.load(io.regular(path), allow_pickle=False) as archive:
        m.require(len(archive.files) == len(set(archive.files)) and set(required) <= set(archive.files), 'NPZ required unique arrays')
        arrays = {k: archive[k] for k in archive.files}
    m.require(all(not a.dtype.hasobject for a in arrays.values()), 'NPZ object/pickle forbidden')
    return arrays


def ordering(axis, expected):
    axis = io.axis(axis); expected = np.asarray(expected)
    m.require(set(map(int, axis)) == set(map(int, expected)), 'complete exact source axis')
    positions = {int(k): i for i, k in enumerate(axis)}
    return [positions[int(k)] for k in expected]


def finite_array(array, shape, name):
    m.require(array.dtype.kind in 'iuf' and array.shape == shape and np.isfinite(array).all(), name + ': finite real shape')
    return np.asarray(array, dtype=np.float64)


def validate_features(path, ref):
    required = ref['method']['artifacts']['features.npz']['arrays']
    a = read_npz(path, required); n, f = ref['features'].shape
    rows = ordering(a['phenotype_row'], ref['row_ids']); cols = ordering(a['feature_index'], np.arange(f))
    m.require(np.array_equal(io.axis(a['subject_id'])[rows], ref['subject_ids']), 'source subject identity')
    # ROI endpoints are not unique axes individually; repeated endpoint indices are expected.
    for name, expected in zip(('roi_i', 'roi_j'), np.tril_indices(200, -1)):
        values = a[name]
        m.require(values.ndim == 1 and len(values) == f and values.dtype.kind in 'iuf', 'ROI edge endpoint shape/type')
        parsed = [io.integer(v) for v in values]
        m.require([parsed[i] for i in cols] == list(expected), 'source edge identities')
    x = finite_array(a['correlation'], (n, f), 'FC')[np.ix_(rows, cols)]
    shrinkage = finite_array(a['shrinkage'], (n,), 'shrinkage')[rows]
    m.require(np.all(np.abs(x) <= 1 + 1e-12) and np.all((shrinkage >= 0) & (shrinkage <= 1)), 'feature natural domain')
    tol = ref['method']['tolerances_proposed_before_values']
    io.close(x, ref['features'], **tol['feature'], name='source FC')
    io.close(shrinkage, ref['shrinkage'], **tol['shrinkage'], name='source shrinkage')


def validate_cohort(path, ref):
    columns = ref['method']['artifacts']['cohort.csv']['columns']
    rows = io.index_rows(io.csv_rows(path, columns), ('phenotype_row',), ('phenotype_row',))
    m.require(set(rows) == {(r['phenotype_row'],) for r in ref['cohort']}, 'complete original phenotype ledger')
    for expected in ref['cohort']:
        io.row_match(rows[(expected['phenotype_row'],)], expected)


def _strings(values, name):
    m.require(values.ndim == 1 and values.dtype.kind in 'US', name + ': string vector')
    return [v.decode('utf-8') if isinstance(v, bytes) else str(v) for v in values]


def _model_certificate(ref, fold, coefficient, intercept):
    # Only exact submitted parameter content on this immutable source/fold basis
    # is cached. A claimed path, result, status or solver name cannot hit this cache.
    digest = hashlib.sha256(coefficient.astype('<f8').tobytes() + np.array([intercept], dtype='<f8').tobytes()).hexdigest()
    key = (source.METHOD_SHA256, source.SOURCE_SHA256, fold['scheme'], fold['fold_id'], digest)
    cache = ref.setdefault('_certificate_cache', {})
    if key not in cache:
        scaler = ref['scalers'][(fold['scheme'], fold['fold_id'])]
        train = (ref['features'][fold['train']] - scaler['mean']) / scaler['scale']
        certificate = m.fit_certificate(train, ref['labels'][fold['train']], coefficient, intercept)
        m.require(certificate['certificate_gap'] <= certificate['certificate_limit'], 'public objective certificate failed')
        test = (ref['features'][fold['test']] - scaler['mean']) / scaler['scale']
        score = test @ coefficient + intercept
        m.require(np.isfinite(score).all(), 'finite replayed decision')
        score.setflags(write=False)
        if len(cache) >= 256: cache.pop(next(iter(cache)))
        cache[key] = certificate, score
    return cache[key]


def validate_models(path, ref):
    a = read_npz(path, ref['method']['artifacts']['fold_models.npz']['arrays'])
    scheme = _strings(a['scheme'], 'model scheme'); ids = a['fold_id']
    m.require(ids.ndim == 1 and ids.dtype.kind in 'iuf' and len(ids) == len(scheme), 'model fold axis')
    keys = [(s, io.integer(i)) for s, i in zip(scheme, ids)]
    m.require(len(keys) == len(set(keys)), 'duplicate model key')
    expected_keys = [(f['scheme'], f['fold_id']) for f in ref['folds']]
    m.require(set(keys) == set(expected_keys), 'complete model family')
    position = {key: i for i, key in enumerate(keys)}
    count, n_features = len(keys), ref['features'].shape[1]
    cols = ordering(a['feature_index'], np.arange(n_features))
    arrays = {name: finite_array(a[name], (count, n_features), name)[:, cols]
              for name in ('scaler_mean', 'scaler_variance', 'scaler_scale', 'coefficient')}
    intercept = finite_array(a['intercept'], (count,), 'intercept')
    m.require(np.all(arrays['scaler_variance'] >= 0) and np.all(arrays['scaler_scale'] > 0), 'scaler natural domain')
    checks = {}; tolerance = ref['method']['tolerances_proposed_before_values']['scaler']
    for fold in ref['folds']:
        key = fold['scheme'], fold['fold_id']; row = position[key]; scaler = ref['scalers'][key]
        for name in ('mean', 'variance', 'scale'):
            io.close(arrays['scaler_' + name][row], scaler[name], **tolerance, name='train-only scaler ' + name)
        certificate, scores = _model_certificate(ref, fold, arrays['coefficient'][row], float(intercept[row]))
        checks[key] = dict(certificate, decision_score=scores, n_constant_features=int(np.sum(scaler['constant'])))
    return checks


def validate_predictions(path, ref, models):
    columns = ref['method']['artifacts']['oof_predictions.csv']['columns']
    rows = io.index_rows(io.csv_rows(path, columns), ('scheme', 'phenotype_row'), ('phenotype_row',))
    expected_keys = {(scheme, int(row)) for scheme in ('loso', 'random10') for row in ref['row_ids']}
    m.require(set(rows) == expected_keys, 'complete source-keyed OOF family')
    predictions = {scheme: np.empty(len(ref['labels']), dtype=np.int64) for scheme in ('loso', 'random10')}
    tol = ref['method']['tolerances_proposed_before_values']['replayed_decision']
    for fold in ref['folds']:
        key = fold['scheme'], fold['fold_id']; tr, te = fold['train'], fold['test']
        majority = int(np.sum(ref['labels'][tr] == 1) >= np.sum(ref['labels'][tr] == 0))
        for j, i in enumerate(te):
            row = rows[(fold['scheme'], int(ref['row_ids'][i]))]
            expected = dict(scheme=fold['scheme'], phenotype_row=int(ref['row_ids'][i]), subject_id=int(ref['subject_ids'][i]),
                            site=str(ref['sites'][i]), label=int(ref['labels'][i]), fold_id=fold['fold_id'],
                            held_out_site=fold['held_out_site'], training_majority_prediction=majority)
            io.row_match(row, expected)
            score = io.number(row['decision_score'])
            io.close(score, models[key]['decision_score'][j], **tol, name='own-model held-out score')
            prediction = io.integer(row['prediction'])
            m.require(prediction == int(score > 0), 'prediction must follow own reported signed score')
            predictions[fold['scheme']][i] = prediction
    return predictions


def validate_fold_table(path, ref, expected, models):
    rows = io.index_rows(io.csv_rows(path, ref['method']['artifacts']['per_fold.csv']['columns']),
                         ('scheme', 'fold_id'), ('fold_id',))
    m.require(set(rows) == {(r['scheme'], r['fold_id']) for r in expected}, 'complete per-fold table')
    tolerance = ref['method']['tolerances_proposed_before_values']
    for record in expected:
        key = record['scheme'], record['fold_id']; row = rows[key]
        io.row_match(row, record, **tolerance['metrics'])
        for field in ('open_recall', 'closed_recall', 'balanced_accuracy'):
            if row[field].strip(): m.require(0 <= io.number(row[field]) <= 1, 'fold metric domain')
        io.row_match(row, {'n_constant_features': models[key]['n_constant_features']})
        for field in ('primal_objective', 'certificate_gap', 'certificate_limit'):
            reported = io.number(row[field]); m.require(reported >= 0, 'reported certificate natural domain')
            io.close(reported, models[key][field], **tolerance['reported_objective_and_certificate'], name=field)
        m.require(row['solver'].strip() and row['solver_status'].strip(), 'actual solver diagnostic required')
        if row['n_iter'].strip(): m.require(io.integer(row['n_iter']) >= 0, 'actual nonnegative iterations')


def _metadata_observed(actual, expected):
    # These public collections are keyed and order-free; the site list itself is
    # canonical in the schema, not a duplicated numeric computational axis.
    collections = {'site_support': 'site', 'frame_count_histogram': 'n_timepoints', 'roi_count_histogram': 'n_rois',
                   'constant_roi_count_histogram': 'n_constant_rois'}
    io.match(actual, {k: v for k, v in expected.items() if k not in collections})
    for name, key in collections.items():
        m.require(name in actual and isinstance(actual[name], list), 'required source observed collection')
        rows = {}; reference = {r[key]: r for r in expected[name]}
        for row in actual[name]:
            m.require(isinstance(row, dict) and key in row, 'source observed keyed record')
            value = row[key] if key == 'site' else io.integer(row[key], True)
            m.require(value not in rows, 'duplicate source observed record'); rows[value] = row
        m.require(set(rows) == set(reference), 'complete source observed records')
        for identity, record in reference.items(): io.match(rows[identity], record)


def validate_metadata(path, ref):
    data = io.read_json(path)
    required = ref['method']['artifacts']['run_metadata.json']['required']
    m.require(isinstance(data, dict) and set(required) <= set(data), 'required run metadata')
    io.match(data, dict(status='ok', task_id='EYESTATE-001', method_id=ref['method']['method_id'],
                       method_contract_sha256=source.METHOD_SHA256, source_manifest_sha256=source.SOURCE_SHA256,
                       dataset_id=ref['method']['source']['dataset_id']))
    io.match(data['source_sha256'], ref['source_sha256'], closed=True)
    _metadata_observed(data['source_observed'], ref['source_observed'])
    versions = data['software_versions']
    m.require(isinstance(versions, dict) and versions and all(isinstance(k, str) and k.strip() for k in versions),
              'actual software versions object')
    warnings = data['fit_warnings']; m.require(isinstance(warnings, list), 'fit warnings list')
    keys = set()
    for row in warnings:
        m.require(isinstance(row, dict) and {'scheme', 'fold_id', 'warnings'} <= set(row), 'warning record schema')
        key = row['scheme'], io.integer(row['fold_id'], True)
        m.require(key not in keys and isinstance(row['warnings'], list), 'warning record unique/list')
        keys.add(key)
    m.require(keys == {(f['scheme'], f['fold_id']) for f in ref['folds']}, 'complete model warning records')


def validate_output_directory(output, ref=None):
    ref = load_reference() if ref is None else ref
    output = io.safe_path(output); artifacts = ref['method']['artifacts']
    m.require(not os.path.lexists(output / 'failure_report.json'), 'reserved failure_report.json marks an incomplete or failed run')
    for filename in artifacts: io.regular(output / filename)
    m.require((output / 'findings.md').read_text().strip(), 'nonempty free findings')
    validate_cohort(output / 'cohort.csv', ref)
    validate_features(output / 'features.npz', ref)
    models = validate_models(output / 'fold_models.npz', ref)
    predictions = validate_predictions(output / 'oof_predictions.csv', ref, models)
    n_unavailable = sum(r['exclusion_reason'] == 'unavailable_derivative' for r in ref['cohort'])
    folds, expected = m.summarize(ref['labels'], ref['sites'], ref['folds'], predictions,
                                 ref['method']['method_id'], len(ref['cohort']), n_unavailable)
    validate_fold_table(output / 'per_fold.csv', ref, folds, models)
    results = io.read_json(output / 'eye_decoding_results.json')
    io.match(results, expected, **ref['method']['tolerances_proposed_before_values']['metrics'])
    m.require(set(results['schemes']) == {'loso', 'random10'}, 'closed scheme identities')
    for name, value in expected.items():
        if isinstance(value, float): m.require(0 <= io.number(results[name], True) <= 1, 'result fraction domain')
    for scheme in ('loso', 'random10'):
        for name, value in expected['schemes'][scheme].items():
            if isinstance(value, float): m.require(0 <= io.number(results['schemes'][scheme][name], True) <= 1, 'scheme fraction domain')
    validate_metadata(output / 'run_metadata.json', ref)
    return dict(results=expected, models=models, predictions=predictions)
