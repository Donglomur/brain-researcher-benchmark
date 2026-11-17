"""Compile only captured selected source; no local pyc or search-path imports."""
import importlib.abc
import importlib.util
import hashlib
import sys
import types
from pathlib import Path
from supervisor import capture, lexical_disjoint, strict
from wire import need


class CapturedPackage(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, bodies):
        self.bodies = bodies
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in self.bodies:
            return None
        return importlib.util.spec_from_loader(fullname, self, is_package=fullname == 'n061')
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        module.__file__ = '<captured-selected-source>/' + module.__name__.replace('.', '/') + '.py'
        if module.__name__ == 'n061':
            module.__path__ = []
        exec(compile(self.bodies[module.__name__], module.__file__, 'exec'), module.__dict__)


def capture_accepted(installed, inherited, private_owners):
    installed = Path(installed)
    names = inherited['runtime']
    lexical_disjoint([installed, *(installed / name for name in names)], private_owners)
    manifest = inherited['installed_manifest']
    capture(installed / 'SOURCE_MANIFEST.json', manifest['bytes'], manifest['sha256'])
    bodies = {}
    for name, pin in names.items():
        need(name.startswith('runtime/n061/') and name.endswith('.py') and
             len(Path(name).parts) == 3, 'exact flat accepted runtime path')
        key = 'n061' if Path(name).name == '__init__.py' else 'n061.' + Path(name).stem
        bodies[key] = capture(installed / name, pin['bytes'], pin['sha256'])
    need(not any(name == 'n061' or name.startswith('n061.') for name in sys.modules),
         'fresh accepted namespace; no borrowed prior module')
    finder = CapturedPackage(bodies); sys.meta_path.insert(0, finder)
    return finder, bodies


def make_host(installed, inherited, private_owners, method_pin, scratch,
              native_request, docker_executable, docker_socket, owner,
              package_root, package_manifest_pin):
    """Effectful source intake, then inert concrete host; native starts on fit.

    This is an operator API, not candidate-supplied authority. Native selection,
    whole-programme allocation, original prepared inputs and provider provenance
    require separate qualification and are not inferred from these arguments.
    """
    from adapter import A0Host
    from enclosure import validate_request
    from supervisor import NativeCommand
    need(type(private_owners) is tuple and private_owners, 'explicit private owner roots')
    need(set(method_pin) == {'path', 'bytes', 'sha256'}, 'explicit frozen method source')
    # Every early path is checked lexically together before metadata or bodies.
    lexical_disjoint([installed, method_pin['path'], scratch, docker_executable, package_root], private_owners)
    validate_request(native_request); owner.tick()
    need(set(package_manifest_pin) == {'bytes', 'sha256'}, 'external selected package manifest pin')
    package_root = Path(package_root)
    selected = strict(capture(package_root / 'SOURCE_MANIFEST.json',
                             package_manifest_pin['bytes'], package_manifest_pin['sha256']))
    need(selected['schema'] == 'N061_NATIVE_STATE_SOURCE_V1', 'exact supervisor source package')
    for role in ('wire', 'enclosure', 'supervisor', 'adapter', 'loader'):
        module = sys.modules.get(role)
        actual = getattr(module, '__compiled_source_bytes__', None)
        pin = selected['files'][role + '.py']
        need(type(module) is types.ModuleType and type(actual) is bytes and
             len(actual) == pin['bytes'] and hashlib.sha256(actual).hexdigest() == pin['sha256'],
             'factory selection must bind each exact already-compiled source body')
        need(capture(package_root / (role + '.py'), pin['bytes'], pin['sha256']) == actual,
             'same captured package and original compiled role')
    child_sources = {}
    for name in ('child.py', 'wire.py'):
        pin = selected['files'][name]
        child_sources[name] = capture(package_root / name, pin['bytes'], pin['sha256'])
    inherited_pin = selected['files']['INHERITED.json']
    pinned_inherited = strict(capture(package_root / 'INHERITED.json', inherited_pin['bytes'], inherited_pin['sha256']))
    need(inherited == pinned_inherited, 'accepted runtime pins bound to same selected package')
    method = capture(method_pin['path'], method_pin['bytes'], method_pin['sha256'])
    finder, accepted = capture_accepted(installed, inherited, private_owners)
    root = Path(scratch)
    need(root.is_dir() and all(not p.is_symlink() for p in (root, *root.parents)),
         'earlier allocated ordinary scratch root')
    bodies = {**child_sources, 'worker.py': accepted['n061.worker'], 'contracts.py': accepted['n061.contracts']}
    need(set(child_sources) == {'child.py', 'wire.py'}, 'captured selected child bootstrap')
    command = NativeCommand(docker_executable, docker_socket, native_request, owner)
    return A0Host(command, root, bodies, method, owner), finder
