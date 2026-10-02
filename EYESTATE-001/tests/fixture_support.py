"""Manufactured mechanics only. These are not original ABIDE evidence."""
import csv
import json
import os
from pathlib import Path
import numpy as np
import metric_contract as m
import source_reference as source


def public_method():
    path = Path(os.environ.get('REPAIR_METHOD_PATH', Path(__file__).parents[1] / 'environment/method_contract.json'))
    return json.loads(path.read_text())


def write_csv(path, columns, rows):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def read_csv(path):
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def rewrite_csv(path, update):
    columns, rows = read_csv(path)
    update(rows)
    write_csv(path, columns, rows)


def rewrite_json(path, update):
    value = json.loads(Path(path).read_text()); update(value)
    Path(path).write_text(json.dumps(value, allow_nan=False))


def rewrite_npz(path, update):
    with np.load(path, allow_pickle=False) as archive:
        value = {k: archive[k] for k in archive.files}
    update(value)
    np.savez_compressed(path, **value)


def manufactured_reference(method=None):
    method = public_method() if method is None else method
    # A zero FC vector represents an identity shrunk covariance. Balanced and
    # unbalanced training sets have an analytic penalized-intercept optimum.
    n, p = 20, 19900
    labels = np.tile([1, 0], 10)
    sites = np.repeat(['A', 'B', 'C', 'D'], 5)
    features = np.zeros((n, p)); rows = np.arange(n) * 2
    ids = np.arange(n) + 900000
    cohort = [dict(phenotype_row=int(rows[i]), subject_id=int(ids[i]), file_id=f'toy_{i}', site=str(sites[i]),
                   eye_code=1 if labels[i] else 2, label=int(labels[i]), source_path=f'roi/toy_{i}.1D',
                   source_sha256='c' * 64, n_timepoints=80, n_rois=200, n_constant_rois=0, n_low_sd_rois=0,
                   included=True, exclusion_reason='included', selected_index=i) for i in range(n)]
    ref = dict(method=method, features=features, row_ids=rows, subject_ids=ids, labels=labels, sites=sites,
               shrinkage=np.ones(n), cohort=cohort, source_sha256={r['source_path']: r['source_sha256'] for r in cohort})
    ref['folds'] = m.make_folds(labels, sites)
    ref['scalers'] = {(f['scheme'], f['fold_id']): m.scale_training(features[f['train']]) for f in ref['folds']}
    ref['source_observed'] = source.observed_metadata(ref, method)
    return ref


def emit_manufactured(output, ref, intercept_delta=0., nearzero_reported_score=None):
    output = Path(output); output.mkdir()
    n, p = ref['features'].shape; folds = ref['folds']; method = ref['method']
    features = dict(phenotype_row=ref['row_ids'], subject_id=ref['subject_ids'], feature_index=np.arange(p),
                    roi_i=np.tril_indices(200, -1)[0], roi_j=np.tril_indices(200, -1)[1],
                    correlation=ref['features'], shrinkage=ref['shrinkage'])
    np.savez_compressed(output / 'features.npz', **features)
    model = dict(scheme=np.array([f['scheme'] for f in folds]), fold_id=np.array([f['fold_id'] for f in folds]),
                 feature_index=np.arange(p), coefficient=np.zeros((len(folds), p)), intercept=np.empty(len(folds)))
    for field in ('mean', 'variance', 'scale'):
        model['scaler_' + field] = np.array([ref['scalers'][(f['scheme'], f['fold_id'])][field] for f in folds])
    predictions = {s: np.empty(n, dtype=int) for s in ('loso', 'random10')}
    rows, certificates = [], {}
    for index, fold in enumerate(folds):
        tr, te = fold['train'], fold['test']; t = 2 * ref['labels'][tr] - 1
        intercept = float(2 * t.sum() / (1 + 2 * len(tr)) + intercept_delta)
        model['intercept'][index] = intercept
        certificate = m.fit_certificate(np.zeros((len(tr), p)), ref['labels'][tr], model['coefficient'][index], intercept)
        certificates[fold['scheme'], fold['fold_id']] = certificate
        reported = nearzero_reported_score if intercept == 0 and nearzero_reported_score is not None else intercept
        prediction = int(reported > 0); predictions[fold['scheme']][te] = prediction
        for i in te:
            rows.append(dict(scheme=fold['scheme'], phenotype_row=int(ref['row_ids'][i]), subject_id=int(ref['subject_ids'][i]),
                             site=str(ref['sites'][i]), label=int(ref['labels'][i]), fold_id=fold['fold_id'],
                             held_out_site=fold['held_out_site'], decision_score=reported, prediction=prediction,
                             training_majority_prediction=int(np.sum(t) >= 0)))
    np.savez_compressed(output / 'fold_models.npz', **model)
    per_fold, results = m.summarize(ref['labels'], ref['sites'], folds, predictions, method['method_id'], len(ref['cohort']), 0)
    for row in per_fold:
        row.update(certificates[row['scheme'], row['fold_id']], n_constant_features=p,
                   solver='manufactured analytic intercept optimum', solver_status='analytic', n_iter=None)
    for name, records in [('cohort.csv', ref['cohort']), ('oof_predictions.csv', rows), ('per_fold.csv', per_fold)]:
        write_csv(output / name, method['artifacts'][name]['columns'], records)
    metadata = dict(status='ok', task_id='EYESTATE-001', method_id=method['method_id'],
                    method_contract_sha256=source.METHOD_SHA256, source_manifest_sha256=source.SOURCE_SHA256,
                    source_sha256=ref['source_sha256'], dataset_id=method['source']['dataset_id'],
                    source_observed=ref['source_observed'], software_versions={'analytic_fixture': 'not_scientific_evidence'},
                    fit_warnings=[dict(scheme=f['scheme'], fold_id=f['fold_id'], warnings=[]) for f in folds])
    (output / 'eye_decoding_results.json').write_text(json.dumps(results, allow_nan=False))
    (output / 'run_metadata.json').write_text(json.dumps(metadata, allow_nan=False))
    (output / 'findings.md').write_text('Manufactured mechanics; no original source or fitted scientific claim.\n')
    return output
