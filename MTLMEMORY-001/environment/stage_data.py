"""Immutable original-source staging for MTLMEMORY-001; no scientific processing."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import threading
import time
import urllib.parse
import urllib.request

MANIFEST_PATH = Path(__file__).with_name('source_manifest.json')
MANIFEST_SHA256 = '3819f2b5e9403f184b94be7d1374476c964c08c054763ec7b8d40cf6bbf7e7b9'
N_FILES = 87
TOTAL_BYTES = 6_197_474_020
CAP_BYTES = 6_300_000_000
TIMEOUT_SECONDS = 1800
SAFE_HEADERS = {'content-length', 'content-type', 'content-encoding', 'etag', 'last-modified', 'x-amz-version-id'}


def reject_symlinks(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Source/evidence paths and their ancestors must not be symlinks')


def read_manifest(path=MANIFEST_PATH):
    path = Path(path)
    reject_symlinks(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Whole source manifest SHA-256 mismatch')
    manifest = json.loads(raw)
    if (manifest.get('dataset_id') != 'dandi000004' or manifest.get('version') != '0.220126.1852'
            or manifest.get('license') != 'CC-BY-4.0' or manifest.get('access') != 'OpenAccess'):
        raise ValueError('Unexpected source release or license identity')
    files = manifest.get('files', [])
    if len(files) != N_FILES or len({x['path'] for x in files}) != N_FILES or len({x['asset_id'] for x in files}) != N_FILES:
        raise ValueError('Original asset inventory must be unique and complete')
    if sum(x['size_bytes'] for x in files) != TOTAL_BYTES or manifest.get('total_size_bytes') != TOTAL_BYTES:
        raise ValueError('Original payload sizes differ from frozen release')
    for item in files:
        relative = PurePosixPath(item['path'])
        parsed = urllib.parse.urlparse(item['transport_url'])
        if (relative.is_absolute() or '..' in relative.parts or len(relative.parts) != 2
                or relative.parts[0] != 'sub-'+item['participant'] or relative.suffix != '.nwb'
                or '\\' in item['path'] or item.get('role') != 'session_nwb'
                or type(item['size_bytes']) is not int or item['size_bytes'] <= 0
                or len(item['sha256']) != 64 or any(c not in '0123456789abcdef' for c in item['sha256'])
                or parsed.scheme != 'https' or parsed.hostname != 'dandiarchive.s3.us-east-2.amazonaws.com'
                or not parsed.path.startswith('/blobs/') or parsed.fragment or parsed.username or parsed.password
                or urllib.parse.parse_qs(parsed.query) != {'versionId': [item['version_id']]}
                or item['blob_url'] != urllib.parse.urlunparse(parsed._replace(query=''))):
            raise ValueError('Unsafe path, participant, role, size, digest or immutable source locator')
    return manifest, raw


def verify_file(path, record):
    path = Path(path)
    reject_symlinks(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size != record['size_bytes']:
        raise ValueError('Original source absent, non-regular, or wrong size: '+record['path'])
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    if digest.hexdigest() != record['sha256']:
        raise ValueError('Published source SHA-256 mismatch: '+record['path'])


def verify_inventory(data_dir, manifest, has_manifest):
    root = Path(data_dir)
    reject_symlinks(root)
    if not root.is_dir():
        raise ValueError('Source directory is absent')
    expected_files = {x['path'] for x in manifest['files']}
    if has_manifest:
        expected_files.add('source_manifest.json')
    expected_dirs = {str(PurePosixPath(x).parent) for x in expected_files if str(PurePosixPath(x).parent) != '.'}
    observed_files, observed_dirs = set(), set()
    for path in root.rglob('*'):
        reject_symlinks(path)
        relative = path.relative_to(root).as_posix()
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            observed_dirs.add(relative)
        elif stat.S_ISREG(mode):
            observed_files.add(relative)
        else:
            raise ValueError('Only regular original files and exact source directories are allowed')
    if observed_files != expected_files or observed_dirs != expected_dirs:
        raise ValueError('Source inventory differs from exact original files and directories')
    for record in manifest['files']:
        verify_file(root / record['path'], record)


def verify_staged(data_dir):
    root = Path(data_dir)
    reject_symlinks(root)
    manifest, _ = read_manifest(root / 'source_manifest.json')
    verify_inventory(root, manifest, has_manifest=True)
    return manifest


def disjoint(a, b):
    a, b = Path(a).absolute(), Path(b).absolute()
    if a == b or a in b.parents or b in a.parents:
        raise ValueError('Source, destination and download evidence must be disjoint, non-nested directories')


def write_json(path, value):
    reject_symlinks(path)
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('No redirect, retry or alternate source object is authorized')


def download_sources(manifest, destination, ledger):
    ledger = Path(ledger)
    reject_symlinks(ledger)
    ledger.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    write_json(ledger / 'attempt.json', dict(started_at_utc=datetime.now(timezone.utc).isoformat(),
        source_manifest_sha256=MANIFEST_SHA256, files=N_FILES, expected_bytes=TOTAL_BYTES,
        cap_bytes=CAP_BYTES, timeout_seconds=TIMEOUT_SECONDS, concurrency=2, automatic_retries=0))
    lock, stop = threading.Lock(), threading.Event()
    state = dict(transferred_bytes=0)

    def one(record):
        if stop.is_set():
            return dict(path=record['path'], status='not_started_after_failure')
        result = dict(path=record['path'], asset_id=record['asset_id'], status='started',
                      source_url=record['transport_url'], expected_sha256=record['sha256'])
        target = Path(destination) / record['path']
        partial = target.with_name(target.name+'.partial')
        size, digest = 0, hashlib.sha256()
        print('Source start: '+record['path']+', '+str(record['size_bytes'])+' bytes', flush=True)
        try:
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            if time.monotonic()-started >= TIMEOUT_SECONDS:
                raise TimeoutError('Source wall limit')
            request = urllib.request.Request(record['transport_url'], headers={
                'Accept-Encoding':'identity', 'If-Match':record['etag'], 'User-Agent':'mtlmemory-source-staging/1.0'})
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
                headers = {k.lower():v for k,v in response.headers.items() if k.lower() in SAFE_HEADERS}
                result['response_headers'] = headers
                if (response.status != 200 or response.geturl() != record['transport_url']
                        or int(headers.get('content-length', '-1')) != record['size_bytes']
                        or headers.get('etag') != record['etag']
                        or headers.get('x-amz-version-id') != record['version_id']
                        or headers.get('content-encoding', 'identity') != 'identity'):
                    raise ValueError('Original HTTP status/URL/size/ETag/version/encoding mismatch')
                with partial.open('xb') as stream:
                    while True:
                        if stop.is_set() or time.monotonic()-started >= TIMEOUT_SECONDS:
                            raise TimeoutError('Source wall limit or another source failed')
                        block = response.read(min(1 << 20, record['size_bytes']-size+1))
                        if not block:
                            break
                        size += len(block)
                        with lock:
                            state['transferred_bytes'] += len(block)
                            if state['transferred_bytes'] > CAP_BYTES:
                                raise ValueError('Cumulative original payload cap exceeded')
                        if size > record['size_bytes']:
                            raise ValueError('Published source size exceeded')
                        digest.update(block)
                        stream.write(block)
            if size != record['size_bytes'] or digest.hexdigest() != record['sha256']:
                raise ValueError('Original size or published SHA-256 mismatch')
            partial.rename(target)
            target.chmod(0o444)
            result['status'] = 'verified_original'
            print('Source verified: '+record['path']+', '+str(size)+' bytes', flush=True)
        except Exception as error:
            stop.set()
            result.update(status='failed', error_type=type(error).__name__, reason=str(error))
            print('Source failed: '+record['path']+', '+type(error).__name__+': '+str(error), flush=True)
        finally:
            result.update(transferred_bytes=size, measured_sha256=digest.hexdigest())
            write_json(ledger / (record['asset_id']+'.json'), result)
        return result

    records = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, record) for record in manifest['files']]
        for future in as_completed(futures):
            records.append(future.result())
    success = len(records)==N_FILES and all(x['status']=='verified_original' for x in records)
    write_json(ledger / 'result.json', dict(status='verified_all_originals' if success else 'failed_preserved',
        transferred_bytes=state['transferred_bytes'], elapsed_seconds=time.monotonic()-started,
        files=sorted(records, key=lambda x:x['path'])))
    if not success:
        raise ValueError('Original source acquisition failed; preserve all files and receipts, no retries')


def stage_data(destination, source_dir=None, ledger=None, manifest_path=MANIFEST_PATH):
    destination = Path(destination)
    reject_symlinks(destination)
    manifest, raw = read_manifest(manifest_path)
    if destination.exists():
        result = verify_staged(destination)
        print('Verified existing source without writes or network', flush=True)
        return result
    if source_dir is not None:
        source_dir = Path(source_dir)
        reject_symlinks(source_dir)
        disjoint(source_dir, destination)
        has_manifest = (source_dir / 'source_manifest.json').exists()
        if has_manifest:
            read_manifest(source_dir / 'source_manifest.json')
        verify_inventory(source_dir, manifest, has_manifest)
    else:
        ledger = Path(ledger) if ledger is not None else destination.parent / (destination.name+'-download')
        reject_symlinks(ledger)
        disjoint(ledger, destination)
        if ledger.exists():
            raise FileExistsError('Preserve existing source download evidence')
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.'+destination.name+'-staging-', dir=destination.parent))
    temporary.chmod(0o755)
    # The owned staging tree is preserved on every failure; never overwrite a destination.
    if source_dir is None:
        download_sources(manifest, temporary, ledger)
    else:
        for record in manifest['files']:
            target = temporary / record['path']
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with (source_dir / record['path']).open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, length=1 << 20)
            target.chmod(0o444)
    with (temporary / 'source_manifest.json').open('xb') as stream:
        stream.write(raw)
    (temporary / 'source_manifest.json').chmod(0o444)
    verify_staged(temporary)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Destination appeared during staging; preserve both trees')
    temporary.rename(destination)
    print('Staged all87 original NWBs plus frozen source manifest; runtime offline', flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('/app/data/mtlmemory'))
    parser.add_argument('--manifest', type=Path, default=MANIFEST_PATH)
    parser.add_argument('--source-dir', type=Path, help='Optional read-only complete original bundle for offline reuse')
    parser.add_argument('--ledger', type=Path, help='Fresh source-download evidence directory outside runtime data')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    if args.verify_existing:
        verify_staged(args.destination)
        print('Offline source identity verification passed', flush=True)
    else:
        stage_data(args.destination, args.source_dir, args.ledger, args.manifest)


if __name__ == '__main__':
    main()
