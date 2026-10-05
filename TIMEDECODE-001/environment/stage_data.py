"""Build-time only: stage three pinned original sample members, never process data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import signal
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

MANIFEST_SHA256 = '533bc28bbcc1e8fe53880504b75756ee4035ecb423e3be84c5fddf1660b779f6'
MANIFEST_PATH = Path(__file__).with_name('source_manifest.json')


def file_hash(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def safe_path(name):
    path = PurePosixPath(name)
    return (isinstance(name, str) and bool(name) and not path.is_absolute()
            and '\\' not in name and '\x00' not in name and '..' not in path.parts
            and name == str(path) and str(path) not in ('', '.'))


def read_manifest(path=None):
    path = MANIFEST_PATH if path is None else Path(path)
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != MANIFEST_SHA256:
        raise ValueError('manifest differs from frozen original-source contract')
    manifest = json.loads(body)
    if manifest['dataset_id'] != 'mne-sample' or manifest['source_version'] != 'osf-86qa2-v6':
        raise ValueError('wrong dataset identity')
    files, archive = manifest['files'], manifest['archive']
    if (len(files) != 3 or len({e['path'] for e in files}) != 3
            or {e['role'] for e in files} != {'raw', 'events', 'version'}):
        raise ValueError('expected three unique original source files and roles')
    for entry in files:
        if not safe_path(entry['path']) or not safe_path(entry['archive_member']):
            raise ValueError('unsafe source manifest path')
        if entry['archive_member'] != archive['archive_prefix']+'/'+entry['path']:
            raise ValueError('archive-to-runtime mapping mismatch')
        if type(entry['size_bytes']) is not int or entry['size_bytes'] < 0:
            raise ValueError('invalid original source size')
        if (not re.fullmatch('[0-9a-f]{64}', entry['sha256'])
                or not re.fullmatch('[0-9a-f]{32}', entry['md5'])):
            raise ValueError('invalid original source checksum')
    if archive['automatic_retries'] != 0 or archive['range_requests'] is not False:
        raise ValueError('source policy forbids retries and range requests')
    return manifest


def verify_staged(data_dir):
    """Return the frozen manifest only after all runtime source bytes are verified."""
    root = Path(data_dir)
    for component in (root.absolute(), *root.absolute().parents):
        if component.is_symlink():
            raise ValueError('staged root or parent may not be a symlink')
    if root.is_symlink() or not root.is_dir():
        raise ValueError('staged source root must be a real directory')
    if (root/'source_manifest.json').is_symlink():
        raise ValueError('manifest may not be a symlink')
    manifest = read_manifest(root/'source_manifest.json')
    expected = {'source_manifest.json'} | {entry['path'] for entry in manifest['files']}
    observed = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('staged source contains a symlink')
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise ValueError('staged source contains a special file')
    if observed != expected:
        raise ValueError('staged file membership differs from three files plus manifest')
    for entry in manifest['files']:
        path = root/entry['path']
        if (path.stat().st_size != entry['size_bytes'] or file_hash(path) != entry['sha256']
                or file_hash(path, 'md5') != entry['md5']):
            raise ValueError(f'original source checksum/size mismatch: {entry["path"]}')
    return manifest


def verify_archive(path, manifest):
    path = Path(path)
    expected = manifest['archive']
    if path.is_symlink() or not path.is_file() or path.stat().st_size != expected['size_bytes']:
        raise ValueError('archive is not the exact original regular file/size')
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            md5.update(chunk); sha.update(chunk)
    if md5.hexdigest() != expected['md5'] or sha.hexdigest() != expected['sha256']:
        raise ValueError('original archive dual checksum mismatch; do not repin')


def check_url(url, policy):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in policy['approved_redirect_hostnames']
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('unapproved source transport endpoint')
    if parsed.hostname == 'osf.io':
        if parsed.path not in ('/download/86qa2', '/download/86qa2/'):
            raise ValueError('unapproved OSF source file')
        if urllib.parse.parse_qs(parsed.query) not in ({'version': ['6']}, {'revision': ['6']}):
            raise ValueError('OSF archive version must remain six')
    if parsed.hostname in ('files.osf.io', 'files.us.osf.io'):
        if parsed.path != policy['approved_osf_file_path']:
            raise ValueError('unapproved OSF storage file')
        query = urllib.parse.parse_qs(parsed.query)
        if not (query.get('version') == ['6'] or query.get('revision') == ['6']):
            raise ValueError('OSF storage archive version must remain six')
    if (parsed.hostname == 'storage.googleapis.com'
            and parsed.path != policy['approved_storage_object_path']):
        raise ValueError('unapproved Google storage object')


def public_url(url):
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


def download_archive(path, manifest, progress=None):
    """One sequential GET, immutable object allowlist, strict byte/time cap, no retries."""
    path, policy = Path(path), manifest['archive']
    if path.exists() or path.is_symlink():
        raise FileExistsError('refuse existing download target')
    redirects = []
    progress = {} if progress is None else progress
    progress.update(url=policy['url'], redirects=redirects, measured_bytes=0,
                    automatic_retries=0)
    print('Source download started: '+policy['name'], flush=True)
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            check_url(newurl, policy)
            redirects.append({'from': public_url(req.full_url), 'to': public_url(newurl), 'status': code})
            if len(redirects) > 5:
                raise ValueError('excessive redirects')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    def timed_out(signum, frame):
        raise TimeoutError('approved source download deadline exceeded')
    old_handler = signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(policy['timeout_seconds'])
    count = 0
    try:
        check_url(policy['url'], policy)
        request = urllib.request.Request(policy['url'], headers={'Accept-Encoding': 'identity'}, method='GET')
        opener = urllib.request.build_opener(Redirect())
        with opener.open(request, timeout=30) as response:
            check_url(response.url, policy)
            if response.status != 200:
                raise ValueError('expected complete HTTP 200 archive')
            declared = response.headers.get('Content-Length')
            if declared is not None and int(declared) not in policy['declared_metadata_sizes_bytes']:
                raise ValueError('unexpected archive Content-Length')
            if response.headers.get('Content-Encoding', 'identity').lower() not in ('', 'identity'):
                raise ValueError('unexpected archive transport encoding')
            progress.update(resolved_url=public_url(response.url), http_status=response.status,
                            declared_content_length=declared,
                            transport_headers={key: response.headers[key] for key in
                              ('Content-Length', 'Content-Type', 'ETag', 'Last-Modified')
                              if key in response.headers})
            with path.open('xb') as output:
                while True:
                    if count >= policy['transfer_cap_bytes']:
                        raise ValueError('archive transfer cap reached')
                    chunk = response.read(min(1024*1024, policy['transfer_cap_bytes']-count))
                    if not chunk:
                        break
                    count += len(chunk)
                    progress['measured_bytes'] = count
                    output.write(chunk)
            receipt = {'url': policy['url'], 'resolved_url': public_url(response.url),
                       'redirects': redirects, 'declared_content_length': declared,
                       'measured_bytes': count, 'automatic_retries': 0}
        verify_archive(path, manifest)
        progress.update(receipt)
        print('Source download verified: '+policy['name']+' '+str(count)+' bytes', flush=True)
        return progress
    except BaseException as exc:
        progress.update(error_type=type(exc).__name__, error=str(exc), partial_file=str(path))
        print('Source download failed: '+policy['name']+' '+type(exc).__name__, flush=True)
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def extract_regular_members(archive_path, destination, manifest):
    destination = Path(destination)
    if any(destination.iterdir()):
        raise FileExistsError('extraction staging directory must be empty')
    policy = manifest['archive']
    allow = {entry['archive_member']: entry for entry in manifest['files']}
    seen, found = set(), set()
    expanded = selected = 0
    with tarfile.open(archive_path, 'r|gz') as archive:
        for member in archive:
            if member.name in seen or not safe_path(member.name):
                raise ValueError('duplicate or unsafe archive member name')
            seen.add(member.name)
            expanded += member.size
            if (len(seen) > policy['max_members'] or member.size < 0
                    or expanded > policy['max_declared_expanded_bytes']):
                raise ValueError('archive inventory bound exceeded')
            if member.name not in allow:
                continue
            if not member.isreg():
                raise ValueError('allowlisted source is not a regular member')
            entry = allow[member.name]
            if member.size != entry['size_bytes']:
                raise ValueError('allowlisted source size mismatch')
            selected += member.size
            if selected > policy['max_selected_expanded_bytes']:
                raise ValueError('selected expanded-byte bound exceeded')
            path = destination/entry['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            checksum, md5, measured = hashlib.sha256(), hashlib.md5(), 0
            with archive.extractfile(member) as stream, path.open('xb') as output:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    measured += len(chunk)
                    if measured > member.size:
                        raise ValueError('member payload exceeds declared size')
                    checksum.update(chunk); md5.update(chunk); output.write(chunk)
            if (measured != member.size or checksum.hexdigest() != entry['sha256']
                    or md5.hexdigest() != entry['md5']):
                raise ValueError('original member checksum mismatch')
            found.add(member.name)
    if found != set(allow):
        raise ValueError('missing allowlisted original source member')
    (destination/'source_manifest.json').write_bytes(MANIFEST_PATH.read_bytes())
    verify_staged(destination)
    return {'archive_members_seen': len(seen), 'declared_expanded_bytes': expanded,
            'selected_bytes': selected, 'selected_files': len(found), 'links_followed': False}


def stage_data(destination, archive=None, receipt=None, keep_archive=False):
    manifest = read_manifest()
    destination = Path(destination).absolute()
    for component in (destination, *destination.parents):
        if component.is_symlink():
            raise ValueError('destination or parent may not be a symlink')
    if receipt is not None:
        receipt = Path(receipt)
        if receipt.exists() or receipt.is_symlink():
            raise FileExistsError('preserve existing receipt')
    if destination.exists() or destination.is_symlink():
        verify_staged(destination)
        return {'status': 'verified_existing', 'destination': str(destination), 'network_requests': 0}
    destination.parent.mkdir(parents=True, exist_ok=True)
    if receipt is not None and Path(receipt).resolve().is_relative_to(destination.resolve()):
        raise ValueError('staging receipt must remain outside runtime data directory')
    work = Path(tempfile.mkdtemp(prefix='.'+destination.name+'-source-stage-', dir=destination.parent))
    selected = work/'selected'
    selected.mkdir()
    ledger = {'status': 'in_progress', 'manifest_sha256': MANIFEST_SHA256,
              'destination': str(destination), 'staging_directory': str(work), 'automatic_retries': 0}
    started = time.monotonic()
    try:
        if archive is None:
            original = work/manifest['archive']['name']
            ledger['download'] = {}
            ledger['archive_path'] = str(original)
            download_archive(original, manifest, ledger['download'])
        else:
            original = Path(archive)
            ledger['local_archive'] = str(original)
            verify_archive(original, manifest)
        ledger['extraction'] = extract_regular_members(original, selected, manifest)
        if destination.exists():
            raise FileExistsError('destination appeared during staging; preserve it')
        for path in selected.rglob('*'):
            path.chmod(0o755 if path.is_dir() else 0o444)
        selected.chmod(0o755)
        selected.rename(destination)
        ledger['status'] = 'verified'
        if archive is None and not keep_archive:
            original.unlink()  # Only this invocation's private, verified temporary archive.
        if archive is not None or not keep_archive:
            work.rmdir()  # Only this invocation's now-empty private staging directory.
        ledger['authoring_archive_retained'] = bool(archive is None and keep_archive)
        return ledger
    except BaseException as exc:
        ledger.update(status='failed', error_type=type(exc).__name__, error=str(exc),
                      partial_artifacts_retained=True)
        raise
    finally:
        ledger['elapsed_seconds'] = time.monotonic()-started
        if receipt is None:
            with tempfile.NamedTemporaryFile(mode='w', prefix=destination.name+'-stage-', suffix='.json',
                                             dir=destination.parent, delete=False) as output:
                json.dump(ledger, output, indent=2)
                output.write('\n')
        else:
            with Path(receipt).open('x') as output:
                json.dump(ledger, output, indent=2)
                output.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', default='/app/data/timedecode')
    parser.add_argument('--archive', help='Exact verified original archive; no network when provided')
    parser.add_argument('--receipt', help='Optional new receipt path outside runtime data directory')
    parser.add_argument('--keep-archive', action='store_true', help='Retain this download for local source-authoring evidence')
    parser.add_argument('--verify-existing', action='store_true', help='Verify staged bytes only; never download')
    args = parser.parse_args()
    if args.verify_existing:
        manifest = verify_staged(args.destination)
        print(json.dumps({'status': 'verified', 'files': len(manifest['files']),
                          'manifest_sha256': MANIFEST_SHA256}))
    else:
        print(json.dumps(stage_data(args.destination, args.archive, args.receipt, args.keep_archive), indent=2))


if __name__ == '__main__':
    main()
