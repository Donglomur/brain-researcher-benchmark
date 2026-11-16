"""Execute the complete pinned author import closure from captured bytes.

Capturing is ordinary source I/O, not native qualification. Third-party runtime
modules and scientific input namespaces still belong to the original operator.
"""
import importlib.abc
import importlib.util
from pathlib import Path, PurePosixPath
import sys
import types
from .core import need, read, relative, pin, encode
from .programme import contract


def capture_author(root, cost, authority):
    authority.require('capture_author_import_closure', authority.source_sha256)
    rows = [r for r in contract('ORIGINAL_SOURCE_CATALOGUE.json')['source_files']
            if r['destination'].startswith('author/') and r['destination'].endswith('.py')]
    names = [r['destination'][7:] for r in rows]
    need(rows and len(names) == len(set(names)), 'complete unique author import roster')
    captured = {}
    for row, name in zip(rows, names):
        relative(name)
        captured[name] = read(Path(root) / name, row['bytes'], cost, row)
    return captured


class _Loader(importlib.abc.Loader):
    def __init__(self, closure, relative_path):
        self.closure, self.path = closure, relative_path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        self.closure.execute(module, self.path)


class CapturedAuthorClosure(importlib.abc.MetaPathFinder):
    def __init__(self, captured, root):
        need(type(captured) is dict and captured, 'captured author source roster')
        self.sources = dict(captured)
        for name, body in self.sources.items():
            relative(name)
            need(name.endswith('.py') and type(body) is bytes, 'author source bytes')
        self.root = Path(root)
        self.aliases = {PurePosixPath(p).stem for p in captured}
        self.directory = ''
        self.modules = {}
        self.installed = False
        self.roster_pin = pin(encode({p: pin(b) for p, b in sorted(captured.items())}))

    def install(self):
        need(not self.installed, 'one author closure installation')
        need(not self.aliases.intersection(sys.modules), 'no inherited author module cache')
        self.old_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        sys.meta_path.insert(0, self)
        self.installed = True

    def find_spec(self, fullname, path=None, target=None):
        if '.' in fullname or fullname not in self.aliases:
            return None
        candidates = [str(PurePosixPath(self.directory) / (fullname + '.py')),
                      fullname + '.py']
        selected = next((p for p in candidates if p in self.sources), None)
        need(selected is not None, 'author alias not in selected module directory/root')
        return importlib.util.spec_from_loader(fullname, _Loader(self, selected))

    def execute(self, module, name):
        need(self.installed and name in self.sources, 'admitted captured module')
        before = self.directory
        self.directory = str(PurePosixPath(name).parent)
        if self.directory == '.':
            self.directory = ''
        module.__file__ = str(self.root / name)
        module.__cached__ = None
        try:
            exec(compile(self.sources[name], module.__file__, 'exec'), vars(module))
        finally:
            self.directory = before

    def load(self, name):
        relative(name)
        need(self.installed and name in self.sources, 'selected author module captured')
        self.directory = str(PurePosixPath(name).parent)
        if self.directory == '.':
            self.directory = ''
        if name not in self.modules:
            key = '_critical_captured_' + name.replace('/', '_').replace('.', '_')
            need(key not in sys.modules, 'no inherited explicit author module')
            module = types.ModuleType(key)
            module.__spec__ = importlib.util.spec_from_loader(key, _Loader(self, name))
            sys.modules[key] = module
            try:
                self.execute(module, name)
            except BaseException:
                sys.modules.pop(key, None)
                raise
            self.modules[name] = module
        return self.modules[name]

    def close(self):
        if self.installed:
            self.installed = False
            if self in sys.meta_path:
                sys.meta_path.remove(self)
            sys.dont_write_bytecode = self.old_bytecode
