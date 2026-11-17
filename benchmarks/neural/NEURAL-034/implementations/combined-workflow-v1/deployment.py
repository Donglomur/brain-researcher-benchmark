"""Read-only selection of the original local image; never runtime qualification."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time

IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
LAYERS = [
    'sha256:3ec51339a507de1c80397e41016d23da1e6fa610d7176da42ce5e46fb2ce4686',
    'sha256:8651006d981438bb177061cc65a4a0caf7de6f150852f8152d1ae0f66fe1df2f',
    'sha256:f50074a9c5e2d05527d12a7bd8fbdaf2f1ebc205736223c5138d9cc5daa05d68',
    'sha256:5dfa3ddcd28d673815d78eb924a712a545d6adbd14611213f9a5540e8b7001fd',
    'sha256:9f185db3205ef1f4bdd643cb89dfad2b9b1c583eca1893a2c47660d7a5021b53',
    'sha256:98e9c34e4d8f9339cc9df654eb454420a63cd4001a4dd4b2482b25adbf4edfae',
]
FIELDS = {'id': '.Id', 'os': '.Os', 'architecture': '.Architecture',
          'size': '.Size', 'layers': '.RootFS.Layers',
          'entrypoint': '.Config.Entrypoint', 'command': '.Config.Cmd',
          'user': '.Config.User', 'working_directory': '.Config.WorkingDir'}
FORMAT = '{' + ','.join('"' + k + '":{{json ' + v + '}}' for k, v in FIELDS.items()) + '}'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def decode(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate metadata key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite metadata'))


def literal(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         not any(c in str(path) for c in '\0\r\n') and
         all(not item.is_symlink() for item in (path, *path.parents)), 'Literal unlinked path')
    return path


def read(path, cap):
    path = literal(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= cap, 'Bounded ordinary source or metadata')
        chunks = []
        left = before.st_size
        while left:
            part = os.read(fd, min(left, 65536))
            need(part, 'Truncated source or metadata')
            chunks.append(part); left -= len(part)
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        after, linked = os.fstat(fd), path.lstat()
        need(not os.read(fd, 1) and all(getattr(before, k) == getattr(after, k) == getattr(linked, k)
             for k in keys), 'Changed source or metadata')
        return b''.join(chunks)
    finally:
        os.close(fd)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def validate_image(value):
    need(type(value) is dict and set(value) == set(FIELDS), 'Exact selected image metadata fields')
    need(value['id'] == IMAGE and value['os'] == 'linux' and value['architecture'] == 'arm64',
         'Original immutable Linux ARM64 image required; no tag or successor fallback')
    need(type(value['size']) is int and value['size'] == 539583315 and value['layers'] == LAYERS,
         'Original image extent and ordered layer identities')
    need(value['entrypoint'] is None and value['command'] == ['python3'] and
         value['user'] == '' and value['working_directory'] == '/work', 'Original image configuration')
    return {'schema': 'neural034-original-image-availability/v1', 'image': value,
            'available': True, 'runtime_qualified': False, 'package_versions_executed': False,
            'numerical_compatibility_executed': False, 'participant_isolation_executed': False}


def transport(binary, host, config):
    binary = literal(binary)
    need(binary.is_file() and os.access(binary, os.X_OK), 'Existing canonical Docker executable')
    need(type(host) is str and host.startswith('unix:///') and
         not any(c in host for c in '\0\r\n?#'), 'Explicit local Unix Engine transport')
    socket = literal(host[7:])
    need(stat.S_ISSOCK(socket.stat().st_mode), 'Existing literal Engine socket')
    config = literal(config)
    need(config.is_dir() and set(p.name for p in config.iterdir()) <= {'config.json'},
         'Dedicated Docker config without credentials or contexts')
    if (config / 'config.json').exists():
        need(decode(read(config / 'config.json', 32)) == {}, 'Empty owned Docker config')
    env = {k: v for k, v in os.environ.items() if not k.startswith('DOCKER_')}
    return [str(binary), '--host', host, '--config', str(config)], env


def bounded_cli(argv, env, seconds=10, cap=16384):
    """Bound stdout+stderr while reading; stop and reap only this CLI group."""
    proc = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    data = {1: bytearray(), 2: bytearray()}
    end = time.monotonic() + seconds
    try:
        with selectors.DefaultSelector() as select:
            for stream, number in ((proc.stdout, 1), (proc.stderr, 2)):
                os.set_blocking(stream.fileno(), False)
                select.register(stream, selectors.EVENT_READ, number)
            while select.get_map():
                need(time.monotonic() < end, 'Image metadata CLI deadline')
                for event, _ in select.select(max(0, min(.1, end - time.monotonic()))):
                    part = os.read(event.fileobj.fileno(), min(4096, cap + 1))
                    if not part:
                        select.unregister(event.fileobj)
                    else:
                        data[event.data].extend(part)
                        need(sum(map(len, data.values())) <= cap, 'Image metadata CLI output cap')
            code = proc.wait(timeout=max(.001, end - time.monotonic()))
        need(code == 0 and not data[2], 'Exact image inspection succeeded without stderr')
        return bytes(data[1])
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=1)
        proc.stdout.close(); proc.stderr.close()


def observe(binary, host, config):
    argv, env = transport(binary, host, config)
    body = bounded_cli(argv + ['image', 'inspect', IMAGE, '--format', FORMAT], env)
    result = validate_image(decode(body))
    result.update(docker_binary=str(binary), docker_host=host, observation_pin=pin(body))
    return result
