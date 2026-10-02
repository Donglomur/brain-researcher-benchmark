"""Manufactured FCVAR staging tests; no originals or live HTTP."""
import copy
from email.message import Message
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import threading

import pytest

SPEC = importlib.util.spec_from_file_location('fcvar_portable_stage', Path(__file__).resolve().parents[1]/'environment/stage_data.py')
s = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = s
SPEC.loader.exec_module(s)


def pins(data):
    return dict(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                md5=hashlib.md5(data).hexdigest(),
                git_blob_sha1=hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest())


def tar_bytes(items):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w', format=tarfile.USTAR_FORMAT) as t:
        for name, data, kind in items:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(data)
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                info.linkname = 'elsewhere'
            t.addfile(info, io.BytesIO(data))
    return gzip.compress(out.getvalue(), mtime=0)


class Response(io.BytesIO):
    def __init__(self, data, url, kind='application/gzip', code=200):
        super().__init__(data)
        self.url, self.code, self.read_calls = url, code, 0
        self.headers = Message()
        self.headers['Content-Length'] = str(len(data))
        self.headers['Content-Type'] = kind

    def geturl(self):
        return self.url

    def read1(self, count=-1):
        self.read_calls += 1
        return super().read(count)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    rows, archives, bodies = [], [], {}
    for key, filename in s.ARCHIVE_FILENAMES.items():
        url = f'https://www.nitrc.org/frs/download.php/{key}/{filename}'
        if key in s.SUBJECT_ARCHIVES:
            sid = s.SUBJECT_ARCHIVES[key]
            descriptions = [(role, sid, f'{role}/{sid}.bin') for role in ('bold', 'confounds')]
        elif key == '7781':
            descriptions = [(role, None, f'metadata/{role}.txt') for role in
                            ('cohort_ids', 'phenotype_metadata', 'slice_timing_metadata')]
        else:
            descriptions = [(role, None, f'atlas/{role}.bin') for role in ('atlas_image', 'atlas_labels')]
        selected, items = [], []
        for role, sid, path in descriptions:
            member = f'original/{role}_{Path(path).name}'
            data = f'manufactured opaque {key} {role}\n'.encode()
            row = dict(path=path, role=role, participant_id=sid, archive_id=key,
                       archive_member=member, source_url=url, **pins(data))
            rows.append(row)
            selected.append({k: row[k] for k in ('path', 'archive_member', 'size_bytes', 'sha256')})
            bodies[path] = data
            items.append((member, data, tarfile.REGTYPE))
        raw = tar_bytes(items)
        archive = dict(archive_id=key, filename=filename, url=url, **pins(raw))
        archive['required_members' if key == '9902' else 'members'] = selected
        archives.append(archive)
        bodies[key] = raw
    for name, role in [('adhd', 'provenance_adhd_notice'), ('harvard_oxford', 'provenance_ho_notice')]:
        data = f'manufactured {name} notice\n'.encode()
        path = f'provenance/{name}.rst'
        row = dict(path=path, role=role, participant_id=None, source_commit=s.DOC_COMMIT,
                   source_url=next(url for url in s.DOC_URLS if url.endswith('/' + name + '.rst')), **pins(data))
        rows.append(row)
        bodies[path] = data
    manifest = dict(schema_version='fcvar-source-v2', task_id='FCVAR-001', runtime_data_directory='/app/data/fcvar',
                    source_files_directory='.', participant_ids=sorted(s.SUBJECT_ARCHIVES.values()),
                    files=rows, archives=archives, source_file_count=len(rows),
                    source_bytes=sum(row['size_bytes'] for row in rows))
    monkeypatch.setattr(s, 'EXPECTED_BYTES', manifest['source_bytes'])
    metadata = tmp_path / 'metadata'
    metadata.mkdir()
    path = metadata / 'source_manifest.json'

    def save(obj=manifest):
        raw = (json.dumps(obj, sort_keys=True) + '\n').encode()
        path.write_bytes(raw)
        monkeypatch.setattr(s, 'MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
        return raw
    raw = save()
    source = tmp_path / 'originals'
    source.mkdir()
    for row in rows:
        target = source / row['path']
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(bodies[row['path']])
    (source / s.MANIFEST_NAME).write_bytes(raw)
    calls, lock = [], threading.Lock()

    def transport(url, timeout):
        assert 0 < timeout <= s.SOCKET_SECONDS
        candidates = s.archive_jobs(manifest) + [r for r in rows if 'archive_id' not in r]
        row = next(r for r in candidates if r['source_url'] == url)
        key = row.get('path', row.get('archive_id'))
        with lock:
            calls.append(key)
        return Response(bodies[key], url, 'application/gzip' if row.get('format') == 'tar.gz' else 'text/plain')
    return dict(manifest=manifest, path=path, save=save, source=source, raw=raw, bodies=bodies,
                transport=transport, calls=calls, dest=tmp_path / 'delivery' / 'staged', work=tmp_path / 'work')


def forbidden(*unused, **kwargs):
    raise AssertionError('unexpected network or write')


def test_manifest_and_complete_local_copy(bundle):
    b = bundle
    before = {p: p.stat().st_mtime_ns for p in b['source'].rglob('*')}
    result = s.stage(b['dest'], b['work'], b['path'], b['source'], forbidden)
    assert result['status'] == 'ok'
    assert result['network_requests'] == result['network_body_bytes'] == result['transfer_starts'] == 0
    assert result['source_file_count'] == 67
    assert (b['dest'] / s.MANIFEST_NAME).read_bytes() == b['raw']
    assert s.verify_staged(b['dest']) == b['manifest']
    assert all(path.stat().st_mtime_ns == stamp for path, stamp in before.items())
    assert all((b['dest'] / r['path']).stat().st_ino != (b['source'] / r['path']).stat().st_ino
               for r in b['manifest']['files'])


def test_complete_cold_route_exact_34_starts(bundle):
    b = bundle
    result = s.stage(b['dest'], b['work'], b['path'], transport=b['transport'])
    assert result['status'] == 'ok'
    assert result['network_requests'] == result['transfer_starts'] == len(set(b['calls'])) == 34
    assert result['network_body_bytes'] == sum(a['size_bytes'] for a in b['manifest']['archives']) + sum(
        r['size_bytes'] for r in b['manifest']['files'] if 'archive_id' not in r)
    assert result['redirects'] == result['automatic_retries'] == 0
    assert not result['source_payload_parsed']
    assert s.verify_staged(b['dest']) == b['manifest']


def test_verify_existing_does_not_write_or_network(bundle, monkeypatch):
    monkeypatch.setattr(s, 'write_json', forbidden)
    monkeypatch.setattr(s, 'open_once', forbidden)
    assert s.verify_staged(bundle['source']) == bundle['manifest']


@pytest.mark.parametrize('case', ['hash', 'same_size_hash', 'extra', 'emptydir', 'link', 'missing', 'manifest'])
def test_all_sources_before_any_copy(bundle, case):
    b = bundle
    row = b['manifest']['files'][-1]
    path = b['source'] / row['path']
    if case == 'hash':
        path.write_bytes(b'broken')
    elif case == 'same_size_hash':
        path.write_bytes(b'!' * row['size_bytes'])
    elif case == 'extra':
        (b['source'] / 'extra').write_bytes(b'extra')
    elif case == 'emptydir':
        (b['source'] / 'empty').mkdir()
    elif case == 'link':
        path.unlink()
        path.symlink_to(b['source'] / b['manifest']['files'][0]['path'])
    elif case == 'missing':
        path.unlink()
    else:
        (b['source'] / s.MANIFEST_NAME).write_bytes(b'{}')
    with pytest.raises(s.Refusal):
        s.stage(b['dest'], b['work'], b['path'], b['source'], forbidden)
    assert not b['dest'].exists()
    assert list((b['work'] / 'pending').iterdir()) == []
    assert json.loads((b['work'] / 'result.json').read_text())['status'] == 'failed'


@pytest.mark.parametrize('case', ['destination_exists', 'work_exists', 'nested', 'source_overlap',
                                 'manifest_overlap', 'symlink_parent', 'traversal'])
def test_path_refusal_before_mutation(bundle, case, tmp_path):
    b = bundle
    dest, work = b['dest'], b['work']
    if case == 'destination_exists':
        dest.mkdir(parents=True)
    elif case == 'work_exists':
        work.mkdir()
    elif case == 'nested':
        dest = work / 'child'
    elif case == 'source_overlap':
        dest = b['source'] / 'child'
    elif case == 'manifest_overlap':
        dest = b['path'].parent / 'child'
    elif case == 'symlink_parent':
        (tmp_path / 'link').symlink_to(b['source'], target_is_directory=True)
        dest = tmp_path / 'link' / 'child'
    else:
        dest = str(tmp_path) + '/missing/../child'
    original = set(tmp_path.rglob('*'))
    with pytest.raises(s.Refusal):
        s.stage(dest, work, b['path'], b['source'], forbidden)
    assert set(tmp_path.rglob('*')) == original


@pytest.mark.parametrize('kind', ['count', 'bytes', 'cohort', 'schema', 'layout', 'duplicate', 'role', 'collision',
                                 'hash_field', 'bool_size', 'archive_url', 'archive_member', 'member_pin', 'doc_url'])
def test_manifest_guards(bundle, kind):
    b = bundle
    obj = copy.deepcopy(b['manifest'])
    if kind == 'count': obj['source_file_count'] -= 1
    elif kind == 'bytes': obj['source_bytes'] += 1
    elif kind == 'cohort': obj['participant_ids'].reverse()
    elif kind == 'schema': obj['schema_version'] = 'other'
    elif kind == 'layout': obj['source_files_directory'] = 'originals'
    elif kind == 'duplicate': obj['files'][1]['path'] = obj['files'][0]['path']
    elif kind == 'role': obj['files'][1]['role'] = obj['files'][0]['role']
    elif kind == 'collision': obj['files'][1]['path'] = obj['files'][0]['path'] + '/nested'
    elif kind == 'hash_field': obj['files'][0]['md5'] = 'wrong'
    elif kind == 'bool_size': obj['files'][0]['size_bytes'] = True
    elif kind == 'archive_url': obj['archives'][0]['url'] += '?other=1'
    elif kind == 'archive_member': obj['archives'][0]['members'][0]['archive_member'] = '../escape'
    elif kind == 'member_pin': obj['archives'][0]['members'][0]['sha256'] = '0' * 64
    elif kind == 'doc_url': obj['files'][-1]['source_url'] = obj['files'][-1]['source_url'].replace(s.DOC_COMMIT, 'main')
    b['save'](obj)
    with pytest.raises(s.Refusal):
        s.load_manifest(b['path'])


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":[1e999]}'])
def test_strict_json(raw):
    with pytest.raises(s.Refusal):
        s.strict_json(raw)


def test_manifest_pin_checked_before_parse(bundle):
    bundle['path'].write_bytes(b'{invalid')
    with pytest.raises(s.Refusal, match='manifest_digest'):
        s.load_manifest(bundle['path'])


@pytest.mark.parametrize('suffix', ['?secret=x', '#fragment', '/other'])
def test_endpoint_escape(bundle, suffix):
    row = s.archive_jobs(bundle['manifest'])[0]
    changed = dict(row, source_url=row['source_url'] + suffix)
    with pytest.raises(s.Refusal):
        s.endpoint(changed['source_url'], changed)


@pytest.mark.parametrize('case', ['missing_length', 'duplicate_length', 'bad_length', 'encoding', 'html',
                                 'duplicate_type', 'wrong_url', 'redirect', 'error', 'short', 'overlong', 'wrong_hash'])
def test_download_refusals(bundle, tmp_path, case):
    row = s.archive_jobs(bundle['manifest'])[0]
    data = bundle['bodies'][row['archive_id']]
    response = Response(data, row['source_url'])
    if case == 'missing_length': del response.headers['Content-Length']
    elif case == 'duplicate_length': response.headers['Content-Length'] = str(len(data))
    elif case == 'bad_length': response.headers.replace_header('Content-Length', str(len(data) + 1))
    elif case == 'encoding': response.headers['Content-Encoding'] = 'gzip'
    elif case == 'html': response.headers.replace_header('Content-Type', 'text/html')
    elif case == 'duplicate_type': response.headers['Content-Type'] = 'application/gzip'
    elif case == 'wrong_url': response.url += '?secret=never_log'
    elif case == 'redirect': response.code = 302
    elif case == 'error': response.code = 500
    elif case == 'short': response = Response(data[:-1], row['source_url'])
    elif case == 'overlong': response = Response(data + b'!', row['source_url'])
    elif case == 'wrong_hash': response = Response(b'!' * len(data), row['source_url'])
    if case in ('short', 'overlong'):
        response.headers.replace_header('Content-Length', str(len(data)))
    state = s.State()
    target = tmp_path / 'object'
    with pytest.raises(s.Refusal):
        s.download(row, target, state, lambda *a: response)
    assert not target.exists()
    assert response.closed and state.cancelled.is_set()
    assert state.requests == 1 and len(state.starts) == 1
    assert 'never_log' not in json.dumps(state.records)
    if case not in ('short', 'overlong', 'wrong_hash'):
        assert response.read_calls == 0
    else:
        assert target.with_name('object.partial').exists()


def test_download_success_closes_and_uses_read1(bundle, tmp_path):
    row = s.archive_jobs(bundle['manifest'])[0]
    response = Response(bundle['bodies'][row['archive_id']], row['source_url'])
    response.read = forbidden
    state = s.State()
    s.download(row, tmp_path / 'object', state, lambda *a: response)
    assert response.closed and response.read_calls >= 2
    assert state.records[0]['status'] == 'verified'


def test_no_redirect_handler_never_reads():
    assert s.NoRedirect().redirect_request(None, Response(b'forbidden', 'https://x'), 302, '', {}, 'https://y') is None


@pytest.mark.parametrize('case', ['cap', 'deadline', 'cancel', 'duplicate'])
def test_state_bounds(case, monkeypatch):
    state = s.State()
    if case == 'cap':
        monkeypatch.setattr(s, 'MAX_BYTES', 2)
        with pytest.raises(s.Refusal, match='aggregate_byte_cap'): state.received(b'123')
    elif case == 'deadline':
        state.deadline = 0
        with pytest.raises(s.Refusal, match='wall_deadline'): state.check()
    elif case == 'cancel':
        state.cancelled.set()
        with pytest.raises(s.Refusal, match='cancelled'): state.start('one')
    else:
        state.start('one')
        with pytest.raises(s.Refusal, match='duplicate'): state.start('one')


def test_parallel_failure_stops_new_scheduling(bundle, monkeypatch, tmp_path):
    monkeypatch.setattr(s, 'WORKERS', 1)
    rows = s.archive_jobs(bundle['manifest'])[:3]
    calls = []
    def fail(url, timeout):
        calls.append(url)
        return Response(b'error', url, code=500)
    state = s.State()
    with pytest.raises(s.Refusal):
        s.parallel_download([(r, tmp_path / r['archive_id']) for r in rows], state, fail)
    assert len(calls) == len(state.starts) == 1


@pytest.mark.parametrize('kind', ['traversal', 'absolute', 'link', 'hardlink', 'duplicate', 'collision', 'fifo',
                                 'member_cap', 'expanded_cap', 'crc', 'tail'])
def test_tar_full_inventory_before_extraction(kind, monkeypatch):
    entries = [('safe/member', b'bytes', tarfile.REGTYPE)]
    if kind == 'traversal': entries.append(('../bad', b'x', tarfile.REGTYPE))
    elif kind == 'absolute': entries.append(('/bad', b'x', tarfile.REGTYPE))
    elif kind == 'link': entries.append(('link', b'', tarfile.SYMTYPE))
    elif kind == 'hardlink': entries.append(('link', b'', tarfile.LNKTYPE))
    elif kind == 'duplicate': entries.append(entries[0])
    elif kind == 'collision': entries.append(('safe', b'x', tarfile.REGTYPE))
    elif kind == 'fifo': entries.append(('pipe', b'', tarfile.FIFOTYPE))
    elif kind == 'member_cap': monkeypatch.setattr(s, 'MAX_MEMBERS', 0)
    elif kind == 'expanded_cap': monkeypatch.setattr(s, 'MAX_EXPANDED_BYTES', 500)
    raw = tar_bytes(entries)
    if kind == 'crc': raw = raw[:-8] + bytes([raw[-8] ^ 1]) + raw[-7:]
    elif kind == 'tail': raw = gzip.compress(gzip.decompress(raw) + b'bad')
    with pytest.raises((s.Refusal, OSError, EOFError, tarfile.TarError)):
        s.tar_inventory(raw, s.State())


def test_tar_selected_bytes_immutable_buffer(bundle, tmp_path):
    row = s.archive_jobs(bundle['manifest'])[0]
    selected = [r for r in bundle['manifest']['files'] if r.get('archive_id') == row['archive_id']]
    archive = tmp_path / 'archive.tgz'
    archive.write_bytes(bundle['bodies'][row['archive_id']])
    target = tmp_path / 'pending'
    target.mkdir()
    s.extract_tar(archive, row, selected, target, s.State())
    assert all((target / r['path']).read_bytes() == bundle['bodies'][r['path']] for r in selected)


def test_tar_digest_before_inventory(bundle, tmp_path, monkeypatch):
    row = s.archive_jobs(bundle['manifest'])[0]
    archive = tmp_path / 'archive.tgz'
    archive.write_bytes(b'!' * row['size_bytes'])
    monkeypatch.setattr(s, 'tar_inventory', forbidden)
    with pytest.raises(s.Refusal, match='sha256'):
        s.extract_tar(archive, row, [], tmp_path / 'pending', s.State())


def test_tar_selection_checked_before_member_copy(bundle, tmp_path):
    row = s.archive_jobs(bundle['manifest'])[0]
    selected = copy.deepcopy([r for r in bundle['manifest']['files'] if r.get('archive_id') == row['archive_id']])
    selected[-1]['archive_member'] = 'missing'
    archive = tmp_path / 'archive.tgz'
    archive.write_bytes(bundle['bodies'][row['archive_id']])
    target = tmp_path / 'pending'
    target.mkdir()
    with pytest.raises(s.Refusal, match='tar_selected'):
        s.extract_tar(archive, row, selected, target, s.State())
    assert list(target.iterdir()) == []


def test_secondary_identity_required():
    row = pins(b'bytes')
    row['md5'] = '0' * 32
    with pytest.raises(s.Refusal, match='md5'):
        s.buffer_identity(b'bytes', row)


def test_rename_no_overwrite(tmp_path):
    source, target = tmp_path / 'pending', tmp_path / 'destination'
    source.mkdir()
    target.mkdir()
    (target / 'sentinel').write_bytes(b'preserve')
    with pytest.raises(OSError):
        s.publish(source, target)
    assert (target / 'sentinel').read_bytes() == b'preserve'
    assert source.is_dir()


def test_late_failure_leaves_no_published_directory(bundle, monkeypatch):
    monkeypatch.setattr(s, 'publish', lambda *a: (_ for _ in ()).throw(s.Refusal('manufactured_late_failure')))
    b = bundle
    with pytest.raises(s.Refusal, match='manufactured_late_failure'):
        s.stage(b['dest'], b['work'], b['path'], b['source'], forbidden)
    result = json.loads((b['work'] / 'result.json').read_text())
    assert result['status'] == 'failed' and not b['dest'].exists()
    assert (b['work'] / 'pending' / s.MANIFEST_NAME).exists()


def test_cli_offline_verify(bundle, monkeypatch, capsys):
    monkeypatch.setattr(s, 'open_once', forbidden)
    assert s.main(['--verify-existing', '--destination', str(bundle['source'])]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['mode'] == 'offline_verify_only' and result['source_file_count'] == 67
    assert s.signal.getitimer(s.signal.ITIMER_REAL) == (0., 0.)


def test_import_is_sourcefree():
    raw = Path(s.__file__).read_text()
    assert 'nibabel' not in raw and 'numpy' not in raw and 'get_fdata' not in raw
    assert 'brain-researcher-benchmark-runs' not in raw
    assert "if __name__ == '__main__':" in raw
