"""Synthetic staging fixtures only: no original BOLD values or network access."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest


ENV=Path(__file__).resolve().parents[1]/'environment'
spec=importlib.util.spec_from_file_location('netinteg_stager',ENV/'stage_data.py')
stager=importlib.util.module_from_spec(spec);spec.loader.exec_module(stager)


def digest(data):return hashlib.sha256(data).hexdigest()


def tar_bytes(entries):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz') as archive:
        for name,data,kind in entries:
            info=tarfile.TarInfo(name)
            if kind=='file':info.size=len(data);archive.addfile(info,io.BytesIO(data))
            else:info.type=kind;info.linkname='outside';archive.addfile(info)
    return out.getvalue()


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    manifest=json.loads((ENV/'source_manifest.json').read_text())
    cache=tmp_path/'cache';archives=tmp_path/'archives';archives.mkdir()
    payloads={}
    for record in manifest['files']:
        payload=('synthetic fixture only: '+record['path']).encode()
        payloads[record['path']]=payload
        record.update(size_bytes=len(payload),sha256=digest(payload))
        if 'git_blob_sha1' in record:
            record['git_blob_sha1']=hashlib.sha1(f'blob {len(payload)}\0'.encode()+payload).hexdigest()
        path=cache/record['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
    records={r['path']:r for r in manifest['files']}
    for archive in manifest['archives']:
        entries=[]
        for member in archive['members']:
            ref=records[member['path']]
            member.update(size_bytes=ref['size_bytes'],sha256=ref['sha256'])
            entries.append((member['archive_member'],payloads[member['path']],'file'))
        payload=tar_bytes(entries)
        archive.update(size_bytes=len(payload),sha256=digest(payload))
        (archives/archive['filename']).write_bytes(payload)
    raw=(json.dumps(manifest,indent=2)+'\n').encode()
    path=tmp_path/'source_manifest.json';path.write_bytes(raw)
    monkeypatch.setattr(stager,'MANIFEST_SHA256',digest(raw))
    return {'manifest':manifest,'path':path,'raw':raw,'cache':cache,'archives':archives,
            'out':tmp_path/'out','payloads':payloads,'tmp':tmp_path}


def no_network(*args,**kwargs):raise AssertionError('No fixture may perform a real network request')


def test_closed_offline_stage_and_repeat_preserve_bytes(bundle,monkeypatch):
    monkeypatch.setattr(stager,'download_sources',no_network)
    stager.stage_data(bundle['out'],bundle['path'],cache_dir=bundle['cache'])
    assert stager.verify_staged(bundle['out'])==bundle['manifest']
    before={p.relative_to(bundle['out']).as_posix():(p.stat().st_ino,p.stat().st_mtime_ns) for p in bundle['out'].rglob('*')}
    stager.stage_data(bundle['out'],bundle['path'])
    after={p.relative_to(bundle['out']).as_posix():(p.stat().st_ino,p.stat().st_mtime_ns) for p in bundle['out'].rglob('*')}
    assert before==after
    for p in (bundle['out'],*bundle['out'].rglob('*')):
        assert p.stat().st_mode&0o777 == (0o755 if p.is_dir() else 0o444)


def test_original_archive_cache_is_offline_and_unchanged(bundle,monkeypatch):
    monkeypatch.setattr(stager,'download_sources',no_network)
    direct=bundle['tmp']/'direct'
    for path in stager.DIRECT:
        target=direct/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(bundle['payloads'][path])
    before={p.name:digest(p.read_bytes()) for p in bundle['archives'].iterdir()}
    stager.stage_data(bundle['out'],bundle['path'],cache_dir=direct,archive_cache_dirs=[bundle['archives']])
    assert stager.verify_staged(bundle['out'])==bundle['manifest']
    assert before=={p.name:digest(p.read_bytes()) for p in bundle['archives'].iterdir()}


def test_conflicting_existing_input_is_preserved_before_network(bundle,monkeypatch):
    monkeypatch.setattr(stager,'download_sources',no_network)
    item=bundle['manifest']['files'][0];bad=bundle['out']/item['path'];bad.parent.mkdir(parents=True)
    bad.write_bytes(b'wrong existing bytes')
    with pytest.raises(ValueError):stager.stage_data(bundle['out'],bundle['path'],cache_dir=bundle['cache'])
    assert bad.read_bytes()==b'wrong existing bytes'
    assert [p for p in bundle['out'].rglob('*') if p.is_file()]==[bad]


def test_conflicting_destination_manifest_is_preserved(bundle,monkeypatch):
    monkeypatch.setattr(stager,'download_sources',no_network)
    bundle['out'].mkdir();target=bundle['out']/'source_manifest.json';target.write_text('{}')
    with pytest.raises(ValueError,match='conflicting'):stager.stage_data(bundle['out'],bundle['path'])
    assert target.read_text()=='{}'


@pytest.mark.parametrize('kind',['file','directory','symlink'])
def test_reject_extra_inventory(bundle,monkeypatch,kind):
    monkeypatch.setattr(stager,'download_sources',no_network)
    stager.stage_data(bundle['out'],bundle['path'],cache_dir=bundle['cache'])
    extra=bundle['out']/'unexpected'
    if kind=='file':extra.write_bytes(b'extra')
    elif kind=='directory':extra.mkdir()
    else:extra.symlink_to(bundle['tmp']/'missing')
    with pytest.raises(ValueError):stager.verify_staged(bundle['out'])
    assert extra.exists() or extra.is_symlink()


def test_missing_source_file(bundle,monkeypatch):
    monkeypatch.setattr(stager,'download_sources',no_network)
    stager.stage_data(bundle['out'],bundle['path'],cache_dir=bundle['cache'])
    (bundle['out']/bundle['manifest']['files'][0]['path']).unlink()
    with pytest.raises(ValueError,match='Incomplete'):stager.verify_staged(bundle['out'])


@pytest.mark.parametrize('where',['root','cache','manifest','cache_file'])
def test_symlink_refusal(bundle,monkeypatch,where):
    monkeypatch.setattr(stager,'download_sources',no_network)
    if where=='root':bundle['out'].symlink_to(bundle['cache'],target_is_directory=True)
    elif where=='cache':
        link=bundle['tmp']/'linked_cache';link.symlink_to(bundle['cache'],target_is_directory=True);bundle['cache']=link
    elif where=='manifest':
        link=bundle['tmp']/'linked_manifest';link.symlink_to(bundle['path']);bundle['path']=link
    else:
        target=bundle['cache']/bundle['manifest']['files'][0]['path'];target.unlink();target.symlink_to(bundle['path'])
    with pytest.raises(ValueError,match='symlink'):stager.stage_data(bundle['out'],bundle['path'],cache_dir=bundle['cache'])


def test_corrupt_whole_manifest_pin(bundle):
    bundle['path'].write_bytes(bundle['raw']+b' ')
    with pytest.raises(ValueError,match='manifest SHA256'):stager.read_manifest(bundle['path'])


@pytest.mark.parametrize('mutation',['role','url','participant','duplicate','archive_member','archive_url','archive_size','sha'])
def test_manifest_semantics_fail_closed(bundle,mutation):
    m=copy.deepcopy(bundle['manifest']);bold=next(r for r in m['files'] if r['role']=='bold')
    if mutation=='role':bold['role']='not_bold'
    elif mutation=='url':next(r for r in m['files'] if r['role']=='atlas_image')['url']='https://example.org/other'
    elif mutation=='participant':bold['participant']=True
    elif mutation=='duplicate':m['files'][-1]=copy.deepcopy(m['files'][0])
    elif mutation=='archive_member':m['archives'][0]['members'][0]['archive_member']='../escape'
    elif mutation=='archive_url':m['archives'][0]['url']='https://www.nitrc.org/other'
    elif mutation=='archive_size':m['archives'][0]['size_bytes']=150000001
    else:bold['sha256']='not-a-digest'
    with pytest.raises(ValueError):stager.validate_manifest(m)


@pytest.mark.parametrize('value',['','/absolute','../escape','a/../b','a//b','a/./b','a\\b','./a','.','a/','a\0b',None])
def test_unsafe_relative_path(value):
    with pytest.raises(ValueError):stager.safe_relative(value)


def test_corrupt_cache_and_published_blob_refused(bundle,monkeypatch):
    monkeypatch.setattr(stager,'download_sources',no_network)
    item=next(r for r in bundle['manifest']['files'] if r['role']=='atlas_image')
    record=copy.deepcopy(item);record['git_blob_sha1']='0'*40
    with pytest.raises(ValueError,match='digest'):stager.verify_file(bundle['cache']/item['path'],record)
    target=bundle['cache']/item['path'];target.write_bytes(b'X'*item['size_bytes'])
    with pytest.raises(ValueError,match='digest'):stager.stage_data(bundle['out'],bundle['path'],cache_dir=bundle['cache'])
    assert not bundle['out'].exists()


@pytest.mark.parametrize('bad',[('../escape',b'x','file'),('/absolute',b'x','file'),
    ('link',b'',tarfile.SYMTYPE),('hardlink',b'',tarfile.LNKTYPE),('device',b'',tarfile.CHRTYPE)])
def test_reject_unsafe_unselected_tar_members(tmp_path,bad):
    source=tmp_path/'source.tgz';source.write_bytes(tar_bytes([bad,('ok',b'ok','file')]))
    rec={'archive_member':'ok','path':'ok','size_bytes':2,'sha256':digest(b'ok')}
    with pytest.raises(ValueError):stager.extract_selected(source,[rec],tmp_path/'out')
    assert not (tmp_path/'escape').exists()


@pytest.mark.parametrize('mode',['duplicate','missing','size','hash'])
def test_selected_tar_identity_checks(tmp_path,mode):
    rec={'archive_member':'ok','path':'ok','size_bytes':2,'sha256':digest(b'ok')}
    entries=[('ok',b'ok','file')]
    if mode=='duplicate':entries.append(('ok',b'ok','file'))
    elif mode=='missing':entries=[('other',b'ok','file')]
    elif mode=='size':entries=[('ok',b'bad','file')]
    else:entries=[('ok',b'no','file')]
    source=tmp_path/'source.tgz';source.write_bytes(tar_bytes(entries))
    with pytest.raises(ValueError):stager.extract_selected(source,[rec],tmp_path/'out')


def test_unselected_safe_member_never_written(tmp_path):
    source=tmp_path/'source.tgz';source.write_bytes(tar_bytes([('extra',b'not selected','file'),('ok',b'ok','file')]))
    rec={'archive_member':'ok','path':'ok','size_bytes':2,'sha256':digest(b'ok')}
    stager.extract_selected(source,[rec],tmp_path/'out')
    assert [p.name for p in (tmp_path/'out').iterdir()]==['ok']


class Response(io.BytesIO):
    status=200
    def __init__(self,data,url,headers):super().__init__(data);self.url=url;self.headers=headers
    def geturl(self):return self.url


@pytest.mark.parametrize('mode',['ok','length','redirect','hash','excess'])
def test_download_pins_and_sanitized_headers(tmp_path,monkeypatch,capsys,mode):
    payload=b'tiny';url='https://example.invalid/fixture'
    record={'url':url,'size_bytes':4,'sha256':digest(payload)}
    headers={'Content-Length':'4','Content-Type':'application/octet-stream','Set-Cookie':'NEVER_RETAIN'}
    data=payload
    if mode=='length':headers['Content-Length']='5'
    elif mode=='hash':data=b'fake'
    elif mode=='excess':data=b'tinyextra'
    class Opener:
        def open(self,request,timeout):return Response(data,url if mode!='redirect' else url+'/changed',headers)
    monkeypatch.setattr(stager.urllib.request,'build_opener',lambda *args:Opener())
    ledger=tmp_path/'ledger'
    if mode=='ok':
        result=stager.download_sources([record],ledger)
        assert result[url].read_bytes()==payload
    else:
        with pytest.raises(ValueError):stager.download_sources([record],ledger)
        assert json.loads((ledger/'result.json').read_text())['status']=='failed'
    assert all('NEVER_RETAIN' not in p.read_text() for p in ledger.glob('*.json'))
    stdout=capsys.readouterr().out
    assert 'NEVER_RETAIN' not in stdout and '"source_transfer": "start"' in stdout
    assert ('"source_transfer": "verified"' if mode=='ok' else '"source_transfer": "failed"') in stdout
    with pytest.raises(FileExistsError):stager.download_sources([record],ledger)


def test_archive_cache_digest_conflict_preserved(bundle,monkeypatch):
    monkeypatch.setattr(stager,'download_sources',no_network)
    first=bundle['manifest']['archives'][0];path=bundle['archives']/first['filename']
    path.write_bytes(b'X'*first['size_bytes'])
    with pytest.raises(ValueError,match='digest'):
        stager.stage_data(bundle['out'],bundle['path'],archive_cache_dirs=[bundle['archives']])
    assert path.read_bytes()==b'X'*first['size_bytes']
    assert not bundle['out'].exists()
