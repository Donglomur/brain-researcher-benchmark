"""SOCIALBRAIN checksum-pinned source staging; no scientific payload parsing.

Transport and race/closure guards adapted from reviewed PR197 stager
ff018832b20d872f7a35762da7259d0a6548cda5c5b97e85856b533ca6b638d8.
Adds immutable Git-file identities to OSF originals. No retries, fallback,
secret URL logs or overwrite. Pending manifest constants fail closed.
Hard outer timeout is required in addition to the graceful 900-second deadline.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import shutil
import stat
import threading
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MANIFEST_SHA256 = '9458c48ac61e1e8b0ee36d513ebf6e7613e889a9895747ca46d4c7bd50af8d0b'
MANIFEST_NAME = 'source_manifest.json'
NODE = '5hju4'
SUBJECTS = tuple(f'sub-pixar{i:03d}' for i in range(1,156))
EXPECTED_COUNT, EXPECTED_BYTES = 330, 942572457
MAX_SECONDS, SOCKET_SECONDS, MAX_BYTES, WORKERS = 900, 30, 1_100_000_000, 2
CHUNK, MAX_REDIRECTS, MAX_REQUESTS = 65536, 5, 2000
MIN_FREE_BYTES = 5 * 1024**3


class Refusal(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise Refusal(code)


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw, str) and raw.startswith('/') and '\0' not in raw, 'absolute_path_required')
    need(not any(p in ('.', '..') for p in raw.split('/')), 'path_traversal')
    path = Path(raw)
    for p in (*reversed(path.parents), path):
        if os.path.lexists(p):
            mode = p.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_path')
            if p != path: need(stat.S_ISDIR(mode), 'non_directory_ancestor')
    return path


def relative(value):
    need(isinstance(value, str) and value and '\\' not in value and '\0' not in value
         and not value.startswith('/') and not re.match(r'^[A-Za-z]:', value), 'unsafe_relative_path')
    need(all(p not in ('', '.', '..') for p in value.split('/')), 'unsafe_relative_path')
    return PurePosixPath(value)


def disjoint(a, b):
    need(a != b and a not in b.parents and b not in a.parents, 'overlapping_paths')


def signature(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns


@contextmanager
def reader(path):
    path = safe_path(path); before = path.lstat()
    need(stat.S_ISREG(before.st_mode), 'regular_file_required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as f:
        need(signature(os.fstat(f.fileno())) == signature(before), 'source_changed_before_read')
        yield f, before
        need(signature(os.fstat(f.fileno())) == signature(before), 'source_changed_during_read')
        need(signature(path.lstat()) == signature(before), 'source_path_changed_during_read')


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate_json_key'); out[key] = value
        return out
    def bad(_): raise Refusal('nonfinite_json')
    obj = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    def check(v):
        if isinstance(v, float): need(math.isfinite(v), 'nonfinite_json')
        elif isinstance(v, (list, dict)):
            for x in (v.values() if isinstance(v, dict) else v): check(x)
    check(obj)
    return obj


def write_json(path, obj):
    with safe_path(path).open('x') as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False); f.write('\n')


def version_query(query, version):
    values = parse_qs(query, keep_blank_values=True)
    need(set(values) == {'revision'} and values['revision'] == [str(version)], 'exact_source_revision')


def endpoint(url, row, initial=False):
    p = urlsplit(url)
    need(p.scheme == 'https' and p.username is None and p.password is None
         and p.port in (None, 443) and not p.fragment, 'endpoint_rejected')
    if initial: need(url == row['source_url'], 'initial_url_mismatch')
    if 'osf_object_id' not in row:
        need(p.hostname == 'raw.githubusercontent.com' and not p.query
             and url == row['source_url'], 'immutable_document_url')
        commit = row.get('source_commit')
        parts=p.path.split('/')
        need(isinstance(commit,str) and re.fullmatch('[0-9a-f]{40}',commit)
             and len(parts)>=5 and parts[:4]==['','nilearn','nilearn',commit]
             and all(x not in ('','.','..') for x in parts[4:]), 'immutable_document_commit')
        return {'host': p.hostname, 'path': p.path}
    oid, version = row['osf_object_id'], row['source_version']
    if p.hostname == 'files.osf.io':
        expected = f'/v1/resources/{NODE}/providers/osfstorage/{oid}'
        need(p.path in (expected, expected + '/'), 'waterbutler_object_or_node')
        version_query(p.query, version)
    elif p.hostname == 'osf.io':
        names = {oid} | ({row['source_guid']} if row.get('source_guid') else set())
        paths = {path for name in names for path in
                 (f'/download/{name}', f'/download/{name}/', f'/{name}/download', f'/{name}/download/')}
        need(p.path in paths, 'osf_object_or_guid')
        version_query(p.query, version)
    elif p.hostname == 'storage.googleapis.com':
        need(not initial and re.fullmatch(r'/cos-osf-prod-files-[a-z0-9-]+/' + row['sha256'], p.path), 'storage_object')
        query = parse_qs(p.query, keep_blank_values=True)
        v2 = {'GoogleAccessId','Expires','Signature'}
        v4 = {'X-Goog-Algorithm','X-Goog-Credential','X-Goog-Date','X-Goog-Expires','X-Goog-Signature'}
        need(all(len(values)==1 and values[0] for values in query.values())
             and (v2 <= set(query) or v4 <= set(query)), 'fresh_signed_storage_required')
    else: raise Refusal('endpoint_rejected')
    return {'host': p.hostname, 'path': p.path}  # Signed query values are never logged.


def transport_start(row):
    """One official versioned start; no cache, fallback or unsigned-GCS entry."""
    if 'osf_object_id' not in row:
        endpoint(row['source_url'],row,initial=True)
        return row['source_url']
    url = f"https://files.osf.io/v1/resources/{NODE}/providers/osfstorage/{row['osf_object_id']}?revision={row['source_version']}"
    need(row['source_url'] == url, 'canonical_waterbutler_url')
    endpoint(url, row, initial=True)
    return url


def load_manifest(path):
    need(isinstance(MANIFEST_SHA256,str) and re.fullmatch('[0-9a-f]{64}',MANIFEST_SHA256)
         and type(EXPECTED_COUNT) is int and EXPECTED_COUNT>2*len(SUBJECTS)+1
         and type(EXPECTED_BYTES) is int and 0<EXPECTED_BYTES<MAX_BYTES, 'unfrozen_manifest_pin')
    with reader(path) as (f, info):
        need(0 < info.st_size <= 4*1024**2, 'manifest_size_cap'); raw=f.read(4*1024**2+1)
    need(len(raw)==info.st_size and hashlib.sha256(raw).hexdigest()==MANIFEST_SHA256,'manifest_digest')
    obj=strict_json(raw)
    need(type(obj) is dict and obj.get('task_id')=='SOCIALBRAIN-001'
         and obj.get('schema_version')=='socialbrain-source-v2','manifest_identity')
    need(obj.get('participant_ids')==list(SUBJECTS),'manifest_cohort')
    rows=obj.get('files');seen=set();pairs=set();objects=set();templates=0
    need(type(rows) is list and type(obj.get('n_files')) is int
         and len(rows)==obj['n_files']==EXPECTED_COUNT,'manifest_count')
    for row in rows:
        need(type(row) is dict,'manifest_row')
        name=row.get('path');relative(name)
        need(name!=MANIFEST_NAME and name not in seen,'duplicate_manifest_path');seen.add(name)
        need(type(row.get('size_bytes')) is int and 0<row['size_bytes']<=16*1024**2,'manifest_member_size')
        for key,length in (('sha256',64),('md5',32),('git_blob_sha1',40)):
            if key in row:need(type(row[key]) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}',row[key]),'manifest_hash_field')
        need('sha256' in row,'manifest_sha256')
        role,sid=row.get('role'),row.get('participant_id')
        if role in ('bold','confounds','participants'):
            key=(sid,role);need(key not in pairs,'duplicate_subject_role');pairs.add(key)
            if role=='participants':need(sid is None and name=='participants.tsv','participants_identity')
            else:
                need(sid in SUBJECTS,'literal_subject')
                suffix='_task-pixar_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz' if role=='bold' else '_task-pixar_desc-confounds_regressors.tsv'
                need(name==sid+suffix,'original_filename')
            need('osf_object_id' in row,'original_provider')
        elif 'osf_object_id' in row:
            need(role=='provenance' and sid is None and name.startswith('provenance/'),
                 'osf_provenance_identity')
        if 'osf_object_id' in row:
            oid,version=row.get('osf_object_id'),row.get('source_version')
            need(type(oid) is str and re.fullmatch('[0-9a-f]{24}',oid) and oid not in objects,'manifest_object')
            objects.add(oid)
            need(type(version) is int and 0<version<10**9 and 'md5' in row,'manifest_version_md5')
        else:
            need(role in ('template','provenance') and sid is None
                 and 'osf_object_id' not in row and 'git_blob_sha1' in row,'document_or_template_identity')
            templates+=role=='template'
        transport_start(row)
    need(pairs=={(sid,role) for sid in SUBJECTS for role in ('bold','confounds')}|{(None,'participants')},
         'closed_original_cohort')
    need(templates==1,'one_anatomical_template')
    need(type(obj.get('total_bytes')) is int and sum(r['size_bytes'] for r in rows)==obj['total_bytes']==EXPECTED_BYTES,
         'manifest_byte_total')
    need(not obj.get('archives'),'unexpected_archive')
    return obj,raw


def hashers(row):
    return {'sha256': hashlib.sha256(), 'md5': hashlib.md5(),
            'git_blob_sha1': hashlib.sha1(f"blob {row['size_bytes']}\0".encode())}


def check_hashes(row, hashes, count):
    need(count == row['size_bytes'], 'source_size_mismatch')
    for key, h in hashes.items():
        if key in row: need(h.hexdigest() == row[key], 'source_' + key + '_mismatch')


def file_identity(path, row, deadline=None):
    hashes, count = hashers(row), 0
    with reader(path) as (f, info):
        need(info.st_size == row['size_bytes'], 'source_size_mismatch')
        while True:
            if deadline is not None: need(time.monotonic() < deadline, 'wall_deadline')
            block = f.read(min(CHUNK, row['size_bytes'] - count + 1))
            if not block: break
            count += len(block); need(count <= row['size_bytes'], 'source_size_overrun')
            for h in hashes.values(): h.update(block)
    check_hashes(row, hashes, count)


def inventory(root, rows, include_manifest=True):
    names = {r['path'] for r in rows} | ({MANIFEST_NAME} if include_manifest else set())
    dirs = {p.as_posix() for n in names for p in PurePosixPath(n).parents if p.as_posix() != '.'}
    found, found_dirs = set(), set()
    for path in safe_path(root).rglob('*'):
        mode, name = path.lstat().st_mode, path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode): need(name in dirs, 'unexpected_directory'); found_dirs.add(name)
        else:
            need(stat.S_ISREG(mode) and name in names, 'unexpected_or_nonregular_file'); found.add(name)
    need(found == names and found_dirs == dirs, 'incomplete_source_inventory')


def verify_staged(data_dir):
    root = safe_path(data_dir)
    need(root.is_dir(), 'source_root_required')
    manifest, _ = load_manifest(root / MANIFEST_NAME)
    inventory(root, manifest['files'])
    for row in manifest['files']: file_identity(root / row['path'], row)
    return manifest


class State:
    def __init__(self):
        self.started = time.monotonic(); self.deadline = self.started + MAX_SECONDS
        self.lock = threading.Lock(); self.cancelled = threading.Event()
        self.bytes = 0; self.requests = 0; self.starts = set(); self.records = []
        self.failure = None

    def fail(self, exc):
        with self.lock:
            if self.failure is None: self.failure = exc
            self.cancelled.set()

    def check(self):
        need(not self.cancelled.is_set(), 'cancelled_after_failure')
        need(time.monotonic() < self.deadline, 'wall_deadline')

    def start(self, key):
        self.check()
        with self.lock:
            need(not self.cancelled.is_set(), 'cancelled_after_failure')
            need(key not in self.starts and len(self.starts) < EXPECTED_COUNT, 'duplicate_or_excess_start'); self.starts.add(key)

    def request(self):
        self.check()
        with self.lock:
            need(not self.cancelled.is_set(), 'cancelled_after_failure')
            need(self.requests < MAX_REQUESTS, 'http_request_cap'); self.requests += 1

    def received(self, block):
        with self.lock:
            self.bytes += len(block); need(self.bytes <= MAX_BYTES, 'aggregate_byte_cap')
        self.check()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args): return None


def open_once(url, timeout):
    headers = {'Accept-Encoding': 'identity', 'User-Agent': 'SOCIALBRAIN-pinned-source/2'}
    request = Request(url, headers=headers)
    try: return build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout)
    except HTTPError as exc: return exc  # Caller closes without reading error/redirect bodies.


def one_header(headers, name, required=False):
    values = headers.get_all(name, [])
    need(len(values) <= 1 and (not required or len(values) == 1), 'missing_or_duplicate_' + name.lower())
    return values[0] if values else None


def copy_stream(stream, target, row, state, network=False):
    hashes, count = hashers(row), 0
    target.parent.mkdir(parents=True, exist_ok=True)
    need(shutil.disk_usage(target.parent).free >= MIN_FREE_BYTES + row['size_bytes'], 'disk_reserve')
    partial = target.with_name(target.name + '.partial')
    read = stream.read1 if network else stream.read
    with partial.open('xb') as out:
        while True:
            state.check(); block = read(min(CHUNK, row['size_bytes'] - count + 1))
            need(isinstance(block, bytes), 'invalid_chunk')
            if not block: break
            count += len(block)
            if network: state.received(block)
            need(count <= row['size_bytes'], 'source_size_overrun')
            out.write(block)
            for h in hashes.values(): h.update(block)
    check_hashes(row, hashes, count); state.check()
    partial.chmod(0o444); os.link(partial, target, follow_symlinks=False); partial.unlink()


def download(row, target, state, transport=open_once):
    key = row['path']; state.start(key)
    record = {'path': key, 'status': 'started', 'redirects': []}
    with state.lock: state.records.append(record)
    print(json.dumps({'source_start': key}), flush=True)
    response = None
    try:
        url, seen = transport_start(row), set()
        record.update(canonical_source_endpoint=endpoint(row['source_url'], row, initial=True),
                      canonical_version_api_url=row.get('canonical_version_api_url'),
                      source_version=row.get('source_version'), endpoint_start=endpoint(url, row))
        for hop in range(MAX_REDIRECTS + 1):
            state.check(); safe = endpoint(url, row)
            need(url not in seen, 'redirect_loop'); seen.add(url)
            record['last_endpoint'] = safe
            state.request()
            remaining = state.deadline - time.monotonic(); need(remaining > 0, 'wall_deadline')
            response = transport(url, min(SOCKET_SECONDS, remaining))
            need(response.geturl() == url, 'implicit_redirect_refused')
            code = int(response.code); record['http_status'] = code
            need(sum(len(k) + len(v) for k, v in response.headers.items()) <= 65536, 'response_headers_cap')
            if code in (301, 302, 303, 307, 308):
                location = one_header(response.headers, 'Location', True)
                response.close(); response = None
                need(hop < MAX_REDIRECTS, 'redirect_refused')
                candidate = urljoin(url, location)
                record['redirects'].append(endpoint(candidate, row)); url = candidate; continue
            need(code == 200, 'http_status')
            need(one_header(response.headers, 'Transfer-Encoding') is None, 'transfer_encoding')
            length = one_header(response.headers, 'Content-Length', required=True)
            if length is not None:
                need(re.fullmatch('[0-9]{1,12}', length) and int(length) == row['size_bytes'], 'content_length_mismatch')
            need((one_header(response.headers, 'Content-Encoding') or 'identity').lower() == 'identity', 'content_encoding')
            content_type = (one_header(response.headers, 'Content-Type', True) or '').split(';')[0].lower().strip()
            need(content_type not in ('text/html', 'application/xhtml+xml'), 'unexpected_html_body')
            copy_stream(response, target, row, state, network=True)
            record.update(status='verified', size_bytes=row['size_bytes'], sha256=row['sha256'])
            print(json.dumps({'source_complete': key, 'bytes': row['size_bytes']}), flush=True)
            return
        raise Refusal('redirect_limit')
    except Exception as exc:
        record.update(status='failed', error_type=type(exc).__name__, reason=str(exc) if isinstance(exc, Refusal) else 'transport_or_io_error')
        state.fail(exc); print(json.dumps(record), flush=True); raise
    finally:
        if response is not None: response.close()


def parallel_download(jobs, state, transport):
    iterator = iter(jobs)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        active = set()
        for _ in range(WORKERS):
            job = next(iterator, None)
            if job is not None: active.add(pool.submit(download, *job, state, transport))
        while active:
            done, active = wait(active, return_when=FIRST_COMPLETED)
            failure = None
            for future in done:
                try: future.result()
                except Exception as exc: failure = failure or exc; state.cancelled.set()
            if failure is not None:
                for future in active: future.cancel()
                raise state.failure or failure
            for _ in done:
                if state.cancelled.is_set(): break
                job = next(iterator, None)
                if job is not None: active.add(pool.submit(download, *job, state, transport))


def publish(pending, destination):
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(-100, os.fsencode(pending), -100, os.fsencode(destination), 1) != 0:
        raise OSError(ctypes.get_errno(), 'atomic_publication_refused')


def stage(destination, work_dir, manifest_path, source_dir=None, transport=open_once):
    dest, work, manifest_path = map(safe_path, (destination, work_dir, manifest_path))
    source = safe_path(source_dir) if source_dir is not None else None
    disjoint(dest, work)
    for protected in (manifest_path, source, Path(__file__).absolute().parent):
        if protected is not None:
            disjoint(dest, protected); disjoint(work, protected)
    need(not os.path.lexists(dest) and not os.path.lexists(work), 'fresh_destination_and_work_required')
    manifest, manifest_raw = load_manifest(manifest_path)
    if source is not None: need(source.is_dir(), 'local_source_required')
    # Validate every relationship and reserve before any directory mutation.
    existing = work.parent
    while not existing.exists(): existing = existing.parent
    need(shutil.disk_usage(existing).free >= MIN_FREE_BYTES + EXPECTED_BYTES, 'disk_reserve')
    dest.parent.mkdir(parents=True, exist_ok=True); work.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(mode=0o755); pending = work / 'pending'; pending.mkdir(mode=0o755)
    state = State()
    report = {'status': 'running', 'source_manifest_sha256': MANIFEST_SHA256, 'automatic_retries': 0,
        'mode': 'verified_local_copy' if source is not None else 'pinned_public_acquisition',
        'source_payload_parsed': False, 'max_workers': WORKERS, 'max_seconds': MAX_SECONDS,
        'max_network_bytes': MAX_BYTES, 'max_http_requests': MAX_REQUESTS, 'min_free_disk_bytes': MIN_FREE_BYTES}
    write_json(work / 'attempt.json', report)
    try:
        if source is not None:
            # Do not copy one source byte until the entire local input passed.
            inventory(source, manifest['files'], include_manifest=(source / MANIFEST_NAME).exists())
            if (source / MANIFEST_NAME).exists(): load_manifest(source / MANIFEST_NAME)
            for row in manifest['files']: file_identity(source / row['path'], row, state.deadline)
            for row in manifest['files']:
                with reader(source / row['path']) as (f, _): copy_stream(f, pending / row['path'], row, state)
        else:
            jobs = [(r, pending / r['path']) for r in manifest['files']]
            parallel_download(jobs, state, transport)
        with (pending / MANIFEST_NAME).open('xb') as f: f.write(manifest_raw)
        (pending / MANIFEST_NAME).chmod(0o444)
        inventory(pending, manifest['files'])
        for row in manifest['files']: file_identity(pending / row['path'], row, state.deadline)
        for path in pending.rglob('*'):
            if path.is_dir(): path.chmod(0o755)
        state.check(); publish(pending, dest)
        report.update(status='ok', source_file_count=len(manifest['files']), source_bytes=manifest['total_bytes'])
    except Exception as exc:
        state.cancelled.set()
        report.update(status='failed', error_type=type(exc).__name__, reason=str(exc) if isinstance(exc, Refusal) else 'transport_or_io_error')
        raise
    finally:
        report.update(network_body_bytes=state.bytes, network_requests=state.requests, transfer_starts=len(state.starts),
                      transfers=sorted(state.records, key=lambda r: r['path']), elapsed_seconds=time.monotonic() - state.started)
        write_json(work / 'result.json', report)
        print(json.dumps(report, sort_keys=True, allow_nan=False), flush=True)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', default='/app/source_manifest.json')
    p.add_argument('--destination', default='/app/data/socialbrain')
    p.add_argument('--work-dir', default='/source_capture')
    p.add_argument('--source-dir')
    p.add_argument('--verify-existing', action='store_true')
    args = p.parse_args(argv)
    old = signal.getsignal(signal.SIGALRM)
    def alarm(*_): raise Refusal('wall_deadline')
    need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'existing_alarm')
    signal.signal(signal.SIGALRM, alarm); signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        if args.verify_existing:
            manifest = verify_staged(args.destination)
            print(json.dumps({'status': 'ok', 'mode': 'offline_verify_only', 'source_file_count': len(manifest['files']),
                              'source_bytes': manifest['total_bytes'], 'source_manifest_sha256': MANIFEST_SHA256}))
        else: stage(args.destination, args.work_dir, args.manifest, args.source_dir)
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'reason': str(exc) if isinstance(exc, Refusal) else 'transport_or_io_error',
                          'error_type': type(exc).__name__}), flush=True)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, old)


if __name__ == '__main__':
    raise SystemExit(main())
