"""Owned POSIX spawn bootstrap: captured originals bind before process unpickling.

This preserves four DataLoader workers and uses spawn rather than inheriting an
ambient package. It is ordinary source/process ownership, not native scientific
qualification. CPython 3.11 POSIX spawn protocol is the explicit current ABI.
"""
from __future__ import annotations
import base64
from contextlib import contextmanager
import hashlib
import io
import json
import multiprocessing as mp
from multiprocessing import context, process, reduction, resource_tracker, spawn, util
from multiprocessing.popen_spawn_posix import Popen as _PosixSpawnPopen
import os
from pathlib import Path
import selectors
import sys
import threading
import time

from .io_core import SourceError, capture_path, strict_json
from . import dependencies
from .import_guard import require_bound_source, activate_captured_originals

_SCOPE = None
_WORKER = False
_HELPERS = ('__init__.py', 'io_core.py', 'dependencies.py', 'import_guard.py', 'spawn_guard.py')
_BUNDLE_MAX = 8 * 1024 * 1024
_SOURCE_MAX = 4 * 1024 * 1024
_ACK_MAX = 32768
_STARTUP_SECONDS = 60.0
_TERM_SECONDS = 1.0
_KILL_SECONDS = 1.0

# This literal executes before any package path from preparation_data is used.
# It reads only a bounded JSON source capsule, never a pickle or ambient helper.
_BOOTSTRAP = r'''
import os,sys,json,base64,hashlib,importlib.abc,importlib.util
source_fd,process_fd,ack_fd,tracker_fd=map(int,sys.argv[1:5])
cap=8*1024*1024
raw=bytearray()
try:
 while True:
  b=os.read(source_fd,min(65536,cap+1-len(raw)))
  if not b:break
  raw.extend(b)
  if len(raw)>cap:raise ValueError("source capsule exceeds bound")
finally:os.close(source_fd)
def pairs(items):
 d={}
 for k,v in items:
  if k in d:raise ValueError("duplicate capsule key")
  d[k]=v
 return d
capsule=json.loads(bytes(raw),object_pairs_hook=pairs)
if set(capsule)!={"runtime_root","helpers","manifest","original_root","originals"}:raise ValueError("source capsule fields")
expected={"__init__.py","io_core.py","dependencies.py","import_guard.py","spawn_guard.py"}
if set(capsule["helpers"])!=expected:raise ValueError("complete bootstrap helpers required")
if any(n=="c4_distribution"or n.startswith("c4_distribution.")or n=="npyx"or n.startswith("npyx.")for n in sys.modules):raise ValueError("preloaded source namespace")
bodies={}
for name,value in capsule["helpers"].items():
 b=base64.b64decode(value,validate=True)
 if len(b)>1048576 or b"\0"in b:raise ValueError("ordinary helper source required")
 b.decode("utf-8");bodies[name]=b
if sum(map(len,bodies.values()))>4*1024*1024:raise ValueError("helper extent")
class Loader(importlib.abc.Loader):
 def __init__(self,name,relative):self.name,self.relative=name,relative
 def create_module(self,spec):return None
 def exec_module(self,module):
  module.__file__=capsule["runtime_root"]+"/c4_distribution/"+self.relative
  module.__cached__=None
  if self.name=="c4_distribution":module.__path__=[]
  exec(compile(bodies[self.relative],module.__file__,"exec",dont_inherit=True,optimize=0),module.__dict__)
class Finder(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name!="c4_distribution"and not name.startswith("c4_distribution."):return None
  relative="__init__.py"if name=="c4_distribution"else name.split(".",1)[1]+".py"
  if relative not in bodies:raise ModuleNotFoundError("unselected owned bootstrap module",name=name)
  return importlib.util.spec_from_loader(name,Loader(name,relative),is_package=name=="c4_distribution")
finder=Finder();sys.meta_path.insert(0,finder)
from c4_distribution.spawn_guard import _child_main
_child_main(capsule,process_fd,ack_fd,tracker_fd,finder)
'''

def _failure(primary, errors, owner, message):
    parts = ([primary] if primary is not None else []) + errors
    if not parts:
        return
    exc = parts[0] if len(parts) == 1 else BaseExceptionGroup(message, parts)
    exc.c4_spawn_owner = owner
    exc.add_note(message)
    raise exc

def _close(fd, errors):
    if fd is None:
        return
    try:
        os.close(fd)
    except BaseException as exc:
        exc.c4_close_owner = {'fd': fd, 'state': 'unknown; not retried'}
        errors.append(exc)

def _b64(raw):
    return base64.b64encode(raw).decode('ascii')

def _snapshot():
    verified = require_bound_source()
    root = Path(__file__).resolve().parents[1]
    manifest = capture_path(root / 'REQUIRED_ORIGINAL_SOURCE.json', dependencies.MANIFEST_BYTES)
    spec = dependencies._specification_bytes(manifest)
    if set(verified.files) != {r['path'] for r in spec['files']}:
        raise SourceError('complete captured original source roster required')
    originals = {}
    for row in spec['files']:
        originals[row['path']] = _b64(dependencies._verified_body(row, verified.files[row['path']]))
    helpers = {name: capture_path(root / 'c4_distribution' / name, 1048576) for name in _HELPERS}
    if sum(map(len, helpers.values())) > _SOURCE_MAX:
        raise SourceError('bootstrap helper extent')
    capsule = {'runtime_root': str(root), 'helpers': {n: _b64(b) for n, b in helpers.items()},
               'manifest': _b64(manifest), 'original_root': str(verified.root), 'originals': originals}
    raw = json.dumps(capsule, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > _BUNDLE_MAX:
        raise SourceError('source capsule extent')
    identity = {'manifest': dependencies.MANIFEST_SHA256,
                'originals': {r['path']: r['sha256'] for r in spec['files']},
                'helpers': {n: hashlib.sha256(b).hexdigest() for n, b in helpers.items()}}
    return raw, identity

def _send_ack(fd, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    if len(raw) > _ACK_MAX:
        raise SourceError('source bootstrap acknowledgement extent')
    view = memoryview(raw)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise SourceError('source bootstrap acknowledgement made no progress')
        view = view[n:]

def _child_main(capsule, process_fd, ack_fd, tracker_fd, owned_finder):
    global _WORKER
    _WORKER = True
    errors = []
    primary = None
    parent_sentinel = None
    code = 1
    try:
        manifest = base64.b64decode(capsule['manifest'], validate=True)
        originals = {n: base64.b64decode(v, validate=True) for n, v in capsule['originals'].items()}
        verified = activate_captured_originals(capsule['original_root'], manifest, originals)
        identity = {'manifest': verified.manifest_sha256,
                    'originals': {n: hashlib.sha256(b).hexdigest() for n, b in verified.files.items()},
                    'helpers': {n: hashlib.sha256(base64.b64decode(b, validate=True)).hexdigest()
                                for n, b in capsule['helpers'].items()}}
        resource_tracker._resource_tracker._fd = tracker_fd
        parent_sentinel = os.dup(process_fd)
        process.current_process()._inheriting = True
        try:
            with os.fdopen(process_fd, 'rb', closefd=True) as stream:
                process_fd = None
                preparation = reduction.pickle.load(stream)
                spawn.prepare(preparation)
                # Preparation may execute the operator main module. Re-admit
                # actual finder/module state before resolving the process and
                # its dataset/augmentation classes from the next pickle.
                require_bound_source()
                if owned_finder not in sys.meta_path:
                    raise SourceError('captured owned bootstrap finder displaced')
                _send_ack(ack_fd, {'stage': 'before_process_unpickle', 'identity': identity})
                worker = reduction.pickle.load(stream)
                require_bound_source()
                if owned_finder not in sys.meta_path:
                    raise SourceError('captured owned bootstrap finder displaced during unpickle')
                _send_ack(ack_fd, {'stage': 'after_process_unpickle', 'identity': identity})
        finally:
            del process.current_process()._inheriting
        _close(ack_fd, errors)
        ack_fd = None
        if errors:
            _failure(None, errors, {'child': os.getpid()}, 'source bootstrap acknowledgement close failed')
        code = worker._bootstrap(parent_sentinel)
        require_bound_source()
    except BaseException as exc:
        primary = exc
        if ack_fd is not None:
            try:
                _send_ack(ack_fd, {'stage': 'failed', 'error_type': type(exc).__name__})
            except BaseException as secondary:
                errors.append(secondary)
    finally:
        _close(process_fd, errors)
        _close(ack_fd, errors)
        _close(parent_sentinel, errors)
    if primary is not None or errors:
        # No scientific payload, traceback, URL or arbitrary exception text is
        # transported through the ordinary source admission channel.
        raise SystemExit(73)
    raise SystemExit(code)

def _pump_startup(writes, ack_fd, expected, deadline):
    """Bound actual source/pickle pipe transfer and both actual child barriers."""
    errors = []
    primary = None
    pending = dict(writes)
    ack = bytearray()
    raw_ack = bytearray()
    acknowledged = []
    parsed = []
    sent_bytes = 0
    expected_bytes = sum(len(v) for v in pending.values())
    selector = selectors.DefaultSelector()
    try:
        for fd, value in pending.items():
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_WRITE)
        os.set_blocking(ack_fd, False)
        selector.register(ack_fd, selectors.EVENT_READ)
        eof = False
        while pending or not eof:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SourceError('source-bound worker startup deadline')
            events = selector.select(min(remaining, 0.1))
            if time.monotonic() >= deadline:
                raise SourceError('source-bound worker startup deadline')
            for key, mask in events:
                fd = key.fd
                if fd in pending:
                    try:
                        count = os.write(fd, pending[fd][:65536])
                    except BlockingIOError:
                        continue
                    if count <= 0:
                        raise SourceError('worker source/pickle pipe made no progress')
                    sent_bytes += count
                    pending[fd] = pending[fd][count:]
                    if not pending[fd]:
                        selector.unregister(fd)
                        pending.pop(fd)
                        _close(fd, errors)
                        if errors:
                            raise SourceError('worker startup pipe close failed')
                else:
                    try:
                        part = os.read(fd, min(65536, _ACK_MAX + 1 - len(raw_ack)))
                    except BlockingIOError:
                        continue
                    if time.monotonic() >= deadline:
                        raise SourceError('source-bound worker late acknowledgement/EOF')
                    if not part:
                        selector.unregister(fd)
                        eof = True
                        continue
                    ack.extend(part)
                    raw_ack.extend(part)
                    if len(raw_ack) > _ACK_MAX:
                        raise SourceError('worker source acknowledgement extent')
                    while b'\n' in ack:
                        line, _, rest = ack.partition(b'\n')
                        ack[:] = rest
                        item = strict_json(bytes(line))
                        parsed.append(item)
                        stage = ('before_process_unpickle', 'after_process_unpickle')
                        if len(acknowledged) >= 2 or item != {'stage': stage[len(acknowledged)], 'identity': expected}:
                            raise SourceError('worker failed exact pre/post-unpickle source binding')
                        acknowledged.append(item['stage'])
        if ack or len(acknowledged) != 2 or time.monotonic() >= deadline:
            raise SourceError('worker source admission incomplete or late')
    except BaseException as exc:
        primary = exc
    finally:
        try:
            selector.close()
        except BaseException as exc:
            errors.append(exc)
        for fd in list(pending):
            _close(fd, errors)
        _close(ack_fd, errors)
    custody = {'unacknowledged': 2 - len(acknowledged), 'sent_bytes': sent_bytes,
               'expected_bytes': expected_bytes, 'acknowledgements': parsed,
               'raw_ack_prefix': bytes(raw_ack), 'unparsed_ack_suffix': bytes(ack)}
    if primary is not None:
        primary.c4_spawn_startup = custody
    for exc in errors:
        exc.c4_spawn_startup = custody
    _failure(primary, errors, custody, 'source-bound worker startup failed')
    return custody

class _BoundPopen(_PosixSpawnPopen):
    def __init__(self, obj, owner):
        self._c4_owner = owner
        super().__init__(obj)

    def _launch(self, obj):
        owner = self._c4_owner
        owner.check()
        capsule, identity = _snapshot()
        tracker_fd = resource_tracker.getfd()
        self._fds.append(tracker_fd)
        preparation = spawn.get_preparation_data(obj._name)
        buffer = io.BytesIO()
        context.set_spawning_popen(self)
        try:
            reduction.dump(preparation, buffer)
            reduction.dump(obj, buffer)
        finally:
            context.set_spawning_popen(None)
        # Source capsules are bounded ordinary bytes. Scientific dataset
        # serialization is the unchanged multiprocessing ABI and remains an
        # explicit unqualified capacity/parent-lifetime obligation.
        payload = buffer.getbuffer()
        parent_r = child_w = child_r = parent_w = source_r = source_w = ack_r = ack_w = None
        errors = []
        primary = None
        launched = False
        try:
            parent_r, child_w = os.pipe()
            child_r, parent_w = os.pipe()
            source_r, source_w = os.pipe()
            ack_r, ack_w = os.pipe()
            self._fds.extend([child_r, child_w, source_r, ack_w])
            command = [spawn.get_executable(), '-I', '-S', '-B', '-c', _BOOTSTRAP,
                       str(source_r), str(child_r), str(ack_w), str(tracker_fd), '--multiprocessing-fork']
            # As with stdlib spawn, OS process creation has no portable
            # interruptible wall bound. No original code is imported before
            # the owned source capsule and both admission barriers below.
            self.pid = util.spawnv_passfds(spawn.get_executable(), command, self._fds)
            self.sentinel = parent_r
            owner.created(self)
            launched = True
            for fd in (child_r, child_w, source_r, ack_w):
                _close(fd, errors)
            child_r = child_w = source_r = ack_w = None
            if errors:
                raise SourceError('spawn parent child-end close failed')
            # Ownership transfers before invocation, including on failure.
            writes = {source_w: memoryview(capsule), parent_w: payload}
            source_w = parent_w = None
            read_fd = ack_r
            ack_r = None
            self._c4_startup = _pump_startup(writes, read_fd, identity, time.monotonic() + _STARTUP_SECONDS)
            owner.admitted(self, identity)
        except BaseException as exc:
            primary = exc
        finally:
            for fd in (child_r, child_w, source_r, source_w, parent_w, ack_r, ack_w):
                _close(fd, errors)
            self.finalizer = util.Finalize(self, util.close_fds, (parent_r,) if parent_r is not None else ())
            if primary is not None or errors:
                if launched:
                    errors.extend(owner.retire_one(self))
                else:
                    owner.launch_unknown = True
                try:
                    self.finalizer()
                except BaseException as exc:
                    errors.append(exc)
        _failure(primary, errors, owner, 'source-bound spawn launch failed')

class _BoundProcess(context.SpawnProcess):
    @staticmethod
    def _Popen(obj):
        return _BoundPopen(obj, _require_scope())

class _BoundContext(context.SpawnContext):
    Process = _BoundProcess

class _WorkerScope:
    def __init__(self):
        self.thread = threading.get_ident()
        self.active = {}
        self.retired = []
        self.retired_count = 0
        self.launch_unknown = False
        self.closed = False
    def check(self):
        if self.closed or threading.get_ident() != self.thread or _WORKER:
            raise SourceError('source worker scope is parent-thread-only and active')
        require_bound_source()
        for popen in list(self.active.values()):
            if popen.poll() is not None:
                self.active.pop(popen.pid)
                self.record_retired(popen)
        if len(self.active) >= 4:
            raise SourceError('source worker scope already owns four live workers')
    def created(self, popen):
        if popen.pid in self.active:
            raise SourceError('duplicate source worker PID')
        self.active[popen.pid] = popen
    def record_retired(self, popen):
        self.retired_count += 1
        self.retired.append({'pid': popen.pid, 'returncode': popen.returncode, 'admitted': getattr(popen, '_c4_admitted', False)})
        # This is a bounded process-custody diagnostic, not the missing full
        # scientific/native execution log issuer.
        self.retired[:] = self.retired[-32:]
    def admitted(self, popen, identity):
        if self.active.get(popen.pid) is not popen:
            raise SourceError('source worker owner lost before admission')
        popen._c4_admitted = True
        popen._c4_source_identity = identity
    def retire_one(self, popen):
        errors = []
        observed = False
        try:
            observed = popen.poll() is not None
        except BaseException as exc:
            errors.append(exc)
        if not observed:
            try:
                popen.terminate()
            except BaseException as exc:
                errors.append(exc)
            try:
                observed = popen.wait(timeout=_TERM_SECONDS) is not None
            except BaseException as exc:
                errors.append(exc)
        if not observed:
            try:
                popen.kill()
            except BaseException as exc:
                errors.append(exc)
            try:
                observed = popen.wait(timeout=_KILL_SECONDS) is not None
            except BaseException as exc:
                errors.append(exc)
        if observed:
            self.active.pop(popen.pid, None)
            self.record_retired(popen)
        else:
            errors.append(SourceError('source worker retirement remains unknown; live owner retained'))
        return errors
    def finish(self, primary):
        errors = []
        for popen in list(self.active.values()):
            errors.extend(self.retire_one(popen))
        self.closed = True
        if self.launch_unknown:
            errors.append(SourceError('source worker launch/retirement unobservable; cleanup unknown'))
        _failure(primary, errors, self, 'source worker scope ended; custody retained')

def _require_scope():
    if _SCOPE is None:
        raise SourceError('source_worker_scope is required before worker creation')
    _SCOPE.check()
    return _SCOPE

def worker_context():
    _require_scope()
    return _BoundContext()

@contextmanager
def source_worker_scope():
    global _SCOPE
    if os.name != 'posix' or sys.implementation.name != 'cpython' or sys.version_info[:2] != (3, 11) or getattr(sys, 'frozen', False):
        raise SourceError('source-bound workers currently require CPython3.11 POSIX spawn ABI')
    if _SCOPE is not None or _WORKER:
        raise SourceError('nested/concurrent source worker scopes are unsupported')
    require_bound_source()
    owner = _WorkerScope()
    _SCOPE = owner
    primary = None
    try:
        yield owner
    except BaseException as exc:
        primary = exc
    finally:
        _SCOPE = None
        owner.finish(primary)
