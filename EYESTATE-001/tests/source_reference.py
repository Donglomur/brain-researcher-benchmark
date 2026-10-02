"""Runtime original-source reconstruction. No numerical answer bank or oracle imports.

Importing this module performs no source I/O or numerical source processing.
"""
from collections import Counter
import csv
from functools import lru_cache
import hashlib
from pathlib import Path
import stat
import numpy as np
import io_contract as io
import metric_contract as m

METHOD_SHA256 = '2cc71a311a25ec5de5bf14d5e2d10097b7e609eba93ea8be273f63f7de08a4a0'
SOURCE_SHA256 = 'd4e930b84667e58831880100039cde688d56ccd0ff8c509f0f363fd1c4685aeb'


def inputs(source_dir, method_path):
    m.require(METHOD_SHA256 is not None and SOURCE_SHA256 is not None, 'source/method freeze pending')
    root = io.safe_path(source_dir); method_path = io.regular(method_path)
    m.require(root.is_dir(), 'source directory')
    m.require(io.sha256(method_path) == METHOD_SHA256, 'public method fingerprint')
    manifest_path = root / 'source_manifest.json'
    m.require(io.sha256(manifest_path) == SOURCE_SHA256, 'source manifest fingerprint')
    method, manifest = io.read_json(method_path), io.read_json(manifest_path)
    files = manifest['files']; names = [r['path'] for r in files]
    m.require(len(names) == len(set(names)), 'unique source paths')
    expected_files = set(names) | {'source_manifest.json'}
    expected_dirs = {str(parent) for name in names for parent in Path(name).parents if str(parent) != '.'}
    observed_files, observed_dirs = set(), set()
    for path in root.rglob('*'):
        io.safe_path(path)
        rel = path.relative_to(root).as_posix()
        if path.is_dir(): observed_dirs.add(rel)
        else: io.regular(path); observed_files.add(rel)
    m.require(observed_files == expected_files and observed_dirs == expected_dirs, 'exact source inventory')
    for record in files:
        path = io.regular(root / record['path'])
        m.require(root in path.parents and path.stat().st_size == record['size_bytes'] and
                  io.sha256(path) == record['sha256'], 'source member bytes')
    return root, method, manifest


def source_cohort(root, method, manifest):
    phenotype = [r for r in manifest['files'] if r['role'] == 'phenotype']
    m.require(len(phenotype) == 1, 'one original phenotype source')
    with io.regular(root / phenotype[0]['path']).open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    m.require(len(rows) == method['source']['phenotype_rows'], 'complete original phenotype rows')
    by_file = {r['file_id']: r for r in manifest['files'] if r['role'] == 'roi_timeseries'}
    m.require(len(by_file) == sum(r['role'] == 'roi_timeseries' for r in manifest['files']), 'unique derivative FILE_ID')
    ledger, features, shrinkages, subject_ids, row_ids, labels, sites = [], [], [], [], [], [], []
    all_ids = set(); used = set()
    for row_index, row in enumerate(rows):
        subject_id = io.integer(row['SUB_ID']); file_id, site = row['FILE_ID'], row['SITE_ID']
        m.require(subject_id not in all_ids and file_id and site, 'original unique subject and exact source strings')
        all_ids.add(subject_id)
        eye = io.integer(row['EYE_STATUS_AT_SCAN'])
        result = dict(phenotype_row=row_index, subject_id=subject_id, file_id=file_id, site=site, eye_code=eye,
                      label=1 if eye == 1 else 0 if eye == 2 else None, source_path=None, source_sha256=None,
                      n_timepoints=None, n_rois=None, n_constant_rois=None, n_low_sd_rois=None,
                      included=False, exclusion_reason='unavailable_derivative', selected_index=None)
        if file_id != 'no_filename':
            m.require(file_id in by_file, 'named source derivative is required')
            record = by_file[file_id]; used.add(file_id)
            m.require(io.integer(record['subject_id']) == subject_id and
                      io.integer(record['phenotype_row_index']) == row_index, 'manifest original subject/row binding')
            with io.regular(root / record['path']).open() as stream:
                header = stream.readline().rstrip('\r\n')
            m.require(header == '\t'.join('#' + str(i) for i in range(1, 201)) and
                      hashlib.sha256(header.encode('utf-8')).hexdigest() == method['source']['roi_header_sha256'],
                      'original source ROI column header')
            values = np.loadtxt(io.regular(root / record['path']), dtype=np.float64)
            m.require(values.ndim == 2 and len(values) > 0 and np.isfinite(values).all(), 'malformed/nonfinite selected original source')
            n, p = values.shape
            constant_count = int(np.count_nonzero(np.all(values == values[0], axis=0)))
            low_sd_count = int(np.count_nonzero((values - values.mean(axis=0)).std(axis=0) < np.finfo(float).eps))
            result.update(source_path=record['path'], source_sha256=record['sha256'], n_timepoints=n, n_rois=p,
                          n_constant_rois=constant_count, n_low_sd_rois=low_sd_count)
            reason = 'invalid_eye_code' if eye not in (1, 2) else 'wrong_roi_count' if p != 200 else 'insufficient_frames' if n <= 50 else 'included'
            m.require(reason == 'included', 'frozen full available-source eligibility')
            result['exclusion_reason'] = reason
            if reason == 'included':
                result.update(included=True, selected_index=len(features))
                fc = m.connectivity(values)
                features.append(fc['correlation']); shrinkages.append(fc['shrinkage'])
                subject_ids.append(subject_id); row_ids.append(row_index); labels.append(result['label']); sites.append(site)
        ledger.append(result)
    m.require(used == set(by_file), 'all source derivative members accounted for')
    m.require(sum(r['exclusion_reason'] == 'unavailable_derivative' for r in ledger) == method['source']['known_no_filename_rows'],
              'complete unavailable-source accounting')
    m.require(len(features) > 0, 'nonempty selected cohort')
    ref = dict(cohort=ledger, features=np.asarray(features), shrinkage=np.asarray(shrinkages),
                row_ids=np.asarray(row_ids, dtype=np.int64), subject_ids=np.asarray(subject_ids, dtype=np.int64),
                labels=np.asarray(labels, dtype=np.int64), sites=np.asarray(sites))
    validate_structure(ref, method)
    return ref


def validate_structure(ref, method):
    selected = [r for r in ref['cohort'] if r['included']]
    counts = [r['n_constant_rois'] for r in selected]
    frames = [r['n_timepoints'] for r in selected]
    actual = dict(n_selected=len(selected), n_sites=len(set(ref['sites'])),
                  n_open=int(np.sum(ref['labels'] == 1)), n_closed=int(np.sum(ref['labels'] == 0)),
                  frame_min=min(frames), frame_max=max(frames), n_people_with_constant_rois=sum(v > 0 for v in counts),
                  max_constant_rois=max(counts), all_nonfinite_count=0,
                  constant_counts_equal_below_epsilon_counts=all(r['n_constant_rois'] == r['n_low_sd_rois'] for r in selected))
    io.match(actual, method['source']['observed_structure_before_features'], closed=True)


def observed_metadata(ref, method):
    selected = [r for r in ref['cohort'] if r['included']]
    named = [r for r in ref['cohort'] if r['source_path'] is not None]
    sites = sorted(set(ref['sites']))
    frame_counts = Counter(r['n_timepoints'] for r in selected)
    roi_counts = Counter(r['n_rois'] for r in named)
    constant_counts = Counter(r['n_constant_rois'] for r in selected)
    return dict(n_phenotype_rows=len(ref['cohort']), n_no_filename=len(ref['cohort']) - len(named),
                n_named_derivatives=len(named), n_selected=len(selected), n_features=19900,
                selected_site_ids=[str(s) for s in sites],
                site_support=[dict(site=str(s), n_open=int(np.sum((ref['sites'] == s) & (ref['labels'] == 1))),
                                   n_closed=int(np.sum((ref['sites'] == s) & (ref['labels'] == 0)))) for s in sites],
                frame_count_histogram=[dict(n_timepoints=k, n_subjects=v) for k, v in sorted(frame_counts.items())],
                roi_count_histogram=[dict(n_rois=k, n_subjects=v) for k, v in sorted(roi_counts.items())],
                constant_roi_count_histogram=[dict(n_constant_rois=k, n_subjects=v) for k, v in sorted(constant_counts.items())],
                source_column_convention=method['source']['source_column_convention'])


def source_stat_snapshot(root):
    # Original inputs are mounted read-only. The snapshot additionally detects
    # accidental changes before reusing a verified in-process reconstruction.
    rows = []
    for p in [root, *sorted(root.rglob('*'))]:
        st = p.lstat()
        m.require(stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode), 'source cache special file or symlink')
        rows.append((str(p.relative_to(root)), st.st_mode, st.st_dev, st.st_ino,
                     st.st_size, st.st_mtime_ns, st.st_ctime_ns))
    return tuple(rows)


@lru_cache(maxsize=1)
def _construct(source_dir, method_path, method_pin, source_pin):
    root, method, manifest = inputs(source_dir, method_path)
    ref = source_cohort(root, method, manifest)
    ref['method'] = method; ref['manifest'] = manifest
    ref['source_sha256'] = {r['path']: r['sha256'] for r in manifest['files']}
    ref['folds'] = m.make_folds(ref['labels'], ref['sites'])
    ref['scalers'] = {(f['scheme'], f['fold_id']): m.scale_training(ref['features'][f['train']]) for f in ref['folds']}
    ref['source_observed'] = observed_metadata(ref, method)
    ref['root'] = root; ref['snapshot'] = source_stat_snapshot(root)
    for value in ref.values():
        if isinstance(value, np.ndarray): value.setflags(write=False)
    for scaler in ref['scalers'].values():
        for value in scaler.values(): value.setflags(write=False)
    return ref


def load_reference(source_dir='/app/data/eyestate', method_path='/app/method_contract.json'):
    root = io.safe_path(source_dir); path = io.regular(method_path)
    m.require(METHOD_SHA256 is not None and SOURCE_SHA256 is not None, 'source/method freeze pending')
    # Always reauthenticate bytes and the closed inventory before cache reuse.
    # stat timestamps are supplementary diagnostics, not an identity substitute.
    inputs(root, path)
    ref = _construct(str(root), str(path), METHOD_SHA256, SOURCE_SHA256)
    m.require(source_stat_snapshot(root) == ref['snapshot'], 'immutable original source cache inputs changed')
    return ref


def destinations(source_dir, method_path, output, report):
    root = io.safe_path(source_dir); method = io.safe_path(method_path)
    paths = [io.safe_path(output), io.safe_path(report)]
    m.require(paths[0] != paths[1] and not any(a in b.parents for a, b in (paths, paths[::-1])),
              'distinct evidence files without parent overlap')
    for path in paths:
        m.require(not path.exists(), 'preserve existing evidence')
        m.require(path != root and root not in path.parents and path not in root.parents and
                  path != method and path not in method.parents, 'evidence must be outside source and method inputs')
    return paths


def write_source_receipt(ref, output, report, status, elapsed_seconds):
    """External audit evidence only; the runtime grader never loads this archive."""
    import json
    folds = ref['folds']; membership = np.empty((2, len(ref['labels'])), dtype=np.int64)
    for fold in folds:
        membership[0 if fold['scheme'] == 'loso' else 1, fold['test']] = fold['fold_id']
    metadata = dict(status=status, method_contract_sha256=METHOD_SHA256, source_manifest_sha256=SOURCE_SHA256,
                    source_sha256=ref['source_sha256'], source_observed=ref['source_observed'],
                    scope='all authenticated source features and deterministic scalers; no model fitting or output-bank grading')
    arrays = dict(phenotype_row=ref['row_ids'], subject_id=ref['subject_ids'], labels=ref['labels'], sites=ref['sites'],
                  feature_index=np.arange(ref['features'].shape[1]), roi_i=np.tril_indices(200, -1)[0],
                  roi_j=np.tril_indices(200, -1)[1], correlation=ref['features'], shrinkage=ref['shrinkage'],
                  fold_membership=membership, model_scheme=np.array([f['scheme'] for f in folds]),
                  model_fold_id=np.array([f['fold_id'] for f in folds]),
                  cohort_json=np.array(json.dumps(ref['cohort'], allow_nan=False)),
                  metadata_json=np.array(json.dumps(metadata, allow_nan=False)))
    for field in ('mean', 'variance', 'scale', 'constant'):
        arrays['scaler_' + field] = np.array([ref['scalers'][(f['scheme'], f['fold_id'])][field] for f in folds])
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream: np.savez_compressed(stream, **arrays)
    receipt = dict(metadata, elapsed_seconds=elapsed_seconds, output=str(output), output_sha256=io.sha256(output),
                   output_size_bytes=output.stat().st_size, n_features=list(ref['features'].shape), n_folds=len(folds),
                   implementation_files={p.name: io.sha256(p) for p in [Path(__file__), Path(m.__file__), Path(io.__file__)]},
                   independence='Original text reader and manual Ledoit-Wolf/scaler/SKF arithmetic. No oracle, checker, historical bank or fitted parameters are construction inputs. Validator shares these canonical arithmetic helpers.')
    with report.open('x') as stream: json.dump(receipt, stream, indent=2, allow_nan=False); stream.write('\n')
    return receipt


def main():
    import argparse
    import json
    import time
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', default='/app/data/eyestate')
    parser.add_argument('--method-contract', default='/app/method_contract.json')
    parser.add_argument('--output', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--pilot', action='store_true', help='Marks resource pilot; still reconstructs the full source feature/scaler basis, and never fits models.')
    args = parser.parse_args()
    output, report = destinations(args.source_dir, args.method_contract, args.output, args.report)
    started = time.monotonic()
    try:
        ref = load_reference(args.source_dir, args.method_contract)
        receipt = write_source_receipt(ref, output, report, 'resource_pilot' if args.pilot else 'ok', time.monotonic() - started)
    except Exception as exc:
        report.parent.mkdir(parents=True, exist_ok=True)
        if not report.exists():
            with report.open('x') as stream:
                json.dump(dict(status='failed_precondition', reason=f'{type(exc).__name__}: {exc}',
                               elapsed_seconds=time.monotonic() - started, method_contract_sha256=METHOD_SHA256,
                               source_manifest_sha256=SOURCE_SHA256), stream, indent=2, allow_nan=False)
        raise
    print(json.dumps(receipt, allow_nan=False))


if __name__ == '__main__':
    main()
