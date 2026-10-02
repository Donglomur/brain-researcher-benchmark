"""External FCVAR source-only oracle writer; import-safe, no source fetches."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import warnings

import numpy as np
import signal_kernel as kernel
import source_reader as source

COHORT_COLUMNS = ('subject', 'source_order', 'site', 'n_timepoints', 'tr_sec',
    'bold_path', 'confounds_path', 'n_global_active_rois', 'n_edges', 'status')
VARIABILITY_COLUMNS = ('subject', 'window_tr', 'n_windows', 'n_rois', 'n_edges',
    'observed_status', 'mean_edge_sd', 'n_null_expected', 'n_null_defined',
    'null_mean_status', 'mean_edge_sd_null', 'ratio_status', 'observed_over_null_ratio',
    'inference_status', 'n_exceedances', 'p_numerator', 'p_denominator', 'p_value', 'significant')
DRAW_COLUMNS = ('subject', 'window_tr', 'surrogate_id', 'status', 'mean_edge_sd', 'exceeds_observed')


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def prepare_destinations(output, private, report, protected):
    destinations = [source.safe_path(p) for p in (output, private, report) if p is not None]
    protected = [source.safe_path(p) for p in protected]
    for i, path in enumerate(destinations):
        kernel.require(not os.path.lexists(path) and path.parent.is_dir(), 'fresh destination with existing parent required')
        kernel.require(all(disjoint(path, q) for q in protected + destinations[:i]),
                       'destination overlaps protected input/code/evidence')
    output.mkdir(mode=0o700)
    if private is not None:
        private.mkdir(mode=0o700)


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def write_npz(path, arrays):
    with Path(path).open('xb') as handle:
        np.savez_compressed(handle, **arrays)


def write_csv(path, columns, rows):
    def cell(value):
        if value is None: return ''
        if isinstance(value, (bool, np.bool_)): return 'true' if value else 'false'
        if isinstance(value, np.generic): return value.item()
        return value
    with Path(path).open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='raise')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: cell(row[key]) for key in columns})


def versions():
    return dict(python=platform.python_version(), **{name: importlib.metadata.version(name)
        for name in ('numpy', 'scipy', 'nibabel', 'nilearn')})


class Progress:
    def __init__(self):
        self.last = -float('inf')

    def __call__(self, message, force=False):
        now = time.monotonic()
        if force or now - self.last >= 30:
            print('FCVAR: ' + message, file=sys.stderr, flush=True)
            self.last = now


def evidence_arrays(basis, results):
    ids = basis['participant_ids']
    persons = basis['persons']
    arrays = dict(participant_ids=np.asarray(ids), roi_ids=np.asarray(basis['roi_ids'], dtype=np.int64),
        roi_labels=np.asarray(basis['roi_labels']),
        frame_subject=np.concatenate([np.full(persons[sid]['n_frames'], sid) for sid in ids]),
        frame_index=np.concatenate([np.arange(persons[sid]['n_frames'], dtype=np.int64) for sid in ids]),
        raw_roi_mean=np.concatenate([persons[sid]['raw'] for sid in ids]),
        clean_roi_series=np.concatenate([persons[sid]['clean'] for sid in ids]),
        geometry_present=np.stack([persons[sid]['geometry_present'] for sid in ids]),
        n_voxels=np.stack([persons[sid]['n_voxels'] for sid in ids]),
        support_sha256=np.stack([persons[sid]['support_sha256'] for sid in ids]),
        roi_active=np.stack([persons[sid]['active'] for sid in ids]),
        surrogate_ids=np.arange(kernel.N_DRAWS, dtype=np.int64))
    for name in ('raw_sample_sd', 'prestandardization_centered_l2', 'activity_threshold', 'full_clean_centered_l2'):
        arrays[name] = np.stack([persons[sid][name] for sid in ids])
    phase_subject, phase_window, frequency_index, angles = [], [], [], []
    by_id = {row['subject']: row for row in results}
    for sid in ids:
        if sid not in by_id:
            continue
        for w in kernel.WINDOWS:
            p = by_id[sid]['phases'][w]
            phase_subject.extend([sid]*p.shape[1])
            phase_window.extend([w]*p.shape[1])
            frequency_index.extend(range(p.shape[1]))
            angles.append(p.T)
    arrays.update(phase_subject=np.asarray(phase_subject, dtype='<U7'),
        phase_window=np.asarray(phase_window, dtype=np.int64),
        frequency_index=np.asarray(frequency_index, dtype=np.int64),
        phase_angles=np.concatenate(angles, axis=0) if angles else np.empty((0, kernel.N_DRAWS)))
    return arrays


def compute(args):
    output = source.safe_path(args.output_dir)
    private = source.safe_path(args.private_dir) if args.private_dir else None
    report = source.safe_path(args.report) if args.report else None
    data, method, schema = map(source.safe_path, (args.data_dir, args.contract_path, args.schema_path))
    code = source.safe_path(Path(__file__).absolute().parent)
    task_root = code.parent if (code.parent / 'task.toml').is_file() else code
    protected = [data, method, schema, task_root, source.safe_path(Path(source.__file__).absolute()),
                 source.safe_path(Path(kernel.__file__).absolute())]
    prepare_destinations(output, private, report, protected)
    start = time.monotonic()
    caught = []
    progress = Progress()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            seed = kernel.integer(args.seed, 0, 2**32-1, 'seed')
            progress('authenticate complete source inventory', force=True)
            inputs = source.authenticate(data, method, schema)
            def checkpoint(sid, person):
                if private is not None:
                    arrays = {name: value for name, value in person.items() if isinstance(value, np.ndarray)}
                    write_npz(private / (sid + '_source_primitives.npz'), arrays)
            selected = [source.FIXED_IDS[0]] if args.pilot_first_person else None
            basis = source.load(inputs, subjects=selected, progress=progress, on_person=checkpoint)
            results = []
            if not args.pilot_first_person:
                for sid in basis['participant_ids']:
                    progress('shared-phase replay ' + sid)
                    person = basis['persons'][sid]
                    result = kernel.analyze_subject(person['clean'], person['clean'], person['active'], sid, seed)
                    results.append(result)
                    if private is not None:
                        write_json(private / (sid + '_statistics.json'),
                                   {name: result[name] for name in ('subject', 'seed', 'windows', 'surrogates')})
                dynamics = kernel.summarize_subjects(results, list(source.FIXED_IDS))
            else:
                dynamics = dict(schema_version='fcvar-results-v3', status='resource_pilot',
                    n_subjects=len(basis['participant_ids']), seed=seed, window_lengths_tr=list(kernel.WINDOWS),
                    primary_window_tr=30, step_tr=kernel.STEP, n_surrogates=kernel.N_DRAWS,
                    windows=None, resource_pilot_scope=dict(participant_ids=basis['participant_ids'],
                        all_source_files_authenticated=True, all_headers_and_confounds_checked=True,
                        primitive_extraction_and_cleaning_only=True, phase_inference_computed=False))
            status = 'resource_pilot' if args.pilot_first_person else 'ok'
            cohort, diagnostics = [], {}
            for sid in basis['participant_ids']:
                person = basis['persons'][sid]
                n_active = int(person['active'].sum())
                n_edges = n_active*(n_active-1)//2
                cohort.append(dict(subject=sid, source_order=list(source.FIXED_IDS).index(sid), site=person['site'],
                    n_timepoints=person['n_frames'], tr_sec=person['tr_sec'], bold_path=person['source_paths']['bold'],
                    confounds_path=person['source_paths']['confounds'], n_global_active_rois=n_active,
                    n_edges=n_edges, status='ok'))
                diagnostics[sid] = dict(cleaning_rank=person['cleaning_rank'], n_global_active_rois=n_active, n_edges=n_edges)
            metadata = dict(schema_version='fcvar-metadata-v3', task_id='FCVAR-001', status=status, seed=seed,
                **basis['pins'], source_files=basis['source_files'], source_observed=basis['source_observed'],
                analysis_observed=dict(persons=diagnostics), software_versions=versions())
            if args.pilot_first_person:
                metadata['resource_pilot_scope'] = dynamics['resource_pilot_scope']
            write_csv(output / 'cohort.csv', COHORT_COLUMNS, cohort)
            write_npz(output / 'roi_evidence.npz', evidence_arrays(basis, results))
            write_csv(output / 'variability.csv', VARIABILITY_COLUMNS, [row for r in results for row in r['windows']])
            write_csv(output / 'surrogate_statistics.csv', DRAW_COLUMNS, [row for r in results for row in r['surrogates']])
            write_json(output / 'dynamics.json', dynamics)
            if args.pilot_first_person:
                findings = 'Fixed-first-person extraction/cleaning resource pilot. No window variability or surrogate rank was computed.\n'
            else:
                lines = ['# Conditional shared-phase comparison', '',
                    f'All {len(cohort)} preselected public recordings are retained with explicit metric support.', '']
                for row in dynamics['windows']:
                    ratio, p = row['mean_subject_observed_over_null_ratio'], row['median_subject_p']
                    lines.append(f"W={row['window_tr']} frames: mean personal ratio={ratio['value']} "
                        f"({ratio['n_defined']}/{ratio['n_expected']} defined); median conditional rank={p['value']} "
                        f"({p['n_defined']}/{p['n_expected']} defined).")
                lines.extend(['', 'These are finite-record spectrum-conditioned method-control results, not an Allen replication, '
                    'a general stationarity test, a neural/causal mechanism, an ADHD population conclusion, or difficulty calibration. '
                    'Undefined support is not evidence of either a positive or negative scientific effect.'])
                findings = '\n'.join(lines) + '\n'
            with (output / 'findings.md').open('x', encoding='utf-8') as handle:
                handle.write(findings)
        metadata['warnings'] = [str(w.message) for w in caught]
        write_json(output / 'run_metadata.json', metadata)
        inventory = {path.name: dict(size_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                     for path in sorted(output.iterdir())}
        receipt = dict(status=status, elapsed_s=time.monotonic()-start, n_subjects=len(cohort),
            n_frames=sum(row['n_timepoints'] for row in cohort), n_rois=48, seed=seed,
            observed_rows=sum(len(r['windows']) for r in results), surrogate_rows=sum(len(r['surrogates']) for r in results),
            warnings=[dict(category=w.category.__name__, message=str(w.message)) for w in caught],
            files=inventory, **basis['pins'])
        if report is not None:
            write_json(report, receipt)
        progress('finished ' + status, force=True)
        return receipt
    except Exception as exc:
        failure = dict(status='failed_precondition', reason=f'{type(exc).__name__}: {exc}',
            elapsed_s=time.monotonic()-start,
            warnings=[dict(category=w.category.__name__, message=str(w.message)) for w in caught])
        write_json(output / 'failure_report.json', failure)
        if report is not None and not os.path.lexists(report):
            write_json(report, failure)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR', '/app/data/fcvar'))
    parser.add_argument('--contract-path', default=os.environ.get('METHOD_CONTRACT', '/app/method_contract.json'))
    parser.add_argument('--schema-path', default=os.environ.get('OUTPUT_SCHEMA', '/app/output_schema.json'))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR', '/app/output'))
    parser.add_argument('--private-dir')
    parser.add_argument('--report')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--pilot-first-person', action='store_true')
    parser.add_argument('--print-contract', action='store_true')
    args = parser.parse_args()
    try:
        if args.print_contract:
            raw = source.stable_bytes(args.contract_path, 2*1024**2)
            source.strict_json(raw)
            sys.stdout.write(raw.decode('utf-8'))
        else:
            print(json.dumps(compute(args), sort_keys=True, allow_nan=False))
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
