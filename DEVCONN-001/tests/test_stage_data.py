"""PR199 manufactured311-role/Power/provenance staging; no originals or network.

Adapted from qualified PR198 fixtures5df10d71; source inputs below are synthetic.
"""
import copy
from email.message import Message
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import threading
from types import SimpleNamespace

import pytest

spec=importlib.util.spec_from_file_location('devconn_stager',Path(__file__).with_name('stage_data.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BODY=b'payload'
COMMIT='a'*40


def original(sid,role):
    num=999 if sid is None else int(sid[-3:])*2+(role=='confounds')
    oid=f'{num:024x}'
    suffix='_task-pixar_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz' if role=='bold' else '_task-pixar_desc-confounds_regressors.tsv'
    name='participants.tsv' if sid is None else sid+suffix
    return dict(path=name,participant_id=sid,role=role,size_bytes=len(BODY),
        sha256=hashlib.sha256(BODY).hexdigest(),md5=hashlib.md5(BODY).hexdigest(),
        osf_object_id=oid,source_version=2,
        source_url=f'https://files.osf.io/v1/resources/5hju4/providers/osfstorage/{oid}?revision=2')


def document(role,name,repository_path=None):
    return dict(path=name,participant_id=None,role=role,size_bytes=len(BODY),
        sha256=hashlib.sha256(BODY).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob 7\0'+BODY).hexdigest(),
        source_commit=COMMIT,source_url=f'https://raw.githubusercontent.com/nilearn/nilearn/{COMMIT}/{repository_path or name}')


def signed(row):
    return 'https://storage.googleapis.com/cos-osf-prod-files-us-east1/'+row['sha256']+'?GoogleAccessId=SECRET&Expires=123&Signature=SECRET'


class Response(io.BytesIO):
    def __init__(self,url,body=BODY,code=200,headers=None):
        super().__init__(body);self.url=url;self.code=code;self.headers=Message();self.reads=0
        for k,v in headers or [('Content-Type','application/octet-stream'),('Content-Length',str(len(body)))]:self.headers[k]=v
    def geturl(self):return self.url
    def read1(self,n):self.reads+=1;return super().read(n)


def write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)


def repin(f,monkeypatch):
    raw=(json.dumps(f.doc,sort_keys=True)+'\n').encode();write(f.manifest,raw)
    monkeypatch.setattr(m,'MANIFEST_SHA256',hashlib.sha256(raw).hexdigest())


@pytest.fixture
def manufactured(tmp_path,monkeypatch):
    ids=('sub-pixar001','sub-pixar002')
    rows=[original(sid,role) for sid in ids for role in ('bold','confounds')]
    notice=original(None,'participants')
    notice.update(path=m.PROCESSING_NOTICE,role='provenance',osf_object_id='f'*24,
        source_url='https://files.osf.io/v1/resources/5hju4/providers/osfstorage/'+'f'*24+'?revision=2')
    rows += [original(None,'participants'),
        document('coordinates',m.COORDINATES_PATH,'nilearn/datasets/data/power_2011.csv'),notice,
        document('provenance','provenance/nilearn_0_12_1/nilearn/datasets/description/power_2011.rst',
                 'nilearn/datasets/description/power_2011.rst'),
        document('provenance','provenance/nilearn_0_12_1/nilearn/datasets/description/development_fmri.rst',
                 'nilearn/datasets/description/development_fmri.rst'),
        document('provenance','provenance/nilearn_0_12_1/LICENSE','LICENSE')]
    doc=dict(task_id='DEVCONN-001',schema_version='devconn-source-v2',participant_ids=list(ids),
             files=rows,n_files=len(rows),total_bytes=len(rows)*len(BODY))
    f=SimpleNamespace(doc=doc,source=tmp_path/'input',manifest=tmp_path/'metadata/source_manifest.json',calls=[],responses=[])
    for row in rows:write(f.source/row['path'],BODY)
    monkeypatch.setattr(m,'SUBJECTS',ids);monkeypatch.setattr(m,'EXPECTED_COUNT',len(rows))
    monkeypatch.setattr(m,'EXPECTED_BYTES',doc['total_bytes']);monkeypatch.setattr(m,'MAX_BYTES',1000)
    monkeypatch.setattr(m,'MAX_REQUESTS',50);monkeypatch.setattr(m.shutil,'disk_usage',lambda _:SimpleNamespace(free=20*1024**3))
    repin(f,monkeypatch)
    def transport(url,seconds):
        assert 0<seconds<=30;f.calls.append(url)
        row=next((r for r in rows if r['source_url']==url),None)
        if row and 'osf_object_id' in row:r=Response(url,b'UNREAD',302,[('Location',signed(row))])
        else:r=Response(url)
        f.responses.append(r);return r
    f.transport=transport
    return f


def test_unfrozen_production_never_reads(monkeypatch):
    monkeypatch.setattr(m,'MANIFEST_SHA256',None)
    monkeypatch.setattr(m,'reader',lambda _:pytest.fail('read before pin'))
    with pytest.raises(m.Refusal,match='unfrozen'):m.load_manifest('/not/read')


def test_production_scope_and_resource_limits():
    assert m.EXPECTED_COUNT==316 and m.EXPECTED_BYTES==940543951
    assert m.SUBJECTS==tuple(f'sub-pixar{i:03d}' for i in range(1,156))
    assert m.COORDINATES_PATH=='atlas/power_2011.csv' and len(m.PROVENANCE_PATHS)==4
    assert (m.WORKERS,m.MAX_SECONDS,m.SOCKET_SECONDS,m.MAX_BYTES,m.MAX_REQUESTS)==(2,900,30,1100000000,2000)
    assert m.MAX_REDIRECTS==5 and m.MIN_FREE_BYTES==5*1024**3


@pytest.mark.parametrize('role,reason',[('coordinates','one_power_coordinates'),('provenance','closed_provenance_inventory')])
def test_missing_required_auxiliary_mapping_is_not_optional(manufactured,monkeypatch,role,reason):
    f=manufactured
    row=next(r for r in f.doc['files'] if r['role']==role)
    f.doc['files'].remove(row);f.doc['n_files']-=1;f.doc['total_bytes']-=len(BODY)
    monkeypatch.setattr(m,'EXPECTED_COUNT',f.doc['n_files'])
    monkeypatch.setattr(m,'EXPECTED_BYTES',f.doc['total_bytes'])
    repin(f,monkeypatch)
    with pytest.raises(m.Refusal,match=reason):m.load_manifest(f.manifest)


def test_closed_mixed_network_bundle(manufactured,tmp_path,capsys):
    f=manufactured
    result=m.stage(tmp_path/'out',tmp_path/'work',f.manifest,transport=f.transport)
    assert result['status']=='ok' and result['source_file_count']==10 and result['source_bytes']==70
    assert result['network_requests']==16 and result['network_body_bytes']==70
    assert result['automatic_retries']==0 and not result['source_payload_parsed']
    assert m.verify_staged(tmp_path/'out')==f.doc
    assert all(r.closed for r in f.responses)
    assert all(r.reads==0 for r in f.responses if r.code==302)
    assert 'SECRET' not in capsys.readouterr().out+(tmp_path/'work/result.json').read_text()
    assert all(stat.S_IMODE((tmp_path/'out'/r['path']).stat().st_mode)==0o444 for r in f.doc['files'])


@pytest.mark.parametrize('internal',[False,True])
def test_local_three_passes_no_network_or_mutation(manufactured,tmp_path,internal):
    f=manufactured
    if internal:write(f.source/'source_manifest.json',f.manifest.read_bytes())
    before={p:(p.read_bytes(),m.signature(p.stat())) for p in f.source.rglob('*') if p.is_file()}
    result=m.stage(tmp_path/'out',tmp_path/'work',f.manifest,f.source,lambda *_:pytest.fail('network'))
    assert result['network_requests']==0 and m.verify_staged(tmp_path/'out')==f.doc
    assert all((p.read_bytes(),m.signature(p.stat()))==v for p,v in before.items())


def test_bad_final_local_member_stops_before_copy(manufactured,tmp_path,monkeypatch):
    f=manufactured;write(f.source/f.doc['files'][-1]['path'],b'PAYLOAD')
    monkeypatch.setattr(m,'copy_stream',lambda *_:pytest.fail('copy before authenticate all'))
    with pytest.raises(m.Refusal,match='sha256'):m.stage(tmp_path/'out',tmp_path/'work',f.manifest,f.source)
    assert not (tmp_path/'out').exists()
    assert json.loads((tmp_path/'work/result.json').read_text())['status']=='failed'


@pytest.mark.parametrize('kind',['task','schema','cohort','id','filename','role','duplicate_pair','duplicate_path','bool_size','zero_size','hash','md5','object','duplicate_object','bool_version','zero_version','participants_id','coordinates_role','coordinates_subject','coordinates_path','unexpected_provenance','processing_provider','notice_osf_provider','duplicate_coordinates','git_blob','git_commit','mutable_url','wrong_node','extra_query','count','total','archives'])
def test_manifest_rejections_before_source(manufactured,monkeypatch,kind):
    f=manufactured;d=f.doc;r=d['files'][0];t=next(x for x in d['files'] if x['role']=='coordinates')
    if kind=='task':d['task_id']='OTHER'
    elif kind=='schema':d['schema_version']='old'
    elif kind=='cohort':d['participant_ids'].reverse()
    elif kind=='id':r['participant_id']='sub-pixar1'
    elif kind=='filename':r['path']='wrong.nii.gz'
    elif kind=='role':r['role']='reduced_confounds'
    elif kind=='duplicate_pair':d['files'][1]=copy.deepcopy(r)
    elif kind=='duplicate_path':d['files'][-1]['path']=r['path']
    elif kind=='bool_size':r['size_bytes']=True
    elif kind=='zero_size':r['size_bytes']=0
    elif kind=='hash':r['sha256']='x'*64
    elif kind=='md5':del r['md5']
    elif kind=='object':r['osf_object_id']='bad'
    elif kind=='duplicate_object':d['files'][1]['osf_object_id']=r['osf_object_id']
    elif kind=='bool_version':r['source_version']=True
    elif kind=='zero_version':r['source_version']=0
    elif kind=='participants_id':d['files'][4]['participant_id']='sub-pixar001'
    elif kind=='coordinates_role':t['role']='template'
    elif kind=='coordinates_subject':t['participant_id']='sub-pixar001'
    elif kind=='coordinates_path':t['path']='atlas/other.csv'
    elif kind=='unexpected_provenance':d['files'][-1]['path']='provenance/unapproved'
    elif kind=='processing_provider':
        old=next(x for x in d['files'] if x['path']==m.PROCESSING_NOTICE)
        old.clear();old.update(document('provenance',m.PROCESSING_NOTICE,'README.md'))
    elif kind=='notice_osf_provider':
        old=d['files'][-1];old.update(osf_object_id='e'*24,source_version=2,md5=hashlib.md5(BODY).hexdigest(),
            source_url='https://files.osf.io/v1/resources/5hju4/providers/osfstorage/'+'e'*24+'?revision=2')
    elif kind=='duplicate_coordinates':
        d['files'][-1]=copy.deepcopy(t);d['files'][-1]['path']='atlas/duplicate.csv'
    elif kind=='git_blob':t['git_blob_sha1']='wrong'
    elif kind=='git_commit':t['source_commit']='main'
    elif kind=='mutable_url':t['source_url']=t['source_url'].replace(COMMIT,'main')
    elif kind=='wrong_node':r['source_url']=r['source_url'].replace('5hju4','pfde9')
    elif kind=='extra_query':r['source_url']+='&token=bad'
    elif kind=='count':d['n_files']+=1
    elif kind=='total':d['total_bytes']+=1
    else:d['archives']=[{}]
    repin(f,monkeypatch)
    with pytest.raises((m.Refusal,KeyError,TypeError)):m.load_manifest(f.manifest)


@pytest.mark.parametrize('kind',['extra','emptydir','symlink','missing','corruption','manifest'])
def test_closed_inventory(manufactured,kind):
    f=manufactured;write(f.source/'source_manifest.json',f.manifest.read_bytes());p=f.source/f.doc['files'][0]['path']
    if kind=='extra':write(f.source/'unexpected',b'x')
    elif kind=='emptydir':(f.source/'unused').mkdir()
    elif kind=='symlink':p.unlink();p.symlink_to(f.manifest)
    elif kind=='missing':p.unlink()
    elif kind=='corruption':write(p,b'PAYLOAD')
    else:write(f.source/'source_manifest.json',b'{}')
    with pytest.raises(m.Refusal):m.verify_staged(f.source)


@pytest.mark.parametrize('kind',['http','credentials','fragment','other_host','unsigned','wrong_storage','wrong_version','duplicate_revision'])
def test_osf_transport_endpoints(manufactured,kind):
    r=manufactured.doc['files'][0];url=signed(r)
    if kind=='http':url=url.replace('https:','http:')
    elif kind=='credentials':url=url.replace('https://','https://user:secret@')
    elif kind=='fragment':url+='#bad'
    elif kind=='other_host':url=url.replace('storage.googleapis.com','evil.test')
    elif kind=='unsigned':url=url.split('?')[0]
    elif kind=='wrong_storage':url=url.replace(r['sha256'],'a'*64)
    elif kind=='wrong_version':url=r['source_url'].replace('revision=2','revision=1')
    else:url=r['source_url']+'&revision=2'
    with pytest.raises(m.Refusal):m.endpoint(url,r)


@pytest.mark.parametrize('kind',['status','url','duplicate_length','length','encoding','transfer','html','hash','overrun','truncated','git_hash'])
def test_response_rejection_and_partial_preservation(manufactured,tmp_path,kind):
    f=manufactured;row=f.doc['files'][-1] if kind=='git_hash' else f.doc['files'][0]
    response=Response(row['source_url'])
    if kind=='status':response.code=503
    elif kind=='url':response.url='https://evil.test'
    elif kind=='duplicate_length':response.headers['Content-Length']='7'
    elif kind=='length':response.headers.replace_header('Content-Length','8')
    elif kind=='encoding':response.headers['Content-Encoding']='gzip'
    elif kind=='transfer':response.headers['Transfer-Encoding']='chunked'
    elif kind=='html':response.headers.replace_header('Content-Type','text/html')
    elif kind in ('hash','git_hash'):response=Response(row['source_url'],b'PAYLOAD')
    elif kind=='overrun':response=Response(row['source_url'],b'payloadX');response.headers.replace_header('Content-Length','7')
    else:response=Response(row['source_url'],b'payloa');response.headers.replace_header('Content-Length','7')
    state=m.State()
    with pytest.raises(m.Refusal):m.download(row,tmp_path/'target',state,lambda *_:response)
    assert response.closed and state.cancelled.is_set() and not (tmp_path/'target').exists()
    if kind in ('status','url','duplicate_length','length','encoding','transfer','html'):assert response.reads==0


@pytest.mark.parametrize('kind',['existing_dest','existing_work','overlap','source_overlap','metadata_overlap','symlink'])
def test_preserve_unsafe_targets(manufactured,tmp_path,kind):
    f=manufactured;dest=tmp_path/'out';work=tmp_path/'work'
    if kind=='existing_dest':dest.mkdir();write(dest/'keep',b'keep')
    elif kind=='existing_work':work.mkdir();write(work/'keep',b'keep')
    elif kind=='overlap':work=dest/'inside'
    elif kind=='source_overlap':dest=f.source/'inside'
    elif kind=='metadata_overlap':dest=f.manifest.parent
    else:dest.symlink_to(tmp_path/'absent')
    with pytest.raises(m.Refusal):m.stage(dest,work,f.manifest,f.source)
    if kind=='existing_dest':assert (dest/'keep').read_bytes()==b'keep'
    if kind=='existing_work':assert (work/'keep').read_bytes()==b'keep'


@pytest.mark.parametrize('kind',['request','bytes','time','cancel','disk'])
def test_bounds(manufactured,tmp_path,monkeypatch,kind):
    f=manufactured;state=m.State()
    if kind=='request':state.requests=m.MAX_REQUESTS
    elif kind=='bytes':state.bytes=m.MAX_BYTES
    elif kind=='time':state.deadline=0
    elif kind=='cancel':state.cancelled.set()
    else:monkeypatch.setattr(m.shutil,'disk_usage',lambda _:SimpleNamespace(free=0))
    with pytest.raises(m.Refusal):
        if kind=='request':state.request()
        elif kind=='bytes':state.received(b'x')
        elif kind=='disk':m.stage(tmp_path/'out',tmp_path/'work',f.manifest,f.source)
        else:state.start('x')


def test_git_hash_requires_correct_content_even_when_sha256_updated(manufactured,tmp_path):
    row=copy.deepcopy(manufactured.doc['files'][-1]);row['sha256']=hashlib.sha256(b'PAYLOAD').hexdigest()
    response=Response(row['source_url'],b'PAYLOAD');state=m.State()
    with pytest.raises(m.Refusal,match='git_blob'):m.download(row,tmp_path/'target',state,lambda *_:response)


def test_public_manifest_may_be_sibling_of_data_directory(manufactured,tmp_path):
    f=manufactured;dest=f.manifest.parent/'data'
    before=f.manifest.read_bytes()
    result=m.stage(dest,tmp_path/'work',f.manifest,f.source)
    assert result['status']=='ok' and f.manifest.read_bytes()==before
    assert m.verify_staged(dest)==f.doc


def test_commit_hex_inside_mutable_ref_path_is_not_an_immutable_url(manufactured):
    row=copy.deepcopy(manufactured.doc['files'][-1])
    row['source_url']=row['source_url'].replace('/'+COMMIT+'/', '/main/'+COMMIT+'/')
    with pytest.raises(m.Refusal,match='immutable_document_commit'):m.transport_start(row)


def test_pinned_osf_processing_notice_and_three_git_notices_are_supported(manufactured,tmp_path):
    f=manufactured
    provenance=[r for r in f.doc['files'] if r['role']=='provenance']
    assert {r['path'] for r in provenance}==m.PROVENANCE_PATHS
    assert [r['path'] for r in provenance if 'osf_object_id' in r]==[m.PROCESSING_NOTICE]
    assert len([r for r in provenance if 'git_blob_sha1' in r])==3
    assert m.stage(tmp_path/'out',tmp_path/'work',f.manifest,f.source)['status']=='ok'


def test_first_causal_failure_not_masked_by_concurrent_cancel(manufactured,tmp_path):
    f=manufactured;state=m.State();barrier=threading.Barrier(2);primary=threading.Event()
    first,second=f.doc['files'][:2]
    class StopResponse(Response):
        def read1(self,n):
            barrier.wait(timeout=5)
            if self.url==first['source_url']:
                failure=OSError('manufactured causal failure');state.fail(failure);primary.set();raise failure
            assert primary.wait(timeout=5)
            state.check()
    def transport(url,seconds):return StopResponse(url)
    with pytest.raises(OSError,match='manufactured causal failure'):
        m.parallel_download([(first,tmp_path/'first'),(second,tmp_path/'second')],state,transport)
    assert isinstance(state.failure,OSError) and state.cancelled.is_set()


def test_failed_staging_is_preserved_not_automatically_retried(manufactured,tmp_path):
    f=manufactured;calls=[]
    def fail(url,_):calls.append(url);raise OSError('SECRET')
    with pytest.raises(OSError):m.stage(tmp_path/'out',tmp_path/'work',f.manifest,transport=fail)
    saved=(tmp_path/'work/result.json').read_bytes();n=len(calls)
    assert b'SECRET' not in saved and not (tmp_path/'out').exists()
    with pytest.raises(m.Refusal):m.stage(tmp_path/'out',tmp_path/'work',f.manifest,transport=fail)
    assert len(calls)==n and (tmp_path/'work/result.json').read_bytes()==saved
