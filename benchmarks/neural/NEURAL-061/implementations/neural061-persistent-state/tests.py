"""Generated source controls only. No native process, data, model or API calls."""
import copy
import hashlib
import io
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import resource
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).absolute().parent
PRODUCER = HERE / 'producer'
# An explicit finite author-control ceiling, not a scientific runtime selection.
resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
# macOS does not accept this small RLIMIT_AS for an already loaded interpreter.
# A source-control RSS ceiling is checked explicitly below; no physical
# enforcement claim is inferred from that observation.


def source(name):
    module = types.ModuleType(name); module.__file__ = str(PRODUCER / (name + '.py'))
    sys.modules[name] = module
    body = (PRODUCER / (name + '.py')).read_bytes()
    exec(compile(body, module.__file__, 'exec'), module.__dict__)
    module.__compiled_source_bytes__ = body
    return module


wire = source('wire'); enclosure = source('enclosure'); supervisor = source('supervisor')
adapter = source('adapter'); loader = source('loader'); child = source('child')
INHERITED = json.loads((PRODUCER / 'INHERITED.json').read_bytes())
finder, accepted = loader.capture_accepted(HERE / 'science', INHERITED,
                                          ('/generated-private-targets',))
from n061 import catalogue, policy, production, preparation, contracts


def request():
    return {'image': 'sha256:' + 'a' * 64, 'memory_bytes': 128 * 1024 * 1024,
            'nano_cpus': 1000000000, 'pids': 16, 'cpu_seconds': 10, 'tmp_bytes': 1048576,
            'frame_bytes': 1048576, 'stderr_bytes': 4096, 'wall_seconds': 20,
            'command_seconds': 5, 'command_bytes': 65536}


def inspect_fixture():
    r = request(); mounts = {'/trusted': '/owned/trusted', '/participant/method.py': '/owned/method.py'}
    h = {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False, 'CapDrop': ['ALL'],
         'CapAdd': None, 'SecurityOpt': ['no-new-privileges:true'], 'PidMode': '', 'IpcMode': 'private',
         'UTSMode': '', 'UsernsMode': '', 'CgroupnsMode': 'private', 'AutoRemove': False,
         'RestartPolicy': {'Name': 'no'}, 'OomKillDisable': False, 'Memory': r['memory_bytes'],
         'MemorySwap': r['memory_bytes'], 'NanoCpus': r['nano_cpus'], 'PidsLimit': r['pids'],
         'Tmpfs': enclosure.tmpfs(r), 'LogConfig': {'Type': 'local', 'Config': {'max-size': '64k',
         'max-file': '1', 'compress': 'false'}}, 'Ulimits': [
             {'Name': key, 'Soft': val, 'Hard': val} for key, val in
             [('cpu', 10), ('nofile', 128), ('core', 0), ('fsize', 1048576)]],
         'Mounts': [{'Type': 'bind', 'Target': target, 'Source': value, 'ReadOnly': True}
                    for target, value in mounts.items()]}
    return {'Name': '/n061-' + 'b' * 32, 'Image': r['image'],
            'Config': {'Image': r['image'], 'Entrypoint': ['python'], 'Cmd': enclosure.command(r),
                       'WorkingDir': '/tmp', 'User': '65534:65534', 'OpenStdin': True, 'Tty': False,
                       'Env': [key + '=1' for key in enclosure.THREADS] + ['PYTHONDONTWRITEBYTECODE=1']},
            'HostConfig': h, 'State': {'Status': 'created', 'Running': False, 'Pid': 0},
            'NetworkSettings': {'Networks': {'none': {}}},
            'Mounts': [{'Type': 'bind', 'Destination': target, 'Source': value, 'RW': False}
                       for target, value in mounts.items()]}, mounts, r


class Owner:
    deadline = 10**30
    def __init__(self): self.used = {}; self.failure = None
    def tick(self): pass
    def reserve(self, key, amount): self.used[key] = self.used.get(key, 0) + amount
    def snapshot(self): return {'generated': True, 'used': self.used.copy()}
    def fail(self, error): self.failure = error


class Opaque:
    def __reduce__(self): raise AssertionError('Fitted state serialization is forbidden')


def binding():
    return {'method': (17, 'b' * 64), 'cell': ('wheel_velocity', 'r', 10, 0, 'anatomy'),
            'arm': 'BR', 'source': tuple('s' + str(i) for i in range(423)),
            'evaluation': tuple('e' + str(i) for i in range(29)), 'state': 'state-1'}


def view(sid, b, training):
    window = {'query': sid + '-q', 'mask': [True, False]}
    if training: window['values'] = [1., float('nan')]
    return {'status': 'complete', 'session': sid, 'cell': b['cell'], 'arm': b['arm'], 'windows': (window,)}


def child_requests(b, *, duplicate=False, leak=False, early_retire=False):
    operations = [('fit', {'source': tuple(view(s, b, True) for s in b['source'])})]
    for sid in b['evaluation']:
        query = view(sid, b, False)
        if leak: query['windows'][0]['values'] = [0, 0]
        operations.append(('predict', {'session': sid, 'query': query}))
    if early_retire: operations = operations[:2]
    operations.append(('retire', None))
    return b''.join(wire.frame({'version': 'N061_CHILD_V1', 'sequence': 0 if duplicate else n,
                              'binding': b, 'operation': op, 'payload': payload}, 1048576)
                    for n, (op, payload) in enumerate(operations))


class FakeWorker:
    def __init__(self): self.state = Opaque(); self.count = 0
    def fit(self, method, source, tool):
        assert len(source) == 423 and tool is None; return self.state
    def infer(self, method, state, query, tool):
        assert state is self.state and tool is None; self.count += 1
        return {'status': 'complete', 'windows': ({'query': query['windows'][0]['query'], 'values': [1., 2.]},)}


class PrimitiveArray:
    dtype = types.SimpleNamespace(kind='f', hasobject=False)
    ndim = 1
    def __init__(self, values): self.values = tuple(values)
    def __len__(self): return len(self.values)


class GeneratedChild:
    all = []
    def __init__(self, command, root, bodies, method, binding, owner):
        self.binding = binding; self.closed = False; self.operations = []; self.opaque = Opaque()
        GeneratedChild.all.append(self)
    def start(self): return self
    def request_operation(self, op, payload):
        self.operations.append(op)
        if op == 'fit':
            assert len(payload['source']) == 423; return {'state': self.binding['state']}
        if op == 'skip': return {'skipped': payload['session']}
        if op == 'retire': return {'retired': self.binding['state']}
        return {'status': 'complete', 'windows': tuple({'query': w['query'], 'values': PrimitiveArray([1., 2.])}
                                                       for w in payload['query']['windows'])}
    def finish(self): self.closed = True; return ('generated-closure', self.binding['state'])
    def abort(self): self.closed = True


def prepared_fixture(regions=('r1', 'r2')):
    public = {}
    for i in range(452):
        source = i < 423; j = i if source else i - 423
        public[('s' if source else 'e') + str(j)] = {'role': 'source' if source else 'evaluation',
                   'ordinal': i, 'animal': ('a' if source else 'b') + str(j % (126 if source else 13))}
    selected = policy.policy(); cat = catalogue.build(selected, regions, public)
    return {'catalogue': cat, 'policy': selected, 'cells': cat.cells, 'public': public}


class Tests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(supervisor.subprocess, 'Popen', side_effect=AssertionError('Native execution forbidden in generated controls'))
        guard.start(); self.addCleanup(guard.stop)
        signal_guard = patch.object(supervisor.os, 'killpg', side_effect=AssertionError('Actual process signalling forbidden in generated controls'))
        signal_guard.start(); self.addCleanup(signal_guard.stop)

    def test_primitive_exact_roundtrip(self):
        value = {(1, 'x'): (2**63 + 17, -0., b'abc', wire.Array('<f8', (2,), struct.pack('<dd', 1., float('nan'))))}
        decoded = wire.decode(wire.encode(value, 4096), 4096, materialize=False)
        self.assertEqual(decoded[(1, 'x')][0], 2**63 + 17)
        self.assertEqual(struct.pack('>d', decoded[(1, 'x')][1]), struct.pack('>d', -0.))
        self.assertEqual(decoded[(1, 'x')][3], value[(1, 'x')][3])

    def test_state_and_object_dtypes_rejected(self):
        for value in (Opaque(), wire.Array('|O8', (1,), b'0' * 8), wire.Array('<f8', (2,), b'0' * 8)):
            with self.assertRaises(ValueError): wire.encode(value, 1024)

    def test_frame_cap_before_body_and_duplicate_dictionary(self):
        with self.assertRaises(ValueError): wire.read_frame(io.BytesIO(struct.pack('>Q', 2**40)), 4096)
        with self.assertRaises(ValueError): wire.decode(b'["dict",[[["atom","x"],["atom",1]],[["atom","x"],["atom",2]]]]', 4096)

    def test_complete_persistent_state_protocol(self):
        b = binding(); worker = FakeWorker(); output = io.BytesIO()
        child.serve(object(), worker, wire, io.BytesIO(child_requests(b)), output, 1048576, b)
        self.assertEqual(worker.count, 29); output.seek(0)
        replies = [wire.read_frame(output, 1048576) for _ in range(31)]
        self.assertEqual(replies[-1]['result'], {'retired': b['state']}); self.assertEqual(output.read(), b'')

    def test_child_rejects_replay_labels_and_partial_retirement(self):
        for kwargs in ({'duplicate': True}, {'leak': True}, {'early_retire': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                b = binding(); child.serve(object(), FakeWorker(), wire, io.BytesIO(child_requests(b, **kwargs)), io.BytesIO(), 1048576, b)

    def test_boundary_accepts_exact_fixture(self):
        info, mounts, r = inspect_fixture()
        self.assertFalse(enclosure.verify(info, info['Name'][1:], mounts, r)['native_qualification'])
        argv = enclosure.create_argv(info['Name'][1:], mounts, r)
        self.assertIn('private', argv); self.assertIn('--pull', argv); self.assertNotIn('--privileged', argv)

    def test_boundary_rejects_namespace_borrowing_and_extra_mounts(self):
        original, mounts, r = inspect_fixture()
        mutations = [('PidMode', 'container:other'), ('IpcMode', 'container:other'), ('UTSMode', 'host'),
                     ('UsernsMode', 'host'), ('CgroupnsMode', 'host'), ('Memory', 1), ('NetworkMode', 'host')]
        for key, value in mutations:
            info = copy.deepcopy(original); info['HostConfig'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): enclosure.verify(info, info['Name'][1:], mounts, r)
        info = copy.deepcopy(original); info['Mounts'].append({'Type': 'bind', 'Destination': '/targets', 'Source': '/private', 'RW': False})
        with self.assertRaises(ValueError): enclosure.verify(info, info['Name'][1:], mounts, r)

    def test_private_overlap_precedes_metadata(self):
        with patch.object(Path, 'is_symlink', side_effect=AssertionError('metadata touched')):
            with self.assertRaises(ValueError):
                supervisor.lexical_disjoint(('/private/source.py',), ('/private',))
            supervisor.lexical_disjoint(('/public/source.py',), ('/private',))

    def test_same_open_capture_rejects_changes_links_and_wrong_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / 'source.py'; path.write_bytes(b'x = 1\n'); digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(supervisor.capture(path, 6, digest), b'x = 1\n')
            with self.assertRaises(ValueError): supervisor.capture(path, 6, '0' * 64)
            linked = Path(temp) / 'linked.py'; linked.symlink_to(path)
            with self.assertRaises(ValueError): supervisor.capture(linked, 6, digest)

    def test_owned_mount_permissions_ignore_umask_without_changing_parent(self):
        class StopCommand:
            request = request()
            def run(self, arguments, **kwargs):
                if arguments[0] == 'create':
                    paths = [x.split('src=')[1].split(',')[0] for x in arguments if x.startswith('type=bind,')]
                    self.permissions = [(Path(p).stat().st_mode & 0o777) for p in paths]
                    self.parent_permissions = Path(paths[0]).parent.stat().st_mode & 0o777
                    raise RuntimeError('generated stop before any native dispatch')
                return b''
        with tempfile.TemporaryDirectory() as temp:
            os.chmod(temp, 0o700); cmd = StopCommand(); old = os.umask(0o077)
            try:
                obj = supervisor.ParticipantChild(cmd, temp, {n: b'# generated\n' for n in ('child.py', 'wire.py', 'worker.py', 'contracts.py')},
                                                 b'# method\n', binding(), Owner())
                with self.assertRaises(RuntimeError): obj.start()
            finally: os.umask(old)
            self.assertEqual(cmd.permissions, [0o755, 0o444]); self.assertEqual(cmd.parent_permissions, 0o755)
            self.assertEqual(Path(temp).stat().st_mode & 0o777, 0o700)

    def test_complete_original_population_caller_and_common_support(self):
        prepared = prepared_fixture(); cat = prepared['catalogue']; owner = Owner()
        command = supervisor.NativeCommand('/generated/docker', 'unix:///generated/socket', request(), owner)
        host = adapter.A0Host(command, '/generated/scratch', {}, b'# generated method\n', owner)
        GeneratedChild.all = []
        def views(prepared, sid, cell, arm, training):
            b = {'cell': cell, 'arm': arm}; result = view(sid, b, training)
            # Same prespecified unavailable query slot in every operand.
            return {'status': 'unavailable', 'reason': 'generated_support'} if sid == 'e1' else result
        def reference(prepared, cell, owner):
            return {'states': {a: Opaque() for a in cat.policy.reference_arms},
                    'predictions': {(sid, a): views(prepared, sid, cell, a, False)
                                    for sid in cat.evaluation for a in cat.policy.reference_arms},
                    'selection': {'generated_no_model_fit': True}}
        fake_np = types.SimpleNamespace(ndarray=PrimitiveArray,
                    isfinite=lambda value: types.SimpleNamespace(all=lambda: True))
        with patch.object(adapter, 'ParticipantChild', GeneratedChild), \
             patch.object(production, 'session_view', views), patch.object(preparation, 'session_view', views), \
             patch.object(production, 'complete_reference', reference), patch.dict(sys.modules, {'numpy': fake_np}):
            result = adapter.construct_prepared(prepared, host, owner)
        self.assertEqual(len(cat.cells), 20); self.assertEqual(len(result.collection.seal), 4640)
        self.assertEqual(len(GeneratedChild.all), 40)
        self.assertTrue(all(c.closed and c.operations.count('predict') == 28 and
                            c.operations.count('skip') == 1 and c.operations[-1] == 'retire' for c in GeneratedChild.all))
        self.assertEqual(len({id(c.opaque) for c in GeneratedChild.all}), 40)
        self.assertEqual(len(result.support.planned_animals), 13)
        self.assertEqual(sum(row.status.value == 'scientific_unavailable' for row in result.support.sessions), 2)
        self.assertFalse(host.reference_states)
        with self.assertRaises(Exception): host.publish_production(result, owner)

    def test_public_entry_still_refuses_before_effects(self):
        with self.assertRaises(Exception): production.collect({}, object(), object())

    def test_owned_group_absence_requires_original_absence(self):
        with patch.object(supervisor.os, 'killpg', side_effect=ProcessLookupError):
            supervisor.require_group_absence(123)
        with patch.object(supervisor.os, 'killpg', return_value=None), self.assertRaises(RuntimeError):
            supervisor.require_group_absence(123)

    def transport_control(self, *, wrong_sequence=False, truncated=False, stderr_overflow=False, bad_native_exit=False):
        class Stream:
            def __init__(self, fd): self.fd = fd; self.closed = False
            def fileno(self): return self.fd
            def close(self): self.closed = True
        class Process:
            pid = 123; returncode = 0
            stdin, stdout, stderr = Stream(10), Stream(11), Stream(12)
            def wait(self, timeout): return self.returncode
            def poll(self): return self.returncode
        class Select:
            def __init__(self): self.rows = {}
            def register(self, stream, events, label):
                self.rows[stream.fd] = types.SimpleNamespace(fd=stream.fd, fileobj=stream, data=label)
            def unregister(self, stream): del self.rows[stream.fd]
            def select(self, timeout): return [(key, 1) for key in list(self.rows.values())]
            def get_map(self): return self.rows
            def close(self): self.rows.clear()
        class Command:
            request = request()
            def __init__(self): self.events = []
            def run(self, args, **kwargs):
                self.events.append(args)
                if args[0] == 'inspect':
                    return json.dumps([{'Id': 'a' * 64, 'State': {'Status': 'exited', 'Running': False,
                         'Pid': 0, 'ExitCode': 1 if bad_native_exit else 0, 'OOMKilled': False, 'Error': ''}}]).encode()
                return b''
        b = binding(); cmd = Command(); obj = supervisor.ParticipantChild(cmd, '/generated', {}, b'', b, Owner())
        obj.proc = Process(); obj.pending = b''; obj.deadline = 10**30; obj.container_id = 'a' * 64
        obj.directory = Path('/generated-owned'); obj.closed = False; obj.create_started = True
        response = wire.frame({'version': 'N061_CHILD_V1', 'sequence': 1 if wrong_sequence else 0,
                               'binding': b, 'operation': 'retire', 'result': {'retired': b['state']}}, 1048576)
        reads = {11: [response[:9] if truncated else response, b''],
                 12: [b'x' * 4097 if stderr_overflow else b'']}
        def read(fd, size):
            return reads[fd].pop(0) if reads[fd] else b''
        with patch.object(supervisor.selectors, 'DefaultSelector', Select), \
             patch.object(supervisor.os, 'read', read), patch.object(supervisor.os, 'write', lambda fd, data: len(data)), \
             patch.object(supervisor.os, 'killpg', return_value=None), \
             patch.object(supervisor, 'require_group_absence', return_value=None), \
             patch.object(supervisor.shutil, 'rmtree', return_value=None):
            result = obj.request_operation('retire', None)
            closure = obj.finish()
        return result, closure, obj, cmd

    def test_supervisor_complete_response_eof_exit_reap_and_absence(self):
        result, closure, obj, cmd = self.transport_control()
        self.assertEqual(result, {'retired': 'state-1'}); self.assertTrue(closure.removed)
        self.assertFalse(closure.qualified); self.assertEqual(obj.eofs, {'out', 'err'})
        self.assertEqual(cmd.events[-1][0:3], ['container', 'ls', '-aq'])

    def test_supervisor_rejects_replay_truncation_stderr_and_native_failure(self):
        for kwargs in ({'wrong_sequence': True}, {'truncated': True}, {'stderr_overflow': True}, {'bad_native_exit': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, BaseExceptionGroup)):
                self.transport_control(**kwargs)

    def test_original_failure_and_cleanup_failure_both_escape(self):
        original = ValueError('original operation'); cleanup = RuntimeError('original cleanup')
        with self.assertRaises(BaseExceptionGroup) as caught:
            supervisor.raise_all(original, [cleanup])
        self.assertIs(caught.exception.exceptions[0], original)
        self.assertIs(caught.exception.exceptions[1], cleanup)

    def test_post_spawn_setup_failure_still_owns_group_and_streams(self):
        class Stream:
            def __init__(self, fail=False): self.fail = fail; self.closed = False
            def close(self):
                self.closed = True
                if self.fail: raise OSError('generated stdin close failure')
        proc = types.SimpleNamespace(pid=123, returncode=0, stdin=Stream(True), stdout=Stream(), stderr=Stream(),
                                     wait=lambda timeout: 0, poll=lambda: 0)
        cmd = supervisor.NativeCommand('/generated/docker', 'unix:///generated/socket', request(), Owner())
        with patch.object(cmd, 'spawn', return_value=proc), patch.object(supervisor.os, 'killpg') as signal_call, \
             patch.object(supervisor, 'require_group_absence') as absence:
            with self.assertRaises(BaseExceptionGroup) as caught: cmd.run(['inspect', 'generated'])
        self.assertIsInstance(caught.exception.exceptions[0], OSError)
        signal_call.assert_called_once_with(123, supervisor.signal.SIGKILL); absence.assert_called_once_with(123)
        self.assertTrue(proc.stdout.closed and proc.stderr.closed)

    def test_abort_kills_surviving_group_and_requires_container_absence(self):
        stream = types.SimpleNamespace(close=lambda: None)
        proc = types.SimpleNamespace(pid=123, returncode=0, stdin=stream, stdout=stream, stderr=stream,
                                     wait=lambda timeout: 0, poll=lambda: 0)
        class Command:
            request = request()
            def __init__(self, present): self.present = present; self.events = []
            def run(self, arguments, **kwargs):
                self.events.append(arguments)
                return b'owned-container\n' if arguments[0] == 'container' and self.present else b''
        for present in (False, True):
            cmd = Command(present); obj = supervisor.ParticipantChild(cmd, '/generated', {}, b'', binding(), Owner())
            obj.proc = proc; obj.container_id = 'a' * 64; obj.create_started = True
            with patch.object(supervisor.os, 'killpg') as signal_call, patch.object(supervisor, 'require_group_absence') as absence:
                if present:
                    with self.assertRaises(BaseExceptionGroup): obj.abort()
                else: obj.abort()
            signal_call.assert_called_once_with(123, supervisor.signal.SIGKILL); absence.assert_called_once_with(123)
            self.assertIs(obj.closed, not present)
            self.assertEqual(cmd.events[-1][0:3], ['container', 'ls', '-aq'])

    def test_factory_rejects_selected_source_different_from_compiled_source(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp).resolve(); files = {}
            for name in ('wire.py', 'enclosure.py', 'supervisor.py', 'adapter.py', 'loader.py'):
                body = (PRODUCER / name).read_bytes()
                if name == 'supervisor.py': body += b'\n# different selected implementation\n'
                (package / name).write_bytes(body)
                files[name] = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
            manifest = json.dumps({'schema': 'N061_NATIVE_STATE_SOURCE_V1', 'files': files}).encode()
            (package / 'SOURCE_MANIFEST.json').write_bytes(manifest)
            with self.assertRaisesRegex(ValueError, 'exact already-compiled'):
                loader.make_host('/generated/installed', INHERITED, ('/generated/private',),
                                 {'path': '/generated/method.py', 'bytes': 1, 'sha256': 'a' * 64},
                                 '/generated/scratch', request(), '/generated/docker', 'unix:///generated/socket',
                                 Owner(), package, {'bytes': len(manifest), 'sha256': hashlib.sha256(manifest).hexdigest()})

    def test_request_setup_and_cleanup_errors_preserve_original_and_failed_state(self):
        original = ValueError('generated selector register failure')
        cleanup = RuntimeError('generated selector close failure')
        class Selector:
            def register(self, *args): raise original
            def close(self): raise cleanup
        owner = Owner(); command = supervisor.NativeCommand('/generated/docker', 'unix:///generated/socket', request(), owner)
        obj = supervisor.ParticipantChild(command, '/generated', {}, b'', binding(), owner)
        obj.proc = types.SimpleNamespace(stdin=object(), stdout=object(), stderr=object()); obj.pending = b''
        with patch.object(supervisor.selectors, 'DefaultSelector', Selector):
            with self.assertRaises(BaseExceptionGroup) as caught: obj.request_operation('fit', {'source': ()})
        self.assertEqual(caught.exception.exceptions, (original, cleanup)); self.assertIs(obj.failed, original)
        self.assertEqual(obj.sequence, 0)
        with self.assertRaises(ValueError): obj.request_operation('fit', {'source': ()})
        for where in ('reservation', 'selector'):
            obj = supervisor.ParticipantChild(command, '/generated', {}, b'', binding(), owner)
            obj.proc = types.SimpleNamespace(stdin=object(), stdout=object(), stderr=object()); obj.pending = b''
            error = RuntimeError('generated ' + where)
            target = owner if where == 'reservation' else supervisor.selectors
            attr = 'reserve' if where == 'reservation' else 'DefaultSelector'
            with patch.object(target, attr, side_effect=error), self.assertRaises(RuntimeError):
                obj.request_operation('fit', {'source': ()})
            self.assertIs(obj.failed, error)

    def test_isolated_loader_preserves_deferred_dataclass_state_and_cleans_failure(self):
        code = ('from __future__ import annotations\nfrom dataclasses import dataclass\n'
                '@dataclass\nclass State:\n    coefficient: float\n'
                '    def __reduce__(self): raise AssertionError("no serialization")\n'
                'def fit(payload): return State(1.0)\ndef infer(payload, state): return []\n')
        class Generated(importlib.abc.Loader):
            def create_module(self, spec): return None
            def exec_module(self, module): exec(compile(code, '<generated-method>', 'exec'), module.__dict__)
        name = 'n061_participant_method'; spec = importlib.util.spec_from_loader(name, Generated())
        try:
            with patch.object(importlib.util, 'spec_from_file_location', return_value=spec):
                method = child.load_participant(wire)
            self.assertIs(sys.modules[name], method)
            state = method.fit({}); self.assertEqual(state.coefficient, 1.0)
            with self.assertRaises(AssertionError): state.__reduce__()
        finally: sys.modules.pop(name, None)
        class Broken(Generated):
            def exec_module(self, module): raise ValueError('generated module execution failure')
        spec = importlib.util.spec_from_loader(name, Broken())
        with patch.object(importlib.util, 'spec_from_file_location', return_value=spec), self.assertRaises(ValueError):
            child.load_participant(wire)
        self.assertNotIn(name, sys.modules)


if __name__ == '__main__':
    result = unittest.main(verbosity=2, exit=False)
    used = resource.getrusage(resource.RUSAGE_SELF)
    rss = used.ru_maxrss if sys.platform == 'darwin' else used.ru_maxrss * 1024
    print(json.dumps({'max_rss_bytes': rss, 'user_cpu_seconds': used.ru_utime,
                      'system_cpu_seconds': used.ru_stime, 'native_calls': 0,
                      'authentic_inputs': 0, 'model_runs': 0}))
    if rss > 128 * 1024 * 1024:
        raise RuntimeError('Observed source-control RSS exceeded lane allocation')
    raise SystemExit(not result.result.wasSuccessful())
