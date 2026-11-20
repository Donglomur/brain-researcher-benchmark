"""Bounded source and generated-artifact handling for the one source campaign."""
import hashlib
import os
from pathlib import Path
import stat
import types

MAX_FIXTURE_WRITES = 524288
MAX_SOURCE_READS = 524288
FROZEN = {
    'frozen/comparison_streamed_batch.py': (5930, '0d3019d706c6014f5258d1fce899fef48a2fb305d137c48f127d451abc3b435f'),
    'frozen/model_operation.py': (22947, 'c74030ec288d451eb29c4b1febd5664896c508471df3dcefcaebe992c9934460'),
    'source_transition.py': (1489, 'e2a340203fe24d6076e3bc79d7430c933263a34a773e4d8dc6bc38418b60139d'),
}


def output_root(path, source_roots):
    value = Path(path)
    if not value.is_absolute() or value != value.resolve(strict=False):
        raise ValueError('absolute canonical output without symlink aliases required')
    for source in source_roots:
        source = Path(source).resolve(strict=True)
        if value == source or source in value.parents or value in source.parents:
            raise ValueError('source/output overlap or ancestor refused')
    for ancestor in (value, *value.parents):
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError('output symlink ancestry refused')
    if value.exists():
        raise ValueError('fresh output path required')
    if not value.parent.is_dir():
        raise ValueError('existing canonical output parent required')
    return value


class CampaignFiles:
    def __init__(self, source_root, helper_root, output):
        self.source_root = Path(source_root).resolve(strict=True)
        self.helper_root = Path(helper_root).resolve(strict=True)
        self.output = output_root(output, (self.source_root, self.helper_root))
        self.output.mkdir(mode=0o700)
        self.written = self.read = 0
        self.modules = {}

    def module(self, relative, *, helper=False):
        key = (helper, relative)
        if key in self.modules:
            return self.modules[key]
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts or rel.suffix != '.py':
            raise ValueError('named relative Python source required')
        root = self.helper_root if helper else self.source_root
        path = root / rel
        if path.resolve(strict=True) != path:
            raise ValueError('source symlink alias refused')
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 131072:
            raise ValueError('bounded regular source')
        if self.read + before.st_size > MAX_SOURCE_READS:
            raise ValueError('source read allowance exhausted')
        with path.open('rb') as handle:
            opened = os.fstat(handle.fileno())
            body = handle.read(before.st_size + 1)
            closed = os.fstat(handle.fileno())
        after = path.stat()
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if not identity(before) == identity(opened) == identity(closed) == identity(after) or len(body) != before.st_size:
            raise ValueError('unstable source')
        self.read += len(body)
        if not helper and relative in FROZEN:
            if (len(body), hashlib.sha256(body).hexdigest()) != FROZEN[relative]:
                raise ValueError('immutable scientific source pin')
        module = types.ModuleType('generated_control_' + str(len(self.modules)))
        module.__file__ = str(path)
        exec(compile(body, str(path), 'exec'), module.__dict__)
        self.modules[key] = module
        return module

    def write(self, name, body):
        relative = Path(name)
        if not isinstance(body, bytes) or relative.is_absolute() or '..' in relative.parts or len(relative.parts) > 2:
            raise ValueError('bounded named bytes artifact required')
        if self.written + len(body) > MAX_FIXTURE_WRITES:
            raise ValueError('cumulative generated fixture allowance exhausted')
        path = self.output / relative
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(body)
        self.written += len(body)
        return path
