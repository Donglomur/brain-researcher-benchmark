"""Fetch/verify the exact ordinary upstream source set; never execute it.

No source hash or receipt confers data, native, scientific or redistribution
rights. The destination is a new external tree, outside the shipped source.
Supported atomic publication: Linux renameat2/NOREPLACE or Darwin
renameatx_np/EXCL. Unsupported hosts/filesystems refuse without a fallback.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import urllib.error
import urllib.request

SPEC_SHA256 = '173e1f258b81018ee486fabaad7d5db9b1d6d1c11c23b2d9c76eb15d82e0904f'
COMMIT = '5b0f9a47970151416aeffaf0302c9abd88c5faf1'
MAX_FILES = 35
MAX_MEMBER = 1048576
MAX_TOTAL = 1048576
MAX_DIRECTORIES = 64
CHUNK = 65536
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


class Refusal(ValueError):
    pass


class Owner:
    """Raw first and ordered cleanup errors; no exception formatting/hooks."""
    def __init__(self):
        self.errors = []
        self.published = False
        self.publication_durability = 'not-published'
        self.read_bytes = 0
        self.write_bytes = 0
        self.verified_paths = set()
        self.partial_stage = None
        self.cleanup_complete = True

    def catch(self, stage, error):
        self.errors.append((stage, error, BaseException.__traceback__.__get__(error)))

    def attempt(self, stage, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except BaseException as error:
            self.catch(stage, error)
            return None

    def raise_first(self):
        if self.errors:
            _, error, tb = self.errors[0]
            raise BaseException.with_traceback(error, tb)

    def report(self):
        return {'published': self.published,
                'publication_durability': self.publication_durability,
                'verified_files': len(self.verified_paths),
                'source_read_bytes': self.read_bytes,
                'source_write_bytes': self.write_bytes,
                'error_stages': [e[0] for e in self.errors],
                'partial_stage': self.partial_stage,
                'cleanup_complete': self.cleanup_complete,
                'physical_resource_qualification': False,
                'scientific_qualification': False,
                'rights_grant': False}


def parts(name):
    if not isinstance(name, str) or not name or len(name) > 240:
        raise Refusal('invalid relative source path')
    p = name.split('/')
    if any(x in ('', '.', '..') or '\\' in x or '\0' in x for x in p):
        raise Refusal('unsafe relative source path')
    if any(not all(c.isascii() and (c.isalnum() or c in '._-') for c in x) for x in p):
        raise Refusal('nonliteral source path')
    return p


def validate_spec(spec, *, production=True):
    if not isinstance(spec, dict) or spec.get('commit') != COMMIT:
        raise Refusal('wrong upstream commit')
    files = spec.get('files')
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise Refusal('invalid source extent')
    if production and len(files) != MAX_FILES:
        raise Refusal('all35 upstream members are mandatory')
    names = set(); total = 0; directories = set()
    for row in files:
        pp = parts(row['path']); name = row['path']
        if name in names or row.get('alias') != 'payload/author_v4_0_2/' + name:
            raise Refusal('duplicate or changed upstream alias')
        names.add(name)
        for i in range(1, len(pp)): directories.add('/'.join(pp[:i]))
        n = row['bytes']
        if type(n) is not int or not 0 <= n <= MAX_MEMBER:
            raise Refusal('member extent refused')
        total += n
        for field, length in [('sha256', 64), ('git_blob', 40)]:
            v = row[field]
            if not isinstance(v, str) or len(v) != length or any(c not in '0123456789abcdef' for c in v):
                raise Refusal('invalid exact source identity')
        expected = 'https://raw.githubusercontent.com/MouseLand/Kilosort/' + COMMIT + '/' + name
        if row.get('source_url') != expected:
            raise Refusal('only the immutable official source URL is allowed')
    if names & directories or len(directories) > MAX_DIRECTORIES or total > MAX_TOTAL:
        raise Refusal('tree extent or file/directory collision')
    if spec.get('total_bytes') != total or spec.get('file_count') != len(files):
        raise Refusal('extent declaration differs')
    if production:
        licence = next((r for r in files if r['path'] == 'LICENSE'), None)
        if licence is None or licence['sha256'] != '3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986':
            raise Refusal('exact upstream licence is mandatory')
    return tuple(files), tuple(sorted(directories, key=lambda p: (p.count('/'), p)))


def load_spec(*, owner=None):
    # One original public owner retains manifest admission/read/close events.
    owner = owner if owner is not None else Owner()
    path = Path(__file__).with_name('UPSTREAM_SOURCE_MANIFEST.json')
    fd = None; data = None
    try:
        # NONBLOCK prevents an expected-name FIFO blocking before fstat.
        # NOFOLLOW and descriptor-kind checks remain necessary after opening.
        fd = os.open(path, FILE_FLAGS)
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > 65536:
            raise Refusal('manifest is not bounded ordinary metadata')
        chunks = []; size = 0
        while True:
            b = os.read(fd, min(CHUNK, 65537 - size))
            if not b: break
            size += len(b)
            if size > 65536: raise Refusal('manifest exceeds bound')
            chunks.append(b)
        data = b''.join(chunks)
        if hashlib.sha256(data).hexdigest() != SPEC_SHA256:
            raise Refusal('changed dependency manifest')
    except BaseException as error: owner.catch('manifest-read', error)
    finally:
        if fd is not None: owner.attempt('manifest-close', os.close, fd)
    owner.raise_first()
    spec = json.loads(data); validate_spec(spec)
    return spec


def absolute_parts(path):
    s = os.fspath(path)
    if not isinstance(s, str) or not s.startswith('/') or s == '/':
        raise Refusal('explicit absolute external destination required')
    p = s.split('/')[1:]
    if any(x in ('', '.', '..') or '\0' in x for x in p):
        raise Refusal('unsafe absolute path')
    return p


def open_directory(path, owner):
    pp = absolute_parts(path)
    fd = os.open('/', DIR_FLAGS)
    try:
        for part in pp:
            nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
            previous = fd; fd = nxt
            try: os.close(previous)
            except BaseException as error:
                owner.catch('path-parent-close', error)
                owner.attempt('path-next-close-after-parent-close-failure', os.close, fd)
                fd = None
                owner.raise_first()
        return fd
    except BaseException as error:
        if not owner.errors or owner.errors[0][1] is not error: owner.catch('path-traversal', error)
        if fd is not None: owner.attempt('path-failed-close', os.close, fd)
        owner.raise_first()


def parent_and_leaf(destination, owner):
    pp = absolute_parts(destination); leaf = pp[-1]
    parts(leaf)
    parent = '/' + '/'.join(pp[:-1])
    if parent == '/': raise Refusal('use a dedicated private parent directory')
    fd = open_directory(parent, owner)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.geteuid() or st.st_mode & 0o022:
            raise Refusal('parent must be owned by this user and not group/world writable')
        return fd, leaf
    except BaseException as error:
        owner.catch('parent-admission', error)
        owner.attempt('parent-refusal-close', os.close, fd)
        owner.raise_first()


def rename_noreplace(parent_fd, source, destination):
    lib = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith('linux'):
        fn = getattr(lib, 'renameat2', None); flag = 1
    elif sys.platform == 'darwin':
        fn = getattr(lib, 'renameatx_np', None); flag = 4
    else: raise Refusal('atomic no-overwrite publication is unsupported on this platform')
    if fn is None: raise Refusal('atomic no-overwrite syscall binding unavailable')
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(parent_fd, os.fsencode(source), parent_fd, os.fsencode(destination), flag) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, owner):
        self.owner = owner

    def redirect_request(self, request, fp, code, message, headers, newurl):
        self.owner.catch('source-redirect', Refusal('source redirect refused; use the selected immutable URL'))
        self.owner.attempt('redirect-response-close', fp.close)
        self.owner.raise_first()


class OfficialTransport:
    def __init__(self, timeout):
        self.timeout = timeout

    def open(self, row, remaining_seconds, owner):
        request = urllib.request.Request(row['source_url'], headers={
            'User-Agent': 'Kilosort4-exact-source-preparation', 'Accept-Encoding': 'identity'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(owner))
        try:
            response = opener.open(request, timeout=min(self.timeout, remaining_seconds))
        except urllib.error.HTTPError as error:
            owner.catch('upstream-http-error', error)
            owner.attempt('http-error-response-close', error.close)
            owner.raise_first()
        try:
            if response.status != 200 or response.geturl() != row['source_url']:
                raise Refusal('unexpected upstream response')
            encoding = response.headers.get('Content-Encoding', 'identity')
            if encoding != 'identity': raise Refusal('encoded response refused')
            declared = response.headers.get('Content-Length')
            if declared is not None and int(declared) != row['bytes']:
                raise Refusal('declared response length differs')
            return response
        except BaseException:
            # Preserve the admission error even when independent response close fails.
            owner.catch('response-admission', sys.exception())
            owner.attempt('response-admission-close', response.close)
            owner.raise_first()


def copy_member(row, fd, stream, owner, deadline):
    sha = hashlib.sha256(); git = hashlib.sha1(b'blob ' + str(row['bytes']).encode() + b'\0')
    size = 0
    while True:
        if time.monotonic() >= deadline: raise TimeoutError('preparation wall deadline')
        b = stream.read(min(CHUNK, row['bytes'] - size + 1))
        if not isinstance(b, bytes): raise Refusal('transport returned nonbytes')
        owner.read_bytes += len(b)
        if len(b) > row['bytes'] - size: raise Refusal('source exceeds exact member extent')
        if not b: break
        sha.update(b); git.update(b); size += len(b)
        view = memoryview(b)
        while view:
            n = os.write(fd, view)
            if type(n) is not int or not 0 < n <= len(view): raise OSError('short/zero source write')
            owner.write_bytes += n; view = view[n:]
    if size != row['bytes'] or sha.hexdigest() != row['sha256'] or git.hexdigest() != row['git_blob']:
        raise Refusal('upstream source identity differs')
    os.fchmod(fd, 0o444); os.fsync(fd)
    owner.verified_paths.add(row['path'])


def verify_fd(root_fd, spec, owner, *, production=True, owned_stage=False):
    files, directories = validate_spec(spec, production=production)
    expected = {r['path']: r for r in files}; actual = set(); dirs = {'': root_fd}; opened = []
    try:
        for name in directories:
            pp = name.split('/'); parent = '/'.join(pp[:-1])
            fd = os.open(pp[-1], DIR_FLAGS, dir_fd=dirs[parent]); opened.append(fd); dirs[name] = fd
        for parent, fd in dirs.items():
            st = os.fstat(fd)
            if st.st_mode & 0o222 and not (owned_stage and parent == '' and stat.S_IMODE(st.st_mode) == 0o700 and st.st_uid == os.geteuid()):
                raise Refusal('prepared directory is writable')
            iterator = os.scandir(fd)
            try:
                seen = 0
                for entry in iterator:
                    seen += 1
                    if seen > MAX_FILES + MAX_DIRECTORIES:
                        raise Refusal('dependency-tree member bound exceeded')
                    name = entry.name
                    rel = parent + '/' + name if parent else name
                    if rel in directories: continue
                    if rel not in expected: raise Refusal('unexpected dependency-tree member')
                    actual.add(rel)
            except BaseException as error: owner.catch('dependency-inventory', error)
            finally: owner.attempt('dependency-inventory-close', iterator.close)
            owner.raise_first()
        if actual != set(expected): raise Refusal('incomplete dependency tree')
        for name, row in expected.items():
            pp = name.split('/'); fd = os.open(pp[-1], FILE_FLAGS, dir_fd=dirs['/'.join(pp[:-1])])
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != row['bytes'] or before.st_mode & 0o222:
                    raise Refusal('dependency must be exact read-only ordinary nonlinked file')
                sha = hashlib.sha256(); git = hashlib.sha1(b'blob ' + str(row['bytes']).encode() + b'\0'); size = 0
                while True:
                    b = os.read(fd, min(CHUNK, row['bytes'] - size + 1)); owner.read_bytes += len(b)
                    if not b: break
                    size += len(b)
                    if size > row['bytes']: raise Refusal('dependency grew during verification')
                    sha.update(b); git.update(b)
                after = os.fstat(fd)
                stable = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                if stable(before) != stable(after) or size != row['bytes'] or sha.hexdigest() != row['sha256'] or git.hexdigest() != row['git_blob']:
                    raise Refusal('changed dependency bytes')
                owner.verified_paths.add(row['path'])
            except BaseException as error: owner.catch('dependency-verification', error)
            finally: owner.attempt('dependency-file-close', os.close, fd)
            owner.raise_first()
    except BaseException as error:
        if not owner.errors or owner.errors[0][1] is not error: owner.catch('dependency-tree-verification', error)
    finally:
        for fd in reversed(opened): owner.attempt('dependency-directory-close', os.close, fd)
    owner.raise_first()


def verify_prepared(root, *, owner=None):
    owner = owner if owner is not None else Owner(); fd = None
    try:
        spec = load_spec(owner=owner); fd = open_directory(root, owner)
        verify_fd(fd, spec, owner)
    except BaseException as error:
        if not owner.errors or owner.errors[0][1] is not error: owner.catch('preparation-verification', error)
    finally:
        if fd is not None: owner.attempt('dependency-root-close', os.close, fd)
    owner.raise_first()
    return owner.report()


def _materialize(spec, destination, transport, *, wall_seconds, owner, production=True):
    """Actual engine; production caller fixes the source manifest and transport.

    The only alternate transport is a private engineering test seam. It grants
    no source authority: exact full content hashes, aliases and extent still run.
    """
    files, directories = validate_spec(spec, production=production)
    if not math.isfinite(wall_seconds) or not 0 < wall_seconds <= 3600:
        raise Refusal('wall bound must be positive and at most3600 seconds')
    deadline = time.monotonic() + wall_seconds
    parent_fd = None; stage = None; dirs = {}; created_files = []; created_dirs = []
    try:
        parent_fd, leaf = parent_and_leaf(destination, owner)
        try: os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError: pass
        else: raise FileExistsError('destination already exists; no reuse or overwrite')
        proposed_stage = '.' + leaf + '.staging-' + str(os.getpid()) + '-' + str(time.monotonic_ns())
        os.mkdir(proposed_stage, 0o700, dir_fd=parent_fd)
        stage = proposed_stage; owner.partial_stage = stage
        dirs[''] = os.open(stage, DIR_FLAGS, dir_fd=parent_fd)
        for name in directories:
            pp = name.split('/'); parent = '/'.join(pp[:-1])
            os.mkdir(pp[-1], 0o700, dir_fd=dirs[parent]); created_dirs.append(name)
            dirs[name] = os.open(pp[-1], DIR_FLAGS, dir_fd=dirs[parent])
        for row in files:
            fd = None; stream = None; before_errors = len(owner.errors)
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError('preparation wall deadline')
                pp = row['path'].split('/')
                fd = os.open(pp[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dirs['/'.join(pp[:-1])])
                created_files.append(row['path'])
                stream = transport.open(row, remaining, owner)
                copy_member(row, fd, stream, owner, deadline)
            except BaseException as error:
                if not any(event[1] is error for event in owner.errors[before_errors:]):
                    owner.catch('source-member', error)
            finally:
                if stream is not None: owner.attempt('source-stream-close', stream.close)
                if fd is not None: owner.attempt('source-file-close', os.close, fd)
            owner.raise_first()
        for name in sorted(dirs, key=lambda x: x.count('/'), reverse=True):
            if name: os.fchmod(dirs[name], 0o555)
            os.fsync(dirs[name])
        # Independently inspect actual staged bytes and complete membership before publication.
        verify_fd(dirs[''], spec, owner, production=production, owned_stage=True)
        if time.monotonic() >= deadline: raise TimeoutError('prepublication wall deadline')
        rename_noreplace(parent_fd, stage, leaf)
        owner.published = True; owner.partial_stage = None
        owner.publication_durability = 'published-root-seal-pending'
        # Darwin requires the moved directory writable. Only our owned root
        # remains0700 through atomic rename; actual byte membership is verified
        # before publication. Public verification refuses it until sealed.
        os.fchmod(dirs[''], 0o555)
        os.fsync(dirs[''])
        owner.publication_durability = 'published-parent-fsync-pending'
        os.fsync(parent_fd)
        owner.publication_durability = 'parent-fsync-returned'
    except BaseException as error:
        if not owner.errors or owner.errors[0][1] is not error: owner.catch('preparation', error)
    finally:
        if stage is not None and not owner.published:
            before_cleanup = len(owner.errors)
            for fd in dirs.values(): owner.attempt('stage-unseal', os.fchmod, fd, 0o700)
            for name in reversed(created_files):
                pp = name.split('/'); parent = '/'.join(pp[:-1])
                if parent in dirs: owner.attempt('stage-file-unlink', os.unlink, pp[-1], dir_fd=dirs[parent])
            for name in reversed(created_dirs):
                pp = name.split('/'); parent = '/'.join(pp[:-1])
                if parent in dirs: owner.attempt('stage-directory-remove', os.rmdir, pp[-1], dir_fd=dirs[parent])
            if parent_fd is not None: owner.attempt('stage-root-remove', os.rmdir, stage, dir_fd=parent_fd)
            owner.cleanup_complete = len(owner.errors) == before_cleanup
            if owner.cleanup_complete: owner.partial_stage = None
        for fd in reversed(list(dirs.values())): owner.attempt('owned-directory-close', os.close, fd)
        if parent_fd is not None: owner.attempt('owned-parent-close', os.close, parent_fd)
    owner.raise_first()
    return owner.report()


def prepare(destination, *, timeout_seconds, wall_seconds, owner=None):
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 300:
        raise Refusal('explicit request timeout must be positive and at most300 seconds')
    owner = owner if owner is not None else Owner()
    return _materialize(load_spec(owner=owner), destination, OfficialTransport(timeout_seconds), wall_seconds=wall_seconds, owner=owner)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare', 'verify'])
    p.add_argument('--destination', required=True)
    p.add_argument('--timeout-seconds', type=float)
    p.add_argument('--wall-seconds', type=float)
    args = p.parse_args(); owner = Owner()
    try:
        if args.mode == 'prepare':
            if args.timeout_seconds is None or args.wall_seconds is None:
                raise Refusal('prepare requires explicit request and whole-operation time bounds')
            prepare(args.destination, timeout_seconds=args.timeout_seconds, wall_seconds=args.wall_seconds, owner=owner)
        else: verify_prepared(args.destination, owner=owner)
    except BaseException as error:
        if not owner.errors or owner.errors[0][1] is not error: owner.catch('CLI', error)
        try: print(json.dumps(owner.report()), file=sys.stderr)
        except BaseException as reporting_error: owner.catch('CLI-report', reporting_error)
        owner.raise_first()
    print(json.dumps(owner.report()))


if __name__ == '__main__':
    main()
