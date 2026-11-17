"""Public fixed source-staging Linux PID1. Execs the unchanged N00657 controls."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import struct
import sys

FIXED_BYTES = 6584
FIXED_SHA = '325dbe77866b1f58e028cfad1a24ec267aec6f7cc1b5b726c355713e70405457'
BUNDLE_CAP = 524284


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def main():
    need(os.getpid() == 1 and sys.platform == 'linux' and platform.machine() == 'x86_64',
         'fixed private Linux amd64 PID 1')
    need(sys.version_info[:3] == (3, 11, 18) and sys.flags.isolated and
         sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize, 'fixed isolated Python 3.11.18')
    def exact(count):
        chunks = []; observed = 0
        while observed < count:
            part = sys.stdin.buffer.read(count - observed)
            need(part, 'complete bounded source frame')
            observed += len(part); chunks.append(part)
        return b''.join(chunks)
    size = struct.unpack('!I', exact(4))[0]
    need(0 < size <= BUNDLE_CAP, 'bounded length-prefixed source bundle')
    raw = exact(size)  # No dependence on Docker's interactive-stdin EOF semantics.
    bundle = json.loads(raw)
    need(set(bundle) == {'fixed_source_base64', 'files'}, 'closed bundle')
    fixed_raw = base64.b64decode(bundle['fixed_source_base64'], validate=True)
    need(len(fixed_raw) == FIXED_BYTES and digest(fixed_raw) == FIXED_SHA,
         'fixed immutable source selection')
    fixed = json.loads(fixed_raw)
    need(type(bundle['files']) is list and len(bundle['files']) == len(fixed['files']) == 17,
         'exact 17 source bodies')
    executable = Path('/usr/local/bin/python3').resolve(strict=True)
    with executable.open('rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 1048576, 'bounded image interpreter')
        executable_body = stream.read(info.st_size + 1)
    need(len(executable_body) == info.st_size, 'complete interpreter body from immutable image')
    need(os.getuid() == 65534 and os.getgid() == 65534, 'fixed unprivileged actor identity')
    runtime = {'schema':'n006-public-linux-runtime-v1','platform':sys.platform,'machine':platform.machine(),
        'python_version':list(sys.version_info[:3]),'pid':os.getpid(),'uid':os.getuid(),'gid':os.getgid(),
        'interpreter':{'path':str(executable),'bytes':len(executable_body),'sha256':digest(executable_body)},
        'identity_basis':'observed interpreter within separately verified immutable image config'}
    print('N006_RUNTIME '+json.dumps(runtime,sort_keys=True),file=sys.stderr,flush=True)
    base = Path(fixed['working_directory'])
    need(str(base) == '/n006', 'fixed public source staging root')
    for row, item in zip(fixed['files'], bundle['files']):
        need(set(item) == {'path', 'body_base64'} and item['path'] == row['path'], 'exact ordered source rows')
        relative=Path(row['path'])
        need(not relative.is_absolute() and '..' not in relative.parts and relative.as_posix()==row['path'], 'canonical relative source')
        path=base/relative
        need(path.is_relative_to(base), 'fixed source path')
        body = base64.b64decode(item['body_base64'], validate=True)
        need(len(body) == row['bytes'] and digest(body) == row['sha256'], 'source body identity')
        path.parent.mkdir(parents=True, exist_ok=True)
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary private source ancestry')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, 'wb') as stream:
            need(stream.write(body) == len(body), 'complete source write')
            stream.flush()
            os.fsync(stream.fileno())
    for directory, dirs, files in os.walk(base, topdown=False):
        os.chmod(directory, 0o555)
    os.chdir(base)
    args = ['/usr/local/bin/python3', '-I', '-S', '-B', 'engineering_controls_v5.py',
            '--manifest', 'OPERATIVE_SOURCES.json', '--manifest-bytes', '2515',
            '--manifest-sha256', 'cd80e46803c8164e93699761f37e8de40eda9821aae6a135533fbc23093d5a43']
    # exec preserves PID 1. Namespace-init death closes separate-session descendants.
    os.execve(args[0], args, {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
                            'TMPDIR': '/tmp', 'PYTHONDONTWRITEBYTECODE': '1'})


if __name__ == '__main__':
    main()
