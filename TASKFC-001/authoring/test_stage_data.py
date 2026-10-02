"""Manufactured staging fixtures only; never original files or real requests."""
from email.message import Message
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import time
from urllib.error import HTTPError
from urllib.request import HTTPDefaultErrorHandler, Request
import zipfile
import pytest

spec=importlib.util.spec_from_file_location("taskfc_stager",Path(__file__).resolve().parents[1] / "environment" / "stage_data.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
COMMIT="a"*40


def row(path,raw,**kwargs):
    return dict(path=path,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),md5=hashlib.md5(raw).hexdigest(),**kwargs)


def github(raw=b"notice"):
    return row("notice.rst",raw,source_commit=COMMIT,source_url=f"https://raw.githubusercontent.com/nilearn/nilearn/{COMMIT}/notice.rst")


def write(p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)


class Response(io.BytesIO):
    def __init__(self,url,body=b"",code=200,headers=None):
        super().__init__(body);self.url=url;self.code=code;self.headers=Message()
        for k,v in (headers or [("Content-Type","application/octet-stream"),("Content-Length",str(len(body)))]):self.headers[k]=v
    def geturl(self):return self.url
    def read1(self,n):
        assert self.code==200,"error/redirect body must not be read"
        return super().read(n)


def bundle(tmp_path,monkeypatch):
    source=tmp_path/"source";source.mkdir();docs=tmp_path/"docs";docs.mkdir()
    bodies={"sub-01/data.bin":b"opaque one","README":b"opaque two","access_data.py":b"inert source code"}
    zipped=io.BytesIO()
    with zipfile.ZipFile(zipped,"w",zipfile.ZIP_DEFLATED) as z:
        for p,b in bodies.items():z.writestr(p,b)
    zipbytes=zipped.getvalue();zippath=tmp_path/"toy.zip";zippath.write_bytes(zipbytes)
    archive=dict(size_bytes=len(zipbytes),sha256=hashlib.sha256(zipbytes).hexdigest(),md5=hashlib.md5(zipbytes).hexdigest(),archive_id="language_localizer_demo_v1",filename="language_localizer.zip",source_guid="3dj2a",source_version=1,osf_node="5dr8p",osf_object_id="5ec46aadf3e87e0080578178",source_url="https://osf.io/download/3dj2a/?revision=1",required_members=list(bodies),inventory=m.zip_inventory(zippath))
    rows=[]
    for p,b in bodies.items():rows.append(row(p,b,archive_id=archive["archive_id"],archive_member=p));write(source/p,b)
    notice=github();rows.append(notice);write(source/notice["path"],b"notice")
    manifest=dict(n_files=len(rows),total_bytes=sum(r["size_bytes"] for r in rows),files=rows,archives=[archive]);raw=json.dumps(manifest).encode();path=docs/"source_manifest.json";path.write_bytes(raw)
    monkeypatch.setattr(m,"MANIFEST_SHA256",hashlib.sha256(raw).hexdigest());monkeypatch.setattr(m,"EXPECTED_COUNT",len(rows));monkeypatch.setattr(m,"EXPECTED_BYTES",manifest["total_bytes"])
    water="https://files.ca-1.osf.io/v1/resources/5dr8p/providers/osfstorage/5ec46aadf3e87e0080578178?revision=1"
    signed="https://storage.googleapis.com/cos-osf-prod-files-ca-1/"+archive["sha256"]+"?Signature=SECRET"
    calls=[]
    def transport(url,timeout,etag=None):
        calls.append(url);assert 0<timeout<=m.SOCKET_SECONDS and etag is None
        if url==notice["source_url"]:return Response(url,b"notice")
        if url==archive["source_url"]:return Response(url,b"unread",302,[("Location",water)])
        if url==water:return Response(url,b"unread",302,[("Location",signed)])
        assert url==signed
        return Response(url,zipbytes)
    return source,path,manifest,transport,calls


def test_public_two_starts_then_offline_verify(tmp_path,monkeypatch,capsys):
    source,path,manifest,transport,calls=bundle(tmp_path,monkeypatch)
    dest=tmp_path/"new-parent/data";work=tmp_path/"work"
    result=m.stage(dest,work,path,transport=transport)
    assert result["status"]=="ok" and result["transfer_starts"]==2 and result["network_requests"]==4
    assert result["network_body_bytes"]==manifest["archives"][0]["size_bytes"]+6
    assert m.verify_staged(dest)==manifest
    assert "SECRET" not in (work/"result.json").read_text()+capsys.readouterr().out
    assert not (dest/"language_localizer.zip").exists()
    for r in manifest["files"]:
        assert (dest/r["path"]).read_bytes()==(source/r["path"]).read_bytes()
        assert stat.S_IMODE((dest/r["path"]).stat().st_mode)==0o444


@pytest.mark.parametrize("with_manifest",[True,False])
def test_local_copy_no_network_or_source_mutation(tmp_path,monkeypatch,with_manifest):
    source,path,manifest,_,_=bundle(tmp_path,monkeypatch)
    if with_manifest:write(source/"source_manifest.json",path.read_bytes())
    before={p:(p.read_bytes(),m.signature(p.stat())) for p in source.rglob("*") if p.is_file()}
    r=m.stage(tmp_path/"out",tmp_path/"work",path,source,lambda *a:pytest.fail("network"))
    assert r["network_requests"]==0 and m.verify_staged(tmp_path/"out")==manifest
    assert all((p.read_bytes(),m.signature(p.stat()))==v for p,v in before.items())


def test_all_auth_before_copy(tmp_path,monkeypatch):
    source,path,manifest,_,_=bundle(tmp_path,monkeypatch);(source/manifest["files"][-1]["path"]).write_bytes(b"bad")
    monkeypatch.setattr(m,"copy_stream",lambda *a,**k:pytest.fail("copy before auth"))
    with pytest.raises(m.Refusal):m.stage(tmp_path/"out",tmp_path/"work",path,source)
    assert json.loads((tmp_path/"work/result.json").read_bytes())["status"]=="failed"


@pytest.mark.parametrize("change",["extra","missing","directory","symlink","digest"])
def test_closed_source_inventory(tmp_path,monkeypatch,change):
    source,path,manifest,_,_=bundle(tmp_path,monkeypatch);write(source/"source_manifest.json",path.read_bytes());p=source/manifest["files"][0]["path"]
    if change=="extra":write(source/"extra",b"x")
    elif change=="directory":(source/"extra").mkdir()
    elif change=="missing":p.unlink()
    elif change=="symlink":p.unlink();p.symlink_to(path)
    else:p.write_bytes(b"wrong")
    with pytest.raises(m.Refusal):m.verify_staged(source)


@pytest.mark.parametrize("which",["source","manifest","dest_in_work","work_in_dest"])
def test_overlap_before_mutation(tmp_path,monkeypatch,which):
    source,path,_,_,_=bundle(tmp_path,monkeypatch);dest,work=tmp_path/"out",tmp_path/"work"
    if which=="source":dest=source/"new/child"
    elif which=="manifest":work=path.parent/"work"
    elif which=="dest_in_work":dest=work/"out"
    else:work=dest/"work"
    with pytest.raises(m.Refusal,match="overlapping"):m.stage(dest,work,path,source)
    assert not dest.exists() and not work.exists()


@pytest.mark.parametrize("which",["out","work"])
def test_existing_preserved(tmp_path,monkeypatch,which):
    source,path,_,_,_=bundle(tmp_path,monkeypatch);write(tmp_path/which/"keep",b"prior")
    with pytest.raises(m.Refusal,match="fresh"):m.stage(tmp_path/"out",tmp_path/"work",path,source)
    assert (tmp_path/which/"keep").read_bytes()==b"prior"


@pytest.mark.parametrize("value",["../x","x//y","x/./y","x/../y","/abs","C:/path","x\\y","x\0y"])
def test_relative_paths(value):
    with pytest.raises(m.Refusal):m.relative(value)


def test_symlink_before_lexical_dot(tmp_path):
    (tmp_path/"link").symlink_to(tmp_path/"missing",target_is_directory=True)
    for s in (str(tmp_path)+"/link/../out",str(tmp_path)+"/link/out"):
        with pytest.raises(m.Refusal):m.safe_path(s)


@pytest.mark.parametrize("raw",[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'])
def test_strict_json(raw):
    with pytest.raises(m.Refusal):m.strict_json(raw)


@pytest.mark.parametrize("change",["version","conflicting","object","host","bucket","digest"])
def test_closed_archive_endpoints(tmp_path,monkeypatch,change):
    _,_,manifest,_,_=bundle(tmp_path,monkeypatch);r=manifest["archives"][0]
    url=r["source_url"]
    if change=="version":url=url.replace("revision=1","revision=2")
    elif change=="conflicting":url+="&version=2"
    elif change=="object":url=url.replace("3dj2a","wrong")
    elif change=="host":url=url.replace("osf.io","evil.example")
    elif change=="bucket":url="https://storage.googleapis.com/other/"+r["sha256"]
    else:url="https://storage.googleapis.com/cos-osf-prod-files-ca-1/"+"0"*64
    with pytest.raises(m.Refusal):m.endpoint(url,r)


def test_version_spelling_and_canonical_start(tmp_path,monkeypatch):
    _,_,manifest,_,_=bundle(tmp_path,monkeypatch);r=manifest["archives"][0];before=dict(r)
    assert m.transport_start(r)==r["source_url"] and r==before
    assert m.endpoint(r["source_url"].replace("revision=1","version=1"),r)["host"]=="osf.io"


@pytest.mark.parametrize("case",["length","missing_length","duplicate","encoding","html","truncated","oversized","digest","status","wrong_url"])
def test_network_failures(tmp_path,case):
    r=github();body=b"notice";headers=[("Content-Type","application/octet-stream"),("Content-Length","6")];code=200;url=r["source_url"]
    if case=="length":headers[-1]=("Content-Length","7")
    elif case=="missing_length":headers.pop()
    elif case=="duplicate":headers.append(("Content-Length","6"))
    elif case=="encoding":headers.append(("Content-Encoding","gzip"))
    elif case=="html":headers[0]=("Content-Type","text/html")
    elif case=="truncated":body=b"short"
    elif case=="oversized":body=b"noticeX"
    elif case=="digest":body=b"NOTICE"
    elif case=="status":code=500
    else:url="https://other.invalid/"
    response=Response(url,body,code,headers);state=m.State()
    with pytest.raises(m.Refusal):m.download(r,tmp_path/"target",state,lambda *a:response)
    assert response.closed and state.cancelled.is_set() and not (tmp_path/"target").exists()


def test_no_new_scheduling_after_failure(tmp_path,monkeypatch):
    state=m.State();jobs=[(dict(github(),path=f"row{i}"),tmp_path/f"row{i}") for i in range(2)]
    with pytest.raises(m.Refusal):m.parallel_download(jobs,state,lambda url,*a:Response(url,code=500))
    assert state.starts=={"row0"}


def test_aggregate_and_deadline(tmp_path,monkeypatch):
    monkeypatch.setattr(m,"MAX_BYTES",3);state=m.State();r=github()
    with pytest.raises(m.Refusal,match="aggregate"):m.download(r,tmp_path/"out",state,lambda url,*a:Response(url,b"notice"))
    state=m.State();state.deadline=time.monotonic()-1
    with pytest.raises(m.Refusal,match="deadline"):state.start("first")


def test_two_start_limit_duplicate_cancel():
    state=m.State();state.start("a")
    with pytest.raises(m.Refusal,match="duplicate"):state.start("a")
    state.start("b")
    with pytest.raises(m.Refusal,match="excess"):state.start("c")
    state.cancelled.set()
    with pytest.raises(m.Refusal,match="cancelled"):state.check()


@pytest.mark.parametrize("name",["../escape","/absolute","a/../x","a\\b","C:/a"])
def test_unsafe_zip(tmp_path,name):
    p=tmp_path/"bad.zip"
    with zipfile.ZipFile(p,"w") as z:z.writestr(name,b"x")
    with pytest.raises(m.Refusal):m.zip_inventory(p)


def test_zip_link_and_trailing(tmp_path):
    p=tmp_path/"bad.zip";info=zipfile.ZipInfo("link");info.external_attr=(stat.S_IFLNK|0o777)<<16
    with zipfile.ZipFile(p,"w") as z:z.writestr(info,b"target")
    with pytest.raises(m.Refusal,match="nonregular"):m.zip_inventory(p)
    with zipfile.ZipFile(p,"w") as z:z.writestr("x",b"x")
    p.write_bytes(p.read_bytes()+b"trailing")
    with pytest.raises(m.Refusal,match="end_record"):m.zip_inventory(p)


def test_fresh_request_headers(monkeypatch):
    class Opener:
        def open(self,request,timeout):
            assert {k.lower() for k,v in request.header_items()}=={"accept-encoding","user-agent"}
            return Response(request.full_url)
    monkeypatch.setattr(m,"build_opener",lambda *a:Opener())
    m.open_once(github()["source_url"],1).close()


def test_default_redirect_error_no_body():
    r=Response("https://osf.io/download/3dj2a/?revision=1",b"unread",302);req=Request(r.url)
    assert m.NoRedirect().http_error_302(req,r,302,"redirect",{}) is None
    with pytest.raises(HTTPError) as e:HTTPDefaultErrorHandler().http_error_default(req,r,302,"redirect",{})
    assert r.tell()==0;e.value.close();assert r.closed


def test_publish_noreplace(tmp_path):
    pending,dest=tmp_path/"pending",tmp_path/"dest";pending.mkdir();write(dest/"keep",b"prior")
    with pytest.raises(OSError):m.publish(pending,dest)
    assert (dest/"keep").read_bytes()==b"prior" and pending.is_dir()


def test_verify_cli_offline(tmp_path,monkeypatch,capsys):
    source,path,_,_,_=bundle(tmp_path,monkeypatch);write(source/"source_manifest.json",path.read_bytes())
    monkeypatch.setattr(m,"stage",lambda *a:pytest.fail("stage called"))
    assert m.main(["--verify-existing","--destination",str(source)])==0
    assert json.loads(capsys.readouterr().out)["source_file_count"]==4
