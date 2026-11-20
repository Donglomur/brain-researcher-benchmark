"""Public CLI generated-fixture controls; no native or scientific qualification.

Real entry path/descriptor/source/dispatch code runs in copied function namespaces.
Only scientific material generation and overlay copying are injected boundaries.
The real retained material/deployment/runtime metadata validators remain in use.
Generated qualification JSON is deliberately insufficient for native execution.
The separate retained-grade control is not a usable public grading route.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WRITTEN = 0
WRITE_LIMIT = 1024 * 1024
GUARD_ACTIVE = True
ARTIFACT_ROOT = None


def no_native(event, args):
    if not GUARD_ACTIVE:
        return
    if event in {'subprocess.Popen', 'os.fork', 'os.forkpty', 'os.exec',
                 'os.posix_spawn', 'os.system', 'os.kill', 'os.killpg',
                 'socket.connect', 'socket.bind', 'socket.getaddrinfo', 'resource.setrlimit'}:
        raise AssertionError('native/network operation forbidden in generated controls: ' + event)
    if event == 'import' and args[0].split('.')[0] in {
            'numpy', 'torch', 'h5py', 'scipy', 'sklearn', 'pandas', 'pynwb', 'hdmf'}:
        raise AssertionError('scientific import forbidden in generated controls')


sys.addaudithook(no_native)


def charge(data):
    global WRITTEN
    WRITTEN += len(data)
    if WRITTEN > WRITE_LIMIT:
        raise AssertionError('cumulative fixture writes exceed cap, including rewrites/deletions')


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def pin(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def put(path, value):
    data = value if type(value) is bytes else encoded(value)
    charge(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.chmod(0o600)
    path.write_bytes(data)
    return {'path': str(path), **pin(data)}


def need(value, message):
    if not value:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ENTRY = load('_public_entry_generated', HERE / 'run_full_panel.py')
FACADE = load('_public_entry_retained_facade', HERE / 'full_panel_episode.py')
OWNER_COMMON = load('_public_entry_retained_common', HERE.parent / 'aggregate-owner-v1' / 'common.py')
OWNER_OVERLAY = load('_public_entry_owner_overlay', HERE / 'owner_overlay.py')
GRADE = load('_public_entry_bounded_grade', HERE / 'grade-bound' / 'grade_bound.py')
GRADE_CHILD = load('_public_entry_grade_child', HERE / 'grade-bound' / 'grade_child.py')
GUARD_ACTIVE = False


def set_guard(active):
    global GUARD_ACTIVE
    GUARD_ACTIVE = active


def artifact_root():
    global ARTIFACT_ROOT
    if ARTIFACT_ROOT is None:
        selected = os.environ.get('ARTIFACT_DIR')
        need(selected is not None, 'fresh external ARTIFACT_DIR is required')
        path = Path(selected)
        need(path.is_absolute() and path == path.resolve() and not path.exists()
             and path.parent.is_dir(), 'ARTIFACT_DIR must be canonical, fresh, with existing parent')
        need(not path.is_relative_to(HERE.parents[4])
             and not any((p / '.git').exists() for p in (path.parent, *path.parent.parents)),
             'ARTIFACT_DIR must be outside the repository')
        path.mkdir(mode=0o700)
        ARTIFACT_ROOT = path
    return ARTIFACT_ROOT


def copied_namespace(module, **overrides):
    namespace = vars(module).copy()
    for name, value in list(namespace.items()):
        if isinstance(value, types.FunctionType) and value.__module__ == module.__name__:
            clone = types.FunctionType(value.__code__, namespace, value.__name__,
                                       value.__defaults__, value.__closure__)
            clone.__kwdefaults__ = value.__kwdefaults__
            namespace[name] = clone
    namespace.update(overrides)
    return namespace


def retained_functions(names, namespace):
    path = HERE.parent / 'aggregate-owner-v1' / 'runner.py'
    tree = ast.parse(path.read_bytes(), filename=str(path))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    need({n.name for n in nodes} == set(names), 'retained function selection')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


class ExecStopped(RuntimeError):
    pass


class OSBoundary:
    def __init__(self, dispatch):
        self.dispatch = dispatch

    def __getattr__(self, name):
        if name == 'execv':
            return self.dispatch
        return getattr(os, name)


class Fixture:
    """Tiny public source tree: injected scientific I/O is explicitly unqualified."""
    def __init__(self, directory):
        self.top = Path(directory).resolve()
        self.repo = self.top / 'repository'
        self.repo.mkdir()
        self.inputs = self.top / 'inputs'
        self.inputs.mkdir()
        self.events = []
        self.dispatched = []
        self.ns = copied_namespace(ENTRY)
        self.ns['os'] = OSBoundary(self.dispatch)
        self.source = self.repo / ENTRY.COMPONENT_REL
        self.source.mkdir(parents=True)
        generated = {name: ('# generated source fixture ' + name + '\n').encode() for name in ENTRY.STATIC}
        generated['task.json'] = encoded({'generated_task': True})
        generated['policy.json'] = encoded({'generated_policy': True})
        generated['RUNTIME_BINDING.json'] = encoded({'generated_binding': True})
        self.ns['STATIC'] = {name: (len(data), pin(data)['sha256']) for name, data in generated.items()}
        for name, data in generated.items():
            put(self.source / name, data)
        self.retained = {'schema': 'smc_aggregate_owner_source_v1',
                         'files': {'runner.py': pin(b'# generated retained runner identity\n'),
                                   'legacy.py': pin(b'# replaced adapter\n')}}
        owner_source = put(self.repo / ENTRY.OWNER_REL / 'SOURCE.json', self.retained)
        self.ns['OWNER_SOURCE'] = {k: owner_source[k] for k in ('bytes', 'sha256')}
        self.request = {'schema': ENTRY.PREPARE_SCHEMA, 'methods': {},
                        'output': str(self.top / 'prepared'), 'max_component_bytes': 32768,
                        'max_overlay_bytes': 32768}
        self.request['pair'] = put(self.inputs / 'pair.json', {'generated_pair': True})
        qualification = put(self.inputs / 'qualification.json', {'generated_unqualified_metadata': True})
        selected = {'image': 'sha256:' + 'a' * 64, 'docker_binary': str(self.inputs / 'docker'),
                    'docker_socket': str(self.inputs / 'socket'),
                    'boot_id': '11111111-1111-1111-1111-111111111111', 'pid_limit': 64,
                    'qualification': qualification, 'resource_policy': 'measured_caps_and_oom_kill_v1',
                    'cgroup_driver': 'cgroupfs',
                    'delegation': {'path': str(self.inputs / 'cgroup' / 'child'),
                        'mount_point': str(self.inputs / 'cgroup'), 'mount_root': '/', 'fs_type': 'cgroup2',
                        'st_dev': 1, 'st_ino': 2, 'uid': 0, 'mount_id': 3}}
        material = {'schema': 'smc_full_panel_material_binding_v1', 'state': 'selected',
                    'task_sha256': pin(generated['task.json'])['sha256'],
                    'policy_sha256': pin(generated['policy.json'])['sha256'],
                    'new_pair': {k: self.request['pair'][k] for k in ('bytes', 'sha256')}, 'missing': []}
        self.request['material_binding'] = put(self.inputs / 'material.json', material)
        self.request['deployment_binding'] = put(self.inputs / 'deployment.json', {
            'schema': 'smc_aggregate_deployment_binding_v1', 'state': 'selected', 'selected': selected, 'missing': []})
        self.runtime = {'schema': 'smc_aggregate_runtime_v1',
            **{k: selected[k] for k in ('image', 'docker_binary', 'docker_socket', 'qualification')},
            'source_read_bytes': 4096, 'host_write_bytes': 4096}
        self.request['runtime'] = put(self.inputs / 'runtime.json', self.runtime)
        for condition in ENTRY.CONDITIONS:
            self.request['methods'][condition] = put(self.inputs / (condition + '.json'), {'generated_method': condition})
        self.request_ref = put(self.inputs / 'request.json', self.request)
        original_publish = self.ns['publish']

        def counted_publish(filename, value):
            charge(value if type(value) is bytes else self.ns['encoded'](value))
            return original_publish(filename, value)

        self.ns['publish'] = counted_publish
        self.ns['episode'] = lambda repo, component: self.facade(component)

        def scientific_module(name, filename, expected):
            self.ns['body'](filename, expected)  # The source identity check remains real.
            need(name == '_smc_public_overlay', 'only overlay-copy boundary injected')
            return types.SimpleNamespace(build_overlay=self.overlay)

        self.ns['module'] = scientific_module

    def dispatch(self, executable, command):
        self.dispatched.append((executable, command))
        marker = Path(self.request['output']) / 'EXECUTE_STARTED.json'
        self.events.append(('exec_boundary', marker.exists()))
        raise ExecStopped('external exec boundary stopped; closure unknown')

    def facade(self, component):
        fixture = self

        class Boundary:
            HERE = component
            TASK_SHA = fixture.ns['fixed']('task.json')['sha256']
            POLICY_SHA = fixture.ns['fixed']('policy.json')['sha256']
            need = staticmethod(need)
            path = staticmethod(Path)
            pin = staticmethod(pin)
            body = staticmethod(lambda path: fixture.ns['body'](path))
            read = staticmethod(lambda path: fixture.ns['decode'](fixture.ns['body'](path)))
            descriptor = staticmethod(lambda row: need(set(row) == {'bytes', 'sha256'} and row['bytes'] > 0,
                                                        'generated selected pin'))
            checked = staticmethod(lambda row: fixture.ns['body'](row['path'], row))
            source_identity = staticmethod(lambda: pin(fixture.ns['body'](component / 'RUNTIME_SOURCE.json')))
            material_binding = FACADE.FullPanelEpisode.material_binding
            deployment_binding = FACADE.FullPanelEpisode.deployment_binding
            runtime_config = FACADE.FullPanelEpisode.runtime_config

            def public_context(self, *args):
                fixture.events.append(('scientific_public_context',))

            def instantiate(self, pair, task, methods, runtime_path, runtime_sha, output):
                fixture.events.append(('scientific_instantiate',))
                output.mkdir()
                put(output / 'PROTOCOL.json', {'pair_path': str(pair), 'task_path': str(task),
                    'source': self.source_identity(), 'outcome': 'improvement',
                    'programs': {c: {'method': methods[c]} for c in ENTRY.CONDITIONS}})

            def admit_protocol(self, filename, digest):
                raw = fixture.ns['body'](filename)
                need(pin(raw)['sha256'] == digest, 'selected generated protocol')
                return fixture.ns['decode'](raw), self.runtime_config(fixture.ns['checked'](fixture.request['runtime']))

        return Boundary()

    def overlay(self, repo, output, max_bytes):
        self.events.append(('overlay_copy_boundary',))
        folder = output / ENTRY.OWNER_REL
        folder.mkdir(parents=True)
        component = Path(self.request['output']) / 'component'
        composition = {'schema': 'smc_full_panel_owner_composition_v1', 'repository_root': str(repo),
            'component_root': str(component), 'component_source': pin(self.ns['body'](component / 'RUNTIME_SOURCE.json')),
            'episode': self.ns['fixed']('full_panel_episode.py'), 'retained_owner_source': self.ns['OWNER_SOURCE']}
        bodies = {'runner.py': b'# generated retained runner identity\n',
                  'legacy.py': self.ns['body'](component / 'owner_legacy.py'),
                  'COMPOSITION.json': encoded(composition)}
        for name, data in bodies.items():
            put(folder / name, data)
        put(folder / 'SOURCE.json', {'schema': 'smc_full_panel_owner_overlay_v1',
            'files': {name: pin(data) for name, data in bodies.items()},
            'retained_owner_source': self.ns['OWNER_SOURCE'], 'component_source': composition['component_source']})
        return {'path': str(folder)}

    def prepare(self):
        return self.ns['prepare'](self.request_ref['path'], self.request_ref['sha256'], repository_root=self.repo)

    def replace_input(self, key, value):
        self.request[key] = put(Path(self.request[key]['path']), value)
        self.request_ref = put(self.inputs / 'request.json', self.request)


class PublicEntryControls(unittest.TestCase):
    def setUp(self):
        set_guard(True)
        self.addCleanup(set_guard, False)
        self.temp = tempfile.TemporaryDirectory(prefix='smc-public-entry-fixture-', dir=artifact_root())
        self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name)

    def execute(self, prepared):
        return self.f.ns['execute'](prepared['path'], prepared['sha256'], 131072, 131072,
                                    repository_root=self.f.repo)

    def test_authenticated_prepare_has_no_creator_or_invocation(self):
        selected = self.f.prepare()
        record = self.f.ns['inspect_prepared'](selected['path'], selected['sha256'], repository_root=self.f.repo)
        self.assertEqual(self.f.dispatched, [])
        self.assertFalse(any(Path(self.temp.name).rglob('INVOCATION.json')))
        self.assertFalse((Path(record['root']) / 'EXECUTE_STARTED.json').exists())
        for key in ('preparation_launched_processes', 'native_execution_performed',
                    'runtime_qualified_by_preparation', 'private_target_accessed'):
            self.assertIs(record[key], False)
        self.assertIn(('scientific_instantiate',), self.f.events)

    def test_request_and_selected_input_tamper_precede_output_creation(self):
        for field in ('request', 'runtime'):
            with self.subTest(field=field):
                ref = self.f.request_ref if field == 'request' else self.f.request[field]
                old = Path(ref['path']).read_bytes()
                put(Path(ref['path']), old + b' ')
                with self.assertRaises(ValueError):
                    self.f.prepare()
                self.assertFalse(Path(self.f.request['output']).exists())
                self.assertEqual(self.f.events, [])
                put(Path(ref['path']), old)

    def test_real_retained_placeholders_refuse_before_scientific_release(self):
        material = json.loads(Path(self.f.request['material_binding']['path']).read_bytes())
        material.update(state='unavailable', new_pair=None, missing=['fresh export'])
        self.f.replace_input('material_binding', material)
        with self.assertRaisesRegex(ValueError, 'unresolved_material_binding'):
            self.f.prepare()
        self.assertEqual(self.f.events, [])
        self.assertFalse((Path(self.f.request['output']) / 'PREPARED.json').exists())

    def test_real_retained_deployment_placeholder_refuses_even_with_claimed_flags(self):
        shipped = json.loads((HERE / 'DEPLOYMENT_BINDING.json').read_bytes())
        self.f.replace_input('deployment_binding', shipped)
        with self.assertRaisesRegex(ValueError, 'unresolved_deployment_binding'):
            self.f.prepare()
        self.assertEqual(self.f.events, [])

    def test_symlink_and_duplicate_metadata_refuse(self):
        alias = self.f.inputs / 'alias.json'
        alias.symlink_to(self.f.request['runtime']['path'])
        with self.assertRaises(ValueError):
            self.f.ns['body'](alias)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.f.ns['decode'](b'{"selected":true,"selected":false}')

    def test_dispatch_marker_precedes_exec_and_survives_unknown_failure(self):
        prepared = self.f.prepare()
        command = self.f.ns['execution_command'](prepared['path'], prepared['sha256'], 131072, 131072,
                                                 repository_root=self.f.repo)
        self.assertEqual(command[:4], [sys.executable, '-I', '-B',
                         json.loads(Path(prepared['path']).read_bytes())['owner_entry']['path']])
        self.assertEqual(command[4], 'execute')
        with self.assertRaises(ExecStopped):
            self.execute(prepared)
        marker = json.loads((Path(self.f.request['output']) / 'EXECUTE_STARTED.json').read_bytes())
        self.assertTrue(marker['dispatch_possible'])
        self.assertFalse(marker['creator_closure_established'])
        self.assertFalse(marker['failure_or_missing_receipt_proves_closure'])
        self.assertEqual(marker['argv'], command)
        self.assertEqual(self.f.events[-1], ('exec_boundary', True))
        with self.assertRaisesRegex(ValueError, 'single use'):
            self.execute(prepared)
        self.assertEqual(len(self.f.dispatched), 1)
        self.assertFalse((Path(self.f.request['output']) / 'owner' / 'RESULT.json').exists())

    def test_prepared_runtime_and_source_tamper_refuse_before_dispatch(self):
        prepared = self.f.prepare()
        root = Path(self.f.request['output'])
        for changed in (Path(prepared['path']), Path(self.f.request['runtime']['path']),
                        root / 'component' / 'full_panel_episode.py', root / 'overlay' / ENTRY.OWNER_REL / 'runner.py'):
            with self.subTest(path=changed.name):
                before = changed.read_bytes()
                put(changed, before + b' ')
                with self.assertRaises(ValueError):
                    self.execute(prepared)
                self.assertEqual(self.f.dispatched, [])
                self.assertFalse((root / 'EXECUTE_STARTED.json').exists())
                put(changed, before)

    def test_rehashed_prepared_claim_cannot_grant_runtime_qualification(self):
        prepared = self.f.prepare()
        value = json.loads(Path(prepared['path']).read_bytes())
        value['runtime_qualified_by_preparation'] = True
        changed = put(Path(prepared['path']), value)
        with self.assertRaisesRegex(ValueError, 'cannot assert'):
            self.execute(changed)
        self.assertEqual(self.f.dispatched, [])

    def test_public_grade_routes_through_selected_bound_helper_without_exec_fallback(self):
        prepared = self.f.prepare()
        record = self.f.ns['inspect_prepared'](prepared['path'], prepared['sha256'], repository_root=self.f.repo)
        result = put(Path(record['owner_root']) / 'RESULT.json', {'generated_owner_result': True})
        runtime = put(self.f.inputs / 'grade-runtime.json', {'generated_runtime_boundary': True})
        calls = []
        sentinel = {'generated_bounded_invocation': True}
        def build(selected, *args, **kwargs):
            self.assertEqual(selected, record)
            self.assertEqual(kwargs['expected_source'], self.f.facade(Path(record['root']) / 'component').source_identity())
            self.assertEqual(kwargs['expected_image_id'], self.f.runtime['image'])
            self.assertEqual(Path(args[0]), Path(runtime['path']))
            self.assertEqual(args[1], runtime['sha256'])
            calls.append('bound_admission')
            return sentinel
        def run(invocation):
            self.assertIs(invocation, sentinel)
            calls.append('bounded_owner_boundary')
            return {'success': False, 'status': 'closure_unknown', 'generated_fixture': True}
        helper = types.SimpleNamespace(build_invocation=build, run_grade=run)
        self.f.ns['grade_module'] = lambda repo: helper
        report = self.f.top / 'grade-work' / 'report' / 'REPORT.json'
        result_value = self.f.ns['protected_grade'](prepared['path'], prepared['sha256'], result['sha256'],
            self.f.inputs / 'unread-target.h5', self.f.inputs / 'unread-evaluator.py', report, 4096,
            grade_runtime_path=runtime['path'], grade_runtime_sha256=runtime['sha256'], repository_root=self.f.repo)
        self.assertEqual(calls, ['bound_admission', 'bounded_owner_boundary'])
        self.assertEqual(result_value['status'], 'closure_unknown')
        self.assertEqual(self.f.dispatched, [])
        self.assertFalse(report.exists())

    def test_changed_fixed_grade_helper_refuses_before_module_or_private_boundary(self):
        root = self.f.source / 'grade-bound'
        files = {}
        for name in ENTRY.GRADE_FILES:
            row = put(root / name, ('# generated authenticated helper ' + name + '\n').encode())
            files[name] = {k: row[k] for k in ('bytes', 'sha256')}
        source = put(root / 'SOURCE.json', {'schema': 'smc_full_panel_grade_sources_v1', 'files': files})
        self.f.ns['GRADE_SOURCE'] = {k: source[k] for k in ('bytes', 'sha256')}
        self.f.ns['module'] = lambda *a: self.fail('changed helper reached code loading')
        changed = root / 'grade_child.py'
        put(changed, changed.read_bytes() + b'# altered\n')
        with self.assertRaises(ValueError):
            self.f.ns['grade_module'](self.f.repo)
        self.assertEqual(self.f.dispatched, [])

    def test_retained_invocation_qualifies_before_any_live_host_or_creation(self):
        calls = []
        def qualify(runtime, source):
            calls.append('qualification')
            raise ValueError('generated runtime is not qualified')
        L = types.SimpleNamespace(admit_protocol=lambda *a: ({'source': pin(b'fixture')}, {}), qualify=qualify)
        ns = retained_functions({'make_invocation'}, {'Path': Path, 'need': need,
            'legacy': types.SimpleNamespace(load=lambda: L, source_identity=lambda: pin(b'owner')),
            'ordinary': Path, 'production_host': lambda: self.fail('live host before qualification')})
        with self.assertRaisesRegex(ValueError, 'not qualified'):
            ns['make_invocation'](self.f.inputs / 'protocol', 'a' * 64,
                                  self.f.top / 'execution', self.f.top / 'owner', 131072, 131072)
        self.assertEqual(calls, ['qualification'])
        self.assertFalse((self.f.top / 'owner').exists())


class RetainedGradeFixture:
    """Generated observations exercise real proof joins and real exclusive lock.

    Native observations, scientific panel admission and numerical scoring are
    synthetic boundaries. Passing these controls is not native qualification.
    """
    def __init__(self, directory, owner_source=None):
        top = Path(directory).resolve()
        self.root, self.owner, public, protocols, self.reports = [top / x for x in
            ('execution', 'owner', 'public', 'protocols', 'reports')]
        for folder in (self.root, self.owner, public, protocols, self.reports):
            folder.mkdir()
        self.calls = []
        L = FACADE.FullPanelEpisode.__new__(FACADE.FullPanelEpisode)
        self.L = L
        L.need, L.path, L.pin = need, Path, pin
        L.encoded = L.request_bytes = OWNER_COMMON.encoded
        L.body = lambda path, *a: Path(path).read_bytes()

        def read(path, expected=None):
            raw = Path(path).read_bytes()
            if expected is not None:
                need(pin(raw) == expected if type(expected) is dict else pin(raw)['sha256'] == expected,
                     'generated saved metadata identity changed')
            return json.loads(raw)

        self.read = L.read = read
        def publish(path, value, mode=0o400):
            raw = value if type(value) is bytes else encoded(value)
            charge(raw)
            with Path(path).open('xb') as stream:
                stream.write(raw)
            return pin(raw)
        L.publish = publish
        L.TASK_SHA = 'e' * 64
        L.material_binding = lambda: {'new_pair': pin(b'generated-pair')}
        deployment = {'pid_limit': 64, 'binding_pin': pin(b'generated-deployment')}
        L.deployment_binding = lambda: deployment
        runtime = {'qualification': {'path': str(public / 'qualification.json'), **pin(b'not-native-proof')},
                   'image': 'sha256:' + '7' * 64, 'deployment': deployment,
                   'source_read_bytes': 1048576, 'host_write_bytes': 1048576}
        protocol = {'source': pin(b'generated-episode-source'), 'outcome': 'improvement',
                    'pair_path': str(public / 'pair.json'), 'task_path': str(public / 'task.json'),
                    'programs': {c: {'program': pin(b'program'), 'declaration': pin(b'plan'),
                        'method': {'path': str(protocols / (c + '.method.json')), 'sha256': 'c' * 64}}
                                for c in FACADE.CONDITIONS}}
        protocol_path = protocols / 'PROTOCOL.json'
        protocol_ref = put(protocol_path, protocol)
        self.protocol_ref = protocol_ref
        L._protocol, L._protocol_path, L._captured_actual = protocol, protocol_path, {}
        L.admit_protocol = lambda path, expected: (read(path, expected), runtime)
        L.public_context = lambda *a: ({}, {})  # Generated panel boundary, never array admission.
        L.validate_closed = lambda request, receipt: need(receipt['all_native_resources_closed'] is True,
                                                        'generated external native observation absent')
        L.mounts_for = lambda *a: {'generated-view': 'identity'}
        L.mount_identity = lambda value: value
        def score(*args, **kwargs):
            self.calls.append('numerical_boundary')
            if getattr(self, 'fail_numeric', False):
                raise ValueError('generated numerical failure')
            return {'generated_measurement': 0, 'native_qualification': False}
        L.api = types.SimpleNamespace(hash_file=lambda path, *a: pin(Path(path).read_bytes())['sha256'])
        L.benchmark = lambda: types.SimpleNamespace(hash_file=L.api.hash_file, score=score)
        source = owner_source if owner_source is not None else pin(b'generated-owner-source')
        invocation = {'output': str(self.root), 'owner': str(self.owner), 'protocol_path': str(protocol_path),
            'protocol_pin': {k: protocol_ref[k] for k in ('bytes', 'sha256')}, 'source': source,
            'deployment_pin': deployment['binding_pin'],
            'clock': {'origin': 1.0, 'deadline': 22561.0, 'controller_deadline': 22501.0,
                      'outcome': 'improvement', 'clock_identity': 'generated-not-native'}}
        invocation_ref = put(self.owner / 'INVOCATION.json', invocation)
        ip = {k: invocation_ref[k] for k in ('bytes', 'sha256')}
        clock = invocation['clock']
        def save(path, value):
            row = put(path, value if type(value) is bytes else OWNER_COMMON.encoded(value))
            return {k: row[k] for k in ('bytes', 'sha256')}
        controller = {'source': source, 'invocation_pin': ip, 'clock': clock,
            'future_controller_and_acknowledged_cli_release_closed': True,
            'controller_group': {'absence_verified': True},
            'acknowledged_cli': {'all_acknowledged_cli_absent': True}}
        controller_pin = save(self.owner / 'CONTROLLER_CLOSED.json', controller)
        pair = {'schema': L.CLOSED_SCHEMA, 'route': L.ROUTE,
            'both_conditions_closed_before_private_grade': True, 'private_target_accessed': False,
            'protocol_path': str(protocol_path), 'protocol_sha256': protocol_ref['sha256'],
            'source': protocol['source'], 'outcome': 'improvement', 'runtime_qualification': runtime['qualification'],
            'owner_invocation_pin': ip, 'owner_source': source, 'conditions': {}}
        natural, closed_scopes, phases = {}, {}, {}
        for index, condition in enumerate(FACADE.CONDITIONS):
            job = self.root / 'jobs' / condition
            quarantine = self.root / 'quarantine' / condition
            programme = protocol['programs'][condition]
            bodies = {'offline.h5': b'generated-byte-prediction', 'actual_declaration.json': encoded({'actual': True}),
                'OUTPUTS.json': encoded({}), 'RESULT.json': encoded({
                    'schema': 'smc_full_panel_program_result_v1', 'inference_condition_id': FACADE.INFERENCE_CONDITION,
                    'outcome': 'improvement', 'condition': condition,
                    'program_sha256': programme['program']['sha256'],
                    'declaration_sha256': programme['declaration']['sha256'],
                    'method_freeze_sha256': programme['method']['sha256'], 'submission_keys': ['offline']})}
            for name, data in bodies.items():
                put(quarantine / name, data)
            exposure = {'mounts': {'generated-view': 'identity'}, 'source': protocol['source'],
                'image': runtime['image'], 'role': 'A' if index == 0 else 'B', 'command': L.COMMAND,
                'boundary_audit': {k: runtime['qualification'][k] for k in ('bytes', 'sha256')}}
            exposure_pin = save(job / 'EXPOSURE.json', exposure)
            save(job / 'EXECUTION.json', L.job_for(protocol, condition))
            request = {'schema': L.REQUEST_SCHEMA, 'phase_id': condition, 'role': exposure['role'],
                'image': runtime['image'], 'source': protocol['source'], 'command': L.COMMAND,
                'workdir': '/work', 'action': 'held_attempt', 'resources': L.resources('improvement', runtime),
                'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}, 'exposure': exposure_pin,
                'aggregate': {'phase_id': condition, 'deployment_pin': deployment['binding_pin'], 'invocation_pin': ip}}
            request_pin = save(job / 'REQUEST.json', request)
            ownership_pin = pin(encoded({'generated_provider_owner': condition}))
            receipt = {'quarantine_root': str(quarantine), 'exposure': exposure_pin,
                'input_before': exposure['mounts'], 'input_after': exposure['mounts'],
                'output_inventory': {'complete': True, 'files': {name: pin(data) for name, data in bodies.items()}},
                'request_sha256': request_pin['sha256'], 'ownership_pin': ownership_pin,
                'all_native_resources_closed': True}
            receipt_path = self.root / 'control' / condition / 'RECEIPT.json'
            receipt_pin = save(receipt_path, receipt)
            freeze_path = self.root / 'freezes' / (condition + '.json')
            freeze_pin = save(freeze_path, {'condition': condition, 'outcome': 'improvement',
                'submissions': {'offline': {'path': str(quarantine / 'offline.h5'),
                                           'sha256': pin(bodies['offline.h5'])['sha256']}}})
            pair['conditions'][condition] = {'receipt_path': str(receipt_path), 'receipt': receipt_pin,
                'freeze_path': str(freeze_path), 'freeze': freeze_pin, 'request': request_pin}
            owner = {'source': source, 'invocation_pin': ip, 'clock': clock, 'request_pin': request_pin,
                     'plan': request['aggregate'], 'limits': request['resources']}
            owner_pin = save(self.owner / ('CGROUP-' + condition + '-OWNER.json'), owner)
            producer = {'source': source, 'invocation_pin': ip, 'clock': clock, 'request_pin': request_pin,
                        'owner_pin': owner_pin, 'event': {'container_id': 'c' * 64}}
            save(self.owner / ('CGROUP-' + condition + '-ATTACHED.json'), producer)
            counters = {'cpu_usage_usec': 1000, 'cpu_stat': {'usage_usec': 1000}, 'memory_peak_bytes': 1024,
                'memory_events': {'low': 0, 'high': 0, 'max': 0, 'oom': 0, 'oom_kill': 0},
                'pids_events': {'max': 0}, 'cgroup_events_before': {'populated': 0}, 'cgroup_events': {'populated': 0}}
            for label, destination in (('FINISHED', natural), ('CLOSED', closed_scopes)):
                proof = {'schema': 'smc_aggregate_scope_receipt_v1', 'phase_id': condition,
                    **owner, 'owner_pin': owner_pin, 'producer': producer, 'counters': counters,
                    'empty': True, 'within_limits': True, 'complete': True, 'errors': [],
                    'zero_cpu_overshoot_claim': False, 'resource_policy': 'measured_caps_and_oom_kill_v1'}
                proof_pin = save(self.owner / ('CGROUP-' + condition + '-' + label + '.json'), proof)
                destination[condition] = {**proof, 'receipt_pin': proof_pin}
            phases[condition] = {'request_pin': request_pin, 'ownership_pin': ownership_pin,
                'receipt_pin': receipt_pin, 'receipt_path': str(receipt_path),
                'all_resources_closed': True, 'producer_container_id': 'c' * 64}
        provider = {'schema': 'smc_aggregate_provider_closure_v1', 'invocation_pin': ip, 'source': source,
                    'clock': clock, 'controller_closure_pin': controller_pin, 'phases': phases, 'recovery_cli_absent': True}
        provider_pin = save(self.owner / 'PROVIDER_CLOSED.json', provider)
        close_pin = save(self.owner / 'AGGREGATE_CLOSED.json', {'schema': 'smc_aggregate_closed_v1',
            'invocation_pin': ip, 'source': source, 'clock': clock, 'controller_closure_pin': controller_pin,
            'value': {'controller_closure_pin': controller_pin, 'scopes': closed_scopes,
                      'complete': True, 'all_scopes_empty': True, 'counters_complete': True, 'within_limits': True}})
        remove_pin = save(self.owner / 'AGGREGATE_REMOVED.json', {'schema': 'smc_aggregate_removed_v1',
            'invocation_pin': ip, 'source': source, 'clock': clock, 'provider_closure_pin': provider_pin,
            'value': {'provider_closure_pin': provider_pin, 'scopes': {c: True for c in FACADE.CONDITIONS},
                      'complete': True, 'all_scopes_removed': True}})
        pair_pin = save(self.root / 'PAIR_CLOSED.json', pair)
        self.result_pin = save(self.owner / 'RESULT.json', {'status': 'closed_pair', 'error': None,
            'recovery_error': None, 'cleanup_errors': [], 'source': source, 'invocation_pin': ip,
            'controller_closure_pin': controller_pin, 'pair_closed_pin': pair_pin,
            'recovery_cli': {'all_acknowledged_cli_absent': True}, 'controller_execution': {'natural_exit': True},
            'aggregate': {'close_pin': close_pin, 'remove_pin': remove_pin,
                          'provider_closure_pin': provider_pin, 'phase_proofs': natural}})
        self.ns = retained_functions({'grade', 'validate_aggregate_completion'}, {
            'Path': Path, 'ordinary': ENTRY.path, 'body': L.body, 'read': read, 'need': need,
            'encoded': OWNER_COMMON.encoded, 'pin': pin, 'CONDITIONS': FACADE.CONDITIONS,
            'legacy': types.SimpleNamespace(source_identity=lambda: source, load=lambda: L)})

    def grade(self, filename='report.json'):
        return self.ns['grade'](self.owner, self.result_pin['sha256'], self.reports / 'unread-target.h5',
                               self.reports / 'unread-evaluator.py', self.reports / filename, 4096)


class RetainedGradeBoundaryControls(unittest.TestCase):
    def setUp(self):
        set_guard(True)
        self.addCleanup(set_guard, False)
        self.temp = tempfile.TemporaryDirectory(prefix='smc-public-grade-source-fixture-', dir=artifact_root())
        self.addCleanup(self.temp.cleanup)
        self.f = RetainedGradeFixture(self.temp.name)

    def test_real_owner_validation_reaches_real_lock_once(self):
        result = self.f.grade()
        self.assertEqual(len(self.f.calls), 2)
        self.assertFalse(result['AI_attribution_verified'])
        self.assertTrue((self.f.root / 'GRADE_STARTED.json').is_file())
        with self.assertRaises(FileExistsError):
            self.f.grade('second-report.json')
        self.assertEqual(len(self.f.calls), 2)

    def test_changed_parent_proof_refuses_before_private_lock_or_numerics(self):
        proof = self.f.owner / ('CGROUP-' + FACADE.CONDITIONS[0] + '-FINISHED.json')
        put(proof, proof.read_bytes() + b' ')
        with self.assertRaises(ValueError):
            self.f.grade()
        self.assertEqual(self.f.calls, [])
        self.assertFalse((self.f.root / 'GRADE_STARTED.json').exists())

    def test_numerical_failure_retains_real_grade_lock(self):
        self.f.fail_numeric = True
        with self.assertRaisesRegex(ValueError, 'numerical failure'):
            self.f.grade()
        self.assertTrue((self.f.root / 'GRADE_STARTED.json').is_file())
        with self.assertRaises(FileExistsError):
            self.f.grade('retry-report.json')
        self.assertEqual(self.f.calls, ['numerical_boundary'])


class BoundedGradeControls(unittest.TestCase):
    def setUp(self):
        set_guard(True)
        self.addCleanup(set_guard, False)
        self.g = copied_namespace(GRADE)

    def actor(self):
        readonly = ['/generated/smc-bound/grade_child.py', '/generated/smc-bound/target.h5',
                    '/generated/smc-bound/evaluator.py']
        omitted = ('desktop.docker.io/mounts/0/Source', 'desktop.docker.io/mounts/0/SourceKind',
                   'desktop.docker.io/mounts/0/Target', 'desktop.docker.io/mounts/1/Source',
                   'desktop.docker.io/mounts/1/SourceKind', 'desktop.docker.io/mounts/1/Target',
                   'desktop.docker.io/ports.scheme')
        labels = {name: 'generated-metadata' for name in omitted}
        labels['codex.fixture'] = 'selected'
        return {'role': 'grade', 'token': 'a' * 32, 'operation_id': 'smc-public-grade-' + 'a' * 32,
            'image_id': 'sha256:' + 'b' * 64, 'image_labels': labels,
            'container_base_labels': {'codex.fixture': 'selected'}, 'image_environment': [],
            'architecture': 'arm64', 'entrypoint': {'path': readonly[0], **pin(b'child')},
            'arguments': ['--request', '/generated/smc-bound/REQUEST.json'],
            'workdir': '/generated/smc-bound/report', 'scratch_dir': '/tmp',
            'readonly_mounts': [{'source': p, 'destination': p} for p in readonly],
            'writable_mounts': [{'source': '/generated/smc-bound/report', 'destination': '/generated/smc-bound/report'}],
            'uid': 0, 'gid': 0}

    def test_exact_finite_grade_limits_and_no_control_namespace(self):
        actor = self.actor()
        private = [m['source'] for m in actor['readonly_mounts'][1:]]
        built = self.g['build_create'](actor, private)
        argv = built['argv']
        self.assertEqual(built['memory'], 2 * 1024**3)
        self.assertEqual(argv[argv.index('--memory') + 1], '2147483648')
        self.assertEqual(argv[argv.index('--memory-swap') + 1], '2147483648')
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        self.assertEqual(argv[argv.index('--cpus') + 1], '1')
        self.assertIn('cpu=600:605', argv)
        self.assertEqual((GRADE.WORK_SECONDS, GRADE.CLEANUP_SECONDS), (720, 60))
        self.assertNotIn('--privileged', argv)
        self.assertNotIn('--pid', argv)
        self.assertFalse(any('docker.sock' in x or '/sys/fs/cgroup' in x for x in argv))
        actor['role'] = 'control'
        with self.assertRaises(ValueError):
            self.g['build_create'](actor, private)

    def test_altered_bounds_refuse_before_saved_proofs_or_private_files(self):
        names = {'schema', 'prepared', 'runtime', 'runtime_descriptor', 'helper_source',
            'expected_component_source', 'expected_image_id', 'owner_result_sha256', 'private_files',
            'report_path', 'scratch_bytes', 'token', 'gate', 'bounds'}
        base = {name: None for name in names}
        base['schema'] = 'smc_full_panel_bounded_grade_invocation_v1'
        fixed = {'memory_bytes': 2147483648, 'cpu_soft_seconds': 600, 'cpu_hard_seconds': 605,
                 'work_seconds': 720, 'cleanup_seconds': 60, 'threads': 1}
        def forbidden(*args, **kwargs):
            self.fail('changed bounds reached metadata/private admission')
        self.g.update(source_selection=forbidden, checked=forbidden, saved_owner_gate=forbidden)
        for key in fixed:
            with self.subTest(key=key):
                invocation = dict(base, bounds={**fixed, key: fixed[key] + 1})
                with self.assertRaisesRegex(ValueError, 'fixed whole-grader bound'):
                    self.g['validate_invocation'](invocation)

    def closed_call(self):
        return {'pid': 123, 'returncode': 0, 'errors': [],
            'cleanup': {'cleanup_complete': True, 'reaped': True, 'group_absence_observed': True,
                        'error': None, 'pid': 123, 'returncode': 0},
            'capture': {'all_eof_observed': True, 'storage_truncated': False, 'read_ceiling_exhausted': False,
                        'closed_without_eof': False, 'stream_close_errors': []}}

    def test_capture_or_container_uncertainty_cannot_be_success(self):
        complete = self.closed_call()
        self.assertEqual(self.g['completion'](None, {'container_absent': True}, [complete])['status'], 'graded')
        failed = self.g['completion']({'error': 'generated failure'}, {'container_absent': True}, [complete])
        self.assertEqual(failed['status'], 'failed')
        self.assertFalse(failed['success'])
        missing_errors = copy.deepcopy(complete)
        del missing_errors['errors']
        refused = self.g['completion'](None, {'container_absent': True}, [missing_errors])
        self.assertFalse(refused['success'])
        self.assertEqual(refused['status'], 'failed')
        for change in ('eof', 'container', 'cleanup'):
            with self.subTest(change=change):
                call = copy.deepcopy(complete)
                if change == 'eof':
                    call['capture']['all_eof_observed'] = False
                if change == 'cleanup':
                    call['cleanup']['cleanup_complete'] = False
                outcome = self.g['completion'](None, {'container_absent': change != 'container'}, [call])
                self.assertEqual(outcome['status'], 'closure_unknown')
                self.assertFalse(outcome['success'])

    def test_unacknowledged_create_cannot_close_from_missing_name(self):
        owner = types.SimpleNamespace(inspect=lambda *a: None,
                                     cli=lambda *a: self.fail('no cleanup command expected'))
        with self.assertRaisesRegex(ValueError, 'unacknowledged'):
            self.g['cleanup_actor'](owner, None, self.actor(), {'name': 'generated'}, None, True, 1)
        closed = self.g['cleanup_actor'](owner, None, self.actor(), {'name': 'generated'}, 'c' * 64, True, 1)
        self.assertTrue(closed['container_absent'])

    def test_saved_proof_gate_authenticates_overlay_and_refuses_owner_leaf_drift(self):
        temporary = tempfile.TemporaryDirectory(prefix='smc-public-owner-gate-fixture-', dir=artifact_root())
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        # Production build_overlay precharges the entire finite inventory before
        # its create-only writes; it performs no native execution or data access.
        overlay = OWNER_OVERLAY.build_overlay(HERE.parents[4], root / 'overlay',
                                              max_bytes=min(524288, WRITE_LIMIT - WRITTEN))
        charge(bytes(overlay['bytes']))
        proofs = root / 'proofs'
        proofs.mkdir()
        fixture = RetainedGradeFixture(proofs, owner_source=overlay['source'])
        owner_entry = Path(overlay['path']) / 'runner.py'
        component = self.g['reference'](HERE / 'RUNTIME_SOURCE.json')
        prepared = {'component_source': component, 'owner_entry': self.g['reference'](owner_entry),
            'overlay_source': self.g['reference'](owner_entry.parent / 'SOURCE.json'),
            'owner_root': str(fixture.owner), 'execution_root': str(fixture.root),
            'protocol': fixture.protocol_ref}
        component_pin = {k: component[k] for k in ('bytes', 'sha256')}
        gate = self.g['saved_owner_gate'](prepared, fixture.result_pin['sha256'], component_pin)
        self.assertEqual(gate['grade_lock'], str(fixture.root / 'GRADE_STARTED.json'))
        self.assertFalse(Path(gate['grade_lock']).exists())
        self.assertEqual(fixture.calls, [])
        manifest_path = owner_entry.parent / 'SOURCE.json'
        composition_path = owner_entry.parent / 'COMPOSITION.json'
        manifest_raw, composition_raw = manifest_path.read_bytes(), composition_path.read_bytes()
        for mutation in ('schema', 'topkeys', 'component_source', 'composition_retained_source'):
            with self.subTest(rehashed_semantic_mutation=mutation):
                manifest = json.loads(manifest_raw)
                if mutation == 'schema':
                    manifest['schema'] = 'generated_wrong_overlay_schema'
                elif mutation == 'topkeys':
                    manifest['unselected_authority'] = True
                elif mutation == 'component_source':
                    manifest['component_source'] = pin(b'generated replaced component')
                else:
                    composition = json.loads(composition_raw)
                    composition['retained_owner_source'] = pin(b'generated replaced owner source')
                    selected = put(composition_path, composition)
                    manifest['files']['COMPOSITION.json'] = {k: selected[k] for k in ('bytes', 'sha256')}
                prepared['overlay_source'] = put(manifest_path, manifest)
                with self.assertRaisesRegex(ValueError, 'Closed exact source overlay'):
                    self.g['saved_owner_gate'](prepared, fixture.result_pin['sha256'], component_pin)
                self.assertEqual(fixture.calls, [])
                self.assertFalse(Path(gate['grade_lock']).exists())
                put(composition_path, composition_raw)
                prepared['overlay_source'] = put(manifest_path, manifest_raw)
        changed = owner_entry.parent / 'journal.py'
        put(changed, changed.read_bytes() + b'\n# generated owner-leaf drift\n')
        with self.assertRaisesRegex(ValueError, 'owner byte|owner source'):
            self.g['saved_owner_gate'](prepared, fixture.result_pin['sha256'], component_pin)
        self.assertFalse(Path(gate['grade_lock']).exists())
        self.assertEqual(fixture.calls, [])

    def test_child_gate_and_cpu_limit_precede_private_body_reads(self):
        child = copied_namespace(GRADE_CHILD)
        events = []
        cpu = [600, 605]
        child.update(sys=types.SimpleNamespace(platform='linux', executable=GRADE.PYTHON),
                     os=types.SimpleNamespace(geteuid=lambda: 0),
                     resource=types.SimpleNamespace(RLIMIT_CPU=0, getrlimit=lambda _: tuple(cpu)))
        def gate(invocation):
            events.append('saved_proof_gate')
            if invocation.get('refuse'):
                raise ValueError('generated saved proof refusal')
        facade = types.SimpleNamespace(validate_invocation=gate, PYTHON=GRADE.PYTHON,
            checked=lambda *a: self.fail('protected body read before original grader guards'))
        invocation = {'refuse': True, 'prepared': {'owner_entry': {'path': '/generated/runner.py'},
                        'owner_root': '/generated/owner'}, 'owner_result_sha256': 'd' * 64,
            'private_files': {'target': {'path': '/generated/target.h5'}, 'evaluator': {'path': '/generated/evaluator.py'}},
            'report_path': '/generated/report.json', 'scratch_bytes': 4096}
        with self.assertRaisesRegex(ValueError, 'saved proof refusal'):
            child['child_argv'](facade, invocation)
        self.assertEqual(events, ['saved_proof_gate'])
        invocation['refuse'] = False
        cpu[0] = 599
        events.clear()
        with self.assertRaisesRegex(ValueError, 'CPU budget'):
            child['child_argv'](facade, invocation)
        self.assertEqual(events, ['saved_proof_gate'])
        cpu[0] = 600
        events.clear()
        argv = child['child_argv'](facade, invocation)
        self.assertEqual(argv[:5], [GRADE.PYTHON, '-I', '-B', '/generated/runner.py', 'grade'])
        self.assertEqual(events[0], 'saved_proof_gate')
        self.assertEqual(events, ['saved_proof_gate'])


if __name__ == '__main__':
    destination = artifact_root() / 'CONTROL_RESULT.json'
    program = unittest.main(exit=False)
    result = program.result
    receipt = {'schema': 'smc-public-entry-controls/v1', 'testsRun': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'successful': result.wasSuccessful(), 'fixture_write_bytes_before_receipt': WRITTEN,
        'cumulative_generated_fixture_bytes': 0, 'receipt_bytes': 0,
        'includes_rewrites_deleted_files_and_attempted_publications': True,
        'limit_bytes': WRITE_LIMIT, 'native_or_scientific_execution_qualified': False}
    for _ in range(4):
        raw = encoded(receipt)
        receipt['receipt_bytes'] = len(raw)
        receipt['cumulative_generated_fixture_bytes'] = WRITTEN + len(raw)
    raw = encoded(receipt)
    need(len(raw) == receipt['receipt_bytes'], 'stable final receipt counter')
    charge(raw)
    with destination.open('xb') as stream:
        stream.write(raw)
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
