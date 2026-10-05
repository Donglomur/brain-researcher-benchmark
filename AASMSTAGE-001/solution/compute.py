"""Original-source explicit Welch features and six fixed LOSO forests."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import mne
import numpy as np
import scipy
import sklearn
from sklearn.ensemble import RandomForestClassifier
from source_reader import inspect_subject, read_retained_epochs, require

METHOD_SHA256 = '5a935b2a61676fafab304fd28343c9720d11e1b7f3c3f5c7f2b12b2744527793'
SOURCE_SHA256 = '241be998b50465f17431dba963499dbb34c355a2e17533a1dd0d659f4e837cbb'
PIPELINE = 'sleepedf-welch256-loso-v2'
STAGES = ['W', 'N1', 'N2', 'N3', 'REM']


def reject_links(path):
    p = Path(path).absolute()
    require(not any(q.is_symlink() for q in (p, *p.parents)), 'Symlink source/evidence path')


def prepare_destinations(output, private, source, method_path):
    paths = [Path(p) for p in (output, private, source, method_path)]
    for p in paths:
        reject_links(p)
    a, b, src, method = [p.resolve() for p in paths]
    for x, y in ((a, b), (a, src), (b, src)):
        require(x != y and x not in y.parents and y not in x.parents, 'Nested source/evidence directories')
    require(all(p != method and p not in method.parents for p in (a, b)), 'Method inside evidence directory')
    for p in (a, b):
        require(not p.exists() or (p.is_dir() and not any(p.iterdir())), 'Refuse existing evidence')
    for p in (a, b):
        p.mkdir(parents=True, exist_ok=True)
    return a, b


def load_inputs(source_dir, method_path):
    reject_links(source_dir); reject_links(method_path)
    require(Path(method_path).is_file(), 'Public method contract must be a regular file')
    raw = Path(method_path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == METHOD_SHA256, 'Public method hash mismatch')
    method = json.loads(raw)
    candidates = [Path(__file__).parents[1]/'environment'/'stage_data.py', Path('/opt/source/stage_data.py')]
    helper = next((p for p in candidates if p.is_file()), None)
    require(helper is not None, 'Source verification helper unavailable')
    spec = importlib.util.spec_from_file_location('aasmstage_integrity', helper)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    manifest = module.verify_staged(source_dir)
    require(hashlib.sha256((Path(source_dir)/'source_manifest.json').read_bytes()).hexdigest() == SOURCE_SHA256,
            'Source manifest hash mismatch')
    paths = {(r['subject'], r['role']): Path(source_dir)/r['path'] for r in manifest['files']}
    return method, manifest, paths


def spectral_features(epochs):
    require(epochs.ndim == 3 and epochs.shape[1:] == (2, 3000) and np.isfinite(epochs).all(), 'Invalid EEG epochs')
    psd, freq = mne.time_frequency.psd_array_welch(np.asarray(epochs, dtype=np.float64), sfreq=100.,
        fmin=0., fmax=50., n_fft=256, n_per_seg=256, n_overlap=0, window='hamming',
        remove_dc=True, average='mean', n_jobs=1, verbose=False)
    require(np.array_equal(freq, np.arange(129)*100/256), 'Unexpected Welch grid')
    denominator = psd[..., (freq >= .5) & (freq <= 30)].sum(axis=-1)
    require(np.isfinite(psd).all() and (psd >= 0).all() and np.isfinite(denominator).all()
            and (denominator > 0).all(), 'Invalid or zero normalization power')
    norm = psd/denominator[..., None]
    features = np.concatenate([norm[..., (freq >= a) & (freq < b)].mean(axis=-1)
        for a, b in [(0.5,4.5),(4.5,8.5),(8.5,11.5),(11.5,15.5),(15.5,30)]], axis=1)
    require(np.isfinite(features).all(), 'Nonfinite features')
    return features, denominator, psd


def confusion_matrix(truth, prediction):
    truth, prediction = np.asarray(truth), np.asarray(prediction)
    require(truth.ndim == 1 and truth.shape == prediction.shape and np.isin(truth, [1,2,3,4,5]).all()
            and np.isin(prediction, [1,2,3,4,5]).all(), 'Invalid class IDs')
    c = np.zeros((5,5), np.int64)
    np.add.at(c, (truth.astype(int)-1, prediction.astype(int)-1), 1)
    return c


def metrics(matrix):
    matrix = np.asarray(matrix)
    require(matrix.shape == (5,5) and (matrix >= 0).all() and np.equal(matrix, np.floor(matrix)).all(), 'Invalid confusion')
    c = [[int(v) for v in row] for row in matrix]
    row, col = [sum(r) for r in c], [sum(c[a][b] for a in range(5)) for b in range(5)]
    n = sum(row); require(n > 0, 'No metric support')
    correct = sum(c[k][k] for k in range(5)); chance = sum(a*b for a,b in zip(row,col)); den = n*n-chance
    recalls = [c[k][k]/row[k] for k in range(5) if row[k]]
    return dict(overall_accuracy=correct/n, balanced_accuracy=sum(recalls)/len(recalls),
        kappa=(n*correct-chance)/den if den else None,
        kappa_status='defined' if den else 'undefined_degenerate_marginals', n_supported_classes=len(recalls), n_epochs=n,
        per_class=[dict(stage_id=k+1,n_true=row[k],n_predicted=col[k],n_correct=c[k][k],
            recall=c[k][k]/row[k] if row[k] else None,
            recall_status='defined' if row[k] else 'undefined_no_true_epochs') for k in range(5)])


def fit_fold(features, labels, subjects, keys, heldout, parameters):
    train, test = np.flatnonzero(subjects != heldout), np.flatnonzero(subjects == heldout)
    require(len(train) > 0 and len(test) > 0, 'Empty fold support')
    forest = RandomForestClassifier(**parameters)
    forest.fit(features[train].astype(np.float32), labels[train])
    probability = np.zeros((len(test),5), np.float64)
    probability[:,forest.classes_.astype(int)-1] = forest.predict_proba(features[test].astype(np.float32))
    require(np.isfinite(probability).all() and (probability >= 0).all() and (probability <= 1).all(), 'Invalid forest probabilities')
    trees = [t.tree_ for t in forest.estimators_]; prefix = f'forest_{heldout}_'
    state = {prefix+'node_offsets':np.cumsum([0]+[t.node_count for t in trees],dtype=np.int64),
        prefix+'classes':forest.classes_.astype(np.int64), prefix+'train_keys':keys[train], prefix+'test_keys':keys[test],
        prefix+'tree_seeds':np.array([t.random_state for t in forest.estimators_],np.int64),
        prefix+'value':np.concatenate([t.value[:,0,:] for t in trees])}
    for name in ('children_left','children_right','feature','threshold','n_node_samples','weighted_n_node_samples'):
        state[prefix+name] = np.concatenate([getattr(t,name) for t in trees])
    return train, test, probability, np.argmax(probability,axis=1)+1, state


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def write_csv(path, rows, columns):
    with Path(path).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore'); writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v) if isinstance(v,list) else v for k,v in row.items()})


def run(source_dir, method_path, output, private, pilot_heldout=None):
    method, manifest, paths = load_inputs(source_dir, method_path)
    annotations, epochs, observations, retained, blocks, powers, arrays = [], [], [], [], [], [], {}
    inspected = {s:inspect_subject(s, paths[s,'psg'], paths[s,'hypnogram'], method) for s in range(6)}
    for subject in range(6):
        a, e, obs = inspected[subject]
        annotations.extend(a); epochs.extend(e); observations.append(obs)
        keep = [r for r in e if r['retained']]
        data = read_retained_epochs(paths[subject,'psg'], e, obs)
        pieces = [spectral_features(data[i:i+128]) for i in range(0,len(data),128)]
        blocks.append(np.concatenate([p[0] for p in pieces])); powers.append(np.concatenate([p[1] for p in pieces]))
        arrays[f'epoch_subject_{subject}'] = data
        arrays[f'psd_subject_{subject}'] = np.concatenate([p[2] for p in pieces]); retained.extend(keep)
        print(f'Original subject {subject}: {len(keep)} source-bound Welch epochs', flush=True)
    features, power = np.concatenate(blocks), np.concatenate(powers)
    keys = np.array([[r['subject'],1,r['onset_sample']] for r in retained],np.int64)
    subjects, labels = keys[:,0], np.array([r['stage_id'] for r in retained],np.int64)
    require(np.array_equal(np.lexsort((keys[:,2],keys[:,0])),np.arange(len(keys))), 'Noncanonical training order')
    probability_all = np.full((len(keys),5),np.nan); prediction_all = np.zeros(len(keys),np.int64)
    prediction_rows, subject_rows, confusion_rows = [], [], []
    pooled = np.zeros((5,5),np.int64)
    folds = [pilot_heldout] if pilot_heldout is not None else list(range(6))
    for heldout in folds:
        train, test, probability, prediction, state = fit_fold(features,labels,subjects,keys,heldout,method['classifier']['parameters'])
        arrays.update(state); probability_all[test] = probability; prediction_all[test] = prediction
        matrix = confusion_matrix(labels[test],prediction); pooled += matrix; result = metrics(matrix)
        for j,index in enumerate(test):
            row = dict(subject=heldout,recording=1,onset_sample=int(keys[index,2]),heldout_subject=heldout,
                       true_stage=int(labels[index]),predicted_stage=int(prediction[j]))
            row.update({k:float(v) for k,v in zip(['prob_w','prob_n1','prob_n2','prob_n3','prob_rem'],probability[j])})
            prediction_rows.append(row)
        summary = dict(subject=heldout,recording=1,training_subjects=[s for s in range(6) if s != heldout],
            n_train_epochs=len(train),n_test_epochs=len(test),
            **{k:result[k] for k in ['overall_accuracy','balanced_accuracy','kappa','kappa_status','n_supported_classes']})
        for k,name in enumerate(['w','n1','n2','n3','rem'],1):
            summary['n_train_'+name] = int((labels[train] == k).sum())
            summary['n_test_'+name] = int((labels[test] == k).sum())
        subject_rows.append(summary)
        confusion_rows.extend(dict(subject=heldout,true_stage=a+1,predicted_stage=b+1,n_epochs=int(matrix[a,b]))
                              for a in range(5) for b in range(5))
        print(f'Held-out subject {heldout}: {len(train)} training, {len(test)} test epochs',flush=True)
    pooled_metrics = metrics(pooled); status = 'resource_pilot' if pilot_heldout is not None else 'ok'
    result = dict(status=status,task_id='AASMSTAGE-001',pipeline_id=PIPELINE,cv_scheme='leave-one-subject-out',
        n_subjects=len(folds),n_stages=5,stages=STAGES,n_epochs_total=pooled_metrics['n_epochs'],
        n_supported_classes=pooled_metrics['n_supported_classes'],accuracy=pooled_metrics['balanced_accuracy'],
        balanced_accuracy=pooled_metrics['balanced_accuracy'],overall_accuracy_for_reference=pooled_metrics['overall_accuracy'],
        cohen_kappa=pooled_metrics['kappa'],kappa_status=pooled_metrics['kappa_status'],per_class=pooled_metrics['per_class'])
    observed = dict(n_subjects=6,n_source_annotations=len(annotations),n_candidate_epochs=len(epochs),
        n_retained_epochs=len(retained),n_dropped_epochs=len(epochs)-len(retained),subjects=observations)
    metadata = dict(status=status,task_id='AASMSTAGE-001',pipeline_id=PIPELINE,dataset_id='sleep-edfx',dataset_version='1.0.0',
        source_manifest_sha256=SOURCE_SHA256,method_contract_sha256=METHOD_SHA256,
        source_sha256={r['path']:r['sha256'] for r in manifest['files']},method_contract=method,source_observed=observed,
        feature_dtype='float64',forest_input_dtype='float32',software_versions=dict(python=platform.python_version(),
            numpy=np.__version__,scipy=scipy.__version__,mne=mne.__version__,scikit_learn=sklearn.__version__))
    if pilot_heldout is not None:
        scope = dict(features_subjects=list(range(6)),fitted_heldout_subjects=folds)
        result['resource_pilot_scope'] = scope; metadata['resource_pilot_scope'] = scope
    feature_rows = []
    for i,key in enumerate(keys):
        row = dict(subject=int(key[0]),recording=1,onset_sample=int(key[2]),psd_sum_fpz_cz=float(power[i,0]),psd_sum_pz_oz=float(power[i,1]))
        row.update({k:float(v) for k,v in zip(method['features']['order'],features[i])}); feature_rows.append(row)
    tables = {'annotations.csv':annotations,'epochs.csv':epochs,'epoch_features.csv':feature_rows,
        'epoch_predictions.csv':prediction_rows,'per_subject.csv':subject_rows,'confusion_counts.csv':confusion_rows}
    for name,rows in tables.items():
        write_csv(output/name,rows,list(method['outputs'][name]['columns']))
    arrays.update(subject=subjects,recording=keys[:,1],onset_sample=keys[:,2],stage_id=labels,
        annotation_index=np.array([r['annotation_index'] for r in retained],np.int64),
        chunk_index=np.array([r['chunk_index'] for r in retained],np.int64),features=features,
        forest_input=features.astype(np.float32),psd_sum=power,probabilities=probability_all,prediction=prediction_all,
        metadata_json=np.array(json.dumps(metadata,allow_nan=False)),results_json=np.array(json.dumps(result,allow_nan=False)),
        annotations_json=np.array(json.dumps(annotations,allow_nan=False)),epochs_json=np.array(json.dumps(epochs,allow_nan=False)),
        pipeline_id=np.array(PIPELINE))
    with (private/'analysis_arrays.npz').open('xb') as stream:
        np.savez_compressed(stream,**arrays)
    write_json(output/'staging_results.json',result); write_json(output/'run_metadata.json',metadata)
    with (output/'findings.md').open('x') as stream:
        stream.write('# Collapsed-R&K sleep-staging method control\n\n'
            f'Status: {status}; held-out subjects {folds}; {result["n_epochs_total"]} test epochs. '
            f'Pooled balanced accuracy {result["balanced_accuracy"]:.9f}; epoch-weighted overall accuracy '
            f'{result["overall_accuracy_for_reference"]:.9f}; Cohen kappa {result["cohen_kappa"]}.\n\n'
            'The two accuracies weight classes and epochs differently; neither is inherently dishonest. '
            'The two-channel features are mean normalized Welch-bin heights, not integrated band fractions. '
            'Subjects, not serial epochs, are the held-out independent units. Original R&K3/4 stages were merged, '
            'not rescored under AASM. This small tutorial-derived method control does not reproduce a Kemp '
            'classifier or establish clinical generalization or frontier-agent difficulty.\n')
    return result


def failure(output, error):
    payload = dict(status='failed_precondition',task_id='AASMSTAGE-001',reason=str(error) or type(error).__name__)
    for name in ('run_metadata.json','staging_results.json'):
        if not (output/name).exists():
            write_json(output/name,payload)
    if not (output/'findings.md').exists():
        with (output/'findings.md').open('x') as stream:
            stream.write('# Failed precondition\n\n'+payload['reason']+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(os.environ.get('DATA_DIR','/app/data/aasmstage')))
    parser.add_argument('--method-contract',type=Path,default=Path(os.environ.get('METHOD_CONTRACT','/app/method_contract.json')))
    parser.add_argument('--output-dir',type=Path,default=Path(os.environ.get('OUTPUT_DIR','/app/output')))
    parser.add_argument('--private-dir',type=Path,default=Path(os.environ.get('PRIVATE_DIR','/app/oracle_private')))
    parser.add_argument('--pilot-heldout',type=int,choices=range(6))
    args = parser.parse_args(); prepared = False
    try:
        output,private = prepare_destinations(args.output_dir,args.private_dir,args.data_dir,args.method_contract)
        prepared = True
        result = run(args.data_dir,args.method_contract,output,private,args.pilot_heldout)
        print(json.dumps(result,allow_nan=False),flush=True)
        return 0
    except Exception as error:
        print(type(error).__name__+': '+(str(error) or type(error).__name__),file=sys.stderr,flush=True)
        if prepared:
            failure(output,error)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
