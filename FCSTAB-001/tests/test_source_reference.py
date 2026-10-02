"""Manufactured small closed bundles only; no original inputs or bank loads."""
from dataclasses import replace
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest

import source_reference as m


def sha(raw): return hashlib.sha256(raw).hexdigest()


def csv_bytes(rows):
    text = io.StringIO(newline=''); csv.writer(text).writerows(rows); return text.getvalue().encode()


def roi_bytes():
    return b'#1\t#2\t#3\n0\t2\t0.1\n1\t0\t0.1\n3\t1\t0.1\n2\t3\t0.1\n4\t2\t0.1\n'


@pytest.fixture
def case(tmp_path):
    root, meta = tmp_path/'source', tmp_path/'public'; root.mkdir(); meta.mkdir()
    ids = ['Pitt_0050003', 'Pitt_0050004']
    pheno = [['', 'SUB_ID', 'FILE_ID', *m.FIELDS], ['0', '50001', 'Other_0050001', 'OTHER', '1'],
             ['1', '050003', ids[0], 'PITT', '2'], ['2', '50002', 'no_filename', 'OTHER', ''],
             ['3', '50004', ids[1], 'PITT', '2'], ['4', '50005', 'Other_0050005', 'OTHER', 'n/a']]
    bodies = {m.PHENOTYPE: csv_bytes(pheno), **{f'roi/{sid}_rois_cc200.1D': roi_bytes() for sid in ids}, m.NOTICE: b'notice\n'}
    records = []
    for path, raw in bodies.items():
        role = 'phenotype' if path == m.PHENOTYPE else 'provenance_abide_notice' if path == m.NOTICE else 'roi_timeseries'
        row = dict(path=path, role=role, size_bytes=len(raw), sha256=sha(raw))
        if role == 'roi_timeseries':
            fid = Path(path).name.removesuffix('_rois_cc200.1D'); j = ids.index(fid)
            row.update(file_id=fid, subject_id=str(int(fid.split('_')[1])), phenotype_row_index=1+2*j)
        if role == 'provenance_abide_notice':
            row['git_blob_sha1'] = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        target = root/path; target.parent.mkdir(exist_ok=True); target.write_bytes(raw); records.append(row)
    manifest = dict(schema_version='fcstab-source-v1', task_id='FCSTAB-001',
                    dataset_id='ABIDE_pcp/cpac/filt_noglobal/rois_cc200', participant_file_ids=ids, files=records,
                    source_file_count=4, source_bytes=sum(map(len, bodies.values())))
    packed = json.dumps(manifest).encode(); (root/'source_manifest.json').write_bytes(packed)
    path = meta/'source_manifest.json'; path.write_bytes(packed)
    method = meta/'method.json'; method.write_bytes(b'{"task_id":"FCSTAB-001","kind":"manufactured-method"}')
    schema = meta/'schema.json'; schema.write_bytes(b'{"task_id":"FCSTAB-001","kind":"manufactured-schema"}')
    ids_path = meta/'subject_ids.txt'; ids_path.write_bytes(('\n'.join(ids)+'\n').encode())
    policy = m.Policy(sha(packed), sha(method.read_bytes()), sha(schema.read_bytes()), sha(ids_path.read_bytes()),
                      file_count=4, source_bytes=manifest['source_bytes'], roi_count=2, phenotype_rows=5,
                      named_phenotype_rows=4, no_filename_rows=1, frames=5, columns=3)
    return dict(data_dir=root, method_path=method, schema_path=schema, manifest_path=path,
                subject_ids_path=ids_path, policy=policy, manifest=manifest, phenotype=pheno)


def run(case):
    return m._reconstruct(**{k: case[k] for k in ('data_dir','method_path','schema_path','manifest_path','subject_ids_path','policy')})


def repin(case, path=None, raw=None):
    if path is not None:
        (case['data_dir']/path).write_bytes(raw)
        row = next(r for r in case['manifest']['files'] if r['path'] == path)
        row.update(size_bytes=len(raw), sha256=sha(raw))
        if 'git_blob_sha1' in row: row['git_blob_sha1'] = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
    case['manifest']['source_bytes'] = sum(r['size_bytes'] for r in case['manifest']['files'])
    packed = json.dumps(case['manifest']).encode()
    case['manifest_path'].write_bytes(packed); (case['data_dir']/'source_manifest.json').write_bytes(packed)
    case['policy'] = replace(case['policy'], source_sha=sha(packed), source_bytes=case['manifest']['source_bytes'])


def forbidden(*unused, **kwargs): pytest.fail('forbidden early/source/helper operation')


def test_genuine_manufactured_source_reconstruction(case):
    before = {str(p):p.read_bytes() for p in case['data_dir'].rglob('*') if p.is_file()}
    out = run(case)
    assert out['status'] == 'complete' and out['raw'].shape == (2, 5, 3)
    assert out['subject_ids'] == ['50003', '50004']
    assert out['fisher_z'].shape == (2, 3, 1) and out['common_roi_mask'].tolist() == [True, True, False]
    assert out['population_sd'].shape == (2, 3, 3) and out['segment_ids'] == ['first', 'second', 'full']
    assert out['authentication']['source_bytes_read'] == 3*case['policy'].source_bytes
    assert out['authentication']['postconsumption_same_descriptor_checksum']
    assert out['authentication']['closed_internal_bundle_members'] == 5
    obs = out['source_observed']; assert obs['total_frames'] == 10
    assert (obs['n_phenotype_rows'], obs['n_named_phenotype_rows'], obs['n_no_filename_rows'], obs['n_selected_derivatives']) == (5,4,1,2)
    assert obs['phenotype_ledger'][1]['source_subject_id_token'] == '050003'
    assert obs['persons']['Pitt_0050003']['L'] == 2
    assert obs['persons']['Pitt_0050003']['segment_support']['first'] == [True, True, False]
    assert obs['clock'] == dict(TR_verified=False, frame_order='original source row order')
    assert not out['selections_computed'] and not out['downstream_endpoints_computed']
    assert all(Path(path).read_bytes() == data for path, data in before.items())


def test_unfrozen_production_pin_rejects_before_io(monkeypatch):
    monkeypatch.setattr(m, 'METHOD_SHA', None)
    monkeypatch.setattr(m, 'safe_path', forbidden)
    with pytest.raises(ValueError, match='unfrozen_authority'): m.reconstruct()


@pytest.mark.parametrize('key', ['method_path','schema_path','manifest_path','subject_ids_path','internal'])
def test_public_pins_before_member_parse(case, monkeypatch, key):
    path = case['data_dir']/'source_manifest.json' if key == 'internal' else case[key]
    path.write_bytes(b'changed'); monkeypatch.setattr(m, 'member', forbidden)
    with pytest.raises(ValueError, match='metadata_digest'): run(case)


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): m.strict_json(raw)


@pytest.mark.parametrize('kind', ['extra_file','extra_dir','symlink','dangling','fifo','missing'])
def test_closed_source_inventory_before_member_read(case, monkeypatch, kind):
    path = case['data_dir']/'unexpected'
    if kind == 'extra_file': path.write_bytes(b'x')
    elif kind == 'extra_dir': path.mkdir()
    elif kind == 'symlink': path.symlink_to(case['data_dir']/m.PHENOTYPE)
    elif kind == 'dangling': path.symlink_to('/absent')
    elif kind == 'fifo': os.mkfifo(path)
    else: (case['data_dir']/m.NOTICE).unlink()
    monkeypatch.setattr(m, 'member', forbidden)
    with pytest.raises(ValueError): run(case)


@pytest.mark.parametrize('kind', ['role','traversal','size_bool','duplicate_path','row_bool','subject_alias','id_alias','counts'])
def test_manifest_typed_identity(case, monkeypatch, kind):
    row = case['manifest']['files'][1]
    if kind == 'role': row['role'] = 'cached_derived'
    elif kind == 'traversal': row['path'] = 'roi/../escape'
    elif kind == 'size_bool': row['size_bytes'] = True
    elif kind == 'duplicate_path': case['manifest']['files'][2]['path'] = row['path']
    elif kind == 'row_bool': row['phenotype_row_index'] = True
    elif kind == 'subject_alias': row['subject_id'] = '050003'
    elif kind == 'id_alias': row['file_id'] = 'pitt_0050003'
    else: case['manifest']['source_file_count'] = 4.0
    repin(case); monkeypatch.setattr(m, 'member', forbidden)
    with pytest.raises(ValueError): run(case)


def test_all_members_authenticated_before_phenotype_or_roi_parse(case, monkeypatch):
    path = case['data_dir']/m.NOTICE; path.write_bytes(b'x'*path.stat().st_size)
    monkeypatch.setattr(m, 'phenotype_rows', forbidden); monkeypatch.setattr(m, 'parse_roi', forbidden)
    with pytest.raises(ValueError, match='source_sha256'): run(case)


@pytest.mark.parametrize('kind', ['rewrite','replace','metadata'])
def test_after_consumption_identity_and_checksum(case, monkeypatch, kind):
    real = m.parse_roi
    def parser(raw, policy):
        out = real(raw, policy)
        path = case['data_dir']/case['manifest']['files'][1]['path']
        if kind == 'rewrite': path.write_bytes(b'x'*len(raw))
        elif kind == 'replace': path.rename(path.with_suffix('.old')); path.write_bytes(raw)
        else: case['schema_path'].write_bytes(b'{}')
        return out
    monkeypatch.setattr(m, 'parse_roi', parser)
    with pytest.raises(ValueError): run(case)


def test_postconsumption_hash_not_only_filesystem_timestamp(case, monkeypatch):
    # Make stat signatures appear unchanged, modeling coarse timestamp behavior.
    monkeypatch.setattr(m, 'signature', lambda info: (0,))
    real = m.parse_roi
    def parser(raw, policy):
        out = real(raw, policy)
        (case['data_dir']/case['manifest']['files'][1]['path']).write_bytes(b'x'*len(raw))
        return out
    monkeypatch.setattr(m, 'parse_roi', parser)
    with pytest.raises(ValueError, match='postconsumption_digest'): run(case)


@pytest.mark.parametrize('kind', ['header_order','blank','comment','width','nan','inf','bad_token','frame','nul'])
def test_strict_original_roi_parser(case, kind):
    lines = roi_bytes().decode().splitlines()
    if kind == 'header_order': lines[0] = '#2\t#1\t#3'
    elif kind == 'blank': lines[1] = ''
    elif kind == 'comment': lines[1] = '# skipped'
    elif kind == 'width': lines[1] = '1 2'
    elif kind in ('nan','inf','bad_token'): lines[1] = {'nan':'nan','inf':'inf','bad_token':'bad'}[kind]+' 2 3'
    elif kind == 'frame': lines.pop()
    raw = ('\n'.join(lines)+'\n').encode()
    if kind == 'nul': raw += b'\0'
    repin(case, case['manifest']['files'][1]['path'], raw)
    with pytest.raises(ValueError): run(case)


@pytest.mark.parametrize('kind', ['duplicate_header','missing_field','duplicate_subject','selected_index','selected_file',
                                 'selected_subject','duplicate_named','blank_row','no_filename'])
def test_complete_phenotype_without_subset_as_missing_assumption(case, kind):
    p = case['phenotype']
    if kind == 'duplicate_header': p[0][-1] = p[0][-2]
    elif kind == 'missing_field': p[0][-1] = 'other'
    elif kind == 'duplicate_subject': p[1][1] = p[2][1]
    elif kind == 'selected_index': p[1], p[2] = p[2], p[1]
    elif kind == 'selected_file': p[2][2] = 'Other_0050003'
    elif kind == 'selected_subject': p[2][1] = '99999'
    elif kind == 'duplicate_named': p[5][2] = p[1][2]
    elif kind == 'blank_row': p[1] = []
    else: p[2][2] = 'no_filename'
    repin(case, m.PHENOTYPE, csv_bytes(p))
    with pytest.raises(ValueError): run(case)


def test_ids_order_is_literal_not_normalized(case):
    raw = b'Pitt_0050004\nPitt_0050003\n'; case['subject_ids_path'].write_bytes(raw)
    case['policy'] = replace(case['policy'], ids_sha=sha(raw))
    with pytest.raises(ValueError, match='source_manifest_membership'): run(case)


def test_private_numerics_poisoned_cache_cannot_override(monkeypatch):
    poisoned = type(sys)('_fcstab_private_source_numerics'); poisoned.reconstruct = forbidden
    monkeypatch.setitem(sys.modules, poisoned.__name__, poisoned)
    loaded = m.load_numerics()
    assert loaded.reconstruct is not forbidden and sys.modules[poisoned.__name__] is poisoned
    monkeypatch.setattr(m, 'NUMERICS_SHA', '0'*64)
    with pytest.raises(ValueError, match='metadata_digest'): m.load_numerics()
