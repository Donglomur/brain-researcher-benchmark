"""Source identity/staging mechanics only; no scientific fits or source downloads."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENV = Path(__file__).parents[1]/"environment"
spec = importlib.util.spec_from_file_location("petref_stage", ENV/"stage_data.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def manifest():
    return json.loads((ENV/"source_manifest.json").read_text())


def tiny_record(data=b"mechanics only\n"):
    return {"path":"tiny.txt", "size_bytes":len(data), "sha256":hashlib.sha256(data).hexdigest(),
        "git_blob_sha1":hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest(),
        "git_entry_kind":"direct_text_blob", "url":"https://example.invalid/no-network"}


def test_manifest_whole_file_pin_and_source_scope():
    source, _ = stage.read_manifest(ENV/"source_manifest.json")
    assert len(source["files"]) == 24
    assert sum(r["role"] == "tac" for r in source["files"]) == 4
    assert sum(r["size_bytes"] for r in source["files"]) == 270682
    assert not any("_km-" in r["path"] or r["path"].endswith(".nii.gz") for r in source["files"])
    assert source["derivative_provenance"]["extraction_rerun"] is False


@pytest.mark.parametrize("field,value", [("dataset_id","ds000001"),("snapshot","latest"),
    ("license","unknown"),("git_tree_sha1","0"*40),("git_tag_commit_sha1","0"*40)])
def test_reject_wrong_snapshot_identity(field,value):
    source=manifest(); source[field]=value
    with pytest.raises(ValueError): stage.validate_manifest(source)


@pytest.mark.parametrize("kind",["drop","duplicate","traversal","absolute","role","subject","session","url","size","sha","gitsha","entrykind","pointer","md5"])
def test_reject_mutated_source_contract(kind):
    source=manifest(); record=next(r for r in source["files"] if r["role"]=="extraction_log")
    if kind=="drop": source["files"].pop()
    elif kind=="duplicate": source["files"].append(copy.deepcopy(record))
    elif kind=="traversal": record["path"]="../outside"
    elif kind=="absolute": record["path"]="/outside"
    elif kind=="role": record["role"]="tac"
    elif kind=="subject": record["subject"]="sub-99"
    elif kind=="session": record["session"]="ses-99"
    elif kind=="url": record["url"]="https://example.invalid/source"
    elif kind=="size": record["size_bytes"]=-1
    elif kind=="sha": record["sha256"]="not a digest"
    elif kind=="gitsha": record["git_blob_sha1"]="0"*40
    elif kind=="entrykind": record["git_entry_kind"]="other"
    elif kind=="pointer": record["annex_pointer"] += "changed"
    elif kind=="md5": record["annex_md5"]="0"*32
    with pytest.raises(ValueError): stage.validate_manifest(source)


def test_edited_manifest_cannot_refresh_source_pins(tmp_path):
    path=tmp_path/"manifest.json"; path.write_text(json.dumps(manifest()))
    with pytest.raises(ValueError,match="manifest SHA256"): stage.read_manifest(path)


@pytest.mark.parametrize("kind",["size","sha256","git_blob_sha1","annex_md5"])
def test_content_checksums_are_independent(tmp_path,kind):
    data=b"mechanics only\n"; path=tmp_path/"tiny.txt"; path.write_bytes(data)
    record=tiny_record(data)
    if kind=="size": record["size_bytes"] += 1
    elif kind=="annex_md5": record.update(git_entry_kind="annex_symlink",annex_md5="0"*32)
    else: record[kind]="0"*len(record[kind])
    with pytest.raises(ValueError): stage.verify_file(path,record)


def test_valid_direct_and_annex_checksums(tmp_path):
    data=b"mechanics only\n"; path=tmp_path/"tiny.txt"; path.write_bytes(data)
    record=tiny_record(data); stage.verify_file(path,record)
    record.update(git_entry_kind="annex_symlink",annex_md5=hashlib.md5(data).hexdigest())
    stage.verify_file(path,record)


def test_stream_download_is_size_bounded(tmp_path,monkeypatch):
    record=tiny_record()
    monkeypatch.setattr(stage.urllib.request,"urlopen",lambda *a,**k:io.BytesIO(b"x"*100))
    with pytest.raises(ValueError,match="exceeds pinned size"):
        stage.download_file(record,tmp_path/"out")


def test_download_requires_correct_content(tmp_path,monkeypatch):
    record=tiny_record()
    monkeypatch.setattr(stage.urllib.request,"urlopen",lambda *a,**k:io.BytesIO(b"x"*record["size_bytes"]))
    with pytest.raises(ValueError,match="SHA256"):
        stage.download_file(record,tmp_path/"out")


def test_local_staging_rehashes_and_is_idempotent(tmp_path,monkeypatch):
    data=b"mechanics only\n"; record=tiny_record(data)
    source=tmp_path/"source"; source.mkdir(); (source/record["path"]).write_bytes(data)
    monkeypatch.setattr(stage,"read_manifest",lambda path:({"files":[record]},b"fixture manifest"))
    monkeypatch.setattr(stage.urllib.request,"urlopen",lambda *a,**k:pytest.fail("local reuse must not download"))
    destination=tmp_path/"destination"
    for _ in range(2): stage.stage_data(destination,tmp_path/"unused",source)
    assert (destination/record["path"]).read_bytes()==data
    assert (destination/record["path"]).stat().st_mode & 0o222 == 0


def test_corrupt_local_source_does_not_publish(tmp_path,monkeypatch):
    record=tiny_record(); source=tmp_path/"source"; source.mkdir()
    (source/record["path"]).write_bytes(b"x"*record["size_bytes"])
    monkeypatch.setattr(stage,"read_manifest",lambda path:({"files":[record]},b"fixture"))
    destination=tmp_path/"destination"
    with pytest.raises(ValueError): stage.stage_data(destination,tmp_path/"unused",source)
    assert not destination.exists()


def test_existing_conflicting_destination_is_preserved(tmp_path,monkeypatch):
    record=tiny_record(); destination=tmp_path/"destination"; destination.mkdir()
    (destination/record["path"]).write_bytes(b"retain conflicting old source")
    monkeypatch.setattr(stage,"read_manifest",lambda path:({"files":[record]},b"fixture"))
    with pytest.raises(ValueError): stage.stage_data(destination,tmp_path/"unused")
    assert (destination/record["path"]).read_bytes()==b"retain conflicting old source"
