"""Stage three unchanged, authenticated MNE release files; no scientific parsing.

Portable build default downloads one pinned archive. --archive explicitly reuses
a fully verified local archive. --verify-existing is entirely offline. No retry.
"""
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import tarfile
import time
import urllib.parse
import urllib.request

MANIFEST_SHA256 = '31b2d095d29abb0236d2439b67c1a7fc7c301c2562ee46de74f399934095df60'
ARCHIVE_SHA256 = 'abce7df32a4d5bc23fa39b997ecbe57232c89ad48ec5ac77c5b84ac912d0e9d1'
CAP_BYTES, WALL_SECONDS, READ_SECONDS = 100_000_000, 300, 30
EXPANDED_CAP, MEMBER_CAP, REDIRECT_CAP = 200_000_000, 30, 5
FILENAMES = {'README.txt', 'version.txt', 'ERP-CORE_Subject-001_Task-Flankers_eeg.fif'}
HEADER_KEYS = ('Content-Length', 'Content-Type', 'ETag', 'Last-Modified', 'Content-Encoding')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink path or ancestor refused')
    return path.resolve(strict=False)


def regular(path):
    path = safe_path(path)
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode), 'Regular file required')
    return path


def write_json(path, value):
    with safe_path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def safe_url(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.hostname or '', p.path, '', ''))


def safe_error(error):
    return re.sub(r'https?://[^\s<>\"\']+', lambda m: safe_url(m.group(0)), str(error) or type(error).__name__)


def allowed_url(url):
    p = urllib.parse.urlsplit(url)
    require(p.scheme == 'https' and p.username is None and p.password is None
            and p.port in (None, 443) and not p.fragment, 'Only ordinary HTTPS source URLs allowed')
    if p.hostname == 'osf.io':
        require(p.path.rstrip('/') in ('/download/rzgba', '/rzgba/download'), 'Unexpected OSF source path')
        require(urllib.parse.parse_qs(p.query, strict_parsing=True) in
                ({'version': ['1']}, {'revision': ['1']}), 'Unexpected source version')
    elif p.hostname == 'storage.googleapis.com':
        require(p.path == '/cos-osf-prod-files-us-east1/' + ARCHIVE_SHA256, 'Unexpected storage bucket/object')
    else:
        require(p.hostname == 'files.osf.io' and p.path.rstrip('/') ==
                '/v1/resources/rxvq7/providers/osfstorage/6034b80b88ea1a0490eea8c4', 'Unexpected storage identity')
    return url


def read_manifest(path):
    path = regular(path)
    require(path.stat().st_size <= 100_000, 'Manifest too large')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, 'Manifest SHA256 mismatch')
    manifest = json.loads(raw)
    entries = manifest['files']
    require(len(entries) == 3 and {e['path'] for e in entries} == FILENAMES, 'Exact three source filenames required')
    require({e['role'] for e in entries} == {'readme', 'version', 'raw_fif'}, 'Source roles mismatch')
    for e in entries:
        require(e['archive_member'] == 'MNE-ERP-CORE-data/' + e['path'], 'Unsafe or unexpected archive member')
        require(type(e['size_bytes']) is int and 0 < e['size_bytes'] < EXPANDED_CAP, 'Invalid member size')
        require(re.fullmatch('[0-9a-f]{64}', e['sha256']) is not None, 'Invalid member SHA256')
    archive = manifest['archive']
    allowed_url(archive['url'])
    require(archive['filename'] == 'MNE-ERP-CORE-data.tar.gz', 'Archive filename mismatch')
    require(type(archive['size_bytes']) is int and 0 < archive['size_bytes'] <= CAP_BYTES, 'Archive size invalid')
    require(re.fullmatch('[0-9a-f]{32}', archive['md5']) is not None and
            re.fullmatch('[0-9a-f]{64}', archive['sha256']) is not None, 'Invalid archive digests')
    return manifest, raw


def verify_file(path, size, sha256, md5=None):
    path = regular(path)
    require(path.stat().st_size == size, 'Source byte count mismatch: ' + path.name)
    sha, md = hashlib.sha256(), hashlib.md5()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            sha.update(block)
            md.update(block)
    require(sha.hexdigest() == sha256 and (md5 is None or md.hexdigest() == md5),
            'Source digest mismatch: ' + path.name)


def verify_staged(data_dir):
    root = safe_path(data_dir)
    require(root.is_dir(), 'Source directory missing')
    manifest, _ = read_manifest(root / 'source_manifest.json')
    require({p.name for p in root.iterdir()} == FILENAMES | {'source_manifest.json'}, 'Source inventory mismatch')
    for e in manifest['files']:
        verify_file(root / e['path'], e['size_bytes'], e['sha256'])
    return manifest


@contextmanager
def total_timeout(seconds):
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'Refuse existing timer')
    previous = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame):
        raise TimeoutError('Total source staging deadline exceeded')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class SourceRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, ledger, started):
        self.ledger, self.started, self.count = ledger, started, 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(time.monotonic() - self.started < WALL_SECONDS, 'Redirect deadline exceeded')
        self.count += 1
        require(self.count <= REDIRECT_CAP, 'Redirect limit exceeded')
        candidate = urllib.parse.urljoin(req.full_url, newurl)
        entry = dict(status_code=code, source=safe_url(req.full_url), destination=safe_url(candidate), allowed=False)
        self.ledger.append(entry)
        allowed_url(candidate)
        entry['allowed'] = True
        return super().redirect_request(req, fp, code, msg, headers, candidate)

    def http_error_302(self, req, fp, code, msg, headers):
        try:
            require(headers.get('Location') is not None, 'Redirect lacks Location')
            redirected = self.redirect_request(req, fp, code, msg, headers, headers['Location'])
        finally:
            fp.close()  # Never drain an unbounded redirect response body.
        remaining = WALL_SECONDS - (time.monotonic() - self.started)
        require(remaining > 0, 'Redirect total deadline exceeded')
        return self.parent.open(redirected, timeout=min(READ_SECONDS, remaining))

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def download_archive(work, spec, receipt, opener=None):
    started = time.monotonic()
    opener = opener or urllib.request.build_opener(SourceRedirect(receipt['redirects'], started))
    partial = work / (spec['filename'] + '.partial')
    request = urllib.request.Request(allowed_url(spec['url']), headers={
        'Accept-Encoding': 'identity', 'User-Agent': 'brbench-errmon-source/1.0'})
    print('source download start: ' + spec['filename'], flush=True)
    with partial.open('xb') as out:
        with opener.open(request, timeout=READ_SECONDS) as response:
            allowed_url(response.geturl())
            receipt['final_url_without_query'] = safe_url(response.geturl())
            receipt['response_headers'] = {k: response.headers[k] for k in HEADER_KEYS if k in response.headers}
            require(response.status == 200, 'Expected full HTTP200 source')
            require(response.headers.get('Content-Encoding', 'identity') == 'identity', 'Unexpected content encoding')
            length = response.headers.get('Content-Length', '')
            require(length.isdecimal() and int(length) == spec['size_bytes'], 'Published Content-Length mismatch')
            while True:
                require(time.monotonic() - started < WALL_SECONDS, 'Streaming deadline exceeded')
                size = receipt['received_bytes']
                require(size < CAP_BYTES, 'Transport cap reached before EOF')
                block = response.read(min(65536, spec['size_bytes'] - size + 1, CAP_BYTES - size))
                if not block:
                    break
                out.write(block)
                receipt['received_bytes'] += len(block)
                require(receipt['received_bytes'] <= spec['size_bytes'], 'Body exceeds published size')
    verify_file(partial, spec['size_bytes'], spec['sha256'], spec['md5'])
    archive = work / spec['filename']
    os.link(partial, archive)
    partial.unlink()  # Only our now-verified temporary hardlink is removed.
    archive.chmod(0o444)
    print('source download verified: ' + spec['filename'] + ' ' + str(spec['size_bytes']) + ' bytes', flush=True)
    return archive


class LimitedExpandedReader(io.RawIOBase):
    def __init__(self, stream):
        self.stream, self.count = stream, 0

    def readable(self):
        return True

    def read(self, size=-1):
        if size == 0:
            return b''
        require(self.count < EXPANDED_CAP, 'Expanded tar stream cap reached before EOF')
        amount = EXPANDED_CAP - self.count if size < 0 else min(size, EXPANDED_CAP - self.count)
        data = self.stream.read(amount)
        self.count += len(data)
        return data


def copy_members(archive_path, stage_dir, manifest):
    """Exact member allowlist, manual exclusive copies, no tar.extract APIs."""
    expected = {e['archive_member']: e for e in manifest['files']}
    seen, count, payload = set(), 0, 0
    with gzip.open(regular(archive_path), 'rb') as gz:
        bounded = LimitedExpandedReader(gz)
        with tarfile.open(fileobj=bounded, mode='r|') as archive:
            for member in archive:
                count += 1
                require(count <= MEMBER_CAP, 'Too many archive members')
                name = member.name
                require(name and not name.startswith('/') and '\\' not in name and ':' not in name and
                        '..' not in name.split('/') and not any(ord(c) < 32 or ord(c) == 127 for c in name),
                        'Unsafe archive path')
                canonical = PurePosixPath(name).as_posix()
                require(canonical not in seen, 'Duplicate archive member')
                seen.add(canonical)
                if canonical == 'MNE-ERP-CORE-data':
                    require(member.type == tarfile.DIRTYPE and member.size == 0, 'Invalid root directory')
                    continue
                require(canonical in expected, 'Unexpected archive member')
                e = expected[canonical]
                require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE) and member.size == e['size_bytes'],
                        'Nonregular or wrong-size source member')
                payload += member.size
                require(payload <= EXPANDED_CAP, 'Member payload cap exceeded')
                member_stream = archive.extractfile(member)
                require(member_stream is not None, 'Missing regular member stream')
                destination = stage_dir / e['path']
                copied = 0
                with destination.open('xb') as out:
                    while True:
                        block = member_stream.read(min(65536, member.size - copied + 1))
                        if not block:
                            break
                        copied += len(block)
                        require(copied <= member.size, 'Member payload exceeds size')
                        out.write(block)
                verify_file(destination, e['size_bytes'], e['sha256'])
                destination.chmod(0o444)
            require(seen == set(expected) | {'MNE-ERP-CORE-data'}, 'Incomplete exact archive inventory')
            while True:
                tail = archive.fileobj.read(65536)
                if not tail:
                    break
                require(not any(tail), 'Nonzero trailing archive payload')
    return dict(member_count=count, member_payload_bytes=payload, expanded_bytes=bounded.count)


def stage(destination, manifest_path, local_archive=None, opener=None):
    manifest, raw = read_manifest(manifest_path)
    destination = safe_path(destination)
    require(destination != destination.parent, 'Filesystem root cannot be a staging destination')
    if destination.exists():
        verify_staged(destination)
        return dict(status='verified_existing', network_used=False, destination=str(destination))
    if local_archive is not None:
        local_archive = regular(local_archive)
        require(destination not in local_archive.parents, 'Destination contains local original archive')
    destination.parent.mkdir(parents=True, exist_ok=True)
    work = safe_path(destination.parent / ('.' + destination.name + '-source-staging'))
    require(not work.exists(), 'Preserve existing staging receipts; use a fresh destination')
    work.mkdir(mode=0o755)
    work.chmod(0o755)
    receipt = dict(status='started', network_used=local_archive is None, received_bytes=0,
                   redirects=[], manifest_sha256=MANIFEST_SHA256, destination=str(destination))
    write_json(work / 'attempt.json', receipt)
    started = time.monotonic()
    try:
        with total_timeout(WALL_SECONDS):
            spec = manifest['archive']
            archive = local_archive if local_archive is not None else download_archive(work, spec, receipt, opener)
            verify_file(archive, spec['size_bytes'], spec['sha256'], spec['md5'])
            receipt['archive_hashes_verified'] = True
            receipt['archive_sha256'] = spec['sha256']
            temporary = work / 'members'
            temporary.mkdir(mode=0o755)
            temporary.chmod(0o755)
            receipt.update(copy_members(archive, temporary, manifest))
            # Claim a fresh destination exclusively; publish only verified original
            # files and write the manifest last. Any interrupted partial is retained.
            destination.mkdir(mode=0o755, exist_ok=False)
            destination.chmod(0o755)
            for e in manifest['files']:
                os.link(temporary / e['path'], destination / e['path'])
            with (destination / 'source_manifest.json').open('xb') as out:
                out.write(raw)
            (destination / 'source_manifest.json').chmod(0o444)
            verify_staged(destination)
            receipt.update(status='verified_staged', n_files=3)
    except Exception as error:
        receipt.update(status='failed_preserved', error_type=type(error).__name__, reason=safe_error(error))
        print('source staging failed: ' + receipt['reason'], flush=True)
        raise
    finally:
        receipt['elapsed_seconds'] = time.monotonic() - started
        write_json(work / 'result.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('/app/data/errmon'))
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('source_manifest.json'))
    parser.add_argument('--archive', type=Path, help='Explicit local complete original archive; never an implicit cache')
    parser.add_argument('--verify-existing', action='store_true', help='Offline verification only, no writes/download')
    args = parser.parse_args(argv)
    try:
        if args.verify_existing:
            require(args.archive is None, '--archive is not applicable to offline verification')
            manifest = verify_staged(args.destination)
            result = dict(status='verified_existing', network_used=False, n_files=len(manifest['files']),
                          manifest_sha256=MANIFEST_SHA256)
        else:
            result = stage(args.destination, args.manifest, args.archive)
    except Exception as error:
        print(json.dumps(dict(status='failed_preserved', reason=safe_error(error)), allow_nan=False))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
