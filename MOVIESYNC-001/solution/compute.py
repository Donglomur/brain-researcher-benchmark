"""Source-only supplied MOVIESYNC oracle. Importing this module does no I/O."""
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
import core
import source_reader as source

COHORT_FIELDS = ('participant_id','participant_source_row','bold_path','confounds_path','n_frames',
                 'n_confound_rows','n_maps','map_rank','nuisance_rank','n_active_visual','status')
PAIR_FIELDS = ('participant_a','participant_b','map_id','map_label','r','status')
ROW_FIELDS = ('participant_id','map_id','map_label','isc_pairwise','pairwise_status','pairwise_n_expected',
              'pairwise_n_defined','isc_loo','loo_status','loo_n_expected','loo_n_defined','loo_n_active_contributors')


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def prepare_destinations(output, private, report, protected):
    destinations = [source.safe_path(p) for p in (output, private, report) if p is not None]
    protected = [source.safe_path(p) for p in protected]
    for p in destinations:
        core.require(not os.path.lexists(p), 'fresh exclusive output required')
        core.require(p.parent.is_dir(), 'output parent must already exist')
        for q in protected:
            core.require(disjoint(p, q), 'output overlaps protected input/code')
    for i, p in enumerate(destinations):
        for q in destinations[:i]:
            core.require(disjoint(p, q), 'evidence destinations overlap')
    Path(output).mkdir(mode=0o700)
    if private is not None:
        Path(private).mkdir(mode=0o700)


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')


def write_npz(path, arrays):
    with Path(path).open('xb') as f:
        np.savez_compressed(f, **arrays)


def write_csv(path, fields, rows):
    with Path(path).open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='raise')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ('' if row[key] is None else row[key]) for key in fields})


def versions():
    return dict(python=platform.python_version(), **{
        name: importlib.metadata.version(name) for name in ('numpy','scipy','nibabel','nilearn')})


def pilot_analysis(x, ids, estimator):
    pa = np.asarray([[core.norm(core.center(x[0, :, k])) > core.ACTIVE_BOUND for k in range(3)]])
    empty = lambda n: dict(value=None, status='incomplete_support', n_expected=n, n_defined=0)
    result = dict(schema_version='moviesync-results-v2', status='resource_pilot', isc_estimator=estimator,
                  visual_isc=None, visual_isc_status='incomplete_support', n_subjects=1,
                  n_timepoints=168, reference_zero=0., estimators={k: empty(40) for k in ('pairwise','loo')},
                  per_subject=[], per_region=[], resource_pilot_scope=dict(participant_ids=ids,
                  extraction_only=True, isc_computed=False, full_source_inventory_authenticated=True))
    return dict(pairs=[], rows=[], results=result, person_active=pa,
                template_active=np.zeros_like(pa), templates=None)


def compute(args):
    output = source.safe_path(args.output_dir)
    private = source.safe_path(args.private_dir) if args.private_dir else None
    report = source.safe_path(args.report) if args.report else None
    data = source.safe_path(args.data_dir)
    contract = source.safe_path(args.contract_path)
    schema = source.safe_path(args.schema_path)
    code = source.safe_path(Path(__file__).absolute().parent)
    task_root = code.parent if (code.parent / 'task.toml').is_file() else code
    prepare_destinations(output, private, report, [data, contract, schema, task_root])
    start = time.monotonic()
    captured = []
    messages = []
    try:
        with warnings.catch_warnings(record=True) as messages:
            warnings.simplefilter('always')
            inputs = source.authenticate(data, contract, schema)
            common = source.load_common(inputs)
            ids = list(core.IDS[:1] if args.pilot_first_subject else core.IDS)
            people = []
            for pid in ids:
                person = source.load_person(inputs, common, pid)
                if private is not None:
                    write_npz(private / f'{pid}.npz', dict(raw_coefficients=person['raw_coefficients'],
                              isc_inputs=person['isc_inputs'], **person['private']))
                people.append(person)
            raw = np.stack([p['raw_coefficients'] for p in people])
            x = np.stack([p['isc_inputs'] for p in people])
            if args.pilot_first_subject:
                analysis = pilot_analysis(x, ids, args.isc_estimator)
            else:
                analysis = core.derive(x, ids, common['visual_ids'], common['map_labels'], estimator=args.isc_estimator)
            arrays = dict(participant_ids=np.asarray(ids), map_ids=np.arange(39, dtype=np.int64),
                          map_labels=np.asarray(common['map_labels']), frame_indices=np.arange(168, dtype=np.int64),
                          raw_coefficients=raw, visual_map_ids=np.asarray(common['visual_ids'], dtype=np.int64),
                          isc_inputs=x, person_active=analysis['person_active'], template_active=analysis['template_active'])
            for i, p in enumerate(people):
                p['cohort']['n_active_visual'] = int(np.count_nonzero(analysis['person_active'][i]))
            source_files = [{key: row.get(key) for key in ('path','role','participant_id','size_bytes','sha256')}
                            for row in inputs['manifest']['files']]
            atlas_header = {key: value for key, value in common['atlas_header'].items()
                            if key not in ('raw_TR','raw_toffset','temporal_units')}
            observed = dict(participant_ids=ids,
                            map_labels=[dict(map_id=i, map_label=label) for i, label in enumerate(common['map_labels'])],
                            visual_map_ids=common['visual_ids'], headers=[p['header'] for p in people],
                            atlas_header=atlas_header, confound_column_names={pid:p['confound_columns'] for pid,p in zip(ids,people)},
                            participant_column_names=common['participant_header'], effective_TR_s=2., effective_origin_s=0.,
                            frame_alignment='released_frame_index_only_no_measured_movie_onset')
            status = 'resource_pilot' if args.pilot_first_subject else 'ok'
            metadata = dict(schema_version='moviesync-metadata-v2', status=status, task_id='MOVIESYNC-001',
                            isc_estimator=args.isc_estimator, **inputs['identity'], source_files=source_files,
                            source_observed=observed, software_versions=versions())
            if args.pilot_first_subject:
                metadata['resource_pilot_scope'] = analysis['results']['resource_pilot_scope']
            write_csv(output/'cohort.csv', COHORT_FIELDS, [p['cohort'] for p in people])
            write_npz(output/'timecourses.npz', arrays)
            write_csv(output/'isc_pairs.csv', PAIR_FIELDS, analysis['pairs'])
            write_csv(output/'isc_per_subject.csv', ROW_FIELDS, analysis['rows'])
            write_json(output/'isc_results.json', analysis['results'])
            write_json(output/'run_metadata.json', metadata)
            if args.pilot_first_subject:
                findings = 'Resource pilot: one fixed person extracted; no ISC or population result computed.\n'
            else:
                p, l = (analysis['results']['estimators'][key] for key in ('pairwise','loo'))
                findings = (f"Fixed-cohort descriptive ISC, all {len(ids)} participants and168 released frames.\n\n"
                            f"Pairwise: {p['value']} ({p['n_defined']}/{p['n_expected']} participant summaries); "
                            f"leave-one-out: {l['value']} ({l['n_defined']}/{l['n_expected']}). "
                            f"Declared headline: {args.isc_estimator}.\n\n"
                            'These arithmetic-r endpoints summarize different comparisons. No sign, ordering or chance-significance '
                            'claim follows from completing this computation. Released-frame alignment is not measured movie-onset '
                            'alignment. This all168-frame visual-component adaptation is not the publication\'s TR11:168 '
                            'ToM/pain functional-maturity analysis, population inference or a task-difficulty result.\n')
            with (output/'findings.md').open('x', encoding='utf-8') as f:
                f.write(findings)
            if private is not None:
                write_npz(private/'analysis_arrays.npz', arrays)
            captured = [dict(category=m.category.__name__, message=str(m.message)) for m in messages]
        inventory = {p.name:dict(size_bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                     for p in sorted(output.iterdir())}
        receipt = dict(status=status, elapsed_s=time.monotonic()-start, n_subjects=len(ids),
                       n_frames=168, n_maps=39, n_visual_maps=3, pair_rows=len(analysis['pairs']),
                       person_region_rows=len(analysis['rows']), warnings=captured, files=inventory,
                       **inputs['identity'])
        if report is not None:
            write_json(report, receipt)
        return receipt
    except Exception as exc:
        captured = [dict(category=m.category.__name__, message=str(m.message)) for m in messages]
        failure = dict(status='failed_precondition', reason=f'{type(exc).__name__}: {exc}',
                       elapsed_s=time.monotonic()-start, warnings=captured)
        write_json(output/'failure_report.json', failure)
        if report is not None and not os.path.lexists(report):
            write_json(report, failure)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR','/app/data/moviesync'))
    parser.add_argument('--contract-path', default=os.environ.get('METHOD_CONTRACT','/app/method_contract.json'))
    parser.add_argument('--schema-path', default=os.environ.get('OUTPUT_SCHEMA','/app/output_schema.json'))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR','/app/output'))
    parser.add_argument('--private-dir')
    parser.add_argument('--report')
    parser.add_argument('--isc-estimator', choices=('pairwise','loo','leave-one-out'), default='pairwise')
    parser.add_argument('--pilot-first-subject', action='store_true')
    parser.add_argument('--print-contract', action='store_true')
    args = parser.parse_args()
    if args.print_contract:
        text = source.stable_bytes(args.contract_path, 1024*1024)
        source.strict_json(text)
        sys.stdout.write(text.decode('utf-8'))
        return 0
    try:
        result = compute(args)
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
