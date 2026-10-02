"""Private five-artifact FCMATUR validation; no source I/O on import.

The caller supplies a freshly authenticated independent source reference.
Only accepted participant connectivity feeds the one downstream replay. The
same-byte numerical kernel is loaded from this private sibling, never from an
agent-visible module, import cache, working directory or public /app helper.
"""
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import sys
import types

import artifact_reader as io


SOURCE_SHA = 'c62460fa4a0255f0efa60c562fdca425af98458f5a9cd8c93687551c893ab1c7'
METHOD_SHA = 'ae174eef6f838bd6e5925941dd095b8b703c15296d1d4578ab868255d2b6eb4c'
SCHEMA_SHA = '8c4760b3ce017c74317efd3f544d577280ca284bae5abad039624fb0fa44498a'
KERNEL_SHA = '72f11842387ca6980f1c753f6f7e1674dde93a67f57c8563ec759f1c445ef301'
PINS = dict(source_manifest_sha256=SOURCE_SHA, method_contract_sha256=METHOD_SHA,
            output_schema_sha256=SCHEMA_SHA)
DERIVED = (1e-6, 1e-6)
PHENOTYPE = (1e-10, 1e-9)
ASSOCIATION = ('unit', 'ids', 'n', 'column_ids', 'rank', 'df', 'r', 't', 'p',
               'ci95', 'estimate_status', 't_status', 'p_status', 'ci_status')
QUADRATIC = ('ids', 'n', 'base_rank', 'full_rank', 'added_rank', 'df1', 'df2',
             'quadratic_beta', 'beta_status', 'gain_ss', 'rss_linear',
             'rss_quadratic', 'F_added_quadratic', 'p_added_quadratic', 'status')
PRIMARY = ('n_source', 'n_base', 'n_within', 'eligible_site_ids', 'all_base_site_counts')
SITE_SUMMARY = ('n_expected', 'n_defined', 'status', 'median_within_site_r',
                'frac_sites_positive', 'n_sites_positive', 'min_r', 'max_r')
CSV_COLUMNS = ('FILE_ID', 'connectivity', 'connectivity_status', 'age', 'site_id',
               'sex', 'dx_group', 'mean_fd', 'age_status', 'site_id_status',
               'sex_status', 'dx_group_status', 'mean_fd_status', 'n_frames',
               'n_columns', 'n_active_columns', 'n_edges', 'base_eligible',
               'within_eligible', 'motion_eligible', 'sex_eligible',
               'control_eligible', 'base_reason')
FLAGS = ('base_eligible', 'within_eligible', 'motion_eligible', 'sex_eligible', 'control_eligible')
MEMBERSHIPS = {'ids', 'eligible_site_ids'}
KEYED_LISTS = {'source_files': 'path', 'phenotype_ledger': 'phenotype_row_index',
               'site_means': 'site_id', 'per_site': 'site_id'}
CLOSED_MAPS = {'persons', 'all_base_site_counts', 'site_counts'}


def need(ok, reason):
    io.require(ok, reason)


def load_kernel():
    path = Path(__file__).absolute().with_name('statistics_kernel.py')
    raw = io.read_bytes(path, 128 * 1024)
    need(hashlib.sha256(raw).hexdigest() == KERNEL_SHA, 'private kernel digest')
    name = '_fcmatur_held_kernel_' + KERNEL_SHA
    module = types.ModuleType(name)
    module.__file__ = str(path)
    # dataclass consults sys.modules during compilation; never reuse a cached
    # module, and restore even a preexisting untrusted entry after compiling.
    prior = sys.modules.get(name)
    present = name in sys.modules
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    finally:
        if present:
            sys.modules[name] = prior
        else:
            del sys.modules[name]
    return module


def keyed(records, key, where, *, integer=False):
    need(type(records) is list, where + ': record list')
    result = {}
    for record in records:
        need(type(record) is dict and key in record, where + ': keyed record')
        value = io.integer(record[key], json_number=True) if integer else record[key]
        need(type(value) is int if integer else type(value) is str and bool(value),
             where + ': key type')
        need(value not in result, where + ': duplicate identity')
        result[value] = record
    return result


def membership(value, where, *, integers=False):
    need(type(value) is list, where + ': membership list')
    if integers:
        keys = [io.integer(v, json_number=True) for v in value]
    else:
        need(all(type(v) is str and v for v in value), where + ': literal identities')
        keys = value
    need(len(set(keys)) == len(keys), where + ': duplicate member')
    return set(keys)


def domain(value, key, where):
    if key in {'r', 'min_r', 'max_r', 'median_within_site_r'}:
        need(-1 <= value <= 1, where + ': correlation domain')
    if key in {'p', 'p_added_quadratic', 'frac_sites_positive'}:
        need(0 <= value <= 1, where + ': probability domain')
    if key in {'F_added_quadratic', 'gain_ss', 'rss_linear', 'rss_quadratic', 'mean_fd'}:
        need(value >= 0, where + ': nonnegative domain')
    if key in {'age', 'mean_age'}:
        need(0 < value < 120, where + ': age domain')
    if key in {'sex', 'dx_group'}:
        need(value in (1, 2), where + ': code domain')


def match(actual, expected, where, *, tolerance=DERIVED, key=''):
    """Compare an explicit required view; extras are not scientific inputs."""
    if expected is None:
        need(actual is None, where + ': required null')
    elif type(expected) is bool:
        need(type(actual) is bool and actual == expected, where + ': Boolean')
    elif type(expected) is int:
        value = io.integer(actual, json_number=True)
        domain(value, key, where)
        need(value == expected, where + ': exact integer')
    elif isinstance(expected, (float, Decimal)):
        value = io.real(actual, json_number=True)
        domain(value, key, where)
        atol, rtol = tolerance
        need(abs(value - float(expected)) <= atol + rtol * abs(float(expected)), where + ': numeric receipt')
    elif type(expected) is str:
        need(type(actual) is str and actual == expected, where + ': literal value')
    elif type(expected) is dict:
        need(type(actual) is dict and expected.keys() <= actual.keys(), where + ': required keys')
        if key in CLOSED_MAPS:
            need(actual.keys() == expected.keys(), where + ': closed identity mapping')
        for name, value in expected.items():
            match(actual[name], value, where + '.' + name, tolerance=tolerance, key=name)
    elif type(expected) is list:
        if key in MEMBERSHIPS or key == 'exact_constant_columns':
            is_integer = key == 'exact_constant_columns'
            need(membership(actual, where, integers=is_integer) ==
                 membership(expected, where, integers=is_integer), where + ': exact membership')
        elif key in KEYED_LISTS:
            name = KEYED_LISTS[key]
            left = keyed(actual, name, where, integer=name == 'phenotype_row_index')
            right = keyed(expected, name, where, integer=name == 'phenotype_row_index')
            need(left.keys() == right.keys(), where + ': complete keyed rows')
            for identity in right:
                match(left[identity], right[identity], where + '[' + str(identity) + ']', tolerance=tolerance)
        else:
            need(type(actual) is list and len(actual) == len(expected), where + ': ordered shape')
            if key == 'ci95':
                bounds = [io.real(v, json_number=True) for v in actual]
                need(len(bounds) == 2 and -1 <= bounds[0] <= bounds[1] <= 1, where + ': CI domain/order')
            for i, value in enumerate(expected):
                match(actual[i], value, where + '[' + str(i) + ']', tolerance=tolerance)
    else:
        raise io.ArtifactError(where + ': unsupported reference type')


def association_view(row):
    result = {key: row[key] for key in ASSOCIATION}
    for key in ('age_support', 'connectivity_support'):
        result[key] = {'active': row[key]['active']}
    return result


def public_statistics(replay):
    primary = dict(schema_version='fcmatur-results-v3', status='complete',
                   **{key: replay[key] for key in PRIMARY})
    for key in ('pooled', 'within_site', 'between_site'):
        primary[key] = association_view(replay[key])
    primary['site_means'] = replay['site_means']
    checks = {}
    for key in ('motion', 'diagnosis', 'sex'):
        row = replay['sensitivity'][key]
        checks[key] = {name: row[name] for name in ('ids', 'n', 'site_counts')}
        for name in ('pooled', 'within_site'):
            checks[key][name] = association_view(row[name])
    row = replay['sensitivity']['nonlinear_age']
    checks['nonlinear_age'] = {key: row[key] for key in QUADRATIC}
    for key in ('linear_residual_support', 'full_residual_support'):
        if key in row:
            checks['nonlinear_age'][key] = {'active': row[key]['active']}
    row = replay['sensitivity']['site_specific_slopes']
    checks['site_specific_slopes'] = {key: row[key] for key in SITE_SUMMARY}
    checks['site_specific_slopes']['per_site'] = [dict(association_view(r), **{
        key: r[key] for key in ('site_id', 'slope', 'slope_status')}) for r in row['per_site']]
    return primary, dict(schema_version='fcmatur-sensitivity-v3', status='complete', checks=checks)


def nullable_csv(token, *, integer=False):
    if token == '':
        return None
    return io.integer(token) if integer else io.real(token)


def validate_participants(rows, reference):
    table = io.keyed_rows(rows, ('FILE_ID',))
    ids = reference['participant_ids']
    need(set(table) == {(sid,) for sid in ids}, 'CSV complete literal participants')
    ledger = {row['file_id']: row for row in reference['phenotype_ledger']
              if row['source_availability'] == 'released_filename'}
    need(set(ledger) == set(ids), 'reference phenotype membership')
    accepted = {}
    for sid in ids:
        row, person, phenotype = table[(sid,)], reference['persons'][sid], ledger[sid]
        need(set(CSV_COLUMNS) <= row.keys(), 'CSV required columns')
        accepted[sid] = nullable_csv(row['connectivity'])
        need(row['connectivity_status'] == person['status'], 'CSV connectivity status')
        for field in ('age', 'sex', 'dx_group', 'mean_fd'):
            value = nullable_csv(row[field], integer=field in ('sex', 'dx_group'))
            match(value, phenotype['normalized'][field], 'CSV.' + sid + '.' + field,
                  tolerance=PHENOTYPE, key=field)
        need(row['site_id'] == (phenotype['normalized']['site_id'] or ''), 'CSV literal site')
        for field, status in phenotype['covariate_status'].items():
            need(row[field + '_status'] == status, 'CSV covariate status')
        for field in ('n_frames', 'n_columns', 'n_active_columns', 'n_edges'):
            need(io.integer(row[field]) == person[field], 'CSV source support count')
    return table, accepted


def validate_metadata(actual, reference):
    expected = dict(schema_version='fcmatur-metadata-v3', status='complete', task_id='FCMATUR-001',
                    pins=reference['pins'], source_files=reference['source_files'])
    match(actual, expected, 'metadata', tolerance=(0., 0.))
    need('phenotype_ledger' in actual and 'source_observed' in actual, 'metadata full provenance')
    match(actual['phenotype_ledger'], reference['phenotype_ledger'], 'metadata.phenotype_ledger',
          tolerance=PHENOTYPE, key='phenotype_ledger')
    match(actual['source_observed'], reference['source_observed'], 'metadata.source_observed',
          tolerance=(0., 0.))
    need(type(actual.get('software')) is dict, 'metadata software object')
    for name in ('python', 'numpy', 'scipy'):
        value = actual['software'].get(name)
        need(type(value) is str and bool(value.strip()), 'metadata software version string')


def validate(output_dir, reference):
    root = io.guarded_path(output_dir, directory=True)
    need(not os.path.lexists(root / io.FAILURE), 'authoritative failure_report.json present')
    need(type(reference) is dict and reference.get('status') == 'complete', 'complete source reference required')
    need(reference.get('pins') == PINS, 'private source/method/schema identity')
    ids = reference['participant_ids']
    need(type(ids) is list and all(type(s) is str and s for s in ids) and len(set(ids)) == len(ids),
         'reference literal identities')
    need(set(reference['persons']) == set(ids), 'reference person membership')
    artifacts = io.read_artifacts(root)
    table, accepted = validate_participants(artifacts['connectivity.csv'], reference)
    validate_metadata(artifacts['run_metadata.json'], reference)
    replay = load_kernel().analyze(reference['canonical_rows'], accepted)
    for row in replay['cohort']:
        submitted = table[(row['subject'],)]
        for key in FLAGS:
            need(io.csv_boolean(submitted[key]) == row[key], 'CSV eligibility ' + key)
        need(submitted['base_reason'] == row['base_reason'], 'CSV base reason')
    primary, sensitivity = public_statistics(replay)
    match(artifacts['connectivity_age.json'], primary, 'primary')
    match(artifacts['sensitivity.json'], sensitivity, 'sensitivity')
    need(not os.path.lexists(root / io.FAILURE), 'authoritative failure_report.json present')
    return dict(status='accepted', n_source=replay['n_source'], n_base=replay['n_base'],
                n_within=replay['n_within'], accepted_participant_values=len(accepted))
