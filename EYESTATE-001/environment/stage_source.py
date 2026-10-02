"""Pinned ABIDE PCP source staging; no ROI numerical parsing or analysis.

Fresh builds conditionally acquire the exact frozen original objects. Explicit
local reuse is read-only. Existing destinations must already verify completely;
unverified files, partial downloads and failure receipts are never overwritten.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

MANIFEST_PATH = Path(__file__).with_name('source_manifest.json')
MANIFEST_SHA256 = 'd4e930b84667e58831880100039cde688d56ccd0ff8c509f0f363fd1c4685aeb'
DATASET = 'ABIDE_pcp/cpac/filt_noglobal/rois_cc200'
PHENO = 'Phenotypic_V1_0b_preprocessed1.csv'
PHENO_VERSION = 'lJ6_qkCzZAQRKrL9I637l1rVdYZnkhlS'
BASE = 'https://s3.amazonaws.com/fcp-indi/data/Projects/ABIDE_Initiative/'
ROI_PREFIX = 'Outputs/cpac/filt_noglobal/rois_cc200/'
N_FILES, TOTAL_BYTES = 1036, 406540381
CAP_BYTES, WALL_SECONDS, READ_SECONDS, WORKERS = 420000000, 1800, 30, 2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink source/evidence path or ancestor refused')
    return path.resolve(strict=False)


def disjoint(a, b):
    a, b = safe_path(a), safe_path(b)
    require(a != b and a not in b.parents and b not in a.parents, 'Source, manifest, destination and evidence paths must be disjoint')


def regular(path):
    path = safe_path(path)
    require(stat.S_ISREG(path.stat().st_mode), 'Regular source/manifest file required')
    return path


def pairs_unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key')
        value[key] = item
    return value


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'Nonfinite source metadata')
    elif isinstance(value, dict):
        for item in value.values(): finite_json(item)
    elif isinstance(value, list):
        for item in value: finite_json(item)


def read_manifest(path=MANIFEST_PATH):
    path = regular(path)
    require(path.stat().st_size <= 4_000_000, 'Source manifest size cap')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, 'Whole source manifest SHA256 mismatch')
    manifest = json.loads(raw, object_pairs_hook=pairs_unique)
    finite_json(manifest)
    validate_manifest(manifest)
    return manifest, raw


def validate_manifest(manifest):
    require(manifest.get('dataset_id') == DATASET and manifest.get('schema_version') == 1 and
            manifest.get('upstream_immutable_release') is False, 'Wrong source dataset/snapshot policy')
    entries = manifest.get('files', [])
    require(len(entries) == N_FILES and len({x['path'] for x in entries}) == N_FILES, 'Source inventory incomplete or duplicated')
    require(sum(x['size_bytes'] for x in entries) == TOTAL_BYTES, 'Frozen original byte total mismatch')
    subjects, rows, phenotype_count = set(), set(), 0
    for entry in entries:
        path = entry['path']
        if entry['role'] == 'phenotype':
            require(path == PHENO and entry['version_id'] == PHENO_VERSION, 'Wrong named-version phenotype identity')
            key = PHENO
            phenotype_count += 1
        else:
            require(entry['role'] == 'roi_timeseries' and re.fullmatch(r'roi/[A-Za-z][A-Za-z0-9_]*_[0-9]{7}_rois_cc200\.1D', path),
                    'Unsafe source path or wrong ROI derivative role')
            filename = path.split('/')[1]
            require(filename == entry['file_id'] + '_rois_cc200.1D' and re.fullmatch(r'[0-9]+', entry['subject_id']) and
                    int(entry['file_id'].rsplit('_', 1)[1]) == int(entry['subject_id']), 'ROI subject/filename mismatch')
            require(int(entry['subject_id']) not in subjects and type(entry['phenotype_row_index']) is int and
                    0 <= entry['phenotype_row_index'] < 1112 and entry['phenotype_row_index'] not in rows,
                    'Duplicate/invalid source subject or phenotype row')
            subjects.add(int(entry['subject_id'])); rows.add(entry['phenotype_row_index'])
            key = ROI_PREFIX + filename
        require(type(entry['size_bytes']) is int and 0 < entry['size_bytes'] <= 1_000_000 and
                re.fullmatch(r'[0-9a-f]{64}', entry['sha256']), 'Invalid exact source size/SHA256')
        require(entry['source_key'] == key and entry['source_url'] == BASE + key, 'Wrong official source object URL/key')
        require(re.fullmatch(r'"[A-Za-z0-9._-]{1,128}"', entry['etag']), 'Unsafe conditional source ETag')
        version = entry['version_id']
        require(version is None or isinstance(version, str) and re.fullmatch(r'[A-Za-z0-9._~-]{1,512}', version), 'Unsafe S3 version')
        expected = BASE + key + (('?' + urllib.parse.urlencode({'versionId': version})) if version is not None else '')
        require(entry['download_url'] == expected, 'Unapproved source transport URL or query')
        require(entry['named_version_immutable'] is (version not in (None, 'null')) and entry['etag_is_assumed_md5'] is False,
                'Incorrect source version/checksum provenance assertion')
    require(phenotype_count == 1 and len(subjects) == N_FILES - 1, 'Missing exact source roles')


def verify_file(path, entry):
    path = regular(path)
    before = path.stat()
    require(before.st_size == entry['size_bytes'], 'Wrong original file size: ' + entry['path'])
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while True:
            block = stream.read(min(65536, entry['size_bytes'] - count + 1))
            if not block: break
            count += len(block)
            require(count <= entry['size_bytes'], 'Original file grew while verifying')
            digest.update(block)
    after = path.stat()
    require(count == entry['size_bytes'] and digest.hexdigest() == entry['sha256'], 'Measured-original SHA256 mismatch: ' + entry['path'])
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Original source changed during verification')


def verify_inventory(root, manifest, with_manifest=False):
    root = safe_path(root)
    require(root.is_dir(), 'Source bundle directory missing')
    expected = {x['path'] for x in manifest['files']}
    if with_manifest: expected.add('source_manifest.json')
    files, directories = set(), set()
    for path in root.rglob('*'):
        path = safe_path(path)
        mode, rel = path.stat().st_mode, path.relative_to(root).as_posix()
        if stat.S_ISREG(mode): files.add(rel)
        elif stat.S_ISDIR(mode): directories.add(rel)
        else: raise ValueError('Special source files refused')
    require(files == expected and directories == {'roi'}, 'Exact original source inventory mismatch; no extras/links')
    for entry in manifest['files']: verify_file(root / entry['path'], entry)


def verify_staged(data_dir):
    root = safe_path(data_dir)
    manifest, _ = read_manifest(root / 'source_manifest.json')
    verify_inventory(root, manifest, with_manifest=True)
    return manifest


def write_json(path, value):
    with safe_path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def safe_error(error):
    return re.sub(r'https?://[^\s<>"\']+', lambda m: m.group(0).split('?', 1)[0], str(error) or type(error).__name__)[:1000]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        fp.close()
        raise ValueError('Unexpected source redirect; no fallback or retry')
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


@contextmanager
def hard_timeout(seconds):
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'Refuse to replace an active timeout')
    old = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame): raise TimeoutError('Total source staging deadline exceeded')
    signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, seconds)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, old)


def download(manifest, destination, ledger, opener=None):
    ledger = safe_path(ledger)
    ledger.mkdir(parents=True, mode=0o755, exist_ok=False)
    opener = opener or urllib.request.build_opener(NoRedirect())
    lock, stop, started = threading.Lock(), threading.Event(), time.monotonic()
    budget = {'received': 0, 'reserved': 0}
    write_json(ledger / 'attempt.json', {'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'manifest_sha256': MANIFEST_SHA256, 'expected_bytes': TOTAL_BYTES, 'cap_bytes': CAP_BYTES,
        'wall_seconds': WALL_SECONDS, 'workers': WORKERS, 'attempts_per_object': 1})
    def check():
        require(not stop.is_set() and time.monotonic() - started < WALL_SECONDS, 'Source failure or wall deadline; no further requests')
    def one(entry):
        check()
        target = destination / entry['path']
        partial = target.with_name(target.name + '.partial')
        result = {'path': entry['path'], 'status': 'incomplete', 'received_bytes': 0}
        digest = hashlib.sha256()
        print('Source start: ' + entry['path'], flush=True)
        try:
            request = urllib.request.Request(entry['download_url'], headers={'Accept-Encoding': 'identity', 'If-Match': entry['etag']})
            with partial.open('xb') as stream:
                with opener.open(request, timeout=min(READ_SECONDS, WALL_SECONDS - (time.monotonic()-started))) as response:
                    h = response.headers
                    require(response.status == 200 and response.geturl() == entry['download_url'] and
                        h.get('Content-Length', '').isdecimal() and int(h['Content-Length']) == entry['size_bytes'] and
                        h.get('Content-Encoding', 'identity') == 'identity' and h.get('ETag') == entry['etag'] and
                        h.get('x-amz-version-id') == entry['version_id'], 'Pinned source HTTP identity/length mismatch')
                    result['response_identity'] = {k: h.get(k) for k in ('Content-Length', 'ETag', 'x-amz-version-id', 'Last-Modified')}
                    while True:
                        check()
                        with lock:
                            remaining = CAP_BYTES - budget['received'] - budget['reserved']
                            require(remaining > 0, 'Aggregate source payload cap reached')
                            count = min(65536, entry['size_bytes']-result['received_bytes']+1, remaining)
                            budget['reserved'] += count
                        block = b''
                        try: block = getattr(response, 'read1', response.read)(count)
                        finally:
                            with lock:
                                budget['reserved'] -= count; budget['received'] += len(block)
                        require(len(block) <= count, 'HTTP reader exceeded bounded request')
                        if not block: break
                        result['received_bytes'] += len(block); stream.write(block); digest.update(block)
                        require(result['received_bytes'] <= entry['size_bytes'], 'Original object exceeded pinned length')
            require(result['received_bytes'] == entry['size_bytes'] and digest.hexdigest() == entry['sha256'], 'Fresh original size/SHA256 mismatch')
            os.link(partial, target); partial.unlink(); target.chmod(0o444)
            result['status'] = 'verified_original'
            print('Source verified: ' + entry['path'] + ', ' + str(result['received_bytes']) + ' bytes', flush=True)
        except BaseException as error:
            stop.set(); result.update(status='failed', reason=safe_error(error))
            if isinstance(error, urllib.error.HTTPError): error.close()
            print('Source failed: ' + entry['path'] + ', ' + safe_error(error), flush=True)
            raise
        finally:
            result['measured_sha256'] = digest.hexdigest()
            write_json(ledger / (target.name + '.json'), result)
        return result
    result = {'status': 'incomplete'}
    try:
        with hard_timeout(WALL_SECONDS), ThreadPoolExecutor(max_workers=WORKERS) as pool:
            try:
                iterator, pending = iter(manifest['files']), set()
                for _ in range(min(WORKERS, len(manifest['files']))): pending.add(pool.submit(one, next(iterator)))
                completed = 0
                while pending:
                    check()
                    done, pending = wait(pending, timeout=min(READ_SECONDS, WALL_SECONDS-(time.monotonic()-started)), return_when=FIRST_COMPLETED)
                    require(done, 'No source worker completed within deadline')
                    for future in done: future.result(); completed += 1
                    for _ in done:
                        entry = next(iterator, None)
                        if entry is not None: pending.add(pool.submit(one, entry))
                require(completed == len(manifest['files']), 'Incomplete original acquisition')
            except BaseException:
                stop.set()
                raise
        result['status'] = 'verified_all_originals'
    except BaseException as error:
        stop.set(); result.update(status='failed_preserved', reason=safe_error(error))
        raise
    finally:
        result.update(received_bytes=budget['received'], wall_seconds=time.monotonic()-started)
        write_json(ledger / 'result.json', result)


def stage_source(destination, source_dir=None, manifest_path=MANIFEST_PATH, ledger=None):
    destination, manifest_path = safe_path(destination), regular(manifest_path)
    disjoint(destination, manifest_path)
    manifest, raw = read_manifest(manifest_path)
    if source_dir is not None:
        source_dir = safe_path(source_dir); disjoint(source_dir, destination)
    if destination.exists():
        result = verify_staged(destination)
        print('Verified existing source; no writes or network', flush=True)
        return result
    if source_dir is not None:
        with_manifest = (source_dir / 'source_manifest.json').exists()
        if with_manifest: read_manifest(source_dir / 'source_manifest.json')
        verify_inventory(source_dir, manifest, with_manifest)
    else:
        ledger = safe_path(ledger or destination.parent / (destination.name + '-download'))
        disjoint(ledger, destination); disjoint(ledger, manifest_path)
        require(not ledger.exists(), 'Preserve existing download evidence; use a fresh ledger directory')
    destination.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.' + destination.name + '-staging-', dir=destination.parent))
    temporary.chmod(0o755); (temporary / 'roi').mkdir(mode=0o755)
    print('Owned staging directory: ' + str(temporary), flush=True)
    # On any failure this unique tree is retained, and the destination is unchanged.
    if source_dir is None:
        download(manifest, temporary, ledger)
    else:
        for entry in manifest['files']:
            target = temporary / entry['path']
            with (source_dir / entry['path']).open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, length=65536)
            target.chmod(0o444)
    with (temporary / 'source_manifest.json').open('xb') as stream: stream.write(raw)
    (temporary / 'source_manifest.json').chmod(0o444)
    verify_staged(temporary)
    require(not destination.exists() and not destination.is_symlink(), 'Destination appeared during staging; preserve both trees')
    temporary.rename(destination)
    print('Staged exactly1036 authenticated originals plus source manifest; runtime offline', flush=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('/app/data/eyestate'))
    parser.add_argument('--manifest', type=Path, default=MANIFEST_PATH)
    parser.add_argument('--source-dir', type=Path, help='Explicit verified local originals for read-only offline reuse')
    parser.add_argument('--ledger', type=Path, help='Fresh acquisition receipts outside the runtime source directory')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args(argv)
    if args.verify_existing:
        verify_staged(args.destination); print('Offline source identity verification passed', flush=True)
    else: stage_source(args.destination, args.source_dir, args.manifest, args.ledger)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
