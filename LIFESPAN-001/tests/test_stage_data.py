"""Manufactured bytes only: no original source mount, network, or arrays."""
from email.message import Message
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import stat
import threading

import pytest

SPEC = importlib.util.spec_from_file_location('lifespan_stage', Path(__file__).parents[1] / 'environment' / 'stage_data.py')
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


@pytest.fixture
def tiny(tmp_path, monkeypatch):
    source = tmp_path / 'originals'
    source.mkdir()
    rows, blobs = [], [b'left-original', b'right-original', b'phenotype', b'annotation']
    roles = ['surface_timeseries', 'surface_timeseries', 'phenotype', 'surface_annotation']
    for index, (blob, role) in enumerate(zip(blobs, roles)):
        name = f'file{index}.bin'
        row = dict(path=f'{s.ROLE_DIR[role]}/{name}', role=role, original_filename=name,
                   nitrc_file_id=8000 + index, size_bytes=len(blob),
                   sha256=hashlib.sha256(blob).hexdigest(), md5=hashlib.md5(blob).hexdigest())
        row['url'] = f'https://www.nitrc.org/frs/download.php/{row["nitrc_file_id"]}/{name}'
        (source / row['path']).parent.mkdir(exist_ok=True)
        (source / row['path']).write_bytes(blob)
        rows.append(row)
    manifest = {'files': rows, 'n_original_files': len(rows), 'total_original_bytes': sum(map(len, blobs))}
    raw = json.dumps(manifest).encode()
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_bytes(raw)
    monkeypatch.setattr(s, 'MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(s, 'EXPECTED_COUNT', len(rows))
    monkeypatch.setattr(s, 'EXPECTED_BYTES', sum(map(len, blobs)))
    monkeypatch.setattr(s.urllib.request, 'build_opener', lambda *a: pytest.fail('unexpected_network'))
    return source, manifest_path, manifest, blobs


class Response(io.BytesIO):
    def __init__(self, row, blob):
        super().__init__(blob)
        self.row, self.status, self.headers = row, 200, Message()
        self.headers['Content-Length'] = str(row['size_bytes'])
        self.headers['Content-Type'] = 'application/force-download'
        self.headers['Set-Cookie'] = 'secret=never-record'
        self.read1_calls = 0

    def geturl(self):
        return self.row['url']

    def read1(self, n):
        self.read1_calls += 1
        return io.BytesIO.read(self, n)

    def read(self, *args):
        raise AssertionError('must use bounded read1')


class Opener:
    def __init__(self, response):
        self.response, self.calls = response, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


def download_fixture(tmp_path, tiny):
    _, _, manifest, blobs = tiny
    row = manifest['files'][0]
    evidence, pending = tmp_path / 'evidence', tmp_path / 'pending'
    evidence.mkdir(); pending.mkdir(); (pending / 'surface').mkdir()
    state = s.State(evidence)
    return row, blobs[0], evidence, pending, state


def test_local_all_bytes_exact_and_offline_verify(tmp_path, tiny):
    source, manifest_path, manifest, blobs = tiny
    destination = tmp_path / 'staged'
    result = s.stage(destination, manifest_path, source)
    assert result['status'] == 'ok' and result['received_bytes'] == 0
    assert s.verify_staged(destination) == manifest
    for row, blob in zip(manifest['files'], blobs):
        p = destination / row['path']
        assert p.read_bytes() == blob and stat.S_IMODE(p.stat().st_mode) == 0o444
        assert stat.S_IMODE(p.parent.stat().st_mode) == 0o755
    assert set(x.relative_to(destination).as_posix() for x in destination.rglob('*') if x.is_file()) == {
        *[r['path'] for r in manifest['files']], s.MANIFEST_NAME}


def test_local_bundle_may_have_same_pinned_manifest(tmp_path, tiny):
    source, path, _, _ = tiny
    (source / s.MANIFEST_NAME).write_bytes(path.read_bytes())
    s.stage(tmp_path / 'staged', path, source)


@pytest.mark.parametrize('mutation', ['wrong_sha', 'wrong_md5', 'truncate', 'extra_file', 'extra_dir', 'missing', 'symlink'])
def test_local_preflight_before_any_copy(tmp_path, tiny, mutation):
    source, path, manifest, _ = tiny
    member = source / manifest['files'][-1]['path']
    if mutation in ('wrong_sha', 'wrong_md5'):
        member.write_bytes(b'X' * member.stat().st_size)
    elif mutation == 'truncate':
        member.write_bytes(b'x')
    elif mutation == 'extra_file':
        (source / 'extra').write_bytes(b'x')
    elif mutation == 'extra_dir':
        (source / 'empty_extra').mkdir()
    elif mutation == 'missing':
        member.unlink()
    else:
        member.unlink(); member.symlink_to(path)
    with pytest.raises(ValueError):
        s.stage(tmp_path / 'staged', path, source)
    assert not (tmp_path / 'staged').exists()
    assert not list(tmp_path.glob('staged.partial-*'))
    report = json.loads((tmp_path / 'staged.staging-evidence/result.json').read_text())
    assert report['status'] == 'failed_preserved' and report['preserved_partial'] is None


@pytest.mark.parametrize('which', ['destination', 'evidence'])
def test_existing_empty_evidence_or_destination_refused(tmp_path, tiny, which):
    source, path, _, _ = tiny
    protected = tmp_path / ('staged' if which == 'destination' else 'staged.staging-evidence')
    protected.mkdir()
    with pytest.raises(ValueError, match='existing_'):
        s.stage(tmp_path / 'staged', path, source)
    assert list(protected.iterdir()) == []


@pytest.mark.parametrize('where', ['inside_source', 'source_itself', 'above_source', 'contains_manifest'])
def test_overlap_refused_without_creating_directories(tmp_path, tiny, where):
    source, path, _, _ = tiny
    destination = {'inside_source': source / 'new/child', 'source_itself': source,
                   'above_source': tmp_path, 'contains_manifest': path.parent}[where]
    before = sorted(str(x) for x in tmp_path.rglob('*'))
    with pytest.raises(ValueError):
        s.stage(destination, path, source)
    assert sorted(str(x) for x in tmp_path.rglob('*')) == before


@pytest.mark.parametrize('value', ['relative/path', '/tmp/../dest', '/tmp/./dest', '/tmp/nul\x00x'])
def test_path_rejects_ambiguous_literals(value):
    with pytest.raises(ValueError):
        s.safe_path(value)


@pytest.mark.parametrize('dangling', [False, True])
def test_symlink_ancestor_refused_even_with_dotdot(tmp_path, dangling):
    target = tmp_path / 'target'
    if not dangling:
        target.mkdir()
    link = tmp_path / 'link'; link.symlink_to(target)
    for path in (str(link / 'dest'), str(link) + '/../dest'):
        with pytest.raises(ValueError):
            s.safe_path(path)


@pytest.mark.parametrize('name', ['/absolute', '../up', 'a/../b', 'a//b', 'a/./b', 'a\\b', ''])
def test_manifest_path_validation(name):
    with pytest.raises(ValueError):
        s.relative(name)


@pytest.mark.parametrize('change', ['http:', 'evilhost', '?query=1', '#fragment', ':443', 'wrong_id', 'userinfo'])
def test_exact_url_only(tiny, change):
    row = dict(tiny[2]['files'][0])
    if change == 'http:':
        row['url'] = row['url'].replace('https:', 'http:')
    elif change == 'evilhost':
        row['url'] = row['url'].replace('www.nitrc.org', 'example.org')
    elif change == ':443':
        row['url'] = row['url'].replace('www.nitrc.org', 'www.nitrc.org:443')
    elif change == 'wrong_id':
        row['nitrc_file_id'] += 1
    elif change == 'userinfo':
        row['url'] = row['url'].replace('https://', 'https://user:pass@')
    else:
        row['url'] += change
    with pytest.raises(ValueError):
        s.endpoint(row)


def test_manifest_pin_not_self_describing(tmp_path, tiny):
    path = tiny[1]
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='manifest_sha256'):
        s.load_manifest(path)


def test_atomic_noreplace(tmp_path):
    pending, target = tmp_path / 'pending', tmp_path / 'target'
    pending.mkdir(); target.mkdir(); (target / 'keep').write_bytes(b'keep')
    with pytest.raises(OSError):
        s.publish_directory(pending, target)
    assert pending.exists() and (target / 'keep').read_bytes() == b'keep'


def test_download_good_uses_read1_and_no_secrets(tmp_path, tiny):
    row, blob, evidence, pending, state = download_fixture(tmp_path, tiny)
    response = Response(row, blob); opener = Opener(response)
    s.download_one(row, pending, state, opener)
    assert (pending / row['path']).read_bytes() == blob and response.read1_calls == 2
    assert len(opener.calls) == 1 and opener.calls[0][1] == 30
    text = (evidence / f'object_{row["nitrc_file_id"]}.json').read_text()
    assert 'secret' not in text and 'Set-Cookie' not in text
    assert json.loads(text)['status'] == 'verified'


@pytest.mark.parametrize('mutation', ['status', 'redirect_url', 'missing_length', 'double_length', 'wrong_length',
                                   'missing_type', 'double_type', 'html', 'gzip', 'double_encoding', 'chunked'])
def test_bad_headers_stop_without_body(tmp_path, tiny, mutation):
    row, blob, evidence, pending, state = download_fixture(tmp_path, tiny)
    response = Response(row, blob)
    if mutation == 'status': response.status = 206
    elif mutation == 'redirect_url': response.geturl = lambda: 'https://example.org/file'
    elif mutation == 'missing_length': del response.headers['Content-Length']
    elif mutation == 'double_length': response.headers['Content-Length'] = str(len(blob))
    elif mutation == 'wrong_length': response.headers.replace_header('Content-Length', '999')
    elif mutation == 'missing_type': del response.headers['Content-Type']
    elif mutation == 'double_type': response.headers['Content-Type'] = 'application/force-download'
    elif mutation == 'html': response.headers.replace_header('Content-Type', 'text/html')
    elif mutation == 'gzip': response.headers['Content-Encoding'] = 'gzip'
    elif mutation == 'double_encoding':
        response.headers['Content-Encoding'] = 'identity'; response.headers['Content-Encoding'] = 'identity'
    else: response.headers['Transfer-Encoding'] = 'chunked'
    opener = Opener(response)
    with pytest.raises(ValueError):
        s.download_one(row, pending, state, opener)
    assert response.read1_calls == 0 and len(opener.calls) == 1 and state.stop.is_set()
    assert not (pending / row['path']).exists()
    assert (pending / (row['path'] + '.partial')).exists()


@pytest.mark.parametrize('blob', [b'', b'x', b'X' * 13, b'too-many-source-bytes'])
def test_bad_bodies_preserved_never_published(tmp_path, tiny, blob):
    row, _, evidence, pending, state = download_fixture(tmp_path, tiny)
    with pytest.raises(ValueError):
        s.download_one(row, pending, state, Opener(Response(row, blob)))
    assert not (pending / row['path']).exists()
    assert (pending / (row['path'] + '.partial')).exists()
    assert json.loads((evidence / f'object_{row["nitrc_file_id"]}.json').read_text())['status'] == 'failed_preserved'


def test_budget_reservation_released(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'MAX_BYTES', 5)
    state = s.State(tmp_path)
    class Reader:
        def read1(self, n):
            assert state.reserved == n == 5
            return b'12345'
    assert state.read(Reader(), 100) == b'12345'
    assert state.reserved == 0 and state.received == 5
    with pytest.raises(ValueError, match='payload_cap'):
        state.read(Reader(), 1)


def test_failed_read_releases_reservation(tmp_path):
    state = s.State(tmp_path)
    class Reader:
        def read1(self, n): raise TimeoutError('manufactured')
    with pytest.raises(TimeoutError): s.State.read(state, Reader(), 10)
    assert state.reserved == 0 and state.received == 0


def test_deadline_stops_new_reads(tmp_path, monkeypatch):
    state = s.State(tmp_path)
    monkeypatch.setattr(state, 'remaining', lambda: 31)
    with pytest.raises(ValueError, match='deadline_reserve'): state.check(network=True)
    monkeypatch.setattr(state, 'remaining', lambda: 0)
    with pytest.raises(ValueError, match='total_wall'): state.check()


def test_peer_failure_stops_new_schedule(tmp_path):
    state = s.State(tmp_path); calls = []
    def operation(row):
        calls.append(row)
        state.stop.set()
        raise ValueError('first failure')
    with pytest.raises(ValueError): s.parallel_download(list(range(20)), operation, state)
    assert 1 <= len(calls) <= 2


@pytest.mark.parametrize('code', [301, 302, 303, 307, 308])
def test_redirect_rejected_and_closed(code):
    fp = io.BytesIO(b'do-not-read')
    headers = Message(); headers['Location'] = 'https://user:password@evil.example/file?token=SECRET'
    method = getattr(s.NoRedirect(), f'http_error_{code}')
    with pytest.raises(ValueError) as error: method(None, fp, code, '', headers)
    assert fp.closed and 'password' not in str(error.value) and 'SECRET' not in str(error.value)


def test_verify_only_cli_no_writes(tmp_path, tiny, monkeypatch):
    source, path, _, _ = tiny
    destination = tmp_path / 'staged'; s.stage(destination, path, source)
    before = {str(p): (p.stat().st_mtime_ns, p.stat().st_mode) for p in destination.rglob('*')}
    assert s.main(['--verify-existing', '--destination', str(destination)]) == 0
    assert before == {str(p): (p.stat().st_mtime_ns, p.stat().st_mode) for p in destination.rglob('*')}


def test_verify_failure_creates_nothing(tmp_path):
    missing = tmp_path / 'absent'
    assert s.main(['--verify-existing', '--destination', str(missing)]) == 1
    assert not missing.exists() and not (tmp_path / 'absent.staging-evidence').exists()


@pytest.mark.parametrize('option', ['--manifest', '--source-root'])
def test_verify_rejects_conflicting_options(tmp_path, option):
    assert s.main(['--verify-existing', option, str(tmp_path)]) == 1


def test_timer_restored():
    old = signal.getsignal(signal.SIGALRM)
    with s.hard_timeout(): assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert signal.getsignal(signal.SIGALRM) == old


def test_local_authenticates_every_file_before_first_copy(tmp_path, tiny, monkeypatch):
    source, path, manifest, _ = tiny
    original, calls = s.checked_stream, []
    def checking(member, row, state=None, target=None):
        calls.append((row['path'], target is not None))
        if target is not None:
            assert len([x for x in calls if not x[1]]) == len(manifest['files'])
        return original(member, row, state, target)
    monkeypatch.setattr(s, 'checked_stream', checking)
    s.stage(tmp_path / 'staged', path, source)
    assert len(calls) == 2 * len(manifest['files'])


def test_source_change_between_authentication_and_copy_preserved(tmp_path, tiny, monkeypatch):
    source, path, manifest, _ = tiny
    original = s.checked_stream
    def checking(member, row, state=None, target=None):
        if target is not None:
            member.write_bytes(b'X' * row['size_bytes'])
        return original(member, row, state, target)
    monkeypatch.setattr(s, 'checked_stream', checking)
    with pytest.raises(ValueError, match='sha256_or_md5'):
        s.stage(tmp_path / 'staged', path, source)
    assert not (tmp_path / 'staged').exists()
    assert len(list(tmp_path.glob('staged.partial-*'))) == 1


def test_fake_network_whole_bundle_no_real_requests(tmp_path, tiny, monkeypatch):
    _, path, manifest, blobs = tiny
    by_url = {row['url']: (row, blob) for row, blob in zip(manifest['files'], blobs)}
    class Factory:
        def open(self, request, timeout):
            row, blob = by_url[request.full_url]
            return Response(row, blob)
    monkeypatch.setattr(s.urllib.request, 'build_opener', lambda *a: Factory())
    destination = tmp_path / 'staged'
    result = s.stage(destination, path)
    assert result['received_bytes'] == manifest['total_original_bytes']
    assert s.verify_staged(destination) == manifest
    assert len(list((tmp_path / 'staged.staging-evidence').glob('object_*.json'))) == len(blobs)


@pytest.mark.parametrize('which', ['manifest', 'root', 'member', 'extra_directory', 'extra_file'])
def test_verify_closed_inventory_and_links(tmp_path, tiny, which):
    source, path, manifest, _ = tiny
    destination = tmp_path / 'staged'; s.stage(destination, path, source)
    if which == 'manifest':
        member = destination / s.MANIFEST_NAME; member.unlink(); member.symlink_to(path)
    elif which == 'root':
        link = tmp_path / 'root_link'; link.symlink_to(destination); destination = link
    elif which == 'member':
        member = destination / manifest['files'][0]['path']; member.unlink(); member.symlink_to(path)
    elif which == 'extra_directory': (destination / 'unexpected').mkdir()
    else: (destination / 'unexpected').write_bytes(b'x')
    with pytest.raises(ValueError): s.verify_staged(destination)


def test_small_umask_does_not_make_source_unreadable(tmp_path, tiny):
    source, path, _, _ = tiny
    old = os.umask(0o077)
    try: s.stage(tmp_path / 'staged', path, source)
    finally: os.umask(old)
    for p in (tmp_path / 'staged').rglob('*'):
        assert stat.S_IMODE(p.stat().st_mode) == (0o755 if p.is_dir() else 0o444)
