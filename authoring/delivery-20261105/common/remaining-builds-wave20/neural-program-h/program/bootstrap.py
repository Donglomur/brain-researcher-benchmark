"""Capture and compile exact source bodies; never import mutable sibling paths."""
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import types

MODULES = {'core': 'core.py', 'projection': 'preparation/projection.py', 'authority': 'authority.py',
           'packet': 'packet.py', 'schedule': 'schedule.py', 'engine': 'engine.py', 'provider': 'provider.py',
           'investigator': 'investigator.py', 'controller': 'controller.py', 'outer': 'outer.py',
           'reference_engine': 'references/engine.py', 'grader': 'grader.py'}
EXTRA = {'worker.py', 'references/worker.py', 'preparation/prepare.py', 'preparation/native.py', 'entry.py', 'bootstrap.py'}


def capture(path, expected, cap):
    path = Path(path)
    if '..' in path.parts:
        raise ValueError('noncanonical source/authority path')
    for parent in path.absolute().parents:
        if not stat.S_ISDIR(os.lstat(parent).st_mode):
            raise ValueError('nonordinary source parent')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > cap:
            raise ValueError('bounded ordinary source required')
        chunks = []; left = before.st_size
        while left:
            block = os.read(fd, min(left, 65536))
            if not block:
                raise ValueError('short source capture')
            left -= len(block); chunks.append(block)
        raw = b''.join(chunks)
        after = os.fstat(fd)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if os.read(fd, 1) or signature(before) != signature(after) or signature(after) != signature(os.lstat(path)):
            raise ValueError('source changed while captured')
        if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != expected:
            raise ValueError('exact source/authority pin mismatch')
        return raw
    finally:
        os.close(fd)


def parse(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate source metadata key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite source metadata')))


class Sources:
    def __init__(self, root, manifest_pin):
        self.root = Path(root)
        raw = capture(self.root/'SOURCE_MANIFEST.json', manifest_pin, 1048576)
        self.manifest = parse(raw); self.pin = manifest_pin
        if self.manifest.get('schema') != 'neural060_runtime_source_v1' or set(self.manifest['files']) != set(MODULES.values()) | EXTRA:
            raise ValueError('complete exact runtime source closure')
        self.pins = self.manifest['files']
        self.bodies = {name: capture(self.root/name, expected, 2097152) for name, expected in self.pins.items()}
        self.loaded = {}
        self.read_bytes = len(raw)+sum(len(b) for b in self.bodies.values())

    def module(self, name):
        if name in self.loaded:
            return self.loaded[name]
        if name not in MODULES:
            raise ValueError('unselected owned module')
        path = MODULES[name]
        module = types.ModuleType('neural060_owned_'+name)
        module.__file__ = str(self.root/path)
        original_import = builtins.__import__
        def importer(import_name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and import_name in MODULES:
                return self.module(import_name)
            return original_import(import_name, globals, locals, fromlist, level)
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=importer)
        self.loaded[name] = module
        try:
            exec(compile(self.bodies[path], module.__file__, 'exec'), module.__dict__)
        except BaseException:
            del self.loaded[name]
            raise
        return module

    def recheck(self):
        for name, expected in self.pins.items():
            capture(self.root/name, expected, 2097152)


def roster(repo):
    expected = {'bytes': 17391, 'sha256': 'c62ba1c5161287d1915d7dd49165be79ca93632dee686be0ea29f0929c1791cf'}
    return capture(Path(repo)/'authoring/delivery-20261105/neural060/REQUIRED_SOURCES.json', expected, 17391)
