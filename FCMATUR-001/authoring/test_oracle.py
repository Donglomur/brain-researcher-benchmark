"""Manufactured oracle QA only; no original paths, banks, network or downloads."""
import argparse
import csv
from dataclasses import replace
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import warnings

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'solution'))

import compute
import source_reader as source


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def emit_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')
    return sha(path.read_bytes())


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / 'originals'
    root.mkdir()
    (root/'roi').mkdir()
    (root/'provenance').mkdir()
    ids = [f'Site_{i:07d}' for i in range(1, 13)]
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['', 'SUB_ID', 'FILE_ID', *source.TOKEN_FIELDS, 'unused_sensitive'])
    for i, fid in enumerate(ids):
        writer.writerow([str(i), str(i+1), fid, str(7+i), ' A ' if i < 6 else 'B',
                         str(1+i%2), str(1+(i%3 != 0)), str(i/100), 'not-exported'])
    writer.writerow(['12', '13', 'no_filename', '19', 'A', '1', '2', '', 'not-exported'])
    contents = {source.PHENOTYPE: buf.getvalue().encode(), source.NOTICE: b'Original source notice\n'}
    raw_arrays = {}
    for i, fid in enumerate(ids):
        x = np.random.RandomState(i).normal(size=(8, 4))
        x[:, 3] = 0.1
        raw_arrays[fid] = x
        contents[f'roi/{fid}_rois_cc200.1D'] = ('#1\t#2\t#3\t#4\n' +
            '\n'.join('\t'.join(repr(float(v)) for v in row) for row in x) + '\n').encode()
    rows = []
    for name, raw in contents.items():
        (root/name).write_bytes(raw)
        record = dict(path=name, size_bytes=len(raw), sha256=sha(raw), md5=hashlib.md5(raw).hexdigest())
        if name == source.PHENOTYPE:
            record['role'] = 'phenotype'
        elif name == source.NOTICE:
            record.update(role='provenance_abide_notice', git_blob_sha1=hashlib.sha1(
                f'blob {len(raw)}\0'.encode()+raw).hexdigest())
        else:
            fid = next(s for s in ids if name == f'roi/{s}_rois_cc200.1D')
            record.update(role='roi_timeseries', file_id=fid, subject_id=str(ids.index(fid)+1),
                          phenotype_row_index=ids.index(fid))
        rows.append(record)
    manifest = dict(schema_version='fcmatur-source-v2', task_id='FCMATUR-001',
        dataset_id='ABIDE_pcp/cpac/filt_noglobal/rois_cc200', files=rows,
        participant_file_ids=list(ids), source_file_count=len(rows), source_bytes=sum(map(len, contents.values())))
    public = tmp_path/'source_manifest.json'
    manifest_sha = emit_json(public, manifest)
    (root/'source_manifest.json').write_bytes(public.read_bytes())
    kernel = Path(os.environ.get('FCMATUR_KERNEL_PATH', str(Path(__file__).parents[1]/'environment'/'statistics_kernel.py')))
    assert kernel.is_file() and sha(kernel.read_bytes()) == source.KERNEL_SHA
    method, schema = tmp_path/'method.json', tmp_path/'schema.json'
    method_sha = emit_json(method, dict(numerical_kernel=dict(sha256=source.KERNEL_SHA)))
    schema_sha = emit_json(schema, dict(required_files=list(compute.FILES), csv=dict(required_columns=list(compute.CSV_COLUMNS)),
        limits=dict(csv_bytes=16*1024**2, json_bytes=16*1024**2, text_bytes=1024**2, entire_output_tree_bytes=64*1024**2)))
    policy = source.Policy(manifest_sha, method_sha, schema_sha, members=len(rows), source_bytes=manifest['source_bytes'],
        subjects=12, phenotype_rows=13, columns=4, total_frames=96, frame_min=8, frame_max=8)
    args = argparse.Namespace(data_dir=str(root), manifest_path=str(public), method_path=str(method), schema_path=str(schema),
        kernel_path=str(kernel), output_dir=str(tmp_path/'output'), private_dir=str(tmp_path/'private'),
        report=str(tmp_path/'report.json'), print_contract=False)
    return dict(root=root, public=public, method=method, schema=schema, kernel=kernel, policy=policy,
                args=args, manifest=manifest, ids=ids, arrays=raw_arrays)


def load(b):
    return source.load(b['root'], b['public'], b['method'], b['schema'], b['kernel'], policy=b['policy'])


def writer_loader(monkeypatch, b):
    original = source.load
    def manufactured(*args, **kwargs):
        return original(*args, **kwargs, policy=b['policy'])
    monkeypatch.setattr(source, 'load', manufactured)


def fingerprints(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def test_source_basis_and_independent_math(bundle):
    before = fingerprints(bundle['root'])
    basis = load(bundle)
    assert basis['participant_ids'] == bundle['ids'] and len(basis['phenotype_ledger']) == 13
    assert basis['phenotype_ledger'][-1]['source_path'] is None
    assert basis['phenotype_ledger'][0]['tokens']['SITE_ID'] == ' A '
    assert basis['phenotype_ledger'][0]['normalized']['site_id'] == 'A'
    assert 'unused_sensitive' not in json.dumps(basis['phenotype_ledger'])
    assert basis['source_observed']['phenotype_columns'][-1] == 'unused_sensitive'
    assert basis['authentication']['source_bytes_read'] == 2*bundle['policy'].source_bytes
    for fid, values in bundle['arrays'].items():
        p = basis['persons'][fid]
        assert p['active_columns'] == [True, True, True, False]
        assert p['exact_constant_columns'] == [4] and p['n_edges'] == 3
        r = np.corrcoef(values[:, :3].T)[np.triu_indices(3, 1)]
        expected = math.fsum(np.arctanh(np.clip(r, -.999, .999))) / 3
        assert p['connectivity'] == pytest.approx(expected, abs=1e-14)
    assert fingerprints(bundle['root']) == before


@pytest.mark.parametrize('field,token,expected,status', [
    ('age','',None,'missing'), ('age','NaN',None,'invalid_numeric'), ('age','inf',None,'invalid_numeric'),
    ('age','broken',None,'invalid_numeric'), ('age','0',None,'invalid_age'), ('age','120',None,'invalid_age'),
    ('age',' 6.5 ',6.5,'ok'), ('mean_fd','-9999',None,'invalid_mean_fd'), ('mean_fd','1000',1000.,'ok'),
    ('sex','1.0',1,'ok'), ('sex','1.5',None,'invalid_code'), ('dx_group','3',None,'invalid_code'),
    ('dx_group','2',2,'ok'), ('site_id',' Ab-C ', 'Ab-C','ok'), ('site_id','',None,'missing')])
def test_normalization(field, token, expected, status):
    assert source.token_value(token, field) == (expected, status)


@pytest.mark.parametrize('change', ['blank_record', 'empty_column', 'duplicate_column', 'wrong_id', 'wrong_file', 'short_row'])
def test_phenotype_malformed(bundle, change):
    rows = list(csv.reader(io.StringIO((bundle['root']/source.PHENOTYPE).read_text())))
    if change == 'blank_record': rows.insert(1, [])
    if change == 'empty_column': rows[0][2] = ''
    if change == 'duplicate_column': rows[0][-1] = 'SEX'
    if change == 'wrong_id': rows[1][1] = '99'
    if change == 'wrong_file': rows[1][2] = rows[1][2].lower()
    if change == 'short_row': rows[1].pop()
    text = io.StringIO(newline=''); csv.writer(text).writerows(rows)
    with pytest.raises(ValueError):
        source.decode_phenotype(text.getvalue().encode(), bundle['manifest']['files'], bundle['policy'])


@pytest.mark.parametrize('body', ['#2\t#1\n1 2\n3 4', '#1\t#2\n1 nan\n3 4', '#1\t#2\n1 2\n',
                                  '#1\t#2\n1 2\n\n3 4', '#1\t#2\n1 2 #comment\n3 4', '#1\t#2\n1 inf\n3 4',
                                  '#1\t#2\n1 2\n3x 4', '#1\t#2\n1 2\n3 4 5'])
def test_bad_roi(body):
    with pytest.raises(ValueError):
        source.decode_roi(body.encode(), replace(source.Policy(), columns=2, frame_min=2, frame_max=2))


def test_every_source_authenticated_before_parse(bundle, monkeypatch):
    (bundle['root']/bundle['manifest']['files'][-1]['path']).write_bytes(b'bad')
    monkeypatch.setattr(source, 'decode_phenotype', lambda *a: pytest.fail('parsed before full authentication'))
    with pytest.raises(ValueError): load(bundle)


@pytest.mark.parametrize('kind', ['extra', 'extra_dir', 'missing', 'symlink', 'fifo', 'internal_manifest', 'public_manifest', 'kernel'])
def test_source_and_pin_failures(bundle, kind, tmp_path):
    root = bundle['root']
    if kind == 'extra': (root/'extra').write_text('x')
    if kind == 'extra_dir': (root/'empty').mkdir()
    if kind in ('missing', 'symlink', 'fifo'):
        path = root/bundle['manifest']['files'][-1]['path']
        path.unlink()
        if kind == 'symlink': path.symlink_to(bundle['public'])
        if kind == 'fifo': os.mkfifo(path)
    if kind == 'internal_manifest': (root/'source_manifest.json').write_text('{}')
    if kind == 'public_manifest': bundle['public'].write_text('{}')
    if kind == 'kernel':
        path = tmp_path/'poison.py'; path.write_text("raise RuntimeError('EXECUTED')")
        bundle['kernel'] = path
    with pytest.raises(ValueError): load(bundle)


def test_source_changed_during_consumption(bundle, monkeypatch):
    real = source.decode_roi
    path = bundle['root']/f"roi/{bundle['ids'][0]}_rois_cc200.1D"
    def altered(raw, policy):
        result = real(raw, policy)
        old = path.stat()
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns+1000000000))
        return result
    monkeypatch.setattr(source, 'decode_roi', altered)
    with pytest.raises(ValueError, match='changed'): load(bundle)


def test_successful_writer_uses_full_kernel_receipts(bundle, monkeypatch):
    writer_loader(monkeypatch, bundle)
    before = fingerprints(bundle['root'])
    result = compute.compute(bundle['args'])
    output = Path(bundle['args'].output_dir)
    assert result['status'] == 'complete' and result['n_source'] == 12
    assert {p.name for p in output.iterdir()} == set(compute.FILES)
    rows = list(csv.DictReader((output/'connectivity.csv').open()))
    assert list(rows[0]) == list(compute.CSV_COLUMNS) and rows[0]['site_id_status'] == 'ok'
    assert rows[0]['base_eligible'] == 'true'
    meta = json.loads((output/'run_metadata.json').read_text())
    assert meta['status'] == 'complete' and len(meta['phenotype_ledger']) == 13
    assert set(meta['software']) == {'python', 'numpy', 'scipy'} and meta['warnings'] == []
    primary = json.loads((output/'connectivity_age.json').read_text())
    assert set(primary) == {'schema_version', 'status', *compute.PRIMARY_KEYS}
    assert primary['pooled']['unit'] == 'participant' and primary['between_site']['unit'] == 'site'
    findings = (output/'findings.md').read_text()
    assert findings.count('95% CI=') == 3 and findings.count('estimate status=') == 3
    for row in (primary['pooled'], primary['within_site'], primary['between_site']):
        assert f"n={row['n']} {row['unit']} units" in findings
        assert row['ci_status'] in findings and row['p_status'] in findings
    assert len(json.loads((output/'sensitivity.json').read_text())['checks']) == 5
    assert fingerprints(bundle['root']) == before


@pytest.mark.parametrize('stage', ['early', 'metadata', 'inventory', 'report'])
def test_failure_marker_early_and_late(bundle, monkeypatch, stage):
    writer_loader(monkeypatch, bundle)
    if stage == 'early':
        monkeypatch.setattr(source, 'load', lambda *a, **k: (_ for _ in ()).throw(ValueError('early')))
    elif stage == 'inventory':
        monkeypatch.setattr(compute, 'output_inventory', lambda *a: (_ for _ in ()).throw(ValueError('inventory')))
    else:
        original = compute.write_json
        target = 'run_metadata.json' if stage == 'metadata' else 'report.json'
        def failed(path, value):
            if path.name == target: raise ValueError(stage)
            return original(path, value)
        monkeypatch.setattr(compute, 'write_json', failed)
    with pytest.raises(ValueError): compute.compute(bundle['args'])
    marker = Path(bundle['args'].output_dir)/'failure_report.json'
    assert json.loads(marker.read_text())['status'] == 'failed_precondition'
    if stage == 'report': assert (marker.parent/'run_metadata.json').is_file()


@pytest.mark.parametrize('existing_marker', [False, True, 'dangling'])
def test_stale_output_never_overwritten(bundle, existing_marker):
    output = Path(bundle['args'].output_dir); output.mkdir()
    (output/'findings.md').write_text('old immutable evidence')
    marker = output/'failure_report.json'
    if existing_marker is True: marker.write_text('prior failure')
    if existing_marker == 'dangling': marker.symlink_to(output/'missing')
    with pytest.raises(ValueError, match='fresh_destination'): compute.compute(bundle['args'])
    assert (output/'findings.md').read_text() == 'old immutable evidence'
    if existing_marker is True: assert marker.read_text() == 'prior failure'
    elif existing_marker == 'dangling': assert marker.is_symlink()
    else: assert json.loads(marker.read_text())['status'] == 'failed_precondition'


@pytest.mark.parametrize('kind', ['source', 'source_child', 'source_parent', 'kernel', 'method', 'linked_output', 'overlap_private'])
def test_output_guards_no_source_writes(bundle, kind, tmp_path):
    args = bundle['args']; before = fingerprints(bundle['root'])
    if kind == 'source': args.output_dir = str(bundle['root'])
    if kind == 'source_child': args.output_dir = str(bundle['root']/'out')
    if kind == 'source_parent': args.output_dir = str(bundle['root'].parent)
    if kind == 'kernel': args.output_dir = str(bundle['kernel'])
    if kind == 'method': args.output_dir = str(bundle['method'])
    if kind == 'linked_output':
        Path(args.output_dir).symlink_to(bundle['root'])
    if kind == 'overlap_private': args.private_dir = args.output_dir
    with pytest.raises(ValueError): compute.compute(args)
    assert fingerprints(bundle['root']) == before and not (bundle['root']/'failure_report.json').exists()


def test_metadata_captures_warnings(bundle, monkeypatch):
    original = source.load
    def load_warning(*args, **kwargs):
        warnings.warn('manufactured diagnostic')
        return original(*args, **kwargs, policy=bundle['policy'])
    monkeypatch.setattr(source, 'load', load_warning)
    compute.compute(bundle['args'])
    metadata = json.loads((Path(bundle['args'].output_dir)/'run_metadata.json').read_text())
    assert metadata['warnings'] == ['manufactured diagnostic']


def test_wrapper_help_is_import_safe(tmp_path):
    wrapper = Path(compute.__file__).with_name('solve.sh')
    result = subprocess.run(['bash', str(wrapper), '--help'], capture_output=True, text=True, timeout=15,
                            cwd=tmp_path, env={**os.environ, 'DATA_DIR': '/absent-manufactured-source'})
    assert result.returncode == 0 and '--output-dir' in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":1e999}', b'{"a":NaN}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): source.strict_json(raw)
