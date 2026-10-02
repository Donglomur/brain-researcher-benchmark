"""External prospective TASKFC oracle writer. Import performs no source I/O.

Complete mode processes the fixed ten-person source. The first-person resource
pilot computes source/design/residual primitives only, never r/z/group endpoints.
Runtime and absolute paths belong solely in external receipts, not public files.
"""
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
import oracle_core as core
import source_reader as source


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def prepare_destinations(output, private, report, protected):
    paths = [source.safe_path(p) for p in (output, private, report) if p is not None]
    protected = [source.safe_path(p) for p in protected]
    for i, path in enumerate(paths):
        core.need(not os.path.lexists(path) and path.parent.is_dir(), 'fresh_destination_existing_parent')
        core.need(all(disjoint(path, p) for p in protected+paths[:i]), 'overlapping_input_output')
    output.mkdir(mode=0o700)
    if private is not None:
        private.mkdir(mode=0o700)


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')


def write_npz(path, arrays):
    with Path(path).open('xb') as handle:
        np.savez_compressed(handle, **arrays)


def write_csv(path, columns, rows):
    with Path(path).open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='raise')
        writer.writeheader()
        writer.writerows(rows)


def versions():
    return dict(python=platform.python_version(), **{n: importlib.metadata.version(n)
                for n in ('numpy', 'scipy', 'nibabel', 'nilearn')})


def pack_arrays(basis):
    ids, persons = basis['participant_ids'], basis['participants']
    max_drift = max(len(persons[s]['designs']['nuisance_names'])-7 for s in ids)
    columns = ('intercept',)+tuple(f'drift_{i+1}' for i in range(max_drift))+core.MOTION_NAMES+core.TASK_NAMES
    included = np.zeros((len(ids), 2, len(columns)), dtype=bool)
    frames, frame_ids, times, raw, design, residuals = [], [], [], [], [], []
    for i, sid in enumerate(ids):
        person, d = persons[sid], persons[sid]['designs']
        n = len(person['raw'])
        matrix = np.zeros((n, len(columns)), dtype=np.float64)
        for j, name in enumerate(d['full_names']):
            matrix[:, columns.index(name)] = d['full_design'][:, j]
        for arm, names in enumerate((d['nuisance_names'], d['full_names'])):
            for name in names:
                included[i, arm, columns.index(name)] = True
        frames.append(d['frame_indices']); frame_ids.extend([sid]*n)
        times.append(d['frame_times']); raw.append(person['raw']); design.append(matrix)
        residuals.append(person['residuals'])
    return dict(participant_ids=np.asarray(ids), roi_ids=np.asarray(core.ROI_NAMES),
                model_ids=np.asarray(core.MODEL_NAMES), design_column_ids=np.asarray(columns),
                frame_participant_id=np.asarray(frame_ids), source_frame_index=np.concatenate(frames),
                frame_time_s=np.concatenate(times), roi_signals=np.concatenate(raw),
                design_values=np.concatenate(design), design_included=included,
                residuals=np.concatenate(residuals))


def analysis_records(basis):
    result = []
    for sid in basis['participant_ids']:
        person = basis['participants'][sid]
        models = []
        names = (person['designs']['nuisance_names'], person['designs']['full_names'])
        for arm, model in enumerate(core.MODEL_NAMES):
            fit, support = person['fits'][arm], person['support'][arm]
            models.append(dict(model_id=model, column_ids=list(names[arm]), rank=fit['rank'],
                residual_df=fit['residual_df'], singular_values=fit['singular_values'].tolist(),
                rank_cutoff=fit['rank_threshold'], roi_support=[dict(roi_id=roi,
                    raw_sample_sd=float(support['raw_sample_sd'][j]),
                    residual_centered_l2=float(support['residual_centered_l2'][j]),
                    activity_threshold=float(support['activity_threshold'][j]),
                    active=bool(support['active'][j])) for j, roi in enumerate(core.ROI_NAMES)]))
        result.append(dict(subject=sid, models=models))
    return result


def pilot_summary():
    return dict(schema_version='taskfc-results-v2', status='resource_pilot', n_subjects=1,
                region_a=core.ROI_NAMES[0], region_b=core.ROI_NAMES[1],
                raw=None, background=None, difference_of_group_fisher_mean_r=None,
                paired_z_sensitivity=None, resource_pilot_scope=dict(
                    participant_ids=[source.PARTICIPANTS[0]], n_authenticated_source_files=48,
                    n_structural_participants=10, endpoints_computed=False))


def emit(output, private, inputs, basis, pilot):
    arrays = pack_arrays(basis)
    if private is not None:
        write_npz(private / 'analysis_arrays.npz', arrays | dict(
            canonical_active=np.stack([basis['participants'][s]['active'] for s in basis['participant_ids']])))
        write_json(private / 'analysis_diagnostics.json', analysis_records(basis))
    if pilot:
        result, connectivity = pilot_summary(), []
    else:
        core.need(basis['participant_ids'] == list(source.PARTICIPANTS), 'complete_oracle_cohort')
        replay = core.derive([basis['participants'][s]['residuals'] for s in source.PARTICIPANTS],
                             [basis['participants'][s]['active'] for s in source.PARTICIPANTS],
                             source.PARTICIPANTS, n_expected=10)
        connectivity = replay.pop('rows')
        result = dict(schema_version='taskfc-results-v2', status='complete', **replay)
    write_npz(output / 'model_arrays.npz', arrays)
    for filename, rows in (('cohort.csv', basis['cohort']), ('events.csv', basis['events']),
                           ('connectivity.csv', connectivity)):
        fields = list(inputs['schema']['artifacts'][filename]['required_columns'])
        write_csv(output / filename, fields, rows)
    write_json(output / 'connectivity_summary.json', result)
    metadata = dict(schema_version='taskfc-metadata-v2', task_id='TASKFC-001',
                    status='resource_pilot' if pilot else 'ok', **inputs['pins'],
                    source_files=[{k: row.get(k) for k in ('path', 'role', 'participant_id', 'size_bytes', 'sha256')}
                                  for row in inputs['manifest']['files']],
                    source_observed=basis['source_observed'], analysis_observed=analysis_records(basis),
                    software_versions=versions())
    if pilot:
        metadata['resource_pilot_scope'] = result['resource_pilot_scope']
        text = ('First-person resource pilot: authenticated all original members and inspected all ten '
                'structural records, but extracted/fitted only sub-01 primitives. No correlation, Fisher '
                'transform, paired statistic or group endpoint was computed.\n')
    else:
        pair = result['paired_z_sensitivity']
        text = (f"All ten released participants are reported. Complete-pair support: {pair['n_defined']}/10. "
                f"Mean nuisance-only minus canonical-Glover residual Fisher z: "
                f"{pair['mean_raw_minus_background_z']} ({pair['status']}); 95% plug-in paired CI: {pair['ci95']}.\n\n"
                'This is whole-run sensitivity of two fixed occipital sphere measurements to a canonical '
                'task-response model. Neither estimate identifies intrinsic or causal coupling; a change '
                'does not establish successful artifact removal. This is not a reproduction of FIR, HCP, '
                'simulation ground truth, a population claim or evidence of benchmark difficulty. '
                'Undefined measurements retain their participants and complete-denominator null summaries.\n')
    with (output / 'findings.md').open('x', encoding='utf-8') as handle:
        handle.write(text)
    return metadata


def compute(args):
    output = source.safe_path(args.output_dir)
    private = source.safe_path(args.private_dir) if args.private_dir else None
    report = source.safe_path(args.report) if args.report else None
    data, manifest, method, schema = map(source.safe_path,
        (args.data_dir, args.manifest_path, args.contract_path, args.schema_path))
    code = source.safe_path(Path(__file__).absolute().parent)
    code_root = code.parent if (code.parent / 'task.toml').is_file() else code
    prepare_destinations(output, private, report, [data, manifest, method, schema, code_root])
    start, caught = time.monotonic(), []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            inputs = source.authenticate(data, manifest, method, schema)
            basis = source.load_primitives(inputs, [source.PARTICIPANTS[0]] if args.pilot_first_subject else None)
            metadata = emit(output, private, inputs, basis, args.pilot_first_subject)
        metadata['warnings'] = [str(w.message) for w in caught]
        write_json(output / 'run_metadata.json', metadata)
        inventory = {p.name: dict(size_bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                     for p in sorted(output.iterdir())}
        receipt = dict(status=metadata['status'], elapsed_s=time.monotonic()-start,
                       participant_ids=basis['participant_ids'], n_subjects=len(basis['participant_ids']),
                       n_authenticated_source_files=48,
                       n_frames={s: len(basis['participants'][s]['raw']) for s in basis['participant_ids']},
                       endpoints_computed=not args.pilot_first_subject,
                       warnings=[dict(category=w.category.__name__, message=str(w.message)) for w in caught],
                       files=inventory, **inputs['pins'])
        if report is not None:
            write_json(report, receipt)
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
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR', '/app/data/taskfc'))
    parser.add_argument('--manifest-path', default=os.environ.get('SOURCE_MANIFEST', '/app/source_manifest.json'))
    parser.add_argument('--contract-path', default=os.environ.get('METHOD_CONTRACT', '/app/method_contract.json'))
    parser.add_argument('--schema-path', default=os.environ.get('OUTPUT_SCHEMA', '/app/output_schema.json'))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR', '/app/output'))
    parser.add_argument('--private-dir')
    parser.add_argument('--report')
    parser.add_argument('--pilot-first-subject', action='store_true')
    parser.add_argument('--print-contract', action='store_true')
    args = parser.parse_args()
    try:
        if args.print_contract:
            raw = source.stable_bytes(args.contract_path, 16*1024**2)
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
