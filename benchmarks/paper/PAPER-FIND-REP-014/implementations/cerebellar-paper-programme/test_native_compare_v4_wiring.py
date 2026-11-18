"""Changed-only dispatch/source-closure controls; no native phase or AI run.

Optional roots compose a private derivative with pinned unchanged text bodies.
An integrated public checkout needs no arguments. No copied scientific suites.
"""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--base-root', type=Path, default=Path(__file__).resolve().parent)
parser.add_argument('--comparator-root', type=Path, default=Path(__file__).resolve().parent)
ARGS, UNIT_ARGS = parser.parse_known_args()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ARGS.comparator_root))


def body(name):
    for root in (HERE, ARGS.comparator_root, ARGS.base_root):
        path = root / name
        if path.is_file():
            return path.read_bytes()
    raise FileNotFoundError(name)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def document(name):
    return json.loads(body(name))


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_text_module(name, filename):
    module = types.ModuleType(name)
    module.__file__ = str(HERE / filename)
    sys.modules[name] = module
    exec(compile(body(filename), module.__file__, 'exec'), module.__dict__)
    return module


load_text_module('paper_i_central_safety', 'central-integration/safety.py')
SOURCE = load_text_module('paper_i_central_source', 'central-integration/source.py')
MANIFEST_NAME = 'EXECUTABLE_SOURCE_MANIFEST.json'
MANIFEST = document(MANIFEST_NAME)
MANIFEST_PIN = pin(body(MANIFEST_NAME))


class OverlayIO:
    """Same exact read-pin interface; no directory clone or native execution."""
    root = HERE / 'virtual-programme'

    def __init__(self, faults=None):
        self.faults = faults or {}
        self.reads = []

    def read(self, path, expected, cap, allow_empty=False):
        name = Path(path).relative_to(self.root).as_posix()
        self.reads.append(name)
        raw = body(name)
        if name in self.faults:
            if self.faults[name] is None:
                raise FileNotFoundError(name)
            raw = self.faults[name]
        need(len(raw) <= cap and (bool(raw) or allow_empty), 'Read bounds')
        need(pin(raw) == expected, 'Exact captured source pin')
        return raw


def capture(io, manifest_pin=MANIFEST_PIN):
    return SOURCE.capture_parent(io, io.root, io.root / MANIFEST_NAME, manifest_pin)


def generated_native_tree():
    from core import BRANCHES
    names = BRANCHES['CF_novice']['targets']
    return {
        'schema': 'filio_native_numeric_v1', 'family': 'CF_novice',
        'roots': [{'name': n, 'class': 'double', 'shape': [1, 1]} for n in names],
        'records': [{'key': n, 'source_class': 'double', 'shape': [1, 1],
                     'values': [1.0], 'codes': [0]} for n in names],
        'metadata': {'native_sessions': 1.0, 'session_cell_counts': 1.0,
                     'condition': 'first DA training session'},
        'matlab_version': 'generated-wiring-fixture',
    }


def dispatch_adapter():
    # Compile the actual changed dispatch function only. Scope and request
    # validation are boundary fixtures; no transport qualification is claimed.
    tree = ast.parse(body('worker.py'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'dispatch')
    namespace = {}

    class Scope:
        def __init__(self, store, name, writable=False):
            self.store, self.name = store, name

        def json(self, path, expected):
            need(self.name == 'input', 'Only input scope reads')
            need(expected == 'generated-' + path, 'Forwarded input pin')
            return self.store['trees'][path]

        def tick(self):
            self.store['ticks'] += 1

    def validate(request):
        need(request == {'action': 'final_evaluate'}, 'Focused generated request')

    namespace.update(Scope=Scope, _validate_request=validate)
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual-worker-dispatch>', 'exec'), namespace)
    return namespace['dispatch']


class NativeWiring(unittest.TestCase):
    def test_actual_dispatch_selects_v4_for_both_arms(self):
        dispatch = dispatch_adapter()
        payload = {'schema': 'paper_i_worker_native_grade_v1', 'branch': 'CF_novice',
                   **{r: {'path': r, 'pin': 'generated-' + r} for r in ('reference', 'A', 'B')}}
        for bad in (None, 'A', 'B'):
            with self.subTest(bad_arm=bad):
                store = {'trees': {r: generated_native_tree() for r in ('reference', 'A', 'B')}, 'ticks': 0}
                if bad:
                    store['trees'][bad]['metadata']['native_sessions'] += 1e-9
                    with self.assertRaises(ValueError):
                        dispatch({'action': 'final_evaluate'}, payload, store)
                else:
                    result = dispatch({'action': 'final_evaluate'}, payload, store)
                    self.assertFalse(result['biological_truth'])
                    self.assertEqual(store['ticks'], 1)
                    for arm in ('A', 'B'):
                        self.assertEqual(result['arms'][arm]['metadata_policy'],
                                         'historical_source_declared_discrete_exact_v1')

    def test_real_capture_loads_all_41_exact_source_bodies(self):
        io = OverlayIO()
        bundle = capture(io)
        self.assertEqual(len(bundle['files']), 41)
        self.assertEqual(sum(len(b) for b in bundle['bodies'].values()), 457439)
        self.assertEqual(set(io.reads), {MANIFEST_NAME} | set(bundle['files']))
        self.assertEqual(bundle['manifest'], MANIFEST_PIN)

    def test_capture_rejects_missing_or_tampered_comparator_dependencies(self):
        for name in ('native_compare_v2.py', 'native_compare_v3.py', 'native_compare_v4.py'):
            for fault in (None, body(name) + b'\n# unexpected mutation\n'):
                with self.subTest(dependency=name, missing=fault is None):
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        capture(OverlayIO({name: fault}))
        bad = copy.deepcopy(MANIFEST)
        bad['files'] = [r for r in bad['files'] if r['path'] != 'native_compare_v4.py']
        raw = (json.dumps(bad) + '\n').encode()
        with self.assertRaises(ValueError):
            capture(OverlayIO({MANIFEST_NAME: raw}), pin(raw))

    def test_recursive_binding_and_freeze_cover_actual_41_plus_central_sources(self):
        bindings = document('central-integration/BINDINGS.json')
        central = document('central-integration/SOURCE_MANIFEST.json')
        freeze = document('central-integration/QUALIFICATION_SOURCE_FREEZE.json')
        proposed = document('central-integration/manifest.proposed.json')
        parent, cr = bindings['parent_root'], bindings['central_root']
        self.assertEqual({k: bindings['parent_manifest'][k] for k in MANIFEST_PIN}, MANIFEST_PIN)
        self.assertEqual({k: central['parent_manifest'][k] for k in MANIFEST_PIN}, MANIFEST_PIN)
        self.assertEqual(document('central-integration/TEMPLATES.json')['runtime_profile']['parent_manifest'], MANIFEST_PIN)
        for row in MANIFEST['files']:
            self.assertEqual(freeze['files'][parent + '/' + row['path']], pin(body(row['path'])))
        for name, expected in central['files'].items():
            self.assertEqual(expected, pin(body('central-integration/' + name)))
            self.assertEqual(freeze['files'][cr + '/' + name], expected)
        self.assertEqual(central['bytes'], sum(p['bytes'] for p in central['files'].values()))
        self.assertEqual(freeze['bytes'], sum(p['bytes'] for p in freeze['files'].values()))
        self.assertEqual(len(freeze['files']), 129)
        self.assertEqual(freeze['files'][parent + '/' + MANIFEST_NAME], MANIFEST_PIN)
        self.assertEqual(freeze['files'][cr + '/SOURCE_MANIFEST.json'], pin(body('central-integration/SOURCE_MANIFEST.json')))
        for ref, name in ((proposed['program_execution']['parent_source'], MANIFEST_NAME),
                          (proposed['provenance']['parent'], MANIFEST_NAME),
                          (proposed['program_execution']['preferred_source_interface']['source'], 'central-integration/SOURCE_MANIFEST.json'),
                          (proposed['program_execution']['source_freeze'], 'central-integration/QUALIFICATION_SOURCE_FREEZE.json')):
            self.assertEqual({k: ref[k] for k in MANIFEST_PIN}, pin(body(name)))
        entry = ast.parse(body('central-integration/entry.py'))
        binding_pin = next(n.value for n in entry.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'BINDINGS_PIN' for t in n.targets))
        self.assertEqual(ast.literal_eval(binding_pin), pin(body('central-integration/BINDINGS.json')))
        self.assertEqual(proposed['program_execution']['scope']['original_runtime_files'], 41)
        self.assertEqual(proposed['program_execution']['entrypoint']['sha256'],
                         pin(body('central-integration/entry.py'))['sha256'])

    def test_actual_receipt_identity_gate_accepts_derivative_and_rejects_legacy(self):
        tree = ast.parse(body('central-integration/receipts.py'))
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Expr)
                 and isinstance(n.value, ast.Call) and n.value.args
                 and isinstance(n.value.args[-1], ast.Constant)
                 and n.value.args[-1].value in (
                     'Exactly the selected immutable41-member runtime',
                     'Selected immutable executable manifest identity')]
        self.assertEqual(len(nodes), 2)
        code = compile(ast.Module(body=nodes, type_ignores=[]), '<actual-receipt-identity-gates>', 'exec')
        files = {r['path']: {k: r[k] for k in ('bytes', 'sha256')} for r in MANIFEST['files']}
        environment = {'require': need, 'equal': lambda a, b, msg: need(a == b, msg),
                       'core': types.SimpleNamespace(TASK='PAPER-FIND-REP-014'), 'TASK': 'PAPER-FIND-REP-014',
                       'files': files, 'manifest_pin': MANIFEST_PIN}
        exec(code, environment)
        for changes in ({'manifest_pin': {'bytes': 6012, 'sha256': '198aff81c325e3cd56414dbff3e6af5bcc1161995196abb94370340b9a3a2e12'}},
                        {'files': {k: v for k, v in files.items() if k != 'native_compare_v4.py'}}):
            with self.assertRaises(ValueError):
                exec(code, {**environment, **changes})

    def test_source_copy_budget_uses_actual_new_extents(self):
        tree = ast.parse(body('central-integration/runner.py'))
        expression = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'clone_bytes' for t in n.targets))
        central = document('central-integration/SOURCE_MANIFEST.json')
        bodies = {n: body('central-integration/' + n) for n in central['files']}
        context = {'bodies': bodies, 'own_manifest_raw': body('central-integration/SOURCE_MANIFEST.json')}
        actual = eval(compile(ast.Expression(expression), '<actual-clone-budget>', 'eval'), {'context': context})
        self.assertEqual(actual, sum(map(len, bodies.values())) + len(context['own_manifest_raw'])
                         + MANIFEST['bytes'] + MANIFEST_PIN['bytes'])
        tree = ast.parse(body('central-integration/binding.py'))
        comparison = next(n for n in ast.walk(tree) if isinstance(n, ast.Compare)
                          and isinstance(n.left, ast.Subscript)
                          and isinstance(n.left.slice, ast.Constant)
                          and n.left.slice.value == 'source_copy_retained_bytes')
        code = compile(ast.Expression(comparison), '<actual-source-copy-floor>', 'eval')
        floor = MANIFEST['bytes'] + MANIFEST_PIN['bytes']
        self.assertTrue(eval(code, {'profile': {'source_copy_retained_bytes': floor}}))
        self.assertFalse(eval(code, {'profile': {'source_copy_retained_bytes': floor - 1}}))

    def test_qualification_authority_and_future_profile_remain_disabled(self):
        self.assertFalse(MANIFEST['actual_execution_authorized'])
        self.assertFalse(MANIFEST['qualification'])
        self.assertTrue(document('central-integration/BINDINGS.json')['source_only_unqualified'])
        central = document('central-integration/SOURCE_MANIFEST.json')
        self.assertFalse(central['qualification'])
        self.assertFalse(central['execution_authorized'])
        freeze = document('central-integration/QUALIFICATION_SOURCE_FREEZE.json')
        self.assertFalse(freeze['qualification'])
        self.assertFalse(freeze['scientific_execution'])
        templates = document('central-integration/TEMPLATES.json')
        self.assertTrue(templates['future_profile_not_selected'])
        self.assertFalse(templates['qualification'])
        self.assertFalse(templates['execution_authorized'])
        self.assertTrue(all(v is False for v in templates['root_authority'].values() if type(v) is bool))
        self.assertEqual(document('central-integration/manifest.proposed.json')['status'], 'source_only_unqualified')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *UNIT_ARGS], verbosity=2)
