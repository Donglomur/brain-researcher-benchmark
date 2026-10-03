"""Manufactured hostile/benign artifact bytes only; no original sources."""
import csv
from contextlib import nullcontext
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import zipfile

import numpy as np
import pytest

SPEC=importlib.util.spec_from_file_location('devconn_io_test',Path(__file__).with_name('io_contract.py'))
I=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(I)


def npz(**arrays):
    stream=io.BytesIO(); np.savez_compressed(stream,**arrays); return stream.getvalue()


def npy(array):
    stream=io.BytesIO(); np.save(stream,array); return stream.getvalue()


def zip_members(members,compression=zipfile.ZIP_STORED):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=compression) as archive:
        for key,value in members: archive.writestr(key,value)
    return stream.getvalue()


def table(columns=None,row=None):
    columns=list(I.CSV_COLUMNS) if columns is None else columns
    row=['sub-pixar001','8','child','.1','4',*(['.2']*3),*(['ok']*3),*(['2']*4)] if row is None else row
    text=io.StringIO(newline=''); writer=csv.writer(text); writer.writerow(columns); writer.writerow(row)
    return text.getvalue().encode()


@pytest.fixture
def output(tmp_path):
    root=tmp_path/'output'; root.mkdir()
    contents={'signal_evidence.npz':npz(x=np.zeros((2,3))),
        'connectivity_metrics.csv':table(),'age_effects.json':b'{}','run_metadata.json':b'{}',
        'findings.md':b'No prespecified direction.'}
    for name,raw in contents.items(): (root/name).write_bytes(raw)
    return root


def test_reader_accepts_regular_nested_extras_without_touching_inputs(output):
    extra=output/'notes'/'subdir'; extra.mkdir(parents=True); (extra/'detail.txt').write_text('extra')
    before={p:p.read_bytes() for p in output.rglob('*') if p.is_file()}
    result=I.read_output(output)
    assert set(result)==set(I.FILES)
    assert result['connectivity_metrics.csv'][0]['subject_id']=='sub-pixar001'
    assert all(path.read_bytes()==value for path,value in before.items())


@pytest.mark.parametrize('mode',['file','broken_symlink','directory'])
def test_failure_marker_always_authoritative(output,mode):
    target=output/'failure_report.json'
    if mode=='file': target.write_bytes(b'{}')
    elif mode=='directory': target.mkdir()
    else: target.symlink_to(output/'absent')
    with pytest.raises(ValueError,match='failed_run_marker'): I.read_output(output)


@pytest.mark.parametrize('mode',['missing','symlink','fifo','file_count','directory_count','depth','total','single_file','findings'])
def test_output_namespace_and_caps(output,monkeypatch,mode):
    target=output/'findings.md'
    if mode=='missing': target.unlink()
    elif mode=='symlink': target.unlink(); target.symlink_to(output/'age_effects.json')
    elif mode=='fifo': target.unlink(); os.mkfifo(target)
    elif mode=='file_count': monkeypatch.setattr(I,'MAX_FILES',4)
    elif mode=='directory_count': monkeypatch.setattr(I,'MAX_DIRS',0); (output/'x').mkdir()
    elif mode=='depth': monkeypatch.setattr(I,'MAX_DEPTH',0); (output/'x').mkdir()
    elif mode=='total': monkeypatch.setattr(I,'LIMIT',20)
    elif mode=='single_file': monkeypatch.setitem(I.FILE_CAPS,'findings.md',2)
    else: target.write_bytes(b' \n ')
    with pytest.raises(ValueError): I.read_output(output)


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e999}',
    b'['*66+b'0'+b']'*66,b'\xff'])
def test_json_invalid_bytes_rejected(raw):
    with pytest.raises((ValueError,UnicodeError)): I.json_bytes(raw)


def test_json_finite_typed_extras_preserved():
    assert I.json_bytes(b'{"x":true,"y":null,"z":[1,"n/a"]}')==dict(x=True,y=None,z=[1,'n/a'])


@pytest.mark.parametrize('mode',['duplicate','blank','missing','ragged','too_many','nonfinite_extra','nul'])
def test_csv_structural_rejections(mode):
    columns=list(I.CSV_COLUMNS); row=['s','8','child','.1','4',*(['.2']*3),*(['ok']*3),*(['2']*4)]
    if mode=='duplicate': columns[-1]=columns[-2]
    elif mode=='blank': columns[-1]=''
    elif mode=='missing': columns[-1]='other'
    elif mode=='ragged': row.pop()
    elif mode=='nonfinite_extra': columns+=['extra']; row+=['1e9999']
    raw=table(columns,row)
    if mode=='nul': raw+=b'\0'
    with pytest.raises(ValueError): I.csv_bytes(raw,max_rows=0 if mode=='too_many' else 155)


def test_csv_harmless_columns_and_scientific_notation():
    row=['s','8','child','1e-2','4',*(['2e-1']*3),*(['ok']*3),*(['2']*4),'free text','2e3']
    parsed=I.csv_bytes(table(list(I.CSV_COLUMNS)+['note','extra'],row))
    assert parsed[0]['mean_fd']=='1e-2' and parsed[0]['note']=='free text'


@pytest.mark.parametrize('dtype',['float32','float64','int16','uint32','bool','U8','S8'])
def test_npz_safe_kinds_and_fortran_order(dtype):
    value=np.array([[1,2],[3,4]],dtype=dtype,order='F')
    decoded=I.npz_bytes(npz(value=value,highdim=np.zeros((1,)*32)))
    assert np.array_equal(decoded['value'],value) and decoded['highdim'].ndim==32


@pytest.mark.parametrize('mode',['object','complex','structured','nonfinite','duplicate','traversal','backslash','colon',
    'unknown_compression','symlink','expanded_cap','member_count','fake_shape','trailing_bytes'])
def test_npz_malformed_or_unsafe_rejected(monkeypatch,mode):
    array=np.array([1.,2.]); name='x.npy'; data=None
    if mode=='object': array=np.array([object()],dtype=object)
    elif mode=='complex': array=np.array([1j])
    elif mode=='structured': array=np.zeros(2,dtype=[('x','f8')])
    elif mode=='nonfinite': array=np.array([np.inf])
    elif mode=='traversal': name='../x.npy'
    elif mode=='backslash': name='x\\y.npy'
    elif mode=='colon': name='x:y.npy'
    elif mode=='expanded_cap': monkeypatch.setattr(I,'LIMIT',200)
    elif mode=='member_count': monkeypatch.setattr(I,'MAX_NPZ_MEMBERS',0)
    if mode=='symlink':
        name=zipfile.ZipInfo('x.npy'); name.create_system=3; name.external_attr=(stat.S_IFLNK|0o777)<<16
    payload=npy(array)
    if mode=='fake_shape':
        stream=io.BytesIO(); np.lib.format.write_array_header_1_0(stream,{'descr':'<f8','fortran_order':False,'shape':(10**10,)})
        payload=stream.getvalue()
    elif mode=='trailing_bytes': payload+=b'extra'
    members=[(name,payload)]* (2 if mode=='duplicate' else 1)
    if mode=='expanded_cap': members.append(('second.npy',payload))
    with pytest.warns(UserWarning) if mode=='duplicate' else nullcontext():
        data=zip_members(members,zipfile.ZIP_BZIP2 if mode=='unknown_compression' else zipfile.ZIP_STORED)
    with pytest.raises((ValueError,zipfile.BadZipFile)): I.npz_bytes(data)


def test_read_bytes_hash_and_size_are_same_buffer(output):
    path=output/'findings.md'; raw=path.read_bytes()
    assert I.read_bytes(path,len(raw),size=len(raw),sha256=hashlib.sha256(raw).hexdigest())==raw
    with pytest.raises(ValueError): I.read_bytes(path,len(raw)-1)
    with pytest.raises(ValueError): I.read_bytes(path,sha256='0'*64)


def test_late_marker_during_parse_rejected(output,monkeypatch):
    original=I.json_bytes
    def parse(*args,**kwargs):
        result=original(*args,**kwargs); (output/'failure_report.json').write_bytes(b'{}'); return result
    monkeypatch.setattr(I,'json_bytes',parse)
    with pytest.raises(ValueError,match='failed_run_marker'): I.read_output(output)


def test_late_same_size_rewrite_during_parse_rejected(output,monkeypatch):
    original=I.json_bytes; target=output/'findings.md'
    def parse(*args,**kwargs):
        result=original(*args,**kwargs); before=target.stat()
        target.write_bytes(b'x'*before.st_size)
        os.utime(target,ns=(before.st_atime_ns,before.st_mtime_ns+1_000_000_000))
        return result
    monkeypatch.setattr(I,'json_bytes',parse)
    with pytest.raises(ValueError,match='output_changed'): I.read_output(output)
