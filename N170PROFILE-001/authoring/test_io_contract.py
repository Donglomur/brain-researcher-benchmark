"""Manufactured generic IO fixtures only; no dataset or scientific imports."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import struct
import sys
import warnings
import zipfile

import numpy as np
import pytest

SPEC=importlib.util.spec_from_file_location('n170_generic_io',Path(__file__).resolve().parents[1]/'tests'/'io_contract.py')
m=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=m;SPEC.loader.exec_module(m)


def put(tmp_path,raw,name='member'):
    p=tmp_path/name;p.write_bytes(raw);return p


def npy(a,version=(1,0)):
    b=io.BytesIO();np.lib.format.write_array(b,np.asarray(a),version=version,allow_pickle=True);return b.getvalue()


def archive(tmp_path,members,compression=zipfile.ZIP_STORED):
    b=io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(b,'w',compression=compression) as z:
            for name,raw in members:z.writestr(name,raw)
    return put(tmp_path,b.getvalue(),'arrays.npz')


def output(tmp_path):
    p=tmp_path/'output';p.mkdir()
    for name in m.FILES:(p/name).write_bytes(b'')
    return p


def test_declared_scope():
    assert m.FILES==('annotations.csv','trials.csv','erp_evidence.npz','per_subject.csv','n170.json','run_metadata.json','findings.md')
    assert m.LIMIT==32*1024**2 and m.AGGREGATE_LIMIT==128*1024**2


def test_authenticated_bytes(tmp_path):
    raw=b'opaque\x00content';p=put(tmp_path,raw)
    assert m.read_bytes(p,size=len(raw),sha256=hashlib.sha256(raw).hexdigest())==raw
    assert m.read_bytes(put(tmp_path,b'','empty'),limit=0,size=0)==b''


@pytest.mark.parametrize('kwargs,error',[
    ({'limit':True},'invalid_read_bound'),({'limit':m.LIMIT+1},'invalid_read_bound'),
    ({'size':True},'invalid_expected_size'),({'size':5},'size_mismatch'),
    ({'sha256':'X'*64},'invalid_expected_sha'),({'sha256':'0'*64},'sha256_mismatch'),
    ({'limit':1},'regular_file_bound')])
def test_read_bounds_and_pins(tmp_path,kwargs,error):
    with pytest.raises(ValueError,match=error):m.read_bytes(put(tmp_path,b'ab'),**kwargs)


@pytest.mark.parametrize('value',['relative','/tmp/../escape','/tmp/./file','/tmp/\x00file'])
def test_reject_path_spelling(value):
    with pytest.raises(ValueError):m.safe_path(value)


@pytest.mark.parametrize('dangling',[False,True])
def test_symlink_ancestor_and_leaf(tmp_path,dangling):
    target=tmp_path/'target'
    if not dangling:target.mkdir()
    link=tmp_path/'link';link.symlink_to(target,target_is_directory=True)
    for p in (link,link/'child'):
        with pytest.raises(ValueError,match='symlink_path'):m.safe_path(p)
    with pytest.raises(ValueError,match='path_traversal'):m.safe_path(str(link)+'/../other')


def test_regular_ancestor_and_fifo(tmp_path):
    p=put(tmp_path,b'x')
    with pytest.raises(ValueError,match='non_directory_ancestor'):m.safe_path(p/'child')
    fifo=tmp_path/'fifo';os.mkfifo(fifo)
    with pytest.raises(ValueError,match='regular_file_bound'):m.read_bytes(fifo)
    with pytest.raises(ValueError,match='regular_file_bound'):m.read_bytes(tmp_path)


def test_second_descriptor_hash_detects_coarse_stat_change(tmp_path,monkeypatch):
    p=put(tmp_path,b'abcd');held=p.stat()
    class Changed(io.BytesIO):
        def fileno(self):return 999
        def seek(self,*args):
            super().seek(0);super().write(b'wxyz');return super().seek(*args)
    def fake_fdopen(fd,mode):
        os.close(fd);return Changed(b'abcd')
    monkeypatch.setattr(m.os,'fdopen',fake_fdopen)
    monkeypatch.setattr(m.os,'fstat',lambda fd:held)
    with pytest.raises(ValueError,match='file_changed'):m.read_bytes(p)


def test_path_replacement_rejected(tmp_path,monkeypatch):
    p=put(tmp_path,b'abcd');old=p.stat();real_open=m.os.open
    def replaced(path,flags):
        moved=tmp_path/'prior';p.rename(moved);p.write_bytes(b'abcd')
        return real_open(path,flags)
    monkeypatch.setattr(m.os,'open',replaced)
    with pytest.raises(ValueError,match='file_replaced'):m.read_bytes(p)
    assert p.stat().st_ino!=old.st_ino


def test_output_exact_and_optional_flat_files(tmp_path):
    p=output(tmp_path);(p/'diagnostic.txt').write_text('descriptive only')
    assert set(m.output_files(p))==set(m.FILES)|{'diagnostic.txt'}


@pytest.mark.parametrize('kind',['missing','directory','symlink','fifo','failure_regular','failure_dangling'])
def test_output_closed_nonregular_and_failure(tmp_path,kind):
    p=output(tmp_path)
    if kind=='missing':(p/m.FILES[0]).unlink()
    elif kind=='directory':(p/'extra').mkdir()
    elif kind=='symlink':(p/'extra').symlink_to(p/'findings.md')
    elif kind=='fifo':os.mkfifo(p/'extra')
    elif kind=='failure_regular':(p/'failure_report.json').write_bytes(b'')
    else:(p/'failure_report.json').symlink_to(p/'absent')
    with pytest.raises(ValueError):m.output_files(p)


@pytest.mark.parametrize('bound,error', [('member','output_file_bound'),('aggregate','aggregate_output_bound'),('count','output_file_count_bound')])
def test_output_bounds(tmp_path,monkeypatch,bound,error):
    p=output(tmp_path)
    if bound=='member':monkeypatch.setattr(m,'LIMIT',2);(p/'extra').write_bytes(b'abc')
    elif bound=='aggregate':
        monkeypatch.setattr(m,'AGGREGATE_LIMIT',2)
        (p/'a').write_bytes(b'ab');(p/'b').write_bytes(b'c')
    else:monkeypatch.setattr(m,'MAX_OUTPUT_FILES',len(m.FILES)-1)
    with pytest.raises(ValueError,match=error):m.output_files(p)


@pytest.mark.parametrize('raw,error',[(b'{"x":1,"x":2}','duplicate_json_key'),
    (b'{"a":{"x":1,"x":2}}','duplicate_json_key'),(b'{"x":NaN}','nonfinite_json'),
    (b'[Infinity]','nonfinite_json'),(b'[-Infinity]','nonfinite_json'),(b'[1e999]','nonfinite_json')])
def test_json_rejections(raw,error):
    with pytest.raises(ValueError,match=error):m.json_bytes(raw)


def test_json_depth_bound_and_types():
    assert m.json_bytes(b'{"extra":[1,true,null,"text"]}')=={'extra':[1,True,None,'text']}
    with pytest.raises(ValueError,match='json_depth_bound'):m.json_bytes(b'['*65+b'0'+b']'*65)
    with pytest.raises(ValueError,match='json_byte_bound'):m.json_bytes('{}')


@pytest.mark.parametrize('value,expected',[('1',1),('1.0',1),('1e3',1000),('-0',0),(np.int32(7),7),(-2**63,-2**63),(2**63-1,2**63-1)])
def test_integer_valid(value,expected):assert m.integer(value)==expected


@pytest.mark.parametrize('value',[True,np.bool_(False),'1.1','NaN','Infinity',2**63,-2**63-1,None,'text'])
def test_integer_invalid(value):
    with pytest.raises(ValueError):m.integer(value)


@pytest.mark.parametrize('value',[True,np.bool_(True),'NaN','inf','1e999',None])
def test_number_invalid(value):
    with pytest.raises(ValueError):m.number(value)


def test_json_number_and_exact_large_integer():
    assert m.number('2.5')==2.5 and m.number(2,json_mode=True)==2
    with pytest.raises(ValueError,match='json_number_type'):m.number('2',json_mode=True)
    m.exact_json(2**53+1,2**53+1);m.exact_json(2.0,2)
    with pytest.raises(ValueError):m.exact_json(2**53+1,2**53)
    with pytest.raises(ValueError):m.exact_json(2**53,2**53+1)


@pytest.mark.parametrize('value,expected',[(True,True),(False,False),('TRUE',True),('false',False),('1',True),('0',False)])
def test_boolean_valid(value,expected):assert m.boolean(value) is expected


@pytest.mark.parametrize('value',[0,1,np.bool_(True),'yes',' true ',None])
def test_boolean_invalid(value):
    with pytest.raises(ValueError):m.boolean(value)


def test_exact_json_optional_keys_and_type_guards():
    m.exact_json({'a':[True,None,3.0],'extra':'okay'},{'a':[True,None,3]})
    for observed,expected in [(1,True),(True,1),('1',1),(0,None),([1,2],[1]),({}, {'x':1})]:
        with pytest.raises(ValueError):m.exact_json(observed,expected)


def test_close_finite_shape_and_tolerance():
    m.close([1.0000001],[1.0])
    for a,b in [([1],[1,2]),([np.nan],[0]),([2],[1])]:
        with pytest.raises(ValueError):m.close(a,b)


def test_csv_bom_reorder_extra_and_key_normalization(tmp_path):
    p=put(tmp_path,'\ufeffnote,id,value\r\n"descriptive, text",1,2.5\r\nother,2,3\r\n'.encode())
    rows=m.csv_read(p,['id','value'],2)
    assert rows[0]=={'note':'descriptive, text','id':'1','value':'2.5'}
    assert set(m.key_rows(rows,['id']))=={('1',),('2',)}
    rows[1]['id']='1.0'
    normalized=[dict(r,id=m.integer(r['id'])) for r in rows]
    with pytest.raises(ValueError,match='duplicate_scientific_key'):m.key_rows(normalized,['id'])


@pytest.mark.parametrize('raw,error',[(b'id,id\n1,2\n','csv_header'),(b'id, \n1,2\n','csv_header'),
    (b'other\n1\n','csv_header'),(b'id,x\n1\n','csv_shape_bound'),(b'id\n1,2\n','csv_shape_bound'),
    (b'id,x\n1,NaN\n','nonfinite_csv_extra'),(b'id,x\n1,Infinity\n','nonfinite_csv_extra'),
    (b'id\n"unclosed','csv_parse_or_field_bound')])
def test_csv_invalid(tmp_path,raw,error):
    with pytest.raises(ValueError,match=error):m.csv_read(put(tmp_path,raw),['id'],2)


def test_csv_bounds_and_field_limit_restored(tmp_path,monkeypatch):
    p=put(tmp_path,b'id\n1\n2\n')
    with pytest.raises(ValueError,match='csv_shape_bound'):m.csv_read(p,['id'],1)
    with pytest.raises(ValueError,match='csv_required_fields'):m.csv_read(p,['id','id'],2)
    before=m.csv.field_size_limit();monkeypatch.setattr(m,'MAX_CSV_FIELD',2)
    p.write_bytes(b'id\n123\n')
    with pytest.raises(ValueError,match='csv_parse_or_field_bound'):m.csv_read(p,['id'],1)
    assert m.csv.field_size_limit()==before


def test_key_rows_missing_duplicate_and_explicit_identity():
    with pytest.raises(ValueError,match='missing_row_key'):m.key_rows([{}],['id'])
    with pytest.raises(ValueError,match='duplicate_scientific_key'):m.key_rows([{'id':'a'},{'id':'a'}],['id'])
    assert len(m.key_rows([{'id':'01'},{'id':'1'}],['id']))==2


@pytest.mark.parametrize('dtype',['bool','int8','uint64','float32','float64','S5','U5'])
def test_npz_safe_storage(tmp_path,dtype):
    a=np.asarray([0,1],dtype=dtype)
    result=m.npz_read(archive(tmp_path,[('a.npy',npy(a))]))
    np.testing.assert_array_equal(result['a'],a)


@pytest.mark.parametrize('version',[(1,0),(2,0),(3,0)])
@pytest.mark.parametrize('compression',[zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED])
def test_npz_versions_fortran_scalar_and_extras(tmp_path,version,compression):
    a=np.asfortranarray(np.arange(24,dtype=np.float64).reshape(2,3,4))
    p=archive(tmp_path,[('cube.npy',npy(a,version)),('extra.npy',npy(np.asarray(3),version))],compression)
    got=m.npz_read(p);np.testing.assert_array_equal(got['cube'],a);assert got['extra'].shape==()


@pytest.mark.parametrize('a',[np.zeros((1,1,1,1)),np.array([object()],dtype=object),np.array([1j]),
    np.array([(1,)],dtype=[('x','i4')]),np.array([np.nan]),np.array([np.inf]),np.array([-np.inf])])
def test_npz_unsafe_dtype_dimension_and_nonfinite(tmp_path,a):
    with pytest.raises(ValueError):m.npz_read(archive(tmp_path,[('a.npy',npy(a))]))


def test_mask_never_licenses_nonfinite_placeholder(tmp_path):
    for value,valid in [(0.0,True),(np.nan,False)]:
        p=archive(tmp_path,[('present.npy',npy([False])),('value.npy',npy([value]))])
        if valid:assert m.npz_read(p)['value'][0]==0
        else:
            with pytest.raises(ValueError,match='npz_nonfinite'):m.npz_read(p)


@pytest.mark.parametrize(
    'name',
    ['../a.npy', 'a/b.npy', 'a\\b.npy', ':a.npy', '.npy', '..npy', 'a.txt'],
)
def test_npz_unsafe_names(tmp_path,name):
    with pytest.raises(ValueError,match='npz_member_name'):m.npz_read(archive(tmp_path,[(name,npy([1]))]))


def test_npz_duplicate_and_member_count(tmp_path,monkeypatch):
    with pytest.raises(ValueError,match='npz_member_count_or_duplicate'):
        m.npz_read(archive(tmp_path,[('a.npy',npy([1])),('a.npy',npy([2]))]))
    monkeypatch.setattr(m,'MAX_NPZ_MEMBERS',1)
    with pytest.raises(ValueError,match='npz_member_count_or_duplicate'):
        m.npz_read(archive(tmp_path,[('a.npy',npy([1])),('b.npy',npy([2]))]))


def test_npz_symlink_member(tmp_path):
    item=zipfile.ZipInfo('a.npy');item.create_system=3;item.external_attr=(stat.S_IFLNK|0o777)<<16
    with pytest.raises(ValueError,match='npz_nonregular_member'):m.npz_read(archive(tmp_path,[(item,npy([1]))]))


def test_npz_unsupported_compression(tmp_path):
    with pytest.raises(ValueError,match='npz_compression'):
        m.npz_read(archive(tmp_path,[('a.npy',npy([1]))],zipfile.ZIP_BZIP2))


def test_npz_encryption_flag_rejected_before_open(tmp_path):
    p=archive(tmp_path,[('a.npy',npy([1]))]);raw=bytearray(p.read_bytes())
    local=raw.index(b'PK\x03\x04');central=raw.index(b'PK\x01\x02')
    struct.pack_into('<H',raw,local+6,1);struct.pack_into('<H',raw,central+8,1);p.write_bytes(raw)
    with pytest.raises(ValueError,match='npz_member_name'):m.npz_read(p)


def test_npz_huge_claim_rejected_before_allocation(tmp_path,monkeypatch):
    b=io.BytesIO();np.lib.format.write_array_header_1_0(b,{'descr':'<f8','fortran_order':False,'shape':(2**40,)})
    p=archive(tmp_path,[('a.npy',b.getvalue())])
    monkeypatch.setattr(m.np,'load',lambda *a,**k:pytest.fail('allocation must not occur'))
    with pytest.raises(ValueError,match='npy_claimed_size'):m.npz_read(p)


def test_npz_expanded_bound(tmp_path,monkeypatch):
    p=archive(tmp_path,[('a.npy',npy(np.zeros(1000)))],zipfile.ZIP_DEFLATED)
    monkeypatch.setattr(m,'AGGREGATE_LIMIT',100)
    with pytest.raises(ValueError,match='npz_expanded_bound'):m.npz_read(p)


def test_npz_parse_uses_authenticated_buffer_only(tmp_path,monkeypatch):
    p=archive(tmp_path,[('a.npy',npy([7]))]);raw=p.read_bytes()
    def capture(_):p.write_bytes(b'not an archive');return raw
    monkeypatch.setattr(m,'read_bytes',capture)
    assert m.npz_read(p)['a'].tolist()==[7]
