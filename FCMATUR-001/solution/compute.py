"""Source-only FCMATUR oracle. No I/O or scientific execution on import."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import sys
import time
import warnings

import source_reader as source

FILES = ('connectivity.csv', 'connectivity_age.json', 'sensitivity.json', 'run_metadata.json', 'findings.md')
CSV_COLUMNS = ('FILE_ID', 'connectivity', 'connectivity_status', 'age', 'site_id', 'sex', 'dx_group',
               'mean_fd', 'age_status', 'site_id_status', 'sex_status', 'dx_group_status', 'mean_fd_status',
               'n_frames', 'n_columns', 'n_active_columns', 'n_edges', 'base_eligible', 'within_eligible',
               'motion_eligible', 'sex_eligible', 'control_eligible', 'base_reason')
PRIMARY_KEYS = ('n_source', 'n_base', 'n_within', 'eligible_site_ids', 'all_base_site_counts',
                'pooled', 'within_site', 'between_site', 'site_means')


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def writable_target(path, protected):
    value = source.safe_path(path)
    source.require(all(disjoint(value, item) for item in protected), 'output_overlaps_protected_input')
    return value


def destinations(output, private, report, protected):
    values = [writable_target(p, protected) for p in (output, private, report) if p is not None]
    for i, value in enumerate(values):
        source.require(value.parent.is_dir() and not os.path.lexists(value), 'fresh_destination_required')
        source.require(all(disjoint(value, other) for other in values[:i]), 'overlapping_destinations')
    output.mkdir(mode=0o700)
    if private is not None:
        private.mkdir(mode=0o700)


def fail_marker(output, protected, failure):
    """Only add an exclusive marker in a safe existing directory; never erase."""
    try:
        path = writable_target(output, protected)
        if not path.is_dir() or not stat.S_ISDIR(path.lstat().st_mode):
            return
        marker = path / 'failure_report.json'
        if not os.path.lexists(marker):
            write_json(marker, failure)
    except (OSError, ValueError):
        # The caller still exits nonzero. Never follow a suspicious target to
        # force a failure receipt, and never overwrite an earlier marker.
        return


def versions():
    return dict(python=platform.python_version(), numpy=importlib.metadata.version('numpy'),
                scipy=importlib.metadata.version('scipy'))


def connectivity_rows(basis, result):
    meta = {row['file_id']: row for row in basis['phenotype_ledger']
            if row['source_availability'] == 'released_filename'}
    flags = {row['subject']: row for row in result['cohort']}
    output = []
    for fid in basis['participant_ids']:
        person, pheno = basis['persons'][fid], meta[fid]
        row = dict(FILE_ID=fid, connectivity=person['connectivity'], connectivity_status=person['status'])
        for key in ('age', 'site_id', 'sex', 'dx_group', 'mean_fd'):
            row[key] = pheno['normalized'][key]
            row[key + '_status'] = pheno['covariate_status'][key]
        for key in ('n_frames', 'n_columns', 'n_active_columns', 'n_edges'):
            row[key] = person[key]
        row.update({key: flags[fid][key] for key in
                    ('base_eligible', 'within_eligible', 'motion_eligible', 'sex_eligible', 'control_eligible', 'base_reason')})
        output.append(row)
    return output


def write_scientific_outputs(output, basis, result):
    schema = basis['schema']
    source.require(tuple(schema['required_files']) == FILES and tuple(schema['csv']['required_columns']) == CSV_COLUMNS,
                   'writer_schema_membership')
    with (output / 'connectivity.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in connectivity_rows(basis, result):
            writer.writerow({key: ('true' if value else 'false') if type(value) is bool else value
                             for key, value in row.items()})
    write_json(output / 'connectivity_age.json', dict(schema_version='fcmatur-results-v3', status='complete',
                                                     **{key: result[key] for key in PRIMARY_KEYS}))
    write_json(output / 'sensitivity.json', dict(schema_version='fcmatur-sensitivity-v3', status='complete',
                                               checks=result['sensitivity']))
    def display(value):
        return 'undefined' if value is None else format(value, '.8g')
    summaries = []
    for name, label in (('pooled', 'Pooled'), ('within_site', 'Site fixed effects'),
                        ('between_site', 'Equally weighted site means')):
        row = result[name]
        interval = ('undefined' if row['ci95'] is None else
                    '[' + ', '.join(display(v) for v in row['ci95']) + ']')
        summaries.append(f"{label}: r={display(row['r'])}; n={row['n']} {row['unit']} units; "
            f"95% CI={interval} ({row['ci_status']}); p={display(row['p'])} ({row['p_status']}); "
            f"estimate status={row['estimate_status']}.")
    findings = (
        f"Fixed released-derivative cohort: {result['n_source']} participants; "
        f"{result['n_base']} contribute to the age/connectivity base sample and {result['n_within']} "
        f"to the site-parent sample ({len(result['eligible_site_ids'])} eligible sites).\n\n"
        + '\n\n'.join(summaries) + '\n\n'
        "The three summaries have different weighting or conditioning and are not interchangeable estimates. "
        "Unavailable quantities remain explicit nulls in the machine-readable records.\n\n"
        "Participant connectivity is the signed equal-edge mean Fisher-z of released CC200 time courses, "
        "using each participant's nonconstant columns. Available edge sets can differ, limiting comparisons. "
        "This is a cross-sectional aggregation/conditioning case study, not longitudinal maturation, "
        "age prediction, a diagnostic contrast or a reproduction of a target paper result. "
        "Between-site correlation is ecological; site adjustment does not identify a scanner cause. "
        "Analytic uncertainty is model-based, not cluster-robust or multiplicity-adjusted. "
        "No direction, ordering or significance was required.\n")
    with (output / 'findings.md').open('x', encoding='utf-8') as stream:
        stream.write(findings)


def output_inventory(output, schema):
    entries = list(output.iterdir())
    source.require({p.name for p in entries} == set(FILES) and
                   all(stat.S_ISREG(p.lstat().st_mode) for p in entries), 'output_inventory')
    limits = schema['limits']
    inventory, total = {}, 0
    for path in sorted(entries):
        raw = path.read_bytes()
        cap = limits['csv_bytes' if path.suffix == '.csv' else 'json_bytes' if path.suffix == '.json' else 'text_bytes']
        source.require(0 < len(raw) <= cap, 'output_member_cap')
        total += len(raw)
        inventory[path.name] = dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    source.require(total <= limits['entire_output_tree_bytes'], 'output_total_cap')
    return inventory


def compute(args):
    # Paths are checked before directories are created, even for stale-output
    # failures. An overlapping source/code target must receive no marker/write.
    data, manifest, method, schema, kernel = map(source.safe_path,
        (args.data_dir, args.manifest_path, args.method_path, args.schema_path, args.kernel_path))
    code = source.safe_path(Path(__file__).absolute().parent)
    code_root = code.parent if (code.parent / 'task.toml').is_file() else code
    protected = [data, manifest, method, schema, kernel, code_root]
    output = source.safe_path(args.output_dir)
    private = source.safe_path(args.private_dir) if args.private_dir else None
    report = source.safe_path(args.report) if args.report else None
    started, caught = time.monotonic(), []
    try:
        destinations(output, private, report, protected)
        last_notice = started
        def progress(done, total):
            nonlocal last_notice
            now = time.monotonic()
            if now - last_notice >= 30:
                print(f'Authenticated participant primitives: {done}/{total}', file=sys.stderr, flush=True)
                last_notice = now
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            basis = source.load(data, manifest, method, schema, kernel, progress=progress)
            accepted = {row['subject']: row['connectivity'] for row in basis['canonical_rows']}
            result = basis['kernel'].analyze(basis['canonical_rows'], accepted)
            write_scientific_outputs(output, basis, result)
        metadata = dict(schema_version='fcmatur-metadata-v3', task_id='FCMATUR-001', status='complete',
            pins=basis['pins'], source_files=basis['source_files'], phenotype_ledger=basis['phenotype_ledger'],
            source_observed=basis['source_observed'], software=versions(),
            warnings=[str(item.message) for item in caught])
        write_json(output / 'run_metadata.json', metadata)
        inventory = output_inventory(output, basis['schema'])
        receipt = dict(status='complete', elapsed_s=time.monotonic()-started, n_source=result['n_source'],
            n_base=result['n_base'], n_within=result['n_within'], files=inventory, pins=basis['pins'],
            authentication=basis['authentication'], warnings=metadata['warnings'])
        if private is not None:
            write_json(private / 'execution_receipt.json', receipt)
        if report is not None:
            write_json(report, receipt)
        return receipt
    except Exception as exc:
        failure = dict(status='failed_precondition', reason=f'{type(exc).__name__}: {exc}',
                       elapsed_s=time.monotonic()-started, warnings=[str(item.message) for item in caught])
        fail_marker(output, protected, failure)
        # A report is optional. All destinations must still be safe/fresh; a
        # failure during preflight cannot authorize an arbitrary report write.
        if report is not None:
            try:
                writable_target(report, protected + [output] + ([private] if private else []))
                if report.parent.is_dir() and not os.path.lexists(report):
                    write_json(report, failure)
            except (OSError, ValueError):
                pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR', '/app/data/fcmatur'))
    parser.add_argument('--manifest-path', default=os.environ.get('SOURCE_MANIFEST', '/app/source_manifest.json'))
    parser.add_argument('--method-path', default=os.environ.get('METHOD_CONTRACT', '/app/method_contract.json'))
    parser.add_argument('--schema-path', default=os.environ.get('OUTPUT_SCHEMA', '/app/output_schema.json'))
    parser.add_argument('--kernel-path', default=os.environ.get('STATISTICS_KERNEL', '/app/statistics_kernel.py'))
    parser.add_argument('--output-dir', default=os.environ.get('OUTPUT_DIR', '/app/output'))
    parser.add_argument('--private-dir')
    parser.add_argument('--report')
    parser.add_argument('--print-contract', action='store_true')
    args = parser.parse_args()
    try:
        if args.print_contract:
            raw = source.hashed_bytes(args.method_path, source.METHOD_SHA, 4 * 1024**2)
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
