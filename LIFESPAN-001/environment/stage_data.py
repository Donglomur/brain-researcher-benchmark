"""Pinned original-source staging for LIFESPAN; never parse scientific arrays.

Build mode makes one bounded capture or explicitly reuses a verified local
source. verify_staged/--verify-existing are read-only and completely offline.
All digests were measured on the authorized NITRC snapshot, not published by
the provider. No retry, redirect, resume, cache discovery or overwrite.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

MANIFEST_SHA256 = '18fd1271190687765461243943ced2b82d5d5fb703c3d675a2f7586992b5f932'
MANIFEST_NAME = 'source_manifest.json'
EXPECTED_COUNT, EXPECTED_BYTES = 121, 4_997_109_352
MAX_BYTES, MAX_SECONDS, SOCKET_SECONDS = 5_100_000_000, 1800, 30
CHUNK_BYTES, WORKERS = 65536, 2
ROLE_DIR = {'surface_timeseries': 'surface', 'phenotype': 'phenotype', 'surface_annotation': 'atlas'}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw, str) and raw.startswith('/') and '\x00' not in raw, 'absolute_path_required')
    need(not any(x in ('.', '..') for x in raw.split('/')), 'path_traversal_refused')
    path, current = Path(raw), Path('/')
    for part in path.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(mode), 'symlink_component_refused')
        if current != path:
            need(stat.S_ISDIR(mode), 'non_directory_ancestor')
    return path


def disjoint(a, b):
    need(a != b and a not in b.parents and b not in a.parents, 'input_output_overlap')


def relative(value):
    need(isinstance(value, str) and value and '\\' not in value and '\x00' not in value,
         'unsafe_manifest_path')
    need(not value.startswith('/') and all(x not in ('', '.', '..') for x in value.split('/')),
         'unsafe_manifest_path')
    return PurePosixPath(value)


def write_json(path, value):
    with safe_path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def redacted(error):
    def trim(match):
        u = urllib.parse.urlsplit(match.group())
        return urllib.parse.urlunsplit((u.scheme, u.hostname or '', u.path, '', ''))
    return re.sub(r'https?://[^\s<>"\']+', trim, str(error) or type(error).__name__)[:1000]


def endpoint(row):
    name, fid = row['original_filename'], row['nitrc_file_id']
    need(type(fid) is int and fid > 0 and isinstance(name, str) and
         re.fullmatch(r'[A-Za-z0-9_.-]+', name) and name not in ('.', '..'), 'invalid_source_identity')
    expected = f'https://www.nitrc.org/frs/download.php/{fid}/{name}'
    need(row['url'] == expected, 'exact_https_nitrc_endpoint_required')
    return expected


def load_manifest(path=None):
    path = safe_path(path or Path(__file__).absolute().with_name(MANIFEST_NAME))
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_size <= 200_000, 'manifest_type_or_size')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, 'manifest_sha256_mismatch')
    manifest = json.loads(raw)
    rows = manifest['files']
    need(len(rows) == EXPECTED_COUNT == manifest['n_original_files'], 'manifest_file_count')
    need(sum(r['size_bytes'] for r in rows) == EXPECTED_BYTES == manifest['total_original_bytes'], 'manifest_total_bytes')
    need(len({r['path'] for r in rows}) == len({r['nitrc_file_id'] for r in rows}) == len(rows), 'duplicate_manifest_identity')
    for row in rows:
        relative(row['path']); endpoint(row)
        need(row['role'] in ROLE_DIR and row['path'] == ROLE_DIR[row['role']] + '/' + row['original_filename'], 'manifest_role_path')
        need(type(row['size_bytes']) is int and 0 < row['size_bytes'] <= 50_000_000, 'manifest_source_size')
        need(re.fullmatch(r'[a-f0-9]{64}', row['sha256']) and re.fullmatch(r'[a-f0-9]{32}', row['md5']), 'manifest_digest_format')
    return manifest, raw


def inventory(root, manifest, include_manifest):
    root = safe_path(root)
    need(root.is_dir(), 'source_root_required')
    expected = {r['path'] for r in manifest['files']}
    if include_manifest:
        expected.add(MANIFEST_NAME)
    dirs = {str(p) for n in expected for p in PurePosixPath(n).parents if str(p) != '.'}
    found = set()
    for path in root.rglob('*'):
        mode, name = path.lstat().st_mode, path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):
            need(name in dirs, 'unexpected_source_directory')
        else:
            need(stat.S_ISREG(mode), 'nonregular_source_member')
            need(name in expected, 'unexpected_source_file')
            found.add(name)
    need(found == expected, 'missing_source_file')


def checked_stream(path, row, state=None, target=None):
    """Authenticate while reading; optional destination is an exclusive copy."""
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_size == row['size_bytes'], 'source_type_or_size')
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    out = None
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'source_changed_before_read')
            if target is not None:
                out = safe_path(target).open('xb')
            while True:
                if state is not None:
                    state.check()
                block = stream.read(min(CHUNK_BYTES, row['size_bytes'] - size + 1))
                if not block:
                    break
                size += len(block); sha.update(block); md5.update(block)
                need(size <= row['size_bytes'], 'source_grew')
                if out is not None:
                    out.write(block)
            after = os.fstat(stream.fileno())
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(identity(before) == identity(after) == identity(path.lstat()), 'source_changed_during_read')
        verify_hashes(row, size, sha, md5)
        return size
    finally:
        if out is not None:
            out.close()


def verify_hashes(row, size, sha, md5):
    need(size == row['size_bytes'], 'source_size_mismatch')
    need(sha.hexdigest() == row['sha256'] and md5.hexdigest() == row['md5'], 'source_sha256_or_md5_mismatch')


def verify_staged(data_dir):
    """Read-only full inventory+manifest+121 dual hashes; zero network."""
    root = safe_path(data_dir)
    manifest, _ = load_manifest(root / MANIFEST_NAME)
    inventory(root, manifest, True)
    for row in manifest['files']:
        checked_stream(root / row['path'], row)
    return manifest


class State:
    def __init__(self, evidence):
        self.evidence, self.started = evidence, time.monotonic()
        self.received, self.reserved = 0, 0
        self.lock, self.stop = threading.Lock(), threading.Event()

    def remaining(self):
        return MAX_SECONDS - (time.monotonic() - self.started)

    def check(self, network=False, starting=False):
        need(self.remaining() > 0, 'total_wall_deadline')
        if starting:
            need(not self.stop.is_set(), 'peer_failure_no_new_transfer')
        if network:
            need(self.remaining() > SOCKET_SECONDS + 2, 'network_deadline_reserve')

    def read(self, response, maximum):
        self.check(network=True)
        with self.lock:
            left = MAX_BYTES - self.received - self.reserved
            need(left > 0, 'aggregate_payload_cap')
            count = min(maximum, left)
            self.reserved += count
        block = b''
        try:
            block = response.read1(count)
            need(len(block) <= count, 'reader_exceeded_reservation')
            return block
        finally:
            with self.lock:
                self.reserved -= count
                self.received += len(block)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        fp.close()
        raise ValueError(f'HTTP{code}_redirect_refused: {redacted(headers.get("Location", ""))}')
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


HEADER_KEYS = ('Content-Length', 'Content-Type', 'Content-Encoding', 'Transfer-Encoding', 'ETag', 'Last-Modified')


def response_headers(response, row):
    need(response.status == 200 and response.geturl() == endpoint(row), 'exact_full_object_HTTP200_required')
    h = response.headers
    for key in ('Content-Length', 'Content-Type'):
        need(len(h.get_all(key, [])) == 1, 'one_' + key + '_required')
    need(h['Content-Length'] == str(row['size_bytes']), 'response_content_length')
    need(h['Content-Type'].lower() == 'application/force-download', 'response_content_type')
    need(len(h.get_all('Content-Encoding', [])) <= 1 and h.get('Content-Encoding', 'identity').lower() == 'identity', 'response_content_encoding')
    need(h.get('Transfer-Encoding') is None, 'response_transfer_encoding')
    return {key: h.get_all(key, []) for key in HEADER_KEYS if key in h}


def download_one(row, pending, state, opener):
    state.check(network=True, starting=True)
    destination = safe_path(pending / row['path'])
    partial = destination.with_name(destination.name + '.partial')
    receipt = {'path': row['path'], 'url': endpoint(row), 'attempts': 1,
               'status': 'incomplete', 'received_bytes': 0}
    sha, md5 = hashlib.sha256(), hashlib.md5()
    print(json.dumps({'event': 'GET_start', 'path': row['path']}), flush=True)
    try:
        with partial.open('xb') as stream:
            request = urllib.request.Request(endpoint(row), headers={
                'Accept-Encoding': 'identity', 'User-Agent': 'LIFESPAN-source-stage/1.0'})
            with opener.open(request, timeout=SOCKET_SECONDS) as response:
                receipt['http_status'] = response.status
                receipt['observed_headers'] = {key: response.headers.get_all(key, []) for key in HEADER_KEYS if key in response.headers}
                receipt['response_headers'] = response_headers(response, row)
                while True:
                    block = state.read(response, min(CHUNK_BYTES, row['size_bytes'] - receipt['received_bytes'] + 1))
                    if not block:
                        break
                    receipt['received_bytes'] += len(block)
                    sha.update(block); md5.update(block); stream.write(block)
                    need(receipt['received_bytes'] <= row['size_bytes'], 'body_exceeds_expected_length')
        verify_hashes(row, receipt['received_bytes'], sha, md5)
        state.check()
        os.link(partial, destination)
        partial.unlink()
        destination.chmod(0o444)
        receipt['status'] = 'verified'
        print(json.dumps({'event': 'GET_verified', 'path': row['path'], 'bytes': receipt['received_bytes']}), flush=True)
    except BaseException as error:
        state.stop.set()
        receipt.update(status='failed_preserved', reason=redacted(error), error_type=type(error).__name__)
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        print(json.dumps({'event': 'GET_failed', 'path': row['path'], 'reason': redacted(error)}), flush=True)
        raise
    finally:
        receipt.update(measured_received_sha256=sha.hexdigest(), measured_received_md5=md5.hexdigest())
        write_json(state.evidence / f'object_{row["nitrc_file_id"]}.json', receipt)


def parallel_download(rows, operation, state):
    iterator = iter(rows)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pending = set()
        try:
            for _ in range(min(WORKERS, len(rows))):
                state.check(network=True, starting=True)
                pending.add(pool.submit(operation, next(iterator)))
            while pending:
                done, pending = wait(pending, timeout=max(.001, state.remaining()), return_when=FIRST_COMPLETED)
                need(done, 'no_completion_before_deadline')
                for future in done:
                    future.result()
                for _ in done:
                    row = next(iterator, None)
                    if row is None:
                        break
                    state.check(network=True, starting=True)
                    pending.add(pool.submit(operation, row))
        except BaseException:
            state.stop.set()
            for future in pending:
                future.cancel()
            raise


def publish_directory(pending, destination):
    """Linux atomic no-replace publication, including against concurrent writers."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(pending), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


@contextmanager
def hard_timeout():
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'existing_wall_timer_refused')
    old = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame):
        raise TimeoutError('staging_hard_wall_deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def stage(destination, manifest_path=None, source_root=None):
    destination = safe_path(destination)
    manifest_path = safe_path(manifest_path or Path(__file__).absolute().with_name(MANIFEST_NAME))
    evidence = safe_path(destination.with_name(destination.name + '.staging-evidence'))
    disjoint(destination, manifest_path); disjoint(evidence, manifest_path)
    need(not destination.exists() and not evidence.exists(), 'existing_destination_or_evidence_refused')
    source = safe_path(source_root) if source_root is not None else None
    if source is not None:
        disjoint(source, destination); disjoint(source, evidence)
    manifest, raw = load_manifest(manifest_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(mode=0o755)
    state, pending = State(evidence), None
    report = {'status': 'incomplete', 'mode': 'verified_local_copy' if source else 'fresh_https',
              'source_manifest_sha256': MANIFEST_SHA256, 'attempts_per_object': 1,
              'digest_origin': 'measured frozen capture, not publisher-provided'}
    try:
        if source is not None:
            has_manifest = (source / MANIFEST_NAME).exists()
            inventory(source, manifest, has_manifest)
            if has_manifest:
                load_manifest(source / MANIFEST_NAME)
            # All sources must pass before any original is copied.
            for row in manifest['files']:
                checked_stream(source / row['path'], row, state)
        pending = Path(tempfile.mkdtemp(prefix=destination.name + '.partial-', dir=destination.parent))
        pending.chmod(0o755)
        for row in manifest['files']:
            parent = (pending / row['path']).parent
            parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            parent.chmod(0o755)
        if source is not None:
            for row in manifest['files']:
                checked_stream(source / row['path'], row, state, pending / row['path'])
                (pending / row['path']).chmod(0o444)
        else:
            opener = urllib.request.build_opener(NoRedirect())
            parallel_download(manifest['files'], lambda row: download_one(row, pending, state, opener), state)
        with (pending / MANIFEST_NAME).open('xb') as stream:
            stream.write(raw)
        (pending / MANIFEST_NAME).chmod(0o444)
        inventory(pending, manifest, True)
        state.check()
        publish_directory(pending, destination)
        report.update(status='ok', source_file_count=len(manifest['files']), source_bytes=sum(x['size_bytes'] for x in manifest['files']))
    except BaseException as error:
        state.stop.set()
        report.update(status='failed_preserved', reason=redacted(error), error_type=type(error).__name__,
                      preserved_partial=str(pending) if pending is not None else None)
        raise
    finally:
        report.update(received_bytes=state.received, elapsed_seconds=time.monotonic() - state.started)
        write_json(evidence / 'result.json', report)
        print(json.dumps(report, allow_nan=False), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', default='/app/data/lifespan')
    parser.add_argument('--manifest')
    parser.add_argument('--source-root', help='Explicit read-only original role-directory bundle; no cache search')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args(argv)
    try:
        with hard_timeout():
            if args.verify_existing:
                need(args.source_root is None and args.manifest is None, 'verify_mode_conflicting_arguments')
                manifest = verify_staged(args.destination)
                print(json.dumps({'status': 'ok', 'source_file_count': len(manifest['files']),
                                  'source_bytes': manifest['total_original_bytes'], 'source_manifest_sha256': MANIFEST_SHA256}))
            else:
                stage(args.destination, args.manifest, args.source_root)
    except Exception as error:
        print(json.dumps({'status': 'failed_preserved', 'reason': redacted(error), 'error_type': type(error).__name__}), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
