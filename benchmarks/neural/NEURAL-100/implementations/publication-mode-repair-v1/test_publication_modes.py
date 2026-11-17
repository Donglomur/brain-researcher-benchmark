"""Generated POSIX publication controls; no data, native leaves, or model execution."""
import atexit
import builtins
import json
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / 'investigation/investigation/package'
TASK = '100'

CHARGED_WRITE_BYTES = 0


def charge_generated(size):
    global CHARGED_WRITE_BYTES
    CHARGED_WRITE_BYTES += size
    if CHARGED_WRITE_BYTES > 262144:
        raise AssertionError('256 KiB cumulative generated fixture ceiling')


def generated_write(path, body):
    charge_generated(len(body))
    path.write_bytes(body)


atexit.register(lambda: print(json.dumps({'task': TASK,
    'generated_write_bytes_charged': CHARGED_WRITE_BYTES,
    'generated_write_ceiling': 262144, 'native_executions': 0})))


def load(name, bindings=None):
    module = types.ModuleType('publication_modes_' + TASK + '_' + name)
    module.__file__ = str(RUNTIME / (name + '.py'))
    module.__dict__.update(bindings or {})
    if name == 'controller':
        imports = {key: types.SimpleNamespace() for key in ('policy', 'native', 'grading')}
        imports['grading'].roster_admit = lambda roster: None
        original = builtins.__import__
        def importer(key, *args, **kwargs):
            return imports[key] if key in imports else original(key, *args, **kwargs)
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=importer)
    exec(compile(Path(module.__file__).read_bytes(), module.__file__, 'exec'), module.__dict__)
    return module


class FixtureBudget:
    """Tiny fixture accounting; no native admission or physical-capacity claim."""
    def __init__(self, *args):
        self.end = 0
        self.writes = 0
    def tick(self): pass
    def read(self, count): pass
    def capacity(self, extra=0): pass
    def write(self, count):
        self.writes += count
        if self.writes > 1048576:
            raise AssertionError('One MiB cumulative generated output ceiling')
    def record(self): return {'generated_bytes': self.writes}


@contextmanager
def private_creation():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


class PublicationModes(unittest.TestCase):
    def setUp(self):
        self.common = load('common')
        original_save = self.common.save
        def counted_save(path, raw, *args, **kwargs):
            charge_generated(len(raw))
            return original_save(path, raw, *args, **kwargs)
        self.common.save = counted_save
        self.controller = load('controller', {'c': self.common})
        parent = os.environ.get('PUBLICATION_FIXTURE_ROOT')
        self.temporary = tempfile.TemporaryDirectory(prefix='generated-' + TASK + '-', dir=parent)
        self.base = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)

    def test_actual_prepare_publishes_complete_nested_view_and_can_retire(self):
        with private_creation():
            package = self.base / 'package'
            root = self.base / 'custody'
            root.mkdir(mode=0o700)
            private = root / 'private'
            private.mkdir(mode=0o700)
            self.common.save(private / 'secret', b'generated private metadata', 1024)
            originals = {'public/nested/deep/input.txt': b'generated input',
                         'public/ROSTER.json': b'{"generated":true}\n'}
            rows = []
            for name, raw in originals.items():
                path = package / name
                path.parent.mkdir(parents=True, exist_ok=True)
                generated_write(path, raw)
                rows.append({'target': name, **self.common.pin(raw)})
            budget = FixtureBudget()
            labels = ('FIT', 'INFER') if TASK == '021' else (None,)
            for label in labels:
                args = (label,) if label else ()
                result = self.controller.prepare(package, rows, root, budget, *args)
                current, expected = result[:2]
                self.assertEqual(set(expected), {'nested/deep/input.txt', 'ROSTER.json'})
                for path in (current, current / 'nested', current / 'nested/deep'):
                    self.assertEqual(mode(path), 0o755)
                    self.assertEqual(mode(path) & 0o005, 0o005)
                for name, raw in originals.items():
                    public_file = current / Path(name).relative_to('public')
                    self.assertEqual(public_file.read_bytes(), raw)
                    self.assertEqual(mode(public_file), 0o444)
                    self.assertEqual(mode(package / name), 0o600)
                self.assertEqual(mode(root), 0o700)
                self.assertEqual(mode(private), 0o700)
                self.assertEqual(mode(private / 'secret'), 0o400)
                prepared = root / ('VIEW_' + label + '_PREPARED.json' if label else 'VIEW_PREPARED.json')
                self.assertEqual(mode(prepared), 0o400)
                self.controller.retire(current, expected, root, budget, *args)
                self.assertFalse(current.exists())
                self.assertEqual(mode(private / 'secret'), 0o400)

    def test_directory_publisher_refuses_symlink_without_changing_target(self):
        with private_creation():
            target = self.base / 'target'
            target.mkdir(mode=0o700)
            link = self.base / 'link'
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises((ValueError, OSError)):
                self.common.public_directory(link, lambda: None)
            self.assertEqual(mode(target), 0o700)

    def test_directory_publisher_requires_owner(self):
        with private_creation():
            target = self.base / 'target'
            target.mkdir(mode=0o700)
            self.common.os = types.SimpleNamespace(**{**vars(os), 'geteuid': lambda: os.geteuid() + 1})
            with self.assertRaisesRegex(ValueError, 'Owned public directory'):
                self.common.public_directory(target, lambda: None)
            self.assertEqual(mode(target), 0o700)

    def test_failed_mode_finalization_closes_descriptor_and_preserves_private_mode(self):
        with private_creation():
            target = self.base / 'target'
            target.mkdir(mode=0o700)
            seen = []
            def failed(fd, requested):
                seen.append(fd)
                raise OSError(errno.EIO, 'generated finalization failure')
            self.common.os = types.SimpleNamespace(**{**vars(os), 'fchmod': failed})
            with self.assertRaisesRegex(OSError, 'generated finalization failure'):
                self.common.public_directory(target, lambda: None)
            self.assertEqual(len(seen), 1)
            with self.assertRaises(OSError) as closed:
                os.fstat(seen[0])
            self.assertEqual(closed.exception.errno, errno.EBADF)
            self.assertEqual(mode(target), 0o700)

    def test_actual_run_publishes_nested_source_capsule_before_prepare(self):
        class StopBeforeDataView(Exception): pass
        with private_creation():
            source = self.base / 'source'
            package = self.base / 'package'
            source.mkdir(); package.mkdir()
            raw = b'{"generated_source_only":true}\n'
            generated_write(source / 'SOURCE_MANIFEST.json', raw)
            program = self.base / 'program.py'
            generated_write(program, b'# generated inert participant source\n')
            root = self.base / 'custody'
            sources = types.SimpleNamespace(root=source, identity=self.common.pin(raw),
                raw={'loader.py': b'# generated inert loader\n',
                     'upstream/grade.py': b'# generated inert dependency\n'}, data={})
            self.controller.policy.selection = lambda *args: None
            self.controller.policy.reviews = lambda *args: None
            self.controller.grading.SCOPE = 'generated publication control'
            self.controller.dependencies = lambda *args: (package, [])
            self.common.Budget = FixtureBudget
            reached = []
            def check_before_prepare(*args):
                reached.append(True)
                self.assertEqual(mode(root / 'commitment'), 0o755)
                self.assertEqual(mode(root / 'commitment/upstream'), 0o755)
                for name in ('loader.py', 'upstream/grade.py', 'SOURCE_MANIFEST.json', 'program.py'):
                    self.assertEqual(mode(root / 'commitment' / name), 0o444)
                for path in (root, root / 'candidate', root / 'grade'):
                    self.assertEqual(mode(path), 0o700)
                self.assertEqual(mode(root / 'COMMITMENT.json'), 0o400)
                raise StopBeforeDataView()
            self.controller.prepare = check_before_prepare
            def forbidden_native(*args):
                raise AssertionError('Native execution forbidden by generated control')
            selection = dict(whole_seconds=1000, output=str(root), other_future_bytes=0,
                data_package=str(package), program={'path': str(program), **self.common.pin(program.read_bytes())},
                host_numpy_version='generated', method_review=self.common.pin(b'generated'))
            with self.assertRaises(StopBeforeDataView):
                self.controller.run(selection, sources, phase=forbidden_native,
                                    np=types.SimpleNamespace(__version__='generated'))
            self.assertEqual(reached, [True])
            self.assertEqual(mode(root / 'FAILURE.json'), 0o400)
            self.assertEqual(mode(source), 0o700)
            self.assertEqual(mode(source / 'SOURCE_MANIFEST.json'), 0o600)


if __name__ == '__main__':
    unittest.main(verbosity=2)
