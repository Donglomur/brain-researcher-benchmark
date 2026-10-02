"""Tiny manufactured source-staging mechanics, never real ROI data or network."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import urllib.request

import pytest

SPEC = importlib.util.spec_from_file_location('stage_source_under_test', Path(__file__).parents[1] / 'environment' / 'stage_source.py')
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def fail(*args, **kwargs): raise AssertionError('Source-free test attempted network')
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', fail)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    original, output = tmp_path/'original', tmp_path/'staged'
    (original/'roi').mkdir(parents=True)
    files = []
    for path, body, role, version, key in [
        (s.PHENO, b'original metadata fixture\n', 'phenotype', s.PHENO_VERSION, s.PHENO),
        ('roi/Pitt_0050003_rois_cc200.1D', b'opaque ROI bytes\n', 'roi_timeseries', 'null', s.ROI_PREFIX+'Pitt_0050003_rois_cc200.1D')]:
        (original/path).write_bytes(body)
        entry = {'path':path, 'role':role, 'size_bytes':len(body), 'sha256':hashlib.sha256(body).hexdigest(),
                 'version_id':version, 'source_key':key, 'source_url':s.BASE+key,
                 'download_url':s.BASE+key+'?versionId='+version, 'etag':'"source-identity-not-md5"',
                 'named_version_immutable':version!='null', 'etag_is_assumed_md5':False}
        if role=='roi_timeseries': entry.update(subject_id='50003',file_id='Pitt_0050003',phenotype_row_index=1)
        files.append(entry)
    manifest = {'schema_version':1,'dataset_id':s.DATASET,'upstream_immutable_release':False,'files':files}
    path = tmp_path/'source_manifest.json'
    raw = (json.dumps(manifest,indent=2)+'\n').encode()
    path.write_bytes(raw)
    monkeypatch.setattr(s,'MANIFEST_SHA256',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(s,'N_FILES',2)
    monkeypatch.setattr(s,'TOTAL_BYTES',sum(x['size_bytes'] for x in files))
    return original,output,path,manifest,raw


def test_read_manifest_whole_digest_and_schema(bundle):
    assert s.read_manifest(bundle[2]) == (bundle[3],bundle[4])


def test_offline_stage_copy_exact_permissions_and_no_source_writes(bundle):
    original,out,path,manifest,raw=bundle
    modes={p.relative_to(original):p.stat().st_mode for p in original.rglob('*')}
    assert s.stage_source(out,original,path)==manifest
    assert (out/'source_manifest.json').read_bytes()==raw
    assert s.verify_staged(out)==manifest
    for entry in manifest['files']:
        assert (out/entry['path']).read_bytes()==(original/entry['path']).read_bytes()
        assert stat.S_IMODE((out/entry['path']).stat().st_mode)==0o444
    assert stat.S_IMODE(out.stat().st_mode)==0o755
    assert stat.S_IMODE((out/'roi').stat().st_mode)==0o755
    assert {p.relative_to(original):p.stat().st_mode for p in original.rglob('*')}==modes


def test_existing_verified_destination_no_network_or_writes(bundle,monkeypatch):
    original,out,path,manifest,_=bundle
    s.stage_source(out,original,path)
    before={p.relative_to(out):(p.stat().st_mtime_ns,p.stat().st_mode) for p in out.rglob('*')}
    monkeypatch.setattr(s,'download',lambda *a,**k:pytest.fail('network on verified reuse'))
    assert s.stage_source(out,manifest_path=path)==manifest
    assert before=={p.relative_to(out):(p.stat().st_mtime_ns,p.stat().st_mode) for p in out.rglob('*')}


def test_unverified_existing_destination_preserved(bundle):
    original,out,path,_,_=bundle
    out.mkdir(); (out/'important').write_bytes(b'preserve')
    with pytest.raises((ValueError,FileNotFoundError)): s.stage_source(out,original,path)
    assert (out/'important').read_bytes()==b'preserve'


@pytest.mark.parametrize('mutation',['extra_file','extra_dir','missing','changed_size','changed_same_size','symlink','fifo'])
def test_exact_inventory_and_bytes_fail_closed(bundle,mutation):
    original,out,path,manifest,_=bundle
    file=original/manifest['files'][1]['path']
    if mutation=='extra_file': (original/'extra').write_bytes(b'X')
    if mutation=='extra_dir': (original/'empty_extra').mkdir()
    if mutation=='missing': file.unlink()
    if mutation=='changed_size': file.write_bytes(b'x')
    if mutation=='changed_same_size': file.write_bytes(b'X'*file.stat().st_size)
    if mutation=='symlink':
        file.rename(original/'other'); file.symlink_to(original/'other')
    if mutation=='fifo':
        import os
        file.unlink(); os.mkfifo(file)
    with pytest.raises((ValueError,FileNotFoundError)): s.stage_source(out,original,path)
    assert not out.exists()


def test_manifest_digest_corruption(bundle):
    path=bundle[2]; path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='manifest SHA'): s.read_manifest(path)


def test_duplicate_and_nonfinite_manifest_rejected_after_known_fixture_pin(bundle,monkeypatch):
    path=bundle[2]
    for raw in [b'{"schema_version":1,"schema_version":1}',b'{"extra":1e999}']:
        path.write_bytes(raw); monkeypatch.setattr(s,'MANIFEST_SHA256',hashlib.sha256(raw).hexdigest())
        with pytest.raises(ValueError): s.read_manifest(path)


@pytest.mark.parametrize('field,value',[
    ('path','../Pitt_0050003_rois_cc200.1D'),('path','roi/../Pitt_0050003_rois_cc200.1D'),
    ('role','bold'),('sha256','A'*64),('etag','"good"\r\nInjected: yes'),('version_id','x&other=y'),
    ('download_url','http://s3.amazonaws.com/wrong'),('source_url','https://example.com/data'),
    ('subject_id','50004'),('phenotype_row_index',True),('phenotype_row_index',1112),
    ('named_version_immutable',True),('etag_is_assumed_md5',True),('size_bytes',True)])
def test_wrong_source_identity_rejected(bundle,field,value):
    manifest=copy.deepcopy(bundle[3]); manifest['files'][1][field]=value
    with pytest.raises((ValueError,TypeError)): s.validate_manifest(manifest)


def test_duplicate_original_paths_refused(bundle):
    manifest=copy.deepcopy(bundle[3]); manifest['files'][1]=copy.deepcopy(manifest['files'][0])
    with pytest.raises(ValueError): s.validate_manifest(manifest)


def test_symlink_manifest_and_ancestor_refused(bundle,tmp_path):
    alias=tmp_path/'alias'; alias.symlink_to(bundle[0],target_is_directory=True)
    with pytest.raises(ValueError,match='Symlink'): s.safe_path(alias/'roi'/'..'/'x')
    link=tmp_path/'manifestlink'; link.symlink_to(bundle[2])
    with pytest.raises(ValueError,match='Symlink'): s.read_manifest(link)


@pytest.mark.parametrize('relative',['child','roi/../child'])
def test_nested_source_destination_rejected(bundle,relative):
    with pytest.raises(ValueError,match='disjoint'): s.stage_source(bundle[0]/relative,bundle[0],bundle[2])


def test_manifest_contained_in_destination_rejected(bundle):
    with pytest.raises(ValueError,match='disjoint'): s.stage_source(bundle[2].parent,bundle[0],bundle[2])


class Response:
    status=200
    def __init__(self,entry,body):
        self.entry=entry; self.stream=io.BytesIO(body)
        self.headers={'Content-Length':str(entry['size_bytes']),'ETag':entry['etag'],'x-amz-version-id':entry['version_id'],'Set-Cookie':'secret'}
    def geturl(self): return self.entry['download_url']
    def read(self,n): pytest.fail('Use one bounded HTTP read1')
    def read1(self,n): return self.stream.read(n)
    def __enter__(self): return self
    def __exit__(self,*args): return None


class Opener:
    def __init__(self,bundle,mutation=None): self.bundle,self.mutation,self.calls=bundle,mutation,[]
    def open(self,req,timeout):
        self.calls.append(req.full_url)
        entry=next(e for e in self.bundle[3]['files'] if e['download_url']==req.full_url)
        assert req.get_header('If-match')==entry['etag'] and timeout>0
        response=Response(entry,(self.bundle[0]/entry['path']).read_bytes())
        if self.mutation=='etag': response.headers['ETag']='"different"'
        if self.mutation=='version': response.headers['x-amz-version-id']='different'
        if self.mutation=='length': response.headers['Content-Length']='999'
        if self.mutation=='digest': response.stream=io.BytesIO(b'X'*entry['size_bytes'])
        if self.mutation=='truncated': response.stream=io.BytesIO(b'X')
        if self.mutation=='overlong': response.stream=io.BytesIO(b'X'*(entry['size_bytes']+1))
        return response


def test_manufactured_conditional_download(bundle,tmp_path):
    target=tmp_path/'downloaded'; (target/'roi').mkdir(parents=True)
    ledger=tmp_path/'ledger'; opener=Opener(bundle)
    s.download(bundle[3],target,ledger,opener)
    s.verify_inventory(target,bundle[3])
    assert len(opener.calls)==2
    assert json.loads((ledger/'result.json').read_text())['status']=='verified_all_originals'
    assert all('secret' not in p.read_text() for p in ledger.glob('*.json'))


@pytest.mark.parametrize('mutation',['etag','version','length','digest','truncated','overlong'])
def test_manufactured_download_failure_preserved_no_retry(bundle,tmp_path,mutation):
    target=tmp_path/'downloaded'; (target/'roi').mkdir(parents=True)
    ledger=tmp_path/'ledger'; opener=Opener(bundle,mutation)
    with pytest.raises(ValueError): s.download(bundle[3],target,ledger,opener)
    assert len(opener.calls)<=2 and len(set(opener.calls))==len(opener.calls)
    assert list(target.rglob('*.partial'))
    result=json.loads((ledger/'result.json').read_text())
    assert result['status']=='failed_preserved' and result['reason']


def test_redirect_body_not_read():
    class Body:
        closed=False
        def read(self,*args): pytest.fail('Redirect body read')
        def close(self): self.closed=True
    body=Body()
    with pytest.raises(ValueError): s.NoRedirect().http_error_302(None,body,302,'moved',{})
    assert body.closed


def test_import_has_no_execution():
    assert callable(s.verify_staged) and callable(s.stage_source)


def test_frozen_real_manifest_metadata_only():
    manifest,raw=s.read_manifest()
    assert len(manifest['files'])==1036
    assert sum(e['size_bytes'] for e in manifest['files'])==406540381
    assert manifest['cohort_source']['original_rows']==1112
    assert manifest['cohort_source']['no_filename_rows']==77
    assert 'source_files_directory' not in manifest and 'cohort_ledger' not in manifest
    assert hashlib.sha256(raw).hexdigest()==s.MANIFEST_SHA256
