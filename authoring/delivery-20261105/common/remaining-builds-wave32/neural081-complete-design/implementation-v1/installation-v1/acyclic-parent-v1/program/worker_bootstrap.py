"""Captured-source loader and bounded trusted reference-worker entry."""
import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time

REQUIRED = frozenset(('common', 'protocol', 'arrays', 'custody', 'model_io', 'outputs', 'numeric_worker', 'numeric'))


def need(value, reason):
    if not value:
        raise ValueError(reason)


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys), 'exact bootstrap fields')


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'nonfinite JSON'))


class WorkerBudget:
    def __init__(self, origin, deadline, read_cap, write_cap, initial_read_bytes):
        self.origin, self.end, self.clock = origin, deadline, time.monotonic
        self.limits = {'read_bytes': read_cap, 'write_bytes': write_cap}
        self.used = {'read_bytes': initial_read_bytes, 'write_bytes': 0}
        self.check_clock()
        need(initial_read_bytes <= read_cap, 'bootstrap input charges exceed worker cap')

    def check_clock(self):
        need(self.origin <= self.clock() < self.end, 'original worker deadline')

    def charge(self, name, amount):
        self.check_clock()
        need(name in self.used and type(amount) is int and amount >= 0 and self.used[name] + amount <= self.limits[name], 'worker managed IO ceiling')
        self.used[name] += amount

    def snapshot(self):
        return {'original_origin': self.origin, 'original_deadline': self.end,
                'managed_requested_io': dict(self.used), 'limits': dict(self.limits),
                'includes_eof_probe_demand': True, 'physical_or_library_io_measured': False}


def capture(desc, budget, maximum=16 * 2**20):
    exact(desc, ('path', 'bytes', 'sha256'))
    size, path = desc['bytes'], desc['path']
    need(type(size) is int and 0 < size <= maximum and type(path) is str, 'bounded bootstrap source')
    p = Path(path)
    need(p.is_absolute() and str(p) == path and not any(x.is_symlink() for x in (p, *p.parents)), 'ordinary captured source')
    budget.charge('read_bytes', size + 1)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == size, 'exact source extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(size + 1)
        last, named = os.fstat(fd), p.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == size and hashlib.sha256(raw).hexdigest() == desc['sha256'] and all(
            getattr(first, k) == getattr(last, k) == getattr(named, k) for k in fields), 'complete stable source capture')
    finally:
        os.close(fd)
    budget.check_clock()
    return raw


class CapturedModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, sources):
        self.sources = sources

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.sources:
            return importlib.util.spec_from_loader(fullname, self, origin=self.sources[fullname][0])
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        filename, body = self.sources[module.__name__]
        module.__file__ = filename
        exec(compile(body, filename, 'exec'), module.__dict__)


def authenticate_modules(module_rows, budget, required, excluded_paths=()):
    """The source-owned entry supplies required names; requests cannot select code."""
    need(type(required) is frozenset and all(type(x) is str for x in required), 'fixed source-owned module set')
    need(type(module_rows) is list and len(module_rows) == len(required), 'complete captured module roster')
    sources, seen_paths = {}, set(excluded_paths)
    for row in module_rows:
        exact(row, ('name', 'source'))
        name = row['name']
        need(type(name) is str and name in required and name not in sources and name not in sys.modules, 'no ambient custom module')
        need(row['source']['path'] not in seen_paths, 'unique captured source body')
        seen_paths.add(row['source']['path'])
        sources[name] = (row['source']['path'], capture(row['source'], budget))
    need(set(sources) == required, 'all own sources captured before import')
    return sources


def start(raw_request, request_descriptor, bootstrap_descriptor, *, origin, deadline, read_cap,
          write_cap, initial_read_bytes, entry_path, entry_bytes):
    budget = WorkerBudget(origin, deadline, read_cap, write_cap, initial_read_bytes)
    request = parse(raw_request)
    exact(request, ('schema', 'job', 'operation', 'generation', 'source', 'payload', 'limits', 'output_root',
                    'allowed', 'protected', 'source_manifest', 'clock', 'worker_io'))
    need(request['schema'] == 'neural081_reference_worker_request_v1', 'worker request identity')
    need(request['clock'] == {'origin': origin, 'deadline': deadline} and request['worker_io'] == budget.limits,
         'same external original clock and prospective IO limits')
    manifest = parse(capture(request['source_manifest'], budget))
    exact(manifest, ('schema', 'entry', 'bootstrap', 'modules', 'dependency_qualification', 'installed_versions'))
    need(manifest['schema'] == 'neural081_reference_source_manifest_v1' and manifest['bootstrap'] == bootstrap_descriptor,
         'complete source manifest/bootstrap join')
    need(manifest['entry']['path'] == entry_path and manifest['entry']['bytes'] == entry_bytes, 'literal isolated entry source')
    capture(manifest['entry'], budget)
    capture(manifest['bootstrap'], budget)
    sources = authenticate_modules(manifest['modules'], budget, REQUIRED, (entry_path, bootstrap_descriptor['path']))
    need(next(row['source'] for row in manifest['modules'] if row['name'] == 'numeric') == request['source'], 'operative numerical source identity')
    qualification = parse(capture(manifest['dependency_qualification'], budget))
    exact(qualification, ('schema', 'status', 'numeric_source', 'installed_versions', 'image_identity',
                          'independent_issuer', 'physical_io_enforcement', 'memory_enforcement'))
    need(qualification['schema'] == 'neural081_numerical_environment_qualification_v1' and
         qualification['status'] == 'qualified' and qualification['numeric_source'] == request['source'] and
         qualification['installed_versions'] == manifest['installed_versions'], 'separately selected exact numerical environment')
    for key in ('image_identity', 'independent_issuer', 'physical_io_enforcement', 'memory_enforcement'):
        exact(qualification[key], ('path', 'bytes', 'sha256'))
    # These issued identities are externally admitted by native authority; no receipt is manufactured here.
    need(manifest['installed_versions'] == {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.6.1'}, 'selected literal historical versions')
    sys.meta_path.insert(0, CapturedModules(sources))
    import common as c
    import custody
    import numeric_worker
    import numeric
    import outputs
    import numpy
    import scipy
    import sklearn
    need({'numpy': numpy.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__} == manifest['installed_versions'], 'installed version mismatch; identity still externally qualified')
    output = c.absolute(request['output_root'])
    need(output.is_dir() and not any(x.is_symlink() for x in (output, *output.parents)), 'allocated ordinary workspace')
    access = custody.Access('G2', request['allowed'], request['protected'], budget)
    pure_request = {key: request[key] for key in ('operation', 'generation', 'source', 'payload', 'limits', 'output_root')}
    pure_request['schema'] = 'neural081_numeric_request_v1'
    result = numeric_worker.execute(pure_request, numeric, request['source'], access, output)
    outputs.finish(output, result, budget, request_descriptor, request['source'], request['job'])
    budget.check_clock()
