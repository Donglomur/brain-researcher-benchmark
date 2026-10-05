"""Tiny source-staging mechanics; never download or read scientific source arrays."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

TASK = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('timedecode_source_stage', TASK/'environment/stage_data.py')
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)
ORIGINAL_MANIFEST = json.loads((TASK/'environment/source_manifest.json').read_text())


def archive_bytes(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        for name, body, kind, link in entries:
            member = tarfile.TarInfo(name)
            member.type, member.linkname = kind, link
            member.size = len(body) if kind == tarfile.REGTYPE else 0
            archive.addfile(member, io.BytesIO(body) if kind == tarfile.REGTYPE else None)
    return output.getvalue()


@pytest.fixture
def source(tmp_path, monkeypatch):
    manifest = copy.deepcopy(ORIGINAL_MANIFEST)
    entries = []
    for index, entry in enumerate(manifest['files']):
        body = ('fixture-only-'+str(index)).encode()
        entry['size_bytes'] = len(body)
        entry['sha256'] = hashlib.sha256(body).hexdigest()
        entry['md5'] = hashlib.md5(body).hexdigest()
        entries.append((entry['archive_member'], body, tarfile.REGTYPE, ''))
    manifest_path = tmp_path/'contract.json'
    archive_path = tmp_path/'original.tar.gz'
    def install(new_entries=None):
        payload = archive_bytes(entries if new_entries is None else new_entries)
        archive_path.write_bytes(payload)
        manifest['archive'].update(size_bytes=len(payload), md5=hashlib.md5(payload).hexdigest(),
                                   sha256=hashlib.sha256(payload).hexdigest(),
                                   declared_metadata_sizes_bytes=[len(payload)])
        body = (json.dumps(manifest, indent=2)+'\n').encode()
        manifest_path.write_bytes(body)
        monkeypatch.setattr(stage, 'MANIFEST_PATH', manifest_path)
        monkeypatch.setattr(stage, 'MANIFEST_SHA256', hashlib.sha256(body).hexdigest())
    install()
    return manifest, entries, archive_path, install, tmp_path/'staged'


def test_shipped_source_manifest_pin():
    assert hashlib.sha256((TASK/'environment/source_manifest.json').read_bytes()).hexdigest() == '533bc28bbcc1e8fe53880504b75756ee4035ecb423e3be84c5fddf1660b779f6'
    assert len(ORIGINAL_MANIFEST['files']) == 3
    assert ORIGINAL_MANIFEST['archive']['size_bytes'] == 1652774934
    assert ORIGINAL_MANIFEST['license']['dataset'] == 'not_established'


def test_local_archive_staging_is_offline_and_exact(source, monkeypatch, tmp_path):
    manifest, entries, archive, install, destination = source
    monkeypatch.setattr(stage.urllib.request, 'build_opener', lambda *a: pytest.fail('local archive must not access network'))
    receipt = tmp_path/'receipt.json'
    result = stage.stage_data(destination, archive, receipt)
    assert result['status'] == 'verified'
    assert stage.verify_staged(destination) == manifest
    assert archive.is_file()
    assert {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} == {'source_manifest.json'}|{e['path'] for e in manifest['files']}
    assert not list(destination.rglob('*.tar.gz'))
    assert not list(destination.rglob('*receipt*'))
    assert json.loads(receipt.read_text())['extraction']['links_followed'] is False


def test_verified_reuse_no_archive_needed(source):
    *_, archive, install, destination = source
    stage.stage_data(destination, archive)
    assert stage.stage_data(destination)['status'] == 'verified_existing'


def test_preserve_existing_conflicting_directory(source):
    *_, archive, install, destination = source
    destination.mkdir()
    existing = destination/'user.txt'; existing.write_text('preserve me')
    with pytest.raises((ValueError, FileNotFoundError)):
        stage.stage_data(destination, archive)
    assert existing.read_text() == 'preserve me'


@pytest.mark.parametrize('mutation', ['content','missing','extra','manifest','symlink'])
def test_staged_source_tampering_rejected(source, mutation):
    manifest, _, archive, _, destination = source
    stage.stage_data(destination, archive)
    path = destination/manifest['files'][0]['path']
    path.chmod(0o644)
    (destination/'source_manifest.json').chmod(0o644)
    if mutation == 'content': path.write_bytes(b'wrong')
    elif mutation == 'missing': path.unlink()
    elif mutation == 'extra': (destination/'answer.txt').write_text('extra')
    elif mutation == 'manifest': (destination/'source_manifest.json').write_text('{}')
    else:
        path.unlink(); path.symlink_to(archive)
    with pytest.raises(ValueError): stage.verify_staged(destination)


@pytest.mark.parametrize('mutation', ['size','md5','sha256'])
def test_archive_identity_rejected(source, mutation):
    manifest, _, archive, _, _ = source
    manifest = copy.deepcopy(manifest)
    manifest['archive'][mutation if mutation != 'size' else 'size_bytes'] = 1 if mutation=='size' else '0'*64
    with pytest.raises(ValueError): stage.verify_archive(archive, manifest)


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.DIRTYPE,tarfile.CHRTYPE])
def test_allowlisted_member_must_be_regular(source, kind):
    _, entries, archive, install, destination = source
    rows = list(entries); rows[0] = (rows[0][0],b'',kind,'../../elsewhere')
    install(rows)
    with pytest.raises(ValueError): stage.stage_data(destination,archive)
    assert not destination.exists()


@pytest.mark.parametrize('name', ['../escape','/absolute','MNE-sample-data/../escape','MNE-sample-data\\evil'])
def test_unsafe_members_rejected_even_if_not_selected(source, name):
    _, entries, archive, install, destination = source
    install(entries+[(name,b'x',tarfile.REGTYPE,'')])
    with pytest.raises(ValueError): stage.stage_data(destination,archive)
    assert not destination.exists()


def test_nonselected_symlink_never_followed(source):
    _, entries, archive, install, destination = source
    install(entries+[('MNE-sample-data/unused',b'',tarfile.SYMTYPE,'/do/not/follow')])
    stage.stage_data(destination,archive)
    assert not (destination/'unused').exists()


@pytest.mark.parametrize('mutation', ['duplicate','missing','bad_payload','bad_size'])
def test_original_members_are_complete_unique_and_hashed(source, mutation):
    _, entries, archive, install, destination = source
    rows = list(entries)
    if mutation=='duplicate': rows.append(rows[0])
    elif mutation=='missing': rows=rows[1:]
    else:
        name,body,kind,link=rows[0]
        rows[0]=(name,(b'X'*len(body) if mutation=='bad_payload' else body+b'x'),kind,link)
    install(rows)
    with pytest.raises(ValueError): stage.stage_data(destination,archive)
    assert not destination.exists()


@pytest.mark.parametrize('limit', ['max_members','max_declared_expanded_bytes','max_selected_expanded_bytes'])
def test_bounded_archive_inventory(source,limit):
    manifest,_,archive,install,destination=source
    manifest['archive'][limit]=1;install()
    with pytest.raises(ValueError):stage.stage_data(destination,archive)


def test_receipt_cannot_enter_runtime(source):
    *_,archive,_,destination=source
    with pytest.raises(ValueError):stage.stage_data(destination,archive,destination/'receipt.json')


@pytest.mark.parametrize('url', ['http://osf.io/download/tp4sg','https://evil.example/x',
 'https://user:pass@osf.io/x','https://osf.io:444/x',
 'https://storage.googleapis.com/wrong/object'])
def test_transport_rejects_unapproved_endpoint(url):
    with pytest.raises(ValueError):stage.check_url(url,ORIGINAL_MANIFEST['archive'])


def test_exact_storage_object_is_allowed_and_token_is_not_logged():
    policy=ORIGINAL_MANIFEST['archive']
    url='https://storage.googleapis.com'+policy['approved_storage_object_path']+'?Signature=do-not-log'
    stage.check_url(url,policy)
    assert '?' not in stage.public_url(url)


def test_mock_download_is_single_request_and_hash_verified(source,monkeypatch,tmp_path):
    manifest,_,archive,_,_=source
    class Response(io.BytesIO):
        status=200
        url=manifest['archive']['url']
        headers={'Content-Length':str(archive.stat().st_size)}
    calls=[]
    class Opener:
        def open(self,request,timeout):
            calls.append(request.full_url)
            return Response(archive.read_bytes())
    monkeypatch.setattr(stage.urllib.request,'build_opener',lambda *a:Opener())
    output=tmp_path/'download.tar.gz'
    receipt=stage.download_archive(output,manifest)
    assert calls==[manifest['archive']['url']]
    assert receipt['measured_bytes']==archive.stat().st_size
    assert receipt['automatic_retries']==0


def test_mock_network_failure_not_retried(source,monkeypatch,tmp_path):
    manifest,*_=source
    calls=[]
    class Opener:
        def open(self,request,timeout):
            calls.append(1);raise OSError('fixture network failure')
    monkeypatch.setattr(stage.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(OSError):stage.download_archive(tmp_path/'failed.partial',manifest)
    assert len(calls)==1


def test_existing_receipt_is_preserved_before_any_staging(source, tmp_path):
    _, _, archive, _, destination = source
    receipt = tmp_path/'prior.json'; receipt.write_text('prior evidence')
    with pytest.raises(FileExistsError):
        stage.stage_data(destination, archive, receipt)
    assert receipt.read_text() == 'prior evidence'
    assert not destination.exists()


def test_symlink_parent_cannot_redirect_destination_or_verification(source, tmp_path):
    _, _, archive, _, destination = source
    parent = tmp_path/'real'; parent.mkdir()
    link = tmp_path/'linked'; link.symlink_to(parent, target_is_directory=True)
    with pytest.raises(ValueError): stage.stage_data(link/'dataset', archive)
    stage.stage_data(parent/'dataset', archive)
    with pytest.raises(ValueError): stage.verify_staged(link/'dataset')


def test_staged_file_permissions_allow_unprivileged_read(source):
    _, _, archive, _, destination = source
    stage.stage_data(destination, archive)
    assert destination.stat().st_mode & 0o777 == 0o755
    for path in destination.rglob('*'):
        assert path.stat().st_mode & 0o777 == (0o755 if path.is_dir() else 0o444)


@pytest.mark.parametrize('url', [
    'https://osf.io/download/86qa2?version=1',
    'https://osf.io/download/86qa2',
    'https://osf.io/download/other?version=6',
    'https://files.osf.io/v1/resources/rxvq7/providers/osfstorage/wrong?version=6',
    'https://files.osf.io/v1/resources/rxvq7/providers/osfstorage/59c0e26f9ad5a1025c4ab159?version=1',
])
def test_transport_identity_cannot_drift(url):
    with pytest.raises(ValueError): stage.check_url(url, ORIGINAL_MANIFEST['archive'])


@pytest.mark.parametrize('failure', ['partial_response', 'wrong_size_header', 'encoded', 'over_cap', 'wrong_body'])
def test_download_rejects_transport_or_content_failure_once(source, monkeypatch, tmp_path, failure):
    manifest, _, archive, _, _ = source
    body = archive.read_bytes()
    class Response(io.BytesIO):
        status = 206 if failure == 'partial_response' else 200
        url = manifest['archive']['url']
        headers = {'Content-Length': str(len(body))}
    if failure == 'wrong_size_header': Response.headers['Content-Length'] = '1'
    if failure == 'encoded': Response.headers['Content-Encoding'] = 'gzip'
    if failure == 'over_cap': manifest['archive']['transfer_cap_bytes'] = 1
    if failure == 'wrong_body': body = b'x'*len(body)
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url); return Response(body)
    monkeypatch.setattr(stage.urllib.request, 'build_opener', lambda *a: Opener())
    progress = {}
    with pytest.raises(ValueError):
        stage.download_archive(tmp_path/'failed.partial', manifest, progress)
    assert len(calls) == 1
    assert progress['automatic_retries'] == 0
    assert progress['error_type'] == 'ValueError'


def test_stale_head_length_never_relaxes_measured_body_identity(source, monkeypatch, tmp_path):
    manifest, _, archive, _, _ = source
    body = archive.read_bytes()
    manifest['archive']['declared_metadata_sizes_bytes'].append(1)
    class Response(io.BytesIO):
        status = 200
        url = manifest['archive']['url']
        headers = {'Content-Length': '1'}
    class Opener:
        def open(self, request, timeout): return Response(body)
    monkeypatch.setattr(stage.urllib.request, 'build_opener', lambda *a: Opener())
    report = stage.download_archive(tmp_path/'verified.tar.gz', manifest)
    assert report['declared_content_length'] == '1'
    assert report['measured_bytes'] == len(body)


def test_keep_authoring_archive_preserves_original_bytes(source, monkeypatch, tmp_path):
    manifest, _, archive, _, destination = source
    def download(path, contract, progress):
        path.write_bytes(archive.read_bytes())
        stage.verify_archive(path, contract)
        progress.update(measured_bytes=path.stat().st_size, automatic_retries=0)
        return progress
    monkeypatch.setattr(stage, 'download_archive', download)
    report = stage.stage_data(destination, receipt=tmp_path/'acquisition.json', keep_archive=True)
    assert report['authoring_archive_retained'] is True
    assert Path(report['archive_path']).read_bytes() == archive.read_bytes()
