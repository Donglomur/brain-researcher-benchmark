"""Bounded opaque immutable-Git staging. No scientific parser or source execution."""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import urllib.error
import urllib.request

SOURCE_SHA = '2e45467d3ef720a686b13a16ac33288369e3685044d243a5fe55128910adcfc8'
SUBJECTS = ['sub-sf02','sub-sf05','sub-sf06','sub-sf07','sub-sf08','sub-sf09','sub-sf10']
PREFIX = 'https://api.github.com/repos/OpenNeuroDatasets/ds005619/git/blobs/'
MAX_RESPONSE = 1048576
MAX_RESPONSE_TOTAL = 4194304
MAX_SECONDS = 120


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('duplicate JSON key')
            value[key] = item
        return value
    def walk(value, depth=0):
        if depth > 64: raise ValueError('JSON depth')
        if isinstance(value, float) and not math.isfinite(value): raise ValueError('nonfinite JSON')
        if isinstance(value, dict):
            for item in value.values(): walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value: walk(item, depth + 1)
    value = json.loads(raw, object_pairs_hook=pairs)
    walk(value)
    return value


def read_file(path, cap):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)): raise ValueError('symlink')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= cap:
            raise ValueError('regular file bound')
        with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(cap + 1)
        signature = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(raw) != before.st_size or signature(before) != signature(os.fstat(fd)) or signature(before) != signature(path.lstat()):
            raise ValueError('file changed')
        return raw
    finally: os.close(fd)


def manifest(path):
    raw = read_file(path, 1048576)
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA: raise ValueError('manifest identity')
    value = strict_json(raw); rows = value['files']
    if value['task_id'] != 'PETVT-001' or value['participant_ids'] != SUBJECTS or value['n_files'] != 31 or value['total_bytes'] != 481091:
        raise ValueError('source scope')
    if len(rows) != 31 or sum(r['size_bytes'] for r in rows) != 481091: raise ValueError('source count')
    paths = set()
    for row in rows:
        p = PurePosixPath(row['path'])
        if p.is_absolute() or str(p) != row['path'] or any(s in ('', '.', '..') for s in p.parts) or str(p) == 'source_manifest.json':
            raise ValueError('source path')
        if row['path'] in paths: raise ValueError('duplicate source path')
        paths.add(row['path'])
        if type(row['size_bytes']) is not int or not 0 < row['size_bytes'] <= 131072: raise ValueError('member bound')
        if not re.fullmatch('[0-9a-f]{40}', row['git_blob_sha1']) or not re.fullmatch('[0-9a-f]{64}', row['sha256']): raise ValueError('digest')
        if row['source_url'] != PREFIX + row['git_blob_sha1']: raise ValueError('fixed immutable endpoint')
    return raw, value


def authenticate(raw, row):
    git = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256'] or git != row['git_blob_sha1']:
        raise ValueError('source payload identity')
    return raw


def inventory(root):
    root = Path(root)
    if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)): raise ValueError('source directory')
    found = set()
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            if (Path(folder)/name).is_symlink(): raise ValueError('source directory symlink')
        for name in files:
            p = Path(folder)/name
            if p.is_symlink() or not stat.S_ISREG(p.lstat().st_mode): raise ValueError('source file type')
            found.add(p.relative_to(root).as_posix())
        if len(found) > 32: raise ValueError('closed inventory')
    return found


def verify(root, raw_manifest, value):
    if inventory(root) != {r['path'] for r in value['files']} | {'source_manifest.json'}: raise ValueError('closed inventory')
    if read_file(Path(root)/'source_manifest.json', 1048576) != raw_manifest: raise ValueError('internal manifest')
    for row in value['files']: authenticate(read_file(Path(root)/row['path'], row['size_bytes']), row)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


class Transport:
    def __init__(self):
        self.started = time.monotonic(); self.requests = 0; self.response_bytes = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def get(self, row):
        if self.requests >= 31 or time.monotonic() - self.started >= MAX_SECONDS: raise ValueError('transport bound')
        self.requests += 1
        request = urllib.request.Request(row['source_url'], headers={'Accept':'application/vnd.github+json','User-Agent':'PETVT-fixed-source/2'})
        try: response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as exc:
            exc.close(); raise ValueError('immutable endpoint HTTP failure') from None
        with response:
            if response.status != 200 or response.geturl() != row['source_url']: raise ValueError('HTTP status/redirect')
            chunks = []; count = 0
            while True:
                if time.monotonic() - self.started >= MAX_SECONDS: raise ValueError('transport wall bound')
                chunk = response.read1(min(65536, MAX_RESPONSE - count + 1))
                if not chunk: break
                count += len(chunk); self.response_bytes += len(chunk)
                if count > MAX_RESPONSE or self.response_bytes > MAX_RESPONSE_TOTAL: raise ValueError('response byte bound')
                chunks.append(chunk)
        envelope = strict_json(b''.join(chunks))
        if envelope.get('sha') != row['git_blob_sha1'] or envelope.get('size') != row['size_bytes'] or envelope.get('encoding') != 'base64':
            raise ValueError('Git blob envelope')
        content = envelope.get('content')
        if type(content) is not str: raise ValueError('Git blob encoding')
        return authenticate(base64.b64decode(content.replace('\n', ''), validate=True), row)


def stage(manifest_path, output, capture, *, source=None):
    raw_manifest, value = manifest(manifest_path)
    out = Path(output).absolute(); report = Path(capture).absolute()
    protected = [Path(manifest_path).absolute(), Path(__file__).absolute()]
    if source is not None: protected.append(Path(source).absolute())
    for p in (out, report):
        if any(a.is_symlink() for a in (p, *p.parents)): raise ValueError('destination symlink')
        if any(p == q or p in q.parents or q in p.parents for q in protected): raise ValueError('protected destination')
    if out == report or out in report.parents or report in out.parents: raise ValueError('destination overlap')
    if out.exists() or report.exists(): raise ValueError('fresh destinations required')
    report.mkdir(parents=True); pending = out.with_name(out.name + '.pending')
    transport = None
    attempt = {'status':'running','source_manifest_sha256':SOURCE_SHA,'n_files':31,'source_bytes':481091,
        'mode':'offline_copy' if source is not None else 'immutable_git_download','max_requests':31,
        'max_response_bytes':MAX_RESPONSE_TOTAL,'max_wall_seconds':MAX_SECONDS,'redirects':0,'retries':0}
    with (report/'attempt.json').open('x') as stream: json.dump(attempt, stream, indent=2)
    try:
        pending.mkdir(parents=True, exist_ok=False)
        if source is not None: verify(source, raw_manifest, value)
        else: transport = Transport()
        cache = {}
        for row in value['files']:
            key = row['git_blob_sha1']
            if source is not None: raw = authenticate(read_file(Path(source)/row['path'], row['size_bytes']), row)
            else:
                if key not in cache: cache[key] = transport.get(row)
                raw = authenticate(cache[key], row)
            target = pending/row['path']; target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream: stream.write(raw)
            target.chmod(0o444)
        with (pending/'source_manifest.json').open('xb') as stream: stream.write(raw_manifest)
        (pending/'source_manifest.json').chmod(0o444)
        verify(pending, raw_manifest, value)
        if source is not None: verify(source, raw_manifest, value)
        if out.exists(): raise ValueError('destination appeared')
        pending.rename(out)
        result = dict(attempt, status='ok', requests=transport.requests if transport else 0,
            response_bytes=transport.response_bytes if transport else 0, original_values_parsed=False)
        with (report/'result.json').open('x') as stream: json.dump(result, stream, indent=2)
        return result
    except Exception as exc:
        with (report/'failure.json').open('x') as stream:
            json.dump({'status':'failed','error_type':type(exc).__name__,'reason':str(exc)}, stream)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-staging', action='store_true')
    parser.add_argument('--manifest', default='/app/source_manifest.json')
    parser.add_argument('--output', default='/app/data/petvt')
    parser.add_argument('--capture', default='/opt/source_capture')
    parser.add_argument('--source')
    args = parser.parse_args(argv)
    if not args.execute_staging:
        print(json.dumps({'status':'plan_only','source_manifest_sha256':SOURCE_SHA,'network_requests':0})); return 0
    result = stage(args.manifest, args.output, args.capture, source=args.source)
    print(json.dumps({'status':result['status'],'n_files':result['n_files']})); return 0


if __name__ == '__main__': raise SystemExit(main())
