"""Bounded outer supervisor for the exactly admitted trusted fixed control.

Maximum main deadline600 seconds plus separately bounded cleanup5 seconds.
This does not change the shared test-pool limits. It owns one direct child and
its new process group; workers started in separate sessions are not contained
by that group. Driver-group absence is never whole-tree closure attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import struct
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
MAX_SECONDS = 600
MAX_GRACE = 5
MAX_STREAM_BYTES = 1024**2
MAX_LOG_BYTES = 2*1024**2
MAX_RECEIPT_BYTES = 16384
READ_CHUNK = 65536
THREAD_ENV = {key: '1' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
    'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')}
ENVIRONMENT = {**THREAD_ENV, 'LANG': 'C', 'LC_ALL': 'C'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def ordinary(path):
    need(type(path) in (str, Path) or isinstance(path, Path), 'Primitive local path')
    path = Path(path)
    need(path.is_absolute() and len(str(path)) <= 4096, 'Absolute bounded path')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'No path symlinks')
    return path


def stamp(value):
    return tuple(getattr(value, key) for key in ('st_dev', 'st_ino', 'st_mode', 'st_nlink',
        'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def read_verified(path, expected, cap, *, capture=True, expected_size=None):
    need(digest(expected) and type(cap) is int and 0 < cap <= 64*1024**2, 'Bounded expected file identity')
    path = ordinary(path)
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb', buffering=0) as stream:
            fd = None
            before = os.fstat(stream.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
                 'Ordinary bounded source before reading')
            need(expected_size is None or before.st_size == expected_size, 'Exact source size')
            remaining, hashed, chunks = before.st_size, hashlib.sha256(), []
            while remaining:
                raw = stream.read(min(READ_CHUNK, remaining))
                need(type(raw) is bytes and 0 < len(raw) <= remaining, 'Exact bounded source stream')
                remaining -= len(raw); hashed.update(raw)
                if capture:
                    chunks.append(raw)
            need(stream.read(1) == b'' and hashed.hexdigest() == expected, 'Source extent and SHA')
            need(stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()), 'Stable authenticated source')
            return b''.join(chunks) if capture else before.st_size
    finally:
        if fd is not None:
            os.close(fd)


def canonical(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: need(False, 'Nonfinite JSON'))
    need(type(value) is dict and encoded(value) == raw, 'Canonical primitive object')
    return value


def prepare_command(argv):
    """Authenticate the exact existing runtime and driver before child launch."""
    need(type(argv) in (list, tuple) and len(argv) == 12
         and all(type(v) is str and 0 < len(v) <= 4096 for v in argv), 'Exact finite trusted command argv')
    argv = tuple(argv)
    need(argv[1:3] == ('-I', '-B') and argv[4::2] == (
        '--protocol', '--protocol-sha256', '--admission', '--admission-sha256'), 'Only fixed control flags')
    python, driver = ordinary(argv[0]), ordinary(argv[3])
    need(python == Path(sys.executable).resolve() and driver == HERE/'fixed_control.py', 'Only existing real interpreter and sibling driver')
    p_raw = read_verified(argv[5], argv[7], 65536)
    a_raw = read_verified(argv[9], argv[11], 16384)
    protocol, admission = canonical(p_raw), canonical(a_raw)
    need(protocol.get('schema') == 'language-selected-fixed-control-protocol/v1'
         and protocol.get('activity') == 'trusted_fixed_time_only_programme_pipeline_control', 'Explicit fixed control protocol')
    need(type(protocol.get('whole_seconds')) is int and 1 <= protocol['whole_seconds'] <= MAX_SECONDS,
         'Bounded inner control deadline')
    source_pins = protocol.get('source_pins')
    need(type(source_pins) is dict and digest(source_pins.get('fixed_control.py'))
         and digest(source_pins.get('supervise.py')), 'Protocol pins driver and this supervisor')
    own = read_verified(Path(__file__).absolute(), source_pins['supervise.py'], 131072)
    source = read_verified(driver, source_pins['fixed_control.py'], 131072)
    config = protocol.get('provider_config')
    need(type(config) is dict and type(config.get('python')) is dict, 'Pinned existing interpreter')
    runtime = config['python']
    need(set(runtime) == {'path', 'bytes', 'sha256', 'version'} and runtime['path'] == str(python)
         and runtime['version'] == sys.version.split()[0] and type(runtime['bytes']) is int
         and 0 < runtime['bytes'] <= 64*1024**2, 'Exact trusted interpreter metadata')
    runtime_bytes = read_verified(python, runtime['sha256'], 64*1024**2,
                                  capture=False, expected_size=runtime['bytes'])
    need(admission.get('schema') == 'language-fixed-control-admission/v1'
         and admission.get('protocol_sha256') == sha(p_raw)
         and admission.get('config_sha256') == sha(encoded(config))
         and type(admission.get('admitted_until_unix')) is int
         and time.time() < admission['admitted_until_unix'], 'Live root admission binds exact protocol/config')
    # Execute exactly the source bytes just authenticated, never reopen driver.
    wrapper = ('import sys\n__file__='+repr(str(driver))+'\n__package__=""\n'
        'sys.argv='+repr([str(driver), *argv[4:]])+'\n'
        'exec(compile('+repr(source)+',__file__,"exec",dont_inherit=True),globals())\n')
    command = (str(python), '-I', '-B', '-c', wrapper)
    proof = {'requested_command_sha256': sha(encoded(argv)), 'executed_command_sha256': sha(encoded(command)),
        'protocol_sha256': sha(p_raw), 'admission_sha256': sha(a_raw),
        'driver_sha256': sha(source), 'supervisor_sha256': sha(own),
        'runtime_sha256': runtime['sha256'], 'runtime_bytes': runtime_bytes,
        'protocol_whole_seconds': protocol['whole_seconds'],
        'verified_source_bytes_executed': True, 'source_reads_plus_eof_bytes':
            len(p_raw)+len(a_raw)+len(source)+len(own)+runtime_bytes+5}
    return command, proof


class Interrupted(RuntimeError):
    pass


class Log:
    """O/E byte plus little-endian uint32 length, then raw retained bytes."""
    def __init__(self, stream):
        self.stream, self.bytes, self.hashed = stream, 0, hashlib.sha256()
        self.observed = {'stdout': 0, 'stderr': 0}
        self.retained = {'stdout': 0, 'stderr': 0}
        self.discarded = 0
    def allowance(self, kind):
        return min(READ_CHUNK, MAX_STREAM_BYTES-self.retained[kind], max(0, MAX_LOG_BYTES-self.bytes-5))
    def consume(self, kind, raw, allowed):
        self.observed[kind] += len(raw)
        kept = raw[:allowed]
        self.discarded += len(raw)-len(kept)
        if kept:
            record = (b'O' if kind == 'stdout' else b'E')+struct.pack('<I', len(kept))+kept
            need(self.bytes+len(record) <= MAX_LOG_BYTES, 'Log cap before write')
            at = 0
            while at < len(record):
                count = self.stream.write(memoryview(record)[at:])
                need(type(count) is int and 0 < count <= len(record)-at, 'Exact log write progress')
                self.hashed.update(record[at:at+count]); self.bytes += count; at += count
            self.retained[kind] += len(kept)
        need(len(raw) <= allowed, 'Bounded stdout/stderr/log overflow')


def fresh_file(path):
    path = ordinary(path)
    need(path.parent.is_dir(), 'Existing ordinary output parent')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        return os.fdopen(fd, 'wb', buffering=0)
    except BaseException:
        os.close(fd)
        raise


def group_absent(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False


def cleanup(proc, grace, clock):
    """Never signal a numeric group once Popen records that it reaped child."""
    result = {'term_sent': False, 'kill_sent': False, 'child_reaped': proc.returncode is not None,
              'driver_group_absent': False, 'errors': []}
    end = clock()+grace
    def send(sig, key):
        if proc.returncode is None:
            try:
                os.killpg(proc.pid, sig); result[key] = True
            except ProcessLookupError:
                pass
            except BaseException as exc:
                result['errors'].append(type(exc).__name__)
    if proc.returncode is None:
        send(signal.SIGTERM, 'term_sent')
        try:
            proc.wait(timeout=max(0, min(grace/2, end-clock())))
        except BaseException as exc:
            result['errors'].append(type(exc).__name__)
    if proc.returncode is None:
        send(signal.SIGKILL, 'kill_sent')
        try:
            proc.wait(timeout=max(0, end-clock()))
        except BaseException as exc:
            result['errors'].append(type(exc).__name__)
    result['child_reaped'] = proc.returncode is not None
    if result['child_reaped']:
        try:
            result['driver_group_absent'] = group_absent(proc.pid)
        except BaseException as exc:
            result['errors'].append(type(exc).__name__)
    return result


def supervise(argv, *, deadline_seconds, grace_seconds, receipt, log, clock=time.monotonic):
    need(type(deadline_seconds) is int and 1 <= deadline_seconds <= MAX_SECONDS
         and type(grace_seconds) is int and 1 <= grace_seconds <= MAX_GRACE, 'At most600 seconds plus5 cleanup')
    need(os.name == 'posix' and threading.active_count() == 1
         and signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL, 'One POSIX child wait owner, default SIGCHLD')
    receipt_path, log_path = ordinary(receipt), ordinary(log)
    need(receipt_path != log_path, 'Distinct fresh receipt and log')
    started = clock(); deadline = started+deadline_seconds
    result = {'schema': 'language-fixed-control-outer-supervisor/v1', 'status': 'failed',
        'deadline_seconds': deadline_seconds, 'cleanup_seconds': grace_seconds,
        'maximum_combined_seconds': deadline_seconds+grace_seconds, 'pid': None, 'exit_code': None,
        'complete_driver_exit_zero': False, 'driver_group_absent': False, 'child_reaped': False,
        'descendant_closure_verified': False, 'native_containment_qualified': False,
        'scientific_qualification': False, 'log_format': 'channelOorE-u32le-length-rawbytes/v1',
        'stream_cap_bytes': MAX_STREAM_BYTES, 'log_cap_bytes': MAX_LOG_BYTES,
        'cleanup': None, 'source': None, 'error_type': None, 'error': None}
    receipt_stream = fresh_file(receipt_path)
    log_stream = proc = selector = logger = None
    pipes, old_handlers = [], {}
    failure = None; finalizing = False
    result['interrupt_signals'] = []
    try:
        log_stream = fresh_file(log_path); logger = Log(log_stream)
        def interrupted(signum, frame):
            if len(result['interrupt_signals']) < 8:
                result['interrupt_signals'].append(signum)
            if not finalizing:
                raise Interrupted('signal '+str(signum))
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            old_handlers[sig] = signal.getsignal(sig); signal.signal(sig, interrupted)
        command, proof = prepare_command(argv); result['source'] = proof
        need(proof['protocol_whole_seconds'] <= deadline_seconds, 'Outer bound includes declared inner deadline')
        need(clock() < deadline, 'Main deadline before launch')
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            close_fds=True, start_new_session=True, restore_signals=True, bufsize=0, cwd='/', env=dict(ENVIRONMENT))
        result['pid'] = proc.pid
        pipes = [proc.stdout, proc.stderr]; selector = selectors.DefaultSelector()
        for stream, kind in zip(pipes, ('stdout', 'stderr')):
            os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ, kind)
        while selector.get_map():
            remaining = deadline-clock(); need(remaining > 0, 'Main control deadline expired')
            for key, _ in selector.select(min(.05, remaining)):
                stream, kind = key.fileobj, key.data
                allowed = logger.allowance(kind)
                raw = os.read(stream.fileno(), min(READ_CHUNK, allowed+1))
                if raw:
                    logger.consume(kind, raw, allowed)
                else:
                    selector.unregister(stream); stream.close()
        need(clock() < deadline, 'Main control deadline before wait')
        result['exit_code'] = proc.wait(timeout=max(0, deadline-clock()))
        result['child_reaped'] = proc.returncode is not None
        result['driver_group_absent'] = group_absent(proc.pid)
        need(result['exit_code'] == 0 and result['driver_group_absent'], 'Natural zero driver exit and absent group')
        result['complete_driver_exit_zero'] = True; result['status'] = 'succeeded'
    except BaseException as exc:
        failure = exc
        result['status'] = 'interrupted' if isinstance(exc, (KeyboardInterrupt, Interrupted)) else 'failed'
        result['error_type'], result['error'] = type(exc).__name__, str(exc)[:512]
    finally:
        finalizing = True
        if proc is not None:
            # wait() may reap internally before propagating an interruption.
            # cleanup rechecks existing returncode before every signal.
            if failure is not None or proc.returncode is None:
                result['cleanup'] = cleanup(proc, grace_seconds, clock)
                result['child_reaped'] = result['cleanup']['child_reaped']
                result['driver_group_absent'] = result['cleanup']['driver_group_absent']
            result['exit_code'] = proc.returncode
        if selector is not None:
            try:
                selector.close()
            except BaseException as exc:
                failure = failure or exc; result['status'] = 'failed'
        for stream in pipes:
            try:
                stream.close()
            except BaseException as exc:
                failure = failure or exc; result['status'] = 'failed'
        result['pipes_closed'] = all(stream.closed for stream in pipes)
        if logger is not None:
            result['log'] = {'bytes': logger.bytes, 'sha256': logger.hashed.hexdigest(),
                'observed_pipe_bytes': logger.observed, 'retained_pipe_bytes': logger.retained,
                'discarded_overflow_bytes': logger.discarded}
        if log_stream is not None:
            try:
                log_stream.flush(); os.fchmod(log_stream.fileno(), 0o400)
            except BaseException as exc:
                failure = failure or exc; result['status'] = 'failed'
            finally:
                try:
                    log_stream.close()
                except BaseException as exc:
                    failure = failure or exc; result['status'] = 'failed'
        result['elapsed_seconds'] = max(0, clock()-started)
        result['scope_limit'] = ('Owns direct driver/group only. Separate-session workers require driver cooperative cleanup; '
            'forced driver death does not prove their absence. No arbitrary-descendant or hostile-code containment.')
        raw = encoded(result)
        try:
            need(len(raw) <= MAX_RECEIPT_BYTES, 'Bounded supervisor receipt')
            at = 0
            while at < len(raw):
                count = receipt_stream.write(memoryview(raw)[at:])
                need(type(count) is int and 0 < count <= len(raw)-at, 'Complete receipt write')
                at += count
            receipt_stream.flush(); os.fchmod(receipt_stream.fileno(), 0o400)
        finally:
            receipt_stream.close()
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deadline-seconds', type=int, required=True)
    parser.add_argument('--grace-seconds', type=int, required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--log', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    result = supervise(command, deadline_seconds=args.deadline_seconds, grace_seconds=args.grace_seconds,
                       receipt=args.receipt, log=args.log)
    return 0 if result['status'] == 'succeeded' else 2


if __name__ == '__main__':
    raise SystemExit(main())
