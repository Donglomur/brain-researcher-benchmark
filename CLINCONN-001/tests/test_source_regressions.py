"""Genuine source-output acceptances and mutations; no source fits in this suite."""
import copy
import csv
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest
import connectivity_contract as q
import proof_of_work as pw
from test_authoring_regressions import write_submission

FILES = ('cohort.csv parcels.csv edges.csv connectivity.csv subject_edge_fc.npz '
         'edge_stats.csv group_stats.json run_metadata.json findings.md').split()
TABLES = ['cohort.csv', 'parcels.csv', 'edges.csv', 'connectivity.csv', 'edge_stats.csv']


@lru_cache(maxsize=1)
def reference():
    return pw.load_reference(os.environ.get('REPAIR_REFERENCE_PATH', str(Path(__file__).with_name('reference.npz'))))


@pytest.fixture
def genuine():
    value = os.environ.get('REPAIR_ORACLE_OUTPUT')
    if value is None:
        pytest.skip('Requires completed original-source oracle output, never a synthetic bank')
    path = Path(value)
    assert all((path/name).is_file() for name in FILES), 'Provided genuine output is incomplete'
    return path


@pytest.fixture
def changed(genuine):
    # Clean each exact fixture directory immediately; do not retain dozens of
    # full172-by-edge matrix copies in pytest's session temp history.
    with tempfile.TemporaryDirectory(prefix='clinconn-real-mutation-') as directory:
        target = Path(directory)
        for name in FILES:
            shutil.copyfile(genuine/name, target/name)
        yield target


def reject(path):
    with pytest.raises((AssertionError, ValueError, TypeError, KeyError, OSError, EOFError)):
        q.validate_output_directory(path, reference())


def rows(path, filename):
    with (path/filename).open(newline='') as stream:
        reader = csv.DictReader(stream); data = list(reader); fields = reader.fieldnames
    return fields, data


def table(path, filename, fields, data):
    with (path/filename).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(data)


def json_edit(path, filename, edit):
    value = json.loads((path/filename).read_text()); edit(value)
    (path/filename).write_text(json.dumps(value, allow_nan=False))


def arrays(path):
    with np.load(path/'subject_edge_fc.npz', allow_pickle=False) as archive:
        return {k: np.array(archive[k]) for k in archive.files}


def test_genuine_oracle(genuine):
    q.validate_output_directory(genuine, reference())


def test_genuine_independent(genuine):
    value = os.environ.get('REPAIR_INDEPENDENT_OUTPUT')
    if value is None:
        pytest.skip('Requires independently recomputed original-source positive')
    q.validate_output_directory(value, reference())


def test_genuine_wrong_first_fd_imputation(genuine):
    value = os.environ.get('REPAIR_WRONG_FD_OUTPUT')
    if value is None:
        pytest.skip('Requires original-FD zero-imputation method control, not hand-perturbed data')
    output = Path(value)
    assert all((output/name).is_file() for name in FILES), 'Provided genuine control is incomplete'
    ref = reference()
    actual = q.validate_arrays(output/'subject_edge_fc.npz', ref)
    for name in q.ARRAY_FIELDS:
        if ref[name].dtype.kind == 'f':
            assert np.array_equal(actual[name], ref[name], equal_nan=True)
        else:
            assert np.array_equal(actual[name], ref[name])
    # The same frozen metadata and FC are valid. Rejection is from measured FD,
    # not an optional control label, expected outcome direction, or prose.
    q.validate_metadata(q.json_load(output/'run_metadata.json'), ref)
    with pytest.raises(AssertionError, match='mean_fd differs from source/declared arithmetic'):
        q.validate_output_directory(output, ref)


def test_public_contract_identity(genuine):
    public = Path(__file__).parents[1]/'environment/method_contract.json'
    q.match(json.loads(public.read_text()), reference()['metadata']['method_contract'], 'public method', 'exact', closed=True)


def test_rows_columns_and_array_axes_order_free(changed):
    for filename in TABLES:
        fields, data = rows(changed, filename)
        for row in data: row['extra_note'] = 'Harmless description'
        table(changed, filename, list(reversed(fields))+['extra_note'], list(reversed(data)))
    values = arrays(changed)
    for key in q.ARRAY_FIELDS:
        values[key] = values[key][::-1] if values[key].ndim == 1 else values[key][::-1, ::-1]
    values['edge_id'] = values['edge_id'].astype(np.uint32)
    np.savez_compressed(changed/'subject_edge_fc.npz', **values)
    q.validate_output_directory(changed, reference())


def test_numeric_notation_summary_rounding_and_free_prose(changed):
    for filename in TABLES:
        fields, data = rows(changed, filename)
        for row in data:
            for field in fields:
                if row[field] and field in q.INT_FIELDS:
                    original = q.integer(row[field]); row[field] = f'{original}.0e0'
                    assert q.integer(row[field]) == original
                elif row[field] and field in ('mean_fc', 'short_range_fc', 'long_range_fc'):
                    row[field] = f'{float(row[field]):.6f}'
        table(changed, filename, fields, data)
    (changed/'findings.md').write_text('These are measured secondary associations, with no required outcome direction.\n')
    q.validate_output_directory(changed, reference())


def test_honest_alternate_software_metadata(changed):
    def edit(x):
        x['software'] = {'independent implementation': 'documented-version'}
        x['comment'] = 'Optional descriptive field'
        x['source_observed']['comment'] = 'Another harmless note'
        x['source_observed']['subjects'].reverse()
    json_edit(changed, 'run_metadata.json', edit)
    q.validate_output_directory(changed, reference())


@pytest.mark.parametrize('name', FILES)
@pytest.mark.parametrize('mode', ['missing', 'empty'])
def test_required_artifacts(changed, name, mode):
    if mode == 'missing': (changed/name).unlink()
    else: (changed/name).write_bytes(b'')
    reject(changed)


@pytest.mark.parametrize('name', TABLES)
@pytest.mark.parametrize('mode', ['drop', 'duplicate'])
def test_complete_keyed_tables(changed, name, mode):
    fields, data = rows(changed, name)
    table(changed, name, fields, data[:-1] if mode == 'drop' else data+[data[0]])
    reject(changed)


@pytest.mark.parametrize('mode', ['offset', 'scale', 'sign', 'identity_permutation', 'wrong_fisher', 'valid_nan',
    'valid_inf', 'hidden_edge_removal', 'wrong_clip_flag', 'wrong_norm', 'wrong_bound', 'wrong_subject_axis',
    'duplicate_edge', 'bool_edge', 'object_array'])
def test_matrix_source_forgeries(changed, mode):
    value = arrays(changed); valid = value['edge_valid']; positions = np.argwhere(valid)
    assert len(positions), 'Genuine mutation needs a measured valid edge'
    i, e = positions[0]
    if mode in ('offset', 'scale', 'sign'):
        value['raw_r'][valid] = (value['raw_r'][valid]+.01 if mode == 'offset' else
            value['raw_r'][valid]*.9 if mode == 'scale' else -value['raw_r'][valid])
        value['raw_r'][valid] = np.clip(value['raw_r'][valid], -1, 1)
        value['fisher_z'] = np.arctanh(np.clip(value['raw_r'], -.999, .999))
        value['fisher_clipped'] = valid & (np.abs(value['raw_r']) > .999)
    elif mode == 'identity_permutation':
        value['raw_r'] = np.roll(value['raw_r'], 1, axis=0)
        value['fisher_z'] = np.roll(value['fisher_z'], 1, axis=0)
    elif mode == 'wrong_fisher': value['fisher_z'] = value['raw_r'].copy()
    elif mode == 'valid_nan': value['raw_r'][i,e] = np.nan
    elif mode == 'valid_inf': value['raw_r'][i,e] = np.inf
    elif mode == 'hidden_edge_removal': value['edge_valid'][i,e] = False
    elif mode == 'wrong_clip_flag': value['fisher_clipped'][i,e] = ~value['fisher_clipped'][i,e]
    elif mode == 'wrong_norm': value['parcel_residual_l2'][0,0] *= 1.01
    elif mode == 'wrong_bound': value['parcel_zero_bound'][0,0] *= 2
    elif mode == 'wrong_subject_axis': value['subject_id'][0] = 'sub-XXXXX'
    elif mode == 'duplicate_edge': value['edge_id'][0] = value['edge_id'][1]
    elif mode == 'bool_edge': value['edge_id'] = value['edge_id'].astype(bool)
    else: value['raw_r'] = value['raw_r'].astype(object)
    np.savez_compressed(changed/'subject_edge_fc.npz', **value)
    reject(changed)


@pytest.mark.parametrize('mode', ['coherent_fc_shift', 'coherent_group_swap'])
def test_coherent_full_fabrication(changed, mode):
    forged = copy.deepcopy(reference()); forged.pop('derived', None)
    if mode == 'coherent_fc_shift':
        keep = forged['edge_valid']; forged['raw_r'][keep] *= .9
        forged['fisher_z'] = np.arctanh(np.clip(forged['raw_r'], -.999, .999))
        forged['fisher_clipped'] = keep & (np.abs(forged['raw_r']) > .999)
    else:
        for name in ('cohort_rows', 'connectivity_rows'):
            for row in forged[name]: row['group'] = 'CONTROL' if row['group'] == 'SCHZ' else 'SCHZ'
    write_submission(changed, forged)
    reject(changed)


@pytest.mark.parametrize('filename,field,mode', [
    ('cohort.csv', 'subject_id', 'alias'), ('cohort.csv', 'selected', 'flip'),
    ('parcels.csv', 'centroid_x', 'shift'), ('parcels.csv', 'n_vertices', 'count'),
    ('edges.csv', 'parcel_i', 'alias'), ('edges.csv', 'distance', 'scale'),
    ('edges.csv', 'distance_bin', 'bin'), ('connectivity.csv', 'mean_fd', 'shift'),
    ('connectivity.csv', 'n_fd_defined', 'count'), ('connectivity.csv', 'qc_fd_lt_0_2', 'flip'),
    ('connectivity.csv', 'mean_fc', 'shift'), ('connectivity.csv', 'short_range_fc', 'shift'),
    ('connectivity.csv', 'long_range_fc', 'shift'), ('connectivity.csv', 'nuisance_rank', 'count'),
    ('edge_stats.csv', 'estimate', 'shift'), ('edge_stats.csv', 'se', 'shift'),
    ('edge_stats.csv', 'df', 'count'), ('edge_stats.csv', 'qcfc_r', 'shift')])
def test_source_table_measurements(changed, filename, field, mode):
    fields, data = rows(changed, filename)
    selected = next(row for row in data if row[field] != '')
    if mode == 'alias': selected[field] = 'arbitrary'+selected[field]
    elif mode == 'flip': selected[field] = str(int(not q.flag(selected[field])))
    elif mode == 'count': selected[field] = str(q.integer(selected[field])+1)
    elif mode == 'bin': selected[field] = 'long' if selected[field] != 'long' else 'short'
    elif mode == 'scale': selected[field] = str(q.number(selected[field])*10)
    else: selected[field] = str(q.number(selected[field])+.01)
    table(changed, filename, fields, data); reject(changed)


@pytest.mark.parametrize('mode', ['effect_sign', 'effect_se', 'ci', 't', 'p', 'group_count', 'fraction', 'map_r', 'missing_null', 'unknown_model'])
def test_group_statistic_forgeries(changed, mode):
    def edit(x):
        row = x['short_range_effects']['all_crude']
        if mode == 'effect_sign': row['estimate'] = -row['estimate']+.01
        elif mode == 'effect_se': row['se'] += .01
        elif mode == 'ci': row['ci95'][0] -= .01
        elif mode == 't': row['t'] = 42.
        elif mode == 'p': row['p'] = -.1
        elif mode == 'group_count': x['group_counts']['SCHZ'] += 1
        elif mode == 'fraction': x['edgewise_abs_t_gt_2']['all_crude']['fraction_abs_t_gt_2'] = 1.1
        elif mode == 'map_r': x['group_map_vs_qcfc']['all_crude']['r'] = -2.
        elif mode == 'missing_null': del row['sse']
        else: x['short_range_effects']['made_up_model'] = copy.deepcopy(row)
    json_edit(changed, 'group_stats.json', edit); reject(changed)


@pytest.mark.parametrize('mode', ['source_hash', 'extra_source', 'method_bool', 'method_filter', 'atlas_extra',
    'atlas_units', 'failed_status', 'missing_field', 'missing_subject', 'duplicate_subject', 'empty_software'])
def test_frozen_source_method_metadata(changed, mode):
    def edit(x):
        if mode == 'source_hash': x['source_manifest_sha256'] = '0'*64
        elif mode == 'extra_source': x['source_sha256']['invented'] = 'a'*64
        elif mode == 'method_bool': x['method_contract']['schema_version'] = True
        elif mode == 'method_filter': x['method_contract']['temporal']['filter']['padlen'] = 0
        elif mode == 'atlas_extra': x['source_observed']['atlas']['invented_affine'] = True
        elif mode == 'atlas_units': x['source_observed']['atlas']['coordinate_units'] = 'metres'
        elif mode == 'failed_status': x['status'] = 'resource_pilot'
        elif mode == 'missing_field': del x['source_manifest_sha256']
        elif mode == 'missing_subject': x['source_observed']['subjects'].pop()
        elif mode == 'duplicate_subject': x['source_observed']['subjects'].append(x['source_observed']['subjects'][0])
        else: x['software'] = {}
    json_edit(changed, 'run_metadata.json', edit); reject(changed)
