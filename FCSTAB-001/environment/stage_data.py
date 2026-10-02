"""Pinned opaque FCSTAB source staging; no numerical/table decoding.

Network staging performs one conditional request per frozen object, without
redirects, retries or fallback. Local reuse authenticates ALL inputs before any
source copy. Runtime verification is entirely offline. CLI alarm plus per-read
deadlines are secondary guards: the caller must retain its outer hard timeout.
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

MANIFEST_SHA256 = 'c57fed19c165e8a606c2b6a9aef89099103a2642d6ab54b93bf525d71ea46171'
PRIOR_MANIFEST_SHA256 = 'd4e930b84667e58831880100039cde688d56ccd0ff8c509f0f363fd1c4685aeb'
SUBJECT_IDS_SHA256 = '7645fc4276e63ed4f09e4135bac9d38da3b036a2e4e522fae432ae490d4d28cb'
DATASET = 'ABIDE_pcp/cpac/filt_noglobal/rois_cc200'
PHENOTYPE = 'Phenotypic_V1_0b_preprocessed1.csv'
PHENOTYPE_VERSION = 'lJ6_qkCzZAQRKrL9I637l1rVdYZnkhlS'
BASE_URL = 'https://s3.amazonaws.com/fcp-indi/data/Projects/ABIDE_Initiative/'
ROI_PREFIX = 'Outputs/cpac/filt_noglobal/rois_cc200/'
NOTICE_PATH = 'provenance/nilearn_0_13_1_ABIDE_pcp.rst'
NOTICE_URL = 'https://raw.githubusercontent.com/nilearn/nilearn/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/description/ABIDE_pcp.rst'
NOTICE_GIT = 'e414ca3c0648f273b1c724ffcd3e4c5bf02a8db5'
CHUNK = 65536
MANIFEST_NAME = 'source_manifest.json'


@dataclass(frozen=True)
class Policy:
    manifest_sha256: str
    file_count: int = 42
    source_bytes: int = 16147721
    roi_count: int = 40
    phenotype_rows: int = 1112
    phenotype_named_rows: int = 1035
    manifest_cap: int = 4 * 1024**2
    member_cap: int = 1_000_000
    transfer_cap: int = 20_000_000
    workers: int = 2
    wall_seconds: int = 600
    socket_seconds: int = 30


PRODUCTION = Policy(MANIFEST_SHA256)


class Refusal(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise Refusal(reason)


def digest_string(value, size=64):
    return type(value) is str and re.fullmatch(f'[0-9a-f]{{{size}}}', value) is not None


def safe_path(value):
    literal = os.fspath(value)
    need(type(literal) is str and literal.startswith('/') and '\0' not in literal, 'absolute_path_required')
    need(not any(part in ('.', '..') for part in literal.split('/')), 'lexical_traversal')
    path = Path(literal)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), 'symlink_path')
            if part != path:
                need(stat.S_ISDIR(mode), 'non_directory_ancestor')
    return path


def relative(value):
    need(type(value) is str and value and '\0' not in value and '\\' not in value
         and not value.startswith('/') and not re.match(r'^[A-Za-z]:', value)
         and all(part not in ('', '.', '..') for part in value.split('/')), 'unsafe_member_path')
    return PurePosixPath(value)


def disjoint(a, b):
    need(a != b and a not in b.parents and b not in a.parents, 'overlapping_paths')


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def reader(path):
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode), 'regular_file_required')
    # Walk directory descriptors too: O_NOFOLLOW on a leaf alone does not
    # prevent replacement of a parent directory with a symlink during open.
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:-1]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=directory)
            os.close(directory)
            directory = following
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, 'rb') as stream:
        need(signature(os.fstat(stream.fileno())) == signature(before), 'changed_before_read')
        yield stream, before
        need(signature(os.fstat(stream.fileno())) == signature(before), 'changed_descriptor_during_read')
        need(signature(safe_path(path).lstat()) == signature(before), 'changed_source_path')


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def invalid(unused):
        raise Refusal('nonfinite_json')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    def finite(item):
        if isinstance(item, float):
            need(math.isfinite(item), 'nonfinite_json')
        elif isinstance(item, (list, dict)):
            for child in item.values() if isinstance(item, dict) else item:
                finite(child)
    finite(value)
    return value


def bounded_pinned_bytes(path, pin, cap, check):
    need(digest_string(pin), 'unfrozen_pin')
    with reader(path) as (stream, info):
        need(0 < info.st_size <= cap, 'metadata_size_cap')
        check()
        raw = stream.read(cap + 1)
        need(len(raw) == info.st_size and len(raw) <= cap, 'metadata_size_changed')
        need(hashlib.sha256(raw).hexdigest() == pin, 'metadata_digest')
        check()
    return raw


def validate_manifest(doc, policy=PRODUCTION):
    need(type(doc) is dict and doc.get('schema_version') == 'fcstab-source-v1'
         and doc.get('task_id') == 'FCSTAB-001' and doc.get('dataset_id') == DATASET
         and doc.get('upstream_immutable_release') is False
         and doc.get('runtime_data_directory') == '/app/data/fcstab'
         and doc.get('source_files_directory') == '.', 'manifest_schema')
    rows, ids = doc.get('files'), doc.get('participant_file_ids')
    need(type(rows) is list and len(rows) == policy.file_count and type(ids) is list
         and len(ids) == policy.roi_count and all(type(x) is str for x in ids)
         and len(set(ids)) == len(ids), 'manifest_count_or_order')
    paths, subjects, indices, ordered_ids = set(), set(), set(), []
    total, n_pheno, n_notice = 0, 0, 0
    for row in rows:
        need(type(row) is dict, 'manifest_row_type')
        path = row.get('path')
        relative(path)
        need(path not in paths and path != MANIFEST_NAME, 'duplicate_member_path')
        paths.add(path)
        size = row.get('size_bytes')
        need(type(size) is int and 0 < size <= policy.member_cap
             and digest_string(row.get('sha256')), 'member_identity')
        for key, width in (('md5', 32), ('git_blob_sha1', 40)):
            if key in row:
                need(digest_string(row[key], width), 'secondary_identity')
        total += size
        need(total <= policy.transfer_cap, 'source_byte_cap')
        role = row.get('role')
        if role == 'provenance_abide_notice':
            n_notice += 1
            need(path == NOTICE_PATH and row.get('source_url') == NOTICE_URL
                 and row.get('download_url') == NOTICE_URL and digest_string(row.get('git_blob_sha1'), 40),
                 'notice_identity')
            continue
        if role == 'phenotype':
            n_pheno += 1
            need(path == PHENOTYPE and row.get('version_id') == PHENOTYPE_VERSION, 'phenotype_identity')
            key = PHENOTYPE
        else:
            need(role == 'roi_timeseries', 'source_role')
            fid, sid, index = row.get('file_id'), row.get('subject_id'), row.get('phenotype_row_index')
            need(type(fid) is str and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*_[0-9]{7}', fid)
                 and path == f'roi/{fid}_rois_cc200.1D', 'literal_file_path')
            need(type(sid) is str and re.fullmatch(r'[0-9]+', sid)
                 and str(int(fid.rsplit('_', 1)[1])) == sid and sid not in subjects,
                 'source_subject_identity')
            subjects.add(sid)
            need(type(index) is int and 0 <= index < policy.phenotype_rows and index not in indices,
                 'phenotype_row_identity')
            indices.add(index)
            ordered_ids.append(fid)
            need(row.get('version_id') == 'null', 'derivative_null_version')
            key = ROI_PREFIX + fid + '_rois_cc200.1D'
        version = row['version_id']
        need(row.get('source_key') == key and row.get('source_url') == BASE_URL + key
             and row.get('download_url') == BASE_URL + key + '?' + urlencode({'versionId': version}),
             'source_locator')
        need(type(row.get('etag')) is str and re.fullmatch(r'"[A-Za-z0-9._-]{1,128}"', row['etag']), 'etag_identity')
        need(row.get('etag_is_assumed_md5') is False
             and row.get('named_version_immutable') is (version != 'null'), 'identity_authority')
    need(n_pheno == 1 and n_notice == 1 and len(subjects) == policy.roi_count
         and policy.file_count == policy.roi_count + 2 and ordered_ids == ids, 'role_count_or_order')
    need(total == policy.source_bytes and type(doc.get('source_bytes')) is int
         and doc['source_bytes'] == total and type(doc.get('source_file_count')) is int
         and doc['source_file_count'] == len(rows), 'source_totals')
    need(not any(str(p) in paths for path in paths for p in relative(path).parents), 'path_collision')
    lineage, cohort = doc.get('reuse_lineage', {}), doc.get('cohort_source', {})
    need(lineage.get('prior_source_manifest_sha256') == PRIOR_MANIFEST_SHA256
         and lineage.get('public_subject_ids_sha256') == SUBJECT_IDS_SHA256, 'lineage_identity')
    need(cohort.get('path') == PHENOTYPE and type(cohort.get('original_rows')) is int
         and cohort['original_rows'] == policy.phenotype_rows
         and type(cohort.get('selected_derivatives')) is int and cohort['selected_derivatives'] == policy.roi_count
         and type(cohort.get('named_derivatives')) is int and cohort['named_derivatives'] == policy.phenotype_named_rows
         and type(cohort.get('no_filename_rows')) is int
         and cohort['no_filename_rows'] == policy.phenotype_rows - policy.phenotype_named_rows, 'cohort_metadata')
    return rows


def read_manifest(path, policy=PRODUCTION, check=lambda: None):
    raw = bounded_pinned_bytes(path, policy.manifest_sha256, policy.manifest_cap, check)
    doc = strict_json(raw)
    validate_manifest(doc, policy)
    return doc, raw


def inventory(root, rows, check=lambda: None, with_manifest=False):
    root = safe_path(root)
    need(root.is_dir(), 'source_directory_required')
    wanted = {r['path'] for r in rows}
    if with_manifest:
        wanted.add(MANIFEST_NAME)
    directories = {str(p) for name in wanted for p in relative(name).parents if str(p) != '.'}
    found, found_dirs, stack = set(), set(), [root]
    while stack:
        parent = safe_path(stack.pop())
        check()
        with os.scandir(parent) as entries:
            for entry in entries:
                check()
                rel = Path(entry.path).relative_to(root).as_posix()
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    need(rel in directories and rel not in found_dirs, 'unexpected_directory')
                    found_dirs.add(rel)
                    stack.append(Path(entry.path))
                else:
                    need(stat.S_ISREG(mode) and rel in wanted and rel not in found, 'unexpected_file_or_link')
                    found.add(rel)
    need(found == wanted and found_dirs == directories, 'incomplete_inventory')


def authenticate(raw, row):
    need(len(raw) == row['size_bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], 'source_size_or_sha256')
    if 'md5' in row:
        need(hashlib.md5(raw).hexdigest() == row['md5'], 'source_md5')
    if 'git_blob_sha1' in row:
        need(hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() == row['git_blob_sha1'], 'source_git_blob')


def member_bytes(path, row, check=lambda: None):
    # Opaque one-member immutable buffer; no scientific/table parser or reopen.
    with reader(path) as (stream, before):
        need(before.st_size == row['size_bytes'], 'source_size')
        check()
        raw = stream.read(row['size_bytes'] + 1)
        authenticate(raw, row)
        check()
    return raw


def verify_staged(data_dir, *, policy=PRODUCTION, check=lambda: None):
    root = safe_path(data_dir)
    doc, unused = read_manifest(root / MANIFEST_NAME, policy, check)
    inventory(root, doc['files'], check, with_manifest=True)
    for row in doc['files']:
        member_bytes(root / row['path'], row, check)
    inventory(root, doc['files'], check, with_manifest=True)
    return doc


def new_bytes(path, raw):
    path = safe_path(path)
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o444)


def new_json(path, doc):
    new_bytes(path, (json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + '\n').encode())


def publish_directory(source, destination):
    # Linux renameat2(RENAME_NOREPLACE) also refuses an existing empty directory.
    # A check followed by ordinary rename would permit an overwrite race.
    source, destination = safe_path(source), safe_path(destination)
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if result:
        raise OSError(ctypes.get_errno(), 'exclusive_directory_publication_failed')


def safe_error(exc):
    # Do not log arbitrary exception text: HTTP errors can contain response or
    # proxy credentials. All Refusal reasons are our fixed nonsecret vocabulary.
    if isinstance(exc, Refusal):
        return str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        return f'http_status_{exc.code}'
    return type(exc).__name__


class State:
    def __init__(self, policy=PRODUCTION, clock=time.monotonic):
        self.policy, self.clock, self.started = policy, clock, clock()
        self.lock, self.stop = threading.Lock(), threading.Event()
        self.received, self.reserved, self.started_paths = 0, 0, set()
        self.first_error = None

    def fail(self, exc):
        with self.lock:
            if self.first_error is None:
                self.first_error = exc
            self.stop.set()

    def check(self):
        need(not self.stop.is_set(), 'cancelled')
        need(self.clock() - self.started < self.policy.wall_seconds, 'wall_deadline')

    def begin(self, row):
        with self.lock:
            self.check()
            need(row['path'] not in self.started_paths and len(self.started_paths) < self.policy.file_count,
                 'duplicate_or_excess_start')
            self.started_paths.add(row['path'])

    def read(self, response, count):
        with self.lock:
            self.check()
            available = self.policy.transfer_cap - self.received - self.reserved
            need(available > 0, 'aggregate_payload_cap')
            count = min(count, available)
            self.reserved += count
        block = b''
        try:
            block = response.read1(count)
            need(type(block) is bytes and len(block) <= count, 'http_read_bound')
        finally:
            with self.lock:
                self.reserved -= count
                self.received += len(block) if isinstance(block, bytes) else 0
        self.check()
        return block


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        fp.close()  # Never consume redirect/error bodies or follow a Location.
        raise Refusal('redirect_refused')
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def one_header(headers, key, required=True):
    values = headers.get_all(key, [])
    need(len(values) == 1 if required else len(values) <= 1, 'missing_or_duplicate_header_' + key)
    return values[0] if values else None


def response_identity(response, row):
    need(response.status == 200 and response.geturl() == row['download_url'], 'http_status_or_final_url')
    h = response.headers
    length = one_header(h, 'Content-Length')
    need(re.fullmatch(r'[0-9]+', length) and int(length) == row['size_bytes'], 'http_content_length')
    need(one_header(h, 'Content-Encoding', False) in (None, 'identity')
         and one_header(h, 'Transfer-Encoding', False) is None, 'http_encoding')
    content_type = one_header(h, 'Content-Type').split(';', 1)[0].strip().lower()
    need(content_type in ('application/octet-stream', 'binary/octet-stream', 'text/plain', 'text/csv',
                          'application/csv', 'text/tab-separated-values'), 'http_content_type')
    result = {'Content-Length': length, 'Content-Type': content_type}
    if row['role'] != 'provenance_abide_notice':
        etag, version = one_header(h, 'ETag'), one_header(h, 'x-amz-version-id')
        need(etag == row['etag'] and version == row['version_id'], 'http_object_identity')
        result.update(ETag=etag, version_id=version, etag_is_assumed_md5=False)
    return result


def download_one(row, target, receipt, state, opener):
    state.begin(row)
    partial = target.with_name(target.name + '.partial')
    result = dict(path=row['path'], source_record=dict(row), status='incomplete', received_bytes=0,
                  canonical_source_url=row['source_url'], initial_endpoint=row['download_url'],
                  attempts=1, redirects=0, automatic_retries=0)
    raw = bytearray()
    try:
        headers = {'Accept-Encoding': 'identity', 'User-Agent': 'FCSTAB-source-stage/2'}
        if row['role'] != 'provenance_abide_notice':
            headers['If-Match'] = row['etag']
        request = urllib.request.Request(row['download_url'], headers=headers)
        with partial.open('xb') as stream:
            state.check()
            timeout = min(state.policy.socket_seconds, state.policy.wall_seconds - (state.clock() - state.started))
            with opener.open(request, timeout=timeout) as response:
                result['response_identity'] = response_identity(response, row)
                while True:
                    block = state.read(response, min(CHUNK, row['size_bytes'] - len(raw) + 1))
                    if not block:
                        break
                    raw.extend(block)
                    stream.write(block)
                    result['received_bytes'] = len(raw)
                    need(len(raw) <= row['size_bytes'], 'http_body_overrun')
        authenticate(bytes(raw), row)
        state.check()
        # Exclusive hardlink is only between our new partial/target, never a
        # source cache. Complete receipts bind bytes, not ETag-as-MD5 guesses.
        os.link(partial, target, follow_symlinks=False)
        partial.unlink()
        target.chmod(0o444)
        result.update(status='verified', measured_sha256=hashlib.sha256(raw).hexdigest())
    except BaseException as exc:
        state.fail(exc)
        result.update(status='failed', reason=safe_error(exc), error_type=type(exc).__name__)
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()
        raise
    finally:
        result['measured_partial_sha256'] = hashlib.sha256(raw).hexdigest()
        new_json(receipt, result)
    return result


def acquire(rows, pending, receipts, state, opener=None):
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    results = []
    iterator = iter(enumerate(rows))
    def submit(pool, pending_jobs):
        item = next(iterator, None)
        if item is not None:
            state.check()
            i, row = item
            pending_jobs.add(pool.submit(download_one, row, pending / row['path'],
                                         receipts / f'{i:04d}.json', state, opener))
    # Cancellation is set BEFORE executor shutdown. In-flight calls remain
    # socket-bounded; the caller's outer timeout handles slow-drip headers.
    with ThreadPoolExecutor(max_workers=state.policy.workers) as pool:
        jobs = set()
        try:
            for unused in range(state.policy.workers):
                submit(pool, jobs)
            while jobs:
                state.check()
                done, jobs = wait(jobs, timeout=1, return_when=FIRST_COMPLETED)
                for job in done:
                    results.append(job.result())
                for unused in done:
                    submit(pool, jobs)
        except BaseException:
            state.stop.set()
            for job in jobs:
                job.cancel()
            # Preserve the first worker's source failure even if the main
            # thread notices cancellation before collecting its Future.
            if state.first_error is not None:
                raise state.first_error
            raise
    need(len(results) == len(rows) and state.received == sum(r['size_bytes'] for r in rows), 'incomplete_capture')
    return results


def stage(manifest_path, destination, work_dir, *, source_dir=None, notice_file=None,
          policy=PRODUCTION, clock=time.monotonic, opener=None):
    need(type(policy) is Policy and digest_string(policy.manifest_sha256)
         and 1 <= policy.workers <= 2, 'explicit_policy_required')
    manifest_path, destination, work, helper = map(safe_path, (
        manifest_path, destination, work_dir, Path(__file__).parent))
    need((source_dir is None) == (notice_file is None), 'both_local_inputs_required')
    source = safe_path(source_dir) if source_dir is not None else None
    notice = safe_path(notice_file) if notice_file is not None else None
    protected = [manifest_path.parent, helper]
    if source is not None:
        need(source.is_dir(), 'source_directory_required')
        disjoint(source, notice.parent)
        protected += [source, notice.parent]
    disjoint(work, destination)
    for root in (work, destination):
        for path in protected:
            disjoint(root, path)
        need(not os.path.lexists(root), 'fresh_destination_and_work_required')
    state = State(policy, clock)
    # Validate every path before creating ANY output parents.
    work.mkdir(parents=True, mode=0o755)
    result = dict(status='running', phase='manifest', source_payloads_parsed=False,
                  source_manifest_sha256=policy.manifest_sha256, network_requests=0,
                  redirects=0, automatic_retries=0, source_writes=False,
                  mode='local_copy' if source else 'conditional_https')
    new_json(work / 'attempt.json', dict(result, transfer_cap=policy.transfer_cap,
             workers=policy.workers, wall_seconds=policy.wall_seconds, socket_seconds=policy.socket_seconds))
    pending = work / 'pending'
    try:
        doc, raw_manifest = read_manifest(manifest_path, policy, state.check)
        rows = doc['files']
        notice_row = next(r for r in rows if r['role'] == 'provenance_abide_notice')
        originals = [r for r in rows if r['role'] != 'provenance_abide_notice']
        if source is not None:
            result['phase'] = 'all_local_input_authentication'
            inventory(source, originals, state.check)
            for row in rows:
                member_bytes(notice if row is notice_row else source / row['path'], row, state.check)
            inventory(source, originals, state.check)
        # Only after full local input authentication create a copied-source tree.
        pending.mkdir(mode=0o755)
        for directory in sorted({str(p) for r in rows for p in relative(r['path']).parents if str(p) != '.'}):
            (pending / directory).mkdir(parents=True, mode=0o755, exist_ok=True)
        receipts = work / 'members'
        receipts.mkdir(mode=0o755)
        if source is None:
            result['phase'] = 'conditional_download'
            acquire(rows, pending, receipts, state, opener)
        else:
            result['phase'] = 'authenticated_local_copy'
            for i, row in enumerate(rows):
                raw = member_bytes(notice if row is notice_row else source / row['path'], row, state.check)
                new_bytes(pending / row['path'], raw)
                new_json(receipts / f'{i:04d}.json', dict(status='verified', path=row['path'],
                         source_record=dict(row), observed_sha256=hashlib.sha256(raw).hexdigest(),
                         observed_size_bytes=len(raw), mode='local_copy'))
            inventory(source, originals, state.check)
        new_bytes(pending / MANIFEST_NAME, raw_manifest)
        result['phase'] = 'offline_bundle_verification'
        verify_staged(pending, policy=policy, check=state.check)
        state.check()
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        publish_directory(pending, destination)
        result.update(status='ok', phase='complete', source_file_count=len(rows), source_bytes=policy.source_bytes,
                      destination=str(destination), internal_manifest_sha256=policy.manifest_sha256)
    except BaseException as exc:
        state.stop.set()
        result.update(status='failed', error_type=type(exc).__name__, reason=safe_error(exc))
        raise
    finally:
        result.update(network_requests=len(state.started_paths), received_bytes=state.received,
                      elapsed_seconds=clock() - state.started)
        new_json(work / 'result.json', result)
    return result


@contextmanager
def cli_timeout(seconds):
    need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'existing_alarm')
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*unused):
        raise Refusal('wall_deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default='/app/source_manifest.json')
    parser.add_argument('--destination', default='/app/data/fcstab')
    parser.add_argument('--work-dir', default='/source_capture')
    parser.add_argument('--source-dir', help='Explicit closed41 selected original-member root; offline local reuse only')
    parser.add_argument('--notice-file', help='Separate authenticated1195B notice; required with --source-dir')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args(argv)
    try:
        with cli_timeout(PRODUCTION.wall_seconds):
            if args.verify_existing:
                need(args.source_dir is None and args.notice_file is None, 'verify_mode_local_inputs_refused')
                verify_staged(args.destination)
                result = dict(status='ok', operation='offline_verify_only', source_file_count=PRODUCTION.file_count,
                              source_bytes=PRODUCTION.source_bytes, source_manifest_sha256=MANIFEST_SHA256,
                              network_requests=0, source_payloads_parsed=False, source_writes=False)
            else:
                result = stage(args.manifest, args.destination, args.work_dir,
                               source_dir=args.source_dir, notice_file=args.notice_file)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='failed', reason=safe_error(exc))))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
