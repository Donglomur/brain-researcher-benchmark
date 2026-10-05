"""Source-free integrity and safe offline-staging fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location('clinconn_stage',Path(__file__).parents[1]/'environment/stage_data.py')
stage=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(stage)


@pytest.fixture
def tiny(tmp_path,monkeypatch):
    body=b'original source bytes'
    r={'path':'data/a.txt','size_bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
       'md5':hashlib.md5(body).hexdigest(),'git_blob_sha1':hashlib.sha1(f'blob {len(body)}\0'.encode()+body).hexdigest()}
    m={'files':[r]};raw=json.dumps(m).encode();source=tmp_path/'original';(source/'data').mkdir(parents=True);(source/r['path']).write_bytes(body)
    monkeypatch.setattr(stage,'read_manifest',lambda *args:(m,raw))
    return source,m,raw


def test_real_public_manifest_is_complete():
    m,_=stage.read_manifest()
    assert len(m['files'])==697 and m['payload_bytes']==2305653613
    assert sum(r['selected'] for r in m['cohort']['rows'])==172
    assert len(m['cohort']['rows'])==177


def test_changed_manifest_rejected(tmp_path):
    p=tmp_path/'manifest';p.write_text('{}')
    with pytest.raises(ValueError,match='manifest'):stage.read_manifest(p)


@pytest.mark.parametrize('name',['','/x','../x','a/../b','a//b','a/./b','a\\b','a\x00b','./x'])
def test_unsafe_relative(name):
    with pytest.raises(ValueError):stage.safe_relative(name)


@pytest.mark.parametrize('field,value',[('sha256','bad'),('size_bytes',True),('size_bytes',0),('transport_url','https://example.org'),('s3_version_id','wrong'),('etag','"multipart-2"')])
def test_bad_source_record(field,value):
    r=copy.deepcopy(stage.read_manifest()[0]['files'][0]);r[field]=value
    with pytest.raises(ValueError):stage.validate_record(r)


def test_disallow_lookalike_host():
    r=copy.deepcopy(stage.read_manifest()[0]['files'][0]);r['url']=r['url'].replace('s3.amazonaws.com','s3.amazonaws.com.evil.test')
    with pytest.raises(ValueError):stage.validate_record(r)


def test_all_publisher_git_pins_required():
    records=[r for r in stage.read_manifest()[0]['files'] if r['role'].startswith('pial_')]
    for r in records:
        r=copy.deepcopy(r);r['git_blob_sha1']='x'
        with pytest.raises(ValueError):stage.validate_record(r)


def test_offline_fresh_and_existing_no_network(tiny,tmp_path,monkeypatch):
    source,m,_=tiny;target=tmp_path/'staged'
    monkeypatch.setattr(stage,'download_sources',lambda *a:pytest.fail('Unexpected network'))
    stage.stage_data(target,source)
    assert stage.verify_staged(target)==m
    assert (target/'data/a.txt').stat().st_mode&0o777==0o444
    assert target.stat().st_mode&0o777==0o755
    assert stage.stage_data(target)==m


@pytest.mark.parametrize('kind',['hash','size','extra','empty_dir','symlink'])
def test_source_conflicts_preserved(tiny,tmp_path,kind):
    source,m,_=tiny;p=source/'data/a.txt';before=p.read_bytes()
    if kind=='hash':p.write_bytes(b'X'+before[1:])
    elif kind=='size':p.write_bytes(before+b'x')
    elif kind=='extra':(source/'unexpected').write_text('keep')
    elif kind=='empty_dir':(source/'unexpected').mkdir()
    else:p.unlink();p.symlink_to(tmp_path/'missing')
    with pytest.raises(ValueError):stage.stage_data(tmp_path/'staged',source)
    assert not (tmp_path/'staged').exists()
    assert source.exists()


def test_existing_destination_is_not_repaired(tiny,tmp_path):
    source,_,_=tiny;target=tmp_path/'staged';target.mkdir();(target/'keep').write_text('original')
    with pytest.raises(ValueError):stage.stage_data(target,source)
    assert (target/'keep').read_text()=='original'


@pytest.mark.parametrize('digest',['md5','git_blob_sha1'])
def test_independent_digest_checked(tiny,digest):
    source,m,_=tiny;r=dict(m['files'][0]);r[digest]='0'*len(r[digest])
    with pytest.raises(ValueError):stage.verify_file(source/r['path'],r)


def test_symlink_ancestor(tiny,tmp_path):
    source,_,_=tiny;link=tmp_path/'alias';link.symlink_to(source,target_is_directory=True)
    with pytest.raises(ValueError):stage.stage_data(tmp_path/'staged',link)


def test_nested_destination(tiny):
    source,_,_=tiny
    with pytest.raises(ValueError):stage.stage_data(source/'new',source)


def test_no_redirect():
    with pytest.raises(ValueError):stage.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com')


def test_receipts_never_overwrite(tmp_path):
    path=tmp_path/'receipt';stage.write_json_new(path,{'v':1})
    with pytest.raises(FileExistsError):stage.write_json_new(path,{'v':2})
    assert json.loads(path.read_text())=={'v':1}
