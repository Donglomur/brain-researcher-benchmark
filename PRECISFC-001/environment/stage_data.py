"""Build-time original MSC staging; runtime integrity checks never access network."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zlib

MANIFEST_PATH = Path(__file__).with_name('source_manifest.json')
PUBLIC_INPUTS = Path(__file__).with_name('public_inputs')
MANIFEST_SHA256 = '4f7fc73e548cfdf744fabbc382cebdd1edff968fe6edd7c1ca846958a1fbb967'
CAP_BYTES, WALL_SECONDS, ORIGINAL_BYTES = 3_800_000_000, 1200, 3_651_426_287
PROVENANCE = {'atlas_coordinates':'power_2011.csv', 'point_transform':'711-2B_to_MNI152lin_T1_t4',
    'atlas_readme':'power_2011_README.txt', 'acquisition_metadata':'task-rest_bold.json',
    'dataset_metadata':'dataset_description.json', 'coordinate_lineage':'coordinate_lineage.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reject_links(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink path or ancestor refused')


def disjoint(first, second):
    first, second = Path(first).resolve(), Path(second).resolve()
    require(first != second and first not in second.parents and second not in first.parents,
            'Source, destination and evidence paths must be disjoint and non-nested')


def validate_manifest(manifest):
    require(manifest['dataset_id'] == 'ds000224' and manifest['release'] == '1.0.4'
            and manifest['release_commit'] == '727a0a4e25ec3f7bea1a20c955ea860206b31e77', 'Wrong release')
    files = manifest['files']
    require(len(files) == len({r['path'] for r in files}) == 42, 'Exactly42 unique source files required')
    expected = {(s, r, role) for s in ('MSC01','MSC02','MSC05','MSC06','MSC08','MSC09')
                for r in ('func01','func02','func03') for role in ('bold','tmask')}
    observed, provenance = set(), set()
    for item in files:
        path = PurePosixPath(item['path'])
        require(not path.is_absolute() and '..' not in path.parts and str(path) == item['path'], 'Unsafe source path')
        require(type(item['size_bytes']) is int and item['size_bytes'] > 0, 'Invalid source size')
        require(re.fullmatch('[0-9a-f]{64}', item['sha256']) is not None, 'Invalid source SHA256')
        if item['role'] in ('bold','tmask'):
            key = (item['subject'], item['session'], item['role'])
            require(key in expected and key not in observed, 'Wrong original cohort/role')
            observed.add(key)
            subject, session, role = key
            suffix = '.nii.gz' if role == 'bold' else '_tmask.txt'
            original = (f'derivatives/volume_pipeline/sub-{subject}/processed_restingstate_timecourses/'
                        f'ses-{session}/talaraich/sub-{subject}_ses-{session}_task-rest_bold_talaraich{suffix}')
            require(item['path'] == original and item['transport'] == 'immutable_s3', 'Wrong original path/transport')
            require(re.fullmatch('[0-9a-f]{32}', item['published_md5']) is not None, 'Invalid published MD5')
            require(item['etag'] == '"'+item['published_md5']+'"', 'Unexpected source ETag')
            url = urllib.parse.urlsplit(item['url'])
            require(url.scheme == 'https' and url.netloc == 's3.amazonaws.com' and not url.fragment, 'Wrong source host')
            require(url.path == '/openneuro.org/ds000224/'+original
                    and urllib.parse.parse_qs(url.query, strict_parsing=True) == {'versionId':[item['version_id']]}
                    and item['version_id'] not in ('','null'), 'Immutable source key/version mismatch')
            if role == 'bold':
                require(re.fullmatch('[0-9a-f]{64}', item['header_sha256']) is not None, 'Header identity missing')
        else:
            role = item['role']
            require(role in PROVENANCE and role not in provenance and item['path'] == 'provenance/'+PROVENANCE[role]
                    and item['transport'] == 'bundled_exact_bytes', 'Unexpected provenance input')
            provenance.add(role)
    require(observed == expected and provenance == set(PROVENANCE), 'Incomplete source inventory')
    require(sum(r['size_bytes'] for r in files if r['transport'] == 'immutable_s3') == ORIGINAL_BYTES,
            'Original source size total changed')


def read_manifest(path=MANIFEST_PATH):
    path = Path(path); reject_links(path)
    require(path.is_file(), 'Manifest must be a regular file')
    raw = path.read_bytes()
    require(MANIFEST_SHA256 is not None and hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256,
            'Whole source manifest SHA256 mismatch or unfrozen manifest')
    manifest = json.loads(raw)
    validate_manifest(manifest)
    return manifest, raw


def verify_header(path, item):
    # Full object checksums must pass before this bounded header-only decoding.
    with Path(path).open('rb') as stream:
        compressed = stream.read(65536)
    header = zlib.decompressobj(16+zlib.MAX_WBITS).decompress(compressed, 352)
    require(len(header) == 352 and hashlib.sha256(header).hexdigest() == item['header_sha256'], 'Header identity mismatch')


def verify_file(path, item):
    path = Path(path); reject_links(path)
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode) and path.stat().st_size == item['size_bytes'],
            'Source absent/nonregular/wrong size: '+item['path'])
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            sha.update(block); md5.update(block)
    require(sha.hexdigest() == item['sha256'], 'Source SHA256 mismatch: '+item['path'])
    if 'published_md5' in item:
        require(md5.hexdigest() == item['published_md5'], 'Published MD5 mismatch: '+item['path'])
    if item['role'] == 'bold':
        verify_header(path, item)


def inventory(root, records, manifest_present=False):
    root = Path(root); reject_links(root)
    require(root.is_dir(), 'Source root absent')
    expected_files = {r['path'] for r in records}
    if manifest_present:
        expected_files.add('source_manifest.json')
    expected_dirs = {str(p) for name in expected_files for p in PurePosixPath(name).parents if str(p) != '.'}
    seen_files, seen_dirs = set(), set()
    for path in root.rglob('*'):
        reject_links(path)
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            seen_dirs.add(name)
        elif path.is_file() and stat.S_ISREG(path.stat().st_mode):
            seen_files.add(name)
        else:
            raise ValueError('Unexpected source filesystem object')
    require(seen_files == expected_files and seen_dirs == expected_dirs, 'Closed source inventory mismatch')
    for item in records:
        verify_file(root/item['path'], item)


def verify_staged(data_dir):
    root = Path(data_dir); reject_links(root)
    manifest, _ = read_manifest(root/'source_manifest.json')
    inventory(root, manifest['files'], manifest_present=True)
    return manifest


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('No redirect, fallback or automatic retry')


def download_originals(records, destination, ledger):
    ledger = Path(ledger); reject_links(ledger)
    ledger.mkdir(parents=True, exist_ok=False, mode=0o755)
    started = time.monotonic()
    lock, stop = threading.Lock(), threading.Event()
    state = {'bytes': 0}
    write_json(ledger/'attempt.json', dict(source_manifest_sha256=MANIFEST_SHA256,
        started_at_utc=datetime.now(timezone.utc).isoformat(), cap_bytes=CAP_BYTES,
        wall_seconds=WALL_SECONDS, concurrency=2, retries=0))

    def one(item):
        result = dict(path=item['path'], status='started', received_bytes=0)
        target = Path(destination)/item['path']
        partial = target.with_name(target.name+'.partial')
        sha, md5 = hashlib.sha256(), hashlib.md5()
        size = 0
        def check():
            require(not stop.is_set(), 'Stopped after another source failure')
            if time.monotonic()-started >= WALL_SECONDS:
                raise TimeoutError('Aggregate source wall limit')
        try:
            check()
            reject_links(target); reject_links(partial)
            require(not target.exists() and not partial.exists(), 'Preserve existing source evidence')
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            print('Source start: '+item['path']+', '+str(item['size_bytes'])+' bytes', flush=True)
            request = urllib.request.Request(item['url'], headers={'Accept-Encoding':'identity',
                'If-Match':item['etag'], 'User-Agent':'precisfc-original-staging/1.0'})
            timeout = min(60, max(0.1, WALL_SECONDS-(time.monotonic()-started)))
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
                result['headers'] = {key:response.headers[key] for key in
                    ('Content-Length','ETag','x-amz-version-id','Last-Modified','Content-Type') if key in response.headers}
                require(response.status == 200 and response.geturl() == item['url'], 'HTTP status/URL mismatch')
                require(int(response.headers['Content-Length']) == item['size_bytes']
                        and response.headers['ETag'] == item['etag']
                        and response.headers['x-amz-version-id'] == item['version_id']
                        and response.headers.get('Content-Encoding','identity') == 'identity', 'HTTP identity mismatch')
                with partial.open('xb') as stream:
                    while True:
                        check()
                        block = response.read(min(1 << 20, item['size_bytes']-size+1))
                        if not block:
                            break
                        size += len(block)
                        with lock:
                            state['bytes'] += len(block)
                            require(state['bytes'] <= CAP_BYTES, 'Aggregate source payload cap')
                        stream.write(block); sha.update(block); md5.update(block)
                        require(size <= item['size_bytes'], 'Original object longer than pinned length')
            require(size == item['size_bytes'] and md5.hexdigest() == item['published_md5']
                    and sha.hexdigest() == item['sha256'], 'Source length/MD5/SHA256 mismatch')
            if item['role'] == 'bold':
                verify_header(partial, item)
            os.link(partial, target); partial.unlink()
            target.chmod(0o444)
            result['status'] = 'verified_original'
            print('Source verified: '+item['path']+', '+str(size)+' bytes', flush=True)
        except Exception as error:
            stop.set()
            result.update(status='failed_preserved', error_type=type(error).__name__, reason=str(error))
            print('Source failed: '+item['path']+', '+type(error).__name__+': '+str(error), flush=True)
        finally:
            result.update(received_bytes=size, measured_sha256=sha.hexdigest(), measured_md5=md5.hexdigest())
            write_json(ledger/(item['subject']+'_'+item['session']+'_'+item['role']+'.json'), result)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(one, item) for item in records]
        results = [future.result() for future in futures]
    ok = len(results) == len(records) and all(x['status'] == 'verified_original' for x in results)
    write_json(ledger/'result.json', dict(status='verified_all_originals' if ok else 'failed_preserved',
        received_bytes=state['bytes'], elapsed_seconds=time.monotonic()-started,
        files=sorted(results, key=lambda x:x['path'])))
    require(ok, 'Source acquisition failed; preserve all receipts/partials and do not retry')


def stage_data(destination, source_dir=None, ledger=None, manifest_path=MANIFEST_PATH, public_inputs=PUBLIC_INPUTS):
    destination, public_inputs = Path(destination), Path(public_inputs)
    reject_links(destination); reject_links(public_inputs)
    manifest, raw = read_manifest(manifest_path)
    disjoint(destination, Path(manifest_path).parent); disjoint(destination, public_inputs)
    if destination.exists():
        return verify_staged(destination)
    originals = [item for item in manifest['files'] if item['transport'] == 'immutable_s3']
    bundled = [item for item in manifest['files'] if item['transport'] == 'bundled_exact_bytes']
    for item in bundled:
        verify_file(public_inputs/PROVENANCE[item['role']], item)
    if source_dir is not None:
        source_dir = Path(source_dir); reject_links(source_dir); disjoint(source_dir, destination)
        if (source_dir/'source_manifest.json').exists():
            verify_staged(source_dir)
        else:
            inventory(source_dir, originals)
    else:
        ledger = Path(ledger) if ledger else destination.parent/(destination.name+'-download')
        reject_links(ledger); disjoint(destination, ledger); disjoint(public_inputs, ledger)
        disjoint(Path(manifest_path).parent, ledger)
        require(not ledger.exists(), 'Preserve previous download ledger')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    temporary = Path(tempfile.mkdtemp(prefix='.'+destination.name+'-staging-', dir=destination.parent))
    temporary.chmod(0o755)
    # Preserve the exact owned temporary tree on every failure.
    if source_dir is None:
        download_originals(originals, temporary, ledger)
    else:
        for item in originals:
            target = temporary/item['path']; target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            with (source_dir/item['path']).open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, length=1 << 20)
            target.chmod(0o444)
    for item in bundled:
        target = temporary/item['path']; target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        with (public_inputs/PROVENANCE[item['role']]).open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst, length=1 << 20)
        target.chmod(0o444)
    with (temporary/'source_manifest.json').open('xb') as stream:
        stream.write(raw)
    (temporary/'source_manifest.json').chmod(0o444)
    verify_staged(temporary)
    require(not destination.exists() and not destination.is_symlink(), 'Destination appeared; preserve both trees')
    temporary.rename(destination)
    print('Staged36 authenticated originals and6 public provenance files; runtime offline', flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('/app/data/precisfc'))
    parser.add_argument('--manifest', type=Path, default=MANIFEST_PATH)
    parser.add_argument('--source-dir', type=Path, help='Optional verified read-only original bundle; never modified')
    parser.add_argument('--public-inputs', type=Path, default=PUBLIC_INPUTS)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    if args.verify_existing:
        verify_staged(args.destination)
    else:
        stage_data(args.destination, args.source_dir, args.ledger, args.manifest, args.public_inputs)


if __name__ == '__main__':
    main()
