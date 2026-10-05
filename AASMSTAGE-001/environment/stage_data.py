"""Immutable original-source staging for AASMSTAGE-001; no scientific processing."""
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
MANIFEST_SHA256 = '241be998b50465f17431dba963499dbb34c355a2e17533a1dd0d659f4e837cbb'
N_FILES = 12
TOTAL_BYTES = 298_590_434
CAP_BYTES = 310_000_000
TIMEOUT_SECONDS = 300
SAFE_HEADERS = {'content-length', 'content-type', 'content-encoding', 'etag', 'last-modified', 'x-amz-version-id'}


def reject_symlinks(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Source/evidence paths and their ancestors must not be symlinks')


def read_manifest(path=MANIFEST_PATH):
    path = Path(path)
    reject_symlinks(path)
    if not path.is_file():
        raise ValueError('Source manifest must be a regular file')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Whole source manifest SHA-256 mismatch')
    manifest = json.loads(raw)
    validate_manifest(manifest)
    return manifest, raw


def validate_manifest(manifest):
    if (manifest.get('dataset') != 'PhysioNet Sleep-EDF Database Expanded'
            or manifest.get('version') != '1.0.0' or manifest.get('license') != 'ODC-By-1.0'
            or manifest.get('subjects') != list(range(6)) or manifest.get('recording') != 1
            or manifest.get('dataset_doi') != '10.13026/C2X676'):
        raise ValueError('Unexpected source release, cohort or license identity')
    files = manifest.get('files', [])
    expected = {
        (0, 'psg'): 'SC4001E0-PSG.edf', (0, 'hypnogram'): 'SC4001EC-Hypnogram.edf',
        (1, 'psg'): 'SC4011E0-PSG.edf', (1, 'hypnogram'): 'SC4011EH-Hypnogram.edf',
        (2, 'psg'): 'SC4021E0-PSG.edf', (2, 'hypnogram'): 'SC4021EH-Hypnogram.edf',
        (3, 'psg'): 'SC4031E0-PSG.edf', (3, 'hypnogram'): 'SC4031EC-Hypnogram.edf',
        (4, 'psg'): 'SC4041E0-PSG.edf', (4, 'hypnogram'): 'SC4041EC-Hypnogram.edf',
        (5, 'psg'): 'SC4051E0-PSG.edf', (5, 'hypnogram'): 'SC4051EC-Hypnogram.edf'}
    if len(files) != N_FILES or len({x['path'] for x in files}) != N_FILES:
        raise ValueError('Original EDF inventory must be unique and complete')
    if sum(x['size_bytes'] for x in files) != TOTAL_BYTES:
        raise ValueError('Original payload size differs from frozen source')
    if {(x['subject'], x['role']): x['path'] for x in files} != expected:
        raise ValueError('Subject, role or original EDF name mismatch')
    for item in files:
        relative = PurePosixPath(item['path'])
        if (relative.is_absolute() or len(relative.parts) != 1 or relative.name != item['path']
                or item.get('recording') != 1 or type(item['subject']) is not int
                or type(item['size_bytes']) is not int or item['size_bytes'] <= 0
                or len(item['sha256']) != 64 or any(c not in '0123456789abcdef' for c in item['sha256'])
                or item['url'] != 'https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/'+item['path']
                or item['transport_url'] != 'https://physionet-open.s3.amazonaws.com/sleep-edfx/1.0.0/sleep-cassette/'+item['path']):
            raise ValueError('Unsafe original path, role, size, checksum or documented mirror URL')



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


def verify_inventory(data_dir, manifest, manifest_name=None):
    root = Path(data_dir)
    reject_symlinks(root)
    if not root.is_dir():
        raise ValueError('Source directory is absent')
    expected_files = {x['path'] for x in manifest['files']}
    if manifest_name is not None:
        expected_files.add(manifest_name)
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
    verify_inventory(root, manifest, 'source_manifest.json')
    return manifest


def disjoint(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
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
        result = dict(path=record['path'], status='started',
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
                'Accept-Encoding':'identity', 'User-Agent':'aasmstage-source-staging/1.0'})
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
                headers = {k.lower():v for k,v in response.headers.items() if k.lower() in SAFE_HEADERS}
                result['response_headers'] = headers
                if (response.status != 200 or response.geturl() != record['transport_url']
                        or int(headers.get('content-length', '-1')) != record['size_bytes']
                        or headers.get('content-encoding', 'identity') != 'identity'):
                    raise ValueError('Original HTTP status/URL/size/encoding mismatch')
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
            write_json(ledger / (record['path']+'.json'), result)
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
        manifest_name = None
        if (source_dir / 'source_manifest.json').exists():
            read_manifest(source_dir / 'source_manifest.json')
            manifest_name = 'source_manifest.json'
        elif (source_dir / 'data_manifest.json').exists():
            legacy = source_dir / 'data_manifest.json'
            reject_symlinks(legacy)
            legacy_raw = legacy.read_bytes()
            if (hashlib.sha256(legacy_raw).hexdigest() not in {
                    MANIFEST_SHA256, '946a3de918109e92a2bfe143205cf9d416ccf9a40571d3788a7b1dbb555883f4'}
                    or json.loads(legacy_raw) != manifest):
                raise ValueError('Legacy read-only source manifest differs from authenticated originals')
            manifest_name = 'data_manifest.json'
        verify_inventory(source_dir, manifest, manifest_name)
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
    print('Staged all12 original EDFs plus frozen source manifest; runtime offline', flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('/app/data/aasmstage'))
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
