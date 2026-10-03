import hashlib
import importlib.util
import json
from email.message import Message
from pathlib import Path
import sys
import urllib.error
import pytest

TASK=Path(__file__).resolve().parents[2]

@pytest.fixture
def stage():
    spec=importlib.util.spec_from_file_location('manufactured_stage',TASK/'environment/stage_data.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

@pytest.fixture
def tiny(stage,tmp_path,monkeypatch):
    payload=b'manufactured opaque NWB bytes; not HDF5'
    name='tiny.nwb';sha=hashlib.sha256(payload).hexdigest()
    manifest={'task_id':'RATPLACE-001','schema_version':'ratplace-source-v2',
              'files':[{'path':name,'sha256':sha,'size_bytes':len(payload)}]}
    raw=(json.dumps(manifest)+'\n').encode();p=tmp_path/'manifest.json';p.write_bytes(raw)
    for key,value in dict(NAME=name,SIZE=len(payload),SHA256=sha,RESERVE=0,
                          MANIFEST_SHA256=hashlib.sha256(raw).hexdigest()).items():
        monkeypatch.setattr(stage,key,value)
    return p,payload

class Response:
    def __init__(self,stage,body,*,length=None,status=200,url=None,encoding=None):
        self.body=body;self.position=0;self.status=status;self.url=url or stage.URL;self.closed=False
        self.headers=Message()
        if length is not False:self.headers['Content-Length']=str(len(body) if length is None else length)
        if encoding:self.headers['Content-Encoding']=encoding
    def geturl(self):return self.url
    def read1(self,n):
        part=self.body[self.position:self.position+n];self.position+=len(part);return part
    def __enter__(self):return self
    def __exit__(self,*a):self.closed=True

class Opener:
    def __init__(self,response):self.response=response;self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout))
        if isinstance(self.response,BaseException):raise self.response
        return self.response

def test_one_exact_request(stage,tiny,tmp_path):
    _,body=tiny;response=Response(stage,body);opener=Opener(response)
    got=stage.download(tmp_path/'partial',100,opener=opener,clock=lambda:0)
    assert got==len(body) and response.closed and len(opener.calls)==1
    request,timeout=opener.calls[0]
    assert request.full_url==stage.URL and request.get_method()=='GET' and timeout==30
    assert request.get_header('Accept-encoding')=='identity'

@pytest.mark.parametrize('kind',['truncated','oversized','hash','missing_length','duplicate_length',
                                 'wrong_length','encoding','status','url','deadline'])
def test_transport_failure_preserves_partial_and_closes(stage,tiny,tmp_path,kind):
    _,body=tiny;kwargs={};payload=body
    if kind=='truncated':payload=body[:-1];kwargs['length']=len(body)
    elif kind=='oversized':payload=body+b'x';kwargs['length']=len(body)
    elif kind=='hash':payload=b'x'*len(body)
    elif kind=='missing_length':kwargs['length']=False
    elif kind=='wrong_length':kwargs['length']=len(body)+1
    elif kind=='encoding':kwargs['encoding']='gzip'
    elif kind=='status':kwargs['status']=206
    elif kind=='url':kwargs['url']='https://elsewhere.invalid/body'
    response=Response(stage,payload,**kwargs)
    if kind=='duplicate_length':response.headers['Content-Length']=str(len(body))
    clock=(lambda:101) if kind=='deadline' else (lambda:0)
    with pytest.raises(ValueError):stage.download(tmp_path/'partial',100,opener=Opener(response),clock=clock)
    if kind!='deadline':assert response.closed
    if kind in ('truncated','oversized','hash'):assert (tmp_path/'partial').exists()

def test_http_error_closed_no_body(stage,tiny,tmp_path):
    class Body:
        closed=False
        def read(self,*a):pytest.fail('error body read')
        def close(self):self.closed=True
    body=Body();error=urllib.error.HTTPError(stage.URL,503,'failure',{},body)
    with pytest.raises(ValueError,match='http_status_503'):
        stage.download(tmp_path/'partial',100,opener=Opener(error),clock=lambda:0)
    assert body.closed and not (tmp_path/'partial').exists()

def test_redirect_handler_returns_no_request(stage):
    assert stage.NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid') is None

def test_local_auth_copy_and_verify(stage,tiny,tmp_path,monkeypatch):
    manifest,raw=tiny;source=tmp_path/'original.nwb';source.write_bytes(raw)
    monkeypatch.setattr(stage,'download',lambda *a,**k:pytest.fail('network attempted'))
    out=tmp_path/'bundle';work=tmp_path/'work'
    result=stage.stage(manifest,out,work,source)
    assert result['requests']==result['received_body_bytes']==0
    assert source.read_bytes()==raw and (out/stage.NAME).read_bytes()==raw
    stage.verify(out,manifest.read_bytes())
    with pytest.raises(ValueError):stage.stage(manifest,out,tmp_path/'work2',source)
    assert not (tmp_path/'work2').exists()

@pytest.mark.parametrize('kind',['bad_payload','source_symlink','overlap','old_work','bad_manifest','extra'])
def test_staging_guard_before_mutation(stage,tiny,tmp_path,kind):
    manifest,raw=tiny;source=tmp_path/'original.nwb';source.write_bytes(raw)
    out=tmp_path/'bundle';work=tmp_path/'work'
    if kind=='bad_payload':source.write_bytes(b'x'*len(raw))
    elif kind=='source_symlink':source.unlink();source.symlink_to(manifest)
    elif kind=='overlap':out=tmp_path
    elif kind=='old_work':work.mkdir()
    elif kind=='bad_manifest':manifest.write_text('{}')
    else:
        stage.stage(manifest,out,work,source);(out/'extra').write_text('x')
        with pytest.raises(ValueError,match='closed'):stage.verify(out,manifest.read_bytes())
        return
    with pytest.raises(ValueError):stage.stage(manifest,out,work,source)
    if kind not in ('overlap','old_work'):assert not out.exists() and not work.exists()

def test_failed_download_retains_first_attempt(stage,tiny,tmp_path,monkeypatch):
    manifest,_=tiny;work=tmp_path/'work';out=tmp_path/'bundle'
    def fail(path,*a):
        path.write_bytes(b'partial');raise ValueError('manufactured_failure')
    monkeypatch.setattr(stage,'download',fail)
    with pytest.raises(ValueError):stage.stage(manifest,out,work)
    assert (work/'original.partial').read_bytes()==b'partial'
    assert json.loads((work/'result.json').read_text())['status']=='failed'
    assert not out.exists()
    with pytest.raises(ValueError,match='fresh'):stage.stage(manifest,out,work)

def test_default_import_has_no_io(stage):
    assert callable(stage.main) and stage.SIZE==61347328

