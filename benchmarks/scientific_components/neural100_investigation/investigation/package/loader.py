"""Capture a closed source set before compiling its modules; no data inputs."""
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import types


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def strict(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def capture(path, expected):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'Ordinary source path')
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and 0 < expected['bytes'] <= 1048576,
         'Bounded source descriptor')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == expected['bytes'],
             'Ordinary exact source extent')
        chunks, remaining = [], a.st_size + 1
        while remaining:
            part = os.read(fd, min(65536, remaining))
            if not part:
                break
            chunks.append(part)
            remaining -= len(part)
        z, named = os.fstat(fd), path.lstat()
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(a, k) == getattr(z, k) == getattr(named, k) for k in fields),
             'Stable captured source')
    finally:
        os.close(fd)
    raw = b''.join(chunks)
    need(pin(raw) == expected, 'Selected source identity')
    raw.decode('utf-8')
    return raw


UPSTREAM = {'artifact_io', 'report_contract', 'grade', 'analysis_core', 'guard'}
LOCAL = {'common', 'policy', 'controller', 'native', 'claims', 'grading'}


class Sources:
    def __init__(self, root, expected):
        self.root = Path(root).absolute()
        self.identity = dict(expected)
        raw = capture(self.root / 'SOURCE_MANIFEST.json', expected)
        manifest = strict(raw)
        need(set(manifest) == {'schema', 'files'} and
             manifest['schema'] == 'neural100_investigation_source_v1', 'Source schema')
        required = {name + '.py' for name in LOCAL}
        required |= {'upstream/' + name + '.py' for name in UPSTREAM}
        required |= {'api.py', 'loader.py', 'holder.py', 'candidate_entry.py',
                     'trusted_entry.py', 'DATA_SOURCE.json'}
        need(type(manifest['files']) is dict and set(manifest['files']) == required,
             'Closed source member set')
        need(sum(p['bytes'] for p in manifest['files'].values()) <= 2097152,
             'Complete source capture cap')
        self.raw = {name: capture(self.root / name, desc)
                    for name, desc in manifest['files'].items()}
        self.manifest, self.modules = manifest, {}
        self.data = strict(self.raw['DATA_SOURCE.json'])

    def module(self, name):
        need(name in LOCAL | UPSTREAM, 'Declared source module only')
        if name in self.modules:
            return self.modules[name]
        filename = ('upstream/' if name in UPSTREAM else '') + name + '.py'
        module = types.ModuleType('neural100_investigation_' + name)
        module.__file__ = str(self.root / filename)
        original_import = builtins.__import__

        def importer(target, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and target in LOCAL | UPSTREAM:
                return self.module(target)
            return original_import(target, globals, locals, fromlist, level)

        namespace = dict(vars(builtins))
        namespace['__import__'] = importer
        module.__dict__['__builtins__'] = namespace
        if name in {'native', 'policy', 'controller'}:
            module.__dict__['c'] = self.module('common')
        self.modules[name] = module
        try:
            exec(compile(self.raw[filename], module.__file__, 'exec'), module.__dict__)
        except BaseException:
            del self.modules[name]
            raise
        return module


def load(root, expected):
    return Sources(root, expected)
