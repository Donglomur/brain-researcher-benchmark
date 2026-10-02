"""Manufactured RESTCONN transport/archive/staging tests; never fetch sources."""
import hashlib
import importlib.util
import io
import json
from email.message import Message
from pathlib import Path
import stat
import tarfile
from urllib.error import HTTPError
from urllib.request import HTTPDefaultErrorHandler, Request
import zipfile

import pytest

SPEC = importlib.util.spec_from_file_location('portable_stage', Path(__file__).resolve().parents[1] / 'environment' / 'stage_data.py')
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)


def hashes(data):
    return dict(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                md5=hashlib.md5(data).hexdigest(),
                git_blob_sha1=hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest())


def tar_bytes(members):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tar:
        for name, data, kind in members:
            info = tarfile.TarInfo(name); info.type = kind; info.size = len(data)
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE): info.linkname = 'target'
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


class Response(io.BytesIO):
    def __init__(self, data, url, code=200, content_type='application/octet-stream', length=True, etag=None):
        super().__init__(data); self.code = code; self.url = url; self.headers = Message(); self.read_calls = 0
        self.headers['Content-Type'] = content_type
        if length: self.headers['Content-Length'] = str(len(data))
        if etag is not None: self.headers['ETag'] = etag
    def geturl(self): return self.url
    def read1(self, count): self.read_calls += 1; return super().read(count)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    rows, archives, payloads, bodies = [], [], {}, {}
    groups = [
        ('adhd_subject_0010064', ['data/0010064/a.bin', 'data/0010064/b.csv']),
        ('adhd_metadata', ['metadata/ids.txt', 'metadata/phenotype.csv', 'metadata/timing.csv']),
        ('msdl_author_zip', ['MSDL_rois/a.nii', 'MSDL_rois/labels.csv', 'provenance/README.txt']),
    ]
    for aid, paths in groups:
        members = []
        for index, path in enumerate(paths):
            data = (aid + ':' + path).encode(); payloads[path] = data
            member = ('MSDL_rois/README.txt' if path == 'provenance/README.txt' else path)
            rows.append(dict(path=path, archive_id=aid, archive_member=member, **hashes(data)))
            members.append((member, data, tarfile.REGTYPE))
        if aid == 'msdl_author_zip':
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for name, data, _ in members: z.writestr(name, data)
            data = out.getvalue(); path = tmp_path / 'archive.zip'; path.write_bytes(data)
            extra = dict(inventory=m.zip_inventory(path), etag='"synthetic"', format='zip')
        else: data = tar_bytes(members); extra = dict(format='tar.gz')
        url = m.ARCHIVE_URLS[aid]; bodies[url] = data
        archives.append(dict(archive_id=aid, source_url=url, required_members=[x[0] for x in members], **hashes(data), **extra))
    for name, url in zip(('adhd', 'msdl_atlas'), sorted(m.DOC_URLS)):
        path = 'provenance/' + name + '.rst'; data = ('doc:' + name).encode()
        payloads[path] = data; bodies[url] = data
        rows.append(dict(path=path, source_url=url, source_commit=m.DOC_COMMIT, **hashes(data)))
    total = sum(row['size_bytes'] for row in rows)
    obj = dict(n_files=10, total_bytes=total, files=rows, archives=archives)
    directory = tmp_path / 'config'; directory.mkdir(); manifest = directory / 'source_manifest.json'
    raw = json.dumps(obj).encode(); manifest.write_bytes(raw)
    monkeypatch.setattr(m, 'EXPECTED_BYTES', total); monkeypatch.setattr(m, 'MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
    responses = []
    def transport(url, timeout, etag=None):
        response = Response(bodies[url], url, etag=etag)
        if etag: response.headers.replace_header('Content-Type', 'application/zip')
        responses.append(response); return response
    return dict(obj=obj, manifest=manifest, raw=raw, bodies=bodies, payloads=payloads,
                transport=transport, responses=responses, destination=tmp_path/'output', work=tmp_path/'work')


def stage(b, **kwargs):
    return m.stage(b['destination'], b['work'], b['manifest'], transport=b['transport'], **kwargs)


def test_exact_five_starts_and_closed_bundle(bundle):
    report = stage(bundle)
    assert report['status'] == 'ok' and report['source_file_count'] == 10
    assert report['transfer_starts'] == report['network_requests'] == 5
    assert report['network_body_bytes'] == sum(map(len, bundle['bodies'].values()))
    assert all(r.closed for r in bundle['responses'])
    assert all(x['endpoint_start'] == x['canonical_source_endpoint'] for x in report['transfers'])
    assert all(x['redirects'] == [] for x in report['transfers'])
    assert len([p for p in bundle['destination'].rglob('*') if p.is_file()]) == 11
    for name, value in bundle['payloads'].items(): assert (bundle['destination']/name).read_bytes() == value
    assert (bundle['destination']/'source_manifest.json').read_bytes() == bundle['raw']
    assert m.verify_staged(bundle['destination']) == bundle['obj']


def test_verified_local_copy_has_zero_network(bundle, tmp_path):
    stage(bundle); source = bundle['destination']; bundle['destination'] = tmp_path/'second'; bundle['work'] = tmp_path/'second-work'
    def forbidden(*a): pytest.fail('network forbidden')
    bundle['transport'] = forbidden
    report = stage(bundle, source_dir=source)
    assert report['network_requests'] == report['network_body_bytes'] == report['transfer_starts'] == 0
    assert m.verify_staged(bundle['destination']) == bundle['obj']


def test_local_all_hashes_before_copy(bundle, tmp_path):
    source = tmp_path/'local'; source.mkdir()
    for path, value in bundle['payloads'].items():
        dest = source/path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(value)
    last = source/bundle['obj']['files'][-1]['path']; last.write_bytes(b'x'*last.stat().st_size)
    with pytest.raises(m.Refusal, match='sha256'): stage(bundle, source_dir=source)
    assert list((bundle['work']/'pending').iterdir()) == [] and not bundle['destination'].exists()


@pytest.mark.parametrize('change', ['length_missing','length_duplicate','length_bad','encoding','html','wrongurl','redirect','status','truncated','oversized','digest'])
def test_download_transport_refusals(bundle, tmp_path, change):
    row = next(r for r in bundle['obj']['files'] if 'source_commit' in r); data = bundle['bodies'][row['source_url']]
    response = Response(data, row['source_url'])
    if change == 'length_missing': del response.headers['Content-Length']
    elif change == 'length_duplicate': response.headers['Content-Length'] = str(len(data))
    elif change == 'length_bad': response.headers.replace_header('Content-Length', str(len(data)+1))
    elif change == 'encoding': response.headers['Content-Encoding'] = 'gzip'
    elif change == 'html': response.headers.replace_header('Content-Type', 'text/html')
    elif change == 'wrongurl': response.url = 'https://attacker.invalid/other'
    elif change == 'redirect': response.code = 302
    elif change == 'status': response.code = 500
    else:
        content = data[:-1] if change == 'truncated' else data+b'x' if change == 'oversized' else b'x'*len(data)
        response = Response(content, row['source_url']); response.headers.replace_header('Content-Length', str(len(data)))
    state = m.State(); target = tmp_path/'target'
    with pytest.raises(m.Refusal): m.download(row, target, state, lambda *a: response)
    assert response.closed and state.cancelled.is_set() and not target.exists()
    if change not in ('truncated','oversized','digest'): assert response.read_calls == 0


def test_zip_missing_length_allowed_but_hash_required(bundle, tmp_path):
    row = bundle['obj']['archives'][-1]; response = Response(bundle['bodies'][row['source_url']], row['source_url'], length=False, etag=row['etag'])
    response.headers.replace_header('Content-Type', 'application/zip')
    target = tmp_path/'zip'; m.download(row, target, m.State(), lambda *a: response)
    assert target.read_bytes() == bundle['bodies'][row['source_url']]


@pytest.mark.parametrize('change', ['etag', 'type'])
def test_zip_header_binding(bundle, tmp_path, change):
    row = bundle['obj']['archives'][-1]; response = Response(bundle['bodies'][row['source_url']], row['source_url'], etag=row['etag'])
    response.headers.replace_header('Content-Type', 'application/zip')
    if change == 'etag': response.headers.replace_header('ETag', '"wrong"')
    else: response.headers.replace_header('Content-Type', 'text/plain')
    with pytest.raises(m.Refusal): m.download(row, tmp_path/'zip', m.State(), lambda *a: response)
    assert response.read_calls == 0 and response.closed


@pytest.mark.parametrize('url', ['http://www.nitrc.org/x','https://evil.invalid/a','https://www.nitrc.org/frs/download.php/7783/adhd40_0010064.tgz?x=1','https://u:p@www.nitrc.org/x','https://www.nitrc.org:444/x','https://www.nitrc.org/x#fragment'])
def test_closed_endpoints(bundle, url):
    row = bundle['obj']['archives'][0]
    with pytest.raises(m.Refusal): m.endpoint(url, row)


def test_redirect_declined_without_body_read():
    response = Response(b'secret', 'https://example.invalid/')
    assert m.NoRedirect().redirect_request(None, response, 302, '', response.headers, 'https://other.invalid/') is None
    with pytest.raises(HTTPError): HTTPDefaultErrorHandler().http_error_default(Request('https://example.invalid/'), response, 302, 'Found', response.headers)
    assert response.read_calls == 0; response.close()


def test_aggregate_cap_counts_received_bytes(bundle, tmp_path, monkeypatch):
    row = next(r for r in bundle['obj']['files'] if 'source_commit' in r)
    monkeypatch.setattr(m, 'MAX_BYTES', row['size_bytes']-1); state = m.State()
    with pytest.raises(m.Refusal, match='aggregate_byte_cap'): m.download(row, tmp_path/'x', state, bundle['transport'])
    assert state.bytes == row['size_bytes'] and state.cancelled.is_set()


@pytest.mark.parametrize('which', ['duplicate','excess','cancelled','expired'])
def test_start_and_time_bounds(which):
    state = m.State()
    if which == 'duplicate': state.start('a'); key = 'a'
    elif which == 'excess':
        for index in range(5): state.start(str(index))
        key = 'sixth'
    elif which == 'cancelled': state.cancelled.set(); key = 'a'
    else: state.deadline = 0; key = 'a'
    with pytest.raises(m.Refusal): state.start(key)


def test_failure_does_not_schedule_more_than_inflight_pair(bundle, monkeypatch):
    attempted = []
    def fail(*args): attempted.append(args[0]); raise OSError('synthetic')
    bundle['transport'] = fail
    with pytest.raises((OSError,m.Refusal)): stage(bundle)
    assert 1 <= len(attempted) <= 2
    report = json.loads((bundle['work']/'result.json').read_text())
    assert report['status'] == 'failed' and report['automatic_retries'] == 0
    assert not bundle['destination'].exists()


def tar_case(tmp_path, members, selected='good', expected=b'ok'):
    data = tar_bytes(members); path = tmp_path/'test.tgz'; path.write_bytes(data)
    archive = dict(required_members=[selected], **hashes(data))
    row = dict(path='out.bin', archive_member=selected, **hashes(expected))
    return path, archive, [row], tmp_path/'pending', m.State()


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.CHRTYPE,tarfile.FIFOTYPE])
def test_tar_nonregular_rejected(tmp_path, kind):
    args = tar_case(tmp_path, [('bad',b'',kind),('good',b'ok',tarfile.REGTYPE)])
    with pytest.raises(m.Refusal, match='tar_nonregular'): m.extract_tar(*args)


@pytest.mark.parametrize('name', ['../escape','/absolute','x/../../escape','C:/drive','x\\bad'])
def test_tar_path_rejected(tmp_path, name):
    args = tar_case(tmp_path, [(name,b'',tarfile.REGTYPE),('good',b'ok',tarfile.REGTYPE)])
    with pytest.raises(m.Refusal, match='unsafe_relative'): m.extract_tar(*args)


@pytest.mark.parametrize('kind', ['duplicate','missing','size','collision'])
def test_tar_inventory_rejections(tmp_path, kind):
    members = [('good',b'ok',tarfile.REGTYPE)]
    if kind == 'duplicate': members += members
    elif kind == 'missing': members = [('other',b'ok',tarfile.REGTYPE)]
    elif kind == 'size': members = [('good',b'bad-size',tarfile.REGTYPE)]
    else: members += [('good/child',b'x',tarfile.REGTYPE)]
    with pytest.raises(m.Refusal): m.extract_tar(*tar_case(tmp_path,members))


def test_tar_unselected_regulars_not_extracted(tmp_path):
    args = tar_case(tmp_path,[('other',b'opaque',tarfile.REGTYPE),('good',b'ok',tarfile.REGTYPE)])
    m.extract_tar(*args)
    assert [x.name for x in args[3].iterdir()] == ['out.bin']


def test_archive_hash_precedes_inventory(tmp_path, monkeypatch):
    args = tar_case(tmp_path,[('good',b'ok',tarfile.REGTYPE)]); args[1]['sha256'] = '0'*64
    monkeypatch.setattr(m.tarfile,'open',lambda *a,**k: pytest.fail('must hash before parser'))
    with pytest.raises(m.Refusal, match='sha256'): m.extract_tar(*args)


@pytest.mark.parametrize('kind', ['unsafe','symlink','duplicate','too_many'])
def test_zip_guards(tmp_path, kind):
    path = tmp_path/'x.zip'
    with zipfile.ZipFile(path,'w') as z:
        if kind == 'unsafe': z.writestr('../bad',b'x')
        elif kind == 'symlink':
            info=zipfile.ZipInfo('link'); info.create_system=3; info.external_attr=(stat.S_IFLNK|0o777)<<16; z.writestr(info,b'target')
        elif kind == 'duplicate': z.writestr('a',b'x'); z.writestr('a',b'y')
        else:
            for i in range(33): z.writestr(str(i),b'x')
    with pytest.raises(m.Refusal): m.zip_inventory(path)


@pytest.mark.parametrize('kind', ['existing','overlap','manifest_bad','symlink'])
def test_staging_safety_before_mutation(bundle, tmp_path, kind):
    if kind == 'existing': bundle['destination'].mkdir()
    elif kind == 'overlap': bundle['destination'] = bundle['manifest'].parent/'out'
    elif kind == 'manifest_bad': bundle['manifest'].write_bytes(bundle['raw']+b' ')
    else: bundle['destination'].symlink_to(tmp_path/'absent')
    with pytest.raises(m.Refusal): stage(bundle)
    assert not bundle['work'].exists()


def test_offline_verify_no_writes_or_network(bundle, monkeypatch, capsys):
    stage(bundle); monkeypatch.setattr(m,'stage',lambda *a,**k:pytest.fail('not staging'))
    assert m.main(['--verify-existing','--destination',str(bundle['destination'])]) == 0
    assert 'offline_verify_only' in capsys.readouterr().out


@pytest.mark.parametrize('body', ['{"a":1,"a":2}','{"a":NaN}','{"a":[1e999]}'])
def test_strict_json(body):
    with pytest.raises(m.Refusal): m.strict_json(body)
