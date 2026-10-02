"""Manufactured byte trees only; no original source, bank or fitting access."""
from dataclasses import replace
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location('fcmatur_source_fixture', Path(__file__).with_name('source_reference.py'))
s = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = s; SPEC.loader.exec_module(s)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def pack_csv(rows):
    stream = io.StringIO(newline=''); csv.writer(stream).writerows(rows)
    return stream.getvalue().encode()


def roi_bytes():
    t = np.arange(5.)
    x = np.column_stack((t, t, -t, np.full(5, .1)))
    return ('#1\t#2\t#3\t#4\n'+'\n'.join('\t'.join(str(v) for v in row) for row in x)+'\n').encode()


@pytest.fixture
def case(tmp_path):
    root, docs = tmp_path/'sources', tmp_path/'docs'
    (root/'roi').mkdir(parents=True); (root/'provenance').mkdir(); docs.mkdir()
    ids = ['Pitt_0050003', 'NYU_0050950']
    phenotype = [['', 'SUB_ID', 'FILE_ID', *s.FIELDS],
        ['0', '50002', 'no_filename', '', 'PITT', '-9999', '1', 'NaN'],
        ['1', '050003', ids[0], ' 12.5 ', ' PITT ', '1', '2', '0.15'],
        ['2', '50950', ids[1], '18', 'NYU', '2', '1', ''],
        ['3', '50009', 'no_filename', 'n/a', '', '', '', 'Inf']]
    payloads = {s.PHENOTYPE: pack_csv(phenotype), **{f'roi/{fid}_rois_cc200.1D':roi_bytes() for fid in ids},
                s.NOTICE:b'manufactured notice only\n'}
    rows = []
    for path, raw in payloads.items():
        row = dict(path=path, size_bytes=len(raw), sha256=sha(raw))
        if path == s.PHENOTYPE: row['role'] = 'phenotype'
        elif path == s.NOTICE:
            row['role'] = 'provenance_abide_notice'
            row['git_blob_sha1'] = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        else:
            fid = ids[len(rows)-1]
            row.update(role='roi_timeseries', file_id=fid, subject_id=str(int(fid.rsplit('_',1)[1])), phenotype_row_index=len(rows))
        rows.append(row); (root/path).write_bytes(raw)
    manifest = dict(schema_version='fcmatur-source-v2', task_id='FCMATUR-001',
                    dataset_id='ABIDE_pcp/cpac/filt_noglobal/rois_cc200', files=rows,
                    participant_file_ids=ids, source_file_count=4, source_bytes=sum(map(len,payloads.values())))
    raw = json.dumps(manifest).encode(); (root/'source_manifest.json').write_bytes(raw)
    manifest_path = docs/'source_manifest.json'; manifest_path.write_bytes(raw)
    method_path, schema_path = docs/'method.json', docs/'schema.json'
    method, schema = b'{"task_id":"FCMATUR-001","purpose":"manufactured"}', b'{"schema_version":"manufactured"}'
    method_path.write_bytes(method); schema_path.write_bytes(schema)
    policy = s.Policy(sha(raw), sha(method), sha(schema), file_count=4, source_bytes=manifest['source_bytes'],
                      roi_count=2, phenotype_rows=4, columns=4, total_frames=10, frame_min=2, frame_max=10)
    return dict(data_dir=root, method_path=method_path, schema_path=schema_path, manifest_path=manifest_path,
                policy=policy, manifest=manifest, phenotype=phenotype, ids=ids)


def run(c):
    return s._reconstruct(**{k:c[k] for k in ('data_dir','method_path','schema_path','manifest_path','policy')})


def repin(c, path=None, raw=None):
    if path is not None:
        (c['data_dir']/path).write_bytes(raw)
        record = next(r for r in c['manifest']['files'] if r['path'] == path)
        record.update(size_bytes=len(raw), sha256=sha(raw))
    c['manifest']['source_bytes'] = sum(r['size_bytes'] for r in c['manifest']['files'])
    packed = json.dumps(c['manifest']).encode()
    c['manifest_path'].write_bytes(packed); (c['data_dir']/'source_manifest.json').write_bytes(packed)
    c['policy'] = replace(c['policy'], source_sha=sha(packed), source_bytes=c['manifest']['source_bytes'])


def forbidden(*a, **kw): pytest.fail('unexpected parser/kernel/source operation')


def test_complete_independent_basis_and_no_original_mutations(case):
    before = {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in case['data_dir'].rglob('*') if p.is_file()}
    got = run(case)
    assert got['status'] == 'complete' and got['participant_ids'] == case['ids']
    assert len(got['phenotype_ledger']) == 4 and got['source_observed']['n_no_filename'] == 2
    assert not got['downstream_statistics_computed']
    assert got['authentication']['source_bytes_read'] == 2*case['policy'].source_bytes
    first = got['canonical_rows'][0]
    assert first['subject'] == case['ids'][0] and first['age'] == 12.5 and first['site_id'] == 'PITT'
    assert first['sex'] == 1 and first['typical_control'] is True
    assert got['canonical_rows'][1]['mean_fd'] is None
    assert got['canonical_rows'][1]['typical_control'] is False
    assert got['phenotype_ledger'][1]['source_subject_id_token'] == '050003'
    assert got['phenotype_ledger'][1]['tokens']['SITE_ID'] == ' PITT '
    assert got['persons'][case['ids'][0]]['active_columns'] == [True,True,True,False]
    assert got['persons'][case['ids'][0]]['n_edges'] == 3
    assert all(p.read_bytes() == b and p.stat().st_mtime_ns == t for p,(b,t) in before.items())


@pytest.mark.parametrize('token,kind,value,status', [
    ('', 'age', None, 'missing'), ('  ', 'mean_fd', None, 'missing'),
    (' 1.5 ', 'age', 1.5, 'ok'), ('0','age',None,'invalid_age'), ('120','age',None,'invalid_age'),
    ('-9999','age',None,'invalid_age'), ('nan','age',None,'invalid_numeric'),
    ('1e999','mean_fd',None,'invalid_numeric'), ('bad','mean_fd',None,'invalid_numeric'),
    ('-.1','mean_fd',None,'invalid_mean_fd'), ('0','mean_fd',0.,'ok'), ('999','mean_fd',999.,'ok'),
    ('1.0','sex',1,'ok'), ('2e0','dx_group',2,'ok'), ('1.5','sex',None,'invalid_code'),
    ('0','dx_group',None,'invalid_code'), ('-9999','sex',None,'invalid_code'),
    (' CASE_Site ','site','CASE_Site','ok'), ('','site',None,'missing')])
def test_frozen_token_policy(token, kind, value, status):
    assert s.normalized_token(token, kind) == (value, status)


def test_missing_site_does_not_remove_literal_cohort(case):
    case['phenotype'][2][4] = '  '
    repin(case, s.PHENOTYPE, pack_csv(case['phenotype']))
    result = run(case)
    assert len(result['canonical_rows']) == 2 and result['canonical_rows'][0]['site_id'] is None
    assert result['canonical_rows'][0]['connectivity'] is not None


@pytest.mark.parametrize('target', ['source','method','schema','internal'])
def test_document_pins_before_original_parsing(case, monkeypatch, target):
    path = {'source':case['manifest_path'],'method':case['method_path'],'schema':case['schema_path'],
            'internal':case['data_dir']/'source_manifest.json'}[target]
    path.write_bytes(b'{}')
    monkeypatch.setattr(s,'parse_roi',forbidden); monkeypatch.setattr(s,'phenotype_rows',forbidden)
    with pytest.raises(ValueError,match='metadata_digest'): run(case)


def test_public_unfrozen_pins_fail_closed_before_source_access(monkeypatch):
    monkeypatch.setattr(s,'METHOD_SHA',None); monkeypatch.setattr(s,'SCHEMA_SHA',None)
    monkeypatch.setattr(s,'safe_path',forbidden)
    with pytest.raises(ValueError,match='unfrozen_authority'): s.reconstruct()


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_json_duplicates_nonfinite(raw):
    with pytest.raises(ValueError): s.strict_json(raw)


def test_all_sources_authenticated_before_first_parse(case, monkeypatch):
    path = case['data_dir']/s.NOTICE; path.write_bytes(b'x'*path.stat().st_size)
    monkeypatch.setattr(s,'phenotype_rows',forbidden)
    with pytest.raises(ValueError,match='source_sha256'): run(case)


@pytest.mark.parametrize('kind',['extra','empty_directory','internal_missing','symlink','dangling','fifo'])
def test_closed_inventory_special_files(case, kind, monkeypatch):
    path = case['data_dir']/'unexpected'
    if kind == 'extra': path.write_bytes(b'x')
    elif kind == 'empty_directory': path.mkdir()
    elif kind == 'internal_missing': (case['data_dir']/'source_manifest.json').unlink()
    elif kind == 'symlink': path.symlink_to(case['data_dir']/s.PHENOTYPE)
    elif kind == 'dangling': path.symlink_to(case['data_dir']/'missing')
    else: os.mkfifo(path)
    monkeypatch.setattr(s,'phenotype_rows',forbidden)
    with pytest.raises((ValueError, FileNotFoundError)): run(case)


@pytest.mark.parametrize('kind',['count','order','duplicate_path','duplicate_index','bad_subject','traversal','wrong_role','bool_size','secondary_hash'])
def test_manifest_identity_rules(case, kind):
    obj = case['manifest']; row = obj['files'][1]
    if kind == 'count': obj['files'].pop()
    elif kind == 'order': obj['participant_file_ids'] = obj['participant_file_ids'][::-1]
    elif kind == 'duplicate_path': obj['files'][2]['path'] = row['path']
    elif kind == 'duplicate_index': obj['files'][2]['phenotype_row_index'] = row['phenotype_row_index']
    elif kind == 'bad_subject': row['subject_id'] = '9999'
    elif kind == 'traversal': row['path'] = '../escape'
    elif kind == 'wrong_role': row['role'] = 'bold'
    elif kind == 'bool_size': row['size_bytes'] = True
    else: row['md5'] = '0'*32
    repin(case)
    with pytest.raises(ValueError): run(case)


@pytest.mark.parametrize('kind',['duplicate_header','empty_other_header','short_row','duplicate_subject','wrong_literal','moved_row','no_filename_conflict'])
def test_phenotype_shape_literal_joins(case, kind):
    rows = case['phenotype']
    if kind == 'duplicate_header': rows[0][-1] = rows[0][-2]
    elif kind == 'empty_other_header': rows[0][-1] = ''
    elif kind == 'short_row': rows[1].pop()
    elif kind == 'duplicate_subject': rows[2][1] = rows[1][1]
    elif kind == 'wrong_literal': rows[2][2] = rows[2][2].lower()
    elif kind == 'moved_row': rows[2], rows[3] = rows[3], rows[2]
    else: rows[2][2] = 'no_filename'
    repin(case,s.PHENOTYPE,pack_csv(rows))
    with pytest.raises(ValueError): run(case)


@pytest.mark.parametrize('kind',['header','blank_frame','comment','width','nan','bad_numeric','too_short','nonascii'])
def test_roi_parser_full_finite_frame_axis(case, kind):
    row = case['manifest']['files'][1]; lines = roi_bytes().decode().splitlines()
    if kind == 'header': lines[0] = '#2\t#1\t#3\t#4'
    elif kind == 'blank_frame': lines.insert(2,'')
    elif kind == 'comment': lines[1] = '#ignore'
    elif kind == 'width': lines[1] = '1 2'
    elif kind in ('nan','bad_numeric'): lines[1] = ('nan' if kind == 'nan' else 'bad')+' 2 3 4'
    elif kind == 'too_short': lines = lines[:2]
    raw = ('\n'.join(lines)+'\n').encode()
    if kind == 'nonascii': raw += b'\xff'
    repin(case,row['path'],raw)
    with pytest.raises(ValueError): run(case)


def test_missing_source_frame_total_not_hidden_drop(case):
    case['policy'] = replace(case['policy'], total_frames=11)
    with pytest.raises(ValueError,match='complete_source_frames'): run(case)


@pytest.mark.parametrize('kind',['during_parse','later_member','metadata_after'])
def test_descriptor_and_final_identity_after_consumption(case, monkeypatch, kind):
    original = s.parse_roi; count = []
    def parse(raw, policy):
        result = original(raw, policy); count.append(True)
        if len(count) == 1:
            if kind == 'during_parse': path = case['data_dir']/case['manifest']['files'][1]['path']
            elif kind == 'later_member': path = case['data_dir']/case['manifest']['files'][2]['path']
            else: path = case['method_path']
            path.write_bytes(b'x'*path.stat().st_size)
            # The parser consumes a hash-authenticated immutable buffer. This
            # fixture tests the additional stat-identity guard, not detection
            # of rewrites hidden by the filesystem timestamp resolution.
            stamp = path.stat()
            os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
        return result
    monkeypatch.setattr(s,'parse_roi',parse)
    with pytest.raises(ValueError): run(case)


def test_private_numerics_source_not_cached_or_public(monkeypatch):
    fake = type(sys)('source_numerics'); fake.connectivity = forbidden
    monkeypatch.setitem(sys.modules,'source_numerics',fake)
    assert s.load_numerics().connectivity(np.column_stack((np.arange(3),np.arange(3))))['status'] == 'ok'
    monkeypatch.setattr(s,'NUMERICS_SHA','0'*64)
    with pytest.raises(ValueError,match='metadata_digest'): s.load_numerics()


def test_no_legacy_or_downstream_imports():
    import ast
    tree = ast.parse(Path(s.__file__).read_text())
    names = [a.name for node in ast.walk(tree) if isinstance(node,ast.Import) for a in node.names]
    names += [node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    assert not any('kernel' in name or 'stager' in name or 'solution' in name or 'opaque' in name for name in names)
