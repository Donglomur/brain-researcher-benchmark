"""Source-bound iSTTC clock controls; all signals, timers and runtime I/O are RAM seams."""
import ast
import builtins
import copy
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import signal
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ADAPTER = HERE.parent / 'adapter.py'
OBSERVER = HERE.parents[1] / 'next-paper-complete-program/observe.py'
ADAPTER_BYTES = ADAPTER.read_bytes()
OBSERVER_BYTES = OBSERVER.read_bytes()
A = ModuleType('clock_review')
A.__file__ = str(ADAPTER)
exec(compile(ADAPTER_BYTES, str(ADAPTER), 'exec'), A.__dict__)
ORIGIN = 100.0
SIGNALS = (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)


class Clock:
    def __init__(self):
        self.now = ORIGIN
        self.original = {s: object() for s in SIGNALS}
        self.handlers = dict(self.original)
        self.end = None
        self.interval = 0.0
        self.events = []
        self.forged_timer = None
        self.fail_cancel = False
        self.fail_restores = set()
        self.fail_positive = False
        self.handler_delay = 0.0
    def monotonic(self): return self.now
    def getsignal(self, s): return self.handlers[s]
    def gets(self, kind):
        assert kind == signal.ITIMER_REAL
        if self.forged_timer is not None: return self.forged_timer
        return (max(0.0, self.end - self.now) if self.end is not None else 0.0, self.interval)
    def sets(self, kind, delay, interval=0.0):
        assert kind == signal.ITIMER_REAL
        self.events.append(('timer', delay, interval))
        if (delay == 0 and self.fail_cancel) or (delay > 0 and self.fail_positive):
            raise OSError('invented timer operation failure')
        self.end = self.now + delay if delay else None
        self.interval = interval
    def install(self, s, handler):
        self.events.append(('handler', s, handler))
        self.now += self.handler_delay
        if s in self.fail_restores and handler is self.original[s]:
            raise OSError('invented handler restoration failure')
        before = self.handlers[s]
        self.handlers[s] = handler
        return before
    def active(self):
        self.handlers[signal.SIGALRM] = A.expired
        self.end = ORIGIN + 120
    def seams(self):
        stack = ExitStack()
        for name, value in [('ORIGIN', ORIGIN), ('INITIAL_HANDLERS', dict(self.original)),
                            ('INITIAL_HANDLER', self.original[signal.SIGALRM])]:
            stack.enter_context(patch.object(A, name, value))
        stack.enter_context(patch.object(A.time, 'monotonic', self.monotonic))
        stack.enter_context(patch.object(A.signal, 'getsignal', self.getsignal))
        stack.enter_context(patch.object(A.signal, 'signal', self.install))
        stack.enter_context(patch.object(A.signal, 'getitimer', self.gets))
        stack.enter_context(patch.object(A.signal, 'setitimer', self.sets))
        return stack


class RamPath:
    def __init__(self, value): self.p = PurePosixPath(str(value))
    def __str__(self): return str(self.p)
    def __fspath__(self): return str(self)
    def __truediv__(self, other): return RamPath(self.p / str(other))
    @property
    def parent(self): return RamPath(self.p.parent)
    @property
    def parents(self): return tuple(RamPath(p) for p in self.p.parents)
    @property
    def parts(self): return self.p.parts
    def absolute(self): return self if self.p.is_absolute() else RamPath('/invented/' + str(self.p))
    def is_absolute(self): return self.p.is_absolute()
    def as_posix(self): return self.p.as_posix()
    def is_symlink(self): return False
    def exists(self): return False
    def is_dir(self): return True
    def mkdir(self, *args, **kwargs): pass
    def rglob(self, pattern): return ()
    def stat(self): return SimpleNamespace(st_size=64)


class Parser:
    def __init__(self, *, observer_error=False, **kwargs): self.observer_error = observer_error
    def add_argument(self, *args, **kwargs): pass
    def parse_args(self, argv=None):
        if self.observer_error: raise SystemExit(2)
        return SimpleNamespace(program='/invented/program', output='/invented/out', review='/invented/review',
                               source_bytes=17, source_sha256='a' * 64, other_reserve_bytes=0,
                               selection='/invented/selection', selection_sha256='b' * 64)


class ClockControls(unittest.TestCase):
    def compile_observer(self): return A.adapted_observe(OBSERVER_BYTES, str(OBSERVER))

    def test_two_ast_nodes_reverse_exactly_with_unchanged_clock_constants(self):
        captured = []
        def compile_seam(tree, filename, mode):
            captured.append(copy.deepcopy(tree))
            return builtins.compile(tree, filename, mode)
        with patch.object(A, 'compile', compile_seam, create=True): self.compile_observer()
        original = ast.parse(OBSERVER_BYTES)
        changed = captured[0]
        self.assertEqual(len(changed.body), len(original.body))
        differing = [i for i, (x, y) in enumerate(zip(original.body, changed.body)) if ast.dump(x) != ast.dump(y)]
        self.assertEqual(len(differing), 2)
        origin, startup = differing
        self.assertEqual(ast.dump(changed.body[origin].value), ast.dump(ast.Name(id='ADAPTER_ORIGIN', ctx=ast.Load())))
        self.assertEqual(ast.dump(changed.body[startup]), ast.dump(ast.parse('CLOCK_OWNED=ADAPTER_TRANSFER_STARTUP()').body[0]))
        for i in differing: changed.body[i] = copy.deepcopy(original.body[i])
        self.assertEqual(ast.dump(changed), ast.dump(original))
        for name in ('cleanup_clock', 'enter_startup', 'main', 'verify_collection', 'observe_child'):
            a = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == name)
            b = next(n for n in captured[0].body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(ast.dump(a), ast.dump(b))
        def endpoints(t): return [n.value for n in ast.walk(t) if isinstance(n, ast.Constant) and n.value in (900000, 900120, 900240)]
        self.assertEqual(endpoints(original), endpoints(captured[0]))
        self.assertEqual(set(endpoints(original)), {900000, 900120, 900240})

    def test_structural_drift_refused(self):
        text = OBSERVER_BYTES.decode()
        for old, new in [('ORIGIN=time.monotonic()', 'ORIGIN=0.0'), ('CLOCK_OWNED=False', 'CLOCK_OWNED=True'),
                         ("if __name__=='__main__':enter_startup()", "if __name__=='__main__':enter_startup();pass")]:
            with self.assertRaises(ValueError): A.adapted_observe(text.replace(old, new).encode(), str(OBSERVER))
        with self.assertRaises(ValueError): A.adapted_observe((text + "\nif __name__=='__main__':pass\n").encode(), str(OBSERVER))

    def test_startup_owner_renewal_periodic_and_expiry_rejected(self):
        c = Clock(); c.active(); c.now += 20
        with c.seams():
            A.startup_owned()
            for timer in ((0., 0.), (100., 1.), (120., 0.)):
                c.forged_timer = timer
                with self.assertRaises(ValueError): A.startup_owned()
            c.forged_timer = None
            c.handlers[signal.SIGALRM] = object()
            with self.assertRaises(ValueError): A.startup_owned()
            c.handlers[signal.SIGALRM] = A.expired; c.now = ORIGIN + 120
            with self.assertRaises(ValueError): A.startup_owned()

    def test_transfer_literal_true_same_origin_deadline_and_delayed_refusal(self):
        c = Clock(); c.active(); c.now += 20
        with c.seams():
            self.assertIs(A.transfer_startup(), True)
            self.assertEqual(c.end, ORIGIN + 900240)
        c = Clock(); c.active(); c.now = ORIGIN + 119; c.handler_delay = 2
        with c.seams(), self.assertRaisesRegex(ValueError, 'startup still live'):
            A.transfer_startup()
        self.assertFalse(any(e[0] == 'timer' for e in c.events))

    def test_actual_adapted_module_owns_cleanup_and_retains_initial_handlers(self):
        c = Clock(); c.active(); c.now += 20
        compiled, _ = self.compile_observer()
        ns = {'__name__': '__adapter_load__', '__file__': str(OBSERVER), 'ADAPTER_ORIGIN': ORIGIN,
              'ADAPTER_TRANSFER_STARTUP': A.transfer_startup}
        with c.seams():
            exec(compiled, ns)
            self.assertIs(ns['CLOCK_OWNED'], True)
            self.assertEqual(ns['ORIGIN'], ORIGIN)
            self.assertIs(ns['INITIAL_HANDLERS'][signal.SIGALRM], A.expired)
            for s in SIGNALS[1:]: self.assertIs(ns['INITIAL_HANDLERS'][s], c.original[s])
            self.assertEqual(c.end, ORIGIN + 900240)
            ns['cleanup_clock']()
            self.assertEqual(c.gets(signal.ITIMER_REAL), (0., 0.))
            self.assertIs(c.handlers[signal.SIGALRM], A.expired)

    def run_main(self, *, observer_failure=None, faults=(), literal_transfer=None, late=False,
                 transfer_failure=False, observer_cleanup_late=False):
        c = Clock(); c.active(); c.now += 20
        c.fail_positive = transfer_failure
        compiled, guard = self.compile_observer()
        admitted = {'selection_operand': (Path('/invented/selection'), {'bytes': 1, 'sha256': 'b' * 64}),
                    'output': Path('/invented/out'), 'metadata_pins': []}
        binding = {'controller_manifest': {'bytes': 17, 'sha256': 'c' * 64}}
        observed_namespaces, saved = [], []
        class Captures:
            def __init__(self, end): self.end, self.reserved = end, 0
            def tick(self):
                if c.now >= self.end: raise TimeoutError('invented capture deadline')
            def read(self, *args, **kwargs): self.tick(); return b'{}'
        class ObserverIO:
            def __init__(self): self.read = self.write = 0
            def capture(self, path, *args, **kwargs):
                name = str(path)
                if name.endswith('selection'):
                    v = {'operation_selected': True, 'schema': 'isttc_complete_program_operation_v1',
                         'source_manifest': {'bytes': 1, 'sha256': 'd' * 64}, 'other_future_bytes': 0}
                elif name.endswith('SOURCE_MANIFEST.json'):
                    v = {'files': {'controller.py': {'bytes': 8, 'sha256': 'e' * 64}}}
                else: return b'invented'
                return (json.dumps(v) + '\n').encode()
            def save(self, path, body): saved.append(str(path)); return A.pin(body)
        def exec_seam(code, ns):
            try:
                builtins.exec(code, ns)
            except BaseException as error:
                c.events.append(('exec_error', ns.get('__name__'), type(error).__name__, ns.get('CLOCK_OWNED')))
                raise
            if ns['__name__'] == '__adapter_load__':
                observed_namespaces.append(ns)
                ns.update(IO=ObserverIO, Path=RamPath, HERE=RamPath('/invented/source'),
                          load=lambda *args: SimpleNamespace(selected=lambda selected: None),
                          observe_child=lambda *args: {'natural_exit': True},
                          verify_collection=lambda *args: {'bytes': 8, 'sha256': 'f' * 64},
                          sys=SimpleNamespace(path=[], executable='/invented/python'))
                if observer_cleanup_late:
                    original_cleanup = ns['cleanup_clock']
                    def delayed_cleanup(primary=None):
                        original_cleanup(primary)
                        c.now = ORIGIN + 900240
                    ns['cleanup_clock'] = delayed_cleanup
        def outcome(*args):
            c.fail_cancel = 'cancel' in faults
            c.fail_restores = {s for s in SIGNALS if s in faults}
            return {'invented': True}
        real_import = builtins.__import__
        def import_seam(name, *args, **kwargs):
            if observer_failure == 'import' and name == 'argparse': raise ImportError('invented post-transfer import')
            return real_import(name, *args, **kwargs)
        def parser_factory(*args, **kwargs):
            return Parser(observer_error=(observer_failure == 'argparse' and not kwargs))
        with c.seams(), ExitStack() as st:
            st.enter_context(patch.object(A, 'sys', SimpleNamespace(argv=['before'], flags=SimpleNamespace(isolated=True, no_site=True),
                                                                  dont_write_bytecode=True, pycache_prefix='/invented/absent')))
            st.enter_context(patch.object(A, 'Captures', Captures))
            st.enter_context(patch.object(A, 'literal', side_effect=lambda p: Path(p)))
            st.enter_context(patch.object(A, 'own_sources', return_value=binding))
            st.enter_context(patch.object(A, 'target', return_value=(compiled, guard, OBSERVER, {})))
            st.enter_context(patch.object(A, 'bind', return_value=admitted))
            st.enter_context(patch.object(A, 'outcome', side_effect=outcome))
            st.enter_context(patch.object(A, 'exec', exec_seam, create=True))
            st.enter_context(patch.object(A, 'print', create=True))
            st.enter_context(patch.object(A.argparse, 'ArgumentParser', parser_factory))
            st.enter_context(patch.object(A.os.path, 'lexists', return_value=False))
            st.enter_context(patch.object(A.os, 'chmod'))
            st.enter_context(patch.object(A.os, 'statvfs', return_value=SimpleNamespace(f_bavail=30 * 1024**3, f_frsize=1)))
            st.enter_context(patch.object(builtins, '__import__', import_seam))
            if literal_transfer is not None:
                real_transfer = A.transfer_startup
                def transfer(): real_transfer(); return literal_transfer
                st.enter_context(patch.object(A, 'transfer_startup', transfer))
            if late:
                original_exec = exec_seam
                def late_exec(code, ns):
                    try: original_exec(code, ns)
                    except SystemExit:
                        c.now = ORIGIN + 900240
                        raise
                st.enter_context(patch.object(A, 'exec', late_exec, create=True))
            code = A.main([])
            argv_after = A.sys.argv
        return code, c, observed_namespaces, saved, argv_after

    def test_actual_adapter_and_original_observer_main_happy_cleanup(self):
        code, c, ns, saved, argv = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(len(ns), 1)
        self.assertTrue(any(p.endswith('/OBSERVED.json') for p in saved))
        self.assertEqual(c.handlers, c.original)
        self.assertEqual(c.gets(signal.ITIMER_REAL), (0., 0.))
        self.assertEqual(argv, ['before'])
        self.assertGreaterEqual(sum(e[0] == 'timer' and e[1] == 0 for e in c.events), 2)

    def test_literal_ownership_rejects_integer_true(self):
        code, c, _, saved, _ = self.run_main(literal_transfer=1)
        self.assertEqual(code, 2)
        self.assertEqual(c.handlers, c.original)
        self.assertFalse(any(p.endswith('/OBSERVED.json') for p in saved))

    def test_import_and_argparse_failure_restore_original_handlers(self):
        for failure in ('import', 'argparse'):
            code, c, _, saved, argv = self.run_main(observer_failure=failure)
            self.assertEqual(code, 2)
            self.assertEqual(c.handlers, c.original)
            self.assertEqual(c.gets(signal.ITIMER_REAL), (0., 0.))
            self.assertEqual(argv, ['before'])
            self.assertFalse(any(p.endswith('/OBSERVED.json') for p in saved))
            self.assertTrue(any(e[0] == 'timer' and e[1] > 120 for e in c.events))

    def test_actual_main_failed_transfer_keeps_observer_unowned_and_restores_all(self):
        code, c, _, saved, argv = self.run_main(transfer_failure=True)
        self.assertEqual(code, 2)
        self.assertIn(('exec_error', '__adapter_load__', 'OSError', False), c.events)
        self.assertEqual(c.handlers, c.original)
        self.assertEqual(c.gets(signal.ITIMER_REAL), (0., 0.))
        self.assertEqual(argv, ['before'])
        self.assertFalse(any(p.endswith('/OBSERVED.json') for p in saved))
        self.assertTrue(any(e[0] == 'timer' and e[1] > 120 for e in c.events))

    def test_final_original_guard_refuses_observer_cleanup_finishing_late(self):
        code, c, _, saved, _ = self.run_main(observer_cleanup_late=True)
        self.assertEqual(code, 2)
        self.assertTrue(any(p.endswith('/OBSERVED.json') for p in saved))
        self.assertIn(('exec_error', '__main__', 'ValueError', True), c.events)
        self.assertNotIn(('exec_error', '__main__', 'SystemExit', True), c.events)
        self.assertEqual(c.handlers, c.original)

    def test_actual_main_independent_cleanup_faults_force_nonzero(self):
        for faults in (('cancel',), (signal.SIGALRM,), (signal.SIGTERM,), (signal.SIGINT,),
                       ('cancel', *SIGNALS)):
            code, c, _, saved, _ = self.run_main(faults=faults)
            self.assertEqual(code, 2)
            self.assertTrue(any(p.endswith('/OBSERVED.json') for p in saved))
            self.assertEqual([e[1] for e in c.events[-3:]], list(SIGNALS))
            self.assertTrue(all(e[0] == 'handler' for e in c.events[-3:]))

    def test_expired_postflight_refuses_no_minimum_new_timer(self):
        code, c, _, _, _ = self.run_main(late=True)
        self.assertEqual(code, 2)
        self.assertEqual(c.handlers, c.original)
        self.assertFalse(any(e[0] == 'timer' and e[1] == 0.001 for e in c.events))
        self.assertEqual(c.gets(signal.ITIMER_REAL), (0., 0.))

    def test_startup_install_failure_independently_restores_all_handlers(self):
        c = Clock(); c.fail_positive = True
        with c.seams(), self.assertRaises(OSError): A.enter_startup()
        self.assertEqual(c.handlers, c.original)
        self.assertEqual([e[1] for e in c.events[-3:]], list(SIGNALS))

    def test_actual_target_propagates_explicit_empty_member_admission(self):
        empty = 'baseline/source/src/isttc/scripts/__init__.py'
        bodies = {'observe.py': OBSERVER_BYTES, 'RESOURCE_PLAN.json': b'{}', empty: b''}
        bodies.update({f'member_{i}.py': b'# invented source\n' for i in range(21)})
        members = {name: A.pin(body) for name, body in bodies.items()}
        manifest = {'schema': 'isttc_full100000_program_source_v1', 'task_id': A.TASK,
                    'source_only': True, 'files': members}
        binding = {'controller_manifest': {'invented': True}, 'controller_members': members,
                   'controller_directory': 'invented', 'controller_resources': {}, 'selected_metadata': []}
        events = []
        class SourceCaptures:
            def read(self, path, cap, expected, *, allow_empty=False):
                name = str(path).removeprefix('/invented/runtime/')
                events.append((name, allow_empty, expected))
                body = bodies[name]
                if not allow_empty and not body: raise ValueError('unexpected nonempty requirement')
                if A.pin(body) != expected: raise ValueError('invented exact source pin mismatch')
                return body
        with patch.object(A, 'metadata', return_value=(manifest, b'invented manifest')), \
                patch.object(A, 'relative', return_value=Path('/invented/runtime')):
            compiled, guard, filename, got = A.target(SourceCaptures(), binding)
        self.assertEqual(len(got), 24)
        self.assertEqual(got[empty], b'')
        self.assertEqual([e for e in events if e[0] == empty], [(empty, True, A.pin(b''))])
        self.assertEqual(filename, Path('/invented/runtime/observe.py'))
        with self.assertRaises(ValueError): A.descriptor(A.pin(b''), 131072)
        self.assertEqual(A.descriptor(A.pin(b''), 131072, allow_empty=True), A.pin(b''))


if __name__ == '__main__':
    unittest.main(verbosity=2)
