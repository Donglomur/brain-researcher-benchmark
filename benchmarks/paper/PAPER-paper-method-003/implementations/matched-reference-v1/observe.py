#!/usr/bin/env python3
"""Observe the unchanged REVE operator, without admitting scientific execution.

Only phase names, counters, elapsed time and process memory enter the trace.
Inputs, outputs, exceptions, labels and scientific scores are never serialized.
The enclosing operator still owns source/runtime admission and resource limits.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import stat
import sys
import time
from types import ModuleType

HERE = Path(__file__).resolve().parent
PINS = {
    'run.py': 'ace54d034e1d0183fa19a491bd801900f2214f421a66c70d2e27745ddb9bc040',
    'native.py': '97bc837cd49fb4f76394bd553258aa7b8d93ac8b1abbe9205ec25f03b3709fc1',
    'recipe.py': '0d515204b447d343b10dc9687d5d63e901f46b77e5dad69f1a2daebae9d88b0a',
}
PHASES = {
    'operation', 'construct', 'begin_stage', 'train_batch', 'train_epoch',
    'validation', 'snapshot_selected', 'restore_selected', 'save_checkpoint',
}
METHODS = {
    '__init__': 'construct', 'begin_stage': 'begin_stage',
    'train_batch': 'train_batch', 'train_epoch': 'train_epoch',
    'validation_metrics': 'validation', 'snapshot_selected': 'snapshot_selected',
    'restore_selected': 'restore_selected', 'save_checkpoint': 'save_checkpoint',
}
FAILURES = {
    'clock', 'rss_high_water', 'rss_current', 'event_limit', 'byte_limit',
    'trace_write', 'source_changed', 'operation_failed', 'unfinished_phase',
}
MAX_SOURCE_BYTES = 64 * 1024


def high_water_rss():
    """Current process lifetime high-water RSS, never an independent phase peak."""
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == 'darwin':
        return int(value)
    if sys.platform.startswith('linux'):
        return int(value) * 1024
    raise OSError('unsupported RSS units')


@functools.lru_cache(maxsize=1)
def _darwin_reader():
    # Darwin SDK sys/proc_info.h: proc_taskinfo has six uint64 and twelve int32.
    # PROC_PIDTASKINFO=4; pti_resident_size is bytes. No subprocess is launched:
    # the maintained CPU profile deliberately refuses subprocess.Popen.
    class TaskInfo(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            'virtual_size', 'resident_size', 'total_user', 'total_system',
            'threads_user', 'threads_system')] + [
                ('counter_' + str(i), ctypes.c_int32) for i in range(12)]

    library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    call = library.proc_pidinfo
    call.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                     ctypes.c_void_p, ctypes.c_int]
    call.restype = ctypes.c_int
    if ctypes.sizeof(TaskInfo) != 96:
        raise OSError('unexpected proc_taskinfo layout')

    def read():
        result = TaskInfo()
        count = call(os.getpid(), 4, 0, ctypes.byref(result), ctypes.sizeof(result))
        if count != ctypes.sizeof(result):
            raise OSError('proc_pidinfo did not return a complete self task record')
        return int(result.resident_size)
    return read


def current_rss():
    """One boundary sample of self RSS; no background or unrelated-process access."""
    if sys.platform == 'darwin':
        return _darwin_reader()()
    if sys.platform.startswith('linux'):
        with open('/proc/self/statm', 'rb') as stream:
            body = stream.read(256)
        values = body.split()
        if len(body) == 256 or len(values) != 7:
            raise OSError('invalid self statm record')
        return int(values[1]) * os.sysconf('SC_PAGE_SIZE')
    raise OSError('current RSS sampling unsupported')


def pinned_sources(root=HERE):
    result = {}
    for name, expected in PINS.items():
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(Path(root) / name, flags), 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_SOURCE_BYTES:
                raise ValueError('bounded ordinary observer dependency required')
            body = stream.read(MAX_SOURCE_BYTES + 1)
            after = os.fstat(stream.fileno())
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if len(body) != before.st_size or any(getattr(before, k) != getattr(after, k) for k in fields):
            raise ValueError('observer dependency changed while reading')
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('observer dependency identity differs: ' + name)
        result[name] = body
    return result


def load_module(name, path, body):
    module = ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


class Observer:
    """Bounded sidecar writer. Measurement failure never substitutes a model result."""
    def __init__(self, path, *, command, profile=None, max_events=20000, max_bytes=8*1024*1024,
                 clock=time.monotonic, high_water=high_water_rss, current=current_rss):
        if command not in ('fit', 'compatibility', 'compat'):
            raise ValueError('only maintained fit or compatibility observation is supported')
        if profile not in (None, 'cuda-fp16', 'cpu-fp32-math'):
            raise ValueError('known independently selected profile required')
        if type(max_events) is not int or not 2 <= max_events <= 1000000:
            raise ValueError('bounded positive event limit required')
        if type(max_bytes) is not int or not 8192 <= max_bytes <= 64*1024*1024:
            raise ValueError('trace byte limit must be 8 KiB to 64 MiB')
        self.clock, self.high_water, self.current = clock, high_water, current
        self.max_events, self.max_bytes = max_events, max_bytes
        self.written = 0; self.events = 0; self.next_id = 0; self.stack = []
        self.failures = set(); self.previous_clock = None; self.origin = None
        self.closed = False
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        self.stream = os.fdopen(os.open(path, flags, 0o600), 'wb')
        if not stat.S_ISREG(os.fstat(self.stream.fileno()).st_mode):
            self.stream.close()
            raise ValueError('ordinary fresh trace file required')
        self._write({'record': 'header', 'schema': 'reve-phase-cost-trace/v1',
                     'command': command, 'declared_profile': profile, 'source_sha256': dict(PINS),
                     'pid': os.getpid(), 'clock': 'monotonic_elapsed_seconds',
                     'rss_scope': 'self process only; includes observer overhead',
                     'high_water_scope': 'cumulative lifetime maximum; not independent phase peak',
                     'current_scope': 'boundary samples only; transient peaks may be missed',
                     'background_samplers': 0, 'resource_enforcement': False,
                     'scientific_qualification': False}, terminal=True)

    def fail(self, code):
        if code not in FAILURES:
            raise ValueError('closed observation failure code required')
        self.failures.add(code)

    def _write(self, row, *, terminal=False):
        raw = (json.dumps(row, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n').encode()
        ceiling = self.max_bytes if terminal else self.max_bytes - 4096
        if self.written + len(raw) > ceiling:
            self.fail('byte_limit'); return
        try:
            self.stream.write(raw); self.stream.flush(); self.written += len(raw)
        except (OSError, ValueError):
            self.fail('trace_write')

    def _measure(self):
        result = {}
        try:
            now = self.clock()
            if type(now) not in (float, int) or not math.isfinite(now) or (
                    self.previous_clock is not None and now < self.previous_clock):
                raise ValueError('invalid monotonic observation')
            if self.origin is None: self.origin = now
            self.previous_clock = now
            result['elapsed_seconds'] = now - self.origin
        except Exception:
            self.fail('clock'); result['elapsed_seconds'] = None
        for key, function, failure in (
                ('cumulative_high_water_rss_bytes', self.high_water, 'rss_high_water'),
                ('boundary_current_rss_bytes', self.current, 'rss_current')):
            try:
                value = function()
                if type(value) is not int or value <= 0:
                    raise ValueError('invalid RSS observation')
                result[key] = value
            except Exception:
                self.fail(failure); result[key] = None
        return result

    @contextmanager
    def phase(self, name):
        if name not in PHASES:
            raise ValueError('closed phase name required')
        identity = self.next_id; self.next_id += 1
        self.stack.append(identity)
        admitted = self.events + 2 <= self.max_events
        if admitted:
            self.events += 2
            begin = self._measure()
            self._write({'record': 'begin', 'phase': name, 'id': identity,
                         'depth': len(self.stack)-1, **begin})
        else:
            self.fail('event_limit')
            begin = None
        status = 'completed'
        try:
            yield
        except BaseException:
            status = 'failed'
            raise
        finally:
            if admitted:
                end = self._measure()
                start_time = begin['elapsed_seconds']; end_time = end['elapsed_seconds']
                duration = None if start_time is None or end_time is None else end_time-start_time
                self._write({'record': 'end', 'phase': name, 'id': identity,
                             'depth': len(self.stack)-1, 'status': status,
                             'duration_seconds': duration, **end})
            self.stack.pop()

    def close(self, operation_status):
        if self.closed:
            raise ValueError('observer already closed')
        if operation_status != 0: self.fail('operation_failed')
        if self.stack: self.fail('unfinished_phase')
        summary = {'record': 'summary', 'observation_complete': not self.failures,
                   'failures': sorted(self.failures), 'event_slots': self.events,
                   'phases_entered': self.next_id, 'operation_exit_code': operation_status,
                   'scientific_qualification': False}
        self._write(summary, terminal=True)
        try:
            self.stream.close()
        except OSError:
            self.fail('trace_write')
        self.closed = True
        return not self.failures


@contextmanager
def instrument(native, observer):
    """Restore every class member, even when the unchanged scientific call fails."""
    cls = native.NativeReference
    originals = {name: getattr(cls, name) for name in METHODS}
    def wrap(original, phase):
        @functools.wraps(original)
        def call(*args, **kwargs):
            with observer.phase(phase):
                return original(*args, **kwargs)
        return call
    try:
        for name, phase in METHODS.items():
            setattr(cls, name, wrap(originals[name], phase))
        yield
    finally:
        for name, original in originals.items():
            setattr(cls, name, original)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True, help='Fresh JSONL file; parent exists.')
    parser.add_argument('--max-events', type=int, default=20000)
    parser.add_argument('--max-bytes', type=int, default=8*1024*1024)
    parser.add_argument('operator_args', nargs=argparse.REMAINDER,
                        help='After --, unchanged run.py fit or compatibility arguments.')
    args = parser.parse_args(argv)
    remaining = args.operator_args[1:] if args.operator_args[:1] == ['--'] else args.operator_args
    if not remaining or remaining[0] not in ('fit', 'compatibility', 'compat'):
        parser.error('supply -- followed by fit or compatibility and its normal arguments')
    observer = None; status = 2
    try:
        bodies = pinned_sources()
        operator = load_module('_reve_observed_operator', HERE/'run.py', bodies['run.py'])
        # Validate argument syntax before opening a trace. Existing run.main still
        # owns its scientific validation and fresh output behavior.
        selected = operator._parser().parse_args(remaining)
        # Preserve run._native_module's import policy even when called without -B.
        sys.dont_write_bytecode = True
        native = load_module('_reve_observed_native', HERE/'native.py', bodies['native.py'])
        pinned_sources()
        observer = Observer(args.trace, command=remaining[0],
                            profile=selected.profile or 'cuda-fp16',
                            max_events=args.max_events, max_bytes=args.max_bytes)
        operator._native_module = lambda: native
        with observer.phase('operation'), instrument(native, observer):
            status = operator.main(remaining)
        try:
            pinned_sources()
        except (OSError, ValueError):
            observer.fail('source_changed')
    except (OSError, ValueError, TypeError, ImportError, KeyError, RuntimeError) as error:
        # No exception text reaches the trace. The maintained CLI still has its
        # ordinary human-readable stderr; observation must not log arguments.
        print('REVE observer refused: ' + type(error).__name__, file=sys.stderr)
    finally:
        if observer is not None and not observer.close(status):
            status = 2
    return status


if __name__ == '__main__':
    raise SystemExit(main())
