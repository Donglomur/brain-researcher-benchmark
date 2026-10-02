"""Fresh, source-authenticated LIFESPAN oracle; no grading-code imports."""
import argparse
import csv
import json
import os
from pathlib import Path
import platform
import signal
import sys
import warnings

import nibabel
import numpy as np
import scipy
import sklearn

import core
import source_reader as source

COHORT_COLUMNS = ['subject_id', 'cohort_index', 'left_path', 'right_path', 'left_sha256', 'right_sha256',
                  'phenotype_row_index', 'age_source', 'age_computational', 'sex', 'n_frames',
                  'n_constant_parcels', 'n_valid_edges', 'global_status', 'segregation_status']
PARCEL_COLUMNS = ['roi_index', 'hemisphere', 'annotation_id', 'label_name', 'vertex_count']
PARTITION_COLUMNS = ['roi_index', 'network_id', 'status']
SUMMARY_COLUMNS = ['subject_id', 'age', 'n_edges_expected', 'n_edges_defined', 'global_fisher_sum',
                   'global_connectivity', 'global_status', 'n_within_edges', 'n_between_edges',
                   'within_positive_sum', 'between_positive_sum', 'within_network_connectivity',
                   'between_network_connectivity', 'system_segregation', 'segregation_status']


def versions():
    return dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                scikit_learn=sklearn.__version__, nibabel=nibabel.__version__)


def check_runtime():
    expected = dict(numpy='2.1.3', scipy='1.14.1', scikit_learn='1.5.2', nibabel='5.3.2')
    actual = versions()
    source.require(sys.version_info[:2] == (3, 12) and all(actual[k] == v for k, v in expected.items()),
                   'Supplied oracle runtime differs from frozen public implementation')


def write_json(path, value):
    with source.safe_path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def write_npz(path, arrays):
    source.require(all(np.asarray(a).dtype.kind != 'O' for a in arrays.values()), 'Object array output refused')
    with source.safe_path(path).open('xb') as stream:
        np.savez_compressed(stream, **arrays)


def write_csv(path, columns, rows):
    with source.safe_path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def destinations(output_dir, private_dir, inputs):
    output, private = source.safe_path(output_dir), source.safe_path(private_dir)
    solution = source.safe_path(Path(__file__).absolute().parent)
    code_root = solution.parent if (solution.parent / 'task.toml').is_file() else solution
    protected = [source.safe_path(x) for x in inputs] + [code_root]
    for dest in (output, private):
        source.require(not dest.exists(), 'Fresh output/private directory required; no overwrite')
        for other in protected:
            source.require(dest != other and dest not in other.parents and other not in dest.parents,
                           'Output/private overlap with protected input/code refused')
    source.require(output != private and output not in private.parents and private not in output.parents,
                   'Output/private overlap refused')
    return output, private


def make_artifacts(inputs, ids, q, observed, analysis, pilot):
    parcels = inputs['parcels']
    vertex_blocks = inputs['membership']['lh'] + inputs['membership']['rh']
    s, frames, rois = q.shape
    arrays = dict(subject_id=np.asarray(ids), roi_index=np.arange(rois, dtype=np.int64),
                  subject_frame_offsets=np.arange(s + 1, dtype=np.int64) * frames,
                  frame_index=np.tile(np.arange(frames, dtype=np.int64), s), roi_timeseries=q.reshape(s * frames, rois),
                  vertex_offsets=np.r_[0, np.cumsum([len(v) for v in vertex_blocks], dtype=np.int64)],
                  vertex_index=np.concatenate(vertex_blocks))
    arrays.update({k: analysis[k] for k in ('parcel_status', 'edge_roi_index', 'edge_valid', 'raw_r',
                                           'fisher_z', 'group_valid', 'group_features')})
    cohort = []
    for i, subject in enumerate(ids):
        pheno = inputs['phenotype'][subject]
        row = dict(subject_id=subject, cohort_index=inputs['subject_ids'].index(subject),
                   phenotype_row_index=pheno['phenotype_row_index'], age_source=pheno['age_source'],
                   age_computational=pheno['age_computational'], sex=pheno['sex'], n_frames=frames,
                   n_constant_parcels=int(np.sum(analysis['parcel_status'][i] == 'constant')),
                   n_valid_edges=int(analysis['edge_valid'][i].sum()),
                   global_status=analysis['summary'][i]['global_status'], segregation_status=analysis['summary'][i]['segregation_status'])
        for hemi, prefix in [('lh', 'left'), ('rh', 'right')]:
            entry = inputs['sources'][(subject, hemi)]
            row[prefix + '_path'], row[prefix + '_sha256'] = entry['path'], entry['sha256']
        cohort.append(row)
    labels = analysis['fit']['labels']
    partition_rows = [dict(roi_index=i, network_id=None if labels is None else str(int(labels[i])),
                           status=analysis['partition']['status']) for i in range(rois)]
    metadata = dict(status='resource_pilot' if pilot else 'ok', method_contract_sha256=source.METHOD_SHA256,
                    source_manifest_sha256=source.SOURCE_SHA256, cohort_manifest_sha256=source.COHORT_SHA256,
                    dataset_id='nki_enhanced_surface', cohort_order=inputs['subject_ids'], roi_order=list(range(rois)),
                    counts=dict(n_subjects=s, n_parcels=rois, n_edges=len(analysis['edge_roi_index']),
                                n_frames_total=s * frames, n_constant_parcels_total=int(np.sum(analysis['parcel_status'] == 'constant')),
                                n_subjects_complete_connectome=int(np.sum(np.all(analysis['edge_valid'], axis=1)))),
                    source_files=[{k: row[k] for k in ('path', 'role', 'size_bytes', 'sha256')} for row in inputs['manifest']['files']],
                    software_versions=versions(), warnings=analysis['warnings'],
                    source_observed=dict(left_vertices=source.N_VERTICES, right_vertices=source.N_VERTICES,
                                         left_cortical_parcels=len(inputs['membership']['lh']),
                                         right_cortical_parcels=len(inputs['membership']['rh']), subjects=observed,
                                         header_timestep_literals=['1000.000000'], header_timing_unit=None,
                                         documented_tr_seconds=0.645, timing_policy='index_order_no_new_temporal_processing',
                                         annotation_labels=inputs['annotation_diagnostics']))
    if pilot:
        metadata['resource_pilot_scope'] = analysis['results']['resource_pilot_scope']
    return dict(cohort=cohort, parcels=parcels, arrays=arrays, partition_rows=partition_rows,
                partition=analysis['partition'], summary=analysis['summary'], results=analysis['results'], metadata=metadata)


def findings(results):
    records = []
    for name in ('overall_connectivity_vs_age', 'system_segregation_vs_age'):
        result = results[name]
        records.append(f"{name}: status={result['status']}" +
                       (f", signed Pearson r={result['pearson_r']:.9g}, two-sided p={result['p']:.9g}, CI={result['ci95']}."
                        if result['status'] == 'ok' else f", defined people={result['n_defined']}/{result['n_expected']}."))
    return ('This is a fixed historical NKI convenience-cohort method control, not a paper finding replication.\n\n' +
            '\n\n'.join(records) + '\n\nCross-sectional associations are not within-person aging or causal effects. '
            'The age-blind partition is learned on this same cohort; the plug-in interval does not propagate partition uncertainty. '
            'Sex, motion and nonlinear age are not adjusted. Header TimeStep1000 has no stated unit; no new temporal processing was applied.\n')


def emit(output, artifacts):
    write_csv(output / 'cohort.csv', COHORT_COLUMNS, artifacts['cohort'])
    write_csv(output / 'parcels.csv', PARCEL_COLUMNS, artifacts['parcels'])
    write_npz(output / 'connectome_primitives.npz', artifacts['arrays'])
    write_csv(output / 'roi_partition.csv', PARTITION_COLUMNS, artifacts['partition_rows'])
    write_json(output / 'partition.json', artifacts['partition'])
    write_csv(output / 'connectome_summary.csv', SUMMARY_COLUMNS, artifacts['summary'])
    write_json(output / 'results.json', artifacts['results'])
    write_json(output / 'run_metadata.json', artifacts['metadata'])
    with (output / 'findings.md').open('x', encoding='utf-8') as stream:
        stream.write(findings(artifacts['results']))
    source.require(sum(p.stat().st_size for p in output.iterdir()) <= 134_217_728, 'Public output exceeds declared byte cap')


def run(data_dir, method_path, cohort_path, output_dir, private_dir, *, pilot_first_subject=False):
    output, private = destinations(output_dir, private_dir, [data_dir, method_path, cohort_path])
    output.mkdir(parents=True, exist_ok=False)
    phase, completed = 'private_directory_creation', []
    caught_messages = []
    try:
        private.mkdir(parents=True, exist_ok=False)
        phase = 'runtime_authentication'
        check_runtime()
        phase = 'source_authentication_and_structure'
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            inputs = source.load_inputs(data_dir, method_path, cohort_path)
            ids = inputs['subject_ids'][:1] if pilot_first_subject else inputs['subject_ids']
            q_rows, observed = [], []
            phase = 'source_parcel_means'
            for subject in ids:
                q, before, description = source.read_subject(inputs, subject)
                write_npz(private / f'source_{subject}.npz', dict(roi_timeseries=q, mean_float64_before_storage=before,
                                                               subject_id=np.asarray(subject)))
                completed.append(subject)
                q_rows.append(q); observed.append(description)
            q_all = np.stack(q_rows)
            ages = [inputs['phenotype'][s]['age_computational'] for s in ids]
            phase = 'source_canonical_analysis'
            analysis = core.analyze(q_all, ages, ids, expected_subject_ids=inputs['subject_ids'],
                                    method_sha256=source.METHOD_SHA256, pilot=pilot_first_subject)
            caught_messages = [f'{w.category.__name__}: {w.message}' for w in caught]
        analysis['warnings'] = caught_messages + analysis['warnings']
        artifacts = make_artifacts(inputs, ids, q_all, observed, analysis, pilot_first_subject)
        phase = 'private_evidence'
        private_arrays = dict(artifacts['arrays'])
        private_arrays.update(age=np.asarray(ages), metadata_json=np.asarray(json.dumps(artifacts['metadata'], allow_nan=False)),
                              results_json=np.asarray(json.dumps(artifacts['results'], allow_nan=False)),
                              partition_json=np.asarray(json.dumps(artifacts['partition'], allow_nan=False)))
        fit = analysis['fit']
        if fit['labels'] is not None:
            private_arrays.update(kmeans_labels=fit['labels'], kmeans_centers=fit['centers'],
                                  kmeans_inertia=np.asarray(fit['inertia']), kmeans_n_iter=np.asarray(fit['n_iter']))
        write_npz(private / 'analysis_arrays.npz', private_arrays)
        write_json(private / 'fit_diagnostics.json', dict(status=fit['status'], n_iter=fit['n_iter'], inertia=fit['inertia'],
                                                        warnings=fit['warnings'], method_contract_sha256=source.METHOD_SHA256))
        phase = 'public_artifacts'
        emit(output, artifacts)
        return artifacts
    except BaseException as error:
        # Exclusive marker overrides any completed success files; preserve all evidence.
        if 'caught' in locals():
            caught_messages = [f'{w.category.__name__}: {w.message}' for w in caught]
        marker = output / 'failure_report.json'
        if not marker.exists() and not marker.is_symlink():
            write_json(marker, dict(status='failed_numerical' if isinstance(error, ArithmeticError) else 'failed_precondition',
                                    phase=phase, reason=str(error)[:1500], error_type=type(error).__name__,
                                    completed_subject_ids=completed, warnings=caught_messages))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('/app/data/lifespan'))
    parser.add_argument('--method-contract', type=Path, default=Path('/app/method_contract.json'))
    parser.add_argument('--cohort-manifest', type=Path, default=Path('/app/cohort_manifest.json'))
    parser.add_argument('--output-dir', type=Path, default=Path(os.environ.get('OUTPUT_DIR', '/app/output')))
    parser.add_argument('--private-dir', type=Path, default=Path('/app/oracle_private'))
    parser.add_argument('--pilot-first-subject', action='store_true')
    args = parser.parse_args(argv)
    def timeout(signum, frame):
        raise TimeoutError('Oracle interrupted by runtime deadline')
    signal.signal(signal.SIGTERM, timeout)
    try:
        result = run(args.data_dir, args.method_contract, args.cohort_manifest, args.output_dir,
                     args.private_dir, pilot_first_subject=args.pilot_first_subject)
    except Exception as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1
    print(json.dumps(dict(status=result['results']['status'], n_subjects=len(result['cohort']),
                          n_rois=len(result['parcels']), n_edges=len(result['arrays']['edge_roi_index']))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
