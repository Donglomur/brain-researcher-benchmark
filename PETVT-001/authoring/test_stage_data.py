"""Manufactured opaque transport and staging checks; no original files/network."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import urllib.error

import pytest

PATH=Path(__file__).resolve().parents[1]/'environment'/'stage_data.py'
SPEC=importlib.util.spec_from_file_location('stage_candidate',PATH)
s=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(s)


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir();rows=[]
    for i in range(31):
        raw=bytes([33+i])*(15521 if i==30 else 15519)
        p=root/f'f{i:02}';p.write_bytes(raw)
        git=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        rows.append(dict(path=p.name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),git_blob_sha1=git,source_url=s.PREFIX+git))
    value=dict(task_id='PETVT-001',participant_ids=s.SUBJECTS,n_files=31,total_bytes=481091,files=rows)
    raw=json.dumps(value).encode();doc=tmp_path/'manifest.json';doc.write_bytes(raw);(root/'source_manifest.json').write_bytes(raw)
    monkeypatch.setattr(s,'SOURCE_SHA',hashlib.sha256(raw).hexdigest())
    return root,doc,value


def test_offline_copy_and_no_scientific_parser(bundle,tmp_path):
    root,doc,value=bundle;out=tmp_path/'out';capture=tmp_path/'capture'
    result=s.stage(doc,out,capture,source=root)
    assert result['status']=='ok' and result['requests']==0 and not result['original_values_parsed']
    s.verify(out,doc.read_bytes(),value)
    assert len(s.inventory(out))==32 and not(out.with_name('out.pending')).exists()


@pytest.mark.parametrize('kind',['payload','extra','missing','symlink','hardlink'])
def test_bad_source_preserves_failure(bundle,tmp_path,kind):
    root,doc,value=bundle;p=root/value['files'][0]['path']
    if kind=='payload':p.write_bytes(b'bad')
    elif kind=='extra':(root/'unexpected').write_text('bad')
    elif kind=='missing':p.unlink()
    elif kind=='symlink':p.unlink();p.symlink_to(doc)
    else:
        import os
        os.link(p,tmp_path/'linked')
    with pytest.raises(ValueError):s.stage(doc,tmp_path/'out',tmp_path/'capture',source=root)
    assert (tmp_path/'capture'/'failure.json').exists() and not(tmp_path/'out').exists()


@pytest.mark.parametrize('destination',['source','ancestor','manifest','capture_equal','existing'])
def test_protected_or_existing_destinations(bundle,tmp_path,destination):
    root,doc,_=bundle;out=tmp_path/'out';capture=tmp_path/'capture'
    if destination=='source':out=root/'nested'
    elif destination=='ancestor':out=tmp_path
    elif destination=='manifest':out=doc
    elif destination=='capture_equal':capture=out
    else:out.mkdir()
    with pytest.raises(ValueError):s.stage(doc,out,capture,source=root)
    assert not(root/'failure.json').exists()


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'{"x":[Infinity]}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):s.strict_json(raw)


class Response(io.BytesIO):
    status=200
    def __init__(self,raw,url):super().__init__(raw);self.url=url
    def geturl(self):return self.url
    def read1(self,n):return self.read(n)


@pytest.mark.parametrize('mutation',['none','sha','size','encoding','base64','payload','redirect','status','oversize'])
def test_git_envelope_and_payload(bundle,mutation):
    root,_,value=bundle;row=value['files'][0];raw=(root/row['path']).read_bytes()
    envelope=dict(sha=row['git_blob_sha1'],size=len(raw),encoding='base64',content=base64.b64encode(raw).decode())
    if mutation=='sha':envelope['sha']='0'*40
    elif mutation=='size':envelope['size']+=1
    elif mutation=='encoding':envelope['encoding']='utf8'
    elif mutation=='base64':envelope['content']='@@'
    elif mutation=='payload':envelope['content']=base64.b64encode(raw[:-1]+b'x').decode()
    response=Response(json.dumps(envelope).encode(),row['source_url'])
    if mutation=='redirect':response.url='https://example.invalid/redirect'
    elif mutation=='status':response.status=302
    elif mutation=='oversize':response=Response(b' '*(s.MAX_RESPONSE+1),row['source_url'])
    transport=s.Transport();transport.opener=type('Opener',(),{'open':lambda *a,**kw:response})()
    if mutation=='none':assert transport.get(row)==raw
    else:
        with pytest.raises(ValueError):transport.get(row)


def test_http_error_closed_unread(bundle):
    _,_,value=bundle;body=io.BytesIO(b'not read')
    error=urllib.error.HTTPError(value['files'][0]['source_url'],403,'forbidden',{},body)
    def fail(*a,**kw):raise error
    transport=s.Transport();transport.opener=type('Opener',(),{'open':fail})()
    with pytest.raises(ValueError,match='HTTP'):transport.get(value['files'][0])
    assert body.closed


@pytest.mark.parametrize('bound',['requests','wall','bytes'])
def test_transport_bounds(bundle,bound):
    _,_,value=bundle;transport=s.Transport()
    if bound=='requests':transport.requests=31
    elif bound=='wall':transport.started-=121
    else:
        transport.response_bytes=s.MAX_RESPONSE_TOTAL
        transport.opener=type('Opener',(),{'open':lambda *a,**kw:Response(b'x',value['files'][0]['source_url'])})()
    with pytest.raises(ValueError):transport.get(value['files'][0])


def test_default_plan_no_manifest_read(monkeypatch,capsys):
    monkeypatch.setattr(s,'manifest',lambda *a:pytest.fail('plan read'))
    assert s.main([])==0 and 'plan_only' in capsys.readouterr().out
