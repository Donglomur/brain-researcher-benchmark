"""Generated request ABI controls; no package imports or native execution.

Execute the controller's actual request-construction AST branch and writer,
then its actual private phase dispatcher with a recording training callback.
The source projection intentionally excludes admissions, transport and models;
these checks do not establish their execution or scientific qualification.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'benchmarks/paper/PAPER-FIND-ADD-003/implementations/hippocampal-programme'
CURRENT = ROOT / 'benchmarks/integrity/current-closures/input-hippocampal/EXECUTABLE_SOURCE_MANIFEST.json'


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identity(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def source_projections():
    controller = ast.parse((PACKAGE / 'controller.py').read_bytes())
    run = next(n for n in controller.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    science = [n for n in ast.walk(run) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'science' for t in n.targets)]
    need(len(science) == 1, 'Exactly one common science-request constructor')
    branches = [n for n in ast.walk(run) if isinstance(n, ast.If)
                and ast.unparse(n.test) == "action in ('train_model', 'analytic_prior')"
                and any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'family'
                                                         for t in s.targets) for s in n.body)]
    need(len(branches) == 1, 'Exactly one actual training/prior staging branch')
    branch = copy.deepcopy(branches[0])
    branch.orelse = []  # Do not execute unrelated scientific phases.
    writer = next(n for n in controller.body if isinstance(n, ast.FunctionDef) and n.name == 'write_job_files')
    preamble = ast.parse("action=planned['action']; role=planned['role']; mounts={}; views=[]").body
    body = ast.Module(body=preamble + [copy.deepcopy(science[0]), branch], type_ignores=[])
    ast.fix_missing_locations(body)
    writer_ast = ast.Module(body=[copy.deepcopy(writer)], type_ignores=[])
    ast.fix_missing_locations(writer_ast)
    phase = ast.parse((PACKAGE / 'phase.py').read_bytes())
    main = next(n for n in phase.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    phase_ast = ast.Module(body=[copy.deepcopy(main)], type_ignores=[])
    ast.fix_missing_locations(phase_ast)
    return (compile(body, str(PACKAGE / 'controller.py'), 'exec'),
            compile(writer_ast, str(PACKAGE / 'controller.py'), 'exec'),
            compile(phase_ast, str(PACKAGE / 'phase.py'), 'exec'))


class GeneratedBudget:
    def __init__(self, manifest):
        self.manifest = manifest

    def read_file(self, path, expected, cap):
        need(Path(path).name == 'TRAINING.json', 'Only generated training metadata is read')
        raw = encoded(self.manifest)
        need(len(raw) <= cap, 'Complete generated training metadata')
        return raw

    def save(self, path, raw):
        path.write_bytes(raw)
        return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class HippocampalRequestTests(unittest.TestCase):
    def setUp(self):
        self.construction, self.writer, self.phase = source_projections()
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.interface = json.loads((PACKAGE / 'native/INTERFACE.json').read_text())

    def construct(self, role='reference', action='train_model', family='neural', both_classes=True):
        case = {'fold': 0, 'generated_fixture': True}
        planned = {'id': 'generated-training', 'action': action, 'role': role, 'family': family, 'case': case}
        manifest = {'channels': 3, 'both_classes': both_classes}
        budget = GeneratedBudget(manifest)
        files = {'TRAINING.json': {'bytes': len(encoded(manifest)), 'sha256': identity(manifest)}}
        entry = {'directory': family, 'files': files, 'manifest': files['TRAINING.json']}
        env = {
            'planned': planned, 'profile': {'producer_seconds': 30},
            'transport_deadline': 60, 'op': {'model_limits': {'max_model_bytes': 4096},
                'preparation_limits': {'max_metadata_bytes': 4096},
                'sources': {'reference': {'root': str(self.root / 'source'),
                                         'files': {'native/h_fit.m': {'bytes': 1, 'sha256': '0' * 64}}}}},
            'phase': self.root / 'phase', 'folds': {identity(case): {
                'root': str(self.root / 'fold-source'), 'result': {'families': {family: entry}}}},
            'budget': budget, 'cap': 4096, 'Path': Path, 'need': need, 'identity': identity,
            'strict': json.loads, 'encoded': encoded,
            'materialize': lambda destination, origin, members, allowance:
                {'root': str(destination), 'files': copy.deepcopy(members)},
            'mount': lambda view, purpose: {'path': view['root'], 'purpose': purpose},
        }
        exec(self.construction, env)
        exec(self.writer, env)
        return env

    def test_all_reference_fit_families_reach_phase_with_native_request_contract(self):
        for family in ('neural', 'nuisance_clock', 'combined', 'shuffled_combined'):
            with self.subTest(family=family):
                env = self.construct(family=family)
                job_root = self.root / ('job-' + family)
                env['write_job_files'](job_root, env['science'],
                                       ['/usr/local/bin/python', '/operator/phase.py'], env['budget'], 4096)
                produced = json.loads((job_root / 'REQUEST.json').read_bytes())
                required = self.interface['request']['required_common_fields']
                self.assertTrue(set(required).issubset(produced))
                self.assertEqual(produced['schema'], self.interface['request']['schema'])
                self.assertEqual(produced['operation'], 'fit')
                self.assertEqual(produced['output_root'], '/output')
                self.assertEqual(produced['training_path'], self.interface['request']['fit_fields']['training_path'])
                self.assertEqual(produced['family'], family)
                self.assertEqual(produced['channels'], 3)
                captured = []

                def capture_request(path, cap):
                    self.assertEqual(path, '/job/REQUEST.json')
                    return (job_root / 'REQUEST.json').read_bytes()

                phase_env = {'strict': json.loads, 'capture': capture_request, 'need': need,
                             'BOOT': 1.0, 'time': SimpleNamespace(monotonic=lambda: 2.0),
                             'train': lambda request: captured.append(copy.deepcopy(request))}
                exec(self.phase, phase_env)
                phase_env['main']()
                self.assertEqual(len(captured), 1)
                self.assertEqual(captured[0], {**produced, 'local_deadline': 31.0})
                self.assertIn('/bridge', env['mounts'])

    def test_candidate_and_analytic_prior_requests_are_not_native_fit_requests(self):
        for role, action, family in [('A', 'train_model', 'neural'), ('B', 'train_model', 'combined'),
                                     ('reference', 'analytic_prior', 'clock_prior')]:
            with self.subTest(role=role, action=action):
                env = self.construct(role=role, action=action, family=family)
                self.assertNotIn('schema', env['science'])
                self.assertNotIn('operation', env['science'])
                self.assertNotIn('training_path', env['science'])
                self.assertNotIn('/bridge', env['mounts'])

    def test_training_class_gate_still_precedes_request_publication(self):
        for role in ('reference', 'A', 'B'):
            with self.subTest(role=role):
                with self.assertRaisesRegex(ValueError, 'both classes'):
                    self.construct(role=role, both_classes=False)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_current_manifest_only_changes_controller_and_keeps_historical_manifest(self):
        historical_path = PACKAGE / 'EXECUTABLE_SOURCE_MANIFEST.json'
        historical_raw = historical_path.read_bytes()
        historical = json.loads(historical_raw)
        current = json.loads(CURRENT.read_text())
        self.assertEqual(current['schema'], 'h_complete_executable_source_v1')
        self.assertEqual(current['predecessor_manifest']['bytes'], len(historical_raw))
        self.assertEqual(current['predecessor_manifest']['sha256'], hashlib.sha256(historical_raw).hexdigest())
        old = {r['path']: r for r in historical['files']}
        new = {r['path']: r for r in current['files']}
        self.assertEqual(set(old), set(new))
        self.assertEqual([name for name in old if old[name] != new[name]], ['controller.py'])
        for name, record in new.items():
            raw = (PACKAGE / name).read_bytes()
            self.assertEqual(len(raw), record['bytes'], name)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record['sha256'], name)
        self.assertFalse(current['scientific_qualification'])
        self.assertFalse(current['execution_authority'])


if __name__ == '__main__':
    unittest.main()
