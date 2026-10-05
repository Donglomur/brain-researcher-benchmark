"""Manufactured bytes only: no release data, network, FIF parsing or EEG."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import signal
import tarfile
import time
import types
import urllib.request

import pytest

spec = importlib.util.spec_from_file_location('stage_draft', Path(__file__).parents[1] / 'environment' / 'stage_data.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def tar_bytes(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for name, kind, payload in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(payload) if kind in (tarfile.REGTYPE, tarfile.AREGTYPE) else 0
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                info.linkname = 'elsewhere'
            archive.addfile(info, io.BytesIO(payload) if info.size else None)
    return gzip.compress(stream.getvalue(), mtime=0)


@pytest.fixture
def toy(tmp_path, monkeypatch):
    names = sorted(s.FILENAMES)
    roles = {'README.txt': 'readme', 'version.txt': 'version', names[0]: 'raw_fif'}
    payloads = {name: ('manufactured ' + name).encode() for name in names}
    entries = [('MNE-ERP-CORE-data', tarfile.DIRTYPE, b'')]
    files = []
    for name in names:
        member = 'MNE-ERP-CORE-data/' + name
        entries.append((member, tarfile.REGTYPE, payloads[name]))
        files.append(dict(path=name, archive_member=member, role=roles[name],
                          size_bytes=len(payloads[name]), sha256=hashlib.sha256(payloads[name]).hexdigest()))
    body = tar_bytes(entries)
    manifest = dict(files=files, archive=dict(filename='MNE-ERP-CORE-data.tar.gz',
        url='https://osf.io/download/rzgba?version=1', size_bytes=len(body),
        md5=hashlib.md5(body).hexdigest(), sha256=hashlib.sha256(body).hexdigest()))
    raw = json.dumps(manifest).encode()
    manifest_path = tmp_path / 'input_manifest.json'
    manifest_path.write_bytes(raw)
    archive_path = tmp_path / 'original.tar.gz'
    archive_path.write_bytes(body)
    monkeypatch.setattr(s, 'MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
    return types.SimpleNamespace(manifest=manifest, raw=raw, manifest_path=manifest_path,
        archive=archive_path, body=body, entries=entries, payloads=payloads, destination=tmp_path / 'out')


class Response(io.BytesIO):
    def __init__(self, body, size=None, status=200, extra=None):
        super().__init__(body)
        self.status = status
        self.headers = {'Content-Length': str(len(body) if size is None else size)}
        self.headers.update(extra or {})
    def geturl(self):
        return 'https://osf.io/download/rzgba?version=1'


class Opener:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, 0
    def open(self, request, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


def test_verified_local_stage_and_exact_bytes(toy, monkeypatch):
    monkeypatch.setattr(s, 'download_archive', lambda *args: pytest.fail('local reuse must stay offline'))
    result = s.stage(toy.destination, toy.manifest_path, toy.archive)
    assert result['status'] == 'verified_staged' and not result['network_used']
    assert result['member_count'] == 4 and toy.archive.read_bytes() == toy.body
    assert (toy.destination / 'source_manifest.json').read_bytes() == toy.raw
    assert {p.name for p in toy.destination.iterdir()} == s.FILENAMES | {'source_manifest.json'}
    for name, data in toy.payloads.items():
        assert (toy.destination / name).read_bytes() == data
        assert (toy.destination / name).stat().st_mode & 0o777 == 0o444
    assert toy.destination.stat().st_mode & 0o777 == 0o755


def test_existing_verified_reuse_does_not_open_network(toy, monkeypatch):
    s.stage(toy.destination, toy.manifest_path, toy.archive)
    monkeypatch.setattr(s, 'download_archive', lambda *args: pytest.fail('no download'))
    result = s.stage(toy.destination, toy.manifest_path)
    assert result['status'] == 'verified_existing' and not result['network_used']


def test_verify_cli_offline_no_writes(toy, monkeypatch, capsys):
    s.stage(toy.destination, toy.manifest_path, toy.archive)
    before = {p.name: p.read_bytes() for p in toy.destination.iterdir()}
    monkeypatch.setattr(urllib.request, 'build_opener', lambda *args: pytest.fail('no network'))
    assert s.main(['--verify-existing', '--destination', str(toy.destination)]) == 0
    assert 'verified_existing' in capsys.readouterr().out
    assert before == {p.name: p.read_bytes() for p in toy.destination.iterdir()}


@pytest.mark.parametrize('change', ['member', 'extra', 'missing', 'manifest', 'directory', 'symlink'])
def test_staged_corruptions_rejected(toy, change):
    s.stage(toy.destination, toy.manifest_path, toy.archive)
    target = toy.destination / 'README.txt'
    if change == 'member':
        target.chmod(0o644)
        target.write_bytes(b'bad')
    elif change == 'extra':
        (toy.destination / 'extra').write_text('untrusted')
    elif change == 'manifest':
        target = toy.destination / 'source_manifest.json'
        target.chmod(0o644)
        target.write_bytes(toy.raw + b' ')
    else:
        target.unlink()
        if change == 'directory':
            target.mkdir()
        if change == 'symlink':
            target.symlink_to(toy.archive)
    with pytest.raises(ValueError):
        s.verify_staged(toy.destination)


def test_preserve_existing_conflicting_destination(toy):
    toy.destination.mkdir()
    (toy.destination / 'keep').write_text('existing evidence')
    with pytest.raises(ValueError):
        s.stage(toy.destination, toy.manifest_path, toy.archive)
    assert (toy.destination / 'keep').read_text() == 'existing evidence'
    assert not (toy.destination.parent / '.out-source-staging').exists()


@pytest.mark.parametrize('which', ['manifest', 'archive', 'destination', 'ancestor'])
def test_symlinks_refused(toy, tmp_path, which):
    manifest, archive, destination = toy.manifest_path, toy.archive, toy.destination
    link = tmp_path / 'link'
    if which == 'manifest':
        link.symlink_to(manifest)
        manifest = link
    elif which == 'archive':
        link.symlink_to(archive)
        archive = link
    elif which == 'destination':
        link.symlink_to(destination)
        destination = link
    else:
        link.symlink_to(tmp_path, target_is_directory=True)
        destination = link / 'elsewhere'
    with pytest.raises(ValueError, match='Symlink'):
        s.stage(destination, manifest, archive)


def test_preserve_existing_work_receipts(toy):
    work = toy.destination.parent / '.out-source-staging'
    work.mkdir()
    (work / 'result.json').write_text('prior failure')
    with pytest.raises(ValueError, match='Preserve'):
        s.stage(toy.destination, toy.manifest_path, toy.archive)
    assert (work / 'result.json').read_text() == 'prior failure'


def test_archive_hash_failure_before_extract(toy, monkeypatch):
    toy.archive.write_bytes(b'x' * len(toy.body))
    monkeypatch.setattr(s, 'copy_members', lambda *args: pytest.fail('unverified archive must not parse'))
    with pytest.raises(ValueError, match='digest'):
        s.stage(toy.destination, toy.manifest_path, toy.archive)
    assert not toy.destination.exists()
    receipt = json.loads((toy.destination.parent / '.out-source-staging/result.json').read_text())
    assert receipt['status'] == 'failed_preserved'


def test_manufactured_download_success(toy):
    opener = Opener(Response(toy.body))
    result = s.stage(toy.destination, toy.manifest_path, opener=opener)
    assert opener.calls == 1 and result['received_bytes'] == len(toy.body)
    assert result['status'] == 'verified_staged'


@pytest.mark.parametrize('failure', ['short', 'oversized', 'hash', 'http', 'length', 'encoding', 'transport'])
def test_one_attempt_preserves_partial_on_failure(toy, failure):
    body = toy.body[:-1] if failure == 'short' else toy.body + b'x' if failure == 'oversized' else toy.body
    if failure == 'hash':
        body = b'x' * len(toy.body)
    response = Response(body, size=len(toy.body) + (failure == 'length'),
        status=503 if failure == 'http' else 200, extra={'Content-Encoding': 'gzip'} if failure == 'encoding' else None)
    opener = Opener(response, OSError('https://files.osf.io/path?token=SECRET') if failure == 'transport' else None)
    with pytest.raises((ValueError, OSError)):
        s.stage(toy.destination, toy.manifest_path, opener=opener)
    work = toy.destination.parent / '.out-source-staging'
    assert opener.calls == 1 and not toy.destination.exists()
    assert (work / 'MNE-ERP-CORE-data.tar.gz.partial').exists()
    assert 'SECRET' not in (work / 'result.json').read_text()


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE, tarfile.GNUTYPE_SPARSE])
def test_nonregular_archive_members(toy, kind, tmp_path):
    entries = list(toy.entries)
    entries[1] = (entries[1][0], kind, b'')
    toy.archive.write_bytes(tar_bytes(entries))
    target = tmp_path / 'members'
    target.mkdir()
    with pytest.raises((ValueError, tarfile.TarError)):
        s.copy_members(toy.archive, target, toy.manifest)


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'duplicate', 'absolute', 'traversal', 'backslash', 'root_file', 'size', 'member_sha'])
def test_archive_inventory_and_member_identity(toy, mutation, tmp_path):
    entries = list(toy.entries)
    if mutation == 'missing':
        entries.pop()
    elif mutation == 'extra':
        entries.append(('MNE-ERP-CORE-data/extra', tarfile.REGTYPE, b'x'))
    elif mutation == 'duplicate':
        entries.append(entries[1])
    elif mutation == 'root_file':
        entries[0] = (entries[0][0], tarfile.REGTYPE, b'')
    elif mutation in ('absolute', 'traversal', 'backslash'):
        names = {'absolute': '/bad', 'traversal': 'MNE-ERP-CORE-data/../bad', 'backslash': 'root\\bad'}
        entries[1] = (names[mutation], tarfile.REGTYPE, entries[1][2])
    elif mutation == 'size':
        entries[1] = (*entries[1][:2], entries[1][2] + b'x')
    else:
        entries[1] = (*entries[1][:2], b'x' * len(entries[1][2]))
    toy.archive.write_bytes(tar_bytes(entries))
    target = tmp_path / 'members'
    target.mkdir()
    with pytest.raises(ValueError):
        s.copy_members(toy.archive, target, toy.manifest)


@pytest.mark.parametrize('failure', ['crc', 'trailing', 'expanded', 'member_cap'])
def test_gzip_and_expansion_limits(toy, failure, tmp_path, monkeypatch):
    if failure == 'crc':
        data = bytearray(toy.body)
        data[-8] ^= 1
        toy.archive.write_bytes(data)
    elif failure == 'trailing':
        toy.archive.write_bytes(gzip.compress(gzip.decompress(toy.body) + b'not zero'))
    elif failure == 'expanded':
        monkeypatch.setattr(s, 'EXPANDED_CAP', 1000)
    else:
        monkeypatch.setattr(s, 'MEMBER_CAP', 3)
    target = tmp_path / 'members'
    target.mkdir()
    with pytest.raises((ValueError, OSError, EOFError, tarfile.TarError)):
        s.copy_members(toy.archive, target, toy.manifest)


@pytest.mark.parametrize('url', [
    'http://osf.io/download/rzgba?version=1',
    'https://osf.io/download/rzgba?version=2',
    'https://files.osf.io/other',
    'https://storage.googleapis.com/other/' + s.ARCHIVE_SHA256,
    'https://storage.googleapis.com/cos-osf-prod-files-us-east1/' + '0' * 64,
    'https://storage.googleapis.com.evil.test/cos-osf-prod-files-us-east1/' + s.ARCHIVE_SHA256,
    'https://user:secret@osf.io/download/rzgba?version=1',
    'https://osf.io:444/download/rzgba?version=1',
    'https://osf.io/download/rzgba?version=1#fragment'])
def test_foreign_redirects_refused(url):
    with pytest.raises(ValueError):
        s.allowed_url(url)


def test_exact_gcs_signed_query_and_rejected_candidate_redaction():
    target = 'https://storage.googleapis.com/cos-osf-prod-files-us-east1/' + s.ARCHIVE_SHA256 + '?token=SECRET'
    assert s.allowed_url(target) == target
    ledger = []
    handler = s.SourceRedirect(ledger, time.monotonic())
    request = urllib.request.Request('https://osf.io/download/rzgba?version=1')
    handler.redirect_request(request, None, 302, 'Found', {}, target)
    assert ledger[0]['allowed'] is True and 'SECRET' not in json.dumps(ledger)
    with pytest.raises(ValueError):
        handler.redirect_request(request, None, 302, 'Found', {}, 'https://evil.test/object?token=SECRET')
    assert ledger[-1]['allowed'] is False and 'SECRET' not in json.dumps(ledger)


def test_redirect_response_body_not_read():
    handler = s.SourceRedirect([], time.monotonic())
    body = types.SimpleNamespace(close=lambda: None, read=lambda: pytest.fail('no redirect body reads'))
    result = object()
    handler.parent = types.SimpleNamespace(open=lambda req, timeout: result)
    request = urllib.request.Request('https://osf.io/download/rzgba?version=1')
    assert handler.http_error_302(request, body, 302, 'Found', {'Location': request.full_url}) is result


def test_hard_deadline_restores_handler():
    previous = signal.getsignal(signal.SIGALRM)
    with pytest.raises(TimeoutError):
        with s.total_timeout(.01):
            time.sleep(.1)
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_draft_has_no_host_cache_paths():
    text = Path(s.__file__).read_text()
    assert '/home/' not in text and 'OWNED_ROOT' not in text


def test_default_portable_paths_without_execution(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(s, 'stage', lambda *args: calls.append(args) or {'status': 'manufactured'})
    assert s.main([]) == 0
    assert calls[0][0] == Path('/app/data/errmon')
    assert calls[0][1].name == 'source_manifest.json' and calls[0][2] is None
