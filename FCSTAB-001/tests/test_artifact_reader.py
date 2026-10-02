"""Source-free malformed/typed/bounded artifact fixtures, never executed here."""
from decimal import Decimal
import io as memory_io
import json
import os
import stat
import struct
import zipfile

import numpy as np
import pytest

import artifact_reader as reader


@pytest.mark.parametrize("raw",[
    b'{"a":1,"a":2}', b'{"a":{"x":1,"x":2}}', b'{"x":NaN}',
    b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}', b'[]',
    b'null', b'{', b'\xff', b'{"x":'+b'['*66+b'0'+b']'*66+b'}'])
def test_json_malformed_or_nonfinite(raw):
    with pytest.raises(reader.ArtifactError): reader.parse_json(raw)


def test_json_bom_typed_number_and_extra_fields():
    result = reader.parse_json(b'\xef\xbb\xbf{"x":1.25,"n":2,"ok":true,"z":null,"extra":{"finite":0}}')
    assert result["x"] == Decimal("1.25") and result["ok"] is True


@pytest.mark.parametrize("value",[True,False,None,[],{},"nan","inf","-inf",2**64])
def test_invalid_integer(value):
    with pytest.raises(reader.ArtifactError): reader.integer(value)


@pytest.mark.parametrize("value",[True,None,[],{},"nan","inf","-inf"])
def test_invalid_real(value):
    with pytest.raises(reader.ArtifactError): reader.real(value)


@pytest.mark.parametrize("function",[reader.real,reader.integer])
def test_json_numbers_are_not_numeric_strings(function):
    with pytest.raises(reader.ArtifactError): function("2",json_number=True)
    assert function(2.0,json_number=True) == 2


@pytest.mark.parametrize("token",["2","2.0","2e0","+2"," 2 "])
def test_csv_numerical_notation(token):
    assert reader.integer(token) == 2 and reader.real(token) == 2


@pytest.mark.parametrize("raw",[
    b'a,a\n1,2\n',b'a,\n1,2\n',b'a,b\n1\n',b'a,b\n1,2,3\n',
    b'a\n\x00\n',b'\xff',b'a,b\n"unfinished,2\n'])
def test_bad_csv(raw):
    with pytest.raises(reader.ArtifactError): reader.parse_csv(raw)


def test_csv_bom_crlf_extra_column():
    assert reader.parse_csv(b'\xef\xbb\xbfa,b,extra\r\n1,2,note\r\n') == [{"a":"1","b":"2","extra":"note"}]


def test_csv_row_limit(monkeypatch):
    monkeypatch.setitem(reader.CAPS,"rows",1)
    with pytest.raises(reader.ArtifactError): reader.parse_csv(b'a\n1\n2\n')


def npy(array):
    output = memory_io.BytesIO()
    np.lib.format.write_array(output,array,allow_pickle=True)
    return output.getvalue()


def archive(members, *, compression=zipfile.ZIP_DEFLATED):
    output = memory_io.BytesIO()
    with zipfile.ZipFile(output,"w",compression=compression) as handle:
        for name,raw in members: handle.writestr(name,raw)
    return output.getvalue()


@pytest.mark.parametrize("array",[
    np.array([np.nan]),np.array([np.inf]),np.array([complex(1,2)]),
    np.array([object()],dtype=object),np.zeros(1,dtype=[("a","f8")]),
    np.array([b'\xff'],dtype='S1')])
def test_bad_npz_dtype_or_values(array):
    with pytest.raises(reader.ArtifactError): reader.parse_npz(archive([("x.npy",npy(array))]))


@pytest.mark.parametrize("name",["../x.npy","a/x.npy","a\\x.npy",".npy","x.txt"])
def test_unsafe_npz_member_names(name):
    with pytest.raises(reader.ArtifactError): reader.parse_npz(archive([(name,npy(np.arange(3)))]))


def test_npz_duplicate():
    with pytest.warns(UserWarning): raw = archive([("x.npy",npy(np.arange(3)))]*2)
    with pytest.raises(reader.ArtifactError): reader.parse_npz(raw)


def test_npz_link_rejected():
    member = zipfile.ZipInfo("x.npy")
    member.create_system = 3; member.external_attr = (stat.S_IFLNK|0o777)<<16
    with pytest.raises(reader.ArtifactError): reader.parse_npz(archive([(member,b'target')]))


def test_npz_members_cap(monkeypatch):
    monkeypatch.setitem(reader.CAPS,"members",1)
    with pytest.raises(reader.ArtifactError): reader.parse_npz(archive([("x.npy",npy(np.arange(3))),("y.npy",npy(np.arange(3)))]))


def test_npz_expanded_cap(monkeypatch):
    monkeypatch.setitem(reader.CAPS,"expanded",100)
    with pytest.raises(reader.ArtifactError): reader.parse_npz(archive([("x.npy",npy(np.zeros(1000)))]))


def test_npy_huge_declared_shape_does_not_allocate():
    header = repr({"descr":"<f8","fortran_order":False,"shape":(2**50,)}).encode()+b'\n'
    raw = b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header
    with pytest.raises(reader.ArtifactError): reader.parse_npz(archive([("x.npy",raw)]))


def test_npy_trailing_or_truncated_bytes():
    for raw in (npy(np.arange(3))+b'extra',npy(np.arange(3))[:-1]):
        with pytest.raises(reader.ArtifactError): reader.parse_npz(archive([("x.npy",raw)]))


def test_npz_safe_types_and_fortran_layout():
    arrays = {"z":np.asfortranarray(np.arange(12,dtype=np.float32).reshape(3,4)),
              "s":np.array(["literal","ids"]),"b":np.array([True,False]),"x":np.zeros((1,)*32)}
    parsed = reader.parse_npz(archive([(key+".npy",npy(value)) for key,value in arrays.items()]))
    for key in arrays: assert np.array_equal(parsed[key],arrays[key])


@pytest.mark.parametrize("array",[np.array([True]),np.array([.5]),np.array([2**63],dtype=np.uint64),np.array([float(2**63)])])
def test_integer_axis_bad(array):
    with pytest.raises(reader.ArtifactError): reader.integer_array(array)


def test_integer_axis_value_equivalence():
    assert reader.integer_array(np.array([1.,2.])).tolist() == [1,2]


@pytest.mark.parametrize("kind",["member","parent","dangling","fifo"])
def test_path_refusal(tmp_path,kind):
    root = tmp_path/"real"; root.mkdir(); target = root/"x"; target.write_bytes(b'abc')
    if kind=="member":
        path = tmp_path/"link"; path.symlink_to(target)
    elif kind=="parent":
        parent = tmp_path/"link"; parent.symlink_to(root,target_is_directory=True); path = parent/"x"
    elif kind=="dangling":
        path = tmp_path/"link"; path.symlink_to(root/"absent")
    else:
        path = tmp_path/"pipe"; os.mkfifo(path)
    with pytest.raises(reader.ArtifactError): reader.read_bytes(path,10)
    assert target.read_bytes() == b'abc'


def test_safe_bounded_read(tmp_path):
    path = tmp_path/"x"; path.write_bytes(b'abc')
    assert reader.read_bytes(path,3) == b'abc'
    with pytest.raises(reader.ArtifactError): reader.read_bytes(path,2)


def test_zero_sized_read_refused(tmp_path):
    path = tmp_path/"x"; path.touch()
    with pytest.raises(reader.ArtifactError): reader.read_bytes(path,10)


def test_output_inventory_caps_precede_parsing(tmp_path,monkeypatch):
    root = tmp_path/"out"; root.mkdir()
    (root/"extra").write_bytes(b'12345')
    monkeypatch.setitem(reader.CAPS,"total",4)
    with pytest.raises(reader.ArtifactError,match="entire output"): reader.read_artifacts(root)


def test_output_inventory_special_extra_rejected(tmp_path):
    root = tmp_path/"out"; root.mkdir(); os.mkfifo(root/"extra")
    with pytest.raises(reader.ArtifactError,match="nonregular"): reader.read_artifacts(root)
