"""External prospective RESTCONN oracle. Import performs no I/O."""
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


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def prepare_destinations(output, private, report, protected):
    destinations = [source.safe_path(p) for p in (output, private, report) if p is not None]
    protected = [source.safe_path(p) for p in protected]
    for i, p in enumerate(destinations):
        core.require(not os.path.lexists(p) and p.parent.is_dir(), 'fresh destination with existing parent required')
        core.require(all(disjoint(p, q) for q in protected + destinations[:i]), 'destination overlaps protected input/evidence')
    output.mkdir(mode=0o700)
    if private is not None: private.mkdir(mode=0o700)


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def write_npz(path, arrays):
    with Path(path).open('xb') as handle:
        np.savez_compressed(handle, **arrays)


def versions():
    return dict(python=platform.python_version(), **{name: importlib.metadata.version(name)
        for name in ('numpy', 'scipy', 'nibabel', 'nilearn')})


def pilot_result(n):
    return dict(subject=core.PARTICIPANT, region_a=core.TARGETS[0], region_b=core.TARGETS[1],
        n_timepoints=n, status='resource_pilot', r=None, p_value=None, significant=None,
        inference=None, resource_pilot_scope=dict(extraction_and_cleaning_only=True,
            circular_inference_computed=False, all_ten_source_members_authenticated=True))


def compute(args):
    output = source.safe_path(args.output_dir)
    private = source.safe_path(args.private_dir) if args.private_dir else None
    report = source.safe_path(args.report) if args.report else None
    data, method, schema = map(source.safe_path, (args.data_dir, args.contract_path, args.schema_path))
    code = source.safe_path(Path(__file__).absolute().parent)
    task_root = code.parent if (code.parent / 'task.toml').is_file() else code
    prepare_destinations(output, private, report, [data, method, schema, task_root])
    start = time.monotonic()
    caught = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            inputs = source.authenticate(data, method, schema)
            basis = source.load(inputs)
            n = len(basis['raw_coefficients'])
            primitive = dict(participant_id=np.asarray(core.PARTICIPANT), frame_indices=np.arange(n, dtype=np.int64),
                map_ids=np.arange(39, dtype=np.int64), map_labels=np.asarray(basis['map_labels']),
                raw_coefficients=basis['raw_coefficients'])
            if private is not None:
                write_npz(private / 'analysis_arrays.npz', primitive | basis['private'] |
                    dict(target_map_ids=np.asarray(basis['target_map_ids']), cleaned_series=basis['cleaned_series'],
                         target_active=basis['active']))
            result = pilot_result(n) if args.pilot_extraction_only else core.circular_evidence(basis['cleaned_series'], basis['active'])
            status = 'resource_pilot' if args.pilot_extraction_only else 'ok'
            metadata = dict(schema_version='restconn-metadata-v2', task_id='RESTCONN-001', status=status,
                **inputs['identity'], source_files=[{key: row.get(key) for key in
                    ('path', 'role', 'participant_id', 'size_bytes', 'sha256')} for row in inputs['manifest']['files']],
                source_observed=basis['source_observed'], analysis_observed=basis['analysis_observed'], software_versions=versions())
            if args.pilot_extraction_only: metadata['resource_pilot_scope'] = result['resource_pilot_scope']
            write_npz(output / 'raw_map_coefficients.npz', primitive)
            with (output / 'timeseries.csv').open('x', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(('frame_index', *core.TARGETS))
                for t, row in enumerate(basis['cleaned_series']): writer.writerow((t, *map(float, row)))
            write_json(output / 'connectivity.json', result)
            if args.pilot_extraction_only:
                findings = 'Extraction/cleaning resource pilot only; no circular rank or connectivity conclusion was computed.\n'
            else:
                findings = (f"Single released recording {core.PARTICIPANT}, {n} complete frames. "
                    f"R DMN–Cereb map-coefficient correlation: {result['r']}; exhaustive circular-rank value: "
                    f"{result['p_value']} ({result['status']}).\n\n"
                    'The two signals are coefficients from a joint fit of all 39 overlapping MSDL maps, not ROI means. '
                    'The all-offset circular rank is not generally a calibrated p-value under temporal dependence; '
                    'it is not xDF or TTS inference. This is a single-recording method control, not a population, '
                    'paper-replication, directional-connectivity or benchmark-difficulty finding.\n')
            with (output / 'findings.md').open('x', encoding='utf-8') as handle: handle.write(findings)
        warn = [dict(category=w.category.__name__, message=str(w.message)) for w in caught]
        metadata['warnings'] = [str(w.message) for w in caught]
        write_json(output / 'run_metadata.json', metadata)
        inventory = {p.name: dict(size_bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(output.iterdir())}
        receipt = dict(status=status, elapsed_s=time.monotonic() - start, participant_id=core.PARTICIPANT,
            n_frames=n, n_maps=39, n_targets=2, map_rank=basis['analysis_observed']['map_rank'],
            confound_rank=basis['analysis_observed']['confound_rank'], n_active_targets=int(basis['active'].sum()),
            circular_inference_computed=not args.pilot_extraction_only, warnings=warn, files=inventory, **inputs['identity'])
        if report is not None: write_json(report, receipt)
        return receipt
    except Exception as exc:
        failure = dict(status='failed_precondition', reason=f'{type(exc).__name__}: {exc}',
            elapsed_s=time.monotonic() - start,
            warnings=[dict(category=w.category.__name__, message=str(w.message)) for w in caught])
        write_json(output / 'failure_report.json', failure)
        if report is not None and not os.path.lexists(report): write_json(report, failure)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR', '/app/data/restconn'))
    parser.add_argument('--contract-path', default=os.environ.get('METHOD_CONTRACT', '/app/method_contract.json'))
    parser.add_argument('--schema-path', default=os.environ.get('OUTPUT_SCHEMA', '/app/output_schema.json'))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR', '/app/output'))
    parser.add_argument('--private-dir')
    parser.add_argument('--report')
    parser.add_argument('--pilot-extraction-only', action='store_true')
    parser.add_argument('--print-contract', action='store_true')
    args = parser.parse_args()
    try:
        if args.print_contract:
            raw = source.stable_bytes(args.contract_path, 1024 ** 2)
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
