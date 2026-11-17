"""Fixed original source capture. No candidate/native module is executed."""
from pathlib import Path
import types
from capture_io import descriptor, need, parse, pin

DEPENDENCIES_PIN = {'bytes': 7068, 'sha256': 'd0f7081fe63a5b019dd3764bfbf4a1f1ece4376b4a20c9caa311e36ef56c3e13'}


def module(raw, filename, **bindings):
    out = types.ModuleType('neural035_closed_' + Path(filename).stem)
    out.__file__ = str(filename)
    out.__dict__.update(bindings)
    exec(compile(raw, str(filename), 'exec'), out.__dict__)
    return out


def load(repository, captures):
    root = Path(repository)
    decoded = captures.budget.decoded
    d = decoded(captures.read(Path(__file__).parent / 'DEPENDENCIES.json', 32768, DEPENDENCIES_PIN), 'source dependencies')
    need(d['schema'] == 'neural035_closed_grading_dependencies_v1', 'fixed dependency schema')
    bodies = {}
    for name, expected in d['files'].items():
        need(not name.startswith('/') and all(v not in ('', '.', '..') for v in name.split('/')),
             'fixed confined dependency')
        descriptor(expected, 2**20)
        bodies[name] = captures.read(root / name, 2**20, expected)
    base = root / d['base']
    prefix = d['base'] + '/program/'
    program = {name[len(prefix):]: raw for name, raw in bodies.items() if name.startswith(prefix)}
    pm = decoded(program.pop('SOURCE_MANIFEST.json'), 'original program manifest')
    need(set(program) == set(pm['files']) and len(program) == 16 and
         all(pin(program[n]) == p for n, p in pm['files'].items()), 'fixed full16 program')
    reg = decoded(bodies[d['base'] + '/registration/BINDINGS.json'], 'original registration binding')
    need(reg['controller_source'] == pin(bodies[prefix + 'SOURCE_MANIFEST.json']) and
         reg['controller_members'] == pm['files'], 'registration/program exact join')
    captures.budget.read(sum(len(program[n]) for n in ('common.py', 'order_core.py', 'output_contract.py',
        'deferred_grade.py', 'observe.py', 'policy.py')) + len(bodies[d['base'] + '/registration/adapter.py']),
        'captured source compilation')
    c = module(program['common.py'], base / 'program/common.py')
    core = module(program['order_core.py'], base / 'program/order_core.py')
    contract = module(program['output_contract.py'], base / 'program/output_contract.py', c=c)
    scorer = module(program['deferred_grade.py'], base / 'program/deferred_grade.py')
    adapter = module(bodies[d['base'] + '/registration/adapter.py'], base / 'registration/adapter.py')
    observer = module(program['observe.py'], base / 'program/observe.py')
    policy = module(program['policy.py'], base / 'program/policy.py', c=c)
    return types.SimpleNamespace(dependencies=d, program=program, reg=reg, c=c, core=core,
        contract=contract, scorer=scorer, adapter=adapter, observer=observer, policy=policy,
        base=base, source=reg['controller_source'],
        adapter_source=pin(bodies[d['base'] + '/registration/SOURCE_MANIFEST.json']),
        target_binding=decoded(bodies[d['private_binding_source']], 'original static grade binding'))
