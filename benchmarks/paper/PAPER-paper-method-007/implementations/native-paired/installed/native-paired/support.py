"""Bounded ordinary operands for the UnitMatch paired study; no scientific imports."""
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time
import types

MICE = tuple(f'Mouse{i}' for i in range(1, 6))
SIZES = (534, 109, 96, 59, 466)
OFFICIAL_COMMIT = '6ef0023cb4a7be0a94dabbab24bb79c084b6fb1e'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def ordinary(path):
    p = Path(path).absolute()
    need('..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)), 'Unlinked literal path')
    need(not any(c in str(p) for c in '\0\r\n'), 'Unambiguous path')
    return p


def relative(value):
    need(type(value) is str and value and str(Path(value)) == value, 'Canonical relative path')
    p = Path(value)
    need(not p.is_absolute() and '..' not in p.parts, 'Safe relative path')
    return p


def identity(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def parse(raw):
    def pairs(rows):
        value = {}
        for k, v in rows:
            need(k not in value, 'Duplicate JSON key')
            value[k] = v
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


class Budget:
    """Prospective aggregate reservations, including full child envelopes and failures.

    This bounds controlled transfers. It is not an OS memory/disk quota for MATLAB.
    Child ceilings must additionally be admitted by the runtime operator.
    """
    def __init__(self, limits):
        keys = ('read_bytes', 'write_bytes', 'retained_bytes', 'functional_spikes',
                'functional_product_bytes', 'live_bytes', 'whole_seconds', 'other_bytes')
        need(all(type(limits.get(k)) is int and limits[k] > 0 for k in keys), 'Explicit positive study limits')
        self.limits = limits
        self.reads = self.writes = self.retained = 0
        self.end = time.monotonic() + limits['whole_seconds']
        self.charge(write=4096, retained=4096)  # prepaid final failure/success receipt

    def charge(self, read=0, write=0, retained=0):
        need(all(type(x) is int and x >= 0 for x in (read, write, retained)), 'Integer full-transfer reservations')
        need(time.monotonic() < self.end, 'Whole study deadline')
        # Charge attempted transfers before effects, including failed operations.
        r, w, s = self.reads + read, self.writes + write, self.retained + retained
        need(r <= self.limits['read_bytes'] and w <= self.limits['write_bytes']
             and s <= self.limits['retained_bytes'], 'Complete study transfer envelope')
        self.reads, self.writes, self.retained = r, w, s

    def record(self):
        return dict(reserved_read_bytes=self.reads, reserved_write_bytes=self.writes,
                    reserved_retained_bytes=self.retained)


def capture(path, cap, pin=None, budget=None):
    p = ordinary(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 <= a.st_size <= cap, 'Bounded ordinary file')
        if pin is not None:
            need(a.st_size == pin['bytes'], 'Exact operand extent')
        if budget:
            budget.charge(read=a.st_size + 1)
        with os.fdopen(fd, 'rb', closefd=False) as f:
            body = f.read(a.st_size + 1)
        z = os.fstat(fd)
        keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        need(len(body) == a.st_size and all(getattr(a, k) == getattr(z, k) for k in keys), 'Stable same-open capture')
        if pin is not None:
            need(identity(body) == {k: pin[k] for k in ('bytes', 'sha256')}, 'Exact operand bytes')
        return body
    finally:
        os.close(fd)


def save(path, body, budget=None):
    p = ordinary(path)
    need(type(body) is bytes and not p.exists(), 'Fresh exact output')
    if budget:
        budget.charge(write=len(body), retained=len(body))
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as f:
            f.write(body)
            f.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    return identity(body)


def executable(path, pin, budget):
    """Same-open streaming identity for a prospectively selected external binary."""
    p = ordinary(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_mode & 0o111
             and a.st_size == pin['bytes'], 'Selected ordinary executable extent')
        budget.charge(read=a.st_size+1)
        digest = hashlib.sha256(); count = 0
        while True:
            block = os.read(fd, min(1048576, a.st_size-count+1))
            if not block:
                break
            count += len(block)
            need(count <= a.st_size, 'Executable grew during capture')
            digest.update(block)
        z = os.fstat(fd)
        keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink')
        need(count == a.st_size and all(getattr(a,k) == getattr(z,k) for k in keys)
             and digest.hexdigest() == pin['sha256'], 'Stable selected executable bytes')
        return {'path': str(p), 'bytes': count, 'sha256': digest.hexdigest()}
    finally:
        os.close(fd)


def module(name, body, path):
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(body, str(path), 'exec'), mod.__dict__)
    return mod


def process(argv, cwd, output, seconds, budget, env=None):
    """Actual fixed child dispatch; preserve both raw streams on failure or timeout.

    No provider callback is part of the operational interface. Controls may patch
    subprocess at its boundary, and are explicitly labelled invented.
    """
    need(type(seconds) is int and seconds > 0, 'Explicit child deadline')
    output = ordinary(output)
    output.mkdir()
    cap = 1024 * 1024
    budget.charge(read=2 * (cap + 1), write=2 * (cap + 1)+16384, retained=2 * (cap + 1)+16384)
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    end = min(budget.end, time.monotonic() + seconds)
    p = sel = None
    error = None
    error_message = None
    eof = {'stdout': False, 'stderr': False}
    started = time.monotonic()
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True, bufsize=0)
        sel = selectors.DefaultSelector()
        for key, f in [('stdout', p.stdout), ('stderr', p.stderr)]:
            os.set_blocking(f.fileno(), False)
            sel.register(f, selectors.EVENT_READ, key)
        while sel.get_map():
            need(time.monotonic() < end, 'Child deadline')
            for key, _ in sel.select(min(.05, max(.001, end - time.monotonic()))):
                b = os.read(key.fileobj.fileno(), min(65536, cap - len(buffers[key.data]) + 1))
                if not b:
                    eof[key.data] = True
                    sel.unregister(key.fileobj)
                else:
                    # The single over-limit byte is preserved, not discarded.
                    buffers[key.data].extend(b)
                    need(len(buffers[key.data]) <= cap, 'Child stream cap')
        rc = p.wait(timeout=max(.001, end - time.monotonic()))
        need(time.monotonic() < end and rc == 0, 'Natural zero within deadline')
    except BaseException as exc:
        error = type(exc).__name__
        error_message = str(exc)
    finally:
        cleanup_errors = []
        def finish(label, action):
            try:
                return action()
            except BaseException as exc:
                cleanup_errors.append({'operation': label, 'error_type': type(exc).__name__})
                return None
        if p is not None and finish('poll', p.poll) is None:
            def kill():
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            finish('kill_owned_group', kill)
            finish('reap_owned_process', lambda: p.wait(timeout=5))
        # On failure retain all bounded post-termination observations as well.
        # A cap/cleanup failure explicitly leaves incomplete stream capture.
        if error and sel is not None:
            drain_end = time.monotonic()+1
            def drain():
                while sel.get_map() and time.monotonic() < drain_end:
                    for key, _ in sel.select(.01):
                        room = cap+1-len(buffers[key.data])
                        if room <= 0:
                            sel.unregister(key.fileobj)
                            continue
                        b = os.read(key.fileobj.fileno(), min(65536, room))
                        if not b:
                            eof[key.data] = True
                            sel.unregister(key.fileobj)
                        else:
                            buffers[key.data].extend(b)
            finish('bounded_failure_drain', drain)
        if sel is not None:
            finish('selector_close', sel.close)
        if p is not None:
            finish('stdout_pipe_close', p.stdout.close)
            finish('stderr_pipe_close', p.stderr.close)
        streams = {}
        for k, v in buffers.items():
            raw = bytes(v)
            saved = finish(k+'_save', lambda k=k, raw=raw: save(output/(k+'.bin'), raw))
            streams[k] = {**identity(raw), 'retained': saved is not None}
        receipt = {'argv': argv, 'cwd': str(cwd), 'returncode': None if p is None else p.returncode,
                   'error': error, 'error_message': error_message, 'streams': streams, 'stream_eof': eof,
                   'elapsed_seconds': time.monotonic() - started,
                   'finalization_errors': cleanup_errors,
                   'natural_zero': error is None and not cleanup_errors and p is not None and p.returncode == 0}
        receipt_body = encoded(receipt)
        need(len(receipt_body) <= 16384, 'Prepaid process receipt extent')
        finish('process_receipt_save', lambda: save(output/'PROCESS.json', receipt_body))
        if cleanup_errors:
            receipt['natural_zero'] = False
    need(receipt['natural_zero'], 'Child failed; original streams retained')
    return receipt


def full_cohort(cohort):
    need(tuple(m['mouse_id'] for m in cohort['mice']) == MICE
         and tuple(len(m['units']) for m in cohort['mice']) == SIZES, 'Complete five-mouse study')
    for mouse in cohort['mice']:
        sessions = mouse['sessions']
        need([s['session'] for s in sessions] == [1, 2], 'Both original recordings')
        expected = [{'session': s['session'], 'cluster_id': cid}
                    for s in sessions for cid in s['good_cluster_ids']]
        need(mouse['units'] == expected and len({(u['session'], u['cluster_id']) for u in expected}) == len(expected),
             'Unchanged original ordered Good_ID identities')
    return cohort
