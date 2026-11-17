"""Direct standard-library portability checks; no scientific or producer run.

Run Python 3.11 -I -S -B. This file is adjacent to the strict source child.
The numerical leaf used for the final deadline check is deliberately inert.
No test supplies grading approval, success receipts or protected records.
"""
import ast
import copy
from contextlib import contextmanager
import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

PACKAGE = Path(__file__).resolve().parent
CORE = PACKAGE / 'closed_paired_grading'
TREE = PACKAGE / 'source_tree'
SOURCE_PIN = {'bytes': 1644, 'sha256': '01b9b3571f31971defadb1af2fb6b0e798ae36fc108fd93e13af899871daea37'}
DEPENDENCY_PIN = {'bytes': 7068, 'sha256': 'd0f7081fe63a5b019dd3764bfbf4a1f1ece4376b4a20c9caa311e36ef56c3e13'}
ORIGINAL_CORE = {'capture_io.py': {'bytes': 5660, 'sha256': 'cdb124aa285ca164b33a4eadfb6a0b6634365355f6d0ecd4e6ed28aeeeafc730'}, 'grade_closed.py': {'bytes': 14134, 'sha256': 'd3c806bfa072ad0fa7fc7605adc33628efe6a178d919b9e50b826031b4bdf66e'}, 'paired_report.py': {'bytes': 14323, 'sha256': '2b68993e15bc52cacb59a534abe5e7e8a300552ea6a9f8a9c43d03dc71759684'}}
ORIGINAL_DEPENDENCY_PYTHON = {'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/baseline_program.py': {'bytes': 2641, 'sha256': '2ded3619c0e02a82baff1d457a92709554160fcd3c87d554693a164a2aafae6b'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/bootstrap.py': {'bytes': 1613, 'sha256': '0bc4e945d93eb34a3ea7bc635042eef48f1f6ec6264c1af3731ee2da592a4143'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/candidate_entry.py': {'bytes': 846, 'sha256': '58eea999fb421d5dd57397c82481ff1daf892252ebd50669251c1a2b82ab19ba'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/common.py': {'bytes': 8653, 'sha256': '18c00b7e3589a29517359af88c14ff6c6b5ffb5867b22198916b65aea7aa0cb4'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/controller.py': {'bytes': 7700, 'sha256': '818db5cc857e8849a4859eddf48b4700dbe56d83c589e2ddf68f2d01ade3ab0a'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/deferred_grade.py': {'bytes': 1442, 'sha256': 'c2c840f9f2f3c68740256c082e7ebc2a6941f5939e68021e2dfbe34e53622840'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/holder.py': {'bytes': 5241, 'sha256': '19fa350e17635d4e6db9b05ac973c549175cafee9fcfa3d78880726db61d8566'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/io_utils.py': {'bytes': 2996, 'sha256': '2f0ac23b3456432933c96e6579708b949b1e093659f99ebc6bfce5ae3f222f7e'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/native.py': {'bytes': 19568, 'sha256': '58dbe7d7f695ea898e747b66405d6e5b4d9b52f0ee41c172331b2fc40ed35e48'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/observe.py': {'bytes': 12855, 'sha256': 'd0ac3093e09a1cc77c58874ee70daa4032eaea4f4d73675f5c1634086d085720'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/order_core.py': {'bytes': 8096, 'sha256': 'ce7863a26f9bfc9156b0297e66302e6682db43c52b742ae71d902227fbb453c7'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/output_contract.py': {'bytes': 1987, 'sha256': '258b45dea139815a35d34fb51a1b0b15ce076de4f64b08142b84a5238b7336a2'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/policy.py': {'bytes': 3624, 'sha256': 'db3715cd9c6c3f66a13a551053ab0ba50df69162ebab6840d22a697778cd5754'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/process.py': {'bytes': 6710, 'sha256': '791ea3b0bab72ef4487b3c3fdd47a828f8effaa27ebf7a6872e3b4ed324e074d'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/program/worker.py': {'bytes': 2633, 'sha256': '24433c301929f9d6870d35a7b1b338a3c064768e160f02838b1e35665214ce11'}, 'authoring/delivery-20261105/common/remaining-builds-wave16/neural035-complete-program/registration/adapter.py': {'bytes': 31264, 'sha256': '881456c46bd0a5085bb6fd778251a09c3c15c363f3328c9b24758aee80ba116c'}, 'authoring/delivery-20261105/neural035/grade.py': {'bytes': 1135, 'sha256': '314b6eb86330ce537770b2bbe1ef8bdff5740daa2cb4c0e34e60aad4ec63d1d0'}, 'authoring/delivery-20261105/neural035/io_utils.py': {'bytes': 2996, 'sha256': '2f0ac23b3456432933c96e6579708b949b1e093659f99ebc6bfce5ae3f222f7e'}, 'authoring/delivery-20261105/neural035/load_public.py': {'bytes': 2220, 'sha256': '4edc0e7b6e40ae87a4f9c07ab612ceb05b8d1c9c674bc26bc00f584f121e4ba2'}, 'authoring/delivery-20261105/neural035/order_core.py': {'bytes': 8096, 'sha256': 'ce7863a26f9bfc9156b0297e66302e6682db43c52b742ae71d902227fbb453c7'}}
OMITTED = {'authoring/delivery-20261105/common/exports/neural035/DELIVERY_MANIFEST.json': {'bytes': 14333, 'sha256': '98732254d14620031e994b5435e9356b1308bb1ad05348913906bae1a5e9fdb3'}, 'authoring/delivery-20261105/neural035/BINDING.json': {'bytes': 382, 'sha256': '5c63126e3e8ce5736cdcd67d3719663065b499420bd743a69823df14a57fd049'}, 'authoring/delivery-20261105/neural035/delivery_manifest.json': {'bytes': 17534, 'sha256': 'cb469962e3a460fa273742805263e6b4aa66564850f659fd1b8466fa7a38f8ff'}}
CHECKS = []


def check(value, label):
    if not value:
        raise AssertionError(label)
    CHECKS.append(label)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def normal(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o644:
        raise AssertionError('ordinary 0644 single-link checkout: ' + str(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise AssertionError('symlink component: ' + str(part))


def expect(exception, message, callback):
    try:
        callback()
    except exception as error:
        if message not in str(error):
            raise AssertionError((message, str(error))) from error
        return error
    raise AssertionError('expected ' + exception.__name__ + ': ' + message)


def function(source, name):
    return next(node for node in ast.parse(source).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)


def body_hash(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def main():
    check(sys.version_info[:2] == (3, 11) and sys.flags.isolated and sys.flags.no_site
          and sys.dont_write_bytecode and not sys.flags.optimize,
          'Python 3.11 isolated no-site no-bytecode nonoptimized command')
    raw = (CORE / 'SOURCE_MANIFEST.json').read_bytes()
    check(pin(raw) == SOURCE_PIN, 'independently pinned exact source manifest')
    manifest = json.loads(raw)
    inventory = {'SOURCE_MANIFEST.json': SOURCE_PIN, **manifest['files']}
    check(set(p.name for p in CORE.iterdir()) == set(inventory) and len(inventory) == 10,
          'strict ten-member core inventory')
    bodies = {}
    for name, expected in inventory.items():
        path = CORE / name
        normal(path)
        bodies[name] = path.read_bytes()
        if pin(bodies[name]) != expected:
            raise AssertionError('core pin ' + name)
    check(True, 'all ten core bodies pinned in ordinary checkout')
    check(pin(bodies['DEPENDENCIES.json']) == DEPENDENCY_PIN, 'external dependency manifest binding')
    deps = json.loads(bodies['DEPENDENCIES.json'])
    check(len(deps['files']) == 31 and sum(v['bytes'] for v in deps['files'].values()) == 201827,
          'all 31 original prerequisite slots retained')
    check({name: deps['files'][name] for name in OMITTED} == OMITTED,
          'three external prerequisite descriptors remain exact')
    packaged = {name: descriptor for name, descriptor in deps['files'].items() if name not in OMITTED}
    actual = {p.relative_to(TREE).as_posix() for p in TREE.rglob('*') if not p.is_dir()}
    check(actual == set(packaged) and len(actual) == 28, 'exact 28-member packaged dependency inventory')
    check(all(not (TREE / name).exists() for name in OMITTED), 'no omitted record or dummy substitute')
    dependency_bodies = {}
    for name, expected in packaged.items():
        path = TREE / name
        normal(path)
        body = path.read_bytes()
        if pin(body) != expected:
            raise AssertionError('dependency pin ' + name)
        dependency_bodies[name] = body
        if name.endswith('.py'):
            ast.parse(body, filename=str(path))
            if pin(body) != ORIGINAL_DEPENDENCY_PYTHON[name]:
                raise AssertionError('original dependency Python changed: ' + name)
    check(len(ORIGINAL_DEPENDENCY_PYTHON) == 20, 'all 20 original dependency Python bodies exact and parsed only')
    for name, expected in ORIGINAL_CORE.items():
        check(pin(bodies[name]) == expected, 'original core exact: ' + name)
    for name, body in bodies.items():
        if name.endswith('.py'):
            ast.parse(body, filename=str(CORE / name))
    base = deps['base']
    program_manifest = json.loads(dependency_bodies[base + '/program/SOURCE_MANIFEST.json'])
    program = {name[len(base + '/program/'):]: body for name, body in dependency_bodies.items()
               if name.startswith(base + '/program/') and not name.endswith('/SOURCE_MANIFEST.json')}
    check(len(program) == 16 and {name: pin(body) for name, body in program.items()} == program_manifest['files'],
          'original full16 program manifest exact join')
    reg = json.loads(dependency_bodies[base + '/registration/BINDINGS.json'])
    check(reg['controller_members'] == program_manifest['files']
          and reg['controller_source'] == pin(dependency_bodies[base + '/program/SOURCE_MANIFEST.json']),
          'unchanged registration controller joins')
    reg_manifest = json.loads(dependency_bodies[base + '/registration/SOURCE_MANIFEST.json'])
    for name, expected in reg_manifest['files'].items():
        if pin(dependency_bodies[base + '/registration/' + name]) != expected:
            raise AssertionError('public registration manifest: ' + name)
    check(True, 'distinct public registration manifest binds actual public README')
    adapter = dependency_bodies[base + '/registration/adapter.py'].decode()
    check('ROOT = HERE.parents[5]' in adapter and (TREE / base / 'registration').parents[5] == TREE,
          'complete original path depth preserves adapter root')
    pair_ast = function(bodies['operator.py'], 'grade_pair')
    check(isinstance(pair_ast.body[-3], ast.With)
          and ast.unparse(pair_ast.body[-2]) == 'original.tick()'
          and ast.unparse(pair_ast.body[-1]) == 'return result',
          'actual final deadline check and return follow module cleanup')
    grade = bodies['grade_closed.py'].decode()
    positions = [grade.index(fragment) for fragment in (
        'authority.require_neural035_closed_pair_grading(', 'captures = Captures(budget)',
        'sources = source_loader.load(', 'pair = capture_closed_collection(',
        'root = path(prepared_root)', 'target_raw = captures.read(')]
    check(positions == sorted(positions), 'actual authority then closure then protected-target order')
    check('2024 * 101 + 1012 * 10' in grade and '99 surrogate peaks' in grade,
          'original full target/scientific scope unchanged')

    spec = importlib.util.spec_from_file_location('_neural035_public_portable_operator', CORE / 'operator.py')
    op = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(op)
    opens = []
    descriptor_wraps = []
    phase = [None]
    def audit(event, args):
        if event == 'open' and phase[0] is not None:
            if isinstance(args[0], (str, bytes, os.PathLike)):
                opens.append((phase[0], os.fspath(args[0])))
            elif type(args[0]) is int:
                descriptor_wraps.append((phase[0], args[0]))
    sys.addaudithook(audit)
    phase[0] = 'inspection'
    inspected = op.inspect(SOURCE_PIN, op._InspectBudget(2**20, 2**20, 30))
    phase[0] = None
    check(inspected['source_files'] == 10 and inspected['complete_inventory'] == inventory
          and inspected['module_code_executed'] is False and inspected['execution_authorized'] is False,
          'actual source inspection succeeds without execution authority')
    check(len(opens) == 10 and {Path(p) for _, p in opens} == {CORE / n for n in inventory},
          'actual inspection opens exactly ten core bodies')
    expect(ValueError, 'Stable exact captured source', lambda: op.inspect(
        {'bytes': SOURCE_PIN['bytes'], 'sha256': '0' * 64}, op._InspectBudget(2**20, 2**20, 30)))
    check(True, 'actual inspection refuses wrong manifest pin')

    sentinel_missing = object()
    aliases = tuple(op._ALIASES)
    prior = {name: sys.modules.get(name, sentinel_missing) for name in aliases}
    expected_namespace = {aliases[0]: None, aliases[1]: types.ModuleType('prior_pair'),
                          aliases[2]: sentinel_missing, aliases[3]: types.ModuleType('prior_grade')}
    def restored():
        return all(sys.modules.get(name, sentinel_missing) is value for name, value in expected_namespace.items())
    def set_namespace():
        for name, value in expected_namespace.items():
            if value is sentinel_missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    called = []
    deadline = time.monotonic() + 30
    class Denied:
        def require_neural035_closed_pair_grading(self, selection, observation):
            budget = sys._getframe(1).f_locals['budget']
            check(type(budget) is sys.modules['capture_io'].Budget, 'actual original Budget class reaches denied authority')
            check(budget.deadline == selection['deadline'] == deadline,
                  'caller absolute deadline preserved through actual grade_pair')
            compilation = sum(len(bodies[name]) for name in op._ALIASES.values())
            check(budget.read_bytes == sum(v['bytes'] for v in inventory.values()) + 10 + compilation
                  and budget.write_bytes == sum(v['bytes'] for v in inventory.values()) + len(b'{}\n'),
                  'actual capture compilation and observation debits carried')
            called.append(selection)
            raise PermissionError('portable test denies grading')
    def call(authority, limit):
        return op.grade_pair(SOURCE_PIN, TREE, PACKAGE / 'absent-producer', {}, b'{}', {},
                             PACKAGE / 'absent-protected', authority,
                             max_read_bytes=2**20, max_write_bytes=2**20, deadline=limit)
    try:
        set_namespace()
        phase[0] = 'denied'
        expect(PermissionError, 'portable test denies grading', lambda: call(Denied(), deadline))
        phase[0] = None
        check(len(called) == 1 and restored(), 'denied authority restores all four aliases including None and absence')
        check({Path(p) for stage, p in opens if stage == 'denied'} == {CORE / n for n in inventory},
              'actual denied authority opens no dependency producer or protected body')

        budget = op._InspectBudget(2**20, 2**20, 30)
        _, _, captured = op._capture(SOURCE_PIN, budget)
        with op._modules(CORE, captured, budget) as loaded:
            original_budget = loaded['capture_io'].Budget(2**20, 2**20, time.monotonic() + 30)
            captures = loaded['capture_io'].Captures(original_budget)
            phase[0] = 'missing'
            absent = next(name for name in deps['files'] if name in OMITTED)
            error = expect(FileNotFoundError, str(TREE / absent),
                           lambda: loaded['source_loader'].load(TREE, captures))
            phase[0] = None
            check(error.filename == str(TREE / absent), 'actual loader refuses genuine first missing prerequisite')
        check(restored(), 'missing prerequisite restores original module namespace')
        check([Path(p) for stage, p in opens if stage == 'missing'] == [CORE / 'DEPENDENCIES.json', TREE / absent],
              'missing prerequisite refusal executes no dependency entrypoint')

        real_modules = op._modules
        real_operator_time = op.time
        captured_clock_globals = []
        seen = []
        clock = [10.0]
        end = 20.0
        clock_facade = types.SimpleNamespace(monotonic=lambda: clock[0])
        inert_sentinel = object()
        @contextmanager
        def cleanup_boundary(root, captured_bodies, capture_budget):
            with real_modules(root, captured_bodies, capture_budget) as loaded:
                captured_io = loaded['capture_io']
                captured_clock_globals.append((captured_io, captured_io.time))
                captured_io.time = clock_facade
                def inert_leaf(*arguments):
                    original_budget = arguments[-1]
                    check(type(original_budget) is loaded['capture_io'].Budget and original_budget.deadline == end,
                          'deadline witness uses actual captured Budget and unchanged absolute deadline')
                    check(capture_budget.deadline == end and clock[0] == 10.0
                          and op.time is captured_io.time is clock_facade,
                          'both actual monotonic paths remain timely at the original fixed cutoff')
                    seen.append(original_budget)
                    return inert_sentinel
                loaded['_neural035_installed_grade'].grade_selected = inert_leaf
                yield loaded
            check(restored(), 'actual alias cleanup completes before final deadline witness')
            clock[0] = 21.0
        op.time = clock_facade
        op._modules = cleanup_boundary
        try:
            expect(ValueError, 'grading deadline', lambda: call(object(), end))
        finally:
            op._modules = real_modules
            op.time = real_operator_time
            for captured_io, original_time in captured_clock_globals:
                captured_io.time = original_time
        check(op.time is real_operator_time
              and all(module.time is original_time for module, original_time in captured_clock_globals),
              'operator and captured Budget clock facades fully restored')
        check(len(seen) == 1 and restored(), 'actual final deadline rejects elapsed cleanup with namespace restored')
    finally:
        phase[0] = None
        for name, value in prior.items():
            if value is sentinel_missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    print(json.dumps({'schema': 'neural035_public_portability_checks_v1', 'checks_passed': len(CHECKS),
                      'checks': CHECKS, 'core_files': 10, 'dependency_files': 28,
                      'omitted_prerequisites': 3,
                      'pathname_acquisitions': {label: sum(stage == label for stage, _ in opens)
                                                for label in ('inspection', 'denied', 'missing')},
                      'existing_descriptor_wraps': {label: sum(stage == label for stage, _ in descriptor_wraps)
                                                    for label in ('inspection', 'denied', 'missing')},
                      'complete_grading_claimed': False,
                      'scientific_campaign_run': False, 'authority_granted': False}, sort_keys=True))


if __name__ == '__main__':
    main()
