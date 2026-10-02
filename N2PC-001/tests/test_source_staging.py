"""Portable-stager manufactured sources/transport only, never original EEG."""
from email.message import Message
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import threading
from dataclasses import replace
from urllib.error import HTTPError
from urllib.request import Request

import pytest

HERE=Path(__file__).resolve().parents[1]/"environment"
spec=importlib.util.spec_from_file_location("portable_n2pc_stage",HERE/"stage_data.py")
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)


@pytest.fixture
def manufactured(tmp_path,monkeypatch):
    inputs=tmp_path/"inputs";inputs.mkdir();originals=tmp_path/"originals";originals.mkdir()
    doc=json.loads((HERE/"source_manifest.json").read_text());bodies={}
    for row in doc["files"]:
        raw=("manufactured-"+row["path"]).encode();bodies[row["download_url"]]=raw
        (originals/row["path"]).write_bytes(raw)
        row.update(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),md5=hashlib.md5(raw).hexdigest())
    doc["total_original_bytes"]=sum(r["size_bytes"] for r in doc["files"])
    raw=json.dumps(doc).encode();manifest=inputs/"source_manifest.json";manifest.write_bytes(raw)
    notice=inputs/"SOURCE_NOTICE.md";notice.write_bytes((HERE/"SOURCE_NOTICE.md").read_bytes())
    monkeypatch.setattr(m,"MANIFEST_SHA256",hashlib.sha256(raw).hexdigest());monkeypatch.setattr(m,"TOTAL_BYTES",doc["total_original_bytes"])
    return dict(doc=doc,manifest=manifest,notice=notice,originals=originals,bodies=bodies)


def stage_local(tmp_path,f,**kwargs):
    return m.stage(tmp_path/"staged",manifest_path=f["manifest"],notice_path=f["notice"],
                   source_dir=f["originals"],disk_free=lambda p:10**12,**kwargs)


class Response:
    def __init__(self,url,raw,headers=None,status=200):
        self.url,self.raw,self.status=url,io.BytesIO(raw),status;self.closed=False;self.reads=0
        self.headers=Message()
        for k,v in headers or [("Content-Length",str(len(raw))),("Content-Type","application/octet-stream")]:self.headers[k]=v
    def geturl(self):return self.url
    def read(self,n):raise AssertionError("read1 only / error bodies unread")
    def read1(self,n):self.reads+=1;return self.raw.read(n)
    def close(self):self.closed=True;self.raw.close()
    def __enter__(self):return self
    def __exit__(self,*a):self.close()


class Factory:
    def __init__(self,bodies):self.bodies=bodies;self.calls=[];self.responses=[]
    def __call__(self,handler):
        outer=self
        class Opener:
            def open(self,request,timeout):
                outer.calls.append(request.full_url);assert timeout==30
                value=outer.bodies[request.full_url]
                if isinstance(value,BaseException):raise value
                response=value if isinstance(value,Response) else Response(request.full_url,value)
                outer.responses.append(response);return response
        return Opener()


def test_frozen_public_documents_are_exact():
    doc,raw=m.load_manifest(HERE/"source_manifest.json")
    assert len(doc["files"])==24 and doc["total_original_bytes"]==1051981416
    assert hashlib.sha256(raw).hexdigest()=="ada7a37ede5c498063d324bc9d5c254b457c5aecab9d41c622c66c38a8e21541"
    assert hashlib.sha256(m.read_notice(HERE/"SOURCE_NOTICE.md")).hexdigest()=="6cc59f632b1fd5868fd3abc99ef2bb28f32b92c861198759a56577550305628e"


def test_local_copy_exact26_readable_separate_inodes(tmp_path,manufactured):
    f=manufactured;before={p.name:(p.stat().st_ino,p.stat().st_mode,p.stat().st_ctime_ns,p.read_bytes()) for p in f["originals"].iterdir()}
    result=stage_local(tmp_path,f)
    assert result["status"]=="verified" and result["source_file_count"]==24 and result["bundle_file_count"]==26
    assert result["network_body_bytes"]==result["objects_started"]==0
    assert len(list((tmp_path/"staged").iterdir()))==26 and (tmp_path/"staged").stat().st_mode&0o777==0o755
    assert m.verify_staged(tmp_path/"staged")==f["doc"]
    for row in f["doc"]["files"]:
        source=f["originals"]/row["path"];copy=tmp_path/"staged"/row["path"]
        assert (source.stat().st_ino,source.stat().st_mode,source.stat().st_ctime_ns,source.read_bytes())==before[source.name]
        assert copy.read_bytes()==source.read_bytes() and copy.stat().st_ino!=source.stat().st_ino
    assert all(p.stat().st_mode&0o777==0o444 for p in (tmp_path/"staged").iterdir())


def test_verify_existing_never_stages_writes_or_fetches(tmp_path,manufactured,monkeypatch,capsys):
    stage_local(tmp_path,manufactured)
    def deny(*a,**k):pytest.fail("offline verification mutation/network")
    monkeypatch.setattr(m,"stage",deny);monkeypatch.setattr(m,"download_one",deny);monkeypatch.setattr(m,"write_bytes",deny)
    monkeypatch.setattr(m,"build_opener",deny);monkeypatch.setattr(Path,"mkdir",deny)
    assert m.main(["--verify-existing","--destination",str(tmp_path/"staged")])==0
    assert json.loads(capsys.readouterr().out)["network_body_bytes"]==0


@pytest.mark.parametrize("mode",["missing","extra","symlink","fifo","directory","size","hash","manifest","notice"])
def test_verify_existing_closed_inventory_and_digests(tmp_path,manufactured,mode):
    stage_local(tmp_path,manufactured);root=tmp_path/"staged";target=root/manufactured["doc"]["files"][0]["path"]
    if mode=="missing":target.unlink()
    elif mode=="extra":(root/"extra").write_bytes(b"x")
    elif mode=="symlink":target.unlink();target.symlink_to(manufactured["originals"]/target.name)
    elif mode=="fifo":target.unlink();os.mkfifo(target)
    elif mode=="directory":target.unlink();target.mkdir()
    else:
        if mode=="manifest":target=root/"source_manifest.json"
        if mode=="notice":target=root/"SOURCE_NOTICE.md"
        raw=target.read_bytes();target.chmod(0o600);target.write_bytes(raw+b"X" if mode=="size" else b"X"+raw[1:])
    with pytest.raises((m.CaptureError,OSError)):m.verify_staged(root)


@pytest.mark.parametrize("mode",["last_hash","missing","extra","symlink","fifo","notice","manifest","low_disk"])
def test_local_authentication_precedes_all_destination_parent_writes(tmp_path,manufactured,mode):
    f=manufactured;target=f["originals"]/f["doc"]["files"][-1]["path"]
    if mode=="last_hash":target.write_bytes(b"X"+target.read_bytes()[1:])
    elif mode=="missing":target.unlink()
    elif mode=="extra":(f["originals"]/"extra").write_bytes(b"X")
    elif mode=="symlink":target.unlink();target.symlink_to(tmp_path/"missing")
    elif mode=="fifo":target.unlink();os.mkfifo(target)
    elif mode=="notice":f["notice"].write_bytes(b"wrong")
    elif mode=="manifest":f["manifest"].write_bytes(b"{}")
    with pytest.raises((m.CaptureError,OSError)):
        m.stage(tmp_path/"new-parent/staged",manifest_path=f["manifest"],notice_path=f["notice"],source_dir=f["originals"],disk_free=lambda p:0 if mode=="low_disk" else 10**12)
    assert not (tmp_path/"new-parent").exists()


@pytest.mark.parametrize("mode",["existing","nested_source","parent_source","receipt_in_source","overlap_receipt","symlink_parent","symlink_dotdot"])
def test_destination_no_overwrite_overlap_or_link(tmp_path,manufactured,mode):
    f=manufactured;dest=tmp_path/"staged";receipt=tmp_path/"receipt"
    if mode=="existing":dest.mkdir()
    elif mode=="nested_source":dest=f["originals"]/"nested/out"
    elif mode=="parent_source":dest=tmp_path
    elif mode=="receipt_in_source":receipt=f["originals"]/"receipt"
    elif mode=="overlap_receipt":receipt=dest/"receipt"
    elif mode=="symlink_parent":(tmp_path/"link").symlink_to(f["originals"]);dest=tmp_path/"link/out"
    elif mode=="symlink_dotdot":(tmp_path/"link").symlink_to(f["originals"]);dest=str(tmp_path)+"/link/../out"
    before=sorted(str(p) for p in tmp_path.rglob("*"))
    with pytest.raises(m.CaptureError):m.stage(dest,manifest_path=f["manifest"],notice_path=f["notice"],receipt_dir=receipt,source_dir=f["originals"],disk_free=lambda p:10**12)
    assert before==sorted(str(p) for p in tmp_path.rglob("*"))


def test_public_fetch_manufactured24_and_closed_staged26(tmp_path,manufactured):
    f=manufactured;factory=Factory(f["bodies"])
    result=m.stage(tmp_path/"staged",manifest_path=f["manifest"],notice_path=f["notice"],opener_factory=factory,disk_free=lambda p:10**12)
    assert result["status"]=="verified" and result["objects_started"]==24 and len(factory.calls)==24
    assert result["network_body_bytes"]==f["doc"]["total_original_bytes"] and all(r.closed for r in factory.responses)
    assert m.verify_staged(tmp_path/"staged")==f["doc"]


def test_http500_preserved_no_secret_or_error_body(tmp_path,manufactured):
    f=manufactured;row=f["doc"]["files"][0];body=Response(row["download_url"],b"SECRET")
    f["bodies"][row["download_url"]]=HTTPError(row["download_url"]+"&token=SECRET",500,"SECRET",Message(),body)
    factory=Factory(f["bodies"])
    with pytest.raises((HTTPError,m.CaptureError)):m.stage(tmp_path/"staged",manifest_path=f["manifest"],notice_path=f["notice"],opener_factory=factory,disk_free=lambda p:10**12)
    receipts=tmp_path/"staged_staging_receipt";record=json.loads((receipts/"object_receipts"/(row["path"]+".json")).read_text())
    assert record["http_status"]==500 and body.closed and body.reads==0 and len(factory.calls)<=2
    assert not (tmp_path/"staged").exists() and (receipts/"originals"/(row["path"]+".partial")).exists()
    assert all("SECRET" not in p.read_text() for p in receipts.rglob("*.json"))


@pytest.mark.parametrize("code",[301,302,303,307,308])
def test_portable_redirect_never_forwards_injected_host_or_auth(tmp_path,manufactured,code):
    row=manufactured["doc"]["files"][0];state=m.State(tmp_path,m.Limits());ledger=[]
    handler=m.Redirects(row,state,ledger);headers=Message();destination="https://storage.googleapis.com/cos-osf-prod-files-us-east1/"+row["sha256"]+"?signature=SECRET"
    headers["Location"]=destination;body=Response(row["download_url"],b"SECRET")
    request=Request(row["download_url"],headers={"Cookie":"SECRET","Authorization":"SECRET","Content-Length":"9"});request.add_unredirected_header("Host","osf.io")
    class Parent:
        def open(self,request,timeout):
            assert request.full_url==destination and timeout==30
            assert {k.lower():v for k,v in request.header_items()}=={k.lower():v for k,v in m.REQUEST_HEADERS.items()}
            assert request.unredirected_hdrs=={};return 1
    handler.parent=Parent()
    assert getattr(handler,f"http_error_{code}")(request,body,code,"",headers)==1
    assert body.closed and body.reads==0 and "SECRET" not in json.dumps(ledger)


def test_copy_race_keeps_failed_receipt_and_never_complete_marker(tmp_path,manufactured,monkeypatch):
    original=m.hash_original;changed=False
    def raced(path,entry,**kwargs):
        nonlocal changed
        if kwargs.get("copy_to") is not None and not changed:
            path.write_bytes(b"X"+path.read_bytes()[1:]);changed=True
        return original(path,entry,**kwargs)
    monkeypatch.setattr(m,"hash_original",raced)
    with pytest.raises(m.CaptureError):stage_local(tmp_path,manufactured)
    report=json.loads((tmp_path/"staged_staging_receipt/result.json").read_text())
    assert report["status"]=="failed_preserved" and not (tmp_path/"staged/source_manifest.json").exists()


def test_late_verification_failure_preserved(tmp_path,manufactured,monkeypatch):
    def deny(*args):raise m.CaptureError("manufactured_late")
    monkeypatch.setattr(m,"verify_staged",deny)
    with pytest.raises(m.CaptureError):stage_local(tmp_path,manufactured)
    report=json.loads((tmp_path/"staged_staging_receipt/result.json").read_text())
    assert report["status"]=="failed_preserved" and report["error_code"]=="manufactured_late"


@pytest.mark.parametrize("option",["--source-dir","--receipt-dir"])
def test_verify_cli_cannot_write_or_stage(option):
    with pytest.raises(SystemExit) as error:m.main(["--verify-existing",option,"/unused"])
    assert error.value.code==2


def test_docker_source_runtime_and_no_reference_exposure():
    text=(HERE/"Dockerfile").read_text()
    assert "ubuntu:24.04@sha256:008173" in text
    assert "COPY --from=source /app/data/n2pc /app/data/n2pc" in text
    assert "COPY SOURCE_NOTICE.md /opt/source/SOURCE_NOTICE.md" in text
    assert "COPY method_contract.json /app/method_contract.json" in text
    assert "--receipt-dir /source_capture" in text and "pytest==8.4.1 pytest-json-ctrf==0.3.5" in text
    for bad in ("COPY solution","COPY tests","reference.npz","/home/", "brbench-"):assert bad not in text
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):assert name+"=1" in text


@pytest.mark.parametrize("mode",["http","userinfo","port","host","osf_path","revision_two","revision_duplicate","revision_missing","fragment","files_node","files_object","files_version","gcs_bucket","gcs_digest"])
def test_production_redirect_identity_escapes_are_refused_and_closed(tmp_path,manufactured,mode):
    row=manufactured["doc"]["files"][0];state=m.State(tmp_path,m.Limits());ledger=[]
    url=row["download_url"]
    if mode=="http":url=url.replace("https:","http:")
    elif mode=="userinfo":url=url.replace("https://","https://user:SECRET@")
    elif mode=="port":url=url.replace("osf.io/","osf.io:444/")
    elif mode=="host":url=url.replace("osf.io/","osf.io.evil/")
    elif mode=="osf_path":url="https://osf.io/download/wrong/?revision=1"
    elif mode=="revision_two":url=url.replace("revision=1","revision=2")
    elif mode=="revision_duplicate":url+="&revision=2"
    elif mode=="revision_missing":url=url.split("?")[0]
    elif mode=="fragment":url+="#SECRET"
    elif mode=="files_node":url=f"https://files.osf.io/v1/resources/wrong/providers/osfstorage/{row['object_id']}?version=1"
    elif mode=="files_object":url="https://files.osf.io/v1/resources/yefrq/providers/osfstorage/incorrect?version=1"
    elif mode=="files_version":url=f"https://files.osf.io/v1/resources/yefrq/providers/osfstorage/{row['object_id']}?version=2"
    elif mode=="gcs_bucket":url="https://storage.googleapis.com/incorrect/"+row["sha256"]
    elif mode=="gcs_digest":url="https://storage.googleapis.com/cos-osf-prod-files-us-east1/incorrect"
    handler=m.Redirects(row,state,ledger);headers=Message();headers["Location"]=url
    body=Response(row["download_url"],b"SECRET")
    class Parent:
        def open(self,*args,**kwargs):pytest.fail("Escaped redirect followed")
    handler.parent=Parent()
    with pytest.raises((m.CaptureError,ValueError)):handler.http_error_302(Request(row["download_url"]),body,302,"",headers)
    assert body.closed and body.reads==0 and ledger[-1]["allowed"] is False
    assert "SECRET" not in json.dumps(ledger)


@pytest.mark.parametrize("mode",["status","length_missing","length_duplicate","length_nondigit","length_wrong","truncated","oversized","sha","md5","encoding","content_type"])
def test_production_download_failures_keep_partial_and_hash_receipt(tmp_path,manufactured,mode):
    row=manufactured["doc"]["files"][0].copy();raw=manufactured["bodies"][row["download_url"]]
    headers=[("Content-Length",str(len(raw))),("Content-Type","application/octet-stream")];status=200
    if mode=="status":status=206
    elif mode=="length_missing":headers=headers[1:]
    elif mode=="length_duplicate":headers.append(("Content-Length",str(len(raw))))
    elif mode=="length_nondigit":headers[0]=("Content-Length","+4")
    elif mode=="length_wrong":headers[0]=("Content-Length",str(len(raw)+1))
    elif mode=="truncated":raw=raw[:-1]
    elif mode=="oversized":raw+=b"X"
    elif mode=="sha":row["sha256"]="a"*64
    elif mode=="md5":row["md5"]="b"*32
    elif mode=="encoding":headers.append(("Content-Encoding","gzip"))
    elif mode=="content_type":headers[1]=("Content-Type","text/html")
    response=Response(row["download_url"],raw,headers=headers,status=status);factory=Factory({row["download_url"]:response})
    capture=tmp_path/"capture";capture.mkdir()
    (capture/"originals").mkdir();(capture/"object_receipts").mkdir();state=m.State(capture,m.Limits())
    with pytest.raises(m.CaptureError):m.download_one(row,state,factory)
    assert response.closed and state.stop.is_set() and len(factory.calls)==1 and state.starts=={row["object_id"]}
    assert (capture/"originals"/(row["path"]+".partial")).exists()
    assert not (capture/"originals"/row["path"]).exists()
    record=json.loads((capture/"object_receipts"/(row["path"]+".json")).read_text())
    assert record["status"]=="failed_preserved" and record["attempts"]==1
    assert record["received_bytes"]<=row["size_bytes"]+1
    if mode in ("status","length_missing","length_duplicate","length_nondigit","length_wrong","encoding","content_type"):
        assert response.reads==0 and record["received_bytes"]==0


def test_production_global_payload_reservation_shared_between_reads(tmp_path):
    state=m.State(tmp_path,replace(m.Limits(),payload_cap=5));entered=threading.Event();release=threading.Event();result=[]
    class Slow:
        def read(self,n):pytest.fail("read1 required")
        def read1(self,n):
            assert n==5;entered.set();assert release.wait(2);return b"12345"
    worker=threading.Thread(target=lambda:result.append(state.read(Slow(),8)));worker.start()
    assert entered.wait(2)
    with pytest.raises(m.CaptureError,match="aggregate_payload_cap"):state.read(Response("unused",b"x"),1)
    release.set();worker.join(2)
    assert not worker.is_alive() and result==[b"12345"] and state.received==5 and state.reserved==0


def test_production_read_exception_releases_reservation(tmp_path):
    state=m.State(tmp_path,m.Limits())
    class Broken:
        def read(self,n):raise OSError("manufactured read failure")
    with pytest.raises(OSError):state.read(Broken(),7)
    assert state.received==state.reserved==0


@pytest.mark.parametrize("mode",["read","start","redirect"])
def test_production_deadline_stops_before_socket_activity(tmp_path,manufactured,mode):
    now=[0.];state=m.State(tmp_path,m.Limits(),clock=lambda:now[0]);now[0]=869.
    row=manufactured["doc"]["files"][0];body=Response(row["download_url"],b"SECRET")
    with pytest.raises(m.CaptureError,match="wall_deadline"):
        if mode=="read":state.read(body,3)
        elif mode=="start":state.start(row["object_id"])
        else:
            handler=m.Redirects(row,state,[]);headers=Message();headers["Location"]=row["download_url"]
            handler.http_error_302(Request(row["download_url"]),body,302,"",headers)
    assert body.reads==0 and state.received==0 and not state.starts
    if mode=="redirect":assert body.closed


@pytest.mark.parametrize("mode",["read","start","redirect"])
def test_production_cancellation_stops_before_socket_activity(tmp_path,manufactured,mode):
    state=m.State(tmp_path,m.Limits());state.stop.set();row=manufactured["doc"]["files"][0]
    body=Response(row["download_url"],b"SECRET")
    with pytest.raises(m.CaptureError,match="capture_cancelled"):
        if mode=="read":state.read(body,3)
        elif mode=="start":state.start(row["object_id"])
        else:
            handler=m.Redirects(row,state,[]);headers=Message();headers["Location"]=row["download_url"]
            handler.http_error_302(Request(row["download_url"]),body,302,"",headers)
    assert body.reads==0 and not state.starts
    if mode=="redirect":assert body.closed


def test_production_parallel_failure_never_schedules_third_member(tmp_path):
    state=m.State(tmp_path,m.Limits());barrier=threading.Barrier(2);calls=[];lock=threading.Lock()
    def operation(i):
        state.start(str(i))
        with lock:calls.append(i)
        barrier.wait(timeout=2)
        if i==0:state.stop.set();raise m.CaptureError("manufactured first failure")
        state.stop.wait(2);state.check()
    with pytest.raises(m.CaptureError):m.parallel(list(range(24)),operation,state)
    assert sorted(calls)==[0,1] and len(state.starts)==2


def test_production_duplicate_and_excess_object_starts_rejected(tmp_path):
    state=m.State(tmp_path,m.Limits())
    state.start("first")
    with pytest.raises(m.CaptureError,match="duplicate_or_excess_start"):state.start("first")
    for i in range(23):state.start(str(i))
    with pytest.raises(m.CaptureError,match="duplicate_or_excess_start"):state.start("twenty_fifth")
    assert len(state.starts)==24
