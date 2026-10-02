"""Source-free integrity and preservation fixtures; no original neural computations."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ENV = Path(__file__).parents[1] / 'environment'
SPEC = importlib.util.spec_from_file_location('mtlmemory_stager', ENV / 'stage_data.py')
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    manifest = json.loads((ENV / 'source_manifest.json').read_text())
    manifest['files'] = manifest['files'][:2]
    payloads = [b'one original fixture', b'a different original fixture']
    source = tmp_path / 'originals'
    for record, payload in zip(manifest['files'], payloads):
        record['size_bytes'] = len(payload)
        record['sha256'] = hashlib.sha256(payload).hexdigest()
        target = source / record['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    manifest['n_files'] = 2
    manifest['total_size_bytes'] = sum(map(len, payloads))
    raw = (json.dumps(manifest, indent=2)+'\n').encode()
    path = tmp_path / 'fixture_manifest.json'
    path.write_bytes(raw)
    monkeypatch.setattr(stage, 'MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(stage, 'N_FILES', 2)
    monkeypatch.setattr(stage, 'TOTAL_BYTES', manifest['total_size_bytes'])
    return SimpleNamespace(manifest=manifest, raw=raw, path=path, source=source, payloads=payloads,
                           destination=tmp_path/'staged', ledger=tmp_path/'ledger')


def repin(bundle, monkeypatch):
    raw = (json.dumps(bundle.manifest, indent=2)+'\n').encode()
    bundle.path.write_bytes(raw)
    monkeypatch.setattr(stage, 'MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())


def install_transport(bundle, monkeypatch, mutation=None):
    calls = []
    lookup = {r['transport_url']:(r,p) for r,p in zip(bundle.manifest['files'],bundle.payloads)}
    class Response(io.BytesIO):
        status = 200
        def __init__(self, record, payload):
            super().__init__(payload)
            self.url = record['transport_url']
            self.headers = {'Content-Length':str(len(payload)), 'ETag':record['etag'],
                            'x-amz-version-id':record['version_id'], 'Content-Encoding':'identity'}
            if mutation:
                mutation(self, record)
        def geturl(self):
            return self.url
    def opened(request, timeout):
        calls.append(request.full_url)
        record,payload = lookup[request.full_url]
        assert request.get_header('Range') is None
        assert request.get_header('If-match') == record['etag']
        return Response(record,payload)
    monkeypatch.setattr(stage.urllib.request, 'build_opener', lambda *args:SimpleNamespace(open=opened))
    return calls


def test_actual_public_manifest_exact_hash_and_inventory():
    manifest, raw = stage.read_manifest()
    assert hashlib.sha256(raw).hexdigest() == '3819f2b5e9403f184b94be7d1374476c964c08c054763ec7b8d40cf6bbf7e7b9'
    assert len(manifest['files']) == 87
    assert sum(r['size_bytes'] for r in manifest['files']) == 6_197_474_020


def test_offline_stage_and_verified_reuse_never_fetch(bundle, monkeypatch):
    monkeypatch.setattr(stage, 'download_sources', lambda *args:pytest.fail('Offline reuse must not fetch'))
    stage.stage_data(bundle.destination, source_dir=bundle.source, manifest_path=bundle.path)
    assert stage.verify_staged(bundle.destination) == bundle.manifest
    before = {p.relative_to(bundle.destination).as_posix():p.stat().st_mtime_ns for p in bundle.destination.rglob('*')}
    stage.stage_data(bundle.destination, manifest_path=bundle.path)
    after = {p.relative_to(bundle.destination).as_posix():p.stat().st_mtime_ns for p in bundle.destination.rglob('*')}
    assert before == after
    assert (bundle.destination.stat().st_mode & 0o777)==0o755
    for p in bundle.destination.rglob('*'):
        assert (p.stat().st_mode & 0o777)==(0o755 if p.is_dir() else 0o444)


def test_offline_reuse_accepts_exact_staged_manifest(bundle):
    (bundle.source/'source_manifest.json').write_bytes(bundle.raw)
    stage.stage_data(bundle.destination, source_dir=bundle.source, manifest_path=bundle.path)
    stage.verify_staged(bundle.destination)


def test_whole_manifest_hash_including_whitespace(bundle):
    bundle.path.write_bytes(bundle.raw+b' ')
    with pytest.raises(ValueError, match='manifest SHA'):
        stage.read_manifest(bundle.path)


@pytest.mark.parametrize('change', [
    lambda m:m.update(version='draft'),
    lambda m:m.update(license='CC0'),
    lambda m:m['files'].append(m['files'][0]),
    lambda m:m['files'][0].update(path='../outside.nwb'),
    lambda m:m['files'][0].update(path='/outside.nwb'),
    lambda m:m['files'][0].update(path='sub-wrong/a.nwb'),
    lambda m:m['files'][0].update(role='reference_answer'),
    lambda m:m['files'][0].update(sha256='G'*64),
    lambda m:m['files'][0].update(transport_url='http://dandiarchive.s3.us-east-2.amazonaws.com/blobs/x'),
    lambda m:m['files'][0].update(transport_url='https://example.org/blobs/x?versionId=foo'),
    lambda m:m['files'][0].update(version_id='different-version'),
    lambda m:m.update(total_size_bytes=1),
])
def test_manifest_schema_rejects_unsafe_or_changed_identity(bundle,monkeypatch,change):
    change(bundle.manifest)
    repin(bundle,monkeypatch)
    with pytest.raises(ValueError):
        stage.read_manifest(bundle.path)


@pytest.mark.parametrize('corruption',['missing','wrong-size','wrong-hash','extra-file','extra-empty-directory','fifo'])
def test_local_source_damage_preserved_no_destination(bundle,corruption):
    target = bundle.source/bundle.manifest['files'][0]['path']
    if corruption=='missing':
        target.unlink()
    elif corruption=='wrong-size':
        target.write_bytes(b'short')
    elif corruption=='wrong-hash':
        target.write_bytes(b'X'*target.stat().st_size)
    elif corruption=='extra-file':
        (bundle.source/'unexpected').write_text('preserve')
    elif corruption=='extra-empty-directory':
        (bundle.source/'unexpected').mkdir()
    else:
        os.mkfifo(bundle.source/'unexpected')
    with pytest.raises(ValueError):
        stage.stage_data(bundle.destination, source_dir=bundle.source,manifest_path=bundle.path)
    assert not bundle.destination.exists()
    if corruption=='extra-file':
        assert (bundle.source/'unexpected').read_text()=='preserve'


@pytest.mark.parametrize('where',['file','source-root','source-ancestor','destination-root','destination-ancestor','manifest'])
def test_symlinks_rejected_without_changes(bundle,tmp_path,where):
    source,destination,manifest = bundle.source,bundle.destination,bundle.path
    if where=='file':
        original = source/bundle.manifest['files'][0]['path']
        backup = tmp_path/'saved'; original.rename(backup); original.symlink_to(backup)
    elif where=='source-root':
        link=tmp_path/'linked-source';link.symlink_to(source,target_is_directory=True);source=link
    elif where=='source-ancestor':
        link=tmp_path/'ancestor';link.symlink_to(tmp_path,target_is_directory=True);source=link/'originals'
    elif where=='destination-root':
        destination.symlink_to(source,target_is_directory=True)
    elif where=='destination-ancestor':
        link=tmp_path/'ancestor';link.symlink_to(tmp_path,target_is_directory=True);destination=link/'new-output'
    else:
        link=tmp_path/'linked-manifest';link.symlink_to(manifest);manifest=link
    with pytest.raises(ValueError,match='symlink'):
        stage.stage_data(destination,source_dir=source,manifest_path=manifest)


def test_conflicting_existing_destination_preserved(bundle):
    bundle.destination.mkdir()
    sentinel=bundle.destination/'mine';sentinel.write_text('preserve')
    with pytest.raises((ValueError,FileNotFoundError)):
        stage.stage_data(bundle.destination,source_dir=bundle.source,manifest_path=bundle.path)
    assert sentinel.read_text()=='preserve'


def test_source_destination_nesting_rejected(bundle):
    with pytest.raises(ValueError,match='non-nested'):
        stage.stage_data(bundle.source/'nested',source_dir=bundle.source,manifest_path=bundle.path)


def test_network_stage_exact_objects_once(bundle,monkeypatch):
    calls=install_transport(bundle,monkeypatch)
    stage.stage_data(bundle.destination,ledger=bundle.ledger,manifest_path=bundle.path)
    assert sorted(calls)==sorted(r['transport_url'] for r in bundle.manifest['files'])
    stage.verify_staged(bundle.destination)
    receipt=json.loads((bundle.ledger/'result.json').read_text())
    assert receipt['status']=='verified_all_originals'
    assert receipt['transferred_bytes']==bundle.manifest['total_size_bytes']


@pytest.mark.parametrize('field,value',[('Content-Length','999'),('ETag','changed'),('x-amz-version-id','changed'),('Content-Encoding','gzip')])
def test_transport_identity_failure_preserves_ledger_no_retry(bundle,monkeypatch,field,value):
    calls=install_transport(bundle,monkeypatch,lambda response,record:response.headers.update({field:value}))
    with pytest.raises(ValueError,match='acquisition failed'):
        stage.stage_data(bundle.destination,ledger=bundle.ledger,manifest_path=bundle.path)
    assert len(calls)==len(set(calls))
    assert not bundle.destination.exists()
    assert json.loads((bundle.ledger/'result.json').read_text())['status']=='failed_preserved'


def test_transport_corrupt_bytes_rejected(bundle,monkeypatch):
    bundle.payloads=[b'X'*len(p) for p in bundle.payloads]
    install_transport(bundle,monkeypatch)
    with pytest.raises(ValueError,match='acquisition failed'):
        stage.stage_data(bundle.destination,ledger=bundle.ledger,manifest_path=bundle.path)
    assert list(bundle.destination.parent.glob('.staged-staging-*'))
    assert not bundle.destination.exists()


def test_existing_ledger_preserved(bundle):
    bundle.ledger.mkdir();(bundle.ledger/'sentinel').write_text('preserve')
    with pytest.raises(FileExistsError):
        stage.stage_data(bundle.destination,ledger=bundle.ledger,manifest_path=bundle.path)
    assert (bundle.ledger/'sentinel').read_text()=='preserve'


def test_ledger_nested_in_destination_rejected(bundle):
    with pytest.raises(ValueError,match='non-nested'):
        stage.stage_data(bundle.destination,ledger=bundle.destination/'ledger',manifest_path=bundle.path)


def test_redirects_never_followed():
    with pytest.raises(ValueError,match='redirect'):
        stage.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://example.org')
