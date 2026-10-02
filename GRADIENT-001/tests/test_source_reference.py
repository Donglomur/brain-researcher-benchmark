"""Source-auth safety on tiny manufactured bytes only; no image/body acquisition."""
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import numpy as np
import pytest
import artifact_reader as a
import source_reference as s


def bundle(tmp_path,monkeypatch):
    root=tmp_path/"source"; root.mkdir(); rows=[]
    for i in range(46):
        name=f"file{i:03d}"; body=f"manufactured {i}".encode()
        (root/name).write_bytes(body)
        rows.append(dict(path=name,role="provenance",participant_id=None,size_bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    body=json.dumps(dict(files=rows)).encode(); (root/"source_manifest.json").write_bytes(body)
    monkeypatch.setattr(s,"SOURCE_SHA256",hashlib.sha256(body).hexdigest())
    return root,rows


def test_good_closed_bundle(tmp_path,monkeypatch):
    root,rows=bundle(tmp_path,monkeypatch)
    manifest,identities=s.authenticate_source(root)
    assert manifest["files"]==rows and len(identities)==46


@pytest.mark.parametrize("kind",["manifest","corrupt","missing","extra","extra_directory","symlink","dangling","fifo"])
def test_source_changes_rejected(tmp_path,monkeypatch,kind):
    root,rows=bundle(tmp_path,monkeypatch); file=root/rows[0]["path"]
    if kind=="manifest": (root/"source_manifest.json").write_text('{"files":[]}')
    elif kind=="corrupt": file.write_bytes(b"x"*file.stat().st_size)
    elif kind=="missing": file.unlink()
    elif kind=="extra": (root/"unknown").write_text("extra")
    elif kind=="extra_directory": (root/"unknown").mkdir()
    else:
        file.unlink()
        if kind=="fifo": os.mkfifo(file)
        elif kind=="symlink": file.symlink_to(root/rows[1]["path"])
        else: file.symlink_to(root/"absent")
    with pytest.raises((a.ArtifactError,OSError)): s.authenticate_source(root)


def test_poisoned_mutable_stage_helper_not_imported(tmp_path,monkeypatch):
    root,_=bundle(tmp_path,monkeypatch)
    poison=types.SimpleNamespace(verify_staged=lambda *_:pytest.fail("mutable helper executed"))
    monkeypatch.setitem(sys.modules,"stage_data",poison)
    monkeypatch.setitem(sys.modules,"source_stage",poison)
    assert len(s.authenticate_source(root)[0]["files"])==46


def test_same_buffer_hash_and_parse(tmp_path,monkeypatch):
    path=tmp_path/"manifest.json"; body=b'{"original":1}'; path.write_bytes(body)
    parser=a.parse_json
    def replace_after_read(buffer):
        path.write_text('{"attacker":2}')
        return parser(buffer)
    monkeypatch.setattr(a,"parse_json",replace_after_read)
    assert s.authenticated_json(path,hashlib.sha256(body).hexdigest(),"manufactured")=={"original":1}


@pytest.mark.parametrize("body",[b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}',b'[]'])
def test_authenticated_invalid_json_still_rejected(tmp_path,body):
    path=tmp_path/"json"; path.write_bytes(body)
    with pytest.raises(a.ArtifactError): s.authenticated_json(path,hashlib.sha256(body).hexdigest(),"manufactured")


def test_not_frozen_does_not_open_path(tmp_path):
    with pytest.raises(a.ArtifactError,match="pin not frozen"):
        s.authenticated_json(tmp_path/"nonexistent",None,"manufactured")


def test_source_replacement_after_authentication(tmp_path,monkeypatch):
    root,rows=bundle(tmp_path,monkeypatch); _,identities=s.authenticate_source(root)
    old=root/rows[0]["path"]; replacement=tmp_path/"replacement"
    replacement.write_bytes(old.read_bytes()); replacement.replace(old)
    with pytest.raises(a.ArtifactError,match="source changed"):
        s.unchanged(root,rows[0]["path"],identities)


@pytest.mark.parametrize("path",["../escape","/absolute","a//b","a/./b","a/../b","a\\b"])
def test_pinned_malformed_paths_rejected(tmp_path,monkeypatch,path):
    root,rows=bundle(tmp_path,monkeypatch); rows[0]["path"]=path
    body=json.dumps(dict(files=rows)).encode(); (root/"source_manifest.json").write_bytes(body)
    monkeypatch.setattr(s,"SOURCE_SHA256",hashlib.sha256(body).hexdigest())
    with pytest.raises(a.ArtifactError,match="unsafe source path"): s.authenticate_source(root)


@pytest.mark.parametrize("mode", ["count", "duplicate", "size_bool", "size_negative", "digest", "role", "participant"])
def test_manifest_exact_count_and_entry_types(tmp_path, monkeypatch, mode):
    root, rows = bundle(tmp_path, monkeypatch)
    if mode == "count": rows.pop()
    elif mode == "duplicate": rows[1] = rows[0]
    elif mode == "size_bool": rows[0]["size_bytes"] = True
    elif mode == "size_negative": rows[0]["size_bytes"] = -1
    elif mode == "digest": rows[0]["sha256"] = "g" * 64
    elif mode == "role": rows[0]["role"] = 1
    else: rows[0]["participant_id"] = True
    body = json.dumps(dict(files=rows)).encode(); (root / "source_manifest.json").write_bytes(body)
    monkeypatch.setattr(s, "SOURCE_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(a.ArtifactError): s.authenticate_source(root)


def test_same_size_changed_source_rehashes_on_every_authentication(tmp_path, monkeypatch):
    root, rows = bundle(tmp_path, monkeypatch)
    s.authenticate_source(root)
    path = root / rows[0]["path"]; before = path.stat()
    path.write_bytes(b"x" * before.st_size)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(a.ArtifactError, match="digest"):
        s.authenticate_source(root)


def test_source_table_is_strict_and_same_buffer_authenticated(tmp_path):
    path = tmp_path / "table.tsv"; body = b"id\tvalue\na\t1\n"
    path.write_bytes(body)
    row = dict(path=path.name, size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    identities = {path.name: s.verify_file(path, row)}
    assert s.source_table(tmp_path, row, identities, "\t") == (["id", "value"], [{"id": "a", "value": "1"}])
    bad = b"id\tid\na\t1\n"; path.write_bytes(bad)
    row.update(size_bytes=len(bad), sha256=hashlib.sha256(bad).hexdigest())
    identities[path.name] = s.verify_file(path, row)
    with pytest.raises(a.ArtifactError, match="columns"):
        s.source_table(tmp_path, row, identities, "\t")


def test_manufactured_nifti_calibration_header_and_single_source_binding(tmp_path):
    import nibabel as nib
    path = tmp_path / "image.nii"
    obj = nib.Nifti1Image(np.zeros((2, 3, 4, 5), dtype=np.int16), np.eye(4))
    obj.header.set_slope_inter(2., 3.)
    nib.save(obj, path)
    body = path.read_bytes()
    row = dict(path=path.name, role="bold", size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    identities = {path.name: s.verify_file(path, row)}
    image, metadata = s.image(tmp_path, row, identities)
    assert metadata["shape"] == [2, 3, 4, 5]
    assert metadata["effective_scaling_slope"] == 2 and metadata["effective_scaling_intercept"] == 3
    assert np.dtype(metadata["source_dtype"]) == np.dtype(np.int16)
    assert np.array_equal(image.get_fdata(), np.full((2, 3, 4, 5), 3.))


def test_authentication_failure_precedes_any_nifti_decode(tmp_path, monkeypatch):
    import nibabel as nib
    monkeypatch.setattr(s, "authenticated_json", lambda *args: {})
    def fail_auth(*args): raise a.ArtifactError("manufactured identity failure")
    monkeypatch.setattr(s, "authenticate_source", fail_auth)
    monkeypatch.setattr(nib, "load", lambda *args: pytest.fail("source parsed before authentication"))
    with pytest.raises(a.ArtifactError, match="identity failure"):
        s.reconstruct(tmp_path, tmp_path / "method", tmp_path / "schema")
