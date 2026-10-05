"""Source-free staging safety tests; no original EEG or network is used."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('aasmstage_source', Path(__file__).parents[1] / 'environment' / 'stage_data.py')
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected network access in source-free fixture')
    monkeypatch.setattr(stage.urllib.request, 'build_opener', forbidden)


def test_published_manifest_identity():
    manifest, raw = stage.read_manifest()
    assert hashlib.sha256(raw).hexdigest() == stage.MANIFEST_SHA256
    assert len(manifest['files']) == 12
    assert sum(r['size_bytes'] for r in manifest['files']) == 298590434
    assert manifest['license'] == 'ODC-By-1.0'


@pytest.mark.parametrize('key,value', [('version', '2.0.0'), ('license', 'CC0'),
    ('subjects', [0, 1]), ('recording', 2), ('dataset_doi', 'wrong')])
def test_bad_manifest_metadata(key, value):
    manifest, _ = stage.read_manifest()
    manifest[key] = value
    with pytest.raises(ValueError):
        stage.validate_manifest(manifest)


@pytest.mark.parametrize('key,value', [('path', '../SC4001E0-PSG.edf'),
    ('path', '/SC4001E0-PSG.edf'), ('role', 'image'), ('subject', True),
    ('recording', 2), ('size_bytes', 1), ('sha256', 'a' * 63),
    ('sha256', 'Z' * 64), ('transport_url', 'https://example.com/file'),
    ('url', 'http://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/SC4001E0-PSG.edf')])
def test_bad_manifest_record(key, value):
    manifest, _ = stage.read_manifest()
    manifest['files'][0][key] = value
    with pytest.raises(ValueError):
        stage.validate_manifest(manifest)


def test_manifest_bytes_cannot_be_reformatted(tmp_path):
    manifest, _ = stage.read_manifest()
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Whole source manifest'):
        stage.read_manifest(path)


@pytest.fixture
def tiny(tmp_path, monkeypatch):
    src = tmp_path / 'original'
    src.mkdir()
    files = []
    for name, body in [('a.edf', b'abc'), ('b.edf', b'defg')]:
        (src / name).write_bytes(body)
        files.append(dict(path=name, size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                          transport_url='https://physionet-open.s3.amazonaws.com/'+name))
    manifest = {'files': files}
    raw = json.dumps(manifest).encode()
    original_reader = stage.read_manifest

    def reader(path=stage.MANIFEST_PATH):
        if Path(path) != stage.MANIFEST_PATH:
            stage.reject_symlinks(path)
            if Path(path).read_bytes() != raw:
                raise ValueError('tiny manifest mismatch')
        return deepcopy(manifest), raw

    monkeypatch.setattr(stage, 'read_manifest', reader)
    return src, tmp_path / 'staged', manifest, raw


def test_offline_stage_then_reverify_without_writes(tiny):
    src, dst, manifest, raw = tiny
    before = {p.name: p.stat().st_mtime_ns for p in src.iterdir()}
    assert stage.stage_data(dst, src) == manifest
    assert stage.verify_staged(dst) == manifest
    assert sorted(p.name for p in dst.iterdir()) == ['a.edf', 'b.edf', 'source_manifest.json']
    assert dst.stat().st_mode & 0o777 == 0o755
    assert all(p.stat().st_mode & 0o777 == 0o444 for p in dst.iterdir())
    modified = {p.name: p.stat().st_mtime_ns for p in dst.iterdir()}
    stage.stage_data(dst)
    assert modified == {p.name: p.stat().st_mtime_ns for p in dst.iterdir()}
    assert before == {p.name: p.stat().st_mtime_ns for p in src.iterdir()}


@pytest.mark.parametrize('mutation', ['wrong_size', 'wrong_hash', 'missing', 'extra', 'directory', 'symlink'])
def test_invalid_original_preserved(tiny, mutation):
    src, dst, _, _ = tiny
    target = src / 'a.edf'
    if mutation == 'wrong_size':
        target.write_bytes(b'a')
    elif mutation == 'wrong_hash':
        target.write_bytes(b'xyz')
    elif mutation == 'missing':
        target.unlink()
    elif mutation == 'extra':
        (src / 'extra.txt').write_text('retain')
    elif mutation == 'directory':
        (src / 'empty').mkdir()
    else:
        target.unlink()
        target.symlink_to(src / 'b.edf')
    before = sorted(p.name for p in src.iterdir())
    with pytest.raises(ValueError):
        stage.stage_data(dst, src)
    assert not dst.exists()
    assert before == sorted(p.name for p in src.iterdir())


def test_conflicting_existing_destination_preserved(tiny):
    src, dst, _, _ = tiny
    dst.mkdir()
    (dst / 'evidence.txt').write_text('must remain')
    with pytest.raises((ValueError, FileNotFoundError)):
        stage.stage_data(dst, src)
    assert (dst / 'evidence.txt').read_text() == 'must remain'


@pytest.mark.parametrize('case', ['same', 'inside', 'ancestor'])
def test_nested_directories_rejected(tiny, case):
    src, dst, _, _ = tiny
    a, b = {'same': (src, src), 'inside': (src, src / 'child'), 'ancestor': (src, src.parent)}[case]
    with pytest.raises(ValueError):
        stage.disjoint(a, b)


def test_symlink_ancestor_rejected(tiny):
    src, dst, _, _ = tiny
    link = src.parent / 'linked'
    link.symlink_to(src, target_is_directory=True)
    with pytest.raises(ValueError):
        stage.stage_data(link / 'destination', src)
    with pytest.raises(ValueError):
        stage.verify_file(link / 'a.edf', {'path': 'a.edf', 'size_bytes': 3})


def test_legacy_manifest_not_silently_trusted(tiny):
    src, dst, manifest, raw = tiny
    (src / 'data_manifest.json').write_bytes(raw)
    with pytest.raises(ValueError, match='Legacy'):
        stage.stage_data(dst, src)
    assert not dst.exists()


def test_download_ledger_cannot_overwrite_existing(tiny):
    _, dst, _, _ = tiny
    ledger = dst.parent / 'ledger'
    ledger.mkdir()
    (ledger / 'old.json').write_text('history')
    with pytest.raises(FileExistsError):
        stage.stage_data(dst, ledger=ledger)
    assert (ledger / 'old.json').read_text() == 'history'


class Response(io.BytesIO):
    def __init__(self, body, record, *, status=200, length=None, encoding='identity', url=None):
        super().__init__(body)
        self.status = status
        self.url = url or record['transport_url']
        self.headers = {'Content-Length': str(record['size_bytes'] if length is None else length),
                        'Content-Encoding': encoding, 'Set-Cookie': 'secret-not-for-receipts'}

    def geturl(self):
        return self.url


@pytest.mark.parametrize('kind', ['pass', 'status', 'size_header', 'encoding', 'url',
                                 'short', 'excess', 'hash', 'cap', 'timeout'])
def test_bounded_mock_transport(tiny, monkeypatch, kind):
    src, dst, manifest, _ = tiny
    dst.mkdir()
    record = manifest['files'][0]
    options, body = {}, b'abc'
    if kind == 'status': options['status'] = 206
    if kind == 'size_header': options['length'] = 4
    if kind == 'encoding': options['encoding'] = 'gzip'
    if kind == 'url': options['url'] = 'https://example.com/other'
    if kind == 'short': body = b'ab'
    if kind == 'excess': body = b'abcd'
    if kind == 'hash': body = b'xyz'
    if kind == 'cap': monkeypatch.setattr(stage, 'CAP_BYTES', 2)
    if kind == 'timeout': monkeypatch.setattr(stage, 'TIMEOUT_SECONDS', 0)
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            return Response(body, record, **options)
    monkeypatch.setattr(stage.urllib.request, 'build_opener', lambda *args: Opener())
    monkeypatch.setattr(stage, 'N_FILES', 1)
    ledger = dst.parent / 'download-ledger'
    if kind == 'pass':
        stage.download_sources({'files': [record]}, dst, ledger)
        assert (dst / 'a.edf').read_bytes() == b'abc'
    else:
        with pytest.raises(ValueError):
            stage.download_sources({'files': [record]}, dst, ledger)
        assert not (dst / 'a.edf').exists()
    assert len(calls) <= 1
    result = json.loads((ledger / 'result.json').read_text())
    assert result['status'] == ('verified_all_originals' if kind == 'pass' else 'failed_preserved')
    assert 'secret-not-for-receipts' not in (ledger / 'a.edf.json').read_text()


def test_redirects_forbidden():
    with pytest.raises(ValueError):
        stage.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other/')
