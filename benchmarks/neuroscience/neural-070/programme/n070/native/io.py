"""Strict data-only admission and complete ordinary-file custody."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from contextlib import contextmanager


def _checkpoint(stage):
    from .resources import checkpoint
    checkpoint('io:'+stage)


def _controller_iter(iterable,stage):
    from .resources import controller_iter
    return controller_iter(iterable,'io:'+stage)


def _controller_operation(fn):
    from functools import wraps
    @wraps(fn)
    def guarded(*args,**kwargs):
        from .resources import controller_call,controller_fatal_call
        # Parsing can be a declared local product failure; original bytes,
        # immutable pins, filesystem cleanup and writes always retain custody.
        call=controller_call if fn.__name__ in ('parse','load')else controller_fatal_call
        return call('io:'+fn.__name__,fn,*args,**kwargs)
    return guarded


@contextmanager
def owned_resource(kind, acquire, release):
    """Own the body failure before one cleanup attempt on the original handle.

    A cleanup exception cannot establish whether the external resource actually
    closed.  Preserve that uncertainty and the raw original errors; never retry
    a descriptor whose number may already have been reused.
    """
    from .observation import Observation
    o = Observation('ordinary_io_resource', sample_clock=False)
    o.handles['resource'] = None
    o.record = {'resource_kind': kind, 'acquisition_attempted': False,
                'acquisition_returned': False, 'body_completed': False,
                'cleanup_attempted': False, 'cleanup_returned': False,
                'closure': 'not_attempted_no_returned_handle'}
    acquired = False
    handle = None
    stage = kind + ':acquire'
    try:
        o.record['acquisition_attempted'] = True
        handle = acquire()
        acquired = True
        o.handles['resource'] = handle
        o.record['acquisition_returned'] = True
        o.record['closure'] = 'open_original_handle'
        stage = kind + ':body'
        yield handle
        o.record['body_completed'] = True
    except BaseException as exc:
        # This precedes release, clocks, serialization and outward projection.
        o.fail(exc, stage)
    finally:
        if acquired:
            o.record['cleanup_attempted'] = True
            o.record['closure'] = 'unknown'
            try:
                release(handle)
            except BaseException as exc:
                o.fail(exc, kind + ':cleanup')
            else:
                o.record['cleanup_returned'] = True
                o.record['closure'] = 'closed'
    if o.first_error is not None:
        o.raise_failure()


class Refusal(ValueError):
    pass


def need(test, reason):
    if not test:
        raise Refusal(reason)


def exact(obj, fields):
    need(type(obj) is dict and set(obj) == set(fields), "Exact object fields required")


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


def integer(x, minimum=0):
    return type(x) is int and x >= minimum


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def identity(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def digest(obj):
    return identity(canonical(obj))["sha256"]


def _pairs(items):
    out = {}
    for key, value in _controller_iter(items,'io:iterator:65'):
        need(key not in out, "Duplicate JSON key")
        out[key] = value
    return out


@_controller_operation
def parse(body, depth=48, nodes=1000000):
    value = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                       parse_constant=lambda _: need(False, "Nonfinite JSON"))
    remaining = nodes

    def visit(x, d):
        nonlocal remaining
        remaining -= 1
        need(d <= depth and remaining >= 0, "Bounded JSON structure")
        if type(x) is dict:
            for k, v in _controller_iter(x.items(),'io:iterator:82'):
                need(type(k) is str, "String JSON key"); visit(v, d + 1)
        elif type(x) is list:
            for v in _controller_iter(x,'io:iterator:85'): visit(v, d + 1)
        elif type(x) is float:
            need(math.isfinite(x), "Finite JSON number")
        else:
            need(x is None or type(x) in (str, int, bool), "Data-only JSON")
    visit(value, 0)
    return value


def relative(name):
    need(type(name) is str and name and "\\" not in name and "\x00" not in name,
         "Ordinary relative path")
    p = PurePosixPath(name)
    need(not p.is_absolute() and str(p) == name and all(x not in (".", "..") for x in _controller_iter(p.parts,'io:iterator:98')),
         "Normalized relative path")
    return name


@_controller_operation
def read(path, cap, pin=None):
    need(integer(cap), "Read cap")
    p = Path(path)
    # Never follow an ancestor link, even when the final member is regular.
    for parent in _controller_iter((p, *p.parents),'io:iterator:108'):
        need(not parent.is_symlink(), "No symlink ancestor")
    with owned_resource('ordinary_read',
                        lambda: os.open(p, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)),
                        os.close) as fd:
        _checkpoint('after_open_before_fstat')
        s = os.fstat(fd)
        _checkpoint('after_initial_fstat')
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= cap,
             "Bounded regular single-link member")
        data = b""
        while True:
            _checkpoint('before_read_syscall')
            chunk = os.read(fd, min(65536, cap + 1 - len(data)))
            data += chunk
            _checkpoint('after_read_syscall')
            if not chunk: break
            need(len(data) <= cap, "Read exceeded cap")
        final = os.fstat(fd)
        need((s.st_ino, s.st_size, s.st_mtime_ns) ==
             (final.st_ino, final.st_size, final.st_mtime_ns), "Stable read")
    if pin:
        need(all(identity(data)[k] == pin[k] for k in _controller_iter(("bytes", "sha256"),'io:iterator:129')), "Exact pinned body")
    return data


@_controller_operation
def load(path, cap=16000000, pin=None):
    return parse(read(path, cap, pin))


@_controller_operation
def write_new(path, body, cap):
    need(len(body) <= cap, "Reserved output member allowance")
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    for parent in _controller_iter((p.parent, *p.parent.parents),'io:iterator:142'):
        need(not parent.is_symlink(), "No output ancestor link")
    with owned_resource('ordinary_write',
                        lambda: os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                        os.close) as fd:
        # Raw bounded writes avoid an implicit buffered-context finalizer that
        # could replace an earlier write/flush failure. Each returned prefix is
        # advanced exactly once; incomplete original files are never removed.
        view = memoryview(body)
        offset = 0
        _checkpoint('before_write')
        while offset < len(view):
            size = min(65536, len(view) - offset)
            written = os.write(fd, view[offset:offset + size])
            need(type(written) is int and 0 < written <= size,
                 "Positive bounded original write progress")
            offset += written
            _checkpoint('after_write_syscall')
            if offset < len(view):
                _checkpoint('before_write')
        _checkpoint('before_fsync')
        os.fsync(fd)
        _checkpoint('after_fsync')
    return identity(body)


@_controller_operation
def dump(path, obj, cap=16000000):
    return write_new(path, canonical(obj) + b"\n", cap)


@_controller_operation
def tree(root, *, total, member, files):
    root = Path(root).absolute(); need(root.is_dir() and not root.is_symlink(), "Ordinary tree root")
    rows = []; used = 0
    for p in _controller_iter(sorted(_controller_iter(root.rglob("*"),"tree_inventory")),'io:iterator:169'):
        s = p.lstat()
        if stat.S_ISDIR(s.st_mode): continue
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "No link or special tree member")
        name = relative(p.relative_to(root).as_posix())
        need(len(rows) < files and used + s.st_size <= total, "Complete tree pre-read bounds")
        b = read(p, member); used += len(b)
        rows.append({"path": name, **identity(b), "mode": stat.S_IMODE(s.st_mode)})
    return {"files": rows, "bytes": used, "identity": digest(rows)}


@_controller_operation
def authenticate_tree(root, selection, limits):
    actual = tree(root, **limits)
    need(actual == selection, "Exact complete selected source/output tree")
    return actual


@_controller_operation
def snapshot(root, target, selection, limits):
    authenticate_tree(root, selection, limits)
    target = Path(target); need(not target.exists(), "Fresh snapshot namespace")
    target.mkdir(parents=True)
    for row in _controller_iter(selection["files"],'io:iterator:192'):
        b = read(Path(root) / row["path"], limits["member"], row)
        p = target / row["path"]; write_new(p, b, limits["member"]); _checkpoint("before_chmod"); p.chmod(row["mode"]); _checkpoint("after_chmod")
    return authenticate_tree(target, selection, limits)
