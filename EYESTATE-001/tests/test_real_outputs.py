"""Actual-output regressions, gated by explicit run paths; no model refitting.

Canonical features are reconstructed from authenticated originals once per
process. Mutations are manufactured adversarial submissions, not source runs.
Each case owns its temporary files; unchanged large NPZ files are hard-linked
only to a private temporary baseline, and every mutation detaches its target.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pytest
import fixture_support as f
import io_contract as io
import metric_contract as m
import proof_of_work as p


def supplied_path(name):
    value = os.environ.get(name)
    if value is None: pytest.skip(name + ' not supplied; genuine source execution is externally gated')
    path = Path(value)
    assert path.is_dir(), name + ' supplied but absent'
    return path


@pytest.fixture(scope='module')
def oracle():
    return supplied_path('REPAIR_ORACLE_OUTPUT')


@pytest.fixture(scope='module')
def reference(oracle):
    return p.load_reference()


@pytest.fixture(scope='module')
def private_baseline(oracle, reference):
    with tempfile.TemporaryDirectory(prefix='eyestate-baseline-') as directory:
        root = Path(directory)
        for name in reference['method']['artifacts']:
            shutil.copyfile(oracle / name, root / name)
        yield root


@pytest.fixture
def case(private_baseline):
    with tempfile.TemporaryDirectory(prefix='eyestate-case-') as directory:
        root = Path(directory)
        for path in private_baseline.iterdir(): os.link(path, root / path.name)
        yield root


def detach(case, filename):
    path = case / filename; temp = case / (filename + '.owned')
    shutil.copyfile(path, temp); os.replace(temp, path)
    return path


def json_change(case, filename, change):
    f.rewrite_json(detach(case, filename), change)


def csv_change(case, filename, change):
    f.rewrite_csv(detach(case, filename), change)


def npz_change(case, filename, change):
    f.rewrite_npz(detach(case, filename), change)


def reject(case, reference):
    with pytest.raises((AssertionError, ValueError, TypeError, KeyError, EOFError, OSError)):
        p.validate_output_directory(case, reference)


def metrics_from_own_predictions(case, reference):
    _, rows = f.read_csv(case / 'oof_predictions.csv')
    keyed = {(r['scheme'], io.integer(r['phenotype_row'])): r for r in rows}
    predictions = {s: np.array([io.integer(keyed[s, int(row)]['prediction']) for row in reference['row_ids']])
                   for s in ('loso', 'random10')}
    records, results = m.summarize(reference['labels'], reference['sites'], reference['folds'], predictions,
                                 reference['method']['method_id'], len(reference['cohort']),
                                 sum(r['exclusion_reason'] == 'unavailable_derivative' for r in reference['cohort']))
    values = {(r['scheme'], r['fold_id']): r for r in records}
    csv_change(case, 'per_fold.csv', lambda rows: [r.update(values[r['scheme'], io.integer(r['fold_id'])]) for r in rows])
    detach(case, 'eye_decoding_results.json').write_text(json.dumps(results, allow_nan=False))


def test_genuine_original_reference_implementation(oracle, reference):
    p.validate_output_directory(oracle, reference)


@pytest.mark.parametrize('kind', ['receipt', 'dangling_symlink'])
def test_genuine_complete_files_with_late_failure(case, reference, kind):
    path = case / 'failure_report.json'
    if kind == 'dangling_symlink': path.symlink_to(case / 'absent')
    else: path.write_text('{"status":"failed_precondition","reason":"late failure"}')
    with pytest.raises(AssertionError, match='reserved failure_report'):
        p.validate_output_directory(case, reference)


def test_genuine_independent_solver(reference):
    p.validate_output_directory(supplied_path('REPAIR_INDEPENDENT_OUTPUT'), reference)


def test_genuine_harmless_prose_metadata_and_solver_diagnostics(case, reference):
    detach(case, 'findings.md').write_text('A descriptive comparison with no prescribed sign or ranking.\n')
    json_change(case, 'run_metadata.json', lambda a: a.update(extra={'optional_analysis': None}, software_versions={'equivalent_stack': 'actual-report-fixture'}))
    csv_change(case, 'per_fold.csv', lambda rows: [r.update(solver='reported-equivalent', solver_status='certificate_verified', n_iter='') for r in rows])
    p.validate_output_directory(case, reference)


def test_genuine_csv_order_extra_columns_numeric_id_notation(case, reference):
    for filename in ('cohort.csv', 'oof_predictions.csv', 'per_fold.csv'):
        path = detach(case, filename); columns, rows = f.read_csv(path)
        for row in rows:
            row['description_extra'] = 'non-scientific'
            for key in ('phenotype_row', 'subject_id', 'fold_id'):
                if key in row and row[key]:
                    value = io.integer(row[key]); row[key] = format(value, '.17e')
                    assert io.integer(row[key]) == value
        f.write_csv(path, ['description_extra'] + columns[::-1], rows[::-1])
    p.validate_output_directory(case, reference)


def test_genuine_coherent_npz_axis_permutations(case, reference):
    rng = np.random.default_rng(47)
    def features(a):
        row = rng.permutation(len(a['phenotype_row'])); col = rng.permutation(len(a['feature_index']))
        for key in ('phenotype_row', 'subject_id', 'shrinkage'): a[key] = a[key][row]
        for key in ('feature_index', 'roi_i', 'roi_j'): a[key] = a[key][col]
        a['correlation'] = a['correlation'][np.ix_(row, col)]
        for key in ('phenotype_row', 'subject_id', 'feature_index', 'roi_i', 'roi_j'): a[key] = a[key].astype(float)
    npz_change(case, 'features.npz', features)
    def models(a):
        row = rng.permutation(len(a['scheme'])); col = rng.permutation(len(a['feature_index']))
        for key in ('scheme', 'fold_id', 'intercept'): a[key] = a[key][row]
        for key in ('coefficient', 'scaler_mean', 'scaler_variance', 'scaler_scale'): a[key] = a[key][np.ix_(row, col)]
        a['feature_index'] = a['feature_index'][col].astype(float)
    npz_change(case, 'fold_models.npz', models)
    p.validate_output_directory(case, reference)


def test_genuine_evidence_float32_does_not_replace_canonical_fit_inputs(case, reference):
    npz_change(case, 'features.npz', lambda a: a.update(correlation=a['correlation'].astype('float32'), shrinkage=a['shrinkage'].astype('float32')))
    def models(a):
        for key in ('scaler_mean', 'scaler_variance', 'scaler_scale'): a[key] = a[key].astype('float32')
    npz_change(case, 'fold_models.npz', models)
    p.validate_output_directory(case, reference)


@pytest.mark.parametrize('arm', ['pearson', 'global-scaler'])
def test_actual_source_component_control(arm, reference):
    root = supplied_path('REPAIR_CONTROL_OUTPUT'); output = root / arm
    assert output.is_dir(), 'supplied actual component control is absent'
    report = io.read_json(root / 'report.json')
    assert report['status'] == 'completed'
    assert report['source_manifest_sha256'] == p.source.SOURCE_SHA256
    assert report['method_contract_sha256'] == p.source.METHOD_SHA256
    record = report['pearson' if arm == 'pearson' else 'global_scaler']
    assert record['control_status'] == 'effective_numeric_rejection'
    assert record['refitted_models'] == 0 and record['new_performance_metrics'] is False
    tolerance = reference['method']['tolerances_proposed_before_values']
    discrepancies = {}
    if arm == 'pearson':
        a = p.read_npz(output / 'features.npz', reference['method']['artifacts']['features.npz']['arrays'])
        rows = p.ordering(a['phenotype_row'], reference['row_ids']); cols = p.ordering(a['feature_index'], np.arange(19900))
        actual, expected = a['correlation'][np.ix_(rows, cols)], reference['features']
        tol = tolerance['feature']
        discrepancies['correlation'] = int(np.count_nonzero(np.abs(actual - expected) > tol['atol'] + tol['rtol'] * np.abs(expected)))
        primitive = lambda: p.validate_features(output / 'features.npz', reference)
        reason = 'source FC.*numeric mismatch'
    else:
        a = p.read_npz(output / 'fold_models.npz', reference['method']['artifacts']['fold_models.npz']['arrays'])
        keys = [(str(s), io.integer(i)) for s, i in zip(a['scheme'], a['fold_id'])]
        cols = p.ordering(a['feature_index'], np.arange(19900)); tol = tolerance['scaler']
        for field in ('mean', 'variance', 'scale'):
            actual = a['scaler_' + field][:, cols]
            expected = np.array([reference['scalers'][key][field] for key in keys])
            discrepancies[field] = int(np.count_nonzero(np.abs(actual - expected) > tol['atol'] + tol['rtol'] * np.abs(expected)))
        primitive = lambda: p.validate_models(output / 'fold_models.npz', reference)
        reason = 'train-only scaler.*numeric mismatch'
    assert sum(discrepancies.values()) > 0, 'declared effective control must actually exceed frozen source tolerances'
    for field, count in discrepancies.items(): assert count == record['discrepancies'][field]['n_outside_tolerance']
    with pytest.raises(AssertionError, match=reason): primitive()
    with pytest.raises(AssertionError, match=reason): p.validate_output_directory(output, reference)


@pytest.mark.parametrize('filename', ['cohort.csv', 'features.npz', 'fold_models.npz', 'oof_predictions.csv',
                                    'per_fold.csv', 'eye_decoding_results.json', 'run_metadata.json', 'findings.md'])
@pytest.mark.parametrize('mode', ['missing', 'empty'])
def test_required_artifacts(case, reference, filename, mode):
    if mode == 'missing': (case / filename).unlink()
    else: detach(case, filename).write_bytes(b'')
    reject(case, reference)


@pytest.mark.parametrize('filename', ['cohort.csv', 'oof_predictions.csv', 'per_fold.csv'])
@pytest.mark.parametrize('mode', ['duplicate', 'drop', 'boolean_key'])
def test_complete_csv_scientific_keys(case, reference, filename, mode):
    def change(rows):
        if mode == 'duplicate': rows.append(rows[0].copy())
        elif mode == 'drop': rows.pop()
        else: rows[0]['fold_id' if filename == 'per_fold.csv' else 'phenotype_row'] = 'True'
    csv_change(case, filename, change); reject(case, reference)


@pytest.mark.parametrize('field', ['label', 'site', 'source_sha256', 'n_timepoints', 'n_constant_rois', 'n_low_sd_rois', 'included'])
def test_source_ledger_binding(case, reference, field):
    def change(rows):
        row = next(r for r in rows if r['included'].lower() in ('true', '1'))
        if field == 'label': row[field] = str(1 - io.integer(row[field]))
        elif field == 'site': row[field] += '_wrong'
        elif field == 'source_sha256': row[field] = '0' * 64
        elif field == 'included': row[field] = 'false'
        else: row[field] = str(io.integer(row[field]) + 1)
    csv_change(case, 'cohort.csv', change); reject(case, reference)


@pytest.mark.parametrize('mode', ['rank_preserving_shift', 'wrong_shrinkage', 'partial', 'duplicate_row', 'wrong_edge', 'nonfinite'])
def test_complete_source_features(case, reference, mode):
    def change(a):
        if mode == 'rank_preserving_shift': a['correlation'] += .04
        elif mode == 'wrong_shrinkage': a['shrinkage'][0] += .01
        elif mode == 'partial': a['correlation'] = a['correlation'][:-1]
        elif mode == 'duplicate_row': a['phenotype_row'][1] = a['phenotype_row'][0]
        elif mode == 'wrong_edge': a['roi_i'][0] += 1
        else: a['correlation'][0, 0] = np.inf
    npz_change(case, 'features.npz', change); reject(case, reference)


@pytest.mark.parametrize('mode', ['mean', 'variance', 'scale', 'zero_model', 'large_intercept', 'duplicate_model', 'missing_model', 'nan'])
def test_canonical_scalers_and_public_model_certificate(case, reference, mode):
    def change(a):
        if mode in ('mean', 'variance', 'scale'): a['scaler_' + mode][0, 0] += .1
        elif mode == 'zero_model': a['coefficient'][:] = 0; a['intercept'][:] = 0
        elif mode == 'large_intercept': a['intercept'][0] += 100
        elif mode == 'duplicate_model': a['scheme'][1] = a['scheme'][0]; a['fold_id'][1] = a['fold_id'][0]
        elif mode == 'missing_model': a['intercept'] = a['intercept'][:-1]
        else: a['coefficient'][0, 0] = np.nan
    npz_change(case, 'fold_models.npz', change); reject(case, reference)


@pytest.mark.parametrize('mode', ['replayed_score', 'own_sign', 'truth', 'fold', 'subject', 'training_majority'])
def test_oof_scores_identities_and_summary_coherence(case, reference, mode):
    def change(rows):
        row = rows[0]
        if mode == 'replayed_score':
            old = io.number(row['decision_score']); row['decision_score'] = old + 100 * (1e-8 + 1e-7 * abs(old))
            row['prediction'] = int(row['decision_score'] > 0)
        elif mode == 'own_sign': row['prediction'] = 1 - io.integer(row['prediction'])
        elif mode == 'truth': row['label'] = 1 - io.integer(row['label'])
        elif mode == 'fold': row['fold_id'] = 100
        elif mode == 'subject': row['subject_id'] = io.integer(row['subject_id']) + 10000000
        else: row['training_majority_prediction'] = 1 - io.integer(row['training_majority_prediction'])
    csv_change(case, 'oof_predictions.csv', change)
    if mode in ('replayed_score', 'own_sign'): metrics_from_own_predictions(case, reference)
    reject(case, reference)


@pytest.mark.parametrize('field', ['primal_objective', 'certificate_gap', 'certificate_limit', 'balanced_accuracy', 'tn', 'n_constant_features'])
def test_reported_fit_and_fold_arithmetic(case, reference, field):
    def change(rows):
        old = io.number(rows[0][field]); rows[0][field] = old + max(1., abs(old))
    csv_change(case, 'per_fold.csv', change); reject(case, reference)


@pytest.mark.parametrize('mode', ['primary', 'random', 'baseline', 'legacy', 'source_count', 'method', 'boolean_count', 'missing_scheme'])
def test_results_arithmetic_not_shape(case, reference, mode):
    def change(a):
        fields = dict(primary='cv_balanced_accuracy', random='random_kfold_balanced_accuracy', baseline='site_only_unseen_site_baseline',
                      legacy='legacy_equal_site_mean_recall', source_count='n_subjects')
        if mode in fields: a[fields[mode]] += .01
        elif mode == 'method': a['method_id'] = 'different'
        elif mode == 'boolean_count': a['n_subjects'] = True
        else: del a['schemes']['random10']
    json_change(case, 'eye_decoding_results.json', change); reject(case, reference)


@pytest.mark.parametrize('mode', ['status', 'source_hash', 'method_hash', 'source_extra', 'missing_warnings', 'missing_histogram',
                                'constant_count', 'nonfinite_extra', 'duplicate_json'])
def test_required_provenance_and_finite_json(case, reference, mode):
    def change(a):
        if mode == 'status': a['status'] = 'resource_pilot'
        elif mode == 'source_hash': a['source_manifest_sha256'] = '0' * 64
        elif mode == 'method_hash': a['method_contract_sha256'] = '0' * 64
        elif mode == 'source_extra': a['source_sha256']['invented'] = '0' * 64
        elif mode == 'missing_warnings': a['fit_warnings'].pop()
        elif mode == 'missing_histogram': del a['source_observed']['constant_roi_count_histogram']
        elif mode == 'constant_count': a['source_observed']['constant_roi_count_histogram'][0]['n_subjects'] += 1
    if mode in ('nonfinite_extra', 'duplicate_json'):
        path = detach(case, 'run_metadata.json'); text = path.read_text()
        extra = ',"extra":{"nested":1e999}}' if mode == 'nonfinite_extra' else ',"status":"ok"}'
        path.write_text(text[:-1] + extra)
    else: json_change(case, 'run_metadata.json', change)
    reject(case, reference)
