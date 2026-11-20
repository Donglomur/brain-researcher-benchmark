"""Generated source controls: no original arrays, scientific imports or native jobs.

Run directly with a fresh canonical ARTIFACT_DIR outside adapter/runtime/controls
and outside every Git worktree. Numeric scoring and operating-system boundaries
are explicit doubles; production functions execute in copied namespaces only.
"""
import ast
import builtins
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = tuple(ROOT / p for p in ('adapter', 'runtime', 'controls'))
LIMIT = 524288
ARTIFACT_ROOT = None
WRITTEN = 0
ACTIVE = False
MODULES = {}
SOURCES = {}


def audit(event, args):
    if not ACTIVE:
        return
    if event in {'subprocess.Popen', 'os.fork', 'os.forkpty', 'os.exec', 'os.posix_spawn',
                 'os.system', 'os.kill', 'os.killpg', 'resource.setrlimit',
                 'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        raise AssertionError('Native boundary forbidden in generated controls: ' + event)
    if event == 'import' and args[0].split('.')[0] in {
            'numpy', 'scipy', 'sklearn', 'h5py', 'torch', 'pandas', 'pynwb', 'hdmf'}:
        raise AssertionError('Scientific import forbidden in generated controls: ' + args[0])


sys.addaudithook(audit)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def charge(amount):
    global WRITTEN
    WRITTEN += amount
    if WRITTEN > LIMIT:
        raise AssertionError('Cumulative generated fixture ceiling exceeded')


def put(path, value):
    raw = value if isinstance(value, bytes) else encode(value)
    charge(len(raw))  # Rewrites, deleted files and failed writes stay charged.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {'path': str(path), **pin(raw)}


def initialize():
    global ARTIFACT_ROOT
    if ARTIFACT_ROOT is not None:
        return
    value = os.environ.get('ARTIFACT_DIR')
    if not value:
        raise ValueError('ARTIFACT_DIR must name a fresh external directory')
    p = Path(value)
    if not p.is_absolute() or str(p) != value or '..' in p.parts or p.resolve() != p:
        raise ValueError('ARTIFACT_DIR must be canonical and absolute')
    if os.path.lexists(p) or not p.parent.is_dir():
        raise ValueError('ARTIFACT_DIR must be fresh with an existing parent')
    if any(p.is_relative_to(s) or s.is_relative_to(p) for s in SOURCE_DIRS):
        raise ValueError('ARTIFACT_DIR must be disjoint from source directories')
    if any((a / '.git').exists() for a in (p.parent, *p.parent.parents)):
        raise ValueError('ARTIFACT_DIR must be outside every Git worktree')
    p.mkdir(mode=0o700)
    ARTIFACT_ROOT = p


def load(name, relative):
    if name in MODULES:
        return MODULES[name]
    p = ROOT / relative
    raw = p.read_bytes()
    SOURCES[relative] = pin(raw)
    module = types.ModuleType('_generated_historical_' + name)
    module.__file__ = str(p)
    exec(compile(raw, str(p), 'exec'), module.__dict__)
    MODULES[name] = module
    return module


def cloned(module, **changes):
    """No production globals are modified; only explicit boundaries are replaced."""
    ns = dict(module.__dict__)
    for name, value in tuple(ns.items()):
        if isinstance(value, types.FunctionType) and value.__globals__ is module.__dict__:
            f = types.FunctionType(value.__code__, ns, value.__name__, value.__defaults__, value.__closure__)
            f.__kwdefaults__ = value.__kwdefaults__
            ns[name] = f
    ns.update(changes)
    return types.SimpleNamespace(**ns)


class Base(unittest.TestCase):
    def setUp(self):
        global ACTIVE
        initialize()
        ACTIVE = True
        self.addCleanup(self.disable_guard)
        self.root = ARTIFACT_ROOT / self.id().split('.')[-1]
        self.root.mkdir()
        self.a = load('adapter', 'adapter/historical_score.py')
        self.h = load('host', 'runtime/historical_grade.py')
        self.c = load('child', 'adapter/historical_grade_child.py')
        self.labels = load('labels', 'runtime/label_policy.py')

    @staticmethod
    def disable_guard():
        global ACTIVE
        ACTIVE = False

    def fixture(self, name='case'):
        base = self.root / name
        base.mkdir()
        source = base / 'source'
        source.mkdir()
        files = {n: put(source / n, ('generated-' + n).encode())
                 for n in sorted(self.a.SOURCE_FILES)}
        manifest = {'schema': 'smc_historical_reference_grade_source_v1',
                    'files': {n: {k: row[k] for k in ('bytes', 'sha256')} for n, row in files.items()}}
        source_row = put(source / 'SOURCE.json', manifest)
        predictions = {arm: put(base / (arm + '.h5'), ('generated-' + arm + '-prediction').encode())
                       for arm in self.a.ARMS}
        target = put(base / 'target.h5', b'generated-target-private')
        evaluator = put(base / 'evaluator.py', b'generated-evaluator-private')
        panel = put(base / 'panel.json', {'n_eval': 574, 'n_train': 2295, 'bin_ms': 20})
        protocol = put(base / 'protocol.json', {'input_commitments': {'test_panel_sha256': panel['sha256']},
                         'exposure': {'target_sha256': target['sha256']}})
        freezes = {}
        freeze_values = {}
        history = {}
        for i, arm in enumerate(self.a.ARMS):
            freeze = {'schema': 'smc_nlb_prediction_freeze_v1', 'arm': arm, 'dataset': 'mc_maze_20',
                      'role': 'author_calibration', 'particles': 192, 'repeats': 32, 'seed': 20261117 + i,
                      'submission_sha256': predictions[arm]['sha256'], 'panel_manifest_sha256': panel['sha256'],
                      'protocol_sha256': protocol['sha256'], 'reference_panel_sha256': files['reference_panel.json']['sha256'],
                      'method_id': 'generated-' + arm}
            freezes[arm] = put(base / (arm + '-freeze.json'), freeze)
            freeze_values[arm] = freeze
            history[arm] = {'prediction_sha256': predictions[arm]['sha256'], 'prediction_bytes': predictions[arm]['bytes'],
                            'freeze_receipt_sha256': freezes[arm]['sha256'],
                            'observed_metrics': {k: (j + i) / 8 for j, k in enumerate(self.a.METRICS)},
                            'score_report_sha256': str(i + 3) * 64,
                            'scoring_dependency_versions': {**self.a.PACKAGES, 'h5py': '3.11.0'},
                            'scoring_execution': {'supervisor_success': i == 0, 'supervisor_exit_code': i,
                              'failure': None if i == 0 else 'ValueError: Scorer identity changed'}}
        calibration_value = {'completion': {'author_reference_calibration_outputs_accepted': True,
                                             'both_supervised_scoring_stages_passed': False}, 'arms': history}
        calibration = put(base / 'calibration.json', calibration_value)
        pins = {n: {k: row[k] for k in ('bytes', 'sha256')} for n, row in {
            'panel': panel, 'protocol': protocol, 'historical_calibration': calibration, 'target': target,
            'evaluator': evaluator, 'scorer.py': files['scorer.py'], 'reference_panel.json': files['reference_panel.json']}.items()}
        request = {'schema': 'smc_historical_reference_grade_request_v1', 'source': source_row,
                   'predictions': predictions, 'freezes': freezes, 'panel': panel, 'protocol': protocol,
                   'historical_calibration': calibration, 'target': target, 'evaluator': evaluator,
                   'output_root': str(base / 'out'), 'scratch_bytes': 3 * 1024**2}
        request_row = put(base / 'request.json', request)
        events = []
        guarded = {target['path'], evaluator['path']}

        def body(filename, expected=None):
            if str(filename) in guarded:
                events.append(('FORBIDDEN_EARLY_BODY', str(filename)))
                raise AssertionError('Adapter metadata must not read protected bodies')
            return self.a.body(filename, expected)

        def snapshot(src, dst, expected, cap):
            try:
                result = self.a.copy_snapshot(src, dst, expected, cap)
            finally:
                if Path(dst).exists():
                    charge(Path(dst).stat().st_size)
            events.append(('snapshot', Path(dst).stem))
            return result

        def publish(filename, value):
            charge(len(encode(value)))
            return self.a.publish(filename, value)

        api = cloned(self.a, HERE=source, PINS=pins, body=body, copy_snapshot=snapshot, publish=publish,
                     PREDICTIONS={a: {k: r[k] for k in ('bytes', 'sha256')} for a, r in predictions.items()},
                     FREEZES={a: {k: r[k] for k in ('bytes', 'sha256')} for a, r in freezes.items()})
        return types.SimpleNamespace(base=base, source=source, api=api, request=request, row=request_row,
                                     freezes=freeze_values, calibration=calibration_value, events=events, pins=pins)

    def score_value(self, f, arm):
        req, freeze = f.request, f.freezes[arm]
        return {'schema': 'smc_nlb_operator_score_v1', 'arm': arm, 'role': 'author_calibration',
                'method_id': freeze['method_id'], 'submission_sha256': req['predictions'][arm]['sha256'],
                'prediction_freeze_sha256': req['freezes'][arm]['sha256'], 'panel_manifest_sha256': req['panel']['sha256'],
                'protocol_sha256': req['protocol']['sha256'], 'reference_panel_sha256': f.pins['reference_panel.json']['sha256'],
                'scorer_sha256': req['evaluator']['sha256'], 'target_sha256': req['target']['sha256'],
                'dependency_versions': self.a.PACKAGES,
                'metrics': {k: v + 0.125 for k, v in f.calibration['arms'][arm]['observed_metrics'].items()}}

    def numerical_boundary(self, f, reject_freeze=None):
        def validate_freeze(prediction, panel, protocol, freeze):
            arm = Path(prediction).stem
            self.assertEqual([x[1] for x in f.events if x[0] == 'snapshot'], list(self.a.ARMS))
            f.events.append(('freeze', arm))
            if arm == reject_freeze:
                raise ValueError('generated full-array freeze rejection')
            return f.freezes[arm]

        def score(*args):
            arm = Path(args[0]).stem
            self.assertEqual([x[1] for x in f.events if x[0] == 'freeze'], list(self.a.ARMS))
            self.assertTrue((Path(f.request['output_root']) / 'BOTH_SNAPSHOTS.json').is_file())
            f.events.append(('target_access', arm))
            # Only generated bytes, standing in for the private numerical boundary.
            self.assertEqual(Path(args[4]).read_bytes(), b'generated-target-private')
            value = self.score_value(f, arm)
            put(Path(args[-1]), value)
            return value

        def load_scorer():
            self.assertEqual([x[1] for x in f.events if x[0] == 'snapshot'], list(self.a.ARMS))
            f.events.append(('load_numerical_boundary', None))
            return types.SimpleNamespace(validate_freeze=validate_freeze, score_predictions=score)

        return types.SimpleNamespace(versions=lambda: dict(self.a.PACKAGES), load_scorer=load_scorer)

    def run_fixture(self, f, reject_freeze=None):
        # Clone the already copied function namespace, keeping its generated pins.
        ns = dict(f.api.run.__globals__)
        boundary = self.numerical_boundary(f, reject_freeze)
        ns.update(versions=boundary.versions, load_scorer=boundary.load_scorer)
        run = types.FunctionType(self.a.run.__code__, ns, 'run')
        return run(f.row['path'], f.row['sha256'])

    def actor(self):
        token = 'a' * 32
        base_labels = {'codex.generated-runtime': 'source-fixture'}
        labels = {**base_labels, **{k: 'generated' for k in self.labels.OMITTED_DESKTOP_KEYS}}
        source = self.root / 'mounted-source'; source.mkdir()
        entry = put(source / 'child.py', b'generated child source')
        target = put(self.root / 'private-target', b'generated private bytes')
        work = self.root / 'report'; work.mkdir()
        actor = {'role': 'grade', 'token': token, 'operation_id': 'smc-historical-reference-grade-' + token,
                 'image_id': self.h.IMAGE_ID, 'architecture': 'arm64', 'image_labels': labels,
                 'container_base_labels': base_labels, 'image_environment': ['PATH=/usr/local/bin:/usr/bin:/bin'],
                 'entrypoint': entry, 'arguments': ['--request', str(self.root / 'request.json'), '--sha256', 'b' * 64],
                 'workdir': str(work), 'scratch_dir': '/tmp', 'uid': 0, 'gid': 0,
                 'readonly_mounts': [{'source': str(source), 'destination': str(source)},
                                     {'source': target['path'], 'destination': target['path']}],
                 'writable_mounts': [{'source': str(work), 'destination': str(work)}]}
        return actor, [target['path']]

    def container(self, actor, built):
        h = {'Memory': built['memory'], 'MemorySwap': built['memory'], 'NanoCpus': 1000000000,
             'PidsLimit': 128, 'ReadonlyRootfs': True, 'Privileged': False, 'NetworkMode': 'none',
             'IpcMode': 'private', 'ShmSize': 16777216, 'CapDrop': ['ALL'], 'AutoRemove': False,
             'LogConfig': {'Type': 'none'}, 'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0},
             'CapAdd': ['CAP_DAC_OVERRIDE'], 'PidMode': '', 'CgroupnsMode': 'private', 'UsernsMode': '',
             'SecurityOpt': ['no-new-privileges:true'], 'Devices': [], 'DeviceRequests': [], 'PortBindings': {},
             'VolumesFrom': [], 'Links': [], 'ExtraHosts': [], 'Binds': [], 'GroupAdd': [], 'DeviceCgroupRules': [],
             'Init': False, 'CgroupParent': '',
             'Ulimits': [{'Name': n, 'Soft': s, 'Hard': h} for n, s, h in [('nofile', 1024, 1024), ('core', 0, 0), ('cpu', 600, 605)]],
             'Tmpfs': {'/tmp': 'rw,nosuid,nodev,noexec,size=1073741824,mode=1777'}}
        labels = {**actor['container_base_labels'], 'codex.smc-historical-reference': actor['token'],
                  'codex.smc-historical-operation': actor['operation_id']}
        c = {'Image': actor['image_id'], 'Labels': labels, 'User': '0:0', 'Entrypoint': [self.h.PYTHON],
             'Cmd': ['-I', '-B', actor['entrypoint']['path'], *actor['arguments']], 'WorkingDir': actor['workdir'],
             'Volumes': None, 'Env': [k + '=' + v for k, v in self.h.environment(actor).items()]}
        return {'Id': 'c' * 64, 'Name': '/' + built['name'], 'Image': actor['image_id'], 'Config': c,
                'HostConfig': h, 'State': {'Running': False, 'Status': 'exited'},
                'Mounts': [{'Type': 'bind', 'Propagation': 'rprivate', 'Source': m['source'],
                            'Destination': m['destination'], 'RW': writable}
                           for key, writable in [('readonly_mounts', False), ('writable_mounts', True)] for m in actor[key]]}

    @staticmethod
    def closed_call():
        return {'pid': 123, 'returncode': 0, 'errors': [], 'stdout': '', 'stderr': '',
                'cleanup': {'cleanup_complete': True, 'reaped': True, 'group_absence_observed': True,
                            'error': None, 'pid': 123, 'returncode': 0},
                'capture': {'all_eof_observed': True, 'storage_truncated': False, 'read_ceiling_exhausted': False,
                            'closed_without_eof': False, 'stream_close_errors': []}}


class AdapterControls(Base):
    def test_authenticated_metadata_and_second_arm_tamper_are_target_blind(self):
        manifest_path = ROOT / 'adapter/SOURCE.json'
        raw = manifest_path.read_bytes()
        selected = {'path': str(manifest_path), **pin(raw)}
        self.assertEqual(self.a.source_identity(selected), selected)
        manifest = json.loads(raw)
        self.assertEqual(manifest['files']['scorer.py'], self.a.PINS['scorer.py'])
        self.assertEqual(manifest['files']['reference_panel.json'], self.a.PINS['reference_panel.json'])

        f = self.fixture()
        actual, freezes, historical = f.api.metadata(f.row['path'], f.row['sha256'])
        self.assertEqual(actual, f.request); self.assertEqual(freezes, f.freezes)
        self.assertFalse(historical['arms']['noncausal']['scoring_execution']['supervisor_success'])
        self.assertEqual(f.events, [])
        with self.assertRaisesRegex(ValueError, 'request changed'):
            f.api.metadata(f.row['path'], '0' * 64)
        freeze = Path(f.request['freezes']['noncausal']['path'])
        original = freeze.read_bytes(); put(freeze, original + b' ')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            f.api.metadata(f.row['path'], f.row['sha256'])
        self.assertEqual(f.events, [])
        put(freeze, original)
        leaf = f.source / 'historical_score.py'; put(leaf, b'drift')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            f.api.metadata(f.row['path'], f.row['sha256'])
        self.assertEqual(f.events, [])

    def test_both_snapshots_and_freezes_precede_target_complete_vectors_preserve_history(self):
        f = self.fixture()
        result = self.run_fixture(f)
        kinds = [x[0] for x in f.events]
        self.assertEqual(kinds, ['snapshot', 'snapshot', 'load_numerical_boundary', 'freeze', 'freeze', 'target_access', 'target_access'])
        self.assertEqual(result['status'], 'both_original_predictions_scored')
        for arm in self.a.ARMS:
            row = result['arms'][arm]
            self.assertEqual(set(row['metrics']), set(self.a.METRICS))
            self.assertEqual(row['signed_delta_from_historical'], {k: 0.125 for k in self.a.METRICS})
            self.assertEqual(row['historical_supervision'], f.calibration['arms'][arm]['scoring_execution'])
            self.assertEqual(Path(row['snapshot']['path']).read_bytes(), Path(f.request['predictions'][arm]['path']).read_bytes())
        for key in ('new_inference_executed', 'participant_episode_executed', 'AI_trial_executed', 'reproduction_claim',
                    'improvement_claim', 'SOTA_claim', 'printed_checkpoint_row_linkage_established',
                    'supervised_completion_qualified_by_this_child', 'historical_noncausal_supervisor_success'):
            self.assertIs(result[key], False)
        self.assertIsNone(result['scientific_equivalence'])
        self.assertEqual(result['intentional_environment_variant'], {'package': 'h5py', 'historical': '3.11.0', 'selected': '3.10.0'})
        self.assertEqual(json.loads((Path(f.request['output_root']) / 'REPORT.json').read_bytes()), result)
        def checked(row, cap=self.h.META_CAP):
            self.assertNotIn(row['path'], [f.request['target']['path'], f.request['evaluator']['path'],
                                           *[x['path'] for x in f.request['predictions'].values()],
                                           *[x['snapshot']['path'] for x in result['arms'].values()]])
            return self.h.checked(row, cap)
        host = cloned(self.h, checked=checked)
        self.assertEqual(host.validate_report(result, f.request, f.row['sha256']), result)
        for kind in ('AI_claim', 'historical_success', 'missing_metric', 'wrong_delta', 'barrier_drift'):
            bad = copy.deepcopy(result)
            if kind == 'AI_claim': bad['AI_trial_executed'] = True
            elif kind == 'historical_success': bad['historical_noncausal_supervisor_success'] = True
            elif kind == 'missing_metric': del bad['arms']['causal']['metrics']['co-bps']
            elif kind == 'wrong_delta': bad['arms']['noncausal']['signed_delta_from_historical']['co-bps'] = 123
            else: bad['barrier']['sha256'] = '0' * 64
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                host.validate_report(bad, f.request, f.row['sha256'])

    def test_second_prediction_drift_prevents_every_numerical_or_target_call(self):
        f = self.fixture()
        p = Path(f.request['predictions']['noncausal']['path'])
        put(p, b'X' * p.stat().st_size)
        with self.assertRaisesRegex(ValueError, 'Stable exact original snapshot bytes'):
            self.run_fixture(f)
        self.assertEqual(f.events, [('snapshot', 'causal')])
        self.assertFalse((Path(f.request['output_root']) / 'BOTH_SNAPSHOTS.json').exists())
        self.assertFalse((Path(f.request['output_root']) / 'REPORT.json').exists())

    def test_second_freeze_rejection_blocks_all_scoring(self):
        f = self.fixture()
        with self.assertRaisesRegex(ValueError, 'generated full-array freeze rejection'):
            self.run_fixture(f, reject_freeze='noncausal')
        self.assertFalse(any(x[0] == 'target_access' for x in f.events))
        self.assertEqual([x[1] for x in f.events if x[0] == 'snapshot'], list(self.a.ARMS))
        self.assertFalse((Path(f.request['output_root']) / 'REPORT.json').exists())

    def test_metric_vector_and_provenance_reject_missing_extra_nonfinite_or_wrong_arm(self):
        f = self.fixture()
        good = self.score_value(f, 'causal')
        self.assertEqual(f.api.validate_score(good, 'causal', f.request, f.freezes['causal']), good['metrics'])
        for kind in ('missing', 'extra', 'nan', 'infinite', 'boolean', 'wrong_arm', 'wrong_target', 'wrong_version'):
            bad = copy.deepcopy(good)
            if kind == 'missing': del bad['metrics']['co-bps']
            elif kind == 'extra': bad['metrics']['extra'] = 1
            elif kind == 'nan': bad['metrics']['co-bps'] = math.nan
            elif kind == 'infinite': bad['metrics']['co-bps'] = math.inf
            elif kind == 'boolean': bad['metrics']['co-bps'] = True
            elif kind == 'wrong_arm': bad['arm'] = 'noncausal'
            elif kind == 'wrong_target': bad['target_sha256'] = '0' * 64
            else: bad['dependency_versions']['h5py'] = '3.11.0'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                f.api.validate_score(bad, 'causal', f.request, f.freezes['causal'])

    def test_snapshot_bound_and_no_clobber_remain_real(self):
        src = self.root / 'prediction'; row = put(src, b'generated prediction')
        dst = self.root / 'snapshot'
        expected = {k: row[k] for k in ('bytes', 'sha256')}
        with self.assertRaisesRegex(ValueError, 'Prospectively bounded'):
            self.a.copy_snapshot(src, dst, expected, row['bytes'] - 1)
        self.assertFalse(dst.exists())
        try: self.a.copy_snapshot(src, dst, expected, row['bytes'])
        finally:
            if dst.exists(): charge(dst.stat().st_size)
        self.assertEqual(dst.read_bytes(), src.read_bytes())
        with self.assertRaises(FileExistsError):
            self.a.copy_snapshot(src, dst, expected, row['bytes'])
        self.assertEqual(dst.read_bytes(), src.read_bytes())


class ChildControls(Base):
    def test_one_whole_child_cpu_thread_budget_precedes_adapter_import(self):
        source = self.root / 'adapter'; source.mkdir()
        events = []
        payload = b"def run(path, sha):\n    events.append(('adapter_run', path, sha))\n"
        members = {n: put(source / n, payload if n == 'historical_score.py' else ('generated-' + n).encode())
                   for n in sorted(self.a.SOURCE_FILES)}
        manifest = put(source / 'SOURCE.json', {'schema': 'smc_historical_reference_grade_source_v1',
                   'files': {n: {k: r[k] for k in ('bytes', 'sha256')} for n, r in members.items()}})
        request = put(self.root / 'request.json', {'source': manifest, 'output_root': str(self.root / 'out')})
        installed = {}
        def setrlimit(kind, value): installed[kind] = value; events.append(('limit', kind, value))
        resource = types.SimpleNamespace(RLIMIT_CPU='cpu', RLIMIT_CORE='core', setrlimit=setrlimit,
                                         getrlimit=lambda k: installed[k])
        env = {}
        fake_os = types.SimpleNamespace(environ=env, umask=lambda x: events.append(('umask', x)))
        site = types.SimpleNamespace(main=lambda: events.append(('site', None)))
        def importer(name, *args, **kwargs):
            if name == 'site': return site
            return builtins.__import__(name, *args, **kwargs)
        def module_from_spec(spec):
            events.append(('adapter_import', None))
            m = types.ModuleType('_generated_numerical_adapter'); m.events = events; return m
        util = types.SimpleNamespace(spec_from_file_location=lambda *a: None, module_from_spec=module_from_spec)
        ns = dict(self.c.__dict__)
        ns.update(HERE=source, resource=resource, os=fake_os, sys=types.SimpleNamespace(dont_write_bytecode=False),
                  importlib=types.SimpleNamespace(util=util), __builtins__={**vars(builtins), '__import__': importer},
                  print=lambda *a, **k: None)
        main = types.FunctionType(self.c.main.__code__, ns, 'main', self.c.main.__defaults__)
        main(['--request', request['path'], '--sha256', request['sha256']])
        self.assertEqual(events[:2], [('limit', 'cpu', (600, 605)), ('limit', 'core', (0, 0))])
        self.assertEqual(sum(x[:2] == ('limit', 'cpu') for x in events), 1)
        self.assertEqual(env, {k: '1' for k in self.c.THREAD_KEYS})
        self.assertLess(next(i for i, x in enumerate(events) if x[0] == 'site'),
                        next(i for i, x in enumerate(events) if x[0] == 'adapter_import'))
        self.assertEqual(sum(x[0] == 'adapter_run' for x in events), 1)


class HostControls(Base):
    def test_one_actor_has_whole_two_arm_limits_and_exact_container_profile(self):
        actor, private = self.actor()
        built = self.h.build_create(actor, private)
        self.assertEqual((self.h.GRADE_MEMORY, self.h.CPU_SOFT, self.h.CPU_HARD, self.h.WORK_SECONDS,
                          self.h.CLEANUP_SECONDS), (2147483648, 600, 605, 720, 60))
        self.assertEqual(built['memory'], 2147483648); self.assertEqual(built['cpu_seconds'], 600)
        args = built['argv']
        for flag, value in (('--memory', '2147483648'), ('--memory-swap', '2147483648'), ('--cpus', '1'),
                            ('--network', 'none'), ('--pull', 'never')):
            self.assertEqual(args[args.index(flag) + 1], value)
        self.assertIn('cpu=600:605', args)
        container = self.container(actor, built)
        self.assertEqual(self.h.verify_container(container, actor, built), 'c' * 64)
        for key, bad in [('Memory', 4294967296), ('NanoCpus', 2000000000), ('NetworkMode', 'bridge'), ('Privileged', True)]:
            value = copy.deepcopy(container); value['HostConfig'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.h.verify_container(value, actor, built)
        tree = ast.parse((ROOT / 'runtime/historical_grade.py').read_bytes())
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_grade')
        calls = [n for n in ast.walk(run) if isinstance(n, ast.Call)]
        self.assertEqual(sum(isinstance(n.func, ast.Name) and n.func.id == 'build_create' for n in calls), 1)
        self.assertEqual(sum(isinstance(n.func, ast.Name) and n.func.id == 'OwnedProcesses' for n in calls), 1)
        self.assertEqual(sum(isinstance(n, ast.Constant) and n.value == 'wait_historical_grade' for n in ast.walk(run)), 1)
        for loop in (n for n in ast.walk(run) if isinstance(n, (ast.For, ast.While))):
            self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                 and n.func.id in {'build_create', 'OwnedProcesses'} for n in ast.walk(loop)))
            self.assertFalse(any(isinstance(n, ast.Constant) and n.value == 'wait_historical_grade'
                                 for n in ast.walk(loop)))

    def test_child_request_rejects_extra_arm_scratch_and_descriptor_drift(self):
        f = self.fixture()
        report = Path(f.request['output_root']).parent / 'report'
        req = copy.deepcopy(f.request); req['output_root'] = str(report / 'historical')
        self.assertEqual(self.h.validate_child_request(req, req['source'], report), req)
        for kind in ('extra_arm', 'over_scratch', 'boolean_scratch', 'wrong_source', 'relative_target', 'extra_field'):
            bad = copy.deepcopy(req)
            if kind == 'extra_arm': bad['predictions']['extra'] = bad['predictions']['causal']
            elif kind == 'over_scratch': bad['scratch_bytes'] = 536870913
            elif kind == 'boolean_scratch': bad['scratch_bytes'] = True
            elif kind == 'wrong_source': bad['source']['sha256'] = '0' * 64
            elif kind == 'relative_target': bad['target']['path'] = 'relative-target'
            else: bad['participant_owner'] = {'qualified': True}
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.h.validate_child_request(bad, req['source'], report)

    def test_failure_or_uncertain_closure_never_success(self):
        call = self.closed_call()
        closed = {'container_absent': True}
        good = self.h.completion(None, closed, [call])
        self.assertEqual(good, {'success': True, 'status': 'graded', 'container_absent': True, 'calls_closed': True})
        for label, mutate in (
            ('missing_errors', lambda c: c.pop('errors')),
            ('error', lambda c: c['errors'].append({'message': 'generated failure'})),
            ('not_reaped', lambda c: c['cleanup'].update(reaped=False)),
            ('group_alive', lambda c: c['cleanup'].update(group_absence_observed=False)),
            ('not_eof', lambda c: c['capture'].update(all_eof_observed=False)),
            ('truncated', lambda c: c['capture'].update(storage_truncated=True)),
            ('read_ceiling', lambda c: c['capture'].update(read_ceiling_exhausted=True))):
            bad = copy.deepcopy(call); mutate(bad)
            with self.subTest(label=label):
                outcome = self.h.completion(None, closed, [bad])
                self.assertFalse(outcome['success'])
                self.assertEqual(outcome['status'], 'failed' if label in ('missing_errors', 'error') else 'closure_unknown')
        self.assertEqual(self.h.completion(None, {'container_absent': False}, [call])['status'], 'closure_unknown')
        self.assertEqual(self.h.completion({'message': 'score failed'}, closed, [call])['status'], 'failed')
        bad = copy.deepcopy(call); bad['returncode'] = bad['cleanup']['returncode'] = 1
        with self.assertRaisesRegex(ValueError, 'successful owned process'): self.h.validate_process(bad)

    def test_cleanup_requires_acknowledged_identity_and_preserves_ambiguous_create(self):
        actor, private = self.actor(); built = self.h.build_create(actor, private)
        class Owner:
            def __init__(owner, inspections): owner.inspections = iter(inspections); owner.commands = []
            def inspect(owner, identity, deadline): return next(owner.inspections)
            def cli(owner, argv, deadline, label, *rest):
                owner.commands.append(argv)
                return {**self.closed_call(), 'stdout': 'c' * 64}
        profile = types.SimpleNamespace(verify_container=self.h.verify_container)
        owner = Owner([None])
        with self.assertRaisesRegex(ValueError, 'unacknowledged create'):
            self.h.cleanup_actor(owner, profile, actor, built, None, True, 123)
        self.assertEqual(owner.commands, [])
        result = self.h.cleanup_actor(Owner([None]), profile, actor, built, 'c' * 64, True, 123)
        self.assertTrue(result['container_absent'])
        owner = Owner([self.container(actor, built), None])
        result = self.h.cleanup_actor(owner, profile, actor, built, 'c' * 64, True, 123)
        self.assertTrue(result['container_absent']); self.assertEqual(owner.commands, [['container', 'rm', 'c' * 64]])
        bad = self.container(actor, built); bad['Id'] = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'same acknowledged container'):
            self.h.cleanup_actor(Owner([bad]), profile, actor, built, 'c' * 64, True, 123)


class ImagePolicyControls(load('image_policy', 'controls/test_image_policy.py').ImagePolicyControls):
    EXTRA_FIXTURES = ()

    def setUp(self):
        global ACTIVE
        initialize()
        ACTIVE = True
        self.addCleanup(self.release_guard)
        self.host = load('host', 'runtime/historical_grade.py')

    @staticmethod
    def release_guard():
        global ACTIVE
        ACTIVE = False

    def fixtures(self):
        return super().fixtures() + list(self.EXTRA_FIXTURES)


def main():
    initialize()
    program = unittest.main(exit=False)
    result = program.result
    receipt = {'schema': 'smc-historical-reference-source-controls/v1', 'testsRun': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
               'successful': result.wasSuccessful(), 'source_identities': SOURCES,
               'fixture_write_bytes_before_receipt': WRITTEN, 'cumulative_generated_fixture_bytes': 0,
               'receipt_bytes': 0, 'includes_rewrites_deleted_files_and_attempted_publications': True,
               'limit_bytes': LIMIT, 'native_or_scientific_execution_qualified': False,
               'numerical_scorer_and_operating_system_boundaries_are_generated_doubles': True}
    for _ in range(8):
        raw = encode(receipt)
        updated = (len(raw), WRITTEN + len(raw))
        if updated == (receipt['receipt_bytes'], receipt['cumulative_generated_fixture_bytes']): break
        receipt['receipt_bytes'], receipt['cumulative_generated_fixture_bytes'] = updated
    put(ARTIFACT_ROOT / 'CONTROL_RESULT.json', receipt)
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
