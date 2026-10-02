"""FCVAR checksum-pinned original staging; no scientific payload decoding.

The cold route starts exactly 32 archive and two document requests, once each.
It authenticates complete archive bytes before bounded full tar inventory and
selected-member extraction. Offline verification never writes. An external hard
process timeout is required in addition to the internal wall/socket deadlines.
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
import ctypes
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import tarfile
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MANIFEST_SHA256 = 'a3d0f6aa1901361c55e29cf6e09a5ee31c8c084d52e4ba7e9a1f7ccddf00609f'
MANIFEST_NAME = 'source_manifest.json'
EXPECTED_COUNT, EXPECTED_BYTES = 67, 1359777527
MAX_SECONDS, SOCKET_SECONDS, MAX_BYTES, WORKERS = 1500, 30, 2 * 1024**3, 2
CHUNK, MAX_STARTS = 65536, 34
MAX_MEMBER_BYTES, MAX_ARCHIVE_BYTES = 128 * 1024**2, 128 * 1024**2
MAX_EXPANDED_BYTES, MAX_MEMBERS = 256 * 1024**2, 128
SUBJECT_ARCHIVES = dict(zip(
    ('7782 7783 7784 7785 7786 7787 7788 7789 7790 7791 7792 7793 7796 7798 7799 '
     '7800 7802 7803 7807 7808 7809 7812 7813 7814 7815 7816 7817 7818 7819 7821').split(),
    ('0010042 0010064 0010128 0021019 0023008 0023012 0027011 0027018 0027034 0027037 '
     '1019436 1206380 1552181 1679142 2014113 2497695 3007585 3154996 3699991 3884955 '
     '3902469 4046678 4134561 4164316 4275075 6115230 7774305 8409791 8697774 9750701').split()))
ARCHIVE_FILENAMES = {key: f'adhd40_{sid}.tgz' for key, sid in SUBJECT_ARCHIVES.items()}
ARCHIVE_FILENAMES.update({'7781': 'adhd40_metadata.tgz', '9902': 'HarvardOxford.tgz'})
DOC_COMMIT = '8de9de0cabc4170d6c6c4be8c709818cffba7a62'
DOC_URLS = {f'https://raw.githubusercontent.com/nilearn/nilearn/{DOC_COMMIT}/nilearn/datasets/description/{name}.rst'
            for name in ('adhd', 'harvard_oxford')}
OTHER_ROLES = {'cohort_ids', 'phenotype_metadata', 'slice_timing_metadata', 'atlas_image',
               'atlas_labels', 'provenance_adhd_notice', 'provenance_ho_notice'}


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
            if p != path:
                need(stat.S_ISDIR(mode), 'non_directory_ancestor')
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
    path = safe_path(path)
    before = path.lstat()
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
            need(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    def bad(_):
        raise Refusal('nonfinite_json')
    obj = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    def check(value):
        if isinstance(value, float):
            need(math.isfinite(value), 'nonfinite_json')
        elif isinstance(value, (list, dict)):
            for item in (value.values() if isinstance(value, dict) else value):
                check(item)
    check(obj)
    return obj


def write_json(path, obj):
    with safe_path(path).open('x') as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')


def endpoint(url, row):
    p = urlsplit(url)
    need(p.scheme == 'https' and p.username is None and p.password is None
         and p.port in (None, 443) and not p.fragment and not p.query, 'endpoint_rejected')
    need(url == row['source_url'], 'exact_source_url')
    if row.get('format') == 'tar.gz':
        key = row['archive_id']
        need(key in ARCHIVE_FILENAMES, 'archive_id')
        expected = f'https://www.nitrc.org/frs/download.php/{key}/{ARCHIVE_FILENAMES[key]}'
        need(url == expected, 'archive_url')
    else:
        need(url in DOC_URLS and row.get('source_commit') == DOC_COMMIT, 'document_commit_url')
    return {'host': p.hostname, 'path': p.path}


def validate_hash_fields(row, cap):
    need(type(row.get('size_bytes')) is int and 0 < row['size_bytes'] <= cap, 'manifest_member_size')
    need('sha256' in row, 'missing_sha256')
    for key, n in (('sha256', 64), ('md5', 32), ('git_blob_sha1', 40)):
        if key in row:
            need(isinstance(row[key], str) and re.fullmatch('[0-9a-f]{' + str(n) + '}', row[key]), 'manifest_hash_field')


def archive_jobs(manifest):
    # Normalize transport fields privately; never rewrite the public manifest.
    return [dict(a, source_url=a['url'], format='tar.gz') for a in manifest['archives']]


def load_manifest(path):
    with reader(path) as (f, info):
        need(info.st_size <= 262144, 'manifest_size_cap')
        raw = f.read(262145)
    need(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, 'manifest_digest')
    obj = strict_json(raw)
    need(obj['schema_version'] == 'fcvar-source-v2' and obj['task_id'] == 'FCVAR-001', 'manifest_schema')
    need(obj['runtime_data_directory'] == '/app/data/fcvar' and obj['source_files_directory'] == '.', 'manifest_layout')
    need(obj['participant_ids'] == sorted(SUBJECT_ARCHIVES.values()), 'manifest_cohort')
    rows, seen, keys = obj['files'], set(), set()
    need(len(rows) == obj['source_file_count'] == EXPECTED_COUNT, 'manifest_count')
    for row in rows:
        relative(row['path'])
        need(row['path'] != MANIFEST_NAME and row['path'] not in seen, 'duplicate_manifest_path')
        seen.add(row['path'])
        validate_hash_fields(row, MAX_MEMBER_BYTES)
        key = row.get('participant_id'), row['role']
        need(key not in keys, 'duplicate_role_identity')
        keys.add(key)
        if 'archive_id' not in row:
            endpoint(row['source_url'], row)
    need(not any(p.as_posix() in seen for n in seen for p in PurePosixPath(n).parents), 'manifest_path_collision')
    wanted = {(sid, role) for sid in SUBJECT_ARCHIVES.values() for role in ('bold', 'confounds')}
    wanted |= {(None, role) for role in OTHER_ROLES}
    need(keys == wanted, 'manifest_roles')
    need(sum(r['size_bytes'] for r in rows) == obj['source_bytes'] == EXPECTED_BYTES, 'manifest_byte_total')
    archives = archive_jobs(obj)
    need(len(archives) == len(ARCHIVE_FILENAMES) and {a['archive_id'] for a in archives} == set(ARCHIVE_FILENAMES), 'archive_count')
    covered = set()
    for archive in archives:
        validate_hash_fields(archive, MAX_ARCHIVE_BYTES)
        endpoint(archive['source_url'], archive)
        need(archive['filename'] == ARCHIVE_FILENAMES[archive['archive_id']], 'archive_filename')
        selected = [r for r in rows if r.get('archive_id') == archive['archive_id']]
        declared = archive.get('members', archive.get('required_members', []))
        pairs = [(r['archive_member'], r['path']) for r in declared]
        expected_n = 3 if archive['archive_id'] == '7781' else 2
        need(len(pairs) == len(selected) == expected_n and len(set(pairs)) == len(pairs)
             and set(pairs) == {(r['archive_member'], r['path']) for r in selected}, 'archive_membership')
        need(len({r['archive_member'] for r in selected}) == len(selected), 'archive_member_duplicate')
        for row in selected:
            relative(row['archive_member'])
            need(row['source_url'] == archive['source_url'], 'member_archive_url')
            if archive['archive_id'] in SUBJECT_ARCHIVES:
                need(row['participant_id'] == SUBJECT_ARCHIVES[archive['archive_id']], 'member_archive_subject')
        for row in declared:
            original = next(r for r in selected if r['path'] == row['path'])
            for key in ('size_bytes', 'sha256'):
                if key in row:
                    need(row[key] == original[key], 'archive_member_pin')
        covered.update(r['path'] for r in selected)
    need(covered == {r['path'] for r in rows if 'archive_id' in r}, 'archive_coverage')
    docs = [r for r in rows if 'archive_id' not in r]
    need(len(docs) == 2 and {r['source_url'] for r in docs} == DOC_URLS, 'direct_document_count')
    need(sum(a['size_bytes'] for a in archives) + sum(r['size_bytes'] for r in docs) <= MAX_BYTES, 'transfer_byte_cap')
    return obj, raw


def hashers(row):
    return {'sha256': hashlib.sha256(), 'md5': hashlib.md5(),
            'git_blob_sha1': hashlib.sha1(f"blob {row['size_bytes']}\0".encode())}


def check_hashes(row, hashes, count):
    need(count == row['size_bytes'], 'source_size_mismatch')
    for key, h in hashes.items():
        if key in row:
            need(h.hexdigest() == row[key], 'source_' + key + '_mismatch')


def buffer_identity(raw, row):
    hashes = hashers(row)
    for h in hashes.values():
        h.update(raw)
    check_hashes(row, hashes, len(raw))


def file_identity(path, row, deadline=None):
    hashes, count = hashers(row), 0
    with reader(path) as (f, info):
        need(info.st_size == row['size_bytes'], 'source_size_mismatch')
        while True:
            if deadline is not None:
                need(time.monotonic() < deadline, 'wall_deadline')
            block = f.read(min(CHUNK, row['size_bytes'] - count + 1))
            if not block:
                break
            count += len(block)
            need(count <= row['size_bytes'], 'source_size_overrun')
            for h in hashes.values():
                h.update(block)
    check_hashes(row, hashes, count)


def inventory(root, rows, include_manifest=True):
    names = {r['path'] for r in rows} | ({MANIFEST_NAME} if include_manifest else set())
    dirs = {p.as_posix() for n in names for p in PurePosixPath(n).parents if p.as_posix() != '.'}
    found, found_dirs = set(), set()
    need(safe_path(root).is_dir(), 'source_root_required')
    for path in root.rglob('*'):
        mode, name = path.lstat().st_mode, path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):
            need(name in dirs, 'unexpected_directory')
            found_dirs.add(name)
        else:
            need(stat.S_ISREG(mode) and name in names, 'unexpected_or_nonregular_file')
            found.add(name)
    need(found == names and found_dirs == dirs, 'incomplete_source_inventory')


def verify_staged(data_dir):
    root = safe_path(data_dir)
    manifest, _ = load_manifest(root / MANIFEST_NAME)
    inventory(root, manifest['files'])
    for row in manifest['files']:
        file_identity(root / row['path'], row)
    return manifest


class State:
    def __init__(self):
        self.started = time.monotonic()
        self.deadline = self.started + MAX_SECONDS
        self.lock, self.cancelled = threading.Lock(), threading.Event()
        self.bytes, self.requests, self.starts, self.records = 0, 0, set(), []

    def check(self):
        need(not self.cancelled.is_set(), 'cancelled_after_failure')
        need(time.monotonic() < self.deadline, 'wall_deadline')

    def start(self, key):
        self.check()
        with self.lock:
            need(key not in self.starts and len(self.starts) < MAX_STARTS, 'duplicate_or_excess_start')
            self.starts.add(key)

    def received(self, block):
        with self.lock:
            self.bytes += len(block)
            need(self.bytes <= MAX_BYTES, 'aggregate_byte_cap')
        self.check()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def open_once(url, timeout):
    request = Request(url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'FCVAR-pinned-source/1'})
    try:
        return build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout)
    except HTTPError as exc:
        return exc  # Caller closes without reading any redirect or error body.


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
            state.check()
            block = read(min(CHUNK, row['size_bytes'] - count + 1))
            need(isinstance(block, bytes), 'invalid_chunk')
            if not block:
                break
            count += len(block)
            if network:
                state.received(block)
            need(count <= row['size_bytes'], 'source_size_overrun')
            out.write(block)
            for h in hashes.values():
                h.update(block)
    check_hashes(row, hashes, count)
    state.check()
    partial.chmod(0o444)
    os.link(partial, target, follow_symlinks=False)
    partial.unlink()


def download(row, target, state, transport=open_once):
    key = row.get('path', row.get('archive_id'))
    state.start(key)
    record = {'path': key, 'status': 'started', 'redirects': 0}
    with state.lock:
        state.records.append(record)
    print(json.dumps({'source_start': key}), flush=True)
    response = None
    try:
        url = row['source_url']
        record['endpoint_start'] = endpoint(url, row)
        state.check()
        with state.lock:
            state.requests += 1
        response = transport(url, min(SOCKET_SECONDS, state.deadline - time.monotonic()))
        record['http_status'] = int(response.code)
        need(response.geturl() == url, 'unexpected_final_url')
        need(sum(len(k) + len(v) for k, v in response.headers.items()) <= 65536, 'response_headers_cap')
        need(response.code == 200, 'http_status_no_redirects')
        length = one_header(response.headers, 'Content-Length', True)
        need(re.fullmatch('[0-9]{1,12}', length) and int(length) == row['size_bytes'], 'content_length_mismatch')
        need((one_header(response.headers, 'Content-Encoding') or 'identity').lower() == 'identity', 'content_encoding')
        kind = one_header(response.headers, 'Content-Type', True).split(';')[0].strip().lower()
        accepted = ({'application/force-download', 'application/octet-stream', 'application/gzip', 'application/x-gzip'}
                    if row.get('format') == 'tar.gz' else {'text/plain', 'application/octet-stream'})
        need(kind in accepted, 'content_type')
        copy_stream(response, target, row, state, network=True)
        record.update(status='verified', size_bytes=row['size_bytes'], sha256=row['sha256'])
        print(json.dumps({'source_complete': key, 'bytes': row['size_bytes']}), flush=True)
    except BaseException as exc:
        record.update(status='failed', error_type=type(exc).__name__,
                      reason=str(exc) if isinstance(exc, Refusal) else 'transport_or_io_error')
        state.cancelled.set()
        print(json.dumps(record), flush=True)
        raise
    finally:
        if response is not None:
            response.close()


def tar_inventory(raw, state):
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode='rb') as source:
        state.check()
        expanded = source.read(MAX_EXPANDED_BYTES + 1)
        need(len(expanded) <= MAX_EXPANDED_BYTES, 'tar_expanded_cap')
        need(source.read(1) == b'', 'tar_expanded_cap')
    rows, seen, end, total = [], {}, 0, 0
    with tarfile.open(fileobj=io.BytesIO(expanded), mode='r:') as archive:
        for member in archive:
            state.check()
            name = member.name[:-1] if member.isdir() and member.name.endswith('/') else member.name
            relative(name)
            need(member.isfile() or member.isdir(), 'tar_nonregular_member')
            need(not member.issparse(), 'tar_sparse_member')
            need(name not in seen and member.size >= 0, 'tar_duplicate_or_negative_size')
            need(not member.isdir() or member.size == 0, 'tar_directory_payload')
            total += member.size
            need(len(rows) < MAX_MEMBERS and total <= MAX_EXPANDED_BYTES, 'tar_inventory_cap')
            seen[name] = 'directory' if member.isdir() else 'file'
            rows.append((name, member))
            end = max(end, member.offset_data + ((member.size + 511) // 512) * 512)
    need(rows and len(expanded) >= end + 1024, 'tar_terminator_missing')
    for offset in range(end, len(expanded), CHUNK):
        state.check()
        need(not any(memoryview(expanded)[offset:offset + CHUNK]), 'nonzero_tar_tail')
    need(not any(seen.get(p.as_posix()) == 'file' for name in seen for p in PurePosixPath(name).parents),
         'tar_file_directory_collision')
    return expanded, dict(rows)


def extract_tar(path, archive, rows, pending, state):
    state.check()
    with reader(path) as (f, info):
        need(info.st_size == archive['size_bytes'] <= MAX_ARCHIVE_BYTES, 'archive_size')
        raw = f.read(MAX_ARCHIVE_BYTES + 1)
    buffer_identity(raw, archive)
    # The exact authenticated immutable buffer, not a reopened pathname, is parsed.
    expanded, members = tar_inventory(raw, state)
    for row in rows:
        state.check()
        member = members.get(row['archive_member'])
        need(member is not None and member.isfile() and member.size == row['size_bytes'], 'tar_selected_size_type')
    for row in rows:
        member = members[row['archive_member']]
        with io.BytesIO(memoryview(expanded)[member.offset_data:member.offset_data + member.size]) as source:
            copy_stream(source, pending / row['path'], row, state)


def parallel_download(jobs, state, transport):
    iterator = iter(jobs)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        active = set()
        for _ in range(WORKERS):
            job = next(iterator, None)
            if job is not None:
                active.add(pool.submit(download, *job, state, transport))
        while active:
            done, active = wait(active, return_when=FIRST_COMPLETED)
            failure = None
            for future in done:
                try:
                    future.result()
                except BaseException as exc:
                    failure = failure or exc
                    state.cancelled.set()
            if failure is not None:
                for future in active:
                    future.cancel()
                raise failure
            for _ in done:
                if state.cancelled.is_set():
                    break
                job = next(iterator, None)
                if job is not None:
                    active.add(pool.submit(download, *job, state, transport))


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
            disjoint(dest, protected)
            disjoint(work, protected)
    need(not os.path.lexists(dest) and not os.path.lexists(work), 'fresh_destination_and_work_required')
    manifest, raw = load_manifest(manifest_path)
    if source is not None:
        need(source.is_dir(), 'local_source_required')
    # All path relationships are checked before any mkdir.
    dest.parent.mkdir(parents=True, exist_ok=True)
    work.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(mode=0o755)
    pending = work / 'pending'
    pending.mkdir(mode=0o755)
    state = State()
    report = dict(status='running', source_manifest_sha256=MANIFEST_SHA256, automatic_retries=0, redirects=0,
                  mode='verified_local_copy' if source is not None else 'pinned_public_acquisition',
                  source_payload_parsed=False, max_workers=WORKERS, max_seconds=MAX_SECONDS, max_network_bytes=MAX_BYTES)
    write_json(work / 'attempt.json', report)
    try:
        if source is not None:
            has_manifest = os.path.lexists(source / MANIFEST_NAME)
            inventory(source, manifest['files'], has_manifest)
            if has_manifest:
                load_manifest(source / MANIFEST_NAME)
            for row in manifest['files']:
                file_identity(source / row['path'], row, state.deadline)
            for row in manifest['files']:
                with reader(source / row['path']) as (f, _):
                    copy_stream(f, pending / row['path'], row, state)
        else:
            archives = archive_jobs(manifest)
            paths = {a['archive_id']: work / (a['archive_id'] + '.tgz') for a in archives}
            jobs = [(r, pending / r['path']) for r in manifest['files'] if 'archive_id' not in r]
            jobs += [(a, paths[a['archive_id']]) for a in archives]
            parallel_download(jobs, state, transport)
            for archive in archives:
                extract_tar(paths[archive['archive_id']], archive,
                            [r for r in manifest['files'] if r.get('archive_id') == archive['archive_id']], pending, state)
        with (pending / MANIFEST_NAME).open('xb') as f:
            f.write(raw)
        (pending / MANIFEST_NAME).chmod(0o444)
        inventory(pending, manifest['files'])
        for row in manifest['files']:
            file_identity(pending / row['path'], row, state.deadline)
        state.check()
        publish(pending, dest)
        report.update(status='ok', source_file_count=len(manifest['files']), source_bytes=manifest['source_bytes'])
    except BaseException as exc:
        state.cancelled.set()
        report.update(status='failed', error_type=type(exc).__name__,
                      reason=str(exc) if isinstance(exc, Refusal) else 'transport_or_io_error')
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
    p.add_argument('--destination', default='/app/data/fcvar')
    p.add_argument('--work-dir', default='/source_capture')
    p.add_argument('--source-dir')
    p.add_argument('--verify-existing', action='store_true')
    args = p.parse_args(argv)
    need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'existing_alarm')
    old = signal.getsignal(signal.SIGALRM)
    def alarm(*unused):
        raise Refusal('wall_deadline')
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        if args.verify_existing:
            manifest = verify_staged(args.destination)
            print(json.dumps(dict(status='ok', mode='offline_verify_only', source_file_count=len(manifest['files']),
                                  source_bytes=manifest['source_bytes'], source_manifest_sha256=MANIFEST_SHA256)))
        else:
            stage(args.destination, args.work_dir, args.manifest, args.source_dir)
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='failed', error_type=type(exc).__name__,
                              reason=str(exc) if isinstance(exc, Refusal) else 'transport_or_io_error')), flush=True)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


if __name__ == '__main__':
    raise SystemExit(main())
