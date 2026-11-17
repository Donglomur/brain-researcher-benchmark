"""Source-pinned central bridge; default is the original metadata-only plan."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time
import types

# Fits the original three 16 MiB metadata operands (campaign, registry,
# admission), the original 1 MiB selection, and this fixed source closure.
# This additional wrapper ceiling is not an increase to any campaign cap.
# A future qualified host must reserve/observe the prefix before launch.
MAX_PREFIX_READ = 64 << 20
LAST_FAILURE_PREFIX = None


def require(ok, message):
    if not ok:
        raise ValueError(message)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'nonfinite JSON'))


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def relative(value):
    require(type(value) is str and bool(value), 'relative path string')
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and
            all(x not in ('', '.', '..') and x.casefold() != '.git' for x in p.parts),
            'canonical relative path')
    return p


class Prefix:
    """New logical source/metadata reservations, never original campaign costs."""
    def __init__(self):
        self.started_ns = time.monotonic_ns()
        self.reserved = 0
        self.completed = []
        self.pending = []
        self.raw_failure = None
        self.failure_stages = []
        self.secondary_failures = []
        self.attachment_attempts = []
        self.terminal_snapshot_attempted = False
        self.terminal_snapshot = None
        self.dispatch_context = None
        # This fallback makes no clock/cost/completion claim. The same Prefix
        # retains the actual reservation, pending reads and original errors.
        self.diagnostic_fallback = {'diagnostic_status': 'unavailable',
                                    'original_error_retained': True,
                                    'physical_io_measured': False}

    def retain_failure(self, error, stage):
        """Own the raw first exception before any diagnostic callback."""
        global LAST_FAILURE_PREFIX
        LAST_FAILURE_PREFIX = self
        if self.raw_failure is None:
            self.raw_failure = error
        elif self.raw_failure is not error:
            self.retain_secondary(error, stage)
        self.failure_stages.append(stage)

    def retain_secondary(self, error, stage):
        self.secondary_failures.append({'stage': stage, 'error': error})

    def attach_failure(self, error, attribute, value, stage):
        # A user-defined exception may reject attribute writes. Do not retry
        # that attachment or depend on it to retain the original Prefix.
        if attribute in self.attachment_attempts:
            return
        self.attachment_attempts.append(attribute)
        try:
            setattr(error, attribute, value)
        except BaseException as secondary:
            self.retain_secondary(secondary, stage)

    def enrich_failure(self, error, stage, attribute, context=None):
        """Best-effort diagnostics; no exception formatting or presentation."""
        self.attach_failure(error, 'n054_failure_custody', self,
                            stage + '.custody_attachment')
        if not self.terminal_snapshot_attempted:
            self.terminal_snapshot_attempted = True
            try:
                self.terminal_snapshot = self.snapshot()
            except BaseException as secondary:
                self.retain_secondary(secondary, stage + '.snapshot')
        snapshot = (self.terminal_snapshot if self.terminal_snapshot is not None
                    else self.diagnostic_fallback)
        value = snapshot if context is None else {'prefix': snapshot, **context}
        self.attach_failure(error, attribute, value, stage + '.diagnostic_attachment')

    def read(self, path, cap, expected=None):
        require(type(cap) is int and 0 <= cap <= MAX_PREFIX_READ, 'bounded member')
        require(self.reserved + cap + 1 <= MAX_PREFIX_READ, 'prefix reservation cap')
        self.reserved += cap + 1
        item = {'path': str(path), 'reserved_bytes': cap + 1}
        self.pending.append(item)
        path = Path(path).absolute()
        for ancestor in (path, *path.parents):
            require(not ancestor.is_symlink(), 'source/metadata path alias')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        primary = None
        try:
            st = os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= cap,
                    'ordinary bounded single-link member')
            parts = []; total = 0
            while True:
                data = os.read(fd, min(65536, cap + 1 - total))
                if not data:
                    break
                parts.append(data); total += len(data)
                require(total <= cap, 'member overflow')
            raw = b''.join(parts)
            require(len(raw) == st.st_size, 'member extent changed')
            if expected is not None:
                require(identity(raw) == expected, 'member identity changed')
            item.update(identity(raw))
        except BaseException as error:
            primary = error
            self.retain_failure(error, 'prefix.read')
            raise
        finally:
            try:
                os.close(fd)
            except BaseException as close_error:
                item['close_status'] = 'unknown_after_once_only_attempt'
                if primary is None:
                    self.retain_failure(close_error, 'prefix.close')
                    raise
                self.retain_secondary(close_error, 'prefix.close')
                self.attach_failure(primary, 'n054_prefix_close_error', close_error,
                                    'prefix.close_attachment')
        self.completed.append(item); self.pending.remove(item)
        return raw

    def snapshot(self):
        return {'reserved_bytes': self.reserved, 'completed': list(self.completed),
                'pending_unknown': list(self.pending), 'started_ns': self.started_ns,
                'observed_ns': time.monotonic_ns(), 'physical_io_measured': False,
                'original_campaign_costs_replaced': False,
                'host_launch_and_exit_custody_qualified': False}


class CapturedRuntime(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Import authenticated n054 bytes without reading pyc files."""
    def __init__(self, root, captured):
        self.root = root; self.modules = {}
        for name, raw in captured.items():
            if not name.startswith('programme/n054/') or not name.endswith('.py'):
                continue
            module = name[len('programme/'):-3].replace('/', '.')
            package = module.endswith('.__init__')
            if package:
                module = module[:-9]
            self.modules[module] = (name, raw, package)

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.modules:
            return importlib.util.spec_from_loader(fullname, self, is_package=self.modules[fullname][2])
        if fullname == 'n054' or fullname.startswith('n054.'):
            raise ImportError('n054 module outside authenticated source closure: ' + fullname)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name, raw, package = self.modules[module.__name__]
        module.__file__ = str(self.root / name)
        if package:
            module.__path__ = [str((self.root / name).parent)]
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)


def authenticate(root, size, sha256, prefix):
    require(type(size) is int and 0 < size <= 131072, 'source lock cap')
    lock = decode(prefix.read(root / 'RUNTIME_SOURCE_LOCK.json', size, {'bytes': size, 'sha256': sha256}))
    require(set(lock) == {'schema', 'task', 'files'} and lock['schema'] == 'n054_runtime_source_lock_v1'
            and lock['task'] == 'NEURAL-054', 'closed source lock')
    require(type(lock['files']) is dict and 1 <= len(lock['files']) <= 512, 'finite source closure')
    captured = {}
    for name, pin in lock['files'].items():
        relative(name)
        require(type(pin) is dict and set(pin) == {'bytes', 'sha256'}, 'closed source pin')
        captured[name] = prefix.read(root / name, pin['bytes'], pin)
    require({'entry.py', 'bridge.py', 'programme/n054/cli.py', 'programme/n054/report.py',
             'programme/n054/views.py', 'programme/n054/controller.py'} <= set(captured), 'complete source roles')
    return captured


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-bytes', type=int, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--route', choices=('plan', 'run', 'prepare'), default='plan')
    parser.add_argument('--condition', default='selected_campaign')
    parser.add_argument('--program', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--other-reserve-bytes', type=int)
    args = parser.parse_args(argv); prefix = Prefix(); finder = None
    try:
        root = Path(__file__).absolute().parent
        captured = authenticate(root, args.source_bytes, args.source_sha256, prefix)
        require(not any(k == 'n054' or k.startswith('n054.') for k in sys.modules), 'fresh source import domain')
        finder = CapturedRuntime(root, captured); sys.meta_path.insert(0, finder)
        bridge = types.ModuleType('n054_packaging_bridge')
        bridge.__file__ = str(root / 'bridge.py')
        exec(compile(captured['bridge.py'], bridge.__file__, 'exec'), bridge.__dict__)
        return bridge.dispatch(args, prefix, {'bytes': args.source_bytes, 'sha256': args.source_sha256})
    except BaseException as error:
        prefix.retain_failure(error, 'entry.main')
        try:
            prefix.enrich_failure(error, 'entry.main', 'n054_packaging_prefix')
        except BaseException as secondary:
            prefix.retain_secondary(secondary, 'entry.main.enrichment')
        raise
    finally:
        try:
            if finder is not None and finder in sys.meta_path:
                sys.meta_path.remove(finder)
        except BaseException as secondary:
            if prefix.raw_failure is None:
                prefix.retain_failure(secondary, 'entry.main.finder_cleanup')
                raise
            prefix.retain_secondary(secondary, 'entry.main.finder_cleanup')


if __name__ == '__main__':
    main()
