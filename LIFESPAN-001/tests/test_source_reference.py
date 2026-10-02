"""Manufactured authentication, same-buffer decoding and source schema cases."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct

import nibabel as nib
import numpy as np
import pytest

import io_contract as c
import source_reference as s


def digest(raw): return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def source_tree(tmp_path, monkeypatch):
    root = tmp_path / "original"; root.mkdir()
    ids = [f"s{i:02d}" for i in range(59)]
    files = []
    def add(path, role, **fields):
        raw = path.encode()
        target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        files.append(dict(path=path, role=role, size_bytes=len(raw), sha256=digest(raw), **fields))
    for person in ids:
        for hemi in ("lh", "rh"): add(f"{person}/{hemi}.gii", "surface_timeseries", subject_id=person, hemisphere=hemi)
    for hemi in ("lh", "rh"): add(hemi+".annot", "surface_annotation", hemisphere=hemi)
    add("phenotype.csv", "phenotype")
    manifest = dict(files=files, n_original_files=121, total_original_bytes=sum(r["size_bytes"] for r in files))
    mraw = json.dumps(manifest).encode(); (root / "source_manifest.json").write_bytes(mraw)
    cohort = dict(subject_ids=ids, n_subjects=59)
    craw = json.dumps(cohort).encode(); cp = tmp_path / "cohort.json"; cp.write_bytes(craw)
    method = dict(source_manifest_sha256=digest(mraw), source_notice_sha256=s.NOTICE_SHA256,
                  cohort=dict(manifest_sha256=digest(craw),n_subjects=59),
                  output=dict(schema_document_sha256=s.OUTPUT_CONTRACT_SHA256))
    raw = json.dumps(method).encode(); mp = tmp_path / "method.json"; mp.write_bytes(raw)
    for name,value in (("SOURCE_SHA256",digest(mraw)),("METHOD_SHA256",digest(raw)),("COHORT_SHA256",digest(craw)),("TOTAL_BYTES",manifest["total_original_bytes"])):
        monkeypatch.setattr(s,name,value)
    return root,mp,cp,manifest


def test_closed_121_positive(source_tree):
    root,mp,cp,m = source_tree
    assert len(s.authenticate(root,mp,cp)[3]["files"]) == 121


@pytest.mark.parametrize("case", ["changed", "missing", "extra_file", "extra_empty_dir", "symlink", "fifo", "manifest_changed", "method_changed", "cohort_changed"])
def test_auth_refuses_before_decoder(source_tree, monkeypatch, case):
    root,mp,cp,m = source_tree
    first = root / m["files"][0]["path"]
    if case == "changed": first.write_bytes(b"!"*first.stat().st_size)
    elif case == "missing": first.unlink()
    elif case == "extra_file": (root / "extra").write_text("extra")
    elif case == "extra_empty_dir": (root / "empty").mkdir()
    elif case == "symlink": first.unlink(); first.symlink_to(mp)
    elif case == "fifo": first.unlink(); os.mkfifo(first)
    else:
        path = {"manifest_changed":root/"source_manifest.json", "method_changed":mp, "cohort_changed":cp}[case]
        path.write_bytes(path.read_bytes()+b" ")
    monkeypatch.setattr(s,"parse_surface",lambda *a: pytest.fail("decoder reached"))
    with pytest.raises(ValueError): s.authenticate(root,mp,cp)


def test_source_mutation_after_auth_cannot_supply_decoder(source_tree):
    root,mp,cp,m = source_tree
    s.authenticate(root,mp,cp)
    row = m["files"][0]
    (root / row["path"]).write_bytes(b"!"*row["size_bytes"])
    with pytest.raises(ValueError): s.source_bytes(root,row)


def test_no_mutable_helper_import(source_tree):
    root,mp,cp,m = source_tree
    (root / "stage_data.py").write_text("raise RuntimeError('must not import')")
    with pytest.raises(ValueError,match="inventory"): s.authenticate(root,mp,cp)


@pytest.mark.parametrize("suffix", ["/../out", "/./out"])
def test_raw_traversal_rejected_before_normalization(tmp_path,suffix):
    with pytest.raises(ValueError): c.safe_path(str(tmp_path)+suffix)


def test_symlink_ancestor(tmp_path):
    (tmp_path / "link").symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError): c.safe_path(tmp_path / "link" / "out")


def annotation_bytes(version=2):
    stream=io.BytesIO()
    def integer(x): stream.write(struct.pack(">i",x))
    def text(x): b=x.encode()+b"\0"; integer(len(b)); stream.write(b)
    table=[("Unknown",(0,0,0,0)),("cortexA",(1,0,0,0)),("Medial_wall",(2,0,0,0)),("cortexB",(3,0,0,0))]
    integer(5)
    for i,label in enumerate((1,1,2,3,3)): integer(i); integer(label)
    integer(1)
    if version==2: integer(-2); integer(4); text("source"); integer(4)
    else: integer(4); text("source")
    for i,(name,color) in enumerate(table):
        if version==2: integer(i)
        text(name)
        for value in color: integer(value)
    return stream.getvalue()


@pytest.mark.parametrize("version",[1,2])
def test_independent_annotation_parser(version):
    cortical,allrows=s.parse_annotation(annotation_bytes(version),"lh",5)
    assert [r["annotation_id"] for r in cortical]==[1,3]
    assert [r["vertices"].tolist() for r in cortical]==[[0,1],[3,4]]
    assert allrows[2]["vertex_count"]==1


@pytest.mark.parametrize("case",["truncated","trailing","unknown","wrong_count","bad_version"])
def test_annotation_rejections(case):
    raw=annotation_bytes()
    if case=="truncated": raw=raw[:-3]
    elif case=="trailing": raw+=b"!"
    elif case=="unknown": raw=raw[:8]+struct.pack(">i",99)+raw[12:]
    elif case=="wrong_count": raw=struct.pack(">i",6)+raw[4:]
    else: raw=raw[:48]+struct.pack(">i",-9)+raw[52:]
    with pytest.raises(ValueError): s.parse_annotation(raw,"lh",5)


def gifti_bytes():
    arrays=[]
    for i in range(3):
        a=nib.gifti.GiftiDataArray(np.arange(5,dtype=np.float32)+i,intent=2001)
        a.meta["TimeStep"]="1000.000000"
        arrays.append(a)
    return nib.gifti.GiftiImage(darrays=arrays).to_bytes()


def test_gifti_same_buffer_decode():
    a,observed=s.parse_surface(gifti_bytes(),3,5)
    assert a.shape==(3,5) and a.dtype==np.float32
    assert observed["intents"]==[2001]


@pytest.mark.parametrize("old,new",[(b'ExternalFileName=""',b'ExternalFileName="external"'),
    (b'Dim0="5"',b'Dim0="6"'),(b'1000.000000',b'0.645000000'),
    (b'NIFTI_INTENT_TIME_SERIES',b'NIFTI_INTENT_NONE'),
    (b'GZipBase64Binary',b'ExternalFileBinary')])
def test_gifti_metadata_failclosed(old,new):
    raw=gifti_bytes(); assert old in raw
    with pytest.raises(ValueError): s.parse_surface(raw.replace(old,new),3,5)


def test_gifti_nonfinite_values():
    im=nib.gifti.GiftiImage.from_bytes(gifti_bytes());im.darrays[0].data[0]=np.nan
    with pytest.raises(ValueError):s.parse_surface(im.to_bytes(),3,5)


def test_phenotype_literal_join():
    raw=b',Age,Dominant Hand,Sex\nx,21.125,R,original\nz,50,L,Z\ny,33,R,Y\n'
    rows,total=s.parse_phenotype(raw,["y","x"])
    assert total==3 and rows["x"]["sex"]=="original" and rows["y"]["phenotype_row_index"]==2


@pytest.mark.parametrize("raw",[
    b'ID,Age,Dominant Hand,Sex\nx,2,R,M\n',b',Age,Dominant Hand,Sex\nx,nan,R,M\n',
    b',Age,Dominant Hand,Sex\nx,-1,R,M\n',b',Age,Dominant Hand,Sex\nx,2,R,M\nx,3,R,F\n',
    b',Age,Dominant Hand,Sex\ny,2,R,M\n',b',Age,Dominant Hand,Sex\nx,2,R\n'])
def test_phenotype_rejections(raw):
    with pytest.raises(ValueError):s.parse_phenotype(raw,["x"])


def test_pinned_same_buffer_json(tmp_path):
    path=tmp_path/"json";raw=b'{"x":1}';path.write_bytes(raw)
    assert c.pinned_json(path,digest(raw))=={"x":1}
    path.write_bytes(b'{"x":2}')
    with pytest.raises(ValueError):c.pinned_json(path,digest(raw))
