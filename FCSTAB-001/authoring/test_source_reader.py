"""Source-free oracle reader fixtures; no original paths or analysis."""
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

import source_reader as m


def sha(raw): return hashlib.sha256(raw).hexdigest()


def pack_csv(rows):
    stream = io.StringIO(newline='')
    csv.writer(stream).writerows(rows)
    return stream.getvalue().encode()


@pytest.fixture
def case(tmp_path):
    root, docs = tmp_path/'source', tmp_path/'documents'
    (root/'roi').mkdir(parents=True); (root/'provenance').mkdir(); docs.mkdir()
    ids = ['Pitt_0050003', 'Pitt_0050004']
    pheno = [['', 'SUB_ID', 'FILE_ID', 'SITE_ID', 'EYE_STATUS_AT_SCAN'],
             ['0', '50001', 'Other_0050001', 'OTHER', '1'],
             ['1', '050003', ids[0], 'PITT', '2'],
             ['2', '50002', 'no_filename', 'PITT', ''],
             ['3', '50004', ids[1], 'PITT', '2'],
             ['4', '50005', 'Other_0050005', 'OTHER', 'n/a']]
    values = np.array([[0, 0.1, 1], [1, 0.1, 2], [2, 0.1, 4], [3, 0.1, 2], [4, 0.1, 8]], float)
    header = '#1\t#2\t#3'
    roi = (header+'\n'+'\n'.join(' '.join(repr(float(v)) for v in row) for row in values)+'\n').encode()
    payloads = {m.PHENOTYPE: pack_csv(pheno),
                **{f'roi/{sid}_rois_cc200.1D': roi for sid in ids},
                m.NOTICE: b'manufactured notice\n'}
    records = []
    for path, raw in payloads.items():
        role = 'phenotype' if path == m.PHENOTYPE else 'provenance_abide_notice' if path == m.NOTICE else 'roi_timeseries'
        row = dict(path=path, role=role, size_bytes=len(raw), sha256=sha(raw))
        if role == 'roi_timeseries':
            fid = Path(path).name.removesuffix('_rois_cc200.1D'); index = ids.index(fid)
            row.update(file_id=fid, subject_id=str(int(fid.split('_')[1])), phenotype_row_index=1+2*index)
        if role == 'provenance_abide_notice':
            row['git_blob_sha1'] = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        (root/path).write_bytes(raw); records.append(row)
    manifest = dict(schema_version='fcstab-source-v1', task_id='FCSTAB-001',
                    dataset_id='ABIDE_pcp/cpac/filt_noglobal/rois_cc200', files=records,
                    participant_file_ids=ids, source_file_count=len(records),
                    source_bytes=sum(len(v) for v in payloads.values()))
    public = {}
    for name, raw in [('source_manifest.json', json.dumps(manifest).encode()),
                      ('method_contract.json', b'{"test":"method"}'),
                      ('output_schema.json', b'{"test":"schema"}'),
                      ('subject_ids.txt', ('\n'.join(ids)+'\n').encode())]:
        (docs/name).write_bytes(raw); public[name] = raw
    (root/'source_manifest.json').write_bytes(public['source_manifest.json'])
    policy = m.Policy(source_sha=sha(public['source_manifest.json']),
        method_sha=sha(public['method_contract.json']), schema_sha=sha(public['output_schema.json']),
        subject_ids_sha=sha(public['subject_ids.txt']), members=4, source_bytes=manifest['source_bytes'],
        subjects=2, phenotype_rows=5, phenotype_named=4, columns=3, total_frames=10, frame_min=5, frame_max=5)
    return dict(root=root, docs=docs, policy=policy, manifest=manifest, pheno=pheno, values=values)


def load(c, **kwargs):
    return m.load(c['root'], c['docs']/'source_manifest.json', c['docs']/'method_contract.json',
                  c['docs']/'output_schema.json', c['docs']/'subject_ids.txt', policy=c['policy'], **kwargs)


def repin(c, path, raw):
    (c['root']/path).write_bytes(raw)
    row = next(r for r in c['manifest']['files'] if r['path'] == path)
    row.update(size_bytes=len(raw), sha256=sha(raw))
    c['manifest']['source_bytes'] = sum(r['size_bytes'] for r in c['manifest']['files'])
    packed = json.dumps(c['manifest']).encode()
    for p in (c['docs']/'source_manifest.json', c['root']/'source_manifest.json'): p.write_bytes(packed)
    c['policy'] = replace(c['policy'], source_sha=sha(packed), source_bytes=c['manifest']['source_bytes'])


def test_complete_original_arrays_not_features(case):
    r = load(case)
    assert r['status'] == 'complete' and r['raw'].shape == (2, 5, 3)
    assert np.array_equal(r['raw'][0], case['values'])
    assert r['subject_ids'] == ['50003', '50004']
    assert len(r['phenotype_ledger']) == 5 and len(r['selected']) == 2
    assert r['phenotype_ledger'][0]['selected_derivative'] is False
    assert r['phenotype_ledger'][1]['source_subject_id_token'] == '050003'
    assert r['source_observed']['n_named_phenotype_rows'] == 4
    assert r['source_observed']['n_no_filename_rows'] == 1
    assert r['source_observed']['total_frames'] == 10
    assert r['authentication']['source_bytes_read'] == 2*case['policy'].source_bytes
    assert 'fisher_z' not in r and 'connectivity' not in r


@pytest.mark.parametrize('name', ['source_manifest.json','method_contract.json','output_schema.json','subject_ids.txt'])
def test_documents_hash_before_decoding(case, monkeypatch, name):
    (case['docs']/name).write_bytes(b'wrong')
    monkeypatch.setattr(m, 'decode_phenotype', lambda *a: pytest.fail('decoded'))
    with pytest.raises(ValueError): load(case)


def test_unfrozen_pin_fails_closed_before_original_decoding(case):
    with pytest.raises(ValueError, match='unfrozen_pin'):
        m.hashed_bytes(case['docs']/'method_contract.json', None, 1000)


@pytest.mark.parametrize('kind', ['extra','empty_dir','symlink','dangling','fifo','internal_manifest','missing'])
def test_closed_source_inventory(case, kind):
    root = case['root']
    if kind == 'extra': (root/'extra').write_text('x')
    elif kind == 'empty_dir': (root/'empty').mkdir()
    elif kind == 'symlink': (root/'link').symlink_to(root/m.PHENOTYPE)
    elif kind == 'dangling': (root/'link').symlink_to(root/'absent')
    elif kind == 'fifo': os.mkfifo(root/'pipe')
    elif kind == 'internal_manifest': (root/'source_manifest.json').write_text('{}')
    else: (root/m.PHENOTYPE).unlink()
    with pytest.raises((ValueError, OSError)): load(case)


def test_all_members_authenticated_before_decode(case, monkeypatch):
    path = case['root']/m.NOTICE; path.write_bytes(b'x'*path.stat().st_size)
    monkeypatch.setattr(m, 'decode_phenotype', lambda *a: pytest.fail('decoded'))
    with pytest.raises(ValueError, match='source_hash'): load(case)


@pytest.mark.parametrize('kind', ['header','width','blank','comment','nonfinite','nonascii','bad_float','frame_count'])
def test_roi_literal_shape_and_finite(case, kind):
    path = case['manifest']['files'][1]['path']; raw = (case['root']/path).read_bytes()
    if kind == 'header': raw = raw.replace(b'#1', b'#2', 1)
    elif kind == 'width': raw = raw.replace(b'0.0 0.1 1.0', b'0.0 0.1')
    elif kind == 'blank': raw = raw.replace(b'1.0 0.1 2.0', b'')
    elif kind == 'comment': raw = raw.replace(b'1.0 0.1 2.0', b'#1 2 3')
    elif kind == 'nonfinite': raw = raw.replace(b'0.1', b'nan', 1)
    elif kind == 'nonascii': raw += b'\xff'
    elif kind == 'bad_float': raw = raw.replace(b'0.1', b'bad', 1)
    else: raw += b'1 2 3\n'
    repin(case, path, raw)
    with pytest.raises(ValueError): load(case)


@pytest.mark.parametrize('kind', ['duplicate_header','blank_header','duplicate_id','duplicate_named','wrong_join','wrong_index','unselected_alias','short_row'])
def test_full_and_selected_phenotype_guards(case, kind):
    rows = case['pheno']
    if kind == 'duplicate_header': rows[0][-1] = rows[0][-2]
    elif kind == 'blank_header': rows[0][-1] = ''
    elif kind == 'duplicate_id': rows[3][1] = rows[2][1]
    elif kind == 'duplicate_named': rows[5][2] = rows[1][2]
    elif kind == 'wrong_join': rows[2][2] = 'Pitt_0050999'
    elif kind == 'wrong_index': rows[1], rows[2] = rows[2], rows[1]
    elif kind == 'unselected_alias': rows[1][2] = rows[2][2]
    else: rows[1].pop()
    repin(case, m.PHENOTYPE, pack_csv(rows))
    with pytest.raises(ValueError): load(case)


def test_late_source_identity_change(case):
    def progress(*unused):
        path = case['root']/m.PHENOTYPE; info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns+1000000000))
    with pytest.raises(ValueError, match='source_changed_after_consumption'): load(case, progress=progress)


def test_authenticate_kernel_source_not_cached_module(tmp_path, monkeypatch):
    path = tmp_path/'kernel.py'; raw = b'VALUE=123\n'; path.write_bytes(raw)
    poison = type(sys)('_fcstab_authenticated_public_kernel'); poison.VALUE = 999
    monkeypatch.setitem(sys.modules, poison.__name__, poison)
    assert m.load_kernel(path, sha(raw)).VALUE == 123
    assert sys.modules[poison.__name__] is poison
    with pytest.raises(ValueError): m.load_kernel(path, '0'*64)


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): m.strict_json(raw)
