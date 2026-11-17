"""Bind all npyx imports to captured exact original bytes in a fresh process.

This is source identity enforcement, not a sandbox or native execution issuer.
No original module is imported by activation itself. No ambient fallback is used.
"""
from __future__ import annotations
import importlib.abc
import importlib.util
from pathlib import Path
import sys
from .dependencies import verify_dependencies
from .io_core import SourceError

_ACTIVE = None

def _is_original(name):
    return name == "npyx" or name.startswith("npyx.")

class _OriginalLoader(importlib.abc.Loader):
    def __init__(self, owner, fullname, relative, package):
        self.owner, self.fullname, self.relative, self.package = owner, fullname, relative, package
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        if self.owner.failed is not None:
            raise SourceError("original import previously failed; fresh process required")
        if module.__spec__.loader is not self or module.__name__ != self.fullname:
            raise SourceError("original loader identity mismatch")
        self.owner.modules[self.fullname] = module
        module.__file__ = str(self.owner.verified.root / self.relative)
        module.__cached__ = None
        if self.package:
            module.__path__ = [str((self.owner.verified.root / self.relative).parent)]
        try:
            code = compile(self.owner.verified.files[self.relative], module.__file__, "exec", dont_inherit=True, optimize=0)
            exec(code, module.__dict__)
        except BaseException as exc:
            self.owner.failed_modules[self.fullname] = exc
            # Preserve the original package's optional ImportError catches.
            # A failed optional submodule must not disable unrelated core
            # routes that the unchanged original initializer permits.
            if not isinstance(exc, ImportError) or self.fullname == "npyx":
                self.owner.failed = exc
            exc.c4_original_import_owner = self.owner
            exc.add_note("Fixed original module import failed; exact failure retained; no automatic module retry")
            raise
    def get_source(self, fullname):
        if fullname != self.fullname:
            raise ImportError("fixed original loader name")
        return self.owner.verified.files[self.relative].decode("utf-8")
    def get_filename(self, fullname):
        if fullname != self.fullname:
            raise ImportError("fixed original loader name")
        return str(self.owner.verified.root / self.relative)
    def is_package(self, fullname):
        if fullname != self.fullname:
            raise ImportError("fixed original loader name")
        return self.package

class _BoundFinder(importlib.abc.MetaPathFinder):
    def __init__(self, verified):
        self.verified = verified
        self.modules = {}
        self.failed = None
        self.failed_modules = {}
        self.import_names = {}
        for name in verified.files:
            if not name.startswith("npyx/") or not name.endswith(".py"):
                continue
            package = name.endswith("/__init__.py")
            dotted = (name[:-12] if package else name[:-3]).replace("/", ".")
            if dotted in self.import_names:
                raise SourceError("ambiguous original import mapping")
            self.import_names[dotted] = (name, package)
        if "npyx" not in self.import_names or "npyx.c4" not in self.import_names:
            raise SourceError("complete original package roots required")
    def find_spec(self, fullname, path=None, target=None):
        if not _is_original(fullname):
            return None
        if self.failed is not None:
            raise SourceError("original binding failed; fresh process required")
        if fullname in self.failed_modules:
            raise self.failed_modules[fullname]
        if fullname not in self.import_names:
            raise ModuleNotFoundError("unselected original module; ambient fallback prohibited", name=fullname)
        relative, package = self.import_names[fullname]
        loader = _OriginalLoader(self, fullname, relative, package)
        spec = importlib.util.spec_from_loader(fullname, loader, origin=str(self.verified.root / relative), is_package=package)
        spec.has_location = True
        spec.cached = None
        if package:
            spec.submodule_search_locations = [str((self.verified.root / relative).parent)]
        return spec
    def inspect_loaded(self):
        if self.failed is not None:
            raise SourceError("original binding failed; fresh process required") from self.failed
        if not sys.meta_path or sys.meta_path[0] is not self:
            raise SourceError("fixed original importer was displaced")
        for name, module in list(sys.modules.items()):
            if not _is_original(name):
                continue
            if module is None or self.modules.get(name) is not module:
                raise SourceError("conflicting preloaded original module")
            if name in self.failed_modules:
                raise SourceError("partially failed original module reinserted")
            spec = getattr(module, "__spec__", None)
            loader = getattr(spec, "loader", None)
            if not isinstance(loader, _OriginalLoader) or loader.owner is not self or loader.fullname != name:
                raise SourceError("foreign original module loader")
            if name not in self.import_names or loader.relative != self.import_names[name][0]:
                raise SourceError("unselected original module identity")
            if getattr(module, "__file__", None) != str(self.verified.root / loader.relative):
                raise SourceError("original module origin changed")
            if loader.package and list(getattr(module, "__path__", ())) != [str((self.verified.root / loader.relative).parent)]:
                raise SourceError("original package search path changed")

def activate_originals(dependency_root):
    global _ACTIVE
    if _ACTIVE is not None:
        if Path(dependency_root).absolute() != _ACTIVE.verified.root:
            raise SourceError("cannot rebind original source in a used process")
        _ACTIVE.inspect_loaded()
        # Recheck disk identity too; execution continues from the original captured bytes.
        current = verify_dependencies(dependency_root)
        if current.manifest_sha256 != _ACTIVE.verified.manifest_sha256 or dict(current.files) != dict(_ACTIVE.verified.files):
            raise SourceError("dependency root changed after binding")
        return _ACTIVE.verified
    if any(_is_original(name) for name in sys.modules):
        raise SourceError("preloaded npyx conflict; use a fresh process")
    verified = verify_dependencies(dependency_root)
    finder = _BoundFinder(verified)
    # Check again after filesystem reads; never delete or silently adopt a module.
    if any(_is_original(name) for name in sys.modules):
        raise SourceError("npyx loaded while source admission was in progress")
    sys.meta_path.insert(0, finder)
    _ACTIVE = finder
    finder.inspect_loaded()
    return verified

def require_bound_source():
    if _ACTIVE is None:
        raise SourceError("activate_originals(exact_prepared_root) before scientific original imports")
    _ACTIVE.inspect_loaded()
    return _ACTIVE.verified

def activate_captured_originals(dependency_root, manifest, bodies):
    """Admit every actual captured original byte before spawned-worker unpickle.

    No caller boolean, prior receipt or standalone digest substitutes for this
    whole fixed-descriptor/body verification. The source root is provenance;
    executable bytes come only from this newly verified captured mapping.
    """
    global _ACTIVE
    from types import MappingProxyType
    from . import dependencies
    if _ACTIVE is not None or any(_is_original(name) for name in sys.modules):
        raise SourceError('captured worker binding requires a fresh original namespace')
    spec = dependencies._specification_bytes(manifest)
    if type(bodies) is not dict or set(bodies) != {r['path'] for r in spec['files']}:
        raise SourceError('complete captured worker original roster required')
    captured = {row['path']: dependencies._verified_body(row, bodies[row['path']]) for row in spec['files']}
    verified = dependencies.VerifiedDependencies(Path(dependency_root).absolute(), dependencies.REVISION,
        dependencies.MANIFEST_SHA256, MappingProxyType(captured))
    finder = _BoundFinder(verified)
    if any(_is_original(name) for name in sys.modules):
        raise SourceError('original namespace loaded during worker source admission')
    sys.meta_path.insert(0, finder)
    _ACTIVE = finder
    finder.inspect_loaded()
    return verified
