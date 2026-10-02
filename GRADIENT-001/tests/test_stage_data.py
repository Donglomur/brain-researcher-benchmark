"""Standalone manufactured source staging tests; never original/source paths."""
import contextlib
from email.message import Message
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import time
from urllib.error import HTTPError
from urllib.request import HTTPDefaultErrorHandler, Request

import pytest

SPEC = importlib.util.spec_from_file_location('gradient_stager', Path(__file__).parents[1] / 'environment/stage_data.py')
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)
COMMIT = 'a' * 40


def digest_row(path, raw, **kwargs):
    return dict(path=path, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                md5=hashlib.md5(raw).hexdigest(), **kwargs)


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)


class Response(io.BytesIO):
    def __init__(self, body=b'payload', code=200, headers=None):
        super().__init__(body); self.code = code; self.headers = Message()
        values = headers if headers is not None else [('Content-Type', 'application/octet-stream'), ('Content-Length', str(len(body)))]
        for key, value in values: self.headers[key] = value

    def read1(self, n): return super().read(n)


def github(raw=b'payload'):
    return digest_row('source.txt', raw, role='provenance', participant_id=None,
        source_url=f'https://raw.githubusercontent.com/nilearn/nilearn/{COMMIT}/document.txt', source_commit=COMMIT)


def osf(raw=b'payload'):
    return digest_row('original.tsv', raw, role='participants', participant_id=None,
        source_guid='abcde', osf_object_id='object123', source_version=2,
        source_url='https://osf.io/download/abcde/?revision=2')


def bundle(tmp_path, monkeypatch):
    root, docs = tmp_path / 'input', tmp_path / 'docs'; root.mkdir(); docs.mkdir()
    rows, bodies = [], {}
    for r, raw in ((github(), b'payload'), (osf(), b'payload')):
        rows.append(r); bodies[r['source_url']] = raw; write(root / r['path'], raw)
    for role, name in (('atlas_image', 'atlas.nii.gz'), ('atlas_labels', 'labels.txt'), ('provenance', 'provenance/license.txt')):
        raw = b'manufactured original ' + role.encode()
        source_url = f'https://raw.githubusercontent.com/ThomasYeoLab/CBIG/{COMMIT}/' + name
        row = digest_row(name, raw, role=role, participant_id=None, source_url=source_url,
                        source_commit=COMMIT, git_blob_sha1=hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest())
        rows.append(row); bodies[source_url] = raw; write(root / name, raw)
    manifest = dict(files=rows, n_files=len(rows), total_bytes=sum(r['size_bytes'] for r in rows))
    raw = (json.dumps(manifest, sort_keys=True) + '\n').encode(); manifest_path = docs / 'source_manifest.json'; write(manifest_path, raw)
    monkeypatch.setattr(m, 'MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(m, 'EXPECTED_COUNT', len(rows)); monkeypatch.setattr(m, 'EXPECTED_BYTES', manifest['total_bytes'])
    def transport(url, timeout, etag=None):
        assert 0 < timeout <= m.SOCKET_SECONDS
        if url.startswith('https://files.osf.io/'):
            assert url == 'https://files.osf.io/v1/resources/5hju4/providers/osfstorage/object123?revision=2'
            return Response(b'', code=302, headers=[('Location', 'https://storage.googleapis.com/cos-osf-prod-files-us-east1/' + rows[1]['sha256'] + '?token=PRIVATE')])
        if url.startswith('https://storage.googleapis.com/'): return Response(b'payload')
        body = bodies[url]
        assert etag is None
        headers = [('Content-Type', 'application/octet-stream'), ('Content-Length', str(len(body)))]
        return Response(body, headers=headers)
    return root, manifest_path, manifest, transport


def test_pinned_public_acquisition_and_offline_closed_verification(tmp_path, monkeypatch, capsys):
    source, manifest_path, manifest, transport = bundle(tmp_path, monkeypatch)
    destination, work = tmp_path / 'new-parent/staged', tmp_path / 'work'
    result = m.stage(destination, work, manifest_path, transport=transport)
    assert result['status'] == 'ok' and result['transfer_starts'] == 5 and result['network_requests'] == 6
    assert result['automatic_retries'] == 0 and result['source_file_count'] == 5
    assert m.verify_staged(destination) == manifest
    assert 'PRIVATE' not in (work / 'result.json').read_text() + capsys.readouterr().out
    assert not (destination / 'source_capture').exists()
    assert all((destination / r['path']).read_bytes() == (source / r['path']).read_bytes() for r in manifest['files'])
    assert all(stat.S_IMODE((destination / r['path']).stat().st_mode) == 0o444 for r in manifest['files'])
    assert stat.S_IMODE((destination / 'provenance').stat().st_mode) == 0o755


@pytest.mark.parametrize('with_manifest', [False, True])
def test_full_local_copy_no_network_or_source_mutation(tmp_path, monkeypatch, with_manifest):
    source, manifest_path, manifest, _ = bundle(tmp_path, monkeypatch)
    if with_manifest: write(source / m.MANIFEST_NAME, manifest_path.read_bytes())
    before = {p: (p.read_bytes(), m.signature(p.stat())) for p in source.rglob('*') if p.is_file()}
    def fail(*_): pytest.fail('network access')
    result = m.stage(tmp_path / 'out', tmp_path / 'work', manifest_path, source, fail)
    assert result['status'] == 'ok' and result['network_requests'] == 0
    assert all((p.read_bytes(), m.signature(p.stat())) == saved for p, saved in before.items())
    assert m.verify_staged(tmp_path / 'out') == manifest


def test_every_local_input_verified_before_any_copy(tmp_path, monkeypatch):
    source, manifest_path, manifest, _ = bundle(tmp_path, monkeypatch)
    (source / manifest['files'][-1]['path']).write_bytes(b'bad')
    monkeypatch.setattr(m, 'copy_stream', lambda *_: pytest.fail('copy before complete auth'))
    with pytest.raises(m.Refusal): m.stage(tmp_path / 'out', tmp_path / 'work', manifest_path, source)
    assert not (tmp_path / 'out').exists()
    assert json.loads((tmp_path / 'work/result.json').read_bytes())['status'] == 'failed'


@pytest.mark.parametrize('kind', ['extra', 'directory', 'link', 'missing', 'bad_hash'])
def test_verification_rejects_closed_inventory_mutations(tmp_path, monkeypatch, kind):
    source, path, manifest, _ = bundle(tmp_path, monkeypatch)
    write(source / m.MANIFEST_NAME, path.read_bytes())
    target = source / manifest['files'][0]['path']
    if kind == 'extra': write(source / 'extra', b'x')
    elif kind == 'directory': (source / 'extra').mkdir()
    elif kind == 'link': target.unlink(); target.symlink_to(path)
    elif kind == 'missing': target.unlink()
    else: target.write_bytes(b'changed')
    with pytest.raises(m.Refusal): m.verify_staged(source)


@pytest.mark.parametrize('which', ['source', 'manifest', 'work_inside_dest', 'dest_inside_work'])
def test_disjoint_guard_precedes_mkdir(tmp_path, monkeypatch, which):
    source, manifest_path, _, _ = bundle(tmp_path, monkeypatch)
    destination, work = tmp_path / 'out', tmp_path / 'work'
    if which == 'source': destination = source / 'new/child'
    elif which == 'manifest': work = manifest_path.parent / 'work'
    elif which == 'work_inside_dest': work = destination / 'work'
    else: destination = work / 'out'
    with pytest.raises(m.Refusal, match='overlapping'): m.stage(destination, work, manifest_path, source)
    assert not destination.exists() and not work.exists()


@pytest.mark.parametrize('existing', ['out', 'work'])
def test_existing_evidence_preserved(tmp_path, monkeypatch, existing):
    source, manifest_path, _, _ = bundle(tmp_path, monkeypatch)
    (tmp_path / existing).mkdir(); write(tmp_path / existing / 'keep', b'prior')
    with pytest.raises(m.Refusal, match='fresh'): m.stage(tmp_path / 'out', tmp_path / 'work', manifest_path, source)
    assert (tmp_path / existing / 'keep').read_bytes() == b'prior'


@pytest.mark.parametrize('suffix', ['link/x', 'link/../x', '../x', './x'])
def test_symlink_and_lexical_dot_paths(tmp_path, suffix):
    (tmp_path / 'link').symlink_to(tmp_path / 'missing', target_is_directory=True)
    with pytest.raises(m.Refusal): m.safe_path(str(tmp_path) + '/' + suffix)


@pytest.mark.parametrize('path', ['', '/abs', '../a', 'a//b', 'a/./b', 'a/../b', 'a\\b', 'C:/a', 'a\0b'])
def test_relative_manifest_paths(path):
    with pytest.raises(m.Refusal): m.relative(path)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":[1e999]}'])
def test_strict_json(raw):
    with pytest.raises(m.Refusal): m.strict_json(raw)


@pytest.mark.parametrize('url', ['http://osf.io/download/abcde/?revision=2', 'https://osf.io.evil/download/abcde/?revision=2',
    'https://user:secret@osf.io/download/abcde/?revision=2', 'https://osf.io:444/download/abcde/?revision=2',
    'https://osf.io/download/abcde/?revision=1', 'https://osf.io/download/wrong/?revision=2',
    'https://files.osf.io/v1/resources/other/providers/osfstorage/object123?revision=2',
    'https://files.osf.io/v1/resources/5hju4/providers/osfstorage/object123?revision=1',
    'https://storage.googleapis.com/other-bucket/object', 'https://storage.googleapis.com/cos-osf-prod-files-us-east1/wrong',
    'https://osf.io/download/abcde/?revision=2#fragment'])
def test_closed_osf_redirect_paths(url):
    with pytest.raises(m.Refusal): m.endpoint(url, osf())


def test_storage_signed_values_redacted():
    r = osf(); url = 'https://storage.googleapis.com/cos-osf-prod-files-us-east1/' + r['sha256'] + '?token=SECRET'
    assert 'SECRET' not in json.dumps(m.endpoint(url, r))


def test_waterbutler_initial_locator_preserves_canonical_row_and_version():
    row = osf(); before = dict(row)
    assert m.transport_start(row) == 'https://files.osf.io/v1/resources/5hju4/providers/osfstorage/object123?revision=2'
    assert row == before
    for version in (1, 2):
        row = dict(osf(), source_version=version, source_url=f'https://osf.io/download/abcde/?revision={version}')
        assert m.transport_start(row).endswith(f'?revision={version}')


def test_non_osf_initial_locators_unchanged(tmp_path, monkeypatch):
    _, _, manifest, _ = bundle(tmp_path, monkeypatch)
    for row in (r for r in manifest['files'] if 'source_guid' not in r):
        assert m.transport_start(row) == row['source_url']


def test_waterbutler_signed_redirect_exact_hash_and_truthful_ledger(tmp_path, capsys):
    row = osf(); before = dict(row); calls = []; state = m.State()
    start = 'https://files.osf.io/v1/resources/5hju4/providers/osfstorage/object123?revision=2'
    signed = 'https://storage.googleapis.com/cos-osf-prod-files-us-east1/' + row['sha256'] + '?signature=PRIVATE'
    def transport(url, timeout, etag):
        calls.append(url)
        if url == start: return Response(b'UNREAD_REDIRECT_BODY', 302, [('Location', signed)])
        assert url == signed
        return Response()
    m.download(row, tmp_path / 'target', state, transport)
    assert calls == [start, signed] and row == before
    assert state.bytes == 7 and state.requests == 2 and state.starts == {row['path']}
    record = state.records[0]
    assert record['canonical_source_endpoint'] == {'host': 'osf.io', 'path': '/download/abcde/'}
    assert record['endpoint_start'] == {'host': 'files.osf.io', 'path': '/v1/resources/5hju4/providers/osfstorage/object123'}
    assert record['source_version'] == 2 and record['status'] == 'verified'
    assert 'PRIVATE' not in json.dumps(record) + capsys.readouterr().out


@pytest.mark.parametrize('case', ['timeout', 'http', 'wrong_version', 'wrong_hash', 'digest'])
def test_waterbutler_failure_has_no_initial_osf_or_unsigned_fallback(tmp_path, case):
    row = osf(); calls = []; state = m.State()
    start = m.transport_start(row)
    def transport(url, timeout, etag):
        calls.append(url)
        assert url == start  # No alternate initial locator is permitted.
        if case == 'timeout': raise TimeoutError('not logged with query credentials')
        if case == 'http': return Response(b'UNREAD', 500)
        if case == 'digest': return Response(b'PAYLOAD')
        candidate = (start.replace('revision=2', 'revision=1') if case == 'wrong_version' else
                     'https://storage.googleapis.com/cos-osf-prod-files-us-east1/' + '0' * 64 + '?secret=PRIVATE')
        return Response(b'UNREAD', 302, [('Location', candidate)])
    with pytest.raises((m.Refusal, TimeoutError)):
        m.download(row, tmp_path / 'target', state, transport)
    assert calls == [start] and state.requests == 1 and state.starts == {row['path']}
    assert state.cancelled.is_set() and state.records[0]['status'] == 'failed'
    assert not (tmp_path / 'target').exists() and 'PRIVATE' not in json.dumps(state.records)


def test_fresh_request_never_forwards_host_cookie_auth(monkeypatch):
    def opener(*_):
        class Fake:
            def open(self, request, timeout):
                headers = {k.lower(): v for k, v in request.header_items()}
                assert set(headers) == {'accept-encoding', 'user-agent', 'if-match'}
                return Response()
        return Fake()
    monkeypatch.setattr(m, 'build_opener', opener)
    response = m.open_once('https://raw.githubusercontent.com/ThomasYeoLab/CBIG/commit/file', 1, '"etag"'); response.close()


def test_redirect_default_error_is_unread_and_closed():
    body = Response(b'never read', code=302)
    request = Request('https://osf.io/download/abcde/?revision=2')
    assert m.NoRedirect().http_error_302(request, body, 302, 'redirect', {'Location': 'https://host/'}) is None
    with pytest.raises(HTTPError) as exc:
        HTTPDefaultErrorHandler().http_error_default(request, body, 302, 'redirect', {})
    assert body.tell() == 0; exc.value.close(); assert body.closed


@pytest.mark.parametrize('case', ['length', 'duplicate_length', 'encoding', 'html', 'truncated', 'oversized', 'digest', 'status'])
def test_network_failure_preserves_partial_or_diagnostic(tmp_path, case):
    r = github(); state = m.State()
    headers = [('Content-Type', 'application/octet-stream'), ('Content-Length', '7')]; raw = b'payload'; code = 200
    if case == 'length': headers[-1] = ('Content-Length', '8')
    elif case == 'duplicate_length': headers.append(('Content-Length', '7'))
    elif case == 'encoding': headers.append(('Content-Encoding', 'gzip'))
    elif case == 'html': headers[0] = ('Content-Type', 'text/html')
    elif case == 'truncated': raw = b'pay'
    elif case == 'oversized': raw = b'payloadX'
    elif case == 'digest': raw = b'PAYLOAD'
    else: code = 500
    response = Response(raw, code, headers)
    with pytest.raises(m.Refusal): m.download(r, tmp_path / 'target', state, lambda *_: response)
    assert response.closed and state.cancelled.is_set() and state.records[0]['status'] == 'failed'
    assert not (tmp_path / 'target').exists()


def test_missing_content_length_refused_for_direct_original(tmp_path):
    response = Response(headers=[('Content-Type', 'application/octet-stream')]); state = m.State()
    with pytest.raises(m.Refusal, match='missing_or_duplicate_content-length'):
        m.download(github(), tmp_path / 'target', state, lambda *_: response)
    assert not (tmp_path / 'target').exists() and response.closed


def test_aggregate_cap_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'MAX_BYTES', 3); state = m.State()
    with pytest.raises(m.Refusal, match='aggregate'): m.download(github(), tmp_path / 'target', state, lambda *_: Response())
    assert state.bytes == 7 and not (tmp_path / 'target').exists()


def test_deadline_and_duplicate_start():
    state = m.State(); state.start('x')
    with pytest.raises(m.Refusal, match='duplicate'): state.start('x')
    state.deadline = time.monotonic() - 1
    with pytest.raises(m.Refusal, match='deadline'): state.check()


def test_cancelled_no_new_transport(tmp_path):
    state = m.State(); state.cancelled.set()
    with pytest.raises(m.Refusal, match='cancelled'):
        m.download(github(), tmp_path / 'target', state, lambda *_: pytest.fail('transport after cancel'))


def test_parallel_failure_no_remaining_scheduling(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'WORKERS', 1); state = m.State()
    jobs = [(dict(github(), path=f'row{i}'), tmp_path / f'row{i}') for i in range(4)]
    with pytest.raises(m.Refusal): m.parallel_download(jobs, state, lambda *_: Response(code=500))
    assert state.starts == {'row0'}


def test_publish_no_replace_preserves_existing(tmp_path):
    pending, destination = tmp_path / 'pending', tmp_path / 'destination'
    pending.mkdir(); destination.mkdir(); write(destination / 'keep', b'old')
    with pytest.raises(OSError): m.publish(pending, destination)
    assert pending.is_dir() and (destination / 'keep').read_bytes() == b'old'


def test_verify_cli_no_network_or_work_creation(tmp_path, monkeypatch, capsys):
    source, path, _, _ = bundle(tmp_path, monkeypatch); write(source / m.MANIFEST_NAME, path.read_bytes())
    monkeypatch.setattr(m, 'stage', lambda *_: pytest.fail('staging in verify-only'))
    work = tmp_path / 'never-created'
    assert m.main(['--verify-existing', '--destination', str(source), '--work-dir', str(work)]) == 0
    assert not work.exists() and json.loads(capsys.readouterr().out)['mode'] == 'offline_verify_only'
