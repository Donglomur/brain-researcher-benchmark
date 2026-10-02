"""Manufactured N170 stager fixtures; no originals, metadata capture or network.

Adapted guard cases from reviewed PR190 test_stage_data.py, SHA256
e9e3ae0b088ac3121b3c7e94f87ae776cde5cb4d82d064dec888d4dc3550eba7.
"""
from email.message import Message
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import threading
import time
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import HTTPDefaultErrorHandler, Request

import pytest

SPEC = importlib.util.spec_from_file_location('n170_stager', Path(__file__).resolve().parents[1]/'environment'/'stage_data.py')
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)


def row(subject=2, role='set', body=b'payload', version=2):
    oid = f'{subject*2+(role=="fdt"):024x}'
    return dict(subject=subject,role=role,path=f'{subject}_N170_shifted_ds.{role}',size_bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),md5=hashlib.md5(body).hexdigest(),
                osf_object_id=oid,source_version=version,
                source_url=f'https://files.osf.io/v1/resources/pfde9/providers/osfstorage/{oid}?revision={version}',
                canonical_file_api_url=f'https://api.osf.io/v2/files/{oid}/',
                canonical_version_api_url=f'https://api.osf.io/v2/files/{oid}/versions/{version}/',
                file_metadata_sha256='a'*64,version_metadata_sha256='b'*64,
                digest_authority='file_metadata/current_version_matched')


def signed(r, query='GoogleAccessId=PRIVATE&Expires=123&Signature=PRIVATE'):
    return 'https://storage.googleapis.com/cos-osf-prod-files-us-east1/'+r['sha256']+'?'+query


class Response(io.BytesIO):
    def __init__(self,url,body=b'payload',code=200,headers=None):
        super().__init__(body);self.url=url;self.code=code;self.headers=Message();self.read_calls=0
        for key,value in (headers if headers is not None else
                          [('Content-Type','application/octet-stream'),('Content-Length',str(len(body)))]):
            self.headers[key]=value
    def geturl(self):return self.url
    def read1(self,n):self.read_calls+=1;return super().read(n)


def write(path,raw):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)


def repin(path,doc,monkeypatch):
    raw=(json.dumps(doc,sort_keys=True)+'\n').encode();write(path,raw)
    monkeypatch.setattr(m,'MANIFEST_SHA256',hashlib.sha256(raw).hexdigest())


@pytest.fixture(autouse=True)
def manufactured_disk(monkeypatch):
    monkeypatch.setattr(m.shutil,'disk_usage',lambda _:SimpleNamespace(free=20*1024**3))


def bundle(tmp_path,monkeypatch):
    source,manifest=tmp_path/'input',tmp_path/'metadata/source_manifest.json'
    rows=[row(s,role,version=2 if s==2 else 7) for s in (2,3) for role in ('set','fdt')]
    doc=dict(task_id='N170PROFILE-001',schema_version='n170-source-v1',subjects=[2,3],
             source_file_count=4,source_bytes=sum(r['size_bytes'] for r in rows),files=rows)
    for r in rows:write(source/r['path'],b'payload')
    monkeypatch.setattr(m,'SUBJECTS',(2,3));monkeypatch.setattr(m,'EXPECTED_COUNT',4)
    monkeypatch.setattr(m,'EXPECTED_BYTES',doc['source_bytes']);monkeypatch.setattr(m,'MAX_BYTES',doc['source_bytes']+4)
    monkeypatch.setattr(m,'MAX_REQUESTS',24);repin(manifest,doc,monkeypatch)
    lookup={r['source_url']:r for r in rows}
    def transport(url,timeout):
        assert 0<timeout<=30
        if url in lookup:return Response(url,b'UNREAD',302,[('Location',signed(lookup[url]))])
        assert url in {signed(r) for r in rows}
        return Response(url)
    return source,manifest,doc,transport


def test_production_bounds_and_reviewed_manifest_pin():
    assert m.MANIFEST_SHA256=='3970137c64990f680468baf1d51b89a73a61a748639795541e2c2734777b54cd'
    assert m.SUBJECTS==tuple(s for s in range(1,41) if s not in (1,5,16))
    assert (m.EXPECTED_COUNT,m.EXPECTED_BYTES,m.MAX_BYTES)==(74,788438272,788438346)
    assert (m.WORKERS,m.MAX_SECONDS,m.SOCKET_SECONDS,m.MAX_REDIRECTS,m.MAX_REQUESTS)==(2,900,30,5,444)
    assert m.MIN_FREE_BYTES==5*1024**3


def test_unfrozen_pin_refuses_before_manifest_read(monkeypatch):
    monkeypatch.setattr(m,'MANIFEST_SHA256',None)
    monkeypatch.setattr(m,'reader',lambda *_:pytest.fail('unfrozen input read'))
    with pytest.raises(m.Refusal,match='unfrozen'):m.load_manifest('/not-read/source_manifest.json')


def test_network_stage_offline_verification_and_query_redaction(tmp_path,monkeypatch,capsys):
    source,manifest,doc,transport=bundle(tmp_path,monkeypatch)
    result=m.stage(tmp_path/'new-parent/data',tmp_path/'work',manifest,transport=transport)
    assert result['status']=='ok' and result['source_file_count']==4 and result['source_bytes']==28
    assert (result['transfer_starts'],result['network_requests'],result['network_body_bytes'])==(4,8,28)
    assert result['automatic_retries']==0 and not result['source_payload_parsed']
    assert m.verify_staged(tmp_path/'new-parent/data')==doc
    assert 'PRIVATE' not in (tmp_path/'work/result.json').read_text()+capsys.readouterr().out
    assert {p.name for p in (tmp_path/'new-parent/data').iterdir()}=={r['path'] for r in doc['files']}|{m.MANIFEST_NAME}
    assert all(stat.S_IMODE((tmp_path/'new-parent/data'/r['path']).stat().st_mode)==0o444 for r in doc['files'])
    assert all((source/r['path']).read_bytes()==(tmp_path/'new-parent/data'/r['path']).read_bytes() for r in doc['files'])


@pytest.mark.parametrize('internal_manifest',[False,True])
def test_local_all_verified_then_copy_without_mutation_or_network(tmp_path,monkeypatch,internal_manifest):
    source,manifest,doc,_=bundle(tmp_path,monkeypatch)
    if internal_manifest:write(source/m.MANIFEST_NAME,manifest.read_bytes())
    before={p:(p.read_bytes(),m.signature(p.stat())) for p in source.iterdir()}
    result=m.stage(tmp_path/'out',tmp_path/'work',manifest,source,lambda *_:pytest.fail('local network'))
    assert result['network_requests']==0 and result['transfer_starts']==0
    assert m.verify_staged(tmp_path/'out')==doc
    assert all((p.read_bytes(),m.signature(p.stat()))==saved for p,saved in before.items())


def test_local_bad_last_member_prevents_first_copy(tmp_path,monkeypatch):
    source,manifest,doc,_=bundle(tmp_path,monkeypatch);write(source/doc['files'][-1]['path'],b'PAYLOAD')
    monkeypatch.setattr(m,'copy_stream',lambda *_:pytest.fail('copy before complete authentication'))
    with pytest.raises(m.Refusal,match='sha256'):m.stage(tmp_path/'out',tmp_path/'work',manifest,source)
    assert not (tmp_path/'out').exists() and json.loads((tmp_path/'work/result.json').read_bytes())['status']=='failed'


@pytest.mark.parametrize('kind',['extra','empty_directory','symlink','missing','hash','notice'])
def test_closed_inventory(tmp_path,monkeypatch,kind):
    source,path,doc,_=bundle(tmp_path,monkeypatch);write(source/m.MANIFEST_NAME,path.read_bytes())
    target=source/doc['files'][0]['path']
    if kind in ('extra','notice'):write(source/('extra' if kind=='extra' else 'SOURCE_NOTICE.md'),b'x')
    elif kind=='empty_directory':(source/'empty').mkdir()
    elif kind=='symlink':target.unlink();target.symlink_to(path)
    elif kind=='missing':target.unlink()
    else:write(target,b'PAYLOAD')
    with pytest.raises(m.Refusal):m.verify_staged(source)


@pytest.mark.parametrize('kind',['subject','role','duplicate_pair','path','object','version','version_bool','md5',
    'file_pin','version_pin','api_version','authority','version_hash','count','total','schema','subjects','archives'])
def test_manifest_shape_and_provider_pins(tmp_path,monkeypatch,kind):
    _,path,doc,_=bundle(tmp_path,monkeypatch);r=doc['files'][0]
    if kind=='subject':r['subject']=1
    elif kind=='role':r['role']='eeg'
    elif kind=='duplicate_pair':doc['files'][1]=dict(r)
    elif kind=='path':r['path']='subdir/'+r['path']
    elif kind=='object':r['osf_object_id']='wrong'
    elif kind=='version':r['source_version']=0
    elif kind=='version_bool':r['source_version']=True
    elif kind=='md5':r['md5']=None
    elif kind=='file_pin':r.pop('file_metadata_sha256')
    elif kind=='version_pin':r['version_metadata_sha256']='not-a-hash'
    elif kind=='api_version':r['canonical_version_api_url']=r['canonical_file_api_url']+'versions/1/'
    elif kind=='authority':r['digest_authority']='assumed_version_checksum'
    elif kind=='version_hash':r['version_sha256']='0'*64
    elif kind=='count':doc['source_file_count']=5
    elif kind=='total':doc['source_bytes']+=1
    elif kind=='schema':doc['schema_version']='wrong'
    elif kind=='subjects':doc['subjects']=[3,2]
    else:doc['archives']=[{}]
    repin(path,doc,monkeypatch)
    with pytest.raises(m.Refusal):m.load_manifest(path)


def test_absent_version_checksum_and_optional_md5_not_invented(tmp_path,monkeypatch):
    _,path,doc,_=bundle(tmp_path,monkeypatch)
    for r in doc['files']:r.pop('md5');r.pop('digest_authority')
    repin(path,doc,monkeypatch);observed,_=m.load_manifest(path)
    assert all('version_sha256' not in r and 'md5' not in r for r in observed['files'])
    assert [r['source_version'] for r in observed['files']]==[2,2,7,7]


@pytest.mark.parametrize('kind',['source','manifest','code','nested_work','nested_dest','existing_work','existing_dest','disk'])
def test_path_or_reserve_refusal_before_output_creation(tmp_path,monkeypatch,kind):
    source,path,_,_=bundle(tmp_path,monkeypatch);dest,work=tmp_path/'out',tmp_path/'work'
    if kind=='source':dest=source/'new/child'
    elif kind=='manifest':work=path.parent/'work'
    elif kind=='code':work=Path(m.__file__).parent/'work'
    elif kind=='nested_work':work=dest/'work'
    elif kind=='nested_dest':dest=work/'out'
    elif kind.startswith('existing'):
        target=work if kind=='existing_work' else dest;target.mkdir();write(target/'keep',b'prior')
    else:monkeypatch.setattr(m.shutil,'disk_usage',lambda _:SimpleNamespace(free=m.MIN_FREE_BYTES))
    with pytest.raises(m.Refusal):m.stage(dest,work,path,source)
    if kind.startswith('existing'):assert (target/'keep').read_bytes()==b'prior'
    else:assert not dest.exists() and not work.exists()


@pytest.mark.parametrize('suffix',['link/x','link/../x','../x','./x'])
def test_safe_lexical_paths(tmp_path,suffix):
    (tmp_path/'link').symlink_to(tmp_path/'missing',target_is_directory=True)
    with pytest.raises(m.Refusal):m.safe_path(str(tmp_path)+'/'+suffix)


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":[1e999]}'])
def test_strict_json(raw):
    with pytest.raises(m.Refusal):m.strict_json(raw)


@pytest.mark.parametrize('kind',['http','host','port','userinfo','node','object','revision','duplicate_revision',
    'other_query','guid','bucket','digest','unsigned','empty_signature','duplicate_signature','fragment'])
def test_closed_redirect_authority(kind):
    r=row();url=r['source_url']
    if kind=='http':url=url.replace('https:','http:')
    elif kind=='host':url=url.replace('files.osf.io','files.osf.io.evil')
    elif kind=='port':url=url.replace('files.osf.io','files.osf.io:444')
    elif kind=='userinfo':url=url.replace('files.osf.io','secret@files.osf.io')
    elif kind=='node':url=url.replace('/pfde9/','/other/')
    elif kind=='object':url=url.replace(r['osf_object_id'],'f'*24)
    elif kind=='revision':url=url.replace('revision=2','revision=1')
    elif kind=='duplicate_revision':url+='&revision=2'
    elif kind=='other_query':url+='&version=2'
    elif kind=='guid':url='https://osf.io/download/other/?revision=2'
    elif kind=='bucket':url=signed(r).replace('cos-osf-prod-files-us-east1','unrelated')
    elif kind=='digest':url=signed(r).replace(r['sha256'],'0'*64)
    elif kind=='unsigned':url=signed(r).split('?')[0]
    elif kind=='empty_signature':url=signed(r,'GoogleAccessId=x&Expires=1&Signature=')
    elif kind=='duplicate_signature':url=signed(r)+'&Signature=OTHER'
    else:url+='#fragment'
    with pytest.raises(m.Refusal):m.endpoint(url,r)


def test_known_guid_or_oid_only_and_signed_v4():
    r=row();r['source_guid']='abcde'
    for name in ('abcde',r['osf_object_id']):m.endpoint(f'https://osf.io/download/{name}/?revision=2',r)
    url=signed(r,'X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=PRIVATE&X-Goog-Date=x&X-Goog-Expires=60&X-Goog-Signature=PRIVATE')
    assert 'PRIVATE' not in json.dumps(m.endpoint(url,r))
    with pytest.raises(m.Refusal):m.endpoint(url,dict(r,source_url=url),initial=True)


def test_fresh_request_no_credential_forwarding(monkeypatch):
    class Opener:
        def open(self,request,timeout):
            assert {k.lower() for k,v in request.header_items()}=={'accept-encoding','user-agent'}
            return Response(request.full_url)
    monkeypatch.setattr(m,'build_opener',lambda *_:Opener())
    m.open_once(row()['source_url'],1).close()


def test_redirect_error_body_not_read():
    r=row();body=Response(r['source_url'],b'never read',302);request=Request(r['source_url'])
    assert m.NoRedirect().http_error_302(request,body,302,'redirect',{'Location':signed(r)}) is None
    with pytest.raises(HTTPError) as error:HTTPDefaultErrorHandler().http_error_default(request,body,302,'redirect',{})
    assert body.tell()==0;error.value.close();assert body.closed


@pytest.mark.parametrize('kind',['missing_length','duplicate_length','length','encoding','html','chunked',
    'truncated','oversized','sha','md5','status','implicit_redirect','timeout'])
def test_network_failure_preserves_partial_and_stops(tmp_path,kind,capsys):
    r=row();state=m.State();body=b'payload';code=200;headers=[('Content-Type','application/octet-stream'),('Content-Length','7')]
    if kind=='missing_length':headers.pop()
    elif kind=='duplicate_length':headers.append(('Content-Length','7'))
    elif kind=='length':headers[-1]=('Content-Length','8')
    elif kind=='encoding':headers.append(('Content-Encoding','gzip'))
    elif kind=='html':headers[0]=('Content-Type','text/html')
    elif kind=='chunked':headers.append(('Transfer-Encoding','chunked'))
    elif kind=='truncated':body=b'pay'
    elif kind=='oversized':body=b'payloadX'
    elif kind=='sha':body=b'PAYLOAD'
    elif kind=='md5':r['md5']='0'*32
    elif kind=='status':code=500
    response=Response(r['source_url'] if kind!='implicit_redirect' else 'https://evil/PRIVATE',body,code,headers)
    calls=[]
    def transport(url,timeout):
        calls.append(url)
        if kind=='timeout':raise TimeoutError('signed PRIVATE never logged')
        return response
    with pytest.raises((m.Refusal,TimeoutError)):m.download(r,tmp_path/'target',state,transport)
    assert calls==[r['source_url']] and state.cancelled.is_set() and not (tmp_path/'target').exists()
    assert state.records[0]['status']=='failed' and 'PRIVATE' not in json.dumps(state.records)+capsys.readouterr().out
    if kind!='timeout':assert response.closed
    if kind in ('truncated','oversized','sha','md5'):assert (tmp_path/'target.partial').exists()


def test_five_redirects_cap_without_reading_redirect_bodies(tmp_path):
    r=row();state=m.State();responses=[]
    def transport(url,timeout):
        next_url=signed(r,'GoogleAccessId=PRIVATE&Expires=1&Signature=PRIVATE'+str(len(responses)))
        response=Response(url,b'UNREAD',302,[('Location',next_url)]);responses.append(response);return response
    with pytest.raises(m.Refusal,match='redirect_refused'):m.download(r,tmp_path/'target',state,transport)
    assert len(responses)==6 and state.requests==6 and state.bytes==0
    assert all(response.closed and response.read_calls==0 for response in responses)


def test_aggregate_eof_cap_and_http_cap(tmp_path,monkeypatch):
    r=row();monkeypatch.setattr(m,'MAX_BYTES',7);state=m.State()
    with pytest.raises(m.Refusal,match='aggregate'):m.download(r,tmp_path/'target',state,lambda url,t:Response(url,b'payloadX',headers=[('Content-Type','application/octet-stream'),('Content-Length','7')]))
    assert state.bytes==8
    state=m.State();state.requests=m.MAX_REQUESTS
    with pytest.raises(m.Refusal,match='http_request_cap'):m.download(r,tmp_path/'other',state,lambda *_:pytest.fail('request beyond cap'))


def test_deadline_duplicate_and_cancellation(tmp_path):
    state=m.State();state.start('x')
    with pytest.raises(m.Refusal,match='duplicate'):state.start('x')
    state.deadline=time.monotonic()-1
    with pytest.raises(m.Refusal,match='deadline'):state.check()
    state=m.State();state.cancelled.set()
    with pytest.raises(m.Refusal,match='cancelled'):m.download(row(),tmp_path/'target',state,lambda *_:pytest.fail('cancelled request'))


def test_socket_bound_is_remaining_deadline(tmp_path):
    r=row();state=m.State();state.deadline=time.monotonic()+0.5
    def transport(url,timeout):assert 0<timeout<=0.5;return Response(url)
    m.download(r,tmp_path/'target',state,transport)


def test_two_worker_failure_does_not_schedule_third(tmp_path):
    state=m.State();barrier=threading.Barrier(2);calls=[]
    def transport(url,timeout):calls.append(url);barrier.wait(timeout=5);return Response(url,b'UNREAD',500)
    jobs=[(row(subject=s),tmp_path/str(s)) for s in (2,3,4,6)]
    with pytest.raises(m.Refusal):m.parallel_download(jobs,state,transport)
    assert len(calls)==2 and len(state.starts)==2 and state.bytes==0 and state.cancelled.is_set()


def test_changed_path_and_modified_copy_fail(tmp_path,monkeypatch):
    r=row();path=tmp_path/'source';write(path,b'payload')
    with pytest.raises(m.Refusal,match=r'^source_(changed_during_read|path_changed_during_read)$'):
        with m.reader(path) as (stream,before):
            assert stream.read()==b'payload';path.unlink();write(path,b'payload')
            assert path.stat().st_ino != before.st_ino
    with pytest.raises(m.Refusal,match='sha256'):
        m.copy_stream(io.BytesIO(b'PAYLOAD'),tmp_path/'target',r,m.State())


def test_atomic_publish_never_replaces(tmp_path):
    pending,dest=tmp_path/'pending',tmp_path/'out';pending.mkdir();dest.mkdir();write(dest/'keep',b'prior')
    with pytest.raises(OSError):m.publish(pending,dest)
    assert pending.exists() and (dest/'keep').read_bytes()==b'prior'


def test_verify_only_never_creates_work_or_network(tmp_path,monkeypatch,capsys):
    source,path,doc,_=bundle(tmp_path,monkeypatch);write(source/m.MANIFEST_NAME,path.read_bytes())
    monkeypatch.setattr(m,'stage',lambda *_:pytest.fail('verify attempted staging'))
    assert m.main(['--verify-existing','--destination',str(source),'--work-dir',str(tmp_path/'absent')])==0
    assert not (tmp_path/'absent').exists() and json.loads(capsys.readouterr().out)['mode']=='offline_verify_only'


def test_graceful_alarm_registration_and_external_bound_disclosure(monkeypatch,capsys):
    handlers=[];timers=[]
    monkeypatch.setattr(m.signal,'getsignal',lambda _:None)
    monkeypatch.setattr(m.signal,'getitimer',lambda _:(0.,0.))
    monkeypatch.setattr(m.signal,'signal',lambda _,handler:handlers.append(handler))
    monkeypatch.setattr(m.signal,'setitimer',lambda *args:timers.append(args))
    def stage(*args):handlers[0]()
    monkeypatch.setattr(m,'stage',stage)
    assert m.main([])==1
    assert timers==[(m.signal.ITIMER_REAL,900),(m.signal.ITIMER_REAL,0)]
    assert json.loads(capsys.readouterr().out)['reason']=='wall_deadline'
    assert 'mandatory external 900-second process-group timeout' in m.__doc__
