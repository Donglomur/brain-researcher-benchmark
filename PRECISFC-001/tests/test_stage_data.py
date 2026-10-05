"""Source-free staging fixtures; original image bodies are never read here."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import pytest

ENV = Path(__file__).parents[1]/'environment'
SPEC = importlib.util.spec_from_file_location('precisfc_stage', ENV/'stage_data.py')
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError('Network is forbidden in source-free fixtures')
    monkeypatch.setattr(stage.urllib.request, 'build_opener', deny)


def record(body, path='nested/source.txt', role='tmask'):
    md5 = hashlib.md5(body).hexdigest()
    return dict(path=path, role=role, subject='MSC01', session='func01', size_bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(), published_md5=md5, etag='"'+md5+'"',
                version_id='fixed', url='https://s3.amazonaws.com/exact?versionId=fixed', transport='immutable_s3')


def toy_bundle(tmp_path, monkeypatch):
    source = tmp_path/'originals'; source.mkdir()
    body = b'0\n1\n'; item = record(body)
    (source/'nested').mkdir(); (source/item['path']).write_bytes(body)
    inputs = tmp_path/'public'; inputs.mkdir()
    text = b'roi,x,y,z\n1,0,0,0\n'
    (inputs/'power_2011.csv').write_bytes(text)
    auxiliary = dict(path='provenance/power_2011.csv', role='atlas_coordinates', transport='bundled_exact_bytes',
                     size_bytes=len(text), sha256=hashlib.sha256(text).hexdigest())
    manifest = {'files':[item,auxiliary]}
    metadata = tmp_path/'metadata'; metadata.mkdir()
    path = metadata/'source_manifest.json'; path.write_text(json.dumps(manifest))
    monkeypatch.setattr(stage, 'MANIFEST_SHA256', hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(stage, 'validate_manifest', lambda value: None)  # Tiny fixture inventory, not production scope.
    return source, inputs, path, manifest


def test_local_source_only_copy_and_readonly_reuse(tmp_path, monkeypatch):
    source, inputs, manifest, _ = toy_bundle(tmp_path, monkeypatch)
    target = tmp_path/'staged'
    stage.stage_data(target, source, manifest_path=manifest, public_inputs=inputs)
    assert stage.verify_staged(target)['files'][0]['path'] == 'nested/source.txt'
    before = {p.relative_to(target).as_posix():p.read_bytes() for p in target.rglob('*') if p.is_file()}
    stage.stage_data(target, source, manifest_path=manifest, public_inputs=inputs)
    assert before == {p.relative_to(target).as_posix():p.read_bytes() for p in target.rglob('*') if p.is_file()}
    assert (source/'nested/source.txt').read_bytes() == b'0\n1\n'
    assert all(p.stat().st_mode & 0o777 == 0o444 for p in target.rglob('*') if p.is_file())
    assert target.stat().st_mode & 0o777 == 0o755


def test_conflicting_destination_preserved(tmp_path, monkeypatch):
    source, inputs, manifest, _ = toy_bundle(tmp_path, monkeypatch)
    target = tmp_path/'staged'; target.mkdir(); (target/'user').write_text('evidence')
    with pytest.raises(ValueError):
        stage.stage_data(target, source, manifest_path=manifest, public_inputs=inputs)
    assert (target/'user').read_text() == 'evidence'


@pytest.mark.parametrize('kind', ['corrupt','extra','empty_dir','link'])
def test_reused_original_inventory_rejects_unverified_changes(tmp_path, monkeypatch, kind):
    source, inputs, manifest, _ = toy_bundle(tmp_path, monkeypatch)
    if kind == 'corrupt':
        (source/'nested/source.txt').write_bytes(b'1\n0\n')
    elif kind == 'extra':
        (source/'extra').write_bytes(b'not an input')
    elif kind == 'empty_dir':
        (source/'unused').mkdir()
    else:
        (source/'alias').symlink_to(source/'nested/source.txt')
    with pytest.raises(ValueError):
        stage.stage_data(tmp_path/'staged', source, manifest_path=manifest, public_inputs=inputs)
    assert not (tmp_path/'staged').exists()


def test_manifest_exact_hash_and_regular_file(tmp_path, monkeypatch):
    _, _, path, _ = toy_bundle(tmp_path, monkeypatch)
    path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError, match='SHA256'):
        stage.read_manifest(path)
    with pytest.raises(ValueError, match='regular'):
        stage.read_manifest(path.parent)


def test_symlink_and_nested_guards(tmp_path, monkeypatch):
    source, inputs, manifest, _ = toy_bundle(tmp_path, monkeypatch)
    link = tmp_path/'link'; link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match='Symlink'):
        stage.stage_data(link/'new', source, manifest_path=manifest, public_inputs=inputs)
    with pytest.raises(ValueError, match='non-nested'):
        stage.stage_data(source/'nested-destination', source, manifest_path=manifest, public_inputs=inputs)
    with pytest.raises(ValueError, match='non-nested'):
        stage.stage_data(manifest.parent/'nested', source, manifest_path=manifest, public_inputs=inputs)


def test_public_input_corruption_precedes_network(tmp_path, monkeypatch):
    _, inputs, manifest, _ = toy_bundle(tmp_path, monkeypatch)
    (inputs/'power_2011.csv').write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        stage.stage_data(tmp_path/'staged', manifest_path=manifest, public_inputs=inputs)
    assert not (tmp_path/'staged').exists()


def test_published_md5_independently_checked(tmp_path):
    body = b'original bytes'; path = tmp_path/'source'; path.write_bytes(body)
    item = record(body); item['published_md5'] = '0'*32
    with pytest.raises(ValueError, match='MD5'):
        stage.verify_file(path, item)


def test_header_only_after_complete_checksums(tmp_path, monkeypatch):
    header = b'H'*352; body = gzip.compress(header+b'NEVER_DECODE'*10000)
    path = tmp_path/'source'; path.write_bytes(body)
    item = record(body, role='bold'); item['header_sha256'] = hashlib.sha256(header).hexdigest()
    stage.verify_file(path, item)
    item['sha256'] = '0'*64
    monkeypatch.setattr(stage, 'verify_header', lambda *args: pytest.fail('Premature header decoding'))
    with pytest.raises(ValueError, match='SHA256'):
        stage.verify_file(path, item)


def test_header_identity_mismatch(tmp_path):
    path = tmp_path/'source'; path.write_bytes(gzip.compress(b'H'*352))
    with pytest.raises(ValueError, match='Header'):
        stage.verify_header(path, {'header_sha256':'0'*64})


@pytest.fixture
def real_manifest():
    # Small metadata only, never open any referenced source object.
    return json.loads((ENV/'source_manifest.json').read_text())


def test_frozen_real_manifest_metadata_only(real_manifest):
    stage.validate_manifest(real_manifest)
    assert hashlib.sha256((ENV/'source_manifest.json').read_bytes()).hexdigest() == stage.MANIFEST_SHA256


@pytest.mark.parametrize('mutation', [
    lambda m:m.update(release='draft'), lambda m:m['files'].pop(),
    lambda m:m['files'].append(copy.deepcopy(m['files'][0])),
    lambda m:m['files'][0].update(path='../escape'),
    lambda m:m['files'][0].update(subject='MSC03'),
    lambda m:m['files'][0].update(role='tmask'),
    lambda m:m['files'][0].update(sha256='bad'),
    lambda m:m['files'][0].update(published_md5='bad'),
    lambda m:m['files'][0].update(size_bytes=True),
    lambda m:m['files'][0].update(etag='"other"'),
    lambda m:m['files'][0].update(version_id='new'),
    lambda m:m['files'][0].update(url=m['files'][0]['url'].replace('s3.amazonaws.com','evil.invalid')),
    lambda m:m['files'][0].update(url=m['files'][0]['url']+'&other=1'),
    lambda m:m['files'][0].update(header_sha256='x'*64),
    lambda m:m['files'][-1].update(role='atlas_readme'),
    lambda m:m['files'][-1].update(path='provenance/other.json')])
def test_closed_manifest_contract(real_manifest, mutation):
    mutation(real_manifest)
    with pytest.raises(ValueError):
        stage.validate_manifest(real_manifest)


class Response(io.BytesIO):
    def __init__(self, body, item, changes=None, status=200):
        super().__init__(body); self.status = status; self.url = item['url']; self.read_calls = 0
        self.headers = {'Content-Length':str(item['size_bytes']), 'ETag':item['etag'],
                        'x-amz-version-id':item['version_id'], **(changes or {})}
    def geturl(self):
        return self.url
    def read(self, size=-1):
        self.read_calls += 1
        return super().read(size)


def fake_download(tmp_path, monkeypatch, body=None, changes=None, status=200):
    original = b'0\n1\n'; item = record(original)
    response = Response(original if body is None else body, item, changes, status)
    class Opener:
        calls = 0
        def open(self, request, timeout):
            self.calls += 1
            assert request.get_header('If-match') == item['etag']
            return response
    opener = Opener()
    monkeypatch.setattr(stage.urllib.request, 'build_opener', lambda *args:opener)
    destination = tmp_path/'source'; destination.mkdir()
    ledger = tmp_path/'ledger'
    return item, response, opener, destination, ledger


def test_download_success_to_immutable_original(tmp_path, monkeypatch):
    item, _, opener, destination, ledger = fake_download(tmp_path, monkeypatch)
    stage.download_originals([item], destination, ledger)
    assert (destination/item['path']).read_bytes() == b'0\n1\n' and opener.calls == 1
    assert json.loads((ledger/'result.json').read_text())['status'] == 'verified_all_originals'


@pytest.mark.parametrize('body', [b'0\n', b'1\n0\n', b'0\n1\nX'])
def test_download_invalid_body_no_retry(tmp_path, monkeypatch, body):
    item, _, opener, destination, ledger = fake_download(tmp_path, monkeypatch, body=body)
    with pytest.raises(ValueError, match='acquisition failed'):
        stage.download_originals([item], destination, ledger)
    assert opener.calls == 1 and not (destination/item['path']).exists()
    assert (destination/(item['path']+'.partial')).read_bytes() == body


@pytest.mark.parametrize('changes', [{'ETag':'wrong'},{'x-amz-version-id':'wrong'},
    {'Content-Length':'99'},{'Content-Encoding':'gzip'}])
def test_download_transport_guard_no_body(tmp_path, monkeypatch, changes):
    item, response, opener, destination, ledger = fake_download(tmp_path, monkeypatch, changes=changes)
    with pytest.raises(ValueError):
        stage.download_originals([item], destination, ledger)
    assert opener.calls == 1 and response.read_calls == 0


def test_no_redirects():
    with pytest.raises(ValueError, match='redirect'):
        stage.NoRedirect().redirect_request(None,None,302,None,None,'https://other.invalid')


def test_download_evidence_not_overwritten(tmp_path, monkeypatch):
    item, _, opener, destination, ledger = fake_download(tmp_path, monkeypatch)
    ledger.mkdir(); (ledger/'original').write_text('preserve')
    with pytest.raises(FileExistsError):
        stage.download_originals([item], destination, ledger)
    assert opener.calls == 0 and (ledger/'original').read_text() == 'preserve'
