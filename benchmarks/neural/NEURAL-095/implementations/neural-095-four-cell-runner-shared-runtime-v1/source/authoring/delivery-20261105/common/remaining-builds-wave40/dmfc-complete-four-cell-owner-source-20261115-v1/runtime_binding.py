"""Closed private import of the unchanged unit/engine and additive V4 owner.

Only captured operator source executes. No task profile, array, Docker command,
model or scientific worker runs while constructing this module graph.
"""
import builtins
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[4]
GENERIC = 'authoring/task-ownership-successors-20261102/nlb017-recovery-capacity-v4'
BASE = 'authoring/dmfc-timing/program-runner-v2'
OWN = 'authoring/delivery-20261105/common/remaining-builds-wave40/dmfc-complete-four-cell-owner-source-20261115-v1'
MAP = {
    'qualified_core': 'authoring/shared-program-runner-v2/qualified_core.py',
    'profile': 'authoring/shared-program-runner-v2/profile.py',
    'engine_profile': 'authoring/shared-large-npz-runner-v1/engine_profile.py',
    'contract_profile': 'authoring/shared-large-npz-runner-v1/contract_profile.py',
    'unit': 'authoring/shared-large-npz-runner-v1/unit.py',
    'engine': BASE + '/engine.py', 'runtime_contract': BASE + '/runtime_contract.py',
    'host_budget': BASE + '/host_budget.py', 'absence': BASE + '/absence.py',
    'recovery': BASE + '/recovery.py',
}
EXTRA = (
    GENERIC + '/nlb_unit.py', GENERIC + '/nlb_engines.py',
    'authoring/nlb-cosmoothing/program-runner-v1/common.py',
    'authoring/task-ownership-successors-20261102/shared/recovery-identity-v1/recovery_identity.py',
    'authoring/shared-program-runner-v2/QUALIFIED_IMPORTS.json',
    'authoring/shared-large-npz-runner-v1/holder_profile.py',
    OWN + '/process_owner.py', OWN + '/group_bootstrap.py', OWN + '/trusted_controller.py',
    'authoring/shared-program-ownership-v3/process_owner.py',
    'authoring/shared-program-ownership-v3/trusted_controller.py',
)
ENV_KEYS = frozenset(('PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'DOCKER_HOST', 'DOCKER_CONFIG'))


def need(value, reason):
    if not value:
        raise ValueError(reason)


def required_sources():
    return tuple(sorted(set(MAP.values()) | set(EXTRA)))


def capture(path, cap=1048576):
    p = Path(path).absolute()
    need('..' not in p.parts and all(not x.is_symlink() for x in (p, *p.parents)), 'unlinked source/input')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'bounded ordinary source/input')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            b = f.read(cap + 1)
        z = os.fstat(fd)
        need(len(b) == a.st_size and all(getattr(a, k) == getattr(z, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'stable complete bytes')
        return b
    finally:
        os.close(fd)


class PrivateModules(dict):
    """Bridge private module identities to dataclasses without canonical writes."""
    def __init__(self, prefix):
        super().__init__(); self.prefix = prefix

    def __setitem__(self, key, value):
        need(type(key) is str and isinstance(value, types.ModuleType), 'private module registration')
        if key in self:
            need(self[key] is value, 'one private alias identity')
            return
        actual = key if key.startswith(self.prefix) else self.prefix + 'dynamic_' + hashlib.sha256(key.encode()).hexdigest()[:16]
        need(actual not in sys.modules and actual not in self, 'fresh qualified module identity')
        value.__name__ = actual
        dict.__setitem__(self, key, value)
        dict.__setitem__(self, actual, value)
        sys.modules[actual] = value


class ClosedRuntime:
    def __init__(self, root, sources, pins, expected):
        self.root = Path(root).absolute(); self.modules = {}; self.expected = expected; self.aliases = {}
        need(self.root == ROOT, 'actual registered repository root')
        need(set(required_sources()) <= set(sources) and set(required_sources()) <= set(pins), 'complete direct runtime source closure')
        self.sources = {}
        need(type(sources) is dict and len(sources) <= 512, 'finite closed source inventory')
        for rel in sources:
            need(type(rel) is str and not Path(rel).is_absolute() and '..' not in Path(rel).parts,
                 'canonical repository source')
            b = sources[rel]; p = pins[rel]
            need(type(b) is bytes and len(b) == p['bytes'] and hashlib.sha256(b).hexdigest() == p['sha256'],
                 'exact captured runtime source: ' + rel)
            self.sources[rel] = b
        transport = expected['transport']
        env = transport['environment']
        need(type(env) is dict and set(env) <= ENV_KEYS and all(type(k) is str and type(v) is str and
             '\0' not in v for k, v in env.items()), 'only explicit sanitized subprocess environment')
        self.os = types.SimpleNamespace(**vars(os)); self.os.environ = dict(env)
        self.prefix = '_dmfc_runtime_%x_' % id(self)
        self.sys = types.SimpleNamespace(**vars(sys)); self.sys.path = list(sys.path)
        self.sys.modules = PrivateModules(self.prefix)
        self.importlib = types.SimpleNamespace(**vars(importlib)); self.importlib.import_module = self.dynamic_import
        self.binding = types.SimpleNamespace(ROOT=self.root, load=self.bound_load, local=self.local)
        self.qualified_core = self.module(MAP['qualified_core'])
        self.engines = self.module(GENERIC + '/nlb_engines.py')
        self.unit = self.module(GENERIC + '/nlb_unit.py')
        self.contract = self.module(MAP['contract_profile'])
        self.owner = self.module(OWN + '/process_owner.py')
        base_budget = self.qualified_core.HostBudget
        class GuardedHostBudget(base_budget):
            concurrency_margin_bytes = 4 * 1024**2
            maximum_increment_bytes = 1024**2
            def __init__(self, root, limit=1073741824, reserve=268435456):
                need(limit > reserve + self.concurrency_margin_bytes, 'whole bound includes write-race margin')
                self.declared_limit = limit
                super().__init__(root, limit - self.concurrency_margin_bytes, reserve)
            def check(self, additional, *, receipt=False):
                need(type(additional) is int and 0 <= additional <= self.maximum_increment_bytes,
                     'bounded per-writer increment; four-writer margin remains valid')
                return super().check(additional, receipt=receipt)
        self.HostBudget = GuardedHostBudget
        self.loader = self
        actual = {'docker': self.qualified_core.DOCKER, 'environment': dict(self.qualified_core.ENV)}
        need(actual == transport, 'configured transport equals exact root-selected transport')
        need(expected['image']['reference'] == self.contract.IMAGE, 'same fixed numerical image')
        self.transport = actual

    def bound_load(self, relative, key):
        return self.module(relative)

    def local(self, filename, key):
        return self.module(GENERIC + '/' + filename)

    def dynamic_import(self, name, package=None):
        need(package is None and name in MAP, 'closed qualified dynamic import')
        return self.module(MAP[name])

    def bind_aliases(self, aliases):
        need(type(aliases) is dict, 'explicit module aliases')
        for name, relative in aliases.items():
            need(type(name) is str and name.isidentifier() and name not in MAP and
                 name not in ('sys', 'os', 'importlib', 'builtins', 'process_owner', 'trusted_controller') and
                 relative in self.sources and relative.endswith('.py'), 'exact noncanonical source alias')
            need(name not in self.aliases or self.aliases[name] == relative, 'one alias origin')
            self.aliases[name] = relative

    def importing(self, name, globals=None, locals=None, fromlist=(), level=0):
        need(level == 0, 'no implicit relative runtime imports')
        if name == 'sys':
            return self.sys
        if name == 'os':
            return self.os
        if name == 'importlib':
            return self.importlib
        if name in ('process_owner', 'trusted_controller'):
            origin = (globals or {}).get('__file__', '')
            prefix = OWN if str(self.root / OWN) in origin else 'authoring/shared-program-ownership-v3'
            return self.module(prefix + '/' + name + '.py')
        if name in MAP:
            return self.module(MAP[name])
        if name in self.aliases:
            return self.module(self.aliases[name])
        return builtins.__import__(name, globals, locals, fromlist, level)

    def module(self, relative, injected=None):
        need(relative in self.sources and relative.endswith('.py'), 'only captured operator Python modules')
        if relative in self.modules:
            need(not injected or all(self.modules[relative].__dict__.get(k) is v for k, v in injected.items()),
                 'one module ABI and injection identity')
            return self.modules[relative]
        module = types.ModuleType(self.prefix + hashlib.sha256(relative.encode()).hexdigest()[:16])
        module.__file__ = str(self.root / relative)
        module.__dict__.update(binding=self.binding, __builtins__={**vars(builtins), '__import__': self.importing})
        if injected:
            need(all(type(k) is str and k.isidentifier() and not k.startswith('__') and k != 'binding'
                     for k in injected), 'explicit private module globals')
            module.__dict__.update(injected)
        self.modules[relative] = module
        self.sys.modules[module.__name__] = module
        try:
            exec(compile(self.sources[relative], module.__file__, 'exec'), module.__dict__)
        except BaseException:
            self.modules.pop(relative, None)
            self.sys.modules.pop(module.__name__, None)
            sys.modules.pop(module.__name__, None)
            raise
        return module

    def load(self, relative, injected=None):
        return self.module(relative, injected)

    def verify_identity(self, until, folder, budget):
        """Read-only probes, only after actual operation admission; never on load."""
        need(time.monotonic() < until, 'original probe deadline')
        engine = self.qualified_core.BaseEngine(until, folder, budget)
        expected = self.expected
        outputs = {}
        for key, argv in (('server', ['info', '--format', '{{json .}}']),
                          ('image', ['image', 'inspect', expected['image']['reference']])):
            value = engine.run(argv, timeout=3, cap=65536)
            engine.write('identity-' + key + '-reply.json', {'argv': argv, 'returncode': value.returncode,
                'stdout_base64': base64.b64encode(value.stdout).decode(),
                'stderr_base64': base64.b64encode(value.stderr).decode()})
            need(value.returncode == 0 and len(value.stderr) <= 4096, 'complete successful identity probe')
            body = json.loads(value.stdout)
            if key == 'image':
                need(type(body) is list and len(body) == 1, 'one exact image')
                body = body[0]
            required = ('ID', 'Name', 'ServerVersion', 'OSType', 'Architecture') if key == 'server' else ('Id', 'Os', 'Architecture')
            observed = {k: body.get(k) for k in required}
            wanted = {k: expected[key][k] for k in required}
            need(all(type(x) is str and x for x in wanted.values()) and observed == wanted, 'actual ' + key + ' identity')
            need(observed.get('OSType', observed.get('Os')) == 'linux', 'Linux numerical runtime')
            engine.write('identity-' + key + '.json', {'argv': argv, 'observed': observed, 'expected': wanted})
            outputs[key] = observed
        return outputs


def load_runtime(root, captured_sources, source_pins, expected_docker_identity):
    return ClosedRuntime(root, captured_sources, source_pins, expected_docker_identity)
