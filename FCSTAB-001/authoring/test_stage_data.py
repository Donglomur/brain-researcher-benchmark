"""Manufactured-only staging tests; no cache, remote requests or scientific parser."""
from __future__ import annotations

from dataclasses import replace
from email.message import Message
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

import pytest

STAGER_PATH = Path(__file__).resolve().parents[1]/'environment'/'stage_data.py'
spec = importlib.util.spec_from_file_location('fcstab_stager', STAGER_PATH)
s = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = s
spec.loader.exec_module(s)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(raw):
    return hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()


@pytest.fixture
def bundle(tmp_path):
    source, notice_dir, metadata = [tmp_path / x for x in ('originals', 'notice', 'metadata')]
    for path in (source, notice_dir, metadata):
        path.mkdir()
    (source / 'roi').mkdir()
    rows, payloads, ids = [], {}, ['Pitt_0050003', 'NYU_0050004']
    for index, fid in enumerate([None, *ids]):
        role = 'phenotype' if fid is None else 'roi_timeseries'
        path = s.PHENOTYPE if fid is None else f'roi/{fid}_rois_cc200.1D'
        key = s.PHENOTYPE if fid is None else s.ROI_PREFIX + fid + '_rois_cc200.1D'
        version = s.PHENOTYPE_VERSION if fid is None else 'null'
        raw = b'opaque\x00\xffbytes\n' + bytes([index])  # Deliberately not valid CSV/ROI text.
        row = dict(path=path, role=role, size_bytes=len(raw), sha256=sha(raw), source_key=key,
                   source_url=s.BASE_URL + key, download_url=s.BASE_URL + key + '?' + s.urlencode({'versionId': version}),
                   version_id=version, etag='"opaque-token-not-a-md5"', etag_is_assumed_md5=False,
                   named_version_immutable=fid is None, arbitrary_documentary_field={'retained': [index]})
        if fid:
            row.update(file_id=fid, subject_id=str(int(fid.rsplit('_', 1)[1])), phenotype_row_index=index)
        rows.append(row)
        payloads[path] = raw
        (source / path).write_bytes(raw)
    raw = b'Manufactured notice, not an upstream source.\n'
    notice = notice_dir / 'notice.rst'
    notice.write_bytes(raw)
    row = dict(path=s.NOTICE_PATH, role='provenance_abide_notice', size_bytes=len(raw), sha256=sha(raw),
               git_blob_sha1=git(raw), source_url=s.NOTICE_URL, download_url=s.NOTICE_URL)
    rows.append(row)
    payloads[row['path']] = raw
    total = sum(x['size_bytes'] for x in rows)
    doc = dict(schema_version='fcstab-source-v1', task_id='FCSTAB-001', dataset_id=s.DATASET,
               upstream_immutable_release=False, runtime_data_directory='/app/data/fcstab', source_files_directory='.',
               files=rows, participant_file_ids=ids, source_file_count=len(rows), source_bytes=total,
               reuse_lineage=dict(prior_source_manifest_sha256=s.PRIOR_MANIFEST_SHA256,
                                  public_subject_ids_sha256=s.SUBJECT_IDS_SHA256),
               cohort_source=dict(path=s.PHENOTYPE, original_rows=4, named_derivatives=2, selected_derivatives=2, no_filename_rows=2))
    raw_manifest = (json.dumps(doc, indent=2) + '\n').encode()
    manifest = metadata / s.MANIFEST_NAME
    manifest.write_bytes(raw_manifest)
    policy = s.Policy(sha(raw_manifest), file_count=4, source_bytes=total, roi_count=2, phenotype_rows=4, phenotype_named_rows=2,
                      transfer_cap=10000, wall_seconds=30)
    return dict(source=source, notice=notice, manifest=manifest, policy=policy, doc=doc, payloads=payloads,
                destination=tmp_path / 'installed' / 'fcstab', work=tmp_path / 'work')


def local(b, **kwargs):
    return s.stage(b['manifest'], b['destination'], b['work'], source_dir=b['source'],
                   notice_file=b['notice'], policy=b['policy'], **kwargs)


def test_local_auth_copy_closed_and_offline(bundle, monkeypatch):
    monkeypatch.setattr(s.urllib.request, 'build_opener', lambda *a: pytest.fail('network'))
    result = local(bundle)
    assert result['status'] == 'ok' and result['network_requests'] == result['received_bytes'] == 0
    assert result['source_payloads_parsed'] is False
    assert s.verify_staged(bundle['destination'], policy=bundle['policy']) == bundle['doc']
    for row in bundle['doc']['files']:
        out = bundle['destination'] / row['path']
        assert out.read_bytes() == bundle['payloads'][row['path']]
        if row['role'] != 'provenance_abide_notice':
            assert out.stat().st_ino != (bundle['source'] / row['path']).stat().st_ino
    assert not (bundle['work'] / 'pending').exists()


def test_every_local_source_authenticated_before_copy(bundle):
    bundle['notice'].write_bytes(b'X' * bundle['notice'].stat().st_size)
    with pytest.raises(s.Refusal, match='source_size_or_sha256'):
        local(bundle)
    assert not bundle['destination'].exists() and not (bundle['work'] / 'pending').exists()
    assert json.loads((bundle['work'] / 'result.json').read_text())['status'] == 'failed'


@pytest.mark.parametrize('target', ['source', 'manifest', 'notice'])
def test_symlink_input_rejected(bundle, target):
    path = bundle[target]
    moved = path.with_name(path.name + '-real')
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises(s.Refusal, match='symlink'):
        local(bundle)
    assert not bundle['destination'].exists()


@pytest.mark.parametrize('kind', ['extra_file', 'extra_dir', 'missing', 'symlink', 'fifo'])
def test_closed_original_inventory(bundle, kind):
    root = bundle['source']
    if kind == 'extra_file':
        (root / 'extra').write_bytes(b'x')
    elif kind == 'extra_dir':
        (root / 'extra').mkdir()
    elif kind == 'missing':
        (root / s.PHENOTYPE).unlink()
    elif kind == 'symlink':
        (root / 'link').symlink_to(root / s.PHENOTYPE)
    else:
        os.mkfifo(root / 'fifo')
    with pytest.raises(s.Refusal):
        local(bundle)
    assert not (bundle['work'] / 'pending').exists()


@pytest.mark.parametrize('target', ['work', 'destination'])
def test_existing_output_preserved(bundle, target):
    path = bundle[target]
    path.mkdir(parents=True)
    (path / 'sentinel').write_bytes(b'keep')
    with pytest.raises(s.Refusal, match='fresh'):
        local(bundle)
    assert (path / 'sentinel').read_bytes() == b'keep'


@pytest.mark.parametrize('target', ['source', 'manifest', 'notice'])
def test_destination_protected_overlap(bundle, target):
    path = bundle[target]
    bundle['destination'] = (path if path.is_dir() else path.parent) / 'nested' / 'out'
    with pytest.raises(s.Refusal, match='overlapping'):
        local(bundle)
    assert not bundle['destination'].parent.exists()


def test_lexical_link_dotdot_rejected(tmp_path):
    (tmp_path / 'link').symlink_to('/tmp')
    with pytest.raises(s.Refusal, match='lexical_traversal'):
        s.safe_path(str(tmp_path) + '/link/../out')


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"a":1e999}', b'{"a":[NaN]}'])
def test_strict_json(raw):
    with pytest.raises(s.Refusal):
        s.strict_json(raw)


@pytest.mark.parametrize('mutation', ['schema', 'task', 'total', 'count', 'order', 'duplicate', 'traversal',
                                    'source_url', 'download_version', 'null_version', 'etag_md5',
                                    'immutable_null', 'subject_alias', 'row_index', 'missing_notice',
                                    'wrong_notice_url', 'duplicate_subject', 'secondary_hash', 'lineage'])
def test_manifest_rejects(bundle, mutation):
    d = json.loads(json.dumps(bundle['doc']))
    r = d['files'][1]
    if mutation == 'schema': d['schema_version'] = 2
    elif mutation == 'task': d['task_id'] = 'EYESTATE-001'
    elif mutation == 'total': d['source_bytes'] += 1
    elif mutation == 'count': d['source_file_count'] = True
    elif mutation == 'order': d['participant_file_ids'].reverse()
    elif mutation == 'duplicate': d['files'][2] = r.copy()
    elif mutation == 'traversal': r['path'] = '../escape'
    elif mutation == 'source_url': r['source_url'] = 'https://evil.invalid/'
    elif mutation == 'download_version': r['download_url'] += '&versionId=2'
    elif mutation == 'null_version': r['version_id'] = None
    elif mutation == 'etag_md5': r['etag_is_assumed_md5'] = True
    elif mutation == 'immutable_null': r['named_version_immutable'] = True
    elif mutation == 'subject_alias': r['subject_id'] = '050003'
    elif mutation == 'row_index': r['phenotype_row_index'] = True
    elif mutation == 'missing_notice': d['files'][-1]['role'] = 'other'
    elif mutation == 'wrong_notice_url': d['files'][-1]['download_url'] += '?token=secret'
    elif mutation == 'duplicate_subject': d['files'][2]['subject_id'] = r['subject_id']
    elif mutation == 'secondary_hash': r['md5'] = 'a'
    elif mutation == 'lineage': d['reuse_lineage']['prior_source_manifest_sha256'] = '0' * 64
    with pytest.raises(s.Refusal):
        s.validate_manifest(d, bundle['policy'])


def test_manifest_same_buffer_pin_and_cap(bundle):
    assert s.read_manifest(bundle['manifest'], bundle['policy'])[0] == bundle['doc']
    with pytest.raises(s.Refusal, match='metadata_size_cap'):
        s.read_manifest(bundle['manifest'], replace(bundle['policy'], manifest_cap=1))
    with pytest.raises(s.Refusal, match='metadata_digest'):
        s.read_manifest(bundle['manifest'], replace(bundle['policy'], manifest_sha256='0' * 64))


@pytest.mark.parametrize('key', ['md5', 'git_blob_sha1'])
def test_secondary_content_digest(bundle, key):
    row = dict(bundle['doc']['files'][0])
    row[key] = '0' * (32 if key == 'md5' else 40)
    with pytest.raises(s.Refusal, match='source_'):
        s.member_bytes(bundle['source'] / row['path'], row)


def test_source_change_during_read(bundle):
    row = bundle['doc']['files'][0]
    def change():
        path = bundle['source'] / row['path']
        path.write_bytes(b'X' * row['size_bytes'])
    with pytest.raises(s.Refusal):
        s.member_bytes(bundle['source'] / row['path'], row, change)


def test_publication_no_replace_even_empty_directory(tmp_path):
    source, dest = tmp_path / 'source', tmp_path / 'dest'
    source.mkdir(); dest.mkdir()
    (source / 'keep').write_bytes(b'x')
    with pytest.raises(OSError):
        s.publish_directory(source, dest)
    assert (source / 'keep').exists() and list(dest.iterdir()) == []


class Response:
    def __init__(self, row, raw):
        self.status, self.url, self.body, self.closed = 200, row['download_url'], io.BytesIO(raw), False
        self.headers = Message()
        self.headers['Content-Length'] = str(row['size_bytes'])
        self.headers['Content-Type'] = 'text/plain; charset=utf-8'
        if row['role'] != 'provenance_abide_notice':
            self.headers['ETag'] = row['etag']
            self.headers['x-amz-version-id'] = row['version_id']
        self.calls = []
    def geturl(self): return self.url
    def read1(self, n):
        self.calls.append(n)
        return self.body.read(n)
    def read(self, *args): pytest.fail('unbounded/non-read1 HTTP body access')
    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True


class Opener:
    def __init__(self, b, amend=lambda r, response: None):
        self.b, self.amend, self.requests, self.responses = b, amend, [], []
    def open(self, req, timeout):
        self.requests.append(req)
        row = next(r for r in self.b['doc']['files'] if r['download_url'] == req.full_url)
        assert req.get_header('Accept-encoding') == 'identity' and 0 < timeout <= 30
        if row['role'] != 'provenance_abide_notice': assert req.get_header('If-match') == row['etag']
        else: assert req.get_header('If-match') is None
        response = Response(row, self.b['payloads'][row['path']])
        self.responses.append(response)
        self.amend(row, response)
        return response


def test_network_exact_once_and_truthful_ledger(bundle):
    opener = Opener(bundle)
    result = s.stage(bundle['manifest'], bundle['destination'], bundle['work'], policy=bundle['policy'], opener=opener)
    assert result['status'] == 'ok' and result['network_requests'] == len(opener.requests) == 4
    assert result['received_bytes'] == bundle['policy'].source_bytes
    assert len({req.full_url for req in opener.requests}) == 4
    receipt = json.loads((bundle['work'] / 'members' / '0001.json').read_text())
    assert receipt['source_record'] == bundle['doc']['files'][1]
    assert receipt['response_identity']['etag_is_assumed_md5'] is False
    assert all(r.closed for r in opener.responses)


@pytest.mark.parametrize('fault', ['status', 'final_url', 'missing_length', 'duplicate_length', 'length',
                                'encoding', 'transfer_encoding', 'type', 'etag', 'version', 'duplicate_etag',
                                'truncated', 'oversize', 'hash'])
def test_response_failures_preserved(bundle, fault):
    def amend(row, response):
        h = response.headers
        if fault == 'status': response.status = 206
        elif fault == 'final_url': response.url += '?secret=do-not-log'
        elif fault == 'missing_length': del h['Content-Length']
        elif fault == 'duplicate_length': h['Content-Length'] = h['Content-Length']
        elif fault == 'length': h.replace_header('Content-Length', '1')
        elif fault == 'encoding': h['Content-Encoding'] = 'gzip'
        elif fault == 'transfer_encoding': h['Transfer-Encoding'] = 'chunked'
        elif fault == 'type': h.replace_header('Content-Type', 'text/html')
        elif fault == 'etag': h.replace_header('ETag', '"different"')
        elif fault == 'version': h.replace_header('x-amz-version-id', 'other')
        elif fault == 'duplicate_etag': h['ETag'] = h['ETag']
        elif fault == 'truncated': response.body = io.BytesIO(b'')
        elif fault == 'oversize': response.body = io.BytesIO(bundle['payloads'][row['path']] + b'X')
        elif fault == 'hash': response.body = io.BytesIO(b'X' * row['size_bytes'])
    opener = Opener(bundle, amend)
    policy = replace(bundle['policy'], workers=1)
    with pytest.raises(s.Refusal):
        s.stage(bundle['manifest'], bundle['destination'], bundle['work'], policy=policy, opener=opener)
    assert len(opener.requests) == 1 and not bundle['destination'].exists()
    assert list((bundle['work'] / 'pending').glob('*.partial'))
    result = (bundle['work'] / 'result.json').read_text()
    assert 'do-not-log' not in result and json.loads(result)['status'] == 'failed'


def test_http_error_closed_unread_and_redacted(bundle):
    body = io.BytesIO(b'SECRET ERROR BODY')
    class ErrorOpener:
        def open(self, req, timeout):
            raise urllib.error.HTTPError('https://x.invalid/?token=SECRET', 412, 'SECRET', Message(), body)
    with pytest.raises(urllib.error.HTTPError):
        s.stage(bundle['manifest'], bundle['destination'], bundle['work'],
                policy=replace(bundle['policy'], workers=1), opener=ErrorOpener())
    assert body.closed
    result = (bundle['work'] / 'result.json').read_text()
    assert 'SECRET' not in result and 'http_status_412' in result


@pytest.mark.parametrize('code', [301, 302, 303, 307, 308])
def test_redirect_closed_without_body(code):
    class Body:
        closed = False
        def close(self): self.closed = True
        def read(self, *a): pytest.fail('redirect body')
    body = Body()
    method = getattr(s.NoRedirect(), f'http_error_{code}')
    with pytest.raises(s.Refusal, match='redirect_refused'):
        method(None, body, code, 'ignored', {'Location': 'https://secret.invalid/?secret=value'})
    assert body.closed


def test_budget_cancellation_duplicate_start_and_deadline(bundle):
    p = replace(bundle['policy'], transfer_cap=2)
    st = s.State(p)
    response = Response(bundle['doc']['files'][0], b'ABC')
    assert st.read(response, 50) == b'AB'
    with pytest.raises(s.Refusal, match='aggregate_payload_cap'): st.read(response, 1)
    assert st.received == 2 and st.reserved == 0
    st = s.State(bundle['policy'])
    row = bundle['doc']['files'][0]
    st.begin(row)
    with pytest.raises(s.Refusal, match='duplicate_or_excess_start'): st.begin(row)
    st.stop.set()
    with pytest.raises(s.Refusal, match='cancelled'): st.read(response, 1)
    times = iter([0., 31.])
    st = s.State(bundle['policy'], lambda: next(times))
    with pytest.raises(s.Refusal, match='wall_deadline'): st.check()


def test_verification_read_only_and_extra_file_rejected(bundle, monkeypatch):
    local(bundle)
    monkeypatch.setattr(s, 'new_bytes', lambda *a: pytest.fail('write'))
    monkeypatch.setattr(s.urllib.request, 'build_opener', lambda *a: pytest.fail('network'))
    s.verify_staged(bundle['destination'], policy=bundle['policy'])
    (bundle['destination'] / 'unexpected').write_bytes(b'x')
    with pytest.raises(s.Refusal, match='unexpected_file'):
        s.verify_staged(bundle['destination'], policy=bundle['policy'])


def test_cli_verify_does_not_stage(bundle, monkeypatch, capsys):
    monkeypatch.setattr(s, 'PRODUCTION', bundle['policy'])
    monkeypatch.setattr(s, 'verify_staged', lambda p: bundle['doc'])
    monkeypatch.setattr(s, 'stage', lambda *a, **k: pytest.fail('stage'))
    assert s.main(['--verify-existing', '--destination', str(bundle['destination'])]) == 0
    assert json.loads(capsys.readouterr().out)['network_requests'] == 0


def test_import_has_no_source_or_network_actions():
    raw = STAGER_PATH.read_text()
    assert 'import numpy' not in raw and 'import pandas' not in raw
    assert 'opaque_reuse' not in raw and 'stage_source' not in raw
    assert 'if __name__ ==' in raw


def test_cli_manifest_default_matches_public_runtime_path(monkeypatch):
    calls = []
    monkeypatch.setattr(s, 'stage', lambda *a, **k: calls.append(a) or {'status':'ok'})
    assert s.main([]) == 0
    assert calls[0][0] == '/app/source_manifest.json'


def test_first_worker_failure_not_replaced_by_cancellation(bundle):
    state = s.State(bundle['policy'])
    first = urllib.error.HTTPError('https://invalid.invalid/', 412, 'ignored', Message(), None)
    state.fail(first)
    state.fail(s.Refusal('cancelled'))
    assert state.first_error is first
    with pytest.raises(urllib.error.HTTPError) as caught:
        s.acquire(bundle['doc']['files'], bundle['work'], bundle['work'], state, Opener(bundle))
    assert caught.value is first


@pytest.mark.parametrize('key,value', [('selected_derivatives', True), ('named_derivatives', True), ('no_filename_rows', True), ('selected_derivatives', 3), ('named_derivatives', 3), ('no_filename_rows', 1)])
def test_selected_and_full_phenotype_counts_are_distinct_and_typed(bundle, key, value):
    doc = json.loads(json.dumps(bundle['doc']))
    doc['cohort_source'][key] = value
    with pytest.raises(s.Refusal, match='cohort_metadata'):
        s.validate_manifest(doc, bundle['policy'])


def test_unselected_named_phenotype_rows_are_not_no_filename(bundle):
    doc = json.loads(json.dumps(bundle['doc']))
    doc['cohort_source'].update(named_derivatives=3, selected_derivatives=2, no_filename_rows=1)
    policy = replace(bundle['policy'], phenotype_named_rows=3)
    assert len(s.validate_manifest(doc, policy)) == 4
