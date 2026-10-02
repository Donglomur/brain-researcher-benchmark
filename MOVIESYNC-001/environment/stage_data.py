"""MOVIESYNC checksum-pinned original source staging; verification is offline.

No numerical payload parsing, hidden caches, automatic retry or overwrite.
Source acquisition/copies occur only through the CLI staging mode; failures
retain the exclusive work directory and partial files outside the runtime data.
OSF transfers start at the official versioned Waterbutler object endpoint;
canonical OSF manifest locators remain unchanged and are recorded separately.
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
import stat
import struct
import threading
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import zipfile

MANIFEST_SHA256 = '773af02ee4f4ca1883565f298cad351fadef302fb1f11fef6dd65cc8c55c13d6'
MANIFEST_NAME = 'source_manifest.json'
EXPECTED_COUNT, EXPECTED_BYTES = 87, 270356915
MAX_SECONDS, SOCKET_SECONDS, MAX_BYTES, WORKERS = 600, 30, 280000000, 2
CHUNK, MAX_REDIRECTS = 65536, 5


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
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


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


def endpoint(url, row, initial=False):
    p = urlsplit(url)
    need(p.scheme == 'https' and p.username is None and p.password is None
         and p.port in (None, 443) and not p.fragment, 'endpoint_rejected')
    if initial: need(url == row['source_url'], 'initial_url_mismatch')
    if row.get('archive_id') == 'msdl_author_zip' and 'required_members' in row:
        need(url == row['source_url'] and p.hostname == 'team.inria.fr' and not p.query, 'archive_redirect_rejected')
    elif 'source_guid' in row:
        if p.hostname == 'osf.io':
            need(p.path in (f"/download/{row['source_guid']}", f"/download/{row['source_guid']}/")
                 and parse_qs(p.query).get('revision') == [str(row['source_version'])], 'osf_revision_or_path')
        elif p.hostname == 'files.osf.io':
            expected = f"/v1/resources/5hju4/providers/osfstorage/{row['osf_object_id']}"
            need(p.path in (expected, expected + '/') and parse_qs(p.query).get('revision') == [str(row['source_version'])],
                 'waterbutler_revision_or_path')
        elif p.hostname == 'storage.googleapis.com':
            need(p.path == '/cos-osf-prod-files-us-east1/' + row['sha256'], 'storage_object')
        else: raise Refusal('endpoint_rejected')
    else:
        need(p.hostname == 'raw.githubusercontent.com' and not p.query and url == row['source_url'], 'immutable_document_url')
        need(re.fullmatch('[0-9a-f]{40}', row['source_commit']) and row['source_commit'] in p.path.split('/'), 'document_commit')
    return {'host': p.hostname, 'path': p.path}  # Never disclose signed query values.


def transport_start(row):
    """Choose one initial locator, never a fallback or a cached signed URL."""
    endpoint(row['source_url'], row, initial=True)
    if 'source_guid' in row:
        url = (f"https://files.osf.io/v1/resources/5hju4/providers/osfstorage/{row['osf_object_id']}"
               f"?revision={row['source_version']}")
    else:
        url = row['source_url']
    endpoint(url, row)
    return url


def load_manifest(path):
    with reader(path) as (f, info):
        need(info.st_size <= 262144, 'manifest_size_cap'); raw = f.read(262145)
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, 'manifest_digest')
    obj = strict_json(raw); rows = obj['files']; seen = set()
    need(len(rows) == obj['n_files'] == EXPECTED_COUNT, 'manifest_count')
    for row in rows:
        relative(row['path'])
        need(row['path'] != MANIFEST_NAME and row['path'] not in seen, 'duplicate_manifest_path'); seen.add(row['path'])
        need(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= 64 * 1024**2, 'manifest_member_size')
        for k, n in (('sha256', 64), ('md5', 32), ('git_blob_sha1', 40)):
            if k in row: need(isinstance(row[k], str) and re.fullmatch('[0-9a-f]{' + str(n) + '}', row[k]), 'manifest_hash_field')
        need('sha256' in row, 'missing_sha256')
        if 'archive_id' not in row: endpoint(row['source_url'], row, True)
    need(sum(r['size_bytes'] for r in rows) == obj['total_bytes'] == EXPECTED_BYTES, 'manifest_byte_total')
    need(len(obj['archives']) == 1, 'archive_count')
    archive = obj['archives'][0]; endpoint(archive['source_url'], archive, True)
    archived = [r for r in rows if 'archive_id' in r]
    need(len(archived) == 3 and {r['archive_member'] for r in archived} == set(archive['required_members'])
         and all(r['archive_id'] == archive['archive_id'] for r in archived), 'archive_membership')
    return obj, raw


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

    def check(self):
        need(not self.cancelled.is_set(), 'cancelled_after_failure')
        need(time.monotonic() < self.deadline, 'wall_deadline')

    def start(self, key):
        self.check()
        with self.lock:
            need(key not in self.starts and len(self.starts) < 85, 'duplicate_or_excess_start'); self.starts.add(key)

    def received(self, block):
        with self.lock:
            self.bytes += len(block); need(self.bytes <= MAX_BYTES, 'aggregate_byte_cap')
        self.check()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args): return None


def open_once(url, timeout, etag=None):
    headers = {'Accept-Encoding': 'identity', 'User-Agent': 'MOVIESYNC-pinned-source/1'}
    if etag is not None: headers['If-Match'] = etag
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
    key = row.get('path', 'MSDL_rois.zip'); state.start(key)
    record = {'path': key, 'status': 'started', 'redirects': []}
    with state.lock: state.records.append(record)
    print(json.dumps({'source_start': key}), flush=True)
    response = None
    try:
        url, seen = transport_start(row), set()
        record.update(canonical_source_endpoint=endpoint(row['source_url'], row, initial=True),
                      source_version=row.get('source_version'), endpoint_start=endpoint(url, row))
        for hop in range(MAX_REDIRECTS + 1):
            state.check(); safe = endpoint(url, row)
            need(url not in seen, 'redirect_loop'); seen.add(url)
            record['last_endpoint'] = safe
            with state.lock: state.requests += 1
            response = transport(url, min(SOCKET_SECONDS, state.deadline - time.monotonic()), row.get('etag'))
            code = int(response.code); record['http_status'] = code
            need(sum(len(k) + len(v) for k, v in response.headers.items()) <= 65536, 'response_headers_cap')
            if code in (301, 302, 303, 307, 308):
                location = one_header(response.headers, 'Location', True)
                response.close(); response = None
                need('required_members' not in row and hop < MAX_REDIRECTS, 'redirect_refused')
                candidate = urljoin(url, location)
                record['redirects'].append(endpoint(candidate, row)); url = candidate; continue
            need(code == 200, 'http_status')
            length = one_header(response.headers, 'Content-Length', required='required_members' not in row)
            if length is not None:
                need(re.fullmatch('[0-9]{1,12}', length) and int(length) == row['size_bytes'], 'content_length_mismatch')
            need((one_header(response.headers, 'Content-Encoding') or 'identity').lower() == 'identity', 'content_encoding')
            content_type = (one_header(response.headers, 'Content-Type', True) or '').split(';')[0].lower().strip()
            need(content_type not in ('text/html', 'application/xhtml+xml'), 'unexpected_html_body')
            if 'required_members' in row:
                need(content_type in ('application/zip', 'application/x-zip-compressed', 'application/octet-stream'), 'archive_content_type')
                need(one_header(response.headers, 'ETag', True) == row['etag'], 'archive_etag')
            copy_stream(response, target, row, state, network=True)
            record.update(status='verified', size_bytes=row['size_bytes'], sha256=row['sha256'])
            print(json.dumps({'source_complete': key, 'bytes': row['size_bytes']}), flush=True)
            return
        raise Refusal('redirect_limit')
    except Exception as exc:
        record.update(status='failed', error_type=type(exc).__name__, reason=str(exc) if isinstance(exc, Refusal) else 'transport_or_io_error')
        state.cancelled.set(); print(json.dumps(record), flush=True); raise
    finally:
        if response is not None: response.close()


def zip_inventory(path):
    with reader(path) as (f, info):
        f.seek(max(0, info.st_size - 65557)); tail = f.read(65557)
    pos = tail.rfind(b'PK\x05\x06')
    need(pos >= 0 and pos + 22 <= len(tail), 'zip_end_record')
    _, disk, start_disk, local_n, total_n, size, offset, comment = struct.unpack('<4s4H2LH', tail[pos:pos + 22])
    need(pos + 22 + comment == len(tail) and disk == start_disk == 0 and local_n == total_n, 'zip_end_record_bounds')
    need(0 < total_n <= 32 and size <= 131072 and offset + size == max(0, info.st_size - 65557) + pos, 'zip_central_cap')
    rows, seen, total = [], set(), 0
    with zipfile.ZipFile(path) as z:
        need(len(z.infolist()) == total_n, 'zip_member_count')
        for item in z.infolist():
            name = item.filename; name_no_slash = name[:-1] if item.is_dir() else name
            relative(name_no_slash)
            need(item.orig_filename == name and name_no_slash not in seen, 'zip_duplicate_or_null_name'); seen.add(name_no_slash)
            kind = stat.S_IFMT(item.external_attr >> 16)
            need(kind in ({0, stat.S_IFDIR} if item.is_dir() else {0, stat.S_IFREG}), 'zip_nonregular_member')
            need(not item.flag_bits & 1 and item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'zip_encoding')
            need(not item.is_dir() or item.file_size == 0, 'zip_directory_payload')
            total += item.file_size; need(total <= 64 * 1024**2, 'zip_expanded_cap')
            rows.append(dict(path=name, size_bytes=item.file_size, compressed_bytes=item.compress_size,
                             crc32=f'{item.CRC:08x}', directory=item.is_dir()))
    files = {r['path'] for r in rows if not r['directory']}
    need(not any(p.as_posix() in files for name in files for p in PurePosixPath(name).parents), 'zip_file_directory_collision')
    return rows


def extract_archive(path, archive, rows, pending, state):
    state.check(); file_identity(path, archive, state.deadline)
    actual = zip_inventory(path)
    need(sorted(actual, key=lambda r: r['path']) == sorted(archive['inventory'], key=lambda r: r['path']), 'zip_inventory_mismatch')
    with zipfile.ZipFile(path) as z:
        for row in rows:
            state.check()
            with z.open(row['archive_member']) as source:
                copy_stream(source, pending / row['path'], row, state)


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
                raise failure
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
    for protected in (manifest_path.parent, source):
        if protected is not None:
            disjoint(dest, protected); disjoint(work, protected)
    need(not os.path.lexists(dest) and not os.path.lexists(work), 'fresh_destination_and_work_required')
    manifest, manifest_raw = load_manifest(manifest_path)
    if source is not None: need(source.is_dir(), 'local_source_required')
    # Validate every relationship before any directory mutation.
    dest.parent.mkdir(parents=True, exist_ok=True); work.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(mode=0o755); pending = work / 'pending'; pending.mkdir(mode=0o755)
    state = State()
    report = {'status': 'running', 'source_manifest_sha256': MANIFEST_SHA256, 'automatic_retries': 0,
        'mode': 'verified_local_copy' if source is not None else 'pinned_public_acquisition',
        'source_payload_parsed': False, 'max_workers': WORKERS, 'max_seconds': MAX_SECONDS, 'max_network_bytes': MAX_BYTES}
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
            archive = manifest['archives'][0]; archive_path = work / 'MSDL_rois.zip'
            jobs = [(r, pending / r['path']) for r in manifest['files'] if 'archive_id' not in r]
            jobs.append((archive, archive_path))
            parallel_download(jobs, state, transport)
            extract_archive(archive_path, archive, [r for r in manifest['files'] if 'archive_id' in r], pending, state)
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
    p.add_argument('--manifest', default=str(Path(__file__).absolute().with_name(MANIFEST_NAME)))
    p.add_argument('--destination', default='/app/data/moviesync')
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
