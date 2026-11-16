"""Whole-cohort candidate execution; operator-private capture and late grading.

Run requires an externally admitted Docker daemon/image, complete authentic
packet and operator environment. Source hashes do not issue that authority.
No candidate programme executes on the host. Generated tests use a fake daemon.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

import safe_io as safe
from absence import absence
import runtime_contract as contract

HERE = Path(__file__).resolve().parent
SHA = re.compile('[0-9a-f]{64}')


def lexical_path(value):
    """Post-bootstrap role spelling only; no metadata or path resolution."""
    safe.need(type(value) is str and value and not any(c in value for c in '\x00\n\r'),
              'Explicit lexical path')
    path=Path(value)
    safe.need(path.anchor=='/' and str(path)==value and '..' not in path.parts,
              'Canonical single-root local POSIX path')
    return path


def plain_path(value):
    safe.need(type(value) is str and value and '\x00' not in value,
              'Explicit ordinary path')
    path = Path(value)
    safe.need(path.is_absolute() and str(path) == value and '..' not in path.parts and
              all(not p.is_symlink() for p in (path, *path.parents)), 'Canonical no-link path')
    return path


def pin(value, cap):
    safe.need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
              type(value['bytes']) is int and 0 < value['bytes'] <= cap and
              type(value['sha256']) is str and SHA.fullmatch(value['sha256']), 'Exact bounded pin')
    return value


def read_pinned(path, value, cap):
    raw = safe.read(path, cap)
    safe.need(len(raw) == value['bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256'],
              'Exact pinned content')
    return raw


def write_bytes(path, raw, mode=0o444):
    path = plain_path(str(path)); fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, mode)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def bounded_command(argv, env, end, seconds, cap=131072):
    remaining = min(seconds, end - time.monotonic())
    safe.need(remaining > 0, 'Command deadline')
    proc = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, close_fds=True)
    parts = [bytearray(), bytearray()]; selector = selectors.DefaultSelector()
    for i, stream in enumerate((proc.stdout, proc.stderr)):
        os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, i)
    deadline = time.monotonic() + remaining
    try:
        while selector.get_map():
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError('Owned command wall deadline')
            for key, _ in selector.select(min(left, .1)):
                block = os.read(key.fd, min(65536, cap + 1 - len(parts[key.data])))
                if not block:
                    selector.unregister(key.fileobj); continue
                parts[key.data].extend(block)
                if len(parts[key.data]) > cap:
                    raise ValueError('Owned command output cap; prefix retained on error')
        code = proc.wait(timeout=max(.001, deadline-time.monotonic()))
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError('Owned CLI descendants still live')
        return {'returncode': code, 'stdout': bytes(parts[0]).decode('utf8', 'replace'),
                'stderr': bytes(parts[1]).decode('utf8', 'replace')}
    except BaseException as error:
        secondary = []
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except BaseException as cleanup_error:
            secondary.append(repr(cleanup_error))
        try:
            proc.wait(timeout=5)
        except BaseException as cleanup_error:
            secondary.append(repr(cleanup_error))
        error.command_observation = {'argv': argv, 'stdout_prefix': bytes(parts[0]).decode('utf8', 'replace'),
            'stderr_prefix': bytes(parts[1]).decode('utf8', 'replace'), 'secondary': secondary}
        raise
    finally:
        selector.close(); proc.stdout.close(); proc.stderr.close()


class Docker:
    def __init__(self, r, output, end):
        self.r, self.output, self.end = r, output, end
        self.owned = []; self.calls = []; self.cleanup_rows = []
        self.env = {k: os.environ[k] for k in ('HOME', 'PATH', 'TMPDIR') if k in os.environ}
        self.env.update(DOCKER_HOST=r['docker_host'], DOCKER_CONFIG=r['docker_config'])

    def call(self, argv, seconds=10):
        safe.need(len(self.calls) < 128, 'Complete operation Docker command allowance including cleanup')
        row = {'argv': argv}
        try:
            result = bounded_command([self.r['docker'], *argv], self.env, self.end, seconds)
            row.update(result); return result
        except BaseException as error:
            row.update(error=repr(error), original=getattr(error, 'command_observation', None)); raise
        finally:
            self.calls.append(row)
            safe.write_new(self.output / f'command-{len(self.calls):04d}.json', row, 2200000)

    def missing(self, kind, name):
        result = self.call(['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name])
        return absence(result['returncode'], result['stdout'], result['stderr'], kind, name)

    def own(self, kind, name):
        safe.need(self.missing(kind, name), 'Exact resource absent before ownership')
        self.owned.append((kind, name))
        safe.write_new(self.output / f'ownership-{len(self.owned):02d}.json',
                       {'kind': kind, 'name': name, 'attempt_recorded_before_create': True}, 4096)

    def inspect(self, kind, name):
        row = self.call(['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name])
        safe.need(row['returncode'] == 0, 'Successful resource inspect')
        rows = safe.strict(row['stdout'])
        safe.need(type(rows) is list and len(rows) == 1 and rows[0]['Name'] ==
                  (name if kind == 'volume' else '/' + name), 'Exact single resource identity')
        return rows[0]

    def volume(self, name):
        self.own('volume', name)
        result = self.call(['volume', 'create', '--driver', 'local', '--opt', 'type=tmpfs',
            '--opt', 'device=tmpfs', '--opt', 'o=' + contract.VOLUME_OPTIONS, name])
        safe.need(result['returncode'] == 0, 'Output volume creation')
        row = self.inspect('volume', name)
        safe.need(row['Driver'] == 'local' and row['Options'] == {'type': 'tmpfs',
            'device': 'tmpfs', 'o': contract.VOLUME_OPTIONS}, 'Complete bounded memory-backed output')

    def create(self, name, role, mounts):
        argv = contract.create_argv(name, role, mounts, self.r)
        self.own('container', name); result = self.call(argv)
        safe.need(result['returncode'] == 0, 'Container creation')
        return contract.verify(self.inspect('container', name), name, role, mounts, self.r)

    def remove(self, kind, name):
        result = self.call(['volume', 'rm', name] if kind == 'volume' else ['rm', '--force', name])
        closed = self.missing(kind, name)
        row = {'kind': kind, 'name': name, 'removal': result, 'absence_verified': closed}
        self.cleanup_rows.append(row)
        safe.need(closed, 'Owned resource absence before capture/grade')

    def close(self):
        errors = []
        for kind, name in reversed(self.owned):
            if any(x['kind'] == kind and x['name'] == name and x['absence_verified'] for x in self.cleanup_rows):
                continue
            try:
                self.remove(kind, name)
            except BaseException as error:
                errors.append({'kind': kind, 'name': name, 'error': repr(error)})
        return errors


